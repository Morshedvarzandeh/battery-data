"""The layers that are not products: sites, companies, market series and
patents. The fictional examples validate, the offline vocabularies match the
SQL enums, and the rules that matter refuse what they should."""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import validate_layers as vl  # noqa: E402


def sql(name: str) -> str:
    return open(os.path.join(ROOT, "schema", name), encoding="utf-8").read()


def sql_enum(text: str, type_name: str) -> list[str]:
    m = re.search(rf"CREATE TYPE {type_name} AS ENUM \((.*?)\);", text, re.S)
    assert m, type_name
    return re.findall(r"'([a-z_]+)'", m.group(1))


def insert_block(text: str, table: str) -> str:
    m = re.search(rf"INSERT INTO {table} \(.*?\) VALUES(.*?'\)\s*;)", text, re.S)
    assert m, table
    return m.group(1)


def schema(name: str) -> dict:
    return json.load(open(os.path.join(ROOT, "json-schema", name), encoding="utf-8"))


class ExamplesValidate(unittest.TestCase):
    def test_every_example_validates(self):
        files = sorted(glob.glob(os.path.join(ROOT, "docs", "examples", "*.y*ml")))
        self.assertGreaterEqual(len(files), 6)
        errs, counts = vl.validate_files(files, expect_dir=False)
        self.assertEqual(errs, [])
        self.assertEqual(counts["sites"], 3)
        self.assertEqual(counts["companies"], 1)
        self.assertEqual(counts["market"], 1)
        self.assertEqual(counts["patents"], 1)

    def test_examples_are_fictional(self):
        for f in glob.glob(os.path.join(ROOT, "docs", "examples", "*.y*ml")):
            text = open(f, encoding="utf-8").read()
            self.assertIn("FICTIONAL", text, f)
            self.assertNotRegex(text, r"https?://(?!example\.org)", f)


class VocabulariesAgree(unittest.TestCase):
    """The JSON schemas are the offline gate; the SQL is what the database
    enforces. They must say the same thing or the gate lies."""

    def test_site_kinds(self):
        self.assertEqual(sql_enum(sql("185_supply_chain.sql"), "site_kind"),
                         schema("site-contribution.schema.json")["properties"]["site"]["properties"]["kind"]["enum"])

    def test_every_site_kind_but_other_has_a_stage(self):
        kinds = set(sql_enum(sql("185_supply_chain.sql"), "site_kind")) - {"other"}
        block = insert_block(sql("184_companies.sql"), "supply_chain_stage")
        staged = set()
        for arr in re.findall(r"'\{([a-z_,]*)\}'", block)[0::2]:
            staged |= {k for k in arr.split(",") if k}
        self.assertEqual(kinds, staged)

    def test_roles_match(self):
        block = insert_block(sql("184_companies.sql"), "organization_role")
        codes = re.findall(r"^\s*\('([a-z_]+)',", block, re.M)
        roles = schema("company-contribution.schema.json")["properties"]["organization"]["properties"]["roles"]["items"]["enum"]
        self.assertEqual(codes, roles)
        stage_block = insert_block(sql("184_companies.sql"), "supply_chain_stage")
        in_stages = set()
        for arr in re.findall(r"'\{([a-z_,]*)\}'", stage_block)[1::2]:
            in_stages |= {r for r in arr.split(",") if r}
        self.assertTrue(in_stages <= set(codes), in_stages - set(codes))

    def test_relation_kinds(self):
        self.assertEqual(sql_enum(sql("184_companies.sql"), "organization_relation_kind"),
                         schema("company-contribution.schema.json")["$defs"]["relation"]["properties"]["relation"]["enum"])

    def test_site_and_market_enums(self):
        site, market = schema("site-contribution.schema.json"), schema("market-contribution.schema.json")
        s185, s186 = sql("185_supply_chain.sql"), sql("186_market.sql")
        self.assertEqual(sql_enum(s185, "site_status"), site["properties"]["site"]["properties"]["status"]["enum"])
        self.assertEqual(sql_enum(s185, "resource_category"), site["$defs"]["resource"]["properties"]["category"]["enum"])
        self.assertEqual(sql_enum(s185, "capacity_status"), site["$defs"]["metric"]["properties"]["status"]["enum"])
        self.assertEqual(sql_enum(s185, "agreement_kind"), market["$defs"]["supply_agreement"]["properties"]["kind"]["enum"])
        self.assertEqual(sql_enum(s185, "distribution_status"), market["$defs"]["distribution"]["properties"]["status"]["enum"])
        self.assertEqual(sql_enum(s186, "price_basis"), market["$defs"]["commodity_price"]["properties"]["basis"]["enum"])
        self.assertEqual(sql_enum(s186, "market_metric"), market["$defs"]["market_volume"]["properties"]["metric"]["enum"])
        self.assertEqual(sql_enum(s186, "trade_direction"), market["$defs"]["trade_flow"]["properties"]["direction"]["enum"])

    def test_chemistry_families(self):
        fam = sql_enum(sql("010_vocabulary.sql"), "chemistry_family")
        market = schema("market-contribution.schema.json")
        self.assertEqual(fam, market["$defs"]["price_index"]["properties"]["chemistry_family"]["enum"])
        self.assertEqual(fam, market["$defs"]["market_volume"]["properties"]["chemistry_family"]["enum"])

    def test_patent_categories(self):
        codes = re.findall(r"^\s*\('([a-z_]+)', '", insert_block(sql("125_patents.sql"), "patent_category"), re.M)
        self.assertEqual(codes, schema("patent-contribution.schema.json")["$defs"]["category_code"]["enum"])
        taxonomy = json.load(open(os.path.join(ROOT, "patents", "taxonomy.json"), encoding="utf-8"))
        cats = taxonomy["categories"]
        self.assertEqual(sorted(codes), sorted(cats if isinstance(cats, dict) else [c["code"] for c in cats]))


