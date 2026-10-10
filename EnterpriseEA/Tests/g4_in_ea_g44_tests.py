"""G44: G4 of the G43 research in the EA — risk weights by setup, T2 momentum filter, T2 add at +1R."""
import bisect
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import t2_oracle as t2  # noqa: E402

LONG = ROOT / "research" / "long"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def bar(o, h, l, c, t=0):
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


class MomentumOracleTests(unittest.TestCase):
    def test_momentum_close(self):
        self.assertTrue(t2.momentum_close(bar(100, 110, 99, 108), 10.0, 1))    # range 11 >= 10, close in top quarter
        self.assertFalse(t2.momentum_close(bar(100, 110, 99, 105), 10.0, 1))   # close in the middle
        self.assertFalse(t2.momentum_close(bar(100, 105, 99, 105), 10.0, 1))   # range 6 < ATR 10
        self.assertTrue(t2.momentum_close(bar(108, 110, 99, 100), 10.0, -1))
        self.assertFalse(t2.momentum_close(bar(100, 110, 99, 108), 10.0, -1))
        self.assertFalse(t2.momentum_close(bar(100, 100, 100, 100), 0.0, 1))

    def test_filter_only_removes_signals(self):
        h4 = [bar(100 + 0.1 * k, 101 + 0.1 * k, 99 + 0.1 * k, 100.05 + 0.1 * k, 1_700_006_400 + k * 14400) for k in range(140)]
        daily = [{"time": 1_600_000_000 - 1_600_000_000 % 86400 + d * 86400, "close": 100 + d * 0.1} for d in range(1300)]
        plain = {(c["i"], c["direction"]) for c in t2.run(h4, daily)}
        filtered = {(c["i"], c["direction"]) for c in t2.run(h4, daily, momentum=True)}
        self.assertTrue(filtered <= plain)


@unittest.skipUnless((LONG / "data" / "bars_XAUUSD_H4.csv").exists(), "long-history data not present")
class MomentumResearchParityTests(unittest.TestCase):
    """The EA mirror with the filter keeps the same signals as the G43 research (sig_t2 + momentum close)."""

    @classmethod
    def setUpClass(cls):
        os.environ["EEA_RESEARCH_DATA"] = str(LONG / "data")
        sys.path.insert(0, str(LONG))
        sys.path.insert(0, str(ROOT / "research" / "g10"))
        import context
        context.DATA = LONG / "data"
        import discovery as dv
        import g43_reversal as rv
        cls.dv, cls.context, cls.rv = dv, context, rv

    def check(self, symbol, start, end):
        dv, context, rv = self.dv, self.context, self.rv
        B = dv.load(symbol, "H4")
        A = rv.arrays(B["bars"])
        p = {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}
        research = {(i, d) for i, d, _ in dv.sig_t2(B, p) if start <= B["t"][i] < end and rv.has_pattern("nến đà", A, i, d)}
        h4 = context.load_bars(symbol, "H4")
        daily = context.load_bars(symbol, "D1")
        lo = bisect.bisect_left([b["time"] for b in h4], start)
        hi = bisect.bisect_left([b["time"] for b in h4], end)
        mine = {(c["i"], c["direction"]) for c in t2.run(h4[:hi], daily, first=max(lo, 75), momentum=True)}
        union = research | mine
        self.assertGreater(len(research), 10)
        self.assertGreaterEqual(len(research & mine) / len(union), 0.95,
                                f"{symbol}: {len(research - mine)} research-only, {len(mine - research)} EA-only")

    def test_xauusd(self):
        self.check("XAUUSD", 1_609_459_200, 1_704_067_200)     # 2021-2023

    def test_eurusd(self):
        self.check("EURUSD", 1_420_070_400, 1_514_764_800)     # 2015-2017


