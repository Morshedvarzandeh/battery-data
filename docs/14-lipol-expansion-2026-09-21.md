# Battery model expansion — 21 September 2026

> Publication update, 4 October: reviewed records have now been promoted.
> This report preserves the research-stage counts and decisions. See the
> [acceptance report](16-catalog-publication-2026-10-04.md) for current counts and remaining holds.

## Result and scope

**1,256 additional, distinct LiPol Battery model candidates** were found against
the existing accepted and pending library, exceeding the requested 590 additions.
They contain **6,280 sourced observations**, covering printed capacities from
1,000 to 4,950 mAh. This batch is from one manufacturer and expands catalog
specifications; it does not add laboratory performance curves or independent
test results.

The candidates remain **pending review**. The accepted library contains 2,170
battery products. The queue now contains 1,362 battery candidates (106 existing
plus 1,256 new) and 13 electrical components, or 1,375 pending products in total.
New entries are not included in the accepted public catalog or API snapshot.

- [Candidate declarations](../review/batches/2026-09-21-lipol-catalog-expansion.json)
- [Complete source-row reconciliation and hold reasons](../review/imports/2026-09-21-lipol-catalogs.json)
- [Individual candidate records](../review/candidates/lipol-battery/)
- [Review queue](../review/index.json)

## Sources and counting

Six manufacturer pages were downloaded on 21 September 2026. Their URLs,
retrieval dates, byte counts and SHA-256 hashes are recorded in the manifest.
Only extracted facts and locators are committed; the proprietary HTML documents
are not redistributed.

