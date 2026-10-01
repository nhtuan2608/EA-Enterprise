"""Paperless controlled-live release gate tests."""
import unittest
from pathlib import Path

from live_authorization_oracle import evaluate_live_authorization, context


ROOT = Path(__file__).resolve().parents[1]


class LiveAuthorizationTests(unittest.TestCase):
    def test_default_context_is_not_authorized(self):
        result = evaluate_live_authorization(context())
        self.assertFalse(result["authorized"])
        self.assertEqual(result["status"], "NOT_AUTHORIZED")

    def test_all_paperless_live_gates_are_required(self):
        ready = context(
            explicit_human_approval=True,
            account_identity_confirmed=True,
            risk_policy_confirmed=True,
            broker_specs_confirmed=True,
            retained_runtime_evidence=True,
            execution_path_compiled=True,
            demo_execution_evidence=True,
            restart_reconciliation_evidence=True,
            emergency_stop_tested=True,
            rollback_tested=True,
            ai_policy_confirmed=True,
            news_policy_confirmed=True,
            limits_locked=True,
            config_backup_ready=True,
            monitoring_ready=True,
            no_unknown_state=True,
            no_open_blockers=True,
            live_account_intended=True,
            authorization_id="release-001",
            build_hash="sha256:abc",
            config_version="live-v1.0.0",
            broker_server="VTMarkets-Live",
            account_mode="HEDGING",
            broker_symbol="EURUSD-VIP",
        )
        result = evaluate_live_authorization(ready)
        self.assertTrue(result["authorized"])
        self.assertEqual(result["status"], "AUTHORIZED_CONTROLLED_LIVE")

    def test_missing_any_gate_fails_closed(self):
        ready = context(
            explicit_human_approval=True,
            account_identity_confirmed=True,
            risk_policy_confirmed=True,
            broker_specs_confirmed=True,
            retained_runtime_evidence=True,
            execution_path_compiled=True,
            demo_execution_evidence=True,
            restart_reconciliation_evidence=True,
            emergency_stop_tested=True,
            rollback_tested=True,
            ai_policy_confirmed=True,
            news_policy_confirmed=True,
            limits_locked=True,
            config_backup_ready=True,
            monitoring_ready=True,
            no_unknown_state=True,
            no_open_blockers=True,
            live_account_intended=True,
            authorization_id="release-001",
            build_hash="sha256:abc",
        )
        ready["rollback_tested"] = False
        result = evaluate_live_authorization(ready)
        self.assertFalse(result["authorized"])
        self.assertEqual(result["reason_code"], "LIVE_GATE_ROLLBACK_NOT_PROVEN")

    def test_gate_has_no_paper_ledger_reference(self):
        source = (ROOT / "Runtime/LiveAuthorizationGate.mqh").read_text(encoding="utf-8")
        self.assertNotIn("PaperLedger", source)
        self.assertNotIn("paper_ledger", source.lower())


if __name__ == "__main__":
    unittest.main()
