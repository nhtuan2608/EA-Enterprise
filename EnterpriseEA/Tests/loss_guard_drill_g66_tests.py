"""G66 D4 tests: synthetic ledger only, no live files."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))
import loss_guard_drill as d  # noqa: E402

INP = {"initial": 10000.0, "reset_balance": 10000.0, "high_water": 10000.0, "reset_utc": 1000,
       "daily_pct": 2.0, "weekly_pct": 4.0, "open_pct": 2.0, "per_trade_pct": 0.5, "next_pct": 0.5,
       "balance": 10000.0, "equity": 10000.0}


def verdict(older=0.0, wk=0.0, today=0.0, open_pct=0.0):
    init = INP["initial"]
    week_balance = INP["reset_balance"] - older / 100 * init
    day_ref = week_balance - wk / 100 * init
    equity = day_ref - today / 100 * init
    open_money, nxt = open_pct / 100 * init, INP["next_pct"] / 100 * init
    internal = d.internal_loss_room(INP, day_ref, week_balance, equity, open_money)
    floor_ok, _ = d.floor_check(INP, day_ref, equity, open_money, nxt)
    return internal["allowed_money"] + d.EPS >= nxt, floor_ok


class LossGuardDrill(unittest.TestCase):
    def test_daily_two_percent_boundary(self):
        self.assertEqual(verdict(today=1.5), (True, True))    # 1.5 + 0.5 == 2.0 still fits
        self.assertEqual(verdict(today=1.9)[0], False)         # full-size trade no longer fits
        self.assertEqual(verdict(today=2.0)[0], False)
        self.assertEqual(verdict(today=2.5)[0], False)

    def test_weekly_four_percent_boundary(self):
        self.assertEqual(verdict(wk=3.0)[0], True)
        self.assertEqual(verdict(wk=3.9)[0], False)
        self.assertEqual(verdict(wk=4.0)[0], False)

    def test_open_risk_counts_against_floor_headroom(self):
        # floors alone: 3.9% lost + 0.5% next = 4.4% < 4.5% ok; with an open 0.5% it reaches 4.9% -> blocked
        init = INP["initial"]
        eq = init * (1 - 0.039)
        self.assertTrue(d.floor_check(INP, init, eq, 0.0, 50.0)[0])
        self.assertFalse(d.floor_check(INP, init, eq, 50.0, 50.0)[0])

    def test_floors_block_near_custom_limits(self):
        self.assertFalse(verdict(today=4.6)[1])
        self.assertFalse(verdict(older=9.6)[1])

    def test_open_risk_reduces_internal_rooms_and_drill_all_pass(self):
        self.assertFalse(d.expected_allowed(INP, 0, 0, 1.5, 0.5))
        self.assertEqual(verdict(today=1.5, open_pct=0.5)[0], False)   # 1.5 + 0.5 open + 0.5 next > 2.0
        self.assertEqual(verdict(wk=3.0, open_pct=0.5)[0], True)       # 3.0 + 0.5 + 0.5 == 4.0 fits
        self.assertEqual(verdict(wk=3.5, open_pct=0.5)[0], False)
        self.assertTrue(all(r["pass"] for r in d.run(INP)))


if __name__ == "__main__":
    unittest.main()