| Manufacturer page | Role | Catalog rows | New candidates sourced here |
|---|---|---:|---:|
| [1,000–3,000 mAh catalog](https://www.lipobattery.us/1000mah-to-3000mah-li-po-batteries/) | Primary | 1,668 | 834 |
| [3,000–5,000 mAh catalog](https://www.lipobattery.us/3000mah-to-5000mah-li-polymer-batteries/) | Primary | 940 | 422 |
| [5,000–10,000 mAh catalog](https://www.lipobattery.us/5000mah-to-10000mah-li-poly-batteries/) | Primary | 665 | 0 |
| [General lithium-ion polymer catalog](https://www.lipobattery.us/china-made-lithium-ion-polymer-battery/) | Cross-check | 459 | — |
| [LP603450 page and related-model tables](https://www.lipobattery.us/1000mah-regular-lipo-battery-lp603450/) | Cross-check | 1,501 | — |
| [LP105274 page and related-model table](https://www.lipobattery.us/li-polymer-batteries-lp105274-4800mah-with-pcm-and-wires-50mm-and-jst-phr-2/) | Cross-check | 388 | — |
| **Total** | | **5,621** | **1,256** |

The three primary pages contain 3,273 catalog rows but only **1,892 model
identities**. Repeated tables and repeated rows do not count as extra products.
The cross-check pages also contain 1,514 identities outside the primary catalogs;
those are retained as cross-check evidence, not added to the candidate count.
Two individual protected-assembly specification tables are retained separately
and excluded from the catalog-row counts above.

| Decision for primary-catalog identities | Models |
|---|---:|
| New, consistent candidates queued for review | **1,256** |
| Already present in accepted data or the pending queue | 15 |
| Conflicting values within or between manufacturer pages | 191 |
| No complete primary row containing capacity, voltage and all three dimensions | 411 |
| Capacity/dimension sanity screen requires clarification | 8 |
| Model/dimension pattern requires clarification | 10 |
| Protected-assembly scope requires clarification | 1 |
| **Total primary identities** | **1,892** |

All 621 unresolved primary identities remain in the reconciliation manifest,
outside both the accepted count and the 1,256 new candidate count. Cross-checks
are from the same manufacturer; agreement between pages is not independent
verification of performance.

## Accuracy controls

1. **Identity:** keep the existing `LiPol Battery Co., Ltd.` manufacturer identity
   across `lipolbattery.com` and `lipobattery.us`. Check model numbers and aliases
   against accepted and pending records. The baseline records and file hashes
   are retained. Distinct manufacturers are not merged just because dimensions
   or numeric model codes match.
2. **Complete accounting:** pin table headers, table counts, row counts, and
   first/last model entries. Every catalog row has a stable source/table/row ID
   and exactly one model decision. Unsupported values are retained and flagged.
3. **Conflicts:** compare every overlapping field, including partial rows with
   no voltage. A contradictory row holds the whole new model identity; the
   importer never selects the most convenient capacity. For example, LP2884157
   appears as both 4,000 and 4,400 mAh and is held.
4. **No repair by inference:** the importer never fills missing voltage from a
   page introduction, derives dimensions from a model number, or combines
   complementary rows into a new specification. Each candidate's five values
   come from a single complete primary row.
5. **Conservative anomaly screening:** a capacity × printed voltage / volume
   proxy outside 100–1,000 Wh/L triggers a hold. This is only a screening
   calculation and is never stored as measured or nominal energy density.
   Model/dimension strings inconsistent with the pattern observed in this
   catalog are also held. The naming pattern is a heuristic, not a verified
   manufacturer rule. For example, LP103228 is printed with a 22 mm length;
   the importer preserves that evidence and holds the entry without correcting it.
6. **Earlier exclusions:** the previous LiPol import's unresolved identities
   remain excluded if encountered in a primary row. New source pages cannot
   silently revive an earlier conflict.

## Record structure and limits

Each JSON-compatible YAML candidate uses the existing contribution schema:

```text
schema_version
product       stable UID, manufacturer, model, kind, rechargeable flag
source        manufacturer URL, title, retrieval date, hash, scope notes
chemistry     sourced lithium-polymer family designation and locator
observations  capacity, printed voltage, length, width, thickness
              each with native unit and table/row evidence
```

Capacity stays in mAh; voltage stays in V; dimensions stay in mm. The printed
`Voltage` column is recorded as `voltage`, without inventing a nominal rating,
charge voltage or cutoff. Capacity test rate, rate unit, temperature and lower
voltage limit are explicitly `unstated`. No rated/minimum/typical statistic is
invented. Dimension axes follow the actual column header.

The product kind follows the existing LiPol catalog's `cell` convention, but
the source notes explicitly leave bare-cell versus protected-assembly dimension
scope unresolved. Tolerances, current limits, chemistry subtype, certification,
cycle life and present availability are not established by these catalog rows.
Generic page claims are not copied into individual products. All of these
limitations remain visible in the candidate files and rendered review payloads.

## Validation and reproduction

The offline importer is [tools/import_lipol_expansion.py](../tools/import_lipol_expansion.py).
Place the six source bodies outside the repository as `<source_key>.html`, with
the manifest's `sources` array saved beside them as `sources.json`. The source
bytes must match the recorded hashes; changed live pages need a fresh review.

```bash
python tools/import_lipol_expansion.py --source-dir /path/to/downloaded-sources
python tools/build_review_batch.py
python tools/render_review_issues.py
python tools/validate_contrib.py review/candidates/
python tools/validate_review.py
python tools/check_duplicates.py
python -m unittest discover -s tests -p 'test_*.py'
```

The committed facts can also be re-parsed and reconciled without downloading
the source bodies. Tests cover axis order, absent conditions, duplicate rows,
aliases, conflicting capacities, earlier holds, malformed dimensions, changed
headers, truncated tables, complete row accounting, and exact regeneration of
the candidate declarations. Schema validation passes for all 1,375 pending
records. The duplicate checker reports zero exact or probable duplicates; the
three previously known Renata identity conflicts remain pending.

The batch is reviewable through its files and pull request. Rendered issue
payloads are prepared locally; individual GitHub issues are not automatically
created by this import.
