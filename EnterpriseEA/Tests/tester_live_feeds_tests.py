"""Tester/LiveFeeds.mqh: on a live chart the tester EAs read HIGH news from the MT5 calendar and compute the G91
sentiment from the broker's pairs; sentiment acts only near HIGH news by default; the spread filter is an opt-in."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOTS = ("S07Tester.mq5", "XauRegimeTester.mq5", "CtxBoxTester.mq5")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8-sig")


class TesterLiveFeedsTests(unittest.TestCase):
    def setUp(self):
        self.lf = read("Tester/LiveFeeds.mqh")

    def test_bots_wire_the_live_sources(self):
        for bot in BOTS:
            src = read(bot)
            with self.subTest(bot=bot):
                inc = src.index('#include "Tester/LiveFeeds.mqh"')
                self.assertLess(src.index("int    g_sent_n=0;"), inc)
                self.assertLess(inc, src.index("double SentimentFactor("))
                self.assertIn("   LoadSentiment();\n   LfInit();", src)
                self.assertIn("void OnTick()\n  {\n   LfRefresh();", src)

    def test_sentiment_near_news_only_by_default(self):
        for bot in BOTS:
            src = read(bot)
            with self.subTest(bot=bot):
                self.assertIn("input bool   InpSentimentNewsOnly       = true;", src)
                self.assertIn("input int    InpSentimentNewsHours      = 4;", src)
                self.assertIn("if(InpSentimentNewsOnly && !LfNearHighNews(now)) return 1.0;", src)

    def test_spread_filter_is_opt_in(self):
        for bot in BOTS:
            src = read(bot)
            with self.subTest(bot=bot):
                line = next(x for x in src.splitlines() if x.startswith("input bool") and "InpSpreadFilter" in x)
                self.assertIn("= false;", line)

    def test_live_only_and_read_only(self):
        self.assertIn("bool LfLive() { return !MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION); }", self.lf)
        for fn in ("void LfInit()", "void LfRefresh()"):
            body = self.lf[self.lf.index(fn):]
            self.assertIn("if(!LfLive()) return;", body[:200])
        for banned in ("FileOpen", "FILE_WRITE", "OrderSend", "Trade/"):
            self.assertNotIn(banned, self.lf)

    def test_news_from_the_calendar(self):
        self.assertIn("CalendarValueHistory(v,(datetime)(now-86400),(datetime)(now+7*86400))", self.lf)
        self.assertIn("e.importance!=CALENDAR_IMPORTANCE_HIGH", self.lf)
        self.assertIn("NewsIgnored(e.name)", self.lf)
        tracked = self.lf[self.lf.index("bool LfTracked("):self.lf.index("void LfNewsRefresh(")]
        for c in ("USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY"):
            self.assertIn(f'c=="{c}"', tracked)

    def test_sentiment_formula_matches_g91(self):
        g91 = read("research/long/g91_tester_inputs.py")
        # measure: ATR14 of the last 14 true ranges over 40 closed H1 bars, 4 and 24 bar moves
        self.assertIn("return (c0 - cc[-5]) / (atr * 2.0), (c0 - cc[-25]) / (atr * math.sqrt(24.0))", g91)
        self.assertIn("z4=(r[39].close-r[35].close)/(atr*2.0);", self.lf)
        self.assertIn("z24=(r[39].close-r[15].close)/(atr*MathSqrt(24.0));", self.lf)
        # readable only with >= 4 FX pairs and >= 3 USD pairs
        self.assertIn("ok = fx_pairs >= 4 and n[0] >= 3", g91)
        self.assertIn("if(fx<4 || n[0]<3)", self.lf)
        # risk blend JPY + CHF (+ gold - S&P), alignment for a gold buy
        self.assertIn("r4 = s4[3] + s4[6]", g91)
        self.assertIn("double r4=s4[3]+s4[6], r24=s24[3]+s24[6];", self.lf)
        self.assertIn("a4 = -s4[0] + 0.5 * reg4", g91)
        self.assertIn("g_sent_v[k][0]=-s4[0]+0.5*r4/parts;", self.lf)
        # share of USD pairs against: columns ag4_buy, ag24_buy, ag4_sell, ag24_sell
        self.assertIn("support = (-d) * zz if s[:3] == \"USD\" else d * zz", g91)
        self.assertIn('const double support=(StringSubstr(g_lf_fx[i],0,3)=="USD" ? -d*zz : d*zz);', self.lf)
        self.assertIn("g_sent_v[k][2+2*s+h]=", self.lf)
        self.assertIn("time_server;ok;a4;a24;ag4_buy;ag24_buy;ag4_sell;ag24_sell", g91)

    def test_near_news_window(self):
        # LfNearHighNews: first event at or after now - w, and it is not later than now + w
        def near(events, now, hours=4):
            w = hours * 3600
            nxt = [t for t in sorted(events) if t >= now - w]
            return bool(nxt) and nxt[0] <= now + w
        self.assertTrue(near([10_000], 10_000 + 4 * 3600))
        self.assertFalse(near([10_000], 10_000 + 4 * 3600 + 1))
        self.assertTrue(near([10_000], 10_000 - 4 * 3600))
        self.assertFalse(near([], 10_000))
        self.assertIn("while(lo<hi) { const int mid=(lo+hi)/2; if(g_news_t[mid]<now-w) lo=mid+1; else hi=mid; }", self.lf)
        self.assertIn("return lo<g_news_n && g_news_t[lo]<=now+w;", self.lf)

    def test_panel_marks_are_ascii(self):
        panel = read("Tester/TesterPanel.mqh")
        self.assertIn('return ok ? "[v]" : "[x]";', panel)
        for bot in BOTS + ("CtxLimitTester.mq5", "Tester/TesterPanel.mqh"):
            src = read(bot)
            with self.subTest(file=bot):
                self.assertNotIn("✓", src)
                self.assertNotIn("✗", src)


if __name__ == "__main__":
    unittest.main()
