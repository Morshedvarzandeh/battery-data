#!/usr/bin/env python3
"""Build the finder's data files (web/data/) from contrib/ and the registry.

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
Derived from contrib/**/*.yaml            -> web/data/cells.json (finder index),
                                             web/data/records/<manufacturer>.json
                                             (full records: every observation with
                                             its conditions and locator),
                                             web/data/summary.json (honest counts),
                                             web/data/coverage-status.json
Derived from offers/*.json               -> a `stock` field on the rows a seller
                                             lists, and the seller block in
                                             summary.json (never part of a record)
Derived from json-schema/quantity-registry -> web/data/registry.json
Derived from schema/010_vocabulary.sql     -> the test-kind taxonomy (checked)

The generated files are not committed (see .gitignore). The deploy workflow and
the local server build them; CI runs --check so a broken contribution or a
heading that names a non-existent quantity still fails the build.

Hand-curated, in web/data/, and checked against the above:
  technologies-and-chemistries.json
                        every chemistry designation filed under one technology
                        (lithium-ion, sodium-ion, lead-acid...) and, where the
                        record supports it, one chemistry (LFP, NMC, NFPP...);
                        an unfiled designation stops the build
  quantity-groups.json  which of the 98 quantities sit under which heading
  test-families.json    which of the test kinds sit under which family
  coverage.json         cells we want and do not yet have -- a wishlist, not data
  family-claims.json    claims a maker makes about a product family, not a part

The hand-curated files are presentation and intent. They are still checked:
a heading may not name a quantity that does not exist, and may not silently
drop one that does. That check is what would have caught the invented registry.

    python tools/build_web_data.py          # write web/data/
    python tools/build_web_data.py --check  # validate only (CI)
"""
from __future__ import annotations
import argparse, glob, json, math, os, re, sys
from catalog_dates import record_dates
import classification

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "web", "data")
REGISTRY = os.path.join(ROOT, "json-schema", "quantity-registry.json")
OFFERS = os.path.join(ROOT, "offers")
CLASSES = os.path.join(DATA, "technologies-and-chemistries.json")
_TAX: dict | None = None


def taxonomy() -> dict:
    global _TAX
    if _TAX is None:
        _TAX = classification.load(CLASSES)
    return _TAX
