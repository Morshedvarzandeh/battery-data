"""Contract and fail-closed release tests for the EU research corpus."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_eu_research_release as contract  # noqa: E402


RECORD_SCHEMA_PATH = ROOT / "json-schema" / "eu-research-record.schema.json"
RELEASE_SCHEMA_PATH = ROOT / "json-schema" / "eu-research-release.schema.json"
OBSERVATION_SCHEMA_PATH = (
    ROOT / "json-schema" / "eu-research-observation.schema.json"
)
FIXTURE = ROOT / "tests" / "fixtures" / "eu_research" / "minimal" / "manifest.json"
BASELINE = (
    ROOT / "tests" / "fixtures" / "eu_research" / "baseline-2026-08-21.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class EuResearchContractTests(unittest.TestCase):
    def test_schemas_are_valid_draft_2020_12(self) -> None:
        for path in (
            RECORD_SCHEMA_PATH,
            RELEASE_SCHEMA_PATH,
            OBSERVATION_SCHEMA_PATH,
        ):
            Draft202012Validator.check_schema(load_json(path))

    def test_every_committed_eu_release_manifest_passes(self) -> None:
        roots = [
            ROOT / "tests" / "fixtures" / "eu_research",
            ROOT / "releases" / "eu_research",
        ]
        manifests = sorted(
            manifest
            for release_root in roots
            if release_root.exists()
            for manifest in release_root.rglob("manifest.json")
        )
        self.assertTrue(manifests)
        for manifest in manifests:
            with self.subTest(manifest=manifest):
                self.assertEqual(contract.validate_snapshot(manifest), [])

    def test_identity_vectors_are_stable_and_recomputed(self) -> None:
        schema = load_json(RECORD_SCHEMA_PATH)
        namespaces = schema["$defs"]["projectData"]["properties"][
            "programme_namespace"
        ]["enum"]
        self.assertEqual(set(namespaces), set(contract.PROGRAMME_LABELS))

        result_data = load_records(FIXTURE.parent / "results.ndjson")[0]["data"]
        result_id = contract.deterministic_result_id(result_data)
        self.assertEqual(
            result_id,
            "research_result/682a5c3a-b4ba-5907-9c4b-2ec3f0474506",
        )
        self.assertEqual(
            contract.deterministic_project_result_id(
                "research_project/eu-h2020/963560", result_id
            ),
            "project_result/d45587ed-ab43-5dc4-871d-da21beb18b57",
        )
        self.assertEqual(
            contract.deterministic_participation_id(
                "research_project/eu-h2020/963560", "org/eu-pic/996435896"
            ),
            "project_participation/abb5f7f1-7368-524d-b370-021c9025a056",
        )
        self.assertEqual(
            contract.canonical_project_id("eu-horizon", " ABC 1 "),
            "research_project/eu-horizon/ABC%201",
        )
        self.assertEqual(
            contract.deterministic_review_id("research_project/eu-fp7/236667"),
            "research_review/be4db9e6-918f-5472-a3c2-0a3bb132f310",
        )
        self.assertEqual(
            contract.deterministic_exclusion_id(
                "research_project/eu-h2020/101007194"
            ),
            "research_exclusion/bd134314-d7ef-5733-b512-914bdd7f2c83",
        )

        result = load_records(FIXTURE.parent / "results.ndjson")[0]
        for claim in result["provenance"]:
            self.assertEqual(
                claim["claim_id"],
                contract.deterministic_claim_id(result["record_id"], claim),
            )

    def test_source_record_collision_has_one_identity_and_must_be_quarantined(self) -> None:
        data = {
            "identity_basis": "SOURCE_RECORD",
            "identity_value": "20100478",
            "source_result_ids": ["20100478"],
            "identity_project_id": "research_project/eu-fp7/231962",
            "identity_source_system": "CORDIS_BULK",
            "identity_source_dataset": "FP7 legal basis/IPR",
        }
        first = {**data, "title": "Process for printed circuit boards recycling"}
        second = {**data, "title": "Recovery of base and precious metals"}
        self.assertEqual(
            contract.deterministic_result_id(first),
            contract.deterministic_result_id(second),
        )

    def test_observation_timestamps_do_not_change_content_hash(self) -> None:
        record = load_records(FIXTURE.parent / "results.ndjson")[0]
        expected = contract.canonical_record_hash(record)
        changed = copy.deepcopy(record)
        changed["provenance"][0]["retrieved_at"] = "2026-08-22T00:00:00Z"
        changed["data"]["access_verified_at"] = "2026-08-22T00:00:00Z"
        self.assertEqual(contract.canonical_record_hash(changed), expected)
        changed["data"]["title"] += " corrected"
        self.assertNotEqual(contract.canonical_record_hash(changed), expected)

        relation = load_records(FIXTURE.parent / "project_results.ndjson")[0]
        relation_expected = contract.canonical_record_hash(relation)
        relation["provenance"][1]["review"]["reviewed_at"] = (
            "2026-08-22T00:00:00Z"
        )
        self.assertEqual(contract.canonical_record_hash(relation), relation_expected)

    def test_project_result_and_participation_id_mismatches_are_rejected(self) -> None:
        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["data"]["official_project_id"] = "999999"
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "project ID does not match project data")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["data"]["framework_programme"] = "HORIZON"
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "programme label does not match namespace")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            results[0]["data"]["identity_value"] = "10.1000/not-the-doi"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "cannot recompute RESULT ID")

        with self.fixture_copy() as target:
            relations = load_records(target / "project_results.ndjson")
            relations[0]["data"]["project_id"] = (
                "research_project/eu-h2020/731148"
            )
            relations[0]["content_hash"] = contract.canonical_record_hash(relations[0])
            self.write_records_and_refresh(
                target, "project_results.ndjson", relations
            )
            self.assert_has_error(target, "project-result ID is not deterministic")

        with self.fixture_copy() as target:
            rows = load_records(target / "participations.ndjson")
            rows[0]["data"]["project_id"] = "research_project/eu-h2020/731148"
            rows[0]["content_hash"] = contract.canonical_record_hash(rows[0])
            self.write_records_and_refresh(target, "participations.ndjson", rows)
            self.assert_has_error(target, "participation ID is not deterministic")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            seabat = next(
                row for row in projects if row["data"].get("acronym") == "SEABAT"
            )
            seabat["data"]["coordinator_org_id"] = "org/eu-pic/000000000"
            seabat["content_hash"] = contract.canonical_record_hash(seabat)
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "coordinator contradicts")

    def test_provenance_snapshot_host_pointer_and_review_rules_are_enforced(self) -> None:
        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["provenance"][0]["source_url"] = "https://evil.example/x"
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "source host is not allowed")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            claim = projects[0]["provenance"][0]
            claim["asserted_fields"] = ["/data/not_a_field"]
            claim["claim_id"] = contract.deterministic_claim_id(
                projects[0]["record_id"], claim
            )
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "asserted field does not resolve")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            claim = projects[0]["provenance"][0]
            claim["source_snapshot_id"] = "source_snapshot/cordis/missing"
            claim["claim_id"] = contract.deterministic_claim_id(
                projects[0]["record_id"], claim
            )
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "unknown source_snapshot_id")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            claim = projects[0]["provenance"][0]
            claim["source_artifact_id"] = "source_artifact/cordis/missing"
            claim["claim_id"] = contract.deterministic_claim_id(
                projects[0]["record_id"], claim
            )
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "unknown source_artifact_id")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["provenance"] = [projects[0]["provenance"][0]]
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "record schema")

    def test_field_rights_pointers_and_open_licence_evidence_are_enforced(self) -> None:
        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            assertion = results[0]["rights"]["field_assertions"][0]
            assertion["applies_to"] = ["/data/not_a_field"]
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "rights pointer does not resolve")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            assertion = results[0]["rights"]["field_assertions"][0]
            assertion["metadata_redistribution"] = "PROHIBITED"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "public data field is not redistributable")

        schema = load_json(RECORD_SCHEMA_PATH)
        result = load_records(FIXTURE.parent / "results.ndjson")[0]
        assertion = result["rights"]["field_assertions"][0]
        assertion["source_content_licence_status"] = "OPEN_LICENSE_VERIFIED"
        assertion["licence"] = None
        assertion["licence_url"] = None
        errors = list(Draft202012Validator(schema).iter_errors(result))
        self.assertTrue(errors)

    def test_approved_release_requires_exact_gates_and_hashed_sources(self) -> None:
        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["status"] = "APPROVED"
            manifest["quality_gates"] = manifest["quality_gates"][:1]
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "manifest schema")

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["status"] = "APPROVED"
            duplicate = copy.deepcopy(manifest["quality_gates"][0])
            duplicate["evidence"] = "different text, same gate"
            manifest["quality_gates"][-1] = duplicate
            self.write_manifest(target, manifest)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(any("duplicate quality gate" in item for item in errors))
            self.assertTrue(any("missing gates" in item for item in errors))

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["status"] = "APPROVED"
            for source in manifest["source_snapshots"]:
                source["snapshot_sha256"] = "sha256:" + "a" * 64
            self.write_manifest(target, manifest)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(
                any("source snapshot SHA-256 mismatch" in item for item in errors)
            )
            self.assertTrue(any("artifact lacks a hash" in item for item in errors))
            self.assertTrue(any("lacks retained bytes" in item for item in errors))

    def test_visibility_schema_and_record_schema_digest_are_enforced(self) -> None:
        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            review = next(
                item
                for item in manifest["record_sets"]
                if item["record_type"] == "REVIEW_CANDIDATE"
            )
            review["visibility"] = "PUBLIC"
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "manifest schema")

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["record_sets"][0]["record_schema_sha256"] = "0" * 64
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "record schema SHA-256 mismatch")

    def test_result_identity_precedence_and_artifact_dataset_binding(self) -> None:
        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            result = results[0]
            result["data"]["identity_basis"] = "FINGERPRINT"
            result["data"]["identity_project_id"] = (
                "research_project/eu-h2020/963560"
            )
            result["data"]["identity_value"] = contract.normalize_fingerprint_title(
                result["data"]["title"]
            )
            result["content_hash"] = contract.canonical_record_hash(result)
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "identity precedence requires DOI")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            claim = results[0]["provenance"][0]
            claim["source_dataset"] = "eurio/project-result"
            claim["claim_id"] = contract.deterministic_claim_id(
                results[0]["record_id"], claim
            )
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "source dataset is not declared by artifact")

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["source_snapshots"][0]["artifacts"][0]["dataset_ids"].append(
                "cordis/adversarial-remint"
            )
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "not in the v1 registry")

        with self.fixture_copy() as target:
            # A registry check alone is insufficient when one artifact declares
            # several registered datasets: relabelling the same row would remint
            # a SOURCE_RECORD identity. Identity-bearing artifacts fail closed
            # unless their sole dataset is the one used in the UUID seed.
            results = load_records(target / "results.ndjson")
            result = results[0]
            result["data"].update(
                {
                    "doi": None,
                    "official_result_uri": None,
                    "identity_basis": "SOURCE_RECORD",
                    "identity_project_id": "research_project/eu-h2020/963560",
                    "identity_source_system": "CORDIS_BULK",
                    "identity_source_dataset": "cordis/fp7-projects",
                    "identity_value": "963560_1327195_PUBLI",
                }
            )
            result["record_id"] = contract.deterministic_result_id(result["data"])
            claim = result["provenance"][0]
            claim["source_dataset"] = "cordis/fp7-projects"
            claim["claim_id"] = contract.deterministic_claim_id(
                result["record_id"], claim
            )
            result["content_hash"] = contract.canonical_record_hash(result)
            self.write_records_and_refresh(target, "results.ndjson", results)

            relations = load_records(target / "project_results.ndjson")
            relation = relations[0]
            relation["data"]["result_id"] = result["record_id"]
            relation["record_id"] = contract.deterministic_project_result_id(
                relation["data"]["project_id"], result["record_id"]
            )
            for relation_claim in relation["provenance"]:
                relation_claim["claim_id"] = contract.deterministic_claim_id(
                    relation["record_id"], relation_claim
                )
            relation["content_hash"] = contract.canonical_record_hash(relation)
            self.write_records_and_refresh(
                target, "project_results.ndjson", relations
            )
            self.assert_has_error(target, "identity artifact is not single-dataset")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            results[0]["data"]["battery_relevance"] = "DIRECT_BATTERY_RESULT"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "record schema")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            duplicate = copy.deepcopy(results[0])
            duplicate["data"]["doi"] = "10.1000/distinct-doi"
            duplicate["data"]["identity_value"] = "10.1000/distinct-doi"
            duplicate["data"]["official_result_uri"] = None
            duplicate["record_id"] = contract.deterministic_result_id(
                duplicate["data"]
            )
            for claim in duplicate["provenance"]:
                claim["claim_id"] = contract.deterministic_claim_id(
                    duplicate["record_id"], claim
                )
            duplicate["content_hash"] = contract.canonical_record_hash(duplicate)
            results.append(duplicate)
            self.write_records_and_refresh(target, "results.ndjson", results)

            relations = load_records(target / "project_results.ndjson")
            duplicate_relation = copy.deepcopy(relations[0])
            duplicate_relation["data"]["result_id"] = duplicate["record_id"]
            duplicate_relation["record_id"] = contract.deterministic_project_result_id(
                duplicate_relation["data"]["project_id"], duplicate["record_id"]
            )
            for claim in duplicate_relation["provenance"]:
                claim["claim_id"] = contract.deterministic_claim_id(
                    duplicate_relation["record_id"], claim
                )
            duplicate_relation["content_hash"] = contract.canonical_record_hash(
                duplicate_relation
            )
            relations.append(duplicate_relation)
            self.write_records_and_refresh(
                target, "project_results.ndjson", relations
            )
            manifest = load_json(target / "manifest.json")
            manifest["summary"]["results"] = 2
            manifest["summary"]["project_result_links"] = 2
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "source result tuple is reused")

    def test_access_evidence_and_temporal_bounds_are_enforced(self) -> None:
        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            data = results[0]["data"]
            data.update(
                {
                    "access_status": "OPEN_FULL_CONTENT",
                    "access_verified_at": "2026-08-21T00:00:00Z",
                    "access_http_status": 204,
                    "access_content_type": "application/pdf",
                    "access_final_url": data["direct_url"],
                    "access_anonymous": True,
                    "access_check_method": "GET",
                    "access_evidence_kind": "SUBSTANTIVE_FILE",
                }
            )
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "incompatible HTTP status")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            data = results[0]["data"]
            data.update(
                {
                    "access_status": "OPEN_FULL_CONTENT",
                    "access_verified_at": "2026-08-21T00:00:00Z",
                    "access_http_status": 200,
                    "access_content_type": "application/problem+json; charset=utf-8",
                    "access_final_url": data["direct_url"],
                    "access_anonymous": True,
                    "access_check_method": "GET",
                    "access_evidence_kind": "OFFICIAL_FULL_NARRATIVE",
                }
            )
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "returned an error media type")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            results[0]["data"]["access_verified_at"] = "2026-08-21T21:03:27Z"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "access verification is after generated_at")

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            claim = results[0]["provenance"][0]
            claim["retrieved_at"] = "2026-08-21T21:03:27Z"
            claim["claim_id"] = contract.deterministic_claim_id(
                results[0]["record_id"], claim
            )
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "claim retrieval is after generated_at")

        with self.fixture_copy() as target:
            relations = load_records(target / "project_results.ndjson")
            claim = relations[0]["provenance"][1]
            claim["review"]["reviewed_at"] = "2026-08-20T23:59:59Z"
            relations[0]["content_hash"] = contract.canonical_record_hash(relations[0])
            self.write_records_and_refresh(
                target, "project_results.ndjson", relations
            )
            self.assert_has_error(target, "claim review predates retrieval")

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["source_snapshots"][0]["artifacts"][0]["retrieved_at"] = (
                "2026-08-21T21:03:27Z"
            )
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "source artifact retrieval is after")

    def test_coordinator_and_pic_consistency_are_bidirectional(self) -> None:
        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            seabat = next(
                row for row in projects if row["data"].get("acronym") == "SEABAT"
            )
            seabat["data"]["coordinator_org_id"] = None
            seabat["content_hash"] = contract.canonical_record_hash(seabat)
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "coordinator contradicts")

        with self.fixture_copy() as target:
            participations = load_records(target / "participations.ndjson")
            extra = copy.deepcopy(participations[0])
            extra["data"]["organization_id"] = "org/eu-pic/000000001"
            extra["data"]["source_organization_id"] = "000000001"
            extra["record_id"] = contract.deterministic_participation_id(
                extra["data"]["project_id"], extra["data"]["organization_id"]
            )
            for claim in extra["provenance"]:
                claim["claim_id"] = contract.deterministic_claim_id(
                    extra["record_id"], claim
                )
            extra["content_hash"] = contract.canonical_record_hash(extra)
            participations.append(extra)
            self.write_records_and_refresh(
                target, "participations.ndjson", participations
            )
            manifest = load_json(target / "manifest.json")
            manifest["summary"]["participations"] = 2
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "coordinator contradicts")

        with self.fixture_copy() as target:
            participations = load_records(target / "participations.ndjson")
            participation = participations[0]
            participation["data"]["source_organization_id"] = "000000001"
            participation["content_hash"] = contract.canonical_record_hash(
                participation
            )
            self.write_records_and_refresh(
                target, "participations.ndjson", participations
            )
            self.assert_has_error(target, "not the declared EU PIC")

        with self.fixture_copy() as target:
            participations = load_records(target / "participations.ndjson")
            participation = participations[0]
            participation["data"]["organization_id"] = "org/eu-pic/000000001"
            participation["data"]["source_organization_id"] = "000000001"
            participation["record_id"] = contract.deterministic_participation_id(
                participation["data"]["project_id"],
                participation["data"]["organization_id"],
            )
            for claim in participation["provenance"]:
                claim["claim_id"] = contract.deterministic_claim_id(
                    participation["record_id"], claim
                )
            participation["content_hash"] = contract.canonical_record_hash(
                participation
            )
            self.write_records_and_refresh(
                target, "participations.ndjson", participations
            )
            projects = load_records(target / "projects.ndjson")
            seabat = next(
                row for row in projects if row["data"].get("acronym") == "SEABAT"
            )
            seabat["data"]["coordinator_org_id"] = "org/eu-pic/000000001"
            seabat["content_hash"] = contract.canonical_record_hash(seabat)
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "PIC lacks a bound official-source claim")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["data"]["framework_programme"] = None
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "record schema")

    def test_sanitization_and_parent_classification_pointers_fail_closed(self) -> None:
        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            token = "github_pat_" + "A" * 40
            results[0]["data"]["description"] = f"accidental credential {token}"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(any("credential or personal contact" in e for e in errors))
            self.assertFalse(any(token in e for e in errors))

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            email = "private.person@example.org"
            results[0]["data"]["description"] = f"contact {email}"
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(any("credential or personal contact" in e for e in errors))
            self.assertFalse(any(email in e for e in errors))

        with self.fixture_copy() as target:
            results = load_records(target / "results.ndjson")
            results[0]["data"]["description"] = (
                "Private mobile: +32 470 12 34 56"
            )
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "credential or personal contact")

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["quality_gates"][0]["evidence"] = (
                "accidental " + "xox" + "b-1234567890-abcdefghijklmnop"
            )
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "leaked into manifest")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            projects[0]["data"]["grant_doi"] = (
                "10.3030/github_pat_" + "A" * 40
            )
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "credential or personal contact")

        with self.fixture_copy() as target:
            projects = load_records(target / "projects.ndjson")
            source_claim = projects[0]["provenance"][0]
            source_claim["asserted_fields"] = ["/data"]
            source_claim["claim_id"] = contract.deterministic_claim_id(
                projects[0]["record_id"], source_claim
            )
            projects[0]["content_hash"] = contract.canonical_record_hash(projects[0])
            self.write_records_and_refresh(target, "projects.ndjson", projects)
            self.assert_has_error(target, "non-curator source asserts")

    def test_retained_source_artifact_bytes_are_verified(self) -> None:
        with self.fixture_copy() as target:
            retained = target / "source_artifacts"
            retained.mkdir()
            artifact_path = retained / "cordis.bin"
            payload = b"synthetic retained source bytes\n"
            artifact_path.write_bytes(payload)
            manifest = load_json(target / "manifest.json")
            artifact = manifest["source_snapshots"][0]["artifacts"][0]
            artifact["retained_path"] = "source_artifacts/cordis.bin"
            artifact["byte_size"] = len(payload)
            artifact["sha256"] = "sha256:" + hashlib.sha256(payload).hexdigest()
            self.write_manifest(target, manifest)
            self.assertEqual(contract.validate_snapshot(target / "manifest.json"), [])

            artifact_path.write_bytes(payload + b"tampered")
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(any("source artifact file SHA-256 mismatch" in e for e in errors))
            self.assertTrue(any("source artifact byte-size mismatch" in e for e in errors))

        with self.fixture_copy() as target:
            source_dir = target / "source_artifacts"
            source_dir.mkdir()
            copied_output = source_dir / "copied-results.ndjson"
            payload = (target / "results.ndjson").read_bytes()
            copied_output.write_bytes(payload)
            manifest = load_json(target / "manifest.json")
            artifact = manifest["source_snapshots"][0]["artifacts"][0]
            artifact["retained_path"] = (
                "source_artifacts/copied-results.ndjson"
            )
            artifact["byte_size"] = len(payload)
            artifact["sha256"] = "sha256:" + hashlib.sha256(payload).hexdigest()
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "bytes alias generated release data")

        for alias in (
            "source_artifacts//shared.bin",
            "source_artifacts/./shared.bin",
        ):
            with self.subTest(alias=alias), self.fixture_copy() as target:
                retained = target / "source_artifacts"
                retained.mkdir()
                manifest = load_json(target / "manifest.json")
                manifest["status"] = "APPROVED"
                for source_index, snapshot in enumerate(
                    manifest["source_snapshots"]
                ):
                    for artifact_index, artifact in enumerate(snapshot["artifacts"]):
                        if source_index < 2:
                            retained_path = (
                                "source_artifacts/shared.bin"
                                if source_index == 0
                                else alias
                            )
                            payload = b"shared retained source bytes\n"
                        else:
                            retained_path = (
                                f"source_artifacts/{source_index}-{artifact_index}.bin"
                            )
                            payload = (
                                f"retained source {source_index}-{artifact_index}\n"
                            ).encode("utf-8")
                        artifact_path = target / retained_path
                        if not artifact_path.exists():
                            artifact_path.write_bytes(payload)
                        artifact["retained_path"] = retained_path
                        artifact["byte_size"] = len(payload)
                        artifact["sha256"] = (
                            "sha256:" + hashlib.sha256(payload).hexdigest()
                        )
                    snapshot["snapshot_sha256"] = (
                        contract.canonical_source_snapshot_hash(snapshot)
                    )
                self.write_manifest(target, manifest)
                self.assert_has_error(target, "retained_path is not canonical")

        with self.fixture_copy() as target:
            _manifest_path, asset_path = self.add_valid_asset(target)
            source_dir = target / "source_artifacts"
            source_dir.mkdir()
            source_alias = source_dir / "asset-alias.pdf"
            source_alias.symlink_to(asset_path)
            payload = asset_path.read_bytes()
            manifest = load_json(target / "manifest.json")
            artifact = manifest["source_snapshots"][0]["artifacts"][0]
            artifact["retained_path"] = "source_artifacts/asset-alias.pdf"
            artifact["byte_size"] = len(payload)
            artifact["sha256"] = "sha256:" + hashlib.sha256(payload).hexdigest()
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "resolves outside source_artifacts/")

        with self.fixture_copy() as target:
            _manifest_path, asset_path = self.add_valid_asset(target)
            (target / "source_artifacts").symlink_to(
                asset_path.parent, target_is_directory=True
            )
            payload = asset_path.read_bytes()
            manifest = load_json(target / "manifest.json")
            artifact = manifest["source_snapshots"][0]["artifacts"][0]
            artifact["retained_path"] = "source_artifacts/example.pdf"
            artifact["byte_size"] = len(payload)
            artifact["sha256"] = "sha256:" + hashlib.sha256(payload).hexdigest()
            self.write_manifest(target, manifest)
            self.assert_has_error(
                target, "source_artifacts/ itself resolves through a symlink"
            )

        with self.fixture_copy() as target:
            _manifest_path, asset_path = self.add_valid_asset(target)
            source_dir = target / "source_artifacts"
            source_dir.mkdir()
            copied_asset = source_dir / "copied-asset.pdf"
            payload = asset_path.read_bytes()
            copied_asset.write_bytes(payload)
            manifest = load_json(target / "manifest.json")
            artifact = manifest["source_snapshots"][0]["artifacts"][0]
            artifact["retained_path"] = "source_artifacts/copied-asset.pdf"
            artifact["byte_size"] = len(payload)
            artifact["sha256"] = "sha256:" + hashlib.sha256(payload).hexdigest()
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "result asset aliases retained source bytes")

    def test_full_snapshot_baseline_is_pinned_and_reconciled(self) -> None:
        with self.fixture_copy() as target:
            baseline = self.configure_full_snapshot(target)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(any("baseline count mismatch" in e for e in errors))
            self.assertTrue(any("project scope counts" in e for e in errors))
            self.assertTrue(any("not derived from ledger" in e for e in errors))
            self.assertNotIn("canonical_counts", baseline)

        with self.fixture_copy() as target:
            baseline = self.configure_full_snapshot(target)
            baseline["counts"]["project_records"] = 2
            baseline_path = target / "baseline.json"
            baseline_path.write_text(
                json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest = load_json(target / "manifest.json")
            manifest["baseline"]["sha256"] = hashlib.sha256(
                baseline_path.read_bytes()
            ).hexdigest()
            self.write_manifest(target, manifest)
            self.assert_has_error(target, "not the registered immutable value")

        with self.fixture_copy() as target:
            self.configure_full_snapshot(target, status="APPROVED")
            self.assert_has_error(
                target, "baseline canonical result/link counts are not frozen"
            )

    def test_strict_ndjson_and_malformed_manifests_fail_closed(self) -> None:
        with self.fixture_copy() as target:
            path = target / "results.ndjson"
            self.write_raw_and_refresh(
                target,
                "results.ndjson",
                path.read_bytes().replace(b"\n", b"\r\n"),
            )
            self.assert_has_error(target, "CR is forbidden")

        with self.fixture_copy() as target:
            path = target / "results.ndjson"
            self.write_raw_and_refresh(
                target, "results.ndjson", b"\xef\xbb\xbf" + path.read_bytes()
            )
            self.assert_has_error(target, "BOM is forbidden")

        with self.fixture_copy() as target:
            path = target / "results.ndjson"
            raw = path.read_bytes().replace(
                b'"record_type":"RESULT"',
                b'"record_type":"RESULT","record_type":"RESULT"',
                1,
            )
            self.write_raw_and_refresh(target, "results.ndjson", raw)
            self.assert_has_error(target, "duplicate JSON object key")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text("[]", encoding="utf-8")
            errors = contract.validate_snapshot(path)
            self.assertTrue(errors)
            self.assertFalse(any("Traceback" in item for item in errors))

        with self.fixture_copy() as target:
            manifest = load_json(target / "manifest.json")
            manifest["record_sets"] = "wrong"
            self.write_manifest(target, manifest)
            errors = contract.validate_snapshot(target / "manifest.json")
            self.assertTrue(errors)
            self.assertFalse(any("Traceback" in item for item in errors))

    def test_valid_asset_then_tampering_and_dangling_links_are_rejected(self) -> None:
        with self.fixture_copy() as target:
            manifest_path, asset_path = self.add_valid_asset(target)
            self.assertEqual(contract.validate_snapshot(manifest_path), [])
            asset_path.write_bytes(asset_path.read_bytes() + b"tampered")
            errors = contract.validate_snapshot(manifest_path)
            self.assertTrue(
                any("result-asset file SHA-256 mismatch" in item for item in errors)
            )
            self.assertTrue(
                any("result-asset byte-size mismatch" in item for item in errors)
            )

        with self.fixture_copy() as target:
            manifest_path, _asset_path = self.add_valid_asset(target)
            results = load_records(target / "results.ndjson")
            results[0]["data"]["asset_ids"] = []
            results[0]["content_hash"] = contract.canonical_record_hash(results[0])
            self.write_records_and_refresh(target, "results.ndjson", results)
            self.assert_has_error(target, "result does not list its bundled asset")

    @staticmethod
    def write_manifest(target: Path, manifest: dict[str, Any]) -> None:
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def write_records_and_refresh(
        cls, target: Path, relative_path: str, records: list[dict[str, Any]]
    ) -> None:
        payload = "".join(
            json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
            for record in sorted(records, key=lambda item: item["record_id"])
        ).encode("utf-8")
        cls.write_raw_and_refresh(target, relative_path, payload)

    @classmethod
    def write_raw_and_refresh(
        cls, target: Path, relative_path: str, payload: bytes
    ) -> None:
        (target / relative_path).write_bytes(payload)
        manifest = load_json(target / "manifest.json")
        record_set = next(
            item for item in manifest["record_sets"] if item["path"] == relative_path
        )
        record_set["record_count"] = len(payload.splitlines())
        record_set["byte_size"] = len(payload)
        record_set["sha256"] = hashlib.sha256(payload).hexdigest()
        cls.write_manifest(target, manifest)

    @staticmethod
    def add_valid_asset(target: Path) -> tuple[Path, Path]:
        assets_dir = target / "assets"
        assets_dir.mkdir()
        asset_path = assets_dir / "example.pdf"
        asset_bytes = b"%PDF-1.4\n% synthetic contract fixture\n"
        asset_path.write_bytes(asset_bytes)
        digest = hashlib.sha256(asset_bytes).hexdigest()
        asset_id = f"result_asset/sha256/{digest}"

        results = load_records(target / "results.ndjson")
        result = results[0]
        result["data"]["access_status"] = "OPEN_FULL_CONTENT"
        result["data"]["access_verified_at"] = "2026-08-21T00:00:00Z"
        result["data"]["access_http_status"] = 200
        result["data"]["access_content_type"] = "application/pdf"
        result["data"]["access_final_url"] = (
            "https://cordis.europa.eu/project/id/963560/results"
        )
        result["data"]["access_anonymous"] = True
        result["data"]["access_check_method"] = "GET"
        result["data"]["access_evidence_kind"] = "SUBSTANTIVE_FILE"
        result["data"]["asset_ids"] = [asset_id]
        result["content_hash"] = contract.canonical_record_hash(result)
        EuResearchContractTests.write_records_and_refresh(
            target, "results.ndjson", results
        )

        asset: dict[str, Any] = {
            "contract_version": "1.0.0",
            "release_id": result["release_id"],
            "record_type": "RESULT_ASSET",
            "record_id": asset_id,
            "record_version": 1,
            "record_lifecycle_state": "CURRENT",
            "curation_state": "ACCEPTED",
            "first_seen_on": "2026-08-21",
            "last_seen_on": "2026-08-21",
            "content_hash": "sha256:" + "0" * 64,
            "provenance": [
                {
                    "claim_id": "claim/00000000-0000-5000-8000-000000000000",
                    "source_snapshot_id": "source_snapshot/cordis/bulk-2026-08",
                    "source_artifact_id": (
                        "source_artifact/cordis/bulk-2026-08/fixture-observation"
                    ),
                    "source_system": "CORDIS_BULK",
                    "source_dataset": "cordis/h2020-project-publications",
                    "source_record_id": "963560_fixture_asset",
                    "source_url": "https://cordis.europa.eu/project/id/963560/results",
                    "retrieved_at": "2026-08-21T00:00:00Z",
                    "extraction_method": "RESULT_PAGE",
                    "evidence_locator": "synthetic contract fixture",
                    "asserted_fields": ["/data/result_id", "/data/source_url"],
                    "payload_sha256": None,
                }
            ],
            "rights": {
                "field_assertions": [
                    {
                        "applies_to": ["/data"],
                        "metadata_redistribution": "ALLOWED",
                        "source_content_licence_status": "OPEN_LICENSE_VERIFIED",
                        "source_asset_redistribution": "ALLOWED",
                        "licence": "CC-BY-4.0",
                        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                        "evidence_url": "https://creativecommons.org/licenses/by/4.0/",
                        "rights_note": "Synthetic test bytes only.",
                    }
                ],
                "record_note": "Synthetic asset used only to test integrity checks.",
            },
            "data": {
                "result_id": result["record_id"],
                "asset_sha256": "sha256:" + digest,
                "byte_size": len(asset_bytes),
                "media_type": "application/pdf",
                "archive_path": "assets/example.pdf",
                "source_url": "https://cordis.europa.eu/project/id/963560/results",
                "retrieved_at": "2026-08-21T00:00:00Z",
            },
        }
        asset["provenance"][0]["claim_id"] = contract.deterministic_claim_id(
            asset_id, asset["provenance"][0]
        )
        asset["content_hash"] = contract.canonical_record_hash(asset)
        asset_payload = (
            json.dumps(asset, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode("utf-8")
        (target / "result_assets.ndjson").write_bytes(asset_payload)

        manifest = load_json(target / "manifest.json")
        template = manifest["record_sets"][0]
        manifest["record_sets"].append(
            {
                "record_type": "RESULT_ASSET",
                "path": "result_assets.ndjson",
                "media_type": "application/x-ndjson",
                "visibility": "PUBLIC",
                "canonical": True,
                "record_count": 1,
                "byte_size": len(asset_payload),
                "sha256": hashlib.sha256(asset_payload).hexdigest(),
                "record_schema": template["record_schema"],
                "record_schema_sha256": template["record_schema_sha256"],
            }
        )
        manifest["summary"]["result_assets"] = 1
        EuResearchContractTests.write_manifest(target, manifest)
        return target / "manifest.json", asset_path

    @staticmethod
    def configure_full_snapshot(
        target: Path, status: str = "CANDIDATE"
    ) -> dict[str, Any]:
        baseline = load_json(BASELINE)
        baseline_path = target / "baseline.json"
        shutil.copy2(BASELINE, baseline_path)
        manifest = load_json(target / "manifest.json")
        manifest["release_kind"] = "FULL_SNAPSHOT"
        manifest["status"] = status
        manifest["baseline"] = {
            "baseline_id": baseline["baseline_id"],
            "path": "baseline.json",
            "sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        }
        manifest["source_observation_summary"] = {
            "source_result_rows": baseline["counts"]["source_result_rows"],
            "source_row_access_counts": baseline["source_row_access_counts"],
            "source_row_result_relevance_counts": baseline[
                "source_row_result_relevance_counts"
            ],
            "source_row_result_type_counts": baseline[
                "source_row_result_type_counts"
            ],
            "primary_project_source_counts": baseline[
                "primary_project_source_counts"
            ],
            "seed_project_result_rows": baseline["seed_project_result_rows"],
        }
        observation: dict[str, Any] = {
            "observation_id": "source_observation/sha256/" + "0" * 64,
            "release_id": manifest["release_id"],
            "source_artifact_id": (
                "source_artifact/cordis/bulk-2026-08/fixture-observation"
            ),
            "source_system": "CORDIS_BULK",
            "source_dataset": "cordis/h2020-project-publications",
            "source_record_id": "963560_1327195_PUBLI",
            "source_row_number": 1,
            "project_id": "research_project/eu-h2020/963560",
            "result_type": "CONFERENCE_PUBLICATION",
            "access_status": "METADATA_ONLY",
            "battery_relevance": "DIRECT_BATTERY_RESULT",
            "disposition": "CANONICAL_LINK",
            "project_result_id": (
                "project_result/d45587ed-ab43-5dc4-871d-da21beb18b57"
            ),
            "disposition_note": None,
        }
        observation["observation_id"] = (
            contract.deterministic_source_observation_id(observation)
        )
        observation_payload = (
            json.dumps(observation, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        observation_dir = target / "source_observations"
        observation_dir.mkdir()
        (observation_dir / "observations.ndjson").write_bytes(observation_payload)
        observation_schema = (
            ROOT / "json-schema" / "eu-research-observation.schema.json"
        )
        manifest["source_observation_ledger"] = {
            "path": "source_observations/observations.ndjson",
            "media_type": "application/x-ndjson",
            "record_count": 1,
            "byte_size": len(observation_payload),
            "sha256": hashlib.sha256(observation_payload).hexdigest(),
            "observation_schema": (
                "https://github.com/Morshedvarzandeh/battery-data/"
                "json-schema/eu-research/1.0.0/observation.schema.json"
            ),
            "observation_schema_sha256": hashlib.sha256(
                observation_schema.read_bytes()
            ).hexdigest(),
            "input_artifact_id": observation["source_artifact_id"],
        }
        EuResearchContractTests.write_manifest(target, manifest)
        return baseline

    def assert_has_error(self, target: Path, expected: str) -> None:
        errors = contract.validate_snapshot(target / "manifest.json")
        self.assertTrue(
            any(expected in item for item in errors),
            msg=f"expected {expected!r}; got:\n" + "\n".join(errors),
        )

    @staticmethod
    def fixture_copy() -> tempfile.TemporaryDirectory[str]:
        class FixtureDirectory(tempfile.TemporaryDirectory[str]):
            def __enter__(self) -> Path:
                path = Path(super().__enter__()) / "fixture"
                shutil.copytree(FIXTURE.parent, path)
                return path

        return FixtureDirectory()


if __name__ == "__main__":
    unittest.main()
