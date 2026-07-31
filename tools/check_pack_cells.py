#!/usr/bin/env python3
"""Check the pack designer's cell library against the contributions it cites.

The designer keeps its own cell records, because it needs geometry and current
limits that a spec extraction often does not carry. That is fine. What is not
fine is a record claiming to rest on a document in this repository when no such
document exists -- the label then reads as evidence while being recall.

So `basis: 'contrib'` is a checkable claim, not a badge:

  - every contribUid must resolve to a real file under contrib/
  - a record with a contribUid must say basis 'contrib', and vice versa
  - values the contribution states and the designer repeats must agree; a
    silent divergence means one of the two has drifted and a reader cannot
    tell which

Anything else -- external datasheets, teardowns, composites -- is allowed and
untouched here. It just may not claim to be sourced from this repository.

    python tools/check_pack_cells.py
"""
from __future__ import annotations
import glob, json, os, re, subprocess, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS_JS = os.path.join(ROOT, "web", "pack-designer", "js", "cells.js")

VALID_BASIS = {"contrib", "external_datasheet", "teardown", "composite", "recalled"}

# Designer field -> (contribution quantity, unit the designer uses).
# Only quantities where both sides mean exactly the same thing; capacity and
# voltage are safe, current limits are not (the designer's are often derived
# from a stated power figure, which is a different claim).
COMPARED = {
    "capacityAh": ("capacity", "Ah"),
    "nominalV": ("nominal_voltage", "V"),
    "massG": ("mass", "g"),
}
SCALE = {("mAh", "Ah"): 0.001, ("Ah", "Ah"): 1.0,
         ("V", "V"): 1.0, ("mV", "V"): 0.001,
         ("g", "g"): 1.0, ("kg", "g"): 1000.0}


def load_cells() -> list[dict]:
    """Read CELLS out of the ES module without a bundler.

    node is already required by nothing else in CI, so parse via node if it is
    present and fall back to a regex if it is not.
    """
    try:
        out = subprocess.run(
            ["node", "--input-type=module", "-e",
             f"import {{CELLS}} from {json.dumps(CELLS_JS)};"
             "process.stdout.write(JSON.stringify(CELLS));"],
            capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        sys.exit(f"could not evaluate {CELLS_JS}: {e}")


def load_contrib() -> dict[str, dict]:
    out = {}
    for f in glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"), recursive=True):
        d = yaml.safe_load(open(f))
        vals = {}
        for o in d.get("observations", []):
            vals.setdefault(o["quantity"], (o["value"], o["unit"]))
        out[d["product"]["uid"]] = {"file": os.path.relpath(f, ROOT), "vals": vals}
    return out


def main() -> int:
    cells, contrib = load_cells(), load_contrib()
    errs: list[str] = []

    for c in cells:
        cid, basis, uid = c["id"], c.get("basis"), c.get("contribUid")

        if basis not in VALID_BASIS:
            errs.append(f"{cid}: basis {basis!r} is not one of {sorted(VALID_BASIS)}")
        if (basis == "contrib") != bool(uid):
            errs.append(
                f"{cid}: basis {basis!r} and contribUid {uid!r} disagree. "
                f"'contrib' means a document in this repository backs it; "
                f"anything else must not carry a contribUid.")
        if not uid:
            continue
        if uid not in contrib:
            errs.append(f"{cid}: contribUid {uid!r} matches no file under contrib/")
            continue

        inferred = set(c.get("inferredFields") or [])
        if "ALL" in inferred:
            errs.append(f"{cid}: basis 'contrib' with inferredFields ['ALL'] — "
                        f"if everything is inferred, the document is not the basis")
            continue

        src = contrib[uid]
        for field, (quantity, want_unit) in COMPARED.items():
            if field in inferred or c.get(field) is None:
                continue
            if quantity not in src["vals"]:
                continue
            value, unit = src["vals"][quantity]
            k = SCALE.get((unit, want_unit))
            if k is None:
                errs.append(f"{cid}: {quantity} in {src['file']} is in {unit!r}, "
                            f"which this check cannot convert to {want_unit!r}")
                continue
            stated, shown = value * k, c[field]
            if abs(stated - shown) > max(abs(stated) * 0.005, 1e-9):
                errs.append(
                    f"{cid}: {field}={shown} {want_unit} but {src['file']} "
                    f"states {quantity}={value} {unit} (= {stated:g} {want_unit})")

    linked = sum(1 for c in cells if c.get("contribUid"))
    for e in errs:
        print(f"  {e}", file=sys.stderr)
    print(f"{len(cells)} cells, {linked} claiming a contribution, {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
