"""Tests for execution contracts, preflight oracle, idempotency and result reconciliation."""
import json
import unittest
from pathlib import Path

from execution_adapter_oracle import preflight, idempotency_decision, idempotency_decision_scan, apply_result, reconcile_result, intent, context, mutate

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
        snapshot = {"deals": [{"deal_ticket": 12345}], "orders": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_MARKET", {}, request_ticket_kind="DEAL")
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        self.assertEqual(res["reason_code"], "OK")

    def test_pending_order_remaining_active_confirms(self):
        snapshot = {"orders": [{"ticket": 12345}], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_PENDING", {}, request_ticket_kind="ORDER")
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        self.assertEqual(res["reason_code"], "OK")

    def test_confirmed_cancel_after_active_order_disappears(self):
        snapshot = {"orders": [], "deals": [{"order_ticket": 12345}], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "CANCEL_PENDING", {}, request_ticket_kind="ORDER")
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        
        snapshot_hist = {"orders": [], "history_orders": [{"ticket": 12345}], "deals": [], "positions": []}
        res_hist = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot_hist, 12345, "CANCEL_PENDING", {}, request_ticket_kind="ORDER")
        self.assertEqual(res_hist["confirmation_state"], "CONFIRMED")

    def test_modify_confirmation_from_active_protective_fields(self):
        snapshot = {"orders": [{"ticket": 12345, "sl": 1.08, "tp": 1.10}], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED", "intent": {"sl": 1.08, "tp": 1.10}}, snapshot, 12345, "MODIFY_PROTECTIVE", {"sl": 1.08, "tp": 1.10}, request_ticket_kind="ORDER")
        self.assertEqual(res["confirmation_state"], "CONFIRMED")
        
        snapshot2 = {"orders": [], "positions": [{"ticket": 12345, "sl": 1.08, "tp": 1.10}], "deals": []}
        res2 = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED", "intent": {"sl": 1.08, "tp": 1.10}}, snapshot2, 12345, "MODIFY_PROTECTIVE", {"sl": 1.08, "tp": 1.10}, request_ticket_kind="POSITION")
        self.assertEqual(res2["confirmation_state"], "CONFIRMED")

    def test_timeout_missing_evidence_race_unknown(self):
        snapshot = {"orders": [], "deals": [], "positions": []}
        res = reconcile_result({"confirmation_state": "REQUEST_ACCEPTED"}, snapshot, 12345, "SUBMIT_PENDING", {}, request_ticket_kind="ORDER")
        self.assertEqual(res["confirmation_state"], "EXECUTION_UNKNOWN")

    def test_hardening_magic_deviation_filling_defaults(self):
        i = intent()
        self.assertEqual(i["magic"], 888888)
        self.assertEqual(i["deviation"], 20)
        self.assertEqual(i["filling_mode"], 0)

    def test_unsupported_filling_mode_fails_closed(self):
        i = intent()
        i["filling_mode"] = 2 # e.g. RETURN
        ctx = context(execution_enabled=True, supported_filling_modes=[0, 1]) # Only FOK and IOC supported
        res = preflight(i, ctx)
        self.assertEqual(res["confirmation_state"], "NOT_SENT")
        self.assertEqual(res["reason_code"], "SYMBOL_FILLING_UNSUPPORTED")

    def test_idempotency_audit_scan_exact_bounded_and_fail_closed(self):
        log_text = '{"intent_id":"1","idempotency_key":"idem-001"}\n'
        res_dup = idempotency_decision_scan(log_text, "idem-001")
        self.assertFalse(res_dup["accepted"])
        self.assertEqual(res_dup["reason_code"], "DUPLICATE_IDEMPOTENCY_KEY")

        res_ok = idempotency_decision_scan(log_text, "idem-999")
        self.assertTrue(res_ok["accepted"])

        # Unreadable (None) or oversized log (>1MB) fails closed
        res_unreadable = idempotency_decision_scan(None, "idem-001")
        self.assertFalse(res_unreadable["accepted"])

        oversized = "A" * 2000000
        res_oversized = idempotency_decision_scan(oversized, "idem-001")
        self.assertFalse(res_oversized["accepted"])

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

    def test_mql_adapter_and_input_default_disabled(self):
        adapter_path = ROOT / "Runtime/ExecutionAdapter.mqh"
        self.assertTrue(adapter_path.exists(), "ExecutionAdapter.mqh must exist")
        
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("InpExecutionEnabled", shell)
        self.assertIn("InpObserverOnly", shell)

    def test_no_automatic_execution_call_sites(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertNotIn("EEA_ExecutionSubmit", shell)
        self.assertNotIn("EEA_ExecutionModifyProtective", shell)
        self.assertNotIn("EEA_ExecutionCancelPending", shell)
        self.assertNotIn("EEA_ExecutionPreflight", shell)

    def test_execution_apis_confined_to_adapter(self):
        adapter_text = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("OrderSend", adapter_text)
        for mqh in ROOT.glob("Runtime/**/*.mqh"):
            if mqh.name == "ExecutionAdapter.mqh":
                continue
            content = mqh.read_text(encoding="utf-8")
            self.assertNotIn("OrderSend", content)

    def test_execution_adapter_features(self):
        adapter_text = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("data_root", adapter_text)
        self.assertIn("position_ticket", adapter_text)
        self.assertIn("ticket", adapter_text)
        self.assertIn("magic", adapter_text)
        self.assertIn("deviation", adapter_text)
        self.assertIn("filling_mode", adapter_text)
        self.assertIn("request_ticket_kind", adapter_text)
        self.assertIn("EEA_ExecutionIsDuplicateIdempotency", adapter_text)


if __name__ == "__main__":
    unittest.main()
