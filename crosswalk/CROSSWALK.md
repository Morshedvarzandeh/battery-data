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
| `absolute_max_voltage` | V | `UpperVoltageLimit` | close | yes |  |
| `absolute_min_voltage` | V | `VoltageLimit` | broader | yes |  |
| `area_specific_impedance` | ohm*m2 | `ElectricImpedance` | broader | yes |  |
| `areal_capacity` | C/m2 | `AreicCapacity` | exact | yes |  |
| `balancing_current` | A | `ElectricCurrent` | broader | yes |  |
| `calendar_life` | s | `CalendarLife` | exact | yes |  |
| `capacity` | C | `Capacity` | exact | yes |  |
| `capacity_retention` | 1 | `RetainedCapacity` | close | yes | Ours is a fraction of the reference capacity; EMMO's is the capacity itself. |
| `charge_cutoff_voltage` | V | `UpperVoltageLimit` | close | yes | EMMO's limit is a window bound; ours is the charge termination voltage, which is the same value on a datasheet. |
| `charge_transfer_resistance` | ohm | `ElectricResistance` | broader | yes |  |
| `coil_power` | W | `Power` | broader | yes |  |
| `coil_voltage` | V | `Voltage` | broader | yes |  |
| `cold_cranking_current` | A | `ElectricCurrent` | broader | yes | No cranking-current class in EMMO; the standard followed lives in condition_set.extra.standard. |
| `cold_resistance` | ohm | `ElectricResistance` | broader | yes |  |
| `contact_resistance` | ohm | `ElectricResistance` | broader | yes |  |
| `conversion_efficiency` | 1 | `EnergyEfficiency` | close | yes | A converter's efficiency at one load point and input voltage; the conditions carry the operating point. |
| `coulombic_efficiency` | 1 | `CoulombicEfficiency` | exact | yes |  |
| `current` | A | `ElectricCurrent` | exact | yes |  |
| `cv_cutoff_current` | A | `CurrentLimit` | related | yes |  |
| `cycle_charge_voltage` | V | `ChargingVoltage` | close | yes |  |
| `cycle_life` | 1 | `ServiceLife` | related | pending |  |
| `cycle_life` | 1 | `CycleLife` | exact | yes |  |
| `cycle_number` | 1 | `CycleIndex` | exact | yes |  |
| `diameter` | m | `Diameter` | exact | yes |  |
| `diffusion_coefficient` | m2/s | `DiffusionCoefficient` | exact | yes |  |
| `discharge_cutoff_voltage` | V | `VoltageLimit` | broader | yes | No lower-limit class in the published ontology. |
| `displacement` | m | `Displacement` | exact | yes |  |
| `dqdv` | C/V | `DifferentialCapacity` | exact | yes |  |
| `dropout_voltage` | V | `Voltage` | broader | yes |  |
| `electrode_area` | m2 | `Area` | broader | yes | EMMO has no electrode-area quantity; the area_kind condition carries which area is meant. |
| `energy` | J | `Energy` | exact | yes |  |
| `energy_density` | J/m3 | `EnergyDensity` | exact | yes |  |
| `energy_efficiency` | 1 | `EnergyEfficiency` | exact | yes |  |
| `entropic_coefficient` | V/K | `TemperatureCoefficientOfTheOpenCircuitVoltage` | exact | yes |  |
| `expansion_force` | N | `Force` | broader | yes |  |
| `first_cycle_efficiency` | 1 | `InitialCoulombicEfficiency` | exact | yes |  |
| `float_charge_voltage` | V | `ChargingVoltage` | close | yes |  |
| `force` | N | `Force` | exact | yes |  |
| `frequency` | Hz | `Frequency` | exact | yes |  |
| `heat_generation_rate` | W | `HeatFlowRate` | close | yes |  |
| `height` | m | `Height` | exact | yes |  |
| `impedance_imag` | ohm | `ImaginaryElectricImpedance` | exact | yes |  |
| `impedance_real` | ohm | `RealElectricImpedance` | exact | yes |  |
| `input_voltage_max` | V | `Voltage` | broader | yes |  |
| `input_voltage_min` | V | `Voltage` | broader | yes |  |
| `insulation_resistance` | ohm | `ElectricResistance` | broader | yes |  |
| `intensity` | 1 | `Intensity` | exact | yes |  |
| `internal_resistance_ac` | ohm | `ACInternalResistance` | exact | yes |  |
| `internal_resistance_dc` | ohm | `DCInternalResistance` | exact | yes |  |
| `leakage_current` | A | `Leakage` | related | yes |  |
| `length` | m | `Length` | exact | yes |  |
| `mass` | kg | `Mass` | exact | yes |  |
| `max_continuous_charge_current` | A | `MaximumContinuousChargingCurrent` | exact | yes |  |
| `max_continuous_discharge_current` | A | `MaximumContinuousDischargingCurrent` | exact | yes |  |
| `max_pulse_charge_current` | A | `MaximumPulseChargingCurrent` | exact | yes |  |
| `max_pulse_discharge_current` | A | `MaximumPulseDischargingCurrent` | exact | yes |  |
| `max_runaway_temperature` | K | `ThermalRunaway` | related | yes |  |
| `measurement_range_max` | A | `ElectricCurrent` | broader | yes |  |
| `nominal_voltage` | V | `NominalVoltage` | exact | yes |  |
| `ohmic_resistance` | ohm | `ElectricResistance` | broader | yes | The high-frequency real-axis intercept; EMMO has no dedicated class. |
| `open_circuit_voltage` | V | `OpenCircuitVoltage` | exact | yes |  |
| `operate_time` | s | `Time` | broader | yes |  |
| `operating_temperature_max` | K | `MaximumOperatingTemperature` | exact | yes |  |
| `operating_temperature_min` | K | `MinimumOperatingTemperature` | exact | yes |  |
| `output_current` | A | `ElectricCurrent` | broader | yes |  |
| `output_voltage_max` | V | `Voltage` | broader | yes |  |
| `output_voltage_min` | V | `Voltage` | broader | yes |  |
| `peak_power` | W | `MaximumPower` | close | yes |  |
| `pickup_voltage` | V | `Voltage` | broader | yes |  |
| `power` | W | `Power` | exact | yes |  |
| `power_dissipation` | W | `Power` | broader | yes |  |
| `pressure` | Pa | `Pressure` | exact | yes |  |
| `rated_current` | A | `ElectricCurrent` | broader | yes |  |
| `rated_power` | W | `Power` | broader | yes |  |
| `rated_voltage` | V | `Voltage` | broader | yes |  |
| `relaxation_time` | s | `RelaxationTime` | exact | yes |  |
| `release_time` | s | `Time` | broader | yes |  |
| `reserve_capacity_minutes` | s | `Time` | broader | yes |  |
| `round_trip_efficiency` | 1 | `RoundTripEnergyEfficiency` | exact | yes |  |
| `runaway_onset_temperature` | K | `ThermalRunaway` | related | yes | EMMO models the process, not the onset temperature. |
| `self_discharge_rate` | 1 | `SelfDischargeRate` | exact | yes |  |
| `service_life_hours` | s | `ServiceLife` | close | yes | Service life against a stated load, schedule and cutoff; EMMO's term does not carry the load. |
| `short_circuit_current` | A | `ShortCircuitCurrent` | exact | yes |  |
| `specific_capacity` | C/kg | `SpecificCapacity` | exact | yes |  |
| `specific_energy` | J/kg | `SpecificEnergy` | exact | yes |  |
| `specific_heat_capacity` | J/(kg*K) | `SpecificHeatCapacity` | exact | yes |  |
| `specific_power` | W/kg | `SpecificPower` | exact | yes |  |
| `stack_pressure` | Pa | `Pressure` | broader | yes |  |
| `standard_charge_current` | A | `ChargingCurrent` | close | yes |  |
| `state_of_charge` | 1 | `StateOfCharge` | exact | yes |  |
| `state_of_health` | 1 | `StateOfHealth` | exact | yes |  |
| `storage_temperature_max` | K | `MaximumStorageTemperature` | exact | yes |  |
| `storage_temperature_min` | K | `MinimumStorageTemperature` | exact | yes |  |
| `switching_frequency` | Hz | `Frequency` | broader | yes |  |
| `temperature` | K | `CelsiusTemperature` | close | yes | Stored in kelvin as SI, quoted in Celsius by every source. |
| `thermal_conductivity_in_plane` | W/(m*K) | `ThermalConductivity` | narrower | yes |  |
| `thermal_conductivity_through_plane` | W/(m*K) | `ThermalConductivity` | narrower | yes | EMMO's is scalar; ours is the through-plane component of a tensor (docs/02-conventions.md section 20). |
| `thickness` | m | `Thickness` | exact | yes |  |
| `time` | s | `Time` | exact | yes |  |
| `two_theta` | deg | `BraggAngle` | close | yes |  |
| `usable_energy` | J | `StoredEnergy` | related | yes | Usable energy is the stored energy the boundary and depth of discharge allow out; the boundary condition carries the rest. |
| `voltage` | V | `Voltage` | exact | yes |  |
| `voltage_drop` | V | `Voltage` | broader | yes |  |
| `volume` | m3 | `Volume` | exact | yes |  |
| `width` | m | `Width` | exact | yes |  |

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
