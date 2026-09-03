#!/usr/bin/env python3
"""Regenerate web/index.html's data blobs from contrib/ and the registry.

WHY THIS EXISTS
---------------
The page used to carry a hand-written snapshot of the same cells that live in
contrib/. Nothing kept the two in step, so a merged contribution appeared in
the repository and not in the UI -- which makes a working submission flow look
broken. Worse, a hand-written snapshot can contain cells that exist nowhere
else: the first version of this page charted ten cells, and eight of them had
no datasheet, no conditions and no locator behind them. In a project whose
premise is that a value without its conditions is not a fact, that is the
failure mode to design out rather than to remember not to repeat.

So the product data on the page is derived, and only derived. A cell reaches
the chart by being a contribution that passes tools/validate_contrib.py. There
is no other door.

WHAT IS DERIVED AND WHAT IS NOT
-------------------------------
Derived from contrib/**/*.yaml            -> products, observations, curves, the chart
Derived from json-schema/quantity-registry -> the quantity registry the entry form reads
Derived from schema/010_vocabulary.sql     -> the test-kind taxonomy

Hand-curated, in web/data/, and checked against the above:
  quantity-groups.json  which of the 98 quantities sit under which heading
  test-families.json    which of the test kinds sit under which family
  coverage.json         cells we want and do not yet have -- a wishlist, not data
  family-claims.json    claims a maker makes about a product family, not a part

The hand-curated files are presentation and intent. They are still checked:
a heading may not name a quantity that does not exist, and may not silently
drop one that does. That check is what would have caught the invented registry.

    python tools/build_web_data.py          # rewrite the page
    python tools/build_web_data.py --check  # fail if the page is stale (CI)
"""
from __future__ import annotations
import argparse, glob, json, math, os, re, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "web", "index.html")
DATA = os.path.join(ROOT, "web", "data")
REGISTRY = os.path.join(ROOT, "json-schema", "quantity-registry.json")
VOCAB = os.path.join(ROOT, "schema", "010_vocabulary.sql")

# Marker pairs in the page. Everything between them is machine-owned; edit the
# contribution or the file in web/data/, never the region.
BEGIN = "/* GENERATED: {} -- do not edit, run tools/build_web_data.py */"
END = "/* END GENERATED: {} */"

SHAPE = {"cylindrical": "cyl", "prismatic_hardcase": "pri", "prismatic": "pri",
         "pouch": "pou", "blade": "pri", "coin": "cyl", "button": "cyl"}


def load(path):
    with open(path) as fh:
        return json.load(fh)


def test_kinds() -> set[str]:
    """The test_kind enum, read from the schema rather than restated here."""
    sql = open(VOCAB).read()
    m = re.search(r"CREATE TYPE test_kind AS ENUM \((.*?)\);", sql, re.S)
    if not m:
        sys.exit("could not find test_kind enum in schema/010_vocabulary.sql")
    return set(re.findall(r"'([a-z0-9_]+)'", m.group(1)))


def check_groupings(registry: dict, groups: dict, fams: dict,
                    exclude: list[str]) -> list[str]:
    """A heading may not invent a quantity, nor quietly lose one.

    Both halves matter. Inventing is how the registry got 48 codes that did not
    exist; losing is how a real quantity becomes unreachable in the UI while
    still passing every other test.
    """
    errs = []
    placed = [q for qs in groups.values() for q in qs]
    for q in placed:
        if q not in registry:
            errs.append(f"quantity-groups.json: '{q}' is not in the registry")
    for q in sorted(set(registry) - set(placed)):
        errs.append(f"quantity-groups.json: '{q}' exists but sits under no heading")
    for q in sorted({q for q in placed if placed.count(q) > 1}):
        errs.append(f"quantity-groups.json: '{q}' appears under more than one heading")

    kinds = test_kinds() - set(exclude)
    listed = [k for ks in fams.values() for k in ks]
    for k in listed:
        if k not in kinds:
            errs.append(f"test-families.json: '{k}' is not a test_kind")
    for k in sorted(kinds - set(listed)):
        errs.append(f"test-families.json: test_kind '{k}' sits under no family")
    return errs


