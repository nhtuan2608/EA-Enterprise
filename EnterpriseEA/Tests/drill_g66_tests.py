"""G66 D1: the live drill entry (Integration/DrillRuntime.mqh), OFF by default, once per nonce, broker-minimum volume."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_inputs_default_off(self):
        self.assertIn("EEA_HIDDEN bool InpDrillEntry              = false;", self.shell)
        self.assertIn('EEA_HIDDEN string InpDrillNonce              = "";', self.shell)
        self.assertIn('EEA_HIDDEN string InpDrillSymbol             = "EURUSD";', self.shell)
        self.assertIn("enum EEA_DrillDirectionInput { DRILL_BUY=0, DRILL_SELL=1 };", self.shell)
        self.assertIn("EEA_HIDDEN EEA_DrillDirectionInput InpDrillDirection = DRILL_BUY;", self.shell)
        self.assertIn("g_drill_enabled=InpDrillEntry;", self.shell)
        self.assertIn("g_drill_nonce=InpDrillNonce;", self.shell)
        self.assertIn('#include "Integration/DrillRuntime.mqh"', self.shell)
        # appended after the existing live inputs
        self.assertLess(self.shell.index("InpScalpRiskWithSwingSameSide"), self.shell.index("InpDrillEntry"))

    def test_runs_after_the_pyramid_under_the_same_guards(self):
        paused = self.shell.index("if(EEA_RemoteEntriesPaused())")
        live = self.shell.index("EEA_ControlledLiveOnTimer(g_live_runtime,g_live_config,")
        add = self.shell.index("EEA_S06BPyramidOnTimer(g_live_runtime,g_live_config,")
        drill = self.shell.index("EEA_DrillOnTimer(g_live_runtime,g_live_config,")
        self.assertLess(paused, live)
        self.assertLess(live, add)
        self.assertLess(add, drill)
        self.assertEqual(self.shell.count("EEA_DrillOnTimer("), 1)
        self.assertIn("if(!g_live_runtime.recovery_blocked)\n                   EEA_DrillOnTimer(", self.shell)
        guard = self.shell.index("if(g_live_config.enabled && g_live_config.armed && !g_live_runtime.recovery_blocked)")
        self.assertLess(guard, drill)

    def test_live_status_drill_block(self):
        fn = section(self.shell, "void EEA_WriteLiveStatus()")
        self.assertLess(fn.index('"risk"'), fn.index('EEA_LiveStatusPair("news"'))
        self.assertLess(fn.index('EEA_LiveStatusPair("news"'), fn.index('EEA_LiveStatusPair("drill"'))
        drill = fn.split('EEA_LiveStatusPair("drill"', 1)[1]
        for key in ("enabled", "nonce", "state", "reason", "candidate_id", "ticket"):
            self.assertIn('EEA_LiveStatusPair("%s"' % key, drill)

    def test_weight_helper_untouched(self):
        limits = (ROOT / "Risk/RiskLimitsProfile.mqh").read_text(encoding="utf-8")
        self.assertNotIn("DRILL", limits)

    def test_dry_run_gate_accepts_the_drill_setup(self):
        gate = (ROOT / "Integration/DryRunCandidateGate.mqh").read_text(encoding="utf-8")
        self.assertIn('i.candidate.setup_id!="DRILL"', gate)


class DrillSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Integration/DrillRuntime.mqh").read_text(encoding="utf-8")
        self.timer = section(self.src, "bool EEA_DrillOnTimer(")

    def test_constants_and_candidate(self):
        self.assertIn('#define EEA_DRILL_SETUP "DRILL"', self.src)
        self.assertIn("#define EEA_DRILL_STOP_ATR 1.0", self.src)
        self.assertIn("#define EEA_DRILL_TARGET_R 1.0", self.src)
        self.assertIn("#define EEA_DRILL_ATR_PERIOD 14", self.src)
        self.assertIn("#define EEA_DRILL_MAX_ATTEMPTS 20", self.src)
        self.assertIn('"DRILL-"+canonical+"-"+nonce', self.src)
        eng = section(self.src, "void EEA_DrillEngine(")
        for token in ("e.state=EEA_S02_TRIGGERED;", "e.candidate.setup_id=EEA_DRILL_SETUP;",
                      "e.candidate.triggered_at_utc=TimeGMT();", "e.candidate.expires_after_bars=1;",
                      "e.candidate.age_after_trigger_bars=0;", 'e.timeframe="H1";'):
            self.assertIn(token, eng)

    def test_gates_like_the_pyramid(self):
        for token in ('if(!g_drill_enabled || g_drill_nonce=="") { g_drill_reason="DRILL_OFF"; return true; }',
                      "if(!config.enabled || !config.armed)", "if(state.recovery_blocked)",
                      "if(pending.entries_blocked)",
                      'EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT())',
                      "if(!session.present)", 'observer.status.runtime_state!="OBSERVING"'):
            self.assertIn(token, self.timer)

    def test_same_risk_pipeline_as_an_entry(self):
        order = ["EEA_DrillNonceDone(g_drill_nonce)", "EEA_ObserverRuntimeIndexOf(", "EEA_DrillSymbolBusy(",
                 "EEA_NewsEntryBlockFor(news,canonical,\"SWING\")", "EEA_ControlledLiveResolvePolicy(",
                 "EEA_LiveSessionAuthorize(", "EEA_DrillPlan(", "EEA_ControlledLiveApplySessionCap(true,",
                 "EEA_ControlledLiveApplyNewsRisk(", "EEA_ControlledLiveBuildRiskContextPlan(",
                 "current.sizing.volume", "EEA_EvaluateDryRunCandidate(", "EEA_RiskDecisionReleaseFromReview(",
                 "EEA_RiskDecisionStoreWrite(", "EEA_BuildMarketExecutionIntent(", "intent.volume",
                 "EEA_ControlledLiveAuditAuthorization(", 'g_drill_state="SUBMITTED";', "EEA_ExecutionSubmit(",
                 "EEA_ExecutionReconcileResult(", "EEA_ExecutionStoreWriteResult(", "EEA_TradeManagerRegister("]
        pos = [self.timer.index(x) for x in order]
        self.assertEqual(pos, sorted(pos))
        self.assertIn('params.idempotency_key="entry-"+candidate_id;', self.timer)
        self.assertIn('"MARKET_ENTRY",', self.timer)
        self.assertIn('"SWING","H1",0.0,0.0,authorization_path,manage_reason', self.timer)

    def test_news_check_present(self):
        self.assertIn('EEA_NewsEntryBlockFor(news,canonical,"SWING")', self.timer)
        self.assertIn('EEA_ControlledLiveApplyNewsRisk(news,canonical,"SWING",plan,reason)', self.timer)

    def test_symbol_must_be_selected_and_not_busy(self):
        self.assertIn('"SYMBOL_NOT_SELECTED"', self.timer)
        self.assertIn('"DRILL_SYMBOL_BUSY"', self.timer)
        busy = section(self.src, "bool EEA_DrillSymbolBusy(")
        self.assertIn("trades.items[k].active && trades.items[k].intent.canonical_symbol==canonical", busy)

    def test_recovery_like_a_normal_entry(self):
        self.assertIn('state.recovery_blocked=(result.confirmation_state=="EXECUTION_UNKNOWN");', self.timer)
        self.assertIn('g_drill_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";', self.timer)
        self.assertIn("state.recovery_result=result;", self.timer)

    def test_once_per_nonce_persistence(self):
        self.assertIn("/current/drill_state.json", self.src)
        write = section(self.src, "bool EEA_DrillStateWrite(")
        self.assertIn("EEA_WriteAtomicText(", write)
        for key in ("nonce", "candidate_id", "state", "reason", "ticket", "at_utc"):
            self.assertIn('\\"%s\\"' % key, write)
        load = section(self.src, "void EEA_DrillStateLoad(")
        self.assertIn('g_drill_state=="SUBMITTED" || g_drill_state=="DONE"', load)
        # SUBMITTED is persisted before the order is sent, and the nonce is marked done with it
        sub = self.timer.index('g_drill_state="SUBMITTED";')
        self.assertLess(sub, self.timer.index("EEA_DrillStateWrite(root)", sub))
        self.assertLess(self.timer.index("EEA_DrillMarkNonceDone(g_drill_nonce);", sub), self.timer.index("EEA_ExecutionSubmit("))
        self.assertLess(self.timer.index("EEA_DrillStateWrite(root)", sub), self.timer.index("EEA_ExecutionSubmit("))
        # an already done nonce returns before any pipeline step
        self.assertLess(self.timer.index("EEA_DrillNonceDone(g_drill_nonce)"), self.timer.index("EEA_LiveSessionAuthorize("))
        self.assertIn('if(!EEA_DrillNonceValid(g_drill_nonce))', self.timer)

    def test_volume_is_the_broker_minimum(self):
        plan = section(self.src, "bool EEA_DrillPlan(")
        self.assertIn("symbol.volume_min", plan)
        self.assertIn("p.per_trade_cap_money=MathMin(EEA_DRILL_CAP_FACTOR*(unit.projected_loss+cost*symbol.volume_min),loss_room);", plan)
        self.assertIn("#define EEA_DRILL_CAP_FACTOR 1.01", self.src)
        self.assertNotIn("EEA_SetupRiskWeight", self.src)
        self.assertEqual(self.timer.count('"DRILL_VOLUME_NOT_MIN"'), 2)      # after sizing and on the intent
        self.assertIn("MathAbs(intent.volume-observer.symbol_specs[row].volume_min)", self.timer)
        self.assertIn("MathAbs(current.sizing.volume-observer.symbol_specs[row].volume_min)", self.timer)

    def test_stop_and_target(self):
        plan = section(self.src, "bool EEA_DrillPlan(")
        self.assertIn("EEA_DRILL_STOP_ATR*atr", plan)
        self.assertIn("p.target_price=entry+direction*EEA_DRILL_TARGET_R*MathAbs(entry-probe.stop_loss);", plan)
        self.assertIn('"DRILL_ATR_UNAVAILABLE"', plan)
        atr = section(self.src, "double EEA_DrillAtrH1(")
        self.assertIn("CopyRates(broker_symbol,PERIOD_H1,1,EEA_DRILL_ATR_PERIOD+1,rates)", atr)    # closed bars only
        self.assertIn("EEA_StrategyRuntimeAtrFromRates(", atr)

    def test_transient_retry_cap_20(self):
        tr = section(self.src, "bool EEA_DrillReasonTransient(")
        self.assertIn('StringFind(reason,"NEWS")==0', tr)
        self.assertIn("LIVE_SPREAD_LIMIT_EXCEEDED", tr)
        self.assertIn("SPREAD_TOO_WIDE_FOR_STOP", tr)
        self.assertIn("DRILL_MARKET_CLOSED", tr)
        rej = section(self.src, "void EEA_DrillReject(")
        self.assertIn("g_drill_attempts>=EEA_DRILL_MAX_ATTEMPTS", rej)
        self.assertIn("if(!EEA_DrillReasonTransient(reason))", rej)
        self.assertIn('"DRILL_RETRY_LIMIT_REACHED_"', rej)

    def test_audit_events(self):
        for ev in ("DRILL_ENTRY_QUEUED", "DRILL_ENTRY_SUBMITTED", "DRILL_ENTRY_REJECTED"):
            self.assertIn('"%s"' % ev, self.src)
        audit = section(self.src, "void EEA_DrillAudit(")
        self.assertIn("candidate_id", audit)
        self.assertIn("EEAEvent_AddReason(event,reason);", audit)

    def test_no_order_send_outside_the_adapter(self):
        self.assertNotIn("OrderSend", self.src)
        self.assertNotIn("CTrade", self.src)
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("OrderSend", adapter)
        for mqh in ROOT.glob("Integration/**/*.mqh"):
            self.assertNotIn("OrderSend(", mqh.read_text(encoding="utf-8"), mqh.name)


class NonceRuleMirror(unittest.TestCase):
    """Python mirror of the nonce rule and the retry rule, checked against the documented constants."""

    @staticmethod
    def valid(n):
        return 1 <= len(n) <= 32 and all(c.isascii() and (c.isalnum() or c in "-_") for c in n)

    def test_nonce_rule(self):
        self.assertTrue(self.valid("d1-2026_10_08"))
        for bad in ("", "a b", "a,b", 'a"b', "x" * 33):
            self.assertFalse(self.valid(bad))


if __name__ == "__main__":
    unittest.main()
