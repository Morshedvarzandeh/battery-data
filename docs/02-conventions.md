# Conventions: where this schema is opinionated, and why

Every entry below is a place where battery practice genuinely conflicts — where
two labs, two cyclers, or two datasheets use the same word for different things.
A schema that picks one silently produces data that looks comparable and is not.

The pattern throughout: **store the convention alongside the number.** Not as
optional metadata, but as part of what the number means.

---

## 1. Current sign

`test_run.current_sign` · `current_sign_convention`

BDF, Voltaiq (VDF), `battdat` and `battery-data-standard` default to
**charge-positive**. `ionworksdata` enforces **discharge-positive**. Same column
name, opposite meaning. Arbin and Maccor make it a *user export setting*, so it
varies file to file from one lab.

**Decision:** never assume. `agents/literature-miner/pipeline.py:infer_current_sign()`
determines it from the data — does charge capacity accumulate while current is
positive? — and cross-checks against the parser default. Store the result.

## 2. Capacity accumulation semantics

`test_run.capacity_accum` · `capacity_accumulation`

Arbin accumulates within a *step*. Neware/`fastnda` give net per step. Voltaiq
resets per *cycle*. BDF carries step/net/cumulative as separate columns.

**Decision:** store which one the source used; derive the others on read.

## 3. Cycle counting

`timeseries_record.cycle_index_as_reported` + `cycle_index_derived` +
`test_run.cycle_definition`

No two vendors agree on when a cycle increments. Neware's BTSDA counts backward
step-index jumps; `fastnda` counts on charge→discharge completion and documents
the divergence; `NewareNDA` exposes three user-selectable modes; Arbin increments
on schedule loops, and a rest-only diagnostic block may or may not count.

**Decision:** `cycle` is not ground truth. Store what the instrument said *and*
what a named, versioned algorithm derived. `step` and `record` are first-class;
`cycle` is an annotation.

## 4. What "1C" means

`condition_set.rate_reference_capacity_ah` + `rate_reference_source`;
`test_run.c_rate_reference_capacity_ah`

C-rate is self-referential. LG defines 1C = 4800 mA, Samsung 4900 mA, and
measured C₁ routinely differs from nameplate by more than 10%. So "0.5C" is a
different current at different vendors, *and* changes if you re-derive it from
measured capacity.

**Decision:** a `rate_unit = 'C'` row without a reference capacity or a stated
source is **rejected by a CHECK constraint**. Not warned about — rejected.

## 5. Rate is not always a current

`condition_set.rate_unit` ∈ `A | mA | C | It | W | P | W_per_kg | ohm`

EVE rates the LF280K in **constant power** ("0.5P" = 448 W). IEC 61960-3 uses
`It` notation. Primary-cell datasheets use resistive loads in ohms. Constant-
power and constant-current discharge are **not interconvertible**.

**Decision:** the unit is an enum, and conversion between incommensurable units
is never performed.

## 6. Capacity statistic

`observation.statistic` ∈ `rated | nominal | standard | minimum | typical | ...`

Panasonic NCR18650GA lists rated 3300, minimum 3350, typical 3450 mAh on one
page — rated is *lowest* because it is quoted at 20 °C while the others are at
25 °C. Any database treating "rated" as the conservative figure has it backwards.
There is no cross-vendor mapping between these words.

**Decision:** one row per stated value. Never reconcile, never average.

## 7. Resistance method

Separate quantities `internal_resistance_ac` and `internal_resistance_dc`,
each with mandatory conditions.

The LG M50LT lists AC 1 kHz = 15 mΩ and DC 10 s = 23 mΩ — 53% apart, same cell.
Energizer states the L91 as "120 to 240 milliohms (**depending on method**)", a
2× range attributable purely to technique. Duracell publishes 120 mΩ (Industrial)
and 81 mΩ (Ultra) for the same AA size, both "@1 kHz".

**Decision:** there is no `internal_resistance` column and never will be.

## 8. Pulse duration

`condition_set.pulse_duration_s` — required for `internal_resistance_dc`

USABC/FreedomCAR uses 10 s. ISO 12405-4 uses 0.1/2/10/18 s. SAE J1798 uses 30 s.
IEC 62660-1 uses 10 s. These capture different physics: ~2 s is ohmic plus fast
charge transfer, 18 s adds diffusion.

**Decision:** resistance is stored as
`(pulse_duration_s, pulse_current_a, direction, soc, temperature) → R`,
never as a scalar DCIR.

## 9. Which two samples define ΔV

`test_run.dcir_extraction` · `dcir_extraction`

V(last pre-pulse) vs OCV vs V(first sample after step); V(t=duration) vs V(last
sample of pulse). Documented case: **logging configuration alone moved a measured
pulse resistance from 36 mΩ to 28 mΩ on the same cell.**

**Decision:** store the extraction method. Never trust vendor-computed `R`
columns — recompute from raw and keep both.

## 10. Charge and regen resistance are different quantities

USABC deliberately uses asymmetric relative currents (1.00 discharge, 0.75 regen).

**Decision:** `condition_set.direction` is required; never merged.

## 11. ASI area convention

`condition_set.area_cm2` + `area_kind` · `area_definition`

ASI = R × A, but "A" is variously total separator area, single-sided cathode
area, or double-sided coated area.

## 12. EIS amplitude

`eis_spectrum.amplitude_value` + `amplitude_unit` + `amplitude_kind`

The EU test-methods white paper specifies **5 mV_rms**; IEC TS 62607-4 specifies
**10 mV** — a direct conflict. The literature is additionally ambiguous about
whether a quoted amplitude is rms, zero-to-peak or peak-to-peak. And the unit
itself changes with mode: mV for PEIS, mA for GEIS.

