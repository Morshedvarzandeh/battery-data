# battery-data standards crosswalk

Generated from `bd.v_crosswalk`. Do not edit by hand.

Four vocabularies describe overlapping parts of the battery data
landscape and no published crosswalk connects them. This is that
crosswalk. The `relation` column records mapping **fidelity**, which
is the part a naive mapping omits and the part that matters: an
`exact` mapping can be relied on for round-tripping, a `broader` one
cannot.

Rows marked `no_equivalent` are deliberate content, not omissions.

## Vocabularies

| Code | Name | Version | Licence |
|---|---|---|---|
| `bdf` | Battery Data Format | 1.2.0 | Apache-2.0 |
| `emmo_battery` | EMMO domain-battery | 0.20.0 | CC-BY-4.0 |
| `emmo_electrochemistry` | EMMO domain-electrochemistry | 0.34.0 | CC-BY-4.0 |
| `bpx` | Battery Parameter eXchange | 0.4 | Apache-2.0 |
| `battery_pass` | Battery Passport Data Model | 1.2.0 | MIT |
| `optimade` | OPTIMADE | 1.3.0 | CC-BY-4.0 |

**bdf** — Published Dec 2025 by the LF Energy Battery Data Alliance. Adopted verbatim for bd.timeseries_record column names. A parallel METADATA format has been announced but does not yet exist - that is the layer bd.product_revision, bd.condition_set and bd.protocol occupy.

**emmo_battery** — Annotated "unstable". Class IRIs are opaque UUIDs; human labels live in skos:prefLabel. Adoption outside EU projects is thin. Treat as the vocabulary of record, not a working data format.

**emmo_electrochemistry** — Carries the quantities and materials terms (~3000).

**bpx** — Physics models only - DFN/SPM/SPMe. No ECM schema and no published roadmap for one; bd.ecm_parameter_point fills that gap.

**battery_pass** — Aligned to DIN DKE SPEC 99100:2025-02. Mandatory under EU Reg 2023/1542 Art. 77 + Annex XIII from 18 Feb 2027.

**optimade** — API conventions worth copying; entry types are crystal-structure-shaped and should not be extended to cells. Federate materials by ID.


## battery_pass

| Quantity | SI unit | External term | Relation | Verified | Note |
|---|---|---|---|---|---|
| `capacity` | C | `io.BatteryPass.Performance#ratedCapacity` | close | yes | Annex XIII rated capacity. Legally required from 18 Feb 2027. |
| `carbon_footprint_per_kwh` | 1 | `io.BatteryPass.CarbonFootprint#carbonFootprintTotal` | exact | yes |  |
| `cycle_life` | 1 | `io.BatteryPass.Performance#expectedLifetimeCycles` | close | yes |  |
| `energy` | J | `io.BatteryPass.Performance#ratedEnergy` | close | yes |  |
| `internal_resistance_dc` | ohm | `io.BatteryPass.Performance#internalResistance` | broader | yes | The Regulation requires "internal resistance (ohms)" with NO method specified. Expect incomparable values across manufacturers unless the method is captured separately - which is what this schema does. |
| `mass` | kg | `io.BatteryPass.GeneralProductInformation#batteryWeight` | close | yes | Mass basis (with or without wrap, terminals, coolant) is unstated in the Regulation and varies between manufacturers. |
| `nominal_voltage` | V | `io.BatteryPass.Performance#nominalVoltage` | exact | yes |  |
| `recycled_content_cobalt` | 1 | `io.BatteryPass.MaterialComposition#recycledContentCobalt` | exact | yes |  |
| `recycled_content_lithium` | 1 | `io.BatteryPass.MaterialComposition#recycledContentLithium` | exact | yes |  |
| `recycled_content_nickel` | 1 | `io.BatteryPass.MaterialComposition#recycledContentNickel` | exact | yes |  |
| `round_trip_efficiency` | 1 | `io.BatteryPass.Performance#roundTripEnergyEfficiency` | close | yes | The Regulation specifies round-trip efficiency at 50% SOC but does not fix the measurement boundary; condition_set.boundary and auxiliaries_included capture what the Regulation leaves open. |
| `self_discharge_rate` | 1 | `io.BatteryPass.Performance#selfDischargingRate` | broader | yes | Four incommensurable metrics are all called self-discharge; the Regulation does not say which. |
| `state_of_health` | 1 | `io.BatteryPass.Performance#stateOfHealth` | broader | yes | Capacity-based, resistance-based and blended SOH are different numbers. |
| `usable_energy` | J | `io.BatteryPass.Performance#usableBatteryEnergy` | close | yes |  |

## bdf

