"""Bots host on Telegram: /bots, /bot on|off, /confirm routing, natural-language switch through the AI bridge."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_bridge as ab  # noqa: E402
import telegram_gateway as tg  # noqa: E402
from telegram_gateway_tests import GatewayCase, OP, VIEWER, msg  # noqa: E402

STATUS = {"document_version": "bots-status-v1.0.0", "account_id": "fnv1a32:abc", "config_version": "observer-v1.0.0",
          "state_version": 4, "state_loaded": True, "symbol": "XAUUSD.r", "pending_bot": "",
          "guard": {"execution_live": True, "operator_paused": False, "open_risk_pct": 3.2, "max_open_risk_pct": 12,
                    "daily_loss_pct": 6},
          "bots": [{"code": "S07", "title": "S07", "active": True, "mode": "LIVE", "open": 1, "today": 12.5,
                    "floating": -3.0, "status": "engine: waiting"},
                   {"code": "VHEDGE", "title": "VHedge G119", "active": False, "mode": "SHADOW", "open": 0, "today": 0,
                    "floating": 0, "status": "INACTIVE"}],
          "written_at_utc": 1_800_000_000}


class BotsCase(GatewayCase):
    def setUp(self):
        super().setUp()
        self.write("current/bots_status.json", STATUS)

    def bot_commands(self):
        d = self.root / "current" / "remote" / "bot_commands"
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []

    def result(self, cid, **fields):
        self.write(f"current/remote/results/{cid}.json", {"command_id": cid, **fields})
        self.gw.run_once(poll_timeout=0)


class BotCommandTests(BotsCase):
    def test_bots_list(self):
        self.feed(msg(1, VIEWER, "/bots"))
        text = self.texts()[0]
        self.assertIn("[ON ] S07 (S07) LIVE", text)
        self.assertIn("[OFF] VHedge G119 (VHEDGE) SHADOW", text)
        self.assertIn("Guard: đã ARM", text)

    def test_viewer_cannot_switch(self):
        self.feed(msg(1, VIEWER, "/bot off s07"), msg(2, VIEWER, "tắt s07 đi"))
        self.assertEqual(self.bot_commands(), [])
        self.assertFalse((self.root / "ai" / "requests").exists() and any((self.root / "ai" / "requests").glob("*.json")))

    def test_off_is_one_command_without_nonce(self):
        self.feed(msg(1, OP, "/bot off vhedge"))
        c = self.bot_commands()[0]
        self.assertEqual((c["schema_version"], c["action"], c["bot"], c["confirmation_nonce"]),
                         ("bot-command-v1.0.0", "BOT_DISABLE", "VHEDGE", ""))
        self.assertEqual((c["account_id"], c["config_version"], c["role"]), ("fnv1a32:abc", "observer-v1.0.0", "OPERATOR"))
        self.assertTrue(c["private_chat_attested"] and c["sender_authenticated"] and c["source_authenticated"])
        self.result(c["command_id"], applied=True, status="APPLIED", state_before="ACTIVE", state_after="INACTIVE",
                    reason_codes=["BOT_DISABLED_TELEGRAM"])
        self.assertIn("EA đã tắt VHedge G119: ACTIVE -> INACTIVE (lệnh đang mở vẫn được quản lý)", self.texts()[-1])

    def test_on_needs_the_nonce_then_confirm_goes_to_the_bot(self):
        self.feed(msg(1, OP, "/bot on g119"))
        c = self.bot_commands()[0]
        self.assertEqual((c["action"], c["bot"]), ("BOT_REQUEST_ENABLE", "VHEDGE"))
        nonce = c["confirmation_nonce"]
        self.assertRegex(nonce, r"^\d{6}$")
        self.assertLessEqual(c["nonce_expires_at_utc"] - c["issued_at_utc"], 120)
        self.assertFalse(any(nonce in t for t in self.texts()))                 # only after the EA accepted
        self.result(c["command_id"], applied=True, status="APPLIED", reason_codes=["BOT_ENABLE_CONFIRMATION_PENDING"])
        self.assertIn(f"/confirm {nonce}", self.texts()[-1])
        self.feed(msg(2, OP, f"/confirm {nonce}"))
        c2 = self.bot_commands()[-1]
        self.assertEqual((c2["action"], c2["bot"], c2["confirmation_nonce"]), ("BOT_CONFIRM_ENABLE", "VHEDGE", nonce))
        self.assertEqual(self.commands(), [])                                    # not a resume
        self.assertGreater(c2["gateway_sequence"], c["gateway_sequence"])

    def test_unknown_confirm_is_still_a_resume(self):
        self.feed(msg(1, OP, "/confirm 654321"))
        self.assertEqual(self.commands()[0]["action"], "CONFIRM_RESUME")
        self.assertEqual(self.bot_commands(), [])

    def test_bad_syntax_and_missing_status(self):
        self.feed(msg(1, OP, "/bot on"), msg(2, OP, "/bot maybe s07"), msg(3, OP, "/bot off nothing"))
        self.assertEqual(self.bot_commands(), [])
        (self.root / "current" / "bots_status.json").unlink()
        self.feed(msg(4, OP, "/bot off s07"))
        self.assertEqual(self.bot_commands(), [])
        self.assertIn("EA chưa sẵn sàng cho lệnh bot", self.texts()[-1])

    def test_aliases(self):
        r = tg.Gateway.resolve_bot
        self.assertEqual([r("s07"), r("VHedge G119"), r("hedge"), r("xau regime"), r("xrt"), r("ctx"), r("ctxlimit"), r("abc")],
                         ["S07", "VHEDGE", "VHEDGE", "XRT", "XRT", "CTXLIMIT", "CTXLIMIT", ""])


class BotIntentTests(BotsCase):
    def intent_request(self):
        reqs = sorted((self.root / "ai" / "requests").glob("*.json"))
        self.assertEqual(len(reqs), 1)
        return json.loads(reqs[0].read_text(encoding="utf-8"))

    def answer(self, request_id, **fields):
        self.write(f"ai/responses/{request_id}.json", {"request_id": request_id, "status": "OK", **fields})
        self.gw.run_once(poll_timeout=0)

    def test_free_text_becomes_a_bot_intent_request(self):
        self.feed(msg(1, OP, "tắt VHedge đi nhé"))
        req = self.intent_request()
        self.assertEqual((req["request_type"], req["allowed_actions"]), ("BOT_INTENT", ["BOT_ENABLE", "BOT_DISABLE"]))
        self.assertEqual(req["context"]["operator_message"], "tắt VHedge đi nhé")
        self.assertEqual([b["code"] for b in req["context"]["bots"]], ["S07", "VHEDGE"])
        self.assertEqual(self.bot_commands(), [])                                # nothing until the AI answered

    def test_ai_disable_is_applied_as_a_standard_command(self):
        self.feed(msg(1, OP, "tắt VHedge đi"))
        rid = self.intent_request()["request_id"]
        self.answer(rid, summary="Tắt VHedge", recommendations=[{"action": "BOT_DISABLE", "target": "VHEDGE", "proposal": "tắt"}])
        self.assertIn("AI hiểu là: TẮT VHedge G119", " ".join(self.texts()))
        c = self.bot_commands()[0]
        self.assertEqual((c["action"], c["bot"]), ("BOT_DISABLE", "VHEDGE"))

    def test_ai_enable_still_needs_confirm(self):
        self.feed(msg(1, OP, "bật lại s07"))
        rid = self.intent_request()["request_id"]
        self.answer(rid, summary="Bật S07", recommendations=[{"action": "BOT_ENABLE", "target": "S07", "proposal": "bật"}])
        c = self.bot_commands()[0]
        self.assertEqual((c["action"], c["bot"]), ("BOT_REQUEST_ENABLE", "S07"))
        self.assertIn("(cần /confirm)", " ".join(self.texts()))

    def test_unclear_or_multiple_bots_send_nothing(self):
        self.feed(msg(1, OP, "thị trường hôm nay thế nào"))
        rid = self.intent_request()["request_id"]
        self.answer(rid, summary="Không phải yêu cầu bật/tắt", recommendations=[])
        self.feed(msg(2, OP, "tắt hết"))
        reqs = sorted((self.root / "ai" / "requests").glob("*.json"))
        rid2 = json.loads(reqs[-1].read_text(encoding="utf-8"))["request_id"]
        self.answer(rid2, summary="hai bot", recommendations=[{"action": "BOT_DISABLE", "target": "S07"},
                                                              {"action": "BOT_DISABLE", "target": "VHEDGE"}])
        self.assertEqual(self.bot_commands(), [])
        self.assertIn("không gửi lệnh nào", self.texts()[-1])

    def test_ai_error_and_timeout(self):
        self.feed(msg(1, OP, "tắt s07"))
        rid = self.intent_request()["request_id"]
        self.write(f"ai/responses/{rid}.json", {"request_id": rid, "status": "ERROR", "error": "AI_PROVIDER_TIMEOUT"})
        self.gw.run_once(poll_timeout=0)
        self.assertIn("AI lỗi: AI_PROVIDER_TIMEOUT", self.texts()[-1])
        self.feed(msg(2, OP, "tắt s07"))
        self.clock.t += tg.BOT_INTENT_WAIT + 1
        self.gw.run_once(poll_timeout=0)
        self.assertIn("AI chưa trả lời", self.texts()[-1])
        self.assertEqual(self.bot_commands(), [])


class BridgeBotIntentTests(unittest.TestCase):
    def request(self, request_type, actions):
        return json.dumps({"schema_version": "1.0", "request_id": "tgi-000001-abcd", "request_type": request_type,
                           "created_at_utc": ab.utc_now(), "deadline_utc": ab.utc_now() + 60, "provider": "claude",
                           "allowed_actions": actions, "context": {"operator_message": "tắt vhedge"}}).encode("utf-8")

    def test_bot_actions_only_inside_bot_intent(self):
        ab.validate_request(self.request("BOT_INTENT", ["BOT_ENABLE", "BOT_DISABLE"]))
        with self.assertRaises(ab.BridgeError):
            ab.validate_request(self.request("ASK_AI", ["REPORT", "BOT_DISABLE"]))

    def test_answer_outside_the_allowed_actions_is_rejected(self):
        req = ab.validate_request(self.request("BOT_INTENT", ["BOT_ENABLE", "BOT_DISABLE"]))
        with self.assertRaises(ab.BridgeError):
            ab.validate_answer({"summary": "x", "recommendations": [{"action": "PAUSE", "target": "S07"}]}, req)
        ok = ab.validate_answer({"summary": "x", "recommendations": [{"action": "BOT_DISABLE", "target": "VHEDGE"}]}, req)
        self.assertEqual(ok["recommendations"][0]["action"], "BOT_DISABLE")

    def test_prompt_task(self):
        req = ab.validate_request(self.request("BOT_INTENT", ["BOT_ENABLE", "BOT_DISABLE"]))
        prompt = ab.build_prompt(req)
        self.assertIn("operator_message", prompt)
        self.assertIn("BOT_ENABLE, BOT_DISABLE", prompt)


if __name__ == "__main__":
    unittest.main()
