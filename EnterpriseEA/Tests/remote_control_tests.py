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
