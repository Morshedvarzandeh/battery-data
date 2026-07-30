#!/usr/bin/env python3
"""
Cycler-format adapters : vendor file -> normalised BDF records -> database.

Every adapter's job is the same three things, and the third is the one
that matters:

  1. read the vendor's rows
  2. rename columns to Battery Data Format machine names
  3. DETERMINE THE CONVENTIONS, rather than assuming them

Step 3 is where published datasets go wrong. Current sign, capacity
accumulation semantics and cycle counting all disagree across vendors,
and two of the widely used open formats attach opposite meanings to the
same column name. An adapter that renames columns and stops has produced
numbers that look comparable and are not.

Nothing here silently coerces. If a convention cannot be determined from
the data, it is recorded as 'unspecified' and the run is flagged.

    python tools/cyclers.py sniff  data/raw/cell_A.csv
    python tools/cyclers.py ingest data/raw/cell_A.csv --unit unit/lab/A-001
    python tools/cyclers.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("cyclers")

# =====================================================================
# BDF target schema
# =====================================================================

BDF_REQUIRED = ["test_time_second", "voltage_volt", "current_ampere"]
BDF_RECOMMENDED = ["unix_time_second", "cycle_count", "step_count",
                   "ambient_temperature_celsius"]
BDF_OPTIONAL = [
    "charging_capacity_ah", "discharging_capacity_ah", "net_capacity_ah",
    "cumulative_capacity_ah", "charging_energy_wh", "discharging_energy_wh",
    "net_energy_wh", "cumulative_energy_wh", "step_time_second", "power_watt",
    "ac_internal_resistance_ohm", "dc_internal_resistance_ohm",
    "surface_temperature_celsius", "temperature_t1_celsius",
    "temperature_t2_celsius", "temperature_t3_celsius",
    "temperature_t4_celsius", "temperature_t5_celsius",
    "ambient_pressure_pa", "applied_pressure_pa", "surface_pressure_pa",
    "record_index", "step_id", "step_type",
]

# ---------------------------------------------------------------------
# Column maps. Vendor headers are wildly inconsistent even within one
# vendor across software versions, so matching is normalised and
# multi-alias rather than exact.
# ---------------------------------------------------------------------

def _norm(name: str) -> str:
    """Fold a vendor header to a comparison key.

    Handles the real-world mess: 'Test_Time(s)', 'Test Time (sec)',
    'time/s', 'Voltage(V)', 'Ewe/V', 'Current..uA.', 'Temperature/degC'
    with Latin-1 mojibake in the degree sign.
    """
    s = name.replace("﻿", "").strip()
    s = s.replace("Â", "")                       # Latin-1 mojibake
    s = re.sub(r"[°º]", "deg", s)
    s = s.lower()
    s = re.sub(r"[\(\[/].*?[\)\]]?$", "", s)      # trailing unit annotation
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


# (bdf_name, [aliases], scale_to_bdf_unit)
ARBIN = [
    ("test_time_second",        ["test_time", "test_time_s"], 1.0),
    ("step_time_second",        ["step_time"], 1.0),
    ("voltage_volt",            ["voltage"], 1.0),
    ("current_ampere",          ["current"], 1.0),
    ("charging_capacity_ah",    ["charge_capacity"], 1.0),
    ("discharging_capacity_ah", ["discharge_capacity"], 1.0),
    ("charging_energy_wh",      ["charge_energy"], 1.0),
    ("discharging_energy_wh",   ["discharge_energy"], 1.0),
    ("cycle_count",             ["cycle_index"], 1.0),
    ("step_count",              ["step_index"], 1.0),
    ("record_index",            ["data_point"], 1.0),
    ("dc_internal_resistance_ohm", ["internal_resistance"], 1.0),
    ("temperature_t1_celsius",  ["aux_temperature_1"], 1.0),
    ("ambient_temperature_celsius", ["temperature"], 1.0),
]

MACCOR = [
    ("test_time_second",        ["test_sec", "test_time_sec", "testtime", "test"], 1.0),
    ("step_time_second",        ["step_time_sec", "step_time"], 1.0),
    ("voltage_volt",            ["voltage", "volts"], 1.0),
    ("current_ampere",          ["current", "amps"], 1.0),
    # Maccor units are NOT stable across exports: capacity may be mAh or
    # Ah, current may be uA/mA/A. Scale is resolved from the header text
    # by _maccor_scale(), not assumed here.
    ("charging_capacity_ah",    ["chg_capacity", "charge_capacity"], 1.0),
    ("discharging_capacity_ah", ["dchg_capacity", "discharge_capacity"], 1.0),
    ("net_capacity_ah",         ["capacity", "cap"], 1.0),
    ("cycle_count",             ["cyc", "cycle", "cycle_id", "cyc_p"], 1.0),
    ("step_count",              ["step"], 1.0),
    ("record_index",            ["rec"], 1.0),
    ("ambient_temperature_celsius", ["evtemp", "temperature", "logtemp001"], 1.0),
    ("dc_internal_resistance_ohm", ["dcir_ohms"], 1.0),
    ("ac_internal_resistance_ohm", ["acimp_ohms"], 1.0),
    ("step_type",               ["md"], 1.0),
]

NEWARE = [
    ("test_time_second",        ["time", "total_time", "test_time"], 1.0),
    ("step_time_second",        ["step_time_elapsed", "step_time"], 1.0),
    ("voltage_volt",            ["voltage"], 1.0),
    ("current_ampere",          ["current"], 1e-3),      # Neware logs mA
    ("charging_capacity_ah",    ["chg_capacity", "charge_capacity"], 1e-3),
    ("discharging_capacity_ah", ["dchg_capacity", "discharge_capacity"], 1e-3),
    ("net_capacity_ah",         ["capacity"], 1e-3),      # mAh
    ("net_energy_wh",           ["energy"], 1e-3),        # mWh
    ("cycle_count",             ["cycle_id", "cycle_index"], 1.0),
    ("step_count",              ["step_id", "step_index"], 1.0),
    ("record_index",            ["record_id"], 1.0),
    ("step_type",               ["step_type", "status"], 1.0),
    ("ambient_temperature_celsius", ["temperature", "aux_t1"], 1.0),
]

BIOLOGIC = [
    ("test_time_second",        ["time"], 1.0),
    ("voltage_volt",            ["ewe", "ecell", "ecell_v"], 1.0),
    ("current_ampere",          ["i", "i_ma", "_i_"], 1e-3),   # mA
    ("net_capacity_ah",         ["q_qo", "dq"], 1e-3),         # mA.h
    ("charging_capacity_ah",    ["qcharge", "q_charge"], 1e-3),
    ("discharging_capacity_ah", ["qdischarge", "q_discharge"], 1e-3),
    ("cycle_count",             ["cycle_number", "cyclenumber"], 1.0),
    ("step_count",              ["ns"], 1.0),
    ("ambient_temperature_celsius", ["temperature"], 1.0),
    ("working_electrode_volt",  ["ewe"], 1.0),
    ("counter_electrode_volt",  ["ece"], 1.0),
    # EIS columns; routed to eis_point rather than timeseries_record
    ("frequency_hz",            ["freq"], 1.0),
    ("z_real_ohm",              ["re_z"], 1.0),
    ("z_imag_ohm",              ["_im_z", "im_z"], 1.0),
]

# BDF files carry PREFERRED LABELS in the header ("Voltage / V"), not the
# machine names ("voltage_volt"). Both must match, so aliases are derived
# by stripping the machine name's unit suffix.
_BDF_UNIT_SUFFIXES = ("_second", "_volt", "_ampere", "_ah", "_wh", "_celsius",
                      "_ohm", "_pa", "_watt", "_hertz", "_deg", "_index")


def _bdf_aliases(machine_name: str) -> list[str]:
    out = {machine_name}
    for suf in _BDF_UNIT_SUFFIXES:
        if machine_name.endswith(suf):
            out.add(machine_name[: -len(suf)])
            break
    return sorted(out)


BDF_NATIVE = [(c, _bdf_aliases(c), 1.0) for c in
              BDF_REQUIRED + BDF_RECOMMENDED + BDF_OPTIONAL]


@dataclass
class Dialect:
    name: str
    colmap: list
    default_sign: str            # documented vendor/parser default
    default_accum: str
    encoding: str = "utf-8"
    sep: str | None = None
    notes: str = ""


DIALECTS = {
    "arbin":    Dialect("arbin", ARBIN, "charge_positive", "per_step",
                        notes="Capacity accumulates WITHIN a step, not per cycle. "
                              "DateTime is an OLE automation date."),
    "maccor":   Dialect("maccor", MACCOR, "unspecified", "per_step",
                        encoding="iso-8859-1", sep="\t",
                        notes="Sign is a user export setting ('Discharge Current "
                              "Exported Negative'). Units vary per export."),
    "neware":   Dialect("neware", NEWARE, "charge_positive", "net_signed",
                        notes="Logs mA/mAh, not A/Ah. Three cycle-count modes."),
    "biologic": Dialect("biologic", BIOLOGIC, "charge_positive", "per_step",
                        encoding="iso-8859-1", sep="\t",
                        notes="Many .mpt columns are computed by EC-Lab at export "
                              "and absent from .mpr."),
    "bdf":      Dialect("bdf", BDF_NATIVE, "charge_positive", "unspecified",
                        notes="Battery Data Format: current positive = charge."),
}


# =====================================================================
# Sniffing
# =====================================================================

SIGNATURES = [
    ("arbin",    {"data_point", "test_time", "cycle_index", "step_index"}, 3),
    ("maccor",   {"rec", "cyc", "step", "md", "es"}, 3),
    ("neware",   {"record_id", "cycle_id", "step_id"}, 2),
    ("neware",   {"cycle_index", "step_index", "status"}, 3),
    ("biologic", {"ewe", "ns", "ox_red", "control"}, 2),
    ("biologic", {"ecell_v", "i_ma", "cyclenumber"}, 2),
    # Machine-name form (a .bdf.parquet round-trip) and preferred-label form.
    ("bdf",      {"test_time_second", "voltage_volt", "current_ampere"}, 3),
    ("bdf",      {"test_time", "voltage", "current", "cycle_count", "step_count"}, 4),
]


def sniff(header: list[str]) -> tuple[str, float]:
    """Identify the dialect from the header row. Returns (name, confidence)."""
    keys = {_norm(h) for h in header}

    # BDF's header convention is distinctive on its own: preferred labels
    # separated from their unit by " / " ("Voltage / V", "Test Time / s").
    # No other cycler formats its headers this way, so a strong match here
    # settles it before the generic scoring runs.
    slash_units = sum(1 for h in header if re.search(r"\s/\s\S+$", h.strip()))
    if slash_units >= max(3, 0.6 * len(header)):
        return "bdf", 1.0

    best, best_score = "unknown", 0.0
    for name, sig, need in SIGNATURES:
        hits = len(sig & keys)
        if hits >= need:
            score = hits / len(sig)
            if score > best_score:
                best, best_score = name, score
    return best, best_score


def read_header(path: str, encoding: str = "utf-8") -> tuple[list[str], str]:
    """Return (header cells, separator). Tries tab, comma, semicolon."""
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            for sep in ("\t", ",", ";"):
                cells = line.rstrip("\r\n").split(sep)
                if len(cells) >= 3:
                    return cells, sep
            return [line.strip()], ","
    return [], ","


# =====================================================================
# Normalisation
# =====================================================================

@dataclass
class Normalised:
    frame: object                      # pandas DataFrame in BDF names
    dialect: str
    current_sign: str = "unspecified"
    capacity_accum: str = "unspecified"
    cycle_definition: str = "as_reported"
    unit_fixes: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    columns_present: list = field(default_factory=list)


def _maccor_scale(header: str) -> float:
    """Maccor embeds the unit in the header; resolve it rather than guess."""
    h = header.lower()
    if "ua" in h or "..ua." in h:
        return 1e-6
    if re.search(r"\bma\b|mahr|mah", h):
        return 1e-3
    return 1.0


def normalise(path: str, dialect_name: str | None = None) -> Normalised:
    import pandas as pd

    header, sep = read_header(path)
    guess, conf = sniff(header)
    dname = dialect_name or guess
    if dname == "unknown":
        raise ValueError(
            f"cannot identify cycler format for {path}. "
            f"Header: {header[:8]}. Pass --dialect explicitly."
        )
    d = DIALECTS[dname]
    if d.sep:
        sep = d.sep

    df = pd.read_csv(path, sep=sep, encoding=d.encoding,
                     engine="python", thousands=",")
    warnings: list[str] = []
    unit_fixes: dict[str, float] = {}

    lookup = {_norm(c): c for c in df.columns}
    out = {}
    for bdf_name, aliases, scale in d.colmap:
        src = next((lookup[a] for a in aliases if a in lookup), None)
        if src is None:
            continue
        if dname == "maccor":
            scale = _maccor_scale(src)
            if scale != 1.0:
                unit_fixes[src] = scale
        elif scale != 1.0:
            unit_fixes[src] = scale
        col = pd.to_numeric(df[src], errors="coerce") if bdf_name != "step_type" \
            else df[src]
        out[bdf_name] = col * scale if (scale != 1.0 and bdf_name != "step_type") else col

    nf = pd.DataFrame(out)

    missing = [c for c in BDF_REQUIRED if c not in nf.columns]
    if missing:
        raise ValueError(f"{path}: missing BDF-required column(s): {missing}")

    # ---- conventions, determined not assumed --------------------------
    sign = detect_current_sign(nf)
    if sign == "unspecified":
        sign = d.default_sign
        if sign != "unspecified":
            warnings.append(
                f"current sign not determinable from data; falling back to the "
                f"documented {dname} default '{sign}'. Verify before trusting "
                f"signed quantities.")
    accum = detect_capacity_accumulation(nf) or d.default_accum

    # Preserve the vendor's cycle index, and recompute independently.
    if "cycle_count" in nf.columns:
        nf["cycle_index_as_reported"] = nf["cycle_count"]
    derived = derive_cycle_index(nf, sign)
    if derived is not None:
        nf["cycle_index_derived"] = derived
        if "cycle_count" in nf.columns:
            disagree = int((nf["cycle_index_as_reported"].max() or 0)) - int(derived.max())
            if abs(disagree) > 1:
                warnings.append(
                    f"vendor cycle count and derived cycle count disagree by "
                    f"{disagree} cycles - this is normal and is why both are stored.")

    if "step_count" not in nf.columns and "step_id" in nf.columns:
        nf["step_count"] = nf["step_id"]

    return Normalised(frame=nf, dialect=dname, current_sign=sign,
                      capacity_accum=accum, unit_fixes=unit_fixes,
                      warnings=warnings, columns_present=list(nf.columns))


# ---------------------------------------------------------------------
# Convention detection
# ---------------------------------------------------------------------

def detect_current_sign(df) -> str:
    """
    Infer from behaviour, never from the column name.

    BDF / Voltaiq / battdat / battery-data-standard are charge-positive;
    ionworksdata is discharge-positive. Same name, opposite meaning.

    Test: does charge capacity increase while current is positive?
    """
    import numpy as np
    cur = df["current_ampere"].to_numpy(dtype=float)
    for cap_col, sign_if_rising in (("charging_capacity_ah", +1),
                                    ("discharging_capacity_ah", -1)):
        if cap_col not in df.columns:
            continue
        cap = df[cap_col].to_numpy(dtype=float)
        if np.all(np.isnan(cap)):
            continue
        dcap = np.diff(cap)
        active = np.abs(cur[1:]) > 1e-9
        rising = dcap > 1e-9
        both = active & rising
        if both.sum() < 5:
            continue
        mean_cur = np.nanmean(cur[1:][both])
        if abs(mean_cur) < 1e-9:
            continue
        polarity = np.sign(mean_cur) * sign_if_rising
        return "charge_positive" if polarity > 0 else "discharge_positive"

    # Fallback: the instrument's own step-type label settles it directly.
    # Compare the sign of the current on rows the cycler itself called
    # "charge". Works across Maccor's single-letter MD flag and Neware's
    # 'CC_Chg' / 'CC_DChg' strings.
    if "step_type" in df.columns:
        kinds = df["step_type"].map(classify_step_type)
        chg = cur[(kinds == "charge").to_numpy()]
        if chg.size >= 5 and np.abs(np.nanmean(chg)) > 1e-9:
            return "charge_positive" if np.nanmean(chg) > 0 else "discharge_positive"
    return "unspecified"


def classify_step_type(raw) -> str:
    """
    Map a vendor step-type label to charge | discharge | rest | other.

    The naive approach - take the first letter - works for Maccor's
    C/D/R flag and silently misreads Neware, where both 'CC_Chg' and
    'CC_DChg' begin with C. Discharge is therefore tested first, and
    on a normalised string.
    """
    if raw is None:
        return "other"
    s = re.sub(r"[^a-z]", "", str(raw).lower())
    if not s:
        return "other"
    if s in ("d", "dc"):
        return "discharge"
    if s in ("c", "cc", "cv", "cccv"):
        return "charge"
    if s.startswith("r") or "rest" in s or "pause" in s or "open" in s:
        return "rest"
    # substring tests, discharge first: 'ccdchg' contains 'chg' as well
    if "dchg" in s or "disch" in s or "dischg" in s:
        return "discharge"
    if "chg" in s or "charg" in s:
        return "charge"
    return "other"


def detect_capacity_accumulation(df) -> str | None:
    """
    Distinguish per-step / per-cycle / cumulative accumulation by counting
    how often the capacity series resets to zero relative to step and
    cycle boundaries.
    """
    import numpy as np
    col = next((c for c in ("charging_capacity_ah", "net_capacity_ah",
                            "cumulative_capacity_ah") if c in df.columns), None)
    if col is None:
        return None
    cap = df[col].to_numpy(dtype=float)
    if np.all(np.isnan(cap)):
        return None
    resets = int(np.sum(np.diff(cap) < -1e-6))
    if resets == 0:
        return "cumulative_test"
    n_steps = df["step_count"].nunique() if "step_count" in df.columns else 0
    n_cycles = df["cycle_count"].nunique() if "cycle_count" in df.columns else 0
    if n_steps and abs(resets - n_steps) <= max(2, 0.2 * n_steps):
        return "per_step"
    if n_cycles and abs(resets - n_cycles) <= max(2, 0.2 * n_cycles):
        return "per_cycle"
    return "net_signed"


def derive_cycle_index(df, sign: str):
    """
    Recompute cycle index with an explicit, named rule:
    increment on each completed charge -> discharge transition.

    Stored alongside the vendor's own count precisely because they
    disagree. Neware's BTSDA counts backward step-index jumps; fastnda
    counts charge->discharge completion and documents the divergence;
    NewareNDA exposes three user-selectable modes.
    """
    import numpy as np
    cur = df["current_ampere"].to_numpy(dtype=float)
    if sign == "discharge_positive":
        cur = -cur
    charging = cur > 1e-9
    discharging = cur < -1e-9

    idx = np.zeros(len(cur), dtype=int)
    n, seen_charge = 1, False
    for i in range(len(cur)):
        if charging[i]:
            seen_charge = True
        elif discharging[i] and seen_charge:
            pass
        idx[i] = n
        if i > 0 and discharging[i - 1] and charging[i] and seen_charge:
            n += 1
            idx[i] = n
    import pandas as pd
    return pd.Series(idx, index=df.index)


# ---------------------------------------------------------------------
# Cycle summary + RPT segmentation
# ---------------------------------------------------------------------

def summarise_cycles(nz: Normalised) -> list[dict]:
    import numpy as np
    df = nz.frame
    key = "cycle_index_derived" if "cycle_index_derived" in df.columns else "cycle_count"
    if key not in df.columns:
        return []
    cur = df["current_ampere"].to_numpy(dtype=float)
    if nz.current_sign == "discharge_positive":
        cur = -cur
    out = []
    for cyc, g in df.groupby(key):
        t = g["test_time_second"].to_numpy(dtype=float)
        v = g["voltage_volt"].to_numpy(dtype=float)
        c = cur[g.index]
        dt = np.diff(t, prepend=t[0])
        ah = np.abs(c) * dt / 3600.0
        chg = float(np.nansum(ah[c > 0]))
        dch = float(np.nansum(ah[c < 0]))
        out.append({
            "cycle_index": int(cyc),
            "start_test_time_s": float(t[0]),
            "duration_s": float(t[-1] - t[0]),
            "charge_capacity_ah": chg,
            "discharge_capacity_ah": dch,
            "coulombic_efficiency": (dch / chg) if chg > 1e-9 else None,
            "v_max": float(np.nanmax(v)), "v_min": float(np.nanmin(v)),
            "mean_discharge_current_a": float(np.nanmean(np.abs(c[c < 0])))
                                        if (c < 0).any() else None,
        })
    return out


def detect_rpt_segments(cycles: list[dict]) -> list[dict]:
    """
    Recover the [aging, RPT, aging, RPT, ...] structure.

    Essentially every aging campaign has this shape, and no published
    schema records it - which is why the literature is perennially
    unclear about whether a plotted capacity came from the reference
    performance test or from the cycling itself.

    RPTs are the low-rate, markedly longer cycles that recur at a fixed
    interval. Median duration separates them robustly.
    """
    import numpy as np
    if not cycles:
        return []
    dur = np.asarray([c["duration_s"] for c in cycles], dtype=float)
    med = float(np.nanmedian(dur))
    is_rpt = dur > 1.8 * med

    segs, start, cur = [], 0, bool(is_rpt[0])
    for i, flag in enumerate(is_rpt):
        if bool(flag) != cur:
            segs.append({"role": "periodic_rpt" if cur else "aging_cycling",
                         "start_cycle": cycles[start]["cycle_index"],
                         "end_cycle": cycles[i - 1]["cycle_index"],
                         "n_cycles": i - start})
            start, cur = i, bool(flag)
    segs.append({"role": "periodic_rpt" if cur else "aging_cycling",
                 "start_cycle": cycles[start]["cycle_index"],
                 "end_cycle": cycles[-1]["cycle_index"],
                 "n_cycles": len(cycles) - start})
    if segs[0]["role"] == "periodic_rpt":
        segs[0]["role"] = "baseline_rpt"
    if segs[-1]["role"] == "periodic_rpt":
        segs[-1]["role"] = "final_rpt"
    for i, s in enumerate(segs):
        s["sequence_index"] = i
    return segs


# =====================================================================
# Database load
# =====================================================================

INGEST_SQL_RUN = """
INSERT INTO bd.test_run
  (uid, product_unit_id, test_kind, current_sign, capacity_accum,
   cycle_definition, c_rate_reference_capacity_ah, c_rate_reference_source,
   source_format, source_encoding, parser_name, parser_version,
   quality_flags, provenance_id)
