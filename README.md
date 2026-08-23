# battery-data

An open, provenance-first database of battery specifications, performance data,
and test conditions — collected from datasheets, scientific literature, and raw
cycler files.

**Design premise:** roughly 40% of what a battery datasheet calls a
"specification" is not an attribute of the product. It is a measurement result
under conditions the datasheet may or may not disclose. Every existing open
battery dataset stores those as plain columns, which silently destroys the
conditions and makes rows non-comparable. This project stores the conditions.

```sql
-- The same cell. The same page of the same datasheet. Both numbers are true.
SELECT model_number, statistic, value_native||' '||unit_native AS capacity,
       rate_value||' '||rate_unit AS rate, voltage_lower_v AS cutoff
  FROM bd.v_observation
 WHERE quantity='capacity' AND model_number='INR21700-50E';

 model_number | statistic | capacity | rate  | cutoff
--------------+-----------+----------+-------+--------
 INR21700-50E | standard  | 4900 mAh | 0.2 C |    2.5
 INR21700-50E | rated     | 4753 mAh | 1 C   |    2.5
```

A schema with a `capacity_mah REAL` column keeps one of those and loses the
other, without telling anyone.

---

## Why this exists

There is a real gap, and it is narrower and more specific than "a comprehensive
battery database". As of mid-2026:

