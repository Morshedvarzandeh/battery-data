# Patent ingestion and classification

The patent layer follows the same rule as cell data: unreviewed extraction
cannot enter accepted tables. Patent identity adds a second problem that product
specifications do not have — a publication is not a family, and a family is not
a jurisdiction-independent legal status.

## Pipeline

```text
CORDIS PATENT_IP source rows (1,155)
              |
              +--> source_label_only (894) --> office-identity review
              |
              +--> verified publication rows (261)
                         |
                         +--> publication-number dedupe (255 candidates)
                                      |
                                      +--> DOCDB family resolution
                                      +--> CPC/IPC + abstract/claims classification
                                      +--> applicant/inventor/legal-status enrichment
                                      +--> human review
                                      +--> accepted patent_family / patent_publication
```

No row is discarded by a heuristic. Source-level duplicates and conflicting
titles stay visible through `source_observation_ids`.

## Classification

`patents/taxonomy.json` is versioned and multi-label. It implements electrical,
mechanical, software and hardware as requested domains, plus battery-specific
technical categories. Keyword classification is only a triage aid. Accepted
classification must be based on the abstract/claims and, when available, CPC or
IPC codes with their scheme version.

## Relational model

- `bd.patent_family` is the reviewed DOCDB-family identity.
- `bd.patent_publication` is a jurisdiction publication within a family.
- `bd.patent_classification` stores versioned, reviewable multi-label tags.
- `bd.patent_project_link` preserves the EU project/result relationship.
- `bd.patent_entity_link` connects reviewed families to products, revisions,
  materials or organisations without weakening their provenance.
- `bd_stage.patent_observation` receives every raw source row.
- `bd_stage.patent_publication_candidate` receives publication-number-deduped
  candidates; it does not promote them.

An accepted family requires a DOCDB family ID and provenance. An accepted
publication requires a family, source and provenance. A legal status cannot be
stored without a jurisdiction and observation date.

## From review to the accepted tables

A family that has been resolved and reviewed enters the accepted tables
through a contribution file, `contrib/patents/<docdb-family-id>.yaml`
([format](../json-schema/patent-contribution.schema.json), fictional example
in [`docs/examples/patent.yaml`](examples/patent.yaml)): the family with its
DOCDB id and primary category, each publication with its dates, applicants,
inventors, categories and legal status observed on a date, and the links to
companies, products and materials, every one with a locator into the office
record. `tools/validate_layers.py` checks it offline (jurisdiction against the
number, one primary category, a legal status with its jurisdiction and date,
links to uids the library holds); `tools/load_layers.py` writes it as
`review = accepted` with provenance, which is the only way rows reach
`bd.patent_family` and `bd.patent_publication`. The staging import never
promotes anything, and CI checks that it did not.

Accepted patents are queryable as `/v1/patent_families`, `/v1/patents` and
`/v1/patent_categories` ([`docs/13-api.md`](13-api.md)), appear in the graph
projection as `PatentFamily` and `PatentPublication` nodes with
`HAS_PUBLICATION`, `PUBLISHED_AS` and `PATENT_RELATES_TO` edges, and in the
RDF export as `bdv:PatentFamily` and `bdv:PatentPublication`.

## Authoritative enrichment sources

- EPO Open Patent Services (OPS): bibliographic, family, citation and legal data
  through authenticated web services.
- EPO DOCDB families: family identity for publication grouping.
- WIPO PATENTSCOPE: international and participating national collections.
- USPTO Open Data Portal: current USPTO datasets and PatentsView access.

The checked-in import contains metadata and source links, not patent full text.
Family resolution and legal-status updates must record the source and retrieval
date used for each assertion.
