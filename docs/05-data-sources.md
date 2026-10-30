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
the page. For the CS2 prismatic LCO cells (1.1 Ah), the set most often reused,
that is He, Williard, Osterman and Pecht, *Journal of Power Sources* 196(23),
10314–10321 (2011); the registry entry carries the two further articles CALCE
lists for CS2. The page states no licence.

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
| `calce` | University of Maryland | Five cell types (CS2, CX2, PL, INR18650-20R, A123); one type per run, read from the file names |
| `xjtu-2024` | Xi'an Jiaotong University | 55 Lishen 18650 NCM523 cells (2.0 Ah) in 6 batches, CC BY 4.0; `.mat`, convert first |
| `batteryarchive` | Battery Archive contributors | Aggregator; cite the originating laboratory |

    python tools/ingest_open_dataset.py list

### What an import stores

Data, as values: one product per cell type, one unit and one test run per
cell file, the run's segments, and one row of values per cycle with the
tester's own cycle number beside the defined one. No charts, plots or
reports are stored; the website dashboard and the API draw those from the
values.

- **Each run cites its own file.** Every file gets its own source location
  (file name and SHA-256) and provenance row, and its test run points there.
  Loading the same files again adds no location or provenance row; a run
  already loaded is refused by its uid instead of doubling its cycles.
- **One product per physical cell type.** A dataset with several cell types
  declares them in the registry (`cell_types`); the type is read from the
  file names, or given with `--cell-type`, and a run whose files are not all
  one type is refused. A dataset that names no single model (Battery Archive)
  needs `--model`, `--manufacturer` and `--nominal-ah` per batch.
- **A maker the dataset does not name** is recorded as `Maker not stated`,
  the same placeholder the contributions use, never as a company called
  "unstated". CALCE names no maker, so its CS2 cells are
  `cell/maker-not-stated/cs2`; XJTU names Lishen but no model number, so its
  cells are `cell/lishen/unstated`.

`plan` prints the product a run would be filed under before anything is
written.

XJTU ships MATLAB files, which the sniffer cannot read. Unzip the Zenodo
archive, convert, then plan and ingest as usual:

    python tools/convert_xjtu_mat.py ~/data/xjtu/ --out ~/data/xjtu-csv/
    python tools/ingest_open_dataset.py plan xjtu-2024 ~/data/xjtu-csv/
    python tools/ingest_open_dataset.py ingest xjtu-2024 ~/data/xjtu-csv/ --emit-sql xjtu.sql

CALCE ships each cell as a folder of session files. Time and cycle numbers
restart in every file and some sessions were exported twice, so each cell is
merged first:

    python tools/convert_calce_cs2.py ~/data/calce/CS2_35/ ~/data/calce/CS2_36/ --out ~/data/calce-csv/
    python tools/ingest_open_dataset.py plan calce ~/data/calce-csv/     # product: cell/maker-not-stated/cs2, cell type CS2

Batches 4–6 never discharge fully, so their per-cycle capacity is not a
capacity measurement. The converter keeps each cycle's label, including the
`test capacity` cycles that are, in a `.cycles.json` file next to each CSV.

Licence fields in that registry are a **starting point, not a ruling**. Verify
at the landing page before redistributing anything.

---

## What this repository does reproduce

Extracted facts from manufacturer specifications, each carrying its
measurement conditions, a page number and a verbatim quote, under
`contrib/cells/`. A number without its conditions is not a fact, and the
validator refuses it:

    python tools/validate_contrib.py contrib/

Per-cycle values computed from open datasets, under `datasets/` (one folder
per dataset, with a manifest naming each source file by path, byte count and
SHA-256): XJTU (CC BY 4.0; 55 cells, 27,642 cycles) and CALCE CS2 (no licence
stated, so computed values only, with the citation CALCE asks for and the
basis in the manifest; 15 cells, 35,424 cycles). The raw time series are not
reproduced. Datasets licensed for non-commercial use only, or whose licence is
unclear, are not used. See [datasets/README.md](../datasets/README.md);
`python tools/check_datasets.py` checks every folder against its manifest.