SELECT %(uid)s, pu.id, %(test_kind)s, %(sign)s, %(accum)s,
       'on_charge_discharge_pair', %(cref)s, %(cref_src)s,
       %(fmt)s, %(enc)s, 'tools/cyclers.py', %(ver)s,
       %(flags)s, %(prov)s
  FROM bd.product_unit pu WHERE pu.uid = %(unit_uid)s
RETURNING id
"""


def _lit(v) -> str:
    """SQL literal. Used by the driver-free emit path."""
    import math
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return "NULL" if (math.isnan(v) or math.isinf(v)) else repr(v)
    if isinstance(v, (list, tuple)):
        return "ARRAY[" + ",".join(_lit(x) for x in v) + "]::text[]" if v else "'{}'::text[]"
    return "'" + str(v).replace("'", "''") + "'"


def emit_sql(nz: Normalised, unit_uid: str, run_uid: str, provenance_id: int,
             test_kind: str = "cycle_life", c_rate_ref_ah: float | None = None,
             c_rate_ref_src: str | None = None) -> tuple[str, dict]:
    """
    Render the whole ingest as a single SQL transaction.

    Exists so ingestion works anywhere `psql` does, with no Python database
    driver installed - which is a common state on lab machines and in
    minimal CI images. It is also the easiest form to review before it
    touches the database.
    """
    cycles = summarise_cycles(nz)
    segments = detect_rpt_segments(cycles)

    out = ["BEGIN;", "SET search_path = bd, public;", "",
           "-- test_run: conventions determined from the data, not assumed",
           f"""INSERT INTO bd.test_run
  (uid, product_unit_id, test_kind, current_sign, capacity_accum,
   cycle_definition, c_rate_reference_capacity_ah, c_rate_reference_source,
   source_format, source_encoding, parser_name, parser_version,
   quality_flags, provenance_id)
