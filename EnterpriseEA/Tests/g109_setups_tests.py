"""G109 step 3 (research/long/g109_setups.py): exits a / b / c, sweep & reclaim, break detection, next-zone target."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
import g109_setups as gs  # noqa: E402


class G109SetupsTests(unittest.TestCase):
    def sim(self, d, entry, stop, target, h, l, c, sp=None):
        sp = np.zeros(len(h)) if sp is None else sp
        return gs.simulate(d, entry, stop, target, np.array(h, float), np.array(l, float), np.array(c, float), sp)

    def test_exit_a_target_and_stop(self):
        r = self.sim(1, 100, 99, 103, [100.5, 101.5, 103.2], [99.6, 100.4, 101.0], [100.2, 101.2, 103.0])
        self.assertEqual(r["a"], 3.0)
        r = self.sim(1, 100, 99, 103, [100.5, 103.5], [99.6, 98.9], [100.2, 99.0])
        self.assertEqual(r["a"], -1.0)                                     # stop and target in one bar: stop

    def test_exit_b_break_even_after_plus_one_r(self):
        # +1R (101) on bar 1, back to the entry on bar 2 -> 0R with break-even, -1R without
        r = self.sim(1, 100, 99, 103, [100.5, 101.2, 100.3, 100.0], [99.5, 100.6, 99.8, 98.9], [100.2, 101.0, 100.0, 99.0])
        self.assertEqual(r["b"], 0.0)
        self.assertEqual(r["a"], -1.0)

    def test_exit_c_half_at_one_r(self):
        r = self.sim(1, 100, 99, 103, [101.2, 100.5, 100.0], [100.3, 99.5, 98.9], [101.0, 99.8, 99.0])
        self.assertAlmostEqual(r["c"], 0.5 * 1 + 0.5 * -1)                 # half at +1R, rest stopped
        r = self.sim(1, 100, 99, 103, [101.2, 103.1], [100.3, 101.0], [101.0, 103.0])
        self.assertAlmostEqual(r["c"], 0.5 * 1 + 0.5 * 3)

    def test_time_stop_and_sell_at_ask(self):
        n = gs.MAX_BARS + 5
        h = np.full(n, 100.2); l = np.full(n, 99.8); c = np.full(n, 100.0)
        r = self.sim(-1, 100.0, 101.0, 97.0, h, l, c, np.full(n, 0.1))
        self.assertAlmostEqual(r["a"], -0.1)                               # exit at ask = 100.1 after 48 bars
        r2 = self.sim(-1, 100.0, 101.0, 97.0, [100.95], [99.0], [99.5], np.array([0.1]))
        self.assertEqual(r2["a"], -1.0)                                    # ask high 101.05 >= stop

    def test_detect_s1(self):
        # upper zone 105 +/- 0.5 (far edge 105.5); sweep to 105.9 then a close back below 105.5
        h = np.array([104.0, 105.2, 105.9, 105.6]); l = h - 0.6; c = np.array([103.8, 105.0, 105.7, 105.3])
        self.assertEqual(gs.detect_s1(1, 105.0, 0.5, 1.0, h, l, c), (3, 105.9))
        h2 = np.array([104.0, 106.2, 106.0]); c2 = np.array([103.8, 106.0, 105.4])
        self.assertIsNone(gs.detect_s1(1, 105.0, 0.5, 1.0, h2, h2 - 0.6, c2))   # excursion 0.7 > 0.5 ATR
        h3 = np.array([104.0, 105.7, 105.8, 105.9, 105.6]); c3 = np.array([103.8, 105.6, 105.7, 105.8, 105.3])
        self.assertIsNone(gs.detect_s1(1, 105.0, 0.5, 1.0, h3, h3 - 0.3, c3))  # no reclaim within 3 bars

    def test_detect_s2(self):
        c = np.array([104.0, 105.6, 105.4, 105.7, 105.8])
        self.assertEqual(gs.detect_s2(1, 105.0, 0.5, c), 4)                 # closes 3 and 4 above 105.5
        self.assertIsNone(gs.detect_s2(1, 105.0, 0.5, np.array([104.0, 105.6, 105.4])))
        self.assertEqual(gs.detect_s2(-1, 100.0, 0.5, np.array([100.0, 99.4, 99.3])), 2)

    def test_next_zone(self):
        zones = [(110.0, 0.5), (104.0, 0.5), (95.0, 0.5)]
        self.assertEqual(gs.next_zone(1, 100.0, zones), 103.5)             # near (lower) edge of the zone above
        self.assertEqual(gs.next_zone(-1, 100.0, zones), 95.5)
        self.assertIsNone(gs.next_zone(1, 112.0, zones))


if __name__ == "__main__":
    unittest.main()
