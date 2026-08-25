#!/usr/bin/env python3
"""Load the checked-in patent import into bd_stage without promoting it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT = ROOT / "patents" / "imports" / "cordis-2026-08-21"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_shards(directory: Path) -> list[dict]:
    return [row for path in sorted(directory.glob("part-*.jsonl")) for row in read_jsonl(path)]


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

    manifest = json.loads((args.input / "manifest.json").read_text(encoding="utf-8"))
    observations = read_shards(args.input / "source-observations")
    candidates = read_shards(args.input / "publication-candidates")
    source_uid = "source/cordis-patent-ip-2026-08-21"
    job_uid = "ingest/cordis-patent-ip-2026-08-21"

    with psycopg2.connect(args.dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO bd.source
              (uid, kind, title, url, retrieved_at, retrieved_from, content_sha256,
               media_type, byte_size, redistributable, raw_metadata)
            VALUES (%s, 'dataset', %s, %s, %s::timestamptz, %s, %s, %s, %s, false, %s)
            ON CONFLICT (uid) DO UPDATE SET
              title=EXCLUDED.title, url=EXCLUDED.url, retrieved_at=EXCLUDED.retrieved_at,
              retrieved_from=EXCLUDED.retrieved_from, content_sha256=EXCLUDED.content_sha256,
              media_type=EXCLUDED.media_type, byte_size=EXCLUDED.byte_size,
              raw_metadata=EXCLUDED.raw_metadata, updated_at=now()
            RETURNING id
            """,
            (
                source_uid,
                "CORDIS battery-project public results: PATENT_IP snapshot",
                manifest["source"]["official_landing_url"],
                manifest["source"]["snapshot_date"],
                manifest["source"]["workbook"],
                manifest["source"]["workbook_sha256"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                manifest["source"]["workbook_size_bytes"],
                Json({"import_id": manifest["import_id"], "counts": manifest["counts"]})
            )
        )
        source_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO bd_stage.ingest_job
              (uid, input_kind, input_uri, input_sha256, source_id, state, stats, finished_at)
            VALUES (%s, 'patent_metadata_snapshot', %s, %s, %s, 'finished', %s, now())
            ON CONFLICT (uid) DO UPDATE SET
              input_uri=EXCLUDED.input_uri, input_sha256=EXCLUDED.input_sha256,
              source_id=EXCLUDED.source_id, state='finished', stats=EXCLUDED.stats,
              finished_at=now(), error=NULL
            RETURNING id
            """,
            (
                job_uid,
                manifest["source"]["workbook"],
                manifest["source"]["workbook_sha256"],
                source_id,
                Json(manifest["counts"])
            )
        )
        job_id = cursor.fetchone()[0]

        observation_values = [(
            job_id,
            row["observation_uid"],
            row["project"]["grant_id"],
            row["project"]["acronym"],
            row["result"]["id"],
            row["result"]["title"],
            row["battery_relevance"],
            row["patent_identity"]["status"],
            row["patent_identity"]["publication_number"],
            row["patent_identity"]["obvious_non_patent_title"],
            row["classification"]["primary_category"],
            row["classification"]["categories"],
            Json(row)
        ) for row in observations]
        execute_values(
            cursor,
            """
            INSERT INTO bd_stage.patent_observation
              (job_id, observation_uid, cordis_project_id, project_acronym,
               cordis_result_id, title, battery_relevance, identity_state,
               publication_number, obvious_non_patent_title, primary_category,
               categories, raw_payload)
            VALUES %s
            ON CONFLICT (observation_uid) DO UPDATE SET
              title=EXCLUDED.title, battery_relevance=EXCLUDED.battery_relevance,
              identity_state=EXCLUDED.identity_state,
              publication_number=EXCLUDED.publication_number,
              obvious_non_patent_title=EXCLUDED.obvious_non_patent_title,
              primary_category=EXCLUDED.primary_category,
              categories=EXCLUDED.categories, raw_payload=EXCLUDED.raw_payload
            """,
            observation_values,
            page_size=200
        )

        candidate_values = [(
            job_id,
            row["publication_uid"],
            row["publication_number"],
            row["title"],
            row["publication_url"],
            row["battery_relevance"],
            row["classification"]["primary_category"],
            row["classification"]["categories"],
            row["source_observation_ids"],
            Json(row)
        ) for row in candidates]
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
            candidate_values,
            page_size=200
        )

    print(f"staged {len(observations)} source rows and {len(candidates)} publication candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