def product(doc: dict, path: str) -> dict:
    """One contribution, in the shape the page renders.

    Observations keep their conditions, their page and their quote. That is the
    whole point of the page: a reader can see where a number came from without
    leaving it.
    """
    p, src, errs = doc["product"], doc.get("source", {}), []
    obs = []
    for o in doc.get("observations", []):
        cond = dict(o.get("conditions") or {})
        unstated = cond.pop("unstated", [])
        cond.pop("verbatim", None)
        extra = cond.pop("extra", None)
        loc = o["locator"]
        row = {"q": o["quantity"], "v": o["value"], "u": o["unit"],
               "stat": o.get("statistic"), "cond": cond,
               "unstated": unstated, "pg": loc.get("page"),
               "quote": loc["quote"], "src": src.get("kind")}
        if extra:
            row["extra"] = extra
        obs.append(row)

    dims = None
    by = {o["q"]: o["v"] for o in obs}
    if {"length", "width", "thickness"} <= set(by):
        dims = [by["length"], by["width"], by["thickness"]]
    elif {"width", "thickness", "height"} <= set(by):
        dims = [by["height"], by["width"], by["thickness"]]
    elif {"diameter", "height"} <= set(by):
        dims = [by["diameter"], by["height"]]

    chem = doc.get("chemistry") or {}
    cloc = chem.get("locator") or {}
    curves = [{"kind": c["curve_kind"], "x": c["x_values"], "y": c["y_values"],
               "z": c.get("z_values"), "xq": c["x_quantity"], "yq": c["y_quantity"],
               "xu": c["x_unit"], "yu": c["y_unit"],
               "cond": {k: v for k, v in (c.get("conditions") or {}).items()
                        if k not in ("unstated", "verbatim", "extra")}}
              for c in doc.get("curves", [])]

    m = metrics(obs, dims, SHAPE.get(p.get("form_factor", ""), "pri"), errs)
    return {
        "uid": p["uid"], "kind": p["kind"],
        "cell": f"{p['manufacturer']} {p['model_number']}",
        "manu": p["manufacturer"], "model": p["model_number"],
        "fmt": p.get("form_factor") or "", "shape": SHAPE.get(p.get("form_factor", ""), "pri"),
        "dims": dims,
        "chem": {"designation": chem.get("designation"),
                 "cathode": chem.get("cathode_text"), "anode": chem.get("anode_text"),
                 "electrolyte": chem.get("electrolyte_text"),
                 "separator": chem.get("separator_text"),
                 # a chemistry claim carries its evidence like any other
                 "anode_quote": cloc.get("quote") if chem.get("anode_text") else None,
                 "cathode_quote": cloc.get("quote") if chem.get("cathode_text") else None,
                 "anode_pg": cloc.get("page"), "cathode_pg": cloc.get("page")},
        "source": {"title": src.get("title"), "ref": src.get("revision"),
                   "date": src.get("document_date"), "kind": src.get("kind"),
                   "url": src.get("url"), "sha256": src.get("sha256"),
                   "note": src.get("note")},
        "obs": obs, "curves": curves, "pulse": pulse_map(curves, m.get("ah")),
        "m": m,
        "file": os.path.relpath(path, ROOT),
        "unit_errors": errs,
        "verified": True,
    }


def pulse_map(curves: list[dict], ah: float | None) -> dict | None:
    """Fold derating_map curves back into the grid the pulse view draws.

    The curves are the honest storage: one observation per (duration, SOC,
    temperature, direction), each with its conditions. The grid is just how a
    reader sees a surface. Values go back to C-rate because that is what the
    view plots and what makes two cells of different capacity comparable.
    """
    maps = [c for c in curves if c["kind"] == "derating_map"]
    if not maps or not ah:
        return None
    out = {"soc": maps[0]["x"], "dis": {}, "chg": {},
           "duration_s": maps[0]["cond"].get("pulse_duration_s")}
    for c in maps:
        side = "chg" if c["cond"].get("direction") == "charge" else "dis"
        out[side][str(int(c["cond"]["temperature_c"]))] = [
            round(v / ah, 3) for v in c["y"]]
    return out


