"""TC-029: floating P/L per local day; the calendar shows "unavailable" when no end-of-day snapshot exists."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_DAYS = 400


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def update(book, day, value, at):
    """Python mirror of EEA_DailyFloatingUpdate: overwrite, keep sorted, drop the oldest beyond capacity."""
    for row in book:
        if row[0] == day:
            row[1], row[2] = value, at
            return
    if len(book) >= MAX_DAYS:
        book.pop(0)
    book.append([day, value, at])
    book.sort(key=lambda r: r[0])


def lookup(book, day):
    return next((r[1] for r in book if r[0] == day), None)


class MirrorTests(unittest.TestCase):
    def test_last_refresh_of_a_day_wins(self):
        book = []
        update(book, 100, 5.0, 1)
        update(book, 100, -3.5, 2)
        self.assertEqual(len(book), 1)
        self.assertEqual(lookup(book, 100), -3.5)

    def test_sorted_and_missing_day_is_unavailable(self):
        book = []
        for d in (102, 100, 101):
            update(book, d, float(d), d)
        self.assertEqual([r[0] for r in book], [100, 101, 102])
        self.assertIsNone(lookup(book, 99))

    def test_capacity_drops_oldest(self):
        book = []
        for d in range(1, MAX_DAYS + 6):
            update(book, d, 1.0, d)
        self.assertEqual(len(book), MAX_DAYS)
        self.assertEqual(book[0][0], 6)
        self.assertIsNone(lookup(book, 5))


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.shell = read("EnterpriseEA.mq5")
        self.store = read("Storage/DailyFloatingStore.mqh")
        self.panel = read("Runtime/SymbolSelectionPanel.mqh")

    def test_store_document(self):
        self.assertIn('"daily-floating-v1.0.0"', self.store)
        self.assertIn("/current/daily_floating.json", self.store)
        self.assertIn("EEA_WriteAtomicText(", self.store)
        self.assertIn("account_fingerprint", self.store)
        self.assertIn("utc_offset_seconds", self.store)

    def test_hook(self):
        body = self.shell.split("void EEA_MaintainDurableState()", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("g_runtime.account.equity-g_runtime.account.balance", body)
        self.assertIn("g_runtime.account.equity>0.0", body)
        self.assertIn("now_utc-g_daily_floating_last_write>=300", body)
        self.assertIn("today_day!=g_daily_floating_last_day", body)
        self.assertIn("EEA_DailyFloatingLoad(", body)
        self.assertIn("EEA_DailyFloatingWrite(", body)

    def test_panel_texts(self):
        self.assertIn('#include "..\Storage\DailyFloatingStore.mqh"', self.panel)
        for text in ("floating EOD unavailable", "floating now ", "floating EOD "):
            self.assertIn(text, self.panel)


if __name__ == "__main__":
    unittest.main()
