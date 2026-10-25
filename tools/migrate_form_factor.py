#!/usr/bin/env python3
"""Record the form factor of lithium-polymer catalog cells.

WHY
---
3,263 of 3,455 battery records carried no `product.form_factor`. Almost all of
them are lithium-polymer catalog rows (LiPol Battery, Harding Energy, EEMB)
whose source prints a family heading ("Li Po Batteries", "Lithium Polymer Cell
Selection Guide") and three rectangular dimensions per row, and never the word
"pouch". The importers correctly refused to invent a value the row did not
print. The result was a finder in which "format" matched 5 % of records.

A lithium-polymer cell sold by length x width x thickness is a pouch cell: the
laminate construction is what the family name denotes, and the rectangular
dimension triple excludes a can. This migration records that as `pouch` and
writes the basis into the source note so a reader can see it was derived from
the family heading plus the dimension set, not printed per row.

RULE (all must hold)
--------------------
  product.kind == "cell" and product.form_factor is absent
  chemistry.designation in {"Lithium polymer", "Lithium-ion polymer"}
  observations contain length, width and thickness and no diameter

Anything else is left alone. Idempotent: a second run changes nothing.

    python tools/migrate_form_factor.py            # apply
    python tools/migrate_form_factor.py --check    # report, exit 1 if work remains
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(ROOT, "contrib", "cells")
AUDIT = os.path.join(ROOT, "review", "audits", "2026-10-25-form-factor-revision.json")
POLYMER = {"Lithium polymer", "Lithium-ion polymer"}
BASIS = ("Form factor recorded as pouch by tools/migrate_form_factor.py: derived "
         "from the lithium-polymer family heading and the rectangular length x "
         "width x thickness dimension set; the source does not print a form "
         "factor per row.")


def eligible(d: dict) -> bool:
    p = d.get("product") or {}
    if p.get("kind") != "cell" or p.get("form_factor"):
        return False
    if (d.get("chemistry") or {}).get("designation") not in POLYMER:
        return False
    q = {o.get("quantity") for o in d.get("observations") or []}
    return {"length", "width", "thickness"} <= q and "diameter" not in q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    todo = []
    for f in sorted(glob.glob(os.path.join(CELLS, "**", "*.yaml"), recursive=True)):
        with open(f, encoding="utf-8") as fh:
            head = fh.read(1)
            if head != "{":
                continue  # hand-written YAML records already state a form factor
            fh.seek(0)
            d = json.load(fh)
        if eligible(d):
            todo.append((f, d))
    if a.check:
        print(f"{len(todo)} record(s) still without a derivable form factor" if todo
              else "ok: every lithium-polymer catalog record states its form factor")
        return 1 if todo else 0
    sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
    revisions = []
    for f, d in todo:
        before = sha(f)
        # keep key order: form_factor goes after model_number as in the schema
        p = d["product"]
        items = list(p.items())
        i = next(k for k, (key, _) in enumerate(items) if key == "model_number") + 1
        items.insert(i, ("form_factor", "pouch"))
        d["product"] = dict(items)
        s = d.setdefault("source", {})
        note = s.get("note") or ""
        if BASIS not in note:
            s["note"] = (note.rstrip() + " " + BASIS).strip()
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        revisions.append({
            "uid": d["product"]["uid"],
            "file": os.path.relpath(f, ROOT),
            "previous_sha256": before,
            "revised_sha256": sha(f),
            "fields": ["product.form_factor", "source.note"],
            "change": "form_factor: pouch recorded; basis appended to source.note",
        })
    # The revision audit is the ledger entry tests resolve the new bytes through
    # (tools/review_ledger.py). Appending keeps a re-run from erasing history.
    audit = {"schema_version": "1", "reviewed_at": date.today().isoformat(),
             "reviewer": "deterministic migration, tools/migrate_form_factor.py",
             "authorization": "Owner-requested catalog review of 2026-10-25 (finder redesign)",
             "scope": "Accepted lithium-polymer catalog cells without a recorded form factor",
             "basis": BASIS, "revisions": []}
    if os.path.exists(AUDIT):
        with open(AUDIT, encoding="utf-8") as fh:
            audit = json.load(fh)
    audit["revisions"].extend(revisions)
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"recorded form_factor: pouch on {len(todo)} record(s); audit: {os.path.relpath(AUDIT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
