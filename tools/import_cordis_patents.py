#!/usr/bin/env python3
"""Import the CORDIS PATENT_IP snapshot into an immutable review dataset.

The CORDIS result label is deliberately not treated as proof that a row is a
patent. Only rows with an official patent-search URL and a parseable publication
number become publication candidates. Every source row is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY = ROOT / "patents" / "taxonomy.json"
SCHEMA_VERSION = "1.0.0"
SOURCE_SHEET = "Deliverables & Other"
SOURCE_WORKBOOK = "EU_CORDIS_Battery_Projects_Public_Results_2026-08-21.xlsx"
SNAPSHOT_DATE = "2026-08-21"


def compact(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normal_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def phrase_present(text: str, phrase: str) -> bool:
    needle = normal_text(phrase)
    return bool(needle and re.search(r"(?:^| )" + re.escape(needle) + r"(?: |$)", text))


def publication_from_url(url: str) -> str | None:
    if "espacenet" not in url.casefold():
        return None
    values = parse_qs(urlparse(url).query).get("q", [])
    if not values:
        return None
    candidate = re.sub(r"[^A-Za-z0-9]", "", values[0]).upper()
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{6,}", candidate):
        return candidate
    return None


def classification(title: str, summary: str, battery_domains: list[str], taxonomy: dict) -> dict:
    text = normal_text(" ".join([title, summary, " ".join(battery_domains)]))
    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}
    for code, spec in taxonomy["categories"].items():
        found = [kw for kw in spec.get("keywords", []) if phrase_present(text, kw)]
        if found:
            scores[code] = len(found)
            matches[code] = found
    priority = {code: index for index, code in enumerate(taxonomy["primary_priority"])}
    primary = None
    if scores:
        primary = sorted(scores, key=lambda code: (-scores[code], priority.get(code, 999), code))[0]
    requested = sorted({
        taxonomy["categories"][code]["requested_category"]
        for code in scores
        if taxonomy["categories"][code].get("requested_category")
    })
    confidence = None
    if primary:
        confidence = round(min(0.95, 0.45 + 0.1 * scores[primary]), 2)
    return {
        "taxonomy_version": taxonomy["version"],
        "primary_category": primary,
        "categories": sorted(scores),
        "requested_categories": requested,
        "keyword_scores": scores,
        "matched_terms": matches,
        "confidence": confidence,
        "review_state": "provisional"
    }


def row_digest(row: dict[str, str]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def source_result_key(record: dict) -> str:
    return f"{record['project']['grant_id']}::{record['result']['id']}"


def build_record(row: dict[str, str], source_row: int, taxonomy: dict) -> dict:
    title = compact(row.get("Result Title"))
    summary = compact(row.get("Description / Summary"))
    direct_url = compact(row.get("Direct URL"))
    publication = publication_from_url(direct_url)
    domains = [item.strip() for item in compact(row.get("Battery Domains")).split(";") if item.strip()]
    raw = {key: compact(value) for key, value in row.items()}
    digest = row_digest(raw)
    obvious_markers = [
        item for item in taxonomy["obvious_non_patent_title_markers"]
        if phrase_present(normal_text(title), item)
    ]
    identity = {
        "status": "verified_publication" if publication else "source_label_only",
        "publication_number": publication,
        "family_status": "needs_docdb_resolution" if publication else "not_applicable",
        "evidence": ["official_espacenet_search_url"] if publication else ["cordis_patent_ip_source_label"],
        "obvious_non_patent_title": bool(obvious_markers) and not publication,
        "obvious_non_patent_markers": obvious_markers
    }
    result_id = compact(row.get("Result ID")) or "no-result-id"
    project_id = compact(row.get("Project ID")) or "no-project-id"
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "cordis_patent_ip_observation",
        "observation_uid": f"cordis/{project_id}/{result_id}/{digest[:12]}",
        "source_row": source_row,
        "project": {
            "grant_id": project_id,
            "acronym": compact(row.get("Acronym")),
            "framework": compact(row.get("Framework / Programme"))
        },
        "result": {
            "id": result_id,
            "type": "PATENT_IP",
            "title": title,
            "summary": summary,
            "type_detail": compact(row.get("Result Type Detail")),
            "authors": compact(row.get("Authors")),
            "published_year": compact(row.get("Published Year")),
            "venue": compact(row.get("Venue / Publisher Details")),
            "doi": compact(row.get("DOI")),
            "reporting_narrative": compact(row.get("Reporting / Final Narrative")),
            "content_update_date": compact(row.get("Content Update Date")),
            "content_truncated": compact(row.get("Content Truncated"))
        },
        "battery_relevance": compact(row.get("Battery Relevance")),
        "battery_domains": domains,
        "availability": {
            "class": compact(row.get("Availability")),
            "note": compact(row.get("Availability Note")),
            "direct_url": direct_url
        },
        "source": {
            "system": compact(row.get("Source")),
            "url": compact(row.get("Source URL")),
            "workbook": SOURCE_WORKBOOK,
            "sheet": SOURCE_SHEET,
            "snapshot_date": SNAPSHOT_DATE,
            "row_sha256": digest
        },
        "patent_identity": identity,
        "classification": classification(title, summary, domains, taxonomy),
        "review_state": "pending_review"
    }


def candidate_from_group(publication: str, rows: list[dict], taxonomy: dict) -> dict:
    def quality(row: dict) -> tuple:
        return (
            row["battery_relevance"] == "DIRECT_BATTERY_RESULT",
            len(row["classification"]["categories"]),
            len(row["result"]["title"])
        )

    canonical = max(rows, key=quality)
    score_totals: dict[str, int] = defaultdict(int)
    for row in rows:
        for code, score in row["classification"]["keyword_scores"].items():
            score_totals[code] += score
    priority = {code: index for index, code in enumerate(taxonomy["primary_priority"])}
    primary = None
    if score_totals:
        primary = sorted(score_totals, key=lambda code: (-score_totals[code], priority.get(code, 999), code))[0]
    categories = sorted(score_totals)
    requested = sorted({
        taxonomy["categories"][code]["requested_category"]
        for code in categories
        if taxonomy["categories"][code].get("requested_category")
    })
    projects = sorted({
        (row["project"]["grant_id"], row["project"]["acronym"], row["project"]["framework"])
        for row in rows
    })
    flags = ["needs_docdb_family", "needs_claims_review", "legal_status_unverified"]
    if not any(row["battery_relevance"] == "DIRECT_BATTERY_RESULT" for row in rows):
        flags.append("battery_relation_unverified")
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "patent_publication_candidate",
        "publication_uid": f"patent-publication/{publication.casefold()}",
        "publication_number": publication,
        "publication_url": canonical["availability"]["direct_url"],
        "title": canonical["result"]["title"],
        "title_variants": sorted({row["result"]["title"] for row in rows if row["result"]["title"]}),
        "source_observation_ids": sorted(row["observation_uid"] for row in rows),
        "source_record_count": len(rows),
        "projects": [
            {"grant_id": grant, "acronym": acronym, "framework": framework}
            for grant, acronym, framework in projects
        ],
        "battery_relevance": (
            "DIRECT_BATTERY_RESULT"
            if any(row["battery_relevance"] == "DIRECT_BATTERY_RESULT" for row in rows)
            else "RESULT_FROM_BATTERY_PROJECT"
        ),
        "classification": {
            "taxonomy_version": taxonomy["version"],
            "primary_category": primary,
            "categories": categories,
            "requested_categories": requested,
            "keyword_scores": dict(sorted(score_totals.items())),
            "review_state": "provisional"
        },
        "family": {"docdb_family_id": None, "status": "needs_docdb_resolution"},
        "legal_status": {"status": "unknown", "jurisdiction": None, "as_of": None},
        "review_flags": flags,
        "review_state": "pending_review"
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_jsonl_shards(directory: Path, records: list[dict], shard_size: int) -> list[tuple[Path, int]]:
    directory.mkdir(parents=True, exist_ok=True)
    for existing in directory.glob("part-*.jsonl"):
        existing.unlink()
    shards = []
    for offset in range(0, len(records), shard_size):
        part = records[offset:offset + shard_size]
        path = directory / f"part-{offset // shard_size + 1:04d}.jsonl"
        write_jsonl(path, part)
        shards.append((path, len(part)))
    return shards


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_report(records: list[dict], candidates: list[dict]) -> dict:
    by_source: dict[str, list[dict]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_source[source_result_key(record)].append(record)
        title_key = normal_text(record["result"]["title"])
        if title_key:
            by_title[title_key].append(record["observation_uid"])
    publication_groups = [item for item in candidates if item["source_record_count"] > 1]
    return {
        "source_observation_count": len(records),
        "unique_observation_uid_count": len({row["observation_uid"] for row in records}),
        "source_result_collision_groups": [
            {
                "source_result_key": key,
                "observation_ids": sorted(row["observation_uid"] for row in rows),
                "publication_numbers": sorted({row["patent_identity"]["publication_number"] for row in rows if row["patent_identity"]["publication_number"]})
            }
            for key, rows in sorted(by_source.items()) if len(rows) > 1
        ],
        "exact_publication_duplicate_groups": [
            {
                "publication_number": item["publication_number"],
                "source_record_count": item["source_record_count"],
                "observation_ids": item["source_observation_ids"]
            }
            for item in publication_groups
        ],
        "normalized_title_collision_groups": sum(1 for rows in by_title.values() if len(rows) > 1),
        "family_duplicate_status": "not_computed_until_docdb_family_resolution"
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas and an XLSX engine are required for this one-time source import") from exc

    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    frame = pd.read_excel(args.workbook, sheet_name=SOURCE_SHEET, dtype=str).fillna("")
    frame = frame[frame["Result Type"].eq("PATENT_IP")]
    records = [
        build_record({key: compact(value) for key, value in row.items()}, int(index) + 2, taxonomy)
        for index, row in frame.iterrows()
    ]
    records.sort(key=lambda row: (source_result_key(row), row["observation_uid"]))

    publication_rows: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        publication = record["patent_identity"]["publication_number"]
        if publication:
            publication_rows[publication].append(record)
    candidates = [candidate_from_group(number, rows, taxonomy) for number, rows in sorted(publication_rows.items())]

    args.output.mkdir(parents=True, exist_ok=True)
    for legacy in (args.output / "source-observations.jsonl", args.output / "publication-candidates.jsonl"):
        if legacy.exists():
            legacy.unlink()
    raw_shards = write_jsonl_shards(args.output / "source-observations", records, 75)
    candidate_shards = write_jsonl_shards(args.output / "publication-candidates", candidates, 85)
    duplicate_path = args.output / "duplicate-report.json"
    duplicate_path.write_text(
        json.dumps(duplicate_report(records, candidates), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    requested_counts = defaultdict(int)
    primary_counts = defaultdict(int)
    for item in candidates:
        primary_counts[item["classification"]["primary_category"] or "unclassified"] += 1
        for category in item["classification"]["requested_categories"]:
            requested_counts[category] += 1
    source_requested_counts = defaultdict(int)
    source_primary_counts = defaultdict(int)
    for item in records:
        source_primary_counts[item["classification"]["primary_category"] or "unclassified"] += 1
        for category in item["classification"]["requested_categories"]:
            source_requested_counts[category] += 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "import_id": "cordis-patent-ip-2026-08-21",
        "created_at": "2026-08-25",
        "source": {
            "workbook": SOURCE_WORKBOOK,
            "workbook_sha256": sha256(args.workbook),
            "workbook_size_bytes": args.workbook.stat().st_size,
            "sheet": SOURCE_SHEET,
            "snapshot_date": SNAPSHOT_DATE,
            "official_landing_url": "https://cordis.europa.eu/projects"
        },
        "counts": {
            "source_rows": len(records),
            "verified_publication_rows": sum(row["patent_identity"]["status"] == "verified_publication" for row in records),
            "source_label_only_rows": sum(row["patent_identity"]["status"] == "source_label_only" for row in records),
            "obvious_non_patent_title_rows": sum(row["patent_identity"]["obvious_non_patent_title"] for row in records),
            "unique_publication_candidates": len(candidates),
            "collapsed_duplicate_publication_rows": sum(item["source_record_count"] - 1 for item in candidates),
            "direct_battery_publication_candidates": sum(item["battery_relevance"] == "DIRECT_BATTERY_RESULT" for item in candidates)
        },
        "classification": {
            "taxonomy_version": taxonomy["version"],
            "source_primary_category_counts": dict(sorted(source_primary_counts.items())),
            "source_requested_category_counts": dict(sorted(source_requested_counts.items())),
            "publication_primary_category_counts": dict(sorted(primary_counts.items())),
            "publication_requested_category_counts": dict(sorted(requested_counts.items())),
            "labels_are_provisional": True
        },
        "files": {
            **{
                str(path.relative_to(args.output)): {"sha256": sha256(path), "records": count}
                for path, count in raw_shards + candidate_shards
            },
            duplicate_path.name: {"sha256": sha256(duplicate_path)}
        },
        "acceptance_boundary": {
            "raw_rows_are_accepted_patents": False,
            "publication_candidates_are_accepted_patent_families": False,
            "requires_human_review": True,
            "requires_docdb_family_resolution": True,
            "legal_status_is_not_freedom_to_operate_advice": True
        }
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
