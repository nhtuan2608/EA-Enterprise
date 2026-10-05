"""G11 part 2: reference-pair H1 export (EA) and the per-news sentiment replay (research/g11)."""
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g11"))

import sentiment_news as sn  # noqa: E402


def series(closes, start=1_700_000_000):
    bars = []
    prev = closes[0]
    for i, c in enumerate(closes):
        bars.append({"time": start + 3600 * i, "open": prev, "high": max(prev, c) + 0.0005,
                     "low": min(prev, c) - 0.0005, "close": c, "spread": 10})
        prev = c
    return {"time": [b["time"] for b in bars], "bars": bars}


def ea_measure(rates):
    """Literal port of EEA_SentMeasure on the 40-bar window."""
    tr = sum(max(rates[i]["high"], rates[i - 1]["close"]) - min(rates[i]["low"], rates[i - 1]["close"])
             for i in range(26, 40))
    atr = tr / 14.0
    c0 = rates[39]["close"]
    return (c0 - rates[35]["close"]) / (atr * 2.0), (c0 - rates[15]["close"]) / (atr * math.sqrt(24.0))


class MeasureTests(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(3)
        price, closes = 1.1, []
        for _ in range(120):
            price += rnd.gauss(0, 0.001)
            closes.append(price)
        self.s = series(closes)

    def test_matches_ea_formula_on_closed_bars_only(self):
        release = self.s["time"][80] + 1800              # half way through bar 80: bar 80 still forming
        z = sn.measure(self.s, release)
        z4, z24 = ea_measure(self.s["bars"][40:80])     # last closed bar is 79
        self.assertAlmostEqual(z["z4"], z4)
        self.assertAlmostEqual(z["z24"], z24)

    def test_needs_forty_closed_bars(self):
        self.assertIsNone(sn.measure(self.s, self.s["time"][30]))


class AnalysisTests(unittest.TestCase):
    def build(self, follow=True):
        rnd = random.Random(5)
        syms = sn.FX + ["XAUUSD"]
        series_by_pair = {}
        n = 400
        for k, sym in enumerate(syms):
            price, closes = 1.0 + k, []
            for i in range(n):
                # USD trends up in the first half and down in the second.
                usd = 1 if i < n // 2 else -1
                drift = 0.002 * usd * (1 if sym[3:6] == "USD" else -1 if sym[:3] == "USD" else 0) * -1
                price += drift + rnd.gauss(0, 0.0005)
                closes.append(price)
            series_by_pair[sym] = series(closes)
        records = []
        for i in range(60, n - 5, 7):
            t = series_by_pair["EURUSD"]["time"][i]
            usd_strong = i < n // 2
            m = (-1.0 if usd_strong else 1.0) * (1 if follow else -1)        # EURUSD falls while USD is strong
            records.append({"quality": "OK", "replay_ok": True, "symbol": "EURUSD", "currency": "USD",
                            "event_utc": t, "move_15m_atr": m, "move_60m_atr": 2 * m,
                            "surprise_side": "ABOVE" if usd_strong else "BELOW", "surprise_quality": "OK"})
        return records, series_by_pair

    def test_reactions_following_sentiment_are_detected(self):
        records, s = self.build(follow=True)
        res = sn.analyse(records, s, lambda utc: 0)
        t = res["summary"]["tests"]["Sentiment 4h -> m15"]
        self.assertGreater(t["n"], 20)
        self.assertGreater(t["hit"], 0.8)
        self.assertGreater(res["summary"]["surprise"]["with_sentiment"]["n"], 0)

    def test_reactions_against_sentiment_are_detected(self):
        records, s = self.build(follow=False)
        t = sn.analyse(records, s, lambda utc: 0)["summary"]["tests"]["Sentiment 4h -> m15"]
        self.assertLess(t["hit"], 0.2)

    def test_too_few_pairs_gives_no_rows(self):
        records, s = self.build()
        few = {k: v for k, v in s.items() if k in ("EURUSD", "GBPUSD", "USDJPY")}
        self.assertEqual(sn.analyse(records, few, lambda utc: 0)["summary"]["n"], 0)


class HelperTests(unittest.TestCase):
    def test_direction_score(self):
        snap = {"s4": {"EUR": 0.4, "USD": -0.6, "JPY": 0.1}}
        self.assertAlmostEqual(sn.direction_score(snap, "EURUSD"), 1.0)
        self.assertAlmostEqual(sn.direction_score(snap, "USDJPY"), -0.7)
        self.assertAlmostEqual(sn.direction_score(snap, "XAUUSD"), 0.6)
        self.assertIsNone(sn.direction_score(snap, "BTCUSD"))

    def test_surprise_direction(self):
        base = {"surprise_side": "ABOVE", "surprise_quality": "OK"}
        self.assertEqual(sn.surprise_direction(dict(base, currency="USD", symbol="EURUSD")), -1)
        self.assertEqual(sn.surprise_direction(dict(base, currency="USD", symbol="USDJPY")), 1)
        self.assertEqual(sn.surprise_direction(dict(base, currency="JPY", symbol="EURUSD")), 0)
        self.assertEqual(sn.surprise_direction(dict(base, surprise_quality="MISSING", currency="USD", symbol="USDJPY")), 0)

    def test_wilson(self):
        p, lo, hi = sn.wilson(50, 100)
        self.assertAlmostEqual(p, 0.5)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        self.assertEqual(sn.wilson(0, 0), (0.0, 0.0, 0.0))


class ExportSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Runtime/BarExport.mqh").read_text(encoding="utf-8")

    def test_reference_pairs_exported_on_h1_from_the_replay_start(self):
        self.assertIn("rt.tf[rt.count]=PERIOD_H1;\n      rt.reference[rt.count]=true;", self.src)
        self.assertIn("if(canonical[i]==ref_canonical[r] && broker[i]!=\"\") selected=true;", self.src)
        self.assertIn("const long start=(rt.tf[j]==PERIOD_M5 || rt.reference[j] ? rt.from_utc : rt.swing_from_utc);", self.src)

    def test_job_signature_decides_whether_the_export_is_current(self):
        self.assertIn('EEA_StrategyCandidateStoreField(json,"signature")==EEA_BarExportSignature(rt)', self.src)
        self.assertIn('",\\"signature\\":\\""+EEA_BarExportSignature(rt)+', self.src)
        self.assertIn('(rt.reference[j] ? "R" : "")', self.src)
        # The job list is built before the meta check (the signature needs it).
        load = self.src.split("void EEA_BarExportLoad(", 1)[1]
        self.assertLess(load.index("rt.reference[rt.count]=true"), load.index("EEA_BarExportMetaPath(rt.root)"))

    def test_shell_passes_the_sentiment_pairs(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("ref_canonical[r]=g_sentiment.pairs[r].canonical; ref_broker[r]=g_sentiment.brokers[r];", shell)
        self.assertIn("ref_canonical,ref_broker,g_sentiment.count);", shell)

    def test_export_stays_read_only(self):
        for forbidden in ("OrderSend", "CTrade", "EEA_ExecutionSubmit"):
            self.assertNotIn(forbidden, self.src)


if __name__ == "__main__":
    unittest.main()
