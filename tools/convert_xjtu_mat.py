#!/usr/bin/env python3
"""
Convert XJTU battery-dataset .mat files to BDF CSV for tools/cyclers.py.

The XJTU dataset (Wang et al., Nature Communications 15, 4332, 2024;
zenodo.org/records/10963339) ships one MATLAB file per cell with two
variables:

  data     1 x N struct array, one element per cycle, with the fields
           system_time, relative_time_min, voltage_V, current_A,
           capacity_Ah, power_Wh, temperature_C, description
  summary  per-cell struct; element 8 is the cycle life, element 9 a
           description of the cell's test strategy

That layout comes from the authors' own loader (XJTUBatteryClass.py in
github.com/wang-fujin/Battery-dataset-preprocessing-code-library). Fields
are read by name when the file carries names, and by that order when it
does not.

One .mat in, two files out:

  <cell>.csv          test_time_second, voltage_volt, current_ampere,
                      cycle_count, temperature_t1_celsius
  <cell>.cycles.json  the per-cycle 'description' labels and the summary

No unix_time_second column: the dataset does not state the logger's time
zone, so system_time is used only for elapsed time.

Choices made on purpose:

- capacity_Ah is not carried into the CSV. The publisher does not say
  whether it is per step, signed or cumulative. cyclers.summarise_cycles
  integrates current itself, and a mislabelled capacity column would
  mislead its current-sign detector. With no capacity column the sign
  falls back to the BDF charge-positive default, and cyclers records that
  fallback as a warning on the test run, which is the honest outcome.
- temperature_C goes to temperature_t1_celsius, not ambient: the dataset
  does not say where the sensor sits.
- The 'description' labels go to the sidecar so the 'test capacity'
  cycles of batches 4-6 stay identifiable. cyclers does not read them.
- Test time is made continuous. If system_time parses as a timestamp it
  is used, which keeps the rests between cycles. Otherwise each cycle's
  relative time is shifted to start one sample after the previous cycle
  ended, and the real gap is unknown; the sidecar says which happened.

Written against the published loader, not yet run on the released files.
Run 'plan' on the output before the first real ingest.

    python tools/convert_xjtu_mat.py ~/data/xjtu/Batch-1/ --out ~/data/xjtu-csv/
    python tools/ingest_open_dataset.py plan xjtu-2024 ~/data/xjtu-csv/
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

DATA_FIELDS = ["system_time", "relative_time_min", "voltage_V", "current_A",
               "capacity_Ah", "power_Wh", "temperature_C", "description"]

# MATLAB datenum of 1970-01-01. A day count in this range is unambiguous.
_DATENUM_EPOCH = 719529.0
_DATENUM_RANGE = (693962.0, 767011.0)          # years 1900 to 2100


def _field(element, name: str):
    """One field of one struct element, by name if present, else by order."""
    names = getattr(getattr(element, "dtype", None), "names", None)
    if names and name in names:
        return element[name]
    return element[DATA_FIELDS.index(name)]


def _vector(value):
    import numpy as np
    arr = np.asarray(value)
    if arr.dtype == object:
        arr = np.asarray([np.asarray(v).ravel()[0] if np.asarray(v).size else None
                          for v in arr.ravel()], dtype=object)
    return arr.ravel()


def _text(value) -> str:
    import numpy as np
    arr = np.asarray(value).ravel()
    if arr.size == 0:
        return ""
    first = arr[0]
    if isinstance(first, np.ndarray):
        return _text(first)
    return str(first).strip()


def _clock_seconds(raw):
    """
    system_time as seconds on the logger's own clock, or None if it does not
    parse. Only differences are used: the time zone is not stated, so no
    absolute Unix time is written.
    """
    import numpy as np
    import pandas as pd
    arr = _vector(raw)
    if arr.size == 0:
        return None
    if arr.dtype.kind in "iuf":
        vals = arr.astype(float)
        lo, hi = _DATENUM_RANGE
        if np.all(np.isfinite(vals)) and vals.min() > lo and vals.max() < hi:
            return (vals - _DATENUM_EPOCH) * 86400.0
        return None
    parsed = pd.to_datetime(pd.Series([str(v).strip() for v in arr]),
                            errors="coerce")
    if parsed.isna().mean() > 0.01:
        return None
    return (parsed - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy(dtype=float)


def convert(path: str, out_dir: str) -> dict:
    import numpy as np
    import pandas as pd
    from scipy.io import loadmat

    mat = loadmat(path)
    if "data" not in mat:
        raise ValueError(f"{path}: no 'data' variable; not an XJTU cell file")
    data = mat["data"]
    cycles = data.ravel()

    frames, labels = [], []
    clocks = [_clock_seconds(_field(e, "system_time")) for e in cycles]
    use_clock = all(c is not None for c in clocks)

    last_end, step = None, 1.0
    for i, element in enumerate(cycles, start=1):
        rel_s = _vector(_field(element, "relative_time_min")).astype(float) * 60.0
        frame = pd.DataFrame({
            "voltage_volt": _vector(_field(element, "voltage_V")).astype(float),
            "current_ampere": _vector(_field(element, "current_A")).astype(float),
            "cycle_count": i,
            "temperature_t1_celsius": _vector(_field(element, "temperature_C")).astype(float),
        })
        if use_clock:
            frame["test_time_second"] = clocks[i - 1]
        else:
            if rel_s.size > 1:
                d = float(np.nanmedian(np.diff(rel_s)))
                if np.isfinite(d) and d > 0:
                    step = d
            # Relative time either restarts each cycle or runs on; only a
            # restart needs shifting.
            offset = 0.0
            if last_end is not None and rel_s.size and rel_s[0] <= last_end:
                offset = last_end - rel_s[0] + step
            frame["test_time_second"] = rel_s + offset
            if rel_s.size:
                last_end = float(rel_s[-1] + offset)
        frames.append(frame)
        labels.append({"cycle_count": i, "description": _text(_field(element, "description")),
                       "rows": int(len(frame))})

    table = pd.concat(frames, ignore_index=True)
    if use_clock:
        table["test_time_second"] -= table["test_time_second"].iloc[0]
    table = table[["test_time_second", "voltage_volt", "current_ampere", "cycle_count",
                   "temperature_t1_celsius"]]

    summary = {}
    if "summary" in mat:
        s = mat["summary"].ravel()[0]
        try:
            summary["cycle_life"] = int(np.asarray(s[8]).ravel()[0])
        except (IndexError, TypeError, ValueError):
            pass
        try:
            summary["description"] = _text(s[9])
        except (IndexError, TypeError):
            pass

    stem = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, stem + ".csv")
    table.to_csv(csv_path, index=False)
    sidecar = {
        "source_file": os.path.basename(path),
        "time_basis": "system_time" if use_clock else
                      "relative_time_min, cycles joined end to end; real gaps unknown",
        "summary": summary,
        "cycles": labels,
    }
    with open(os.path.join(out_dir, stem + ".cycles.json"), "w") as fh:
        json.dump(sidecar, fh, indent=2, ensure_ascii=False)
    return {"csv": csv_path, "rows": int(len(table)), "cycles": len(labels),
            "time_basis": sidecar["time_basis"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="convert_xjtu_mat", description=__doc__.split("\n")[1])
    ap.add_argument("path", help="a .mat file, or a directory searched recursively")
    ap.add_argument("--out", required=True, help="directory for the CSV and sidecar files")
    a = ap.parse_args(argv)

    files = [a.path] if os.path.isfile(a.path) else sorted(
        glob.glob(os.path.join(a.path, "**", "*.mat"), recursive=True))
    if not files:
        print(f"no .mat files under {a.path}", file=sys.stderr)
        return 1
    failed = 0
    for p in files:
        try:
            r = convert(p, a.out)
            print(f"{os.path.basename(p):32} {r['cycles']:5} cycles {r['rows']:10} rows  "
                  f"time: {r['time_basis'].split(',')[0]}")
        except Exception as exc:                                  # noqa: BLE001
            failed += 1
            print(f"{os.path.basename(p):32} FAILED: {exc}", file=sys.stderr)
    print(f"\n{len(files) - failed}/{len(files)} converted into {a.out}")
    print(f"next:  python tools/ingest_open_dataset.py plan xjtu-2024 {a.out}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
