#!/usr/bin/env python3
"""Promote exactly one owner-approved issue candidate into contrib/cells/."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = re.compile(r"<!--\s*battery-candidate:\s*(review/candidates/[a-z0-9._/-]+\.yaml)\s*-->")
APPROVAL = "- [x] Approve this battery for the accepted library"
ACCEPTED_TAIL = ("accepted_file", "issue_number", "issue_url")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", type=int, required=True)
    args = parser.parse_args()
    body = os.environ.get("ISSUE_BODY", "")
    if APPROVAL.lower() not in body.lower():
        raise SystemExit("approval checkbox is not checked")
    match = MARKER.search(body)
    if not match:
        raise SystemExit("candidate marker is missing")
    rel = match.group(1)
    source = (ROOT / rel).resolve()
    candidate_root = (ROOT / "review/candidates").resolve()
    if candidate_root not in source.parents or not source.is_file():
        raise SystemExit("candidate path is outside the review queue or missing")
    doc = json.loads(source.read_text())
    uid = doc["product"]["uid"]
    kind, maker, model = uid.split("/", 2)
    if kind not in {"cell", "module", "pack", "system", "primary_cell", "component"}:
        raise SystemExit("unsupported product kind")
    if not re.fullmatch(r"[a-z0-9-]+", maker) or not re.fullmatch(r"[a-z0-9._-]+", model):
        raise SystemExit("unsafe product uid")
    destination = ROOT / "contrib/cells" / maker / f"{model}.yaml"
    if destination.exists():
        raise SystemExit(f"accepted file already exists: {destination.relative_to(ROOT)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(source, destination)

    index_path = ROOT / "review/index.json"
    index = json.loads(index_path.read_text())
    found = False
    for position, item in enumerate(index["candidates"]):
        if item["candidate_file"] == rel:
            # tools/build_review_batch.py rebuilds an accepted entry with
            # accepted_file ahead of the issue keys, and CI diffs this file
            # against that builder's output. Assigning in place would append
            # accepted_file last and leave the index stale the moment it is
            # written, so the tail is rewritten in the builder's order.
            entry = {k: v for k, v in item.items() if k not in ACCEPTED_TAIL}
            entry["state"] = "accepted"
            entry["accepted_file"] = str(destination.relative_to(ROOT))
            entry["issue_number"] = args.issue
            entry["issue_url"] = item.get("issue_url")
            index["candidates"][position] = entry
            found = True
            break
    if not found:
        raise SystemExit("candidate is missing from review/index.json")
    index["candidate_count"] = sum(item["state"] == "pending_review" for item in index["candidates"])
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print(f"candidate_file={rel}")
    print(f"accepted_file={destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
