"""The API registry without a database: every resource names a view that
exists in the schema, every resource sits in exactly one layer, the field
map derivation types columns the way the grammar expects, list fields take
HAS and refuse =, and the OpenAPI document is generated whole."""
from __future__ import annotations

import glob
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))

import resources as R  # noqa: E402
from filter_grammar import FilterError, parse_filter  # noqa: E402


def schema_views() -> set[str]:
    views = set()
    for f in glob.glob(os.path.join(ROOT, "schema", "*.sql")):
        views |= set(re.findall(r"CREATE (?:OR REPLACE )?VIEW (\w+)", open(f, encoding="utf-8").read()))
    return views


class RegistryIsConsistent(unittest.TestCase):
    def test_every_view_exists(self):
        views = schema_views()
        for name, res in R.RESOURCES.items():
            if res.view:
                self.assertIn(res.view, views, f"{name} -> bd.{res.view}")
            for rel, (view, _, _) in res.related.items():
                self.assertIn(view, views, f"{name}.{rel} -> bd.{view}")

    def test_every_resource_in_exactly_one_layer(self):
        placed = [r for layer in R.LAYERS for r in layer["resources"]]
        self.assertEqual(sorted(placed), sorted(R.RESOURCES))
        self.assertEqual(len(placed), len(set(placed)))

    def test_layers_read_in_supply_chain_order(self):
        codes = [l["code"] for l in R.LAYERS]
        self.assertEqual(codes[0], "map")
        self.assertLess(codes.index("chemistry"), codes.index("products"))
        self.assertLess(codes.index("companies"), codes.index("supply_chain"))
        self.assertLess(codes.index("supply_chain"), codes.index("market"))

    def test_graph_rels_match_projection(self):
        text = open(os.path.join(ROOT, "schema", "190_graph.sql"), encoding="utf-8").read()
        projected = set(re.findall(r"^SELECT '([A-Z_]+)',", text, re.M))
        kinds = open(os.path.join(ROOT, "schema", "184_companies.sql"), encoding="utf-8").read()
        m = re.search(r"CREATE TYPE organization_relation_kind AS ENUM \((.*?)\);", kinds, re.S)
        relation_kinds = {k.upper() for k in re.findall(r"'([a-z_]+)'", m.group(1))}
        self.assertEqual(set(R.GRAPH_RELS), projected | relation_kinds)
        self.assertEqual(sorted(k.lower() for k in relation_kinds), sorted(R.ORG_RELATION_KINDS))


class FieldMapsAndGrammar(unittest.TestCase):
    COLS = [{"column_name": "uid", "data_type": "text"},
            {"column_name": "value", "data_type": "double precision"},
            {"column_name": "rank", "data_type": "integer"},
            {"column_name": "share_pct", "data_type": "numeric"},
            {"column_name": "commodities", "data_type": "ARRAY"},
            {"column_name": "in_stock", "data_type": "boolean"},
            {"column_name": "period_start", "data_type": "date"},
            {"column_name": "status", "data_type": "USER-DEFINED"},
            {"column_name": "applicants", "data_type": "jsonb"}]

    def test_types(self):
        fm = R.field_map(self.COLS)
        self.assertEqual(fm["uid"], {"col": '"uid"', "type": "string", "column": "uid"})
        self.assertEqual(fm["value"]["type"], "number")
        self.assertEqual(fm["rank"]["type"], "number")
        self.assertEqual(fm["share_pct"]["type"], "number")
        self.assertEqual(fm["commodities"], {"col": '"commodities"', "type": "list", "column": "commodities"})
        for cast in ("in_stock", "period_start", "status", "applicants"):
            self.assertEqual(fm[cast], {"col": f'"{cast}"::text', "type": "string", "column": cast}, cast)

    def test_aliases_are_added_not_overriding(self):
        fm = R.field_map(self.COLS, {"uid": {"col": "x", "type": "number"}, "capacity_ah": {"col": "value", "type": "number"}})
        self.assertEqual(fm["uid"]["col"], '"uid"')
        self.assertEqual(fm["capacity_ah"], {"col": "value", "type": "number", "column": None})

    def test_list_fields_take_has_and_refuse_comparison(self):
        fm = R.field_map(self.COLS)
        where, params = parse_filter('commodities HAS "lithium"', fm)
        self.assertIn('"commodities" &&', where)
        self.assertEqual(params, [["lithium"]])
        where, params = parse_filter('commodities HAS ALL "lithium","nickel"', fm)
        self.assertIn('"commodities" @>', where)
        where, _ = parse_filter('commodities CONTAINS "lith"', fm)
        self.assertIn('array_to_string("commodities"', where)
        with self.assertRaises(FilterError):
            parse_filter('commodities = "lithium"', fm)
        with self.assertRaises(FilterError):
            parse_filter('uid HAS "x"', fm)

    def test_casts_filter_as_strings(self):
        fm = R.field_map(self.COLS)
        where, params = parse_filter('in_stock = "true" AND period_start >= "2024-01-01" AND status != "closed"', fm)
        self.assertIn('"in_stock"::text = $1', where)
        self.assertIn('"period_start"::text >= $2', where)
        self.assertEqual(params, ["true", "2024-01-01", "closed"])
        with self.assertRaises(FilterError):
            parse_filter("value CONTAINS \"1\"", fm)

    def test_openapi_is_whole(self):
        fms = {name: R.field_map(self.COLS) for name in R.RESOURCES}
        doc = R.openapi(fms)
        self.assertEqual(doc["openapi"], "3.1.0")
        for name, res in R.RESOURCES.items():
            self.assertIn(f"/v1/{name}", doc["paths"], name)
            if res.view:
                self.assertIn(f"/v1/{name}/{{id}}", doc["paths"], name)
            self.assertIn(name, doc["components"]["schemas"])
        self.assertIn("/v1/query", doc["paths"])
        self.assertIn("/v1/graph/reachable", doc["paths"])
        self.assertEqual(sorted(t["name"] for t in doc["tags"]), sorted(l["code"] for l in R.LAYERS))
        self.assertEqual(doc["components"]["schemas"]["sites"]["properties"]["commodities"]["type"], "array")


if __name__ == "__main__":
    unittest.main()
