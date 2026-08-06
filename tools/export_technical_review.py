#!/usr/bin/env python3
"""Export the protected technical workspace snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    index = json.loads((ROOT / "review/index.json").read_text())
    candidates = []
    for item in index["candidates"]:
        if item["state"] != "pending_review":
            continue
        doc = json.loads((ROOT / item["candidate_file"]).read_text())
        candidates.append({**item, **doc})
    test_families = json.loads((ROOT / "web/data/test-families.json").read_text())
    payload = {
        "schema_version": 1,
        "generated_from": index["batch"],
        "review_state": "pending_review",
        "stats": {
            "candidates": len(candidates),
            "candidate_observations": sum(len(item["observations"]) for item in candidates),
            "candidate_sources": len({item["source"]["uid"] for item in candidates}),
            "test_families": sum(len(values) for values in test_families["FAM"].values()),
            "accepted_hppc_datasets": 0,
        },
        "candidates": candidates,
        "test_families": test_families,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(candidates)} candidates to {out}")


if __name__ == "__main__":
    main()
