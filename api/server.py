#!/usr/bin/env python3
"""
battery-data read API: one API for every layer.

Conventions borrowed from OPTIMADE, because they are already what 21
materials-science providers implement and there is no reason to invent a
second dialect:

  * versioned base URL            /v1/...
  * JSON:API response envelope    {meta, data, links}
  * formal filter grammar         ?filter=capacity_ah >= 4.5 AND ...
  * federation endpoint           /v1/links

What is deliberately NOT borrowed: OPTIMADE's entry types. They are
crystal-structure-shaped and do not describe cells, mines or patents.

Every resource in api/resources.py is served the same way:

    GET  /v1/info                     the layers and their resources
    GET  /v1/info/{resource}          field map, operators, examples
    GET  /v1/{resource}?filter=&sort=&fields=&page_limit=&page_offset=
    GET  /v1/{resource}/{id}          one row with its related rows
    POST /v1/query                    {"resource", "filter", "fields", "sort", "page_limit", "page_offset"}
    GET  /v1/graph/reachable?start=&rels=&depth=&direction=
    GET  /v1/openapi.json

The field map of a resource is read from information_schema at first use,
so a column added to a view is filterable without a code change. The one
addition to the envelope is provenance: every row that has a source
carries source_uid, source_url, page and quote, and an API that dropped
that on the floor would undo the point of the schema.

    python api/server.py --port 8080
    curl 'localhost:8080/v1/sites?filter=kind="mine" AND commodities HAS "lithium"'

Storage access goes through a small adapter so the service runs whether
or not a Python database driver is installed - on a bare machine it
shells out to psql, which is the state of most lab boxes.
"""
from __future__ import annotations

import argparse
import datetime
import decimal
import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from filter_grammar import FIELDS, COMPONENT_FIELDS, FilterError, parse_filter, to_psycopg  # noqa: E402
from resources import (LAYERS, RESOURCES, GRAPH_RELS, FILTER_OPERATORS,  # noqa: E402
                       field_map, layer_of, openapi)

API_VERSION = "1.1.0"
PROVIDER = {
    "name": "battery-data",
    "description": "Open, provenance-first battery database: chemistry, products, components, "
                   "companies, supply chain, market, patents",
    "prefix": "bd",
    "homepage": "https://github.com/Morshedvarzandeh/battery-data",
}
MAX_PAGE = 500
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


# =====================================================================
# Storage adapter
# =====================================================================

