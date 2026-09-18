#!/usr/bin/env python3
"""Export a deterministic read snapshot of the accepted library.

The snapshot is derived from contrib/ alone: review/, seed/ and patent
candidates never enter it. It is the file Lemonergy's hosted Data API is
built from, and the same file anyone can build locally to check what that
API serves. Every record keeps its values, units, conditions, bounds, source
and locator; nothing is summarised here.

    python tools/export_catalog_snapshot.py --output build/catalog.json

Each record is validated with the contribution schema and the quantity
registry first (tools/validate_contrib.py). One invalid file refuses the
whole export: a snapshot that silently dropped a record would look complete
and be wrong. The export also refuses a dirty contrib/ tree, so the recorded
revision is the commit the records actually came from.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_contrib import REGISTRY, SCHEMA, check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Morshedvarzandeh/battery-data"
FORMAT_VERSION = 1
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_record(path: Path):
    raw = path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return yaml.safe_load(raw)


def git_revision(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError("not a Git checkout; pass --revision explicitly")
    return result.stdout.strip()


def contrib_is_dirty(root: Path) -> bool:
    result = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "contrib"],
                            capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def build(root: Path, revision: str, *, schema: dict | None = None,
          registry: dict | None = None) -> dict:
    """Validate every accepted record and return the snapshot document."""
    if not SHA_PATTERN.fullmatch(revision or ""):
        raise ValueError("revision must be the full 40-character Git commit SHA of the checkout")
    contrib = (root / "contrib").resolve()
    if not contrib.is_dir():
        raise ValueError(f"no contrib/ directory under {root}")
    if schema is None:
        schema = json.load(open(SCHEMA))
    if registry is None:
        registry = json.load(open(REGISTRY))
    validator = jsonschema.Draft202012Validator(schema)

    records, seen, errors = [], {}, []
    for path in sorted(contrib.rglob("*.y*ml")):
        if path.is_symlink() or not path.resolve().is_relative_to(contrib):
            raise ValueError(f"{path}: contributions must be regular files inside contrib/")
        file_errors = check(str(path), schema, registry, validator=validator)
        if file_errors:
            errors.extend(file_errors)
            continue
        doc = load_record(path)
        uid = doc["product"]["uid"]
        relative = path.relative_to(root).as_posix()
        if uid in seen:
            errors.append(f"{relative}: duplicate product UID {uid} (also in {seen[uid]})")
            continue
        seen[uid] = relative
        # Approval is the promotion into contrib/; nothing else is scanned.
        records.append({"file": relative, "record": doc})
    if errors:
        raise ValueError("\n".join(errors))
    if not records:
        raise ValueError("refusing an empty accepted catalog")

    records.sort(key=lambda entry: entry["record"]["product"]["uid"])
    content = {
        "format_version": FORMAT_VERSION,
        "repository": REPOSITORY,
        "source_revision": revision,
        "counts": {
            "products": len(records),
            "observations": sum(len(entry["record"]["observations"]) for entry in records),
            "by_kind": dict(sorted(Counter(entry["record"]["product"]["kind"] for entry in records).items())),
        },
        "records": records,
    }
    return {**content, "release": digest(content)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="battery-data checkout to export (default: this repository)")
    parser.add_argument("--revision",
                        help="full commit SHA the records come from (default: git rev-parse HEAD)")
    parser.add_argument("--output", type=Path, required=True, help="where to write catalog.json")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="export even if contrib/ has uncommitted changes (local checks only)")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        revision = args.revision or git_revision(root)
        if not args.allow_dirty and contrib_is_dirty(root):
            raise ValueError("contrib/ has uncommitted changes; commit them or pass --allow-dirty")
        snapshot = build(root, revision)
    except ValueError as error:
        print(f"export refused:\n{error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical(snapshot) + "\n")
    counts = snapshot["counts"]
    print(f"{counts['products']} accepted records, {counts['observations']} observations; "
          f"release {snapshot['release']}; revision {revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
