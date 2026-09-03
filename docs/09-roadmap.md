# Roadmap: from a schema to the best open battery dataset

Written 2026-09-03 from a review of the accepted library, the cell-bench page
and the review queue. It is a checklist, not a design document: an item is
ticked only when its change is committed **and** the CI gates still pass
(`tools/validate_contrib.py`, `tools/check_duplicates.py`,
`tools/validate_review.py`, `tools/build_web_data.py --check`, and the review
builders producing no diff).

The rule that governs every item below is the repository's own: **a value
without its conditions, its page and its quote is not a fact.** Nothing on this
list is satisfied by a number typed from memory, and where a source could not
be reached the item says so instead of being ticked.

## Where the library stood when this was written

82 accepted products, 690 observations, one source per product.

| Gap | Affected |
|---|---|
| Capacity with rate, temperature or cutoff unstated | 77 of 82 files |
| Observations carrying any C-rate at all | 8 of 690 |
| No internal resistance of either kind | 69 of 82 |
| DC pulse resistance | 0 of 82 |
| No discharge current or power limit | 61 of 82 |
| No chemistry designation | 52 of 82 |
| No form factor | 57 of 82 |
| No cycle life among rechargeables | 47 |
| No charge or discharge cutoff voltage | 81 of 82 |
| No `statistic` label on the value | 536 of 690 observations |
| Source is a web page rather than a datasheet | 70 of 82 |
| No document hash / no document date | 81 / 64 of 82 |
| Files with curves / applications / measured test data | 1 / 0 / 0 |
| Registry quantities never used | 46 of 98 |
| Coverage wishlist sourced | 2 of 49 targets |
| Candidates waiting in the review queue | 372 |

## 1. The Report tab

- [ ] **1.1 Stale caption.** The report header still prints "figures provisional, no source locators", left over from the hand-typed seed page. Replace it with a per-column stated-or-derived flag.
- [ ] **1.2 Define the capacity rule.** Wh/kg is built from the first capacity observation in the file whatever its rate. Rank on the lowest stated rate, prefer the standard or typical figure, and print the rate next to the number.
- [ ] **1.3 Completeness column.** Fields present out of the twelve the completeness view tracks, plus the count of conditions the source leaves unstated, on the Compare table and the Report.
- [ ] **1.4 Coverage wiring.** Targets that already exist in `contrib/` must carry their uid in `web/data/coverage.json` so they count as sourced.
- [ ] **1.5 Reference cells reach the page.** The four seed cells and the SQL pack catalogue never reach the page because it reads only `contrib/`. Port the reference cells to YAML without doubling them in the database.
- [ ] **1.6 Columns an engineer selects on.** Max continuous discharge current at its temperature, DC resistance with method and duration, cycle life with its conditions, operating window, standard charge current, source kind, revision and date.

## 2. Every product record

Format first, then data. Each value carries its conditions and a locator.

- [ ] **2.1 Capacity at two rates**, standard near 0.2C and rated near 1C, with temperature and cutoff.
- [ ] **2.2 Voltages**: nominal, charge cutoff, discharge cutoff, temperature-dependent cutoff where stated.
- [ ] **2.3 Charging**: standard charge current, CV termination current, max charge current per temperature band, charge time.
- [ ] **2.4 Discharge limits**: max continuous current per temperature band, pulse current with duration.
- [ ] **2.5 Resistance both ways**: AC at 1 kHz, DC pulse with duration, current, SOC, temperature and direction.
- [ ] **2.6 Life**: cycle life with DoD, rate, temperature and end-of-life criterion, clamp force for prismatics, calendar life.
- [ ] **2.7 Envelope**: operating window by direction, storage window banded by duration, self-discharge with its period.
- [ ] **2.8 Physical**: dimensions with basis, mass basis, volume, the maker's own Wh/kg and Wh/L.
- [ ] **2.9 Identity**: chemistry with cathode and anode text, form factor, IEC designation, aliases, lifecycle status, successor.
- [ ] **2.10 Compliance**: UN 38.3, IEC 62133, UL 1642, UL 9540A claims with certificate numbers. Add the section to the contribution format and loader.
- [ ] **2.11 Curves**: discharge curves at several rates and temperatures, cycle-life curve, OCV against SOC both directions, derating maps.
- [ ] **2.12 Applications**: where the cell is fielded, with basis and confidence.
- [ ] **2.13 Source hygiene**: sha256, retrieval date, revision, page number and a `statistic` on every value; re-extract the records rebuilt from issue text from their real documents.

## 3. Breadth, and the layers beyond datasheets

- [ ] **3.1 Clear the review queue.** Promote the pending candidates that pass validation and the duplicate gate.
- [ ] **3.2 The coverage wishlist.** Source the missing targets: LG MJ1, M50 and HG2; Samsung 35E, 30Q, 40T and 50S; Panasonic NCR18650B and the 2170; Molicel P26A to P45B; Murata VTC5A and VTC6; BYD Blade; CATL Shenxing; EVE LF280K, LF304 and LF560K; Gotion; the 4680 and 4695 families; LG, SK On and AESC pouch; CATL, HiNa and Natron sodium-ion; QuantumScape, Solid Power, WeLion and ProLogium; Yinlong and Microvast LTO.
- [ ] **3.3 Other chemistries the scope promises.** Li-SOCl2 and Li-MnO2 primary cells; alkaline and Li-FeS2; NiMH; silicon-anode and LMFP cells.
- [ ] **3.4 Measured test data.** Register and ingest Severson 2019, Oxford 2017, NASA PCoE and CALCE, with their cells as products and runs linked to units.
- [ ] **3.5 Independent characterisation.** Third-party tests and teardown chemistry under their own evidence basis.
- [ ] **3.6 Commercial and lifecycle layers.** Price and availability as a time series, active or end-of-life status, rebadge and second-source equivalences.
- [ ] **3.7 Assembly links.** Packs, modules and systems name their cells so the graph has something to traverse.
- [ ] **3.8 EU passport fields.** Carbon footprint, recycled content, expected lifetime in cycles and years, power at −10 °C.
- [ ] **3.9 Model parameters.** A BPX set and an ECM surface for at least one cell.
- [ ] **3.10 A second source per product.** Distributor listings or a second revision for the top cells, so the contradiction view has something to detect.

## Log

Entries are appended as items are ticked, newest last.

