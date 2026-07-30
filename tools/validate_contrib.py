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


def check(path: str, schema: dict, registry: dict) -> list[str]:
    errs: list[str] = []
    doc = yaml.safe_load(open(path))

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

    all_errs = []
    for f in files:
        e = check(f, schema, registry)
        rel = os.path.relpath(f, ROOT)
        print(f"  {'FAIL' if e else 'ok  '}  {rel}")
        all_errs += e

    for e in all_errs:
        print(f"\n  {e}", file=sys.stderr)
    print(f"\n{len(files)} file(s), {len(all_errs)} error(s)")
    return 1 if all_errs else 0


if __name__ == "__main__":
    sys.exit(main())
