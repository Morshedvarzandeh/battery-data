"""A deterministic read snapshot of accepted GitHub contributions, like web/data.

The snapshot is derived; it is never a second editorial database. Deploy the same
file to every worker. Clients pin its content hash to detect a release change.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import jsonschema
import yaml

from tools.validate_contrib import check

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "https://github.com/Morshedvarzandeh/battery-data"
BATTERY_KINDS = {"cell", "primary_cell", "module", "pack", "system"}
COMPONENT_TYPES = {"contactor", "precharge_contactor", "fuse", "inverter", "dc_dc_converter", "charger"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build(root: Path, revision: str):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("revision must be the full Git commit SHA for this data checkout")
    schema = json.loads((root / "json-schema/cell-contribution.schema.json").read_text())
    registry = json.loads((root / "json-schema/quantity-registry.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    records = []
    seen = set()
    for path in sorted((root / "contrib").rglob("*.yaml")):
        if path.is_symlink() or not path.resolve().is_relative_to((root / "contrib").resolve()):
            raise ValueError("contributions must be regular files inside contrib/")
        errors = check(str(path), schema, registry, validator=validator)
        if errors:
            raise ValueError("\n".join(errors))
        raw = path.read_text()
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = yaml.safe_load(raw)
        uid = doc["product"]["uid"]
        if uid in seen:
            raise ValueError(f"duplicate product UID: {uid}")
        seen.add(uid)
        # Approval is the promotion into contrib/; never scan review/ or seed/.
        records.append({"file": path.relative_to(root).as_posix(), "record": doc})
    if not records:
        raise ValueError("refusing an empty accepted catalog")
    content = {"format_version": 1, "source_revision": revision,
               "records": sorted(records, key=lambda r: r["record"]["product"]["uid"])}
    return {**content, "release": digest(content)}


class Catalog:
    def __init__(self, snapshot):
        content = {k: v for k, v in snapshot.items() if k != "release"}
        if snapshot.get("format_version") != 1 or snapshot.get("release") != digest(content):
            raise ValueError("invalid catalog format or content hash")
        if not re.fullmatch(r"[0-9a-f]{40}", snapshot["source_revision"]):
            raise ValueError("invalid source revision")
        self.release = snapshot["release"]
        self.revision = snapshot["source_revision"]
        self.entries = snapshot["records"]
        self.by_uid = {r["record"]["product"]["uid"]: r for r in self.entries}
        if len(self.by_uid) != len(self.entries) or not self.entries:
            raise ValueError("empty catalog or duplicate UID")
        if any(not r["file"].startswith("contrib/") or ".." in Path(r["file"]).parts
               for r in self.entries):
            raise ValueError("catalog includes a file outside the accepted library")
        self.counts = dict(Counter(r["record"]["product"]["kind"] for r in self.entries))

    def summary(self, entry):
        doc = entry["record"]
        return {"product": doc["product"], "chemistry": doc.get("chemistry"),
                "source": doc["source"], "observation_count": len(doc["observations"]),
                "review_status": "accepted",
                "record_url": f"{REPOSITORY}/blob/{self.revision}/{entry['file']}"}

    def detail(self, uid):
        entry = self.by_uid.get(uid)
        if entry is None:
            return None
        return {**self.summary(entry), "record": entry["record"]}

    def select(self, filters, batteries_only=False):
        output = []
        for entry in self.entries:
            doc = entry["record"]
            p = doc["product"]
            if batteries_only and p["kind"] not in BATTERY_KINDS:
                continue
            if filters.kind and p["kind"] != filters.kind:
                continue
            if filters.component_type and p.get("component_type") != filters.component_type:
                continue
            if filters.manufacturer and p["manufacturer"].casefold() != filters.manufacturer.casefold():
                continue
            if filters.chemistry and (doc.get("chemistry", {}).get("designation") or "").casefold() != filters.chemistry.casefold():
                continue
            if filters.q and filters.q.casefold() not in " ".join(
                    (p["uid"], p["manufacturer"], p["model_number"])).casefold():
                continue
            if filters.quantity and not any(
                o["quantity"] == filters.quantity and o["unit"] == filters.unit
                and (not filters.statistic or o.get("statistic") == filters.statistic)
                and (filters.min_value is None or o["value"] >= filters.min_value)
                and (filters.max_value is None or o["value"] <= filters.max_value)
                for o in doc["observations"]
            ):
                continue
            output.append(entry)
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = build(args.root, args.revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(snapshot) + "\n")
    print(f"{len(snapshot['records'])} accepted records; release {snapshot['release']}")


if __name__ == "__main__":
    main()
