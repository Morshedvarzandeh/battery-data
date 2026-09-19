# Data sources

Sources this project knows about but does **not** reproduce.

A source can be useful to a reader without its contents living in this
repository. Some are commercial products, some are open but better cited than
copied, and some are simply large enough that a link and a hash serve better
than a mirror. This file is where those are credited.

The rule the repository follows either way is the one in `START-HERE.md`:
store the extracted facts plus a URL, a hash and a retrieval date — never the
document body. `source.redistributable` in the schema controls the exception.
Kept this way, a takedown request is a per-source problem rather than a
project-ending one.

## Patent intelligence sources

Patent coverage is multi-source because no office or aggregator is complete on
families, legal events, citations, full text, languages and update latency at
the same time. The implementation and rights boundary are documented in
[`agents/patent-miner/AGENT.md`](../agents/patent-miner/AGENT.md).

- **Google Patents Public Data / BigQuery** is the global discovery backbone.
  Google hosts the public dataset; the querying project pays query costs beyond
  the applicable free tier. Scheduled runs therefore create a bounded plan
  only. Execution needs an explicit manual checkbox and hard bytes-billed cap.
- **EPO Open Patent Services (OPS)** exposes EPO worldwide bibliographic,
  family, legal-status, full-text and image data through a standardized XML
  API. It is the planned family/legal-event enrichment source. Registration,
  fair-use limits and OPS terms still apply.
- **WIPO PATENTSCOPE** covers published PCT applications and participating
  national/regional collections. Use an authorised data/API product; the
  PATENTSCOPE human interface is not a bulk retrieval endpoint.
- **USPTO Open Data Portal** provides official US APIs and bulk products. Bulk
  archive identity, file hashes and product dates must remain in provenance.

Patent document bodies are not mirrored merely because they are readable in a
browser. Every release records metadata and full-text rights separately.

---

## Referenced, not reproduced

### Batemo Cell Explorer

**Batemo GmbH** — <https://www.batemo.com/products/batemo-cell-explorer/>

Third-party characterisation of commercial cells bought on the open market:
extensive measurement data across the full operating regime, a validated
physical cell model, and a teardown report covering materials and
microstructure. Cells are measured independently of their manufacturers, which
makes the figures unusually comparable across vendors.

Measurement data, cell models and teardown reports are **commercial products**.
Chemistry, resistance, heat power and efficiency are behind their Insights
subscription. Cite and link; do not reproduce.

Worth knowing for: EV prismatic cells including BYD Blade, and any case where
you need characterisation traceable to something other than a vendor's own
marketing.

### CALCE Battery Data

**Center for Advanced Life Cycle Engineering, University of Maryland**
<https://calce.umd.edu/battery-data>

Open-access experimental data on lithium-ion cells: full and partial cycling,
storage, dynamic driving profiles, open-circuit voltage measurements and
impedance. Cylindrical, pouch and prismatic form factors across LCO, LFP and
NMC.

CALCE asks that publications using the data cite the CALCE article(s)
describing the experiments that generated it — cite the experiment, not just
the page.

The campaign protocols are stated precisely enough to reconstruct, which is
rare. Pulsed-discharge profiles alternating rates on fixed durations,
temperature cycling in stepped ambients, and partial-SOC ageing with periodic
full characterisation to re-establish true capacity as it fades. If you want
worked examples of the interleaving that `test_segment` exists to model, this
is where to look.

One caveat for anyone building a reference from it: CALCE is the testing
laboratory, not the manufacturer. Several of its cells carry CALCE's own
sample designations rather than manufacturer model numbers, and the pages do
not name the makers. Excellent test data attached to partly anonymous cells.

---

## Bulk cycling datasets

Registered in `tools/ingest_open_dataset.py`, which builds the provenance
spine and walks files through `tools/cyclers.py`. Landing pages rather than
file URLs, because published datasets move their files.

| Key | Source | Notes |
|---|---|---|
| `severson-2019` | Toyota Research Institute / MIT / Stanford | 124 cells, fast-charge policies vary per cell |
| `oxford-2017` | University of Oxford | Drive-cycle ageing with periodic characterisation |
| `nasa-pcoe` | NASA Ames | Includes EIS sweeps; those belong in `eis_spectrum` |
| `calce` | University of Maryland | Five cell types at different capacities |
| `batteryarchive` | Battery Archive contributors | Aggregator; cite the originating laboratory |

    python tools/ingest_open_dataset.py list

Licence fields in that registry are a **starting point, not a ruling**. Verify
at the landing page before redistributing anything.

---

## What this repository does reproduce

Extracted facts from manufacturer specifications, each carrying its
measurement conditions, a page number and a verbatim quote, under
`contrib/cells/`. A number without its conditions is not a fact, and the
validator refuses it:

    python tools/validate_contrib.py contrib/
