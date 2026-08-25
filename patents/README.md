# Patent review corpus

This directory is a separate patent knowledge layer. It does not turn a CORDIS
result label into an accepted patent and it does not mix unreviewed patent data
with accepted battery product specifications.

## Current import

`imports/cordis-2026-08-21/` preserves all 1,155 rows labelled `PATENT_IP` in
the CORDIS battery-project result snapshot:

- `source-observations/part-*.jsonl` — every source row, unchanged in meaning and with
  a stable observation ID, provenance, provisional categories and review flags;
- `publication-candidates/part-*.jsonl` — 261 rows with official Espacenet search URLs
  collapsed to 255 unique publication-number candidates;
- `duplicate-report.json` — exact publication groups, source-result collisions
  and title collisions, without deleting source observations;
- `manifest.json` — source hash, row reconciliation, category counts and the
  acceptance boundary.

The remaining 894 rows have only the broad CORDIS patent/IP source label. They
stay `source_label_only` until an official publication/application number is
found. Obvious websites, reports, events and similar titles are flagged, not
silently discarded.

## Categories

Classification is multi-label. The four requested domains are:

- electrical — BMS electrical functions, switching, protection, conversion and
  power paths;
- mechanical — housings, structures, compression, joining, crash protection,
  sealing and vent mechanics;
- software — control, estimation, diagnostics, optimisation, digital twins and
  cybersecurity;
- hardware — circuits, PCBs, ASICs, controllers, sensors and gateways.

Battery-specific categories cover electrochemistry/materials, manufacturing,
thermal safety, charging infrastructure, and recycling/second life. All keyword
labels are provisional and must be checked against the patent abstract and
claims before acceptance.

## Identity and review rules

1. A source observation is never an accepted patent.
2. A publication number is not a patent family. DOCDB family resolution is a
   separate required step.
3. Exact publication duplicates collapse only in the candidate view; every
   source observation remains present and linked.
4. Legal status is jurisdiction-specific and must carry an `as_of` date.
5. Patent landscape data is not a freedom-to-operate opinion.
6. Accepted families require human review and provenance. The SQL schema
   enforces this boundary.

## Commands

```bash
python tools/validate_patents.py
python tools/check_patent_duplicates.py --fail-on exact
python tools/load_patents.py --dsn "dbname=batterydb"  # staging only
```

To reproduce the checked-in files from the source workbook:

```bash
python tools/import_cordis_patents.py \
  EU_CORDIS_Battery_Projects_Public_Results_2026-08-21.xlsx \
  --output patents/imports/cordis-2026-08-21
```

Official enrichment sources are EPO Open Patent Services and DOCDB families,
WIPO PATENTSCOPE, and the USPTO Open Data Portal. Credentials are never stored
in the repository.
