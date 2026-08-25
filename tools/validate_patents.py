#!/usr/bin/env python3
"""Dependency-free validation of the checked-in patent import."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "patents" / "imports" / "cordis-2026-08-21"
PUBLICATION = re.compile(r"^[A-Z]{2}[A-Z0-9]{6,}$")


def read_jsonl(path: Path, errors: list[str]) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            errors.append(f"{path}: line {number}: invalid JSON: {exc}")
    return rows


def read_shards(directory: Path, errors: list[str]) -> list[dict]:
    paths = sorted(directory.glob("part-*.jsonl"))
    if not paths:
        errors.append(f"{directory}: no JSONL shards")
    return [row for path in paths for row in read_jsonl(path, errors)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    manifest = json.loads((IMPORT / "manifest.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((ROOT / "patents" / "taxonomy.json").read_text(encoding="utf-8"))
    observations = read_shards(IMPORT / "source-observations", errors)
    candidates = read_shards(IMPORT / "publication-candidates", errors)
    category_codes = set(taxonomy["categories"])
    requested_codes = set(taxonomy["requested_categories"])

    for filename, spec in manifest["files"].items():
        path = IMPORT / filename
        if not path.is_file():
            errors.append(f"missing import file: {path}")
        elif sha256(path) != spec["sha256"]:
            errors.append(f"{path}: SHA-256 does not match manifest")

    expected = manifest["counts"]
    if len(observations) != expected["source_rows"]:
        errors.append("source row count does not match manifest")
    if len(candidates) != expected["unique_publication_candidates"]:
        errors.append("publication candidate count does not match manifest")

    observation_ids: set[str] = set()
    verified_rows = 0
    for row in observations:
        uid = row.get("observation_uid", "")
        if uid in observation_ids:
            errors.append(f"duplicate observation UID: {uid}")
        observation_ids.add(uid)
        if row.get("record_type") != "cordis_patent_ip_observation":
            errors.append(f"{uid}: wrong record_type")
        if (row.get("result") or {}).get("type") != "PATENT_IP":
            errors.append(f"{uid}: source result type is not PATENT_IP")
        if row.get("review_state") != "pending_review":
            errors.append(f"{uid}: raw import crossed the review boundary")
        identity = row.get("patent_identity") or {}
        publication = identity.get("publication_number")
        if identity.get("status") == "verified_publication":
            verified_rows += 1
            if not isinstance(publication, str) or not PUBLICATION.fullmatch(publication):
                errors.append(f"{uid}: verified publication has no valid publication number")
            if "official_espacenet_search_url" not in identity.get("evidence", []):
                errors.append(f"{uid}: verified publication lacks office-search evidence")
        elif identity.get("status") == "source_label_only":
            if publication is not None:
                errors.append(f"{uid}: source-label-only row carries a publication number")
        else:
            errors.append(f"{uid}: invalid patent identity state")
        classification = row.get("classification") or {}
        if classification.get("taxonomy_version") != taxonomy["version"]:
            errors.append(f"{uid}: taxonomy version mismatch")
        if not set(classification.get("categories", [])) <= category_codes:
            errors.append(f"{uid}: unknown category code")
        if not set(classification.get("requested_categories", [])) <= requested_codes:
            errors.append(f"{uid}: unknown requested category")

    publication_numbers: set[str] = set()
    publication_uids: set[str] = set()
    referenced_observations: list[str] = []
    for row in candidates:
        uid = row.get("publication_uid", "")
        publication = row.get("publication_number", "")
        if uid in publication_uids:
            errors.append(f"duplicate publication UID: {uid}")
        publication_uids.add(uid)
        if publication in publication_numbers:
            errors.append(f"duplicate publication candidate: {publication}")
        publication_numbers.add(publication)
        if not PUBLICATION.fullmatch(publication):
            errors.append(f"{uid}: invalid publication number")
        source_ids = row.get("source_observation_ids") or []
        if len(source_ids) != row.get("source_record_count"):
            errors.append(f"{uid}: source_record_count mismatch")
        for source_id in source_ids:
            referenced_observations.append(source_id)
            if source_id not in observation_ids:
                errors.append(f"{uid}: unknown source observation {source_id}")
        if (row.get("family") or {}).get("status") != "needs_docdb_resolution":
            errors.append(f"{uid}: family was asserted without DOCDB resolution")
        if (row.get("legal_status") or {}).get("status") != "unknown":
            errors.append(f"{uid}: legal status was asserted without dated evidence")
        if row.get("review_state") != "pending_review":
            errors.append(f"{uid}: candidate crossed the review boundary")
        classification = row.get("classification") or {}
        if not set(classification.get("categories", [])) <= category_codes:
            errors.append(f"{uid}: unknown category code")

    if verified_rows != expected["verified_publication_rows"]:
        errors.append("verified publication row count does not match manifest")
    if len(referenced_observations) != verified_rows:
        errors.append("publication candidates do not preserve every verified source row")
    if len(referenced_observations) - len(set(referenced_observations)):
        errors.append("a source observation is referenced by multiple publication candidates")

    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    print(
        f"{len(observations)} source row(s), {verified_rows} verified publication row(s), "
        f"{len(candidates)} unique publication candidate(s), {len(errors)} error(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
