"""G48: signal parity between the live EA and the research generators (research/g10/signal_parity.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))

import signal_parity as sp  # noqa: E402


class PureTests(unittest.TestCase):
    def test_online_needs_a_refresh_soon_after_the_close(self):
        refreshes = [1000, 1030, 5000]
        self.assertTrue(sp.online(1000, refreshes))
        self.assertTrue(sp.online(4500, refreshes))           # 500 s later
        self.assertFalse(sp.online(2000, refreshes))          # next refresh 3000 s later: PC off / EA removed
        self.assertFalse(sp.online(6000, refreshes))

    def test_compare_splits_match_missed_offline_extra(self):
        a, b, c, d = ("T2", "XAUUSD", 1, 100), ("T2", "XAUUSD", -1, 200), ("T2", "BTCUSD", 1, 300), ("T2", "BTCUSD", 1, 400)
        research, ea = {a, b, c}, {a, d}
        close = {b: 1000, c: 9000}
        out = sp.compare(research, ea, close, refreshes=[1100, 20000])
        self.assertEqual(out["MATCH"], [a])
        self.assertEqual(out["EA_EXTRA"], [d])
        self.assertEqual(out["EA_MISSED"], [b])                # EA was running
        self.assertEqual(out["EA_OFFLINE"], [c])               # no refresh within 10 minutes

    def test_daily_closes_from_h1_by_server_day(self):
        day = 86400 * 20000
        h1 = [{"time": day + h * 3600, "close": 1.0 + h} for h in range(24)] + [{"time": day + 86400, "close": 9.0}]
        d = sp.daily_from_h1(h1)
        self.assertEqual([x["time"] for x in d], [day, day + 86400])
        self.assertEqual(d[0]["close"], 24.0)                  # last H1 close of the server day

    def test_text_flags_differences(self):
        res = {"S04": {"MATCH": [1, 2], "EA_MISSED": [], "EA_EXTRA": [], "EA_OFFLINE": [3]},
               "T2": {"MATCH": [], "EA_MISSED": [1], "EA_EXTRA": [], "EA_OFFLINE": []},
               "replay": {"S04 SWING": {"ea": 30, "research": 30, "match": 30, "ea_only": [], "research_only": []}}}
        txt = sp.text(res)
        self.assertIn("S04: khớp 2, EA bỏ sót 0, EA thừa 0, lúc EA tắt 1 (100%)", txt)
        self.assertIn("T2: khớp 0, EA bỏ sót 1", txt)
        self.assertIn("CẦN XEM", txt)
        self.assertIn("Replay lịch sử của EA S04 SWING: khớp 30/30", txt)

    def test_heartbeat_when_no_signal_in_the_window(self):
        empty = {"MATCH": [], "EA_MISSED": [], "EA_EXTRA": [], "EA_OFFLINE": []}
        txt = sp.text({"T2": dict(empty, heartbeat=["T2", "EURUSD", -1, 1_790_870_400])})
        self.assertIn("nghiên cứu: tín hiệu gần nhất trước mốc EURUSD", txt)
        txt = sp.text({"T2": dict(empty, heartbeat=None)})
        self.assertIn("KHÔNG có tín hiệu nào", txt)                # silence before the window = check the tool
        txt = sp.text({"T2": dict(empty, MATCH=[1])})
        self.assertNotIn("gần nhất", txt)

    def test_every_selected_symbol_is_checked(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "current").mkdir()
            (root / "current" / "symbol_selection.json").write_text(
                json.dumps({"canonical_symbols": ["XAUUSD", "BTCUSD", "EURUSD"]}), encoding="utf-8")
            rows = [{"symbol": "GBPUSD"}]
            self.assertEqual(sp.ea_symbols(root, rows), ["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD"])
            (root / "current" / "symbol_selection.json").unlink()
            self.assertEqual(sp.ea_symbols(root, []), sorted(sp.DEFAULT_SYMBOLS))

    def test_t2_uses_d1_bars_when_present(self):
        src = (ROOT / "research" / "g10" / "signal_parity.py").read_text(encoding="utf-8")
        self.assertIn('daily = context.load_bars(symbol, "D1")[-1000:] if d1_path.exists() else daily_from_h1(h1)', src)
        self.assertIn('context.DATA, context.CACHE = scratch, scratch / ".cache"', src)   # live mode never touches the export cache

    def test_t2_only_symbols_match_the_ea_default_and_run_t2_alone(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        line = shell.split("EEA_HIDDEN string InpT2OnlySymbols", 1)[1].split(";", 1)[0]
        self.assertEqual(tuple(line.split('"')[1].split(",")), sp.T2_ONLY)
        calls = []
        orig = sp.research_keys, sp.ce.load, sp.refresh_times, sp.ea_symbols, dict(sp.SYMBOL_START)
        try:
            sp.research_keys = lambda s, setup, start: (calls.append((s, setup)) or (set(), {}, 0))
            sp.ce.load = lambda path, since: []
            sp.refresh_times = lambda audit, since: []
            sp.ea_symbols = lambda root, rows: ["EURUSD", "XAGUSD", "ETHUSD"]
            sp.SYMBOL_START.clear()
            sp.SYMBOL_START["XAGUSD"] = sp.START["T2"] + 86400
            r = sp.run(root=Path("."))
        finally:
            sp.research_keys, sp.ce.load, sp.refresh_times, sp.ea_symbols = orig[:4]
            sp.SYMBOL_START.clear(); sp.SYMBOL_START.update(orig[4])
        self.assertEqual(sorted(calls), [("EURUSD", "S04"), ("EURUSD", "S06B"), ("EURUSD", "T2"), ("XAGUSD", "T2")])
        self.assertEqual(r["not_followed"], ["ETHUSD"])         # no start yet: never counted as missed
        self.assertIn("T2 chưa có mốc theo dõi (chưa so): ETHUSD", sp.text(r))

    def test_starts_follow_the_deploys(self):
        self.assertLess(sp.START["S04"], sp.START["S06B"])
        self.assertLess(sp.START["S06B"], sp.START["T2"])     # T2 counted from the G44 momentum filter only
        self.assertEqual(sp.S06B, {"box": 24, "max_box_atr": 3.0, "contraction": 0.85, "mode": "immediate", "sl": "far"})


if __name__ == "__main__":
    unittest.main()
