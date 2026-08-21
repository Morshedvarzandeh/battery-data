# EU battery-research data contract

This document defines the boundary for importing EU-funded battery projects and
their indexed public results. It is deliberately a contract before it is a
database migration: the source corpus is large enough that changing identity,
rights or review rules after loading it would create silent duplicates and
untraceable claims.

No production EU records are loaded by this contract. The representative files
under `tests/fixtures/eu_research/` exist only to prove that the rules are
machine-checkable.

## Scope

The corpus has three included project classes:

| Class | Inclusion rule |
|---|---|
| `BATTERY_CORE` | Batteries are the primary object of development, manufacture, modelling, testing, demonstration, reuse or recycling. |
| `BATTERY_INTEGRATED` | A broader application has a separately identifiable battery objective, work package, KPI, prototype or result. |
| `BATTERY_ECOSYSTEM` | Battery-centred roadmaps, standards, databases, infrastructure, education or coordination. |

Incidental batteries, semantic false positives and non-battery storage remain
outside the approved corpus. Ambiguous projects stay in the review queue; an AI
or extraction rule cannot approve its own scientific classification.

The bounded 21 August 2026 baseline is recorded in
`tests/fixtures/eu_research/baseline-2026-08-21.json`:

| Measure | Count |
|---|---:|
| Included projects | 1,608 |
| Strict core and ecosystem projects | 858 |
| Integrated projects | 750 |
| Indexed source result rows | 65,486 |
| Participation records | 15,050 |
| Review candidates | 2,911 |
| Excluded matches | 175 |

`65,486` is the number of project-associated rows emitted by the bounded source
harvest. It is not a canonical `RESULT` count: DOI/URI deduplication can produce
fewer results and a separate number of `PROJECT_RESULT` links. Those two counts
are frozen only after identity conflicts have been reviewed. A full release's
`source_observation_summary` reproduces the source-row partitions in the
baseline, but the validator accepts those totals only when it recomputes them
from the hashed `source_observation_ledger`. Each harvested result row appears
once with its exact source artifact/dataset/row, project, access/type/relevance
partition and disposition: canonical link, duplicate link, quarantined identity
or documented non-public exclusion. Linked dispositions resolve to an emitted
`PROJECT_RESULT`; the others require a note. These rows are audit evidence, not
canonical `RESULT` records. Baseline `.1` intentionally
has no reviewed canonical result/link counts and therefore cannot authorize an
`APPROVED` full release. Review must produce a new immutable baseline ID and
digest containing those counts. Likewise, `15,050`
is a participation-row count, not a claim that there are 15,050 unique
organisations. The coverage claim means every record found by the documented
official-source retrieval and classification method as observed on that date;
it cannot include confidential, unreported, removed or later-added results.

## Repository boundary

Postgres remains the source of truth and `bd_graph` remains a rebuildable
projection. The future SQL module must not overload existing concepts:

- `bd.campaign` is a battery test campaign, not an EU grant project.
- `bd.source` is a retrievable artefact, not the project-result relationship.
- `bd.access_tier` is an authorisation control, not online availability.
- `bd_stage.candidate_state` is ingestion review, not battery-scope class.
- coordinator and participant are project-specific roles; they do not belong in
  the global `organization.roles` array.

When the relational module is added, it should load as
`schema/145_research.sql`. It must exist before `schema/150_graph.sql` if the
graph projection will reference research tables.

The expected future entities are:

```text
research_project ── project_result ── research_result ── result_asset
        │
        ├── project_participation ── organization
        ├── funding_call / funding_topic / programme
        └── project_concept
```

`research_result` is independent from `project_result`: one DOI may acknowledge
several grants without duplicating the publication or losing any attribution.
Global `RESULT` records own identity, bibliography/type, access, assets and
rights. Only `PROJECT_RESULT` owns grant-context `battery_relevance` and
`battery_domains`. A result-wide view is derived from accepted links: direct
relevance outranks contextual relevance, and domains are their union. Derived
values are never stored back on `RESULT`, so one shared DOI can have different
valid classifications for different projects.

## Record envelope

Every canonical or curation record uses the immutable v1 identifier declared by
`json-schema/eu-research-record.schema.json` and carries:

