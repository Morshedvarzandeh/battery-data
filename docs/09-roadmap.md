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
- [x] **1.4 Coverage wiring.** Targets that already exist in `contrib/` must carry their uid in `web/data/coverage.json` so they count as sourced.
- [x] **1.5 Reference cells reach the page.** The four seed cells and the SQL pack catalogue never reach the page because it reads only `contrib/`. Port the reference cells to YAML without doubling them in the database.
- [x] **1.6 Columns an engineer selects on.** Max continuous discharge current at its temperature, DC resistance with method and duration, cycle life with its conditions, operating window, standard charge current, source kind, revision and date.

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
- [x] **2.9 Identity**: chemistry with cathode and anode text, form factor, IEC designation, aliases, lifecycle status, successor.
- [x] **2.10 Compliance**: UN 38.3, IEC 62133, UL 1642, UL 9540A claims with certificate numbers. Add the section to the contribution format and loader.
- [ ] **2.11 Curves**: discharge curves at several rates and temperatures, cycle-life curve, OCV against SOC both directions, derating maps.
- [ ] **2.12 Applications**: where the cell is fielded, with basis and confidence.
- [ ] **2.13 Source hygiene**: sha256, retrieval date, revision, page number and a `statistic` on every value; re-extract the records rebuilt from issue text from their real documents.

## 3. Breadth, and the layers beyond datasheets

- [x] **3.1 Clear the review queue.** Promote the pending candidates that pass validation and the duplicate gate.
- [ ] **3.2 The coverage wishlist.** Source the missing targets: LG MJ1, M50 and HG2; Samsung 35E, 30Q, 40T and 50S; Panasonic NCR18650B and the 2170; Molicel P26A to P45B; Murata VTC5A and VTC6; BYD Blade; CATL Shenxing; EVE LF280K, LF304 and LF560K; Gotion; the 4680 and 4695 families; LG, SK On and AESC pouch; CATL, HiNa and Natron sodium-ion; QuantumScape, Solid Power, WeLion and ProLogium; Yinlong and Microvast LTO.
- [ ] **3.3 Other chemistries the scope promises.** Li-SOCl2 and Li-MnO2 primary cells; alkaline and Li-FeS2; NiMH; silicon-anode and LMFP cells.
- [ ] **3.4 Measured test data.** Register and ingest Severson 2019, Oxford 2017, NASA PCoE and CALCE, with their cells as products and runs linked to units.
- [ ] **3.5 Independent characterisation.** Third-party tests and teardown chemistry under their own evidence basis.
- [x] **3.6 Commercial and lifecycle layers.** Price and availability as a time series, active or end-of-life status, rebadge and second-source equivalences.
- [x] **3.7 Assembly links.** Packs, modules and systems name their cells so the graph has something to traverse.
- [ ] **3.8 EU passport fields.** Carbon footprint, recycled content, expected lifetime in cycles and years, power at −10 °C.
- [x] **3.9 Model parameters.** A BPX set and an ECM surface for at least one cell.
- [ ] **3.10 A second source per product.** Distributor listings or a second revision for the top cells, so the contradiction view has something to detect.

## 4. Everything around the battery

A pack is a cell plus the hardware that lets it be used safely. The same rule
applies to that hardware as to the cell: a contactor's breaking capacity
without the circuit voltage and time constant it was tested at is not a fact,
and a fuse's current rating without the ambient temperature is a derating
curve pretending to be a number.

