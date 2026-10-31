# web/ — the cell finder

The page people use to find a cell, read every value with the conditions it
was rated at, and follow it to the manufacturer document. Deployed by
`.github/workflows/pages.yml`; the hub at lemonergy.com/data/ can embed or link
it.

| File | What it is |
|---|---|
| `index.html`, `style.css`, `app.js` | the page; tokens follow the Learn/Design system (see `style.css` header) |
| `data/quantity-groups.json`, `data/test-families.json`, `data/coverage.json`, `data/family-claims.json` | hand-curated, committed, checked by the builder |
| `data/cells.json`, `data/records/*.json`, `data/summary.json`, `data/registry.json`, `data/coverage-status.json` | **generated, not committed** — `python tools/build_web_data.py` |

Run it locally:

```bash
python tools/build_web_data.py          # ~20 s, writes web/data/
python -m http.server -d web 8000       # then open http://localhost:8000/
```

`fetch()` needs a server; opening `index.html` from the file system shows the
"data files are not built" message.

## What the page shows and refuses to show

- A value appears only when a contribution states it. Nothing is filled in.
- Calculated numbers (energy, Wh/kg from capacity × voltage ÷ mass) carry a
  `calc` mark in the table and the record.
- A voltage printed as "Voltage" without the word nominal is shown dotted
  with a tooltip; `vq` in `cells.json` says which quantity it came from.
- Upper and lower bounds ("≤ 10.2 mm", "≥ 300 mAh") are shown in the full
  record with their sign and are not used for comparison metrics.
- "Stated" is the count of eight core specifications the source gives:
  capacity, voltage, mass, continuous discharge current, cycle life,
  internal resistance, dimensions, operating temperature. The table sorts by
  it so the records that can carry an engineering decision come first.
- The CSV export is the filtered table, with `wh_per_kg_derived` and
  `voltage_quantity` columns so a spreadsheet keeps the same honesty.

`tests/test_web_observations.cjs` exercises the pure functions in `app.js`
(record grouping, Markdown export, lifecycle dates, CSV, similarity).

## Battery pages

`tools/build_battery_pages.cjs` turns the finder's data into one page per
battery (`web/batteries/<maker>/<model>/`, the record's uid as the path), a
page per maker with its source documents and every model in a sortable table,
the library index, `web/batteries/sources/` (every source document once, by
maker, with its link or hash, revision, retrieval date and the records it
supports), and `web/batteries/sitemap.xml`. Each battery page ends its source
block with a citation to copy: the document, then the record and page where
the values were compiled. The deploy builds them after `web/data/`; they
are not committed. lemonergy.com serves them at `/data/batteries/`, and every
page's canonical address is that one.

Values read exactly as in the finder: the pages use `web/app.js` for labels,
units, conditions, grouping, provenance and similar records. Search engines
are asked to index a battery's page only when its record states at least six
quantities, at least one beyond capacity, voltage, size and mass, from a named
maker; the others carry `noindex, follow` and stay out of the sitemap, and
their maker's page is the indexed one. `tests/test_battery_pages.cjs` checks
all of it.

    python tools/build_web_data.py
    node tools/build_battery_pages.cjs
