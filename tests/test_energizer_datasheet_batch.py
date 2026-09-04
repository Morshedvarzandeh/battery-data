"""Integrity checks for the September 2026 official datasheet expansion."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "review" / "candidates" / "energizer"


class EnergizerDatasheetBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = sorted(CANDIDATES.glob("*.yaml"))
        cls.documents = [json.loads(path.read_text()) for path in cls.paths]

    def test_batch_has_31_distinct_products(self) -> None:
        self.assertEqual(len(self.documents), 31)
        uids = [doc["product"]["uid"] for doc in self.documents]
        self.assertEqual(len(uids), len(set(uids)))

    def test_every_source_is_the_hashed_official_pdf(self) -> None:
        for doc in self.documents:
            source = doc["source"]
            self.assertTrue(source["url"].startswith("https://data.energizer.com/pdfs/"))
            self.assertRegex(source["sha256"], re.compile(r"^[0-9a-f]{64}$"))
            self.assertFalse(source["redistributable"])
            self.assertEqual(source["kind"], "datasheet")

    def test_only_extracted_facts_are_committed(self) -> None:
        self.assertFalse(any(ROOT.rglob("*.pdf")))


if __name__ == "__main__":
    unittest.main()

