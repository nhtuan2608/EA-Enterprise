"""G72 S07 (design specs/2026-10-09-s07-dmi-ema-design.md): the EA engine against the research rule
(research/long/g67_dmi_ema.py), the plan, the pyramiding gate, the Trade Manager profile and the wiring."""
import importlib.util
import math
import random
import sys
import unittest
from pathlib import Path

import s07_oracle as o

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "long"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end="\n  }\n"):
    return text.split(start, 1)[1].split(end, 1)[0]


def synthetic(n=900, seed=7, step=1800):
    rng = random.Random(seed)
    bars, p, t = [], 2000.0, 1_700_000_000
    for i in range(n):
        drift = 0.6 if (i // 150) % 2 == 0 else -0.5
        vol = 0.6 if (i // 40) % 3 == 0 else 2.5          # quiet stretches = compressions
        o_ = p
        c = p + drift * vol * 0.3 + rng.gauss(0, vol)
        h, l = max(o_, c) + abs(rng.gauss(0, vol * 0.5)), min(o_, c) - abs(rng.gauss(0, vol * 0.5))
        t += step + (172800 if i % 240 == 239 else 0)   # a weekend gap now and then
        bars.append({"time": t, "open": o_, "high": h, "low": l, "close": c})
        p = c
    return bars


class IndicatorTests(unittest.TestCase):
    def test_wilder_and_ema_formulas(self):
        bars = synthetic(60)
        ind = o.indicators(bars)
        # EMA seeded with the first close, alpha 2/(n+1)
        self.assertAlmostEqual(ind["e"][21][1], bars[0]["close"] + 2 / 22 * (bars[1]["close"] - bars[0]["close"]))
        # Wilder: the first ATR is the first bar's range, then RMA with alpha 1/14
        self.assertAlmostEqual(ind["atr"][0], bars[0]["high"] - bars[0]["low"])
        tr1 = max(bars[1]["high"] - bars[1]["low"], abs(bars[1]["high"] - bars[0]["close"]), abs(bars[1]["low"] - bars[0]["close"]))
        self.assertAlmostEqual(ind["atr"][1], ind["atr"][0] + (tr1 - ind["atr"][0]) / 14)
        for x in ind["adx"]:
            self.assertTrue(0.0 <= x <= 100.0)

    def test_mql_uses_the_same_formulas(self):
        src = read("Setups/DmiEmaCompression.mqh")
        for token in ("const double k=2.0/(period+1);", "out[0]=rates[0].close;", "const double a=1.0/EEA_S07_DMI_PERIOD;",
                      "const double pdm=(up>dn && up>0.0) ? up : 0.0;", "const double mdm=(dn>up && dn>0.0) ? dn : 0.0;",
                      "const double dx=(sum>1e-9 ? 100.0*MathAbs(pdi[i]-mdi[i])/sum : 0.0);", "atr[i]=tr_s;"):
            self.assertIn(token, src)


class SignalTests(unittest.TestCase):
    def test_signal_rules(self):
        bars = synthetic()
        ind = o.indicators(bars)
        hits = [(i, d) for i in range(300, len(bars)) for d in (o.signal_at(bars, ind, i, 8, 1),) if d]
        self.assertGreater(len(hits), 0)
        for i, d in hits:
            self.assertEqual(d, 1)                           # H4 side +1 allows buys only
            k = min(range(i - 8, i), key=lambda j: (ind["adx"][j], j))
            self.assertLessEqual(ind["adx"][k], 20.0)
            self.assertLessEqual(abs(ind["pdi"][k] - ind["mdi"][k]), 6.0)
            self.assertGreater(ind["adx"][i], ind["adx"][i - 1])
            self.assertGreater(bars[i]["close"], max(ind["e"][n][i] for n in (21, 55, 100, 200)))
        self.assertEqual([d for i in range(300, len(bars)) for d in (o.signal_at(bars, ind, i, 8, 0),) if d], [])

    def test_stop_anchor_skips_the_gap(self):
        bars = synthetic(40)
        i = 20
        bars[15]["time"] = bars[14]["time"] + 3 * 86400
        for k in range(15, 21):
            bars[k]["time"] = bars[15]["time"] + (k - 15) * 1800
        bars[13]["low"] = 1.0                                # before the gap: ignored
        self.assertGreater(o.stop_anchor(bars, i, 8, 1), 1.0)

    def test_plan_stop_range_and_target(self):
        self.assertIsNone(o.plan(100.0, 80.0, 1, 4.0))       # 20.4 > 4 ATR
        p = o.plan(100.0, 99.9, 1, 2.0)                      # too close: widened to 1 ATR
        self.assertAlmostEqual(p["risk"], 2.0)
        self.assertAlmostEqual(p["target"], 100.0 + 8 * 2.0)
        p = o.plan(100.0, 95.0, 1, 2.0)
        self.assertAlmostEqual(p["stop"], 95.0 - 0.2)

    @unittest.skipUnless(importlib.util.find_spec("numpy") and (RESEARCH / "data" / "m30v" / "XAUUSD.csv").exists(),
                         "research data or numpy not available")
    def test_matches_the_research_generator_on_xauusd_m30(self):
        sys.path.insert(0, str(RESEARCH))
        import g67_dmi_ema as g
        g.set_tf("M30")
        g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = 8, 20.0, 6.0, 10.0
        D = g.load("XAUUSD")
        research = {i for i, d in g.signals(D) if d == 1 and g.block_ok(D, i, d, "B6")}
        n = len(D["t"])
        lo, hi = n - 6000, n - 1
        bars = [{"time": int(D["t"][k]), "open": float(D["o"][k]), "high": float(D["h"][k]), "low": float(D["l"][k]),
                 "close": float(D["c"][k])} for k in range(n)]
        ind = o.indicators(bars)
        mine = {i for i in range(lo, hi) if o.signal_at(bars, ind, i, 8, int(D["h4_side"][i])) == 1}
        ref = {i for i in research if lo <= i < hi}
        self.assertGreater(len(ref), 10)
        self.assertEqual(mine, ref)
        for i in sorted(ref)[:50]:
            d = 1
            self.assertAlmostEqual(o.stop_anchor(bars, i, 8, d), float(min(D["l"][i - 8:i + 1])) if all(
                D["t"][k] - D["t"][k - 1] <= 21600 for k in range(i - 7, i + 1)) else o.stop_anchor(bars, i, 8, d))

        # G72 parity tool path: broker H4 bars (same server buckets) -> run() gives the same buys.
        h4 = []
        for b in bars:
            k = b["time"] - b["time"] % 14400
            if h4 and h4[-1]["time"] == k:
                h4[-1].update(high=max(h4[-1]["high"], b["high"]), low=min(h4[-1]["low"], b["low"]), close=b["close"])
            else:
                h4.append({"time": k, "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"]})
        sides = o.h4_sides(bars, h4)
        self.assertEqual([s for s, _ in sides[lo:hi]], [int(x) for x in D["h4_side"][lo:hi]])
        self.assertEqual({i for i, d in o.run(bars, h4, "S07", "M30", first=lo) if i < hi}, ref)


class ParityToolTests(unittest.TestCase):
    def test_s07_slots_in_signal_parity(self):
        text = read("research/g10/signal_parity.py")
        for slot in ("S07:M30", "S07A:M15", "S07A:H1", "S07A:H4", "S07S:H1"):
            self.assertIn(f'"{slot}"', text)
        self.assertIn("s07_oracle.run(", text)
        self.assertIn('r.get("profile") == "TREND"', text)
        self.assertIn("mt5.TIMEFRAME_M30", text)

    def test_sell_runs_only_near_the_h4_ema(self):
        bars = synthetic(1200, seed=11)
        h4 = [b for b in bars if b["time"] % 14400 == 0] or bars[::8]
        ind = o.indicators(bars)
        for i, d in o.run(bars, h4, "S07S", "H1"):
            self.assertEqual(d, -1)
            side, e = o.h4_sides(bars, h4)[i]
            self.assertTrue(o.sell_location(bars, i, 4, e, ind["atr"][i]))
        self.assertTrue(all(d == 1 for _, d in o.run(bars, h4, "S07", "M30")))


class PyramidTests(unittest.TestCase):
    def test_gate(self):
        self.assertEqual(o.add_allowed(1, True, True, 0, 7200), "S07A_ADD_ALLOWED")
        self.assertEqual(o.add_allowed(3, True, True, 0, 7200), "S07_MAX_OPEN_LEGS")
        self.assertEqual(o.add_allowed(1, False, True, 0, 7200), "S07A_NO_OPEN_BASE")
        self.assertEqual(o.add_allowed(2, True, True, 2, 7200), "S07A_MAX_ADDS")
        self.assertEqual(o.add_allowed(1, True, True, 0, 1800), "S07A_TOO_CLOSE_TO_PREVIOUS_LEG")
        self.assertEqual(o.add_allowed(1, True, False, 0, 7200), "S07A_BASE_NOT_IN_PROFIT")

    def test_mql_gate_and_record(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        gate = section(live, "bool EEA_S07EntryAllowed(")
        for token in ("EEA_S07OpenLegs(trades,canonical,direction)>=EEA_S07_MAX_OPEN_LEGS", '"S07_BASE_ALREADY_OPEN"',
                      "count>=EEA_S07_MAX_ADDS", "(long)TimeGMT()-last<EEA_S07_ADD_SPACING_SECONDS",
                      "direction*(now-base.entry_price)<=0.0"):
            self.assertIn(token, gate)
        on_timer = section(live, "bool EEA_ControlledLiveOnTimer(", "\n  }\n\n")
        self.assertIn("if(EEA_StrategyRuntimeIsS07(strategy.setup[i]))", on_timer)
        self.assertIn("EEA_S07RecordAdd(trades,observer.root,", on_timer)
        src = read("Setups/DmiEmaCompression.mqh")
        for token in ("#define EEA_S07_MAX_ADDS 2", "#define EEA_S07_MAX_OPEN_LEGS 3", "#define EEA_S07_ADD_SPACING_SECONDS 3600",
                      "#define EEA_S07_ADX_LOW 20.0", "#define EEA_S07_DI_GAP 6.0", "#define EEA_S07_ADX_RISE 10.0",
                      "#define EEA_S07_TARGET_R 8.0", "#define EEA_S07_TRAIL_SWITCH_R 3.0", "#define EEA_S07_STOP_MAX_ATR 4.0"):
            self.assertIn(token, src)


class PlanAndManagementTests(unittest.TestCase):
    def test_plan_branch(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        plan = section(live, "bool EEA_ControlledLiveResolveV1Plan(")
        for token in ("buffer=s07 ? EEA_S07_STOP_BUFFER_ATR*engine.signal_atr", '"S07_STOP_TOO_WIDE"',
                      "target=entry+direction*EEA_S07_TARGET_R*risk_distance;",
                      "p.max_correlated_trades=MathMax(p.max_correlated_trades,EEA_S07_MAX_OPEN_LEGS);"):
            self.assertIn(token, plan)

    def test_trend_profile_exit(self):
        tm = read("Runtime/TradeManagerRuntime.mqh")
        prof = section(tm, "void EEA_TradeProfileFor(")
        self.assertIn('if(profile=="TREND")', prof)
        self.assertIn("p.be_at_r=1.0e9; p.partial_at_r=1.0e9;", prof)
        obs = section(tm, "string EEA_TradeManagerObserveTrendBars(")
        self.assertIn("const double ema=(wide ? e100[b] : e55[b]);", obs)
        self.assertIn("t.bars>=EEA_S07HoldBars(t.timeframe)", obs)
        self.assertTrue(o.trend_exit(1, 99.0, 100.0, 98.0, 1.0))
        self.assertFalse(o.trend_exit(1, 99.0, 100.0, 98.0, 3.5))   # past 3R the EMA100 rules

    def test_timeframes(self):
        pend = read("Runtime/PendingOrderRuntime.mqh")
        fn = section(pend, "ENUM_TIMEFRAMES EEA_PendingTimeframe(")
        for tf in ("PERIOD_M15", "PERIOD_M30", "PERIOD_H4", "PERIOD_H1"):
            self.assertIn(tf, fn)


class WiringTests(unittest.TestCase):
    def test_inputs_default_shadow_and_only_s07_live(self):
        shell = read("EnterpriseEA.mq5")
        for token in ("input EEA_S07ModeInput InpS07Mode       = S07_SHADOW;", "input EEA_S07ModeInput InpS07AddMode    = S07_SHADOW;",
                      "input EEA_S07SellModeInput InpS07SellMode = S07S_SHADOW;", 'input string InpS07Symbols              = "XAUUSD";',
                      "input EEA_S04ModeInput InpS04Mode       = S04_SHADOW;", "input EEA_S06BModeInput InpS06BMode     = S06B_SHADOW;",
                      "(int)InpS07SellMode,InpS07Symbols,(int)InpS07EarlyMode,",
                      "input EEA_S07EarlyModeInput InpS07EarlyMode = S07E_LIVE;",
                      "input EEA_S07ReentryModeInput InpS07ReentryMode = S07R_SHADOW;"):
            self.assertIn(token, shell)

    def test_slots_and_modes(self):
        rt = read("Runtime/StrategyCandidateRuntime.mqh")
        slot = section(rt, "void EEA_StrategyRuntimeSlot(")
        for token in ('setup=(j==0 ? "S07" : j==4 ? "S07S" : j==5 ? "S07E" : j==6 ? "S07R" : "S07A");',
                      'timeframe=(j==0 || j==5 || j==6 ? "M30" : j==1 ? "M15" : j==3 ? "H4" : "H1");',
                      'profile="TREND";'):
            self.assertIn(token, slot)
        self.assertIn('setup=="S07S" ? MathMin(runtime.s07_sell_mode,EEA_S04_MODE_SHADOW)', rt)   # never LIVE
        self.assertIn("if(EEA_StrategyRuntimeIsS07(setup)) return EEA_StrategyRuntimeSymbolListed(runtime.s07_symbols,canonical);", rt)
        scan = section(rt, "bool EEA_StrategyRuntimeScanS07Engine(", "\n  }\n\n")
        self.assertIn("EEA_S07SellLocation(rates,b,window", scan)
        self.assertIn("else if(d!=1) d=0;", scan)

    def test_s07e_is_wired(self):
        rt = read("Runtime/StrategyCandidateRuntime.mqh")
        self.assertIn("#define EEA_S07_SLOTS 7", rt)
        self.assertIn('setup=="S07E" ? MathMin(runtime.s07_early_mode,runtime.s07_mode)', rt)   # G87: capped by S07
        self.assertIn('if(setup=="S07E" && runtime.s07_early_mode==EEA_S04_MODE_OFF) return false;', rt)
        self.assertIn('runtime.setup[index]=="S07E" ? "_s07e"', rt)
        self.assertIn('if(runtime.setup[index]=="S07E") return EEA_StrategyRuntimeScanS07EarlyEngine(', rt)
        scan = section(rt, "bool EEA_StrategyRuntimeScanS07EarlyEngine(", "\n  }\n\n")
        for token in ("CopyRates(broker_symbol,PERIOD_M15,1,", "EEA_S07ProvisionalSignal(rates,q,window", "if(d!=1) d=0;",
                      "(long)engine.breakout_bar_utc-(long)engine.breakout_bar_utc%1800==bucket) d=0;"):
            self.assertIn(token, scan)
        self.assertIn('setup=="S07E" ? "/logs/s07e_shadow.jsonl"', read("Integration/ControlledLiveRuntime.mqh"))

    def test_provisional_signal_mirrors_mql(self):
        mql = section(read("Setups/DmiEmaCompression.mqh"), "int EEA_S07ProvisionalSignal(")
        for token in ("const double pd0=pdi[q]*atr[q]/100.0, md0=mdi[q]*atr[q]/100.0;", "const double ts=atr[q]+a*(tr-atr[q]);",
                      "const double adx_p=adx[q]+a*(dx-adx[q]);", "int a0=q+1-window;", "int k=q-window+1;"):
            self.assertIn(token, mql)


class G87Tests(unittest.TestCase):
    def test_base_slot_shared_first_trigger_enters(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn('bool EEA_S07IsBaseSetup(const string setup) { return setup=="S07" || setup=="S07E" || setup=="S07R"; }',
                      read("Setups/DmiEmaCompression.mqh"))
        gate = section(live, "bool EEA_S07EntryAllowed(")
        self.assertIn("if(EEA_S07IsBaseSetup(setup))", gate)
        self.assertIn('reason="S07_BASE_ALREADY_OPEN"', gate)
        self.assertIn("EEA_S07IsBaseSetup(trades.items[i].intent.setup_id)) return i;", live)
        self.assertIn('(strategy.setup[index]=="S07E" || strategy.setup[index]=="S07R") ? "M15" : engine.timeframe', live)
        self.assertIn("EEA_S07IsBaseSetup(setup) ? 0 : 1", read("Integration/SetupArbitration.mqh"))

    def test_risk_weights(self):
        shell = read("EnterpriseEA.mq5")
        for token in ("InpS07UnorderedRiskWeight  = 0.67", "InpRiskWeightS07A          = 0.67", "InpS07AdxExit              = true",
                      "g_risk_weight_s07a=InpRiskWeightS07A;", "g_s07_unordered_weight=InpS07UnorderedRiskWeight;",
                      "g_s07_adx_exit=InpS07AdxExit;"):
            self.assertIn(token, shell)
        self.assertIn('else if(setup=="S07A") w=g_risk_weight_s07a;', read("Risk/RiskLimitsProfile.mqh"))
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn('StringFind(engine.candidate.reason_code,"_RB3")<0', live)
        rt = read("Runtime/StrategyCandidateRuntime.mqh")
        self.assertIn("EEA_S07MarkOrdered(engine,d==1 ? (e21[b]>e55[b] && e55[b]>e100[b] && rates[b].close>e21[b])", rt)
        self.assertIn("EEA_S07MarkOrdered(engine,x21>x55 && x55>x100 && sub[s].close>x21);", rt)

    def test_adx_exhaustion_exit_on_base_legs(self):
        tm = section(read("Runtime/TradeManagerRuntime.mqh"), "string EEA_TradeManagerObserveTrendBars(")
        self.assertIn("const bool adx_exit=(g_s07_adx_exit && EEA_S07IsBaseSetup(t.intent.setup_id));", tm)
        self.assertIn("adx[b-1]>=EEA_S07_ADX_EXHAUSTION && adx[b]<adx[b-1]", tm)
        self.assertIn('"S07_ADX_EXHAUSTION_EXIT"', tm)
        self.assertIn("#define EEA_S07_ADX_EXHAUSTION 50.0", read("Setups/DmiEmaCompression.mqh"))

    def test_context_and_reentry(self):
        tm = read("Runtime/TradeManagerRuntime.mqh")
        self.assertIn("EEA_S07ContextRecordClose(t.intent.canonical_symbol,t.direction,t.opened_at_utc,t.exited_at_utc,cause,", tm)
        self.assertIn("t.mfe_r>=EEA_S07_TARGET_R-0.05", tm)
        rt = read("Runtime/StrategyCandidateRuntime.mqh")
        scan = section(rt, "bool EEA_StrategyRuntimeScanS07ReentryEngine(", "\n  }\n\n")
        for token in ('why="S07R_ALREADY_USED"', 'why="S07R_BASE_HIT_TARGET"',
                      "close_utc<=c.closed_utc || close_utc>c.closed_utc+EEA_S07_REENTRY_SECONDS",
                      "(sub[s].close>hi && pp>mm)", "h4_side==dd", "EEA_S07ContextMarkUsed(engine.canonical_symbol);"):
            self.assertIn(token, scan)
        self.assertIn('setup=="S07R" ? MathMin(runtime.s07_reentry_mode,runtime.s07_mode)', rt)
        self.assertIn("#define EEA_S07_REENTRY_SECONDS 7200", read("Setups/DmiEmaCompression.mqh"))
        self.assertIn('setup=="S07R" ? "/logs/s07r_shadow.jsonl"', read("Integration/ControlledLiveRuntime.mqh"))


class EarlyTests(unittest.TestCase):
    def test_full_bar_equals_signal_at(self):
        bars = synthetic(1500, seed=5)
        ind = o.indicators(bars)
        n = 0
        for i in range(300, len(bars)):
            for side in (1, -1):
                b = bars[i]
                d, _, anchor = o.provisional_signal(bars, ind, i - 1, 8, b["time"], b["open"], b["high"], b["low"], b["close"], side)
                self.assertEqual(d, o.signal_at(bars, ind, i, 8, side))
                if d:
                    n += 1
                    self.assertAlmostEqual(anchor, o.stop_anchor(bars, i, 8, d))
        self.assertGreater(n, 3)

    @unittest.skipUnless(importlib.util.find_spec("numpy") and (RESEARCH / "data" / "m15v" / "XAUUSD.csv").exists(),
                         "research data or numpy not available")
    def test_matches_research_g73_v1_triggers(self):
        sys.path.insert(0, str(RESEARCH))
        import g73_early as m
        ctx = m.context("M30", "M15")
        P, S = ctx["P"], ctx["S"]
        trs, _ = m.v1_trades(ctx)
        early = [t for t in trs if not t["at_close"]][-150:]
        self.assertGreater(len(early), 50)
        lo = min(t["sig"] for t in early) - 1600
        bars = [{"time": int(P["t"][k]), "open": float(P["o"][k]), "high": float(P["h"][k]), "low": float(P["l"][k]),
                 "close": float(P["c"][k])} for k in range(lo, len(P["t"]))]
        ind = o.indicators(bars)
        for t in early:
            i = t["sig"]
            f = int(ctx["first"][i])
            k = f + t["sub_k"]
            fh, fl = float(S["h"][f:k + 1].max()), float(S["l"][f:k + 1].min())
            d, atr_p, anchor = o.provisional_signal(bars, ind, i - 1 - lo, 8, int(P["t"][i]), float(S["o"][f]), fh, fl,
                                                    float(S["c"][k]), int(P["h4_side"][i]))
            self.assertEqual(d, t["d"])
            self.assertAlmostEqual(atr_p * 1.0, t["risk"] / t["dist_atr"], delta=0.02 * atr_p)


if __name__ == "__main__":
    unittest.main()
