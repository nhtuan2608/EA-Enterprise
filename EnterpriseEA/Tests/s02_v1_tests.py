"""S02 v1 design checks (docs/superpowers/specs/2026-10-03-s02-break-retest-v1-design.md).

Synthetic bars and a reference oracle; this is not MQL5 runtime proof.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import s02_oracle
import s02_v1_oracle as v1

ROOT = Path(__file__).resolve().parents[1]
H = 3600
DAY = 86400
MONDAY = 1791158400  # 2026-10-05 00:00 server time, a Monday


def bar(t, o, h, l, c):
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def flat_bars(start, count, step, price, spread=0.0005):
    return [bar(start + i * step, price, price + spread, price - spread, price) for i in range(count)]


class RiskLimitsTests(unittest.TestCase):
    def test_limits_follow_firm_floors(self):
        two = v1.risk_limits("FTMO_2_STEP")
        one = v1.risk_limits("FTMO_1_STEP")
        self.assertAlmostEqual(two["internal_daily"], 0.02)
        self.assertAlmostEqual(two["per_trade"], 0.005)
        self.assertAlmostEqual(two["total_open"], 0.02)
        self.assertAlmostEqual(two["currency_exposure"], 0.0125)
        self.assertAlmostEqual(two["internal_weekly"], 0.04)
        self.assertAlmostEqual(one["internal_daily"], 0.012)
        self.assertAlmostEqual(one["per_trade"], 0.003)
        self.assertAlmostEqual(one["currency_exposure"], 0.0075)
        self.assertAlmostEqual(one["internal_weekly"], 0.024)
        for limits in (one, two):
            self.assertLess(limits["internal_daily"], limits["firm_daily"])
            self.assertLess(limits["internal_weekly"], limits["firm_overall"])
            self.assertLessEqual(limits["total_open"], limits["internal_daily"])
        self.assertIsNone(v1.risk_limits("UNSELECTED"))

    def test_trade_risk_money_never_exceeds_cap_and_modifiers_only_reduce(self):
        limits = v1.risk_limits("FTMO_2_STEP")
        self.assertAlmostEqual(v1.trade_risk_money(limits, 105_000, 100_000, 1.0), 500.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 95_000, 100_000, 1.0), 475.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 100_000, 100_000, 0.5), 250.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 100_000, 100_000, 3.0), 500.0)

    def test_mql_formulas_match_oracle(self):
        src = (ROOT / "Risk/RiskLimitsProfile.mqh").read_text(encoding="utf-8")
        for token in ("MathMin(0.4*l.firm_daily_fraction,0.02)", "l.internal_daily_fraction/4.0",
                      "l.total_open_fraction=l.internal_daily_fraction", "2.5*l.per_trade_fraction",
                      "MathMin(2.0*l.internal_daily_fraction,0.4*l.firm_overall_fraction)",
                      "l.safety_buffer_fraction=l.per_trade_fraction", "MathMax(0.0,MathMin(1.0,modifier))",
                      "RISK_LIMITS_POLICY_UNSELECTED", "EEA_FtmoPolicyRates"):
            self.assertIn(token, src)


class LocationTests(unittest.TestCase):
    def test_tc_s02_01_two_independent_sources_qualify_one_does_not(self):
        points = [("PREV_DAY", "HIGH", 1.10000, 100), ("SWING", "HIGH", 1.10020, 200), ("SESSION", "HIGH", 1.12000, 300)]
        zones = v1.build_zones(points, tolerance=0.0005, max_width=0.0010)
        self.assertEqual(len(zones), 2)
        self.assertTrue(zones[0]["qualified"])
        self.assertEqual(zones[0]["sources"], "PREV_DAY+SWING")
        self.assertFalse(zones[1]["qualified"])
        self.assertEqual(zones[1]["reason"], "CONFLUENCE_INSUFFICIENT")

    def test_tc_s02_02_same_bar_counts_once(self):
        points = [("PREV_DAY", "HIGH", 1.10000, 500), ("SESSION", "HIGH", 1.10000, 500)]
        zone = v1.build_zones(points, tolerance=0.0005, max_width=0.0010)[0]
        self.assertEqual(zone["independent_sources"], 1)
        self.assertFalse(zone["qualified"])

    def test_tc_s02_03_atr_scaled_tolerance_is_symbol_independent(self):
        base = [("PREV_DAY", "LOW", 1.0, 1), ("SWING", "LOW", 1.0015, 2), ("SESSION", "LOW", 1.006, 3)]
        expected = None
        for scale, atr in ((1.0, 0.008), (2600.0, 0.008 * 2600.0), (60000.0, 0.008 * 60000.0)):
            points = [(s, side, p * scale, t) for s, side, p, t in base]
            zones = v1.build_zones(points, tolerance=0.25 * atr, max_width=0.5 * atr)
            shape = [(z["members"], z["qualified"], z["sources"]) for z in zones]
            expected = expected or shape
            self.assertEqual(shape, expected)

    def test_zone_wider_than_limit_is_rejected(self):
        points = [("PREV_DAY", "HIGH", 1.1000, 1), ("SWING", "HIGH", 1.1004, 2), ("SESSION", "HIGH", 1.1008, 3)]
        zone = v1.build_zones(points, tolerance=0.0005, max_width=0.0006)[0]
        self.assertEqual(zone["reason"], "ZONE_TOO_WIDE")

    def test_previous_day_week_and_session_windows(self):
        now = MONDAY + 2 * DAY + 10 * H  # Wednesday 10:00
        bars = flat_bars(MONDAY - 7 * DAY, 10 * 24, H, 1.1)
        bars[24 * 8 + 5]["high"] = 1.2   # Tuesday 05:00 -> previous day high
        bars[3]["low"] = 1.0             # previous week Monday 03:00 -> previous week low
        day = v1.levels_previous_day(bars, now)
        self.assertEqual(day[0][2:], (1.2, MONDAY + DAY + 5 * H))
        week = v1.levels_previous_week(bars, now)
        self.assertEqual(week[1][2:], (1.0, MONDAY - 7 * DAY + 3 * H))
        self.assertEqual(v1.week_start(now), MONDAY)
        # server is UTC+3; London 07-12 UTC is 10-15 server time. At 10:00 server the
        # session of today has not ended, so yesterday's window is used.
        session = v1.levels_session(bars, now, 3 * H, 7, 12)
        self.assertGreaterEqual(session[0][3], MONDAY + DAY + 10 * H)
        self.assertLess(session[0][3], MONDAY + DAY + 15 * H)

    def test_swings_must_be_confirmed_and_unbroken(self):
        bars = flat_bars(0, 20, H, 1.0)
        bars[10] = bar(10 * H, 1.0, 1.05, 0.999, 1.0)
        swings = v1.levels_swings(bars, wing=3, lookback=20)
        self.assertIn(("SWING", "HIGH", 1.05, 10 * H), swings)
        bars[15]["close"] = 1.06
        bars[15]["high"] = 1.06
        self.assertNotIn(("SWING", "HIGH", 1.05, 10 * H), v1.levels_swings(bars, wing=3, lookback=20))

    def test_mql_location_contract(self):
        src = (ROOT / "Market/ConfluenceLevels.mqh").read_text(encoding="utf-8")
        for token in ("EEA_BuildConfluenceZones", "CONFLUENCE_INSUFFICIENT", "ZONE_TOO_WIDE", "CONFLUENCE_ZONE",
                      "used_times[u]==points[order[n]].bar_time", "EEA_LevelsPreviousDay", "EEA_LevelsPreviousWeek",
                      "EEA_LevelsSession", "EEA_LevelsSwings", "(day+3)%7"):
            self.assertIn(token, src)
        self.assertNotIn("CopyRates", src)
        self.assertNotIn("OrderSend", src)


class HtfTests(unittest.TestCase):
    def _zigzag(self, rising: bool):
        bars, price = [], 1.0
        for leg in range(6):
            for k in range(5):
                step = 0.002 if (leg % 2 == 0) == rising else -0.002
                drift = 0.001 if rising else -0.001
                price += step + drift
                bars.append(bar(len(bars) * H, price, price + 0.0005, price - 0.0005, price))
        return bars

    def test_tc_s02_06_structure_and_counter_trend_modifier(self):
        self.assertEqual(v1.htf_structure(self._zigzag(True), 2), "UP")
        self.assertEqual(v1.htf_structure(self._zigzag(False), 2), "DOWN")
        self.assertEqual(v1.htf_structure(flat_bars(0, 30, H, 1.0), 2), "NEUTRAL")
        self.assertEqual(v1.htf_risk_modifier("UP", -1), 0.5)
        self.assertEqual(v1.htf_risk_modifier("DOWN", 1), 0.5)
        self.assertEqual(v1.htf_risk_modifier("UP", 1), 1.0)
        self.assertEqual(v1.htf_risk_modifier("NEUTRAL", -1), 1.0)
        src = (ROOT / "Market/ConfluenceLevels.mqh").read_text(encoding="utf-8")
        self.assertIn('if(highs[0]>highs[1] && lows[0]>lows[1]) return "UP";', src)


class ZoneEngineTests(unittest.TestCase):
    CONFIG = {"config_version": "s02-v1-scalp-0.1.0", "break_buffer_atr": 0.10, "acceptance_buffer_atr": 0.0,
              "retest_tolerance_atr": 0.15, "invalidation_buffer_atr": 0.10, "hold_buffer_atr": 0.0,
              "max_bars_to_accept": 2, "max_bars_to_retest": 12, "max_bars_for_reaction": 3,
              "candidate_ttl_bars": 2, "break_body_ratio": 0.5, "trigger_body_ratio": 0.4,
              "trigger_progress_atr": 0.05, "fail_on_close_inside_zone": True}

    def run_bars(self, bars, low=1.1000, high=1.1010, atr=0.0020):
        engine = s02_oracle.new_engine({"canonical_symbol": "EURUSD", "timeframe": "M5"}, self.CONFIG)
        events = [s02_oracle.process_zone(engine, dict(b, atr=atr), low, high, self.CONFIG) for b in bars]
        return engine, events

    def test_tc_s02_04_full_long_sequence_tracks_zone_and_retest_extreme(self):
        bars = [bar(300, 1.1008, 1.1045, 1.1006, 1.1040),   # strong break above zone high
                bar(600, 1.1040, 1.1050, 1.1030, 1.1045),   # acceptance
                bar(900, 1.1045, 1.1046, 1.1012, 1.1020),   # retest touches zone high + tol
                bar(1200, 1.1020, 1.1060, 1.1018, 1.1055)]  # trigger
        engine, events = self.run_bars(bars)
        self.assertEqual([e["state"] for e in events], ["DETECTED", "ARMED", "RETESTING", "TRIGGERED"])
        self.assertAlmostEqual(engine["invalidation_price"], 1.1000 - 0.1 * 0.0020)
        self.assertAlmostEqual(engine["candidate"]["retest_extreme"], 1.1012)
        self.assertEqual(engine["candidate"]["zone_high"], 1.1010)

    def test_tc_s02_05_close_back_inside_fails_acceptance_and_weak_break_is_ignored(self):
        _, events = self.run_bars([bar(300, 1.1008, 1.1045, 1.1006, 1.1040), bar(600, 1.1040, 1.1041, 1.1003, 1.1005)])
        self.assertEqual(events[-1]["reason"], "ACCEPTANCE_FAILED")
        weak = bar(300, 1.1030, 1.1060, 1.1000, 1.1036)  # closes beyond but body is 10% of range
        _, events = self.run_bars([weak])
        self.assertEqual(events[0]["state"], "IDLE")

    def test_zero_width_zone_with_v1_extras_off_is_the_prototype(self):
        legacy = dict(self.CONFIG, break_body_ratio=0.0, trigger_body_ratio=0.0,
                      trigger_progress_atr=0.0, fail_on_close_inside_zone=False)
        bars = [bar(300, 1.1008, 1.1045, 1.1006, 1.1040), bar(600, 1.1040, 1.1050, 1.1030, 1.1045)]
        a = s02_oracle.new_engine({"canonical_symbol": "X", "timeframe": "M5"}, legacy)
        b = s02_oracle.new_engine({"canonical_symbol": "X", "timeframe": "M5"}, legacy)
        for item in bars:
            ea = s02_oracle.process(a, dict(item, atr=0.002), 1.1010, legacy)
            eb = s02_oracle.process_zone(b, dict(item, atr=0.002), 1.1010, 1.1010, legacy)
            self.assertEqual((ea["state"], ea["reason"]), (eb["state"], eb["reason"]))

    def test_mql_engine_and_checkpoint_carry_zone(self):
        engine = (ROOT / "Setups/BreakRetest.mqh").read_text(encoding="utf-8")
        for token in ("bool EEA_S02ProcessClosedBarZone", "return EEA_S02ProcessClosedBarZone(e,b,key_level,key_level,c,ev);",
                      "EEA_S02BodyOk(b,1,c.break_body_ratio)", "\"ACCEPTANCE_FAILED\"", "e.retest_extreme=",
                      "void EEA_S02V1Config", "c.max_bars_to_retest=swing ? 10 : 12;", "c.fail_on_close_inside_zone=true;",
                      "e.invalidation_price=zone_low-c.invalidation_buffer_atr*b.atr;"):
            self.assertIn(token, engine)
        store = (ROOT / "Storage/StrategyCandidateStore.mqh").read_text(encoding="utf-8")
        for token in ('\\"zone_low\\":', '\\"retest_extreme\\":',
                      'engine.zone_low=zone_low_text=="" ? engine.key_level', "engine.zone_low>engine.zone_high"):
            self.assertIn(token, store)


class RuntimeWiringTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        self.scan = self.runtime.split("bool EEA_StrategyRuntimeCollectLevels", 1)[1].split("bool EEA_StrategyRuntimeLoadEngine", 1)[0]

    def test_two_profile_engines_per_symbol(self):
        init = self.runtime.split("bool EEA_StrategyCandidateRuntimeInitV1", 1)[1].split("string EEA_StrategyRuntimeCheckpointPath", 1)[0]
        slot = self.runtime.split("void EEA_StrategyRuntimeSlot", 1)[1].split("\n  }\n", 1)[0]
        for token in ('profile=(p%2==0 ? "SCALP" : "SWING")', 'timeframe=(p%2==0 ? "M5" : "H1")',
                      'setup=(p<2 ? "S02" : "S04")', "EEA_S02V1Config(config,profile)", "EEA_S04V1Config(config,profile)"):
            self.assertIn(token, slot)
        for token in ("EEA_StrategyRuntimeSlot(runtime,p,setup,profile,timeframe,runtime.profile_config[engine_count])",
                      "runtime.zone_mode=true", "count*stride>EEA_STRATEGY_RUNTIME_MAX_ENGINES", "runtime.symbol_count=engine_count"):
            self.assertIn(token, init)
        self.assertIn("return 2+(runtime.s04_mode==EEA_S04_MODE_OFF ? 0 : 2)+(runtime.s06_mode==EEA_S04_MODE_OFF ? 0 : 1);", self.runtime)

    def test_zone_scan_uses_profile_timeframes_closed_bars_and_qualified_zones_only(self):
        for token in ("swing ? PERIOD_H1 : PERIOD_M5", "swing ? PERIOD_H4 : PERIOD_H1",
                      "CopyRates(broker_symbol,entry_tf,1,", "CopyRates(broker_symbol,level_tf,1,",
                      "ArraySetAsSeries(level_rates,false)", "0.25*context_atr,0.5*context_atr,2",
                      "if(!zones[z].qualified) continue;", "EEA_S02ProcessClosedBarZone(engine,bar,zones[pick].low,zones[pick].high,config,event)",
                      "EEA_S02ProcessClosedBarZone(engine,bar,engine.zone_low,engine.zone_high,config,event)",
                      "engine.state==EEA_S02_IDLE || EEA_S02IsTerminal(engine.state)", "EEA_HtfStructure(bars,level_count,EEA_S02_SWING_WING)",
                      "EEA_LevelsSession(bars,level_count,now_server,offset,7,12,points,point_count)", "EEA_LevelsPreviousWeek"):
            self.assertIn(token, self.scan)
        self.assertNotIn("iATR", self.scan)
        self.assertNotIn("OrderSend", self.runtime)

    def test_atr_from_rates_matches_simple_true_range_average(self):
        atr = self.runtime.split("double EEA_StrategyRuntimeAtrFromRates", 1)[1].split("bool EEA_StrategyRuntimeBuildZones", 1)[0]
        self.assertIn("MathMax(rates[i].high,prev_close)-MathMin(rates[i].low,prev_close)", atr)
        self.assertIn("sum/period", atr)
        rates = [{"high": 1.0 + i * 0.01, "low": 0.99 + i * 0.01, "close": 0.995 + i * 0.01} for i in range(16)]
        trs = [max(r["high"], p["close"]) - min(r["low"], p["close"]) for p, r in zip(rates[1:], rates[2:])]
        self.assertGreater(sum(trs[-14:]) / 14, 0)

    def test_checkpoints_are_per_engine_identity(self):
        self.assertIn('"/current/strategy_"+runtime.engines[index].canonical_symbol+"_"', self.runtime)
        load = self.runtime.split("bool EEA_StrategyRuntimeLoadEngine", 1)[1].split("bool EEA_StrategyRuntimeSyncSymbols", 1)[0]
        self.assertIn("string version=runtime.engines[i].config_version;", load)
        self.assertIn("EEA_S02Init(runtime.engines[i],canonical,timeframe,version);", load)
        loader = self.runtime.split("bool EEA_StrategyRuntimeLoadCheckpoints", 1)[1].split("bool EEA_StrategyRuntimeWriteCheckpoints", 1)[0]
        self.assertIn("EEA_StrategyRuntimeLoadEngine(runtime,i,now_utc,max_age_seconds)", loader)

    def test_restart_replays_missed_bars_and_resets_after_long_gap(self):
        scan = self.runtime.split("bool EEA_StrategyRuntimeScanZoneEngine", 1)[1].split("bool EEA_StrategyRuntimeLoadEngine", 1)[0]
        for token in ("swing ? EEA_S02_SWING_CATCHUP_BARS : EEA_S02_SCALP_CATCHUP_BARS",
                      "while(first<last && (datetime)entry_rates[first].time<=engine.last_processed_bar_utc) first++;",
                      "gap_too_large", '"CHECKPOINT_GAP_RESET"', "for(int b=first;b<=last;b++)"):
            self.assertIn(token, scan)
        self.assertIn("#define EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS 604800", self.runtime)
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertNotIn("EEA_StrategyRuntimeLoadCheckpoints(g_strategy_runtime,TimeGMT(),3600)", shell)
        self.assertEqual(shell.count("EEA_StrategyRuntimeSyncSymbols(g_strategy_runtime,g_runtime.canonical_symbols"), 2)

    def test_sync_keeps_running_engines_by_identity(self):
        sync = self.runtime.split("bool EEA_StrategyRuntimeSyncSymbols", 1)[1].split("bool EEA_StrategyRuntimeOnTimer", 1)[0]
        for token in ("runtime.engines[j].canonical_symbol==canonical[i] && runtime.engines[j].timeframe==timeframe",
                      "next.engines[e]=runtime.engines[old]", "EEA_StrategyRuntimeLoadEngine(next,k,now_utc,max_age_seconds)",
                      "if(!runtime.enabled || !runtime.zone_mode) return true;"):
            self.assertIn(token, sync)

    def test_applied_selection_is_restored_for_the_same_account(self):
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        loader = store.split("bool EEA_RuntimeStoreLoadSymbolSelectionList", 1)[1].split("EEAStateLoadResult EEA_RuntimeStoreCheckSymbolSelection", 1)[0]
        for token in ("EEA_RuntimeStoreReadSymbolSelectionJson(path,config_version,account_fingerprint,json)",
                      '"\\"broker_server\\":\\""+EEA_JsonEscape(broker_server)', "if(canonical[k]==item) return false;"):
            self.assertIn(token, loader)
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1]
        self.assertLess(init.index("EEA_ReadRuntimeAccount"), init.index("EEA_RuntimeStoreLoadSymbolSelectionList"))
        self.assertLess(init.index("EEA_RuntimeStoreLoadSymbolSelectionList"), init.index("EEA_ObserverRuntimeAutoDiscover"))
        self.assertIn("EEA_ObserverRuntimeAutoDiscover(selection, brokers, discover_reasons, selection_count", init)

    def test_v1_candidates_use_the_derived_plan_and_the_same_risk_kernel(self):
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        loop = live.split("bool EEA_ControlledLiveOnTimer", 1)[1]
        self.assertNotIn("LIVE_S02_V1_RISK_PATH_PENDING", live)
        self.assertLess(loop.index("EEA_ControlledLiveResolveV1Plan"), loop.index("EEA_ControlledLiveBuildRiskContextPlan"))
        self.assertLess(loop.index("EEA_ControlledLiveBuildRiskContextPlan"), loop.index("EEA_EvaluateDryRunCandidate"))
        self.assertIn("last_candidate_id[EEA_STRATEGY_RUNTIME_MAX_ENGINES]", live)

    def test_v1_plan_is_structural_and_broker_derived(self):
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        plan = live.split("bool EEA_ControlledLiveResolveV1Plan", 1)[1].split("bool EEA_ControlledLiveBuildRiskContext(", 1)[0]
        for token in ("engine.candidate.retest_extreme", "MathMax(0.10*engine.signal_atr,1.5*spread_price)",
                      "EEA_S02V1StructuralTarget(points,point_count,direction,entry,min_target,target)",
                      '"NO_STRUCTURAL_TARGET"', "p.max_spread_points=2.0*median_spread", "p.max_spread_stop_fraction=0.25",
                      "p.minimum_net_rr=swing ? 2.0 : 1.5", "EEA_CommissionPerLotPerSide", "EEA_SwapMoneyPerLotPerNight",
                      "EEA_RiskLimitsForPolicy(policy.committed_policy,limits,reason)",
                      "p.base_risk_fraction=limits.per_trade_fraction*htf",
                      "p.portfolio_cap_money=limits.total_open_fraction*ledger.initial_capital",
                      "p.currency_cap_money=limits.currency_exposure_fraction*ledger.initial_capital",
                      '"LIVE_DAILY_RESET_SNAPSHOT_STALE"', '"LIVE_INITIAL_CAPITAL_UNKNOWN"'):
            self.assertIn(token, plan)
        for manual in ("config.stop_buffer_ticks", "config.target_r_multiple", "config.max_spread_points",
                       "config.minimum_net_rr", "config.base_risk_fraction"):
            self.assertNotIn(manual, plan)

    def test_risk_kernel_applies_costs_exposure_spread_and_margin(self):
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        body = live.split("bool EEA_ControlledLiveBuildRiskContextPlan", 1)[1].split("bool EEA_ControlledLiveOnTimer", 1)[0]
        for token in ('"SPREAD_TOO_WIDE_FOR_STOP"', "EEA_CurrencyExposureAllows(exposure,symbol.base_currency,symbol.profit_currency",
                      "portfolio.budget_money/(unit_quote.projected_loss+plan.cost_per_lot_money)",
                      '"MARGIN_LEVEL_TOO_LOW"', "final_quote.projected_loss+plan.cost_per_lot_money*final_volume",
                      "gain_final-plan.cost_per_lot_money*final_volume",
                      "MathMax(0.0,plan.portfolio_cap_money-existing_stress_loss)"):
            self.assertIn(token, body)
        self.assertNotIn("config.base_risk_fraction", body)
        self.assertNotIn("config.max_spread_points", body)

    def test_shell_defaults_to_v1_and_panel_shows_zone_detail(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("input bool   InpS02UsePrototype        = false;", shell)
        self.assertIn("EEA_StrategyCandidateRuntimeInitV1(g_strategy_runtime,canonical,count,InpStrategyRuntimeEnabled,(int)InpS04Mode,", shell)
        self.assertIn("view.setup_detail[row]", shell)
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn('ObjectSetString(chart_id,n+"_u",OBJPROP_TOOLTIP,detail=="" ? "\\n" : detail);', panel)


if __name__ == "__main__":
    unittest.main()