TO_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001}
TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
TO_AH = {"Ah": 1.0, "mAh": 0.001}
TO_V = {"V": 1.0, "mV": 0.001}
TO_W = {"W": 1.0, "kW": 1000.0, "mW": 0.001}
TO_A = {"A": 1.0, "mA": 0.001, "kA": 1000.0}
TO_MOHM = {"mΩ": 1.0, "mohm": 1.0, "Ω": 1000.0, "ohm": 1000.0, "uohm": 0.001, "µΩ": 0.001}
# temperature: (factor, offset) into degrees Celsius
TO_C = {"°C": (1.0, 0.0), "degC": (1.0, 0.0), "C": (1.0, 0.0), "K": (1.0, -273.15)}

# Every unit a metric consumes must be listed. An unknown unit is a hard stop:
# silently treating 4900 mAh as 4900 Ah puts a cell on the chart at a thousand
# times its real energy, and it looks like a plausible outlier rather than a bug.
SCALES = {"mass": TO_G, "capacity": TO_AH, "nominal_voltage": TO_V,
          "charge_cutoff_voltage": TO_V, "discharge_cutoff_voltage": TO_V,
          "peak_power": TO_W, "rated_power": TO_W,
          "max_continuous_discharge_current": TO_A,
          "max_continuous_charge_current": TO_A,
          "max_pulse_discharge_current": TO_A, "standard_charge_current": TO_A,
          "internal_resistance_ac": TO_MOHM, "internal_resistance_dc": TO_MOHM,
          "length": TO_MM, "width": TO_MM, "thickness": TO_MM,
          "height": TO_MM, "diameter": TO_MM}
TEMPERATURES = {"operating_temperature_min", "operating_temperature_max",
                "storage_temperature_min", "storage_temperature_max"}

# The quantities bd.v_completeness tracks. The page reports the same twelve so
# a number on the site and a number in a query mean the same thing.
TRACKED = ["capacity", "nominal_voltage", "mass", "max_continuous_discharge_current",
           "internal_resistance_ac", "internal_resistance_dc", "cycle_life",
           "operating_temperature_min", "operating_temperature_max", "energy",
           "charge_cutoff_voltage", "discharge_cutoff_voltage"]

# Which stated figure to lead with when a datasheet states several. Lower is
# preferred. "standard" and "typical" are what the maker measured under its
# reference procedure; "rated" and "minimum" are guarantees; "maximum" is a
# ceiling and never a central figure.
STAT_RANK = {"standard": 0, "typical": 1, "nominal": 2, "rated": 3, "initial": 4,
             "minimum": 5, "design": 6, "guaranteed": 7, "mean": 8, "median": 9,
             "measured": 10, "maximum": 11, "absolute_max": 12, "absolute_min": 12}
MASS_RANK = {"typical": 0, "nominal": 1, "standard": 2, "mean": 3, "measured": 4,
             "rated": 5, "maximum": 6, "minimum": 7}


def convert(o: dict, errs: list[str]):
    """One observation in its canonical unit, or None -- never a bare number."""
    q, u = o["q"], o["u"]
    if q in TEMPERATURES:
        if u not in TO_C:
            errs.append(f"{q}: unit {u!r} is not a temperature unit; add it to TO_C")
            return None
        k, off = TO_C[u]
        return o["v"] * k + off
    table = SCALES.get(q)
    if table is None:
        return o["v"]
    if u not in table:
        errs.append(f"{q}: unit {u!r} is not convertible; add it to SCALES")
        return None
    return o["v"] * table[u]


def c_rate(o: dict, nameplate_ah: float | None) -> tuple[float | None, str | None]:
    """The rate an observation was taken at, as a C-rate and as text.

    C and It rates are used as stated. An absolute current is divided by the
    nameplate so two cells of different capacity compare, and the text keeps
    the current as printed. Constant power (EVE's "0.5P") is stated but not a
    C-rate, and is never converted: the text carries it, the number stays None.
    """
    cond = o.get("cond") or {}
    rv, ru = cond.get("rate_value"), cond.get("rate_unit")
    if rv is None or ru in (None, "unspecified"):
        return None, None
    if ru in ("C", "It"):
        return float(rv), f"{rv:g}{ru}"
    if ru in TO_A:
        amps = rv * TO_A[ru]
        return (amps / nameplate_ah if nameplate_ah else None), f"{rv:g} {ru}"
    return None, f"{rv:g}{ru}" if ru == "P" else f"{rv:g} {ru}"


