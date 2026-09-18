# The acquisition list — what the library does not state yet

*Measured 18 September 2026 against the accepted library. Every number here
is printed by `python tools/coverage_report.py`; regenerate it rather than
trust this copy.*

## Why this document exists

The cell layer of the Lemonergy Data API answers four questions about a
cell: where it sits in a population on two axes, how it ranks among cells of
its own size, which cells share its envelope, and what fits a given space.
Those are answerable today for most of the library, because most of the
library states a capacity, a voltage, a mass and three dimensions.

Every other comparison a cell engineer expects — a Ragone plot, an impedance
comparison, a discharge-curve overlay, cycle life against depth of
discharge, current capability against capacity — **cannot be drawn at all**,
and not because the code is missing. The inputs are. Across the 2,131
accepted cells the library states a cycle life for 35, a continuous
discharge current for 22, an AC impedance for 13, a DC resistance for none
and a specific power for none.

That distinction matters commercially. A missing feature is a backlog item.
A missing measurement is an acquisition task with a known cost per record,
and it is the binding constraint on what the second island can sell. This
document names each gap, the analysis it blocks, and what a record has to
carry to close it — so the work can be scheduled instead of rediscovered.

The same counts ride on every `/cells/*` response as `absent_axes`, read
from the live release. As records arrive the gaps shrink in the API and on
`lemonergy.com/data/` without anyone editing a page.

## What the library states today

| Quantity | Cells stating it | Share | What it gates |
|---|---:|---:|---|
| `capacity` | 2,114 | 99.2% | every ranking and density figure |
| `width` | 1,833 | 86.0% | the box envelope, volume and Wh/L |
| `length` | 1,831 | 85.9% | the box envelope, volume and Wh/L |
| `thickness` | 1,793 | 84.1% | the box envelope, the thickness cohort and Wh/L |
| `voltage` | 1,791 | 84.0% | energy in Wh where no nominal voltage is stated |
| `mass` | 1,667 | 78.2% | specific energy (Wh/kg) |
| `nominal_voltage` | 228 | 10.7% | energy in Wh, and every Wh-per-something |
| `height` | 178 | 8.4% | the cylinder envelope, volume and Wh/L |
| `operating_temperature_max` | 153 | 7.2% | the temperature window a design must respect |
| `operating_temperature_min` | 153 | 7.2% | the temperature window a design must respect |
| `diameter` | 136 | 6.4% | the cylinder envelope, volume and Wh/L |
| `cycle_life` | 35 | 1.6% | capacity retention against cycles; cost per kWh-cycle |
| `specific_energy` | 28 | 1.3% | a stated Wh/kg to cross-check the derived one against |
| `max_continuous_discharge_current` | 22 | 1.0% | current capability against capacity; C-rate headroom |
| `max_continuous_charge_current` | 21 | 1.0% | charge-time estimates |
| `volume` | 17 | 0.8% |  |
| `internal_resistance_ac` | 13 | 0.6% | impedance comparison between cells |
| `energy_density` | 7 | 0.3% | a stated Wh/L to cross-check the derived one against |
| `peak_power` | 4 | 0.2% |  |
| `rated_power` | 4 | 0.2% |  |
| `absolute_max_voltage` | 1 | 0.0% |  |
| `absolute_min_voltage` | 1 | 0.0% |  |
| `capacity_retention` | 1 | 0.0% | a measured fade curve rather than a single endpoint |
| `charge_cutoff_voltage` | 1 | 0.0% |  |
| `cv_cutoff_current` | 1 | 0.0% |  |
| `discharge_cutoff_voltage` | 1 | 0.0% |  |
| `max_pulse_discharge_current` | 1 | 0.0% | peak-power sizing |
| `self_discharge_rate` | 1 | 0.0% | shelf life and storage loss |
| `shipping_voltage` | 1 | 0.0% |  |
| `standard_charge_current` | 1 | 0.0% |  |
| `energy` | **none** | 0.0% | a stated energy to cross-check the derived one against |
| `internal_resistance_dc` | **none** | 0.0% | pack sag under load, usable power, a Ragone plot |
| `specific_power` | **none** | 0.0% | the Ragone plot (specific power against specific energy) |

A quantity with **none** is listed because it is absent, not omitted because
it is absent: a coverage report that only showed what the library happens to
have would be useless for planning.

Envelopes: 1,791 box, 136 cylinder, 204 publish no dimensions at all.
Sources carrying a document date: 18 of 2,170.

## The five analyses that are blocked, in the order worth closing

### 1. DC internal resistance — zero records

**Blocks:** pack voltage sag under load, usable power at a given current,
the power half of a Ragone plot, and any honest answer to "will this cell
hold the bus above its floor at peak".

This is the one number the design island asks for and never finds. The
Data API's `/compare` route takes a mission and runs each cell through the
same simulation; with no DC resistance in the library the caller has to
supply one, and the response marks it as the caller's assumption. Every
comparison that involves power is therefore only as good as a number the
customer guessed.

**What a record needs:** `internal_resistance_dc` in mΩ with the pulse
length, state of charge, temperature and current it was measured at. A DCIR
without its pulse length is not a resistance, it is a number — so the
quantity registry requires those conditions, and a datasheet that gives an
unqualified "IR ≤ 30 mΩ" should be recorded with `unstated` naming what the
document did not say.

**Where it is published:** cylindrical-cell datasheets from Molicel, LG
Energy Solution, Samsung SDI, Murata and EVE routinely state a 1 kHz AC
impedance *and* a DC resistance; large prismatic LFP datasheets from CATL,
EVE, REPT and HiTHIUM state DCIR at several states of charge. The 136
cylindrical records already in the library are the natural first batch.