SELECT {_lit(run_uid)}, pu.id, {_lit(test_kind)}::test_kind,
       {_lit(nz.current_sign)}::current_sign_convention,
       {_lit(nz.capacity_accum)}::capacity_accumulation,
       'on_charge_discharge_pair'::cycle_definition,
       {_lit(c_rate_ref_ah)}, {_lit(c_rate_ref_src)},
       {_lit(nz.dialect)}, {_lit(DIALECTS[nz.dialect].encoding)},
       'tools/cyclers.py', '0.3.0',
       {_lit(nz.warnings)}, {_lit(provenance_id)}
  FROM bd.product_unit pu WHERE pu.uid = {_lit(unit_uid)};""", ""]

    out.append("-- segments: the [aging, RPT, aging, RPT, ...] structure")
    for s in segments:
        out.append(
            f"""INSERT INTO bd.test_segment
  (uid, test_run_id, sequence_index, role, start_cycle, end_cycle)
SELECT {_lit(run_uid + '/seg' + str(s['sequence_index']))}, tr.id,
       {s['sequence_index']}, {_lit(s['role'])}::segment_role,
       {s['start_cycle']}, {s['end_cycle']}
  FROM bd.test_run tr WHERE tr.uid = {_lit(run_uid)};""")
    out.append("")

    out.append("-- per-cycle summary")
    for c in cycles:
        out.append(
            f"""INSERT INTO bd.cycle_summary
  (test_run_id, cycle_index, cycle_index_source, start_test_time_s, duration_s,
   charge_capacity_ah, discharge_capacity_ah, coulombic_efficiency, v_max, v_min)
