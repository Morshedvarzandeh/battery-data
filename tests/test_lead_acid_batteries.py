"""Lead-acid batteries (29 October 2026): filed as transcribed, and never for Design."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import classification as cls  # noqa: E402
import import_lead_acid_batteries as imp  # noqa: E402
import review_ledger  # noqa: E402

BATCH = ROOT / "review" / "batches" / "2026-10-29-lead-acid-batteries.json"
AUDIT = ROOT / "review" / "audits" / "2026-10-29-lead-acid-batteries.json"
TAX = cls.load(str(ROOT / "web" / "data" / "technologies-and-chemistries.json"))
NEW_QUANTITIES = {"cranking_current", "reserve_capacity", "float_charge_voltage", "cyclic_charge_voltage",
                  "equalize_charge_voltage", "short_circuit_current"}


def docs():
    return [c["document"] for c in json.loads(BATCH.read_text(encoding="utf-8"))["candidates"]]


class LeadAcid(unittest.TestCase):
    def test_batch_is_current(self):
        self.assertEqual(BATCH.read_text(encoding="utf-8"), json.dumps(imp.build(), indent=1, ensure_ascii=False) + "\n",
                         "run tools/import_lead_acid_batteries.py")

    def test_every_battery_is_accepted_unchanged(self):
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        by_uid = {d["uid"]: d for d in audit["decisions"]}
        self.assertEqual(len(by_uid), 97)
        for doc in docs():
            d = by_uid[doc["product"]["uid"]]
            raw = (ROOT / d["accepted_file"]).read_bytes()
            # A later revision audit may change named fields (the VARTA records moved
            # to their datasheets on 2026-10-30); everything else is as accepted.
            changed = review_ledger.revised_fields(d["accepted_file"])
            self.assertEqual(review_ledger.without_fields(json.loads(raw), changed),
                             review_ledger.without_fields(doc, changed), d["accepted_file"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             review_ledger.accepted_sha256(d["accepted_file"], d["accepted_document_sha256"]))

    def test_varta_records_cite_their_datasheets(self):
        import revise_varta_datasheets as varta
        self.assertEqual(len(varta.SHEETS), 11)
        weights = 0
        for etn, _size, sha, rendered, weight in varta.SHEETS:
            path = ROOT / "contrib" / "cells" / "clarios" / f"varta-dynamic-efb-{etn}.yaml"
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(review_ledger.revised_fields(str(path.relative_to(ROOT))), varta.FIELDS)
            src = doc["source"]
            self.assertEqual((src["kind"], src["sha256"], src["retrieved_at"]), ("datasheet", sha, rendered))
            self.assertTrue(src["url"].endswith(f"/{etn}K262.pdf"))
            for o in doc["observations"]:
                self.assertEqual(o["locator"]["page"], 2)
            mass = [o for o in doc["observations"] if o["quantity"] == "mass"]
            if weight == "-":
                self.assertEqual(mass, [], "the N50 sheet prints no weight")
                self.assertIn("'Weight filled: -'", src["note"])
            else:
                weights += 1
                self.assertEqual(mass[0]["unit"], "kg")
                self.assertEqual(mass[0]["locator"]["quote"], f"Weight filled: {weight}")
                self.assertAlmostEqual(mass[0]["value"], float(weight.split()[0].replace(",", ".")))
            cca = next(o for o in doc["observations"] if o["quantity"] == "cranking_current")
            self.assertEqual(cca["conditions"]["extra"]["standard"], "not stated", "the sheets print no CCA standard")
        self.assertEqual(weights, 10)

    def test_technology_variant_and_design(self):
        seen = set()
        for doc in docs():
            c = cls.classify(TAX, doc["chemistry"]["designation"])
            self.assertEqual((c["tech"], c["chem"]), ("Lead-acid", "PbO2/Pb"), doc["product"]["uid"])
            seen.add(c["variant"])
            self.assertFalse(cls.designable(TAX, c["tech"]))
        self.assertEqual(seen, {"AGM", "Gel", "Flooded", "EFB"})

    def test_cells_and_monoblocs(self):
        for doc in docs():
            volts = next(o["value"] for o in doc["observations"] if o["quantity"] == "nominal_voltage")
            self.assertEqual(doc["product"]["kind"], "cell" if volts == 2 else "module", doc["product"]["uid"])
            self.assertTrue(doc["product"]["uid"].startswith(doc["product"]["kind"] + "/"))

    def test_hour_rate_capacity_names_its_reference(self):
        for doc in docs():
            for o in doc["observations"]:
                c = o.get("conditions") or {}
                if o["quantity"] != "capacity" or c.get("rate_unit") != "C":
                    continue
                hours = c["extra"]["hour_rate_h"]
                self.assertAlmostEqual(c["rate_value"] * hours, 1.0, places=6)
                self.assertEqual(c["rate_reference_capacity_ah"], o["value"])
                if "cutoff_per_cell_v" in c["extra"] and "voltage_lower_v" in c:
                    volts = next(x["value"] for x in doc["observations"] if x["quantity"] == "nominal_voltage")
                    self.assertAlmostEqual(c["voltage_lower_v"], c["extra"]["cutoff_per_cell_v"] * round(volts / 2), places=6)

    def test_no_resistance_without_a_method(self):
        for doc in docs():
            qs = {o["quantity"] for o in doc["observations"]}
            self.assertNotIn("internal_resistance_dc", qs)
            if "internal_resistance_ac" in qs:
                self.assertEqual(doc["product"]["manufacturer"], "Yuasa")
                self.assertTrue(all(o["conditions"]["frequency_hz"] == 1000 for o in doc["observations"]
                                    if o["quantity"] == "internal_resistance_ac"))

    def test_new_quantities_are_registered_everywhere(self):
        reg = json.loads((ROOT / "json-schema" / "quantity-registry.json").read_text())
        sql = (ROOT / "schema" / "139_lead_acid_quantities.sql").read_text()
        groups = json.loads((ROOT / "web" / "data" / "quantity-groups.json").read_text())["groups"]
        grouped = {q for qs in groups.values() for q in qs}
        for q in NEW_QUANTITIES:
            self.assertIn(q, reg)
            self.assertIn(f"('{q}'", sql)
            self.assertIn(q, grouped)
        self.assertIn("('min', 's', 60, 0, 'time')", sql)
        used = {o["quantity"] for d in docs() for o in d["observations"]}
        self.assertTrue(NEW_QUANTITIES <= used)

    def test_cranking_ratings_keep_their_name(self):
        for doc in docs():
            for o in doc["observations"]:
                if o["quantity"] == "cranking_current":
                    self.assertIn(o["conditions"]["extra"]["rating"], {"CCA", "HCA", "MCA", "MPCA", "MHPCA"})
                    self.assertIn("standard", o["conditions"]["extra"])


if __name__ == "__main__":
    unittest.main()
