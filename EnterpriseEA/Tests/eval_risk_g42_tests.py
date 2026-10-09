"""G42: risk per trade for the evaluation phase (Risk/RiskLimitsProfile.mqh, InpEvalRiskPercent)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = 0.015
FIRM = {"FTMO_1_STEP": (0.03, 0.10), "FTMO_2_STEP": (0.05, 0.10), "BALANCE_BASED_FTMO_V1": (0.05, 0.10)}


def limits(policy, override=0.0, custom=None):
    """Python mirror of EEA_RiskLimitsForPolicy."""
    daily, overall = custom if custom else FIRM[policy]
    day_int = min(0.4 * daily, 0.02)
    out = {"per_trade": day_int / 4.0, "daily": day_int, "open": day_int, "currency": 2.5 * day_int / 4.0,
           "weekly": min(2.0 * day_int, 0.4 * overall), "buffer": day_int / 4.0}
    if override > 0.0:
        ceiling = 0.8 * daily
        p = min(min(override, CAP), 0.5 * ceiling)
        out = {"per_trade": p, "daily": min(4.0 * p, ceiling), "open": min(4.0 * p, ceiling),
               "currency": 2.5 * p, "weekly": min(2.0 * min(4.0 * p, ceiling), 0.8 * overall), "buffer": p}
    return out


class EvalRiskTests(unittest.TestCase):
    def test_no_override_is_the_derived_set(self):
        two = limits("FTMO_2_STEP")
        self.assertAlmostEqual(two["per_trade"], 0.005)
        self.assertAlmostEqual(two["daily"], 0.02)
        self.assertAlmostEqual(two["weekly"], 0.04)
        one = limits("FTMO_1_STEP")
        self.assertAlmostEqual(one["per_trade"], 0.003)
        self.assertAlmostEqual(one["daily"], 0.012)

    def test_override_at_the_derived_value_changes_nothing(self):
        a, b = limits("FTMO_2_STEP"), limits("FTMO_2_STEP", 0.005)
        for key in a:
            self.assertAlmostEqual(a[key], b[key], msg=key)

    def test_two_step_at_one_and_a_half_percent(self):
        r = limits("FTMO_2_STEP", 0.015)
        self.assertAlmostEqual(r["per_trade"], 0.015)
        self.assertAlmostEqual(r["daily"], 0.04)     # 4x would be 6%: held at 80% of the firm's 5%
        self.assertAlmostEqual(r["open"], 0.04)
        self.assertAlmostEqual(r["weekly"], 0.08)
        self.assertAlmostEqual(r["buffer"], 0.015)

    def test_one_step_is_clipped_by_its_smaller_daily_allowance(self):
        r = limits("FTMO_1_STEP", 0.015)
        self.assertAlmostEqual(r["daily"], 0.024)    # 80% of 3%
        self.assertAlmostEqual(r["per_trade"], 0.012)  # half the internal daily limit

    def test_cap_and_ceilings_hold_for_any_request(self):
        for policy in FIRM:
            for req in (0.001, 0.005, 0.01, 0.015, 0.05, 1.0):
                r = limits(policy, req)
                firm_daily, firm_overall = FIRM[policy]
                self.assertLessEqual(r["per_trade"], CAP + 1e-12)
                self.assertLessEqual(r["daily"], 0.8 * firm_daily + 1e-12)
                self.assertLessEqual(r["weekly"], 0.8 * firm_overall + 1e-12)
                self.assertLessEqual(r["per_trade"], 0.5 * r["daily"] + 1e-12)
                # the session store accepts these limits
                self.assertLessEqual(r["per_trade"], 0.02)
                self.assertLessEqual(r["daily"], 0.05)

    def test_custom_small_daily_allowance_still_leaves_room(self):
        r = limits("CUSTOM", 0.015, custom=(0.01, 0.05))
        self.assertAlmostEqual(r["daily"], 0.008)
        self.assertAlmostEqual(r["per_trade"], 0.004)


class SourceTests(unittest.TestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_mql_matches_the_mirror(self):
        src = self.read("Risk/RiskLimitsProfile.mqh")
        for token in ("0.8*l.firm_daily_fraction", "MathMin(g_risk_per_trade_override,EEA_RISK_OVERRIDE_CAP),0.5*day_ceiling",
                      "MathMin(4.0*p,day_ceiling)", "2.5*p", "MathMin(2.0*l.internal_daily_fraction,0.8*l.firm_overall_fraction)",
                      "l.safety_buffer_fraction=p"):
            self.assertIn(token, src)
        self.assertIn("#define EEA_RISK_OVERRIDE_CAP 0.015", self.read("Risk/PolicyRules.mqh"))

    def test_inputs_default_to_the_decision_and_funded_turns_it_off(self):
        shell = self.read("EnterpriseEA.mq5")
        self.assertIn("InpAccountPhase = PHASE_EVALUATION", shell)
        self.assertIn("InpEvalRiskPercent         = 0.5", shell)
        self.assertIn("InpAccountPhase==PHASE_EVALUATION && InpEvalRiskPercent>0.0", shell)
        self.assertIn("MathMin(InpEvalRiskPercent/100.0,EEA_RISK_OVERRIDE_CAP) : 0.0", shell)


if __name__ == "__main__":
    unittest.main()
