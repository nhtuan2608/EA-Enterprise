"""ProbSetupEA source checks: shadow by default, own magic, orders only behind InpTradeEnabled, closed bars only,
restart-safe position handling, frozen MQL tables = research/long/out/g114_frozen.json, and the Python decision used
by the parity check = the G114 functions."""
from __future__ import annotations

import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
EA = (ROOT / "ProbSetupEA.mq5").read_text(encoding="utf-8-sig")
SIG = (ROOT / "ProbSetup" / "ProbSignals.mqh").read_text(encoding="utf-8-sig")
DEC = (ROOT / "ProbSetup" / "ProbDecide.mqh").read_text(encoding="utf-8-sig")
TAB = (ROOT / "ProbSetup" / "ProbTables.mqh").read_text(encoding="utf-8-sig")
FZ = json.loads((ROOT / "research" / "long" / "out" / "g114_frozen.json").read_text(encoding="utf-8"))


def body(src: str, name: str) -> str:
    i = src.index(name + "(")
    j = src.index("{", i)
    depth, k = 0, j
    while True:
        depth += {"{": 1, "}": -1}.get(src[k], 0)
        if depth == 0:
            return src[j:k + 1]
        k += 1


class ProbSetupEATests(unittest.TestCase):
    def test_shadow_by_default_and_own_magic(self):
        self.assertIn("input bool       InpTradeEnabled = false;", EA)
        self.assertIn("input long       InpMagic        = 141414;", EA)
        for m in ("707070", "717171", "969696", "106106"):
            self.assertNotIn(m, EA)
        self.assertIn("#define PS_PASSED false", TAB)

    def test_orders_only_in_trytrade_behind_the_switch(self):
        calls = [m.start() for m in re.finditer(r"g_trade\.(Buy|Sell)\(", EA)]
        self.assertEqual(len(calls), 2)
        tt = body(EA, "void TryTrade")
        self.assertTrue(tt.lstrip("{ \r\n").startswith("if(!InpTradeEnabled) return;"))
        self.assertIn("g_trade.Buy(", tt)
        self.assertNotIn("OrderSend", EA)
        self.assertEqual(EA.count("PositionClose("), 1)                      # only the 48-bar time stop
        self.assertIn("HasPosition(tk)) return;", tt)                        # one position at a time
        self.assertIn("InpMaxLateSec", tt)                                   # no late entry after a restart

    def test_one_order_per_bar_across_chart_copies(self):
        tt = body(EA, "void TryTrade")
        claim = tt.index("ClaimBar(rt[n-1].time)")
        self.assertLess(claim, tt.index("g_trade.Buy("))
        self.assertIn("HasPosition(tk)) return;", tt[claim:])                # re-checked after the claim
        cb = body(EA, "bool ClaimBar")
        self.assertIn("GlobalVariableSetOnCondition(gv,(double)bar,cur)", cb)
        self.assertIn("if(cur>=(double)bar) return false;", cb)

    def test_restart_safe_no_trade_state(self):
        mp = body(EA, "void ManagePosition")
        self.assertIn("POSITION_TIME", mp)
        self.assertIn("PositionGetInteger(POSITION_MAGIC)==InpMagic", body(EA, "bool HasPosition"))
        oi = body(EA, "int OnInit")
        self.assertNotIn("g_rows", oi)                                       # the ledger is rebuilt from bars

    def test_closed_bars_only(self):
        rf = body(EA, "bool Refresh")
        self.assertIn("CopyRates(_Symbol,PERIOD_H1,1,", rf)
        self.assertIn("CopyRates(_Symbol,PERIOD_H4,1,", rf)
        self.assertIn("CopyRates(_Symbol,PERIOD_D1,1,", rf)
        ps = body(SIG, "int PsSignals")
        self.assertIn("for(int j=MathMax(start,PS_NEWX_BARS+40);j<n-1;j++)", ps)   # the last row is only the entry bar
        self.assertIn("r[e].open", ps)
        self.assertNotIn("r[e].close", ps)
        self.assertNotIn("r[e].high", ps)

    def test_no_shared_runtime(self):
        for src in (EA, SIG, DEC, TAB):
            for bad in ("Runtime/", "Integration/", "EventSetTimer", "CtxLimit/", "AdvisorCore"):
                self.assertNotIn(bad, src)

    def test_constants_match_research(self):
        import g109_setups as gs
        import g112_chase as gc
        import prob_setup_oracle as po
        want = {"PS_IMP_BARS": gc.IMP_BARS, "PS_IMP_ATR": gc.IMP_ATR, "PS_NEWX_BARS": gc.NEWX_BARS, "PS_MAX_BARS": gc.MAX_BARS,
                "PS_MIN_STOP_ATR": gc.MIN_STOP_ATR, "PS_MAX_STOP_ATR": gc.MAX_STOP_ATR,
                "PS_MIN_STOP_SPREADS": gs.MIN_STOP_SPREADS, "PS_MIN_ATR_SPREADS": gs.MIN_ATR5_SPREADS}
        for k, v in want.items():
            m = re.search(rf"#define {k} ([0-9.]+)", SIG)
            self.assertIsNotNone(m, k)
            self.assertEqual(float(m.group(1)), float(v), k)
        self.assertEqual((po.IMP_BARS, po.NEWX_BARS, po.MAX_BARS), (gc.IMP_BARS, gc.NEWX_BARS, gc.MAX_BARS))

    def test_tables_match_frozen_json(self):
        fams = re.findall(r"\{ (\d+), ([-0-9.e]+), ([-0-9.e]+), ([-0-9.e]+), ([-0-9.e]+), (true|false) \}", TAB)
        self.assertEqual(len(fams), len(FZ["families"]))
        for (fid, base, W, L, var, passed), f in zip(fams, FZ["families"]):
            self.assertEqual(int(fid), f["id"])
            for a, b in ((base, f["base"]), (W, f["W"]), (L, f["L"]), (var, f["var"])):
                self.assertEqual(float(a), b)
            self.assertEqual(passed, "false")
        sec = lambda name: TAB[TAB.index(name):TAB.index("};", TAB.index(name))]
        lr = re.findall(r"\{ (\d+), (\d+), (-?\d+), ([-0-9.e]+) \}", sec("PsLr PS_LR[]"))
        want = [(f["id"], w["factor"], w["level"], w["w"]) for f in FZ["families"] for w in f["weights"]]
        self.assertEqual([(int(a), int(b), int(c), float(d)) for a, b, c, d in lr], want)
        bl = re.findall(r"\{ (\d+), ([-0-9.e]+), ([-0-9.e]+), ([-0-9.e]+) \}", sec("PsBlock PS_BLOCKS[]"))
        want = [(f["id"], b["lo"], b["p"], b["n"]) for f in FZ["families"] for b in f["blocks"]]
        self.assertEqual([(int(a), float(b), float(c), float(d)) for a, b, c, d in bl], want)
        los = [float(b) for a, b, c, d in bl]
        for fid in {int(a) for a, *_ in bl}:                                 # blocks sorted by score, p increasing
            fb = [(float(b), float(c)) for a, b, c, d in bl if int(a) == fid]
            self.assertEqual(fb, sorted(fb))
            self.assertTrue(all(fb[k][1] < fb[k + 1][1] for k in range(len(fb) - 1)))
        self.assertEqual(FZ["factors"], ["side", "sess", "d1", "h4", "adx", "vol", "div", "pos"])
        self.assertIn("#define PS_F_POS 7", SIG)

    def test_parity_decision_equals_g114(self):
        import numpy as np
        import pandas as pd
        import g114_prob as gp
        import prob_setup_parity as pp
        f = FZ["families"][0]
        rng = np.random.default_rng(2)
        for _ in range(200):
            lv = [int(rng.choice([-1, 1])), int(rng.integers(0, 3)), int(rng.integers(-1, 2)), int(rng.integers(-1, 2)),
                  int(rng.integers(0, 3)), int(rng.integers(-1, 3)), int(rng.integers(0, 2)), int(rng.integers(0, 3))]
            d = pp.decide(FZ, f["id"], lv)
            tab = {("f_" + FZ["factors"][w["factor"]], w["level"]): w["w"] for w in f["weights"]}
            F = pd.DataFrame([{("f_" + n): v for n, v in zip(FZ["factors"], lv)}])
            s = gp.nb_score(F, f["p0"], tab)[0]
            self.assertAlmostEqual(d["score"], s, places=12)
            blocks = [(b["lo"], b["p"], b["n"]) for b in f["blocks"]]
            p, n = gp.pav_predict(blocks, np.array([s]))
            self.assertAlmostEqual(d["p"], p[0], places=12)
            self.assertAlmostEqual(d["p_lo"], gp.wilson_lower(p[0], n[0]), places=12)
            ev = gp.ev_lower(d["p_lo"], f["W"], f["L"])
            self.assertAlmostEqual(d["ev_lo"], ev, places=12)
            self.assertAlmostEqual(d["kelly"], gp.kelly_size(ev, f["var"]), places=12)

    def test_wilson_formula_same_as_mql(self):
        import g114_prob as gp
        self.assertIn("const double rad=z*MathSqrt(MathMax(p*(1.0-p)/n+z*z/(4.0*n*n),0.0));", DEC)
        self.assertIn("#define PS_Z90 1.6448536269514722", DEC)
        self.assertAlmostEqual(gp.Z90, 1.6448536269514722)


if __name__ == "__main__":
    unittest.main()
