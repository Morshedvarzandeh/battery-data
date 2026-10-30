"""The accepted-library snapshot is deterministic, validated and complete."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import export_catalog_snapshot as snap  # noqa: E402

REVISION = "3bd20c0271b1e0dc517076febf799a9f25072ffd"
SAMPLES = ["contrib/cells/samsung-sdi/inr21700-50e.yaml", "contrib/cells/eemb/lp103042.yaml"]


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for sample in SAMPLES:
            target = self.tmp / sample
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / sample, target)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_snapshot_is_sorted_hashed_and_complete(self):
        snapshot = snap.build(self.tmp, REVISION)
        self.assertEqual(snapshot["format_version"], 1)
        self.assertEqual(snapshot["source_revision"], REVISION)
        uids = [entry["record"]["product"]["uid"] for entry in snapshot["records"]]
        self.assertEqual(uids, sorted(uids))
        self.assertEqual(snapshot["counts"]["products"], 2)
        self.assertEqual(snapshot["counts"]["by_kind"], {"cell": 2})
        self.assertEqual(snapshot["counts"]["observations"],
                         sum(len(e["record"]["observations"]) for e in snapshot["records"]))
        for entry in snapshot["records"]:
            self.assertTrue(entry["file"].startswith("contrib/"))
            self.assertIn("locator", entry["record"]["observations"][0])
        content = {k: v for k, v in snapshot.items() if k != "release"}
        self.assertEqual(snapshot["release"], snap.digest(content))
        self.assertEqual(snap.build(self.tmp, REVISION), snapshot, "two builds agree byte for byte")

    def test_refuses_bad_revision_duplicates_invalid_and_empty(self):
        with self.assertRaises(ValueError):
            snap.build(self.tmp, "main")
        duplicate = self.tmp / "contrib/cells/eemb/again.yaml"
        shutil.copy(self.tmp / SAMPLES[1], duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate product UID"):
            snap.build(self.tmp, REVISION)
        duplicate.unlink()
        broken_path = self.tmp / SAMPLES[1]
        doc = yaml.safe_load(broken_path.read_text())
        broken = copy.deepcopy(doc)
        del broken["observations"][0]["locator"]
        broken_path.write_text(yaml.safe_dump(broken, sort_keys=False))
        with self.assertRaises(ValueError):
            snap.build(self.tmp, REVISION)
        shutil.rmtree(self.tmp / "contrib")
        os.makedirs(self.tmp / "contrib")
        with self.assertRaisesRegex(ValueError, "empty"):
            snap.build(self.tmp, REVISION)

    def test_each_record_says_whether_design_may_use_it(self):
        # Design takes lithium-ion and sodium-ion only, as the finder says.
        extra = {"contrib/cells/trojan-battery/t-105.yaml": (False, "Lead-acid"),
                 "contrib/cells/samsung-sdi/inr21700-50e.yaml": (True, "Lithium-ion")}
        for sample in extra:
            target = self.tmp / sample
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / sample, target)
        primary = next(p for p in sorted((ROOT / "contrib").rglob("*.yaml"))
                       if yaml.safe_load(p.read_text())["product"]["kind"] == "primary_cell")
        target = self.tmp / primary.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(primary, target)
        by_file = {e["file"]: e["design"] for e in snap.build(self.tmp, REVISION)["records"]}
        for sample, (allowed, tech) in extra.items():
            self.assertEqual(by_file[sample], {"allowed": allowed, "technology": tech}, sample)
        self.assertFalse(by_file[primary.relative_to(ROOT).as_posix()]["allowed"], "a primary cell is not lithium-ion")
        self.assertTrue(all(isinstance(d["allowed"], bool) for d in by_file.values()))

    def test_canonical_json_is_stable(self):
        text = snap.canonical({"b": 1, "a": [1.5, "é"]})
        self.assertEqual(text, '{"a":[1.5,"é"],"b":1}')
        self.assertEqual(json.loads(text), {"a": [1.5, "é"], "b": 1})


if __name__ == "__main__":
    unittest.main()
