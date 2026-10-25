"""AI council step 3b-2: EA context export (source checks) and bridge/council_market.py on synthetic bars with known answers."""
from __future__ import annotations

import calendar
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
import council_market as cm  # noqa: E402

T_END = calendar.timegm((2026, 10, 22, 14, 0, 0))     # Thursday 14:00 server
OFF = 7200


def doc(last=None, spread_now=20, gap=False, missing=False, regime_up=True, written=None):
    m30 = []
    n = 1000
    for k in range(n):
        t = T_END - (n - 1 - k) * 1800
        p = 4000 + 0.05 * k
        m30.append([t, p, p + 1.0, p - 1.0, p + 0.02, 1000, 20])
    if missing:
        del m30[-10:-4]                              # a 3.5 h hole on Thursday
    if gap:
        m30[-20][1] = m30[-21][4] + 30.0             # treated as the first bar after a weekend below
        m30 = [r if i < len(m30) - 20 else [r[0] + 2 * 86400] + r[1:] for i, r in enumerate(m30)]
    if last:
        m30[-1] = [m30[-1][0]] + last
    day0 = (T_END // 86400 - 1) * 86400
    d1 = []
    for k in range(300):
        t = day0 - (299 - k) * 86400
        p = 3000 + (k if regime_up else -k) * 3.0
        d1.append([t, p, p + 20, p - 20, p + (1 if regime_up else -1)])
    h4 = [[T_END - (249 - k) * 14400, 3800 + k, 3801 + k, 3799 + k, 3800.5 + k] for k in range(250)]
    return {"document_version": "council-context-v1", "symbol": "XAUUSD-VIP", "written_at_utc": written or T_END - OFF + 1800 + 60,
            "server_offset": OFF, "point": 0.01, "digits": 2, "bid": 4050.0, "ask": 4050.0 + spread_now * 0.01,
            "m30": m30, "h4": h4, "d1": d1}


NOW = T_END - OFF + 1800 + 90                           # just after the last bar closed (UTC)


class MarketTests(unittest.TestCase):
    def test_state_card(self):
        a = cm.analyse(doc(), NOW)
        g = a["gia"]
        self.assertEqual(g["che_do_d1"], 1)
        self.assertEqual(g["sma50_200_d1"], 1)
        self.assertEqual(g["phia_ema200_h4"], 1)
        self.assertAlmostEqual(g["atr14_m30"], 2.0, delta=0.15)
        self.assertIn("không dùng để đoán hướng", g["ghi_chu"])
        self.assertEqual(a["bat_thuong"], [])
        self.assertTrue(any(s["ten"] == "4 khung cùng chiều" for s in a["tinh_huong"]))

    def test_down_regime(self):
        self.assertEqual(cm.analyse(doc(regime_up=False), NOW)["gia"]["che_do_d1"], -1)

    def test_sweep_of_previous_day_low(self):
        d = doc()
        pdl = d["d1"][-1][3]
        a = cm.analyse(doc(last=[pdl + 2, pdl + 3, pdl - 5, pdl + 1, 1000, 20]), NOW)
        names = [s["ten"] for s in a["tinh_huong"]]
        self.assertIn("quét PDL rồi rút cùng chiều D1", names)
        self.assertTrue(all("C18" in s["ghi_chu"] for s in a["tinh_huong"]))

    def test_anomalies(self):
        self.assertTrue(any(b["khoa"].startswith("spread:") for b in cm.analyse(doc(spread_now=80), NOW)["bat_thuong"]))
        p = 4000 + 0.05 * 999
        big = cm.analyse(doc(last=[p, p + 12, p - 1, p + 10, 1000, 20]), NOW)["bat_thuong"]
        self.assertTrue(any(b["khoa"].startswith("bigbar:") for b in big))
        self.assertTrue(any(b["khoa"].startswith("missing:") for b in cm.analyse(doc(missing=True), NOW)["bat_thuong"]))
        self.assertTrue(any(b["khoa"].startswith("gap:") for b in cm.analyse(doc(gap=True), NOW + 2 * 86400)["bat_thuong"]))
        stale = cm.analyse(doc(written=NOW - 3600), NOW)["bat_thuong"]
        self.assertTrue(any(b["khoa"].startswith("ctxstale:") for b in stale))

    def test_load_and_council_context(self):
        import council
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "current" / "council").mkdir(parents=True)
            (root / "logs").mkdir()
            (root / "current" / "council" / "context.json").write_text(json.dumps(doc(spread_now=80)), encoding="utf-8")
            c = council.Council(root, council.load_config(None), call=lambda *a: "{}", clock=lambda: NOW)
            ctx = c.context({"loai": "thuc_thi"})
            self.assertIn("the_trang_thai", ctx["gia"])
            trig = c.triggers()
            self.assertTrue(any(t["khoa"].startswith("spread:") and t["loai"] == "thuc_thi" for t in trig))

    def test_short_file_is_safe(self):
        a = cm.analyse({"m30": [[0, 1, 1, 1, 1, 1, 1]]}, NOW)
        self.assertEqual(a["bat_thuong"], [])


class ExportSourceTests(unittest.TestCase):
    def test_export(self):
        src = (ROOT / "Runtime" / "CouncilContext.mqh").read_text(encoding="utf-8-sig")
        for token in ('"council-context-v1"', "EEA_COUNCIL_M30_BARS 1000", "EEA_COUNCIL_H4_BARS 250", "EEA_COUNCIL_D1_BARS 300",
                      "CopyRates(sym,tf,1,count,r)", '"/current/council/context.json"', "EEA_WriteAtomicText", "bar==g_council_context_bar",
                      '\\"server_offset\\":', '\\"bid\\":', '\\"ask\\":', "r[i].tick_volume", "r[i].spread"):
            self.assertIn(token, src)
        for token in ("OrderSend", "CTrade", "PositionClose"):
            self.assertNotIn(token, src)
        ea = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8-sig")
        self.assertIn('#include "Runtime/CouncilContext.mqh"', ea)
        self.assertIn("input bool   InpCouncilContext          = true;", ea)
        self.assertIn("EEA_CouncilContextTimer(g_config.data_root,InpBotsSymbol);", ea)
        self.assertIn("g_council_context_enabled=InpCouncilContext;", ea)


if __name__ == "__main__":
    unittest.main()
