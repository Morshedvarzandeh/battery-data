#!/usr/bin/env python3
"""Populate an Apache AGE graph from bd_graph.node / bd_graph.edge.

Runs inside the same Postgres, so no export is needed: every node becomes a
vertex labelled with its projection label, every edge a relationship of its
kind, both carrying the projection's JSON props. Skips cleanly when the AGE
extension is not installed, which is the normal case on a stock server.

    python tools/load_age.py --dsn dbname=batterydb [--graph battery]
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    import psycopg2
except ImportError:
    sys.exit("pip install psycopg2-binary")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="dbname=batterydb")
    ap.add_argument("--graph", default="battery")
    a = ap.parse_args()
    conn = psycopg2.connect(a.dsn)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'age'")
    if cur.fetchone() is None:
        print("Apache AGE is not installed; use bd_graph.reachable() in plain SQL, "
              "or tools/export_graph.py for Neo4j.")
        return 0
    cur.execute("LOAD 'age'; SET search_path = ag_catalog, bd_graph, public;")
    cur.execute("SELECT 1 FROM ag_graph WHERE name = %s", (a.graph,))
    if cur.fetchone() is None:
        cur.execute("SELECT create_graph(%s)", (a.graph,))
    cur.execute("SELECT bd_graph.refresh()")
    cur.execute("SELECT label, node_key, uid, title, props FROM bd_graph.node ORDER BY node_key")
    n = 0
    for label, key, uid, title, props in cur.fetchall():
        body = json.dumps({"key": key, "uid": uid, "title": title, **(props or {})}, default=str)
        cur.execute(f"SELECT * FROM cypher(%s, $$ CREATE (:{label} {body}) $$) AS (v agtype)", (a.graph,))
        n += 1
    cur.execute("SELECT rel, src_key, dst_key, props FROM bd_graph.edge ORDER BY src_key, rel, dst_key")
    m = 0
    for rel, src, dst, props in cur.fetchall():
        body = json.dumps(props or {}, default=str)
        cur.execute(
            f"SELECT * FROM cypher(%s, $$ MATCH (a {{key: '{src}'}}), (b {{key: '{dst}'}}) "
            f"CREATE (a)-[:{rel} {body}]->(b) $$) AS (v agtype)", (a.graph,))
        m += 1
    conn.commit()
    print(f"graph '{a.graph}': {n} vertices, {m} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
