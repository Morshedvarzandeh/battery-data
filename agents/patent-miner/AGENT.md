# Patent Intelligence Agent

The patent miner discovers battery patents, separates publications from
inventions/families, preserves office classifications and source evidence, and
applies the editable battery taxonomy in
`taxonomy/battery-patent-taxonomy.v1.json`.

It is deliberately not an FTO or legal-opinion engine. A search result, family
relationship, legal event or model-generated label can be incomplete. The
database stores what each source asserted, when it was retrieved, and which
human approved the immutable release.

## Pipeline

```text
DISCOVER -> NORMALIZE -> FAMILY-DEDUPE -> CLASSIFY -> VALIDATE
                                                        |
                                                        v
PROMOTE <- HUMAN APPROVAL <- HASHED RELEASE MANIFEST <- STAGE
```

The agent may write only to `bd_stage.patent_candidate`. A database trigger
rejects a `bd.patent_document` unless it belongs to a content-addressed release
whose status is `accepted` and whose approver is an identified human.

## Why patents are a separate agent

- One invention can have tens of publications in different jurisdictions.
- Simple, INPADOC, national and analyst-built families are different claims,
  so the schema stores the family definition with the identifier.
- Application, publication and grant numbers are not interchangeable.
- Applicants, assignees and current owners are different roles over time.
- Legal events are source assertions, not a timeless `active=true` flag.
- IPC/CPC codes are official classifications; Lemonergy's battery categories
  are a separate versioned interpretation.
- Claim text, bibliographic metadata and office PDFs may have different reuse
  terms. The agent never treats public accessibility as permission to mirror.

## Source strategy

No single source is complete enough to support a global claim. The target is a
multi-source coverage ledger with measurable gaps.

| Layer | Role | Automation rule |
|---|---|---|
| Google Patents Public Data / BigQuery | Global discovery backbone and first-pass family/classification metadata | A query is run only after a manual cost/credential checkbox and a maximum-bytes cap |
| EPO OPS / DOCDB / INPADOC | Worldwide family, bibliographic, citation and legal-event enrichment | Free allowance still requires registration; credentials are never invented or enabled by a scheduled run |
| WIPO PATENTSCOPE | PCT publications and participating-office coverage | Use only an authorised programmatic/data product; never scrape the human UI |
| USPTO Open Data Portal | US bulk grants, applications and file-wrapper data | Prefer official bulk/API products and immutable file hashes |
| National/regional offices | Gap repair and current legal status | Each adapter has its own rights and completeness contract |

Official service pages and terms must be snapshotted in every release manifest.
Link health checks may report a change, but may not silently reclassify rights.

## User-controlled categories

Edit `taxonomy/battery-patent-taxonomy.v1.json`; do not edit Rust code to add a
category. Version 1 has independent facets for:

- chemistry;
- component;
- manufacturing;
- pack/system;
- charging;
- lifecycle/recycling;
- application; and
- objective.

Each label lists its classification prefixes and phrases. The classifier emits
the exact matched CPC/IPC code or phrase as evidence. Reclassification is
deterministic:

```bash
cargo run --manifest-path agents/patent-miner/Cargo.toml -- classify \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --input patents.normalized.ndjson \
  --output patents.reclassified.ndjson
```

Changing the meaning of an existing label requires a new taxonomy version. A
release always records both taxonomy and classifier versions, so old results
remain reproducible.

## Discovery

Generate a bounded BigQuery discovery plan:

```bash
cargo run --manifest-path agents/patent-miner/Cargo.toml -- plan \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --source google-patents \
  --from 2026-08-01 --to 2026-08-24 \
  --output battery-patents.sql
```

The query searches primary battery CPC/IPC prefixes first, then cross-domain
profiles such as charging, traction packs, testing, materials and recycling.
The date range is mandatory. The generated query is never executed by this
command, which prevents a plan-only or scheduled run from spending money.

## Normalize and classify

BigQuery exports may contain each publication directly or under a
`raw_record` field. Both are accepted:

```bash
cargo run --manifest-path agents/patent-miner/Cargo.toml -- ingest-google \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --input google-export.ndjson \
  --output battery-patents.ndjson \
  --rejects rejected.ndjson \
  --retrieved-at 2026-08-24T20:00:00Z
```

The default is fail-closed if any record is malformed. `--allow-rejects` is for
exploratory shards only; a release manifest refuses invalid records. Claims are
not copied by the Google adapter. It records `fulltext_redistributable=false`
until a source-specific rights adapter proves otherwise.

## Validate, manifest and stage

```bash
cargo run --manifest-path agents/patent-miner/Cargo.toml -- validate \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --input battery-patents.ndjson

cargo run --manifest-path agents/patent-miner/Cargo.toml -- manifest \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --input battery-patents.ndjson \
  --output release-2026-08-24.json \
  --release-version 2026-08-24-google-v1 \
  --source-provider google_patents_public_data \
  --source-retrieved-at 2026-08-24T20:00:00Z \
  --source-terms-url https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data

cargo run --manifest-path agents/patent-miner/Cargo.toml -- stage-sql \
  --taxonomy taxonomy/battery-patent-taxonomy.v1.json \
  --input battery-patents.ndjson \
  --output stage-patents.sql
```

The SQL is idempotent and targets only `bd_stage.patent_candidate`. It cannot
promote its own output.

## Coverage must be measured, not advertised

“Biggest” is tracked on five independent axes:

1. unique publication documents;
2. distinct families under each named family definition;
3. authorities/jurisdictions and language coverage;
4. update lag from source publication; and
5. accepted, evidence-backed battery taxonomy coverage.

Raw row count alone is not a quality claim. Family duplicates, corrections,
machine translations and re-ingested snapshots never count as new inventions.

## Implemented now

| Capability | Status |
|---|---|
| Versioned editable taxonomy | Complete |
| Classification-first Google BigQuery plan | Complete |
| Google raw-record normalizer | Complete |
| CPC/IPC + phrase classifier with evidence | Complete |
| Publication/source dedupe and validation | Complete |
| Deterministic release manifest | Complete |
| Staging-only SQL exporter | Complete |
| PostgreSQL patent/family/party/citation/legal-event schema | Complete |
| Knowledge-graph patent nodes and edges | Complete |
| EPO OPS enrichment adapter | Next source adapter |
| USPTO bulk adapter | Next source adapter |
| WIPO authorised data adapter | Contract/access work required |
| Claim-level semantic models | Later; rights and human calibration first |
| FTO/legal conclusions | Explicitly out of scope |

## Scale roadmap

1. Backfill Google discovery in monthly shards, newest first; never use one
   unbounded query.
2. Add EPO family/legal-event enrichment and reconcile conflicting family IDs.
3. Add USPTO bulk XML with immutable archive/file hashes.
4. Build the source/authority/language coverage ledger and repair gaps by office.
5. Train claim-level classifiers only from reviewed labels; compare them against
   deterministic CPC/keyword baselines before accepting any model version.
6. Publish family landscapes, assignee networks, technology trends and white
   spaces through read-only API endpoints. Keep legal interpretation separate.
