#!/usr/bin/env python3
"""Load model parameter contributions from contrib/models/ into the library.

Each JSON file is one parameter set for one product in the library, with the
article it came from and the bytes it was read from. It lands in
bd.model_parameterisation with provenance, and the graph projection then
carries a Model node with a PARAMETERISES edge to the revision.

    python tools/load_models.py --dsn dbname=batterydb
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("pip install psycopg2-binary")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def load(cur, path: str, reviewer_id: int) -> str:
    doc = json.load(open(path, encoding="utf-8"))
    model, source = doc["model"], doc["source"]
    rel = os.path.relpath(path, ROOT)
    revision_id = scalar(cur,
        """SELECT cr.product_revision_id FROM bd.v_current_revision cr
             JOIN bd.product p ON p.id = cr.product_id WHERE p.uid = %s""",
        (model["product_uid"],))
    if revision_id is None:
        return f"FAIL  {rel}: product {model['product_uid']} is not in the library"
    cur.execute(
        """INSERT INTO bd.source (uid, kind, title, doi, url, license, scope_note,
                                  content_sha256, retrieved_at, raw_metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
           ON CONFLICT (uid) DO NOTHING""",
        (source["uid"], source["kind"], source.get("title"), source.get("doi"),
         source.get("url"), source.get("license"), source.get("note"), source.get("sha256"),
         psycopg2.extras.Json({"citations": doc.get("citations", [])})))
    source_id = scalar(cur, "SELECT id FROM bd.source WHERE uid = %s", (source["uid"],))
    provenance_id = scalar(cur,
        """INSERT INTO bd.provenance (source_location_id, evidence, extraction, review,
                                      contributor_id, reviewed_by, reviewed_at, review_note)
           VALUES (bd.whole_source(%s), 'literature_reported', 'file_parse', 'accepted',
                   %s, %s, now(), %s) RETURNING id""",
        (source_id, reviewer_id, reviewer_id, f"accepted into contrib/ as {rel}"))
    cur.execute(
        """INSERT INTO bd.model_parameterisation
             (uid, name, kind, product_revision_id, payload, format_name, format_version,
              provenance_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (uid) DO UPDATE
             SET name = EXCLUDED.name, kind = EXCLUDED.kind,
                 product_revision_id = EXCLUDED.product_revision_id,
                 payload = EXCLUDED.payload, format_name = EXCLUDED.format_name,
                 format_version = EXCLUDED.format_version,
                 provenance_id = EXCLUDED.provenance_id""",
        (model["uid"], model["name"], model["kind"], revision_id,
         psycopg2.extras.Json(doc["payload"]), model.get("format_name"),
         model.get("format_version"), provenance_id))
    return f"ok    {rel}: {len(doc['payload'])} parameters -> {model['product_uid']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("BATTERY_DSN", "dbname=batterydb"))
    ap.add_argument("--reviewer", default="user/contrib-review")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(ROOT, "contrib", "models", "**", "*.json"), recursive=True))
    if not files:
        print("no model contributions under contrib/models")
        return 0
    conn = psycopg2.connect(a.dsn)
    failed = 0
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bd.contributor (uid, display_name, is_bot) VALUES (%s, %s, true)
                   ON CONFLICT (uid) DO NOTHING""", (a.reviewer, "contrib review (owner-approved)"))
            reviewer_id = scalar(cur, "SELECT id FROM bd.contributor WHERE uid = %s", (a.reviewer,))
            for f in files:
                line = load(cur, f, reviewer_id)
                failed += line.startswith("FAIL")
                print("  " + line)
    conn.close()
    print(f"\n{len(files)} model file(s), {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