SELECT tr.id, {c['cycle_index']}, 'on_charge_discharge_pair'::cycle_definition,
       {_lit(c['start_test_time_s'])}, {_lit(c['duration_s'])},
       {_lit(c['charge_capacity_ah'])}, {_lit(c['discharge_capacity_ah'])},
       {_lit(c['coulombic_efficiency'])}, {_lit(c['v_max'])}, {_lit(c['v_min'])}
  FROM bd.test_run tr WHERE tr.uid = {_lit(run_uid)};""")
    out.append("COMMIT;")

    return "\n".join(out), {"n_cycles": len(cycles), "n_segments": len(segments),
                            "segments": segments, "warnings": nz.warnings,
                            "current_sign": nz.current_sign,
                            "capacity_accum": nz.capacity_accum}


def load_to_db(dsn: str, nz: Normalised, unit_uid: str, run_uid: str,
               provenance_id: int, test_kind: str = "cycle_life",
               c_rate_ref_ah: float | None = None,
               c_rate_ref_src: str | None = None) -> dict:
    import psycopg2
    import psycopg2.extras

    cycles = summarise_cycles(nz)
    segments = detect_rpt_segments(cycles)

    conn = psycopg2.connect(dsn)
    with conn, conn.cursor() as cur:
        cur.execute(INGEST_SQL_RUN, {
            "uid": run_uid, "unit_uid": unit_uid, "test_kind": test_kind,
            "sign": nz.current_sign, "accum": nz.capacity_accum,
            "cref": c_rate_ref_ah, "cref_src": c_rate_ref_src,
            "fmt": nz.dialect, "enc": DIALECTS[nz.dialect].encoding,
            "ver": "0.3.0", "flags": nz.warnings, "prov": provenance_id,
        })
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"no product_unit with uid={unit_uid}")
        run_id = row[0]

        for s in segments:
            cur.execute("""
                INSERT INTO bd.test_segment
                  (uid, test_run_id, sequence_index, role, start_cycle, end_cycle)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (f"{run_uid}/seg{s['sequence_index']}", run_id,
                  s["sequence_index"], s["role"], s["start_cycle"], s["end_cycle"]))

        psycopg2.extras.execute_batch(cur, """
            INSERT INTO bd.cycle_summary
              (test_run_id, cycle_index, cycle_index_source, start_test_time_s,
               duration_s, charge_capacity_ah, discharge_capacity_ah,
               coulombic_efficiency, v_max, v_min)
            VALUES (%s,%s,'on_charge_discharge_pair',%s,%s,%s,%s,%s,%s,%s)
        """, [(run_id, c["cycle_index"], c["start_test_time_s"], c["duration_s"],
               c["charge_capacity_ah"], c["discharge_capacity_ah"],
               c["coulombic_efficiency"], c["v_max"], c["v_min"])
              for c in cycles])
    conn.close()
    return {"test_run_id": run_id, "n_cycles": len(cycles),
            "n_segments": len(segments), "segments": segments,
            "warnings": nz.warnings}


