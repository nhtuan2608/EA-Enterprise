"""G26 (step 1 after G23/G24/G25): SCALP mode cap, S06B variant, per-engine modes, AI review fix."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import s06_oracle as s06  # noqa: E402
from s06_compression_expansion_tests import synthetic_bars  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class DefaultsTests(unittest.TestCase):
    def setUp(self):
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_recommended_defaults(self):
        for token in ("input EEA_S02ModeInput InpS02Mode       = S02_SHADOW;",
                      "input EEA_S04ModeInput InpS04Mode       = S04_LIVE;",
                      "input EEA_S06ModeInput InpS06Mode       = S06_SHADOW;",
                      "input EEA_S06BModeInput InpS06BMode     = S06B_SHADOW;",
                      "input EEA_ScalpModeInput InpScalpMode   = SCALP_SHADOW;"):
            self.assertIn(token, self.shell)

    def test_ai_review_not_requeued_on_reinit(self):
        timer = section(self.shell, "void EEA_AiTimer()")
        self.assertIn("if(g_news_reaction.loaded && !g_ai_backfill_known)", timer)
        self.assertIn("{ g_ai_backfill_done_seen=g_news_reaction.backfill_done; g_ai_backfill_known=true; }", timer)
        self.assertLess(timer.index("g_ai_backfill_known=true"),
                        timer.index("bool backfill_finished=(g_news_reaction.backfill_done && !g_ai_backfill_done_seen);"))


class EngineModeTests(unittest.TestCase):
    def setUp(self):
        self.rt = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")

    def test_scalp_cap(self):
        fn = section(self.rt, "int EEA_StrategyRuntimeEngineMode(")
        self.assertIn('return runtime.profile[index]=="SCALP" ? MathMin(mode,runtime.scalp_mode) : mode;', fn)

        def mode(setup_mode, profile, scalp_mode):      # mirror (OFF 0 < SHADOW 1 < LIVE 2)
            return min(setup_mode, scalp_mode) if profile == "SCALP" else setup_mode
        self.assertEqual(mode(2, "SCALP", 1), 1)        # S04 SCALP LIVE -> SHADOW
        self.assertEqual(mode(2, "SWING", 1), 2)        # S04 SWING stays LIVE
        self.assertEqual(mode(1, "SCALP", 2), 1)

    def test_every_decision_uses_engine_mode(self):
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        ledger = (ROOT / "Integration/CandidateLedger.mqh").read_text(encoding="utf-8")
        self.assertEqual(live.count("EEA_StrategyRuntimeEngineMode(strategy,i)"), 2)
        self.assertNotIn("EEA_StrategyRuntimeSetupMode(", live)
        self.assertIn("const int mode=EEA_StrategyRuntimeEngineMode(strategy,i);", ledger)

    def test_s06b_slot_and_checkpoint(self):
        self.assertIn('else { setup="S06B"; EEA_S06BV1Config(config); }', self.rt)
        self.assertIn('runtime.setup[index]=="S06B" ? "_s06b"', self.rt)
        self.assertIn("(runtime.s06b_mode==EEA_S04_MODE_OFF ? 0 : 1)", self.rt)


class S06BTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Setups/CompressionExpansion.mqh").read_text(encoding="utf-8")

    def test_config_identity(self):
        self.assertIn('c.config_version="s06b-v1-swing-0.1.0";', self.src)
        self.assertIn("#define EEA_S06B_BOX_BARS 24", self.src)
        self.assertIn('return EEA_S06IsVariantB(c) ? "S06B" : "S06";', self.src)
        self.assertEqual(s06.BOX_BARS_B, 24)

    def test_release_triggers_at_once(self):
        start = section(self.src, "void EEA_S06StartRelease(")
        self.assertIn("if(EEA_S06IsVariantB(c))", start)
        self.assertIn('EEA_S06Transition(e,ev,b.closed_at_utc,EEA_S02_TRIGGERED,"CANDIDATE_TRIGGERED",', start)

    def test_oracle_immediate_variant(self):
        bars = synthetic_bars(4)
        confirm = s06.run(bars)
        immediate = s06.run(bars, box_bars=24, immediate=True)
        self.assertGreater(len(immediate), 0)
        for c in immediate:                              # entry on the release bar, ATR of the bar before
            self.assertAlmostEqual(c["signal_atr"], bars[c["i"] - 1]["atr"])
        self.assertNotEqual([c["i"] for c in confirm], [c["i"] for c in immediate])

    def test_live_plan_keeps_every_side_for_s06b(self):
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn('const bool s06=(strategy.setup[index]=="S06" || strategy.setup[index]=="S06B");', live)
        self.assertIn('if(strategy.setup[index]=="S06" && strategy.htf_risk_modifier[index]<1.0)', live)
        self.assertIn('setup=="S06B" ? "/logs/s06b_shadow.jsonl"', live)
        gate = (ROOT / "Integration/DryRunCandidateGate.mqh").read_text(encoding="utf-8")
        self.assertIn('i.candidate.setup_id!="S06B"', gate)


if __name__ == "__main__":
    unittest.main()