class Db:
    """psycopg if available, otherwise psql. Same interface either way."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.driver = None
        for mod in ("psycopg", "psycopg2"):
            try:
                self.driver = __import__(mod)
                self.driver_name = mod
                break
            except ImportError:
                continue
        if self.driver is None:
            self.driver_name = "psql"
        self._fields: dict[str, dict] = {}

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        params = params or []
        if self.driver is not None:
            conn = self.driver.connect(self.dsn)
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, r)) for r in cur.fetchall()]
            finally:
                conn.close()

        # psql fallback: inline params as SQL literals, having already
        # confirmed they never reach the query text as identifiers.
        def lit(v):
            if v is None:
                return "NULL"
            if isinstance(v, bool):
                return "TRUE" if v else "FALSE"
            if isinstance(v, (int, float)):
                return repr(v)
            if isinstance(v, (list, tuple)):
                return "ARRAY[" + ",".join(lit(x) for x in v) + "]::text[]"
            return "'" + str(v).replace("'", "''") + "'"

        out, idx = [], 0
        for part in re.split(r"(%s)", sql):
            if part == "%s":
                out.append(lit(params[idx]))
                idx += 1
            else:
                out.append(part)
        final = "".join(out)

        wrapped = f"SELECT coalesce(json_agg(t),'[]') FROM ({final}) t;"
        env = dict(os.environ)
        for k, v in _dsn_to_env(self.dsn).items():
            env[k] = v
        r = subprocess.run(["psql", "-tAq", "-c", wrapped],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip())
        return json.loads(r.stdout.strip() or "[]")

    # -- field maps, read once per resource from the database ----------
    def fields(self, resource: str) -> dict:
        if resource in self._fields:
            return self._fields[resource]
        res = RESOURCES[resource]
        if res.view is None:
            self._fields[resource] = {}
            return {}
        cols = self.query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'bd' AND table_name = %s ORDER BY ordinal_position", [res.view])
        if not cols:
            raise RuntimeError(f"view bd.{res.view} for resource {resource!r} does not exist; "
                               f"rebuild the database with tools/build_db.sh")
        aliases = {"cells": FIELDS, "components": COMPONENT_FIELDS}.get(resource, {})
        self._fields[resource] = field_map(cols, aliases)
        return self._fields[resource]

    def all_fields(self) -> dict[str, dict]:
        return {name: self.fields(name) for name in RESOURCES}


def _dsn_to_env(dsn: str) -> dict:
    m = {"host": "PGHOST", "port": "PGPORT", "user": "PGUSER",
         "password": "PGPASSWORD", "dbname": "PGDATABASE"}
    env = {}
    for tok in dsn.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            if k in m:
                env[m[k]] = v
    return env


def _json_default(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return str(v)


# =====================================================================
# Envelope
# =====================================================================

def envelope(data, *, request_url: str, returned: int, more: bool,
             warnings: list | None = None, extra_meta: dict | None = None):
    meta = {
        "api_version": API_VERSION,
        "query": {"representation": request_url},
        "data_returned": returned,
        "more_data_available": more,
        "provider": PROVIDER,
    }
    if warnings:
        meta["warnings"] = warnings
    if extra_meta:
        meta.update(extra_meta)
    return {"meta": meta, "data": data}


# ---------------------------------------------------------------------
# Packs and the vehicles they are fielded in. Kept as its own SQL rather
# than a view, because the useful shape is an aggregate: a pack query
# wants its assembly, its applications and its market values folded in.
# Attribution travels with the row.
# ---------------------------------------------------------------------
PACK_SELECT = """
SELECT
  p.uid                                        AS product_uid,
  p.model_number,
  o.name                                       AS organisation,
  p.brand                                      AS brand,
  pc.designation                               AS chemistry,
  p.form_factor_code,
  energy.value_si / 3.6e6                      AS rated_kwh,
  mass.value_si                                AS pack_mass_kg,
  asm.quantity                                 AS module_count,
  cmv.unit_value                               AS used_module_value_eur,
  rp.price_per_kwh                             AS oem_replacement_price_eur_per_kwh,
  array_remove(array_agg(DISTINCT a.name), NULL)          AS vehicle_models,
  array_remove(array_agg(DISTINCT a.sector::text), NULL)  AS sectors,
  max(pa.confidence)                           AS attribution_confidence,
  min(pa.basis::text)                          AS attribution_basis
FROM bd.product p
JOIN bd.organization o            ON o.id = p.manufacturer_id
JOIN bd.product_revision r        ON r.product_id = p.id
LEFT JOIN bd.product_chemistry pc ON pc.product_revision_id = r.id
LEFT JOIN bd.product_assembly asm ON asm.parent_revision_id = r.id
LEFT JOIN bd.product_revision mr  ON mr.id = asm.child_revision_id
LEFT JOIN bd.component_market_value cmv
       ON cmv.product_revision_id = mr.id AND cmv.valid_to IS NULL
LEFT JOIN bd.replacement_price rp
       ON rp.product_revision_id = r.id AND rp.valid_to IS NULL
LEFT JOIN bd.product_application pa
       ON pa.product_revision_id = r.id AND pa.superseded_by IS NULL
LEFT JOIN bd.application a        ON a.id = pa.application_id
LEFT JOIN bd.observation energy
       ON energy.product_revision_id = r.id AND energy.statistic = 'nominal'
      AND energy.quantity_id = (SELECT id FROM bd.quantity WHERE code='energy')
LEFT JOIN bd.observation mass
       ON mass.product_revision_id = r.id AND mass.statistic = 'nominal'
      AND mass.quantity_id = (SELECT id FROM bd.quantity WHERE code='mass')
WHERE p.kind = 'pack'
GROUP BY p.uid, p.model_number, o.name, p.brand, pc.designation,
         p.form_factor_code,
         asm.quantity, cmv.unit_value, rp.price_per_kwh,
         energy.value_si, mass.value_si