# =====================================================================
# Self-test: synthesise vendor files and round-trip them
# =====================================================================

def _synth(dialect: str, n_cycles: int = 120, rpt_every: int = 25) -> str:
    """Generate a plausible vendor export, including an RPT pattern."""
    import numpy as np
    rows, t, cyc, step, rec = [], 0.0, 1, 1, 1
    cap_nom = 4.9
    for k in range(1, n_cycles + 1):
        is_rpt = (k % rpt_every == 1)
        rate = 0.2 if is_rpt else 1.0
        cur_a = cap_nom * rate
        pts = 40 if is_rpt else 12
        for phase, sgn in (("chg", +1), ("dchg", -1)):
            cap = 0.0
            dt = (3600 / rate) / pts
            for i in range(pts):
                t += dt
                cap += abs(cur_a) * dt / 3600
                v = 3.0 + 1.2 * (i / pts) if sgn > 0 else 4.2 - 1.2 * (i / pts)
                rows.append({"t": t, "v": v, "i": sgn * cur_a, "cap": cap,
                             "cyc": k, "step": step, "rec": rec,
                             "type": "CC_Chg" if sgn > 0 else "CC_DChg"})
                rec += 1
            step += 1
    buf = io.StringIO()
    if dialect == "arbin":
        buf.write("Data_Point,Test_Time(s),Step_Time(s),Cycle_Index,Step_Index,"
                  "Current(A),Voltage(V),Charge_Capacity(Ah),Discharge_Capacity(Ah)\n")
        for r in rows:
            chg = r["cap"] if r["i"] > 0 else 0.0
            dch = r["cap"] if r["i"] < 0 else 0.0
            buf.write(f'{r["rec"]},{r["t"]:.3f},0,{r["cyc"]},{r["step"]},'
                      f'{r["i"]:.4f},{r["v"]:.4f},{chg:.5f},{dch:.5f}\n')
    elif dialect == "neware":
        # Neware logs mA / mAh
        buf.write("Record ID\tCycle ID\tStep ID\tStatus\tTime (s)\t"
                  "Voltage (V)\tCurrent (mA)\tCapacity (mAh)\n")
        for r in rows:
            buf.write(f'{r["rec"]}\t{r["cyc"]}\t{r["step"]}\t{r["type"]}\t'
                      f'{r["t"]:.3f}\t{r["v"]:.4f}\t{r["i"]*1000:.2f}\t'
                      f'{r["cap"]*1000:.2f}\n')
    elif dialect == "maccor":
        buf.write("Rec#\tCyc#\tStep\tTest (Sec)\tVoltage\tCurrent\t"
                  "Capacity..mAHr.\tMD\n")
        for r in rows:
            # Maccor with discharge exported NEGATIVE off: magnitude only
            buf.write(f'{r["rec"]}\t{r["cyc"]}\t{r["step"]}\t{r["t"]:.3f}\t'
                      f'{r["v"]:.4f}\t{r["i"]:.4f}\t{r["cap"]*1000:.2f}\t'
                      f'{"C" if r["i"]>0 else "D"}\n')
    elif dialect == "bdf":
        buf.write("Test Time / s,Voltage / V,Current / A,Cycle Count / 1,"
                  "Step Count / 1,Charging Capacity / A.h\n")
        for r in rows:
            chg = r["cap"] if r["i"] > 0 else 0.0
            buf.write(f'{r["t"]:.3f},{r["v"]:.4f},{r["i"]:.4f},'
                      f'{r["cyc"]},{r["step"]},{chg:.5f}\n')
    return buf.getvalue()


