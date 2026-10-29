"""Open-dataset registry entries, and the XJTU .mat converter end to end."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import cyclers  # noqa: E402
import ingest_open_dataset as ingest  # noqa: E402

try:
    import numpy as np
    from scipy.io import savemat
    import convert_xjtu_mat as xjtu
    HAVE_SCIPY = True
except ImportError:                                               # pragma: no cover
    HAVE_SCIPY = False

REQUIRED = {"name", "publisher", "landing", "citation", "license", "cells",
            "file_glob", "test_kind", "notes"}


class RegistryTest(unittest.TestCase):
    def test_every_entry_has_the_fields_the_pipeline_reads(self):
        for key, ds in ingest.DATASETS.items():
            with self.subTest(dataset=key):
                self.assertFalse(REQUIRED - set(ds), f"{key} lacks {REQUIRED - set(ds)}")
                self.assertTrue(ds["landing"].startswith("https://"))

    def test_xjtu_entry_matches_the_published_cell(self):
        ds = ingest.DATASETS["xjtu-2024"]
        self.assertEqual((ds["manufacturer"], ds["ff_code"], ds["nominal_ah"]),
                         ("Lishen", "18650", 2.0))
        self.assertEqual(ds["doi"], "10.5281/zenodo.10963339")
        self.assertIn("CC BY 4.0", ds["license"])
        sql = ingest.spine_sql(ds, "xjtu-2024", "2026-10-29", [], None, None)
        self.assertIn("'cell/lishen/unstated'", sql)
        self.assertIn("'src/dataset/xjtu-2024'", sql)

    def test_calce_cites_the_cs2_experiment_article(self):
        ds = ingest.DATASETS["calce"]
        self.assertEqual(ds["model"], "CS2")
        self.assertIn("Journal of Power Sources 196(23)", ds["citation"])


def _cycle(t0_clock, restart_relative, cycle_no, label):
    """
    One XJTU-shaped cycle, rests included as in the released files:
    1800 s charge at +4 A, 300 s rest, 3600 s discharge at -2 A, 300 s rest.
    """
    n_chg, n_rest, n_dch = 1800, 300, 3600
    cur = np.concatenate([np.full(n_chg, 4.0), np.zeros(n_rest),
                          np.full(n_dch, -2.0), np.zeros(n_rest)])
    volt = np.concatenate([np.linspace(3.6, 4.2, n_chg), np.full(n_rest, 4.15),
                           np.linspace(4.2, 2.5, n_dch), np.full(n_rest, 2.9)])
    secs = np.arange(len(cur), dtype=float)
    rel_min = secs / 60.0 if restart_relative else (secs + cycle_no * 10_000) / 60.0
    if t0_clock is None:
        clock = np.zeros(len(secs))          # unparseable: forces the fallback
    else:
        import pandas as pd
        stamps = pd.Timestamp(t0_clock) + pd.to_timedelta(secs, unit="s")
        # The released files write the date and time with a comma between them.
        clock = np.array([s.strftime("%Y-%m-%d,%H:%M:%S") for s in stamps])
    return (clock.reshape(-1, 1), rel_min.reshape(-1, 1), volt.reshape(-1, 1),
            cur.reshape(-1, 1), np.zeros((len(secs), 1)), np.zeros((len(secs), 1)),
            np.full((len(secs), 1), 25.0), label)


ROWS_PER_CYCLE = 6000
SUMMARY_FIELDS = ["charge_capacity_Ah", "discharge_capacity_Ah", "charge_power_Wh",
                  "discharge_power_Wh", "charge_median_voltage", "discharge_median_voltage",
                  "charge_mean_voltage", "discharge_mean_voltage", "cycle_life", "description"]


def _write_mat(path, use_clock, restart_relative=True):
    labels = ["2C charge 1C discharge", "test capacity", "2C charge 1C discharge"]
    starts = ["2023-03-01 08:00:00", "2023-03-01 09:40:00", "2023-03-01 11:20:00"]
    data = np.zeros((1, 3), dtype=[(f, object) for f in xjtu.DATA_FIELDS])
    for i in range(3):
        data[0, i] = _cycle(starts[i] if use_clock else None, restart_relative, i, labels[i])
    # The released files' summary layout: per-cycle arrays, then cycle life
    # and a description in positions 8 and 9.
    summary = np.zeros((1, 1), dtype=[(f, object) for f in SUMMARY_FIELDS])
    reported = np.array([[2.0], [1.98], [1.96]])
    summary[0, 0] = tuple([reported, reported] + [np.zeros((3, 1))] * 6
                          + [np.array([[3]]), "batch-1 synthetic"])
    savemat(path, {"data": data, "summary": summary})


@unittest.skipUnless(HAVE_SCIPY, "scipy not installed")
class XjtuConverterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _convert(self, **kw):
        mat = os.path.join(self.tmp, "2C_battery-1.mat")
        _write_mat(mat, **kw)
        return xjtu.convert(mat, os.path.join(self.tmp, "csv"))

    def test_clock_time_keeps_the_rest_between_cycles(self):
        r = self._convert(use_clock=True)
        self.assertEqual((r["cycles"], r["rows"]), (3, 3 * ROWS_PER_CYCLE))
        self.assertTrue(r["time_basis"].startswith("system_time"))
        nz = cyclers.normalise(r["csv"])
        self.assertEqual(nz.dialect, "bdf")
        t = nz.frame["test_time_second"].to_numpy()
        # cycle 2 starts 100 min after cycle 1 started, so 6000 s on the clock.
        self.assertAlmostEqual(t[ROWS_PER_CYCLE], 6000.0)
        cycles = cyclers.summarise_cycles(nz)
        self.assertEqual(len(cycles), 3)
        for c in cycles:
            self.assertAlmostEqual(c["charge_capacity_ah"], 2.0, places=2)
            self.assertAlmostEqual(c["discharge_capacity_ah"], 2.0, places=2)

    def test_relative_time_is_joined_when_the_clock_does_not_parse(self):
        for restart in (True, False):
            with self.subTest(restart_relative=restart):
                r = self._convert(use_clock=False, restart_relative=restart)
                self.assertTrue(r["time_basis"].startswith("relative_time_min"))
                t = cyclers.normalise(r["csv"]).frame["test_time_second"].to_numpy()
                self.assertTrue((np.diff(t) > 0).all())

    def test_sidecar_keeps_the_capacity_check_labels(self):
        r = self._convert(use_clock=True)
        with open(r["csv"].replace(".csv", ".cycles.json")) as fh:
            side = json.load(fh)
        self.assertEqual(side["summary"], {"cycle_life": 3, "description": "batch-1 synthetic"})
        self.assertEqual([c["description"] for c in side["cycles"]][1], "test capacity")
        self.assertEqual([c["reported_discharge_capacity_ah"] for c in side["cycles"]],
                         [2.0, 1.98, 1.96])

    def test_converted_file_runs_through_the_ingest_pipeline(self):
        r = self._convert(use_clock=True)
        out = io.StringIO()
        stats = ingest.run_pipeline("xjtu-2024", ingest.DATASETS["xjtu-2024"],
                                    [r["csv"]], out)
        self.assertEqual((stats["files"], stats["cycles"], stats["failed"]), (1, 3, []))
        sql = out.getvalue()
        self.assertIn("'cell/lishen/unstated/unit/xjtu-2024/2C_battery-1'", sql)
        # No capacity column, so the sign falls back to the BDF default and says so.
        self.assertTrue(any("current sign not determinable" in w for w in stats["warnings"]))


@unittest.skipUnless(HAVE_SCIPY, "scipy not installed")
class CycleBoundaryTest(unittest.TestCase):
    def test_a_rest_between_discharge_and_charge_still_ends_the_cycle(self):
        import pandas as pd
        one = [4.0] * 5 + [0.0] * 3 + [-2.0] * 5 + [0.0] * 3
        df = pd.DataFrame({"current_ampere": one * 4})
        idx = cyclers.derive_cycle_index(df, "charge_positive")
        self.assertEqual(list(idx.unique()), [1, 2, 3, 4])
        # The rest after a discharge stays with the cycle it ends.
        self.assertEqual(idx.iloc[len(one) - 1], 1)
        self.assertEqual(idx.iloc[len(one)], 2)


if __name__ == "__main__":
    unittest.main()
