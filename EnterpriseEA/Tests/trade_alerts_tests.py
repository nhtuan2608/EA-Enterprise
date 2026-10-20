"""Telegram alerts for bot orders and MT5 rejections, and the digest's missed signals (20/10/2026)."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import trade_alerts as ta  # noqa: E402
from telegram_gateway_tests import GatewayCase  # noqa: E402

TITLES = {"VHEDGE": "VHedge G119", "XRT": "XauRegime", "CTXLIMIT": "CtxLimit"}


class MessageTests(unittest.TestCase):
    def test_bot_lines(self):
        live = {"bot": "XRT", "event": "FILL", "mode": "LIVE", "server": "2026.10.20 15:00", "text": "khớp BÁN 0.01 lot"}
        self.assertTrue(ta.bot_message(live, TITLES).startswith("✅ BOT KHỚP LỆNH · XauRegime\nkhớp BÁN 0.01 lot"))
        self.assertIsNone(ta.bot_message({**live, "mode": "SHADOW"}, TITLES))
        self.assertIsNone(ta.bot_message({**live, "event": "NEAR"}, TITLES))
        failed = {**live, "event": "DECISION", "text": "broker từ chối lệnh market (mã 10019)"}
        self.assertTrue(ta.bot_message(failed, TITLES).startswith("❗ BOT LỖI ĐẶT LỆNH · XauRegime"))
        self.assertIsNone(ta.bot_message({**live, "event": "DECISION", "text": "dự báo dưới ngưỡng"}, TITLES))

    def test_mt5_journal_lines(self):
        line = "AB\t0\t10:00:00.000\tTrades\t'1': failed market sell 0.01 XAUUSD.r sl: 4180.00 [No money]"
        text = ta.mt5_failure_message(line)
        self.assertTrue(text.startswith("❗ LỖI GỬI LỆNH (MT5)\n'1': failed market sell"))
        self.assertIn("Nghĩa là: không đủ tiền ký quỹ", text)
        self.assertIn("khối lượng không hợp lệ", ta.mt5_failure_message("x\t0\tt\tTrades\tfailed buy limit 0.001 X [Invalid volume]"))
        for quiet in ("CD\t0\t10:00:01.000\tNetwork\t'1': scanning network finished",
                      "RG\t2\t14:36:34\tExperts\tinitializing of EnterpriseEA_Bots (XAUUSD.r,M5) failed with code 32767 "
                      "(incorrect parameters)"):
            self.assertIsNone(ta.mt5_failure_message(quiet))

    def test_utf16_tail_returns_only_complete_new_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "20261020.log"
            path.write_bytes("A\tline one\r\nB\tline two\r\n".encode("utf-16"))
            lines, pos = ta.tail_utf16(path, 0)
            self.assertEqual(lines, ["A\tline one", "B\tline two"])
            with open(path, "ab") as fh:
                fh.write("C\tline three\r\nD\tpart".encode("utf-16-le"))
            lines, pos2 = ta.tail_utf16(path, pos)
            self.assertEqual(lines, ["C\tline three"])
            self.assertEqual(ta.tail_utf16(path, pos2)[0], [])


class GatewayAlertTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.terminal = self.root / "terminal"
        self.root = self.terminal / "MQL5" / "Files" / "EnterpriseEA"
        (self.root / "current").mkdir(parents=True)
        (self.root / "logs").mkdir()
        self.write("current/operator_mode.json", {"mode": "RUNNING", "account_id": "a", "state_version": 3})
        self.journal = self.root / "logs" / f"bots-{time.strftime('%Y%m', time.gmtime(self.clock.t))}.jsonl"
        self.mt5 = self.terminal / "logs" / f"{time.strftime('%Y%m%d', time.gmtime(self.clock.t))}.log"
        self.mt5.parent.mkdir()
        self.journal.write_text(json.dumps({"bot": "VHEDGE", "event": "ENTRY", "mode": "LIVE", "text": "cũ"}) + "\n",
                                encoding="utf-8")
        self.mt5.write_bytes("X\t0\tt\tTrades\tfailed market buy 0.01 XAUUSD.r [No money]\r\n".encode("utf-16"))
        self.gw = self.new_gateway()

    def append_bot(self, row):
        with open(self.journal, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def append_mt5(self, line):
        with open(self.mt5, "ab") as fh:
            fh.write((line + "\r\n").encode("utf-16-le"))

    def test_new_live_orders_and_rejections_reach_telegram_once(self):
        self.gw.run_once(poll_timeout=0)
        self.assertFalse(any("cũ" in t or "No money" in t for t in self.texts()))       # history is not replayed
        self.append_bot({"bot": "VHEDGE", "event": "FILL", "mode": "LIVE", "server": "s", "text": "khớp MUA 0.01"})
        self.append_bot({"bot": "XRT", "event": "ENTRY", "mode": "SHADOW", "server": "s", "text": "ảo"})
        self.append_mt5("Y\t0\tt\tTrades\tfailed market sell 0.01 XAUUSD.r [No money]")
        self.append_mt5("Y\t0\tt\tTrades\tfailed market sell 0.01 XAUUSD.r [No money]")
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(t.startswith("✅ BOT KHỚP LỆNH · VHedge G119") for t in self.texts()), 2)  # 2 users
        self.assertFalse(any("ảo" in t for t in self.texts()))
        self.assertEqual(sum(t.startswith("❗ LỖI GỬI LỆNH (MT5)") for t in self.texts()), 2)          # once each

    def test_digest_groups_live_signals_that_did_not_enter(self):
        start, end = self.clock.t - 3600, self.clock.t + 60
        rows = [{"closed_utc": self.clock.t - 60, "mode": "LIVE", "disposition": "NOT_EXECUTED", "setup": "S07AS",
                 "symbol": "XAUUSD", "timeframe": "H1", "profile": "SWING", "reason": "S07A_NO_OPEN_BASE"}] * 2
        (self.root / "logs" / "candidates.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        self.append_bot({"at_utc": self.clock.t - 30, "bot": "XRT", "event": "SKIP", "mode": "LIVE",
                         "text": "chế độ D1 GIẢM"})
        text = self.gw.digest_text(start, end)
        self.assertIn("Tín hiệu LIVE không vào được:\n  • S07AS XAUUSD H1: S07A_NO_OPEN_BASE ×2", text)
        self.assertIn("Bot LIVE bị chặn / bỏ qua:\n  • XauRegime: chế độ D1 GIẢM ×1", text)


if __name__ == "__main__":
    unittest.main()
