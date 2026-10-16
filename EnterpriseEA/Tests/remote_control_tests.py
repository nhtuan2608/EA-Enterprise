"""Synthetic Telegram-control contract tests; no MT5 or Telegram calls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from contract_tests import schema_errors
from remote_control_oracle import ai_reply_acceptable, evaluate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/remote-control-v1.0.0.json").read_text(encoding="utf-8"))


class RemoteModeContractTests(unittest.TestCase):
    def setUp(self):
        self.state = deepcopy(FIXTURE["state"])
        self.pause = deepcopy(FIXTURE["pause_command"])
        self.evidence = deepcopy(FIXTURE["resume_evidence"])

    def test_wire_contracts_accept_synthetic_examples(self):
        for schema_name, value in (("remote-command.schema.json", self.pause),
                                   ("remote-command.schema.json", FIXTURE["resume_request"]),
                                   ("remote-command.schema.json", FIXTURE["resume_confirm"]),
                                   ("telegram-ai-request.schema.json", FIXTURE["ai_request"]),
                                   ("telegram-ai-reply.schema.json", FIXTURE["ai_reply"])):
            with self.subTest(schema=schema_name):
                schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
                self.assertEqual(schema_errors(schema, value), [])

    def test_pause_is_proposal_and_duplicate_has_no_second_effect(self):
        proposed, status, reason = evaluate(self.state, self.pause, self.evidence, 1001)
        self.assertEqual(status, "VALIDATED_PENDING_COMMIT")
        self.assertEqual(reason, "ENTRIES_PAUSE_PROPOSED")
        self.assertTrue(proposed["operator_paused"])
        self.assertFalse(self.state["operator_paused"])
        self.assertEqual(proposed["state_version"], 5)
        again, status, _ = evaluate(proposed, self.pause, self.evidence, 1002)
        self.assertEqual(status, "DUPLICATE_IGNORED")
        self.assertEqual(again, proposed)

    def test_untrusted_sender_group_and_wrong_account_rejected(self):
        for key, value in (("sender_authenticated", False), ("source_authenticated", False),
                           ("private_chat_attested", False), ("role", "VIEWER"),
                           ("account_id", "other-account"), ("config_version", "other-config")):
            with self.subTest(key=key):
                command = deepcopy(self.pause)
                command[key] = value
                next_state, status, _ = evaluate(self.state, command, self.evidence, 1001)
                self.assertEqual(status, "REJECTED")
                self.assertEqual(next_state, self.state)

    def test_stale_state_and_expired_command_rejected(self):
        for key, value, now in (("expected_state_version", 3, 1001),
                                ("expires_at_utc", 1002, 1003),
                                ("gateway_sequence", 9, 1001)):
            with self.subTest(key=key):
                command = deepcopy(self.pause)
                command[key] = value
                self.assertEqual(evaluate(self.state, command, self.evidence, now)[1], "REJECTED")

    def test_missing_durable_state_stays_paused(self):
        unavailable = deepcopy(self.state)
        unavailable["initialized"] = False
        unavailable["operator_paused"] = True
        next_state, status, reason = evaluate(unavailable, self.pause, self.evidence, 1001)
        self.assertEqual((status, reason), ("REJECTED", "DURABLE_REMOTE_STATE_REQUIRED"))
        self.assertEqual(next_state, unavailable)
        self.assertTrue(next_state["operator_paused"])

    def test_resume_requires_same_user_nonce_and_fresh_safety(self):
        paused = evaluate(self.state, self.pause, self.evidence, 1001)[0]
        requested, status, _ = evaluate(paused, FIXTURE["resume_request"], self.evidence, 1006)
        self.assertEqual(status, "VALIDATED_PENDING_COMMIT")
        self.assertTrue(requested["operator_paused"])
        self.assertEqual(requested["pending_chat_id"], "private-chat-1")
        confirm = deepcopy(FIXTURE["resume_confirm"])
        for key, value, now in (("confirmation_nonce", "wrong", 1011),
                                ("user_id", "other-user", 1011),
                                ("chat_id", "other-chat", 1011),
                                ("confirmation_nonce", confirm["confirmation_nonce"], 1026)):
            with self.subTest(key=key, now=now):
                bad = deepcopy(confirm)
                bad[key] = value
                self.assertEqual(evaluate(requested, bad, self.evidence, now)[1], "REJECTED")
        missing = deepcopy(self.evidence)
        missing["account_wide_reconciled"] = False
        self.assertEqual(evaluate(requested, confirm, missing, 1011)[2], "RESUME_SAFETY_EVIDENCE_NOT_READY")
        resumed, status, _ = evaluate(requested, confirm, self.evidence, 1011)
        self.assertEqual(status, "VALIDATED_PENDING_COMMIT")
        self.assertFalse(resumed["operator_paused"])
        self.assertEqual(resumed["pending_nonce"], "")
        self.assertTrue(requested["operator_paused"])

    # Telegram /session (17/10/2026): sign needs the input, a 24h/7d duration and a 6-digit code.
    def session_command(self, action, sequence, update_id, now, nonce="", seconds=0):
        command = deepcopy(FIXTURE["resume_request"])
        command.update(command_id=f"cmd-session-{sequence}", action=action, gateway_sequence=sequence,
                       telegram_update_id=update_id, issued_at_utc=now, expires_at_utc=now + 120,
                       confirmation_nonce=nonce, nonce_expires_at_utc=now + 115 if action == "REQUEST_SESSION_SIGN" else 0,
                       session_seconds=seconds, expected_state_version=self.state["state_version"])
        return command

    def allowed(self):
        evidence = deepcopy(self.evidence)
        evidence["session_remote_sign_allowed"] = True
        return evidence

    def test_session_sign_needs_input_duration_and_matching_code(self):
        request = self.session_command("REQUEST_SESSION_SIGN", 11, 101, 1000, "482913", 7 * 86400)
        schema = json.loads((ROOT / "schemas" / "remote-command.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema_errors(schema, request), [])
        self.assertEqual(evaluate(self.state, request, self.evidence, 1001)[2], "SESSION_REMOTE_SIGN_DISABLED")
        bad = deepcopy(request)
        bad["session_seconds"] = 3600
        self.assertEqual(evaluate(self.state, bad, self.allowed(), 1001)[2], "SESSION_DURATION_INVALID")
        pending, status, reason = evaluate(self.state, request, self.allowed(), 1001)
        self.assertEqual((status, reason), ("VALIDATED_PENDING_COMMIT", "SESSION_SIGN_CONFIRMATION_PENDING"))
        self.assertEqual((pending["pending_action"], pending["pending_session_seconds"]), ("SESSION_SIGN", 7 * 86400))
        self.assertFalse(pending["operator_paused"])            # a session request never pauses or resumes
        self.state = pending
        confirm = self.session_command("CONFIRM_SESSION_SIGN", 12, 102, 1010, "482913")
        for key, value, now in (("confirmation_nonce", "000000", 1011), ("user_id", "other-user", 1011),
                                ("chat_id", "other-chat", 1011), ("confirmation_nonce", "482913", 1116)):
            with self.subTest(key=key, now=now):
                wrong = deepcopy(confirm)
                wrong[key] = value
                self.assertEqual(evaluate(pending, wrong, self.allowed(), now)[2], "SESSION_CONFIRMATION_INVALID_OR_EXPIRED")
        self.assertEqual(evaluate(pending, confirm, self.evidence, 1011)[2], "SESSION_REMOTE_SIGN_DISABLED")
        signed, status, reason, effect = evaluate(pending, confirm, self.allowed(), 1011, with_effect=True)
        self.assertEqual((status, reason), ("VALIDATED_PENDING_COMMIT", "SESSION_SIGN_PROPOSED"))
        self.assertEqual(effect, {"session_sign_seconds": 7 * 86400, "session_revoke": False})
        self.assertEqual((signed["pending_nonce"], signed["pending_action"]), ("", ""))

    def test_session_code_cannot_resume_and_resume_code_cannot_sign(self):
        paused = evaluate(self.state, self.pause, self.evidence, 1001)[0]
        self.state = paused
        request = self.session_command("REQUEST_SESSION_SIGN", 12, 102, 1005, "482913", 86400)
        pending = evaluate(paused, request, self.allowed(), 1006)[0]
        self.state = pending
        resume = self.session_command("CONFIRM_RESUME", 13, 103, 1010, "482913")
        self.assertEqual(evaluate(pending, resume, self.allowed(), 1011)[2], "RESUME_CONFIRMATION_INVALID_OR_EXPIRED")
        requested = evaluate(paused, FIXTURE["resume_request"], self.evidence, 1006)[0]
        self.state = requested
        sign = self.session_command("CONFIRM_SESSION_SIGN", 13, 103, 1010, FIXTURE["resume_confirm"]["confirmation_nonce"])
        self.assertEqual(evaluate(requested, sign, self.allowed(), 1011)[2], "SESSION_CONFIRMATION_INVALID_OR_EXPIRED")

    def test_old_state_without_pending_action_still_resumes(self):
        paused = evaluate(self.state, self.pause, self.evidence, 1001)[0]
        requested = evaluate(paused, FIXTURE["resume_request"], self.evidence, 1006)[0]
        del requested["pending_action"], requested["pending_session_seconds"]
        self.assertEqual(evaluate(requested, FIXTURE["resume_confirm"], self.evidence, 1011)[1], "VALIDATED_PENDING_COMMIT")

    def test_revoke_needs_no_code_and_no_input(self):
        revoke = self.session_command("REVOKE_SESSION", 11, 101, 1000)
        _, status, reason, effect = evaluate(self.state, revoke, self.evidence, 1001, with_effect=True)
        self.assertEqual((status, reason), ("VALIDATED_PENDING_COMMIT", "SESSION_REVOKE_PROPOSED"))
        self.assertEqual(effect, {"session_sign_seconds": 0, "session_revoke": True})

    def test_ea_runs_session_effects_only_after_commit(self):
        gate = (ROOT / "Integration/RemoteModeGate.mqh").read_text(encoding="utf-8")
        runtime = (ROOT / "Integration/RemoteModeRuntime.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for code in ("SESSION_REMOTE_SIGN_DISABLED", "SESSION_DURATION_INVALID", "SESSION_CHALLENGE_INVALID",
                     "SESSION_CONFIRMATION_INVALID_OR_EXPIRED", "SESSION_SIGN_PROPOSED", "SESSION_REVOKE_PROPOSED"):
            self.assertIn(f'"{code}"', gate)
        self.assertIn("if(applied && (d.session_sign_seconds>0 || d.session_revoke))", runtime)
        self.assertIn("input bool   InpSessionRemoteSignAllowed = false;", shell)
        self.assertIn("e.session_remote_sign_allowed=InpSessionRemoteSignAllowed;", shell)
        self.assertIn("EEA_LiveSessionSign(seconds,reason) : EEA_LiveSessionRevoke(reason)", shell)

    def test_ai_reply_stays_read_only_and_bound_to_request(self):
        request, reply = deepcopy(FIXTURE["ai_request"]), deepcopy(FIXTURE["ai_reply"])
        self.assertTrue(ai_reply_acceptable(request, reply, 1103))
        for key, value in (("chat_id", "another-chat"), ("request_id", "other-request"),
                           ("evidence_refs", ["unknown-snapshot"]), ("valid_until_utc", 1101)):
            with self.subTest(key=key):
                invalid = deepcopy(reply)
                invalid[key] = value
                self.assertFalse(ai_reply_acceptable(request, invalid, 1103))
        reply["answer"] = "Please resume and place an order."
        self.assertTrue(ai_reply_acceptable(request, reply, 1103))
        self.assertEqual(self.state, FIXTURE["state"])

    def test_module_has_no_transport_order_or_shell_integration(self):
        source = (ROOT / "Integration/RemoteModeGate.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("VALIDATED_PENDING_COMMIT", source)
        for forbidden in ("OrderSend", "WebRequest", "FileOpen", "CTrade", "ShellExecute"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("RemoteModeGate.mqh", shell)


if __name__ == "__main__":
    unittest.main()
