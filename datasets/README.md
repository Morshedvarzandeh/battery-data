# Published dataset values

One folder per open dataset whose licence allows its values to be shared.
Each holds the **per-cycle values** computed from the dataset, one row per
cycle, and a `manifest.json` that says where they came from. The raw files
(time series, `.mat`, `.xlsx`) stay with their publisher and are named in the
manifest by path, byte count and SHA-256, so every row can be traced to the
file it came from and recomputed with the import tools.

This follows the repository's rule: the facts, plus a URL, a hash and a
retrieval date, never the source body. Graphs are drawn by the website
dashboard and the API from these values; no chart is stored here.

| Folder | Dataset | Cells | Cycles | Licence |
|---|---|---|---|---|
| `xjtu-2024/` | XJTU battery degradation dataset (Wang et al., Nature Communications 2024; Zenodo 10963339) | 55 Lishen 18650 NMC523, 2.0 Ah | 27,642 | CC BY 4.0 |

**Using the values.** Credit the dataset as the manifest's `attribution`
says. Read the manifest's `caveats` before comparing capacities: in XJTU
Batches 4 to 6, only cycles labelled `[test capacity]` discharge fully.

**Not here.** CALCE publishes its data without a licence, so its values are
not redistributed; `tools/ingest_open_dataset.py` imports them for local use.

**Adding a dataset.** Register it in `tools/ingest_open_dataset.py`, import
it, and add a folder only if its licence permits redistribution. Then run
`python tools/check_datasets.py`, which refuses a folder whose files, hashes,
counts or columns differ from its manifest.
