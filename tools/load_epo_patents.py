#!/usr/bin/env python3
"""Load the checked-in EPO patent/company review batch into bd_stage only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT = ROOT / "patents" / "imports" / "epo-linked-data-2026-09-04"


def read_shards(directory: Path) -> list[dict]:
    return [
        json.loads(line)
        for path in sorted(directory.glob("part-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--input", type=Path, default=DEFAULT_IMPORT)
    args = parser.parse_args()

    try:
        import psycopg2
        from psycopg2.extras import Json, execute_values
    except ImportError as exc:
        raise SystemExit("psycopg2 is required to load the patent staging tables") from exc

    manifest_path = args.input / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = read_shards(args.input / "publication-candidates")
    companies = read_shards(args.input / "companies")
    links = read_shards(args.input / "publication-company-links")
    source_bytes = sum((args.input / name).stat().st_size for name in manifest["files"] if name.startswith("source/"))
    source_uid = "source/epo-linked-data-battery-patents-2026-09-04"
    job_uid = "ingest/epo-linked-data-battery-patents-2026-09-04"

    with psycopg2.connect(args.dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO bd.source
              (uid, kind, title, url, retrieved_at, retrieved_from, content_sha256,
               media_type, byte_size, license, license_url, redistributable, raw_metadata)
            VALUES (%s, 'dataset', %s, %s, %s::timestamptz, %s, %s, %s, %s,
                    %s, %s, true, %s)
            ON CONFLICT (uid) DO UPDATE SET
              title=EXCLUDED.title, url=EXCLUDED.url, retrieved_at=EXCLUDED.retrieved_at,
              retrieved_from=EXCLUDED.retrieved_from, content_sha256=EXCLUDED.content_sha256,
              media_type=EXCLUDED.media_type, byte_size=EXCLUDED.byte_size,
              license=EXCLUDED.license, license_url=EXCLUDED.license_url,
              redistributable=EXCLUDED.redistributable, raw_metadata=EXCLUDED.raw_metadata,
              updated_at=now()
            RETURNING id
            """,
            (
                source_uid,
                "EPO Linked Open EP Data battery-patent query snapshot",
                manifest["source"]["landing_url"],
                manifest["source"]["snapshot_date"],
                manifest["source"]["endpoint"],
                sha256(manifest_path),
                "application/sparql-results+json",
                source_bytes,
                manifest["source"]["license"],
                "https://creativecommons.org/licenses/by/4.0/",
                Json({"import_id": manifest["import_id"], "counts": manifest["counts"], "query_scope": manifest["source"]["query_scope"]}),
            ),
        )
        source_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO bd_stage.ingest_job
              (uid, input_kind, input_uri, input_sha256, source_id, state, stats, finished_at)
            VALUES (%s, 'patent_linked_data_snapshot', %s, %s, %s, 'finished', %s, now())
            ON CONFLICT (uid) DO UPDATE SET
              input_uri=EXCLUDED.input_uri, input_sha256=EXCLUDED.input_sha256,
              source_id=EXCLUDED.source_id, state='finished', stats=EXCLUDED.stats,
              finished_at=now(), error=NULL
            RETURNING id
            """,
            (job_uid, manifest["source"]["endpoint"], sha256(manifest_path), source_id, Json(manifest["counts"])),
        )
        job_id = cursor.fetchone()[0]

        execute_values(
            cursor,
            """
            INSERT INTO bd_stage.patent_publication_candidate
              (job_id, publication_uid, publication_number, title, publication_url,
               battery_relevance, primary_category, categories,
               source_observation_uids, raw_payload)
            VALUES %s
            ON CONFLICT (publication_number) DO UPDATE SET
              title=EXCLUDED.title, publication_url=EXCLUDED.publication_url,
              battery_relevance=EXCLUDED.battery_relevance,
              primary_category=EXCLUDED.primary_category,
              categories=EXCLUDED.categories,
              source_observation_uids=EXCLUDED.source_observation_uids,
              raw_payload=EXCLUDED.raw_payload
            """,
            [(
                job_id, row["publication_uid"], row["publication_number"], row["title"],
                row["publication_url"], row["battery_relevance"],
                row["classification"]["primary_category"], row["classification"]["categories"],
                row["source_observation_ids"], Json(row),
            ) for row in candidates],
            page_size=200,
        )

        execute_values(
            cursor,
            """
            INSERT INTO bd_stage.patent_company_candidate
              (job_id, company_uid, canonical_name, legal_name, country,
               organization_type, aliases, primary_category, categories,
               publication_count, earliest_publication_date, latest_publication_date,
               website, raw_payload)
            VALUES %s
            ON CONFLICT (company_uid) DO UPDATE SET
              canonical_name=EXCLUDED.canonical_name, legal_name=EXCLUDED.legal_name,
              country=EXCLUDED.country, organization_type=EXCLUDED.organization_type,
              aliases=EXCLUDED.aliases, primary_category=EXCLUDED.primary_category,
              categories=EXCLUDED.categories, publication_count=EXCLUDED.publication_count,
              earliest_publication_date=EXCLUDED.earliest_publication_date,
              latest_publication_date=EXCLUDED.latest_publication_date,
              website=EXCLUDED.website, raw_payload=EXCLUDED.raw_payload
            """,
            [(
                job_id, row["company_uid"], row["canonical_name"], row["legal_name"], row["country"],
                row["organization_type"], row["aliases"], row["value_chain"]["primary_category"],
                row["value_chain"]["categories"], row["patent_portfolio"]["publication_count"],
                row["patent_portfolio"]["earliest_publication_date"],
                row["patent_portfolio"]["latest_publication_date"],
                row["corporate_profile"]["website"], Json(row),
            ) for row in companies],
            page_size=200,
        )

        execute_values(
            cursor,
            """
            INSERT INTO bd_stage.patent_publication_company_link
              (job_id, publication_uid, company_uid, relation, raw_name, country, raw_payload)
            VALUES %s
            ON CONFLICT (publication_uid, company_uid, relation, raw_name) DO UPDATE SET
              country=EXCLUDED.country, raw_payload=EXCLUDED.raw_payload
            """,
            [(
                job_id, row["publication_uid"], row["company_uid"], row["relation"],
                row["raw_name"], row["country"], Json(row),
            ) for row in links],
            page_size=300,
        )

    print(f"staged {len(candidates)} EPO publication, {len(companies)} company and {len(links)} applicant-link candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
