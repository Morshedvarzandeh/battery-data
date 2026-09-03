#!/usr/bin/env python3
"""Dependency-free validation for deterministic review candidates."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UID = re.compile(r"^[a-z_]+/[a-z0-9-]+/[a-z0-9._-]+$")
KINDS = {"cell", "module", "pack", "system", "primary_cell", "component"}


def main() -> int:
    registry = json.loads((ROOT / "json-schema/quantity-registry.json").read_text())
    index = json.loads((ROOT / "review/index.json").read_text())
    errors = []
    seen = set()
    files = sorted((ROOT / "review/candidates").glob("**/*.yaml"))
    pending = [item for item in index["candidates"] if item["state"] == "pending_review"]
    indexed = {item["candidate_file"] for item in pending}

    for path in files:
        rel = str(path.relative_to(ROOT))
        try:
            doc = json.loads(path.read_text())
        except Exception as exc:
            errors.append(f"{rel}: not deterministic JSON/YAML: {exc}")
            continue
        product = doc.get("product") or {}
        uid = product.get("uid", "")
        if not UID.fullmatch(uid):
            errors.append(f"{rel}: invalid product uid {uid!r}")
        if uid in seen:
            errors.append(f"{rel}: duplicate product uid {uid}")
        seen.add(uid)
        if product.get("kind") not in KINDS:
            errors.append(f"{rel}: invalid product kind")
        if not product.get("manufacturer") or not product.get("model_number"):
            errors.append(f"{rel}: manufacturer and model_number are required")
        source = doc.get("source") or {}
        if not str(source.get("url", "")).startswith("https://"):
            errors.append(f"{rel}: source must be an https URL")
        observations = doc.get("observations") or []
        if not observations:
            errors.append(f"{rel}: no observations")
        for number, obs in enumerate(observations):
            where = f"{rel}: observation {number}"
            quantity = obs.get("quantity")
            if quantity not in registry:
                errors.append(f"{where}: unknown quantity {quantity!r}")
                continue
            if not isinstance(obs.get("value"), (int, float)) or not obs.get("unit"):
                errors.append(f"{where}: value and unit are required")
            quote = (obs.get("locator") or {}).get("quote", "")
            if len(quote) < 8:
                errors.append(f"{where}: evidence quote is missing")
            conditions = obs.get("conditions") or {}
            unstated = set(conditions.get("unstated") or [])
            for required in registry[quantity]:
                supplied = conditions.get(required) not in (None, "unspecified")
                if not supplied and required not in unstated:
                    errors.append(f"{where}: missing condition {required}")
            if (conditions.get("rate_unit") == "C"
                    and conditions.get("rate_reference_capacity_ah") is None
                    and not conditions.get("rate_reference_source")):
                errors.append(f"{where}: C-rate without rate_reference_capacity_ah or rate_reference_source")

    actual = {str(path.relative_to(ROOT)) for path in files}
    for rel in sorted(actual - indexed):
        errors.append(f"{rel}: missing from review/index.json")
    for rel in sorted(indexed - actual):
        errors.append(f"{rel}: indexed candidate file does not exist")
    if index.get("candidate_count") != len(files):
        errors.append("review/index.json candidate_count does not match files")
    if index.get("total_record_count") != len(index.get("candidates", [])):
        errors.append("review/index.json total_record_count does not match records")
    for item in index["candidates"]:
        if item["state"] == "accepted":
            accepted = item.get("accepted_file")
            if not accepted or not (ROOT / accepted).is_file():
                errors.append(f"{item['uid']}: accepted record is missing")

    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    print(f"{len(files)} review candidate(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
