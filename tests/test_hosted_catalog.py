"""Offline release and query tests; billing is exercised against PostgreSQL in CI."""
import copy
import json
from pathlib import Path
import unittest

from api.hosted.catalog import Catalog, build

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = build(ROOT, "1" * 40)
        cls.catalog = Catalog(cls.snapshot)

    def test_release_contains_exactly_accepted_contributions(self):
        files = {p.relative_to(ROOT).as_posix() for p in (ROOT / "contrib").rglob("*.yaml")}
        self.assertEqual(files, {r["file"] for r in self.catalog.entries})
        self.assertEqual(len(files), len(self.catalog.by_uid))
        pending = json.loads((ROOT / "review/index.json").read_text())["candidates"]
        self.assertTrue(all(c["uid"] not in self.catalog.by_uid for c in pending if c["state"] == "pending_review"))

    def test_original_ratings_and_missing_conditions_survive(self):
        result = self.catalog.detail("cell/samsung-sdi/inr21700-50e")
        values = [o for o in result["record"]["observations"] if o["quantity"] == "capacity"]
        self.assertEqual([4900, 4753], [o["value"] for o in values])
        self.assertEqual([0.2, 1], [o["conditions"]["rate_value"] for o in values])
        pulse = next(o for o in result["record"]["observations"] if o["quantity"] == "max_pulse_discharge_current")
        self.assertIn("pulse_duration_s", pulse["conditions"]["unstated"])
        self.assertIn("/blob/" + "1" * 40 + "/contrib/", result["record_url"])

    def test_modified_snapshot_fails_closed(self):
        changed = copy.deepcopy(self.snapshot)
        changed["records"][0]["record"]["product"]["model_number"] = "tampered"
        with self.assertRaises(ValueError): Catalog(changed)

    def test_snapshot_is_repeatable(self):
        self.assertEqual(self.snapshot, build(ROOT, "1" * 40))


if __name__ == "__main__": unittest.main()
