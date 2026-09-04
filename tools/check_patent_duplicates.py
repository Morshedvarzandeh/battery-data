#!/usr/bin/env python3
"""Report duplicate and collision signals in the patent review import."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "patents" / "imports" / "cordis-2026-08-21"
sys.path.insert(0, str(ROOT / "tools"))
from import_cordis_patents import duplicate_report  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_shards(directory: Path) -> list[dict]:
    return [row for path in sorted(directory.glob("part-*.jsonl")) for row in read_jsonl(path)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--fail-on", choices=("exact", "review", "never"), default="exact")
    args = parser.parse_args()

    observations = read_shards(IMPORT / "source-observations")
    candidates = read_shards(IMPORT / "publication-candidates")
    actual = duplicate_report(observations, candidates)
    expected = json.loads((IMPORT / "duplicate-report.json").read_text(encoding="utf-8"))

    by_publication: dict[str, list[str]] = {}
    for path in sorted((ROOT / "patents" / "imports").glob("*/publication-candidates/part-*.jsonl")):
        import_id = path.parents[1].name
        for row in read_jsonl(path):
            by_publication.setdefault(row["publication_number"], []).append(import_id)
    cross_import_duplicates = {
        publication: imports
        for publication, imports in by_publication.items()
        if len(set(imports)) > 1
    }

    exact_errors = []
    if actual["unique_observation_uid_count"] != actual["source_observation_count"]:
        exact_errors.append("duplicate observation UID")
    if len({row["publication_number"] for row in candidates}) != len(candidates):
        exact_errors.append("duplicate canonical publication number")
    if actual != expected:
        exact_errors.append("checked-in duplicate report is stale")
    if cross_import_duplicates:
        exact_errors.append(
            f"{len(cross_import_duplicates)} publication number(s) occur in multiple imports"
        )

    if args.format == "json":
        print(json.dumps({"report": actual, "exact_errors": exact_errors}, indent=2, sort_keys=True))
    else:
        print(f"{actual['source_observation_count']} source observation(s) scanned")
        print(f"{len(candidates)} canonical publication candidate(s)")
        print(f"{len(by_publication)} publication candidate(s) across all imports")
        print(f"{len(cross_import_duplicates)} cross-import publication duplicate(s)")
        print(f"{len(actual['exact_publication_duplicate_groups'])} exact publication group(s) collapsed")
        print(f"{len(actual['source_result_collision_groups'])} source-result collision group(s) retained for review")
        print(f"{actual['normalized_title_collision_groups']} normalized-title collision group(s)")
        print("family duplicates: pending DOCDB family resolution")
        for error in exact_errors:
            print(f"FAIL {error}", file=sys.stderr)

    if args.fail_on == "never":
        return 0
    if exact_errors:
        return 1
    if args.fail_on == "review" and (
        actual["source_result_collision_groups"]
        or actual["normalized_title_collision_groups"]
        or candidates
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
