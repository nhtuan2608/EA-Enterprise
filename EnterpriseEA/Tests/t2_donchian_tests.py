"""G38 T2 (H4 Donchian on the D1 EMA200 side, SHADOW): oracle, research parity and EA wiring."""
import bisect
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import t2_oracle as t2  # noqa: E402

LONG = ROOT / "research" / "long"


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


def bars(closes, t0=1_700_006_400, step=14400, width=1.0):
    out = []
    for k, c in enumerate(closes):
        out.append({"time": t0 + k * step, "open": c, "high": c + width, "low": c - width, "close": c})
    return out


class OracleTests(unittest.TestCase):
    def daily(self, n, rising=True):
        return [{"time": 1_600_000_000 - 1_600_000_000 % 86400 + d * 86400, "close": 100 + (d if rising else -d) * 0.1}
                for d in range(n)]

    def test_side_needs_two_hundred_days(self):
        d = self.daily(150)
        self.assertEqual(t2.daily_side(d, d[-1]["time"] + 86400), 0)
        d = self.daily(400)
        self.assertEqual(t2.daily_side(d, d[-1]["time"] + 86400), 1)
        d = self.daily(400, rising=False)
        self.assertEqual(t2.daily_side(d, d[-1]["time"] + 86400), -1)

    def test_side_ignores_the_current_day(self):
        d = self.daily(400)
        today = d[-1]["time"]
        rigged = d[:-1] + [dict(d[-1], close=0.0)]             # today's (unfinished) bar crashes
        self.assertEqual(t2.daily_side(rigged, today + 3600), 1)

    def test_breakout_only_with_the_d1_side(self):
        self.assertEqual(t2.direction(105, 90, 100, 1), 1)
        self.assertEqual(t2.direction(105, 90, 100, -1), 0)     # against the D1 side
        self.assertEqual(t2.direction(85, 90, 100, -1), -1)
        self.assertEqual(t2.direction(95, 90, 100, 1), 0)       # inside the channel
        self.assertEqual(t2.direction(105, 90, 100, 0), 0)      # side unknown

    def test_channel_excludes_the_signal_bar(self):
        h4 = bars([100.0] * 70 + [100.5])                       # +0.5 within the previous highs (101)
        daily = self.daily(400)
        self.assertEqual(t2.run(h4, daily, first=70), [])
        h4 = bars([100.0] * 70 + [101.5])
        c = t2.run(h4, daily, first=70)
        self.assertEqual([(x["i"], x["direction"]) for x in c], [(70, 1)])
        self.assertAlmostEqual(c[0]["anchor"], 101.5 - 2.0 * c[0]["atr"])


@unittest.skipUnless((LONG / "data" / "bars_EURUSD_H4.csv").exists(), "long-history data not present")
class ResearchParityTests(unittest.TestCase):
    """The EA mirror finds the same signals as research/long/discovery.py sig_t2 on real MT5 data."""

    @classmethod
    def setUpClass(cls):
        os.environ["EEA_RESEARCH_DATA"] = str(LONG / "data")
        sys.path.insert(0, str(LONG))
        sys.path.insert(0, str(ROOT / "research" / "g10"))
        import context
        context.DATA = LONG / "data"
        import discovery as dv
        cls.dv, cls.context = dv, context

    def check(self, symbol, start, end):
        dv, context = self.dv, self.context
        B = dv.load(symbol, "H4")
        p = {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}
        research = {(i, d) for i, d, _ in dv.sig_t2(B, p) if start <= B["t"][i] < end}
        h4 = context.load_bars(symbol, "H4")
        daily = context.load_bars(symbol, "D1")
        lo = bisect.bisect_left([b["time"] for b in h4], start)
        hi = bisect.bisect_left([b["time"] for b in h4], end)
        mine = {(c["i"], c["direction"]) for c in t2.run(h4[:hi], daily, first=max(lo, 75))}
        union = research | mine
        self.assertGreater(len(research), 20)
        agree = len(research & mine) / len(union)
        self.assertGreaterEqual(agree, 0.97, f"{symbol}: {len(research - mine)} research-only, {len(mine - research)} EA-only")

    def test_eurusd(self):
        self.check("EURUSD", 1_420_070_400, 1_514_764_800)     # 2015-2017

    def test_xauusd(self):
        self.check("XAUUSD", 1_609_459_200, 1_704_067_200)     # 2021-2023


