"""VHedgeTester.mq5 follows the G116 / G119 research rules."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8-sig")


class VHedgeTesterTests(unittest.TestCase):
    def setUp(self):
        self.src = read("VHedgeTester.mq5")
        self.g116 = read("research/long/g116_v_hedge.py")

    def test_defaults_are_the_g119_candidate(self):
        for token in ("input VHT_Mode InpMode          = VHT_SHADOW;", "input double   InpStopAtr       = 1.5;",
                      "input double   InpTargetR       = 5.0;", "input bool     InpBreakEven     = true;",
                      "input double   InpEmaSpreadAtr  = 0.91;", "input double   InpVVolRatio     = 1.26;",
                      "input double   InpRVolRatio     = 1.17;"):
            self.assertIn(token, self.src)

    def test_v_and_return_rules_match_research(self):
        self.assertIn("body = ((o < e) & (c > e)) | ((o > e) & (c < e))", self.g116)
        self.assertIn("RET_BARS = 6", self.g116)
        self.assertIn("(r[i].open<e[i] && r[i].close>e[i]) || (r[i].open>e[i] && r[i].close<e[i])", self.src)
        self.assertIn("#define VHT_RET_BARS 6", self.src)
        self.assertIn("if(inside) { decided=true; hit=(left && q==j); }", self.src)
        self.assertIn("if(hit && found_v<0) found_v=v;", self.src)        # the earliest V claims the return bar

    def test_hedge_add_target_and_break_even(self):
        self.assertIn("const double gap=(InpStopAtr+0.1)*atr;", self.src)
        self.assertIn("G.tp=G.surv_entry+d*InpTargetR*G.R;", self.src)
        self.assertIn("A.entry=(d==1 ? ask : bid);", self.src)
        self.assertIn("A.sl=G.surv_sl", self.src)
        self.assertIn("InpBreakEven && !G.be_done && d*(G.best-G.surv_entry)>=G.R", self.src)
        self.assertIn("#define VHT_CAP_BARS 288", self.src)

    def test_live_only_on_hedging_accounts(self):
        self.assertIn("ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", self.src)
        self.assertIn("return INIT_PARAMETERS_INCORRECT;", self.src)


if __name__ == "__main__":
    unittest.main()
