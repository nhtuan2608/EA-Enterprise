"""G96 XauRegimeTester.mq5: the tester EA follows the G96 rules and keeps the S07Tester gates."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class XauRegimeTesterTests(unittest.TestCase):
    def setUp(self):
        self.src = read("XauRegimeTester.mq5")

    def test_tester_only_reads_its_two_input_files(self):
        for banned in ("Runtime/", "Integration/", "FILE_WRITE", "EventSetTimer"):
            self.assertNotIn(banned, self.src)
        self.assertEqual(self.src.count("FileOpen("), 2)
        self.assertIn('#property tester_file "S07Tester_news.csv"', self.src)
        self.assertIn('#property tester_file "S07Tester_sentiment.csv"', self.src)

    def test_regime_matches_research_r1(self):
        research = read("research/long/g96_regime.py")
        self.assertIn("slope = np.sign(e - e.shift(10))", research)
        self.assertIn("return np.where(side == slope, side, 0.0)", research)
        self.assertIn("g_day.state=(side==slope ? side : 0);", self.src)
        self.assertIn("e[i]>e[i-InpSlopeDays]", self.src)
        self.assertIn("input int          InpSlopeDays     = 10;", self.src)
        # ATR20 = simple mean of the true range, like load_d1()
        self.assertIn(".rolling(20).mean()", research)
        self.assertIn("g_day.atr=tr/InpAtrPeriod;", self.src)

    def test_defaults_are_the_part_a_pick(self):
        self.assertIn("input XRT_Mode     InpMode          = XRT_LONG_ONLY;", self.src)
        self.assertIn("input int          InpEmaPeriod     = 50;", self.src)
        self.assertIn("input bool         InpTrail         = true;", self.src)
        self.assertIn("input double       InpTrailAtr      = 3.0;", self.src)
        self.assertIn("input XRT_Zone     InpBuyZone       = XRT_MARKET;", self.src)

    def test_exits_and_trail_block(self):
        self.assertIn('if(g_day.state!=dir) { CloseOwn("regime"); g_exit_regime++; }', self.src)
        self.assertIn("dir*(g_day.close-g_best)<=-InpTrailAtr*g_day.atr", self.src)
        self.assertIn("if(g_blocked_dir!=0 && g_day.state!=g_blocked_dir) g_blocked_dir=0;", self.src)

    def test_gates_are_the_s07tester_ones(self):
        s07 = read("S07Tester.mq5")
        for token in ("if(a4<=-0.8 && a24<=-0.8 && ag4>=0.7 && ag24>=0.7) return 0.0;",
                      "if(a4<=-0.3 && a24<=-0.3) return 0.5;",
                      "now>=t-(long)InpNewsSwingBlockBeforeMin*60 && now<t+(long)InpNewsPostMin*60",
                      "return normalizing && !MarketStable();",
                      "if(median>0.0 && point>0.0 && spread/point>2.0*median)",
                      "const double basis=("):
            self.assertIn(token, s07)
            self.assertIn(token, self.src)
        # a waiting limit is pulled while the News Guard blocks new entries
        self.assertIn("else if(NewsBlocked((long)TimeCurrent())) { DeletePending(); g_block_news++; g_want_entry=true; }",
                      self.src)

    def test_zones_cover_the_plan(self):
        body = self.src.split("enum XRT_Zone", 1)[1].split("};", 1)[0]
        zones = re.findall(r"XRT_(\w+)=(\d)", body)
        self.assertEqual([int(v) for _, v in zones], list(range(9)))


if __name__ == "__main__":
    unittest.main()
