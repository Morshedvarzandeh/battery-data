# EPO Linked Open EP Data battery-patent snapshot — 2026-09-04

This immutable review batch was retrieved from the European Patent Office's
Linked Open EP Data SPARQL endpoint. It searches six exact IPC classes to avoid
an unbounded full-text scrape:

| IPC seed | Review purpose | Source rows |
|---|---|---:|
| H01M10-0525 | Lithium-ion cells and materials | 350 |
| H01M10-44 | Charge/discharge control and electrical management | 100 |
| H01M10-48 | Monitoring, sensing and test hardware | 100 |
| H01M10-613 | Thermal management | 100 |
| H01M50-20 | Modules, packs, housings and structures | 100 |
| G01R31-367 | Battery diagnostics, SOC/SOH and software | 100 |

The source query is limited to EP A1/A2 publications with an English title. It
also retrieves inventive IPC classifications and published applicant
name/country values, application links, priorities and international-application
links. The 850 query observations consolidate to 801 publication
candidates because one publication can match multiple seed classes.

## Contents

- `source/` — exact EPO SPARQL JSON response bytes;
- `publication-candidates/` — publication-number-unique review records;
- `companies/` — normalised applicant-organisation profiles;
- `publication-company-links/` — applicant evidence edges;
- `company-index.json` — company/category navigation index;
- `duplicate-report.json` — repeated hits, cross-import checks and review
  collisions;
- `manifest.json` — hashes, counts, taxonomy versions and acceptance boundary.

These are not accepted patents, resolved DOCDB families or current-owner
assertions. Every record remains pending human review. Patent landscape data is
not a freedom-to-operate opinion.