**Decision:** three separate fields.

## 13. EIS upper frequency

100 kHz is common practice; the white paper argues for starting at **10 kHz**
because above that you are measuring your cabling inductance, not the cell.

**Decision:** store the full frequency list plus `cable_description` and
`sensing` (4-wire Kelvin is effectively mandatory and is recorded).

## 14. Rest before measurement

`condition_set.rest_before_s` + `relaxation_criterion`

15 min, 1 h, 3 h and 60 h all appear in the literature for "rest before EIS". It
determines the low-frequency tail entirely, and for OCV it determines the value.

## 15. OCV is path-dependent

`condition_set.direction` required on `open_circuit_voltage`.

For LFP and Si-bearing cells, hysteresis is large enough that voltage-based SOC
is unusable — which is why `soc_method` is also a stored enum.

## 16. ICA/DVA processing

`curve.processing`

The best-practice literature is emphatic that smoothing **after** differentiation
displaces peaks and is routinely misread as degradation. Peak position is also
variously defined at reaction onset or at the maximum.

**Decision:** store the raw curve, and treat the derivative as a derived artefact
carrying its full recipe — bin size, smoothing method and window,
`smoothed_before_differentiation`, and the peak-position convention.

## 17. End-of-life definition

`protocol.eol_criterion_pct` + `eol_reference` + measurement rate and temperature

80% of *nameplate* and 80% of *measured BOL* are different numbers. LG defines
EOL on **energy** ("≥80% of Wh_ini"), Samsung on capacity. The EVE LF280K
datasheet contains **two contradictory definitions**: 80% energy retention for
its 6000-cycle claim, and separately "IR exceeds 150% of initial OR capacity
< 60% of nominal" as product end-of-life.

**Decision:** EOL is a property of the *protocol*, not of the cell. Both of EVE's
definitions are stored; the contradiction is visible rather than resolved.

## 18. Cycle life needs a mechanical constraint

`condition_set.constraint_mode` + `clamp_force_n`

EVE specifies cycle life "under 300 kgf ± 20 kgf clamping force". Unclamped, the
number is meaningless. This condition has no analogue for cylindrical cells.

## 19. Constant-force and constant-gap are different experiments

`mechanical_constraint`

Constant force measures *displacement*. Constant gap measures *force*. A shared
"swelling" table is a modelling error, so `thermal`/mechanical results carry the
fixture type as a required condition.

## 20. Thermal conductivity is a tensor

`thermal_property.k_through_plane_w_mk` / `k_in_plane_x_w_mk` / `k_in_plane_y_w_mk`

Verified on one pouch cell: through-plane 0.51 W/m/K, in-plane 26.6 W/m/K — a
factor of **52**. A scalar `k` column destroys the measurement.

## 21. Specific heat is SOC-dependent

6% difference between 50% and 100% SOC on a verified 20 Ah LFP cell, and it
depends on whether tabs and casing are included. `mass_basis` is stored.

## 22. Entropic coefficient

Sign convention varies; units appear as mV/K, V/K and J/mol/K; potentiometric,
calorimetric and frequency-domain methods disagree. All are stored explicitly.

## 23. ARC phi factor

`arc_result.phi_factor` + `holder_mass_g`

Thermal-inertia factor and holder mass are required to compare ARC results
between labs and are routinely omitted in publications.

## 24. Hazard scale

`abuse_result.hazard_scale` + `hazard_scale_version` + `hazard_level`

EUCAR 0–7 and SAE J2464 HSL 0–7 are similar but **not identical**, and some labs
use proprietary scales.

## 25. Self-discharge units are not interconvertible

`self_discharge_metric`

mV/day ("K-value"), µA leakage, %/month, and stand-test capacity retention are
four different measurements. Converting OCV decay to an equivalent leakage
current requires dOCV/dSOC at that SOC plus the cell capacity.

**Decision:** separate typed results. Never coerce.

## 26. Measurement boundary

`condition_set.boundary` + `auxiliaries_included`

Megapack 2 XL quotes 91.7% round-trip (2-hour) and 93.7% (4-hour) for the same
product. BYD quotes DC; Tesla quotes AC. Powerwall 3 publishes no conventional
RTE at all — instead "Solar→Battery→Home/Grid 89%", which includes PV conversion
and is not comparable to either. CATL's auxiliary HVAC draws up to 36.7 kW on a
2 MW system, so inclusion moves RTE by points.

## 27. The protocol file

`protocol.schedule_blob` + `schedule_text` + `schedule_sha256` + `protocol_step`

Cycler schedules (Arbin `.sdx`, Maccor procedures, Neware step XML, BioLogic
`.mps`) are universally discarded at publication. The Battery Data Genome names
protocol translation as the field's **top unsolved problem**.

**Decision:** store the vendor blob verbatim, plus a parsed step table, plus a
hash. Nothing else in the ecosystem does this.

---

## Bonus: sensor identity

`sensor` + `test_run_sensor`

`Aux_Temperature_1`, `LogTemp001` and `EVTemp` are free-text column names
carrying no location semantics. A thermocouple on the tab and one on the can
centre differ by tens of kelvin under load. This is the largest silent
information loss in every public dataset surveyed.

**Decision:** a sensor is a first-class entity with a mount location, and raw
columns bind to it.

---

## Bonus: declared absence

`condition_set.unstated`

The third state between "recorded" and "missing". Samsung publishes a 14,700 mA
non-continuous rating and **never states a duration**. Leaving `pulse_duration_s`
NULL makes that indistinguishable from an ingest bug.

Listing a column in `unstated` satisfies the required-conditions check and marks
the observation as incomplete — recording the omission as a fact about the
document rather than hiding it.
