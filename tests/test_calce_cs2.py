"""CALCE CS2 session merging: ordering, repeat exports, overlaps, time axis, cycles."""
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

try:
    import numpy as np
    import pandas as pd
    import openpyxl  # noqa: F401
    import convert_calce_cs2 as calce
    HAVE_EXCEL = True
except ImportError:                                               # pragma: no cover
    HAVE_EXCEL = False


def _arbin_session(start, n_cycles, first_test_time=30.0):
    """Arbin-shaped rows: per cycle 60 s charge at +1 A, 10 s rest, 60 s discharge at -1 A, 10 s rest."""
    rows, t = [], first_test_time
    clock = pd.Timestamp(start)
    for c in range(1, n_cycles + 1):
        q_chg = q_dch = 0.0
        for step, (n, cur) in enumerate([(60, 1.0), (10, 0.0), (60, -1.0), (10, 0.0)], start=1):
            for _ in range(n):
                q_chg += max(cur, 0) / 3600.0
                q_dch += max(-cur, 0) / 3600.0
                rows.append({"Data_Point": len(rows) + 1, "Test_Time(s)": t,
                             "Date_Time": clock + pd.to_timedelta(t - first_test_time, unit="s"),
                             "Step_Time(s)": 0.0, "Step_Index": step, "Cycle_Index": c,
                             "Current(A)": cur, "Voltage(V)": 3.7 + 0.3 * cur,
                             "Charge_Capacity(Ah)": q_chg, "Discharge_Capacity(Ah)": q_dch})
                t += 1.0
    return pd.DataFrame(rows)


def _write_xlsx(path, df):
    with pd.ExcelWriter(path) as w:
        pd.DataFrame({"TEST REPORT": ["synthetic"]}).to_excel(w, sheet_name="Info", index=False)
        df.to_excel(w, sheet_name="Channel_1-008", index=False)


@unittest.skipUnless(HAVE_EXCEL, "pandas/openpyxl not installed")
class ArbinMergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cell = os.path.join(self.tmp, "CS2_99")
        os.makedirs(self.cell)
        a = _arbin_session("2010-08-16 10:00:00", 3)
        b = _arbin_session("2010-08-20 10:00:00", 2)
        _write_xlsx(os.path.join(self.cell, "CS2_99_8_17_10.xlsx"), a)
        _write_xlsx(os.path.join(self.cell, "CS2_99_8_21_10.xlsx"), b)
        # The same session exported again under a later name, as CALCE did for CS2_35.
        _write_xlsx(os.path.join(self.cell, "CS2_99_8_30_10.xlsx"), b)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_repeat_export_is_dropped_and_cycles_run_on(self):
        r = calce.convert(self.cell, os.path.join(self.tmp, "csv"))
        self.assertEqual((r["sessions"], r["kept"], r["format"]), (3, 2, "arbin"))
        with open(os.path.join(self.tmp, "csv", "CS2_99.sessions.json")) as fh:
            log = json.load(fh)["sessions"]
        self.assertTrue(log[2]["action"].startswith("dropped: identical to CS2_99_8_21_10"))
        nz = cyclers.normalise(r["csv"])
        self.assertEqual(nz.dialect, "bdf")
        # The capacity columns let the pipeline prove the sign from the data.
        self.assertEqual(nz.current_sign, "charge_positive")
        self.assertFalse(any("not determinable" in w for w in nz.warnings))
        self.assertEqual(int(nz.frame["cycle_count"].max()), 5)
        cycles = cyclers.summarise_cycles(nz)
        self.assertEqual(len(cycles), 5)
        for c in cycles:
            self.assertAlmostEqual(c["discharge_capacity_ah"], 60 / 3600, places=3)

    def test_sessions_sit_on_one_clock(self):
        r = calce.convert(self.cell, os.path.join(self.tmp, "csv"))
        t = pd.read_csv(r["csv"])["test_time_second"].to_numpy()
        self.assertTrue((np.diff(t) > 0).all())
        # The second session starts four days after the first.
        self.assertAlmostEqual(t[3 * 140], 4 * 86400.0)

    def test_overlapping_rows_are_trimmed(self):
        a = _arbin_session("2010-08-16 10:00:00", 3)
        overlap = _arbin_session("2010-08-16 10:05:00", 3)   # starts inside the first session
        shutil.rmtree(self.cell)
        os.makedirs(self.cell)
        _write_xlsx(os.path.join(self.cell, "CS2_99_8_17_10.xlsx"), a)
        _write_xlsx(os.path.join(self.cell, "CS2_99_8_18_10.xlsx"), overlap)
        table, sessions = calce.merge_cell(calce.session_files(self.cell))
        self.assertGreater(sessions["sessions"][1]["trimmed_overlap_rows"], 0)
        self.assertTrue((np.diff(table["test_time_second"].to_numpy()) > 0).all())