def capacity_key(o: dict, nameplate_ah: float | None):
    """THE CAPACITY RULE.

    A datasheet states several capacities and they are not interchangeable:
    the Samsung 50E's 4900 mAh at 0.2C and 4753 mAh at 1C sit on one page. The
    figure the page leads with is chosen by this rule and only this rule:

      1. a capacity whose rate the source states beats one whose rate it does
         not, so a bare number never outranks a conditioned one;
      2. among stated rates, the lowest rate wins -- that is the maker's own
         "standard" figure, the one taken nearest equilibrium;
      3. ties break on the statistic, standard before typical before rated;
      4. then the larger value, so a range's upper figure is not hidden.

    The rate that won is printed next to the number. A reader who wants the
    1C figure opens the cell sheet, where every stated capacity is listed.
    """
    rate, text = c_rate(o, nameplate_ah)
    stated = text is not None
    return (0 if stated else 1, 0 if rate is not None else 1, rate or 0.0,
            STAT_RANK.get(o.get("stat"), 13), -o["v"])


def pick(obs: list[dict], q: str, key):
    rows = [o for o in obs if o["q"] == q]
    return min(rows, key=key) if rows else None


def nearest(obs: list[dict], q: str, temperature_c: float = 25.0):
    """The observation of q taken nearest a temperature; higher value on ties.

    A current limit is a surface over temperature (the LG M50LT has three).
    Absent a stated temperature the row is taken as the room-temperature
    figure, which is what bd.v_cell_selection does too, and the page says so.
    """
    def key(o):
        t = (o.get("cond") or {}).get("temperature_c")
        return (abs((25.0 if t is None else t) - temperature_c), -o["v"])
    return pick(obs, q, key)


def temperature_limit(obs: list[dict], q: str, errs: list[str]):
    """Operating limit in Celsius, discharge direction preferred."""
    def key(o):
        d = (o.get("cond") or {}).get("direction")
        return (0 if d == "discharge" else 1 if d in (None, "symmetric") else 2,
                (o["v"] if q.endswith("_min") else -o["v"]))
    o = pick(obs, q, key)
    return convert(o, errs) if o else None


def basis_text(o: dict | None, nameplate_ah: float | None) -> dict | None:
    if not o:
        return None
    cond = o.get("cond") or {}
    rate, text = c_rate(o, nameplate_ah)
    return {"stat": o.get("stat"), "rate": text or "rate unstated", "rate_c": rate,
            "temp": cond.get("temperature_c"), "cutoff": cond.get("voltage_lower_v"),
            "unstated": o.get("unstated") or []}


