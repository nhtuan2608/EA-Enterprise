"""G40: T2 live path behind InpT2Mode=T2_LIVE (default SHADOW): POSITION Trade Manager profile, POSITION treated
as SWING for news, sentiment, session quota and costs, live_status.json and /status."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "bridge"))

from telegram_gateway_tests import GatewayCase  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class TradeManagerPositionTests(unittest.TestCase):
    def setUp(self):
        self.tm = (ROOT / "Runtime/TradeManagerRuntime.mqh").read_text(encoding="utf-8")
        self.prof = self.tm.split('if(profile=="POSITION")', 1)[1].split("return;", 1)[0]

    def test_profile_matches_research_trend_rule(self):
        for token in ("p.be_at_r=1.0e9;", "p.partial_at_r=1.0e9;", "p.trail_start_r=0.0;",
                      "p.trail_mode=EEA_TM_TRAIL_ATR;", "p.trail_atr_mult=3.0;", "p.timeout_bars=180;"):
            self.assertIn(token, self.prof)
        sys.path.insert(0, str(ROOT / "research" / "g10"))
        import candidates_eval as ce
        self.assertEqual(ce.T2_RULE["trail"], ("ATR", 0.0, 3.0))      # same trail as the research / virtual results
        self.assertIsNone(ce.T2_RULE["be"]); self.assertIsNone(ce.T2_RULE["partial"])

    def test_trail_tightens_only_past_break_even(self):
        upd = section(self.tm, "void EEA_TradeManagerUpdate(")
        self.assertIn("if(trail>0.0 && t.direction*(trail-be_price)>0.0 &&", upd)
        self.assertIn("t.direction*(trail-position.sl)>=0.1*r)", upd)
        self.assertIn("trail=last.close-t.direction*p.trail_atr_mult*atr;", upd)

    def test_swing_and_scalp_untouched(self):
        swing = self.tm.split('if(profile=="SWING")', 1)[1].split("return;", 1)[0]
        self.assertIn("p.trail_mode=EEA_TM_TRAIL_STRUCTURE;", swing)
        self.assertIn("p.timeout_bars=120;", swing)


class LivePathTests(unittest.TestCase):
    def setUp(self):
        self.live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.timer = section(self.live, "bool EEA_ControlledLiveOnTimer(")

    def test_position_follows_swing_rules(self):
        self.assertIn('string EEA_RiskProfileOf(const string profile) { return profile=="POSITION" ? "SWING" : profile; }', self.live)
        self.assertIn('news_profile=(strategy.zone_mode ? EEA_RiskProfileOf(strategy.profile[i]) : "SCALP");', self.timer)
        self.assertIn('entry_profile=(strategy.zone_mode ? EEA_RiskProfileOf(strategy.profile[i]) : "SCALP");', self.timer)
        sent = section(self.live, "bool EEA_ControlledLiveApplySentiment(")
        self.assertIn("const string profile=EEA_RiskProfileOf(strategy.profile[index]);", sent)
        plan = section(self.live, "bool EEA_ControlledLiveResolveV1Plan(")
        self.assertIn('bool swing=(EEA_RiskProfileOf(strategy.profile[index])=="SWING");', plan)
        self.assertIn('strategy.profile[index]=="POSITION" ? EEA_T2_EXPECTED_NIGHTS : EEA_S02_SWING_EXPECTED_NIGHTS', plan)

    def test_t2_registered_without_structure_exit(self):
        self.assertIn('strategy.setup[i]=="T2" ? 0.0 : strategy.engines[i].zone_low', self.timer)
        self.assertIn('strategy.setup[i]=="T2" ? 0.0 : strategy.engines[i].zone_high', self.timer)

    def test_same_side_rule_per_profile_and_live_mode_gate(self):
        self.assertIn("strategy.engines[i].direction,strategy.profile[i]))", self.timer)   # one per symbol, side, profile
        self.assertIn("if(strategy.zone_mode && EEA_StrategyRuntimeEngineMode(strategy,i)!=EEA_S04_MODE_LIVE) continue;", self.timer)

    def test_dry_run_gate_accepts_t2(self):
        gate = (ROOT / "Integration/DryRunCandidateGate.mqh").read_text(encoding="utf-8")
        self.assertIn('i.candidate.setup_id!="T2"', gate)

    def test_target_cap_and_nights(self):
        eng = (ROOT / "Setups/DonchianTrend.mqh").read_text(encoding="utf-8")
        self.assertIn("#define EEA_T2_TARGET_CAP_R 20.0", eng)
        self.assertIn("#define EEA_T2_EXPECTED_NIGHTS 10.0", eng)


class LiveSymbolsTests(unittest.TestCase):
    """G41: T2 trades LIVE only on the listed trend assets; the other symbols keep recording in SHADOW."""

    def setUp(self):
        self.rt = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_default_list_and_wiring(self):
        self.assertIn('input string InpT2LiveSymbols           = "XAUUSD,BTCUSD";', self.shell)
        init = self.shell.index("(int)InpT2Mode);")
        self.assertLess(init, self.shell.index("g_strategy_runtime.t2_live_symbols=InpT2LiveSymbols;"))

    def test_engine_mode_caps_unlisted_symbols(self):
        fn = section(self.rt, "int EEA_StrategyRuntimeEngineMode(")
        self.assertIn('if(runtime.setup[index]=="T2" && mode==EEA_S04_MODE_LIVE &&', fn)
        self.assertIn("!EEA_StrategyRuntimeSymbolListed(runtime.t2_live_symbols,runtime.engines[index].canonical_symbol))", fn)
        self.assertIn("mode=EEA_S04_MODE_SHADOW;", fn)

        def listed(lst, sym):          # mirror of EEA_StrategyRuntimeSymbolListed
            return any(p.strip().upper() == sym.upper() and p.strip() for p in lst.split(","))
        self.assertTrue(listed("XAUUSD, btcusd", "BTCUSD"))
        self.assertFalse(listed("XAUUSD,BTCUSD", "EURUSD"))
        self.assertFalse(listed("", "XAUUSD"))
        lst = section(self.rt, "bool EEA_StrategyRuntimeSymbolListed(")
        self.assertIn("StringTrimLeft(s); StringTrimRight(s); StringToUpper(s);", lst)


class LiveStatusTests(unittest.TestCase):
    def test_written_on_timer_never_on_tick(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        timer = shell.split("void OnTimer()", 1)[1]
        tick = shell.split("void OnTick()", 1)[1].split("void OnTimer()", 1)[0]
        self.assertIn("EEA_WriteLiveStatus();", timer)
        self.assertNotIn("EEA_WriteLiveStatus", tick)
        fn = section(shell, "void EEA_WriteLiveStatus()")
        for key in ("execution_enabled", "observer_only", "live_trade_armed", "live_path_armed", "session",
                    "operator_paused", "recovery_blocked", "last_reason", "modes", "s06b_pyramid_live"):
            self.assertIn(f'"{key}"', fn)
        self.assertIn("if(now-g_live_status_written<30) return;", fn)
        self.assertIn('"/current/live_status.json"', fn)

    def test_written_every_timer_with_strategy_diagnostics(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        timer = shell.split("void OnTimer()", 1)[1]
        # once per timer, before (outside) the strategy branch, so a disabled strategy runtime still reports
        self.assertEqual(timer.count("EEA_WriteLiveStatus();"), 1)
        self.assertLess(timer.index("EEA_WriteLiveStatus();"),
                        timer.index('if(InpStrategyRuntimeEnabled && g_runtime.status.runtime_state=="OBSERVING" &&'))
        fn = section(shell, "void EEA_WriteLiveStatus()")
        for key in ("strategy_running", "strategy_enabled", "strategy_checkpoints_loaded", "strategy_reason",
                    "runtime_state", "runtime_reason"):
            self.assertIn(f'"{key}"', fn)
        for reason in ("INPUT_STRATEGY_RUNTIME_DISABLED", '"RUNTIME_"+g_runtime.status.runtime_state',
                       "CHECKPOINTS_NOT_LOADED_YET"):
            self.assertIn(reason, fn)


class StatusLineTests(GatewayCase):
    def status(self, **kw):
        base = {"written_at_utc": int(self.clock()), "execution_enabled": True, "observer_only": False,
                "live_trade_armed": True, "operator_paused": False, "recovery_blocked": False, "session": "ACTIVE",
                "modes": {"S04": "LIVE", "S06B": "SHADOW", "T2": "SHADOW"}}
        base.update(kw)
        self.write("current/live_status.json", base)
        return self.gw.live_text()

    def test_ready(self):
        self.assertEqual(self.status(), "SẴN SÀNG; LIVE: S04")

    def test_names_what_blocks_entries(self):
        txt = self.status(live_trade_armed=False, session="EXPIRED")
        self.assertIn("KHÔNG vào được", txt)
        self.assertIn("InpLiveTradeArmed=false", txt)
        self.assertIn("phiên EXPIRED", txt)

    def test_strategy_off_blocks_and_names_the_reason(self):
        txt = self.status(strategy_running=False, strategy_reason="EEA_STRATEGY_RUNTIME_CHECKPOINT_CORRUPT")
        self.assertIn("KHÔNG vào được", txt)
        self.assertIn("chiến lược tắt: EEA_STRATEGY_RUNTIME_CHECKPOINT_CORRUPT", txt)
        self.assertEqual(self.status(strategy_running=True), "SẴN SÀNG; LIVE: S04")

    def test_stale_and_missing(self):
        self.assertIn("[cũ", self.status(written_at_utc=int(self.clock()) - 600))
        (self.root / "current" / "live_status.json").unlink()
        self.assertIn("chưa có live_status.json", self.gw.live_text())


if __name__ == "__main__":
    unittest.main()
