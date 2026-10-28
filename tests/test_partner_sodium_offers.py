"""The partner sodium-ion cells and the seller stock list that rides beside them.

Three promises are tested here because each one is easy to break by accident:

1. A seller's stock line never changes a record. The finder row for an offered
   product is the same row, field for field, with one added `stock` key.
2. A printed C-rate stays a C-rate. Unit "C" is the coulomb in the unit table,
   so a current quantity must never carry it, and the C-rate quantities must.
3. The partner's contact details stay out. No record in this batch carries an
   e-mail address, a telephone number or a source URL.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402
import build_web_data as web  # noqa: E402

BATCH_DIR = ROOT / "contrib" / "cells" / "maker-not-stated"
CURRENT_QS = {"max_continuous_discharge_current", "max_continuous_charge_current",
              "max_pulse_discharge_current", "standard_charge_current"}
RATE_QS = {"max_continuous_discharge_rate", "max_continuous_charge_rate",
           "max_pulse_discharge_rate", "standard_charge_rate"}


def records():
    for path in sorted(BATCH_DIR.glob("*.yaml")):
        yield path, yaml.safe_load(path.read_text(encoding="utf-8"))


class PartnerSodiumCells(unittest.TestCase):
    def test_batch_declaration_is_current(self):
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "import_partner_sodium_cells.py"), "--check"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_forty_sodium_ion_cells_with_no_named_maker(self):
        docs = [d for _, d in records()]
        self.assertEqual(len(docs), 40)
        for d in docs:
            self.assertEqual(d["product"]["manufacturer"], web.MAKER_NOT_STATED)
            self.assertEqual(d["chemistry"]["designation"], "Sodium-ion")

    def test_c_rates_are_never_coulombs(self):
        for path, d in records():
            for o in d["observations"]:
                if o["quantity"] in CURRENT_QS:
                    self.assertIn(o["unit"], {"A", "mA"}, f"{path.name}: {o['quantity']} in {o['unit']}")
                if o["quantity"] in RATE_QS:
                    self.assertEqual(o["unit"], "C-rate", path.name)

    def test_no_contact_details_or_source_urls(self):
        email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
        phone = re.compile(r"\+\d[\d\s-]{7,}\d")  # international form; model numbers never start with +
        for path, d in records():
            self.assertNotIn("url", d["source"], path.name)
            text = json.dumps(d, ensure_ascii=False)
            self.assertIsNone(email.search(text), path.name)
            self.assertIsNone(phone.search(text.replace(d["source"]["sha256"], "")), path.name)

    def test_registry_and_schema_know_the_rate_quantities(self):
        reg = json.loads((ROOT / "json-schema" / "quantity-registry.json").read_text())
        sql = (ROOT / "schema" / "138_c_rate_quantities.sql").read_text()
        for q in RATE_QS:
            self.assertIn(q, reg)
            self.assertIn(f"'{q}'", sql)


class SellerStockList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = sorted((ROOT / "contrib").glob("**/*.y*ml"))
        cls.products = [web.product(yaml.safe_load(open(f)), str(f)) for f in files]
        cls.offers, cls.sellers, cls.errs = web.load_offers({p["uid"] for p in cls.products})

    def test_stock_list_is_valid_and_complete(self):
        self.assertEqual(self.errs, [])
        self.assertEqual(len(self.offers), 40)
        self.assertEqual([s["name"] for s in self.sellers], ["Lemonergy"])

    def test_an_offer_changes_nothing_but_the_stock_field(self):
        for p in self.products:
            offer = self.offers.get(p["uid"])
            if not offer:
                continue
            with_offer, without = web.index_row(p, offer), web.index_row(p)
            self.assertEqual(with_offer.pop("stock"), offer)
            self.assertEqual(with_offer, without, p["uid"])

    def test_unknown_uid_is_refused(self):
        _, _, errs = web.load_offers(set())
        self.assertTrue(errs and all("not an accepted product" in e for e in errs))

    def test_placeholder_maker_is_not_counted_as_a_manufacturer(self):
        rows = [web.index_row(p, self.offers.get(p["uid"])) for p in self.products]
        s = web.summary(rows, self.sellers)
        self.assertEqual(s["manufacturers"], len({r["manu"] for r in rows if r["kind"] != "component"}) - 1)
        self.assertEqual(s["maker_not_stated"], 40)
        self.assertEqual(s["available_now"], 40)


if __name__ == "__main__":
    unittest.main()
