#!/usr/bin/env python3
"""
Validate community contributions in contrib/ .

Two passes, because JSON Schema alone is not sufficient:

  1. Structural  - jsonschema against json-schema/cell-contribution.schema.json
  2. Semantic    - every quantity must exist in bd.quantity, and every entry in
                   its required_conditions must be supplied or declared in
                   `unstated`.

Pass 2 is the one that matters. It is what stops a contributor submitting a
capacity with no rate, or an internal resistance with no method. It needs the
quantity registry, so it reads either a live database or the offline registry
dumped by tools/dump_quantities.py.

    python tools/validate_contrib.py contrib/            # offline registry
    python tools/validate_contrib.py contrib/ --dsn dbname=batterydb
"""
from __future__ import annotations
import argparse, json, os, sys, glob

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml jsonschema")
import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "json-schema", "cell-contribution.schema.json")
REGISTRY = os.path.join(ROOT, "json-schema", "quantity-registry.json")


def load_registry(dsn: str | None) -> dict[str, list[str]]:
    if dsn:
        import psycopg2
        with psycopg2.connect(dsn) as c, c.cursor() as cur:
            cur.execute("SELECT code, required_conditions FROM bd.quantity")
            return {r[0]: list(r[1] or []) for r in cur.fetchall()}
    if os.path.exists(REGISTRY):
        return json.load(open(REGISTRY))
    sys.exit(f"no registry at {REGISTRY}; run tools/dump_quantities.py or pass --dsn")


def check(path: str, schema: dict, registry: dict, known: set[str] | None = None) -> list[str]:
    errs: list[str] = []
    doc = yaml.safe_load(open(path))
    known = known or set()

    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as e:
        loc = "/".join(str(p) for p in e.absolute_path)
        return [f"{path}: structural: {loc}: {e.message}"]

    for i, obs in enumerate(doc.get("observations", [])):
        q = obs["quantity"]
        where = f"{path}: observations[{i}] ({q})"

        if q not in registry:
            errs.append(f"{where}: unknown quantity")
            continue

        cond = obs.get("conditions") or {}
        unstated = set(cond.get("unstated") or [])
        for req in registry[q]:
            supplied = cond.get(req) is not None and cond.get(req) != "unspecified"
            if not supplied and req not in unstated:
                errs.append(
                    f"{where}: missing required condition '{req}'. Supply it, or "
                    f"if the source does not state it, add '{req}' to "
                    f"conditions.unstated -- do not omit it."
                )

        # Conditions on a quantity that needs none is a smell, not an error.
        if not registry[q] and cond and set(cond) - {"verbatim", "extra", "unstated"}:
            pass
        errs += check_c_rate(where, cond)

    for i, curve in enumerate(doc.get("curves", [])):
        where = f"{path}: curves[{i}] ({curve.get('curve_kind')})"
        # A curve whose axis names a quantity the registry lacks is dropped by
        # the loader without a word; the CATL charge derating map was, until
        # max_pulse_charge_current existed.
        for axis in ("x_quantity", "y_quantity", "z_quantity"):
            code = curve.get(axis)
            if code is not None and code not in registry:
                errs.append(f"{where}: {axis} {code!r} is not a registry quantity")
        errs += check_c_rate(where, curve.get("conditions") or {})

    errs += check_applications(path, doc)
    errs += check_links(path, doc, known)
    return errs


def check_links(path: str, doc: dict, known: set[str]) -> list[str]:
    """Bill-of-materials and equivalence links point at library products.

    A `contains` entry naming a product that is not in the library would land
    nowhere: the loader has no revision to attach it to. It is an error here
    so the missing child is written first, not discovered as a silent gap in
    the graph. An equivalence to a product outside the library is a claim
    that cannot be checked either way, so it is a warning-grade error too.
    """
    errs = []
    me = doc["product"]["uid"]
    for i, link in enumerate(doc.get("contains") or []):
        where = f"{path}: contains[{i}] ({link.get('uid')})"
        if link.get("uid") == me:
            errs.append(f"{where}: a product cannot contain itself")
        elif known and link.get("uid") not in known:
            errs.append(f"{where}: child product is not in the library; add its "
                        f"contribution first so the assembly edge has something to point at")
    for i, link in enumerate(doc.get("equivalences") or []):
        where = f"{path}: equivalences[{i}] ({link.get('uid')})"
        if link.get("uid") == me:
            errs.append(f"{where}: a product cannot be equivalent to itself")
        elif known and link.get("uid") not in known:
            errs.append(f"{where}: the other product is not in the library")
    seen = set()
    for i, offer in enumerate(doc.get("offers") or []):
        key = (offer.get("seller"), offer.get("region"), offer.get("observed_at"))
        if key in seen:
            errs.append(f"{path}: offers[{i}]: duplicate seller/region/date; a price is a "
                        f"time series with one point per observation date")
        seen.add(key)
    return errs