- [x] **4.1 Component taxonomy.** A `component_kind` on the product: DC-DC converter, contactor, relay, fuse, pyro-fuse, BMS, battery disconnect unit, busbar, cell contact system, current sensor, temperature sensor, pre-charge resistor, service disconnect, isolation monitor, on-board charger, inverter or PCS, cooling plate, chiller, heater, thermal interface material, vent, enclosure, connector, cable.
- [x] **4.2 Quantities for switching and protection.** Rated voltage, rated current with its ambient, breaking capacity with circuit voltage and time constant, pre-arcing and total I²t, minimum breaking current, contact resistance at its test current, coil voltage, coil hold power, electrical and mechanical endurance, dielectric strength with its duration, insulation resistance, voltage drop, cold resistance.
- [x] **4.3 Quantities for power conversion and sensing.** Input and output voltage windows, output current at ambient, conversion efficiency at a stated load and input voltage, switching frequency, standby draw, measurement range and accuracy, balancing current.
- [ ] **4.4 Component curves.** Time-current characteristic, current derating against ambient, efficiency against load, breaking capability against voltage.
- [x] **4.5 Component coverage list.** The contactor, fuse, pyro-fuse, DC-DC, BMS, sensor, isolation-monitor and charger products a reference must carry, as a wishlist that turns into numbers as documents land.
- [x] **4.6 Bill of materials.** Packs and systems name their contactors, fuses, BMS and DC-DC through `contains`, so the graph traverses the whole battery system.
- [x] **4.7 Page and API for components.** Component kinds in the Compare filter with their own column set, a component sheet, and a components endpoint.

## 5. Every chemistry

- [x] **5.1 Chemistry family and construction.** A `family` on the chemistry block: lithium-ion, lithium metal, lithium primary, sodium-ion, sodium-sulfur, sodium-nickel-chloride, lead-acid, nickel-metal-hydride, nickel-cadmium, nickel-zinc, zinc-air, alkaline, silver oxide, flow vanadium, flow zinc-bromine, flow iron, solid state, supercapacitor. A `construction` for lead-acid: flooded, AGM, gel, tubular plate, flat plate, bipolar, carbon-enhanced.
- [x] **5.2 Lead-acid quantities.** Cold cranking current with temperature, duration, cutoff and the standard it follows; reserve capacity with its load and cutoff; float and cycle charge voltages with temperature; temperature compensation coefficient; design life on float at temperature; capacity at the 20-hour, 10-hour and 5-hour rates as separate observations.
- [x] **5.3 Lead-acid and AGM coverage list.** Automotive, motive-power, stationary and UPS ranges from the makers a reference must carry.
- [x] **5.4 Sodium coverage list.** Sodium-ion cells and packs from the makers shipping or sampling them, plus sodium-sulfur and sodium-nickel-chloride stationary products.
- [x] **5.5 Nickel, zinc, flow and supercapacitor coverage lists.** NiMH and NiCd cells and packs, nickel-zinc, zinc-air, flow batteries by electrolyte, and supercapacitor cells and modules.
- [x] **5.6 Conventions for the new chemistries.** The places these chemistries disagree with each other and with lithium practice, written into `docs/02-conventions.md` and enforced as required conditions.

## 6. Ontology and knowledge graph

The relational store is the source of truth; the graph and the semantic
export are derived from it. Compatibility means three things: every quantity
and unit resolves to a published IRI, every record can be emitted as RDF that
a triple store or a knowledge graph loads unchanged, and the graph projection
covers the whole scope above, components and applications included.

- [x] **6.1 EMMO and BattINFO bindings, generated.** `tools/sync_vocabularies.py` pulls the EMMO domain-battery and domain-electrochemistry ontologies, checks in their label-to-IRI tables with the commit they came from, and binds `quantity.emmo_iri` from a curated label map instead of hand-copied IRIs.
- [x] **6.2 QUDT bindings, verified.** Every quantity carries a QUDT quantity-kind IRI and every unit a QUDT unit IRI, checked against the QUDT vocabulary rather than typed.
- [x] **6.3 RDF export.** The accepted library as JSON-LD and Turtle: products and revisions as schema.org and BattINFO classes, observations as SOSA observations with QUDT quantity values, conditions as typed properties, provenance as PROV-O, all deterministic and checked in CI.
- [x] **6.4 Graph projection covers the whole scope.** Nodes and edges for applications, components inside packs, datasets and models, with a Neo4j and Apache AGE export.
- [x] **6.5 Alignment document.** One table per external vocabulary saying which class or property each concept here maps to, and where the mapping is only approximate.

## 7. Upstream, distribution and market

A cell's datasheet says nothing about where its lithium was mined, which
refinery turned it into hydroxide, which factory built the cell, who
distributes it, or what the market paid for any of that. Those are the
questions a buyer, an investor or a regulator asks first. The same rule
applies: a resource estimate without its reporting code and cut-off grade, a
capacity without whether it is nameplate or actual, a price without its
basis, region and period, is not a fact.