### 2. Continuous and pulse discharge current — 22 and 1 records

**Blocks:** current capability against capacity, C-rate headroom, the
first question asked after "how much energy".

**What a record needs:** `max_continuous_discharge_current` and
`max_pulse_discharge_current` in A, with the temperature, the pulse
duration for the pulse figure, and the cutoff voltage the limit applies to.

**Where it is published:** nearly every cell datasheet states at least the
continuous figure. The gap here is not availability, it is that the two
large catalogs the library was built from are *selection guides* — tables of
model, capacity, voltage and size — rather than datasheets. Closing it means
pulling the individual datasheets behind those catalog rows.

### 3. Cycle life and capacity retention — 35 and 1 records

**Blocks:** capacity retention against cycles, cost per kWh-cycle, and
every stationary-storage comparison, where cycle life is the economics.

**What a record needs:** `cycle_life` in cycles with the depth of
discharge, charge and discharge rates, temperature and the retention
threshold it is counted to (80% is conventional and is not universal), or
`capacity_retention` as a percentage at a stated cycle count.

A cycle life without its threshold and depth of discharge is unusable — a
"6,000 cycles" to 60% at 50% DoD and a "6,000 cycles" to 80% at 100% DoD
are different products. This is the gap where recording the conditions
matters most, and where most published figures are least qualified.

### 4. Specific power — zero records

**Blocks:** the Ragone plot, which is the chart the paid platforms lead
with.

This one closes for free with DC resistance: specific power at a stated
current follows from the resistance, the voltage window and the mass, all
of which the library either has or gains in gap 1. It is listed separately
because the *stated* figure is worth capturing where a datasheet gives it,
as a cross-check against the derived one — which is what `/cells/audit`
exists to do.

### 5. Discharge curves — not a quantity at all

**Blocks:** the overlay every datasheet prints and no specification schema
carries: voltage against capacity at several rates and temperatures.

A curve is not an observation, it is a series, and recording it means a
schema decision rather than a transcription: either a table of
(capacity, voltage) pairs per stated condition, or a reference to a
digitised dataset. This is the one gap on the list that is a design task
before it is an acquisition task, and it should not be started until gaps
1–3 are moving.

## The manufacturers who are absent

| Manufacturer | Cells | Share |
|---|---:|---:|
| Harding Energy | 1,343 | 63.0% |
| LiPol Battery Co., Ltd. | 448 | 21.0% |
| Renata | 108 | 5.1% |
| EEMB | 60 | 2.8% |
| Maxell | 57 | 2.7% |
| REPT BATTERO | 31 | 1.5% |
| Panasonic Energy | 27 | 1.3% |
| Energizer | 17 | 0.8% |
| EVE Energy | 15 | 0.7% |
| Murata | 11 | 0.5% |
| Panasonic | 5 | 0.2% |
| Toshiba | 4 | 0.2% |
| HiTHIUM | 3 | 0.1% |
| CATL | 1 | 0.0% |
| Samsung SDI | 1 | 0.0% |

Two historical selection guides are 84% of the cells. That is a true and
uncomfortable description of the library, and it shapes what the comparison
surface can honestly claim: it is strong on small pouch geometry and energy
density, and thin on everything a cylindrical or large-format designer
chooses on.

The names a working designer expects to compare, and their state here:

| Maker | Cells in the library | What is missing |
|---|---:|---|
| Molicel (E-One Moli) | none | the P-series cylindricals that high-power designs default to |
| LG Energy Solution | none | 18650/21700 cylindricals and the pouch range |
| BYD | none | blade LFP prismatics |
| CALB, Gotion, Sunwoda | none | large-format LFP and NMC prismatics |
| Samsung SDI | 1 | the rest of the cylindrical and prismatic range |
| CATL | 1 | the prismatic LFP range, which is most of the world's stationary storage |
| Panasonic / Panasonic Energy | 32 | the cylindrical range beyond the recorded models |
| EVE Energy | 15 | the large prismatic LFP range |
| HiTHIUM, REPT BATTERO | 3 and 31 | the rest of each published range |

A maker absent from the library is a maker whose published documents have
not been transcribed. It is not a judgement about their cells, and the
maker landscape on `lemonergy.com/data/` says so in those words.

## Two structural gaps

**Document dates.** Sources carrying a `document_date` are 18 of 2,170.
Every imported catalog note says availability is unverified, which is
honest but coarse: a date per source document is what lets a response say
how old a figure is, and lets a reader weigh a 2013 pouch table against a
2025 datasheet. This is mechanical work on existing records and should be
done first, because it costs least and improves every response.

**Chemistry designations.** 1,791 records carry "Lithium polymer" and 60
"Lithium-ion polymer" — the words the source catalogs used. Those are form
factors dressed as chemistries: neither names a cathode. The classifier in
the API maps them to a `LIPO` class and does not pretend otherwise, but a
chemistry-class comparison over this library is mostly a comparison of one
class against a handful. Closing this means reading the underlying
datasheets, so it rides along with gap 2.

## Reproduce these numbers

```bash
python tools/coverage_report.py                       # from contrib/
python tools/coverage_report.py --markdown            # the tables above
python tools/coverage_report.py --json                # the whole measurement
python tools/export_catalog_snapshot.py --output build/catalog.json
python tools/coverage_report.py --snapshot build/catalog.json
```

The report reads the same export the hosted API is built from, so its counts
are the counts a customer sees in `absent_axes`. If a number in this
document disagrees with the tool, the tool is right and this file is stale.
