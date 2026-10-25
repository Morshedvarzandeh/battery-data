# Finder redesign and the depth plan (25 October 2026)

What changed in this repository, what the private hub pages
(lemonergy.com/data and lemonergy.com/data/live) should change to match, and
the extraction plan that turns a wide catalog into a deep one.

## 1. The finding that drives everything else

Counted over every record in `contrib/cells/**/*.yaml` at commit 2c126c2:

| | records | share |
|---|---|---|
| Battery records | 3,455 | |
| from LiPol Battery + Harding Energy (catalog pouches) | 3,047 | 88 % |
| capacity + nominal voltage + mass (point values, not bounds) | 228 | 6.6 % |
| continuous discharge rating | 26 | 0.8 % |
| cycle-life figure | 38 | 1.1 % |
| internal resistance | 13 | 0.4 % |
| form factor recorded (before this review) | 192 | 5.5 % |
| document date recorded | 34 | 1.0 % |

Samsung SDI 1 · CATL 2 · BYD 1 · LG 8 · Molicel 0. The Ragone chart plotted
27 cells. The library is wide where few people look and empty where most do.
Design and copy cannot fix that; extraction can. Everything in §4 exists to
make the gap visible and the fix mechanical.

## 2. What this branch changed in the repository

- **`form_factor: pouch` on 3,047 catalog cells** — `tools/migrate_form_factor.py`,
  recorded in `review/audits/2026-10-25-form-factor-revision.json` with the
  previous and revised bytes of every file. `tools/review_ledger.py` is the
  general mechanism: a revision audit documents a change to an accepted
  record, and the tests that pin accepted bytes resolve through the ledger.
  Phase B revisions (adding a discharge rating to an accepted Samsung record,
  say) use the same mechanism: write the change, append a `revisions` entry
  with `fields` and `change`, done.
- **The finder** (`web/`) is rebuilt in the Learn/Design visual system and
  reads generated data (`web/data/*.json`, gitignored) instead of carrying a
  13 MB inline copy. See `web/README.md`.
- **CI** runs once per PR and once on `main`, cancels superseded runs and
  skips the Postgres job when a PR touches nothing it tests. `pages.yml`
  deploys `web/` to GitHub Pages (Settings → Pages → Source: GitHub Actions,
  once).

## 3. Hand-off: the hub pages

The hub lives in a private repository, so these are the changes to make there.
`web/style.css` in this repository is the reference token file; its `:root`
block is the Learn/Design palette and can be copied into `data.css`.

### Visual