| Quantity | SI unit | External term | Relation | Verified | Note |
|---|---|---|---|---|---|
| `capacity` | C | — *(none)* | no_equivalent | yes | BDF carries cumulative charge/discharge capacity per record. It has no concept of a rated capacity under stated conditions - that is metadata, and the metadata format does not exist yet. |
| `cycle_life` | 1 | — *(none)* | no_equivalent | yes | Out of scope for a time-series format. |
| `current` | A | `current_ampere` | close | yes | BDF documents positive = charge. This schema does NOT inherit that as an assumption: test_run.current_sign records the convention per run, because ionworksdata uses the opposite sign under the same column name. |
| `cycle_number` | 1 | `cycle_count` | close | yes | BDF carries a single cycle count. This schema stores cycle_index_as_reported AND cycle_index_derived, because no two cyclers agree on when a cycle increments. |
| `frequency` | Hz | `frequency_hertz` | exact | yes |  |
| `impedance_imag` | ohm | `imaginary_impedance_ohm` | exact | yes |  |
| `impedance_real` | ohm | `real_impedance_ohm` | exact | yes |  |
| `internal_resistance_ac` | ohm | `ac_internal_resistance_ohm` | broader | yes | BDF has a single AC resistance column with no frequency, SOC or temperature. Those are required conditions here, so a BDF value alone cannot be promoted to an observation without them. |
| `internal_resistance_dc` | ohm | `dc_internal_resistance_ohm` | broader | yes | Same issue, worse: DC resistance without a pulse duration is uninterpretable, and 2 s / 10 s / 18 s / 30 s are all in standard use. |
| `power` | W | `power_watt` | exact | yes |  |
| `pressure` | Pa | `applied_pressure_pa` | narrower | yes | BDF separates ambient / applied / surface pressure. |
| `temperature` | K | `ambient_temperature_celsius` | narrower | yes | BDF separates ambient / surface / t1..t5. This schema additionally binds each to a sensor entity with a mount location, which BDF has no concept of. |
| `time` | s | `test_time_second` | exact | yes | BDF required column. |
| `voltage` | V | `voltage_volt` | exact | yes | BDF required column. |

## bpx

| Quantity | SI unit | External term | Relation | Verified | Note |
|---|---|---|---|---|---|
| `internal_resistance_dc` | ohm | — *(none)* | no_equivalent | yes | BPX is explicitly physics-model-only and has NO equivalent-circuit schema. There is no ECM standard anywhere in the field. bd.ecm_parameter_point is this project's proposal: R0 and RC branches as a lookup surface over (SOC, temperature, direction, pulse duration) with mandatory fit provenance. |
| `capacity` | C | `Nominal cell capacity [A.h]` | close | yes | BPX nominal capacity carries no rate or temperature; this schema requires them. |
| `charge_cutoff_voltage` | V | `Upper voltage cut-off [V]` | exact | yes |  |
| `diffusion_coefficient` | m2/s | `Diffusivity [m2.s-1]` | close | yes |  |
| `discharge_cutoff_voltage` | V | `Lower voltage cut-off [V]` | exact | yes |  |
| `electrode_area` | m2 | `Electrode area [m2]` | close | yes | BPX does not state which area definition; this schema requires area_kind. |
| `entropic_coefficient` | V/K | `Entropic change coefficient [V.K-1]` | close | yes | BPX places this per-particle; sign convention is not stated. |
| `open_circuit_voltage` | V | `OCP [V]` | related | yes | BPX OCP is per-electrode (with separate lithiation/delithiation branches and a hysteresis decay constant); this quantity is full-cell OCV. |
| `specific_heat_capacity` | J/(kg*K) | `Specific heat capacity [J.K-1.kg-1]` | close | yes | BPX stores a single scalar. Measured specific heat is SOC-dependent (~6% between 50% and 100% SOC), so this schema requires soc_pct. |

## emmo_battery

| Quantity | SI unit | External term | Relation | Verified | Note |
|---|---|---|---|---|---|
| `cycle_life` | 1 | `ServiceLife` | related | pending |  |
| `state_of_charge` | 1 | `StateOfCharge` | exact | pending |  |

## emmo_electrochemistry

| Quantity | SI unit | External term | Relation | Verified | Note |
|---|---|---|---|---|---|
| `capacity` | C | `Capacity` | broader | pending | IRI resolved at build time from electrochemistry.ttl. |
| `open_circuit_voltage` | V | `OpenCircuitVoltage` | close | pending |  |

## Reading the relation column

- **`exact`** — round-trips losslessly
- **`close`** — same quantity, minor definitional differences
- **`broader`** — the external term is more general - information is lost going out
- **`narrower`** — the external term is more specific
- **`related`** — associated but not substitutable
- **`no_equivalent`** — **the external vocabulary has no term for this**

## Unverified rows

EMMO class IRIs are opaque UUIDs (`BatteryCell` = 
`battery_68ed592a_7924_45d0_a108_94d6275d57f0`). Rows marked *pending*
carry a label but no IRI: `tools/sync_vocabularies.py` resolves them by
parsing `battery.ttl` and `electrochemistry.ttl` at build time.
Hand-copying UUIDs from documentation is how crosswalks silently rot.