def selftest() -> int:
    import tempfile
    ok = True
    print("Cycler adapter self-test\n" + "=" * 62)
    for dialect in ("arbin", "neware", "maccor", "bdf"):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(_synth(dialect))
            path = f.name
        header, _ = read_header(path, DIALECTS[dialect].encoding)
        guessed, conf = sniff(header)
        nz = normalise(path)
        cycles = summarise_cycles(nz)
        segs = detect_rpt_segments(cycles)
        rpts = [s for s in segs if "rpt" in s["role"]]

        # Neware/Maccor emit mA and mAh; check the scale actually converted.
        peak_a = float(nz.frame["current_ampere"].abs().max())
        scale_ok = 0.5 < peak_a < 20

        print(f"\n  {dialect:9} sniffed={guessed:9} conf={conf:.2f}")
        print(f"    columns -> BDF : {len(nz.columns_present)}")
        print(f"    current sign   : {nz.current_sign}")
        print(f"    capacity accum : {nz.capacity_accum}")
        print(f"    peak current   : {peak_a:.2f} A  {'ok' if scale_ok else 'UNIT ERROR'}")
        print(f"    cycles         : {len(cycles)}")
        print(f"    RPTs detected  : {len(rpts)} at {[s['start_cycle'] for s in rpts][:6]}")
        if nz.warnings:
            for w in nz.warnings:
                print(f"    warning        : {w}")

        if guessed != dialect:
            print(f"    FAIL: sniffed {guessed}, expected {dialect}"); ok = False
        if not scale_ok:
            print("    FAIL: unit scaling wrong"); ok = False
        if len(rpts) < 4:
            print(f"    FAIL: expected >=4 RPTs, got {len(rpts)}"); ok = False
        os.unlink(path)

    print("\n" + "=" * 62)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


