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
- Test time is made continuous. Within a cycle, relative_time_min sets the
  spacing (it is finer than the 1 s clock). If system_time parses, it
  places each cycle's start, which keeps the rests between cycles.
  Otherwise each cycle starts one sample after the previous one ended, and
  the real gap is unknown. The sidecar says which happened.
- The file's own per-cycle charge and discharge capacities go into the
  sidecar next to each label, so integrated values can be checked.

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


# The released files write '2022-09-16,15:05:22'. That comma defeats pandas'
# format inference, which then falls back to a slow per-value parser and
# still fails, so known layouts are tried explicitly.
_CLOCK_FORMATS = ("%Y-%m-%d,%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
                  "%Y-%m-%dT%H:%M:%S")


def _cycle_start_clock(raw):
    """
    The first system_time of a cycle as seconds on the logger's clock, or
    None if it does not parse. Only differences between cycle starts are
    used: the time zone is not stated, so no absolute Unix time is written.
    """
    import datetime as dt
    import numpy as np
    arr = _vector(raw)
    if arr.size == 0:
        return None
    first = arr[0]
    if isinstance(first, (int, float, np.integer, np.floating)):
        lo, hi = _DATENUM_RANGE
        v = float(first)
        return (v - _DATENUM_EPOCH) * 86400.0 if lo < v < hi else None
    text = str(first).strip()
    for fmt in _CLOCK_FORMATS:
        try:
            return (dt.datetime.strptime(text, fmt) - dt.datetime(1970, 1, 1)).total_seconds()
        except ValueError:
            continue
    return None


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
    # Within a cycle, relative_time_min is finer than the 1 s wall clock, so it
    # sets the sample spacing. The clock only places each cycle's start, which
    # keeps the rests between cycles.
    starts = [_cycle_start_clock(_field(e, "system_time")) for e in cycles]
    use_clock = all(s is not None for s in starts)

    last_end, step = None, 1.0
    for i, element in enumerate(cycles, start=1):
        rel_s = _vector(_field(element, "relative_time_min")).astype(float) * 60.0
        frame = pd.DataFrame({
            "voltage_volt": _vector(_field(element, "voltage_V")).astype(float),
            "current_ampere": _vector(_field(element, "current_A")).astype(float),
            "cycle_count": i,
            "temperature_t1_celsius": _vector(_field(element, "temperature_C")).astype(float),
        })
        if rel_s.size > 1:
            d = float(np.nanmedian(np.diff(rel_s)))
            if np.isfinite(d) and d > 0:
                step = d
        if use_clock and rel_s.size:
            t = (starts[i - 1] - starts[0]) + (rel_s - rel_s[0])
            # A cycle cannot start before the last one ended; the 1 s clock
            # can say it does by a sample.
            if last_end is not None and t[0] <= last_end:
                t = t + (last_end - t[0] + step)
        else:
            # Relative time either restarts each cycle or runs on; only a
            # restart needs shifting.
            offset = 0.0
            if last_end is not None and rel_s.size and rel_s[0] <= last_end:
                offset = last_end - rel_s[0] + step
            t = rel_s + offset
        frame["test_time_second"] = t
        if rel_s.size:
            last_end = float(t[-1])
        frames.append(frame)
        labels.append({"cycle_count": i, "description": _text(_field(element, "description")),
                       "rows": int(len(frame))})

    table = pd.concat(frames, ignore_index=True)
    table = table[["test_time_second", "voltage_volt", "current_ampere", "cycle_count",
                   "temperature_t1_celsius"]]

    summary = {}
    if "summary" in mat:
        s = mat["summary"].ravel()[0]
        names = getattr(s.dtype, "names", None) or ()
        try:
            summary["cycle_life"] = int(np.asarray(s[8]).ravel()[0])
        except (IndexError, TypeError, ValueError):
            pass
        try:
            summary["description"] = _text(s[9])
        except (IndexError, TypeError):
            pass
        # The file's own per-cycle capacities, kept beside each label so the
        # integrated values can be checked against what the lab reported.
        for name in ("charge_capacity_Ah", "discharge_capacity_Ah"):
            if name in names:
                vals = np.asarray(s[name], dtype=float).ravel()
                key = "reported_" + name.lower()
                for lab, v in zip(labels, vals):
                    lab[key] = None if not np.isfinite(v) else round(float(v), 6)

    stem = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, stem + ".csv")
    table.to_csv(csv_path, index=False)
    sidecar = {
        "source_file": os.path.basename(path),
        "time_basis": "system_time for cycle starts; relative_time_min within cycles" if use_clock else
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
                  f"time: {r['time_basis'].split(' ')[0]}")
        except Exception as exc:                                  # noqa: BLE001
            failed += 1
            print(f"{os.path.basename(p):32} FAILED: {exc}", file=sys.stderr)
    print(f"\n{len(files) - failed}/{len(files)} converted into {a.out}")
    print(f"next:  python tools/ingest_open_dataset.py plan xjtu-2024 {a.out}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
