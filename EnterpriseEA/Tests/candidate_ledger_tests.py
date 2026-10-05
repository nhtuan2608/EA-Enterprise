"""G18 candidate ledger (EA side) and virtual-result report (research/g10/candidates_eval.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research" / "g10"))

import s06_oracle  # noqa: E402
from s06_compression_expansion_tests import synthetic_bars  # noqa: E402


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class LedgerSourceTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Integration/CandidateLedger.mqh").read_text(encoding="utf-8")
        self.update = section(self.src, "bool EEA_CandidateLedgerUpdate(")

    def test_line_carries_what_the_offline_model_needs(self):
        line = section(self.src, "string EEA_CandidateLedgerLine(")
        for field in ("candidate_id", "setup", "profile", "symbol", "timeframe", "direction", "bar_time",
                      "extreme", "zone_low", "zone_high", "signal_atr", "key_level", "mode", "disposition",
                      "reason", "entry_kind", "first_seen_utc", "closed_utc"):
            self.assertIn(f'\\"{field}\\":', line)
        self.assertIn('return root+"/logs/candidates.jsonl";', self.src)

    def test_triggered_and_placed_candidates_are_tracked(self):
        self.assertIn("if(!triggered && !in_trade && !in_pending) continue;", self.update)
        self.assertIn("if(mode==EEA_S04_MODE_OFF) continue;", self.update)
        self.assertIn("EEA_CandidateLedgerWritten(l,id)", self.update)

    def test_outcome_written_once_when_final(self):
        # Kept while still TRIGGERED and not entered; written when entered or gone.
        self.assertIn("if(l.items[k].seen && !l.items[k].executed) continue;", self.update)
        self.assertIn("l.written[l.written_next]=l.items[k].candidate_id;", self.update)

    def test_reasons(self):
        reason = section(self.src, "string EEA_CandidateLedgerReason(")
        self.assertIn('if(mode==EEA_S04_MODE_SHADOW) return "SHADOW_MODE";', reason)
        self.assertIn('if(!live_armed) return "LIVE_NOT_ARMED";', reason)
        self.assertIn("live.reason_candidate[engine]==id", reason)
        self.assertIn('return "NOT_EVALUATED:"+live.last_reason;', reason)

    def test_shell_updates_ledger_after_entry_pass(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        live = shell.index("EEA_ControlledLiveOnTimer(g_live_runtime,")
        ledger = shell.index("EEA_CandidateLedgerUpdate(g_candidate_ledger,")
        self.assertLess(live, ledger)
        self.assertIn("EEA_CandidateLedgerInit(g_candidate_ledger);", shell)

    def test_ledger_never_trades(self):
        for forbidden in ("OrderSend", "CTrade", "EEA_ExecutionSubmit"):
            self.assertNotIn(forbidden, self.src)


def synthetic_ctx():
    bars = synthetic_bars(7)
    for b in bars:
        b["utc"] = b["time"]
    return {"symbol": "EURUSD", "profile": "SWING", "point": 0.00001, "from_server": 0, "entry": bars,
            "bar_level": [0] * len(bars), "levels": {0: {"points": [], "structure": "NEUTRAL"}}}


def row(c, ctx, disposition="NOT_EXECUTED", reason="DUPLICATE_SAME_SIDE", bar_time=None):
    return {"candidate_id": f"S06-EURUSD-H1-{c['i']}", "setup": "S06", "profile": "SWING", "symbol": "EURUSD",
            "direction": c["direction"], "bar_time": ctx["entry"][c["i"]]["time"] if bar_time is None else bar_time,
            "extreme": c["anchor"], "zone_low": c["zone_low"], "zone_high": c["zone_high"],
            "signal_atr": c["signal_atr"], "disposition": disposition, "reason": reason, "closed_utc": 1}


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        import candidates_eval
        self.ev = candidates_eval
        self.ctx = synthetic_ctx()
        self.cands = s06_oracle.run(self.ctx["entry"])
        self.assertGreater(len(self.cands), 5)

    def test_virtual_result_matches_research_evaluate(self):
        import replay
        c = self.cands[0]
        got = self.ev.evaluate_row(row(c, self.ctx), self.ctx)
        cand = {"kind": "MARKET", "i": c["i"], "time": self.ctx["entry"][c["i"]]["time"], "direction": c["direction"],
                "extreme": c["anchor"], "zone_low": c["zone_low"], "zone_high": c["zone_high"],
                "signal_atr": c["signal_atr"], "points": [], "structure": "NEUTRAL"}
        want = replay.evaluate(self.ctx, cand, "S06", "SWING", "tm", dict(self.ev.TRADE["S06"]))
        self.assertEqual(got["status"], want["status"])
        self.assertAlmostEqual(got["r"], want.get("r", 0.0))

    def test_unknown_bar_is_no_bars_yet(self):
        got = self.ev.evaluate_row(row(self.cands[0], self.ctx, bar_time=1), self.ctx)
        self.assertEqual(got["status"], "NO_BARS_YET")

    def test_unfinished_trade_is_no_bars_yet(self):
        ctx = dict(self.ctx, entry=self.ctx["entry"][:self.cands[-1]["i"] + 3])
        got = self.ev.evaluate_row(row(self.cands[-1], ctx), ctx)
        self.assertIn(got["status"], ("NO_BARS_YET", "EVALUATED"))
        if got["status"] == "EVALUATED":
            self.assertNotEqual(got.get("result"), "OPEN")

    def test_report_groups_by_outcome(self):
        rows = []
        for k, c in enumerate(self.cands):
            r = row(c, self.ctx, *(("EXECUTED", "EXECUTED") if k % 2 == 0 else ("NOT_EXECUTED", "NOT_EVALUATED:X")))
            rows.append(self.ev.evaluate_row(r, self.ctx))
        rep = self.ev.report(rows)["S06_SWING"]
        self.assertEqual(set(rep), {"ALL", "EXECUTED", "NOT_EVALUATED", "NO_BARS_YET"})
        self.assertEqual(rep["ALL"]["n"], rep["EXECUTED"]["n"] + rep["NOT_EVALUATED"]["n"])

    def test_load_filters_by_close_time(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "candidates.jsonl"
            p.write_text("\n".join(json.dumps({"closed_utc": t}) for t in (10, 20, 30)) + "\n", encoding="utf-8")
            self.assertEqual(len(self.ev.load(p, 20)), 2)
            self.assertEqual(self.ev.load(Path(d) / "missing.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
