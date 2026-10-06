"""Daily summary (master specification 13.3): Telegram digest at a local time and /today."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import telegram_gateway as tg  # noqa: E402
from telegram_gateway_tests import FakeApi, msg  # noqa: E402


def local(y, mo, d, h, mi):
    return int(time.mktime((y, mo, d, h, mi, 0, 0, 0, -1)))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class DigestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "logs").mkdir()
        (self.root / "current").mkdir()
        self.now = [local(2027, 3, 10, 12, 0)]
        self.api = FakeApi()
        cfg = tg.load_config(None)
        cfg["notify"]["edge"] = False      # G37: no real edge_monitor.py run here
        cfg.update(operators=[1], viewers=[2], digest_local="23:30")
        self.gw = tg.Gateway(self.root, cfg, self.api, "", clock=lambda: self.now[0])
        day = local(2027, 3, 10, 0, 0)
        self.write("logs/trades.jsonl", [
            {"exit_utc": day + 3600, "realized_known": True, "realized_r": 3.0, "realized_money": 30.0},
            {"exit_utc": day + 7200, "realized_known": True, "realized_r": -1.0, "realized_money": -10.0},
            {"exit_utc": day - 3600, "realized_known": True, "realized_r": 9.0, "realized_money": 90.0}])   # yesterday
        self.write("logs/candidates.jsonl", [
            {"closed_utc": day + 100, "setup": "S06", "profile": "SWING", "disposition": "EXECUTED"},
            {"closed_utc": day + 200, "setup": "S02", "profile": "SCALP", "disposition": "NOT_EXECUTED",
             "reason": "DUPLICATE_SAME_SIDE"},
            {"closed_utc": day + 300, "setup": "S02", "profile": "SCALP", "disposition": "NOT_EXECUTED",
             "reason": "NOT_EVALUATED:OPERATOR_PAUSED_ENTRIES"}])
        self.write("logs/audit.jsonl", [
            {"event_type": "NEWS_ENTRY_BLOCKED", "occurred_at_utc": iso(day + 500)},
            {"event_type": "NEWS_ENTRY_BLOCKED", "occurred_at_utc": iso(day + 600)},
            {"event_type": "EA_STOPPED", "occurred_at_utc": iso(day + 700), "reason_codes": ["DEINIT_REASON_9"]},
            {"event_type": "EA_STOPPED", "occurred_at_utc": iso(day - 700)},                              # yesterday
            {"event_type": "RUNTIME_REFRESHED", "occurred_at_utc": iso(day + 800)}])
        (self.root / "current" / "operator_mode.json").write_text(json.dumps({"mode": "RUNNING"}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, rows):
        (self.root / rel).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_digest_content(self):
        start, end = self.gw.local_day_bounds()
        text = self.gw.digest_text(start, end)
        self.assertIn("TÓM TẮT NGÀY 10/03", text)
        self.assertIn("Lệnh đóng: 2 (1 thắng), +2.00R, +20.00", text)
        self.assertIn("Candidate: 3 (S02/SCALP 2, S06/SWING 1)", text)
        self.assertIn("EXECUTED 1", text)
        self.assertIn("DUPLICATE_SAME_SIDE 1", text)
        self.assertIn("NOT_EVALUATED 1", text)
        self.assertIn("News Guard chặn vào lệnh: 2", text)
        self.assertIn("EA_STOPPED 1", text)
        self.assertIn("Vào lệnh (theo EA): RUNNING", text)

    def test_sent_once_after_the_configured_time(self):
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.api.sent, [])                                  # 12:00: too early
        self.now[0] = local(2027, 3, 10, 23, 31)
        self.gw.run_once(poll_timeout=0)
        self.gw.run_once(poll_timeout=0)
        digests = [m for m in self.api.sent if m["text"].startswith("TÓM TẮT NGÀY")]
        self.assertEqual(sorted(m["chat_id"] for m in digests), [1, 2])     # operator and viewer, once each
        self.now[0] = local(2027, 3, 11, 23, 45)
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(m["text"].startswith("TÓM TẮT NGÀY 11/03") for m in self.api.sent), 2)

    def test_disabled_and_on_demand(self):
        self.gw.config["notify"]["digest"] = False
        self.now[0] = local(2027, 3, 10, 23, 50)
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.api.sent, [])
        self.api.updates = [msg(5, 2, "/today")]
        self.gw.run_once(poll_timeout=0)
        self.assertTrue(self.api.sent[-1]["text"].startswith("TÓM TẮT NGÀY 10/03"))
        self.assertIn("/today", tg.HELP_VIEWER)

    def test_empty_day(self):
        for rel in ("logs/trades.jsonl", "logs/candidates.jsonl", "logs/audit.jsonl"):
            (self.root / rel).unlink()
        text = self.gw.digest_text(*self.gw.local_day_bounds())
        self.assertIn("Lệnh đóng: 0", text)
        self.assertIn("Candidate: 0", text)
        self.assertIn("Sự kiện hệ thống: không có", text)


if __name__ == "__main__":
    unittest.main()
