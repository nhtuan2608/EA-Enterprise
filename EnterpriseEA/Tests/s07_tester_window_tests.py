"""S07Tester: the M15 add frame's compression window is an input (default 12 bars = 3 h); the shared live-EA
constant (Setups/DmiEmaCompression.mqh, 16 bars) is unchanged."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class S07TesterWindowTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "S07Tester.mq5").read_text(encoding="utf-8-sig")
        self.lib = (ROOT / "Setups" / "DmiEmaCompression.mqh").read_text(encoding="utf-8-sig")

    def test_m15_window_input(self):
        self.assertIn("input int    InpM15WindowBars     = 12;", self.src)
        self.assertIn('int TesterWindowBars(const string tf) { return tf=="M15" ? MathMax(4,InpM15WindowBars) : EEA_S07WindowBars(tf); }',
                      self.src)

    def test_frames_use_the_tester_window(self):
        self.assertIn("const int window=TesterWindowBars(f.name);", self.src)      # adds: signal and stop anchor
        self.assertIn("w=TesterWindowBars(f.name);", self.src)                      # panel checklist
        self.assertNotIn("EEA_S07WindowBars(f.name)", self.src)

    def test_live_ea_constant_unchanged(self):
        self.assertIn('{ return timeframe=="M15" ? 16 : timeframe=="M30" ? 8 : timeframe=="H1" ? 4 : 8; }', self.lib)


if __name__ == "__main__":
    unittest.main()