- [x] **7.1 Sites.** Mines, refineries, chemical and cathode plants, cell and pack factories, recyclers and distribution centres as first-class entities with operator, country, coordinates, status and what they produce.
- [x] **7.2 Resources and reserves.** Tonnage, grade, cut-off grade, contained metal, category and the reporting code they were declared under, dated.
- [x] **7.3 Capacity and output.** Nameplate, planned and actual capacity and production per site and period, in the unit the source states.
- [x] **7.4 Ownership and supply agreements.** Who owns what share of which site, and who has agreed to sell what to whom, for how long.
- [x] **7.5 Prices.** Commodity price series with basis, market, grade and period, and cell and pack price indices, from sources whose licence allows redistribution; licensed assessments are recorded as sources to join, never copied.
- [x] **7.6 Market volumes.** Production, shipments, installations and sales by maker, region, segment and chemistry family, per period.
- [x] **7.7 Trade flows.** Imports and exports by reporter, partner, HS code and period.
- [x] **7.8 Distribution.** Distributors, the makers they are authorised for, the regions they serve, and the listings already carried as offers.
- [x] **7.9 Contribution formats, validators and loaders** for sites and market series, with the same locator-per-claim discipline.
- [x] **7.10 Coverage list** for mines, refineries, factories, recyclers, distributors and open statistical sources.
- [x] **7.11 Views, graph and RDF** for the new layer: sites as places, ownership and supply as edges, prices and volumes as queryable series.

## 8. One API for every layer

- [x] **8.1 A resource registry.** Every queryable view registered once, with its field map derived from the database rather than typed, so a new view is queryable the day it exists.
- [x] **8.2 One grammar, one envelope.** `/v1/{resource}` and `/v1/{resource}/{id}` for every registered resource, with the OPTIMADE-style filter, sort, pagination and field selection the cells endpoint already has.
- [x] **8.3 A query endpoint and a graph endpoint.** `POST /v1/query` taking a resource, filter, fields, sort and limit as JSON; `/v1/graph/reachable` for multi-hop questions; provenance carried on every row that has it.
- [x] **8.4 OpenAPI.** `/v1/openapi.json` generated from the registry so clients and agents discover every resource and field.
- [x] **8.5 Documentation.** `docs/12-market-and-supply-chain.md` and `docs/13-api.md`.

## 9. A structure people can follow

The owner's brief: chemistry, patents, companies and the parts of the supply
chain are all here, and a reader must not have to guess how they fit. The
structure has to be data, documented once, and served the same way.

- [x] **9.1 The map.** One document that says what the layers are, where each layer's data lives, how it gets in and how it comes out, mirrored at the top of the README and in `GET /v1/info`.
- [x] **9.2 The supply chain as a vocabulary.** An ordered table of stages from mining to recycling that every site kind and every organisation role belongs to, read by the views, the graph and the API rather than typed twice.
- [x] **9.3 Companies as a layer.** A profile format with roles, identifiers and dated relations, one uid per company, names resolved against aliases before a new uid is minted.
- [x] **9.4 Patents wired in.** The reviewed end of the patent pipeline as a contribution format, with views, API resources, graph and RDF.
- [x] **9.5 Test centres and recycling centres.** Laboratories, certification bodies, research facilities, collection points, second-life facilities and recyclers as site kinds and roles with their own stages, on the coverage list.
- [x] **9.6 One gate per layer.** A validator that tells a file's layer from its shape and refuses one in the wrong directory, a loader for every layer, fictional examples that CI validates and loads, and tests that keep the offline vocabularies equal to the SQL.

## Log