def metrics(obs: list[dict], dims: list | None, shape: str,
            errs: list[str]) -> dict:
    """The comparison numbers, and whether each was stated or worked out.

    Wh/kg from a stated capacity, voltage and mass is arithmetic on facts, not
    a new fact, and the distinction is worth keeping visible: a reader should
    be able to tell which of two cells had its specific energy printed on the
    datasheet and which one we divided. Nothing is computed from a value the
    source did not state, and the capacity that feeds the arithmetic is chosen
    by capacity_key(), never by position in the file.
    """
    caps = [convert(o, []) for o in obs if o["q"] == "capacity"]
    nameplate = max((c for c in caps if c), default=None)

    cap = pick(obs, "capacity", lambda o: capacity_key(o, nameplate))
    ah = convert(cap, errs) if cap else None
    volt_o = pick(obs, "nominal_voltage", lambda o: (STAT_RANK.get(o.get("stat"), 13),))
    volt = convert(volt_o, errs) if volt_o else None
    mass_o = pick(obs, "mass", lambda o: (MASS_RANK.get(o.get("stat"), 8),))
    g = convert(mass_o, errs) if mass_o else None
    wh = ah * volt if ah is not None and volt is not None else None

    litres = None
    if dims:
        litres = (math.pi * (dims[0] / 2) ** 2 * dims[1] / 1e6
                  if shape == "cyl" and len(dims) == 2
                  else dims[0] * dims[1] * dims[2] / 1e6 if len(dims) == 3 else None)

    out = {"wh": wh, "mass_g": g, "litres": litres, "ah": ah, "v": volt,
           "cap_basis": basis_text(cap, nameplate),
           "v_basis": volt_o.get("stat") if volt_o else None,
           "mass_basis": mass_o.get("stat") if mass_o else None}

    # Stated density figures beat derived ones; typical beats the rest.
    for key, stated, num, den in (("whkg", "specific_energy", wh, g and g / 1000),
                                  ("whl", "energy_density", wh, litres)):
        so = pick(obs, stated, lambda o: (STAT_RANK.get(o.get("stat"), 13),))
        if so is not None:
            out[key], out[key + "_derived"] = so["v"], False
        elif num and den:
            out[key], out[key + "_derived"] = round(num / den, 1), True
        else:
            out[key], out[key + "_derived"] = None, False

    # Current limits are a surface over temperature; lead with the row nearest
    # room temperature and say what temperature that row was stated at.
    cur_o = nearest(obs, "max_continuous_discharge_current")
    cur = convert(cur_o, errs) if cur_o else None
    out["a"] = cur
    out["a_temp"] = (cur_o.get("cond") or {}).get("temperature_c") if cur_o else None
    out["a_unstated"] = bool(cur_o and "temperature_c" in (cur_o.get("unstated") or []))
    out["crate"] = round(cur / ah, 2) if cur and ah else None

    peak_o = pick(obs, "peak_power", lambda o: (STAT_RANK.get(o.get("stat"), 13),))
    peak = convert(peak_o, errs) if peak_o else None
    out["wkg"] = (round(peak / (g / 1000), 1) if peak and g else
                  round(cur * volt / (g / 1000), 1) if cur and g and volt else None)

    # Resistance is never one number: method, duration, SOC and temperature
    # travel with it or it does not appear.
    def resistance(q):
        def key(o):
            c = o.get("cond") or {}
            t, soc = c.get("temperature_c"), c.get("soc_pct")
            return (abs((25 if t is None else t) - 25), abs((50 if soc is None else soc) - 50))
        o = pick(obs, q, key)
        if not o:
            return None
        c = o.get("cond") or {}
        return {"mohm": convert(o, errs), "dur": c.get("pulse_duration_s"),
                "freq": c.get("frequency_hz"), "soc": c.get("soc_pct"),
                "temp": c.get("temperature_c"), "dir": c.get("direction"),
                "stat": o.get("stat"), "unstated": o.get("unstated") or []}
    out["dcir"] = resistance("internal_resistance_dc")
    out["acir"] = resistance("internal_resistance_ac")

    # Cycle life is a function, not a number: lead with the claim that states
    # the most of its conditions, and carry those conditions with it.
    def cycles_key(o):
        c = o.get("cond") or {}
        return (-sum(1 for k in ("temperature_c", "dod_pct", "rate_value") if c.get(k) is not None),
                -o["v"])
    cyc = pick(obs, "cycle_life", cycles_key)
    if cyc:
        c = cyc.get("cond") or {}
        _, rate_text = c_rate(cyc, nameplate)
        extra = cyc.get("extra") or {}
        out["cycles"] = {"n": cyc["v"], "dod": c.get("dod_pct"), "rate": rate_text,
                         "temp": c.get("temperature_c"),
                         "eol": extra.get("eol_criterion_pct"),
                         "unstated": cyc.get("unstated") or []}
    else:
        out["cycles"] = None

    out["tmin"] = temperature_limit(obs, "operating_temperature_min", errs)
    out["tmax"] = temperature_limit(obs, "operating_temperature_max", errs)
    chg = pick(obs, "standard_charge_current", lambda o: (STAT_RANK.get(o.get("stat"), 13),))
    out["chg"] = convert(chg, errs) if chg else None
    chg_max = nearest(obs, "max_continuous_charge_current")
    out["chg_max"] = convert(chg_max, errs) if chg_max else None
    for key, q in (("vchg", "charge_cutoff_voltage"), ("vdis", "discharge_cutoff_voltage")):
        o = pick(obs, q, lambda o: (STAT_RANK.get(o.get("stat"), 13),))
        out[key] = convert(o, errs) if o else None

    # Completeness: what the record has against what an engineer needs, and
    # how much of what it has rests on conditions the source never states.
    present = {o["q"] for o in obs}
    out["complete"] = sum(1 for q in TRACKED if q in present)
    out["tracked"] = len(TRACKED)
    out["missing"] = [q for q in TRACKED if q not in present]
    out["unstated"] = sum(len(o.get("unstated") or []) for o in obs)
    out["obs_unstated"] = sum(1 for o in obs if o.get("unstated"))
    out["n_obs"] = len(obs)
    return out


