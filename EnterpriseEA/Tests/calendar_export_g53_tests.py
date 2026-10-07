"""G53: MT5 calendar history export (Runtime/CalendarExport.mqh) and its research reader."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import calendar_history as ch  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class ExportSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Runtime" / "CalendarExport.mqh").read_text(encoding="utf-8")
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_input_extends_and_defaults_on(self):
        self.assertIn("input bool   InpResearchExportCalendar  = true;", self.shell)
        self.assertIn("EEA_CalendarExportInit(g_calendar_export,g_config.data_root,InpResearchExportCalendar);", self.shell)
        self.assertIn('EEA_LiveStatusPair("calendar_export",g_calendar_export.reason,true)', self.shell)

    def test_runs_only_while_the_bar_export_is_idle_and_after_it(self):
        bars = self.shell.index("EEA_BarExportUpdate(g_bar_export,")
        cal = self.shell.index("EEA_CalendarExportUpdate(g_calendar_export,g_bar_export.done || !g_bar_export.enabled);")
        self.assertLess(bars, cal)
        upd = section(self.src, "void EEA_CalendarExportUpdate(")
        self.assertIn("if(!rt.enabled || !idle) return;", upd)

    def test_one_year_per_pass_and_never_an_empty_past_year(self):
        upd = section(self.src, "void EEA_CalendarExportUpdate(")
        self.assertEqual(upd.count("EEA_CalendarExportYear(rt,"), 1)
        year = section(self.src, "bool EEA_CalendarExportYear(")
        self.assertIn("if(ArraySize(values)<=0)", year)
        self.assertIn("FileMove(tmp,0,path,FILE_REWRITE)", year)              # never a half-written year
        due = section(self.src, "bool EEA_CalendarExportDue(")
        self.assertIn("if(year<current_year) return false;", due)
        self.assertIn("EEA_BarExportStale(", due)

    def test_rows_high_and_moderate_tracked_currencies_utc_at_the_event(self):
        year = section(self.src, "bool EEA_CalendarExportYear(")
        self.assertIn("ev.importance!=CALENDAR_IMPORTANCE_HIGH && ev.importance!=CALENDAR_IMPORTANCE_MODERATE", year)
        self.assertIn("EEA_NewsCurrencyTracked(country.currency)", year)
        self.assertIn("const long utc=EEA_NewsCalendarUtc(raw);", year)                       # G54
        self.assertIn("const long server=utc+EEA_NewsServerOffsetAt(utc,now_offset,now);", year)
        self.assertIn('"time_utc,time_server,time_calendar,currency,importance,sector,event_id,name,actual,forecast,previous\\n"', year)
        self.assertNotIn("CALENDAR_IMPORTANCE_LOW", year)
        self.assertNotIn("Order", year)                                       # read-only
        self.assertIn("#define EEA_CALENDAR_EXPORT_FROM_YEAR 2010", self.src)


def utc(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp())


class ReaderTests(unittest.TestCase):
    def write(self, folder, rows):
        head = "time_utc,time_server,time_calendar,currency,importance,sector,event_id,name,actual,forecast,previous\n"
        (folder / "calendar_2024.csv").write_text(head + "".join(
            f"{a},{b},{b},{c},{imp},0,1,{name},,,\n" for a, b, c, imp, name in rows), encoding="utf-8")

    def test_load_filters_importance_and_keywords(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)
            self.write(f, [(30, 30 + 10800, "USD", "HIGH", "Nonfarm Payrolls"),
                           (10, 10 + 10800, "USD", "HIGH", "Initial Jobless Claims"),
                           (20, 20 + 10800, "EUR", "MODERATE", "ZEW")])
            got = ch.load(f, ("HIGH",), ["initial jobless claims"])
            self.assertEqual([e["name"] for e in got], ["Nonfarm Payrolls"])
            self.assertEqual(len(ch.load(f, ("HIGH", "MODERATE"))), 3)

    def test_currencies_like_the_ea(self):
        self.assertEqual(ch.currencies_of("EURUSD"), {"EUR", "USD"})
        for s in ("XAUUSD", "BTCUSD", "XAGUSD", "ETHUSD", "USOUSD", "SP500"):
            self.assertEqual(ch.currencies_of(s), {"USD"}, s)
        ev = [{"currency": "EUR", "time_server": 5}, {"currency": "JPY", "time_server": 6},
              {"currency": "USD", "time_server": 7}]
        self.assertEqual(ch.times_for(ev, "EURUSD"), [5, 7])
        self.assertEqual(ch.times_for(ev, "XAUUSD"), [7])

    def test_nfp_checks(self):
        ev = [{"currency": "USD", "name": "Nonfarm Payrolls", "time_utc": utc(2024, 7, 5, 12, 30),
               "time_server": utc(2024, 7, 5, 15, 30)},
              {"currency": "USD", "name": "Nonfarm Payrolls", "time_utc": utc(2024, 12, 6, 13, 30),
               "time_server": utc(2024, 12, 6, 15, 30)}]
        self.assertEqual(ch.nfp_utc_share(ev), (2, 1.0))
        ev[1]["time_utc"] += 3600
        self.assertEqual(ch.nfp_utc_share(ev), (2, 0.5))
        # H1 bars on the server clock: the NFP bar moves 4, the same hour on other Fridays 1
        h1 = []
        for day in (5, 12, 19, 26):
            t = utc(2024, 7, day, 15, 0)
            rng = 4.0 if day == 5 else 1.0
            h1.append({"time": t, "high": 100 + rng, "low": 100.0})
        n, ratio = ch.nfp_bar_ratio(ev[:1], h1)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(ratio, 4.0)


class PlanTests(unittest.TestCase):
    def test_decision_needs_every_period_and_the_interval(self):
        import os
        old = os.environ.get("EEA_RESEARCH_DATA")
        try:
            sys.path.insert(0, str(ROOT / "research" / "long"))
            import news_rules_long as nr
        finally:
            if old is None:
                os.environ.pop("EEA_RESEARCH_DATA", None)
            else:
                os.environ["EEA_RESEARCH_DATA"] = old
        rows = []
        for p in ("train", "validate", "test"):
            for j in range(30):
                gain = 0.2 if (p != "test" or j % 2) else 0.0      # k1.0 better in every period
                rows.append({"period": p, "be": 0.0, "k1.0": gain, "k1.5": 0.3 if p == "train" else -0.1,
                             "k2.0": 0.0})
        chosen, lines = nr.decide(rows)
        self.assertEqual(chosen, "k1.0")
        self.assertIn("k=1.5", lines[1])
        self.assertIn("không đạt", lines[1])                             # good in train only: rejected
        self.assertEqual(nr.period_of(utc(2016, 12, 31, 0, 0)), "train")
        self.assertEqual(nr.period_of(utc(2021, 1, 1, 0, 0)), "test")
        self.assertIsNone(nr.period_of(utc(2026, 1, 1, 0, 0)))


if __name__ == "__main__":
    unittest.main()
