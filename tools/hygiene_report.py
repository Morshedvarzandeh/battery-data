#!/usr/bin/env python3
"""Source hygiene: which accepted records rest on what, and what to re-extract.

Every record in the library is source-backed, and not every source is a
datasheet. Some were rebuilt from the text of their review issue and carry
no page numbers or statistic labels; most came from a maker's web page rather
than the specification PDF; few carry a document hash or date. None of that
is hidden in the files, but nobody can act on it file by file. This report
puts it in one place and turns it into the list of re-extractions to run
from a machine that can reach the sources.

    python tools/hygiene_report.py            # writes review/hygiene.json
    python tools/hygiene_report.py --check    # CI: the report is current

review/hygiene.json carries a per-record row and a manifest: for each record
that needs its document, the command that re-extracts it through
tools/extract_datasheet.py. Running that needs the network and an API key,
which is why the manifest is a file and not a workflow step.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "review", "hygiene.json")

CAPACITY_CONDITIONS = ("rate_value", "rate_unit", "temperature_c", "voltage_lower_v")


def row(path: str, doc: dict) -> dict:
    p, s = doc["product"], doc.get("source") or {}
    obs = doc.get("observations") or []
    note = s.get("note") or ""
    unstated = sum(len((o.get("conditions") or {}).get("unstated") or []) for o in obs)
    flags = []
    if note.startswith("Recovered from the review issue"):
        flags.append("rebuilt_from_issue")
    if note.startswith("Ported from seed"):
        flags.append("table_level_quotes")
    if s.get("kind") not in ("datasheet", "journal_article", "third_party_test", "dataset"):
        flags.append("not_a_datasheet")
    if not s.get("sha256"):
        flags.append("no_document_hash")
    if not s.get("document_date"):
        flags.append("no_document_date")
    if not s.get("revision"):
        flags.append("no_revision")
    if sum(1 for o in obs if not o.get("statistic")):
        flags.append("statistic_missing")
    if sum(1 for o in obs if (o.get("locator") or {}).get("page") is None):
        flags.append("page_missing")
    caps = [o for o in obs if o["quantity"] == "capacity"]
    if caps and all(any(c in ((o.get("conditions") or {}).get("unstated") or [])
                        for c in CAPACITY_CONDITIONS) for o in caps):
        flags.append("capacity_conditions_unstated")
    if not (doc.get("chemistry") or {}).get("designation") and p["kind"] != "component":
        flags.append("no_chemistry")
    if not p.get("form_factor") and p["kind"] in ("cell", "primary_cell"):
        flags.append("no_form_factor")
    return {
        "uid": p["uid"], "kind": p["kind"], "manufacturer": p["manufacturer"],
        "model_number": p["model_number"], "file": os.path.relpath(path, ROOT),
        "source_kind": s.get("kind"), "source_url": s.get("url"),
        "observations": len(obs), "unstated_conditions": unstated,
        "statistic_missing": sum(1 for o in obs if not o.get("statistic")),
        "page_missing": sum(1 for o in obs if (o.get("locator") or {}).get("page") is None),
        "flags": flags,
    }


def command(r: dict) -> str:
    kind = {"primary_cell": "primary_cell", "cell": "cell", "module": "module",
            "pack": "pack", "system": "system", "component": "component"}[r["kind"]]
    return (f"python tools/extract_datasheet.py --pdf '{r['source_url']}' "
            f"--manufacturer '{r['manufacturer']}' --model '{r['model_number']}' --kind {kind} "
            f"--out '{r['file']}'")


def build() -> dict:
    files = sorted(glob.glob(os.path.join(ROOT, "contrib", "cells", "**", "*.y*ml"), recursive=True))
    rows = [row(f, yaml.safe_load(open(f, encoding="utf-8"))) for f in files]
    rows.sort(key=lambda r: r["uid"])
    needs = [r for r in rows if {"rebuilt_from_issue", "not_a_datasheet", "table_level_quotes",
                                 "capacity_conditions_unstated"} & set(r["flags"])]
    totals = {}
    for r in rows:
        for f in r["flags"]:
            totals[f] = totals.get(f, 0) + 1
    return {
        "generated_from": f"{len(rows)} accepted records",
        "totals": dict(sorted(totals.items())),
        "records": rows,
        "reextraction_manifest": {
            "why": ("Each record here rests on a web page, on issue text, on table-level "
                    "quotes, or states a capacity without its conditions. Re-extracting from "
                    "the specification document restores per-value quotes, page numbers, "
                    "statistic labels and the conditions. It needs the network and an "
                    "Anthropic API key, so it runs from a machine that has both, one command "
                    "per record, and each result goes through the review flow."),
            "count": len(needs),
            "commands": [{"uid": r["uid"], "flags": r["flags"], "run": command(r)} for r in needs],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    body = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if a.check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != body:
            print("review/hygiene.json is stale. Run: python tools/hygiene_report.py", file=sys.stderr)
            return 1
        print("review/hygiene.json is up to date")
        return 0
    open(OUT, "w", encoding="utf-8").write(body)
    report = json.loads(body)
    print(f"  {report['generated_from']}; re-extraction manifest: {report['reextraction_manifest']['count']} records")
    for k, v in report["totals"].items():
        print(f"    {k:32} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
