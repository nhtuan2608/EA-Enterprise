"""Telegram /session (17/10/2026): sign 24h/7d with a /confirm code, revoke at once, AI intent for both."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_bridge as ab  # noqa: E402
import telegram_gateway as tg  # noqa: E402
from contract_tests import schema_errors  # noqa: E402
from telegram_gateway_tests import GatewayCase, OP, VIEWER, msg  # noqa: E402

SCHEMA = json.loads((ROOT / "schemas" / "remote-command.schema.json").read_text(encoding="utf-8"))


class SessionCase(GatewayCase):
    def result(self, cid, **fields):
        self.write(f"current/remote/results/{cid}.json", {"command_id": cid, **fields})
        self.gw.run_once(poll_timeout=0)


class SessionCommandTests(SessionCase):
    def test_sign_7d_sends_code_only_after_ea_accepts_and_confirm_signs(self):
        self.feed(msg(1, OP, "/session 7d"))
        c = self.commands()[0]
        self.assertEqual((c["action"], c["session_seconds"]), ("REQUEST_SESSION_SIGN", 7 * 86400))
        self.assertRegex(c["confirmation_nonce"], r"^\d{6}$")
        self.assertLessEqual(c["nonce_expires_at_utc"] - c["issued_at_utc"], 120)
        self.assertEqual(schema_errors(SCHEMA, c), [])
        self.assertFalse(any(c["confirmation_nonce"] in t for t in self.texts()))
        self.result(c["command_id"], applied=True, status="VALIDATED_PENDING_COMMIT",
                    reason_codes=["SESSION_SIGN_CONFIRMATION_PENDING"])
        self.assertIn(f"/confirm {c['confirmation_nonce']}", self.texts()[-1])
        self.assertIn("7 ngày", self.texts()[-1])
        self.write("current/live_session.json", {"session_id": "session-1", "status": "ACTIVE", "revoked_at_utc": 0,
                                                 "valid_until_utc": self.clock.t + 7 * 86400,
                                                 "allowed_symbols": "XAUUSD.r", "risk_policy_id": "CUSTOM"})
        self.feed(msg(2, OP, f"/confirm {c['confirmation_nonce']}"))
        confirm = self.commands()[-1]
        self.assertEqual((confirm["action"], confirm["confirmation_nonce"]),
                         ("CONFIRM_SESSION_SIGN", c["confirmation_nonce"]))
        self.assertEqual(schema_errors(SCHEMA, confirm), [])
        self.result(confirm["command_id"], applied=True, status="VALIDATED_PENDING_COMMIT", reason_codes=["SESSION_SIGNED"])
        self.assertIn("EA đã cấp phiên live", self.texts()[-1])
        self.assertIn("session-1: ACTIVE", self.texts()[-1])

    def test_unknown_code_still_goes_to_resume(self):
        self.feed(msg(1, OP, "/confirm 654321"))
        self.assertEqual(self.commands()[0]["action"], "CONFIRM_RESUME")

    def test_session_code_expires_with_the_challenge(self):
        self.feed(msg(1, OP, "/session 24h"))
        c = self.commands()[0]
        self.result(c["command_id"], applied=True, status="VALIDATED_PENDING_COMMIT")
        self.clock.t += tg.RESUME_TTL + 1
        self.gw.run_once(poll_timeout=0)
        self.feed(msg(2, OP, f"/confirm {c['confirmation_nonce']}"))
        self.assertEqual(self.commands()[-1]["action"], "CONFIRM_RESUME")   # EA rejects it: wrong challenge

    def test_revoke_needs_no_code(self):
        self.feed(msg(1, OP, "/session revoke"))
        c = self.commands()[0]
        self.assertEqual((c["action"], c["confirmation_nonce"], c["session_seconds"]), ("REVOKE_SESSION", "", 0))
        self.assertEqual(schema_errors(SCHEMA, c), [])
        self.result(c["command_id"], applied=True, status="VALIDATED_PENDING_COMMIT", reason_codes=["SESSION_REVOKED"])
        self.assertIn("EA đã thu hồi phiên live", self.texts()[-1])

    def test_disabled_input_is_explained(self):
        self.feed(msg(1, OP, "/session 24h"))
        c = self.commands()[0]
        self.result(c["command_id"], applied=False, status="REJECTED", state_after="RUNNING",
                    reason_codes=["SESSION_REMOTE_SIGN_DISABLED"])
        self.assertIn("InpSessionRemoteSignAllowed=true", self.texts()[-1])

    def test_viewer_and_bad_syntax_send_nothing(self):
        self.feed(msg(1, VIEWER, "/session 7d"), msg(2, OP, "/session 3d"))
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.texts()[0], "Lệnh này chỉ dành cho operator.")
        self.assertIn("Cú pháp: /session", self.texts()[1])

    def test_status_without_argument(self):
        self.feed(msg(1, OP, "/session"))
        self.assertEqual(self.texts()[-1], "Chưa có phiên live nào.")
        self.write("current/live_session.json", {"session_id": "session-2", "status": "REVOKED", "revoked_at_utc": 5})
        self.feed(msg(2, OP, "/session"))
        self.assertIn("session-2: REVOKED", self.texts()[-1])
        self.assertEqual(self.commands(), [])


class SessionIntentTests(SessionCase):
    def ask(self, update_id, text, **answer):
        self.feed(msg(update_id, OP, text))
        reqs = sorted((self.root / "ai" / "requests").glob("*.json"))
        req = json.loads(reqs[-1].read_text(encoding="utf-8"))
        self.write(f"ai/responses/{req['request_id']}.json", {"request_id": req["request_id"], "status": "OK", **answer})
        self.gw.run_once(poll_timeout=0)
        return req

    def test_ai_sign_7d_still_needs_confirm(self):
        req = self.ask(1, "cấp phiên 7 ngày", summary="Cấp 7 ngày",
                       recommendations=[{"action": "SESSION_SIGN_7D", "target": "SESSION", "proposal": "cấp"}])
        self.assertIn("live_session", req["context"])
        c = self.commands()[0]
        self.assertEqual((c["action"], c["session_seconds"]), ("REQUEST_SESSION_SIGN", 7 * 86400))
        self.assertIn("AI hiểu là: CẤP phiên live 7 ngày (cần /confirm)", " ".join(self.texts()))

    def test_ai_revoke_is_sent_at_once(self):
        self.ask(1, "thu hồi phiên đi", summary="Thu hồi",
                 recommendations=[{"action": "SESSION_REVOKE", "target": "SESSION", "proposal": "thu hồi"}])
        self.assertEqual(self.commands()[0]["action"], "REVOKE_SESSION")

    def test_ai_two_requests_send_nothing(self):
        self.ask(1, "cấp phiên và tắt vhedge", summary="hai yêu cầu",
                 recommendations=[{"action": "SESSION_SIGN_24H", "target": "SESSION"},
                                  {"action": "BOT_DISABLE", "target": "VHEDGE"}])
        self.assertEqual(self.commands(), [])
        self.assertIn("không gửi lệnh nào", self.texts()[-1])


class BridgeSessionIntentTests(unittest.TestCase):
    def request(self, request_type, actions):
        return json.dumps({"schema_version": "1.0", "request_id": "tgi-000001-abcd", "request_type": request_type,
                           "created_at_utc": ab.utc_now(), "deadline_utc": ab.utc_now() + 60, "provider": "claude",
                           "allowed_actions": actions, "context": {"operator_message": "cấp phiên 7 ngày"}}).encode("utf-8")

    def test_session_actions_only_inside_bot_intent(self):
        req = ab.validate_request(self.request("BOT_INTENT", ["SESSION_SIGN_7D", "SESSION_REVOKE"]))
        ok = ab.validate_answer({"summary": "x", "recommendations": [{"action": "SESSION_SIGN_7D", "target": "SESSION"}]},
                                req)
        self.assertEqual(ok["recommendations"][0]["action"], "SESSION_SIGN_7D")
        with self.assertRaises(ab.BridgeError):
            ab.validate_request(self.request("ASK_AI", ["REPORT", "SESSION_SIGN_7D"]))

    def test_prompt_names_the_session_actions(self):
        prompt = ab.build_prompt(ab.validate_request(self.request("BOT_INTENT", ["SESSION_SIGN_24H", "SESSION_SIGN_7D"])))
        self.assertIn("SESSION_SIGN_7D", prompt)
        self.assertIn("live_session", prompt)


if __name__ == "__main__":
    unittest.main()
