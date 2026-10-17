"""G76/G77 F3 as a recorded label (17/10/2026): same window and signal rule as research/long/g77_dxy_tf.py."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from symbol_registry_oracle import resolve_batch  # noqa: E402

F3_SEC, M30 = 7200, 1800


def f3_label(signals, direction, gold_open):
    """Mirror of EEA_DxyF3Label once DXY is scanned: research any_dxy(X, tc - 2h, tc, -d)."""
    tc = gold_open + M30
    return "YES" if any(d == -direction and tc - F3_SEC < close <= tc for close, d in signals) else "NO"


class DxyLabelTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "Market/DxyLabel.mqh").read_text(encoding="utf-8")

    def test_window_is_the_two_hours_before_the_gold_close(self):
        gold_open = 100_000
        tc = gold_open + M30
        self.assertEqual(f3_label([(tc, -1)], 1, gold_open), "YES")                # same close counts
        self.assertEqual(f3_label([(tc - F3_SEC + 1, -1)], 1, gold_open), "YES")
        self.assertEqual(f3_label([(tc - F3_SEC, -1)], 1, gold_open), "NO")        # exactly 2 h before: out
        self.assertEqual(f3_label([(tc + M30, -1)], 1, gold_open), "NO")           # later DXY bar: no look-ahead
        self.assertEqual(f3_label([(tc, 1)], 1, gold_open), "NO")                  # same direction is F1, not F3
        self.assertEqual(f3_label([(tc, 1)], -1, gold_open), "YES")                # gold sell after DXY up
        self.assertIn("s.signal_close[i]>tc-EEA_DXY_F3_SECONDS && s.signal_close[i]<=tc", self.source)
        self.assertIn("s.signal_dir[i]==-direction", self.source)
        self.assertIn("const long tc=gold_bar_open+EEA_DXY_TF_SECONDS;", self.source)

    def test_dxy_signal_is_the_s07_base_rule_with_its_own_h4_side(self):
        self.assertIn("EEA_S07SignalAt(rates,b,window,e21,e55,e100,e200,pdi,mdi,adx,h4_side)", self.source)
        self.assertIn('EEA_S07WindowBars("M30")', self.source)
        self.assertIn("CopyRates(s.broker,PERIOD_H4,1,EEA_DXY_H4_BARS,h4)", self.source)
        self.assertNotIn("OrderSend", self.source)

    def test_label_only_on_gold_s07_m30_base_and_recorded_with_usd_flow(self):
        self.assertIn('canonical!="XAUUSD" || (setup!="S07" && setup!="S07S") || timeframe!="M30"', self.source)
        ledger = (ROOT / "Integration/CandidateLedger.mqh").read_text(encoding="utf-8")
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_DxyF3Json(g_dxy_label,e.canonical_symbol,strategy.setup[i],e.timeframe,e.direction,x.bar_time)", ledger)
        self.assertIn("EEA_DxyF3Json(g_dxy_label,engine.canonical_symbol,setup,engine.timeframe,engine.direction,", live)
        # A label never changes a decision: no other file reads it.
        for path in ROOT.rglob("*.mq*"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "EEA_DxyF3Label(" in text:
                self.assertEqual(path.name, "DxyLabel.mqh")

    def test_timer_keeps_the_dxy_bars_loaded(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_DxyLabelRefresh(g_dxy_label);", shell)
        self.assertIn("if(rates[last].time<=s.last_bar) return true;", self.source)   # rescans only on a new bar

    def test_broker_dollar_index_names(self):
        rows = resolve_batch(["DXY"], [{"name": "USDInd", "tradeable": True, "conversion_only": False}])
        self.assertEqual(rows[0]["broker_symbol"], "USDInd")
        rows = resolve_batch(["DXY"], [{"name": "USDX.", "tradeable": True, "conversion_only": False}])
        self.assertEqual(rows[0]["broker_symbol"], "USDX.")
        for path in ("Runtime/ObserverRuntime.mqh", "Runtime/SymbolSelectionPanel.mqh"):
            self.assertIn('b=="USDIND"', (ROOT / path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
