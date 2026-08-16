"""Regression tests for tools/check_duplicates.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_duplicates as duplicates  # noqa: E402


def record(
    path: str,
    uid: str,
    model: str,
    *,
    manufacturer: str = "Example Battery Co., Ltd.",
    aliases: tuple[str, ...] = (),
    source: str = "uid:srcmanufacturercatalog",
    capacity_ah: float | None = 3.0,
    diameter_mm: float | None = 21.0,
    kind: str = "cell",
    form_factor: str = "cylindrical",
    rechargeable: bool | None = True,
) -> duplicates.Record:
    specs: dict[str, tuple[duplicates.SpecValue, ...]] = {}
    if capacity_ah is not None:
        specs["capacity"] = (duplicates.SpecValue(capacity_ah, "Ah"),)
    if diameter_mm is not None:
        specs["diameter"] = (duplicates.SpecValue(diameter_mm, "mm"),)
    return duplicates.Record(
        path=path,
        uid=uid,
        kind=kind,
        manufacturer=manufacturer,
        model=model,
        aliases=aliases,
        source_keys=frozenset({source}) if source else frozenset(),
        specs=specs,
        box_dimensions_mm=None,
        form_factor=form_factor,
        rechargeable=rechargeable,
    )


class NormalizationTests(unittest.TestCase):
    def test_manufacturer_drops_only_legal_suffixes(self) -> None:
        self.assertEqual(
            duplicates.normalize_manufacturer("EVE Energy Co., Ltd."), "eveenergy"
        )
        self.assertNotEqual(
            duplicates.normalize_manufacturer("LG Energy Solution"),
            duplicates.normalize_manufacturer("LG Chem"),
        )

    def test_curated_manufacturer_alias(self) -> None:
        self.assertEqual(
            duplicates.normalize_manufacturer("Panasonic Energy Co., Ltd."),
            duplicates.normalize_manufacturer("Panasonic"),
        )

    def test_model_normalization_keeps_variant_suffix(self) -> None:
        self.assertEqual(
            duplicates.compact_identifier("INR-21700 P42A"), "inr21700p42a"
        )
        self.assertNotEqual(
            duplicates.compact_identifier("CR2032"),
            duplicates.compact_identifier("CR2032-MFR-HF1"),
        )

    def test_tracking_query_does_not_create_a_new_source(self) -> None:
        first = duplicates.normalize_url("https://EXAMPLE.com/spec.pdf?utm_source=x&a=1")
        second = duplicates.normalize_url("http://example.com/spec.pdf?a=1#page=2")
        self.assertEqual(first, second)


class ClassificationTests(unittest.TestCase):
    def test_exact_uid_blocks_even_when_specs_conflict(self) -> None:
        records = [
            record("one.yaml", "cell/example/p42a", "P42A", capacity_ah=4.2),
            record("two.yaml", "cell/example/p42a", "P42-A", capacity_ah=4.5),
        ]
        findings = duplicates.find_duplicates(records)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].classification, "exact_duplicate")
        self.assertIn("exact_uid", findings[0].signals)

    def test_punctuation_drift_with_matching_specs_is_probable_duplicate(self) -> None:
        records = [
            record("one.yaml", "cell/example/m35-a", "M35-A"),
            record("two.yaml", "cell/example/m35.a", "m35.a"),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "probable_duplicate")
        self.assertIn("normalized_manufacturer_model", finding.signals)
        self.assertTrue(finding.agreements)

    def test_official_punctuation_variant_with_different_capacity_is_review_only(self) -> None:
        # Real-world Renata edge case: both strings are official catalogue
        # models.  Removing the separator must not silently merge them.
        records = [
            record(
                "cr2016-mfr.yaml",
                "primary_cell/renata/cr2016-mfr",
                "CR2016 MFR",
                manufacturer="Renata",
                capacity_ah=0.090,
                diameter_mm=20.0,
            ),
            record(
                "cr2016.mfr.yaml",
                "primary_cell/renata/cr2016.mfr",
                "CR2016.MFR",
                manufacturer="Renata",
                capacity_ah=0.104,
                diameter_mm=20.0,
            ),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "identity_collision")
        self.assertTrue(any(item.startswith("capacity:") for item in finding.conflicts))
        self.assertFalse(duplicates.should_fail([finding], "duplicate"))
        self.assertTrue(duplicates.should_fail([finding], "review"))

    def test_connector_and_tab_variants_are_not_exact_duplicates(self) -> None:
        records = [
            record(
                "bare.yaml",
                "primary_cell/renata/cr2032",
                "CR2032",
                manufacturer="Renata",
            ),
            record(
                "tabbed.yaml",
                "primary_cell/renata/cr2032-mfr-hf1",
                "CR2032-MFR-HF1",
                manufacturer="Renata",
            ),
        ]
        self.assertEqual(duplicates.find_duplicates(records), [])

    def test_explicit_alias_can_link_different_model_spellings(self) -> None:
        records = [
            record(
                "short.yaml",
                "cell/molicel/p42a",
                "P42A",
                manufacturer="Molicel",
                aliases=("INR21700-P42A",),
            ),
            record(
                "long.yaml",
                "cell/molicel/inr21700-p42a",
                "INR 21700 P42A",
                manufacturer="Molicel",
            ),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "probable_duplicate")
        self.assertEqual(finding.signals, ("alias_model_match",))

    def test_same_source_model_catches_manufacturer_spelling_drift(self) -> None:
        records = [
            record("one.yaml", "cell/eve/p42a", "P42A", manufacturer="EVE Energy"),
            record("two.yaml", "cell/eve-alt/p42a", "P42-A", manufacturer="EVE"),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "probable_duplicate")
        self.assertEqual(finding.signals, ("same_source_model",))

    def test_shared_dataset_model_does_not_merge_unrelated_manufacturers(self) -> None:
        records = [
            record("one.yaml", "primary_cell/maxell/cr2032", "CR2032",
                   manufacturer="Maxell"),
            record("two.yaml", "primary_cell/panasonic/cr2032", "CR2032",
                   manufacturer="Panasonic"),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "identity_collision")
        self.assertEqual(finding.signals, ("same_source_model",))

    def test_kind_conflict_prevents_automatic_merge(self) -> None:
        records = [
            record("cell.yaml", "cell/example/x1", "X1", kind="cell"),
            record("pack.yaml", "module/example/x1", "X-1", kind="module"),
        ]
        finding = duplicates.find_duplicates(records)[0]
        self.assertEqual(finding.classification, "identity_collision")
        self.assertIn("kind: cell vs module", finding.conflicts)


if __name__ == "__main__":
    unittest.main()
