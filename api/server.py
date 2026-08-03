#!/usr/bin/env python3
"""
battery-data read API.

Conventions borrowed from OPTIMADE, because they are already what 21
materials-science providers implement and there is no reason to invent a
second dialect:

  * versioned base URL            /v1/...
  * JSON:API response envelope    {meta, data, links}
  * formal filter grammar         ?filter=capacity_ah >= 4.5 AND ...
  * vendor-namespaced fields      _bd_revision
  * federation endpoint           /v1/links

What is deliberately NOT borrowed: OPTIMADE's entry types. They are
crystal-structure-shaped and do not describe cells.

The one addition to the envelope is `provenance`. Every value this API
returns can be traced to a document, a revision and a page, and an API
that drops that on the floor would undo the point of the schema.

    python api/server.py --port 8080
    curl 'localhost:8080/v1/cells?filter=capacity_ah>=4.5&page_limit=5'

Storage access goes through a small adapter so the service runs whether
or not a Python database driver is installed - on a bare machine it
shells out to psql, which is the state of most lab boxes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from filter_grammar import FIELDS, FilterError, parse_filter, to_psycopg  # noqa: E402

API_VERSION = "1.0.0"
PROVIDER = {
    "name": "battery-data",
    "description": "Open, provenance-first battery database",
    "prefix": "bd",
    "homepage": "https://github.com/Morshedvarzandeh/battery-data",
}


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
                return "ARRAY[" + ",".join(lit(x) for x in v) + "]"
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


# =====================================================================
# Endpoints
# =====================================================================

CELL_SELECT = """
SELECT product_uid, manufacturer, model_number, form_factor, form_factor_code,
       chemistry, cathode_text, anode_text,
       capacity_low_rate_ah, capacity_low_rate_c, capacity_low_rate_statistic,
       capacity_1c_ah, max_cont_discharge_a, nominal_voltage_v, mass_kg,
       specific_energy_wh_per_kg_derived, discharge_temp_min_c,
       revision_label, product_revision_id
  FROM bd.v_cell_selection
"""

PROVENANCE_SELECT = """
SELECT quantity, statistic, value_native, unit_native, value_si,
       temperature_c, rate_value, rate_unit, soc_pct, pulse_duration_s,
       frequency_hz, direction, voltage_lower_v,
       evidence, extraction, confidence, review,
       source_uid, source_title, source_url, doi, source_revision,
       page, section, quote
  FROM bd.v_observation
 WHERE product_revision_id = %s
 ORDER BY quantity
