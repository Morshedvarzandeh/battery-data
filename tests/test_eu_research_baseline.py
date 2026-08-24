"""Literal regression checks for the frozen 2026-08-21 EU corpus baseline.

These assertions intentionally repeat the expected values instead of deriving
them from the fixture. A coordinated edit to the fixture's totals and
partitions must fail until the frozen baseline is deliberately reviewed and
this test is updated with it.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = (
    ROOT / "tests" / "fixtures" / "eu_research" / "baseline-2026-08-21.json"
)

EXPECTED_COUNTS = {
    "project_records": 1608,
    "strict_core_and_ecosystem_projects": 858,
    "integrated_projects": 750,
    "projects_with_indexed_results": 1360,
    "projects_without_indexed_results": 248,
    "source_result_rows": 65486,
    "participation_records": 15050,
    "review_candidates": 2911,
    "excluded_matches": 175,
}

EXPECTED_SCOPE_COUNTS = {
    "BATTERY_CORE": 855,
    "BATTERY_ECOSYSTEM": 3,
    "BATTERY_INTEGRATED": 750,
}

EXPECTED_SOURCE_ROW_ACCESS_COUNTS = {
    "OPEN_FULL_CONTENT": 12567,
    "OPEN_REPOSITORY_LANDING_PAGE": 3079,
    "METADATA_ONLY": 49840,
    "PAYWALLED": 0,
    "RESTRICTED_OR_CONFIDENTIAL": 0,
    "BROKEN_OR_MISSING": 0,
}

EXPECTED_SOURCE_ROW_RELEVANCE_COUNTS = {
    "DIRECT_BATTERY_RESULT": 4223,
    "RESULT_FROM_BATTERY_PROJECT": 61209,
    "UNCLASSIFIED": 54,
}

EXPECTED_PRIMARY_PROJECT_SOURCE_COUNTS = {
    "CORDIS_MODERN_BULK_OR_LIVE": 1411,
    "CORDIS_ARCHIVED_SEARCH": 152,
    "FUNDING_TENDERS_PORTAL": 45,
}

EXPECTED_SOURCE_ROW_TYPE_COUNTS = {
    "COMMUNICATION_DISSEMINATION": 1147,
    "CONFERENCE_PUBLICATION": 9963,
    "DATASET_DATABASE": 116,
    "PROJECT_REPORT_SUMMARY": 1214,
    "HARDWARE_PROTOTYPE_DESIGN": 307,
    "JOURNAL_PUBLICATION": 42416,
    "LCA_TEA_COST_MARKET": 111,
    "MODEL_SIMULATOR_DIGITAL_TWIN": 49,
    "OTHER_PUBLIC_RESULT": 194,
    "PATENT_IP": 1155,
    "PROJECT_ADMINISTRATION": 423,
    "SOFTWARE_SOURCE_CODE": 285,
    "STANDARD_ROADMAP_POLICY": 334,
    "TECHNICAL_DELIVERABLE": 7487,
    "TEST_METHOD_PROTOCOL": 3,
    "TRAINING_EDUCATION": 282,
}

EXPECTED_FRAMEWORK_PROGRAMME_COUNTS = {
    "CEF2027": 1,
    "DIGITAL": 1,
    "ECSC": 1,
    "EDF": 3,
    "EMFF": 1,
    "ENG": 7,
    "ENV": 2,
    "Erasmus+": 2,
    "FP1": 18,
    "FP2": 10,
    "FP3": 24,
    "FP4": 35,
    "FP5": 33,
    "FP6": 9,
    "FP7": 191,
    "H2020": 747,
    "HORIZON": 473,
    "IC": 4,
    "Innovation Fund": 28,
    "Interregional Innovation Investments (I3)": 2,
    "LIFE": 4,
    "PRE_FWP": 9,
    "RFCS2027": 1,
    "SOCPL": 1,
    "Single Market Programme": 1,
}

EXPECTED_SEED_PROJECTS = [
    {"acronym": "SEABAT", "project_id": "research_project/eu-h2020/963560"},
    {
        "acronym": "FLEXSHIP",
        "project_id": "research_project/eu-horizon/101095863",
    },
    {
        "acronym": "HAVEN",
        "project_id": "research_project/eu-horizon/101137636",
    },
    {"acronym": "GHOST", "project_id": "research_project/eu-h2020/770019"},
    {"acronym": "INVADE", "project_id": "research_project/eu-h2020/731148"},
]

EXPECTED_SEED_PROJECT_RESULT_ROWS = {
    "SEABAT": 20,
    "FLEXSHIP": 11,
    "HAVEN": 9,
    "GHOST": 19,
    "INVADE": 68,
}

EXPECTED_INPUT_SNAPSHOT_SHA256 = {
    "final_projects.json": (
        "0173fd74bf5964cb113ec845ba18a40de039d2a338da879f108f80d42099c15e"
    ),
    "final_public_results.json": (
        "50fd5623d47eb685eb60c44d12a59d89957f995116dce2c63866fff2e81572d9"
    ),
    "final_participants.json": (
        "e71488d63c28362b8ce8d5adc42b69471f1ee9dc3376a16333084d52fc14da5c"
    ),
    "final_review_queue.json": (
        "9d76f4c9692453e4ebbe80ace52a77333de832d24344d9cd7b4a9dbec528c8ed"
    ),
    "final_excluded_matches.json": (
        "69c89c99fb25cff17d6a231274836c1d49d67c181de218fb105ce962a012db27"
    ),
}

EXPECTED_INPUT_SNAPSHOT_DATASET_IDS = {
    "final_projects.json": "battery-data/eu-battery-projects",
    "final_public_results.json": "battery-data/eu-battery-public-results",
    "final_participants.json": "battery-data/eu-battery-participations",
    "final_review_queue.json": "battery-data/eu-battery-review-candidates",
    "final_excluded_matches.json": "battery-data/eu-battery-excluded-matches",
}

EXPECTED_BASELINE_SHA256 = (
    "884cb26bb2110fcc9bfc0784e1184b4603367b8b5f1ef1d0ba914f0537dcb035"
)


class FrozenEuResearchBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def test_baseline_identity_is_frozen(self) -> None:
        self.assertEqual(self.baseline["contract_version"], "1.0.0")
        self.assertEqual(
            self.baseline["baseline_id"], "baseline/eu-battery/2026-08-21.1"
        )
        self.assertEqual(
            self.baseline["release_id"], "snapshot/eu-battery/2026-08-21.1"
        )
        self.assertEqual(self.baseline["as_of_date"], "2026-08-21")

    def test_literal_counts_and_partitions_are_frozen(self) -> None:
        self.assertEqual(self.baseline["counts"], EXPECTED_COUNTS)
        self.assertEqual(self.baseline["scope_counts"], EXPECTED_SCOPE_COUNTS)
        self.assertEqual(
            self.baseline["source_row_access_counts"],
            EXPECTED_SOURCE_ROW_ACCESS_COUNTS,
        )
        self.assertEqual(
            self.baseline["source_row_result_relevance_counts"],
            EXPECTED_SOURCE_ROW_RELEVANCE_COUNTS,
        )
        self.assertEqual(
            self.baseline["primary_project_source_counts"],
            EXPECTED_PRIMARY_PROJECT_SOURCE_COUNTS,
        )
        self.assertEqual(
            self.baseline["source_row_result_type_counts"],
            EXPECTED_SOURCE_ROW_TYPE_COUNTS,
        )
        self.assertEqual(
            self.baseline["framework_programme_counts"],
            EXPECTED_FRAMEWORK_PROGRAMME_COUNTS,
        )

    def test_partitions_reconcile_with_frozen_parent_totals(self) -> None:
        project_total = EXPECTED_COUNTS["project_records"]
        source_row_total = EXPECTED_COUNTS["source_result_rows"]
        self.assertEqual(sum(EXPECTED_SCOPE_COUNTS.values()), project_total)
        self.assertEqual(
            sum(EXPECTED_PRIMARY_PROJECT_SOURCE_COUNTS.values()), project_total
        )
        self.assertEqual(
            sum(EXPECTED_FRAMEWORK_PROGRAMME_COUNTS.values()), project_total
        )
        self.assertEqual(
            sum(EXPECTED_SOURCE_ROW_ACCESS_COUNTS.values()), source_row_total
        )
        self.assertEqual(
            sum(EXPECTED_SOURCE_ROW_RELEVANCE_COUNTS.values()), source_row_total
        )
        self.assertEqual(
            sum(EXPECTED_SOURCE_ROW_TYPE_COUNTS.values()), source_row_total
        )
        self.assertEqual(
            EXPECTED_COUNTS["projects_with_indexed_results"]
            + EXPECTED_COUNTS["projects_without_indexed_results"],
            project_total,
        )
        self.assertEqual(
            EXPECTED_SCOPE_COUNTS["BATTERY_CORE"]
            + EXPECTED_SCOPE_COUNTS["BATTERY_ECOSYSTEM"],
            EXPECTED_COUNTS["strict_core_and_ecosystem_projects"],
        )

    def test_seed_projects_and_result_rows_are_frozen(self) -> None:
        self.assertEqual(self.baseline["seed_projects"], EXPECTED_SEED_PROJECTS)
        self.assertEqual(
            self.baseline["seed_project_result_rows"],
            EXPECTED_SEED_PROJECT_RESULT_ROWS,
        )

    def test_coverage_exceptions_are_frozen(self) -> None:
        self.assertEqual(
            self.baseline["coverage_assertions"],
            {
                "lc_bat_projects": {"expected": 40, "included": 40},
                "battery_labelled_topic_projects": {
                    "expected": 161,
                    "included": 161,
                },
                "euroscivoc_electric_batteries": {
                    "expected": 280,
                    "included": 279,
                    "excluded": 1,
                    "documented_exception": "research_project/eu-h2020/946845",
                },
            },
        )

    def test_input_snapshot_hashes_are_frozen(self) -> None:
        self.assertEqual(
            self.baseline["input_snapshot_sha256"],
            EXPECTED_INPUT_SNAPSHOT_SHA256,
        )
        self.assertEqual(
            self.baseline["input_snapshot_dataset_ids"],
            EXPECTED_INPUT_SNAPSHOT_DATASET_IDS,
        )

    def test_baseline_file_digest_is_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(BASELINE_PATH.read_bytes()).hexdigest(),
            EXPECTED_BASELINE_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