- contract and immutable release identifiers;
- a namespaced canonical record ID and record version;
- record-lifecycle and curation states;
- first- and last-seen dates;
- a deterministic content hash;
- at least one provenance claim linked to a manifest source snapshot;
- field-scoped source-content rights and redistribution status; and
- type-specific data.

Source claims must use official `https://` URLs. Paths such as
`/tmp/cordis_data/...`, `file://...` or a developer's workspace are forbidden
in a release. If exact source bytes were retained, their SHA-256 is recorded;
otherwise the candidate record must retain the official locator, source record
ID, retrieval time and asserted fields. An approved release requires every
source artifact's retained bytes to be materialized for validation through a
release-local `retained_path`, byte size and SHA-256. The validator reads those
bytes; a manifest-only hash is not evidence. Large files may be materialized
from private object storage without being committed or publicly redistributed.
Each artifact declares stable logical `dataset_ids` from the v1 registry, and
every claim's `source_dataset` must belong to its exact artifact. Changing the
registry is a reviewed contract change because dataset IDs participate in
source-record identity. An artifact used to mint a `SOURCE_RECORD` identity
must declare exactly that one dataset; multi-dataset artifacts may provide
ordinary provenance but cannot supply an identity seed. Retained sources live
only below `source_artifacts/`;
their paths and bytes may not alias a manifest, baseline, observation ledger,
record set or result asset. `snapshot_sha256` is the
prefixed SHA-256 of
the snapshot object after removing only `snapshot_sha256`, NFC-normalising its
JSON tree and serialising it with the record hash's sorted, compact UTF-8 JSON
rules. It therefore binds the exact URLs, request/distribution descriptions,
retrieval times and component hashes. Every claim names both its snapshot and
the exact component artifact within that snapshot. Each asserted field is a
valid JSON Pointer into the record.

CORDIS, EURIO and Funding & Tenders claims describe only source-supplied facts;
they cannot assert `scope_class`, `battery_domains` or battery relevance,
including through an ancestor pointer such as `/data`. An
accepted battery classification requires a distinct `CURATOR` claim with the
methodology version, named reviewer identity, review time, evidence and an
`ACCEPT` decision. A rule or model may propose a classification but cannot
author its own approval.

## Stable identity

Project IDs follow repository-style slash notation:

```text
research_project/<programme-namespace>/<official-project-id>
```

Examples:

```text
SEABAT   research_project/eu-h2020/963560
FLEXSHIP research_project/eu-horizon/101095863
HAVEN    research_project/eu-horizon/101137636
GHOST    research_project/eu-h2020/770019
INVADE   research_project/eu-h2020/731148
```

The programme namespace is selected from the v1 registry, not generated from a
free-text programme label:

```text
eu-fp1 … eu-fp7, eu-h2020, eu-horizon, eu-pre-fwp,
eu-cef2027, eu-digital, eu-ecsc, eu-edf, eu-emff, eu-eng, eu-env,
eu-erasmus-plus, eu-i3, eu-ic, eu-innovation-fund, eu-life,
eu-rfcs2027, eu-single-market-programme, eu-socpl
```

The external project ID is trimmed, NFC-normalised and RFC 3986
percent-encoded outside the unreserved set, using uppercase hex. The validator
recomputes the complete ID from `programme_namespace` and
`official_project_id`; a bare project ID is never canonical.

Results and relationship records use UUIDv5 with `NAMESPACE_URL`. A seed is the
UTF-8 encoding of a compact JSON array (`ensure_ascii=false`), rather than a
delimiter-concatenated string. This keeps embedded punctuation unambiguous.
The v1 arrays are:

```json
["urn:battery-data:eu-research:result:v1", "doi", "<normalised-doi>"]
["urn:battery-data:eu-research:result:v1", "official-uri", "<normalised-uri>"]
["urn:battery-data:eu-research:result:v1", "source-record", "<project-id>", "<source-system>", "<source-dataset>", "<source-record-id>"]
["urn:battery-data:eu-research:result:v1", "fingerprint", "<project-id>", "<result-type>", "<year-or-null>", "<normalised-title>"]
["urn:battery-data:eu-research:project-result:v1", "<project-id>", "<result-id>"]
["urn:battery-data:eu-research:participation:v1", "<project-id>", "<organisation-id>"]
```

