# Crosswalk to existing standards

Four vocabularies describe overlapping parts of the battery data landscape and
**no published crosswalk connects them**. Producing one is itself a defensible
artefact, and it is what the graph projection is for.

| Standard | Owner | Covers | Status |
|---|---|---|---|
| **BDF** (Battery Data Format) | LF Energy Battery Data Alliance | Cycler time-series columns | Live, Dec 2025. Credible and backed. |
| **BattINFO / EMMO domain-battery** | BIG-MAP / EMMO | Vocabulary IRIs for cells, tests, models | Mature-ish, annotated "unstable", thin adoption |
| **BPX** | Faraday Institution | Physics model parameters (DFN/SPM/SPMe) | Live, adopted by PyBaMM. **No ECM support.** |
| **BatteryPassDataModel** | batterypass / DIN DKE SPEC 99100 | EU Regulation 2023/1542 passport fields | Live, mandatory from 18 Feb 2027 |
| **OPTIMADE** | Materials Consortia | Materials federation + API conventions | v1.3.0, 21 providers, zero battery-specific |

## How this schema binds to each

Bindings live in the `bd.quantity` table as columns, so the crosswalk is
generated from data rather than hand-maintained in prose:

```sql
SELECT code, si_unit, bdf_name, emmo_iri, bpx_key, battery_pass_path
  FROM bd.quantity WHERE bdf_name IS NOT NULL;
```

### BDF — adopted verbatim

`bd.timeseries_record` uses BDF machine names as its own column names:
`test_time_second`, `voltage_volt`, `current_ampere` (required);
`unix_time_second`, `cycle_count`, `step_count`, `ambient_temperature_celsius`
(recommended); plus the ~51 optional columns.

Consequence: every column gets an RDF predicate for free under
`https://w3id.org/battery-data-alliance/ontology/battery-data-format#`, and BDF
files round-trip losslessly. The one thing NOT adopted is BDF's implicit sign
convention — see `docs/02-conventions.md` §1.

**The opening:** the Battery Data Alliance has stated that a *parallel metadata
format* is their immediate next deliverable. It does not exist yet. That layer
is what `bd.product`, `bd.product_revision`, `bd.condition_set` and
`bd.protocol` are. The right move is to contribute this upstream rather than
compete with it.

### BattINFO / EMMO — vocabulary, not table structure

Class IRIs are opaque UUIDs (`BatteryCell` =
`battery_68ed592a_7924_45d0_a108_94d6275d57f0`); human labels live in
`skos:prefLabel`. `tools/sync_vocabularies.py` parses `battery.ttl` and
`electrochemistry.ttl` at build time and populates `quantity.emmo_iri`.

Do NOT hand-copy IRIs from documentation — generate them.

EMMO's `hasDescription` / `isDescriptionFor` relation encodes exactly this
schema's `product_revision` ↔ `product_unit` split, and BattINFO's
`CellSpec → Cell → Test → Dataset` chain maps onto
`product_revision → product_unit → test_run → dataset`.

### BPX — stored verbatim, not translated

`model_parameterisation.payload` holds the BPX JSON document unmodified for
`bpx_*` kinds, so a row round-trips through `pip install bpx` and
`pybamm.ParameterValues.create_from_bpx()`.

BPX carries a validation dataset inline; this schema instead foreign-keys
`validation_run_id` to a real test run, so validation data is not duplicated.

**The gap BPX leaves:** it is explicitly physics-model-only. There is **no ECM
standard at all** — practice is NREL `thevenin` structs, `impedance.py` circuit
strings, and MATLAB/Simscape blobs. `bd.ecm_parameter_point` fills that: R₀ and
RC branches as a lookup surface over (SOC, temperature, direction, pulse
duration), with mandatory fit provenance. This is a genuine, unoccupied,
low-cost win.

### EU Battery Passport — passport-ready from day one

Two things are cheap now and expensive to retrofit:

1. `product_unit.battery_status` ∈ original | reused | repurposed |
   remanufactured | waste, and `product_unit.passport_id`
2. `access_tier` on every fact-bearing table, per Article 77(2):
   public / legitimate_interest / authority_only / restricted

Performance fields required by Annex XIII map onto existing quantities:
rated capacity, energy, usable energy, nominal/min/max voltage, power capability
at 20 °C **and at −10 °C** (which is why current limits are a temperature-banded
surface, §26), round-trip efficiency at 50% SOC, internal resistance,
electrochemical impedance, expected lifetime in cycles and years, temperature
operating range, SOH, capacity and power fade.

### OPTIMADE — copy the conventions, federate the content

Worth copying for the public API: versioned `/v1` base URL, JSON:API envelope
with `meta.data_returned` and `more_data_available`, a formal filter grammar
(`HAS ALL`, `IS KNOWN`, `CONTAINS`), a `/links` federation endpoint, and the
`_providerprefix_field` vendor-extension convention.

Not worth doing: extending OPTIMADE's entry types to cells. Its schema is
crystal-structure-shaped. `material.optimade_ids` resolves to `mp-…` / `oqmd-…`
instead of re-hosting structures.

## Standards referenced but never redistributed

IEC, ISO, SAE and GB/T texts are paywalled (IEC 61960-3 is ~CHF 300). `bd.standard`
stores the citation — SDO, number, part, edition, year, title, URL — and
`bd.protocol` stores *our own recorded conditions*. Redistributing their tables
would be infringement; citing them is not.

The USABC/DOE test manuals (INL) are the exception: free, public, and the source
of most public datasets' protocols. They are the ones to implement in full.
