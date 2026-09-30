"""Synthetic composition tests; component results are contract fixtures, not MT5 proof."""
import json
import unittest
from pathlib import Path

from dry_run_gate_oracle import evaluate, mutate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/dry-run-gate-v0.1.0.json").read_text(encoding="utf-8"))


class DryRunCandidateGateExamples(unittest.TestCase):
    def test_end_to_end_fixed_cases(self):
        for row in FIXTURE["cases"]:
            with self.subTest(name=row["name"]):
                case = FIXTURE["base"]
                for path, value in row["mutations"]:
                    case = mutate(case, path, value)
                actual = evaluate(case)
                self.assertEqual(actual["decision_status"], row["expected"]["decision_status"])
                self.assertIn(row["expected"]["reason_code"], actual["reason_codes"])
                if row["expected"]["decision_status"] == "REVIEWABLE_CANDIDATE":
                    self.assertEqual(actual["candidate_id"], case["candidate"]["candidate_id"])
                    self.assertEqual(actual["final_volume"], case["sizing"]["volume"])
                else:
                    self.assertEqual(actual["final_volume"], 0)
                    self.assertEqual(actual["projected_loss"], 0)
                    self.assertEqual(actual["net_reward_risk"], 0)

    def test_gate_isolated_and_never_emits_execution_permission(self):
        source = (ROOT / "Integration/DryRunCandidateGate.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("REVIEWABLE_CANDIDATE", source)
        self.assertNotIn('"ALLOW"', source)
        self.assertNotIn("ORDER_INTENT", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("DryRunCandidateGate.mqh", shell)


if __name__ == "__main__":
    unittest.main()
