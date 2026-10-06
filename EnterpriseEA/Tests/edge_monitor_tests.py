"""G37: edge monitor (research/g10/edge_monitor.py, edge_params.json) and its Telegram wiring (/edge, daily check)."""
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research" / "g10"))
sys.path.insert(0, str(ROOT / "bridge"))

import edge_monitor as em  # noqa: E402
from telegram_gateway_tests import GatewayCase, OP, msg  # noqa: E402

PARAMS = em.load_params()


class ParamsTests(unittest.TestCase):
    def test_every_stream_calibrated(self):
        for key in ("S04_SWING", "S06B_SWING_USD", "S06B_SWING_USD_ADD", "T2_POSITION"):
            p = PARAMS[key]
            self.assertGreater(p["mean"], 0)
            self.assertAlmostEqual(p["k"], p["mean"] / 2)
            self.assertGreater(p["h_alarm"], p["h_warn"])
            self.assertGreaterEqual(p["arl0_alarm"], 250)            # rare false alarm when the edge holds
            self.assertGreaterEqual(p["arl0_warn"], 60)
            self.assertLess(p["detection"]["mean_0"]["median"], 250)  # an edge gone is caught faster
            dd = p["drawdown"]
            self.assertLessEqual(dd["20"]["p95"], dd["20"]["p99"])
            self.assertLessEqual(dd["20"]["p99"], dd["100"]["p99"])   # longer runs, deeper drawdowns

    def test_monitor_streams_use_existing_params(self):
        names = em.streams([], [])
        self.assertEqual(set(names), {"S04_SWING thật", "S04_SWING ảo", "S06B_SWING ảo lọc USD", "S06B_SWING ảo lọc USD + bồi",
                                      "T2_POSITION ảo"})
        for key, _ in names.values():
            self.assertIn(key, PARAMS)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.p = PARAMS["S06B_SWING_USD"]

    def test_no_data(self):
        self.assertEqual(em.check([], self.p)["status"], "NO_DATA")

    def test_research_like_results_rarely_alarm(self):
        rnd = random.Random(1)
        alarms = oks = 0
        for _ in range(200):
            # 40 trades with the research mean and spread: the edge is intact
            rs = [rnd.gauss(self.p["mean"], self.p["sd"]) for _ in range(40)]
            st = em.check(rs, self.p)["status"]
            alarms += st == "ALARM"
            oks += st == "OK"
        self.assertLessEqual(alarms, 20)            # at most 10% false alarms over 40 trades
        self.assertGreaterEqual(oks, 120)

    def test_edge_gone_is_caught(self):
        rnd = random.Random(2)
        caught = sum(em.check([rnd.gauss(-0.1, self.p["sd"]) for _ in range(80)], self.p)["status"] == "ALARM"
                     for _ in range(200))
        self.assertGreaterEqual(caught, 120)        # most losing runs of 80 trades raise the alarm

    def test_steady_losses_alarm(self):
        r = em.check([-1.0] * 15, self.p)
        self.assertEqual(r["status"], "ALARM")
        self.assertTrue(any("CUSUM" in x for x in r["reasons"]))
        self.assertTrue(any("sụt" in x for x in r["reasons"]))

    def test_warn_before_alarm(self):
        p = self.p
        steps = int(p["h_warn"] / (p["k"] + 1.0)) + 1           # each -1R adds k + 1 to the CUSUM
        r = em.check([-1.0] * steps, p)
        self.assertIn(r["status"], ("WARN", "ALARM"))
        self.assertGreater(r["cusum"], p["h_warn"])

    def test_cusum_resets_on_wins(self):
        r = em.check([-1.0, -1.0, 3.0, 3.0, -1.0], self.p)
        self.assertLess(r["cusum"], 2.0)

    def test_mean_bound_needs_twenty_trades(self):
        p = dict(self.p, h_alarm=1e9, h_warn=1e9, drawdown={"300": {"p95": 1e9, "p99": 1e9}})
        small = em.check([-0.5] * 19, p)
        big = em.check([-0.5] * 20, p)
        self.assertEqual(small["status"], "OK")
        self.assertEqual(big["status"], "ALARM")
        self.assertTrue(any("cận trên" in x for x in big["reasons"]))

    def test_dd_limit_picks_next_tabulated_count(self):
        table = {"10": {"p95": 1.0, "p99": 2.0}, "20": {"p95": 3.0, "p99": 4.0}}
        self.assertEqual(em.dd_limit(table, 5, "p99"), 2.0)
        self.assertEqual(em.dd_limit(table, 11, "p95"), 3.0)
        self.assertEqual(em.dd_limit(table, 99, "p99"), 4.0)