# A record whose source names no producer. It is a real row, not a company,
# so it is not counted as one of the library's manufacturers.
MAKER_NOT_STATED = "Maker not stated"
VOCAB = os.path.join(ROOT, "schema", "010_vocabulary.sql")


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
        loc = o["locator"]
        obs.append({"q": o["quantity"], "v": o["value"], "u": o["unit"],
                    "stat": o.get("statistic"), "cond": cond,
                    "lower_bound": o.get("is_lower_bound", False),
                    "upper_bound": o.get("is_upper_bound", False),
                    "unstated": unstated, "pg": loc.get("page"),
                    "section": loc.get("section"),
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
    # Technology and chemistry are derived from what the record states, apart.
    klass = classification.classify(taxonomy(), chem.get("designation"),
                                    chem.get("cathode_text"), chem.get("electrolyte_text"))
    curves = [{"kind": c["curve_kind"], "x": c["x_values"], "y": c["y_values"],
               "z": c.get("z_values"), "xq": c["x_quantity"], "yq": c["y_quantity"],
               "xu": c["x_unit"], "yu": c["y_unit"],
               "cond": {k: v for k, v in (c.get("conditions") or {}).items()
                        if k not in ("unstated", "verbatim", "extra")}}
              for c in doc.get("curves", [])]

    return {
        "uid": p["uid"], "kind": p["kind"],
        "dates": record_dates(doc),
        **({"component_type": p["component_type"]} if p.get("component_type") else {}),
        **({"lifecycle": doc["lifecycle"]} if doc.get("lifecycle") else {}),
        **({"bms": doc["bms"]} if doc.get("bms") else {}),
        "cell": (p["model_number"] if p["manufacturer"] == MAKER_NOT_STATED
                 else f"{p['manufacturer']} {p['model_number']}"),
        "manu": p["manufacturer"], "model": p["model_number"],
        "fmt": p.get("form_factor") or "", "ffc": p.get("form_factor_code"),
        "shape": SHAPE.get(p.get("form_factor", ""), "pri"),
        "dims": dims,
        "chem": {"designation": chem.get("designation"),
                 "cathode": chem.get("cathode_text"), "anode": chem.get("anode_text"),
                 "electrolyte": chem.get("electrolyte_text"),
                 "separator": chem.get("separator_text"),
                 # a chemistry claim carries its evidence like any other
                 "anode_quote": cloc.get("quote") if chem.get("anode_text") else None,
                 "cathode_quote": cloc.get("quote") if chem.get("cathode_text") else None,
                 "anode_pg": cloc.get("page"), "cathode_pg": cloc.get("page"),
                 **({"electrolyte_locator": cloc} if chem.get("electrolyte_text") else {})},
        "class": klass,
        "source": {"title": src.get("title"), "ref": src.get("revision"),
                   "date": src.get("document_date"), "kind": src.get("kind"),
                   "url": src.get("url"), "sha256": src.get("sha256"),
                   "note": src.get("note"),
                   **({"retrieved_at": src["retrieved_at"]} if src.get("retrieved_at") else {})},
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
        # A bound is not a point estimate. Keep it in the sourced details,
        # but do not silently turn it into exact comparison/derived metrics.
        if o.get("lower_bound") or o.get("upper_bound"):
            continue
        v.setdefault(o["q"], o["v"]), u.setdefault(o["q"], o["u"])

    g = scaled(v, u, "mass", errs)
    ah, volt = scaled(v, u, "capacity", errs), scaled(v, u, "nominal_voltage", errs)
    wh = ah * volt if ah is not None and volt is not None else None

    litres = None
    bounded_dimensions = any(o.get("lower_bound") or o.get("upper_bound") for o in obs
                             if o["q"] in {"length", "width", "thickness", "height", "diameter"})
    if dims and not bounded_dimensions:
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
    # A rating printed only as a C-rate stays a C-rate: amperes would need the
    # capacity the C refers to, which such sources do not state.
    rate = v.get("max_continuous_discharge_rate")
    if rate is not None and u.get("max_continuous_discharge_rate") != "C-rate":
        errs.append(f"max_continuous_discharge_rate: unit {u.get('max_continuous_discharge_rate')!r} is not 'C-rate'")
        rate = None
    out["crate_s"] = cur is None and rate is not None
    if out["crate_s"]:
        out["crate"] = rate
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
    docs = [(yaml.safe_load(open(f)), f) for f in files]
    labels = [((d.get("chemistry") or {}).get("designation"), (d.get("chemistry") or {}).get("cathode_text"),
               (d.get("chemistry") or {}).get("electrolyte_text"))
              for d, _ in docs if d["product"]["kind"] != "component"]
    cerrs = classification.check(taxonomy(), labels)
    if cerrs:
        for e in cerrs:
            print(f"  technologies-and-chemistries.json: {e}", file=sys.stderr)
        sys.exit(f"\n{len(cerrs)} classification error(s); page not written")
    products = [product(d, f) for d, f in docs]

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


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


CORE = ("capacity", "voltage", "mass", "max_continuous_discharge_current", "cycle_life",
        "internal_resistance", "dims", "operating_temperature")


def index_row(p: dict, offer: dict | None = None) -> dict:
    """One compact row for the finder table. Derived values are flagged.

    `v` is the nominal voltage when the source states one; otherwise the
    printed `voltage` column with `vq: "voltage"`, so the page can say the
    document printed a voltage without asserting it is nominal. Energy and
    Wh/kg derived from that value inherit the flag through `whkg_derived`.
    """
    by, units = {}, {}
    for o in p["obs"]:
        if o.get("lower_bound") or o.get("upper_bound"):
            continue
        by.setdefault(o["q"], o["v"]); units.setdefault(o["q"], o["u"])
    m = p["m"]
    v, vq = m["v"], "nominal_voltage"
    if v is None and by.get("voltage") is not None and units.get("voltage") == "V":
        v, vq = by["voltage"], "voltage"
    ah, g = m["ah"], m["mass_g"]
    wh = m["wh"] if m["wh"] is not None else (round(ah * v, 3) if ah is not None and v is not None else None)
    whkg, whkg_d = m["whkg"], m["whkg_derived"]
    if whkg is None and wh is not None and g:
        whkg, whkg_d = round(wh / g * 1000, 1), True
    ir = None
    for q in ("internal_resistance_ac", "internal_resistance_dc"):
        if by.get(q) is not None and units.get(q) in ("mohm", "mΩ", "ohm", "Ω"):
            ir = by[q] * (1000 if units[q] in ("ohm", "Ω") else 1); break
    dims = p["dims"]
    cyc = by.get("cycle_life")
    # A printed bound ("≥3000 cycles", "≤1 mΩ") is not a point value and stays out of
    # every metric and of `depth`, but it is not "not stated" either. Carry the first
    # one so the page can show it as the bound it is.
    bounds = {}
    for o in p["obs"]:
        if (o.get("lower_bound") or o.get("upper_bound")) and o["q"] not in bounds:
            bounds[o["q"]] = ("≥" if o.get("lower_bound") else "≤", o["v"], o["u"])
    cyc_b = list(bounds["cycle_life"][:2]) if cyc is None and "cycle_life" in bounds else None
    ir_b = None
    if ir is None:
        for q in ("internal_resistance_ac", "internal_resistance_dc"):
            if q in bounds and bounds[q][2] in ("mohm", "mΩ", "ohm", "Ω"):
                op, val, unit = bounds[q]
                ir_b = [op, val * (1000 if unit in ("ohm", "Ω") else 1)]; break
    tmin, tmax = by.get("operating_temperature_min"), by.get("operating_temperature_max")
    present = [ah is not None, v is not None, g is not None, m["a"] is not None or m["crate_s"], cyc is not None,
               ir is not None, dims is not None, tmin is not None]
    s = p["source"]
    doc = (s.get("date") or "")[:4] or None
    # Year, as the source supports it. A documented product release first; else
    # the document's own date; else a revision that is plainly a year ("2019"
    # on a 2019 selection guide). `yk` says which, so the page can label it.
    year, yk = None, None
    rel = (p.get("dates") or {}).get("release") or {}
    if rel.get("status") == "documented" and (rel.get("event") or {}).get("date"):
        year, yk = rel["event"]["date"][:4], "release"
    elif doc:
        year, yk = doc, "doc"
    elif re.fullmatch(r"(19|20)\d{2}", str(s.get("ref") or "")):
        year, yk = str(s["ref"]), "doc"
    # the three ratings that matter most for a component, as printed
    ratings = []
    if p["kind"] == "component":
        for q in ("continuous_carry_current", "contact_voltage_rating", "fuse_current_rating",
                  "fuse_voltage_rating", "interrupting_current", "bms_series_cells_max",
                  "bms_pack_voltage_max", "rated_output_current", "input_voltage_max",
                  "resistance_rating", "resistor_power_rating"):
            if by.get(q) is not None:
                ratings.append(f"{q.replace('_', ' ')} {by[q]:g} {units.get(q) or ''}".strip())
            if len(ratings) == 3:
                break
    return {
        "uid": p["uid"], "kind": p["kind"], "manu": p["manu"], "model": p["model"],
        **({"ct": p["component_type"]} if p.get("component_type") else {}),
        "chem": p["chem"]["designation"], "fmt": p["fmt"] or None,
        "tech": p["class"]["tech"], "tvar": p["class"]["variant"], "cclass": p["class"]["chem"],
        "ffc": p.get("ffc"), "ah": ah, "v": v, "vq": vq if v is not None else None,
        "g": g, "wh": wh, "whkg": whkg, "whkg_d": whkg_d, "whl": m["whl"],
        "a": m["a"], "crate": m["crate"], "crate_s": m["crate_s"], "cyc": cyc, "ir": ir, "dims": dims,
        **({"cyc_b": cyc_b} if cyc_b else {}), **({"ir_b": ir_b} if ir_b else {}), "shape": p["shape"],
        "tmin": tmin, "tmax": tmax, "depth": sum(present), "n": len(p["obs"]),
        "src": s.get("kind"), "doc": doc, "year": year, "yk": yk, "url": s.get("url"), "title": s.get("title"),
        "ratings": ratings, "shard": slug(p["manu"]),
        # A seller's availability rides on the row for display and an opt-in
        # filter only. It is read after `depth` and touches no metric.
        **({"stock": offer} if offer else {}),
    }


def load_offers(known: set[str]) -> tuple[dict[str, dict], list[dict], list[str]]:
    """Seller stock lists, checked against the accepted products.

    An offer is a seller's own statement. It names a product by uid and adds
    nothing to the product: an unknown uid, an unknown status or a malformed
    date stops the build rather than showing a badge on the wrong row.
    """
    by_uid, sellers, errs = {}, [], []
    schema = None
    try:
        import jsonschema
        schema = jsonschema.Draft202012Validator(load(os.path.join(ROOT, "json-schema", "offer.schema.json")))
    except ImportError:
        pass
    for path in sorted(glob.glob(os.path.join(OFFERS, "*.json"))):
        rel = os.path.relpath(path, ROOT)
        doc = load(path)
        if schema is not None:
            problems = sorted(schema.iter_errors(doc), key=lambda e: list(e.absolute_path))
            errs += [f"{rel}: {'/'.join(map(str, e.absolute_path))}: {e.message}" for e in problems]
            if problems:
                continue
        seller = doc["seller"]
        listed = []
        for o in doc["offers"]:
            if o["status"] not in ("in_stock", "on_request"):
                errs.append(f"{rel}: {o['uid']}: unknown status {o['status']!r}")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["as_of"]):
                errs.append(f"{rel}: {o['uid']}: as_of must be YYYY-MM-DD")
            if o["uid"] not in known:
                errs.append(f"{rel}: {o['uid']} is not an accepted product")
            if o["uid"] in by_uid:
                errs.append(f"{rel}: {o['uid']} is offered twice")
            by_uid[o["uid"]] = {"by": seller["name"], "s": o["status"], "d": o["as_of"]}
            listed.append(o)
        sellers.append({**seller, "statement": doc["statement"], "count": len(listed),
                        "as_of": max((o["as_of"] for o in listed), default=None)})
    return by_uid, sellers, errs


def summary(rows: list[dict], sellers: list[dict] | None = None) -> dict:
    cells = [r for r in rows if r["kind"] != "component"]
    return {
        "battery_records": len(cells),
        "component_records": len(rows) - len(cells),
        "manufacturers": len({r["manu"] for r in cells} - {MAKER_NOT_STATED}),
        "maker_not_stated": sum(1 for r in cells if r["manu"] == MAKER_NOT_STATED),
        "sellers": sellers or [],
        "available_now": sum(1 for r in rows if (r.get("stock") or {}).get("s") == "in_stock"),
        "with_capacity_voltage_mass": sum(1 for r in cells if r["ah"] is not None and r["v"] is not None and r["g"] is not None),
        "with_nominal_voltage": sum(1 for r in cells if r["vq"] == "nominal_voltage"),
        "with_continuous_discharge": sum(1 for r in cells if r["a"] is not None or r.get("crate_s")),
        "with_cycle_life": sum(1 for r in cells if r["cyc"] is not None),
        "with_internal_resistance": sum(1 for r in cells if r["ir"] is not None),
        "with_form_factor": sum(1 for r in cells if r["fmt"]),
        "with_document_date": sum(1 for r in cells if r["doc"]),
        "with_release_year": sum(1 for r in cells if r["yk"] == "release"),
        "with_any_year": sum(1 for r in cells if r["year"]),
        "observations": sum(r["n"] for r in rows),
        "by_manufacturer": dict(sorted(((m, sum(1 for r in cells if r["manu"] == m)) for m in {r["manu"] for r in cells}), key=lambda kv: -kv[1])),
    }


def write_json(path: str, payload) -> bool:
    """Write only when the content changed, so timestamps stay honest."""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == body:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate groupings and contributions; write nothing")
    ap.add_argument("--out", default=DATA, help="output directory (default web/data)")
    a = ap.parse_args()

    blobs = build()
    products = blobs["CONTRIB"]["PRODUCTS"]
    offers, sellers, offer_errs = load_offers({p["uid"] for p in products})
    if offer_errs:
        for e in offer_errs:
            print(f"  {e}", file=sys.stderr)
        sys.exit(f"\n{len(offer_errs)} offer error(s); page not written")
    rows = [index_row(p, offers.get(p["uid"])) for p in products]
    n, charted = len(rows), sum(1 for r in rows if r["kind"] != "component" and r["whkg"])
    for p in products:
        for e in p["unit_errors"]:
            print(f"  {p['uid']}: {e}", file=sys.stderr)
    if a.check:
        print(f"ok: {n} products build ({charted} chartable); groupings consistent; "
              f"{len(offers)} offered by {len(sellers)} seller(s)")
        return 0

    out = a.out
    changed = write_json(os.path.join(out, "cells.json"), rows)
    changed |= write_json(os.path.join(out, "summary.json"), summary(rows, sellers))
    changed |= write_json(os.path.join(out, "registry.json"), blobs["REGISTRY"])
    changed |= write_json(os.path.join(out, "coverage-status.json"), blobs["CONTRIB"]["COVERAGE"])
    shards: dict[str, list[dict]] = {}
    for p in products:
        shards.setdefault(slug(p["manu"]), []).append(p)
    for name, recs in shards.items():
        changed |= write_json(os.path.join(out, "records", f"{name}.json"), recs)
    print(f"wrote {os.path.relpath(out, ROOT)}/: {n} products in {len(shards)} record shards, "
          f"{charted} on the chart{'' if changed else ' (no change)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