@unittest.skipUnless(HAVE_EXCEL, "pandas not installed")
class CadexTest(unittest.TestCase):
    def test_cadex_sessions_join_end_to_end_in_name_date_order(self):
        tmp = tempfile.mkdtemp()
        try:
            cell = os.path.join(tmp, "CS2_98")
            os.makedirs(cell)
            minutes = np.arange(0, 140) / 1.0
            ma = np.concatenate([np.full(60, 550), np.zeros(10), np.full(60, -550), np.zeros(10)])
            body = pd.DataFrame({"Time": minutes, "Status code": 8, "mV": 3800, "mA": ma,
                                 "Pgm step": 1, "Pgm cycle": 2, "Capacity": 100})
            # Written out of order on purpose: 1_19 must come before 1_26.
            for name in ("CS2_98_1_26_10.txt", "CS2_98_1_19_10.txt"):
                body.to_csv(os.path.join(cell, name), sep="\t", index=False)
            self.assertEqual([os.path.basename(f) for f in calce.session_files(cell)],
                             ["CS2_98_1_19_10.txt", "CS2_98_1_26_10.txt"])
            table, sessions = calce.merge_cell(calce.session_files(cell))
            self.assertEqual(sessions["format"], "cadex")
            self.assertNotIn("cycle_count", table)
            t = table["test_time_second"].to_numpy()
            self.assertTrue((np.diff(t) > 0).all())
            self.assertAlmostEqual(t[1] - t[0], 60.0)        # minutes to seconds
            self.assertAlmostEqual(table["current_ampere"].max(), 0.55)
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(HAVE_EXCEL, "pandas not installed")
class CadexSnapshotTest(unittest.TestCase):
    def test_progressive_snapshots_collapse_to_the_longest(self):
        tmp = tempfile.mkdtemp()
        try:
            cell = os.path.join(tmp, "CS2_97")
            os.makedirs(cell)
            ma = np.tile(np.concatenate([np.full(60, 550), np.zeros(10), np.full(60, -550), np.zeros(10)]), 3)
            full = pd.DataFrame({"Time": np.arange(len(ma), dtype=float), "mV": 3800, "mA": ma})
            # Three exports of one running test, then a separate test.
            full.iloc[:140].to_csv(os.path.join(cell, "CS2_97_1_19_10.txt"), sep="\t", index=False)
            full.iloc[:280].to_csv(os.path.join(cell, "CS2_97_1_20_10.txt"), sep="\t", index=False)
            full.to_csv(os.path.join(cell, "CS2_97_1_21_10.txt"), sep="\t", index=False)
            other = full.iloc[:140].copy(); other["mV"] = 3700
            other.to_csv(os.path.join(cell, "CS2_97_2_01_10.txt"), sep="\t", index=False)
            table, sessions = calce.merge_cell(calce.session_files(cell))
            actions = {s["file"]: s["action"] for s in sessions["sessions"]}
            self.assertTrue(actions["CS2_97_1_19_10.txt"].startswith("dropped: earlier snapshot"))
            self.assertTrue(actions["CS2_97_1_20_10.txt"].startswith("dropped: earlier snapshot"))
            self.assertEqual(actions["CS2_97_1_21_10.txt"], "kept")
            self.assertEqual(actions["CS2_97_2_01_10.txt"], "kept")
            self.assertEqual(len(table), len(full) + 140)
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(HAVE_EXCEL, "pandas not installed")
class LoggingGapTest(unittest.TestCase):
    def test_a_recording_gap_adds_no_charge(self):
        tmp = tempfile.mkdtemp()
        try:
            t = np.concatenate([np.arange(0, 3600, 60.0), np.arange(0, 3600, 60.0) + 3600 + 2 * 86400])
            cur = np.concatenate([np.full(30, 1.0), np.full(30, -1.0), np.full(60, -1.0)])
            path = os.path.join(tmp, "gap.csv")
            pd.DataFrame({"test_time_second": t, "voltage_volt": 3.7, "current_ampere": cur,
                          "cycle_count": 1}).to_csv(path, index=False)
            nz = cyclers.normalise(path)
            self.assertTrue(any("logging gap" in w for w in nz.warnings))
            (c,) = cyclers.summarise_cycles(nz)
            # 89 one-minute discharge samples at 1 A, not 2 days' worth.
            self.assertAlmostEqual(c["discharge_capacity_ah"], 89 / 60, places=3)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
