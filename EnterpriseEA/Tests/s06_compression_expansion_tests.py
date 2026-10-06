"""S06 Compression Expansion v1: oracle vs the G10 research prototype, plan, and wiring."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research" / "g10"))

import s06_oracle as s06  # noqa: E402

CHOSEN = {"box": 12, "max_box_atr": 3.0, "contraction": 0.85, "mode": "confirm", "sl": "far"}


def atr_at(bars, last, period=14):
    if last < period:
        return 0.0
    s = 0.0
    for i in range(last - period + 1, last + 1):
        pc = bars[i - 1]["close"]
        s += max(bars[i]["high"], pc) - min(bars[i]["low"], pc)
    return s / period


def synthetic_bars(seed, n=4000):
    """Random walk with quiet stretches followed by impulses, so compressions occur."""
    rnd = random.Random(seed)
    bars, price, t = [], 1.1000, 1_700_000_000
    vol = 0.0010
    for i in range(n):
        phase = (i // 60) % 3
        vol = 0.0003 if phase == 1 else 0.0012 if phase == 2 and i % 60 < 6 else 0.0009
        o = price
        drift = rnd.gauss(0, vol)
        if phase == 2 and i % 60 < 3:
            drift = (1 if (i // 180) % 2 else -1) * abs(drift) * 2.5
        c = o + drift
        h = max(o, c) + abs(rnd.gauss(0, vol * 0.4))
        lo = min(o, c) - abs(rnd.gauss(0, vol * 0.4))
        bars.append({"time": t + 3600 * i, "open": o, "high": h, "low": lo, "close": c, "spread": 10})
        price = c
    for i in range(len(bars)):
        bars[i]["atr"] = atr_at(bars, i)
    return bars


class OracleMatchesResearchTests(unittest.TestCase):
    def test_same_candidates_as_research_prototype(self):
        import setups
        total = 0
        for seed in (1, 2, 3):
            bars = synthetic_bars(seed)
            ctx = {"entry": bars, "from_server": bars[s06.WARM]["time"], "bar_level": [0] * len(bars),
                   "levels": {0: {"points": [], "structure": "NEUTRAL"}}}
            research = setups.s06(ctx, CHOSEN)
            mine = s06.run(bars)
            self.assertEqual([(c["i"], c["direction"]) for c in research], [(c["i"], c["direction"]) for c in mine])
            for r, m in zip(research, mine):
                self.assertAlmostEqual(r["extreme"], m["anchor"], places=10)
                self.assertAlmostEqual(r["zone_low"], m["zone_low"], places=10)
                self.assertAlmostEqual(r["zone_high"], m["zone_high"], places=10)
                self.assertAlmostEqual(r["signal_atr"], m["signal_atr"], places=10)
            total += len(mine)
        self.assertGreater(total, 10)


class EngineTests(unittest.TestCase):
    def bar(self, o, h, lo, c, atr=1.0, t=0):
        return {"time": t, "open": o, "high": h, "low": lo, "close": c, "atr": atr}

    def test_release_needs_compression(self):
        e = s06.Engine()
        # Box 4 ATR wide: not compressed even with a strong close above it.
        self.assertIsNone(e.step(self.bar(100, 106, 100, 105.5), 100, 104, 1.0, 2.0))
        self.assertEqual(e.state, "IDLE")
        # Volatility not contracted (1.0 > 0.85 x 1.1).
        self.assertIsNone(e.step(self.bar(100, 104, 100, 103.5), 100, 102, 1.0, 1.1))
        self.assertEqual(e.state, "IDLE")

    def test_release_then_confirmation_triggers_with_far_edge_stop(self):
        e = s06.Engine()
        e.step(self.bar(101, 103.6, 101, 103.5), 100, 102.5, 1.0, 2.0)
        self.assertEqual(e.state, "RELEASED")
        c = e.step(self.bar(103.5, 104, 103, 103.8, atr=1.2), 0, 0, 0, 0)
        self.assertEqual(e.state, "TRIGGERED")
        self.assertEqual((c["direction"], c["anchor"], c["signal_atr"]), (1, 100, 1.2))

    def test_no_confirmation_expires_and_next_bar_is_scanned(self):
        e = s06.Engine()
        e.step(self.bar(101, 103.6, 101, 103.5), 100, 102.5, 1.0, 2.0)
        self.assertIsNone(e.step(self.bar(103.5, 103.6, 102, 102.2), 0, 0, 0, 0))
        self.assertEqual(e.state, "EXPIRED")
        e.step(self.bar(102, 102.2, 98.4, 98.5), 99.5, 102.4, 1.0, 2.0)
        self.assertEqual((e.state, e.direction), ("RELEASED", -1))

    def test_weak_release_is_ignored(self):
        e = s06.Engine()
        # Range below 1 ATR.
        self.assertIsNone(e.step(self.bar(102.4, 103.2, 102.4, 103.1), 100, 102.5, 1.0, 2.0))
        # Close beyond the box by less than 0.10 ATR.
        self.assertIsNone(e.step(self.bar(101, 102.6, 101, 102.55), 100, 102.5, 1.0, 2.0))
        # Body under half the range.
        self.assertIsNone(e.step(self.bar(102.0, 104.0, 101.5, 102.7), 100, 102.5, 1.0, 2.0))
        self.assertEqual(e.state, "IDLE")

    def test_plan_is_fixed_three_r(self):
        p = s06.plan({"direction": -1, "anchor": 110.0, "signal_atr": 2.0}, entry=105.0, spread=0.1)
        self.assertAlmostEqual(p["stop"], 110.2)
        self.assertAlmostEqual(p["risk"], 5.2)
        self.assertAlmostEqual(p["target"], 105.0 - 15.6)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.engine = (ROOT / "Setups/CompressionExpansion.mqh").read_text(encoding="utf-8")
        self.runtime = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        self.live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_constants_match_oracle(self):
        for name, value in (("BOX_BARS", "12"), ("MAX_BOX_ATR", "3.0"), ("CONTRACTION", "0.85"),
                            ("CONTRACTION_LOOKBACK", "48"), ("RELEASE_BUFFER_ATR", "0.10"),
                            ("RELEASE_BODY_RATIO", "0.50"), ("RELEASE_MIN_RANGE_ATR", "1.0"), ("TARGET_R", "3.0")):
            self.assertIn(f"#define EEA_S06_{name} {value}", self.engine)
            self.assertEqual(float(getattr(s06, name)), float(value))

    def test_one_swing_engine_per_symbol_when_enabled(self):
        self.assertIn('profile="SWING"; timeframe="H1";', self.runtime)
        self.assertIn('{ setup="S06"; EEA_S06V1Config(config); }', self.runtime)
        self.assertIn("(runtime.s06_mode==EEA_S04_MODE_OFF ? 0 : 1)", self.runtime)
        self.assertIn('runtime.setup[index]=="S06" ? "_s06"', self.runtime)

    def test_runtime_feeds_box_and_contraction_atrs(self):
        self.assertIn("EEA_STRATEGY_RUNTIME_ATR_PERIOD+(s06 ? EEA_S06_CONTRACTION_LOOKBACK : 0)", self.runtime)
        step = self.runtime.split("bool EEA_StrategyRuntimeS06Step", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("EEA_StrategyRuntimeAtrFromRates(rates,b-1,", step)
        self.assertIn("EEA_StrategyRuntimeAtrFromRates(rates,b-EEA_S06_CONTRACTION_LOOKBACK,", step)
        self.assertIn("const int box_bars=EEA_S06BoxBars(runtime.profile_config[index]);", step)
        self.assertIn("for(int k=b-box_bars+1;k<b;k++)", step)

    def test_live_plan_market_entry_htf_aligned_fixed_target(self):
        self.assertIn('reason="ENTRY_AUTO_MARKET_S06_CONFIRMED";', self.live)
        self.assertIn('reason="ENTRY_AUTO_S06_BACK_INSIDE_BOX"', self.live)
        self.assertIn('if(strategy.setup[index]=="S06" && strategy.htf_risk_modifier[index]<1.0)', self.live)
        self.assertIn('{ reason="S06_COUNTER_HTF"; return false; }', self.live)
        self.assertIn("target=entry+direction*EEA_S06_TARGET_R*risk_distance;", self.live)
        self.assertIn('setup=="S06" ? "/logs/s06_shadow.jsonl"', self.live)

    def test_input_and_dry_run_gate(self):
        self.assertIn("input EEA_S06ModeInput InpS06Mode       = S06_SHADOW;", self.shell)
        self.assertIn("(int)InpS02Mode,(int)InpS06Mode,(int)InpS06BMode,(int)InpScalpMode,", self.shell)
        gate = (ROOT / "Integration/DryRunCandidateGate.mqh").read_text(encoding="utf-8")
        self.assertIn('i.candidate.setup_id!="S06"', gate)

    def test_engine_never_trades(self):
        for forbidden in ("OrderSend", "CTrade", "EEA_ExecutionSubmit"):
            self.assertNotIn(forbidden, self.engine)


if __name__ == "__main__":
    unittest.main()
