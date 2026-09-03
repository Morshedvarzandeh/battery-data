# Roadmap: from a schema to the best open battery dataset

Written 2026-09-03 from a review of the accepted library, the cell-bench page
and the review queue. It is a checklist, not a design document: an item is
ticked only when its change is committed **and** the CI gates still pass
(`tools/validate_contrib.py`, `tools/check_duplicates.py`,
`tools/validate_review.py`, `tools/build_web_data.py --check`, and the review
builders producing no diff).

The target is the largest open, provenance-first dataset of batteries and of
everything around them: every chemistry from lead-acid to sodium-ion to solid
state, every level from cell to grid container, and the components a battery
cannot work without: DC-DC converters, contactors, fuses, pyro-fuses, BMS,
busbars, sensors, chargers and thermal hardware.

The rule that governs every item below is the repository's own: **a value
without its conditions, its page and its quote is not a fact.** Nothing on this
list is satisfied by a number typed from memory, and where a source could not
be reached the item says so instead of being ticked.

### The environment this pass ran in

The session that works this list can reach GitHub and PyPI and nothing else:
every manufacturer, distributor, archive, publisher and dataset host is blocked
by the network egress policy. So this pass does three kinds of work, and says
which is which in the log:

1. **Structure**: schema, contribution format, validators, loaders, page and
   API, so the dataset can hold the full scope and scale without a rewrite.
2. **Data already in reach**: the review queue, the SQL reference cells, and
   parameter sets and datasets published on GitHub with their citations.
3. **Data that needs the network**: datasheet re-extraction and every new
   manufacturer document. Those items stay open, each with the exact command to
   run from a machine that can reach the source.

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

- [x] **1.1 Stale caption.** The report header still prints "figures provisional, no source locators", left over from the hand-typed seed page. Replace it with a per-column stated-or-derived flag.
- [x] **1.2 Define the capacity rule.** Wh/kg is built from the first capacity observation in the file whatever its rate. Rank on the lowest stated rate, prefer the standard or typical figure, and print the rate next to the number.
- [x] **1.3 Completeness column.** Fields present out of the twelve the completeness view tracks, plus the count of conditions the source leaves unstated, on the Compare table and the Report.
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

## 4. Everything around the battery

A pack is a cell plus the hardware that lets it be used safely. The same rule
applies to that hardware as to the cell: a contactor's breaking capacity
without the circuit voltage and time constant it was tested at is not a fact,
and a fuse's current rating without the ambient temperature is a derating
curve pretending to be a number.

- [ ] **4.1 Component taxonomy.** A `component_kind` on the product: DC-DC converter, contactor, relay, fuse, pyro-fuse, BMS, battery disconnect unit, busbar, cell contact system, current sensor, temperature sensor, pre-charge resistor, service disconnect, isolation monitor, on-board charger, inverter or PCS, cooling plate, chiller, heater, thermal interface material, vent, enclosure, connector, cable.
- [ ] **4.2 Quantities for switching and protection.** Rated voltage, rated current with its ambient, breaking capacity with circuit voltage and time constant, pre-arcing and total I²t, minimum breaking current, contact resistance at its test current, coil voltage, coil hold power, electrical and mechanical endurance, dielectric strength with its duration, insulation resistance, voltage drop, cold resistance.
- [ ] **4.3 Quantities for power conversion and sensing.** Input and output voltage windows, output current at ambient, conversion efficiency at a stated load and input voltage, switching frequency, standby draw, measurement range and accuracy, balancing current.
- [ ] **4.4 Component curves.** Time-current characteristic, current derating against ambient, efficiency against load, breaking capability against voltage.
- [ ] **4.5 Component coverage list.** The contactor, fuse, pyro-fuse, DC-DC, BMS, sensor, isolation-monitor and charger products a reference must carry, as a wishlist that turns into numbers as documents land.
- [ ] **4.6 Bill of materials.** Packs and systems name their contactors, fuses, BMS and DC-DC through `contains`, so the graph traverses the whole battery system.
- [ ] **4.7 Page and API for components.** Component kinds in the Compare filter with their own column set, a component sheet, and a components endpoint.

