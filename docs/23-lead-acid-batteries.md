# Lead-acid batteries — in the library, never in Design

The Technology filter listed Lead-acid and its variants at zero. These are
the first 97 lead-acid batteries, added on 29 October 2026 at the owner's
request, with one condition: lead-acid must never be offered for Lemonergy
Design, which works with lithium-ion and sodium-ion. A separate lead-acid
part may follow; until then lead-acid is reference data only.

## What is in

| Variant | Use | Source | Products |
|---|---|---|---|
| AGM | deep cycle / solar | Victron Energy Gel and AGM datasheet | 12 (one 6 V, eleven 12 V) |
| Gel | deep cycle / solar | same datasheet | 7 × 12 V |
| Gel | standby (OPzV) | Exide Sonnenschein A600 technical data sheet | 14 × 2 V cells, 4 blocks |
| Flooded | deep cycle (golf cart, RV, solar) | Trojan T-105 datasheet | 1 × 6 V |
| Flooded | standby (OPzS) | Exide Classic OPzS technical data sheet | 21 × 2 V cells, 6 blocks |
| AGM | standby / UPS / alarm | Yuasa NP technical data sheets | NP4-12, NP7-12, NP12-12, NP17-12I, NP12-6 |
| AGM | starting and deep cycle | ODYSSEY Extreme specification page (EnerSys) | 16 × 12 V |
| EFB | start-stop starting | VARTA Dynamic EFB product pages (Clarios) | 11 × 12 V |

Every source is first-party. 35 products are 2 V cells (`kind: cell`); the
62 six- and twelve-volt monoblocs hold several cells in one case and are
`kind: module`. The finder's default Kind is rechargeable cells, so a search
for AGM or EFB says how many match under *Modules, packs and systems* and
offers to show them.

`tools/import_lead_acid_batteries.py` holds every spec table as printed and
writes the batch; `review/audits/2026-10-29-lead-acid-batteries.json` accepts
it. Before acceptance each transcribed row and statement was located again in
a fresh copy of its source.

## Design exclusion

`web/data/technologies-and-chemistries.json` gives every technology a
`design` flag. Only Lithium-ion and Sodium-ion are `true`. Everything else —
lead-acid, nickel chemistries, primary cells — stays in the library and is
marked:

* the finder shows *Not for Lemonergy Design* on the record, and the CSV
  export has a `lemonergy_design` column;
* the hub (lemonergy.com/data) reads the same flag: its shortlist does not
  offer these records, *Open in Design* refuses them, and the discharge
  calculator does not list them.

A record that states no technology is not excluded on a guess.

## Ratings lead-acid needs

`schema/139_lead_acid_quantities.sql` (and its migration) adds a minute unit
and six quantities, each with its required conditions:

| Quantity | Holds | Notes |
|---|---|---|
| `cranking_current` | CCA, HCA, MCA, MPCA, MHPCA | the rating name and the standard go in `conditions.extra`; EN and SAE CCA are different tests |
| `reserve_capacity` | minutes at a constant current to an end voltage | a time, never ampere-hours |
| `float_charge_voltage` | standby charge voltage | tolerance and compensation in `extra` |
| `cyclic_charge_voltage` | absorption / boost / "bulk" voltage | a charger setting, not a maximum rating |
| `equalize_charge_voltage` | periodic equalising charge (flooded) | |
| `short_circuit_current` | prospective short-circuit current | standard in `extra` |

## Conventions

* **Hour-rate capacity.** C20, "20-hr rate" and "20 hr. discharge" are the
  capacity delivered at C20/20 amperes. They are stored as `rate_value =
  1/hours`, `rate_unit = "C"`, with the hour rate in `extra.hour_rate_h` and
  the capacity itself named as the C-rate reference.
* **End voltage per cell.** "1.80 Vpc" is kept in `extra.cutoff_per_cell_v`;
  `voltage_lower_v` is the product's own terminal voltage, per-cell value ×
  cells in series (printed for the Trojan, otherwise nominal voltage at 2 V
  per cell). The arithmetic is stated in `extra.voltage_lower_basis`.
* **Ranges** such as "13,5 - 13,8 V" are two observations, minimum and
  maximum, sharing one quote.
* **Fahrenheit only.** "CCA @0°F" and "RES CAP @80°F" are converted to
  −17.8 °C and 26.7 °C with the printed temperature kept in `extra`.
* **Resistance without a method** is not recorded (docs/02, section 7). Yuasa
  prints 1 kHz, so its values are AC resistance; Exide and ODYSSEY print no
  method and their resistance is held.
* **Manufacturer** is the company that issues the document; the brand stays in
  the model: *Exide — Sonnenschein A602/225*, *EnerSys — ODYSSEY ODX-AGM24*,
  *Clarios — VARTA Dynamic EFB 572501076*.
* **Chemistry** of every lead-acid battery is the PbO2/Pb couple; the variant
  (AGM, gel, flooded, EFB) is the technology variant, never the chemistry.

## Held for later

The Exide constant-current and constant-power discharge tables (1.60–1.90 Vpc,
3 minutes to 20 hours) are the data a lead-acid design tool needs; they are
not transcribed yet. Also held: Victron's capacity-versus-discharge-time
table, storage voltages and compensation coefficients; Yuasa's 10-minute
constant-power ratings; the VARTA PDF datasheets, which could not be opened
for this review (download only), so weight and the C20 and CCA bases of the
VARTA records are not stated; and every graph.
