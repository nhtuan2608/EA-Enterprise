"""G19 Telegram gateway (bridge/telegram_gateway.py) against a fake Telegram API (TC-TG-01..08)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

import telegram_gateway as tg  # noqa: E402

OP, VIEWER, STRANGER = 111, 222, 333
TOKEN = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"


class FakeApi:
    def __init__(self):
        self.sent, self.updates, self.fail_sends = [], [], 0

    def call(self, method, params, timeout=35):
        if method == "getUpdates":
            out, self.updates = self.updates, []
            return {"ok": True, "result": out}
        if method == "sendMessage":
            if self.fail_sends:
                self.fail_sends -= 1
                raise ConnectionError(f"boom {TOKEN}")
            self.sent.append(params)
            return {"ok": True, "result": {}}
        raise AssertionError(method)


class Clock:
    def __init__(self, t=1_800_000_000):
        self.t = t

    def __call__(self):
        return self.t


def msg(update_id, uid, text, chat_id=None, chat_type="private", message_id=None):
    return {"update_id": update_id, "message": {"message_id": message_id or update_id, "text": text,
                                                "from": {"id": uid, "is_bot": False},
                                                "chat": {"id": uid if chat_id is None else chat_id, "type": chat_type}}}


class GatewayCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api, self.clock = FakeApi(), Clock()
        self.config = tg.load_config(None)
        self.config.update(operators=[OP], viewers=[VIEWER])
        self.config["notify"]["edge"] = False      # G37: no real edge_monitor.py run in the shared harness
        (self.root / "current").mkdir()
        self.write("current/operator_mode.json", {"document_version": "operator-mode-v1.0.0", "mode": "RUNNING",
                                                  "operator_paused": False, "account_id": "fnv1a32:abc",
                                                  "config_version": "observer-v1.0.0", "state_version": 3})
        self.gw = self.new_gateway()

    def tearDown(self):
        self.tmp.cleanup()

    def new_gateway(self):
        return tg.Gateway(self.root, self.config, self.api, TOKEN, clock=self.clock)

    def write(self, rel, payload):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")

    def feed(self, *updates):
        self.api.updates = list(updates)
        self.gw.run_once(poll_timeout=0)

    def commands(self):
        d = self.root / "current" / "remote" / "commands"
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []

    def texts(self):
        return [m["text"] for m in self.api.sent]


class AuthTests(GatewayCase):
    def test_tc_tg_01_only_private_allowlisted_chats(self):
        self.feed(msg(1, STRANGER, "/pause"), msg(2, OP, "/pause", chat_type="group", chat_id=-5),
                  msg(3, OP, "/pause", chat_id=999), msg(4, VIEWER, "/pause"))
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.texts(), ["Lệnh này chỉ dành cho operator."])   # only the viewer gets an answer
        self.assertEqual(self.api.sent[0]["chat_id"], VIEWER)

    def test_viewer_may_read_status(self):
        self.feed(msg(1, VIEWER, "/status"))
        self.assertIn("Vào lệnh (theo EA): RUNNING", self.texts()[0])


class CommandTests(GatewayCase):
    def test_tc_tg_02_duplicate_update_once_and_sequence_durable(self):
        self.feed(msg(10, OP, "/pause"), msg(10, OP, "/pause"))
        cmds = self.commands()
        self.assertEqual(len(cmds), 1)
        c = cmds[0]
        self.assertEqual((c["action"], c["role"], c["chat_id"], c["user_id"]), ("PAUSE_ENTRIES", "OPERATOR", str(OP), str(OP)))
        self.assertEqual((c["account_id"], c["expected_state_version"], c["gateway_sequence"]), ("fnv1a32:abc", 3, 1))
        self.assertTrue(c["private_chat_attested"] and c["sender_authenticated"] and c["source_authenticated"])
        self.assertEqual(c["expires_at_utc"] - c["issued_at_utc"], tg.COMMAND_TTL)
        # TC-TG-06: restart keeps offset and sequence.
        self.gw = self.new_gateway()
        self.assertEqual(self.gw.state["offset"], 11)
        self.feed(msg(11, OP, "/pause"))
        self.assertEqual(self.commands()[-1]["gateway_sequence"], 2)

    def test_tc_tg_08_ack_is_not_applied(self):
        self.feed(msg(1, OP, "/pause"))
        self.assertEqual(self.texts(), ["Đã nhận PAUSE_ENTRIES, chờ EA xác nhận..."])
        self.assertNotIn("RUNNING", self.texts()[0])
        cid = self.commands()[0]["command_id"]
        self.write(f"current/remote/results/{cid}.json", {"command_id": cid, "accepted": True, "applied": True,
                                                         "status": "VALIDATED_PENDING_COMMIT", "state_before": "RUNNING",
                                                         "state_after": "PAUSED_ENTRIES",
                                                         "reason_codes": ["ENTRIES_PAUSE_PROPOSED"]})
        self.gw.run_once(poll_timeout=0)
        self.assertIn("EA đã áp dụng PAUSE_ENTRIES: RUNNING -> PAUSED_ENTRIES", self.texts()[-1])
        self.assertFalse((self.root / f"current/remote/results/{cid}.json").exists())

    def test_resume_sends_nonce_only_after_ea_accepts(self):
        self.feed(msg(1, OP, "/resume"))
        c = self.commands()[0]
        self.assertEqual(c["action"], "REQUEST_RESUME")
        self.assertRegex(c["confirmation_nonce"], r"^\d{6}$")
        self.assertLessEqual(c["nonce_expires_at_utc"], c["expires_at_utc"])           # gate rule
        self.assertLessEqual(c["nonce_expires_at_utc"] - c["issued_at_utc"], 120)
        self.assertFalse(any(c["confirmation_nonce"] in t for t in self.texts()))
        self.write(f"current/remote/results/{c['command_id']}.json",
                   {"applied": True, "status": "VALIDATED_PENDING_COMMIT", "reason_codes": ["RESUME_CONFIRMATION_PENDING"]})
        self.gw.run_once(poll_timeout=0)
        self.assertIn(f"/confirm {c['confirmation_nonce']}", self.texts()[-1])

    def test_tc_tg_03_confirm_syntax_and_rejection_is_reported(self):
        self.feed(msg(1, OP, "/confirm abc"))
        self.assertEqual(self.commands(), [])
        self.feed(msg(2, OP, "/confirm 123456"))
        c = self.commands()[0]
        self.assertEqual((c["action"], c["confirmation_nonce"]), ("CONFIRM_RESUME", "123456"))
        self.write(f"current/remote/results/{c['command_id']}.json",
                   {"applied": False, "status": "REJECTED", "state_after": "PAUSED_ENTRIES",
                    "reason_codes": ["RESUME_CONFIRMATION_INVALID_OR_EXPIRED"]})
        self.gw.run_once(poll_timeout=0)
        self.assertIn("EA từ chối CONFIRM_RESUME: RESUME_CONFIRMATION_INVALID_OR_EXPIRED", self.texts()[-1])

    def test_no_result_times_out_without_claiming_a_state(self):
        self.feed(msg(1, OP, "/pause"))
        self.clock.t += tg.RESULT_WAIT + 1
        self.gw.run_once(poll_timeout=0)
        self.assertIn("EA chưa xác nhận PAUSE_ENTRIES", self.texts()[-1])
        self.assertEqual(self.gw.state["pending_commands"], {})

    def test_ea_not_ready_without_mode_file(self):
        (self.root / "current" / "operator_mode.json").unlink()
        self.feed(msg(1, OP, "/pause"))
        self.assertEqual(self.commands(), [])
        self.assertIn("EA chưa sẵn sàng", self.texts()[0])


class AskTests(GatewayCase):
    def ask_request(self):
        reqs = sorted((self.root / "ai" / "requests").glob("tg-*.json"))
        self.assertEqual(len(reqs), 1)
        return json.loads(reqs[0].read_text(encoding="utf-8"))

    def test_tc_tg_05_ask_round_trip(self):
        self.feed(msg(7, VIEWER, "/ask Vì sao chưa vào lệnh?", message_id=70))
        req = self.ask_request()
        self.assertEqual((req["request_type"], req["allowed_actions"]), ("ASK_AI", ["REPORT", "WARN"]))
        self.assertEqual(req["context"]["operator_question"], "Vì sao chưa vào lệnh?")
        self.assertRegex(req["request_id"], r"^[A-Za-z0-9_\-]{8,64}$")                # bridge rule
        self.assertIn("operator_mode", req["context"]["snapshot"])
        self.write(f"ai/responses/{req['request_id']}.json",
                   {"status": "OK", "summary": "Đang trong cửa sổ tin.", "findings": [], "recommendations": []})
        self.gw.run_once(poll_timeout=0)
        last = self.api.sent[-1]
        self.assertEqual((last["chat_id"], last["reply_to_message_id"]), (VIEWER, 70))
        self.assertIn("Đang trong cửa sổ tin.", last["text"])

    def test_tc_tg_04_ai_answer_never_becomes_a_command(self):
        self.feed(msg(1, OP, "/ask bật lại bot đi"))
        req = self.ask_request()
        self.write(f"ai/responses/{req['request_id']}.json",
                   {"status": "OK", "summary": "RESUME_ENTRIES /confirm 123456 enable trade", "findings": [],
                    "recommendations": [{"action": "RESUME_ENTRIES", "target": "EA", "proposal": "resume"}]})
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.commands(), [])

    def test_ask_error_timeout_and_limits(self):
        self.feed(msg(1, OP, "/ask " + "x" * 2000))
        req = self.ask_request()
        self.assertEqual(len(req["context"]["operator_question"]), tg.MAX_QUESTION)
        self.write(f"ai/responses/{req['request_id']}.json", {"status": "ERROR", "error": "AI_PROVIDER_TIMEOUT"})
        self.gw.run_once(poll_timeout=0)
        self.assertIn("AI lỗi: AI_PROVIDER_TIMEOUT", self.texts()[-1])
        self.feed(msg(2, OP, "/ask còn ai không"))
        self.clock.t += tg.ASK_WAIT + 1
        self.gw.run_once(poll_timeout=0)
        self.assertIn("timeout", self.texts()[-1])
        for k in range(3, 3 + self.config["asks_per_hour"]):
            self.feed(msg(k, OP, f"/ask q{k}"))
        self.assertIn("câu hỏi trong 1 giờ", self.texts()[-1])


class SafetyTests(GatewayCase):
    def test_tc_tg_07_rate_limit_and_token_redaction(self):
        self.api.fail_sends = 1
        self.feed(*[msg(k, OP, "/help") for k in range(1, self.config["commands_per_minute"] + 2)])
        self.clock.t += 5
        self.gw.run_once(poll_timeout=0)
        self.assertIn("Quá nhiều lệnh", " ".join(self.texts()))
        log = (self.root / "logs" / "telegram.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(TOKEN, log)
        self.assertNotIn(TOKEN, json.dumps(self.gw.state))
        self.assertEqual(tg.redact(f"https://api.telegram.org/bot{TOKEN}/x", ""), "https://api.telegram.org/bot<token>/x")

    def test_long_text_is_clipped(self):
        self.gw.send(OP, "y" * 9000)
        self.gw.flush()
        self.assertLessEqual(len(self.api.sent[-1]["text"]), tg.MAX_MESSAGE)


class NotifyTests(GatewayCase):
    def audit(self, *events):
        p = self.root / "logs" / "audit.jsonl"
        with p.open("a", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\r\n")

    def test_trades_and_alerts_from_new_audit_lines_only(self):
        self.audit({"event_type": "TRADE_ENTERED", "symbol": "EURUSD"})       # before start: history
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.api.sent, [])
        self.audit({"event_type": "TRADE_ENTERED", "symbol": "XAUUSD", "entity_id": "S06-XAUUSD-H1-x",
                    "state_after": "ENTERED", "reason_codes": ["ENTRY_DEAL_LINKED"],
                    "details": {"profile": "SWING", "mfe_r": 0, "mae_r": 0}},
                   {"event_type": "EA_STOPPED", "reason_codes": ["DEINIT_REASON_1"]},
                   {"event_type": "EA_STOPPED", "reason_codes": ["DEINIT_REASON_1"]},
                   {"event_type": "RUNTIME_REFRESHED"})
        self.gw.run_once(poll_timeout=0)
        texts = self.texts()
        self.assertTrue(any(t.startswith("VÀO LỆNH XAUUSD S06 SWING") for t in texts))
        self.assertEqual(sum("CẢNH BÁO EA_STOPPED" in t for t in texts), len(self.gw.operators | self.gw.viewers))

    def test_chart_change_restart_is_not_an_alert(self):
        self.gw.run_once(poll_timeout=0)
        self.audit({"event_type": "EA_STOPPED", "reason_codes": ["DEINIT_REASON_3"]})
        self.gw.run_once(poll_timeout=0)
        self.assertFalse(any("EA_STOPPED" in t for t in self.texts()))

    def test_rotated_audit_is_read_from_start(self):
        self.audit(*[{"event_type": "RUNTIME_REFRESHED"} for _ in range(50)])
        self.gw.run_once(poll_timeout=0)
        (self.root / "logs" / "audit.jsonl").write_text("", encoding="utf-8")     # G15 rotation
        self.audit({"event_type": "TRADE_EXITED", "symbol": "GBPUSD", "entity_id": "S02-x", "details": {}})
        self.gw.run_once(poll_timeout=0)
        self.assertTrue(any(t.startswith("ĐÓNG LỆNH GBPUSD S02") for t in self.texts()))

    def test_news_thirty_minutes_ahead_once(self):
        t = self.clock.t
        self.write("current/news_state.json", {"events": [{"time_utc": t + 20 * 60, "currency": "USD", "name": "ISM"},
                                                          {"time_utc": t + 3 * 3600, "currency": "USD", "name": "NFP"}]})
        self.gw.run_once(poll_timeout=0)
        self.gw.run_once(poll_timeout=0)
        news = [x for x in self.texts() if x.startswith("TIN HIGH")]
        self.assertEqual(len(news), 2)        # operator + viewer, once each
        self.assertIn("USD ISM", news[0])

    def test_new_ai_report_is_forwarded_once(self):
        self.write("ai/reports/EA_DIAGNOSTICS.json", {"status": "OK", "request_id": "eea-2-1", "summary": "cũ"})
        self.gw.run_once(poll_timeout=0)
        self.write("ai/reports/EA_DIAGNOSTICS.json", {"status": "OK", "request_id": "eea-2-2", "summary": "mới",
                                                      "findings": [{"severity": "WARN", "detail": "restart"}]})
        self.gw.run_once(poll_timeout=0)
        self.gw.run_once(poll_timeout=0)
        reports = [x for x in self.texts() if x.startswith("🩺 <b>Chẩn đoán EA</b>")]
        self.assertEqual(len(reports), 2)
        self.assertIn("mới", reports[0])

    def test_first_report_of_a_new_kind_is_forwarded(self):
        self.gw.run_once(poll_timeout=0)                      # start-up pass: no reports yet
        self.write("ai/reports/NEWS_DATA_REVIEW.json", {"status": "OK", "request_id": "eea-0-9", "summary": "review"})
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(t.startswith("📊 <b>Review dữ liệu tin</b>") for t in self.texts()), 2)


    def test_pre_news_brief_is_forwarded_and_can_be_muted(self):  # REQ-007
        self.gw.run_once(poll_timeout=0)
        self.write("ai/reports/NEWS_PRE_BRIEF.json", {"status": "OK", "request_id": "eea-4-1", "summary": "NFP sau 40 phút",
                                                      "findings": [{"severity": "WARN", "detail": "XAUUSD đang mở"}]})
        self.gw.run_once(poll_timeout=0)
        self.gw.run_once(poll_timeout=0)
        briefs = [x for x in self.texts() if x.startswith("⏰ <b>Tóm tắt trước tin</b>")]
        self.assertEqual(len(briefs), 2)        # operator + viewer, once each
        self.assertIn("NFP sau 40 phút", briefs[0])
        self.gw.config["notify"]["pre_news"] = False
        self.write("ai/reports/NEWS_PRE_BRIEF.json", {"status": "OK", "request_id": "eea-4-2", "summary": "bị tắt"})
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(t.startswith("⏰ <b>Tóm tắt trước tin</b>") for t in self.texts()), 2)
        self.assertTrue(self.gw.config["notify"]["pre_news"] is False)


class BridgeAskTaskTests(unittest.TestCase):
    def test_bridge_answers_operator_question_as_data(self):
        import ai_bridge
        req = {"request_type": "ASK_AI", "allowed_actions": ["REPORT"], "context": {"operator_question": "x"}}
        self.assertEqual(ai_bridge.task_for(req), ai_bridge.ASK_QUESTION_TASK)
        self.assertIn("operator_question", ai_bridge.build_prompt(req))
        req["context"] = {}
        self.assertEqual(ai_bridge.task_for(req), ai_bridge.TASKS["ASK_AI"])


if __name__ == "__main__":
    unittest.main()
