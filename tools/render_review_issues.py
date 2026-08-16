#!/usr/bin/env python3
"""Render one human-reviewable GitHub issue payload per candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def conditions_text(value):
    conditions = dict(value or {})
    unstated = conditions.pop("unstated", [])
    parts = [f"{key}={val}" for key, val in conditions.items() if key != "extra"]
    if unstated:
        parts.append("not stated: " + ", ".join(unstated))
    return "; ".join(parts) or "not required"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--unmapped-only", action="store_true",
        help="render only pending candidates that do not yet have an issue number",
    )
    parser.add_argument(
        "--out", default="review/issues.json",
        help="output path, relative to the repository root unless absolute",
    )
    args = parser.parse_args()
    index = json.loads((ROOT / "review/index.json").read_text())
    payloads = []
    for item in index["candidates"]:
        if item["state"] != "pending_review":
            continue
        if args.unmapped_only and item.get("issue_number"):
            continue
        path = ROOT / item["candidate_file"]
        doc = json.loads(path.read_text())
        product, source = doc["product"], doc["source"]
        rows = []
        for observation in doc["observations"]:
            quote = observation["locator"]["quote"].replace("|", "\\|")
            rows.append(
                f"| `{observation['quantity']}` | {observation['value']} {observation['unit']} | "
                f"{conditions_text(observation.get('conditions'))} | {quote} |"
            )
        body = "\n".join([
            f"## {product['manufacturer']} {product['model_number']}",
            "",
            f"**Product type:** `{product['kind']}`  ",
            f"**Candidate file:** `{item['candidate_file']}`  ",
            f"**Source:** [{source.get('title', source['uid'])}]({source.get('url', '')})  ",
            f"**Source revision/date:** {source.get('revision') or source.get('document_date') or 'not stated'}",
            "",
            "| Quantity | Value | Conditions | Source locator excerpt |",
            "|---|---:|---|---|",
            *rows,
            "",
            "## Decision",
            "",
            "Check the box only after the values, units, conditions, and excerpts are correct.",
            "",
            "- [ ] Approve this battery for the accepted library",
            "",
            "If something is wrong, leave the box empty and comment with the correction.",
            "The candidate remains outside the accepted customer catalog until approval.",
            "The candidate-promotion workflow must be present on the default branch before this checkbox can accept data.",
            "",
            f"<!-- battery-candidate: {item['candidate_file']} -->",
            f"<!-- battery-uid: {product['uid']} -->",
        ])
        payloads.append({
            "title": f"[candidate] {product['manufacturer']} {product['model_number']}",
            "body": body,
            "candidate_file": item["candidate_file"],
            "uid": product["uid"],
        })
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payloads, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(payloads)} issue payloads")


if __name__ == "__main__":
    main()
