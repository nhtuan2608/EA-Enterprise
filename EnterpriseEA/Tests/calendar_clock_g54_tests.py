"""G54: MT5 calendar times are on today's server clock for every date.

Checked on the export of 07/10/2026: every Nonfarm Payrolls 2010-2026 sits at 15:30 (US summer) or 16:30 (US winter)
calendar time with today's offset UTC+3, i.e. 12:30 / 13:30 UTC; the EURUSD H1 bar that moves is 15:00 server in
winter (bars on UTC+2 then). The old conversion (offset at the event) put winter events one hour late."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))

import context  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


def utc(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp())


class ClockTests(unittest.TestCase):
    """Python mirror of the corrected rule against the NFP facts."""
    NOW_OFFSET = 10800                       # export taken in US summer (UTC+3)
    NOW = utc(2026, 10, 7, 9, 0)

    def convert(self, calendar_time):
        u = calendar_time - self.NOW_OFFSET                                   # EEA_NewsCalendarUtc
        return u, u + context.server_offset_at(u, self.NOW_OFFSET, self.NOW)  # bar clock of that date

    def test_winter_nfp(self):
        cal = utc(2026, 1, 9, 16, 30)        # what MT5 gives: 16:30 on today's UTC+3 clock
        u, server = self.convert(cal)
        self.assertEqual(u, utc(2026, 1, 9, 13, 30))
        self.assertEqual(server, utc(2026, 1, 9, 15, 30))       # winter bars on UTC+2: the 15:00 H1 bar moves
        old = cal - context.server_offset_at(cal - self.NOW_OFFSET, self.NOW_OFFSET, self.NOW)
        self.assertEqual(old - u, 3600)                          # the bug: one hour late

    def test_summer_nfp_unchanged(self):
        cal = utc(2026, 7, 2, 15, 30)
        u, server = self.convert(cal)
        self.assertEqual(u, utc(2026, 7, 2, 12, 30))
        self.assertEqual(server, cal)


class RecorderSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "News" / "NewsReactionRecorder.mqh").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.cal = (ROOT / "News" / "NewsCalendar.mqh").read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_helper(self):
        self.assertIn("long EEA_NewsCalendarUtc(const long calendar_time) { return calendar_time-EEA_NewsServerOffsetSeconds(); }",
                      self.cal)

    def test_record_and_window_use_today_offset_for_utc(self):
        rec = section(self.src, "int EEA_NrRecord(")
        self.assertIn("const long event_utc=(long)value.time-now_offset;", rec)
        self.assertIn("const long offset=EEA_NewsServerOffsetAt(event_utc,now_offset,(long)TimeGMT());", rec)
        self.assertIn("r.event_utc=event_utc;", rec)
        win = section(self.src, "long EEA_NrProcessWindow(")
        self.assertIn("CalendarValueHistory(values,(datetime)(from+now_offset),(datetime)(to+now_offset),NULL,NULL)", win)
        self.assertIn("long T=(long)values[i].time-now_offset;", win)
        self.assertNotIn("EEA_NewsServerOffsetAt", win)

    def test_old_lines_measured_again(self):
        self.assertIn('",\\"time_rule\\":\\"calendar_now_offset\\""', self.src)
        self.assertIn('StringFind(line,"\\"time_rule\\":\\"calendar_now_offset\\"")<0) continue;', self.src)
        self.assertIn('StringFind(json,"news-reaction-backfill-v1.2.0")>=0)', self.src)        # the backfill restarts
        self.assertIn('"{\\"document_version\\":\\"news-reaction-backfill-v1.2.0\\",', self.src)

    def test_calendar_export_format_two_rewrites_every_year(self):
        exp = (ROOT / "Runtime" / "CalendarExport.mqh").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn("#define EEA_CALENDAR_EXPORT_FORMAT 2", exp)
        due = section(exp, "bool EEA_CalendarExportDue(")
        fmt = due.index("!=EEA_CALENDAR_EXPORT_FORMAT) return true;")
        self.assertLess(fmt, due.index("if(year<current_year) return false;"))      # past years too
        self.assertIn('"{\\"format\\":"+IntegerToString(EEA_CALENDAR_EXPORT_FORMAT)', exp)


class ReaderTests(unittest.TestCase):
    def test_reaction_ok(self):
        self.assertTrue(context.reaction_ok({"time_rule": "calendar_now_offset"}))
        self.assertFalse(context.reaction_ok({}))

    def test_every_reader_filters(self):
        for rel in ("research/g10/replay.py", "research/g11/sentiment_news.py", "research/long/news_impact.py",
                    "research/g10/t2_news_be.py"):
            self.assertIn("context.reaction_ok(", (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_t2_news_be_uses_the_bar_clock_of_the_date(self):
        src = (ROOT / "research" / "g10" / "t2_news_be.py").read_text(encoding="utf-8")
        self.assertIn("ev = [x + context.server_offset_at(x, offset, now_utc) for x in news_times(path, s, keys)]", src)
        self.assertNotIn("walk(c, t, ce.T2_RULE, ev, offset", src)

    def test_nfp_check_passes_on_corrected_rows(self):
        import calendar_history as ch
        with tempfile.TemporaryDirectory() as d:
            head = "time_utc,time_server,time_calendar,currency,importance,sector,event_id,name,actual,forecast,previous\n"
            rows = []
            for cal in (utc(2026, 1, 9, 16, 30), utc(2026, 7, 2, 15, 30)):
                u = cal - 10800
                rows.append(f"{u},{u + context.server_offset_at(u, 10800, utc(2026, 10, 7, 0, 0))},{cal},USD,HIGH,0,1,"
                            "Nonfarm Payrolls,,,\n")
            (Path(d) / "calendar_2026.csv").write_text(head + "".join(rows), encoding="utf-8")
            self.assertEqual(ch.nfp_utc_share(ch.load(Path(d))), (2, 1.0))


if __name__ == "__main__":
    unittest.main()
