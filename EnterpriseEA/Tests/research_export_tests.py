"""G10 research bar export: read-only, closed bars only, bounded re-export."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BarExportTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Runtime/BarExport.mqh").read_text(encoding="utf-8")

    def test_read_only(self):
        for forbidden in ("OrderSend", "EEA_ExecutionSubmit", "CTrade"):
            self.assertNotIn(forbidden, self.src)

    def test_closed_bars_and_layout(self):
        self.assertIn("(long)TimeTradeServer()-PeriodSeconds((ENUM_TIMEFRAMES)rt.tf[j])", self.src)
        self.assertIn('"time,open,high,low,close,spread\\n"', self.src)
        self.assertIn("int tfs[3]={PERIOD_M5,PERIOD_H1,PERIOD_H4};", self.src)

    def test_export_once_per_week(self):
        self.assertIn("#define EEA_BAR_EXPORT_MAX_AGE 604800", self.src)
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_BarExportUpdate(g_bar_export,", shell)

    def test_weekend_and_hourly_recheck(self):
        self.assertIn("#define EEA_BAR_EXPORT_RECHECK_SECONDS 3600", self.src)
        self.assertIn("!EEA_BarExportStale(StringToInteger(EEA_StrategyCandidateStoreField(json,\"exported_at_utc\")),(long)TimeGMT())",
                      self.src)
        self.assertIn("rt.loaded=false; rt.done=false;", self.src)


def weekend_start(now):
    """Mirror of EEA_BarExportWeekendStart."""
    day = now // 86400
    weekday = (day + 4) % 7
    return day * 86400 if weekday == 6 else (day - 1) * 86400 if weekday == 0 else 0


def stale(exported, now):
    """Mirror of EEA_BarExportStale."""
    if now - exported >= 604800:
        return True
    w = weekend_start(now)
    return w > 0 and exported < w


class WeekendRefreshTests(unittest.TestCase):
    MON = 1791158400  # 2026-10-05 00:00 UTC, a Monday

    def test_weekend_start(self):
        sat = self.MON + 5 * 86400
        self.assertEqual(weekend_start(self.MON + 3600), 0)
        self.assertEqual(weekend_start(self.MON + 4 * 86400 + 80000), 0)     # Friday
        self.assertEqual(weekend_start(sat + 7200), sat)                      # Saturday
        self.assertEqual(weekend_start(sat + 86400 + 7200), sat)              # Sunday

    def test_monday_export_is_refreshed_on_saturday_once(self):
        exported = self.MON + 3600
        sat = self.MON + 5 * 86400
        self.assertFalse(stale(exported, self.MON + 4 * 86400))              # Friday: current
        self.assertTrue(stale(exported, sat + 600))                          # Saturday: due
        self.assertFalse(stale(sat + 900, sat + 86400 + 600))                # re-exported Saturday: Sunday current
        self.assertTrue(stale(exported, exported + 604800))                  # a week old

    def test_mql_formula_matches(self):
        src = (ROOT / "Runtime/BarExport.mqh").read_text(encoding="utf-8")
        self.assertIn("const long weekday=(day+4)%7;", src)
        self.assertIn("if(weekday==6) return day*86400;", src)
        self.assertIn("if(weekday==0) return (day-1)*86400;", src)


if __name__ == "__main__":
    unittest.main()
