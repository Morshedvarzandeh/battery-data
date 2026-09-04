"""Regression tests for the EPO patent/company expansion."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_epo_linked_patents as epo  # noqa: E402


class EpoApplicantTests(unittest.TestCase):
    def test_applicant_parser_preserves_country_and_multiple_parties(self) -> None:
        value = "SK On Co., Ltd.@@KR||SK Innovation Co., Ltd.@@KR"
        self.assertEqual(
            epo.parse_applicants(value),
            [
                {"raw_name": "SK On Co., Ltd.", "country": "KR"},
                {"raw_name": "SK Innovation Co., Ltd.", "country": "KR"},
            ],
        )

    def test_natural_person_is_not_silently_made_a_company(self) -> None:
        self.assertTrue(epo.looks_like_person("Jang, Dong Hun"))
        self.assertFalse(epo.looks_like_person("Samsung SDI Co., Ltd."))


class CheckedInEpoImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = ROOT / "patents" / "imports" / "epo-linked-data-2026-09-04"
        cls.manifest = json.loads((cls.base / "manifest.json").read_text())
        cls.candidates = [
            json.loads(line)
            for path in sorted((cls.base / "publication-candidates").glob("part-*.jsonl"))
            for line in path.read_text().splitlines()
        ]
        cls.companies = [
            json.loads(line)
            for path in sorted((cls.base / "companies").glob("part-*.jsonl"))
            for line in path.read_text().splitlines()
        ]
        cls.links = [
            json.loads(line)
            for path in sorted((cls.base / "publication-company-links").glob("part-*.jsonl"))
            for line in path.read_text().splitlines()
        ]

    def test_expansion_exceeds_requested_200_without_exact_duplicates(self) -> None:
        self.assertEqual(len(self.candidates), 801)
        self.assertEqual(len({row["publication_number"] for row in self.candidates}), 801)
        self.assertEqual(self.manifest["counts"]["cross_import_duplicates_excluded"], 0)

    def test_company_profiles_and_links_reconcile(self) -> None:
        self.assertEqual(len(self.companies), 383)
        self.assertEqual(len(self.links), 856)
        self.assertTrue(all(row["patent_portfolio"]["publication_count"] > 0 for row in self.companies))

    def test_requested_technical_domains_are_present(self) -> None:
        requested = {
            category
            for row in self.candidates
            for category in row["classification"]["requested_categories"]
        }
        self.assertEqual(requested, {"electrical", "mechanical", "software", "hardware"})

    def test_nothing_is_accepted_or_represented_as_current_owner(self) -> None:
        self.assertTrue(all(row["review_state"] == "pending_review" for row in self.candidates))
        self.assertTrue(all(row["family"]["status"] == "needs_docdb_resolution" for row in self.candidates))
        self.assertTrue(all(not row["assignees"] for row in self.candidates))
        self.assertTrue(all(row["review_state"] == "pending_review" for row in self.companies))


if __name__ == "__main__":
    unittest.main()
