#!/usr/bin/env python3
"""Load the candidate sets under review/layers into bd_stage.layer_candidate.

Staging only. A candidate never reaches bd.*: the table's CHECK refuses a
payload with a quote, a page, a locator or a source, and the accepted
tables take rows only from tools/load_layers.py. What this gives the
library is a queryable queue (bd_stage.v_layer_candidate, /v1/layer_candidates)
of every name still to verify, with the page to verify it against.

Idempotent: a set is keyed by the sha256 of its file as an ingest job, and
a candidate by its uid; a reload updates the payload and keeps the review
state unless it is still queued.

    python tools/load_layer_candidates.py --dsn dbname=batterydb
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys

try:
    import psycopg2
    import psycopg2.extras
    import yaml
except ImportError:
    sys.exit("pip install psycopg2-binary pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "review", "layers")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_layers import plain  # noqa: E402


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def load_file(cur, path: str) -> tuple[str, int, int]:
    raw = open(path, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    doc = plain(yaml.safe_load(raw.decode("utf-8")))
    rel = os.path.relpath(path, ROOT)
    job_id = scalar(cur, "SELECT id FROM bd_stage.ingest_job WHERE input_sha256 = %s", (sha,))
    if job_id is None:
        job_id = scalar(cur,
            """INSERT INTO bd_stage.ingest_job (uid, input_kind, input_uri, input_sha256, state, stats, finished_at)
               VALUES (%s, 'layer_candidates', %s, %s, 'done', %s, now()) RETURNING id""",
            (f"job/layer-candidates/{doc['candidate_set']}/{sha[:12]}", rel, sha,
             psycopg2.extras.Json({"companies": len(doc.get("companies") or []),
                                   "sites": len(doc.get("sites") or []),
                                   "recalled_by": doc["recalled_by"], "recalled_on": doc["recalled_on"]})))
    upsert = """
        INSERT INTO bd_stage.layer_candidate
            (job_id, candidate_set, entity, uid, name, country, kind, roles, operator_uid,
             verify_at, confidence, recalled_on, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s::bd.site_kind, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (uid) DO UPDATE SET
            job_id = EXCLUDED.job_id, candidate_set = EXCLUDED.candidate_set, entity = EXCLUDED.entity,
            name = EXCLUDED.name, country = EXCLUDED.country, kind = EXCLUDED.kind, roles = EXCLUDED.roles,
            operator_uid = EXCLUDED.operator_uid, verify_at = EXCLUDED.verify_at,
            confidence = EXCLUDED.confidence, recalled_on = EXCLUDED.recalled_on, payload = EXCLUDED.payload"""
    n_c = n_s = 0
    for c in doc.get("companies") or []:
        cur.execute(upsert, (job_id, doc["candidate_set"], "company", c["uid"], c["name"], c["country"],
                             None, c["roles"], None, c["verify_at"], c["confidence"], doc["recalled_on"],
                             psycopg2.extras.Json(c)))
        n_c += 1
    for s in doc.get("sites") or []:
        cur.execute(upsert, (job_id, doc["candidate_set"], "site", s["uid"], s["name"], s["country"],
                             s["kind"], [], s["operator_uid"], s["verify_at"], s["confidence"],
                             doc["recalled_on"], psycopg2.extras.Json(s)))
        n_s += 1
    return rel, n_c, n_s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dsn", default=os.environ.get("BATTERY_DSN", "dbname=batterydb"))
    a = ap.parse_args()
    files = a.paths or sorted(glob.glob(os.path.join(DIR, "*.y*ml")))
    if not files:
        print("no candidate sets under review/layers")
        return 0
    conn = psycopg2.connect(a.dsn)
    total_c = total_s = 0
    with conn:
        with conn.cursor() as cur:
            for f in files:
                rel, n_c, n_s = load_file(cur, f)
                total_c += n_c
                total_s += n_s
                print(f"  ok    {rel}: {n_c} companies, {n_s} sites")
            in_lib = scalar(cur, "SELECT count(*) FROM bd_stage.v_layer_candidate WHERE in_library")
    conn.close()
    print(f"\n{len(files)} set(s), {total_c} companies, {total_s} sites staged; {in_lib} already in the library by uid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
