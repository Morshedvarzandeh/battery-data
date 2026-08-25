"""Regression tests for patent identity, classification and checked-in data."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_cordis_patents as patents  # noqa: E402


class PatentIdentityTests(unittest.TestCase):
    def test_publication_number_from_official_search_url(self) -> None:
        self.assertEqual(
            patents.publication_from_url(
                "https://worldwide.espacenet.com/patent/search?q=WO2015062985A1"
            ),
            "WO2015062985A1"
        )

    def test_cordis_download_is_not_patent_identity(self) -> None:
        self.assertIsNone(
            patents.publication_from_url(
                "https://ec.europa.eu/research/participants/documents/downloadPublic?id=123"
            )
        )


class PatentClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = json.loads((ROOT / "patents" / "taxonomy.json").read_text())

    def classify(self, title: str) -> dict:
        return patents.classification(title, "", [], self.taxonomy)

    def test_requested_categories(self) -> None:
        fixtures = {
            "Power converter busbar and contactor": "electrical",
            "Mechanical enclosure with crash protection": "mechanical",
            "Software algorithm for state of charge estimation": "software",
            "ASIC sensor on a printed circuit board": "hardware"
        }
        for title, expected in fixtures.items():
            with self.subTest(title=title):
                self.assertIn(expected, self.classify(title)["requested_categories"])


class CheckedInImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base = ROOT / "patents" / "imports" / "cordis-2026-08-21"
        cls.manifest = json.loads((base / "manifest.json").read_text())
        cls.observations = [
            json.loads(line)
            for path in sorted((base / "source-observations").glob("part-*.jsonl"))
            for line in path.read_text().splitlines()
        ]
        cls.candidates = [
            json.loads(line)
            for path in sorted((base / "publication-candidates").glob("part-*.jsonl"))
            for line in path.read_text().splitlines()
        ]

    def test_all_source_rows_are_preserved(self) -> None:
        self.assertEqual(len(self.observations), 1155)
        self.assertEqual(len({row["observation_uid"] for row in self.observations}), 1155)

    def test_publication_duplicates_are_collapsed_without_losing_sources(self) -> None:
        self.assertEqual(len(self.candidates), 255)
        self.assertEqual(sum(row["source_record_count"] for row in self.candidates), 261)
        self.assertEqual(len({row["publication_number"] for row in self.candidates}), 255)

    def test_no_candidate_is_accepted_or_called_a_family(self) -> None:
        self.assertTrue(all(row["review_state"] == "pending_review" for row in self.candidates))
        self.assertTrue(all(row["family"]["status"] == "needs_docdb_resolution" for row in self.candidates))
        self.assertTrue(all(row["legal_status"]["status"] == "unknown" for row in self.candidates))

    def test_all_requested_categories_exist_in_source_queue(self) -> None:
        found = {category for row in self.observations for category in row["classification"]["requested_categories"]}
        self.assertEqual(found, {"electrical", "mechanical", "software", "hardware"})


if __name__ == "__main__":
    unittest.main()
