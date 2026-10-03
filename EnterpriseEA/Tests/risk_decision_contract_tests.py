"""Static contract checks for the pure risk-release decision boundary."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "Risk" / "RiskDecision.mqh"


class RiskDecisionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONTRACT.read_text(encoding="utf-8") if CONTRACT.exists() else ""

    def _section(self, signature, next_signature=None):
        self.assertIn(signature, self.source)
        start = self.source.index(signature)
        if next_signature is None:
            return self.source[start:]
        self.assertIn(next_signature, self.source[start:])
        end = self.source.index(next_signature, start)
        return self.source[start:end]

    def test_contract_declares_release_decision_and_provenance(self):
        self.assertTrue(CONTRACT.exists())
        for declaration in (
            "struct EEA_RiskDecision",
            "string decision_status",
            "string release_status",
            "string decision_id",
            "string candidate_id",
            "string setup_id",
            "string policy_id",
            "string account_id",
            "string reconciliation_id",
            "string symbol",
            "string quote_id",
            "string portfolio_snapshot_id",
            "double final_volume",
            "int direction",
            "double entry_reference",
            "double stop_loss",
            "double take_profit",
            "double projected_loss",
            "double available_headroom",
            "datetime decided_at_utc",
            "datetime expires_at_utc",
            "string reason_code",
            "string secondary_reason_code",
        ):
            self.assertIn(declaration, self.source)

    def test_defaults_are_unknown_and_blocked(self):
        defaults = self._section(
            "void EEA_RiskDecisionDefaults",
            "bool EEA_RiskDecisionValidForRelease",
        )
        self.assertIn('decision.decision_status="UNKNOWN";', defaults)
        self.assertIn('decision.release_status="BLOCKED";', defaults)
        for required_default in (
            'decision.decision_id="";',
            'decision.candidate_id="";',
            'decision.setup_id="";',
            'decision.policy_id="";',
            'decision.account_id="";',
            'decision.reconciliation_id="";',
            'decision.symbol="";',
            'decision.quote_id="";',
            'decision.portfolio_snapshot_id="";',
            "decision.final_volume=0.0;",
            "decision.projected_loss=0.0;",
            "decision.available_headroom=0.0;",
            "decision.decided_at_utc=0;",
            "decision.expires_at_utc=0;",
            'decision.reason_code="UNKNOWN";',
        ):
            self.assertIn(required_default, defaults)

    def test_reviewable_candidate_is_not_release_approval(self):
        validation = self._section("bool EEA_RiskDecisionValidForRelease")
        self.assertIn('decision.decision_status!="RISK_APPROVED"', validation)
        self.assertIn('decision.release_status!="RELEASED"', validation)
        self.assertIn('decision.decision_status=="REVIEWABLE_CANDIDATE"', self.source)

    def test_release_validation_requires_lineage_positive_numbers_and_freshness(self):
        validation = self._section("bool EEA_RiskDecisionValidForRelease")
        for required_check in (
            'decision.decision_id==""',
            'decision.candidate_id==""',
            'decision.setup_id==""',
            'decision.policy_id==""',
            'decision.account_id==""',
            'decision.reconciliation_id==""',
            'decision.symbol==""',
            'decision.quote_id==""',
            'decision.portfolio_snapshot_id==""',
            "!MathIsValidNumber(decision.final_volume)",
            "decision.final_volume<=0.0",
            "!MathIsValidNumber(decision.projected_loss)",
            "decision.projected_loss<=0.0",
            "!MathIsValidNumber(decision.available_headroom)",
            "decision.available_headroom<0.0",
            "now_utc<=0",
            "decision.decided_at_utc<=0",
            "decision.expires_at_utc<=decision.decided_at_utc",
            "decision.decided_at_utc>now_utc",
            "decision.expires_at_utc<=now_utc",
        ):
            self.assertIn(required_check, validation)

    def test_release_carries_budget_and_reward_risk_for_intent_binding(self):
        self.assertIn("double risk_budget", self.source)
        self.assertIn("double net_reward_risk", self.source)
        validation = self._section("bool EEA_RiskDecisionValidForRelease")
        self.assertIn("decision.risk_budget", validation)
        self.assertIn("decision.net_reward_risk", validation)
        for field in ("decision.direction", "decision.entry_reference", "decision.stop_loss", "decision.take_profit"):
            self.assertIn(field, validation)

    def test_contract_has_no_broker_io_or_shell_dependencies(self):
        forbidden = (
            "#include",
            "OrderSend",
            "CTrade",
            "FileOpen",
            "WebRequest",
            "SymbolInfo",
            "AccountInfo",
            "PositionGet",
            "ExecutionAdapter",
            "ExecutionGate",
            "EnterpriseEA.mq5",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
