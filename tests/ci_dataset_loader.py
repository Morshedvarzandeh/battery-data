#!/usr/bin/env python3
"""Load a synthetic multi-file dataset twice in a rolled-back transaction.

Checks what only the database can show: every test run's provenance resolves
to its own file (name and SHA-256), loading the dataset's files again adds no
source location or provenance row, a run already loaded is refused by its uid
rather than duplicated, and a maker the dataset does not name is the
library's placeholder organisation.
"""
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import cyclers  # noqa: E402
import ingest_open_dataset as ingest  # noqa: E402

STEMS = ["CS2_901", "CS2_902", "CS2_903"]


def inline(sql):
    # The emitted file is one transaction per block; run it inside ours instead.
    return "\n".join(line for line in sql.splitlines() if line.strip() not in ("BEGIN;", "COMMIT;"))


def emitted_sql(files):
    out = io.StringIO()
    stats = ingest.run_pipeline("calce", ingest.DATASETS["calce"], files, out)
    assert stats["files"] == len(files) and not stats["failed"], stats
    return inline(out.getvalue())


def spine_again(files):
    ds = ingest.resolve_identity("calce", ingest.DATASETS["calce"], files)
    hashed = [(f, ingest.sha256(f)) for f in files]
    return inline(ingest.spine_sql(ds, "calce", "2026-10-30", hashed, None, ds["nominal_ah"])
                  + ingest.provenance_sql("calce"))


tmp = tempfile.mkdtemp()
try:
    files = []
    for stem in STEMS:
        path = os.path.join(tmp, stem + ".csv")
        with open(path, "w") as fh:
            fh.write(cyclers._synth("arbin", n_cycles=8, rpt_every=4))
        files.append(path)
    sql = emitted_sql(files)

    connection = psycopg2.connect(sys.argv[1])
    try:
        with connection.cursor() as cur:
            def counts():
                cur.execute("""SELECT (SELECT count(*) FROM bd.source_location sl JOIN bd.source s ON s.id = sl.source_id
                                        WHERE s.uid = 'src/dataset/calce'),
                                      (SELECT count(*) FROM bd.provenance p JOIN bd.source_location sl ON sl.id = p.source_location_id
                                         JOIN bd.source s ON s.id = sl.source_id WHERE s.uid = 'src/dataset/calce'),
                                      (SELECT count(*) FROM bd.test_run WHERE uid LIKE 'run/calce/CS2_90%')""")
                return cur.fetchone()

            cur.execute(sql)
            first = counts()
            assert first == (3, 3, 3), first
            cur.execute("""SELECT tr.uid, sl.file_path, sl.quote FROM bd.test_run tr
                             JOIN bd.provenance p ON p.id = tr.provenance_id
                             JOIN bd.source_location sl ON sl.id = p.source_location_id
                            WHERE tr.uid LIKE 'run/calce/CS2_90%' ORDER BY tr.uid""")
            rows = cur.fetchall()
            for stem, (run, file_path, quote) in zip(STEMS, rows):
                assert run == f"run/calce/{stem}", run
                assert file_path == f"{stem}.csv", (run, file_path)
                assert quote.startswith(f"cycler file {stem}.csv sha256:"), quote
            cur.execute(spine_again(files))
            assert counts() == first, ("loading the files again added rows", counts(), first)
            cur.execute("SAVEPOINT rerun")
            try:
                cur.execute(sql)
                raise AssertionError("a run already loaded was accepted again")
            except psycopg2.errors.UniqueViolation:
                cur.execute("ROLLBACK TO SAVEPOINT rerun")
            assert counts() == first
            cur.execute("""SELECT o.uid, o.name FROM bd.product p JOIN bd.organization o ON o.id = p.manufacturer_id
                            WHERE p.uid = 'cell/maker-not-stated/cs2'""")
            assert cur.fetchone() == ("org/maker-not-stated", "Maker not stated")
            cur.execute("SELECT count(*) FROM bd.organization WHERE uid = 'org/unstated'")
            assert cur.fetchone()[0] == 0
        print("Dataset import: each run cites its own file; a second load adds nothing; unnamed maker is the placeholder")
    finally:
        connection.rollback()
        connection.close()
finally:
    shutil.rmtree(tmp)
