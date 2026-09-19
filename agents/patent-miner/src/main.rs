use anyhow::{bail, Context, Result};
use battery_patent_miner::classify;
use battery_patent_miner::google;
use battery_patent_miner::io;
use battery_patent_miner::model::PatentRecord;
use battery_patent_miner::plan;
use battery_patent_miner::taxonomy::Taxonomy;
use battery_patent_miner::{AGENT_NAME, AGENT_VERSION};
use chrono::DateTime;
use clap::{Parser, Subcommand};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "patent-miner", version, about = "Battery patent discovery and classification agent")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Generate a date-bounded, classification-first source query.
    Plan {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long, default_value = "google-patents")]
        source: String,
        #[arg(long)]
        from: String,
        #[arg(long)]
        to: String,
        #[arg(long)]
        output: PathBuf,
    },
    /// Normalize a Google Patents Public Data export and classify every record.
    IngestGoogle {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        rejects: PathBuf,
        #[arg(long)]
        retrieved_at: String,
        #[arg(long, default_value_t = 0.60)]
        min_score: f64,
        #[arg(long, default_value_t = false)]
        include_unmatched: bool,
        #[arg(long, default_value_t = false)]
        allow_rejects: bool,
    },
    /// Reclassify already-normalized records after editing the taxonomy.
    Classify {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value_t = 0.60)]
        min_score: f64,
        #[arg(long, default_value_t = false)]
        include_unmatched: bool,
    },
    /// Fail closed if any normalized record violates the release contract.
    Validate {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long)]
        input: PathBuf,
    },
    /// Build a deterministic pending-review release manifest.
    Manifest {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        release_version: String,
        #[arg(long)]
        source_provider: String,
        #[arg(long)]
        source_retrieved_at: String,
        #[arg(long)]
        source_terms_url: String,
        #[arg(long, default_value_t = 100)]
        sample_size: usize,
    },
    /// Emit idempotent SQL that writes only to bd_stage.patent_candidate.
    StageSql {
        #[arg(long)]
        taxonomy: PathBuf,
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Plan { taxonomy, source, from, to, output } => {
            let taxonomy = Taxonomy::load(&taxonomy)?;
            if source != "google-patents" {
                bail!("unsupported source {source}; available: google-patents");
            }
            let sql = plan::google_bigquery(&taxonomy, &from, &to)?;
            fs::write(&output, sql)
                .with_context(|| format!("cannot write {}", output.display()))?;
            eprintln!("wrote date-bounded discovery plan to {}", output.display());
        }
        Command::IngestGoogle {
            taxonomy,
            input,
            output,
            rejects,
            retrieved_at,
            min_score,
            include_unmatched,
            allow_rejects,
        } => {
            require_rfc3339(&retrieved_at, "--retrieved-at")?;
            let taxonomy = Taxonomy::load(&taxonomy)?;
            let values = io::read_json_lines(&input)?;
            let mut records = Vec::new();
            let mut rejected = Vec::new();
            let mut seen = HashSet::new();
            let mut out_of_scope = 0usize;
            for (idx, wrapped) in values.into_iter().enumerate() {
                let raw = match io::unwrap_google(wrapped) {
                    Ok(v) => v,
                    Err(error) => {
                        rejected.push(json!({"line": idx + 1, "stage": "unwrap", "error": error.to_string()}));
                        continue;
                    }
                };
                let mut record = match google::normalize(&raw, &taxonomy.taxonomy_version, &retrieved_at) {
                    Ok(record) => record,
                    Err(error) => {
                        rejected.push(json!({"line": idx + 1, "stage": "normalize", "error": error.to_string()}));
                        continue;
                    }
                };
                let decision = classify::classify(&mut record, &taxonomy, min_score);
                if !decision.relevant && !include_unmatched {
                    out_of_scope += 1;
                    continue;
                }
                let validation = classify::validate(&record, &taxonomy);
                if !validation.valid() {
                    rejected.push(json!({
                        "line": idx + 1,
                        "stage": "validate",
                        "publication_number": record.publication_number,
                        "errors": validation.errors,
                        "warnings": validation.warnings,
                        "coverage_reasons": decision.reasons
                    }));
                    continue;
                }
                if !seen.insert(record.publication_number.clone()) {
                    rejected.push(json!({
                        "line": idx + 1,
                        "stage": "deduplicate",
                        "publication_number": record.publication_number,
                        "error": "duplicate publication number in input shard"
                    }));
                    continue;
                }
                records.push(record);
            }
            records.sort_by(|a, b| a.publication_number.cmp(&b.publication_number));
            io::write_records(&output, &records)?;
            io::write_values(&rejects, &rejected)?;
            eprintln!(
                "{} normalized and classified; {} out of scope; {} rejected",
                records.len(), out_of_scope, rejected.len()
            );
            if !rejected.is_empty() && !allow_rejects {
                bail!(
                    "{} record(s) rejected; inspect {} or rerun with --allow-rejects for an exploratory shard",
                    rejected.len(),
                    rejects.display()
                );
            }
        }
        Command::Classify { taxonomy, input, output, min_score, include_unmatched } => {
            let taxonomy = Taxonomy::load(&taxonomy)?;
            let mut records = io::read_records(&input)?;
            let mut kept = Vec::new();
            for mut record in records.drain(..) {
                record.taxonomy_version = taxonomy.taxonomy_version.clone();
                let decision = classify::classify(&mut record, &taxonomy, min_score);
                if decision.relevant || include_unmatched {
                    kept.push(record);
                }
            }
            kept.sort_by(|a, b| a.publication_number.cmp(&b.publication_number));
            io::write_records(&output, &kept)?;
            eprintln!("{} records classified", kept.len());
        }
        Command::Validate { taxonomy, input } => {
            let taxonomy = Taxonomy::load(&taxonomy)?;
            let records = io::read_records(&input)?;
            let mut failures = 0usize;
            let mut publications = HashSet::new();
            let mut source_ids = HashSet::new();
            for record in &records {
                let result = classify::validate(record, &taxonomy);
                for warning in result.warnings {
                    eprintln!("warning {}: {}", record.publication_number, warning);
                }
                for error in result.errors {
                    failures += 1;
                    eprintln!("error {}: {}", record.publication_number, error);
                }
                if !publications.insert(record.publication_number.as_str()) {
                    failures += 1;
                    eprintln!("error {}: duplicate publication number", record.publication_number);
                }
                if !source_ids.insert((record.source.provider.as_str(), record.source.record_id.as_str())) {
                    failures += 1;
                    eprintln!("error {}: duplicate source record", record.publication_number);
                }
            }
            if failures > 0 {
                bail!("validation failed with {failures} error(s)");
            }
            eprintln!("ok: {} patent records satisfy the release contract", records.len());
        }
        Command::Manifest {
            taxonomy,
            input,
            output,
            release_version,
            source_provider,
            source_retrieved_at,
            source_terms_url,
            sample_size,
        } => {
            require_rfc3339(&source_retrieved_at, "--source-retrieved-at")?;
            let taxonomy = Taxonomy::load(&taxonomy)?;
            let mut records = io::read_records(&input)?;
            records.sort_by(|a, b| a.publication_number.cmp(&b.publication_number));
            ensure_release_valid(&records, &taxonomy)?;
            let hashes: Vec<String> = records
                .iter()
                .map(io::record_hash)
                .collect::<Result<Vec<_>>>()?;
            let families: HashSet<String> = records
                .iter()
                .flat_map(|record| record.family_keys.iter())
                .map(|f| format!("{}:{}:{}", f.provider, f.kind, f.id))
                .collect();
            let unclassified = records.iter().filter(|r| r.annotations.is_empty()).count();
            let seed = hex::encode(Sha256::digest(hashes.join("\n").as_bytes()));
            let mut snapshot = Map::new();
            snapshot.insert(
                source_provider,
                json!({
                    "retrieved_at": source_retrieved_at,
                    "terms_url": source_terms_url,
                    "watermark": Value::Null,
                    "snapshot_sha256": Value::Null
                }),
            );
            let manifest = json!({
                "schema_version": "1.0.0",
                "release_version": release_version,
                "taxonomy_version": taxonomy.taxonomy_version,
                "classifier_version": format!("{}-{}", AGENT_NAME, AGENT_VERSION),
                "source_snapshot": snapshot,
                "ordered_record_hashes": hashes,
                "validation": {
                    "records": records.len(),
                    "families": families.len(),
                    "duplicates": 0,
                    "invalid": 0,
                    "unclassified": unclassified,
                    "source_errors": 0
                },
                "review_gate": {
                    "state": "pending_review",
                    "sample_size": sample_size.min(records.len()),
                    "sampling_seed": seed,
                    "reviewer": Value::Null,
                    "reviewed_at": Value::Null,
                    "notes": Value::Null
                }
            });
            let bytes = serde_json::to_vec_pretty(&manifest)?;
            fs::write(&output, &bytes)
                .with_context(|| format!("cannot write {}", output.display()))?;
            let manifest_hash = hex::encode(Sha256::digest(&bytes));
            eprintln!("manifest_sha256={manifest_hash}");
        }
        Command::StageSql { taxonomy, input, output } => {
            let taxonomy = Taxonomy::load(&taxonomy)?;
            let records = io::read_records(&input)?;
            io::write_stage_sql(&output, &records, &taxonomy)?;
            eprintln!("wrote {} staged candidates to {}", records.len(), output.display());
        }
    }
    Ok(())
}

fn ensure_release_valid(records: &[PatentRecord], taxonomy: &Taxonomy) -> Result<()> {
    let mut publications = HashSet::new();
    let mut sources = HashSet::new();
    for record in records {
        let result = classify::validate(record, taxonomy);
        if !result.valid() {
            bail!(
                "record {} is invalid: {}",
                record.publication_number,
                result.errors.join("; ")
            );
        }
        if !publications.insert(record.publication_number.as_str()) {
            bail!("duplicate publication number {}", record.publication_number);
        }
        if !sources.insert((record.source.provider.as_str(), record.source.record_id.as_str())) {
            bail!("duplicate source record {}:{}", record.source.provider, record.source.record_id);
        }
    }
    Ok(())
}

fn require_rfc3339(value: &str, flag: &str) -> Result<()> {
    DateTime::parse_from_rfc3339(value)
        .with_context(|| format!("{flag} must be RFC 3339 with an explicit timezone"))?;
    Ok(())
}
