"""G29: USD flow flag (EA, Market/UsdFlow.mqh) and the S06B pyramiding shadow (research/g10/pyramid.py,
candidates_eval.py)."""
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research" / "g10"))

import s06_oracle  # noqa: E402
from candidate_ledger_tests import row, synthetic_ctx  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


def mql_usd_flow(eur, gbp, jpy, ema_n=50, bars=400):
    """Mirror of EEA_UsdFlowUpdate: last `bars` closed bars of each, merged on time, EMA seeded with the first value."""
    a, b, c = eur[-bars:], gbp[-bars:], jpy[-bars:]
    k = 2.0 / (ema_n + 1)
    jb = jc = used = 0
    ema = v = 0.0
    t = 0
    for ta, ca in a:
        while jb < len(b) and b[jb][0] < ta:
            jb += 1
        while jc < len(c) and c[jc][0] < ta:
            jc += 1
        if jb >= len(b) or jc >= len(c):
            break
        if b[jb][0] != ta or c[jc][0] != ta:
            continue
        v = (-math.log(ca) - math.log(b[jb][1]) + math.log(c[jc][1])) / 3.0
        ema = v if used == 0 else ema + k * (v - ema)
        t = ta
        used += 1
    if used < 2 * ema_n:
        return 0, 0
    return (1 if v > ema else -1), t


def research_usd_flow(eur, gbp, jpy, ema_n=50):
    """research/long/filters.py usd_index on the full history: time -> flow."""
    series = {}
    for rows, sgn, name in ((eur, -1, "e"), (gbp, -1, "g"), (jpy, 1, "j")):
        for t, c in rows:
            series.setdefault(t, {})[name] = sgn * math.log(c)
    times = sorted(t for t, x in series.items() if len(x) == 3)
    k, e, out = 2.0 / (ema_n + 1), None, {}
    for t in times:
        val = sum(series[t].values()) / 3
        e = val if e is None else e + k * (val - e)
        out[t] = 1 if val > e else -1
    return out


def walk_series(seed, n, start, drop):
    rnd = random.Random(seed)
    p, out = start, []
    for i in range(n):
        p *= math.exp(rnd.gauss(0, 0.002))
        if i % drop:
            out.append((3600 * i, p))
    return out


class UsdFlowMirrorTests(unittest.TestCase):
    def test_mirror_agrees_with_research_index(self):
        eur, gbp, jpy = walk_series(1, 3000, 1.1, 97), walk_series(2, 3000, 1.3, 89), walk_series(3, 3000, 140.0, 83)
        full = research_usd_flow(eur, gbp, jpy)
        agree = total = 0
        for end in range(1000, 3000, 7):              # the EA sees the bars closed up to `end`
            cut = lambda s: [x for x in s if x[0] < 3600 * end]  # noqa: E731
            flow, t = mql_usd_flow(cut(eur), cut(gbp), cut(jpy))
            self.assertIn(t, full)
            total += 1
            agree += flow == full[t]
        self.assertGreaterEqual(agree / total, 0.99)

    def test_alignment_signs(self):
        def align(flow, symbol, d):                   # mirror of EEA_UsdFlowAlignment
            sign = 1 if symbol == "USDJPY" else -1 if symbol in ("EURUSD", "GBPUSD", "XAUUSD", "BTCUSD") else 0
            return 0 if flow == 0 or sign == 0 else (1 if d * sign == flow else -1)
        self.assertEqual(align(1, "EURUSD", -1), 1)     # USD strong: sell EURUSD is aligned
        self.assertEqual(align(1, "USDJPY", 1), 1)
        self.assertEqual(align(-1, "XAUUSD", -1), -1)
        self.assertEqual(align(0, "EURUSD", 1), 0)


class UsdFlowSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Market/UsdFlow.mqh").read_text(encoding="utf-8")
        self.live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_index_definition(self):
        self.assertIn("#define EEA_USD_FLOW_EMA 50", self.src)
        upd = section(self.src, "bool EEA_UsdFlowUpdate(")
        self.assertIn("v=(-MathLog(a[ia].close)-MathLog(b[jb].close)+MathLog(c[jc].close))/3.0;", upd)
        self.assertIn("ema=(used==0 ? v : ema+k*(v-ema));", upd)
        self.assertIn("s.flow=(v>ema ? 1 : -1);", upd)
        self.assertIn("CopyRates(eur,PERIOD_H1,1,EEA_USD_FLOW_BARS,a)", upd)    # closed bars only
        sign = section(self.src, "int EEA_UsdFlowSymbolSign(")
        self.assertIn('if(canonical=="USDJPY") return 1;', sign)

    def test_s06b_live_gate_and_logs(self):
        self.assertIn('#include "../Market/UsdFlow.mqh"', self.live)
        self.assertIn('if(strategy.setup[index]=="S06B" && g_s06b_require_usd_flow)', self.live)
        self.assertIn('if(usd<0) { reason="S06B_COUNTER_USD"; return false; }', self.live)
        self.assertIn('if(usd==0) { reason="S06B_USD_FLOW_UNKNOWN"; return false; }', self.live)
        self.assertIn("EEA_UsdFlowJson(g_usd_flow,engine.canonical_symbol,engine.direction)", self.live)
        ledger = (ROOT / "Integration/CandidateLedger.mqh").read_text(encoding="utf-8")
        self.assertIn("x.usd_json=EEA_UsdFlowJson(g_usd_flow,e.canonical_symbol,e.direction);", ledger)
        self.assertIn('+e.usd_json+', ledger)

    def test_shell(self):
        self.assertIn("EEA_HIDDEN bool InpS06BRequireUsdFlow        = true;", self.shell)
        self.assertIn("g_s06b_require_usd_flow=InpS06BRequireUsdFlow;", self.shell)
        upd = self.shell.index("EEA_UsdFlowUpdateFromObserver(g_usd_flow,g_runtime);")
        self.assertLess(upd, self.shell.index("EEA_S04ShadowOnTimer(g_live_runtime,"))
        self.assertLess(upd, self.shell.index("EEA_ControlledLiveOnTimer(g_live_runtime,"))

    def test_never_trades(self):
        for forbidden in ("OrderSend", "CTrade", "EEA_ExecutionSubmit"):
            self.assertNotIn(forbidden, self.src)


class PyramidTests(unittest.TestCase):
    def setUp(self):
        import candidates_eval
        import pyramid
        import replay
        self.ev, self.pyr, self.replay = candidates_eval, pyramid, replay
        self.ctx = synthetic_ctx()
        self.cands = s06_oracle.run(self.ctx["entry"])

    def plan(self, c):
        cand = {"kind": "MARKET", "i": c["i"], "time": self.ctx["entry"][c["i"]]["time"], "direction": c["direction"],
                "extreme": c["anchor"], "zone_low": c["zone_low"], "zone_high": c["zone_high"],
                "signal_atr": c["signal_atr"], "points": [], "structure": "NEUTRAL"}
        res = self.replay.evaluate(self.ctx, cand, "S06B", "SWING", "tm", dict(self.ev.TRADE["S06B"]))
        t = {"symbol": "EURUSD", "i": c["i"], "dir": c["direction"], "entry": res.get("entry"), "stop": res.get("stop"),
             "target": res.get("target"), "zl": c["zone_low"], "zh": c["zone_high"]}
        return res, t

    def test_current_rule_reproduces_trade_manager(self):
        n = 0
        for c in self.cands:
            res, t = self.plan(c)
            if res["status"] != "EVALUATED":
                continue
            self.assertAlmostEqual(self.pyr.run(self.ctx, t, self.pyr.CURRENT)["r"], res["r"], places=12)
            n += 1
        self.assertGreater(n, 3)

    def test_add_keeps_one_risk_unit(self):
        for c in self.cands:
            res, t = self.plan(c)
            if res["status"] != "EVALUATED":
                continue
            base = self.pyr.run(self.ctx, t, self.pyr.CURRENT)
            j = self.pyr.add_bar(self.ctx, t, 1.0, base["exit_i"])
            added = self.pyr.run(self.ctx, t, self.pyr.CURRENT, 1.0)
            if j is None:
                self.assertAlmostEqual(added["r"], base["r"])
            else:   # the add risks one unit of its own (stop at the first entry): never more, plus its fee
                self.assertGreaterEqual(added["r"] - base["r"], -1.1)
                self.assertGreater(added["exit_i"], j)

    def test_s06b_rows_get_add_and_usd_groups(self):
        rows = []
        for k, c in enumerate(self.cands):
            r = dict(row(c, self.ctx, "NOT_EXECUTED", "SHADOW_MODE"), setup="S06B",
                     usd_alignment="ALIGNED" if k % 2 else "COUNTER")
            rows.append(self.ev.evaluate_row(r, self.ctx))
        self.assertTrue(any("r_add" in e for e in rows))
        rep = self.ev.report(rows)["S06B_SWING"]
        for g in ("ALL", "SHADOW_MODE", "ALL_ADD_1R", "USD_ALIGNED", "USD_COUNTER", "USD_UNKNOWN"):
            self.assertIn(g, rep)
        self.assertEqual(rep["USD_ALIGNED"]["n"] + rep["USD_COUNTER"]["n"], rep["ALL"]["n"])
        self.assertEqual(self.ev.ADD_AT, {"S06B": 1.0})


if __name__ == "__main__":
    unittest.main()
