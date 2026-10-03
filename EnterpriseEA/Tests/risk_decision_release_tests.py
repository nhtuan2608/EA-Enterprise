import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RiskDecisionReleaseTests(unittest.TestCase):
    def test_release_builder_is_strict_second_pass_and_fail_closed(self):
        source = (ROOT / "Integration/RiskDecisionRelease.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for token in (
            "EEA_RiskDecisionReleaseFromReview",
            "EEA_EvaluateDryRunCandidate",
            "RISK_APPROVED",
            "RELEASED",
            "RISK_RELEASE_RECHECK_REQUIRED",
            "quote_repriced",
            "portfolio_reconciled",
            "symbol_spec_unchanged",
            "account_snapshot_id",
            "reconciliation_fingerprint",
        ):
            self.assertIn(token, source)
        self.assertIn('RiskDecisionRelease.mqh', shell)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("FileOpen", source)

    def test_release_builder_does_not_promote_review_string_without_second_pass(self):
        source = (ROOT / "Integration/RiskDecisionRelease.mqh").read_text(encoding="utf-8")
        self.assertIn("!recheck.quote_repriced", source)
        self.assertIn("!recheck.policy_rechecked", source)
        self.assertIn("!recheck.runtime_current", source)
        self.assertIn('decision.decision_status="RISK_APPROVED"', source)


if __name__ == "__main__":
    unittest.main()
