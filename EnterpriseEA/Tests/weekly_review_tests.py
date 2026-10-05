"""G20: realized result of closed trades (EA), weekly review (research), exit notification,
and retried atomic writes (bridge, gateway)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "g10"))
sys.path.insert(0, str(ROOT / "bridge"))


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class TradeManagerExitTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Runtime/TradeManagerRuntime.mqh").read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_realized_sums_every_deal_and_needs_an_exit_deal(self):
        real = section(self.src, "bool EEA_TradeManagerRealized(")
        self.assertIn("if(r.deals[i].position_id!=t.position_id) continue;", real)
        self.assertIn("money+=r.deals[i].profit+r.deals[i].commission+r.deals[i].swap+r.deals[i].fee;", real)
        self.assertIn('if(r.deals[i].entry!="0" && r.deals[i].time_utc>=exit_utc)', real)
        self.assertIn("return closed;", real)

    def test_r_is_money_over_initial_stop_risk(self):
        risk = section(self.src, "double EEA_TradeManagerInitialRiskMoney(")
        self.assertIn("t.entry_price,t.initial_sl,loss", risk)
        self.assertIn("return MathAbs(loss);", risk)
        rec = section(self.src, "void EEA_TradeManagerRecordExit(")
        self.assertIn('(r_known ? DoubleToString(money/risk,3) : "null")', rec)
        self.assertIn('EEA_WriteAtomicAppendText(root+"/logs/trades.jsonl",line+"\\r\\n");', rec)
        for field in ("candidate_id", "setup", "profile", "symbol", "direction", "entry_price", "initial_sl",
                      "volume", "opened_at_utc", "mfe_r", "mae_r"):
            self.assertIn(f'\\"{field}\\":', rec)

    def test_exit_keeps_the_cause(self):
        self.assertIn('const string cause=t.exit_request!="" ? t.exit_request : t.last_reason;', self.src)
        self.assertIn("EEA_TradeManagerRecordExit(audit,root,t,observer.reconciliation,cause);", self.src)
        self.assertNotIn('EEA_TradeManagerAudit(audit,t,"TRADE_EXITED"', self.src)


def trade(setup, profile, r, money, exit_utc, known=True):
    return {"setup": setup, "profile": profile, "realized_known": known, "realized_r": r if known else None,
            "realized_money": money, "exit_utc": exit_utc}


class WeeklyReviewTests(unittest.TestCase):
    def test_real_summary_and_window(self):
        import weekly_review as wr
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "trades.jsonl"
            rows = [trade("S06", "SWING", 2.5, 25.0, 100), trade("S06", "SWING", -1.0, -10.0, 150),
                    trade("S06", "SWING", None, 0.0, 160, known=False), trade("S02", "SCALP", 1.0, 5.0, 999)]
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            got = wr.load_trades(p, 100, 200)
        self.assertEqual(len(got), 3)
        s = wr.real_summary(got)
        self.assertEqual((s["n"], s["unknown"]), (2, 1))
        self.assertAlmostEqual(s["exp"], 0.75)
        self.assertAlmostEqual(s["money"], 15.0)
        self.assertAlmostEqual(s["win"], 0.5)

    def test_build_and_markdown(self):
        import weekly_review as wr
        evaluated = [
            {"setup": "S06", "profile": "SWING", "group": "EXECUTED", "status": "EVALUATED", "r": 3.0, "time": 1},
            {"setup": "S06", "profile": "SWING", "group": "DUPLICATE_SAME_SIDE", "status": "EVALUATED", "r": -1.0, "time": 2},
            {"setup": "S02", "profile": "SCALP", "group": "NEWS_PRE_NEWS", "status": "NO_BARS_YET", "r": 0.0, "time": 3},
        ]
        review = wr.build([trade("S06", "SWING", 2.4, 24.0, 5)], evaluated)
        s06 = review["S06_SWING"]
        self.assertEqual((s06["real"]["n"], s06["model_exec"]["n"], s06["alone"]["n"]), (1, 1, 2))
        self.assertIn("DUPLICATE_SAME_SIDE", s06["blocked"])
        self.assertEqual(review["S02_SCALP"]["no_bars_yet"], 1)
        md = wr.markdown(review, 0, 7 * 86400)
        self.assertIn("| S06_SWING | n=1 exp=+2.40R win=100% tiền +24.00 | n=1 exp=+3.00R", md)
        self.assertIn("+0.10R", md)
        self.assertIn("chưa đủ nến: 1", md)


class ExitNotificationTests(unittest.TestCase):
    def test_exit_message_carries_realized_result(self):
        import telegram_gateway as tg
        from telegram_gateway_tests import FakeApi
        with tempfile.TemporaryDirectory() as d:
            cfg = tg.load_config(None)
            cfg.update(operators=[1])
            gw = tg.Gateway(Path(d), cfg, FakeApi(), "", clock=lambda: 1_800_000_000)
            gw.audit_event({"event_type": "TRADE_EXITED", "symbol": "XAUUSD", "entity_id": "S06-x",
                            "details": {"profile": "SWING", "realized_known": True, "realized_r": 2.95,
                                        "realized_money": 29.5, "exit_cause": "TAKE_PROFIT"}})
            gw.audit_event({"event_type": "TRADE_EXITED", "symbol": "EURUSD", "entity_id": "S02-x",
                            "details": {"realized_known": False}})
            texts = [m["text"] for m in gw.state["outbox"]]
        self.assertIn("Kết quả: +2.95R (+29.50)  thoát: TAKE_PROFIT", texts[0])
        self.assertIn("chưa thấy deal đóng", texts[1])


class AtomicRetryTests(unittest.TestCase):
    def check(self, writer):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "x.json"
            real = os.replace
            calls = {"n": 0}

            def flaky(src, dst):
                calls["n"] += 1
                if calls["n"] < 3:
                    raise PermissionError("locked")
                return real(src, dst)
            with mock.patch("os.replace", flaky), mock.patch("time.sleep"):
                writer(target, {"a": 1})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})
            self.assertEqual(calls["n"], 3)

    def test_gateway_retries_locked_target(self):
        import telegram_gateway as tg
        self.check(tg.write_atomic)

    def test_bridge_retries_locked_target(self):
        import ai_bridge
        self.check(ai_bridge.Bridge._write_atomic)


if __name__ == "__main__":
    unittest.main()
