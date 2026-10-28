#!/usr/bin/env python3
"""Declare the partner sodium-ion cells (28 October 2026) as a review batch.

Lemonergy received seven documents from a commercial partner that resells
sodium-ion cells: one 35-row cell spreadsheet ("2026H2") and six single-cell
datasheets. The owner supplied them in chat and asked for the cells to be
filed, with three instructions that shape every record:

* the producer is named only when a document makes it clear -- none of these
  do, so every product is filed under ``Maker not stated``;
* the partner company and its contact person, e-mail and phone are not
  recorded anywhere -- sources are identified by their SHA-256 alone;
* Lemonergy's own stock statement lives in ``offers/lemonergy.json``, outside
  the cell records, so it can never change a cell's facts or its rank.

This script is the transcription. It writes one declaration file,
``review/batches/2026-10-28-partner-sodium-ion-cells.json``, which
``tools/build_review_batch.py`` turns into candidate files exactly like every
other documented import. Spreadsheet cells are parsed from the cell text as
printed, so a value and its quote cannot drift apart.

    python tools/import_partner_sodium_cells.py           # write the batch
    python tools/import_partner_sodium_cells.py --check   # fail if stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "review" / "batches" / "2026-10-28-partner-sodium-ion-cells.json"
RETRIEVED = "2026-10-28"
MAKER, MAKER_SLUG = "Maker not stated", "maker-not-stated"
CATHODE_CODES = {"NFPP", "NFM", "NVP", "PB"}  # sodium-ion cathode-family labels
C_REF = "Supplier C-rate label; the capacity the C-rate refers to is not stated"
AXIS_BASIS = ("The sheet prints dimensions without axis labels. Axes are matched to the "
              "thickness-width-height digits of the model code, the order the same "
              "supplier's datasheets label (for example 18-148-67 mm, T x W x H).")
BLADE_AXIS = ("The sheet prints dimensions without axis labels. For blade cells the "
              "printed order is read as length x width x thickness, matching the "
              "thickness-length-width digits of the model code.")

WITHHELD = ("The issuing distributor's company name and its contact person, e-mail "
            "address and telephone number appear on the document and are deliberately "
            "not recorded, at the repository owner's instruction. The document is "
            "identified by its SHA-256 only and has no public URL.")
NO_MAKER = ("The document is issued by a distributor, not by the cell producer, and does "
            "not name the producer; the manufacturer is therefore recorded as not stated. "
            "The model number is the distributor's designation.")

# --------------------------------------------------------------- spreadsheet
SHEET_SOURCE = {
    "uid": "src/partner-sodium-ion-cell-spreadsheet-2026h2",
    "kind": "distributor_listing",
    "title": "Sodium-ion battery cell spreadsheet 2026H2 (partner supplier list)",
    "revision": "2026H2",
    "document_date": "2026",
    "retrieved_at": RETRIEVED,
    "sha256": "83abdfa4dfa77e5bfb41d79a1118e8d2653b1d48f1702728c6c5c36307ab7e17",
    "license": "proprietary",
    "redistributable": False,
}
SHEET_NOTE = " ".join([
    "Facts only; source body is not redistributed. One-page supplier cell spreadsheet "
    "supplied to Lemonergy by a commercial partner on 2026-10-28.", NO_MAKER, WITHHELD,
    "Quotes are normalized table transcriptions: row model, column header, then the cell "
    "text as printed.",
    "The sheet states no test conditions. Capacity rate, temperature and cut-off; AC "
    "resistance frequency, SOC and temperature; cycle-life temperature, depth of "
    "discharge and end-of-life criterion are all unstated.",
    "C-rates are kept as printed and never converted to amperes, because the sheet does "
    "not state the capacity they refer to. 'cont' and 'pulse' labels are kept; no pulse "
    "duration is printed. A Charge Rate printed without 'std' or 'max' is recorded as a "
    "maximum charge rate with that ambiguity noted on the value. 'Voltage Range' is "
    "recorded as the discharge and charge cut-off voltages.",
    "Pulse-cycle counts are kept as a qualifier on the cycle-life value, not as "
    "full-cycle life.",
    "The sheet itself notes that the production schedule is not fixed and that stock "
    "and lead time should be checked; Lemonergy's own stock statement is kept separately "
    "in offers/lemonergy.json.",
])

# model, chemistry, nominal voltage, voltage range, capacity, shape, dimensions,
# weight, ACIR, charge rate, discharge rate, cycle life, temperature range --
# each exactly as printed on the sheet.
SHEET_ROWS = [
    ("JNC18650P", "NFPP", "2.85 V", "1.5-3.5 V", "0.9 Ah", "Cylindrical", "Ø18.3×65.3 mm", "33 g", "≤15 mΩ", "1C std / 5C max", "35C cont / 70C pulse", "≥2000 cycles (1C) / ≥20,000 pulse cycles", "Charge −10~70°C Discharge −40~70°C"),
    ("JNC26650P", "NFM", "3.0 V", "1.5-3.9 V", "2 Ah", "Cylindrical", "Ø26.2×65.5 mm", "71 g", "≤5 mΩ", "6C", "20C cont / 75C pulse", "≥2000 cycles (1C) / ≥20,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC26650H", "NFM", "3.0 V", "1.5-3.9 V", "2.5 Ah", "Cylindrical", "Ø26.2×65.5 mm", "74 g", "≤5 mΩ", "6C", "20C cont / 65C pulse", "≥2500 cycles (1C) / ≥20,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC32700S", "NFPP", "3.0 V", "2.0-3.65 V", "3 Ah", "Cylindrical", "Ø32.4×71 mm", "120 g", "≤5 mΩ", "4C", "20C cont / 60C pulse", "≥3000 cycles (1C) / ≥20,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC32700P", "NFM", "3.0 V", "1.5-3.9 V", "3.5 Ah", "Cylindrical", "Ø32.4×71 mm", "123 g", "≤5 mΩ", "3C", "20C cont / 50C pulse", "≥3000 cycles (1C) / ≥20,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC32700H", "NFM", "3.0 V", "1.5-3.9 V", "4.5 Ah", "Cylindrical", "Ø32.4×71 mm", "125 g", "≤5 mΩ", "6C", "20C cont / 50C pulse", "≥3000 cycles (1C) / ≥20,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC32140P", "NFPP", "3.0 V", "2.0-3.65 V", "7 Ah", "Cylindrical", "Ø32.4×143 mm", "220 g", "≤5 mΩ", "6C", "20C cont / 70C pulse", "≥4000 cycles (1C) / ≥50,000 pulse cycles", "Charge −20~75°C Discharge −40~75°C"),
    ("JNC32140H", "NFM", "3.0 V", "1.5-3.95 V", "10 Ah", "Cylindrical", "Ø33.2×140 mm", "270 g", "≤3 mΩ", "3C", "10C cont / 25C pulse", "≥3000 cycles (1C) / ≥40,000 pulse cycles", "Charge −20~70°C Discharge −30~70°C"),
    ("JNC46145H", "PB", "3.2 V", "2.0-3.65 V", "13 Ah", "Cylindrical", "Ø46.7×145 mm", "400 g", "≤1 mΩ", "10C", "20C cont / 25C pulse", "≥3000 cycles (1C) / ≥30,000 pulse cycles", "Charge −20~60°C Discharge −40~80°C"),
    ("JNC40140P", "NFM", "3.1 V", "1.5-3.95 V", "15 Ah", "Cylindrical", "Ø40.5×140 mm", "382 g", "≤1.8 mΩ", "3C", "4C cont / 15C pulse", "≥3000 cycles (0.5C)", "Charge 0~60°C Discharge −40~65°C"),
    ("JNC40160H", "NFM", "3.1 V", "2.0-3.95 V", "20 Ah", "Cylindrical", "Ø40.5×160 mm", "445 g", "≤1.5 mΩ", "1C", "2C cont / 5C pulse", "≥2000 cycles (1C)", "Charge −10~60°C Discharge −40~70°C"),
    ("JNC60145P", "NFPP", "2.9 V", "1.5-3.5 V", "23 Ah", "Cylindrical", "Ø60.2×145.8 mm", "720 g", "≤1 mΩ", "5C", "20C cont", "≥3000 cycles (5C) ≥2000 cycles (7C)", "Charge −20~60°C Discharge −40~85°C"),
    ("JNC60145L", "NFPP", "2.9 V", "1.5-3.5 V", "25 Ah", "Cylindrical", "Ø60.2×145.8 mm", "710 g", "≤1 mΩ", "3C", "15C cont", "≥10000 cycles (3C)", "Charge −20~60°C Discharge −40~85°C"),
    ("JNC60145H", "NFPP", "2.9 V", "1.5-3.5 V", "28 Ah", "Cylindrical", "Ø60.2×145.8 mm", "700 g", "≤1 mΩ", "1C", "3C cont", "≥2000 cycles (0.5C)", "Charge −20~60°C Discharge −40~85°C"),
    ("JNC66160P", "NFPP", "2.9 V", "1.5-3.5 V", "30 Ah", "Cylindrical", "Ø65.8×160.5 mm", "1000 g", "≤1 mΩ", "5C", "20C cont", "≥3000 cycles (5C)", "Charge −20~60°C Discharge −40~85°C"),
    ("JNC66160H", "NFPP", "2.9 V", "1.5-3.5 V", "32 Ah", "Cylindrical", "Ø65.8×160.5 mm", "980 g", "≤1 mΩ", "2C", "8C cont", "≥2000 cycles (0.5C)", "Charge −20~60°C Discharge −40~60°C"),
    ("JNC120420", "NFPP", "2.85 V", "1.5-3.4 V", "280 Ah", "Cylindrical", "Ø120×420 mm", "8300 g", "≤0.18 mΩ", "1C", "1C cont", "≥6000 cycles (0.5C)", "Charge 0~60°C Discharge −40~60°C"),
    # JNP1814867 is filed once, from its own datasheet (JNP1814867-5.5HP below).
    ("JNP27148140", "NFPP", "2.85 V", "1.5-3.6 V", "28 Ah", "Prismatic", "148.7×27.5×140.1 mm", "983 g", "≤0.6 mΩ", "1C", "15C cont / 20C pulse", "≥3000 cycles (1C)", "Charge 0~40°C Discharge −40~80°C"),
    ("JSP3636245", "SMC", "2.4 V", "2.0-2.67 V", "41 Ah", "Prismatic", "35.75×35.75×245 mm", "725 g", "/", "16A", "32A", "≥6000 cycles (0.2C)", "Operating −40~80°C"),
    ("JNP27175204", "NVP", "3.1 V", "2.0-3.65 V", "46 Ah", "Prismatic", "175×27×204 mm", "1740 g", "≤0.3 mΩ", "6C", "6C cont / 10C pulse", "≥8000 cycles (1C)", "Charge -20~55°C Discharge −40~55°C"),
    ("JNP50160118P", "NFPP", "2.85 V", "1.5-3.5 V", "50 Ah", "Prismatic", "160.3×50.5×118 mm", "1800 g", "≤0.5 mΩ", "2C", "7C cont", "≥8000 cycles (1C)", "Charge 0~55°C Discharge −40~60°C"),
    ("JNP50160118L", "NFPP", "2.85 V", "1.5-3.5 V", "50 Ah", "Prismatic", "160.3×50.5×118 mm", "1800 g", "≤0.5 mΩ", "1C", "6C cont", "≥3000 cycles (1C)", "Charge -20~60°C Discharge −40~60°C"),
    ("JNB13420144", "NFPP", "2.9 V", "1.8-3.4V", "60 Ah", "Blade", "420×144×13.5 mm", "1650 g", "≤0.7 mΩ", "2C", "3C cont / 5C pulse", "≥8000 cycles (1C)", "Charge −10~65°C Discharge −30~70°C"),
    ("JNC27175204", "NVP", "3.1 V", "2.0-3.65 V", "65 Ah", "Prismatic", "175×27×204 mm", "1800 g", "≤0.3 mΩ", "5C", "5C cont / 10C pulse", "≥8000 cycles (1C)", "Charge -20~55°C Discharge −40~55°C"),
    ("JNP50160118H", "NFM", "3.0 V", "2.0-3.95 V", "70 Ah", "Prismatic", "160.3×50.8×118.6 mm", "1800 g", "≤1 mΩ", "1C", "6C cont / 8C pulse", "≥2000 cycles (1C)", "Charge 0~40°C Discharge −40~60°C"),
    ("JNP50160118C", "NCO", "2.9 V", "2.0-3.4 V", "70 Ah", "Prismatic", "160.3×50.8×118.6 mm", "1800 g", "≤1 mΩ", "1C std / 2C max", "2C cont / 4C pulse", "≥30000 cycles (1C)", "Charge 0~40°C Discharge −40~60°C"),
    ("JNB20420144", "NFPP", "2.9 V", "1.8-3.4 V", "91 Ah", "Blade", "420×144×20 mm", "2510 g", "≤0.65 mΩ", "2C", "3C cont / 5C pulse", "≥8000 cycles (1C)", "Charge −10~65°C Discharge −30~70°C"),
    ("JNP54173207L", "NFPP", "2.85 V", "1.5-3.4 V", "100 Ah 110 Ah", "Prismatic", "173.5×53.5×204.5 mm", "3300 g", "≤0.4 mΩ", "1C std / 3C max", "3C cont / 8C pulse", "≥10,000 cycles (0.5C)", "Charge −20~60°C Discharge −40~60°C"),
    ("JNB27420144", "NFPP", "2.9 V", "1.8-3.4 V", "125 Ah", "Blade", "420×144×27.4 mm", "3460 g", "≤0.45 mΩ", "2C", "3C cont / 5C pulse", "≥8000 cycles (1C)", "Charge −10~65°C Discharge −30~70°C"),
    ("JNB14700230", "NFPP", "2.85 V", "1.5-3.3 V", "180 Ah", "Blade", "700×230×14.2 mm", "5700 g", "≤0.5 mΩ", "1C", "1C cont / 5C pulse", "≥6000 cycles (0.5C)", "Charge 0~45°C Discharge −40~60°C"),
    ("JNP54173207H", "NFM", "3.0 V", "1.5-4.0 V", "200 Ah", "Prismatic", "174×53.7×207 mm", "3800 g", "≤0.25 mΩ", "3C", "2C cont / 3C pulse", "≥10,000 cycles (0.5C)", "Charge −10~60°C Discharge −40~60°C"),
    ("JNP72173208C", "NCO", "2.9 V", "2.0-3.4 V", "210 Ah", "Prismatic", "174.6×72×207 mm", "5100 g", "≤1 mΩ", "0.5C", "0.5C cont / 1C pulse", "≥30000 cycles (0.5C)", "Charge 0~40°C Discharge −40~60°C"),
    ("JNP73174207H", "NFM", "3.0 V", "1.5-4.0 V", "270 Ah", "Prismatic", "173.8×72×207 mm", "5100 g", "≤0.25 mΩ", "1C", "1C cont", "≥3000 cycles (0.5C)", "Charge −20~60°C Discharge −40~60°C"),
    ("JNB57420162", "NFPP", "2.9 V", "1.8-3.4V", "280 Ah", "Blade", "404×162×57 mm", "7733 g", "≤0.35 mΩ", "2C", "3C cont / 5C pulse", "≥8000 cycles (1C)", "Charge −10~65°C Discharge −30~70°C"),
]

# Row-specific qualifications. Each is a fact about the documents, not a guess.
ROW_NOTES = {
    "JNC46145H": "A separate partner datasheet, NaCR46145-40.3Wh-3.1V, describes a 13 Ah, Ø46.7 mm, 400 g cell with a different nominal voltage (3.1 V), printed length (152 mm), continuous discharge rating (15C) and cycle life (≥3500). The documents do not establish that the two designations are the same part, so they are kept as separate records.",
    "JNP54173207L": "The capacity cell prints both 100 Ah and 110 Ah without saying which is nominal or typical; both are kept. A separate partner datasheet, NFPP54173204-285Wh, describes a 100 Ah, 2.85 V, 1.5-3.4 V, 3.3 kg NFPP cell of similar size with a different continuous discharge rating (1C), charge-temperature floor (0 °C) and cycle life (≥8000); the documents do not establish that they are the same part.",
    "JNP50160118H": "A separate partner datasheet, NaCP51160120-216Wh, describes a 72 Ah, 3 V, 1.5-3.9 V, 1.8 kg cell of similar size and the same 6C/8C discharge ratings; the documents do not establish that the two designations are the same part.",
    "JNB57420162": "The model code reads 420 but the printed length is 404 mm; the printed value is kept.",
    "JNP72173208C": "The model code reads 208 but the printed height is 207 mm; the printed value is kept. Chemistry is printed as NCO and is not expanded.",
    "JNP50160118C": "Chemistry is printed as NCO and is not expanded.",
    "JNP73174207H": "The model code reads 73 but the printed thickness is 72 mm; the printed value is kept.",
    "JNC27175204": "Listed with a JNC prefix (used elsewhere on the sheet for cylindrical cells) but with shape Prismatic; recorded as printed.",
    "JSP3636245": "Chemistry is printed as SMC and is not expanded. The ACIR cell is printed as '/', so no resistance is recorded. Charge and discharge rates are printed in amperes without 'cont' or 'max'. The temperature range is printed as a single operating range, not split by charge and discharge.",
}


def num(text: str) -> float:
    v = float(text.replace(",", "").replace("−", "-"))
    return int(v) if v.is_integer() else v


def quote(model: str, header: str, cell: str) -> str:
    return f"{model} · {header}: {cell}"


def loc(model: str, header: str, cell: str) -> dict:
    return {"page": 1, "section": f"Cell table, row {model}, column {header}",
            "quote": quote(model, header, cell)}


def obs(q, v, u, locator, stat=None, cond=None, lower=False, upper=False):
    o = {"quantity": q, "value": v, "unit": u, "locator": locator}
    if stat:
        o["statistic"] = stat
    if lower:
        o["is_lower_bound"] = True
    if upper:
        o["is_upper_bound"] = True
    if cond:
        o["conditions"] = cond
    return o


def sheet_rates(model: str, header: str, cell: str, direction: str) -> list[dict]:
    """'1C std / 5C max', '6C', '16A', '35C cont / 70C pulse', '20C cont'."""
    out, L = [], loc(model, header, cell)
    parts = [p.strip() for p in cell.split("/")]
    for part in parts:
        m = re.fullmatch(r"([\d.]+)\s*(C|A)(?:\s+(std|max|cont|pulse))?", part)
        if not m:
            raise SystemExit(f"{model}: cannot read {header} part {part!r}")
        value, unit, label = num(m.group(1)), m.group(2), m.group(3)
        extra = {"printed": part, "source_column": header}
        if unit == "C":
            extra["rate_reference"] = C_REF
        if direction == "charge":
            if label == "std":
                q, stat = "standard_charge_rate" if unit == "C" else "standard_charge_current", "standard"
            else:
                q, stat = ("max_continuous_charge_rate" if unit == "C" else "max_continuous_charge_current"), "maximum"
                extra["label_scope"] = ("printed as 'max'; whether continuous or peak is not stated" if label == "max"
                                        else "printed without 'std' or 'max'; whether this is the standard or the maximum rate, and continuous or peak, is not stated")
        else:
            if label == "pulse":
                q = "max_pulse_discharge_rate" if unit == "C" else "max_pulse_discharge_current"
                cond = {"direction": "discharge", "unstated": ["pulse_duration_s", "temperature_c"], "extra": extra}
                out.append(obs(q, value, "C-rate" if unit == "C" else "A", L, "maximum", cond))
                continue
            q = "max_continuous_discharge_rate" if unit == "C" else "max_continuous_discharge_current"
            if label != "cont":
                extra["label_scope"] = "printed without 'cont' or 'pulse'; continuity is not stated"
            stat = "maximum"
        cond = {"direction": direction, "unstated": ["temperature_c"], "extra": extra}
        out.append(obs(q, value, "C-rate" if unit == "C" else "A", L, stat, cond))
    return out


def sheet_cycles(model: str, cell: str) -> list[dict]:
    L = loc(model, "Cycle Life", cell)
    pulse = re.search(r"≥([\d,]+) pulse cycles", cell)
    out = []
    for value, rate in re.findall(r"≥([\d,]+) cycles \(([\d.]+)C\)", cell):
        extra = {"source_comparator": "≥", "end_of_life_criterion": "not stated",
                 "rate_direction": "not stated"}
        if pulse:
            extra["pulse_cycle_claim"] = f"≥{pulse.group(1)} pulse cycles; pulse profile and end-of-life criterion not stated; not a full-cycle life"
        out.append(obs("cycle_life", num(value), "cycles", L, "minimum", {
            "rate_value": num(rate), "rate_unit": "C", "rate_reference_source": C_REF,
            "unstated": ["rate_reference_capacity_ah", "temperature_c", "dod_pct"],
            "extra": extra}, lower=True))
    if not out:
        raise SystemExit(f"{model}: no cycle-life figure read from {cell!r}")
    return out


def sheet_temps(model: str, cell: str) -> list[dict]:
    L, out = loc(model, "Temp Range (Charge/Discharge)", cell), []
    found = re.findall(r"(Charge|Discharge|Operating)\s+([−-]?\d+)~([−-]?\d+)°C", cell)
    if not found:
        raise SystemExit(f"{model}: no temperature read from {cell!r}")
    for kind, lo, hi in found:
        for q, v, stat in (("operating_temperature_min", num(lo), "minimum"),
                           ("operating_temperature_max", num(hi), "maximum")):
            cond = ({"direction": kind.lower(), "unstated": ["temperature_reference"]}
                    if kind != "Operating" else {"unstated": ["temperature_reference", "direction"]})
            out.append(obs(q, v, "°C", L, stat, cond))
    return out


def sheet_dims(model: str, shape: str, cell: str) -> list[dict]:
    L = loc(model, "Dimensions", cell)
    if shape == "Cylindrical":
        d, h = re.fullmatch(r"Ø([\d.]+)×([\d.]+) mm", cell).groups()
        return [obs("diameter", num(d), "mm", L), obs("height", num(h), "mm", L)]
    a, b, c = (num(x) for x in re.fullmatch(r"([\d.]+)×([\d.]+)×([\d.]+) mm", cell).groups())
    if shape == "Blade":
        ex = {"axis_basis": BLADE_AXIS}
        return [obs("length", a, "mm", L, cond={"extra": ex}), obs("width", b, "mm", L, cond={"extra": ex}),
                obs("thickness", c, "mm", L, cond={"extra": ex})]
    ex = {"axis_basis": AXIS_BASIS}
    return [obs("width", a, "mm", L, cond={"extra": ex}), obs("thickness", b, "mm", L, cond={"extra": ex}),
            obs("height", c, "mm", L, cond={"extra": ex})]


def sheet_record(row) -> dict:
    model, chem, vnom, vrange, cap, shape, dims, weight, acir, charge, discharge, cycles, temps = row
    o = []
    caps = re.findall(r"([\d.]+) Ah", cap)
    for c in caps:
        cond = {"unstated": ["rate_value", "rate_unit", "temperature_c", "voltage_lower_v"]}
        if len(caps) > 1:
            cond["extra"] = {"printed_with": cap, "note": "two capacities printed in one cell; which is nominal is not stated"}
        o.append(obs("capacity", num(c), "Ah", loc(model, "Capacity", cap), cond=cond))
    o.append(obs("nominal_voltage", num(vnom.split()[0]), "V", loc(model, "Nominal Voltage", vnom), "nominal"))
    lo, hi = re.fullmatch(r"([\d.]+)-([\d.]+)\s?V", vrange).groups()
    ex = {"extra": {"source_label": "Voltage Range"}}
    o.append(obs("discharge_cutoff_voltage", num(lo), "V", loc(model, "Voltage Range", vrange), "minimum", ex))
    o.append(obs("charge_cutoff_voltage", num(hi), "V", loc(model, "Voltage Range", vrange), "maximum", ex))
    o += sheet_dims(model, shape, dims)
    o.append(obs("mass", num(weight.split()[0]), "g", loc(model, "Weight", weight)))
    if acir != "/":
        v = num(re.fullmatch(r"≤([\d.]+) mΩ", acir).group(1))
        o.append(obs("internal_resistance_ac", v, "mohm", loc(model, "ACIR", acir), "maximum", {
            "unstated": ["frequency_hz", "soc_pct", "temperature_c"],
            "extra": {"source_label": "ACIR", "source_comparator": "≤"}}, upper=True))
    o += sheet_rates(model, "Charge Rate", charge, "charge")
    o += sheet_rates(model, "Discharge Rate", discharge, "discharge")
    o += sheet_cycles(model, cycles)
    o += sheet_temps(model, temps)

    chemistry = {"designation": "Sodium-ion", "locator": {
        "page": 1, "section": "Title and Chemistry column",
        "quote": f"Sodium ion Battery Cell Spreadsheet 2026H2 · {model} · Chemistry: {chem}"}}
    if chem in CATHODE_CODES:
        chemistry["cathode_text"] = chem
    ff = {"Cylindrical": "cylindrical", "Prismatic": "prismatic_hardcase", "Blade": "blade"}[shape]
    note = SHEET_NOTE + (" " + ROW_NOTES[model] if model in ROW_NOTES else "")
    if ff == "prismatic_hardcase":
        note += " Shape is printed as Prismatic; hard-case construction is the schema's only prismatic format."
    return document(model, ff, {**SHEET_SOURCE, "note": note}, o, chemistry)


def document(model, ff, source, observations, chemistry, aliases=None):
    product = {"uid": f"cell/{MAKER_SLUG}/{model.lower()}", "kind": "cell", "manufacturer": MAKER,
               "model_number": model, "is_rechargeable": True, "form_factor": ff}
    if aliases:
        product["aliases"] = aliases
    return {"schema_version": "1", "product": product, "source": source,
            "chemistry": chemistry, "observations": observations}


# ---------------------------------------------------------------- datasheets
def ds_source(slug, title, sha, note, pages="One-page supplier datasheet"):
    return {"uid": f"src/partner-datasheet-{slug}", "kind": "datasheet", "title": title,
            "retrieved_at": RETRIEVED, "sha256": sha, "license": "proprietary",
            "redistributable": False,
            "note": " ".join([f"Facts only; source body is not redistributed. {pages} "
                              "supplied to Lemonergy by a commercial partner on 2026-10-28.",
                              NO_MAKER, WITHHELD, note])}


def D(section, text):
    return {"page": 1, "section": section, "quote": text}


def ds_temps(charge, discharge, cq, dq):
    out = []
    for direction, (lo, hi), text in (("charge", charge, cq), ("discharge", discharge, dq)):
        out.append(obs("operating_temperature_min", lo, "°C", D("Cell characteristics / Operating Temperature", text), "minimum",
                       {"direction": direction, "unstated": ["temperature_reference"]}))
        out.append(obs("operating_temperature_max", hi, "°C", D("Cell characteristics / Operating Temperature", text), "maximum",
                       {"direction": direction, "unstated": ["temperature_reference"]}))
    return out


CAP_UNSTATED = {"unstated": ["rate_value", "rate_unit", "temperature_c", "voltage_lower_v"]}
E_UNSTATED = {"unstated": ["rate_value", "rate_unit", "temperature_c"]}
TOL = {"tol_plus": 0.5, "tol_minus": 0.5}
NOT_RECORDED = ("Not recorded: the 'Special at 0V: Shippable and Rechargeable' claim "
                "(a qualitative statement, no voltage quantity fits it)")


def with_tol(o, plus=0.5, minus=0.5):
    o.update({"tol_plus": plus, "tol_minus": minus})
    return o


def he175():
    sec = "Cell characteristics"
    s = ds_source("nfpp71174207-he175", "Sodium-ion cell datasheet NFPP71174207-HE175 (partner supplier)",
                  "268bcb8e3914220930119bb907b837666ebc9bd7da0278b5b42565e7a3f24724",
                  "Cathode family is read from the NFPP prefix of the model designation. "
                  "Charge and discharge ratings are printed as constant-power rates (P) with the "
                  "corresponding watts; no current is printed. The cycle-life figures are printed with "
                  "1P/1P, 100% DOD and a 300 kgf fixture force; end-of-life criterion is not stated. "
                  "The thickness 71.7 mm is drawn at 300 kgf ± 20 kgf. The drawing gives two heights, "
                  "H2 207.10 ± 0.5 mm and H1 204.20 ± 0.5 mm; both are kept, H2 first because the "
                  "table prints it. Held: '1P Discharge Energy Retention ≥96%' (reference and test not "
                  "stated). " + NOT_RECORDED + ". The cycle-life graph is not digitised.")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    o = [
        T("capacity", 175, "Ah", "Nominal Capacity 175Ah 498.75Wh", "nominal", CAP_UNSTATED),
        T("energy", 498.75, "Wh", "Nominal Capacity 175Ah 498.75Wh", "nominal",
          {**E_UNSTATED, "extra": {"value_basis": "equals 175 Ah × 2.85 V as printed; not stated to be a measured discharge energy"}}),
        T("nominal_voltage", 2.85, "V", "Nominal Voltage 2.85V", "nominal"),
        T("discharge_cutoff_voltage", 1.5, "V", "Voltage Range 1.5V~3.4V", "minimum", {"extra": {"source_label": "Voltage Range"}}),
        T("charge_cutoff_voltage", 3.4, "V", "Voltage Range 1.5V~3.4V", "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 106, "Wh/kg", "Energy Density ≥106Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("rated_power", 1496.25, "W", "Max. Cont. Charge Rate 3P/1496.25W", "maximum",
          {"direction": "charge", "boundary": "cell", "unstated": ["temperature_c"], "extra": {"rate_label": "3P", "continuity": "continuous"}}),
        T("rated_power", 1496.25, "W", "Max. Discharge Rate 3P/1496.25W", "maximum",
          {"direction": "discharge", "boundary": "cell", "unstated": ["temperature_c"], "extra": {"rate_label": "3P", "continuity": "not stated"}}),
        T("internal_resistance_ac", 0.21, "mohm", "Internal Resistance AC≤0.21mΩ at 1KHz 40%SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 40, "unstated": ["temperature_c"], "extra": {"source_comparator": "≤"}}, upper=True),
        with_tol(T("thickness", 71.7, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm", None,
                   {"extra": {"fixture_force": "drawn at 300 kgf ± 20 kgf"}})),
        with_tol(T("width", 174.2, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm")),
        with_tol(T("height", 207.1, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm", None,
                   {"extra": {"drawing_label": "H2: 207.10±0.5mm"}})),
        with_tol(obs("height", 204.2, "mm", D("Dimension drawing", "H2: 207.10±0.5mm H1: 204.20±0.5mm"), None,
                     {"extra": {"drawing_label": "H1: 204.20±0.5mm", "note": "second drawn height; which features each height includes is not stated"}})),
        T("cycle_life", 12000, "cycles", "Cycle Life @1P/1P 100% DOD 300kgf ≥12000 Times @25℃", "minimum",
          {"temperature_c": 25, "dod_pct": 100, "rate_value": 1, "rate_unit": "P",
           "extra": {"source_comparator": "≥", "rate_direction": "1P charge / 1P discharge", "fixture_force": "300 kgf", "end_of_life_criterion": "not stated"}}, lower=True),
        T("cycle_life", 8000, "cycles", "Cycle Life @1P/1P 100% DOD 300kgf ≥8000 Times @45℃", "minimum",
          {"temperature_c": 45, "dod_pct": 100, "rate_value": 1, "rate_unit": "P",
           "extra": {"source_comparator": "≥", "rate_direction": "1P charge / 1P discharge", "fixture_force": "300 kgf", "end_of_life_criterion": "not stated"}}, lower=True),
        T("mass", 4.7, "kg", "Approx. Weight 4.7kg", "typical", {"extra": {"source_label": "Approx. Weight"}}),
    ]
    o += ds_temps((-20, 60), (-35, 65), "Charge: -20℃~60℃", "Disharge: -35℃~65℃")
    chem = {"designation": "Sodium-ion", "cathode_text": "NFPP",
            "locator": D("Title", "Rechargeable Sodium ion Battery Product Datasheet NFPP71174207-HE175")}
    return document("NFPP71174207-HE175", "prismatic_hardcase", s, o, chem)


def me170():
    sec = "Cell characteristics"
    s = ds_source("nfpp71173207-me170", "Sodium-ion cell datasheet NFPP71173207-ME170 (partner supplier)",
                  "88db7a1397d746f5ee5561c90dac364013dba6af5b5f5e45396a2083038d320a",
                  "Cathode family is read from the NFPP prefix of the model designation. "
                  "Charge and discharge ratings are printed as constant-power rates (P) with the "
                  "corresponding watts; no current is printed. Cycle life is printed at 0.5P, room "
                  "temperature (no number given), 100% DOD and a 300 kgf fixture force, to 80% and to "
                  "70% of an unstated quantity. The drawing is the same as for the 175 Ah model: "
                  "thickness drawn at 300 kgf ± 20 kgf; heights H2 207.10 and H1 204.20 ± 0.5 mm. "
                  "Held: '1P Discharge Energy Retention ≥95%' (reference and test not stated). "
                  + NOT_RECORDED + ". The cycle-life graph is not digitised.")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    life = lambda n, eol: T("cycle_life", n, "cycles", f"Cycle Life @0.5P RT 100%DOD 300kgf ≥{n} Times to {eol}%", "minimum",
                            {"dod_pct": 100, "rate_value": 0.5, "rate_unit": "P", "unstated": ["temperature_c"],
                             "extra": {"source_comparator": "≥", "temperature_text": "RT", "fixture_force": "300 kgf",
                                       "end_of_life_criterion": f"{eol}% (of an unstated quantity)"}}, lower=True)
    o = [
        T("capacity", 170, "Ah", "Nominal Capacity 170Ah 484.5Wh", "nominal", CAP_UNSTATED),
        T("energy", 484.5, "Wh", "Nominal Capacity 170Ah 484.5Wh", "nominal",
          {**E_UNSTATED, "extra": {"value_basis": "equals 170 Ah × 2.85 V as printed; not stated to be a measured discharge energy"}}),
        T("nominal_voltage", 2.85, "V", "Nominal Voltage 2.85V", "nominal"),
        T("discharge_cutoff_voltage", 1.5, "V", "Voltage Range 1.5V~3.45V", "minimum", {"extra": {"source_label": "Voltage Range"}}),
        T("charge_cutoff_voltage", 3.45, "V", "Voltage Range 1.5V~3.45V", "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 103, "Wh/kg", "Energy Density ≥103Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("rated_power", 484.5, "W", "Max. Cont. Charge Rate 1P/484.5W", "maximum",
          {"direction": "charge", "boundary": "cell", "unstated": ["temperature_c"], "extra": {"rate_label": "1P", "continuity": "continuous"}}),
        T("rated_power", 484.5, "W", "Max. Discharge Rate 1P/484.5W", "maximum",
          {"direction": "discharge", "boundary": "cell", "unstated": ["temperature_c"], "extra": {"rate_label": "1P", "continuity": "not stated"}}),
        T("internal_resistance_ac", 0.3, "mohm", "Internal Resistance AC≤0.3mΩ at 1KHz 40%SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 40, "unstated": ["temperature_c"], "extra": {"source_comparator": "≤"}}, upper=True),
        with_tol(T("thickness", 71.7, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm", None,
                   {"extra": {"fixture_force": "drawn at 300 kgf ± 20 kgf"}})),
        with_tol(T("width", 174.2, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm")),
        with_tol(T("height", 207.1, "mm", "Dimension T 71.7±0.5mm x W 174.2±0.5mm x H 207.1±0.5mm", None,
                   {"extra": {"drawing_label": "H2: 207.10±0.5mm"}})),
        with_tol(obs("height", 204.2, "mm", D("Dimension drawing", "H2: 207.10±0.5mm H1: 204.20±0.5mm"), None,
                     {"extra": {"drawing_label": "H1: 204.20±0.5mm", "note": "second drawn height; which features each height includes is not stated"}})),
        life(6000, 80), life(10000, 70),
        T("mass", 4.65, "kg", "Approx. Weight 4.65kg", "typical", {"extra": {"source_label": "Approx. Weight"}}),
    ]
    o += ds_temps((0, 60), (-40, 60), "Charge: 0℃~60℃", "Disharge: -40℃~60℃")
    chem = {"designation": "Sodium-ion", "cathode_text": "NFPP",
            "locator": D("Title", "Rechargeable Sodium ion Battery Product Datasheet NFPP71173207-ME170")}
    return document("NFPP71173207-ME170", "prismatic_hardcase", s, o, chem)


def jnp1814867():
    sec = "Cell Characteristics"
    s = ds_source("jnp1814867-5.5hp", "Sodium-ion cell datasheet JNP1814867-5.5HP (partner supplier)",
                  "0ccff58eeb656f1989b687720140b1af3e18bd1797cf9ef23de8f10203c6eee9",
                  "The partner spreadsheet lists the same model as JNP1814867 (NVP, 5.5 Ah, 2.9 V, "
                  "148×18×67 mm, 290 g, ≤1.1 mΩ, 10C std / 40C max, 30C cont / 75C pulse, charge and "
                  "discharge −40~55°C); it is filed once, from this datasheet, with JNP1814867 as an "
                  "alias. The two documents disagree on one label: the sheet prints the 8000-cycle "
                  "figure at (1C), this datasheet at (2C); the datasheet's label is recorded. The sheet "
                  "gives the chemistry as NVP; this datasheet does not. Amperes are the datasheet's own "
                  "figures printed beside each C-rate. The cycle-life graph's caption (25°C, 0-100% SOC, "
                  "1C charge / 2C discharge) is not attached to the ≥8000 figure, which the graph does "
                  "not reach. Held: '40C/220A Peak' charge (no peak-charge quantity; duration not "
                  "stated), the ≥2400 W/kg power density's test conditions are all unstated, the nail "
                  "penetration claim ('Passed', no test standard named). " + NOT_RECORDED +
                  ". Temperature-rise graphs are not digitised.")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    vr = "Voltage Range 2.0~3.45V T＞0℃ 1.5~3.45V T≤0℃"
    o = [
        T("capacity", 5.5, "Ah", "Nominal Capacity 5.5Ah 16Wh", "nominal", CAP_UNSTATED),
        T("energy", 16, "Wh", "Nominal Capacity 5.5Ah 16Wh", "nominal", E_UNSTATED),
        T("nominal_voltage", 2.9, "V", "Nominal Voltage 2.9V", "nominal"),
        T("discharge_cutoff_voltage", 2.0, "V", vr, "minimum", {"extra": {"source_label": "Voltage Range", "applies_when": "T > 0 °C"}}),
        T("discharge_cutoff_voltage", 1.5, "V", vr, "minimum", {"extra": {"source_label": "Voltage Range", "applies_when": "T ≤ 0 °C"}}),
        T("charge_cutoff_voltage", 3.45, "V", vr, "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 55, "Wh/kg", "Energy Density ≥55Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("specific_power", 2400, "W_per_kg", "Power Density ≥2400W/Kg", "minimum",
          {"unstated": ["temperature_c", "soc_pct", "pulse_duration_s"], "extra": {"source_comparator": "≥"}}, lower=True),
        T("max_continuous_charge_current", 55, "A", "Max. Cont. Charge Rate 10C/55A Cont. 40C/220A Peak", "maximum",
          {"direction": "charge", "unstated": ["temperature_c"], "extra": {"rate_label": "10C", "peak_printed": "40C/220A Peak; duration not stated"}}),
        T("max_continuous_discharge_current", 165, "A", "Max. Discharge Rate 30C/165A Cont. 75C/412.5A Peak", "maximum",
          {"direction": "discharge", "unstated": ["temperature_c"], "extra": {"rate_label": "30C"}}),
        T("max_pulse_discharge_current", 412.5, "A", "Max. Discharge Rate 30C/165A Cont. 75C/412.5A Peak", "maximum",
          {"direction": "discharge", "unstated": ["pulse_duration_s", "temperature_c"], "extra": {"rate_label": "75C"}}),
        T("internal_resistance_ac", 1.1, "mohm", "Internal Resistance 1KHz AC≤1.1mΩ at 50% SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 50, "unstated": ["temperature_c"], "extra": {"source_comparator": "≤"}}, upper=True),
        T("thickness", 18, "mm", "Dimension (T x W x H) 18-148-67mm"),
        T("width", 148, "mm", "Dimension (T x W x H) 18-148-67mm"),
        T("height", 67, "mm", "Dimension (T x W x H) 18-148-67mm"),
        T("cycle_life", 8000, "cycles", "Cycle Life (to 80%SOH) ≥8000 cycles (2C) ≥45000 pulse cycles", "minimum",
          {"rate_value": 2, "rate_unit": "C", "rate_reference_source": C_REF,
           "unstated": ["rate_reference_capacity_ah", "temperature_c", "dod_pct"],
           "extra": {"source_comparator": "≥", "end_of_life_criterion": "80% SOH",
                     "pulse_cycle_claim": "≥45000 pulse cycles; pulse profile not stated; not a full-cycle life"}}, lower=True),
        T("capacity_retention", 89, "%", "-40℃ 1C Discharge Capacity ≥89% VS 25℃", "minimum",
          {"temperature_c": -40, "rate_value": 1, "rate_unit": "C", "rate_reference_source": C_REF,
           "unstated": ["cycle_index", "rate_reference_capacity_ah"],
           "extra": {"source_comparator": "≥", "relative_to": "1C discharge capacity at 25 °C"}}, lower=True),
        T("mass", 0.29, "kg", "Approx. Weight 0.29kg", "typical", {"extra": {"source_label": "Approx. Weight"}}),
    ]
    o += ds_temps((-40, 55), (-40, 55), "Charge: -40℃~55℃", "Disharge: -40℃~55℃")
    # The NVP label is on the spreadsheet, not on this datasheet, so it stays in the note:
    # a record carries one source, and a chemistry claim needs a locator in it.
    chem = {"designation": "Sodium-ion",
            "locator": D("Title", "Rechargeable Sodium ion Battery Product Datasheet JNP1814867-5.5HP")}
    return document("JNP1814867-5.5HP", "prismatic_hardcase", s, o, chem, aliases=["JNP1814867"])


def nacr46145():
    sec = "Cell characteristics"
    s = ds_source("nacr46145-40.3wh-3.1v", "Sodium-ion cell datasheet NaCR46145-40.3Wh-3.1V (partner supplier)",
                  "3a5f9e5942ff999aa6f4dae4bd6964307915ae1f8c9f22cc8fe3012dc6039c6a",
                  "The datasheet names no cathode chemistry. It prints '15C/200A Cont.'; 15 × 13 Ah is "
                  "195 A, and both figures are kept as printed without reconciliation. The partner "
                  "spreadsheet's JNC46145H (PB, 3.2 V, Ø46.7×145 mm, 20C cont) is not established to be "
                  "the same part and is a separate record. Held: the 5C and 10C high-rate temperature "
                  "and voltage tables (a module '4S voltage' is mixed into them), the nail penetration "
                  "claim ('Passed', no test standard named). " + NOT_RECORDED +
                  ". The cycle-life graph is not digitised.")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    o = [
        T("capacity", 13, "Ah", "Nominal Capacity 13Ah 40.3Wh", "nominal", CAP_UNSTATED),
        T("energy", 40.3, "Wh", "Nominal Capacity 13Ah 40.3Wh", "nominal", E_UNSTATED),
        T("nominal_voltage", 3.1, "V", "Nominal Voltage 3.1V", "nominal"),
        T("discharge_cutoff_voltage", 2.0, "V", "Voltage Range 2V-3.65V", "minimum", {"extra": {"source_label": "Voltage Range"}}),
        T("charge_cutoff_voltage", 3.65, "V", "Voltage Range 2V-3.65V", "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 101, "Wh/kg", "Energy Density ≥101Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("max_continuous_charge_current", 130, "A", "Max. Cont. Charge Rate 10C/130A", "maximum",
          {"direction": "charge", "unstated": ["temperature_c"], "extra": {"rate_label": "10C"}}),
        T("max_continuous_discharge_current", 200, "A", "Max. Discharge Rate 15C/200A Cont. 613W Peak 10s", "maximum",
          {"direction": "discharge", "unstated": ["temperature_c"],
           "extra": {"rate_label": "15C", "arithmetic_note": "15 × 13 Ah = 195 A; the printed 200 A is kept"}}),
        T("peak_power", 613, "W", "Max. Discharge Rate 15C/200A Cont. 613W Peak 10s", "maximum",
          {"pulse_duration_s": 10, "boundary": "cell", "direction": "discharge", "unstated": ["soc_pct", "temperature_c"]}),
        T("internal_resistance_ac", 1, "mohm", "Internal Resistance 1KHz AC≤1mΩ BOL at 70% SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 70, "unstated": ["temperature_c"],
           "extra": {"source_comparator": "≤", "state": "beginning of life"}}, upper=True),
        with_tol(T("diameter", 46.7, "mm", "Dimension (D x H) 46.7±0.5mm x 152.0±0.5mm")),
        with_tol(T("height", 152.0, "mm", "Dimension (D x H) 46.7±0.5mm x 152.0±0.5mm")),
        T("cycle_life", 3500, "cycles", "Cycle Life ≥3500 Times @1C/1C 90% DOD at RT", "minimum",
          {"rate_value": 1, "rate_unit": "C", "rate_reference_source": C_REF, "dod_pct": 90,
           "unstated": ["rate_reference_capacity_ah", "temperature_c"],
           "extra": {"source_comparator": "≥", "rate_direction": "1C charge / 1C discharge", "temperature_text": "RT",
                     "end_of_life_criterion": "not stated"}}, lower=True),
        T("capacity_retention", 88, "%", "-18℃ 1C Discharge Capacity 1.8V~3.65V ≥88% VS 25℃", "minimum",
          {"temperature_c": -18, "rate_value": 1, "rate_unit": "C", "rate_reference_source": C_REF,
           "voltage_lower_v": 1.8, "voltage_upper_v": 3.65, "unstated": ["cycle_index", "rate_reference_capacity_ah"],
           "extra": {"source_comparator": "≥", "relative_to": "1C discharge capacity at 25 °C"}}, lower=True),
        T("mass", 400, "g", "Approx. Weight 400g", "typical", {"extra": {"source_label": "Approx. Weight"}}),
    ]
    o += ds_temps((-20, 60), (-40, 80), "Charge: -20℃~60℃", "Disharge: -40℃~80℃")
    chem = {"designation": "Sodium-ion", "locator": D("Title", "Rechargeable Sodium ion Battery PRODUCT DATASHEET NaCR46145-40.3Wh-3.1V")}
    return document("NaCR46145-40.3Wh-3.1V", "cylindrical", s, o, chem)


OCV_SOC = [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
OCV_V = [3.933, 3.816, 3.726, 3.651, 3.582, 3.515, 3.443, 3.365, 3.285, 3.203, 3.122,
         3.042, 2.961, 2.878, 2.857, 2.826, 2.767, 2.662, 2.522, 2.367, 2.144]


def nacp51160120():
    sec = "Cell characteristics"
    s = ds_source("nacp51160120-216wh", "Sodium-ion cell datasheet NaCP51160120-216Wh (partner supplier)",
                  "ee868e9d419ff1dcc4ba4c30f349dd46f394b096c31974ea1b68ba929d130f9e",
                  "The datasheet names no cathode chemistry. The partner spreadsheet's JNP50160118H (NFM, 70 Ah) is not established "
                  "to be the same part and is a separate record. The SOC-OCV curve is transcribed from "
                  "the 21 value labels printed on the chart; the 35% label is partly covered by the 30% "
                  "label and reads 2.878, last digit uncertain. The cycle-life legend '1C/ 2000th/85.36%' "
                  "is recorded as a measured retention point; its temperature and DOD are not printed. "
                  "Product-drawing dimensions (120.0, 116.0, 160, 51 mm with tolerances) are not "
                  "mapped to axes beyond the table's T-W-H figures. " + NOT_RECORDED + ".",
                  pages="Two-page supplier datasheet (page 2 repeats two chart images and has no text)")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    o = [
        T("capacity", 72, "Ah", "Nominal Capacity 72Ah 216Wh", "nominal", CAP_UNSTATED),
        T("energy", 216, "Wh", "Nominal Capacity 72Ah 216Wh", "nominal", E_UNSTATED),
        T("nominal_voltage", 3, "V", "Nominal Voltage 3V", "nominal"),
        T("discharge_cutoff_voltage", 1.5, "V", "Voltage Range 1.5V-3.9V", "minimum", {"extra": {"source_label": "Voltage Range"}}),
        T("charge_cutoff_voltage", 3.9, "V", "Voltage Range 1.5V-3.9V", "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 120, "Wh/kg", "Energy Density ≥120Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("max_continuous_charge_current", 72, "A", "Max. Cont. Charge Rate 1C/72A", "maximum",
          {"direction": "charge", "unstated": ["temperature_c"], "extra": {"rate_label": "1C"}}),
        T("max_continuous_discharge_current", 432, "A", "Max. Discharge Rate 6C/432A Cont. 8C/576A Peak 10s", "maximum",
          {"direction": "discharge", "unstated": ["temperature_c"], "extra": {"rate_label": "6C"}}),
        T("max_pulse_discharge_current", 576, "A", "Max. Discharge Rate 6C/432A Cont. 8C/576A Peak 10s", "maximum",
          {"direction": "discharge", "pulse_duration_s": 10, "unstated": ["temperature_c"], "extra": {"rate_label": "8C"}}),
        T("internal_resistance_ac", 1, "mohm", "Internal Resistance 1KHz AC≤1mΩ at 50% SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 50, "unstated": ["temperature_c"], "extra": {"source_comparator": "≤"}}, upper=True),
        T("thickness", 51, "mm", "Dimension (T x W x H) 51-160-120mm"),
        T("width", 160, "mm", "Dimension (T x W x H) 51-160-120mm"),
        T("height", 120, "mm", "Dimension (T x W x H) 51-160-120mm"),
        T("cycle_life", 2000, "cycles", "Cycle Life ≥2000 Times @0.5C/1C 100% DOD at RT", "minimum",
          {"rate_value": 1, "rate_unit": "C", "rate_reference_source": C_REF, "dod_pct": 100,
           "unstated": ["rate_reference_capacity_ah", "temperature_c"],
           "extra": {"source_comparator": "≥", "rate_direction": "0.5C charge / 1C discharge", "temperature_text": "RT",
                     "end_of_life_criterion": "not stated"}}, lower=True),
        obs("capacity_retention", 85.36, "%", D("Cycle Life chart legend", "1C/ 2000th/85.36%"), "measured",
            {"cycle_index": 2000, "rate_value": 1, "rate_unit": "C", "rate_reference_source": C_REF,
             "unstated": ["temperature_c", "rate_reference_capacity_ah", "dod_pct"],
             "extra": {"source_note": "chart legend of the cycle-life graph"}}),
        T("capacity_retention", 80, "%", "-20℃ 0.5C Discharge Capacity ≥80% VS 25℃", "minimum",
          {"temperature_c": -20, "rate_value": 0.5, "rate_unit": "C", "rate_reference_source": C_REF,
           "unstated": ["cycle_index", "rate_reference_capacity_ah"],
           "extra": {"source_comparator": "≥", "relative_to": "0.5C discharge capacity at 25 °C"}}, lower=True),
        T("mass", 1.8, "kg", "Approx. Weight 1.8kg", "typical", {"extra": {"source_label": "Approx. Weight"}}),
        T("stack_pressure", 0.2, "MPa", "Compress Pressure 0.2MPa", None,
          {"unstated": ["soc_pct", "constraint_mode"], "extra": {"source_label": "Compress Pressure"}}),
    ]
    o += ds_temps((0, 40), (-40, 60), "Charge: 0℃~40℃", "Disharge: -40℃~60℃")
    doc = document("NaCP51160120-216Wh", "prismatic_hardcase", s, o,
                   {"designation": "Sodium-ion", "locator": D("Title", "Rechargeable Sodium ion Battery Product Datasheet NaCP51160120-216Wh")})
    doc["curves"] = [{
        "curve_kind": "ocv_soc", "x_quantity": "state_of_charge", "y_quantity": "open_circuit_voltage",
        "x_unit": "%", "y_unit": "V", "x_values": OCV_SOC, "y_values": OCV_V,
        "conditions": {"direction": "discharge", "unstated": ["temperature_c", "rest_before_s"]},
        "processing": {"method": "transcribed from printed point labels, not digitised from the line",
                       "uncertain_points": [{"soc_pct": 35, "note": "label partly covered by the 30% label; last digit uncertain"}]},
        "locator": D("Discharge SOC-OCV chart", "Discharge SOC-OCV · 3.933 at 100% … 2.144 at 0%"),
    }]
    return doc


def nfpp54173204():
    sec = "Cell characteristics"
    s = ds_source("nfpp54173204-285wh", "Sodium-ion cell datasheet NFPP54173204-285Wh (partner supplier)",
                  "29b16475385cd2c4c76fb45038b668d40139d2dcc3250066934fb9a245915f38",
                  "Cathode family is read from the NFPP prefix of the model designation. The charge row "
                  "prints '1C/300A Cont.'; 1C of the 100 Ah nominal capacity would be 100 A, so the 300 A "
                  "figure conflicts with its own label and is not recorded as a continuous current; the "
                  "1C rate is. The ≥90 Wh/kg figure and 285 Wh / 3.3 kg (about 86 Wh/kg) disagree; both "
                  "are kept as printed. The dimension drawing prints 53.7 ± 0.5 × 173.5 ± 0.8 mm and two "
                  "heights, 207.2 ± 0.8 and 204.4 ± 0.6 mm, which differ from the table's rounded "
                  "54-173-204 mm; both are kept, the table first. Terminal spacing 123 ± 0.3 mm has no "
                  "quantity and is not recorded. The partner spreadsheet's JNP54173207L (173.5×53.5×204.5 mm) "
                  "is not established to be the same part and is a separate record. Held: '3C 300A Peak 10s' charge (no peak-"
                  "charge quantity), the nail penetration claim ('Passed', no test standard named). "
                  + NOT_RECORDED + ". The cycle-life graph is not digitised.")
    T = lambda q, v, u, t, stat=None, cond=None, **k: obs(q, v, u, D(sec, t), stat, cond, **k)
    o = [
        T("capacity", 100, "Ah", "Nominal Capacity 100Ah 285Wh", "nominal", CAP_UNSTATED),
        T("energy", 285, "Wh", "Nominal Capacity 100Ah 285Wh", "nominal", E_UNSTATED),
        T("nominal_voltage", 2.85, "V", "Nominal Voltage 2.85V", "nominal"),
        T("discharge_cutoff_voltage", 1.5, "V", "Voltage Range 1.5V-3.4V", "minimum", {"extra": {"source_label": "Voltage Range"}}),
        T("charge_cutoff_voltage", 3.4, "V", "Voltage Range 1.5V-3.4V", "maximum", {"extra": {"source_label": "Voltage Range"}}),
        T("specific_energy", 90, "Wh/kg", "Energy Density ≥90Wh/Kg", "minimum",
          {**E_UNSTATED, "extra": {"source_comparator": "≥"}}, lower=True),
        T("max_continuous_charge_rate", 1, "C-rate", "Max. Charge Rate 1C/300A Cont. 3C 300A Peak 10s", "maximum",
          {"direction": "charge", "unstated": ["temperature_c"],
           "extra": {"rate_reference": C_REF, "conflict": "printed with 300 A, which is not 1C of 100 Ah; the ampere figure is not recorded"}}),
        T("max_continuous_discharge_current", 100, "A", "Max. Discharge Rate 1C/100A Cont. 3C/300A Peak 10s", "maximum",
          {"direction": "discharge", "unstated": ["temperature_c"], "extra": {"rate_label": "1C"}}),
        T("max_pulse_discharge_current", 300, "A", "Max. Discharge Rate 1C/100A Cont. 3C/300A Peak 10s", "maximum",
          {"direction": "discharge", "pulse_duration_s": 10, "unstated": ["temperature_c"], "extra": {"rate_label": "3C"}}),
        T("internal_resistance_ac", 0.4, "mohm", "Internal Resistance 1KHz AC≤0.4mΩ at 50% SOC", "maximum",
          {"frequency_hz": 1000, "soc_pct": 50, "unstated": ["temperature_c"], "extra": {"source_comparator": "≤"}}, upper=True),
        T("thickness", 54, "mm", "Dimension 54-173-204mm (T x W x H)"),
        T("width", 173, "mm", "Dimension 54-173-204mm (T x W x H)"),
        T("height", 204, "mm", "Dimension 54-173-204mm (T x W x H)"),
        with_tol(obs("thickness", 53.7, "mm", D("Dimension drawing", "53.7±0.5"), None,
                     {"extra": {"drawing_label": "53.7±0.5 (top view, across the terminals)"}})),
        with_tol(obs("width", 173.5, "mm", D("Dimension drawing", "173.5±0.8"), None,
                     {"extra": {"drawing_label": "173.5±0.8 (top view)"}}), 0.8, 0.8),
        with_tol(obs("height", 207.2, "mm", D("Dimension drawing", "207.2±0.8 204.4±0.6"), None,
                     {"extra": {"drawing_label": "207.2±0.8 (front view, outer dimension line)",
                                "note": "which features each drawn height includes is not stated"}}), 0.8, 0.8),
        with_tol(obs("height", 204.4, "mm", D("Dimension drawing", "207.2±0.8 204.4±0.6"), None,
                     {"extra": {"drawing_label": "204.4±0.6 (front view, inner dimension line)",
                                "note": "which features each drawn height includes is not stated"}}), 0.6, 0.6),
        T("cycle_life", 8000, "cycles", "Cycle Life ≥8000 Times @0.5C/0.5C 100% DOD at RT 300kgf", "minimum",
          {"rate_value": 0.5, "rate_unit": "C", "rate_reference_source": C_REF, "dod_pct": 100,
           "unstated": ["rate_reference_capacity_ah", "temperature_c"],
           "extra": {"source_comparator": "≥", "rate_direction": "0.5C charge / 0.5C discharge", "temperature_text": "RT",
                     "fixture_force": "300 kgf", "end_of_life_criterion": "not stated"}}, lower=True),
        T("capacity_retention", 80, "%", "-40℃ 0.5C Discharge Capacity ≥80% VS 25℃", "minimum",
          {"temperature_c": -40, "rate_value": 0.5, "rate_unit": "C", "rate_reference_source": C_REF,
           "unstated": ["cycle_index", "rate_reference_capacity_ah"],
           "extra": {"source_comparator": "≥", "relative_to": "0.5C discharge capacity at 25 °C"}}, lower=True),
        T("mass", 3.3, "kg", "Approx. Weight 3.3kg", "typical", {"extra": {"source_label": "Approx. Weight"}}),
    ]
    o += ds_temps((0, 60), (-40, 60), "Charge: 0℃~60℃", "Disharge: -40℃~60℃")
    chem = {"designation": "Sodium-ion", "cathode_text": "NFPP",
            "locator": D("Title", "Rechargeable Sodium ion Battery PRODUCT DATASHEET NFPP54173204-285Wh")}
    return document("NFPP54173204-285Wh", "prismatic_hardcase", s, o, chem)


def build() -> dict:
    docs = [sheet_record(r) for r in SHEET_ROWS] + [jnp1814867(), nacr46145(), nacp51160120(),
                                                    nfpp54173204(), me170(), he175()]
    uids = [d["product"]["uid"] for d in docs]
    assert len(uids) == len(set(uids)), "duplicate uid in batch"
    return {
        "schema_version": 1,
        "batch": "2026-10-28-partner-sodium-ion-cells",
        "note": ("Sodium-ion cells from documents a commercial partner supplied to Lemonergy, filed under "
                 "the owner instruction to add them with the producer only where a document names it (none "
                 "do) and without the partner's identity or contact details. Acceptance validates source "
                 "transcription, not cell performance. Lemonergy's stock statement is in offers/lemonergy.json. "
                 "See review/audits/2026-10-28-partner-sodium-ion-cells.json."),
        "candidates": [{"document": d} for d in docs],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed batch differs")
    a = ap.parse_args()
    body = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if a.check:
        if not BATCH.exists() or BATCH.read_text(encoding="utf-8") != body:
            print(f"{BATCH.relative_to(ROOT)} is stale; run tools/import_partner_sodium_cells.py", file=sys.stderr)
            return 1
        print(f"ok: {BATCH.relative_to(ROOT)} is current")
        return 0
    BATCH.write_text(body, encoding="utf-8")
    n = len(json.loads(body)["candidates"])
    print(f"wrote {BATCH.relative_to(ROOT)}: {n} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
