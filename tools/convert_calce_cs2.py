#!/usr/bin/env python3
"""
Convert one CALCE CS2 cell's session files into a single BDF CSV for
tools/cyclers.py.

CALCE publishes each CS2 cell as a folder of session files, one per stretch
of testing, named <cell>_<month>_<day>_<yy>:

  Arbin (most cells)   .xlsx, one or more 'Channel_*' sheets with
                       Test_Time(s), Date_Time, Step_Index, Cycle_Index,
                       Current(A), Voltage(V), Charge_Capacity(Ah),
                       Discharge_Capacity(Ah) and more
  CADEX (CS2_8, 21)    tab-separated .txt with Time (minutes), mV, mA,
                       Pgm step, Pgm cycle and a 'Capacity' in percent

What a session file is not: a continuation of the previous one. Test time
and cycle index restart in every file, sessions are days apart, and the
same session is sometimes exported twice under two names (CS2_35_2_4_11
and CS2_35_2_10_11 are identical). Concatenating the files as they are
double-counts cycles and runs time backwards. So, per cell:

- Sessions are ordered by their first timestamp (Arbin) or by the date in
  the file name (CADEX).
- An exact repeat of an earlier session is dropped; rows of a later
  session that fall inside an earlier one's time span are trimmed. CADEX
  files are progressive snapshots of one running test, each repeating the
  earlier ones from the start, so each chain collapses to its longest
  file. The sidecar lists every session and what was done with it.
- Arbin sessions are placed on one time axis by Date_Time, with the finer
  Test_Time inside each session. CADEX files carry no clock, so their
  sessions are joined end to end and the real gaps are unknown.
- Arbin cycle_count and step_count run on across sessions (each session's
  own numbering plus the running offset). CADEX numbers positions in the
  test program instead, so those cells get cycles derived from current only.

One cell in, two files out:

  <cell>.csv           test_time_second, voltage_volt, current_ampere,
                       and for Arbin cells cycle_count, step_count,
                       charging_capacity_ah, discharging_capacity_ah
  <cell>.sessions.json what each session file contributed

The CADEX 'Capacity' column is a percentage, not a charge, so it is not
carried; cycle capacity is integrated from current either way.

    python tools/convert_calce_cs2.py ~/data/calce/CS2_35/ --out ~/data/calce-csv/
    python tools/ingest_open_dataset.py plan calce ~/data/calce-csv/
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import sys

_NAME_DATE = re.compile(r"_(\d{1,2})_(\d{1,2})_(\d{2})$")

ARBIN_COLUMNS = {
    "Test_Time(s)": "test_time_s",
    "Date_Time": "date_time",
    "Step_Index": "step_index",
    "Cycle_Index": "cycle_index",
    "Current(A)": "current_a",
    "Voltage(V)": "voltage_v",
    "Charge_Capacity(Ah)": "charge_ah",
    "Discharge_Capacity(Ah)": "discharge_ah",
}


def name_date(path: str) -> _dt.date | None:
    """The date in a CALCE session file name: CS2_35_10_15_10 -> 2010-10-15."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = _NAME_DATE.search(stem)
    if not m:
        return None
    month, day, yy = (int(g) for g in m.groups())
    try:
        return _dt.date(2000 + yy, month, day)
    except ValueError:
        return None


def _excel_engine() -> str | None:
    try:
        import python_calamine  # noqa: F401
        return "calamine"         # about ten times faster than openpyxl here
    except ImportError:
        return None


def read_arbin(path: str):
    """All 'Channel' sheets of one Arbin workbook, in sheet order."""
    import pandas as pd
    frames = []
    with pd.ExcelFile(path, engine=_excel_engine()) as book:
        sheets = [s for s in book.sheet_names if s.lower().startswith("channel")]
        if not sheets:
            raise ValueError(f"{path}: no Channel sheet")
        for s in sheets:
            df = book.parse(s)
            missing = [c for c in ("Test_Time(s)", "Date_Time", "Current(A)", "Voltage(V)") if c not in df]
            if missing:
                raise ValueError(f"{path} [{s}]: missing {missing}")
            frames.append(df[[c for c in ARBIN_COLUMNS if c in df]].rename(columns=ARBIN_COLUMNS))
    df = pd.concat(frames, ignore_index=True)
    df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")
    return df


