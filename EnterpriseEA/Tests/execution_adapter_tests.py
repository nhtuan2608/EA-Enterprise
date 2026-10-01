"""Tests for execution contracts, preflight oracle, idempotency and result reconciliation."""
import json
import unittest
from pathlib import Path

from execution_adapter_oracle import preflight, idempotency_decision, apply_result, reconcile_result, intent, context, mutate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "Tests/Fixtures/execution-adapter-v0.1.0.json"


class ExecutionAdapterOracleTests(unittest.TestCase):
    def test_disabled_default_rejects_without_request(self):
        res = preflight(intent(), context(execution_enabled=False))
        self.assertEqual(res["confirmation_state"], "NOT_SENT")
        self.assertEqual(res["reason_code"], "EXECUTION_DISABLED")
        self.assertFalse(res["request_sent"])

    def test_stale_reconciliation_blocks_preflight(self):
        res = preflight(intent(), context(execution_enabled=True, reconciliation_fresh=False))
        self.assertEqual(res["confirmation_state"], "NOT_SENT")
        self.assertEqual(res["reason_code"], "RECONCILIATION_STALE")

    def test_duplicate_idempotency_key_never_sends_second_request(self):
        state = {"accepted_keys": ["idem-001"]}
        res = idempotency_decision(state, "idem-001")
        self.assertEqual(res, {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"})

    def test_acknowledgement_requires_reconciliation_confirmation(self):
        res = apply_result({}, {"request_sent": True, "request_retcode": "DONE", "broker_confirmed": False})
        self.assertEqual(res["confirmation_state"], "EXECUTION_UNKNOWN")

    def test_redaction_no_raw_login_or_credentials_in_intent(self):
        i = intent()
        for forbidden in ["login", "account_name", "password", "secret", "token"]:
            self.assertNotIn(forbidden, i)

    def test_no_paper_ledger_exists(self):
        paper_files = list(ROOT.glob("*paper*.mqh")) + list(ROOT.glob("*Paper*.mqh")) + list(ROOT.glob("*paper*.py"))
        self.assertEqual(len(paper_files), 0, "No paper ledger files or modules are permitted.")

    def test_market_fill_in_history_confirms(self):
        snapshot = {"deals": [{"order_ticket": 12345}], "orders": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_MARKET", {})
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        self.assertEqual(res["reason_code"], "OK")

    def test_pending_order_remaining_active_confirms(self):
        snapshot = {"orders": [{"ticket": 12345}], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_PENDING", {})
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        self.assertEqual(res["reason_code"], "OK")

    def test_confirmed_cancel_after_active_order_disappears(self):
        snapshot = {"orders": [], "deals": [{"order_ticket": 12345}], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "CANCEL_PENDING", {})
        self.assertEqual(res["confirmation_state"], "CONFIRMED")

    def test_modify_confirmation_from_active_protective_fields(self):
        snapshot = {"orders": [{"ticket": 12345, "sl": 1.08, "tp": 1.10}], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED", "intent": {"sl": 1.08, "tp": 1.10}}, snapshot, 12345, "MODIFY_PROTECTIVE", {"sl": 1.08, "tp": 1.10})
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        
        snapshot2 = {"orders": [], "positions": [{"ticket": 12345, "sl": 1.08, "tp": 1.10}], "deals": []}
        res2 = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED", "intent": {"sl": 1.08, "tp": 1.10}}, snapshot2, 12345, "MODIFY_PROTECTIVE", {"sl": 1.08, "tp": 1.10})
        self.assertEqual(res2["confirmation_state"], "CONFIRMED")

    def test_timeout_missing_evidence_race_unknown(self):
        snapshot = {"orders": [], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_PENDING", {})
        self.assertEqual(res["confirmation_state"], "EXECUTION_UNKNOWN")

    def test_fixture_cases(self):
        if not FIXTURE_PATH.exists():
            self.skipTest("Fixture not found yet")
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for row in fixture["cases"]:
            with self.subTest(name=row["name"]):
                c = fixture["base"]
                for path, value in row["mutations"]:
                    c = mutate(c, path, value)
                actual = preflight(c["intent"], c["context"])
                self.assertEqual(actual["confirmation_state"], row["expected"]["confirmation_state"])
                self.assertEqual(actual["reason_code"], row["expected"]["reason_code"])
                self.assertEqual(actual["request_sent"], row["expected"]["request_sent"])


if __name__ == "__main__":
    unittest.main()