def coverage(segments: list[dict], products: list[dict]) -> list[dict]:
    """Mark each target sourced or missing by looking, not by being told.

    A stored status drifts the moment a contribution lands or is withdrawn,
    and it drifted the wrong way once already: eight cells sat marked
    'provisional' on the strength of numbers that had no document at all.
    """
    known = {p["uid"] for p in products}
    out = []
    for seg in segments:
        cells = [{**c, "status": "sourced" if c.get("uid") in known else "missing"}
                 for c in seg["cells"]]
        out.append({**seg, "cells": cells})
    return out


def build() -> dict:
    registry = load(REGISTRY)
    qg = load(os.path.join(DATA, "quantity-groups.json"))
    groups, axis_only = qg["groups"], qg.get("axis_only", [])
    tf = load(os.path.join(DATA, "test-families.json"))

    errs = check_groupings(registry, groups, tf["FAM"], tf.get("EXCLUDE", []))
    if errs:
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        sys.exit(f"\n{len(errs)} grouping error(s); page not written")

    files = sorted(glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"),
                             recursive=True))
    products = [product(yaml.safe_load(open(f)), f) for f in files]

    return {
        # GROUPS drives the datasheet slot list, so axis-only quantities are
        # left out of it: they are real, and they are not blanks a datasheet
        # could ever fill.
        "REGISTRY": {"REG": registry,
                     "GROUPS": {k: v for k, v in groups.items() if k not in axis_only}},
        "TAXONOMY": {"FAM": tf["FAM"], "LANDS": tf["LANDS"]},
        "CONTRIB": {"PRODUCTS": products,
                    "COVERAGE": coverage(load(os.path.join(DATA, "coverage.json")), products),
                    "FAMILY_CLAIMS": load(os.path.join(DATA, "family-claims.json"))},
    }


def render(page: str, blobs: dict) -> str:
    for name, payload in blobs.items():
        b, e = BEGIN.format(name), END.format(name)
        if b not in page or e not in page:
            sys.exit(f"page is missing the {name} marker pair")
        body = f"const _{name} = {json.dumps(payload, ensure_ascii=False, sort_keys=True)};"
        page = re.sub(re.escape(b) + r".*?" + re.escape(e),
                      lambda _: f"{b}\n{body}\n{e}", page, flags=re.S)
    return page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the page is out of date")
    a = ap.parse_args()

    blobs = build()
    current = open(PAGE).read()
    new = render(current, blobs)

    n = len(blobs["CONTRIB"]["PRODUCTS"])
    charted = sum(1 for p in blobs["CONTRIB"]["PRODUCTS"]
                  if p["kind"] == "cell" and p["m"]["whkg"])
    if a.check:
        if new != current:
            print("web/index.html is stale. Run: python tools/build_web_data.py",
                  file=sys.stderr)
            return 1
        print(f"web/index.html is up to date ({n} products, {charted} charted)")
        return 0

    open(PAGE, "w").write(new)
    print(f"wrote {os.path.relpath(PAGE, ROOT)}: {n} products, {charted} on the chart")
    for p in blobs["CONTRIB"]["PRODUCTS"]:
        print(f"  {p['kind']:7} {p['cell']:38} {len(p['obs']):3} obs "
              f"{len(p['curves']):3} curves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
