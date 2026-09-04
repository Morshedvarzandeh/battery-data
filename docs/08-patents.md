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

EPO Linked Open EP Data (850 query observations)
              |
              +--> query-hit dedupe (801 new EP A1/A2 candidates)
                           |
                           +--> company/entity resolution queue (383)
                           +--> applicant links (856)
                           +--> DOCDB family + claims review
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
- `bd.organization_category` and `bd.organization_category_assignment` provide
  a versioned company value-chain taxonomy.
- `bd.patent_organization_link` distinguishes applicant, assignee, observed
  owner and licensee; these relations are never treated as interchangeable.
- `bd_stage.patent_observation` receives every raw source row.
- `bd_stage.patent_publication_candidate` receives publication-number-deduped
  candidates; it does not promote them.
- `bd_stage.patent_company_candidate` and
  `bd_stage.patent_publication_company_link` hold company profiles and applicant
  relations until entity-curator approval.

An accepted family requires a DOCDB family ID and provenance. An accepted
publication requires a family, source and provenance. A legal status cannot be
stored without a jurisdiction and observation date.

## Authoritative enrichment sources

- EPO Open Patent Services (OPS): bibliographic, family, citation and legal data
  through authenticated web services.
- EPO DOCDB families: family identity for publication grouping.
- WIPO PATENTSCOPE: international and participating national collections.
- USPTO Open Data Portal: current USPTO datasets and PatentsView access.

The checked-in import contains metadata and source links, not patent full text.
Family resolution and legal-status updates must record the source and retrieval
date used for each assertion.

## Company review

Applicant names are resolved conservatively. Case and punctuation variants can
collapse, and aliases explicitly listed in `patents/company-registry.json` can
resolve to one candidate. Parent/subsidiary relationships and former-company
relationships are never inferred from similar names. Profiles expose legal
name, aliases, country, website, ROR/LEI slots, value-chain categories, complete
publication portfolios and technical-category counts; unknown values stay null
and carry an explicit review flag.

The accepted read API exposes `/v1/patent-companies`, filterable by `category`
and `country`, plus `/v1/patent-companies/{uid}` for the linked publication
portfolio. Pending candidates remain in the protected review layer and do not
appear in these endpoints.
