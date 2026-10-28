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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c_rates  # noqa: E402

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml jsonschema")
import jsonschema
from datetime import date
import re
from catalog_dates import date_value

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


def check(path: str, schema: dict, registry: dict, *, validator=None) -> list[str]:
    errs: list[str] = []
    with open(path) as stream:
        raw = stream.read()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        doc = yaml.safe_load(raw)

    try:
        (validator or jsonschema.Draft202012Validator(schema)).validate(doc)
    except jsonschema.ValidationError as e:
        loc = "/".join(str(p) for p in e.absolute_path)
        return [f"{path}: structural: {loc}: {e.message}"]

    for i, obs in enumerate(doc.get("observations", [])):
        q = obs["quantity"]
        where = f"{path}: observations[{i}] ({q})"

        if q not in registry:
            errs.append(f"{where}: unknown quantity")
            continue

        # "C" is the coulomb in the unit table. A printed C-rate stored here
        # loads as a charge, not a current (2.2C became 2.2 coulombs).
        if c_rates.is_misfiled(obs):
            errs.append(f"{where}: unit 'C' is the coulomb, not a C-rate. Record a printed "
                        f"C-rate as '{c_rates.TWIN[q]}' with unit 'C-rate'; do not convert it "
                        f"to amperes unless the source does.")

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

    errs += check_applications(path, doc)
    errs += check_lifecycle(path, doc)
    for field in ('document_date', 'retrieved_at'):
        value = doc.get('source', {}).get(field)
        try:
            parsed = date_value(value)
            if value and field == 'retrieved_at' and parsed['precision'] != 'day':
                raise ValueError('retrieved_at must identify the day checked')
        except ValueError as error:
            errs.append(f'{path}: source.{field}: {error}')
    return errs


def check_lifecycle(path: str, doc: dict) -> list[str]:
    """A source update is not a launch; partial dates must stay partial."""
    life = doc.get('lifecycle')
    if not life:
        return []
    errors = []
    checked = life['checked_at']
    events = list(life['events'])
    if life['release'].get('event'):
        events.append(life['release']['event'])
    errors += check_events(path, events, checked)
    value = life['market_evidence']['retrieved_at']
    try:
        if date_value(value)['precision'] != 'day':
            raise ValueError('market evidence retrieval requires day precision')
        if value > checked:
            errors.append(f'{path}: lifecycle: market evidence retrieved after check')
    except ValueError:
        errors.append(f'{path}: lifecycle: invalid calendar date {value}')
    return errors


def check_events(path: str, events: list, checked: str) -> list[str]:
    """Shared chronology checks for product lifecycle and platform milestones."""
    errors = []
    for value in [checked] + [e['evidence']['retrieved_at'] for e in events]:
        try:
            if date_value(value)['precision'] != 'day':
                raise ValueError('evidence checks require day precision')
        except ValueError:
            errors.append(f'{path}: lifecycle: invalid calendar date {value}')
        if value > checked:
            errors.append(f'{path}: lifecycle: evidence retrieved after check')
    patterns = {'year': r'\d{4}', 'month': r'\d{4}-\d{2}', 'day': r'\d{4}-\d{2}-\d{2}'}
    for event in events:
        value, precision = event.get('date'), event['precision']
        if precision == 'unspecified':
            if value is not None:
                errors.append(f'{path}: lifecycle: unspecified date must retain only date_text')
            continue
        if not value or not re.fullmatch(patterns[precision], value):
            errors.append(f'{path}: lifecycle: date does not match {precision} precision')
            continue
        try:
            date.fromisoformat(value + {'year': '-01-01', 'month': '-01', 'day': ''}[precision])
        except ValueError:
            errors.append(f'{path}: lifecycle: invalid event calendar date {value}')
        if event['event_type'] != 'planned_availability' and value > checked[:len(value)]:
            errors.append(f'{path}: lifecycle: an observed event cannot be in the future')
    return errors


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
    validator = jsonschema.Draft202012Validator(schema)
    registry = load_registry(a.dsn)

    files = ([a.path] if a.path.endswith((".yaml", ".yml"))
             else sorted(glob.glob(os.path.join(a.path, "**", "*.y*ml"), recursive=True)))
    if not files:
        print(f"no contribution files under {a.path}")
        return 0

    all_errs = []
    for f in files:
        e = check(f, schema, registry, validator=validator)
        rel = os.path.relpath(f, ROOT)
        print(f"  {'FAIL' if e else 'ok  '}  {rel}")
        all_errs += e

    for e in all_errs:
        print(f"\n  {e}", file=sys.stderr)
    print(f"\n{len(files)} file(s), {len(all_errs)} error(s)")
    return 1 if all_errs else 0


if __name__ == "__main__":
    sys.exit(main())
