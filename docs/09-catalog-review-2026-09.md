# Battery library review — 16 September 2026

## Result

The library contains **2,170 accepted battery products and 12,335 observations**,
with **106 pending records**. These are product models, not individual physical
batteries or independently tested samples.

| Review group | Accepted | Held pending |
|---|---:|---:|
| Previously accepted library | 82 | — |
| Existing pending queue reviewed | 297 | 106 |
| New Harding Energy catalog models | 1,343 | — |
| New LiPol Battery catalog models | 448 | — |
| Total | **2,170** | **106** |

Accepted types: 1,920 rechargeable cells, 211 primary cells, 36 packs, 2 modules,
and 1 complete system. Each has a stable identity; packs and cells are distinct
product kinds.

The owner explicitly requested: “review the one that are there and pending and
if they are right not duplicated accept them”. Codex performed the delegated
review; no GitHub approval checkbox was represented as a human review.

The [machine-readable audit](../review/audits/2026-09-16-catalog-review.json)
records all 403 existing decisions and 1,791 new acceptances: source hashes,
original and accepted file hashes, methods, corrections, and individual hold
reasons. The 82 previously accepted records were included in schema and identity
checks, but were not all independently re-extracted in this review.

## Manufacturer catalog sources

| Source | Source rows | Accepted models | Repeated rows collapsed | Excluded rows |
|---|---:|---:|---:|---:|
| [Harding Energy, 2019 selection guide](https://www.hardingenergy.com/wp-content/uploads/2019/03/HEI-Lithium-Polymer-Cell-Selection-Guide-2019.pdf) | 1,371 | 1,343 | 3 | 25 |
| [LiPol Battery, page headed “new models 2013”](https://www.lipolbattery.com/lipo%20batteries.html) | 452 | 448 | 2 | 2 |

**These are historical catalogs; current availability is unverified.** Every
imported source note carries this caveat, displayed in the catalog. Acceptance
means the recorded claims match the cited source; it does not establish measured
performance under unspecified conditions or suitability for a design.

Harding has 37 pages and numbered rows through 1,372, but omits row 1,351. The
importer reconciles that exact sequence and fails if extraction loses a row.
LiPol extraction checks all four table headers and 452 rows. PDF pages 1, 8,
and 37 were visually inspected, including the exceptional unbounded 5.1 mm
thickness on row 275. This was structured catalog review with representative
visual checks, not individual datasheet review for all 1,791 models.

Fourteen model identities (27 source rows) were excluded before candidate
creation because specifications conflicted under one model, or a capacity and
dimension combination required clarification. Identical rows collapse to one
model. All excluded rows and duplicate decisions remain in the
[Harding manifest](../review/imports/2026-09-15-manufacturer-catalogs/harding-energy.json)
and [LiPol manifest](../review/imports/2026-09-15-manufacturer-catalogs/lipol-battery.json).
They are outside both the accepted and pending counts.

Capacity, printed voltage, dimensions, and mass where supplied retain native
units and printed ≥/≤ limits. “Voltage” is not relabeled nominal voltage or an
operating cutoff. Missing capacity test conditions are marked `unstated`. No
cathode chemistry or cell format is inferred from model numbers. Harding's
bare-cell dimensions exclude protection boards and assemblies; the source asks
customers to confirm dimensions before design use.

Manufacturer document bodies are not committed. Only extracted facts, row
locators, source URLs, retrieval dates, and SHA-256 hashes are retained.

## Existing queue review

Seventy-seven of 84 source URLs were retrieved: 41 PDFs and 36 HTML pages.
Seven CATL URLs returned HTTP 403; their ten candidates remain pending.

| Manufacturer | Accepted | Held | Main reason for held entries |
|---|---:|---:|---|
| Renata | 140 | 15 | Three identity/capacity conflict pairs, eight missing model matches, one anomalous mass |
| Maxell | 57 | 8 | Source variants disagree under the same model number |
| EEMB | 42 | 0 | Recorded values matched the table and explicit family statements |
| Panasonic | 27 | 1 | Separate model-page source not independently verified |
| Energizer | 17 | 14 | Additional diagram, capacity, or protocol mapping needed |
| Murata | 11 | 0 | Recorded values matched the model table |
| HiTHIUM | 3 | 3 | Approximate densities labeled minimum; unsupported temperature scope |
| Molicel | 0 | 13 | Standard, fast-charge, and continuous-current labels need confirmation |
| CATL | 0 | 10 | Source retrieval blocked |
| EVE | 0 | 10 | Resistance units/bounds, current labels, dimension axes, or conflicting source claims |
| BYD | 0 | 9 | Missing usable-energy test footnote and unsupported temperature scope |
| CNTE | 0 | 7 | AC/DC boundaries, dimensions, and system limits need review |
| BAK | 0 | 6 | Resistance method not established; lost tolerances |
| LG Energy Solution | 0 | 5 | Listing does not establish numeric specifications |
| Samsung SDI | 0 | 5 | Mass limits treated as exact; module identities/dimensions need review |

For example, EVE 21700-40P's source says ≤12 mΩ, while the candidate contains
0.012 mΩ. It was not accepted. Holding a record does not necessarily mean every
value is wrong; some lack sufficient verification.

The full-library duplicate check reports zero exact and zero probable duplicates.
Three Renata pairs remain pending because normalized names match but capacities
differ. Punctuation was not used to manufacture extra accepted entries.

## Repository structure

```text
contrib/cells/<manufacturer>/<model>.yaml   accepted products
review/candidates/<manufacturer>/*.yaml    unresolved candidates
review/index.json                         review state and audit links
review/audits/                            per-record review decisions
review/imports/                           extracted facts and reconciliation
json-schema/                             contribution schema and quantity rules
schema/                                  PostgreSQL schema
tools/                                  import, validation, review and export
web/index.html                           generated catalog
```

Each contribution groups identity, source metadata, optional sourced chemistry,
and observations. Observations have a quantity, value, unit, statistic or bound,
test conditions (or explicitly missing conditions), and evidence locator. The
database separates product identity, document-specific revision, and physical
unit. Its graph is a derived view.

## Reproduce and validate

Download the source documents separately, then run the offline importer:

```bash
python tools/import_manufacturer_catalogs.py \
  --harding-pdf /path/to/harding-2019.pdf \
  --lipol-html /path/to/lipol.html \
  --retrieved-at 2026-09-15
python tools/build_review_batch.py
python tools/render_review_issues.py
python tools/build_web_data.py
python tools/validate_contrib.py contrib/
python tools/validate_contrib.py review/candidates/
python tools/validate_review.py
python tools/check_duplicates.py
python -m unittest discover -s tests -p 'test_*.py'
```

Manifest hashes identify the reviewed source bytes; changed live documents need
fresh review. Regeneration preserves accepted states without recreating approved
candidates. The web view retains native units, bounds, notes, and locators;
bounded inputs are excluded from calculations presented as exact estimates.