ORDER BY o.name, p.model_number
"""


# =====================================================================
# The generic query, shared by GET /v1/{resource} and POST /v1/query
# =====================================================================

def build_query(db: Db, resource: str, *, filter_expr: str = "", sort: str = "",
                fields: list[str] | None = None, limit: int = 20, offset: int = 0):
    """Return (sql, params, selected_columns) for a resource query."""
    res = RESOURCES[resource]
    fm = db.fields(resource)
    columns = [f for f, spec in fm.items() if spec.get("column")]        # real view columns
    if fields:
        bad = [f for f in fields if f not in columns]
        if bad:
            raise FilterError(f"unknown field(s) {', '.join(bad)} for {resource}; "
                              f"see /v1/info/{resource}")
        selected = [res.id] + [f for f in fields if f != res.id]
    else:
        selected = columns
    where, params = parse_filter(filter_expr, fm)
    order = res.sort or res.id
    if sort:
        desc = sort.startswith("-")
        key = sort.lstrip("-")
        if key not in fm:
            raise FilterError(f"cannot sort by unknown field {key!r}; see /v1/info/{resource}")
        order = f"{fm[key]['col']} {'DESC' if desc else 'ASC'} NULLS LAST"
    sql = (f"SELECT {', '.join(chr(34) + c + chr(34) for c in selected)} FROM bd.{res.view} WHERE {where} "
           f"ORDER BY {order} LIMIT {int(limit) + 1} OFFSET {int(offset)}")
    sql, params = to_psycopg(sql, params)
    return sql, params, selected


def run_query(db: Db, resource: str, request_url: str, *, filter_expr: str = "", sort: str = "",
              fields: list[str] | None = None, limit: int = 20, offset: int = 0) -> dict:
    res = RESOURCES[resource]
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    sql, params, _ = build_query(db, resource, filter_expr=filter_expr, sort=sort, fields=fields,
                                 limit=limit, offset=offset)
    rows = db.query(sql, params)
    more = len(rows) > limit
    rows = rows[:limit]
    data = [{"type": resource, "id": str(r.get(res.id)), "attributes": r} for r in rows]
    payload = envelope(data, request_url=request_url, returned=len(data), more=more,
                       extra_meta={"layer": layer_of(resource), **({"note": res.note} if res.note else {})})
    payload["links"] = {"base_url": "/v1"}
    if more:
        q = {"page_limit": limit, "page_offset": offset + limit}
        if filter_expr:
            q["filter"] = filter_expr
        if sort:
            q["sort"] = sort
        if fields:
            q["fields"] = ",".join(fields)
        payload["links"]["next"] = f"/v1/{resource}?" + urllib.parse.urlencode(q)
    return payload


def detail(db: Db, resource: str, ident: str, request_url: str) -> dict | None:
    res = RESOURCES[resource]
    fm = db.fields(resource)
    columns = [f for f, spec in fm.items() if spec.get("column")]
    rows = db.query(f"SELECT {', '.join(chr(34) + c + chr(34) for c in columns)} FROM bd.{res.view} "
                    f"WHERE {fm[res.id]['col']} = %s",
                    [ident if fm[res.id]["type"] != "number" else _number(ident)])
    if not rows:
        return None
    row = rows[0]
    relationships = {}
    for name, (view, view_col, row_key) in res.related.items():
        key = row.get(row_key)
        if key is None:
            relationships[name] = {"data": []}
            continue
        rel_rows = db.query(f'SELECT * FROM bd.{view} WHERE "{view_col}" = %s LIMIT 1000', [key])
        relationships[name] = {"data": rel_rows}
    entry = {"type": resource, "id": str(row.get(res.id)), "attributes": row}
    if relationships:
        entry["relationships"] = relationships
    return envelope([entry], request_url=request_url, returned=1, more=False,
                    extra_meta={"layer": layer_of(resource),
                                "note": "Every attribute traces to the observations and rows under "
                                        "relationships, each with its conditions and its page-level "
                                        "citation." if res.related else None})


def _number(s: str):
    try:
        return int(s)
    except ValueError:
        return float(s)


# =====================================================================
# HTTP
# =====================================================================

class Handler(BaseHTTPRequestHandler):
    db: Db = None                                  # injected in serve()
    server_version = "battery-data/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code: int, payload: dict, content_type: str = "application/vnd.api+json"):
        body = json.dumps(payload, indent=2, default=_json_default).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, title: str, detail_text: str = "", hint: str = ""):
        err = {"status": str(code), "title": title}
        if detail_text:
            err["detail"] = detail_text
        if hint:
            err["meta"] = {"hint": hint}
        self._send(code, {"meta": {"api_version": API_VERSION, "provider": PROVIDER},
                          "errors": [err]})

    # -- routing ------------------------------------------------------
    def do_GET(self):                              # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path.rstrip("/") or "/"
        one = lambda k, d="": (q.get(k) or [d])[0]  # noqa: E731
        try:
            if path in ("/", "/versions"):
                return self._send(200, {"available_api_versions": [{"url": "/v1", "version": API_VERSION}],
                                        "provider": PROVIDER})
            if path == "/v1/info":
                return self._info()
            if path == "/v1/links":
                return self._links()
            if path == "/v1/openapi.json":
                return self._send(200, openapi(self.db.all_fields(), version=API_VERSION), "application/json")
            if path == "/v1/graph/reachable":
                return self._reachable(one("start"), one("rels"), one("depth", "3"), one("direction", "both"))
            if path == "/v1/query":
                return self._query({"resource": one("resource"), "filter": one("filter"), "sort": one("sort"),
                                    "fields": one("fields"), "page_limit": one("page_limit", "20"),
                                    "page_offset": one("page_offset", "0")})
            m = re.fullmatch(r"/v1/info/([a-z_]+)", path)
            if m:
                return self._info_resource(m.group(1))
            m = re.fullmatch(r"/v1/([a-z_]+)", path)
            if m:
                return self._list(m.group(1), q)
            m = re.fullmatch(r"/v1/([a-z_]+)/(.+)", path)
            if m:
                return self._detail(m.group(1), urllib.parse.unquote(m.group(2)))
            return self._error(404, "Not found", f"No endpoint {path}", "Try /v1/info for the endpoint list.")
        except FilterError as e:
            return self._error(400, "Invalid query", str(e), "See /v1/info/{resource} for the fields.")
        except Exception as e:                     # noqa: BLE001
            return self._error(500, "Internal error", str(e))

    def do_POST(self):                             # noqa: N802
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if path != "/v1/query":
            return self._error(404, "Not found", f"POST is only served at /v1/query, not {path}")
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise FilterError("the body must be a JSON object")
            return self._query(body)
        except FilterError as e:
            return self._error(400, "Invalid query", str(e), "See /v1/info/{resource} for the fields.")
        except json.JSONDecodeError as e:
            return self._error(400, "Invalid JSON", str(e))
        except Exception as e:                     # noqa: BLE001
            return self._error(500, "Internal error", str(e))

    # -- endpoints ----------------------------------------------------
    def _info(self):
        layers = []
        for layer in LAYERS:
            layers.append({**layer, "resources": [
                {"name": r, "endpoint": f"/v1/{r}", "description": RESOURCES[r].description,
                 "filterable": RESOURCES[r].view is not None} for r in layer["resources"]]})
        self._send(200, {"meta": {"api_version": API_VERSION, "provider": PROVIDER},
                         "data": {
            "type": "info", "id": "/",
            "api_version": API_VERSION,
            "layers": layers,
            "entry_types_by_format": {"json": [n for n, r in RESOURCES.items() if r.view]},
            "available_endpoints": ["info", "info/{resource}", "{resource}", "{resource}/{id}", "query",
                                    "graph/reachable", "openapi.json", "links", "versions"],
            "formats": ["json"],
            "filter_operators": FILTER_OPERATORS,
            "license": "CC-BY-4.0 for curated data; source documents and licensed price assessments "
                       "are not redistributed",
        }})

    def _info_resource(self, resource: str):
        if resource not in RESOURCES:
            return self._error(404, "Not found", f"No resource {resource!r}",
                               "See /v1/info for the resource list.")
        res = RESOURCES[resource]
        fm = self.db.fields(resource)
        props = {name: {"type": spec["type"], "column": spec["col"], "sortable": spec["type"] != "list"}
                 for name, spec in fm.items()}
        self._send(200, {"meta": {"api_version": API_VERSION, "provider": PROVIDER},
                         "data": {
            "type": "info", "id": resource, "layer": layer_of(resource),
            "description": res.description, "note": res.note or None,
            "endpoint": f"/v1/{resource}", "id_field": res.id,
            "properties": props, "formats": ["json"],
            "output_fields_by_format": {"json": [f for f, s in fm.items() if s.get("column")]},
            "filter_operators": FILTER_OPERATORS,
            "examples": res.examples,
            "related": {name: f"/v1/{resource}/{{id}} -> relationships.{name} (bd.{view})"
                        for name, (view, _, _) in res.related.items()},
        }})

    def _links(self):
        self._send(200, {"meta": {"api_version": API_VERSION, "provider": PROVIDER},
                         "data": [
            {"type": "links", "id": "mp",
             "attributes": {"name": "Materials Project",
                            "base_url": "https://optimade.materialsproject.org",
                            "link_type": "external",
                            "description": "Materials are federated, not re-hosted; "
                                           "material.optimade_ids resolves here."}},
            {"type": "links", "id": "bda",
             "attributes": {"name": "Battery Data Alliance",
                            "base_url": "https://batterydataalliance.energy",
                            "link_type": "external",
                            "description": "Time-series format (BDF) adopted verbatim."}},
        ]})

    def _list(self, resource: str, q: dict):
        if resource not in RESOURCES:
            return self._error(404, "Not found", f"No resource {resource!r}",
                               "See /v1/info for the resource list.")
        res = RESOURCES[resource]
        one = lambda k, d="": (q.get(k) or [d])[0]  # noqa: E731
        if resource == "layers":
            return self._send(200, envelope([{"type": "layers", "id": l["code"], "attributes": l} for l in LAYERS],
                                            request_url=self.path, returned=len(LAYERS), more=False))
        if resource == "packs":
            return self._packs(q)
        if res.view is None:
            return self._error(404, "Not found", f"{resource} has no list endpoint")
        fields = [f for f in one("fields").split(",") if f] or None
        payload = run_query(self.db, resource, self.path, filter_expr=one("filter"), sort=one("sort"),
                            fields=fields, limit=int(one("page_limit", "20")),
                            offset=int(one("page_offset", "0")))
        self._send(200, payload)

    def _query(self, body: dict):
        resource = body.get("resource")
        if resource not in RESOURCES or RESOURCES[resource].view is None:
            raise FilterError(f"resource must be one of: "
                              f"{', '.join(n for n, r in RESOURCES.items() if r.view)}")
        fields = body.get("fields") or None
        if isinstance(fields, str):
            fields = [f for f in fields.split(",") if f]
        payload = run_query(self.db, resource, self.path, filter_expr=body.get("filter") or "",
                            sort=body.get("sort") or "", fields=fields,
                            limit=int(body.get("page_limit") or 20), offset=int(body.get("page_offset") or 0))
        self._send(200, payload)

    def _detail(self, resource: str, ident: str):
        if resource not in RESOURCES or RESOURCES[resource].view is None:
            return self._error(404, "Not found", f"No resource {resource!r} with detail rows")
        payload = detail(self.db, resource, ident, self.path)
        if payload is None:
            return self._error(404, "Not found", f"No {resource} row with id {ident!r}")
        self._send(200, payload)

    def _packs(self, q: dict):
        limit = min(int((q.get("page_limit") or [200])[0]), MAX_PAGE)
        offset = int((q.get("page_offset") or [0])[0])
        sector = (q.get("sector") or [""])[0]
        sql, params = PACK_SELECT, []
        if sector:
            sql = "SELECT * FROM (" + sql + ") t WHERE %s = ANY(t.sectors)"
            params.append(sector)
        sql += " LIMIT %s OFFSET %s"
        rows = self.db.query(sql, params + [limit + 1, offset])
        more = len(rows) > limit
        rows = rows[:limit]
        payload = envelope([{"type": "packs", "id": r["product_uid"], "attributes": r} for r in rows],
                           request_url=self.path, returned=len(rows), more=more,
                           extra_meta={"layer": "products"})
        payload["links"] = {"base_url": "/v1"}
        self._send(200, payload)

    def _reachable(self, start: str, rels: str, depth: str, direction: str):
        if not start:
            raise FilterError("start is required: a uid such as cell/..., org/..., site/... or patent/...")
        if direction not in ("out", "in", "both"):
            raise FilterError("direction must be out, in or both")
        try:
            depth_n = max(1, min(int(depth), 8))
        except ValueError:
            raise FilterError("depth must be an integer between 1 and 8")  # noqa: B904
        rel_list = [r.strip().upper() for r in rels.split(",") if r.strip()] or None
        node = self.db.query("SELECT node_key, label FROM bd_graph.node WHERE uid = %s ORDER BY node_key LIMIT 1",
                             [start])
        if not node:
            return self._error(404, "Not found", f"No graph node with uid {start!r}",
                               "The projection is refreshed with SELECT bd_graph.refresh().")
        rows = self.db.query("SELECT node_key, label, uid, title, depth, path FROM "
                             "bd_graph.reachable(%s::text, %s::text[], %s::int, %s::text) "
                             "ORDER BY depth, label, uid",
                             [node[0]["node_key"], rel_list, depth_n, direction])
        self._send(200, envelope(rows, request_url=self.path, returned=len(rows), more=False,
                                 extra_meta={"start": {"uid": start, "label": node[0]["label"]},
                                             "rels": rel_list or "all", "depth": depth_n,
                                             "direction": direction, "relationship_types": GRAPH_RELS}))


def serve(port: int, dsn: str):
    Handler.db = Db(dsn)
    print(f"battery-data API on http://127.0.0.1:{port}/v1")
    print(f"  storage driver : {Handler.db.driver_name}")
    print(f"  try            : /v1/info, /v1/cells?filter=capacity_ah>=4.5, /v1/sites, /v1/openapi.json")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--dsn", default=os.getenv("BATTERY_DSN", "dbname=batterydb"))
    a = ap.parse_args()
    serve(a.port, a.dsn)
