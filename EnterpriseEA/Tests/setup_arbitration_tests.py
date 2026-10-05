"""G18 setup arbitration: evidence priority (B), one trade per symbol/side/profile (E2),
reduced SCALP risk stacked on a same-side SWING (A4), per-candidate reasons."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rank(setup, profile):
    """Mirror of EEA_SetupPriorityRank."""
    return (0 if profile == "SWING" else 3) + (0 if setup == "S06" else 1 if setup == "S04" else 2)


def order(setups, profiles):
    """Mirror of EEA_SetupPriorityOrder (stable insertion sort)."""
    return sorted(range(len(setups)), key=lambda i: (rank(setups[i], profiles[i]), i))


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class PriorityTests(unittest.TestCase):
    def test_evidence_order(self):
        cells = [("S06", "SWING"), ("S04", "SWING"), ("S02", "SWING"), ("S04", "SCALP"), ("S02", "SCALP")]
        self.assertEqual([rank(s, p) for s, p in cells], [0, 1, 2, 4, 5])

    def test_engine_layout_of_two_symbols(self):
        # Engine layout per symbol: S02 SC, S02 SW, S04 SC, S04 SW, S06 SW.
        setups = ["S02", "S02", "S04", "S04", "S06"] * 2
        profiles = ["SCALP", "SWING", "SCALP", "SWING", "SWING"] * 2
        self.assertEqual(order(setups, profiles), [4, 9, 3, 8, 1, 6, 2, 7, 0, 5])

    def test_mql_matches_mirror(self):
        src = (ROOT / "Integration/SetupArbitration.mqh").read_text(encoding="utf-8")
        self.assertIn('const int setup_rank=(setup=="S06" || setup=="S06B" ? 0 : setup=="S04" ? 1 : 2);', src)
        self.assertIn('return (profile=="SWING" ? 0 : 3)+setup_rank;', src)
        # Stable: only strictly higher ranks move.
        self.assertIn("EEA_SetupPriorityRank(setup[order[j]],profile[order[j]])>rank", src)


class LiveLoopTests(unittest.TestCase):
    def setUp(self):
        self.cl = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.loop = self.cl.split("bool EEA_ControlledLiveOnTimer(", 1)[1]

    def test_loop_visits_by_priority(self):
        self.assertIn("EEA_SetupPriorityOrder(strategy.setup,strategy.profile,strategy.symbol_count,order);", self.loop)
        self.assertIn("const int i=order[k];", self.loop)
        self.assertNotIn("for(int i=0;i<strategy.symbol_count;i++)", self.loop)

    def test_duplicate_same_side_blocks_before_plan(self):
        e2 = self.loop.index('state.last_reason="DUPLICATE_SAME_SIDE"; continue;')
        self.assertLess(self.loop.index('state.last_reason="OPPOSITE_SETUP_ACTIVE"; continue;'), e2)
        self.assertLess(e2, self.loop.index("EEA_ControlledLiveResolveV1Plan("))
        same = section(self.cl, "bool EEA_ControlledLiveSameSideActive(")
        self.assertIn("trades.items[i].direction==direction && trades.items[i].profile==profile", same)
        self.assertIn('(pending.items[i].timeframe=="H1" ? "SWING" : "SCALP")!=profile', same)

    def test_scalp_stacked_on_swing_takes_reduced_risk(self):
        stack = section(self.cl, "bool EEA_ControlledLiveApplyStackRisk(")
        self.assertIn('if(strategy.profile[index]!="SCALP") return true;', stack)
        self.assertIn('strategy.engines[index].direction,"SWING")) return true;', stack)
        self.assertIn("plan.base_risk_fraction*=MathMax(0.0,MathMin(1.0,factor));", stack)
        self.assertIn("EEA_ControlledLiveApplyStackRisk(trades,pending,strategy,i,config.scalp_risk_with_swing_same_side,",
                      self.loop)
        self.assertIn("c.scalp_risk_with_swing_same_side=0.5;", self.cl)
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("input double InpScalpRiskWithSwingSameSide = 0.5;", shell)
        self.assertIn("MathMax(0.0,MathMin(1.0,InpScalpRiskWithSwingSameSide));", shell)

    def test_reason_is_kept_per_candidate(self):
        self.assertIn("if(noted>=0) state.candidate_reason[noted]=state.last_reason;", self.loop)
        self.assertIn("noted=i;\n      state.reason_candidate[i]=candidate_id;", self.loop)
        self.assertIn('state.candidate_reason[i]="EXECUTED";\n         return true;', self.loop)
        # Every early exit after the candidate is noted names its reason.
        noted_at = self.loop.index("noted=i;")
        body = self.loop[noted_at:self.loop.index("state.last_reason=result.reason_code;")]
        lines = body.splitlines()
        exits = [k for k, line in enumerate(lines) if "continue;" in line]
        self.assertGreater(len(exits), 10)
        for k in exits:
            window = "\n".join(lines[max(0, k - 20):k + 1])
            self.assertIn("state.last_reason=", window, lines[k])


if __name__ == "__main__":
    unittest.main()