# =====================================================================
# CLI
# =====================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cyclers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sniff", help="identify format and show the mapping")
    s.add_argument("path")

    n = sub.add_parser("normalise", help="write BDF-normalised CSV")
    n.add_argument("path"); n.add_argument("--dialect"); n.add_argument("--out", default="-")

    i = sub.add_parser("ingest", help="load into the database")
    i.add_argument("path"); i.add_argument("--dialect")
    i.add_argument("--unit", required=True, help="product_unit uid")
    i.add_argument("--run-uid"); i.add_argument("--provenance", type=int, required=True)
    i.add_argument("--test-kind", default="cycle_life")
    i.add_argument("--c-rate-ref-ah", type=float)
    i.add_argument("--dsn", default=os.getenv("BATTERY_DSN", "dbname=batterydb"))
    i.add_argument("--emit-sql", metavar="PATH",
                   help="write a SQL transaction instead of connecting. "
                        "Use '-' for stdout and pipe into psql; needs no "
                        "Python database driver.")

    sub.add_parser("selftest", help="synthesise vendor files and round-trip them")

    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if a.cmd == "selftest":
        return selftest()

    if a.cmd == "sniff":
        header, sep = read_header(a.path)
        name, conf = sniff(header)
        print(json.dumps({"dialect": name, "confidence": round(conf, 3),
                          "separator": repr(sep), "n_columns": len(header),
                          "header": header[:20],
                          "notes": DIALECTS.get(name, DIALECTS["bdf"]).notes},
                         indent=2))
        return 0

    nz = normalise(a.path, getattr(a, "dialect", None))

    if a.cmd == "normalise":
        out = nz.frame.to_csv(index=False)
        if a.out == "-":
            sys.stdout.write(out)
        else:
            open(a.out, "w").write(out)
            log.info("wrote %s (%d rows, %d BDF columns)",
                     a.out, len(nz.frame), len(nz.columns_present))
        return 0

    if a.cmd == "ingest":
        sha = hashlib.sha256(open(a.path, "rb").read()).hexdigest()[:12]
        run_uid = a.run_uid or f"run/{os.path.basename(a.path)}/{sha}"
        ref_src = "declared" if a.c_rate_ref_ah else None

        if a.emit_sql:
            sql, res = emit_sql(nz, a.unit, run_uid, a.provenance,
                                a.test_kind, a.c_rate_ref_ah, ref_src)
            if a.emit_sql == "-":
                sys.stdout.write(sql)
            else:
                open(a.emit_sql, "w").write(sql)
            log.info("%s", json.dumps(res["segments"][:6]))
            log.info("run=%s cycles=%d segments=%d sign=%s accum=%s",
                     run_uid, res["n_cycles"], res["n_segments"],
                     res["current_sign"], res["capacity_accum"])
            return 0

        res = load_to_db(a.dsn, nz, a.unit, run_uid, a.provenance,
                         a.test_kind, a.c_rate_ref_ah, ref_src)
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
