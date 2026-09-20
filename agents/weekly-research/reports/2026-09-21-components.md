# Battery fuses and precharge resistors — 21 September 2026

## Result

133 additional manufacturer-listed component models, 712 observations, all pending
review. The scope is battery-system protection and precharge, including Sensata;
no numeric component quota was specified. This is a manually requested expansion,
separate from the weekly run's default 20-model ceiling.

| Source family | Added fuse models | Added resistor models | Evidence |
|---|---:|---:|---|
| Sensata GIGAVAC GFP400 | 1 | 0 | Exact GFPA415B ordering example; technical table and note 3 |
| Mersen ABAT15C | 16 | 0 | Page 2 part table, including distinct TTF/LI terminals |
| Mersen ABAT13C / 13D / 13G | 8 / 3 / 3 | 0 | Page 2 part tables; page 1 qualified maximum interruption |
| Mersen NH gBat | 50 | 0 | Pages 2–4; size/current-specific UL table on page 1 |
| Vishay HRHA | 0 | 28 | 30 listed part IDs, standard ordering legend; 2 held |
| Vishay LTO150H | 0 | 24 | 27 listed part IDs, standard ordering legend; 3 held |
| **Total** | **81** | **52** | **133 distinct part numbers; eight product families** |

Component library after this batch: **146 pending models / 774 observations**,
zero accepted. Battery records remain **2,170 accepted / 1,362 pending**. Patents
were not researched or changed in this batch. Components never count as batteries.

## Provenance

The [manifest](../../../review/imports/2026-09-21-battery-fuses-precharge-resistors.json)
contains manufacturer URLs, retrieval date, literal revisions, seven original PDF
hashes, two identity-page hashes, all 80 Mersen table rows and all 57 listed Vishay
identities (52 candidates and five held). Original copyrighted bodies remain
outside Git. Downloaded table/legend pages were checked visually against extraction.

Sensata's manufacturer PDF was readable through web text retrieval. Direct bytes
returned HTTP 403 and screenshot retrieval supplied no viewable image, so its
source explicitly lacks a hash and flags visual verification as pending. Only
the explicit GFPA415B example is included; ordering options are not multiplied
into invented part numbers.

Vishay part identities come from the complete page-provided `qualityTabResults`
list, beyond the first 25 displayed rows. Resistance/tolerance are decoded using
the corresponding datasheet's ordering legend. Each decoded observation retains
the identity URL, byte hash and row, and is labelled as decoded rather than measured.
HRHA's datasheet is dated 2021; listing does not prove current availability.
LTO150H's EV/BMS precharge application is stated in the linked official release.

## Accuracy decisions

- Sensata: 400 A continuous with 4/0 busbars is separate from the 1500 A trigger
  and its +100/−400 A tolerance. Breaking points retain 650 V / 15.5 kA / 12 µH
  and up to 850 V / 12 kA / 4 µH. No 10 kA at 1000 V inference.
- Mersen ABAT15C: TTF 250 kA and LI 200 kA use the part table's L/R = 3 ms,
  preserving the different minimum breaking currents. The inconsistent page 1
  overview heading of L/R ≤ 4 ms is disclosed, not substituted for table conditions.
- Mersen NH: 1XL/2XL UL 50 kA at 1 ms, 3L through 400 A UL 150 kA at 3 ms,
  and 3L 450/500 A UL 200 kA at 3 ms remain distinct. NH1/NH2 have no imported
  interruption value because they are omitted from that qualified UL table.
  I²t values and curves were not promoted into observations in this batch.
- HRHA: 90 W on 6 mm stainless steel versus 54 W on 6 mm Pamitherm at 30°C
  ambient. Four energy observations preserve waveform, duration and cooling wait:
  9000 J / 1.8 s / 100 or 167 s; 1850 J / 0.74 s / 30 or 34 s.
- LTO150H: 150 W requires a heatsink/clip and 45°C case; free-air 4.5 W at 25°C
  is separate and the latter's temperature reference is explicitly unstated.
  The 500 V limiting element voltage has no assumed AC/DC designation. The
  headline 75 J/0.1 s is not treated as an unconditional rating.
- Nameplate current is not a recommended load current. Source-stated application
  roles are not evidence of installation in a specific vehicle or battery pack.

## Held and follow-up

Held HRHATP10R0JB and HRHATP10R0JB991: termination/coating/custom code outside the
inspected standard legend. Held LTO150H6R190FTE3 (unsupported F tolerance),
LTO150H5R000GTB7 and LTO150H470R0JTB7 (nonstandard suffix). No default family
specifications were assigned to these five identities.

Sensata's 2020 fuse catalog bytes were inaccessible; the HVF summary did not
establish exact orderable part IDs. Eaton's DC catalog was web-readable but direct
download failed; its ESS battery-fuse tables are a future source. See the updated
[backlog](../source-backlog.json). No manufacturer was contacted and no paid
research service was used.

## Structure and reproduction

Added `precharge_resistor` as the seventh category. Seven new quantity codes
separate resistor ratings, fuse trigger current and minimum interruption from
battery impedance/energy and converter output. JSON Schema, SQL, quantity groups,
review rendering, catalog and export share the same structure. Duplicate checks
now include accepted components and compare resistance/tolerance and fuse ratings.

```bash
python tools/import_battery_components.py --check
# Optional re-extraction from the exact downloaded bodies, outside Git:
python tools/import_battery_components.py --source-dir /path/to/sources --check
python tools/build_review_batch.py
python tools/render_review_issues.py
python tools/build_component_catalog.py
python tools/build_web_data.py
python tools/validate_contrib.py contrib/
python tools/validate_contrib.py review/candidates/
python tools/validate_review.py
python tools/check_duplicates.py
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_web_observations.cjs
```

CI exercises representative new components in a disposable PostgreSQL transaction
and rolls it back, checking kA conversion, asymmetric trip tolerance, percent
conversion, case temperature and all four distinct pulse-condition identities.
The SQL files initialize fresh databases; an existing deployment needs an additive
migration before using these new columns/enums. No live database was rebuilt.

Local validation passed: all 2,170 accepted records and 1,508 pending records;
78 Python regression tests; JavaScript observation-display tests; byte-verified
source re-extraction; catalog freshness; whitespace checks. The duplicate scan
found zero exact/probable duplicates and only the three pre-existing Renata
punctuation/capacity conflicts. No new component identity collision was found.
