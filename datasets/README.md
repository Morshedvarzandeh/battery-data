# Published dataset values

One folder per open dataset whose values are published. Each holds the
**per-cycle values** computed from the dataset, one row per cycle, and a `manifest.json` that says where they came from. The raw files
(time series, `.mat`, `.xlsx`) stay with their publisher and are named in the
manifest by path, byte count and SHA-256, so every row can be traced to the
file it came from and recomputed with the import tools.

This follows the repository's rule: the facts, plus a URL, a hash and a
retrieval date, never the source body. Graphs are drawn by the website
dashboard and the API from these values; no chart is stored here.

| Folder | Dataset | Cells | Cycles | Licence |
|---|---|---|---|---|
| `xjtu-2024/` | XJTU battery degradation dataset (Wang et al., Nature Communications 2024; Zenodo 10963339) | 55 Lishen 18650 NMC523, 2.0 Ah | 27,642 | CC BY 4.0 |
| `calce/` | CALCE CS2 cells (He et al., J. Power Sources 2011; calce.umd.edu/battery-data) | 15 prismatic LCO, 1.1 Ah | 35,424 | none stated: computed values only, see `publication_basis` |

**Using the values.** Credit the dataset as the manifest's `attribution`
says. Read the manifest's `caveats` before comparing capacities: in XJTU
Batches 4 to 6, only cycles labelled `[test capacity]` discharge fully; in
CALCE, a cycle discharges fully when `v_min` reaches 2.75 V or below, and two
cycles listed under `exceptions` hold two charges each.

**No licence stated.** CALCE publishes its data openly and asks for its
articles to be cited, but states no licence. Its raw files are therefore not
redistributed; the per-cycle values Lemonergy computed from them are, with the
citation, on the owner's instruction (`publication_basis` in the manifest).
They are withdrawn if CALCE asks.

**Not published.** Datasets licensed for non-commercial use only, or whose
licence is unclear, are not published or used (owner's decision, 30 October
2026).

**Adding a dataset.** Register it in `tools/ingest_open_dataset.py`, import
it, and add a folder only if its licence permits redistribution or it
states no licence and the manifest gives a `publication_basis`. Then run
`python tools/check_datasets.py`, which refuses a folder whose files, hashes,
counts or columns differ from its manifest.
