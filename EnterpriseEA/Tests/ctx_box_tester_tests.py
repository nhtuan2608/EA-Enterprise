"""G106 CtxBoxTester.mq5 follows research/long/g106_ctx_box.py and keeps the S07Tester gates."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class CtxBoxTesterTests(unittest.TestCase):
    def setUp(self):
        self.src = read("CtxBoxTester.mq5")
        self.py = read("research/long/g106_ctx_box.py")

    def test_reads_only_its_two_input_files(self):
        for banned in ("Runtime/", "Integration/", "FILE_WRITE", "EventSetTimer"):
            self.assertNotIn(banned, self.src)
        self.assertEqual(self.src.count("FileOpen("), 2)

    def test_timeframe_pairs_match_research(self):
        self.assertIn('PAIRS = {"M5": ("m5v", "30min"), "M15": ("m15v", "1h"), "M30": ("m30v", "4h"), "H1": ("h1v", "4h")}', self.py)
        self.assertIn("case CBT_M5: return PERIOD_M30; case CBT_M15: return PERIOD_H1; }", self.src)
        self.assertIn("return PERIOD_H4;", self.src)

    def test_context_switch_entry_and_stop(self):
        self.assertIn("sw = ctx & ~np.concatenate([[False], ctx[:-1]])", self.py)
        self.assertIn("if(now==0 || now==before) return;", self.src)
        self.assertIn("for(int k=i-15;k<=i;k++)", self.src)
        self.assertIn("TryEnter(now,ext-now*0.1*atr[i]);", self.src)

    def test_box_hold_matches_research(self):
        self.assertIn("Hb[\"box_ok\"] = (bh - bl) <= 2.5 * Hb[\"atr\"]", self.py)
        self.assertIn("const bool box_ok=(bh-bl)<=InpBoxMaxAtr*atr[b];", self.src)
        self.assertIn("input double       InpBoxMaxAtr     = 2.5;", self.src)
        self.assertIn("d*(g_leg[s].best-g_leg[s].entry)/g_leg[s].risk>=1.0", self.src)
        self.assertIn("d*(hc-(g_leg[s].level-d*InpCloseBufAtr*at))<0.0", self.src)
        self.assertIn("if(d*(cand-g_leg[s].hard)>0.0", self.src)

    def test_gates_are_the_s07tester_ones(self):
        s07 = read("S07Tester.mq5")
        for token in ("if(a4<=-0.8 && a24<=-0.8 && ag4>=0.7 && ag24>=0.7) return 0.0;",
                      "now>=t-(long)InpNewsSwingBlockBeforeMin*60 && now<t+(long)InpNewsPostMin*60",
                      "if(median>0.0 && point>0.0 && spread/point>2.0*median)"):
            self.assertIn(token, s07)
            self.assertIn(token, self.src)


if __name__ == "__main__":
    unittest.main()