def read_cadex(path: str):
    """
    One CADEX tab-separated export; time in minutes, current and voltage in mA
    and mV. 'Pgm cycle' and 'Pgm step' count positions in the test program,
    not cycles, so they are not carried; cycles are derived from current.
    """
    import pandas as pd
    raw = pd.read_csv(path, sep="\t")
    raw = raw.loc[:, ~raw.columns.str.startswith("Unnamed")]
    missing = [c for c in ("Time", "mV", "mA") if c not in raw]
    if missing:
        raise ValueError(f"{path}: missing {missing}")
    return pd.DataFrame({
        "test_time_s": pd.to_numeric(raw["Time"], errors="coerce") * 60.0,
        "voltage_v": pd.to_numeric(raw["mV"], errors="coerce") / 1000.0,
        "current_a": pd.to_numeric(raw["mA"], errors="coerce") / 1000.0,
    })


def read_session(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return read_arbin(path), "arbin"
    if ext == ".txt":
        return read_cadex(path), "cadex"
    raise ValueError(f"{path}: not an Arbin workbook or CADEX export")


def _fingerprint(df) -> str:
    """Same rows, same values, same clock: a repeat export of one session."""
    import numpy as np
    cols = [c for c in ("test_time_s", "voltage_v", "current_a") if c in df]
    h = hashlib.sha256(np.ascontiguousarray(df[cols].to_numpy(dtype=float)).tobytes())
    if "date_time" in df:
        h.update(np.ascontiguousarray(df["date_time"].to_numpy(dtype="datetime64[s]").astype("int64")).tobytes())
    return h.hexdigest()


def _snapshot_drops(loaded) -> dict:
    """
    CADEX files are progressive snapshots of one running test: each later
    export repeats the earlier ones from the start (CS2_8_4_8_10 holds all
    of CS2_8_4_5_10 and more). Joined end to end they would count most of
    the data two or three times. Each chain collapses to its longest file;
    returns {file: reason} for the files dropped.
    """
    import numpy as np
    cols = ["test_time_s", "voltage_v", "current_a"]
    drops, last = {}, None
    for f, df, _k in loaded:
        if last is not None and len(df):
            lf, ldf = last
            n = min(len(ldf), len(df))
            if n and np.allclose(ldf[cols].iloc[:n].to_numpy(dtype=float),
                                 df[cols].iloc[:n].to_numpy(dtype=float), rtol=0, atol=1e-9):
                if len(df) >= len(ldf):
                    drops[os.path.basename(lf)] = "dropped: earlier snapshot of " + os.path.basename(f)
                    last = (f, df)
                else:
                    drops[os.path.basename(f)] = "dropped: shorter copy of " + os.path.basename(lf)
                continue
        if len(df):
            last = (f, df)
    return drops


def session_files(cell_dir: str) -> list[str]:
    files = [f for f in glob.glob(os.path.join(cell_dir, "*"))
             if os.path.splitext(f)[1].lower() in (".xlsx", ".xls", ".txt")]
    return sorted(files, key=lambda f: (name_date(f) or _dt.date.max, os.path.basename(f)))


def merge_cell(files: list[str]):
    """Read and merge one cell's sessions; returns (table, sessions log)."""
    import numpy as np
    import pandas as pd

    loaded = []
    for f in files:
        df, kind = read_session(f)
        df = df.dropna(subset=["test_time_s", "voltage_v", "current_a"]).reset_index(drop=True)
        if kind == "arbin":
            df["date_time"] = df["date_time"].ffill().bfill()
        loaded.append((f, df, kind))
    kinds = {k for _, _, k in loaded}
    if len(kinds) > 1:
        raise ValueError(f"mixed session formats in one cell: {sorted(kinds)}")
    kind = kinds.pop() if kinds else None
    if kind == "arbin":
        # A file's name date is when it was exported; its first timestamp is
        # when the session ran.
        loaded.sort(key=lambda x: (x[1]["date_time"].min() if len(x[1]) else pd.Timestamp.max,
                                   os.path.basename(x[0])))

    drops = _snapshot_drops(loaded) if kind == "cadex" else {}

    frames, log, seen = [], [], {}
    clock0, last_clock_end, last_end, step = None, None, None, 1.0
    cyc_off, step_off = 0, 0
    for f, df, _k in loaded:
        entry = {"file": os.path.basename(f), "rows_in": int(len(df))}
        if entry["file"] in drops:
            entry.update(action=drops[entry["file"]], rows_kept=0)
            log.append(entry)
            continue
        if df.empty:
            entry.update(action="empty", rows_kept=0)
            log.append(entry)
            continue
        fp = _fingerprint(df)
        if fp in seen:
            entry.update(action="dropped: identical to " + seen[fp], rows_kept=0)
            log.append(entry)
            continue
        seen[fp] = entry["file"]

        if kind == "arbin" and last_clock_end is not None:
            keep = (df["date_time"] > last_clock_end).to_numpy()
            if not keep.all():
                entry["trimmed_overlap_rows"] = int((~keep).sum())
                df = df[keep].reset_index(drop=True)
                if df.empty:
                    entry.update(action="dropped: inside an earlier session", rows_kept=0)
                    log.append(entry)
                    continue

        rel = df["test_time_s"].to_numpy(dtype=float)
        forward = np.diff(rel)
        forward = forward[forward > 0]
        if forward.size:
            step = float(np.median(forward))

        if kind == "arbin":
            clock = df["date_time"]
            if clock0 is None:
                clock0 = clock.iloc[0]
            t = rel - rel[0] + (clock.iloc[0] - clock0).total_seconds()
            entry["start"], entry["end"] = str(clock.iloc[0]), str(clock.iloc[-1])
            last_clock_end = clock.iloc[-1]
        else:
            t = rel - rel[0] + (0.0 if last_end is None else last_end + step)
        # Never run backwards: the logger clock is whole seconds.
        if last_end is not None and t[0] <= last_end:
            t = t + (last_end - t[0] + step)

        out = pd.DataFrame({"test_time_second": t,
                            "voltage_volt": df["voltage_v"].to_numpy(dtype=float),
                            "current_ampere": df["current_a"].to_numpy(dtype=float)})
        if kind == "arbin":
            for src, dst, off in (("cycle_index", "cycle_count", cyc_off),
                                  ("step_index", "step_count", step_off)):
                if src in df and df[src].notna().any():
                    v = df[src].to_numpy(dtype=float)
                    out[dst] = v - np.nanmin(v) + 1 + off
            for src, dst in (("charge_ah", "charging_capacity_ah"),
                             ("discharge_ah", "discharging_capacity_ah")):
                if src in df:
                    out[dst] = df[src].to_numpy(dtype=float)
            if "cycle_count" in out:
                cyc_off = int(np.nanmax(out["cycle_count"]))
            if "step_count" in out:
                step_off = int(np.nanmax(out["step_count"]))
        last_end = float(t[-1])
        entry.update(action="kept", rows_kept=int(len(out)))
        frames.append(out)
        log.append(entry)

    if not frames:
        raise ValueError("no usable sessions")
    table = pd.concat(frames, ignore_index=True)
    sessions = {"format": kind,
                "time_basis": ("Date_Time places each session; Test_Time within it" if kind == "arbin"
                               else "sessions joined end to end; real gaps unknown"),
                "sessions": log}
    return table, sessions


def convert(cell_dir: str, out_dir: str) -> dict:
    cell = os.path.basename(os.path.normpath(cell_dir))
    table, sessions = merge_cell(session_files(cell_dir))
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, cell + ".csv")
    table.to_csv(csv_path, index=False)
    sessions["cell"] = cell
    with open(os.path.join(out_dir, cell + ".sessions.json"), "w") as fh:
        json.dump(sessions, fh, indent=2)
    kept = sum(1 for s in sessions["sessions"] if s.get("action") == "kept")
    return {"csv": csv_path, "rows": int(len(table)), "sessions": len(sessions["sessions"]),
            "kept": kept, "format": sessions["format"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="convert_calce_cs2", description=__doc__.split("\n")[1])
    ap.add_argument("path", nargs="+", help="one or more cell folders (CS2_35/ ...)")
    ap.add_argument("--out", required=True, help="directory for the CSV and sessions files")
    a = ap.parse_args(argv)
    failed = 0
    for p in a.path:
        try:
            r = convert(p, a.out)
            print(f"{os.path.basename(os.path.normpath(p)):10} {r['format']:6} "
                  f"{r['kept']}/{r['sessions']} sessions kept  {r['rows']} rows")
        except Exception as exc:                                  # noqa: BLE001
            failed += 1
            print(f"{p}: FAILED: {exc}", file=sys.stderr)
    print(f"next:  python tools/ingest_open_dataset.py plan calce {a.out}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
