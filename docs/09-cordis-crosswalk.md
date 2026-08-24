# CORDIS and Funding & Tenders crosswalk

This crosswalk defines how official EU programme records enter the EU research
contract. It records source precedence, not a claim that one source is complete
on its own.

## Source roles

| Source | Primary use | Important boundary |
|---|---|---|
| [CORDIS projects and results](https://cordis.europa.eu/projects) | Project identity, objectives, framework data, organisations, deliverables, publications and report summaries | Modern bulk files do not cover every programme or every dynamically supplied OpenAIRE result. |
| [CORDIS archived search](https://cordis.europa.eu/about/search) | Historical and non-framework project rescue | Keyword matches require battery-centrality review. |
| [EURIO](https://cordis.europa.eu/about/sparql) | Cross-source project, organisation, topic and result relationships for FP7–Horizon Europe | Graph coverage and result coverage differ from bulk files. |
| [Funding & Tenders APIs](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis) | Signed awards, calls/topics and programmes outside primary CORDIS framework files | Portal status values and embedded result structures require source-specific parsing. |
| OpenAIRE records linked by CORDIS | Publication, dataset and software enrichment | A repository record or DOI does not prove open full text or an open licence. |

## Project mapping

| Source field | Contract target | Rule |
|---|---|---|
| Project/grant agreement ID | `PROJECT.data.official_project_id` | Preserve the official value; namespace it in `record_id`. |
| Programme ID/name | `programme_namespace`, `framework_programme` | Namespace is immutable after ID minting; descriptive labels may be versioned. |
| Acronym, title, objective | Project data | Preserve source text and provenance; never use title alone to merge. |
| Source status | `source_status` | Preserve verbatim. |
| Dates and status | `start_date`, `end_date`, `normalized_status` | Normalize status to `UPCOMING`, `ACTIVE`, `ENDED`, `TERMINATED` or `UNKNOWN`. |
| Total cost / EU contribution | Decimal-string EUR fields | Do not use binary floats in canonical records. |
| Call and topic identifiers | `call_codes`, `topic_codes` | Keep identifiers separately from titles. |
| Coordinator and participants | `PARTICIPATION` records | V1 requires the supplied nine-digit PIC as both `source_organization_id` and `org/eu-pic/<PIC>`. Non-PIC/fuzzy matches remain review proposals. |
| EuroSciVoc/keywords/battery rules | Scope and concept links | Persist rule version and evidence; classification changes are reviewed versions. |
| CORDIS and Portal URLs | `official_urls` and provenance | Only official `https://` locators enter releases. |

CORDIS and Funding & Tenders records auto-link only when the official project ID
and compatible programme namespace agree. Grant DOI, acronym, title and dates
strengthen the match but cannot override a programme conflict. A conflict
creates an alias-review candidate instead of a silent merge.

## Result mapping

| Source record | Contract result type | Rule |
|---|---|---|
| Periodic or final publishable project report/summary | `PROJECT_REPORT_SUMMARY` | Preserve the explicit source finality in `report_finality` (`PERIODIC`, `FINAL` or `UNKNOWN`) and the supplied ordinal in `period_number`; never infer `FINAL` merely from the word “publishable” or from a missing period. |
| Public technical deliverable | `TECHNICAL_DELIVERABLE` or a more specific reviewed type | Keep the source deliverable type and number. |
| Journal article | `JOURNAL_PUBLICATION` | Preserve bibliographic fields losslessly. |
| Conference paper/proceedings | `CONFERENCE_PUBLICATION` | Preserve bibliographic fields losslessly. |
| Dataset/database | `DATASET_DATABASE` | A repository landing page is not proof of an open licence. |
| Software/code repository | `SOFTWARE_SOURCE_CODE` | Record the repository and release/version locators separately when supplied. |
| Patent or FP7 IPR record | `PATENT_IP` | Preserve the source IPR classification. |
| Roadmap, standard or policy output | `STANDARD_ROADMAP_POLICY` | Preserve the source type. |
| Prototype or hardware design | `HARDWARE_PROTOTYPE_DESIGN` | Preserve the source type. |

The result entity and project-result relationship are separate. For each source
observation, select the first usable identity basis in this exact precedence and
store the normalised seed as `identity_value`:

1. `DOI`: normalised DOI.
2. `OFFICIAL_URI`: persistent normalised EURIO, CORDIS or OpenAIRE URI.
3. `SOURCE_RECORD`: the required project ID, source system, source dataset and
   source record ID components.
4. `FINGERPRINT`: conservative normalised title/type/year fingerprint scoped to
   the project.

Every `SOURCE_RECORD` component is required; `source_dataset` distinguishes
overlapping exports from the same source system and must match a stable logical
`dataset_id` declared by the exact source artifact. Retrieval dates and
filenames do not belong in that ID. IDs come from the versioned v1 registry;
callers cannot create a new slug during ingestion. The artifact used for an
identity must declare that dataset alone; a multi-dataset container can support
provenance but cannot choose the UUID seed. Missing tuple components,
identity collisions and incompatible records that resolve to the same candidate
ID are quarantined for review. They are never assigned an automatic suffix or
silently merged. UUID seeds use the canonical JSON-array encoding defined by
the main contract, never delimiter-concatenated text.

The precedence is machine-enforced in v1. A lower-precedence identity carrying
a DOI or official URI is quarantined pending a future reviewed-equivalence
contract; it cannot silently preserve or remint an accepted ID. DOI and official
URI values are canonical and unique corpus-wide. A project-scoped source-record
or fingerprint identity must be linked to the project in its seed.

`RESULT` stores only project-independent identity, bibliography/type, access,
asset and rights data. Battery relevance and domains are reviewed and stored on
`PROJECT_RESULT`, where a shared result may validly differ by grant.

Do not collapse a deliverable and publication merely because their titles are
similar. Do not confuse the project DOI `10.3030/<grant-id>` with a publication
or dataset DOI. A shared DOI produces one `research_result` and several
`project_result` links when multiple grants are acknowledged.

## Availability mapping

| Observation | Access status |
|---|---|
| Anonymous request returns the substantive document/file or official full narrative | `OPEN_FULL_CONTENT` |
| Public repository or project landing page is present but another action is required | `OPEN_REPOSITORY_LANDING_PAGE` |
| Bibliographic/result metadata is public; content access was not verified | `METADATA_ONLY` |
| Payment is required | `PAYWALLED` |
| Authentication, confidentiality or explicit restriction applies | `RESTRICTED_OR_CONFIDENTIAL` |
| Link is absent, broken or no longer resolves | `BROKEN_OR_MISSING` |

`OPEN_FULL_CONTENT` records require a verification timestamp. An
`OPEN_REPOSITORY_LANDING_PAGE` assertion requires the checked URL,
`access_verified_at` and check evidence recording the request method, HTTP
status, final URL after redirects, content type, whether access was anonymous,
and the observed reason another action is needed to reach the substantive
content. Both open states require anonymous `GET`; full content accepts a final
200/206 response with `SUBSTANTIVE_FILE` or `OFFICIAL_FULL_NARRATIVE`, while a
landing page requires a final 200 response, `LANDING_PAGE` and a non-empty
`availability_note`. DOI-only publications default to `METADATA_ONLY`. Link-check evidence
does not change the separate asset-redistribution decision.

## Source precedence and conflicts

- Funding & Tenders is authoritative for the award, call and topic definition.
- CORDIS/EURIO supplies research-oriented project and relationship metadata.
- OpenAIRE can enrich publications, datasets and software linked to a project.
- Project repositories can supply content only when grant attribution is
  verifiable.
- Conflicting values remain parallel source assertions until reviewed. No
  source silently overwrites another.

Raw source records are immutable, and harvesting is lossless: retain the
complete source row or document and every harvested field, including fields not
yet mapped into a canonical property, in a content-addressed source snapshot or
assertion. Source-normalized records retain raw value, normalized value,
`source_dataset`, source record ID, first/last-seen dates and payload hash so an
omitted canonical field remains recoverable and auditable. Canonical records are
versioned projections of those retained assertions. Approval materializes each
source artifact's bytes at its release-local `retained_path` and verifies the
declared size and digest; an official URL or manifest-only checksum is not a
substitute for the observed bytes.

Every harvested result observation is also emitted once in the strict, hashed
NDJSON source-observation ledger. Its deterministic row ID binds the source
artifact, dataset, source row number, project, partitions and final disposition.
The validator derives the 65,486 total, access/type/relevance partitions and
seed-project counts from this ledger and resolves linked rows to canonical
`PROJECT_RESULT` records. Copying the baseline summary without the rows cannot
pass approval.

## Refresh contract

Recommended observation cadence:

- weekly: active-project results and lightweight Portal/CORDIS probes;
- monthly: full Horizon Europe, H2020 and FP7 bulk files;
- quarterly: older closed projects and full archived/non-framework
  reconciliation; and
- annually: a clean deterministic rebuild from retained source snapshots.

The Git repository stores schemas, mappings, manifests, tests and compact QA
summaries. Large immutable raw snapshots belong in content-addressed object
storage; normalized Parquet/CSV/SQLite and the Excel workbook are release
artefacts. External result binaries remain link-only unless their individual
licence permits redistribution.
