#!/usr/bin/env python3
"""Move C-rates out of the ampere quantities.

WHY
---
Twenty REPT records store "Fast Charging (10%~80%) 2.2C" as
`max_continuous_charge_current` with unit `C`. In the unit table (schema/
010_vocabulary.sql) `C` is the coulomb, so the database stored 2.2 C as 2.2
coulombs: a charge, where a current was expected, and a number with no
relation to the cell's real charge current (2.2C on a 104 Ah cell is about
229 A). Nothing flagged it, because the unit exists and the value is
plausible-looking.

A C-rate is a multiple of capacity, not a current. Since 28 October 2026 the
registry has quantities for exactly this (schema/138_c_rate_quantities.sql),
stored with unit `C-rate` (1/h). This migration moves each such observation
to its C-rate twin and keeps everything else -- value, conditions, quote --
as recorded. It does not convert to amperes: the source does not say which
capacity its C-rate refers to.

RULE
----
An observation whose quantity is one of the four ampere current limits and
whose unit is exactly "C" is moved to the matching *_rate quantity with unit
"C-rate". Anything else is left alone. Idempotent: a second run finds nothing.

Every change is recorded as a revision in the audit file, so
tools/review_ledger.py can pin the new bytes.

    python tools/migrate_c_rate_units.py            # apply
    python tools/migrate_c_rate_units.py --check    # exit 1 if work remains
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, sys
import c_rates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "review", "audits", "2026-10-28-c-rate-unit-revision.json")
NOTE = ("C-rate revision (2026-10-28, tools/migrate_c_rate_units.py): the printed C-rate was "
        "stored as a current with unit C, which the unit table reads as coulombs; it is now "
        "recorded as {q} with unit C-rate. The value is unchanged and is not converted to amperes.")


def revise(doc: dict) -> list[str]:
    moved = [o["quantity"] for o in doc.get("observations") or [] if c_rates.normalize(o)]
    if moved:
        src = doc["source"]
        src["note"] = (src.get("note", "").rstrip() + " " + NOTE.format(q=", ".join(sorted(set(moved))))).strip()
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    revisions = []
    for f in sorted(glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"), recursive=True)):
        raw = open(f, encoding="utf-8").read()
        if not raw.lstrip().startswith("{"):
            # YAML-bodied files are reported, never rewritten, so their formatting survives.
            import yaml
            doc = yaml.safe_load(raw) or {}
            if any(c_rates.is_misfiled(o) for o in doc.get("observations") or []):
                sys.exit(f"{os.path.relpath(f, ROOT)}: C-rate stored as a current in a YAML-bodied file; fix it by hand")
            continue
        doc = json.loads(raw)
        moved = revise(doc)
        if not moved:
            continue
        rel = os.path.relpath(f, ROOT)
        body = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        revisions.append({
            "uid": doc["product"]["uid"], "file": rel,
            "previous_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "revised_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "fields": ["observations", "source.note"],
            "change": "; ".join(f"{q}: unit C (coulomb) -> C-rate" for q in moved),
        })
        if not a.check:
            open(f, "w", encoding="utf-8").write(body)
    if a.check:
        print(f"{len(revisions)} file(s) still store a C-rate as a current")
        return 1 if revisions else 0
    if revisions:
        audit = {
            "schema_version": "1",
            "reviewed_at": "2026-10-28",
            "reviewer": "deterministic migration, tools/migrate_c_rate_units.py",
            "authorization": "Repository owner, in chat, 2026-10-28: explain the REPT unit error and fix it",
            "scope": "Accepted records storing a C-rate in an ampere current quantity with unit C",
            "basis": ("Unit C is the coulomb in schema/010_vocabulary.sql. Each value is moved, unchanged, to "
                      "the matching C-rate quantity from schema/138_c_rate_quantities.sql with unit C-rate. "
                      "No ampere value is derived."),
            "revisions": revisions,
        }
        with open(AUDIT, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(audit, indent=1, ensure_ascii=False) + "\n")
    print(f"revised {len(revisions)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