## 5. Every chemistry

- [ ] **5.1 Chemistry family and construction.** A `family` on the chemistry block: lithium-ion, lithium metal, lithium primary, sodium-ion, sodium-sulfur, sodium-nickel-chloride, lead-acid, nickel-metal-hydride, nickel-cadmium, nickel-zinc, zinc-air, alkaline, silver oxide, flow vanadium, flow zinc-bromine, flow iron, solid state, supercapacitor. A `construction` for lead-acid: flooded, AGM, gel, tubular plate, flat plate, bipolar, carbon-enhanced.
- [ ] **5.2 Lead-acid quantities.** Cold cranking current with temperature, duration, cutoff and the standard it follows; reserve capacity with its load and cutoff; float and cycle charge voltages with temperature; temperature compensation coefficient; design life on float at temperature; capacity at the 20-hour, 10-hour and 5-hour rates as separate observations.
- [ ] **5.3 Lead-acid and AGM coverage list.** Automotive, motive-power, stationary and UPS ranges from the makers a reference must carry.
- [ ] **5.4 Sodium coverage list.** Sodium-ion cells and packs from the makers shipping or sampling them, plus sodium-sulfur and sodium-nickel-chloride stationary products.
- [ ] **5.5 Nickel, zinc, flow and supercapacitor coverage lists.** NiMH and NiCd cells and packs, nickel-zinc, zinc-air, flow batteries by electrolyte, and supercapacitor cells and modules.
- [ ] **5.6 Conventions for the new chemistries.** The places these chemistries disagree with each other and with lithium practice, written into `docs/02-conventions.md` and enforced as required conditions.

## 6. Ontology and knowledge graph

The relational store is the source of truth; the graph and the semantic
export are derived from it. Compatibility means three things: every quantity
and unit resolves to a published IRI, every record can be emitted as RDF that
a triple store or a knowledge graph loads unchanged, and the graph projection
covers the whole scope above, components and applications included.

- [ ] **6.1 EMMO and BattINFO bindings, generated.** `tools/sync_vocabularies.py` pulls the EMMO domain-battery and domain-electrochemistry ontologies, checks in their label-to-IRI tables with the commit they came from, and binds `quantity.emmo_iri` from a curated label map instead of hand-copied IRIs.
- [ ] **6.2 QUDT bindings, verified.** Every quantity carries a QUDT quantity-kind IRI and every unit a QUDT unit IRI, checked against the QUDT vocabulary rather than typed.
- [ ] **6.3 RDF export.** The accepted library as JSON-LD and Turtle: products and revisions as schema.org and BattINFO classes, observations as SOSA observations with QUDT quantity values, conditions as typed properties, provenance as PROV-O, all deterministic and checked in CI.
- [ ] **6.4 Graph projection covers the whole scope.** Nodes and edges for applications, components inside packs, datasets and models, with a Neo4j and Apache AGE export.
- [ ] **6.5 Alignment document.** One table per external vocabulary saying which class or property each concept here maps to, and where the mapping is only approximate.

## Log

Entries are appended as items are ticked, newest last.
- 2026-09-03 · **1.1** · The Report header now states that every figure traces to a contribution and counts derived figures and issue-rebuilt records; density columns carry a stated-or-derived basis column; the source pill shows datasheet, maker web page or rebuilt-from-issue instead of a blanket 'datasheet'.
- 2026-09-03 · **1.2** · capacity_key() in tools/build_web_data.py: a stated rate beats an unstated one, the lowest stated rate wins, ties break standard > typical > rated. The winning rate is printed in the 'Ah at' column and the full basis is the hover text.
- 2026-09-03 · **1.3** · Fields present out of the twelve bd.v_completeness tracks, the missing list, and the count of unstated conditions, on the Compare table, the Report (new Completeness section, Markdown and CSV) and as a 'most complete record' leader.
