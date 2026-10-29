#!/usr/bin/env python3
"""Declare the first lead-acid batteries (29 October 2026) as a review batch.

The finder gained a Technology filter with Lead-acid and its variants (AGM,
gel, flooded, EFB) listed at zero. The owner asked for lead-acid batteries to
fill it, with one condition: they must never be offered for Lemonergy Design,
which is for lithium-ion and sodium-ion ("otherwise it is a mess"); a separate
lead-acid part follows later. The exclusion is a property of the technology
(``design: false`` in web/data/technologies-and-chemistries.json), not of these
records, so nothing here mentions Design.

Scope, chosen to cover the four variants across the three uses lead-acid is
bought for -- deep-cycle/solar, standby/UPS and engine starting:

=====================  ======================================  ===========
Source                 Products                                Variant
=====================  ======================================  ===========
Victron Energy sheet   12 AGM + 7 GEL Deep Cycle monoblocs     AGM, gel
Trojan T-105 sheet     T-105 6 V deep-cycle battery            flooded
Exide Sonnenschein     A600: 14 x 2 V OPzV cells, 4 blocks     gel
Exide Classic OPzS     21 x 2 V OPzS cells, 6 blocks           flooded
Yuasa NP sheets        NP4-12, NP7-12, NP12-12, NP17-12I,      AGM
                       NP12-6 (standby / UPS)
ODYSSEY Extreme page   16 AGM starting/deep-cycle batteries    AGM
VARTA Dynamic EFB      11 start-stop batteries (web pages)     EFB
=====================  ======================================  ===========

Conventions that only lead-acid needs (docs/23 explains each):

* An hour-rate capacity (C20, "20-hr rate", "20 hr. discharge") is stored as
  ``rate_value = 1/hours`` with ``rate_unit = "C"`` -- the 20-hour current is
  C20/20 by definition -- and the printed hour rate is kept in
  ``conditions.extra.hour_rate_h``.
* An end voltage printed per cell ("1.80 Vpc", "1.75 V/cell") is kept in
  ``extra.cutoff_per_cell_v``. ``voltage_lower_v`` holds the product's own
  terminal voltage: per-cell value x cells in series, where the cell count is
  printed (Trojan) or is the nominal voltage at 2 V per lead-acid cell.
* 6 V and 12 V monoblocs are ``kind: module`` (several cells in one case);
  2 V cells are ``kind: cell``.
* A resistance printed without its method (most lead-acid sheets) is held, not
  recorded: the library has no method-free resistance quantity by design
  (docs/02 section 7). Yuasa states 1 kHz, so its values are recorded as AC.
* A range ("13,5 - 13,8") is two observations, minimum and maximum, sharing
  one quote.

Each spec table is transcribed here as printed, so a value and its quote come
from the same string and cannot drift apart.

    python tools/import_lead_acid_batteries.py           # write the batch
    python tools/import_lead_acid_batteries.py --check   # fail if stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "review" / "batches" / "2026-10-29-lead-acid-batteries.json"
RETRIEVED = "2026-10-29"
FACTS = "Facts only; source body is not redistributed."
F_TO_C = {0: -17.8, 80: 26.7}  # temperatures printed only in Fahrenheit


def num(text: str):
    v = float(text.replace(",", "."))
    return int(v) if v.is_integer() else v


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9.]+", "-", text.lower())).strip("-")


def L(section: str, quote: str, page: int | None = None) -> dict:
    loc = {"section": section, "quote": quote}
    if page:
        loc["page"] = page
    return loc


def obs(q, v, u, loc, stat=None, cond=None, lower=False, upper=False, tol=None):
    o = {"quantity": q, "value": v, "unit": u, "locator": loc}
    if stat:
        o["statistic"] = stat
    if tol is not None:
        o["tol_plus"], o["tol_minus"] = tol, tol
    if lower:
        o["is_lower_bound"] = True
    if upper:
        o["is_upper_bound"] = True
    if cond:
        o["conditions"] = cond
    return o


def cond(unstated=(), extra=None, **known):
    c = {k: v for k, v in known.items() if v is not None}
    if unstated:
        c["unstated"] = list(unstated)
    if extra:
        c["extra"] = extra
    return c


def cells_in_series(volts: float) -> int:
    n = round(volts / 2)
    assert n >= 1 and abs(n * 2 - volts) < 1e-9, volts
    return n


def end_voltage(per_cell: float, volts: float) -> float:
    return round(per_cell * cells_in_series(volts), 3)


def hour_rate(hours: float, ref_ah, temp, per_cell, volts, label, unstated=()):
    """Capacity conditions for an hour-rate capacity (C20, C10, 5-Hr ...).

    The n-hour rate discharges at C_n / n, so the C in rate_value refers to the
    capacity being stated; the database requires that reference to be named.
    """
    extra = {"hour_rate_h": hours, "source_label": label}
    lower = None
    if per_cell is not None:
        lower = end_voltage(per_cell, volts)
        extra["cutoff_per_cell_v"] = per_cell
        if cells_in_series(volts) > 1:
            extra["voltage_lower_basis"] = (f"{per_cell} V per cell x {cells_in_series(volts)} cells "
                                            f"(nominal {volts:g} V at 2 V per lead-acid cell)")
    miss = list(unstated)
    if temp is None:
        miss.append("temperature_c")
    if lower is None:
        miss.append("voltage_lower_v")
    return cond(miss, extra, rate_value=round(1 / hours, 4), rate_unit="C",
                rate_reference_capacity_ah=ref_ah,
                rate_reference_source=f"{hours:g}-hour rate: the current is this {hours:g}-hour capacity divided by {hours:g} h",
                temperature_c=temp, voltage_lower_v=lower)


def range_obs(q, lo, hi, u, loc, c):
    return [obs(q, lo, u, loc, "minimum", c), obs(q, hi, u, loc, "maximum", c)]


def document(kind, maker, maker_slug, model, source, observations, chemistry,
             aliases=None, form_factor="prismatic_hardcase", ffc=None):
    product = {"uid": f"{kind}/{maker_slug}/{slug(model)}", "kind": kind, "manufacturer": maker,
               "model_number": model, "is_rechargeable": True, "form_factor": form_factor}
    if ffc:
        product["form_factor_code"] = ffc
    if aliases:
        product["aliases"] = aliases
    return {"schema_version": "1", "product": product, "source": source,
            "chemistry": chemistry, "observations": observations}


def lead(variant: str, loc: dict, electrolyte: str | None = None) -> dict:
    c = {"designation": f"Lead-acid {variant}", "locator": loc}
    if electrolyte:
        c["electrolyte_text"] = electrolyte
    return c


# ====================================================================== Victron
VICTRON_URL = "https://www.victronenergy.com/upload/documents/Datasheet-GEL-and-AGM-Batteries-EN.pdf"
VICTRON_SOURCE = {
    "uid": "src/victron-gel-and-agm-batteries-datasheet-2025-12",
    "kind": "datasheet",
    "title": "Victron Energy Gel and AGM Batteries datasheet (EN)",
    "url": VICTRON_URL,
    "retrieved_at": RETRIEVED,
    "sha256": "0581f9e3039e42280903e1b0bceeaa39feb1bf968a990cb7e0f0f9e475e0981b",
    "license": "proprietary",
    "redistributable": False,
    "note": " ".join([
        FACTS, "Four-page Victron Energy datasheet (1,028,647 bytes; PDF created 2025-12-09; no printed date or "
        "revision). Page 4 tables give article number, Ah, V, l x w x h, weight, CCA @0°F and RES CAP @80°F per "
        "battery; pages 1-4 give range-wide statements recorded on every battery of the range they name.",
        "Capacity: 'Rated capacity: 20 hr. discharge at 25°C'; page 1 says the rated capacity 'refers to 20 hour "
        "discharge, in other words: a discharge current of 0,05 C' and Table 1 gives 10,8 V as the end voltage of "
        "the 20-hour discharge. Table 1 is printed for the 12 V range, so the 6 V AGM battery's end voltage is "
        "recorded as unstated.",
        "CCA and RES CAP are printed without units; CCA is read as amperes and RES CAP as minutes, the units these "
        "ratings are defined in. Their temperatures are printed in Fahrenheit only and converted (0°F = -17.8 °C, "
        "80°F = 26.7 °C). Neither rating states its standard, duration, current or end voltage.",
        "Charge voltages are Table 3 settings 'for a 12 V battery' and are recorded on the 12 V batteries only, "
        "at the 25 °C centre point that section 14 names for temperature compensation. Storage-mode voltages, the "
        "-4 mV/°C per cell compensation, Table 1's capacity-versus-discharge-time percentages and the cycle-life "
        "and temperature graphs are not recorded. Small AGM batteries (8-38 Ah) print no CCA or RES CAP.",
        "The article number BAT212200084 is printed with a space ('BAT2122000 84'); it is recorded without it.",
    ]),
}
# article, Ah, V, (l, w, h), kg, CCA, RES CAP  -- page 4, as printed
VICTRON_AGM = [
    ("BAT406225084", "240", "6", "320 x 176 x 247", "31", "700", "270"),
    ("BAT212070084", "8", "12", "151 x 65 x 101", "2,5", None, None),
    ("BAT212120086", "14", "12", "151 x 98 x 101", "4,4", None, None),
    ("BAT212200084", "22", "12", "181 x 77 x 167", "5,8", None, None),
    ("BAT412350084", "38", "12", "197 x 165 x 170", "12,5", None, None),
    ("BAT412550084", "60", "12", "229 x 138 x 227", "20", "280", "80"),
    ("BAT412800084", "90", "12", "350 x 167 x 183", "27", "400", "130"),
    ("BAT412101084", "110", "12", "330 x 171 x 220", "32", "500", "170"),
    ("BAT412121084", "130", "12", "410 x 176 x 227", "38", "550", "200"),
    ("BAT412151084", "165", "12", "485 x 172 x 240", "47", "600", "220"),
    ("BAT412201084", "220", "12", "522 x 238 x 240", "65", "650", "250"),
    ("BAT412124081", "240", "12", "522 x 240 x 224", "67", "650", "250"),
]
VICTRON_GEL = [
    ("BAT412550104", "60", "12", "229 x 138 x 227", "20", "250", "70"),
    ("BAT412800104", "90", "12", "350 x 167 x 183", "26", "360", "120"),
    ("BAT412101104", "110", "12", "330 x 171 x 220", "33", "450", "150"),
    ("BAT412121104", "130", "12", "410 x 176 x 227", "38", "500", "180"),
    ("BAT412151104", "165", "12", "485 x 172 x 240", "48", "550", "200"),
    ("BAT412201104", "220", "12", "522 x 238 x 240", "66", "600", "220"),
    ("BAT412126101", "265", "12", "520 x 268 x 223", "75", "650", "250"),
]
VICTRON_RANGE = {
    "AGM": {
        "table": "12 Volt Deep Cycle AGM",
        "technology": "Technology: flat plate AGM",
        "float_life": "Float design life: 7 -10 years at 20°C",
        "float_life_years": (7, 10),
        "cycles": [("400 cycles at 80% discharge", 400, 80), ("600 cycles at 50% discharge", 600, 50),
                   ("1500 cycles at 30% discharge", 1500, 30)],
        "life_table": [("30°C / 86°F", 30, 4), ("40°C / 104°F", 40, 2)],
        "pulse": ("5 seconds | 8 C | 7 C", 8),
        "absorption": [("Absorption | 14,2 - 14,6 | 14,6 - 14,9", "14,2", "14,6", "Cycle service, normal"),
                       ("Absorption | 14,2 - 14,6 | 14,6 - 14,9", "14,6", "14,9", "Cycle service, fastest recharge")],
        "float": "Float | 13,5 - 13,8 | 13,5 - 13,8 | 13,5 - 13,8",
        "electrolyte": "Electrolyte absorbed into a glass-fibre mat between the plates (AGM)",
        "electrolyte_quote": "AGM stands for Absorbent Glass Mat. In these batteries the electrolyte is absorbed into a "
                             "glass -fibre mat between the plates by capillary action.",
    },
    "gel": {
        "table": "12 Volt Deep Cycle GEL",
        "technology": "Technology: flat plate GEL",
        "float_life": "Float design life: 12 years at 20°C",
        "float_life_years": (12, 12),
        "cycles": [("500 cycles at 80% discharge", 500, 80), ("750 cycles at 50% discharge", 750, 50),
                   ("1800 cycles at 30% discharge", 1800, 30)],
        "life_table": [("30°C / 86°F", 30, 6), ("40°C / 104°F", 40, 3)],
        "pulse": ("5 seconds | 8 C | 7 C", 7),
        "absorption": [("Absorption | 14,1 - 14,4", "14,1", "14,4", "Cycle service, normal")],
        "float": "Float | 13,5 - 13,8 | 13,5 - 13,8",
        "electrolyte": "Electrolyte immobilized as gel",
        "electrolyte_quote": "Here the electrolyte is immobilized as gel.",
    },
}


def victron(row, variant: str) -> dict:
    art, ah, v, dims, kg, cca, rc = row
    R = VICTRON_RANGE[variant]
    tab = f"Page 4, {R['table']} table, row {art}"
    volts = num(v)
    twelve = volts == 12
    cap = hour_rate(20, num(ah), 25, None, volts, "Rated capacity: 20 hr. discharge at 25°C")
    cap["extra"]["rate_basis"] = "Page 1: 'a discharge current of 0,05 C'"
    if twelve:  # Table 1's 10,8 V end voltage is printed for the 12 V range
        cap["unstated"].remove("voltage_lower_v")
        cap["voltage_lower_v"] = 10.8
        cap["extra"]["voltage_lower_basis"] = "Page 1, Table 1: end voltage 10,8 V for the 20-hour discharge"
        if not cap["unstated"]:
            del cap["unstated"]
    o = [obs("capacity", num(ah), "Ah",
             L(tab + ", column Ah, and General Specification", f"{art} · Ah: {ah} · Rated capacity: 20 hr. discharge at 25°C", 4),
             "rated", cap),
         obs("nominal_voltage", volts, "V", L(tab + ", column V", f"{art} · V: {v}", 4), "nominal")]
    l, w, h = (num(x) for x in dims.split(" x "))
    for q, val in (("length", l), ("width", w), ("height", h)):
        o.append(obs(q, val, "mm", L(tab + ", column l x w x h mm", f"{art} · l x w x h: {dims} mm", 4)))
    o.append(obs("mass", num(kg), "kg", L(tab + ", column Weight kg", f"{art} · Weight: {kg} kg", 4)))
    if cca:
        o.append(obs("cranking_current", num(cca), "A", L(tab + ", column CCA @0°F", f"{art} · CCA @0°F: {cca}", 4),
                     "rated", cond(["duration_s", "voltage_lower_v"],
                                   {"rating": "CCA", "temperature_printed": "0°F", "standard": "not stated"},
                                   temperature_c=F_TO_C[0])))
    if rc:
        o.append(obs("reserve_capacity", num(rc), "min", L(tab + ", column RES CAP @80°F", f"{art} · RES CAP @80°F: {rc}", 4),
                     "rated", cond(["rate_value", "rate_unit", "voltage_lower_v"],
                                   {"source_label": "RES CAP @80°F", "temperature_printed": "80°F",
                                    "unit_basis": "printed without a unit; reserve capacity is defined in minutes"},
                                   temperature_c=F_TO_C[80])))
    gs = f"Page 4, {R['table']} General Specification"
    lo, hi = R["float_life_years"]
    life_c = cond(["soc_pct"], {"basis": "Float design life", "service": "float"}, temperature_c=20)
    if lo == hi:
        o.append(obs("calendar_life", lo, "year", L(gs, R["float_life"], 4), "design", life_c))
    else:
        o += [obs("calendar_life", x, "year", L(gs, R["float_life"], 4), s, life_c)
              for x, s in ((lo, "minimum"), (hi, "maximum"))]
    for row_label, tc, yr in R["life_table"]:
        o.append(obs("calendar_life", yr, "year",
                     L("Page 1, Table 2: Design service life of Victron batteries under float service",
                       f"{'AGM' if variant == 'AGM' else 'Gel'} 'Deep Cycle' years · {row_label}: {yr}", 1),
                     "design", cond(["soc_pct"], {"basis": "Design service life under float service", "service": "float"},
                                    temperature_c=tc)))
    for text, n, dod in R["cycles"]:
        o.append(obs("cycle_life", n, "cycles", L(gs + ", Cycle design life", f"Cycle design life: {text}", 4), "design",
                     cond(["temperature_c", "rate_value", "rate_unit"], {"source_label": "Cycle design life"}, dod_pct=dod)))
    pq, pv = R["pulse"]
    o.append(obs("max_pulse_discharge_rate", pv, "C-rate",
                 L("Page 1, Table 1, lowest row ('the maximum allowable 5 seconds discharge current')",
                   f"{pq} (AGM 'Deep Cycle' | Gel 'Deep Cycle')", 1), "maximum",
                 cond(["temperature_c"], {"rate_reference": "C as used for the rated 20-hour capacity"}, pulse_duration_s=5)))
    o.append(obs("max_continuous_charge_rate", 0.2, "C-rate",
                 L("Page 3, section 15: Charge current",
                   "The charge current s hould preferably not exceed 0,2 C (20A for a 100Ah battery).", 3), "maximum",
                 cond(["temperature_c"], {"source_label": "should preferably not exceed",
                                         "note": "Temperature compensation is required above 0,2 C"})))
    o.append(obs("self_discharge_rate", 2, "%/month",
                 L("Page 1, section 4: Low Self-Discharge",
                   "The rate of self -discharge is less than 2% per month at 20°C.", 1), "maximum",
                 cond(["soc_pct", "duration_s"], {"note": "The self-discharge doubles for every increase in temperature by 10°C."},
                      temperature_c=20), upper=True))
    if twelve:
        t3 = "Page 4, Table 3: Recommended charge voltage (12 V battery)"
        t3c = {"basis": "Section 14: the centre point for temperature compensation is 25°C"}
        for quote, a, b, service in R["absorption"]:
            o += range_obs("cyclic_charge_voltage", num(a), num(b), "V",
                           L(t3, f"Victron {variant if variant == 'AGM' else 'Gel'} 'Deep Cycle' · {quote}", 4),
                           cond([], {**t3c, "service": service, "source_label": "Absorption"}, temperature_c=25))
        o += range_obs("float_charge_voltage", 13.5, 13.8, "V",
                       L(t3, f"Victron {variant if variant == 'AGM' else 'Gel'} 'Deep Cycle' · {R['float']}", 4),
                       cond([], {**t3c, "source_label": "Float"}, temperature_c=25))
    chem = lead(variant, L(gs + " and page 1", f"{R['technology']} · {R['electrolyte_quote']}", 4), R["electrolyte"])
    return document("module", "Victron Energy", "victron-energy", art, VICTRON_SOURCE, o, chem)


# ======================================================================= Trojan
TROJAN_SOURCE = {
    "uid": "src/trojan-t-105-datasheet-ds-020819",
    "kind": "datasheet",
    "title": "Trojan Battery T-105 datasheet",
    "url": "https://assets.ctfassets.net/nh2mdhlonj7m/3RwDBLAA3SCrYnhfDrQnKl/01b3929a9ced420254efa6ced4fb9ab4/T105_Trojan_Data_Sheets.pdf",
    "revision": "T-105.DS_020819",
    "document_date": "2019",
    "retrieved_at": RETRIEVED,
    "sha256": "79c4f8a6f2f3ba4245b5151945de27af40e52cd8b69078e7ce0f785d789602d5",
    "license": "proprietary",
    "redistributable": False,
    "note": " ".join([
        FACTS, "Two-page Trojan Battery Company datasheet (937,294 bytes), linked as 'T-105 6V FLOODED BATTERY "
        "DATASHEET' from https://www.trojanbattery.com/products/t-105-6v-flooded-battery. Printed '© 2019'.",
        "Capacities (footnote B) and minutes (footnote A) are at a constant rate at 80°F (27°C) to 1.75 V/cell; "
        "the sheet adds 'Capacities are based on peak performance.' The battery has 3 cells (printed), so the end "
        "voltage is 5.25 V. Hour-rate capacities are stored as 1/hours C.",
        "C.C.A. and C.A. are printed as '—' (no cranking rating), as are internal resistance and short-circuit "
        "current; none is recorded. Charger settings are the 6 V column at 77°F/25°C. The open-circuit-voltage "
        "rows are the 6 VOLT column of the state-of-charge table; specific gravity and per-cell voltages are not "
        "recorded. Dimensions are the millimetre figures; footnotes C and F say they vary with handle and terminal "
        "type. The product page prints slightly different dimensions (width 7.11 in (181), height 11.07 in (281)); "
        "the datasheet's figures are recorded. The performance and capacity-versus-temperature graphs are not "
        "digitised.",
    ]),
}


def trojan() -> list[dict]:
    s, ph, el = "Page 1, PHYSICAL SPECIFICATIONS", "Page 1, ELECTRICAL SPECIFICATIONS", "Page 1, CHARGING INSTRUCTIONS"
    row = "GC2 | T-105 | 6 | 3 | 1, 2, 3, 4 | 10.30 (262) | 7.13 (181) | 11.15 (283) | 62 (28)"
    foot = "Page 2, footnote B: 'The amount of amp-hours (Ah) a battery can deliver when discharged at a constant rate at 80°F (27°C) and maintain a voltage above 1.75 V/cell.'"
    o = []
    for hours, ah in ((20, 225), (5, 185), (10, 207), (100, 250)):
        c = hour_rate(hours, ah, 27, 1.75, 6, f"{hours}-Hr")
        c["extra"]["voltage_lower_basis"] = "1.75 V per cell x 3 cells (CELL(S) 3 printed)"
        c["extra"]["note"] = "Capacities are based on peak performance."
        o.append(obs("capacity", ah, "Ah", L(el + ", CAPACITY B AMP-HOURS (Ah); " + foot,
                                             f"CAPACITY B AMP-HOURS (Ah) · {hours}-Hr: {ah}", 1), "rated", c))
    o.append(obs("nominal_voltage", 6, "V", L(s, "VOLTAGE | 6", 1), "nominal"))
    o.append(obs("series_count", 3, "1", L(s, f"BCI | MODEL NAME | VOLTAGE | CELL(S) · {row}", 1)))
    for q, val in (("length", 262), ("width", 181), ("height", 283)):
        o.append(obs(q, val, "mm", L(s + ", DIMENSIONS C INCHES (mm); height per footnote F is to the highest point",
                                     f"LENGTH | WIDTH | HEIGHT F · {row}", 1)))
    o.append(obs("mass", 28, "kg", L(s + ", WEIGHT H LBS.(kg); footnote H: weight may vary", f"WEIGHT H LBS.(kg) · {row}", 1)))
    ra = "Page 2, footnote A: 'The number of minutes a battery can deliver when discharged at a constant rate at 80°F (27°C) and maintain a voltage above 1.75 V/cell.'"
    for amps, mins in ((25, 447), (75, 115)):
        o.append(obs("reserve_capacity", mins, "min", L(el + ", CAPACITY A MINUTES; " + ra,
                                                        f"CAPACITY A MINUTES · @ {amps} Amps: {mins}", 1), "rated",
                     cond([], {"cutoff_per_cell_v": 1.75, "voltage_lower_basis": "1.75 V per cell x 3 cells",
                               "source_label": "CAPACITY A MINUTES", "note": "Capacities are based on peak performance."},
                          rate_value=amps, rate_unit="A", temperature_c=27, voltage_lower_v=5.25)))
    o.append(obs("energy", 1.5, "kWh", L(el, "ENERGY (kWh) · 100-Hr: 1.50", 1), "rated",
                 cond(["temperature_c"], {"hour_rate_h": 100, "source_label": "ENERGY (kWh) 100-Hr"},
                      rate_value=0.01, rate_unit="C", rate_reference_capacity_ah=250,
                      rate_reference_source="100-Hr rate: the 100-hour capacity printed beside it (250 Ah)")))
    cs = cond([], {"source_label": "CHARGER VOLTAGE SETTINGS (AT 77°F/25°C), SYSTEM VOLTAGE 6V",
                   "temperature_compensation": "0.005 volt per cell for every 1°C below/above 25°C (add/subtract)"},
              temperature_c=25)
    o.append(obs("cyclic_charge_voltage", 7.41, "V", L(el, "Bulk Charge | 7.41 (6V)", 1), "standard",
                 {**cs, "extra": {**cs["extra"], "source_label": cs["extra"]["source_label"] + ", Bulk Charge"}}))
    o.append(obs("float_charge_voltage", 6.75, "V", L(el, "Float Charge | 6.75 (6V)", 1), "standard", cs))
    o.append(obs("equalize_charge_voltage", 8.10, "V", L(el, "Equalize Charge | 8.10 (6V)", 1), "standard", cs))
    ot = "OPERATING TEMPERATURE -4°F to 113°F (-20°C to +45°C)."
    oc = cond(["temperature_reference", "direction"],
              {"note": "At temperatures below 32°F (0°C) maintain a state of charge greater than 60%."})
    o.append(obs("operating_temperature_min", -20, "°C", L("Page 1, OPERATIONAL DATA", ot, 1), "minimum", oc))
    o.append(obs("operating_temperature_max", 45, "°C", L("Page 1, OPERATIONAL DATA", ot, 1), "maximum", oc))
    sd = "SELF DISCHARGE 5 – 15% per month depending on storage temperature conditions."
    sdc = cond(["temperature_c", "soc_pct", "duration_s"], {"note": "depending on storage temperature conditions"})
    o += range_obs("self_discharge_rate", 5, 15, "%/month", L("Page 1, OPERATIONAL DATA", sd, 1), sdc)
    for soc, volt in ((100, "6.37"), (90, "6.31"), (80, "6.25"), (70, "6.19"), (60, "6.12"), (50, "6.05"),
                      (40, "5.98"), (30, "5.91"), (20, "5.83"), (10, "5.75")):
        o.append(obs("open_circuit_voltage", num(volt), "V",
                     L("Page 1, STATE OF CHARGE MEASURE OF OPEN-CIRCUIT VOLTAGE, 6 VOLT column",
                       f"PERCENTAGE CHARGE {soc} · 6 VOLT {volt}", 1), "typical",
                     cond(["temperature_c", "direction", "rest_before_s"], soc_pct=soc)))
    chem = lead("flooded", L("Page 1, product data", "BATTERY | Deep-Cycle Flooded/Wet Lead-Acid Battery", 1))
    return [document("module", "Trojan Battery", "trojan-battery", "T-105", TROJAN_SOURCE, o, chem,
                     aliases=["T-105 with Bayonet Cap"], ffc="BCI GC2")]


# ======================================================================== Exide
def exide_source(uid, title, url, sha, size, created, pages, extra):
    return {"uid": uid, "kind": "datasheet", "title": title, "url": url, "retrieved_at": RETRIEVED,
            "sha256": sha, "license": "proprietary", "redistributable": False,
            "note": " ".join([FACTS, f"{pages}-page Exide technical data sheet ({size} bytes; PDF created {created}; "
                              "no printed date or revision).", extra])}


A600_SOURCE = exide_source(
    "src/exide-sonnenschein-a600-technical-data-sheet-2023-04", "Sonnenschein A600 Technical data sheet",
    "https://www.exidegroup.com/nz/sites/default/files/2023-04/230404_Sonnenschein_A600_technicaldata.pdf",
    "7aebed8bf66aa876082efb665f6855359cf3369be29649bd2dc40d278ef81e1c", "381,728", "2023-04-04", 10,
    "Main table on page 1: nominal capacity C10 to 1.80 Vpc at 20 °C; dimensions are maxima; weight is approximate; "
    "h2 includes the installed connector. The 'Type acc. to DIN' column prints a footnote digit after each type "
    "(superscript 1 = DIN 40 742 cells, 2 = DIN 40 744 blocks); the types are recorded without it. The datasheet "
    "does not name the electrolyte: the gel designation comes from Exide's own A600 product page "
    "(https://www.exidegroup.com/eu/en/product/sonnenschein-a600, retrieved 2026-10-29: 'Valve regulated Gel "
    "technology (VRLA)'). Internal resistance is printed without its method and is not recorded (the library "
    "keeps AC and DC resistance apart and has no method-free quantity). The constant-current and constant-power "
    "discharge tables (pages 3-10, 1.60-1.90 Vpc, 3 min-10 h) are not transcribed; they are kept for the later "
    "lead-acid design work. Shelf life ('up to 2 years at 20 °C without recharge') is not recorded.")
# type, part number, DIN type as printed, V, C10 Ah, l, w, h1, h2, kg, IR, Isc
A600 = [
    ("A602/225", "NGA6020225HS0FA", "4 OPzV 2001", "2", "224", "105", "208", "357", "399", "17.4", "0.95", "2200"),
    ("A602/280", "NGA6020280HS0FA", "5 OPzV 2501", "2", "280", "126", "208", "357", "399", "22.0", "0.79", "2700"),
    ("A602/335", "NGA6020335HS0FA", "6 OPzV 3001", "2", "337", "147", "208", "357", "399", "25.0", "0.61", "3350"),
    ("A602/415", "NGA6020415HS0FA", "5 OPzV 3501", "2", "416", "126", "208", "473", "515", "30.0", "0.62", "3300"),
    ("A602/500", "NGA6020500HS0FA", "6 OPzV 4201", "2", "499", "147", "208", "473", "515", "35.0", "0.53", "3950"),
    ("A602/580", "NGA6020580HS0FA", "7 OPzV 4901", "2", "582", "168", "208", "473", "515", "39.0", "0.47", "4400"),
    ("A602/750", "NGA6020750HS0FA", "6 OPzV 6001", "2", "748", "147", "208", "648", "690", "49.0", "0.48", "4300"),
    ("A602/1010", "NGA6021010HS0FA", "8 OPzV 8001", "2", "998", "212", "193", "648", "690", "66.0", "0.38", "4850"),
    ("A602/1250", "NGA6021250HS0FA", "10 OPzV 10001", "2", "1248", "212", "235", "648", "690", "80.0", "0.33", "6250"),
    ("A602/1510", "NGA6021510HS0FA", "12 OPzV 12001", "2", "1497", "212", "277", "648", "690", "95.0", "0.29", "7850"),
    ("A602/1650C", "NGA6021650HS0FA", "12 OPzV 15001", "2", "1643", "212", "277", "717", "759", "106", "0.23", "9000"),
    ("A602/2200", "NGA6022200HS0FA", "16 OPzV 20001", "2", "2190", "216", "400", "775", "816", "149", "0.19", "10750"),
    ("A602/2740", "NGA6022740HS0FA", "20 OPzV 25001", "2", "2738", "214", "489", "774", "816", "190", "0.16", "13400"),
    ("A602/3300", "NGA6023300HS0FA", "24 OPzV 30001", "2", "3286", "214", "578", "774", "816", "238", "0.13", "16100"),
    ("A606/200", "NGA6060200HS0FC", "6V 4 OPzV 2002", "6", "200", "272", "206", "323", "347", "45.7", "2.71", "1707"),
    ("A606/300", "NGA6060300HS0FC", "6V 6 OPzV 3002", "6", "300", "380", "206", "323", "347", "65.4", "1.90", "2614"),
    ("A612/100", "NGA6120100HS0FC", "12V 2 OPzV 1002", "12", "100", "272", "206", "323", "347", "46.2", "9.68", "1934"),
    ("A612/150", "NGA6120150HS0FC", "12V 3 OPzV 1502", "12", "150", "380", "206", "323", "347", "66.9", "6.43", "2896"),
]
A600_COLS = ("Type | Part number | Type acc. to DIN | Nom. voltage V | Nominal capacity C10 1.80 Vpc 20 °C Ah | "
             "Length (l) max. mm | Width (w) max. mm | Height (h1) max. mm | Height (h2)* max. mm | Weight approx. kg | "
             "Internal resistance mOhm | Short circuit current A | Terminal | Pole pairs")


def a600(row) -> dict:
    typ, part, din, v, c10, l, w, h1, h2, kg, _ir, isc = row
    volts, cell = num(v), v == "2"
    printed = " | ".join(row) + " | F-M8"
    tab = f"Page 1, Technical characteristics and data, row {typ}"
    q = f"{printed}"
    o = [obs("capacity", num(c10), "Ah", L(tab + ", column Nominal capacity C10 1.80 Vpc 20 °C", q, 1), "nominal",
             hour_rate(10, num(c10), 20, 1.80, volts, "Nominal capacity C10 1.80 Vpc 20 °C")),
         obs("nominal_voltage", volts, "V", L(tab + ", column Nom. voltage", q, 1), "nominal")]
    for qq, val, col in (("length", l, "Length (l) max."), ("width", w, "Width (w) max."), ("height", h1, "Height (h1) max.")):
        o.append(obs(qq, num(val), "mm", L(f"{tab}, column {col} mm", q, 1), "maximum"))
    o.append(obs("height", num(h2), "mm", L(f"{tab}, column Height (h2)* max. mm", q, 1), "maximum",
                 cond([], {"source_label": "Height (h2)*", "note": "* Includes installed connector"})))
    o.append(obs("mass", num(kg), "kg", L(f"{tab}, column Weight approx. kg", q, 1), "typical"))
    o.append(obs("short_circuit_current", num(isc), "A", L(f"{tab}, column Short circuit current A", q, 1), None,
                 cond(["temperature_c"], {"standard": "not stated on the sheet; designed in accordance with IEC 60896-21/22"})))
    life = 20 if cell else 15
    o.append(obs("calendar_life", life, "year",
                 L("Page 1, Technical features",
                   "Design life: 15 years for 6/12 V blocks and 20 years for 2 V cells at 20 °C (80% remaining capacity from C10)", 1),
                 "design", cond(["soc_pct"], {"basis": "Design life", "end_of_life": "80% remaining capacity from C10"},
                                temperature_c=20)))
    chem = lead("gel", L("Exide product page for the Sonnenschein A600 series (https://www.exidegroup.com/eu/en/product/sonnenschein-a600), "
                         "not the datasheet", "Valve regulated Gel technology (VRLA)"), "Gel (valve-regulated)")
    din_type = re.sub(r"[12]$", "", din)
    return document("cell" if cell else "module", "Exide", "exide", f"Sonnenschein {typ}", A600_SOURCE, o, chem,
                    aliases=[typ, part, din_type])


OPZS_SOURCE = exide_source(
    "src/exide-classic-opzs-technical-data-sheet-2024-03", "Classic OPzS Technical data sheet",
    "https://www.exidegroup.com/eu/sites/default/files/2024-03/Classic_OPzS_technicaldata.pdf",
    "4debaadb1419d7b9832aff17ad308430ab4287a473ea717b86e64a8869eed3af", "1,056,049", "2024-03-25", 15,
    "Reached from https://www.exidegroup.com/eu/en/document/classic-opzs-datasheet. Main table on page 2: nominal "
    "capacity C10 to 1.80 Vpc at 20 °C; dimensions are maxima; height includes the installed connector and 'can "
    "differ depending on the used vent(s)'; weight includes acid and 'may differ by ±5%'. The separate acid weight "
    "is not recorded. Flooded is read from the sheet's liquid electrolyte ('diluted sulphuric acid') and its "
    "'W (wet)' part-number code; the word 'flooded' is not printed. Internal resistance is printed without its "
    "method and is not recorded. The constant-current and constant-power discharge tables (pages 4-15) are not "
    "transcribed; they are kept for the later lead-acid design work.")
# type, part number, V, C10 Ah, l, L, w, h, kg incl. acid, kg acid, IR, Isc
OPZS = [
    ("6V 4 OPzS 200 LA", "NVZS060200WC0FB", "6", "200", "272", "282", "206", "347", "41.0", "13.0", "2.68", "2283"),
    ("6V 5 OPzS 250 LA", "NVZS060250WC0FB", "6", "250", "380", "392", "206", "347", "56.0", "20.0", "2.39", "2800"),
    ("6V 6 OPzS 300 LA", "NVZS060300WC0FB", "6", "300", "380", "392", "206", "347", "63.0", "20.0", "1.96", "3106"),
    ("12V 1 OPzS 50 LA", "NVZS120050WC0FB", "12", "50", "272", "282", "206", "347", "34.0", "15.0", "18.1", "688"),
    ("12V 2 OPzS 100 LA", "NVZS120100WC0FB", "12", "100", "272", "282", "206", "347", "43.0", "14.0", "9.26", "1314"),
    ("12V 3 OPzS 150 LA", "NVZS120150WC0FB", "12", "150", "380", "392", "206", "347", "64.0", "19.0", "6.46", "1884"),
    ("2 OPzS 100 LA", "NVZS020100WC0FB", "2", "105", "105", "115", "208", "395", "13.7", "5.20", "1.45", "1400"),
    ("3 OPzS 150 LA", "NVZS020150WC0FB", "2", "158", "105", "115", "208", "395", "15.2", "5.00", "1.05", "1950"),
    ("4 OPzS 200 LA", "NVZS020200WC0FB", "2", "210", "105", "115", "208", "395", "16.6", "4.60", "0.83", "2450"),
    ("5 OPzS 250 LA", "NVZS020250WC0FB", "2", "260", "126", "136", "208", "395", "20.0", "5.80", "0.72", "2850"),
    ("6 OPzS 300 LA", "NVZS020300WC0FB", "2", "310", "147", "157", "208", "395", "23.3", "6.90", "0.63", "3250"),
    ("5 OPzS 350 LA", "NVZS020350WC0FB", "2", "380", "126", "136", "208", "511", "26.7", "8.10", "0.63", "3250"),
    ("6 OPzS 420 LA", "NVZS020420WC0FB", "2", "455", "147", "157", "208", "511", "31.0", "9.30", "0.56", "3650"),
    ("7 OPzS 490 LA", "NVZS020490WC0FB", "2", "530", "168", "178", "208", "511", "35.4", "10.8", "0.50", "4100"),
    ("6 OPzS 600 LA", "NVZS020600WC0FB", "2", "680", "147", "157", "208", "686", "43.9", "13.0", "0.47", "4350"),
    ("7 OPzS 700 LA", "NVZS020700WC0FB", "2", "750", "147", "157", "208", "686", "47.2", "12.8", "0.43", "4800"),
    ("8 OPzS 800 LA", "NVZS020800WC0FB", "2", "910", "212", "222", "193", "686", "59.9", "17.1", "0.30", "6800"),
    ("9 OPzS 900 LA", "NVZS020900WC0FB", "2", "980", "212", "222", "193", "686", "63.4", "16.8", "0.27", "7500"),
    ("10 OPzS 1000 LA", "NVZS021000WC0FB", "2", "1140", "212", "222", "235", "686", "73.2", "21.7", "0.26", "7900"),
    ("12 OPzS 1200 LA", "NVZS021200WC0FB", "2", "1370", "212", "222", "277", "686", "86.4", "26.1", "0.23", "8900"),
    ("12 OPzS 1500 LA", "NVZS021500WC0FB", "2", "1700", "212", "222", "277", "836", "108", "33.7", "0.24", "8500"),
    ("14 OPzS 1750 LA", "NVZS021750WC0FB", "2", "1800", "212", "222", "277", "836", "114", "32.7", "0.22", "9300"),
    ("16 OPzS 2000 LA", "NVZS022000WC0FA", "2", "2250", "215", "225", "400", "812", "151", "50.0", "0.16", "12800"),
    ("18 OPzS 2250 LA", "NVZS022250WC0FA", "2", "2450", "215", "225", "400", "812", "158", "48.0", "0.14", "14600"),
    ("20 OPzS 2500 LA", "NVZS022500WC0FA", "2", "2800", "215", "225", "490", "812", "184", "60.0", "0.12", "17000"),
    ("22 OPzS 2750 LA", "NVZS022750WC0FA", "2", "3000", "215", "225", "490", "812", "191", "58.0", "0.11", "17800"),
    ("24 OPzS 3000 LA", "NVZS023000WC0FA", "2", "3350", "215", "225", "580", "812", "217", "71.0", "0.11", "18600"),
]


def opzs(row) -> dict:
    typ, part, v, c10, l, L_inst, w, h, kg, _acid, _ir, isc = row
    volts, cell = num(v), v == "2"
    q = " | ".join(row) + " | F-M8"
    tab = f"Page 2, Technical characteristics and data, row {typ}"
    o = [obs("capacity", num(c10), "Ah", L(tab + ", column Nominal capacity C10 1.80 Vpc 20 °C", q, 2), "nominal",
             hour_rate(10, num(c10), 20, 1.80, volts, "Nominal capacity C10 1.80 Vpc 20 °C")),
         obs("nominal_voltage", volts, "V", L(tab + ", column Nom. voltage", q, 2), "nominal"),
         obs("length", num(l), "mm", L(tab + ", column Length (l) max. mm", q, 2), "maximum"),
         obs("width", num(w), "mm", L(tab + ", column Width (w) max. mm", q, 2), "maximum"),
         obs("height", num(h), "mm", L(tab + ", column Height* (h) max. mm", q, 2), "maximum",
             cond([], {"note": "* Includes installed connector, the above mentioned height can differ depending on the used vent(s)."})),
         obs("length", num(L_inst), "mm", L(tab + ", column Installed length (L) max. mm", q, 2), "maximum",
             cond([], {"source_label": "Installed length (L)"})),
         obs("mass", num(kg), "kg", L(tab + ", column Weight incl. acid** approx. kg", q, 2), "typical",
             cond([], {"source_label": "Weight incl. acid", "note": "** Actual weight may differ by ±5%"})),
         obs("short_circuit_current", num(isc), "A", L(tab + ", column Short circuit current A", q, 2), None,
             cond(["temperature_c"], {"standard": "not stated on the sheet"})),
         obs("calendar_life", 20, "year",
             L("Page 1, Technical features", "• 20 years design life at 20 °C ambient temperature (until 80% nominal C10)", 1),
             "design", cond(["soc_pct"], {"basis": "Design life", "end_of_life": "80% nominal C10"}, temperature_c=20))]
    chem = lead("flooded", L("Page 1, Technical features and part-number note",
                             "Electrolyte: diluted sulphuric acid dN = 1.24 kg/l · Change W (wet) to D (dry) in the part number", 1),
                "Diluted sulphuric acid, dN = 1.24 kg/l")
    return document("cell" if cell else "module", "Exide", "exide", f"Classic {typ}", OPZS_SOURCE, o, chem,
                    aliases=[typ, part])


# ======================================================================== Yuasa
# sku as encoded in the download URL, model, bytes, sha256, V, CP/block, CP/cell, C20, C10,
# L, W, H (as printed), kg, terminal, float/block, cyclic/block, float I, cyclic I, 1 s, 1 min, Isc, IR, VdS
YUASA = [
    ("NP4-12%2F187%2FNF%2FBox", "NP4-12", 106162, "669ebf1d252ed143cef6008f656d6714e1f7792bafcca4a2848ec1aa3dc48313",
     "12", "86.22", "14.37", "4", "3.7", "90 (±1)", "70 (±1)", "105.5", "1.75", "Faston - 4.75mm",
     "13.65", "14.5", "1", "1", "120", "40", "120", "40", None),
    ("NP7-12%2F187%2FNF%2FBox", "NP7-12", 116474, "3d3d3ef88dafa3b7d8eaa5d6fcb0f6870f4e310971f337a0b47fe79e2cac0e32",
     "12", "150.9", "25.15", "7", "6.4", "151 (±1)", "65 (±1)", "97.5", "2.2", "Faston - 4.75mm",
     "13.65", "14.5", "1.75", "1.75", "210", "48", "500", "25", "VdS_No:_G_189099"),
    ("NP12-12%2F250%2FNF%2FBox", "NP12-12", 113233, "1a9eab3fe19e5dc9dfcdb40845d57ed47b44a5bbcb97e5a515bd86df8cf66cce",
     "12", "258.66", "43.11", "12", "11.1", "151 (±1)", "98 (±1)", "97.5 (±1)", "4.05", "Faston - 6.35mm",
     "13.65", "14.5", "3", "3", "360", "75", "320", "16", "VdS_No:_G189170"),
    ("NP17-12%2FI%2FNF%2FBox", "NP17-12I", 106827, "66900548f88e4f3b2fad038b273abebe54f10086bcc9e0d366929a5199ca14fb",
     "12", "366.48", "61.08", "17", "15.7", "181 (±1)", "76 (±1)", "167 (±2)", "6.1", "M5 (F)",
     "13.65", "14.5", "4.25", "4.25", "500", "150", "421", "15", "VdS_No:_G_197022"),
    ("NP12-6%2F250%2FNF%2FBox", "NP12-6", 119530, "95032494c80e1ec69f38c32dece5f3d72ade0da17490b2f0a3928578e1f807a4",
     "6", None, "43.11", "12", "11.1", "151 (±1)", "50 (±1)", "97.5 (±1)", "2.05", "Faston - 6.35mm",
     "6.825", "7.26", "3", "3", "360", "75", "360", "8", "VdS_No:_G_194006"),
]


def dim(text: str):
    m = re.fullmatch(r"([\d.]+)(?: \(±([\d.]+)\))?", text)
    return num(m.group(1)), (num(m.group(2)) if m.group(2) else None)


def yuasa(row) -> dict:
    (sku, model, size, sha, v, _cpb, _cpc, c20, c10, l, w, h, kg, term,
     fl, cy, fli, cyi, i1s, i1m, isc, ir, vds) = row
    volts = num(v)
    title = f"Yuasa {model} {v}V {c20}Ah - Yuasa NP series standby & cyclic AGM VRLA battery"
    src = {"uid": f"src/yuasa-{slug(model)}-technical-data-sheet-2026-10-29", "kind": "datasheet",
           "title": f"Yuasa Technical Data Sheet {model}",
           "url": f"https://www.yuasa.com/uk/datasheet/index/download/?sku={sku}",
           "retrieved_at": RETRIEVED, "sha256": sha, "license": "proprietary",
           "redistributable": False,
           "note": " ".join([
               FACTS, f"One-page datasheet generated on request by yuasa.com for SKU {sku.replace('%2F', '/')} "
               f"(linked from https://www.yuasa.com/uk/{model.lower()}); it prints 'Data Sheet generated on "
               f"29/10/2026 – E&OE'. That is the date the copy was generated, not a revision date, so no document "
               f"date is recorded. Each download is regenerated, so the SHA-256 ({size:,} bytes) identifies the "
               "copy inspected, not a revision.",
               "Capacities are '20-hr rate Capacity to 1.75V /Cell at 20°C' and '10-hr rate Capacity to 1.8V /Cell at "
               "20°C'; the per-cell end voltages are multiplied by the cells implied by the nominal voltage (the sheet "
               "also prints float voltage per block and per cell, 6:1 for 12 V). Charge voltages are per block at 20 °C "
               "with the printed tolerances (±1% float, ±3% cyclic) kept in extra; the per-cell values and the "
               "correction factors (-3 mV float, -4 mV cyclic, 'from std 20°C') are not recorded because the sheet "
               "does not say per what. The float and cyclic charge current limits are printed equal and recorded once. "
               "The 10-minute constant-power ratings are not recorded. Internal resistance is 'measured at 1 kHz'.",
           ])}
    sec = "Yuasa Technical Data Sheet"
    o = [obs("capacity", num(c20), "Ah", L(sec + ", Specifications", f"20-hr rate Capacity to 1.75V /Cell at 20°C (Ah) | {c20}"),
             "rated", hour_rate(20, num(c20), 20, 1.75, volts, "20-hr rate Capacity to 1.75V /Cell at 20°C")),
         obs("capacity", num(c10), "Ah", L(sec + ", Specifications", f"10-hr rate Capacity to 1.8V /Cell at 20°C (Ah) | {c10}"),
             "rated", hour_rate(10, num(c10), 20, 1.8, volts, "10-hr rate Capacity to 1.8V /Cell at 20°C")),
         obs("nominal_voltage", volts, "V", L(sec + ", Specifications", f"Nominal Voltage (V) | {v} V"), "nominal")]
    for q, text, lab in (("length", l, "Length (mm)"), ("width", w, "Width (mm)"), ("height", h, "Height (mm)")):
        val, tol = dim(text)
        o.append(obs(q, val, "mm", L(sec + ", Dimensions", f"{lab} | {text}"), None, None, tol=tol))
    o.append(obs("mass", num(kg), "kg", L(sec + ", Dimensions", f"Weight (kg) | {kg}")))
    o.append(obs("float_charge_voltage", num(fl), "V", L(sec + ", Charge Voltage", f"Float charge voltage at 20°C /Block (±1%) | {fl}"),
                 "standard", cond([], {"tolerance": "±1%", "per": "block"}, temperature_c=20)))
    o.append(obs("cyclic_charge_voltage", num(cy), "V",
                 L(sec + ", Charge Voltage", f"Cyclic (or Boost) charge Voltage at 20°C (V) /Block (±3%) | {cy}"),
                 "standard", cond([], {"tolerance": "±3%", "per": "block", "source_label": "Cyclic (or Boost) charge Voltage"},
                                  temperature_c=20)))
    assert fli == cyi
    o.append(obs("max_continuous_charge_current", num(cyi), "A",
                 L(sec + ", Charge Current", f"Float charge current limit (A) | {fli} · Cyclic (or Boost) charge current limit (A) | {cyi}"),
                 "maximum", cond(["temperature_c"], {"source_label": "Float / Cyclic (or Boost) charge current limit"})))
    for secs, amps in ((1, i1s), (60, i1m)):
        lab = "1s" if secs == 1 else "1m"
        o.append(obs("max_pulse_discharge_current", num(amps), "A",
                     L(sec + ", Maximum Discharge Current", f"Maximum discharge current {lab} (A) | {amps}"), "maximum",
                     cond(["temperature_c"], pulse_duration_s=secs)))
    o.append(obs("short_circuit_current", num(isc), "A",
                 L(sec + ", Short-Circuit Current & Internal Resistance", f"Short-Circuit current - according to EN IEC 60896-21 (A) | {isc}"),
                 None, cond(["temperature_c"], {"standard": "EN IEC 60896-21"})))
    o.append(obs("internal_resistance_ac", num(ir), "mΩ",
                 L(sec + ", Short-Circuit Current & Internal Resistance", f"Internal resistance (mΩ) measured at 1 kHz | {ir}"),
                 None, cond(["soc_pct", "temperature_c"], frequency_hz=1000)))
    o.append(obs("self_discharge_rate", 3, "%/month", L(sec + ", Storage", "Capacity loss per month at 20°C (% approx.) | 3"),
                 "typical", cond(["soc_pct", "duration_s"], {"source_label": "Capacity loss per month (% approx.)"}, temperature_c=20)))
    ot = sec + ", Operating Temperature Range"
    for q, val, d, text in (("operating_temperature_min", -15, "charge", "Charge | -15°C to +50°C"),
                            ("operating_temperature_max", 50, "charge", "Charge | -15°C to +50°C"),
                            ("operating_temperature_min", -20, "discharge", "Discharge | -20°C to +60°C"),
                            ("operating_temperature_max", 60, "discharge", "Discharge | -20°C to +60°C")):
        o.append(obs(q, val, "°C", L(ot, text), "minimum" if q.endswith("min") else "maximum",
                     cond(["temperature_reference"], direction=d)))
    for q, val in (("storage_temperature_min", -20), ("storage_temperature_max", 60)):
        o.append(obs(q, val, "°C", L(ot, "Storage (in fully charged condition) | -20°C to +60°C"),
                     "minimum" if q.endswith("min") else "maximum",
                     cond(["duration_s"], {"note": "in fully charged condition"})))
    o.append(obs("calendar_life", 5, "year", L(sec + ", Design Life & Approvals", "Yuasa design life at 20°C (yrs) | Up to 5 years"),
                 "design", cond(["soc_pct"], {"basis": "Yuasa design life",
                                              "eurobat_classification": "Standard commercial: 3 to 5 years"},
                                temperature_c=20), upper=True))
    chem = lead("AGM", L(sec + ", title", title), None)
    aliases = [sku.replace("%2F", "/")]
    return document("module", "Yuasa", "yuasa", model, src, o, chem, aliases=aliases)


# ====================================================================== Odyssey
ODY_URL = "https://www.odysseybattery.com/extreme-series-battery-specifications/"
ODY_SOURCE = {
    "uid": "src/odyssey-extreme-series-specifications-web-2026-10-29",
    "kind": "manufacturer_web",
    "title": "ODYSSEY Extreme Series Battery Specifications",
    "url": ODY_URL,
    "retrieved_at": RETRIEVED,
    "sha256": "c1f0d5d05bcf2dde3f0af2a4f4cda074f68274815c09b7ad06e71e6ac40180d3",
    "license": "proprietary",
    "redistributable": False,
    "note": " ".join([
        FACTS, "EnerSys ODYSSEY specification web page (HTML as fetched, 194,170 bytes). 'All values shown are nominal "
        "unless otherwise noted.' The cranking ratings (MHPCA, MPCA, CCA, HCA, MCA) carry the footnote 'Cold Start "
        "Performance S.A.E J537 Apr 2016'; the page prints no temperature, duration or end voltage for them, so "
        "those stay unstated and the rating name is kept in extra. PHCA is printed as a 5-second '**Pulse Current' "
        "and is recorded as a 5 s pulse discharge current. Capacities print no temperature or end voltage. Weight "
        "and dimensions are the metric figures in parentheses; dimensions are maxima, total height first and "
        "container height second. Internal resistance is printed without its method and is not recorded. The AGM "
        "designation comes from the ODYSSEY Extreme series page (https://www.odysseybattery.com/extreme-series-batteries/, "
        "retrieved 2026-10-29), not from this table. Terminal and torque columns are not recorded.",
    ]),
}
ODY_COLS = ("NEW PART NUMBER (Old Part Number) | Voltage | PHCA** 5 sec. [A] | MHPCA* [A] | MPCA* [A] | CCA* [A] | "
            "HCA* [A] | MCA* [A] | 20 HR Rate [Ah] | 10 HR Rate [Ah] | Reserve Capacity [Minutes] | Maximum Length | "
            "Maximum Width | Maximum Total Height | Maximum Container Height | Weight")
# part, old part(s), V, PHCA, MHPCA, MPCA, CCA, HCA, MCA, C20, C10, RC, L, W, H total, H container, weight
ODYSSEY = [
    ("ODX-AGM24", "NSB-AGM24", "12", "1500", "", "", "840", "1200", "1000", "76", "73", "160", "10.9 (277)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "57.1 (25.9)"),
    ("ODX-AGM24F", "NSB-AGM24F", "12", "1500", "", "", "840", "1200", "1000", "76", "73", "160", "10.9 (277)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "57.1 (25.9)"),
    ("ODX-AGM24M", "NSB-AGM24M", "12", "1500", "1400", "1225", "840", "1200", "1000", "76", "73", "160", "10.9 (277)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "57.1 (25.9)"),
    ("ODX-AGM27", "NSB-AGM27", "12", "1750", "", "", "930", "1290", "1080", "92", "88", "195", "12.5 (318)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "67.9 (30.8)"),
    ("ODX-AGM27F", "NSB-AGM27F", "12", "1750", "", "", "930", "1290", "1080", "92", "88", "195", "12.5 (318)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "67.9 (30.8)"),
    ("ODX-AGM27M", "NSB-AGM27M", "12", "1750", "1600", "1325", "930", "1290", "1080", "92", "88", "195", "12.5 (318)", "6.8 (173)", "8.8 (224)", "8.2 (208)", "67.9 (30.8)"),
    ("ODX-AGM31", "31-PC2150S", "12", "2150", "", "", "1150", "1545", "1370", "103", "98", "220", "13 (330)", "6.8 (173)", "9.5 (241)", "8.5 (216)", "77.8 (35.3)"),
    ("ODX-AGM31A", "31-PC2150T", "12", "2150", "", "", "1150", "1545", "1370", "103", "98", "220", "13 (330)", "6.8 (173)", "9.7 (246)", "8.5 (216)", "77.8 (35.3)"),
    ("ODX-AGM31R", "31R-PC2150S", "12", "2150", "", "", "1150", "1545", "1370", "103", "98", "220", "13 (330)", "6.8 (173)", "9.5 (241)", "8.6 (218)", "77.8 (35.3)"),
    ("ODX-AGM31M", "31M-PC2150", "12", "2150", "1950", "1625", "1150", "1545", "1370", "103", "98", "220", "13 (330)", "6.8 (173)", "9.9 (251)", "8.9 (226)", "77.8 (35.3)"),
    ("ODX-AGM34", "34-PC1500", "12", "1500", "", "", "850", "1250", "1050", "68", "62", "135", "10.9 (277)", "6.8 (173)", "7.9 (201)", "7.3 (185)", "49.5 (22.5)"),
    ("ODX-AGM34R", "34R-PC1500", "12", "1500", "", "", "850", "1250", "1050", "68", "62", "135", "10.9 (277)", "6.8 (173)", "7.9 (201)", "7.3 (185)", "49.5 (22.5)"),
    ("ODX-AGM34M", "34M-PC1500 or NSB-AGM34M", "12", "1500", "1400", "1275", "850", "1250", "1050", "68", "62", "135", "10.9 (277)", "6.8 (173)", "7.8 (198)", "7.2 (183)", "50.9 (23.1)"),
    ("ODX-AGM34 78", "34/78-PC1500", "12", "1500", "", "", "850", "1250", "1050", "68", "62", "135", "10.9 (277)", "6.8 (173)", "7.9 (201)", "7.3 (185)", "49.5 (22.5)"),
    ("ODX-AGM65", "65-PC1750", "12", "1750", "", "", "950", "1350", "1070", "74", "65", "145", "11.8 (300)", "7.2 (183)", "7.5 (191)", "6.8 (173)", "54 (24.5)"),
    ("ODX-AGM78", "78-PC1500", "12", "1500", "", "", "850", "1250", "1050", "68", "62", "135", "10.9 (277)", "6.8 (173)", "7.3 (185)", "7.3 (185)", "49.5 (22.5)"),
]


def metric(text: str):
    return num(re.search(r"\(([\d.]+)\)", text).group(1))


def odyssey(row) -> dict:
    part, old, v, phca, mhpca, mpca, cca, hca, mca, c20, c10, rc, l, w, ht, hc, wt = row
    volts = num(v)
    q = f"{part} ({old}) | " + " | ".join(row[2:])
    sec = f"Extreme Battery Specifications table, row {part}"
    o = []
    for hours, val, lab in ((20, c20, "20 HR Rate [Ah]"), (10, c10, "10 HR Rate [Ah]")):
        o.append(obs("capacity", num(val), "Ah", L(f"{sec}, column {lab}", q), "nominal",
                     hour_rate(hours, num(val), None, None, volts, lab)))
    o.append(obs("nominal_voltage", volts, "V", L(f"{sec}, column Voltage", q), "nominal"))
    for rating, val in (("CCA", cca), ("HCA", hca), ("MCA", mca), ("MPCA", mpca), ("MHPCA", mhpca)):
        if val:
            o.append(obs("cranking_current", num(val), "A", L(f"{sec}, column {rating}* [A]; *Cold Start Performance S.A.E J537 Apr 2016", q),
                         "nominal", cond(["temperature_c", "duration_s", "voltage_lower_v"],
                                         {"rating": rating, "standard": "SAE J537 Apr 2016"})))
    o.append(obs("max_pulse_discharge_current", num(phca), "A", L(f"{sec}, column PHCA** 5 sec. [A]; **Pulse Current", q),
                 "nominal", cond(["temperature_c"], {"source_label": "PHCA** 5 sec."}, pulse_duration_s=5)))
    o.append(obs("reserve_capacity", num(rc), "min", L(f"{sec}, column Reserve Capacity [Minutes]", q), "nominal",
                 cond(["rate_value", "rate_unit", "temperature_c", "voltage_lower_v"])))
    for qq, val, lab, extra in (("length", l, "Maximum Length [in (mm)]", None), ("width", w, "Maximum Width [in (mm)]", None),
                                ("height", ht, "Maximum Total Height [in (mm)]", None),
                                ("height", hc, "Maximum Container Height [in (mm)]", {"source_label": "Maximum Container Height"})):
        o.append(obs(qq, metric(val), "mm", L(f"{sec}, column {lab}", q), "maximum", cond([], extra) if extra else None))
    o.append(obs("mass", metric(wt), "kg", L(f"{sec}, column Weight [lb (kg)]", q), "nominal"))
    rt = "Rated Operating Temperature -40°F (-40°C) to 176°F (80°C)"
    oc = cond(["temperature_reference", "direction"], {"source_label": "Rated Operating Temperature"})
    o.append(obs("operating_temperature_min", -40, "°C", L("Extreme Battery Specifications, heading", rt), "minimum", oc))
    o.append(obs("operating_temperature_max", 80, "°C", L("Extreme Battery Specifications, heading", rt), "maximum", oc))
    chem = lead("AGM", L("ODYSSEY Extreme series page (https://www.odysseybattery.com/extreme-series-batteries/), not the specification table",
                         "ODYSSEY Extreme batteries employ dry cell Absorbed Glass Mat (AGM) technology to contain acid"),
                "Absorbed glass mat (AGM)")
    aliases = [part] + [a.strip() for a in old.split(" or ")]
    return document("module", "EnerSys", "enersys", f"ODYSSEY {part}", ODY_SOURCE, o, chem, aliases=aliases)


# ======================================================================== VARTA
VARTA_NOTE = " ".join([
    FACTS, "VARTA Automotive product detail page (HTML as fetched). VARTA Automotive batteries are made and sold by "
    "Clarios ('Clarios manufactures and distributes VARTA Automotive batteries', varta-automotive.com home page), "
    "so the manufacturer is Clarios and the model keeps the VARTA name. Dynamic EFB is the renamed Silver Dynamic "
    "EFB ('Dynamic EFB replaces the well-known Silver Dynamic EFB'). The page prints capacity, CCA, voltage and "
    "dimensions only: the capacity's rate, temperature and end voltage and the CCA's standard, temperature, "
    "duration and end voltage are not stated. Dimensions are L/W/H in millimetres per the page's tooltip. The "
    "linked PDF datasheet could not be opened for this review (download only), so weight and the rated values it "
    "may print are not recorded. The regional listing at https://www.varta-automotive.com/en/products/automotive/dynamic-efb "
    "prints different dimensions for some models; only this product page's figures are recorded. The page body "
    "changes from one fetch to the next, so the SHA-256 identifies the copy inspected; every recorded figure was "
    "re-read from a fresh copy before acceptance.",
])
# ETN, page bytes, sha256, Ah, CCA, short code, L/W/H, case size; /en/ listing dimensions where they differ
VARTA = [
    ("595500085", 208434, "748504fa425e7116e607d5621d05e9a37e77ad6fb1bed0c37b3c3c323c5899ec", "95", "850", "N95", "353/175/190", "H8/L5", "352/175/190"),
    ("585501080", 208303, "312b21f7c8165a19d062f5c1ea6f9d4b91cf5a747c193ce844e63409f36795bb", "85", "800", "N85", "306/173/225", "D31", None),
    ("580500080", 208272, "466939046d5febc6c5cd8d51394931d40775eb8080f0c81d4a18aa5cbc775956", "80", "800", "N80", "315/175/190", "H7/L4", "314/175/190"),
    ("575500073", 208302, "38619135677719c38fc8c8951a5e4e4d64b3dd977330ec502b442aead57bc331", "75", "730", "E46", "315/175/175", "T7/LB4", "314/175/175"),
    ("572501076", 208298, "b9dc62abd83935d9caf7320724671b874bd8401be2a4c6ed8ae32357aced0e62", "72", "760", "N72", "260/173/225", "D26", "261/175/220"),
    ("570500076", 208291, "fa5743597854871444494827fc7b1b8662e34efcaca38664d7d598e6f35b4a2c", "70", "760", "N70", "278/175/190", "H6/L3", None),
    ("565501065", 208292, "016dd4524b9d7bbec083f6ec27bf8ff1e8b8bb1dfa76300a881efcfa986d22dd", "65", "650", "N65", "232/173/225", "D23", None),
    ("565500065", 208302, "763e2f7b1b95d466f0005b1412a20c7815d7ca4a89e40f64129c6f7a2bfb7b6b", "65", "650", "D54", "278/175/175", "T6/LB3", None),
    ("560500064", 208327, "c358d15432345c2873b34e94e235a8b0b20cc5f5a720327e69cb8475448a6d0e", "60", "640", "N60", "242/175/190", "H5/L2", None),
    ("550500055", 208249, "69c2def51d15b3322e4cceb877b00b2f6c65dabda0950db671e7da13a0684539", "50", "550", "N50", "207/175/190", "H4/L1", None),
    ("605500095", 207913, "77fc78796450482938aade9c76800e7cff00b29712d2faf0ffd6adde7f3b1e54", "105", "950", "N105", "394/175/190", "L6/H9", None),
]


def varta(row) -> dict:
    etn, size, sha, ah, cca, short, dims, case, en_dims = row
    url = f"https://www.varta-automotive.com/products/product/{etn}k262"
    note = VARTA_NOTE + f" Page body {size:,} bytes."
    if en_dims:
        note += f" The regional listing prints {en_dims} for this model."
    src = {"uid": f"src/varta-dynamic-efb-{etn}-web-2026-10-29", "kind": "manufacturer_web",
           "title": f"VARTA Dynamic EFB {etn} product page", "url": url, "retrieved_at": RETRIEVED, "sha256": sha,
           "license": "proprietary", "redistributable": False, "note": note}
    sec = "Technical Specifications"
    o = [obs("capacity", num(ah), "Ah", L(sec, f"{ah} Ah Capacity"), None,
             cond(["rate_value", "rate_unit", "temperature_c", "voltage_lower_v"])),
         obs("nominal_voltage", 12, "V", L(sec, "12 V Voltage"), "nominal"),
         obs("cranking_current", num(cca), "A", L(sec, f"{cca} A CCA"), None,
             cond(["temperature_c", "duration_s", "voltage_lower_v"], {"rating": "CCA", "standard": "not stated"}))]
    l, w, h = (num(x) for x in dims.split("/"))
    for q, val in (("length", l), ("width", w), ("height", h)):
        o.append(obs(q, val, "mm", L(sec + " (tooltip: The dimensions are in millimetres (mm).)", f"{dims} Dimensions (L/W/H)")))
    chem = lead("EFB", L("Product page heading and FAQ",
                         f"DYNAMIC EFB {etn} · While EFB is an improved flooded battery"), None)
    return document("module", "Clarios", "clarios", f"VARTA Dynamic EFB {etn}", src, o, chem,
                    aliases=[etn, short], ffc=case)


# ======================================================================= build
def build() -> dict:
    docs = ([victron(r, "AGM") for r in VICTRON_AGM] + [victron(r, "gel") for r in VICTRON_GEL] + trojan()
            + [a600(r) for r in A600] + [opzs(r) for r in OPZS] + [yuasa(r) for r in YUASA]
            + [odyssey(r) for r in ODYSSEY] + [varta(r) for r in VARTA])
    uids = [d["product"]["uid"] for d in docs]
    assert len(uids) == len(set(uids)), "duplicate uid in batch"
    return {
        "schema_version": 1,
        "batch": "2026-10-29-lead-acid-batteries",
        "note": ("First lead-acid batteries (AGM, gel, flooded, EFB) from first-party datasheets and product pages, "
                 "added under the owner instruction to fill the Lead-acid technology filter. Lead-acid is never "
                 "offered for Lemonergy Design (technology flag design: false). Acceptance validates source "
                 "transcription, not battery performance. See review/audits/2026-10-29-lead-acid-batteries.json "
                 "and docs/23-lead-acid-batteries.md."),
        "candidates": [{"document": d} for d in docs],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed batch differs")
    a = ap.parse_args()
    body = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if a.check:
        if not BATCH.exists() or BATCH.read_text(encoding="utf-8") != body:
            print(f"{BATCH.relative_to(ROOT)} is stale; run tools/import_lead_acid_batteries.py", file=sys.stderr)
            return 1
        print(f"ok: {BATCH.relative_to(ROOT)} is current")
        return 0
    BATCH.write_text(body, encoding="utf-8")
    n = len(json.loads(body)["candidates"])
    print(f"wrote {BATCH.relative_to(ROOT)}: {n} products")
    return 0


if __name__ == "__main__":
    sys.exit(main())