def check_c_rate(where: str, cond: dict) -> list[str]:
    """A C-rate is self-referential; the database refuses one with no reference.

    LG calls 1C 4800 mA and Samsung 4900 mA (docs/02-conventions.md section 4),
    so "0.2C" is a different current per vendor. bd.condition_set enforces
    this with a CHECK, and a file that passes here only to be refused at load
    time is a promotion that looks accepted and is not. Say which capacity the
    rate refers to, or say the document does not: rate_reference_source
    'unstated' with rate_reference_capacity_ah listed as unstated.
    """
    if cond.get("rate_unit") != "C":
        return []
    if cond.get("rate_reference_capacity_ah") is not None or cond.get("rate_reference_source"):
        return []
    return [f"{where}: a C-rate needs its reference capacity. Set "
            f"rate_reference_capacity_ah, or rate_reference_source: unstated when the "
            f"document never defines 1C (and list rate_reference_capacity_ah in unstated)."]


# Bases where somebody with direct knowledge put the claim in writing. Anything
# else is a reading of indirect evidence, and must say how sure it is.
FIRSTHAND_BASES = {"manufacturer_stated", "regulatory_filing"}


def check_applications(path: str, doc: dict) -> list[str]:
    """Deployment claims get the same treatment as observations.

    The failure mode here is different from a wrong number: this can be wrong
    about whether the relationship exists at all. So a claim resting on a
    teardown, a trade article or an inference has to carry an explicit
    confidence rather than sitting in the table looking as solid as a
    datasheet line.
    """
    errs, seen = [], {}
    for i, app in enumerate(doc.get("applications", [])):
        where = f"{path}: applications[{i}] ({app.get('uid', '?')})"
        basis = app["basis"]

        if basis not in FIRSTHAND_BASES and app.get("confidence") is None:
            errs.append(
                f"{where}: basis '{basis}' is indirect evidence, so 'confidence' "
                f"is required. State how sure you are -- an unhedged teardown "
                f"claim reads like a manufacturer statement."
            )

        if app.get("in_service_to") and app.get("in_service_from") \
                and app["in_service_to"] < app["in_service_from"]:
            errs.append(f"{where}: in_service_to precedes in_service_from")

        # Same application named twice in one file means one of the two rows
        # will silently lose the UNIQUE race at load time.
        key = (app["uid"], app.get("role"))
        if key in seen:
            errs.append(f"{where}: duplicate of applications[{seen[key]}] "
                        f"(same uid and role)")
        seen[key] = i

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=os.path.join(ROOT, "contrib"))
    ap.add_argument("--dsn")
    a = ap.parse_args()

    schema = json.load(open(SCHEMA))
    jsonschema.Draft202012Validator.check_schema(schema)
    registry = load_registry(a.dsn)

    files = ([a.path] if a.path.endswith((".yaml", ".yml"))
             else sorted(glob.glob(os.path.join(a.path, "**", "*.y*ml"), recursive=True)))
    if not files:
        print(f"no contribution files under {a.path}")
        return 0

    # Every uid under contrib/, so bill-of-materials links can be checked
    # against the library as a whole rather than the file being validated.
    known = set()
    for f in sorted(glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"), recursive=True)):
        try:
            known.add(yaml.safe_load(open(f))["product"]["uid"])
        except Exception:
            pass

    all_errs = []
    for f in files:
        e = check(f, schema, registry, known)
        rel = os.path.relpath(f, ROOT)
        print(f"  {'FAIL' if e else 'ok  '}  {rel}")
        all_errs += e

    for e in all_errs:
        print(f"\n  {e}", file=sys.stderr)
    print(f"\n{len(files)} file(s), {len(all_errs)} error(s)")
    return 1 if all_errs else 0


if __name__ == "__main__":
    sys.exit(main())