- **Time-series cycling data is solved.** The LF Energy Battery Data Alliance
  published the [Battery Data Format (BDF)](https://github.com/battery-data-alliance/battery-data-format)
  in December 2025 — a credible, well-backed, cross-vendor standard with a
  resolvable ontology IRI per column. Re-inventing it would be wasted work.
  **This project adopts BDF verbatim** for raw records.

- **The materials layer is solved.** Materials Project, OQMD, AFLOW and NOMAD
  are well funded and OPTIMADE-federated. This project *federates* to them by
  ID rather than re-hosting crystal structures.

- **Cell specifications are not solved.** Every serious cell-spec database is a
  static Excel file or a paywalled subscription app. None has an API. None has
  stable per-cell identifiers. None tracks provenance to a datasheet PDF and
  revision. None versions a spec when the manufacturer revises it.

- **Nobody links the layers.** Datasheet spec → measured test data → fitted
  model parameters → regulatory passport fields are four disjoint vocabularies
  (BDF, BattINFO, BPX, BatteryPassDataModel) with **no published crosswalk**.

- **Test protocol is nowhere a first-class entity.** There is no identifier
  anywhere in the field for "IEC 62660-1:2018 §7.2 capacity test at 23 °C, 1 It"
  that you can foreign-key to.

- **BDF has no metadata sibling — yet.** The Battery Data Alliance explicitly
  named a parallel metadata format as their immediate next deliverable. That is
  precisely this layer, and there is a path to contributing rather than competing.

The honest counterweight: **raw cycling data is not scarce** (BatteryArchive,
Zenodo and `awesome-battery-data` already index 7,500+ cells), and willingness
to pay for cell-spec data alone is demonstrably low — the most complete open
product sells for $15. The defensible value is in **linkage, freshness,
provenance, and API guarantees**, not in the rows.

---

## Architecture

**Postgres is the source of truth. The graph is a derived, rebuildable projection.**

The relational core wins on what this database is mostly for: numeric range
filtering, unit enforcement, condition constraints, bulk analytics, and refusing
malformed data at the door. A property graph is weak at all of those.

But a graph wins decisively where join depth is unbounded: *which pack products
transitively contain a cell whose cathode uses material from supplier X*, or
*what is the shortest provenance path from this published figure to a raw cycler
file*. So both exist, and nothing is stored only in the graph.

```
                    ┌──────────────────────────────────────┐
  datasheets ──┐    │            POSTGRES (bd)             │
  papers ──────┼───►│  source of truth, strict constraints │
  cycler files─┤    │                                      │
  contrib PRs ─┘    │  product ─ product_revision ─ unit   │
       │            │      │            │            │     │
       ▼            │      │      observation ── condition_set
  bd_stage          │      │       curve      │            │
  review queue ────►│      └─ assembly     test_run ─ segment
  (nothing enters   │                          │            │
   bd.* unreviewed) │                    dataset (BDF) / eis│
                    └───────────────┬──────────────────────┘
                                    │ derived, rebuildable
                    ┌───────────────▼──────────────────────┐
                    │  bd_graph  node / edge / reachable() │
                    │  → Apache AGE  or  → Neo4j export    │
                    └──────────────────────────────────────┘
```

### The three-level identity split

```
product           the thing the market calls "INR21700-50E"
product_revision  one specification document's account of it
product_unit      a physical object with a serial number
```

This is not over-engineering. Tesla publishes different Powerwall 3 numbers for
AU, UK, IE and MT. The Samsung 50E exists at V0.2, V1.0, and a customer-scoped
"Tentative" issue. The LG M50LT datasheet is stamped *"this document is NOT the
final version"*. Keying specs on the model number overwrites all of that, and
the EU battery passport legally requires instance-level identity anyway.

---

## Quick start

```bash
./setup.sh
```

That creates the database, loads the schema and the example cells, runs every
test, and reports what worked. Safe to run twice. `./setup.sh --api` also starts
the read API.

No Postgres installed and would rather keep it that way:

```bash
docker compose up      # database + API, nothing installed on your machine
```

New to the repo? **[`START-HERE.md`](START-HERE.md)** is the one-page version.

<details>
<summary>Manual setup</summary>

```bash
createdb batterydb
./tools/build_db.sh batterydb          # 67 tables, 10 views, 98 quantities
psql -d batterydb -f seed/001_reference_cells.sql
python tools/load_contrib.py --dsn dbname=batterydb   # accepted contributions
psql -d batterydb -f tests/010_killer_queries.sql
```
</details>

Engineering selection:

```sql
SELECT manufacturer, model_number, chemistry,
       capacity_low_rate_ah, capacity_1c_ah, max_cont_discharge_a
  FROM bd.v_cell_selection
 WHERE form_factor_code='21700'
   AND capacity_low_rate_ah >= 4.5
   AND max_cont_discharge_a >= 9;
```

Multi-hop traversal, no graph extension required:

```sql
SELECT * FROM bd_graph.reachable('rev:3', ARRAY['CONTAINS'], 6, 'in');
```

---

## What the schema refuses to accept

The database rejects data that cannot be interpreted. This is the core feature,
not a limitation.

```sql
INSERT INTO bd.observation (product_revision_id, quantity_id, value_native,
                            unit_native, provenance_id)
SELECT pr.id, q.id, 15, 'mohm', pv.id ...
WHERE q.code='internal_resistance_ac';

ERROR:  quantity "internal_resistance_ac" is uninterpretable without
        condition(s): frequency_hz, soc_pct, temperature_c
HINT:   Supply the condition, or - if the SOURCE genuinely does not state it -
        list the column name in condition_set.unstated. That records the
        omission as a fact about the document instead of hiding it as a NULL.
```

That rule exists because the LG M50LT datasheet lists **15 mΩ** (AC, 1 kHz) and
**23 mΩ** (DC, 10 s pulse) for the same cell — 53% apart — and Energizer states
the L91's resistance as *"120 to 240 milliohms (depending on method)"*.

`condition_set.unstated` is the third state between "recorded" and "missing":
Samsung publishes a 14,700 mA pulse rating and **never gives a duration**. That
omission is a fact about the datasheet worth storing, and a NULL cannot express it.

---

## Documentation

| Doc | Contents |
|---|---|
| [`docs/01-architecture.md`](docs/01-architecture.md) | Relational vs graph, the identity split, storage strategy |
| [`docs/02-conventions.md`](docs/02-conventions.md) | **The 27 places the field genuinely disagrees**, and what this schema does about each |
| [`docs/03-crosswalk.md`](docs/03-crosswalk.md) | Mapping to BDF, BattINFO/EMMO, BPX, EU Battery Passport, OPTIMADE |
| [`docs/04-ingestion.md`](docs/04-ingestion.md) | Pipelines, review queue, contribution format |
| [`docs/05-data-sources.md`](docs/05-data-sources.md) | Sources credited but not reproduced, and the bulk cycling datasets |
| [`docs/06-submitting-a-datasheet.md`](docs/06-submitting-a-datasheet.md) | **Upload a PDF, review what was extracted, accept or reject** |
| [`docs/07-candidate-review.md`](docs/07-candidate-review.md) | Owner-only issue checkbox → validated accepted library |
| [`agents/literature-miner/AGENT.md`](agents/literature-miner/AGENT.md) | The papers → data agent |
| [`LICENSING.md`](LICENSING.md) | **What is open, what is sold, and why the line sits where it does** |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | The contribution licence, and what contributors get back |
| [`PILOT.md`](PILOT.md) | **Free design-partner access to the full corpus — the current phase** |
| [`TERMS.md`](TERMS.md) | API subscription terms, for when the service is sold |
| [`PRIVACY.md`](PRIVACY.md) | What is logged, why, and for how long |

---

## Scope

| Level | Covered |
|---|---|
| **Cells** | Cylindrical (18650/21700/4680/26650/32700/46xx), pouch, prismatic, coin |
| **Modules / packs / systems** | EV packs, home ESS, grid BESS containers, tool and drone packs |
| **Consumer & primary** | Alkaline, Li-SOCl₂, Li-MnO₂, Li-FeS₂, button cells, NiMH |
| **Materials** | Cathode/anode/electrolyte/separator, suppliers, federated to OPTIMADE |
| **Test data** | Capacity/RPT, HPPC, EIS+DRT, cycle life, calendar aging, OCV/GITT/PITT, ICA/DVA, HPC, self-discharge, formation, thermal (ARC, entropic, heat capacity, anisotropic conductivity), abuse and vent gas, mechanical swelling, drive cycles, three-electrode, post-mortem |
| **Models** | BPX (DFN/SPM/SPMe) stored verbatim; ECM as an (SOC, T) lookup surface with fit provenance |

---

## Components

| Path | What it is |
|---|---|
| `schema/` | 67 tables, 10 views, 98-quantity registry. Loads on stock Postgres 16 |
| `tools/cyclers.py` | Arbin / Maccor / Neware / BioLogic / BDF adapters. **Determines conventions from the data** rather than assuming them, and recovers the `[aging, RPT, aging, RPT]` structure automatically |
| `api/` | Read API on OPTIMADE conventions, with an OPTIMADE-style filter grammar |
| `agents/literature-miner/` | Papers and datasets → structured records with provenance |
| `crosswalk/` | Generated BDF ↔ EMMO ↔ BPX ↔ Battery Passport mapping |
| `tools/validate_contrib.py` | CI gate: refuses a contribution whose values lack their conditions |
| `tools/check_duplicates.py` | Cross-library identity gate for exact UIDs, normalized model aliases, and specification conflicts |

### The query no other battery schema can express

```sql
-- Capacity fade measured on REFERENCE PERFORMANCE TESTS only, not on the
-- aging cycles. Every aging campaign has this structure; no other schema
-- records which cycles were which, which is why the literature is
-- perennially unclear about what a plotted capacity actually came from.
SELECT s.role, cs.cycle_index, cs.discharge_capacity_ah
  FROM bd.cycle_summary cs
  JOIN bd.test_segment s
    ON s.test_run_id = cs.test_run_id
   AND cs.cycle_index BETWEEN s.start_cycle AND s.end_cycle
 WHERE s.role IN ('baseline_rpt','periodic_rpt','final_rpt');
```

### Ingesting a cycler file

```bash
python tools/cyclers.py sniff  data/raw/cell_A.csv     # identify the format
python tools/cyclers.py ingest data/raw/cell_A.csv \
    --unit unit/lab/50E-001 --provenance 5 --c-rate-ref-ah 4.9
```

Conventions are detected, not assumed — current sign is inferred from whether
capacity accumulates while current is positive, cross-checked against the
instrument's own step-type labels. Where it cannot be determined, the run is
flagged rather than silently defaulted.

### API

```bash
python api/server.py --port 8080
curl -G localhost:8080/v1/cells \
     --data-urlencode 'filter=capacity_ah >= 4.5 AND form_factor_code = "21700"'
```

Cell detail responses carry the observations they were derived from, each with
its conditions and a page-level citation. An API that dropped provenance would
undo the point of the schema.

## Status

Schema, query layer, graph projection, staging/review, cycler adapters, read API,
literature-miner and the standards crosswalk are complete and tested. Seeded with
four reference cells chosen because each breaks a naive schema differently.

Next: wire the literature-miner to a model provider, EIS/`.mpr` binary parsing,
and propose the metadata layer upstream to the Battery Data Alliance.

## Licence

Two licences and one boundary. The full account, with the reasoning, is in
**[`LICENSING.md`](LICENSING.md)**; the machine-readable version is
[`REUSE.toml`](REUSE.toml), and CI fails if a file is not covered by it.

| What | Licence |
|---|---|
| Code — `schema/` `tools/` `api/` `agents/` `tests/` | **AGPL-3.0-or-later** |
| Docs, crosswalk, and the published sample — `docs/` `crosswalk/` `json-schema/` `seed/` `contrib/` `review/` `web/` | **CC-BY-4.0** |
| The curated corpus and the hosted API | **not in this repository** — [`TERMS.md`](TERMS.md) |

**On the code.** Run a modified version as a service and the modifications are
owed back to whoever uses it. Querying the database, loading your own data, and
running it inside a business trigger nothing. Calling the hosted API from closed
commercial software triggers nothing either — the AGPL binds people who modify
and serve the program, not people who talk to a server someone else runs.

**On the data.** The sample published here is CC-BY-4.0 and that will not be
withdrawn; attribution is the only condition, and every row already carries the
provenance needed to give it. `crosswalk/` is deliberately the most permissive
thing in the repository — a standards mapping nobody may adopt is a mapping
nobody adopts.

**On the corpus.** The full curated corpus is not published here. It is served
by API under [`PILOT.md`](PILOT.md) — free design-partner access, which is the
current phase — and later by subscription under [`TERMS.md`](TERMS.md), which
is what funds the curation. That boundary is the commercial model, and it is drawn precisely in
`LICENSING.md` rather than left to be inferred.

The honest version of why it is arranged this way: a spec number off a datasheet
is a *fact*, and facts are not copyrightable. No data licence protects this
corpus. What protects it is a subscription contract, the EU/EEA database right
(asserted — see `LICENSING.md`), a machine-readable TDM reservation, and the
freshness a scraped copy does not have. A licence that claimed more would be a
bluff, and a bluff that gets tested is worse than no claim.

**Datasheets are not redistributed.** `source.redistributable` governs whether a
document body is stored, and every value keeps a URL, hash and retrieval date so
any takedown request is answerable. `source.license` records the terms each
source arrived under, which is not the same question as the terms this
repository ships under.

**This database is not a substitute for the manufacturer's controlled datasheet
and is not qualified for safety-critical design.** Verify before anything is
built, certified or shipped. The provenance exists so that you can.

The relicence from MIT applies going forward. Earlier commits were published
under MIT and those rights do not expire.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md). One thing to know before you start: your
contribution may be served through the paid API, you keep your copyright, and
contributors get free API access. §2 states exactly what you grant and §3 what
you get back — read them before you open a pull request rather than after.

Sign your commits off with `git commit -s`. That line carries both the
[DCO](DCO) and the contribution licence, and CI checks for it.
