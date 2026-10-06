"""G37: edge monitor (research/g10/edge_monitor.py) against the calibrated parameters."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))

import edge_monitor as em  # noqa: E402

P = em.load_params()["S04_SWING"]


class EdgeMonitorTests(unittest.TestCase):
    def test_params_are_consistent(self):
        for name, p in em.load_params().items():
            self.assertGreater(p["h_alarm"], p["h_warn"], name)
            self.assertGreater(p["k"], 0, name)
            self.assertAlmostEqual(p["k"], p["mean"] / 2, places=6, msg=name)
            self.assertGreaterEqual(p["arl0_alarm"], 250, name)
            self.assertGreaterEqual(p["arl0_warn"], 60, name)

    def test_no_data(self):
        self.assertEqual(em.check([], P)["status"], "NO_DATA")

    def test_edge_like_results_are_ok(self):
        rs = [1.0, -1.0, 1.0, -1.0, 0.5, -0.5, 1.0, -1.0]
        self.assertEqual(em.check(rs, P)["status"], "OK")

    def test_losing_streak_raises_warn_then_alarm(self):
        warn = em.check([-1.0] * 8, P)
        self.assertIn(warn["status"], ("WARN", "ALARM"))
        alarm = em.check([-1.0] * 30, P)
        self.assertEqual(alarm["status"], "ALARM")
        self.assertGreater(alarm["cusum"], P["h_alarm"])

    def test_cusum_ignores_gains_after_reset(self):
        self.assertEqual(em.check([-1.0, -1.0] + [1.0] * 6, P)["cusum"], 0.0)

    def test_mean_test_needs_20_trades(self):
        rs = [-0.1] * 19
        self.assertNotIn("cận trên", " ".join(em.check(rs, P)["reasons"]))
        r = em.check([-0.3] * 40, P)
        self.assertEqual(r["status"], "ALARM")

    def test_drawdown_limit_uses_next_tabulated_n(self):
        t = {"5": {"p95": 1.0, "p99": 2.0}, "10": {"p95": 3.0, "p99": 4.0}}
        self.assertEqual(em.dd_limit(t, 3, "p95"), 1.0)
        self.assertEqual(em.dd_limit(t, 6, "p99"), 4.0)
        self.assertEqual(em.dd_limit(t, 99, "p99"), 4.0)

    def test_streams_use_only_known_realized_s04_swing(self):
        trades = [{"setup": "S04", "profile": "SWING", "realized_known": True, "realized_r": 1.5, "exit_utc": 2},
                  {"setup": "S04", "profile": "SWING", "realized_known": False, "realized_r": 9, "exit_utc": 1},
                  {"setup": "S04", "profile": "SCALP", "realized_known": True, "realized_r": 7, "exit_utc": 3},
                  {"setup": "S06B", "profile": "SWING", "realized_known": True, "realized_r": 7, "exit_utc": 3}]
        s = em.streams(trades, [])
        self.assertEqual(s["S04_SWING thật"][1], [1.5])

    def test_virtual_streams_filter_usd_and_use_add_result(self):
        ev = [{"status": "EVALUATED", "setup": "S06B", "profile": "SWING", "usd": "ALIGNED", "r": 1.0, "r_add": 2.0, "time": 2},
              {"status": "EVALUATED", "setup": "S06B", "profile": "SWING", "usd": "COUNTER", "r": 5.0, "time": 1},
              {"status": "BLOCKED", "setup": "S06B", "profile": "SWING", "usd": "ALIGNED", "r": 5.0, "time": 3}]
        s = em.streams([], ev)
        self.assertEqual(s["S06B_SWING ảo lọc USD"][1], [1.0])
        self.assertEqual(s["S06B_SWING ảo lọc USD + bồi"][1], [2.0])

    def test_text_recommends_shadow_only_on_alarm(self):
        ok = em.run([], [], em.load_params())
        self.assertNotIn("SHADOW", em.text(ok, 0))
        bad = {"x": dict(em.check([-1.0] * 30, P), params="S04_SWING")}
        self.assertIn("SHADOW", em.text(bad, 0))


if __name__ == "__main__":
    unittest.main()
