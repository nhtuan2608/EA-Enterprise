import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExecutionIntentBuilderTests(unittest.TestCase):
    def test_builder_binds_released_decision_and_rejects_pending(self):
        source = (ROOT / "Runtime/ExecutionIntentBuilder.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for token in (
            "EEA_BuildMarketExecutionIntent",
            "EEA_RiskDecisionValidForRelease",
            "EEA_RiskDecisionBindsExecutionIntent",
            "EEA_EXEC_ACTION_SUBMIT_MARKET",
            "EXECUTION_INTENT_BUILDER_PENDING_UNSUPPORTED",
            "idempotency_key",
            "risk_budget",
            "projected_loss",
            "quote_snapshot_id",
        ):
            self.assertIn(token, source)
        self.assertIn('ExecutionIntentBuilder.mqh', shell)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("FileOpen", source)


if __name__ == "__main__":
    unittest.main()
