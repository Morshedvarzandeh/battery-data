# Partner sodium-ion cells and the Lemonergy stock list — 28 October 2026

Lemonergy now sells sodium-ion cells through a sourcing partner. This change
adds those cells to the library and lets the finder say they are available,
without letting that commercial fact touch the data.

## What was added

**40 sodium-ion cells, 680 observations, from 7 hashed documents** the partner
supplied: a one-page 35-row cell spreadsheet (2026H2) and six single-cell
datasheets. 34 records come from the spreadsheet; 6 from the datasheets. The
spreadsheet row JNP1814867 is the same model as the datasheet
JNP1814867-5.5HP, so it is filed once, from the datasheet, with the short code
as an alias.

| Format | Cells | Capacity range |
|---|---:|---|
| Cylindrical | 18 | 0.9–280 Ah |
| Prismatic | 17 | 5.5–270 Ah |
| Blade | 5 | 60–280 Ah |

The transcription is `tools/import_partner_sodium_cells.py`, which writes
`review/batches/2026-10-28-partner-sodium-ion-cells.json`. Spreadsheet values
are parsed from the cell text as printed, so a value and its quote cannot
drift apart. Acceptance is recorded in
`review/audits/2026-10-28-partner-sodium-ion-cells.json`.

## Three rules these records follow

**The producer is named only when a document names it.** None of the seven
does. The issuer is a distributor, so every record says
`manufacturer: Maker not stated` under `cell/maker-not-stated/…`. The finder
shows "Maker not stated"; summary counts do not count it as a manufacturer.
When a producer is established from a document, the record moves and keeps
its old uid as an alias.

**The partner stays out of the public data.** No company name, person, e-mail
or telephone number is recorded, and the documents have no public URL. Each
source is identified by its SHA-256 and the date Lemonergy received it. Model
numbers are kept as printed; they are the product's identity.

**Stock is a seller's statement, kept beside the record, not in it.**
`offers/lemonergy.json` (schema `json-schema/offer.schema.json`) lists the 40
uids with `status: in_stock` and an `as_of` date. `tools/build_web_data.py`
refuses an offer for an unknown uid, a duplicate, an unknown status or a bad
date. The finder row gains one `stock` field and nothing else —
`tests/test_partner_sodium_offers.py` checks that an offered row is otherwise
identical to the same row without the offer, so availability cannot move a
record in any default sort. Readers see an "In stock · Lemonergy" line, an
opt-in **Available now from Lemonergy** filter, and a **Request a quote** link
to info@lemonergy.com.

## C-rates are now stored as C-rates

The spreadsheet prints current limits only as C-rates ("35C cont / 70C
pulse"). Two wrong options existed: put 35 in a current quantity with unit
`C`, which the unit table reads as 35 coulombs, or multiply by a capacity the
sheet never names as the reference. `schema/138_c_rate_quantities.sql` (and
`migrations/2026-10-28-c-rate-quantities.sql` for existing databases) adds a
`C-rate` unit and four quantities:

| Quantity | Required conditions |
|---|---|
| `max_continuous_discharge_rate` | temperature |
| `max_pulse_discharge_rate` | pulse duration, temperature |
| `max_continuous_charge_rate` | temperature |
| `standard_charge_rate` | temperature |

Where a source prints amperes, the ampere quantities are still used. The
finder shows a printed C-rate as such ("35 C", never converted) and counts it
as a continuous discharge rating.

Twenty existing REPT records (`contrib/cells/rept/*.yaml`) store a fast-charge
rate as `max_continuous_charge_current` with unit `C`; the database reads
them as coulombs (`value_si` 2.2 for "2.2C"). They are left unchanged here,
because accepted records change only through a revision audit; moving them to
`max_continuous_charge_rate` is that revision.

## What the sources leave open

- No test conditions on the spreadsheet: capacity rate, temperature and
  cut-off; AC-resistance frequency, SOC and temperature; cycle-life
  temperature, depth of discharge and end-of-life criterion are all declared
  `unstated`.
- A "Charge Rate" printed without "std" or "max" is recorded as a maximum
  with that ambiguity on the value. Discharge "cont" and "pulse" labels are
  kept; no pulse duration is printed.
- Spreadsheet dimensions carry no axis labels. Axes follow the
  thickness-width-height digits of each model code, the order the same
  supplier's datasheets label; the basis is stored on each dimension.
- Pulse-cycle counts ("≥20,000 pulse cycles") stay a qualifier on the
  cycle-life value, not a full-cycle life.
- Three datasheets resemble spreadsheet rows (NaCR46145 / JNC46145H,
  NFPP54173204 / JNP54173207L, NaCP51160120 / JNP50160118H) but differ in
  voltage, size or rating, so they are separate records with the
  relationship noted.
- Internal inconsistencies are kept and disclosed, not reconciled: 15C/200 A
  on a 13 Ah cell, "1C/300A" charge on a 100 Ah cell (the 300 A is not
  recorded), ≥90 Wh/kg against 285 Wh / 3.3 kg.

## Finder changes that apply to every record

- A printed bound ("≥3,000 cycles", "≤1 mΩ") now shows as that bound in the
  inspector and the Cycles column instead of "not stated". It still stays out
  of metrics, sorting and the 8-dot depth count.
- Source kinds read as a person would say them ("supplier list" for a
  distributor listing), instead of every non-datasheet reading "manufacturer
  web page".
- CSV export gains continuous discharge C-rate, cycle-life and resistance
  bounds, and availability.

The hub's shortlist at lemonergy.com/data is built in the private hub
repository and does not yet show the stock line; the full finder under
`/data/finder/` does, once this repository deploys.
