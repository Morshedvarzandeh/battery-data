"""Published per-cycle dataset values: traceable to their files, licensed for reuse."""
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
            self.assertTrue(any("redistributable" in e for e in errs))
            self.assertTrue(any("2C_battery-1 has" in e for e in errs))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