class SourceTests(unittest.TestCase):
    def test_engine_filter(self):
        src = read("Setups/DonchianTrend.mqh")
        self.assertIn("#define EEA_T2_MOMENTUM_QUARTER 0.25", src)
        self.assertIn("range<atr", src)
        self.assertIn("const int momentum_mask=3", src)
        self.assertIn('"T2_NO_MOMENTUM_CLOSE"', src)
        scan = read("Runtime/StrategyCandidateRuntime.mqh")
        self.assertIn("if(runtime.t2_momentum_filter)", scan)
        self.assertIn("EEA_StrategyRuntimeAtrFromRates(rates,b-1,EEA_STRATEGY_RUNTIME_ATR_PERIOD)", scan)
        self.assertIn("runtime.t2_momentum_filter=false;", scan)

    def test_risk_weights_only_lower_the_risk(self):
        src = read("Risk/RiskLimitsProfile.mqh")
        self.assertIn("return MathMax(0.0,MathMin(1.0,w));", src)
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn("double weight=EEA_SetupRiskWeight(strategy.setup[index]);", live)
        self.assertIn("weight*=MathMax(0.0,MathMin(1.0,g_s07_unordered_weight));", live)   # G87: only lowers
        self.assertIn("p.base_risk_fraction=limits.per_trade_fraction*htf*weight;", live)
        self.assertIn("MathMin(limits.per_trade_fraction*weight*ledger.initial_capital,loss_room)", live)
        add = read("Integration/S06BPyramidRuntime.mqh")
        self.assertIn("const double weight=EEA_SetupRiskWeight(setup);", add)
        self.assertIn("p.base_risk_fraction=limits.per_trade_fraction*weight;", add)

    def test_inputs_and_defaults(self):
        shell = read("EnterpriseEA.mq5")
        for text in ("InpT2PyramidLive             = false", "InpT2MomentumFilter          = true",
                     "InpRiskWeightS04           = 0.65", "InpRiskWeightS06B          = 1.00",
                     "InpRiskWeightT2            = 0.34", "g_t2_pyramid_live=InpT2PyramidLive;",
                     "g_risk_weight_s04=InpRiskWeightS04;", "g_risk_weight_s06b=InpRiskWeightS06B;",
                     "g_risk_weight_t2=InpRiskWeightT2;", "g_strategy_runtime.t2_momentum_filter=InpT2MomentumFilter;"):
            self.assertIn(text, shell)

    def test_weights_keep_the_research_ratios(self):
        # mean / variance weights of G43 (S04 0.98, S06B 1.51, T2 0.51) scaled so the largest is 1
        for got, raw in ((0.65, 0.98), (1.00, 1.51), (0.34, 0.51)):
            self.assertAlmostEqual(got, raw / 1.51, delta=0.01)

    def test_t2_add(self):
        src = read("Integration/S06BPyramidRuntime.mqh")
        self.assertIn("#define EEA_T2_ADD_AT_R 1.0", src)
        self.assertIn("bool   g_t2_pyramid_live=false;", src)
        self.assertIn('const bool t2=(t.intent.setup_id=="T2" && g_t2_pyramid_live);', src)
        self.assertIn("(s06 && !t.be_done)", src)                       # break-even only required for S06B
        self.assertIn("p.invalidation_price=(t2 ? t.entry_price : position.sl)+t.direction*tick;", src)
        self.assertIn('const string profile=(t2 ? "POSITION" : "SWING");', src)
        self.assertIn("EEA_S06BEngineIndex(strategy,t.intent.canonical_symbol,setup)", src)
        self.assertIn("profile,t.timeframe,0.0,0.0,authorization_path,manage_reason", src)

    def test_virtual_add_for_t2(self):
        src = (ROOT / "research" / "g10" / "candidates_eval.py").read_text(encoding="utf-8")
        self.assertIn("T2_ADD_AT = 1.0", src)
        self.assertIn("res_add = pyramid.run(ctx, t, T2_RULE, T2_ADD_AT)", src)
        self.assertIn('r_add=res_add["r"]', src)


if __name__ == "__main__":
    unittest.main()