Entries are appended as items are ticked, newest last.
- 2026-09-03 · **1.1** · The Report header now states that every figure traces to a contribution and counts derived figures and issue-rebuilt records; density columns carry a stated-or-derived basis column; the source pill shows datasheet, maker web page or rebuilt-from-issue instead of a blanket 'datasheet'.
- 2026-09-03 · **1.2** · capacity_key() in tools/build_web_data.py: a stated rate beats an unstated one, the lowest stated rate wins, ties break standard > typical > rated. The winning rate is printed in the 'Ah at' column and the full basis is the hover text.
- 2026-09-03 · **1.3** · Fields present out of the twelve bd.v_completeness tracks, the missing list, and the count of unstated conditions, on the Compare table, the Report (new Completeness section, Markdown and CSV) and as a 'most complete record' leader.
- 2026-09-03 · **1.5** · The LG INR21700-M50LT, EVE LF280K and Energizer E91 reference cells are now contributions under contrib/cells/, with the seed's table-level locators declared as such in source.note. tools/load_contrib.py recognises an observation or curve the library already holds under the same revision, statistic, value, unit and conditions and records the restatement instead of doubling it, which also removed the doubled Samsung 50E rows; it now loads curves, which it had silently dropped.
- 2026-09-03 · **1.6** · Compare table and Report carry max continuous discharge at its temperature, DC and AC resistance with pulse duration or frequency, cycle life with DoD, rate and temperature, the operating window and the standard charge current; bd.v_cell_selection and the /v1/cells filter grammar expose the same columns (discharge_temp_max_c, max_cont_charge_a, standard_charge_a, charge/discharge cutoffs, dcir_* with pulse duration, acir_* with frequency, cycle_life_* with its conditions).
- 2026-09-03 · **6.1** · tools/sync_vocabularies.py fetches the inferred EMMO domain-battery ontology (import closure: battery, electrochemistry, chemical substance, EMMO core), indexes 4575 classes by prefLabel into vocab/emmo-index.json with label collisions resolved deterministically and kept visible, and resolves the labels curated in vocab/bindings.json into schema/175_vocabulary_bindings.sql and json-schema/quantity-iris.json. 76 quantities carry an EMMO IRI; capacity and energy also bind per statistic (NominalCapacity, RatedCapacity, TypicalCapacity, MinimumCapacity, MaximumCapacity, NominalEnergy, RatedEnergy); product kinds, form factors, chemistry families and designations bind to their classes. bd.quantity_mapping holds 113 verified EMMO rows and the crosswalk is regenerated from them. CI runs the check.
- 2026-09-03 · **6.2** · bd.quantity.qudt_quantity_kind and bd.unit.qudt_iri, bound for 96 quantities and 57 units from the QUDT vocabularies indexed in vocab/qudt-index.json; the four terms QUDT lacks (entropic coefficient, dV/dQ, milliwatt-hour, millivolt per kelvin) are recorded as null rather than guessed.
- 2026-09-03 · **3.1** · All 372 pending candidates promoted with tools/promote_candidates.py, the bulk form of the approval box, on the owner's instruction to accept the queue wholesale. The library is now 457 products (162 cells, 219 primary cells, 61 packs, 27 modules, 21 systems) and loads into the database with 2630 contributed observations and the query tests passing. Seven files carried a C-rate with no reference capacity, which the database refuses; they now declare the reference unstated, and both validators enforce the rule so the offline gate and the database agree. The 372 GitHub issues stay open: closing them is the approve workflow's job on merge, or the owner's.
- 2026-09-03 · **4.1** · product.component_kind (33 kinds from contactor to thermal interface material) in the schema, the contribution format (required when kind is component) and the loader; documented in docs/10-components-and-chemistries.md.
- 2026-09-03 · **4.2** · 21 switching and protection quantities in schema/131_component_quantities.sql with their required conditions: breaking capacity needs circuit_voltage_v and time_constant_ms (both new condition_set columns), rated current its ambient, contact resistance its test current, endurance its switched load. Units kA, A2s, ms, us, MΩ, kΩ and operations added.
- 2026-09-03 · **4.3** · Input and output voltage windows, output current at ambient, conversion efficiency at a stated input voltage and load (rate_unit pct for a load as a fraction of rating), switching frequency, measurement range and accuracy, balancing current. Plus max_pulse_charge_current, whose absence had been silently dropping the CATL charge derating curves, and short_circuit_current.
- 2026-09-03 · **5.1** · chemistry.family (22 families) and chemistry.construction (lead-acid: flooded, AGM, gel, tubular, flat, bipolar, carbon-enhanced) in schema, format and loader, with a CHECK that construction only appears on lead-acid; both bound to their EMMO classes.
- 2026-09-03 · **5.2** · cold_cranking_current (temperature, duration, cutoff required; standard in extra), reserve_capacity_minutes (load, cutoff, temperature), float and cycle charge voltages (temperature), temperature compensation coefficient; capacity at the 20-, 10- and 5-hour rates as separate observations.
- 2026-09-03 · **5.6** · docs/02-conventions.md sections 28 to 33: DC breaking capacity and the circuit it was broken in, fuse ratings as derating curves, contact resistance at its test current, converter efficiency as a surface, four different cold-cranking tests, lead-acid capacity per rate and float against cycle voltage.
- 2026-09-03 · **1.4** · web/data/coverage.json carries uids for every target the library already holds, the Toshiba SCiB cells and the reference cells included; the Coverage page now counts 56 of 227 targets sourced across 27 segments.
- 2026-09-03 · **4.5** · Eight component segments on the coverage list: contactors and relays, fuses and pyro-fuses, DC-DC converters and chargers, BMS and disconnect units, sensors and isolation monitors, busbars and cell contact systems, thermal management, connectors and service disconnects. Names only until a document lands.
- 2026-09-03 · **5.3** · Sixteen lead-acid and AGM targets across automotive, motive power, stationary and UPS ranges.
- 2026-09-03 · **5.4** · Sodium-ion targets with three already sourced (CATL gen 1, CATL Naxtra, Hithium N162Ah), plus sodium-sulfur and sodium-nickel-chloride.
- 2026-09-03 · **5.5** · Nickel and zinc, flow battery and supercapacitor segments on the coverage list.
- 2026-09-03 · **2.9** · Format and loader: product.lifecycle, aliases, iec/ansi designations, equivalences with drop_in, rebadge, second_source, successor and predecessor relations, each with its evidence. Filling chemistry, form factor and lifecycle on the 457 existing records needs their documents (see the log under 2.13).
- 2026-09-03 · **2.10** · certifications (standard, scope, status defaulting to claimed, certificate number, body, dates) and transport (UN number, packing instruction, Wh rating, lithium content, transport SOC) in the contribution format and loader, into bd.certification and bd.transport_classification with provenance. Values follow when documents are re-extracted.
- 2026-09-03 · **3.6** · offers as a price time series (seller, region, currency, price, MOQ, lead time, grade, observed_at) into bd.product_offer, lifecycle status on the product, equivalences into bd.product_equivalence; the validator refuses a duplicate seller/region/date and an equivalence to a product outside the library.
- 2026-09-03 · **3.7** · contains in the contribution format: child uid, quantity, series and parallel counts, topology, evidence. The validator refuses a child not in the library; the loader applies links after every file has loaded, so a pack may name a cell later in the run. Toshiba's catalogue and BYD's datasheet name module counts but not the cell part numbers, so no link is asserted yet.
- 2026-09-03 · **4.6** · The same contains block carries contactors, fuses, BMS and converters once their records exist; product_assembly accepts any product kind and the CONTAINS edge is what bd_graph.reachable() walks.
- 2026-09-03 · **3.9** · Five published DFN parameter sets imported from PyBaMM at tag v24.1 with tools/import_pybamm_parameters.py: Chen 2020, O'Regan 2022 and O'Kane 2022 for the LG INR21700-M50, Marquis 2019 for the Kokam SLPB78205130H, Ecker 2015 for the Kokam SLPB 75106100. Each carries the article it transcribes (DOI from PyBaMM's own CITATIONS.bib), the file URL, tag and sha256, function-valued parameters as source code, and lands in bd.model_parameterisation through tools/load_models.py, which CI runs. The three cells enter the library with the capacity and cut-offs the sets state, quoting the file line. An ECM surface still needs a source with a fitted table.
- 2026-09-03 · **6.3** · tools/export_rdf.py writes rdf/battery-data.ttl from contrib/ (JSON-LD with --jsonld): products as schema:Product and their EMMO kind, form factor, family and designation classes; revisions as BatteryCellSpecification and prov:Entity; every value as a sosa:Observation with the EMMO observed property (per statistic where EMMO has one), a qudt:QuantityValue with verified unit and quantity kind, a bdv:ConditionSet with declared absence, and PROV-O provenance down to page and quote. 460 products, 2666 observations, about 65,000 triples, deterministic and CI-checked; parsed and queried with SPARQL as a test.
- 2026-09-03 · **6.4** · bd_graph gains Application nodes with FIELDED_IN edges at the source's granularity, Certification nodes with HOLDS_CERTIFICATION and CERTIFIED_TO, OFFERED_BY edges carrying price and date, component_kind on products and chemistry family and construction on revisions. tools/export_graph.py writes Neo4j CSVs and a Cypher loader; tools/load_age.py populates Apache AGE when installed. CI runs both.
- 2026-09-03 · **6.5** · docs/11-ontology.md: which vocabulary carries what (schema.org, EMMO/BattINFO, SOSA, QUDT, PROV-O), where the mapping is broader or approximate, the graph projection's labels and edges, and a SPARQL query as proof.
- 2026-09-03 · **2.1 to 2.8, 2.11, 2.12** · Blocked here: the network egress policy blocks every manufacturer, distributor and archive domain, so no datasheet could be read. The format, validator, loader, page and RDF export accept every one of these fields today. review/hygiene.json carries the re-extraction manifest: one command per record, 441 records, to run with `tools/extract_datasheet.py` from a machine with network access and an Anthropic API key, or one product at a time through the submit-datasheet workflow. Curves (2.11) and fielded applications (2.12) come from the same documents.
- 2026-09-03 · **2.13** · The hygiene rules are enforced and reported: a C-rate needs its reference, a curve axis must be a registry quantity, and review/hygiene.json (CI-checked) lists per record whether it was rebuilt from issue text, lacks a hash, date, revision, page numbers or statistic labels. The values themselves need the re-extraction above.
- 2026-09-03 · **3.2, 3.3** · 56 of 227 coverage targets are sourced after the queue promotion (Molicel P26A to P50B, Murata VTC5A and VTC6, BAK, EVE LF304, Hithium 314Ah and N162Ah, CATL Naxtra and sodium-ion, BYD Battery-Box, LG RESU, CATL TENER, CNTE). The remaining 171 targets, and every lead-acid, nickel, zinc, flow and supercapacitor product, need their documents fetched; the coverage list is the work order.
- 2026-09-03 · **3.4** · datasets/registry.json exports the five registered open datasets with landing pages, citations and licence notes, and the offline demo of the ingestion pipeline runs (three vendor dialects, 270 cycles, 24 segments). The files themselves live on data.matr.io, ora.ox.ac.uk, nasa.gov and calce.umd.edu, all blocked from this session; `tools/ingest_open_dataset.py ingest <key> <dir>` is the command once they are downloaded.
- 2026-09-03 · **3.5, 3.8, 3.10** · Third-party tests, teardown chemistry, passport fields and second sources are documents to fetch; the format carries them (source kinds third_party_test and teardown_report, the passport quantities, a second source as a second contribution file for the same product, which the loader keeps as a second revision and the contradiction view compares).
- 2026-09-03 · **4.4** · Curve kinds time_current, derating and efficiency are documented in docs/10-components-and-chemistries.md and the loader stores any curve kind; the curves come with the component datasheets on the coverage list.
- 2026-09-03 · **4.7** · The Compare filter offers every product kind; with components selected the table, Report, CSV and Markdown switch to a component column set (rated voltage and current with its ambient, breaking capacity with circuit voltage and L/R, I²t, coil voltage and power, contact resistance at its test current, endurance, input and output windows, output current, efficiency at its load point) with an empty-state note pointing at the coverage list until the first component lands. bd.v_component_selection and GET /v1/components (with /v1/components/{uid} detail carrying every observation) expose the same figures through the OPTIMADE-style filter grammar, which now takes a field map so a cell field is refused on a component query.
- 2026-09-04 · **7.1** · bd.site in schema/185_supply_chain.sql: twenty kinds from mine and brine operation through refinery, precursor, cathode, anode, electrolyte and separator plants, cell, module and component factories, test laboratories and research facilities, second-life facilities, collection points and recycling plants, to distribution centres and ports; operator, country, coordinates, status with its date, commodities and products; every kind but other on a stage of the map. contrib/sites/<operator>/<site>.yaml is the format, bd.v_site and /v1/sites the query surfaces, schema:Place with geo coordinates in the RDF export, a Site node with OPERATES and OWNS edges in the graph.
- 2026-09-04 · **7.2** · bd.resource_estimate: commodity, category (measured to total_reserve), reporting code, tonnage, grade, cut-off grade, contained metal, each with its unit, dated, with unstated[] for declared absence. The database refuses a row without a reporting code and a cut-off unless they are declared unstated, and only a mine or a brine may carry one. /v1/resource_estimates.
- 2026-09-04 · **7.3** · bd.site_metric: capacity, production, throughput, recovery rate, capex, energy use, headcount, test channels and chambers, collection volume, per site and period in the unit the source states; a capacity or production row must say nameplate, planned, announced, under construction, actual or estimated. /v1/site_metrics.
- 2026-09-04 · **7.4** · bd.site_ownership with share, role and validity, and bd.supply_agreement with supplier, buyer, kind, subject, the site it draws on, traded form, volume, term and announcement date; OWNS, SUPPLIES and SUPPLIED_FROM edges; /v1/supply_agreements and a site's or a company's agreements under its detail.
- 2026-09-04 · **7.5** · bd.commodity_price (traded form, grade, basis, market, currency, per unit, period, provider) and bd.price_index (segment, chemistry family and designation, sector, region, per kWh, basis, period). The market format's source declares its licence and data_redistributable; the validator and the loader refuse every price, index and volume row when it is false, and the file lists the licensed feeds under providers as sources to join. /v1/commodity_prices, /v1/price_indices.
- 2026-09-04 · **7.6** · bd.market_volume: production, shipment, installation, sales, capacity, demand and inventory by maker, region, country, sector, chemistry family and designation, with share and rank, per period. /v1/market_volumes.
- 2026-09-04 · **7.7** · bd.trade_flow: reporter, partner, HS code, direction, period, value in USD and quantity with unit. /v1/trade_flows.
- 2026-09-04 · **7.8** · bd.distribution: distributor, manufacturer, status (authorized, franchised, independent, broker, marketplace), regions, product families, listing URL, validity; DISTRIBUTES edges; /v1/distributions; offers stay bd.product_offer rows carried by product files and are queryable as /v1/offers.
- 2026-09-04 · **7.9** · Four formats under json-schema/ (site, company, market, patent) with a locator on every claim; tools/validate_layers.py tells a file's layer from its shape, refuses one under the wrong directory, checks reporting codes, capacity status, ordered periods, uid pins, self-relations and the licence rule; tools/load_layers.py loads all four with provenance and replaces what a file asserted on reload. Fictional examples under docs/examples are validated by CI and loaded into a throwaway database to prove the path.
- 2026-09-04 · **7.10** · Eleven new segments on the coverage list, 500 targets in all: lithium mines and brines; nickel, cobalt, manganese and graphite mines; refineries and chemical plants; precursor, cathode and anode plants; cell, module and pack factories; component factories; test laboratories and certification bodies; recyclers, collection and second life; distributors and marketplaces; companies to profile; open statistical and patent sources with the licensed assessments marked join-never-copy. build_web_data counts a site, company or source uid as sourced the day its file lands.
- 2026-09-04 · **7.11** · Views for every table of the layer in schema/187_views_market.sql, each with source_uid, source_url, page and quote; Site nodes with stage, OPERATES, OWNS, SUPPLIES, SUPPLIED_FROM, DISTRIBUTES and company-relation edges in the graph projection (now schema/190_graph.sql); sites as schema:Place with geo coordinates, companies with relations, agreements, distribution, prices, volumes, trade and patents in tools/export_rdf.py, proven with SPARQL on the examples.
- 2026-09-04 · **8.1** · api/resources.py registers every queryable view once, grouped by layer in the order of the map, with its id column, default sort, related rows and examples; the field map is read from information_schema at first use (numbers filter as numbers, arrays with HAS, everything else against its text form, identifiers quoted), so a new column or view is queryable without code. tests/test_api_registry.py checks every view exists and every resource sits in exactly one layer.
- 2026-09-04 · **8.2** · GET /v1/{resource} and /v1/{resource}/{id} for all 33 resources with the OPTIMADE-style grammar (list fields take HAS and CONTAINS over their elements and refuse =), sort, field selection and paging; a detail carries its related rows (a cell its observations, curves, certifications, offers and parameter sets; a company its products, sites, agreements, distribution and relations; a site its estimates, metrics and agreements; a family its publications). /v1/info/{resource} is generated from the field map.
- 2026-09-04 · **8.3** · POST /v1/query takes resource, filter, fields, sort and paging as JSON; GET /v1/graph/reachable takes a uid, relationship types, depth and direction and walks bd_graph.reachable(). Every row that has a source carries source_uid, source_url, page and quote.
- 2026-09-04 · **8.4** · GET /v1/openapi.json: an OpenAPI 3.1 document with a path, a schema and a layer tag per resource, generated from the registry and the field maps; CI starts the server and checks every resource lists, the detail carries observations, the query and graph endpoints answer and the document is whole.
- 2026-09-04 · **8.5** · docs/12-market-and-supply-chain.md (sites, test laboratories, recyclers, resources, capacity, ownership, agreements, distribution, prices, volumes, trade, the licence rule, formats, queries) and docs/13-api.md (endpoints, resources by layer, the grammar and its field types, examples for every layer, how to add a resource); README rows and API section.
- 2026-09-04 · **9.1** · docs/00-map.md: the layers with where each one's data lives, how it gets in and how it comes out, the fourteen stages, one company one uid, what is refused at the door; the same table at the top of the README; GET /v1/info lists the layers and their resources in the same order; /v1/layers serves them.
- 2026-09-04 · **9.2** · bd.supply_chain_stage (14 stages, mining to collection and recycling) and bd.organization_role (28 roles, each on a stage or on none) in schema/184_companies.sql; bd.site_stage() and bd.organization_stages() read them; v_site, v_company, v_stage and the graph carry the stage; /v1/stages returns the map with counts. tests/test_layers.py keeps the JSON schema enums equal to the SQL.
- 2026-09-04 · **9.3** · contrib/companies/<slug>.yaml with legal name, aliases, former names, country and headquarters, founding year, website, roles, LEI, ROR, ticker, parent and dated relations (parent_of, subsidiary_of, joint_venture_of, brand_of, formerly, renamed_to, acquired, merged_into, spun_off_from, minority_stake_in, licensee_of) into bd.organization and bd.organization_relation; the loader and the RDF export resolve a name against existing names, legal names and aliases before minting a uid, proven on the examples where a mine's operator and the company file stay one uid. /v1/companies, /v1/company_relations.
- 2026-09-04 · **9.4** · contrib/patents/<docdb-family-id>.yaml takes a reviewed family with its publications, categories and links into bd.patent_family, patent_publication, patent_classification and patent_entity_link as accepted rows with provenance, the only path in; views v_patent_family, v_patent and v_patent_category; /v1/patent_families, /v1/patents, /v1/patent_categories; bdv:PatentFamily and bdv:PatentPublication in RDF; docs/08-patents.md says so. The CORDIS staging import still promotes nothing and CI still checks it.
- 2026-09-04 · **9.5** · test_laboratory and research_facility (stage: testing, certification and research), second_life_facility (second life), collection_point and recycling_plant (collection and recycling) as site kinds with lab, certification_body, research_institute, second_life and recycler as roles; a laboratory's services are its products and its channels and chambers its metrics; a recycler's capacity must say nameplate or actual and its recovery rate is per element. Examples under docs/examples, 45 laboratories, recyclers and second-life targets on the coverage list.
- 2026-09-04 · **9.6** · tools/validate_layers.py and tools/load_layers.py cover sites, companies, market and patents by the file's shape; tools/validate_contrib.py and tools/load_contrib.py read contrib/cells only and skip anything else with a pointer; docs/examples holds a fictional file per layer that CI validates and loads into a throwaway database; tests/test_layers.py and tests/test_api_registry.py run without a database.
