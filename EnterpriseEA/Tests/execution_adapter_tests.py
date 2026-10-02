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

    def test_missing_execution_identifiers_fail_closed(self):
        for field, reason in (
            ("intent_id", "INTENT_ID_MISSING"),
            ("correlation_id", "CORRELATION_ID_MISSING"),
            ("idempotency_key", "IDEMPOTENCY_KEY_MISSING"),
        ):
            with self.subTest(field=field):
                i = intent()
                i[field] = ""
                res = preflight(i, context(execution_enabled=True))
                self.assertEqual(res["confirmation_state"], "NOT_SENT")
                self.assertEqual(res["reason_code"], reason)
                self.assertFalse(res["request_sent"])

    def test_config_and_runtime_identity_must_match(self):
        for field, reason in (
            ("config_version", "CONFIG_VERSION_MISSING"),
            ("account_snapshot_id", "ACCOUNT_SNAPSHOT_INVALID"),
            ("reconciliation_snapshot_id", "RECONCILIATION_STALE"),
            ("symbol_fingerprint", "SYMBOL_FINGERPRINT_MISSING"),
        ):
            with self.subTest(field=field):
                i = intent()
                ctx = context(execution_enabled=True)
                if field in i:
                    i[field] = ""
                else:
                    ctx[field] = ""
                res = preflight(i, ctx)
                self.assertEqual(res["confirmation_state"], "NOT_SENT")
                self.assertEqual(res["reason_code"], reason)

        ctx = context(execution_enabled=True)
        ctx["config_version"] = "old-config"
        res = preflight(intent(), ctx)
        self.assertEqual(res["reason_code"], "CONFIG_VERSION_MISMATCH")

    def test_symbol_binding_and_fingerprint_must_match(self):
        for field, reason in (
            ("canonical_symbol", "CANONICAL_SYMBOL_MISMATCH"),
            ("broker_symbol", "BROKER_SYMBOL_MISMATCH"),
            ("symbol_fingerprint", "SYMBOL_FINGERPRINT_MISMATCH"),
        ):
            with self.subTest(field=field):
                ctx = context(execution_enabled=True)
                ctx[field] = "other"
                res = preflight(intent(), ctx)
                self.assertEqual(res["reason_code"], reason)

    def test_freshness_state_and_symbol_geometry_fail_closed(self):
        cases = (
            ({"runtime_state": "DEGRADED"}, "EXECUTION_STATE_INVALID"),
            ({"reconciliation_valid_until_utc": 99, "now_utc": 100}, "RECONCILIATION_STALE"),
            ({"volume": 0.105}, "VOLUME_STEP_INVALID"),
            ({"price": 1.100034}, "PRICE_GEOMETRY_INVALID"),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                i = intent()
                ctx = context(execution_enabled=True)
                for key, value in overrides.items():
                    if key in i:
                        i[key] = value
                    else:
                        ctx[key] = value
                res = preflight(i, ctx)
                self.assertEqual(res["reason_code"], reason)

    def test_duplicate_idempotency_key_never_sends_second_request(self):
        state = {"accepted_keys": ["idem-001"]}
        res = idempotency_decision(state, "idem-001")
        self.assertEqual(res, {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"})

    def test_empty_idempotency_key_is_rejected(self):
        res = idempotency_decision({"accepted_keys": []}, "")
        self.assertEqual(res, {"accepted": False, "reason_code": "IDEMPOTENCY_KEY_MISSING"})

    def test_acknowledgement_requires_reconciliation_confirmation(self):
        res = apply_result({}, {"request_sent": True, "request_retcode": "DONE", "broker_confirmed": False})
        self.assertEqual(res["confirmation_state"], "EXECUTION_UNKNOWN")

    def test_failed_retcode_is_rejected_without_confirmation(self):
        res = apply_result({}, {"request_sent": True, "request_retcode": "10004"})
        self.assertEqual(res["confirmation_state"], "REJECTED")
        self.assertEqual(res["reason_code"], "ORDER_SEND_FAILED_10004")

    def test_missing_retcode_fails_closed(self):
        res = apply_result({}, {"request_sent": True})
        self.assertEqual(res["confirmation_state"], "REJECTED")
        self.assertEqual(res["reason_code"], "REQUEST_RETCODE_MISSING")

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
