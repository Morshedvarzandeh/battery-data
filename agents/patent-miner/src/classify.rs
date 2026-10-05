use crate::model::{Annotation, PatentRecord, ValidationResult};
use crate::taxonomy::{code_has_prefix, Taxonomy};
use chrono::NaiveDate;
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct CoverageDecision {
    pub relevant: bool,
    pub reasons: Vec<String>,
}

pub fn classify(record: &mut PatentRecord, taxonomy: &Taxonomy, min_score: f64) -> CoverageDecision {
    let text = record.searchable_text();
    let codes: Vec<&str> = record.classifications.iter().map(|c| c.code.as_str()).collect();
    let mut annotations = Vec::new();

    for taxon in &taxonomy.taxa {
        let class_hits: Vec<String> = codes
            .iter()
            .flat_map(|code| {
                taxon
                    .rules
                    .classification_prefixes
                    .iter()
                    .filter(move |prefix| code_has_prefix(code, prefix))
                    .map(move |prefix| format!("classification:{code} matches {prefix}"))
            })
            .collect();

        let negative = taxon
            .rules
            .negative_keywords
            .iter()
            .any(|term| text.contains(&term.to_lowercase()));
        let keyword_hits: Vec<String> = if negative {
            Vec::new()
        } else {
            taxon
                .rules
                .keywords
                .iter()
                .filter(|term| text.contains(&term.to_lowercase()))
                .map(|term| format!("keyword:{term}"))
                .collect()
        };

        if class_hits.is_empty() && keyword_hits.is_empty() {
            continue;
        }
        let class_score: f64 = if class_hits.is_empty() { 0.0 } else { 0.92 };
        let keyword_score: f64 = if keyword_hits.is_empty() {
            0.0
        } else {
            0.62 + 0.06 * (keyword_hits.len().saturating_sub(1).min(3) as f64)
        };
        let score: f64 = if class_score > 0.0 && keyword_score > 0.0 {
            0.98
        } else {
            class_score.max(keyword_score)
        };
        if score < min_score {
            continue;
        }

        let mut evidence = class_hits;
        evidence.extend(keyword_hits);
        evidence.truncate(12);
        annotations.push(Annotation {
            taxon_id: taxon.id.clone(),
            method: if evidence.iter().any(|e| e.starts_with("classification:")) {
                "classification_rule".to_string()
            } else {
                "keyword_rule".to_string()
            },
            score,
            rule_id: Some(format!("{}:{}", taxonomy.taxonomy_version, taxon.id)),
            evidence,
        });
    }

    annotations.sort_by(|a, b| {
        a.taxon_id
            .cmp(&b.taxon_id)
            .then_with(|| b.score.total_cmp(&a.score))
    });
    record.annotations = annotations;

    coverage_decision(record, taxonomy, &text, &codes)
}

fn coverage_decision(
    record: &PatentRecord,
    taxonomy: &Taxonomy,
    text: &str,
    codes: &[&str],
) -> CoverageDecision {
    let mut reasons = Vec::new();
    for prefix in taxonomy
        .coverage_contract
        .primary_prefixes
        .iter()
        .chain(taxonomy.coverage_contract.historical_prefixes.iter())
    {
        for code in codes {
            if code_has_prefix(code, prefix) {
                reasons.push(format!("primary_classification:{code} matches {prefix}"));
            }
        }
    }
    if !reasons.is_empty() {
        reasons.sort();
        reasons.dedup();
        return CoverageDecision {
            relevant: true,
            reasons,
        };
    }

    for exclusion in &taxonomy.coverage_contract.exclusion_profiles {
        let class_hit = codes.iter().any(|code| {
            exclusion
                .classification_prefixes
                .iter()
                .any(|prefix| code_has_prefix(code, prefix))
        });
        let rescued = exclusion
            .unless_terms
            .iter()
            .any(|term| text.contains(&term.to_lowercase()));
        if class_hit && !rescued {
            return CoverageDecision {
                relevant: false,
                reasons: vec![format!("excluded:{}", exclusion.id)],
            };
        }
    }

    for profile in &taxonomy.coverage_contract.cross_domain_profiles {
        let class_hit = codes.iter().any(|code| {
            profile
                .classification_prefixes
                .iter()
                .any(|prefix| code_has_prefix(code, prefix))
        });
        let term_hits: Vec<&String> = profile
            .required_terms
            .iter()
            .filter(|term| text.contains(&term.to_lowercase()))
            .collect();
        if class_hit && !term_hits.is_empty() {
            reasons.push(format!(
                "cross_domain:{} with {}",
                profile.id,
                term_hits.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(",")
            ));
        }
    }

    // Classification can be absent or lag publication. Keep a text-only
    // candidate only when two independent domain taxa matched; a lone use of
    // the word "battery" is not enough to pollute the corpus.
    if reasons.is_empty() {
        let strong: Vec<&Annotation> = record
            .annotations
            .iter()
            .filter(|a| a.taxon_id != "scope/battery" && a.score >= 0.62)
            .collect();
        let has_battery_term = ["battery", "electrochemical cell", "accumulator"]
            .iter()
            .any(|term| text.contains(term));
        if has_battery_term && strong.len() >= 2 {
            reasons.push(format!("text_only:{} independent taxonomy matches", strong.len()));
        }
    }

    CoverageDecision {
        relevant: !reasons.is_empty(),
        reasons,
    }
}

