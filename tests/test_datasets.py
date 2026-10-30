"""Published per-cycle dataset values: traceable to their files, with a licence or a stated basis."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_datasets  # noqa: E402

XJTU = ROOT / "datasets" / "xjtu-2024"


class DatasetsTest(unittest.TestCase):
    def test_every_published_dataset_passes(self):
        self.assertEqual(check_datasets.main(), 0)

    def test_xjtu_is_complete_and_attributed(self):
        m = json.loads((XJTU / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["license"], "CC BY 4.0")
        self.assertIn("doi:10.5281/zenodo.10963339", m["attribution"])
        self.assertEqual(len(m["source_files"]), 55)
        self.assertEqual(sum(f["cycles"] for f in m["source_files"]), 27642)
        self.assertEqual(m["files"]["cycles.csv"]["rows"], 27642)
        self.assertEqual(m["product_uid"], "cell/lishen/unstated")

    def test_calce_is_published_as_computed_values_with_its_basis(self):
        m = json.loads((ROOT / "datasets" / "calce" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["license"], "none stated")
        self.assertIs(m["redistributable"], False)
        self.assertIn("raw files are not redistributed", m["publication_basis"])
        self.assertIn("J. Power Sources 196 (2011)", m["attribution"])
        self.assertEqual(len(m["source_files"]), 15)
        self.assertEqual(sum(f["cycles"] for f in m["source_files"]), 35424)
        self.assertTrue(any("CS2_3" in c and "CS2_25" in c for c in m["caveats"]), "the two conflicting recordings are named")
        self.assertEqual([(x["cell"], x["cycle"]) for x in m["exceptions"]], [("CS2_8", 574), ("CS2_21", 425)])

    def test_an_unlisted_or_stale_exception_is_refused(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            folder = tmp / "calce"
            shutil.copytree(ROOT / "datasets" / "calce", folder)
            m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            m["exceptions"][0]["value"] = 1.99
            m["exceptions"][1]["cycle"] = 426
            (folder / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
            errs = check_datasets.check_folder(str(folder))
            self.assertTrue(any("charge_ah=1.9902 outside" in e for e in errs), errs)
            self.assertTrue(any("CS2_21 cycle 426 charge_ah does not occur" in e for e in errs), errs)
        finally:
            shutil.rmtree(tmp)

    def test_a_changed_value_or_count_is_refused(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            folder = tmp / "xjtu-2024"
            shutil.copytree(XJTU, folder)
            csv_path = folder / "cycles.csv"
            text = csv_path.read_text(encoding="utf-8").splitlines(keepends=True)
            text[1] = text[1].replace("1.99128", "1.99129")
            csv_path.write_text("".join(text), encoding="utf-8")
            self.assertTrue(any("SHA-256" in e for e in check_datasets.check_folder(str(folder))))

            shutil.rmtree(folder)
            shutil.copytree(XJTU, folder)
            m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            bad = copy.deepcopy(m)
            bad["redistributable"] = False
            bad["source_files"][0]["cycles"] += 1
            (folder / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")
            errs = check_datasets.check_folder(str(folder))
            self.assertTrue(any("publication_basis" in e for e in errs))
            self.assertTrue(any("2C_battery-1 has" in e for e in errs))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
