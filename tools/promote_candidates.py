#!/usr/bin/env python3
"""Promote review candidates into contrib/cells/ in bulk.

The one-at-a-time path is .github/scripts/promote_candidate.py, driven by the
owner ticking a box on each candidate's issue. This is the same move, made for
every pending candidate at once, when the owner has decided to accept the
queue wholesale rather than issue by issue. It is a decision, so it is never
run by CI and never by a workflow: someone runs it, reads the result and
commits it.

Every safety the single-candidate script applies is applied here: paths are
resolved inside review/candidates/, the uid must be well formed, an existing
accepted file is never overwritten, and review/index.json is rewritten in the
builder's key order so the deterministic rebuild produces no diff.

    python tools/promote_candidates.py --dry-run
    python tools/promote_candidates.py --all
    python tools/promote_candidates.py --uid cell/molicel/inr21700-p45b

After it, run the rest of the review pipeline so the checked-in artefacts
agree with the move:

    python tools/build_review_batch.py
    python tools/render_review_issues.py
    python tools/validate_review.py
    python tools/validate_contrib.py contrib/
    python tools/check_duplicates.py
    python tools/build_web_data.py
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "review/index.json"
CANDIDATES = (ROOT / "review/candidates").resolve()
KINDS = {"cell", "module", "pack", "system", "primary_cell", "component"}
ACCEPTED_TAIL = ("accepted_file", "issue_number", "issue_url")


def promote(item: dict, dry_run: bool) -> tuple[dict, str]:
    rel = item["candidate_file"]
    source = (ROOT / rel).resolve()
    if CANDIDATES not in source.parents:
        return item, f"refused: {rel} is outside the review queue"
    if not source.is_file():
        return item, f"skipped: {rel} has no file behind it (issue outlived its candidate)"
    doc = json.loads(source.read_text())
    uid = doc["product"]["uid"]
    kind, maker, model = uid.split("/", 2)
    if kind not in KINDS:
        return item, f"refused: {uid} has an unsupported kind"
    if not re.fullmatch(r"[a-z0-9-]+", maker) or not re.fullmatch(r"[a-z0-9._-]+", model):
        return item, f"refused: unsafe uid {uid}"
    destination = ROOT / "contrib/cells" / maker / f"{model}.yaml"
    if destination.exists():
        return item, f"skipped: {destination.relative_to(ROOT)} already exists"
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    entry = {k: v for k, v in item.items() if k not in ACCEPTED_TAIL}
    entry["state"] = "accepted"
    entry["accepted_file"] = str(destination.relative_to(ROOT))
    entry["issue_number"] = item.get("issue_number")
    entry["issue_url"] = item.get("issue_url")
    return entry, f"accepted: {uid} -> {entry['accepted_file']}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="every pending candidate")
    g.add_argument("--uid", action="append", help="one product uid; repeatable")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    index = json.loads(INDEX.read_text())
    wanted = set(a.uid or [])
    moved, skipped = 0, 0
    for position, item in enumerate(index["candidates"]):
        if item["state"] != "pending_review":
            continue
        if not a.all and item["uid"] not in wanted:
            continue
        entry, message = promote(item, a.dry_run)
        print("  " + message)
        if message.startswith("accepted"):
            index["candidates"][position] = entry
            moved += 1
        else:
            skipped += 1
    index["candidate_count"] = sum(i["state"] == "pending_review" for i in index["candidates"])
    if not a.dry_run:
        INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print(f"\n{moved} promoted, {skipped} skipped, {index['candidate_count']} still pending"
          + (" (dry run, nothing written)" if a.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
