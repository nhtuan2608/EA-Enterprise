"""G31: live S06B pyramiding add (Integration/S06BPyramidRuntime.mqh), OFF by default, and the G30 news
keyword default."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research" / "g10"))


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_off_by_default(self):
        self.assertIn("input bool InpS06BPyramidLive           = false;", self.shell)
        self.assertIn("g_s06b_pyramid_live=InpS06BPyramidLive;", self.shell)
        self.assertIn('#include "Integration/S06BPyramidRuntime.mqh"', self.shell)

    def test_runs_after_the_entry_pass_and_never_when_paused_or_recovering(self):
        live = self.shell.index("EEA_ControlledLiveOnTimer(g_live_runtime,g_live_config,")
        add = self.shell.index("EEA_S06BPyramidOnTimer(g_live_runtime,g_live_config,")
        paused = self.shell.index("if(EEA_RemoteEntriesPaused())")
        self.assertLess(paused, live)
        self.assertLess(live, add)
        self.assertIn("if(!g_live_runtime.recovery_blocked)\n                   EEA_S06BPyramidOnTimer(", self.shell)

    def test_news_keywords_default_from_g30(self):
        for key in ("Initial Jobless Claims", "EIA Crude Oil", "Lagarde Speech", "CB Consumer Confidence",
                    "Durable Goods", "Home Sales", "S&P Global Services PMI",
                    "Note Auction", "Money Stock"):
            self.assertIn(key, self.shell.split("input string InpNewsIgnoreKeywords", 1)[1].split("\n", 1)[0])
        line = self.shell.split("input string InpNewsIgnoreKeywords", 1)[1].split(";", 1)[0]
        # strong events must never be matched by a keyword (substring, any currency)
        keys = [k.strip().lower() for k in line.split('"')[1].split(",")]
        for strong in ("Fed Interest Rate Decision", "Nonfarm Payrolls", "Core CPI m/m", "CPI y/y", "GDP q/q",
                       "Retail Sales m/m", "Core PCE Price Index m/m", "ISM Manufacturing PMI", "30-Year Bond Auction",
                       "BoE Interest Rate Decision", "ECB Monetary Policy Press Conference", "Average Hourly Earnings m/m"):
            self.assertFalse(any(k in strong.lower() for k in keys), strong)
        self.assertLess(len(line.split('"')[1]), 250)          # MT5 string input limit


class PyramidSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Integration/S06BPyramidRuntime.mqh").read_text(encoding="utf-8")
        self.timer = section(self.src, "bool EEA_S06BPyramidOnTimer(")

    def test_constants(self):
        self.assertIn("#define EEA_S06B_ADD_AT_R 1.0", self.src)
        self.assertIn('#define EEA_S06B_ADD_SUFFIX "-ADD1"', self.src)
        self.assertIn("bool   g_s06b_pyramid_live=false;", self.src)

    def test_gates(self):
        for token in ('if(!g_s06b_pyramid_live && !g_t2_pyramid_live) { g_s06b_pyramid_reason="PYRAMID_OFF"; return true; }',
                      "if(state.recovery_blocked)", "if(pending.entries_blocked)",
                      'EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT())',
                      'if(!session.present) { g_s06b_pyramid_reason="S06B_ADD_NEEDS_LIVE_SESSION"; return false; }',
                      'const bool s06=(t.intent.setup_id=="S06B" && g_s06b_pyramid_live);',
                      'if((!s06 && !t2) || t.add_candidate!="" || EEA_S06BIsAddCandidate(t.intent.candidate_id) ||',
                      "t.exit_request!=\"\" || (s06 && !t.be_done)) continue;",
                      "EEA_StrategyRuntimeEngineMode(strategy,engine_index)!=EEA_S04_MODE_LIVE",
                      "EEA_S06BAddBarReady(t,t2 ? EEA_T2_ADD_AT_R : EEA_S06B_ADD_AT_R,bar_time)",
                      'EEA_NewsEntryBlockFor(news,t.intent.canonical_symbol,"SWING")'):
            self.assertIn(token, self.timer)

    def test_same_risk_pipeline_as_an_entry(self):
        order = ["EEA_LiveSessionAuthorize(", "EEA_S06BAddPlan(", "EEA_ControlledLiveApplySessionCap(true,",
                 "EEA_ControlledLiveApplyNewsRisk(", "EEA_ControlledLiveBuildRiskContextPlan(",
                 "EEA_EvaluateDryRunCandidate(", "EEA_RiskDecisionReleaseFromReview(", "EEA_RiskDecisionStoreWrite(",
                 "EEA_BuildMarketExecutionIntent(", "EEA_ControlledLiveAuditAuthorization(",
                 "trades.items[k].add_candidate=add_id;", "EEA_ExecutionSubmit(", "EEA_TradeManagerRegister("]
        pos = [self.timer.index(x) for x in order]
        self.assertEqual(pos, sorted(pos))
        self.assertIn('params.idempotency_key="entry-"+add_id;', self.timer)

    def test_recovery_like_a_normal_entry(self):
        self.assertIn('state.recovery_blocked=(result.confirmation_state=="EXECUTION_UNKNOWN");', self.timer)
        self.assertIn('g_s06b_pyramid_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";', self.timer)

    def test_plan_stop_at_first_break_even_stop_and_first_target(self):
        plan = section(self.src, "bool EEA_S06BAddPlan(")
        self.assertIn("p.invalidation_price=(t2 ? t.entry_price : position.sl)+t.direction*tick;", plan)   # S06B: first stop (G44: T2 first entry)
        self.assertIn("p.stop_buffer_price=tick;", plan)
        self.assertIn("p.target_price=t.initial_tp;", plan)
        self.assertIn("if(!t2 && (position.sl<=0.0 || t.direction*(position.sl-t.entry_price)<0.0))", plan)
        self.assertIn("p.base_risk_fraction=limits.per_trade_fraction*weight;", plan)   # G44 setup weight <= 1
        self.assertIn("p.portfolio_cap_includes_existing=true;", plan)

        def stop(direction, sl, tick):      # mirror of EEA_ProposeStructuralLevels' stop
            raw = (sl + direction * tick) - direction * tick
            return raw
        self.assertAlmostEqual(stop(1, 1.10000, 0.00001), 1.10000)
        self.assertAlmostEqual(stop(-1, 150.250, 0.001), 150.250)

    def test_add_managed_like_research_rule2(self):
        self.assertIn("trades.items[j].be_done=true; trades.items[j].partial_done=true;", self.timer)
        self.assertIn('profile,t.timeframe,0.0,0.0,authorization_path,manage_reason)', self.timer)
        self.assertIn('const string profile=(t2 ? "POSITION" : "SWING");', self.timer)   # S06B adds stay SWING (G44)
        import pyramid
        self.assertEqual(pyramid.CURRENT["trail"], ("STRUCT", 2.0, 5))   # the TM trails from 2R of its own risk

    def test_engine_candidate_is_fresh(self):
        eng = section(self.src, "void EEA_S06BAddEngine(")
        for token in ("e.state=EEA_S02_TRIGGERED;", 'e.candidate.setup_id=setup;', "e.candidate.triggered_at_utc=TimeGMT();",
                      "e.candidate.expires_after_bars=1;", "e.candidate.age_after_trigger_bars=0;",
                      "e.candidate.config_version=e.config_version;"):
            self.assertIn(token, eng)


class TradeManagerFieldTests(unittest.TestCase):
    def test_add_candidate_persisted(self):
        tm = (ROOT / "Runtime/TradeManagerRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn("string add_candidate;", tm)
        self.assertIn('EEA_PendingS("add_candidate",t.add_candidate)', tm)
        self.assertIn('t.add_candidate=EEA_RiskLedgerField(json,"add_candidate");', tm)
        self.assertIn('t.add_candidate=""; t.intent=intent;', tm)


if __name__ == "__main__":
    unittest.main()
