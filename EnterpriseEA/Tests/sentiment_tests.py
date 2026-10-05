"""Market sentiment from price and cross pairs: reduce-only filter (M1-M6)."""
import unittest
from pathlib import Path

from sentiment_oracle import config, pair, compute, align


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


def usd_strong_market(scale=1.0):
    """USD up everywhere (EURUSD/GBPUSD/AUDUSD/NZDUSD down, USDJPY/USDCAD/USDCHF up)."""
    z = scale
    return [pair("EURUSD", -z, -z), pair("GBPUSD", -z, -z), pair("AUDUSD", -z, -z), pair("NZDUSD", -z, -z),
            pair("USDJPY", z, z), pair("USDCAD", z, z), pair("USDCHF", z, z), pair("EURJPY", 0.0, 0.0),
            pair("XAUUSD", -z, -z, "GOLD")]


class SentimentComputeTests(unittest.TestCase):
    def test_usd_strength_and_ranking(self):
        snap = compute(usd_strong_market(), config())
        self.assertTrue(snap["ok"])
        self.assertAlmostEqual(snap["s4"]["USD"], 1.0)
        self.assertLess(snap["s4"]["EUR"], 0)

    def test_too_few_pairs_is_unavailable_and_neutral(self):
        snap = compute([pair("EURUSD", 1, 1), pair("GBPUSD", 1, 1)], config())
        self.assertFalse(snap["ok"])
        a = align(snap, [], config(), "EURUSD", 1, "SWING")
        self.assertEqual((a["verdict"], a["factor"], a["block"]), ("UNAVAILABLE", 1.0, False))


class SentimentAlignTests(unittest.TestCase):
    def test_buying_eurusd_against_a_strong_usd(self):
        market = usd_strong_market(scale=1.0)
        snap = compute(market, config())
        swing = align(snap, market, config(), "EURUSD", 1, "SWING")
        self.assertEqual(swing["verdict"], "STRONGLY_AGAINST")
        self.assertTrue(swing["block"])                      # M4: SWING blocked
        scalp = align(snap, market, config(), "EURUSD", 1, "SCALP")
        self.assertFalse(scalp["block"])
        self.assertEqual(scalp["factor"], 0.5)               # M4: SCALP x0.5
        sell = align(snap, market, config(), "EURUSD", -1, "SWING")
        self.assertEqual((sell["verdict"], sell["factor"]), ("ALIGNED", 1.0))

    def test_both_windows_must_disagree(self):  # M2
        market = [pair("EURUSD", -1, 0.5), pair("GBPUSD", -1, 0.5), pair("AUDUSD", -1, 0.5), pair("NZDUSD", -1, 0.5),
                  pair("USDJPY", 1, -0.5), pair("USDCAD", 1, -0.5), pair("USDCHF", 1, -0.5)]
        snap = compute(market, config())
        a = align(snap, market, config(), "EURUSD", 1, "SWING")
        self.assertEqual(a["factor"], 1.0)

    def test_gold_uses_usd_and_regime(self):
        market = usd_strong_market(scale=1.0)
        snap = compute(market, config())
        a = align(snap, market, config(), "XAUUSD", 1, "SCALP")
        self.assertLess(a["a4"], -0.3)
        self.assertEqual(a["factor"], 0.5)

    def test_never_raises_risk(self):
        for scale in (-2.0, -0.5, 0.0, 0.5, 2.0):
            market = usd_strong_market(scale)
            snap = compute(market, config())
            for symbol in ("EURUSD", "USDJPY", "XAUUSD"):
                for direction in (1, -1):
                    for profile in ("SCALP", "SWING"):
                        self.assertLessEqual(align(snap, market, config(), symbol, direction, profile)["factor"], 1.0)


class SentimentSourceTests(unittest.TestCase):
    def test_defaults_match_decisions(self):
        pure = read("Market/Sentiment.mqh")
        defaults = section(pure, "void EEA_SentConfigDefaults")
        for token in ("c.against_threshold=-0.3", "c.strong_threshold=-0.8", "c.strong_consensus=0.7",
                      "c.against_factor=0.5", "c.min_combined_factor=0.25"):
            self.assertIn(token, defaults)

    def test_live_loop_applies_reduce_only_with_floor(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        apply = section(live, "bool EEA_ControlledLiveApplySentiment")
        self.assertIn('if(alignment.block) { reason="SENTIMENT_STRONGLY_AGAINST"; return false; }', apply)
        self.assertIn("alignment.factor>1.0", apply)
        self.assertIn('"RISK_MODIFIERS_TOO_LOW"', apply)
        self.assertIn("plan.base_risk_fraction*=alignment.factor;", apply)
        self.assertIn("EEA_ControlledLiveApplySentiment(sentiment,news,strategy,i,plan,alignment,reason)", live)
        self.assertIn('"SENTIMENT_APPLIED"', live)

    def test_only_closed_bars_and_no_orders(self):
        runtime = read("Market/SentimentRuntime.mqh")
        self.assertIn("CopyRates(broker,PERIOD_H1,1,40,rates)", runtime)   # shift 1: closed bars only
        for forbidden in ("OrderSend", "EEA_ExecutionSubmit", "EEA_ExecutionClosePosition"):
            self.assertNotIn(forbidden, runtime)


if __name__ == "__main__":
    unittest.main()
