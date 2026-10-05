"""G17 soak monitor (bridge/soak_monitor.py) and the Telegram /trades, /week, /soak commands."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import soak_monitor as sm  # noqa: E402
import telegram_gateway as tg  # noqa: E402
from telegram_gateway_tests import FakeApi, Clock, msg  # noqa: E402

DAY = 86400


def sample(at, pid=1, private=300.0, handles=1000, cpu_pct=None, failures=0, logs=10.0):
    s = {"at_utc": at, "process_found": True, "pid": pid, "cpu_seconds": 0.0, "working_set_mb": private,
         "private_mb": private, "handles": handles, "threads": 30, "refresh_failures": failures,
         "max_refresh_ms": 16, "logs_mb": logs}
    if cpu_pct is not None:
        s["cpu_pct"] = cpu_pct
    return s


class SoakMonitorTests(unittest.TestCase):
    def test_slope_per_day(self):
        self.assertAlmostEqual(sm.slope_per_day([(0, 100.0), (DAY, 150.0), (2 * DAY, 200.0)]), 50.0)
        self.assertEqual(sm.slope_per_day([(0, 1.0)]), 0.0)

    def test_stable_run_is_ok(self):
        rows = [sample(k * 300, cpu_pct=2.0) for k in range(200)]          # ~16.6 h, flat
        r = sm.report(rows)
        self.assertEqual((r["verdict"], r["flags"]), ("OK", []))
        self.assertGreaterEqual(r["hours"], 16)

    def test_leaks_and_budget_are_flagged(self):
        rows = [sample(k * 3600, private=300 + 5 * k, handles=1000 + 20 * k, cpu_pct=40.0, failures=k // 10)
                for k in range(24)]
        r = sm.report(rows)
        self.assertEqual(r["verdict"], "CHECK")
        for flag in ("MEMORY_CLIMBING", "HANDLES_CLIMBING", "CPU_ABOVE_BUDGET", "REFRESH_FAILURES"):
            self.assertIn(flag, r["flags"])

    def test_short_window_is_preliminary_and_restart_starts_new_run(self):
        rows = [sample(0, pid=1, private=900), sample(300, pid=2, cpu_pct=50.0), sample(600, pid=2, cpu_pct=50.0)]
        r = sm.report(rows)
        self.assertEqual((r["pid"], r["samples"], r["verdict"]), (2, 2, "PRELIMINARY"))
        self.assertEqual(sm.report([])["verdict"], "NOT_ENOUGH_DATA")

    def test_take_sample_computes_cpu_share_and_reads_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "current").mkdir()
            (root / "logs").mkdir()
            (root / "current" / "runtime_status.json").write_text(
                json.dumps({"runtime_state": "OBSERVING", "refresh_failure_count": 0, "max_refresh_duration_ms": 16}),
                encoding="utf-8")
            prev = {"at_utc": 1000, "pid": 7, "cpu_seconds": 10.0}
            s = sm.take_sample(root, {"pid": 7, "cpu_seconds": 40.0, "working_set_mb": 250.0, "private_mb": 280.0,
                                      "handles": 1100, "threads": 35}, prev, 1300)
        self.assertEqual(s["cpu_pct"], 10.0)
        self.assertEqual((s["runtime_state"], s["max_refresh_ms"]), ("OBSERVING", 16))

    def test_report_text(self):
        r = sm.report([sample(k * 300, cpu_pct=1.0) for k in range(10)])
        self.assertIn("RAM riêng", sm.report_text(r))
        self.assertIn("chưa đủ mẫu", sm.report_text(sm.report([])))


class FakeProc:
    def __init__(self, out=b"# Report\n|a|b|\n|---|---|\n**x**", code=0, done=True):
        self.out, self.code, self.done, self.killed = out, code, done, False
        self.returncode = code if done else None

    def poll(self):
        return self.code if self.done else None

    def communicate(self):
        return self.out, b"err"

    def kill(self):
        self.killed = True


class GatewayReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api, self.clock = FakeApi(), Clock()
        cfg = tg.load_config(None)
        cfg.update(operators=[111], viewers=[222])
        self.procs = []
        self.gw = tg.Gateway(self.root, cfg, self.api, "", clock=self.clock, runner=self.runner)

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self):
        p = self.procs.pop(0)
        return p

    def feed(self, *updates):
        self.api.updates = list(updates)
        self.gw.run_once(poll_timeout=0)

    def texts(self):
        return [m["text"] for m in self.api.sent]

    def test_trades_lists_recent_closed_trades(self):
        self.feed(msg(1, 222, "/trades"))
        self.assertEqual(self.texts()[-1], "Chưa có lệnh nào đã đóng.")
        (self.root / "logs").mkdir(exist_ok=True)
        rows = [{"symbol": "XAUUSD", "setup": "S06", "profile": "SWING", "direction": 1, "realized_known": True,
                 "realized_r": 3.0, "realized_money": 30.0, "exit_utc": 1_800_000_000, "exit_cause": "TP"},
                {"symbol": "EURUSD", "setup": "S02", "profile": "SCALP", "direction": -1, "realized_known": False,
                 "realized_r": None, "exit_utc": 1_800_000_100}]
        (self.root / "logs" / "trades.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        self.feed(msg(2, 222, "/trades"))
        text = self.texts()[-1]
        self.assertIn("XAUUSD S06/SWING BUY +3.00R (+30.00) TP", text)
        self.assertIn("EURUSD S02/SCALP SELL chưa rõ", text)
        self.assertIn("Tổng 1 lệnh có R: +3.00R", text)

    def test_week_runs_once_and_sends_plain_text(self):
        self.procs = [FakeProc()]
        self.feed(msg(1, 111, "/week"))                       # the fake job finishes in the same pass
        self.assertIn("Đang tính báo cáo tuần", self.texts()[-2])
        out = self.texts()[-1]
        self.assertIn("# Report", out)
        self.assertNotIn("|---", out)
        self.assertNotIn("**", out)
        self.feed(msg(2, 111, "/week"))                       # rate limit: one per 10 minutes
        self.assertIn("1 lần mỗi 10 phút", self.texts()[-1])

    def test_week_error_and_timeout(self):
        self.procs = [FakeProc(out=b"", code=1)]
        self.feed(msg(1, 111, "/week"))
        self.gw.run_once(poll_timeout=0)
        self.assertIn("Báo cáo tuần lỗi", self.texts()[-1])
        slow = FakeProc(done=False)
        self.procs = [slow]
        self.clock.t += 601
        self.feed(msg(2, 222, "/week"))
        self.clock.t += tg.WEEK_TIMEOUT + 1
        self.gw.run_once(poll_timeout=0)
        self.assertTrue(slow.killed)
        self.assertIn("quá thời gian", self.texts()[-1])

    def test_soak_command(self):
        self.feed(msg(1, 222, "/soak"))
        self.assertIn("chưa đủ mẫu", self.texts()[-1])

    def test_help_lists_new_commands(self):
        for cmd in ("/trades", "/week", "/soak"):
            self.assertIn(cmd, tg.HELP_VIEWER)


if __name__ == "__main__":
    unittest.main()
