"""News data health: deterministic checks over the reaction records (G6, AI design section 7)."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


def time_alignment_warn(peaks, big_moves):
    """Mirror: WARN when >= 30% of >= 5 strong DIRECT reactions peak 55..65 minutes from T."""
    strong = [p for p, m in zip(peaks, big_moves) if abs(m) >= 1.0]
    sixty = [p for p in strong if 55 <= abs(p) <= 65]
    return len(strong) >= 5 and len(sixty) * 10 >= len(strong) * 3


class NewsHealthRuleTests(unittest.TestCase):
    def test_time_alignment_rule(self):
        self.assertFalse(time_alignment_warn([0, 1, 0, 2, 0], [1.5] * 5))
        self.assertTrue(time_alignment_warn([60, 61, 0, 0, 0], [1.5] * 5))
        self.assertFalse(time_alignment_warn([60, 61, 59], [1.5] * 3))      # too few samples
        self.assertFalse(time_alignment_warn([60, 60, 60, 60, 60], [0.5] * 5))  # weak reactions ignored


class NewsHealthSourceTests(unittest.TestCase):
    def setUp(self):
        self.rec = read("News/NewsReactionRecorder.mqh")

    def test_every_check_of_the_design_exists(self):
        evaluate = section(self.rec, "void EEA_NewsHealthEvaluate")
        for code in ("NDH_INCOMPLETE_RATE", "NDH_TIME_ALIGNMENT", "NDH_SPREAD_SOURCE", "NDH_OUTLIER",
                     "NDH_CLUSTER_CONSISTENCY", "NDH_BACKFILL_STALL", "NDH_SAMPLE_COVERAGE",
                     "NDH_SUGGESTION_GAP", "NDH_GUARD_EFFECT"):
            self.assertIn('"' + code + '"', evaluate)

    def test_thresholds(self):
        add = section(self.rec, "void EEA_NewsHealthAdd")
        self.assertIn("MathAbs(move15_atr)>10.0 || spread_ratio>30.0", add)
        self.assertIn("if(a>=55 && a<=65) h.offset_sixty++;", add)
        self.assertIn("MathAbs(h.cluster_move15[i]-move15_atr)>0.05", add)
        evaluate = section(self.rec, "void EEA_NewsHealthEvaluate")
        self.assertIn("h.symbol_incomplete[i]*10>h.symbol_total[i]", evaluate)     # > 10%
        self.assertIn("(long)TimeGMT()-rt.cursor_changed_utc>2*3600", evaluate)    # stall after 2h

    def test_peak_offset_is_recorded(self):
        pure = read("News/NewsReaction.mqh")
        self.assertIn("r.peak_bar_offset_min=(int)((bars[i].t-T)/60);", pure)
        self.assertIn('"peak_bar_offset_min', self.rec)

    def test_health_is_display_and_audit_only(self):
        evaluate = section(self.rec, "void EEA_NewsHealthEvaluate")
        for forbidden in ("cfg.", "OrderSend", "EEA_Execution"):
            self.assertNotIn(forbidden + "max_normalize_min=" if forbidden == "cfg." else forbidden, evaluate)
        shell = read("EnterpriseEA.mq5")
        self.assertIn('"NEWS_DATA_HEALTH"', shell)
        self.assertIn("EEA_NewsHealthWrite(g_news_health,g_config.data_root);", shell)


if __name__ == "__main__":
    unittest.main()
