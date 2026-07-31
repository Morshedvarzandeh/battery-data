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
        cond.pop("verbatim", None), cond.pop("extra", None)
        loc = o["locator"]
        obs.append({"q": o["quantity"], "v": o["value"], "u": o["unit"],
                    "stat": o.get("statistic"), "cond": cond,
                    "unstated": unstated, "pg": loc.get("page"),
                    "quote": loc["quote"], "src": src.get("kind")})

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
        "obs": obs, "curves": curves, "pulse": pulse_map(curves, by.get("capacity")),
        "m": metrics(obs, dims, SHAPE.get(p.get("form_factor", ""), "pri"), errs),
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

# Every unit a metric consumes must be listed. An unknown unit is a hard stop:
# silently treating 4900 mAh as 4900 Ah puts a cell on the chart at a thousand
# times its real energy, and it looks like a plausible outlier rather than a bug.
SCALES = {"mass": TO_G, "capacity": TO_AH, "nominal_voltage": TO_V,
          "peak_power": TO_W, "max_continuous_discharge_current": {"A": 1.0, "mA": 0.001},
          "length": TO_MM, "width": TO_MM, "thickness": TO_MM,
          "height": TO_MM, "diameter": TO_MM}


def scaled(v: dict, u: dict, q: str, errs: list[str]):
    """A quantity in its canonical unit, or None -- never a bare number."""
    if v.get(q) is None:
        return None
    table = SCALES.get(q)
    if table is None:
        return v[q]
    if u.get(q) not in table:
        errs.append(f"{q}: unit {u.get(q)!r} is not convertible; add it to SCALES")
        return None
    return v[q] * table[u[q]]


def metrics(obs: list[dict], dims: list | None, shape: str,
            errs: list[str]) -> dict:
    """The comparison numbers, and whether each was stated or worked out.

    Wh/kg from a stated capacity, voltage and mass is arithmetic on facts, not
    a new fact, and the distinction is worth keeping visible: a reader should
    be able to tell which of two cells had its specific energy printed on the
    datasheet and which one we divided. Nothing is computed from a value the
    source did not state.
    """
    v, u = {}, {}
    for o in obs:                       # first statement of a quantity wins
        v.setdefault(o["q"], o["v"]), u.setdefault(o["q"], o["u"])

    g = scaled(v, u, "mass", errs)
    ah, volt = scaled(v, u, "capacity", errs), scaled(v, u, "nominal_voltage", errs)
    wh = ah * volt if ah is not None and volt is not None else None

    litres = None
    if dims:
        d = [x * TO_MM.get(u.get(k, "mm"), 1.0) for x, k in
             zip(dims, ("length", "width", "thickness"))]  # dims already mm
        litres = (math.pi * (d[0] / 2) ** 2 * d[1] / 1e6 if shape == "cyl" and len(d) == 2
                  else d[0] * d[1] * d[2] / 1e6 if len(d) == 3 else None)

    out = {"wh": wh, "mass_g": g, "litres": litres}
    for key, stated, num, den in (("whkg", "specific_energy", wh, g and g / 1000),
                                  ("whl", "energy_density", wh, litres)):
        if v.get(stated) is not None:
            out[key], out[key + "_derived"] = v[stated], False
        elif num and den:
            out[key], out[key + "_derived"] = round(num / den, 1), True
        else:
            out[key], out[key + "_derived"] = None, False

    peak = scaled(v, u, "peak_power", errs)
    cur = scaled(v, u, "max_continuous_discharge_current", errs)
    out["wkg"] = (round(peak / (g / 1000), 1) if peak and g else
                  round(cur * volt / (g / 1000), 1) if cur and g and volt else None)
    out["ah"], out["v"], out["a"] = ah, volt, cur
    out["crate"] = round(cur / ah, 2) if cur and ah else None
    return out


def seed(products: list[dict]) -> list[dict]:
    """The comparison chart: cells with enough sourced numbers to place a point.

    A cell missing any of capacity, voltage or mass is left off rather than
    filled in. An absent point is a gap someone can close; a guessed one is a
    lie that plots.
    """
    rows = []
    for p in products:
        if p["kind"] != "cell":
            continue
        by = {}
        for o in p["obs"]:
            by.setdefault(o["q"], o)
        need = ("capacity", "nominal_voltage", "mass")
        if not all(q in by for q in need):
            continue
        g = by["mass"]["v"] * (1000 if by["mass"]["u"] == "kg" else 1)
        cur = by.get("max_continuous_discharge_current")
        rows.append({"cell": p["cell"], "manu": p["manu"],
                     "chem": p["chem"]["designation"] or "?", "fmt": p["fmt"],
                     "shape": p["shape"], "dims": p["dims"],
                     "ah": by["capacity"]["v"], "v": by["nominal_voltage"]["v"],
                     "g": round(g, 1), "a": cur["v"] if cur else None,
                     "uid": p["uid"]})
    return sorted(rows, key=lambda r: (-r["ah"], r["cell"]))


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