DOIs are trimmed, stripped of `doi:` or a DOI-resolver prefix, percent-decoded
once, NFC-normalised and case-folded. Official URIs have a lowercase scheme and
host, no default port or fragment, and normalised percent encoding. Fingerprint
titles are NFKC-normalised, case-folded and whitespace-collapsed while retaining
punctuation. The stored identity fields must reproduce the record UUID exactly.

The basis is not caller-selected: v1 requires the first usable value in the
order DOI, official URI, complete source-record tuple, then fingerprint. A
lower-precedence record that already carries a higher-precedence identifier is
invalid. A later identifier discovered for an accepted lower-precedence record
stays quarantined until a future reviewed-equivalence contract defines how to
preserve the immutable ID.

DOI and official-URI identities are global and unique across accepted results,
even when they are not the minting basis. Source-record and conservative
fingerprint identities include their project. A source-record identity also
includes its artifact-declared logical dataset ID because source IDs can overlap
across exports; dated filenames are not dataset IDs. If two
incompatible source rows still resolve to the same seed—as occurs in some FP7
IPR rows—both are quarantined; neither receives a suffix or a silent merge.
Every source-record or fingerprint identity must have a `PROJECT_RESULT` link
to the project used in its UUID seed.

Provenance claims, review candidates and exclusions also use documented UUIDv5
helpers in `tools/validate_eu_research_release.py`. Claim identity includes the
source snapshot and artifact, source record, asserted pointers and evidence
locator. Review and exclusion identity is scoped to the candidate project.
Asset identity is not UUID-based: it is exactly
`result_asset/sha256/<digest-of-file-bytes>`.

Contract v1 accepts only the official nine-digit participant identification
code, stored as both `source_organization_id` and `org/eu-pic/<PIC>`. All 15,050
bounded participation rows provide this value. Non-PIC organisations and fuzzy
name matches remain review proposals until a pinned core-organisation registry
is part of a later contract. Participation identity is project plus
organisation, while `roles` is multivalued versioned data. For each project,
the set of participations carrying `COORDINATOR` must equal exactly the
singleton `coordinator_org_id`, or be empty when that field is null.

Automatic suffixes such as `-2` are forbidden. Identity conflicts become
review candidates with `same_as` or `possible_duplicate_of` decisions in a
later storage contract.

## Deterministic content hashes

Contract version 1 uses this canonical payload:

1. Remove `release_id`, `first_seen_on`, `last_seen_on` and `content_hash`.
   Remove observation-only timestamps at their exact paths:
   `provenance/*/retrieved_at`, `provenance/*/review/reviewed_at`,
   `data/access_verified_at` and `RESULT_ASSET.data/retrieved_at`.
2. Normalise source strings before record construction; monetary values remain
   decimal strings rather than binary floating-point values.
3. Serialize UTF-8 JSON with keys sorted, no insignificant whitespace and no
   ASCII escaping.
4. Prefix the lowercase SHA-256 digest with `sha256:`.

Observation dates can change without changing scientific content; the source
payload digest, asserted value, access status and review decision remain in the
hash. A changed assertion retains its ID, increments `record_version` and
receives a new hash. An unchanged record retains all three.

## Access is not a licence

Result availability and reuse permission are independent dimensions.

Availability:

```text
OPEN_FULL_CONTENT
OPEN_REPOSITORY_LANDING_PAGE
METADATA_ONLY
PAYWALLED
RESTRICTED_OR_CONFIDENTIAL
BROKEN_OR_MISSING
```

Source-content licence status:

```text
OPEN_LICENSE_VERIFIED
PUBLIC_DOMAIN_VERIFIED
EXPLICIT_REUSE_PERMISSION
RESTRICTED
NO_LICENSE_FOUND
SOURCE_SPECIFIC
UNKNOWN
```

Asset redistribution:

```text
ALLOWED
LINK_ONLY
PROHIBITED
UNKNOWN
```

