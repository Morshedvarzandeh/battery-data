"""Recalled names, and the gate between a name and a record.

The candidate sets under review/layers say who and what to look for; they
carry no source, no page and no quote, and nothing in them may enter the
accepted tables until tools/verify_layer_candidates.py has found the name on
a real page and quoted it. These tests hold that line: the sets validate,
they declare their own uncertainty, they never smuggle provenance, and the
verifier writes a contribution only when the page actually names the thing.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "verify-pages")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import validate_layer_candidates as vlc  # noqa: E402
import verify_layer_candidates as vfy  # noqa: E402


def sets() -> list[dict]:
    return [yaml.safe_load(open(f, encoding="utf-8"))
            for f in sorted(glob.glob(os.path.join(ROOT, "review", "layers", "*.y*ml")))]


class CandidateSetsAreHonest(unittest.TestCase):
    def test_every_set_validates(self):
        errs, stats = vlc.validate(sorted(glob.glob(os.path.join(ROOT, "review", "layers", "*.y*ml"))))
        self.assertEqual(errs, [])
        self.assertGreater(stats["companies"], 100)
        self.assertGreater(stats["sites"], 100)

    def test_no_candidate_carries_provenance(self):
        """The one rule that matters: a recalled name may not look sourced."""
        for doc in sets():
            self.assertEqual(vlc.forbidden_keys(doc), [], doc["candidate_set"])

    def test_every_set_says_it_is_a_recall(self):
        for doc in sets():
            self.assertIn("recalled_by", doc)
            self.assertIn("verif", doc["caveat"].lower())
            self.assertGreaterEqual(len(doc["caveat"]), 40)

    def test_verify_at_is_always_https(self):
        for doc in sets():
            for c in (doc.get("companies") or []) + (doc.get("sites") or []):
                self.assertTrue(c["verify_at"].startswith("https://"), c["uid"])

    def test_no_capacity_or_tonnage_anywhere(self):
        """A GWh or a tonnage without a source is the thing this database
        exists to refuse, so a candidate may not carry one at all."""
        banned = {"capacity", "capacity_gwh", "gwh", "tonnage", "production", "output",
                  "value", "price", "share_pct"}
        for doc in sets():
            for c in (doc.get("companies") or []) + (doc.get("sites") or []):
                self.assertEqual(banned & set(c), set(), c["uid"])

    def test_stage_map_is_read_from_the_schema(self):
        roles, kinds = vlc.stage_map()
        self.assertEqual(kinds["cell_factory"], "cell")
        self.assertEqual(kinds["recycling_plant"], "recycling")
        self.assertEqual(kinds["test_laboratory"], "testing")
        self.assertEqual(roles["cathode_producer"], "active_material")
        self.assertEqual(roles["recycler"], "recycling")

    def test_a_candidate_with_a_quote_is_refused(self):
        doc = {"schema_version": "1", "candidate_set": "x", "recalled_by": "a test fixture",
               "recalled_on": "2026-01-01", "caveat": "x" * 41,
               "companies": [{"uid": "org/x", "name": "X", "country": "SE", "roles": ["manufacturer"],
                              "verify_at": "https://example.org", "confidence": "low",
                              "quote": "invented"}]}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.yaml")
            yaml.safe_dump(doc, open(p, "w", encoding="utf-8"))
            errs, _ = vlc.validate([p])
        self.assertTrue(any("carries no provenance" in e or "additional" in e.lower() for e in errs), errs)


class VerificationIsTheGate(unittest.TestCase):
    def run_verifier(self, out: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(FIX, "candidates.yaml"), os.path.join(d, "candidates.yaml"))
            log = os.path.join(d, "log.json")
            old_dir, old_log = vfy.DIR, vfy.LOG
            vfy.DIR, vfy.LOG = d, log
            try:
                argv = sys.argv
                sys.argv = ["verify", "--offline-dir", FIX, "--out", out]
                vfy.main()
            finally:
                sys.argv = argv
                vfy.DIR, vfy.LOG = old_dir, old_log
            return json.load(open(log, encoding="utf-8"))

    def test_a_name_on_the_page_becomes_a_sourced_contribution(self):
        with tempfile.TemporaryDirectory() as out:
            log = self.run_verifier(out)
            by_uid = {e["uid"]: e for e in log}
            self.assertEqual(by_uid["org/morrow-batteries"]["result"], "verified")
            self.assertEqual(by_uid["site/morrow-batteries/arendal"]["result"], "verified")
            doc = yaml.safe_load(open(os.path.join(out, "companies", "morrow-batteries.yaml"),
                                      encoding="utf-8"))
            # the contribution is complete: source, locator, quote, hash
            self.assertEqual(doc["organization"]["uid"], "org/morrow-batteries")
            self.assertIn("Morrow Batteries", doc["locator"]["quote"])
            self.assertEqual(len(doc["source"]["sha256"]), 64)
            self.assertTrue(doc["source"]["url"].startswith("https://"))
            # and it says which fields are still only recalled
            self.assertIn("not yet confirmed", doc["organization"]["description"])

    def test_a_name_not_on_the_page_is_refused(self):
        with tempfile.TemporaryDirectory() as out:
            log = self.run_verifier(out)
            entry = next(e for e in log if e["uid"] == "org/no-such-name")
            self.assertEqual(entry["result"], "name not found on the page")
            self.assertFalse(os.path.exists(os.path.join(out, "companies", "no-such-name.yaml")))

    def test_the_quote_is_prose_not_a_navigation_bar(self):
        with tempfile.TemporaryDirectory() as out:
            self.run_verifier(out)
            q = yaml.safe_load(open(os.path.join(out, "companies", "morrow-batteries.yaml"),
                                    encoding="utf-8"))["locator"]["quote"]
            self.assertNotIn("Careers", q)          # the nav bar
            self.assertNotIn("script", q.lower())   # the script tag
            self.assertIn("Norwegian battery company", q)

    def test_a_site_pins_its_operator_by_name_from_another_set(self):
        with tempfile.TemporaryDirectory() as out:
            self.run_verifier(out)
            doc = yaml.safe_load(open(os.path.join(out, "sites", "morrow-batteries", "arendal.yaml"),
                                      encoding="utf-8"))
            self.assertEqual(doc["site"].get("operator"), "Morrow Batteries")
            self.assertIn("as recalled", doc["site"]["notes"])

    def test_two_pages_on_one_host_are_two_sources(self):
        with tempfile.TemporaryDirectory() as out:
            self.run_verifier(out)
            a = yaml.safe_load(open(os.path.join(out, "companies", "morrow-batteries.yaml"),
                                    encoding="utf-8"))["source"]["uid"]
            b = yaml.safe_load(open(os.path.join(out, "sites", "morrow-batteries", "arendal.yaml"),
                                    encoding="utf-8"))["source"]["uid"]
            self.assertNotEqual(a, b)

    def test_the_output_passes_the_contribution_validator(self):
        import validate_layers as vl
        with tempfile.TemporaryDirectory() as out:
            self.run_verifier(out)
            files = sorted(glob.glob(os.path.join(out, "**", "*.yaml"), recursive=True))
            self.assertEqual(len(files), 2)
            errs, counts = vl.validate_files(files, expect_dir=False)
            self.assertEqual(errs, [])
            self.assertEqual((counts["companies"], counts["sites"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
