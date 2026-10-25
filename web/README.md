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