class RulesBite(unittest.TestCase):
    known = {"products": {"cell/example-cells/x1"}, "orgs": {"org/example-cells"}, "sites": {"site/a/b"}}

    def test_layer_detection(self):
        self.assertEqual(vl.layer_of({"site": {}}), "sites")
        self.assertEqual(vl.layer_of({"organization": {}}), "companies")
        self.assertEqual(vl.layer_of({"family": {}}), "patents")
        self.assertEqual(vl.layer_of({"source": {}, "commodity_prices": []}), "market")
        self.assertEqual(vl.layer_of({"product": {}}), "products")
        self.assertIsNone(vl.layer_of({"something": 1}))

    def test_licensed_prices_are_refused(self):
        doc = {"source": {"data_redistributable": False},
               "commodity_prices": [{"period_start": "2024-01-01", "period_end": "2024-12-31"}]}
        errs = vl.check_market("f", doc, self.known)
        self.assertTrue(any("may not be redistributed" in e for e in errs), errs)

    def test_resource_needs_reporting_code_or_declares_it(self):
        base = {"site": {"kind": "mine", "operator": "X"}, "resources": [{"commodity": "lithium", "tonnage": 1}]}
        errs = vl.check_site("f", base, self.known)
        self.assertTrue(any("reporting_code" in e for e in errs))
        self.assertTrue(any("cutoff_grade" in e for e in errs))
        ok = {"site": {"kind": "mine", "operator": "X"},
              "resources": [{"commodity": "lithium", "tonnage": 1, "reporting_code": "JORC 2012",
                             "unstated": ["cutoff_grade"]}]}
        self.assertEqual(vl.check_site("f", ok, self.known), [])

    def test_capacity_needs_its_status(self):
        doc = {"site": {"kind": "cell_factory", "operator": "X"},
               "metrics": [{"metric": "capacity", "value": 1, "unit": "GWh/yr", "period_start": "2025-01-01"}]}
        self.assertTrue(any("nameplate" in e for e in vl.check_site("f", doc, self.known)))

    def test_resource_estimate_only_on_a_mine(self):
        doc = {"site": {"kind": "test_laboratory", "operator": "X"},
               "resources": [{"commodity": "lithium", "tonnage": 1, "reporting_code": "JORC 2012", "cutoff_grade": 0.5}]}
        self.assertTrue(any("belongs to a mine" in e for e in vl.check_site("f", doc, self.known)))

    def test_unknown_uid_pins_are_refused(self):
        doc = {"site": {"kind": "mine", "operator_uid": "org/nobody"}}
        self.assertTrue(any("not a known organisation" in e for e in vl.check_site("f", doc, self.known)))
        doc = {"organization": {"uid": "org/a", "name": "A"},
               "relations": [{"relation": "subsidiary_of", "organization_uid": "org/a", "locator": {}}]}
        self.assertTrue(any("itself" in e for e in vl.check_company("f", doc, self.known)))

    def test_patent_rules(self):
        doc = {"family": {"uid": "patent/1", "docdb_family_id": "1"},
               "publications": [{"publication_number": "EP1234567B1", "jurisdiction": "US",
                                 "legal_status": "granted",
                                 "categories": [{"code": "a", "primary": True}, {"code": "b", "primary": True}]}],
               "links": [{"relation": "covers_product", "product_uid": "cell/nobody/x"}]}
        errs = vl.check_patent("f", doc, self.known)
        self.assertTrue(any("does not match the number" in e for e in errs), errs)
        self.assertTrue(any("legal status" in e for e in errs), errs)
        self.assertTrue(any("primary" in e for e in errs), errs)
        self.assertTrue(any("not in contrib/cells" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