| Today | Change to |
|---|---|
| Yellow active-nav pill on `/data/` and `/data/live` | Blue underline (`box-shadow: inset 0 -2px 0 var(--accent)`), as Learn does; the lemon stays in the logo mark only |
| `-apple-system, Segoe UI` body font | `Arial, Helvetica, sans-serif` (Learn and Design) |
| Olive-green "details." in the `/live` hero; green-tinted "Next island" CTA panel | Ink for the headline; `--soft` (#f5f6f8) panel with a `--line` border. The design system has no green |
| Card shadows and 12–16 px radii on result cards | 1 px `--line` border, 6 px radius, no shadow except on the one floating panel |
| Monospace values inside cards | Body face with `font-variant-numeric: tabular-nums` |
| `02 / ISLAND 03` mono eyebrows | Keep the numbered eyebrow (it is the site's navigation motif) but in the body face, 11 px, letter-spaced, blue |

### Structure of `/data/`

1. Hero: eyebrow, one headline, one sentence, the search box, example chips,
   and **one row of honest counts** from `summary.json` — records,
   components, cells with capacity + nominal voltage + mass, with a
   continuous discharge rating, with a cycle-life figure. The last three are
   the ones to watch move.
2. The finder: embed this repository's deployed page in an iframe, or copy
   `index.html` + `app.js` + `style.css` and point `app.js` at the data URL
   (`<script src="app.js" data-base="https://…/data/">`). It replaces the
   14-input sidebar and the card grid.
3. One "Bring it into your tools" strip: a tabbed code sample and three
   links. The endpoint table and the four plan cards move to **`/data/api`**,
   one page, with the reference first and the plans second. `/data/live`
   keeps the live demo and the mission comparison and loses its copy of the
   plans and the endpoint list.
4. "Tell us which cell you need" stays as the last block.

### Copy

- "3,633 battery products" on `/data/live` is 3,455 batteries + 178
  components. Use the two numbers from `summary.json`.
- "28 curated cells" under a "3,455" headline reads as a contradiction. Show
  the full table sorted by how much the source states; the curated set is
  the top of that sort.
- Every "Not recorded" in a card becomes an empty cell with a dash in a
  table; the inspector states "Not stated by the source: …" once.

## 4. Phase B — depth on the cells people search for

The target list is `web/data/coverage.json` (rendered at the bottom of the
finder as sourced / wanted). Five batches, 56 cells, ordered by how often
engineers compare them:

1. Power cylindrical 21700 — Molicel P45B/P42A/P50B, Samsung 50S/40T/30T,
   LG M50LT/M58, Panasonic NCR2170, Murata VTC6A (sourced), EVE 50E, BAK,
   Tenpower, Lishen.
2. 18650 — Samsung 35E/30Q/25R, LG MJ1/HG2, Panasonic NCR18650B/GA
   (sourced), Murata VTC5A (sourced), Molicel P28A/P26A, EVE 35V, BAK.
3. Prismatic LFP 100–320 Ah — EVE LF280K/LF304/LF105, CATL 280/302
   (sourced)/314 (sourced), Gotion 314, REPT 280/320, Hithium 280, CALB
   L173F280, BYD Blade, Lishen 280, Great Power 314.
4. Automotive pouch and prismatic NMC — LG E66A/E78, SK On E582, Farasis,
   CATL NMC 50Ah, Samsung PRiMX 94Ah / Gen5, CALB L221N113A, SVOLT 115Ah,
   Northvolt.
5. Coin and primary — CR2032 family (mostly sourced), L91, BR2032, CR2450.

### The extraction contract for every batch

Each record reaches the accepted library with these, each as an observation
with conditions, or an explicit `unstated` declaration:

| Quantity | Conditions that must be stated or declared unstated |
|---|---|
| `capacity` (standard and rated if both printed) | rate, temperature, lower cut-off |
| `nominal_voltage`, `charge_cutoff_voltage`, `discharge_cutoff_voltage` | — |
| `max_continuous_discharge_current` | temperature |
| `max_pulse_discharge_current` | pulse duration, temperature |
| `standard_charge_current`, `max_continuous_charge_current` | temperature |
| `cycle_life` | DoD, rate, temperature, end-of-life criterion |
| `internal_resistance_ac` (1 kHz) and/or `internal_resistance_dc` | frequency or pulse, SoC, temperature |
| `mass`; `diameter` + `height` or `length` + `width` + `thickness` | — |
| `operating_temperature_min/max` for charge and discharge | direction |
| `source.document_date`, `source.revision` | printed on the sheet |

That is the eight-slot "Stated" meter on the finder plus the three fields the
compare and energy map need. A record that reaches 8/8 moves to the top of
the default sort automatically.

### How a batch runs

```bash
# one cell; the PDF URL is the manufacturer's or a distributor's copy
python tools/extract_datasheet.py --url <pdf-url> \
    --manufacturer "Molicel" --model INR21700-P45B --kind cell
python tools/validate_contrib.py contrib/cells/molicel/
python tools/check_duplicates.py
python tools/build_web_data.py --check
```

The extraction output is a pull request; the review checks the two failure
modes in `docs/06-submitting-a-datasheet.md` (a quote attached to the wrong
column; a condition marked unstated that is printed in a footnote). Where a
batch revises an accepted record, append its entry to a dated revision audit
so the ledger chain stays unbroken.

Expected effect after batches 1–3: continuous discharge ratings from 26 to
~70 records, cycle life from 38 to ~70, cells with 8/8 from 4 to ~40 — and
the energy map, compare and similar-records features start carrying the
cells people actually ask about.

## 5. Phase C — once the depth exists

- **Digitised curves.** The schema already has `curves` (x/y series with
  conditions and a locator). The finder shows their presence in the full
  record; rendering them is a small SVG line chart per curve kind. The work
  is the digitisation pipeline, not the display.
- **Third-party measurements** as a `source.kind` (`independent_test`) so
  lygte-info, BatteryRealData and Battery Archive values can sit beside the
  datasheet claim, labelled.
- **Contribution and error flags** from the page: a "Report a value" link per
  observation that opens the issue form with the uid and quantity prefilled.
- **Shareable and saved shortlists**: the `#cmp=` link exists; persistence
  belongs to the hub's account layer.