pub fn validate(record: &PatentRecord, taxonomy: &Taxonomy) -> ValidationResult {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();

    if record.schema_version != crate::RECORD_SCHEMA_VERSION {
        errors.push(format!("unsupported schema_version {}", record.schema_version));
    }
    if record.taxonomy_version != taxonomy.taxonomy_version {
        errors.push(format!(
            "record taxonomy {} != loaded taxonomy {}",
            record.taxonomy_version, taxonomy.taxonomy_version
        ));
    }
    if !valid_publication_number(&record.publication_number) {
        errors.push("publication_number is not normalized".to_string());
    }
    if record.authority.len() != 2
        || !record.authority.chars().all(|c| c.is_ascii_uppercase())
        || !record.publication_number.starts_with(&record.authority)
    {
        errors.push("authority is not the publication-number prefix".to_string());
    }
    if record.document_number.trim().is_empty() || record.family_keys.is_empty() {
        errors.push("document_number and at least one family key are required".to_string());
    }
    if record.titles.is_empty() && record.abstracts.is_empty() {
        errors.push("neither title nor abstract is present".to_string());
    }
    if record.source.provider.trim().is_empty() || record.source.record_id.trim().is_empty() {
        errors.push("source provider and record_id are required".to_string());
    }
    if !is_sha256(&record.source.record_sha256) {
        errors.push("source.record_sha256 is not lowercase SHA-256".to_string());
    }
    if record.rights.metadata_license.trim().is_empty() {
        errors.push("metadata rights are not recorded".to_string());
    }
    if record.rights.fulltext_redistributable && record.rights.fulltext_license.is_none() {
        errors.push("redistributable full text has no recorded licence".to_string());
    }
    for (field, value) in [
        ("filing_date", &record.filing_date),
        ("priority_date", &record.priority_date),
        ("publication_date", &record.publication_date),
        ("grant_date", &record.grant_date),
    ] {
        if let Some(date) = value {
            if NaiveDate::parse_from_str(date, "%Y-%m-%d").is_err() {
                errors.push(format!("{field} is not YYYY-MM-DD"));
            }
        }
    }
    if record.classifications.is_empty() {
        warnings.push("no IPC/CPC/source classification supplied".to_string());
    }
    if record.annotations.is_empty() {
        warnings.push("record has no battery taxonomy annotation".to_string());
    }
    let known: HashSet<&str> = taxonomy.taxa.iter().map(|t| t.id.as_str()).collect();
    for annotation in &record.annotations {
        if !known.contains(annotation.taxon_id.as_str()) {
            errors.push(format!("unknown taxon {}", annotation.taxon_id));
        }
        if !(0.0..=1.0).contains(&annotation.score) {
            errors.push(format!("annotation {} has invalid score", annotation.taxon_id));
        }
        if annotation.evidence.is_empty() {
            errors.push(format!("annotation {} has no evidence", annotation.taxon_id));
        }
    }

    ValidationResult { errors, warnings }
}

fn valid_publication_number(value: &str) -> bool {
    value.len() >= 4
        && value.as_bytes()[0..2].iter().all(u8::is_ascii_uppercase)
        && value[2..]
            .chars()
            .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || "/.-".contains(c))
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .chars()
            .all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::*;
    use crate::taxonomy::*;

    fn taxonomy() -> Taxonomy {
        Taxonomy {
            taxonomy_version: "1.0.0".into(),
            coverage_contract: CoverageContract {
                primary_prefixes: vec!["H01M10".into()],
                historical_prefixes: vec![],
                cross_domain_profiles: vec![],
                exclusion_profiles: vec![],
            },
            taxa: vec![Taxon {
                id: "chemistry/lithium_ion".into(),
                facet: "chemistry".into(),
                code: "lithium_ion".into(),
                label: "Lithium-ion".into(),
                description: None,
                parent: None,
                rules: Rules {
                    classification_prefixes: vec!["H01M10/052".into()],
                    keywords: vec!["lithium-ion".into()],
                    negative_keywords: vec![],
                },
            }],
        }
    }

    fn record() -> PatentRecord {
        PatentRecord {
            schema_version: "1.0.0".into(),
            taxonomy_version: "1.0.0".into(),
            publication_number: "EP1234567A1".into(),
            authority: "EP".into(),
            document_number: "1234567A1".into(),
            kind_code: Some("A1".into()),
            application_number: None,
            pct_number: None,
            filing_date: None,
            priority_date: None,
            publication_date: None,
            grant_date: None,
            withdrawn: None,
            family_keys: vec![FamilyKey { kind: "simple".into(), provider: "x".into(), id: "1".into() }],
            titles: vec![LocalizedText { language: "en".into(), text: "Lithium-ion battery".into(), machine_translation: false }],
            abstracts: vec![],
            claims: vec![],
            classifications: vec![Classification { scheme: "CPC".into(), code: "H01M 10/0525".into(), version: None, inventive: None, first_position: None }],
            parties: vec![],
            citations: vec![],
            annotations: vec![],
            source: SourceRef { provider: "test".into(), record_id: "1".into(), record_url: None, retrieved_at: "2026-08-24T00:00:00Z".into(), source_updated_at: None, record_sha256: "a".repeat(64) },
            rights: Rights { metadata_license: "test".into(), metadata_terms_url: None, fulltext_redistributable: false, fulltext_license: None, fulltext_terms_url: None },
        }
    }

    #[test]
    fn cpc_and_keyword_produce_traceable_annotation() {
        let mut record = record();
        let decision = classify(&mut record, &taxonomy(), 0.6);
        assert!(decision.relevant);
        assert_eq!(record.annotations.len(), 1);
        assert_eq!(record.annotations[0].method, "classification_rule");
        assert_eq!(record.annotations[0].score, 0.98);
        assert!(validate(&record, &taxonomy()).valid());
    }
}