An open URL does not prove an open licence. A DOI proves neither full-text
access nor redistribution permission. Every rights assertion names the JSON
Pointers to which it applies, so imported text, repository-authored
classification and a beneficiary asset can retain different terms.
The most-specific matching pointer governs; equally specific conflicting
assertions resolve to the more restrictive policy and require review.
Every emitted data field must be covered. A public record may include only a
field whose effective `metadata_redistribution` decision is `ALLOWED`; link-only
or prohibited content stays in the retained source snapshot and is represented
by its official locator instead.
`OPEN_LICENSE_VERIFIED`, public-domain and explicit-permission assertions must
name the licence/permission and evidence URL. `METADATA_ONLY` cannot carry a
bundled asset. Every other observed access status requires the checked URL and
verification timestamp; open landing/full-content checks also record status,
content type and final URL, and require `access_anonymous=true`. Open claims use
an anonymous `GET` final response: full content accepts status 200 or 206 and an
evidence kind of `SUBSTANTIVE_FILE` or `OFFICIAL_FULL_NARRATIVE`; a landing page
accepts status 200, uses `LANDING_PAGE`, and explains the remaining action in
`availability_note`. A 204, unresolved redirect or `HEAD` response is not proof
of substantive access.

A `result_asset` requires explicit licence or reuse permission, media type,
byte count and content checksum. Validation resolves its archive path inside
the release, hashes the actual bytes, matches the digest in both record ID and
payload, and verifies the owning result links back to it.

The default is therefore metadata plus official links. Beneficiary PDFs,
software, datasets, images and other files are not mirrored unless their
individual terms allow it. See the [CORDIS legal notice](https://cordis.europa.eu/about/legal)
and the [Horizon Results Platform legal provisions](https://ec.europa.eu/info/funding-tenders/opportunities/docs/project-result/Legal_Provisions_for_the_use_of_the_Horizon_Results_Platform.pdf).

## Release contract and gates

Each immutable snapshot uses the v1 identifier declared by
`json-schema/eu-research-release.schema.json`. Source-observation rows use the
separately pinned `json-schema/eu-research-observation.schema.json`. The manifest pins the record
schema digest, links every claim to a source snapshot and, for a full snapshot,
pins a baseline ID to its validator-registered immutable digest. A caller cannot
replace the file and update the manifest hash; a new baseline requires a new ID
and registry entry. Emitted project, participation, review, exclusion, scope,
programme, project-result coverage and seed-project values reconcile against
that baseline. Approved releases also bind every frozen input digest to exactly
one retained source artifact with its frozen dataset ID. Every core record must
cite a frozen input, every input must be used, and the observation ledger must
name the frozen public-results input from which it was built. Canonical records are sorted by `record_id` and
emitted as strict UTF-8 NDJSON with LF terminators. CSV, Parquet, SQLite and
Excel are derived representations, never independent sources of truth.

An approved release must pass all of these gates:

1. Manifest and record schemas.
2. Source provenance and snapshot hashes.
3. Canonical identifier and duplicate checks.
4. Manifest-to-file count, byte-size and SHA-256 reconciliation.
5. Project/result/participation referential integrity.
6. Scope-classification fixtures and independent review.
7. Anonymous access verification for full-content claims.
8. Field- and asset-level rights review.
9. Deterministic rebuild from the same source snapshot.
10. Sanitised export with no credentials, local paths or unnecessary personal
    contact fields.

All snapshot, artifact, claim, review, access and bundled-asset observation
timestamps are bounded by `generated_at`; a review cannot predate the claim it
reviews. Sanitisation rejects high-confidence credential material and email
contact data without echoing the sensitive value in diagnostics.

Review candidates and excluded matches remain internal curation artefacts. They
must never appear in the public project/result API as approved projects.
An approved full release declares project, result, project-result,
participation, review-candidate and exclusion record sets even when an internal
set is empty; an asset set is present only when redistributable bytes exist.

Run the reusable validator locally with:

```bash
python tools/validate_eu_research_release.py path/to/manifest.json
```

It fails closed on malformed JSON or UTF-8, verifies deterministic IDs,
source/field pointers, visibility, counts, checksums, references and bundled
asset bytes, and requires exactly one passed instance of every gate for an
approved release.

## Consumer rule

`battery-design`, `battery-core` and analytical applications consume an exact
approved release or a release-aware API. They must not copy the canonical corpus
into their own repositories or silently follow `latest`. Publications and
deliverables are evidence; they do not become simulation parameters until they
pass the repository's normal inspect, validate, review and publish workflow.