class VirtualResultTests(unittest.TestCase):
    """research/g10/candidates_eval.py: T2 ledger lines walked with the research exit, one per symbol."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "research" / "g10"))
        import candidates_eval as ce
        import pyramid
        self.ce, self.pyr = ce, pyramid
        # uptrend for 200 bars, then a sharp fall that hits the ATR trail; 100 more bars of data
        closes = [100.0 + 0.05 * k for k in range(200)] + [110.0 - 0.5 * k for k in range(1, 101)]
        bars_ = bars(closes, width=0.4)
        for b_ in bars_:
            b_["spread"] = 10
        for i in range(len(bars_)):
            bars_[i]["atr"] = t2.atr_at(bars_, i) if i >= 14 else 0.0
        self.ctx = {"entry": bars_, "point": 0.01, "symbol": "XAUUSD"}

    def row(self, i, d=1, symbol="XAUUSD"):
        b_ = self.ctx["entry"][i]
        return {"candidate_id": f"T2-{symbol}-H4-{i}", "setup": "T2", "profile": "POSITION", "symbol": symbol,
                "direction": d, "bar_time": b_["time"], "extreme": b_["close"] - d * 2.0 * b_["atr"],
                "zone_low": 0.0, "zone_high": 0.0, "signal_atr": b_["atr"], "disposition": "NOT_EXECUTED",
                "reason": "SHADOW_MODE", "closed_utc": 1}

    def test_walk_uses_the_research_exit(self):
        e = self.ce.evaluate_row(self.row(100), self.ctx)
        self.assertEqual(e["status"], "EVALUATED")
        self.assertEqual(self.ce.T2_RULE["trail"], ("ATR", 0.0, 3.0))
        self.assertEqual(self.ce.T2_RULE["timeout"], 180)
        self.assertIsNone(self.ce.T2_RULE["target"])
        self.assertGreater(e["r"], 0)                                   # a steady trend pays

    def test_open_trade_is_not_counted_yet(self):
        e = self.ce.evaluate_row(self.row(290, d=-1), self.ctx)            # short with the fall, still open
        self.assertEqual(e["status"], "NO_BARS_YET")

    def test_one_t2_trade_per_symbol_at_a_time(self):
        rows = [self.ce.evaluate_row(self.row(i), self.ctx) for i in (100, 101, 102)]
        self.ce.mark_t2_overlaps(rows)
        self.assertEqual([r["status"] for r in rows], ["EVALUATED", "T2_POSITION_OPEN", "T2_POSITION_OPEN"])

    def test_gap_fill_is_restored(self):
        before = self.pyr.GAP_FILL
        self.ce.evaluate_row(self.row(100), self.ctx)
        self.assertEqual(self.pyr.GAP_FILL, before)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.engine = (ROOT / "Setups/DonchianTrend.mqh").read_text(encoding="utf-8")
        self.rt = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        self.live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_constants_match_research_and_oracle(self):
        for name, value in (("CHANNEL_BARS", "60"), ("STOP_ATR", "2.0"), ("TRAIL_ATR", "3.0"), ("EMA_DAYS", "200")):
            self.assertIn(f"#define EEA_T2_{name} {value}", self.engine)
        self.assertEqual((t2.CHANNEL, t2.STOP_ATR, t2.TRAIL_ATR, t2.EMA_DAYS), (60, 2.0, 3.0, 200))
        self.assertIn("#define EEA_T2_DAILY_BARS 1000", self.rt)
        self.assertEqual(t2.DAILY_BARS, 1000)
        self.assertIn('c.config_version="t2-v1-position-0.1.0";', self.engine)

    def test_engine_rules(self):
        d = section(self.engine, "int EEA_T2Direction(")
        self.assertIn("if(b.close>channel_high && d1_side==1) return 1;", d)
        self.assertIn("if(b.close<channel_low && d1_side==-1) return -1;", d)
        step = section(self.engine, "bool EEA_T2ProcessClosedBar(")
        self.assertIn("e.retest_extreme=b.close-d*EEA_T2_STOP_ATR*b.atr;", step)
        self.assertIn("e.candidate.expires_after_bars=1;", step)

    def test_scan_mirrors_oracle(self):
        scan = section(self.rt, "bool EEA_StrategyRuntimeScanT2Engine(")
        self.assertIn("CopyRates(broker_symbol,PERIOD_H4,1,EEA_T2_CATCHUP_BARS+warm+1,rates)", scan)
        self.assertIn("for(int j=b-EEA_T2_CHANNEL_BARS+1;j<b;j++)", scan)
        self.assertIn("bar.atr=EEA_StrategyRuntimeAtrFromRates(rates,b,EEA_STRATEGY_RUNTIME_ATR_PERIOD);", scan)
        self.assertIn("CopyRates(broker_symbol,PERIOD_D1,0,EEA_T2_DAILY_BARS,daily)", scan)
        side = section(self.rt, "int EEA_StrategyRuntimeT2SideAt(")
        self.assertIn("while(count<daily_count && (long)daily[count].time<day_start) count++;", side)
        self.assertIn("if(count<EEA_T2_EMA_DAYS) return 0;", side)

    def test_default_shadow_live_only_by_choice(self):
        self.assertIn("enum EEA_T2ModeInput { T2_OFF=0, T2_SHADOW=1, T2_LIVE=2 };", self.shell)
        self.assertIn("EEA_HIDDEN EEA_T2ModeInput InpT2Mode         = EEA_ED(T2_SHADOW,T2_OFF);", self.shell)
        self.assertIn('setup=="T2" ? runtime.t2_mode :', self.rt)

    def test_slot_checkpoint_and_logs(self):
        self.assertIn('setup="T2"; profile="POSITION"; timeframe="H4"; EEA_T2V1Config(config);', self.rt)
        self.assertIn('(runtime.t2_mode==EEA_S04_MODE_OFF ? 0 : 1)', self.rt)
        self.assertIn('runtime.setup[index]=="T2" ? "_t2"', self.rt)
        self.assertIn('if(runtime.setup[index]=="T2") return EEA_StrategyRuntimeScanT2Engine(runtime,index,broker_symbol);', self.rt)
        self.assertIn('setup=="T2" ? "/logs/t2_shadow.jsonl"', self.live)
        self.assertIn('timeframe=="H4" ? PERIOD_H4', self.live)
        self.assertIn('if(strategy.setup[index]=="T2") invalidation+=direction*buffer;', self.live)
        self.assertIn("target=entry+direction*EEA_T2_TARGET_CAP_R*risk_distance;", self.live)
        arb = (ROOT / "Integration/SetupArbitration.mqh").read_text(encoding="utf-8")
        self.assertIn('if(profile=="POSITION") return 6;', arb)

    def test_stop_lands_on_the_anchor(self):
        # mirror of the plan: invalidation moved inside by the buffer, stop = invalidation -/+ buffer
        for direction, anchor, buffer in ((1, 1.0950, 0.0004), (-1, 151.20, 0.03)):
            invalidation = anchor + direction * buffer
            stop = invalidation - buffer if direction == 1 else invalidation + buffer
            self.assertAlmostEqual(stop, anchor)

    def test_engine_never_trades(self):
        for forbidden in ("OrderSend", "CTrade", "EEA_ExecutionSubmit"):
            self.assertNotIn(forbidden, self.engine)


if __name__ == "__main__":
    unittest.main()
