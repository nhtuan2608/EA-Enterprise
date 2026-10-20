"""Free-text questions on Telegram (20/10/2026): the AI answers from a read-only evidence bundle."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_bridge as ab  # noqa: E402
import operator_evidence as oe  # noqa: E402
from telegram_gateway_tests import GatewayCase, OP, msg  # noqa: E402

NOW = 1_800_000_000


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.terminal = Path(self.tmp.name) / "terminal"
        self.root = self.terminal / "MQL5" / "Files" / "EnterpriseEA"
        (self.root / "logs").mkdir(parents=True)
        (self.root / "current").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def jsonl(self, rel, rows):
        (self.root / rel).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_bundle_holds_the_window_and_the_reasons(self):
        (self.root / "current" / "live_status.json").write_text(json.dumps(
            {"written_at_utc": NOW - 20, "live_trade_armed": True, "session": "ACTIVE", "last_reason": "X"}))
        (self.root / "current" / "account_snapshot.json").write_text(json.dumps({"balance": 0.72, "equity": 0.72}))
        (self.root / "current" / "symbol_registry.json").write_text(json.dumps({"symbols": [
            {"canonical_symbol": "XAUUSD", "broker_symbol": "XAUUSD.r"}, {"canonical_symbol": "ETHUSD", "broker_symbol": ""}]}))
        self.jsonl("logs/candidates.jsonl", [
            {"first_seen_utc": NOW - 90000, "closed_utc": NOW - 90000, "setup": "OLD"},
            {"first_seen_utc": NOW - 3600, "closed_utc": NOW - 3000, "setup": "S07", "symbol": "XAUUSD",
             "timeframe": "M30", "direction": 1, "mode": "LIVE", "disposition": "NOT_EXECUTED",
             "reason": "LIVE_VOLUME_BELOW_SYMBOL_MINIMUM"}])
        self.jsonl("logs/audit.jsonl", [
            {"event_type": "RUNTIME_REFRESHED", "occurred_at_utc": iso(NOW - 60)},
            {"event_type": "RUNTIME_REFRESH_FAILED", "occurred_at_utc": iso(NOW - 60)},
            {"event_type": "ENTRY_BLOCKED", "occurred_at_utc": iso(NOW - 1800), "symbol": "XAUUSD",
             "reason_codes": ["ORDER_SEND_FAILED_10019"], "details": {"retcode": 10019}},
            {"event_type": "S06_SHADOW_CANDIDATE", "occurred_at_utc": iso(NOW - 1200), "symbol": "EURUSD",
             "details": {"setup": "S06", "entry": 1.1, "sl": 1.09, "tp": 1.13, "volume": 1.4, "secret": "no"}}])
        self.jsonl("logs/bots-202701.jsonl", [
            {"at_utc": NOW - 600, "bot": "XRT", "event": "NEAR", "text": "gần"},
            {"at_utc": NOW - 500, "bot": "CTXLIMIT", "event": "DECISION", "text": "dự báo dưới ngưỡng"}])
        day = time.strftime("%Y%m%d", time.gmtime(NOW))
        (self.terminal / "logs").mkdir()
        (self.terminal / "logs" / f"{day}.log").write_bytes(
            "AB\t0\t10:00:00.000\tTrades\t'1': failed market buy 0.01 XAUUSD.r [No money]\r\n"
            "CD\t0\t10:00:01.000\tNetwork\tscanning network\r\n".encode("utf-16"))
        d = oe.collect(self.root, NOW, 24)
        self.assertTrue(d["ea"]["running"])
        self.assertEqual(d["account"]["balance"], 0.72)
        self.assertEqual(d["symbols"], {"XAUUSD": "XAUUSD.r", "ETHUSD": ""})
        self.assertEqual([s["reason"] for s in d["signals"]], ["LIVE_VOLUME_BELOW_SYMBOL_MINIMUM"])  # window only
        self.assertEqual([e["event"] for e in d["ea_events"]], ["ENTRY_BLOCKED", "S06_SHADOW_CANDIDATE"])
        self.assertEqual(d["runtime_refresh_failed"], 1)
        self.assertEqual(d["ea_events"][1]["plan"], {"setup": "S06", "entry": 1.1, "sl": 1.09, "tp": 1.13, "volume": 1.4})
        self.assertEqual([j["event"] for j in d["bot_journal"]], ["DECISION"])                    # NEAR left out
        self.assertEqual(len(d["mt5_journal"]), 1)
        self.assertIn("[No money]", d["mt5_journal"][0])

    def test_bundle_fits_the_request_budget(self):
        self.jsonl("logs/candidates.jsonl", [{"first_seen_utc": NOW - 60, "closed_utc": NOW - 60, "setup": "S07",
                                              "reason": "x" * 300} for _ in range(400)])
        d = oe.collect(self.root, NOW, 24)
        self.assertLessEqual(len(json.dumps(d, ensure_ascii=False).encode("utf-8")), oe.MAX_BYTES)
        self.assertGreater(len(d["signals"]), 0)


class ChatTests(GatewayCase):
    def request(self):
        reqs = sorted((self.root / "ai" / "requests").glob("*.json"))
        return json.loads(reqs[-1].read_text(encoding="utf-8"))

    def test_question_is_answered_as_a_report_and_never_a_command(self):
        self.feed(msg(1, OP, "sáng giờ có lệnh nào không, sao không vào được?"))
        req = self.request()
        self.assertEqual(req["request_type"], "OPERATOR_CHAT")
        self.assertIn("evidence", req["context"])
        rid = req["request_id"]
        self.write(f"ai/responses/{rid}.json", {"request_id": rid, "status": "OK",
                                                "summary": "Chưa có lệnh thật: số dư 0.72 USC quá nhỏ.",
                                                "findings": [{"severity": "WARN", "detail": "khối lượng dưới mức tối thiểu"}],
                                                "recommendations": [{"action": "REPORT", "target": "S07", "proposal": "x"}]})
        self.gw.run_once(poll_timeout=0)
        answer = self.api.sent[-1]
        self.assertTrue(answer["text"].startswith("💬 <b>Trả lời</b> · AI"))
        self.assertEqual(answer.get("parse_mode"), "HTML")
        self.assertIn("số dư 0.72 USC", answer["text"])
        self.assertEqual(self.commands(), [])

    def test_ask_carries_the_same_evidence(self):
        self.feed(msg(1, OP, "/ask hôm nay có lệnh nào không"))
        req = self.request()
        self.assertEqual(req["request_type"], "ASK_AI")
        self.assertIn("signals", req["context"]["evidence"])


class BridgeChatTests(unittest.TestCase):
    def request(self, request_type, actions):
        return json.dumps({"schema_version": "1.0", "request_id": "tgi-000009-abcd", "request_type": request_type,
                           "created_at_utc": ab.utc_now(), "deadline_utc": ab.utc_now() + 60, "provider": "claude",
                           "allowed_actions": actions, "context": {"operator_message": "có lệnh nào không"}}).encode()

    def test_operator_chat_may_propose_a_command_ask_may_not(self):
        req = ab.validate_request(self.request("OPERATOR_CHAT", ["REPORT", "WARN", "BOT_DISABLE", "SESSION_REVOKE"]))
        self.assertIn("evidence", ab.build_prompt(req))
        with self.assertRaises(ab.BridgeError):
            ab.validate_request(self.request("ASK_AI", ["REPORT", "BOT_DISABLE"]))


if __name__ == "__main__":
    unittest.main()
