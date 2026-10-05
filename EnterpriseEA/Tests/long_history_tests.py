"""G23: conversion of the long-history MT5 exports (research/long/convert_raw.py)."""
import calendar
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))

import convert_raw as cr  # noqa: E402

HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"


class ConvertTests(unittest.TestCase):
    def test_parse_line_is_server_wall_clock(self):
        t, o, h, lo, c, sp = cr.parse_line("2025.10.08\t23:00:00\t4044.87\t4046.49\t4038.54\t4041.59\t11941\t0\t25")
        self.assertEqual(t, calendar.timegm((2025, 10, 8, 23, 0, 0, 0, 0, 0)))
        self.assertEqual((o, c, sp), (4044.87, 4041.59, 25))
        self.assertIsNone(cr.parse_line(HEADER))
        self.assertIsNone(cr.parse_line("garbage"))

    def test_convert_floors_spread_drops_duplicates_and_early_rows(self):
        lines = [HEADER,
                 "2017.06.01\t00:00:00\t1.0\t1.1\t0.9\t1.05\t1\t0\t0\n",       # before start: dropped
                 "2024.03.01\t00:00:00\t1.0\t1.1\t0.9\t1.05\t1\t0\t1\n",       # spread 1 -> floor
                 "2024.03.01\t00:00:00\t1.0\t1.1\t0.9\t1.05\t1\t0\t1\n",       # duplicate time: dropped
                 "2024.03.01\t01:00:00\t1.05\t1.2\t1.0\t1.1\t1\t0\t20\n",
                 "2024.03.01\t02:00:00\t1.1\t1.2\t1.0\t1.15\t1\t0\t30\n"]
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "raw.csv", Path(d) / "out.csv"
            src.write_text("".join(lines), encoding="utf-8")
            years = cr.convert(src, dst, start=calendar.timegm((2018, 1, 1, 0, 0, 0, 0, 0, 0)))
            out = dst.read_text(encoding="utf-8").splitlines()
        self.assertEqual(out[0], "time,open,high,low,close,spread")
        self.assertEqual(len(out), 4)
        spreads = [int(l.split(",")[-1]) for l in out[1:]]
        self.assertEqual(spreads, [20, 20, 30])          # floor = median of 2024+ non-zero spreads (1, 20, 30) = 20
        self.assertEqual(dict(years), {2024: 3})

    def test_sparse_history_starts(self):
        self.assertEqual(cr.START["XAUUSD"], calendar.timegm((2018, 3, 1, 0, 0, 0, 0, 0, 0)))
        self.assertEqual(cr.START["BTCUSD"], calendar.timegm((2018, 1, 1, 0, 0, 0, 0, 0, 0)))


if __name__ == "__main__":
    unittest.main()
