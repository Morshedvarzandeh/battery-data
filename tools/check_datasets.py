#!/usr/bin/env python3
"""Check the published per-cycle dataset values under datasets/.

datasets/<key>/ holds values computed from an open dataset: one row per cycle,
never the raw time series. A dataset whose licence lets them be redistributed
(CC BY 4.0 for XJTU) says `redistributable: true`; one that states no licence
(CALCE) says `redistributable: false` and must carry a `publication_basis`
saying why its computed values are published and that its files are not.
The raw files stay where their publisher keeps them; the manifest
names each one with its byte count and SHA-256, so the values can be traced to
the exact file they came from and recomputed with the import tools.

This check refuses a dataset folder when:
- its manifest lacks the licence, attribution, source files or column units;
- the dataset is not in tools/ingest_open_dataset.py, or is not redistributable
  and gives no publication_basis;
- a file's bytes, SHA-256 or row count differ from the manifest;
- the CSV header differs from the manifest's columns;
- a row names a cell with no source file, or the per-cell cycle counts differ;
- a source file names a batch the manifest's batches do not describe;
- cycles are not numbered 1..n per cell, or a number is not finite;
- a capacity is negative or above 1.5 times the nominal capacity, unless the
  manifest's `exceptions` names that cell, cycle, column and value with a
  reason (a listed exception that no longer occurs is refused too).

    python tools/check_datasets.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS = os.path.join(ROOT, "datasets")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ingest_open_dataset as ingest  # noqa: E402

REQUIRED = ("dataset", "title", "citation", "license", "attribution", "redistributable",
            "retrieved_at", "product_uid", "source_files", "columns", "files", "cells")
NUMERIC = ("charge_ah", "discharge_ah", "charge_ah_reported", "discharge_ah_reported",
           "coulombic_efficiency", "v_max", "v_min", "duration_s", "start_test_time_s")


def check_folder(folder: str) -> list[str]:
    errs: list[str] = []
    name = os.path.basename(folder)
    path = os.path.join(folder, "manifest.json")
    if not os.path.exists(path):
        return [f"{name}: no manifest.json"]
    m = json.load(open(path, encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in m]
    if missing:
        return [f"{name}: manifest lacks {missing}"]
    if m["dataset"] != name:
        errs.append(f"{name}: manifest names dataset {m['dataset']!r}")
    if m["dataset"] not in ingest.DATASETS:
        errs.append(f"{name}: not a registered dataset in tools/ingest_open_dataset.py")
    if m["redistributable"] is not True and not str(m.get("publication_basis") or "").strip():
        errs.append(f"{name}: not redistributable and no publication_basis says why its values are published")
    for col, spec in m["columns"].items():
        if "unit" not in spec or "meaning" not in spec:
            errs.append(f"{name}: column {col} needs a unit (null if none) and a meaning")
    sources = {os.path.splitext(os.path.basename(f["path"]))[0]: f for f in m["source_files"]}
    for f in m["source_files"]:
        if "batch" in f and f["batch"] not in m.get("batches", {}):
            errs.append(f"{name}: source file {f['path']} names batch {f['batch']!r}, which batches does not describe")
    for f in m["source_files"]:
        if len(f.get("sha256", "")) != 64 or not isinstance(f.get("bytes"), int):
            errs.append(f"{name}: source file {f.get('path')} needs bytes and a SHA-256")
    nominal = m["cells"].get("nominal_capacity_ah")
    allowed = {}
    for x in m.get("exceptions", []):
        if not str(x.get("reason") or "").strip():
            errs.append(f"{name}: exception {x.get('cell')} cycle {x.get('cycle')} gives no reason")
        allowed[(x.get("cell"), int(x.get("cycle", 0)), x.get("column"))] = x.get("value")
    used = set()
    for fname, spec in m["files"].items():
        fpath = os.path.join(folder, fname)
        if not os.path.exists(fpath):
            errs.append(f"{name}: {fname} is missing")
            continue
        raw = open(fpath, "rb").read()
        if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            errs.append(f"{name}: {fname} SHA-256 differs from the manifest")
        if b"\r" in raw:
            errs.append(f"{name}: {fname} has CR line endings")
        rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
        if len(rows) != spec["rows"]:
            errs.append(f"{name}: {fname} has {len(rows)} rows, manifest says {spec['rows']}")
        if rows and list(rows[0].keys()) != list(m["columns"].keys()):
            errs.append(f"{name}: {fname} columns {list(rows[0].keys())} differ from the manifest")
            continue
        seen = defaultdict(list)
        for i, r in enumerate(rows, start=2):
            if r["cell"] not in sources:
                errs.append(f"{name}: {fname}:{i} cell {r['cell']} has no source file")
                continue
            seen[r["cell"]].append(int(r["cycle"]))
            for col in NUMERIC:
                if col not in r or r[col] == "":
                    continue
                v = float(r[col])
                if not math.isfinite(v):
                    errs.append(f"{name}: {fname}:{i} {col} is not finite")
                elif col.endswith("_ah") or col.endswith("_ah_reported"):
                    if v < 0 or (nominal and v > 1.5 * nominal):
                        key = (r["cell"], int(r["cycle"]), col)
                        if key in allowed and allowed[key] == v:
                            used.add(key)
                        else:
                            errs.append(f"{name}: {fname}:{i} {col}={v} outside 0..1.5 x nominal")
        counts = Counter({c: len(v) for c, v in seen.items()})
        for cell, f in sources.items():
            if f.get("cycles") != counts.get(cell, 0):
                errs.append(f"{name}: {cell} has {counts.get(cell, 0)} cycles, manifest says {f.get('cycles')}")
        for cell, cyc in seen.items():
            if cyc != list(range(1, len(cyc) + 1)):
                errs.append(f"{name}: {cell} cycles are not numbered 1..{len(cyc)} in order")
    for key in sorted(set(allowed) - used):
        errs.append(f"{name}: exception {key[0]} cycle {key[1]} {key[2]} does not occur")
    return errs


def main() -> int:
    folders = sorted(os.path.join(DATASETS, d) for d in os.listdir(DATASETS)
                     if os.path.isdir(os.path.join(DATASETS, d)))
    errs = [e for f in folders for e in check_folder(f)]
    for e in errs:
        print(e)
    print(f"{len(folders)} dataset(s), {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