class StreamTests(unittest.TestCase):
    def test_sources(self):
        trades = [{"setup": "S04", "profile": "SWING", "realized_known": True, "realized_r": 1.5, "exit_utc": 2},
                  {"setup": "S04", "profile": "SWING", "realized_known": True, "realized_r": -1.0, "exit_utc": 1},
                  {"setup": "S04", "profile": "SWING", "realized_known": False, "realized_r": None, "exit_utc": 3},
                  {"setup": "S02", "profile": "SWING", "realized_known": True, "realized_r": 2.0, "exit_utc": 4}]
        ev = [{"setup": "S04", "profile": "SWING", "status": "EVALUATED", "time": 5, "r": 0.5},
              {"setup": "S04", "profile": "SWING", "status": "NO_BARS_YET", "time": 6, "r": 0.0},
              {"setup": "S06B", "profile": "SWING", "status": "EVALUATED", "time": 7, "r": 3.0, "r_add": 5.0, "usd": "ALIGNED"},
              {"setup": "S06B", "profile": "SWING", "status": "EVALUATED", "time": 8, "r": -1.0, "usd": "COUNTER"},
              {"setup": "S06B", "profile": "SWING", "status": "EVALUATED", "time": 9, "r": -1.0, "usd": "ALIGNED"}]
        s = em.streams(trades, ev)
        self.assertEqual(s["S04_SWING thật"][1], [-1.0, 1.5])         # exit order, known results only
        self.assertEqual(s["S04_SWING ảo"][1], [0.5])
        self.assertEqual(s["S06B_SWING ảo lọc USD"][1], [3.0, -1.0])   # aligned only
        self.assertEqual(s["S06B_SWING ảo lọc USD + bồi"][1], [5.0, -1.0])

    def test_text_proposes_shadow_only_on_alarm(self):
        res = em.run([], [{"setup": "S04", "profile": "SWING", "status": "EVALUATED", "time": t, "r": -1.0}
                          for t in range(30)], PARAMS)
        self.assertEqual(res["S04_SWING ảo"]["status"], "ALARM")
        self.assertIn("SHADOW", em.text(res, 0))
        quiet = em.run([], [], PARAMS)
        self.assertNotIn("SHADOW", em.text(quiet, 0))


class FakeProc:
    def __init__(self, out="", code=0):
        self.out, self.returncode = out, code

    def poll(self):
        return self.returncode

    def communicate(self):
        return self.out.encode("utf-8"), b""

    def kill(self):
        pass


class GatewayEdgeTests(GatewayCase):
    def edge_gateway(self, out="Theo dõi lợi thế: OK"):
        import telegram_gateway as tg
        self.runs = []

        def runner():
            self.runs.append(1)
            return FakeProc(out)
        return tg.Gateway(self.root, self.config, self.api, "", clock=self.clock, edge_runner=runner)

    def test_edge_command_replies_with_the_report(self):
        self.gw = self.edge_gateway("Theo dõi lợi thế (từ 2026-10-06)\nOK S04_SWING thật: 3 lệnh")
        self.feed(msg(1, OP, "/edge"))
        self.feed()
        texts = self.texts()
        self.assertTrue(any("Đang kiểm tra lợi thế" in t for t in texts))
        self.assertTrue(any("S04_SWING thật: 3 lệnh" in t for t in texts))
        self.assertIn("/edge", self.gw.config and __import__("telegram_gateway").HELP_VIEWER)

    def test_daily_check_pushes_only_a_worse_status_once(self):
        self.config["notify"]["edge"] = True
        self.config["edge_local"] = "00:00"
        self.gw = self.edge_gateway()
        self.write("current/edge_monitor.json", {"streams": {
            "S04_SWING ảo": {"status": "ALARM", "n": 25, "mean": -0.4, "research_mean": 0.11, "reasons": ["CUSUM 14.0 > 13.0"]},
            "S06B_SWING ảo lọc USD": {"status": "OK", "n": 5, "mean": 0.5, "research_mean": 0.34, "reasons": []}}})
        self.feed()                      # starts the daily job
        self.feed()                      # collects it
        pushed = [m["text"] for m in self.api.sent if m["chat_id"] == OP and "lợi thế" in m["text"]]
        self.assertEqual(len(pushed), 1)          # one push per user (operator and viewer)
        self.assertIn("BÁO ĐỘNG lợi thế S04_SWING ảo", pushed[0])
        self.assertIn("SHADOW", pushed[0])
        self.assertNotIn("S06B", pushed[0])
        self.assertEqual(len(self.runs), 1)
        self.feed()                      # same day: no second run, no second push
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(len([m for m in self.api.sent if m["chat_id"] == OP and "lợi thế" in m["text"]]), 1)
        self.assertEqual(self.gw.state["edge_status"]["S04_SWING ảo"], "ALARM")

    def test_daily_check_off_by_config(self):
        self.config["notify"]["edge"] = False
        self.config["edge_local"] = "00:00"
        self.gw = self.edge_gateway()
        self.feed()
        self.assertEqual(self.runs, [])


if __name__ == "__main__":
    unittest.main()
