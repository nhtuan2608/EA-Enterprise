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


if __name__ == "__main__":
    unittest.main()
