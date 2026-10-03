"""Static boundary checks for the paperless controlled-live orchestration."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ControlledLiveRuntimeTests(unittest.TestCase):
    def test_live_authorization_store_is_identity_bound_and_fail_closed(self):
        store = (ROOT / "Storage/LiveAuthorizationStore.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_LiveAuthorizationStoreLoad",
            "explicit_human_approval",
            "restart_reconciliation_evidence",
            "emergency_stop_tested",
            "rollback_tested",
            "authorization_valid_until_utc",
            "candidate_id",
            "account_fingerprint",
            "broker_server",
            "broker_symbol",
            "EEA_EvaluateLiveAuthorization",
        ):
            self.assertIn(token, store)
        decision_store = (ROOT / "Storage/RiskDecisionStore.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_RiskDecisionStoreWrite", decision_store)
        self.assertIn("risk_decision.json", decision_store)
        recovery_store = (ROOT / "Storage/ExecutionRecoveryStore.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_ExecutionRecoveryLoad", recovery_store)
        self.assertIn("EXECUTION_UNKNOWN", recovery_store)

    def test_shell_routes_live_work_through_controlled_runtime(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        runtime = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn('#include "Integration/ControlledLiveRuntime.mqh"', shell)
        self.assertIn("InpLiveTradeArmed", shell)
        self.assertIn("EEA_ControlledLiveOnTimer", shell)
        self.assertIn("EEA_ExecutionSubmit", runtime)
        self.assertIn("EEA_ExecutionReconcileResult", runtime)
        self.assertIn("EEA_RiskDecisionReleaseFromReview", runtime)
        self.assertIn("EEA_BuildMarketExecutionIntent", runtime)
        self.assertIn("EEA_RuntimeStatus execution_status=observer.status", runtime)
        self.assertIn("execution_status.new_entries_blocked=false", runtime)
        self.assertIn("EEA_RiskDecisionStoreWrite", runtime)
        self.assertIn("EEA_ControlledLiveReconcileRecovery", runtime)
        self.assertIn("recovery_blocked", runtime)

    def test_live_defaults_remain_disabled_and_no_paper_path_exists(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("input bool   InpObserverOnly           = true;", shell)
        self.assertIn("input bool   InpExecutionEnabled       = false;", shell)
        self.assertIn("input bool   InpLiveTradeArmed         = false;", shell)
        self.assertNotIn("Paper ledger", shell)


if __name__ == "__main__":
    unittest.main()
