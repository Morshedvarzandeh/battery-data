#!/usr/bin/env python3
"""Validate the checked-in EPO patent/company review import."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "patents" / "imports" / "epo-linked-data-2026-09-04"
PUBLICATION = re.compile(r"^EP[0-9]+A[12]$")


def read_shards(directory: Path, errors: list[str]) -> list[dict]:
    paths = sorted(directory.glob("part-*.jsonl"))
    if not paths:
        errors.append(f"{directory}: no JSONL shards")
    rows = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                errors.append(f"{path}: line {number}: invalid JSON: {exc}")
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema_errors(document: dict, schema: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return [error.message for error in validator.iter_errors(document)]


def main() -> int:
    errors: list[str] = []
    manifest = json.loads((IMPORT / "manifest.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((ROOT / "patents" / "taxonomy.json").read_text(encoding="utf-8"))
    company_taxonomy = json.loads((ROOT / "patents" / "company-taxonomy.json").read_text(encoding="utf-8"))
    publication_schema = json.loads((ROOT / "json-schema" / "patent-publication.schema.json").read_text(encoding="utf-8"))
    company_schema = json.loads((ROOT / "json-schema" / "patent-company.schema.json").read_text(encoding="utf-8"))
    candidates = read_shards(IMPORT / "publication-candidates", errors)
    companies = read_shards(IMPORT / "companies", errors)
    links = read_shards(IMPORT / "publication-company-links", errors)

    for filename, spec in manifest["files"].items():
        path = IMPORT / filename
        if not path.is_file():
            errors.append(f"missing import file: {path}")
        elif sha256(path) != spec["sha256"]:
            errors.append(f"{path}: SHA-256 does not match manifest")

    counts = manifest["counts"]
    if len(candidates) != counts["new_publication_candidates"]:
        errors.append("publication candidate count does not match manifest")
    if len(candidates) < 200:
        errors.append("EPO expansion contains fewer than 200 new candidates")
    if len(companies) != counts["company_candidates"]:
        errors.append("company candidate count does not match manifest")
    if len(links) != counts["publication_company_links"]:
        errors.append("publication-company link count does not match manifest")

    existing = {
        json.loads(line)["publication_number"]
        for path in (ROOT / "patents" / "imports" / "cordis-2026-08-21" / "publication-candidates").glob("part-*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    }
    publication_numbers = set()
    publication_uids = set()
    source_records = []
    requested_categories = set()
    for row in candidates:
        uid = row.get("publication_uid", "")
        number = row.get("publication_number", "")
        if uid in publication_uids:
            errors.append(f"duplicate publication UID: {uid}")
        publication_uids.add(uid)
        if number in publication_numbers:
            errors.append(f"duplicate publication number: {number}")
        publication_numbers.add(number)
        if number in existing:
            errors.append(f"cross-import publication duplicate: {number}")
        if not PUBLICATION.fullmatch(number):
            errors.append(f"invalid EPO publication number: {number}")
        if row.get("review_state") != "pending_review":
            errors.append(f"{number}: crossed the human-review boundary")
        if (row.get("family") or {}).get("status") != "needs_docdb_resolution":
            errors.append(f"{number}: family asserted without DOCDB resolution")
        if (row.get("legal_status") or {}).get("status") != "unknown":
            errors.append(f"{number}: legal status asserted without dated evidence")
        if row.get("assignees"):
            errors.append(f"{number}: applicant data was represented as assignee data")
        classification = row.get("classification") or {}
        if classification.get("review_state") != "provisional":
            errors.append(f"{number}: technical classification is not provisional")
        if not set(classification.get("categories", [])) <= set(taxonomy["categories"]):
            errors.append(f"{number}: unknown technical category")
        requested_categories.update(classification.get("requested_categories", []))
        records = row.get("source_records") or []
        if len(records) != row.get("source_record_count"):
            errors.append(f"{number}: source record count mismatch")
        source_records.extend(records)
        for problem in schema_errors(row, publication_schema):
            errors.append(f"{number}: schema: {problem}")

    if requested_categories != {"electrical", "mechanical", "software", "hardware"}:
        errors.append(f"requested patent-domain coverage incomplete: {sorted(requested_categories)}")
    if len(source_records) != counts["raw_publication_observations"]:
        errors.append("source observation reconciliation failed")
    if len(source_records) != len(set(source_records)):
        errors.append("one EPO source record is assigned to multiple candidates")

    company_uids = set()
    company_by_uid = {}
    company_categories = set(company_taxonomy["categories"])
    for row in companies:
        uid = row.get("company_uid", "")
        if uid in company_uids:
            errors.append(f"duplicate company UID: {uid}")
        company_uids.add(uid)
        company_by_uid[uid] = row
        if row.get("review_state") != "pending_review":
            errors.append(f"{uid}: company crossed the human-review boundary")
        value_chain = row.get("value_chain") or {}
        if value_chain.get("review_state") != "provisional":
            errors.append(f"{uid}: company category is not provisional")
        if not set(value_chain.get("categories", [])) <= company_categories:
            errors.append(f"{uid}: unknown company category")
        if value_chain.get("primary_category") not in value_chain.get("categories", []):
            errors.append(f"{uid}: primary company category is not in categories")
        for problem in schema_errors(row, company_schema):
            errors.append(f"{uid}: schema: {problem}")

    links_by_company: dict[str, set[str]] = defaultdict(set)
    link_keys = set()
    for row in links:
        key = (row.get("publication_uid"), row.get("company_uid"), row.get("relation"), row.get("raw_name"))
        if key in link_keys:
            errors.append(f"duplicate publication-company link: {key}")
        link_keys.add(key)
        if row.get("publication_uid") not in publication_uids:
            errors.append(f"link references unknown publication: {row.get('publication_uid')}")
        if row.get("company_uid") not in company_uids:
            errors.append(f"link references unknown company: {row.get('company_uid')}")
        if row.get("review_state") != "pending_review":
            errors.append(f"link crossed review boundary: {key}")
        links_by_company[row.get("company_uid")].add(row.get("publication_number"))

    for uid, company in company_by_uid.items():
        declared = set(company["patent_portfolio"]["publication_numbers"])
        if declared != links_by_company[uid]:
            errors.append(f"{uid}: portfolio publication list does not match applicant links")
        if len(declared) != company["patent_portfolio"]["publication_count"]:
            errors.append(f"{uid}: portfolio publication count mismatch")

    duplicate_report = json.loads((IMPORT / "duplicate-report.json").read_text(encoding="utf-8"))
    if duplicate_report["cross_import_publication_duplicates_excluded"]:
        errors.append("cross-import publication duplicates were present in generated output")
    if duplicate_report["unique_publications_before_existing_filter"] != len(candidates):
        errors.append("duplicate report unique-publication count is stale")

    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    print(
        f"{len(candidates)} new publication candidate(s), {len(companies)} company candidate(s), "
        f"{len(links)} applicant link(s), {len(errors)} error(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