"""


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
# Packs and the vehicles they are fielded in.
#
# Cells are the deep end of this database; packs are the end most callers
# arrive at, because "what is in this car" is the first question anyone
# asks. Kept as its own endpoint rather than a product_kind filter on
# /v1/cells, because the useful shape is different: a pack query wants its
# assembly, its applications and its market values folded in.
#
# Attribution travels with the row. A caller that values a pack against a
# community-reported link should be able to see that it did.
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


class Handler(BaseHTTPRequestHandler):
    db: Db = None                                  # injected in serve()
    server_version = "battery-data/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/vnd.api+json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, title: str, detail: str = "", hint: str = ""):
        err = {"status": str(code), "title": title}
        if detail:
            err["detail"] = detail
        if hint:
            err["meta"] = {"hint": hint}
        self._send(code, {"meta": {"api_version": API_VERSION,
                                   "provider": PROVIDER},
                          "errors": [err]})

    def do_GET(self):                              # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path.rstrip("/") or "/"

        try:
            if path == "/" or path == "/versions":
                return self._send(200, {"available_api_versions":
                                        [{"url": "/v1", "version": API_VERSION}],
                                        "provider": PROVIDER})
            if path == "/v1/info":
                return self._info()
            if path == "/v1/info/cells":
                return self._info_cells()
            if path == "/v1/links":
                return self._links()
            if path == "/v1/cells":
                return self._cells(q, self.path)
            m = re.fullmatch(r"/v1/cells/(.+)", path)
            if m:
                return self._cell_detail(urllib.parse.unquote(m.group(1)), q)
            if path == "/v1/packs":
                return self._packs(q, self.path)
            if path == "/v1/crosswalk":
                return self._crosswalk()
            return self._error(404, "Not found",
                               f"No endpoint {path}",
                               "Try /v1/info for the endpoint list.")
        except FilterError as e:
            return self._error(400, "Invalid filter", str(e),
                               "See /v1/info/cells for filterable fields.")
        except Exception as e:                     # noqa: BLE001
            return self._error(500, "Internal error", str(e))

    # -- endpoints ----------------------------------------------------
    def _info(self):
        self._send(200, {"meta": {"api_version": API_VERSION,
                                  "provider": PROVIDER},
                         "data": {
            "type": "info", "id": "/",
            "api_version": API_VERSION,
            "entry_types_by_format": {"json": ["cells"]},
            "available_endpoints": ["info", "links", "cells", "crosswalk",
                                    "versions"],
            "formats": ["json"],
            "license": "CC-BY-4.0 for curated data; source documents are not "
                       "redistributed",
        }})

    def _info_cells(self):
        props = {name: {"description": f"maps to {spec['col']}",
                        "type": spec["type"],
                        "sortable": True}
                 for name, spec in FIELDS.items()}
        self._send(200, {"meta": {"api_version": API_VERSION,
                                  "provider": PROVIDER},
                         "data": {
            "type": "info", "id": "cells",
            "description": "Battery cells with their specification values.",
            "properties": props,
            "formats": ["json"],
            "output_fields_by_format": {"json": sorted(FIELDS)},
            "filter_operators": ["=", "!=", "<", "<=", ">", ">=", "AND", "OR",
                                 "NOT", "CONTAINS", "STARTS WITH", "ENDS WITH",
                                 "IS KNOWN", "IS UNKNOWN", "HAS", "HAS ALL",
                                 "HAS ANY", "HAS ONLY"],
            "examples": [
                'capacity_ah >= 4.5 AND form_factor_code = "21700"',
                'manufacturer CONTAINS "Samsung" AND max_cont_discharge_a > 9',
                'chemistry = "LFP" AND capacity_ah > 200',
            ],
            "note": ("capacity_ah is the low-rate figure and capacity_1c_ah the "
                     "~1C figure. They are exposed separately on purpose: "
                     "vendors publish both and they are not the same number."),
        }})

    def _links(self):
        self._send(200, {"meta": {"api_version": API_VERSION,
                                  "provider": PROVIDER},
                         "data": [
            {"type": "links", "id": "mp",
             "attributes": {"name": "Materials Project",
                            "base_url": "https://optimade.materialsproject.org",
                            "link_type": "external",
                            "description": "Materials are federated, not "
                                           "re-hosted; material.optimade_ids "
                                           "resolves here."}},
            {"type": "links", "id": "bda",
             "attributes": {"name": "Battery Data Alliance",
                            "base_url": "https://batterydataalliance.energy",
                            "link_type": "external",
                            "description": "Time-series format (BDF) adopted "
                                           "verbatim."}},
        ]})

    def _crosswalk(self):
        rows = self.db.query("SELECT * FROM bd.v_crosswalk ORDER BY vocabulary, quantity")
        self._send(200, envelope(rows, request_url=self.path,
                                 returned=len(rows), more=False,
                                 extra_meta={"description":
                                             "Mapping to BDF, EMMO/BattINFO, "
                                             "BPX and the EU Battery Passport."}))

    def _cells(self, q: dict, request_url: str):
        expr = (q.get("filter") or [""])[0]
        limit = min(int((q.get("page_limit") or [20])[0]), 500)
        offset = int((q.get("page_offset") or [0])[0])
        sort = (q.get("sort") or [""])[0]

        where, params = parse_filter(expr)
        sql, params = to_psycopg(f"{CELL_SELECT} WHERE {where}", params)

        order = "capacity_low_rate_ah DESC NULLS LAST"
        if sort:
            desc = sort.startswith("-")
            key = sort.lstrip("-")
            if key not in FIELDS:
                raise FilterError(f"cannot sort by unknown field {key!r}")
            order = f"{FIELDS[key]['col']} {'DESC' if desc else 'ASC'} NULLS LAST"

        sql += f" ORDER BY {order} LIMIT %s OFFSET %s"
        rows = self.db.query(sql, params + [limit + 1, offset])
        more = len(rows) > limit
        rows = rows[:limit]

        data = [{"type": "cells", "id": r.pop("product_uid"), "attributes": r}
                for r in rows]
        payload = envelope(data, request_url=request_url,
                           returned=len(data), more=more)
        payload["links"] = {"base_url": "/v1"}
        if more:
            payload["links"]["next"] = (
                f"/v1/cells?filter={urllib.parse.quote(expr)}"
                f"&page_limit={limit}&page_offset={offset + limit}")
        self._send(200, payload)

    def _packs(self, q: dict, request_url: str):
        limit = min(int((q.get("page_limit") or [200])[0]), 500)
        offset = int((q.get("page_offset") or [0])[0])
        sector = (q.get("sector") or [""])[0]

        sql = PACK_SELECT
        params: list = []
        if sector:
            # Filter after aggregation, since sectors is an aggregate.
            sql = "SELECT * FROM (" + sql + ") t WHERE %s = ANY(t.sectors)"
            params.append(sector)

        sql += " LIMIT %s OFFSET %s"
        rows = self.db.query(sql, params + [limit + 1, offset])
        more = len(rows) > limit
        rows = rows[:limit]

        payload = envelope(rows, request_url=request_url,
                           returned=len(rows), more=more)
        payload["links"] = {"base_url": "/v1"}
        self._send(200, payload)

    def _cell_detail(self, uid: str, q: dict):
        sql, params = to_psycopg(f"{CELL_SELECT} WHERE product_uid = $1", [uid])
        rows = self.db.query(sql, params)
        if not rows:
            return self._error(404, "Not found", f"No cell with id {uid!r}")
        cell = rows[0]
        rev_id = cell.get("product_revision_id")

        # Provenance is part of the response, not an optional extra.
        obs = self.db.query(*to_psycopg(PROVENANCE_SELECT.replace("%s", "$1"),
                                        [rev_id])) if rev_id else []
        payload = envelope(
            [{"type": "cells", "id": uid, "attributes": cell,
              "relationships": {"observations": {"data": obs}}}],
            request_url=self.path, returned=1, more=False,
            extra_meta={"note": ("Every attribute is derived from the "
                                 "observations list, each of which carries its "
                                 "measurement conditions and a page-level "
                                 "citation.")})
        self._send(200, payload)


def serve(port: int, dsn: str):
    Handler.db = Db(dsn)
    print(f"battery-data API on http://127.0.0.1:{port}/v1")
    print(f"  storage driver : {Handler.db.driver_name}")
    print(f"  try            : /v1/cells?filter=capacity_ah>=4.5")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--dsn", default=os.getenv("BATTERY_DSN", "dbname=batterydb"))
    a = ap.parse_args()
    serve(a.port, a.dsn)
