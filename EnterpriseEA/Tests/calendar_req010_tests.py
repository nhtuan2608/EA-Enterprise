"""REQ-010 / CHK-CAL-01/02: monthly calendar with money, %, R; day detail; month summary (avg day, max DD, R)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


HAS_VALUE, HAS_START, HAS_MIN = 1, 2, 4


def new_row(day):
    return dict(day=day, value=0.0, flags=0, start_balance=0.0, start_equity=0.0, min_floating=0.0,
                r_sum=0.0, r_best=0.0, r_worst=0.0, r_count=0)


def ensure(book, day):
    for row in book:
        if row["day"] == day:
            return row
    row = new_row(day)
    book.append(row)
    book.sort(key=lambda r: r["day"])
    return row


def observe(book, day, balance, equity):
    """Mirror of EEA_DailyFloatingObserve."""
    row = ensure(book, day)
    floating = equity - balance
    row["value"] = floating
    if not row["flags"] & HAS_START:
        row["start_balance"], row["start_equity"] = balance, equity
        row["flags"] |= HAS_START
    if not row["flags"] & HAS_MIN or floating < row["min_floating"]:
        row["min_floating"] = floating
        row["flags"] |= HAS_MIN
    row["flags"] |= HAS_VALUE


def add_r(book, day, r):
    """Mirror of EEA_DailyFloatingAddR."""
    row = ensure(book, day)
    if row["r_count"] == 0:
        row["r_best"] = row["r_worst"] = r
    else:
        row["r_best"], row["r_worst"] = max(row["r_best"], r), min(row["r_worst"], r)
    row["r_sum"] += r
    row["r_count"] += 1


def cell(mode, active, net, has_start, start_balance, r_count, r_sum):
    """Mirror of EEA_SymbolPanelCalendarCell."""
    if mode == 1:
        if not has_start or start_balance <= 0:
            return "n/a"
        return "%+.2f%%" % (net / start_balance * 100) if active else "0%"
    if mode == 2:
        return "%+.2fR" % r_sum if r_count > 0 else "-"
    return "%+.2f" % net if active else "0"


def month_max_dd(nets):
    cum = peak = dd = 0.0
    for n in nets:
        cum += n
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


class MirrorTests(unittest.TestCase):
    def test_start_is_set_once_and_min_floating_tracks_worst(self):
        book = []
        observe(book, 10, 1000.0, 1000.0)
        observe(book, 10, 1010.0, 985.0)    # floating -25
        observe(book, 10, 1010.0, 1004.0)   # floating -6, min stays -25
        row = book[0]
        self.assertEqual((row["start_balance"], row["start_equity"]), (1000.0, 1000.0))
        self.assertEqual(row["min_floating"], -25.0)
        self.assertEqual(row["value"], -6.0)  # last floating overwrites (TC-029)

    def test_r_aggregation(self):
        book = []
        for r in (1.5, -1.0, 0.5):
            add_r(book, 10, r)
        row = book[0]
        self.assertEqual((row["r_sum"], row["r_best"], row["r_worst"], row["r_count"]), (1.0, 1.5, -1.0, 3))
        self.assertFalse(row["flags"] & HAS_VALUE)  # an R-only row has no floating: stays "unavailable"

    def test_cell_formats(self):
        self.assertEqual(cell(0, True, 12.5, True, 1000, 0, 0), "+12.50")
        self.assertEqual(cell(1, True, 12.5, True, 1000, 0, 0), "+1.25%")
        self.assertEqual(cell(1, True, 12.5, False, 0, 0, 0), "n/a")
        self.assertEqual(cell(2, True, 12.5, True, 1000, 2, 1.25), "+1.25R")
        self.assertEqual(cell(2, True, 12.5, True, 1000, 0, 0), "-")

    def test_month_max_drawdown_is_peak_to_trough_of_cumulative_net(self):
        self.assertEqual(month_max_dd([10, -4, -3, 5, -12, 20]), 14.0)  # cum 10,6,3,8,-4: peak 10 -> trough -4
        self.assertEqual(month_max_dd([-5, 3]), 5.0)
        self.assertEqual(month_max_dd([1, 2]), 0.0)

    def test_average_day(self):
        nets = [10.0, -4.0, 6.0]
        self.assertAlmostEqual(sum(nets) / len(nets), 4.0)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.store = read("Storage/DailyFloatingStore.mqh")
        self.panel = read("Runtime/SymbolSelectionPanel.mqh")
        self.tm = read("Runtime/TradeManagerRuntime.mqh")
        self.shell = read("EnterpriseEA.mq5")

    def test_store_fields_and_v10_compatibility(self):
        for token in ("start_balance", "start_equity", "min_floating", "r_sum", "r_best", "r_worst", "r_count",
                      '"daily-floating-v1.1.0"', "EEA_DAILY_FLOATING_DOCUMENT_V10", "n!=3 && n!=11",
                      "flags=EEA_DAILY_FLOATING_HAS_VALUE;"):
            self.assertIn(token, self.store)
        load = self.store.split("bool EEA_DailyFloatingLoad(", 1)[1]
        self.assertIn("EEA_DAILY_FLOATING_DOCUMENT_V10", load)  # v1.0.0 rows keep start/min/R unknown

    def test_exit_hook(self):
        rec = self.tm.split("void EEA_TradeManagerRecordExit(", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("if(r_known) EEA_DailyFloatingRecordExitR(exit_utc,money/risk);", rec)
        self.assertIn('#include "../Storage/DailyFloatingStore.mqh"', self.tm)
        self.assertEqual(self.tm.count("EEA_TradeManagerRecordExit(audit,root,t,observer.reconciliation,cause);"), 1)
        fn = self.store.split("bool EEA_DailyFloatingRecordExitR(", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("if(!g_daily_floating.loaded) return false;", fn)
        self.assertIn("g_daily_floating.loaded=true;", self.shell)

    def test_toggle(self):
        self.assertIn("int calendar_mode;", self.panel)
        self.assertIn("g_panel_state.calendar_mode=0;", self.panel)
        self.assertIn("(g_panel_state.calendar_mode+1)%3", self.panel)
        self.assertIn('"Btn_CalMode"', self.panel)
        label = self.panel.split("string EEA_SymbolPanelCalendarModeLabel(", 1)[1][:200]
        for text in ('"MONEY"', '"%"', '"R"'):
            self.assertIn(text, label)

    def test_cell_formats_in_source(self):
        fn = self.panel.split("string EEA_SymbolPanelCalendarCell(", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn('return "n/a";', fn)
        self.assertIn("net/start_balance*100.0", fn)
        self.assertIn('"R" : "-"', fn)

    def test_detail_and_summary_texts(self):
        for text in ('"start "', '"return "', '"max floating DD "', '"best R "', '" / worst R "', "best/worst R n/a",
                     "of start equity", '"Month  avg day "', '"max DD "', '"Lbl_CalSummary2"', '"Lbl_CalDetail3"',
                     "month_cum+=net[day]", "month_peak-month_cum", "month_first_start", "detail_y+78", "detail_y+92",
                     "detail_y+108", "EEA_PANEL_INNER_WIDTH,70"):
            self.assertIn(text, self.panel)


if __name__ == "__main__":
    unittest.main()
