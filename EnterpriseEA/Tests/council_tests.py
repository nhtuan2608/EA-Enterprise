"""AI council step 3b-1 (docs/superpowers/plans/2026-10-25-council-3b.md): validator, budget, triggers, judge rules, CUSUM,
no command files. The model is faked; nothing is called."""
from __future__ import annotations

import json
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
import council  # noqa: E402
import council_prompts as cp  # noqa: E402
import council_rules as cr  # noqa: E402

T0 = 1_793_000_000          # a Thursday (market open)


def answer(role, **kw):
    a = {"agent": role, "de_xuat": "giu_nguyen", "muc_tu_tin": "vua",
         "ly_do": [{"noi_dung": "mặc định để luật bot quyết", "dan_chung": ["D"]}]}
    if role == "tham_phan":
        a.update(phan_quyet="giu_nguyen", thoi_han_phut=60, ke_hoach=[], tom_tat_vi="Giữ nguyên.")
    a.update(kw)
    return a


class FakeModel:
    def __init__(self, overrides=None, fail=()):
        self.calls = []
        self.overrides = overrides or {}
        self.fail = set(fail)

    def __call__(self, model, prompt, cfg):
        role = next(r for r in cp.ROLES if f"Bạn là '{r}'" in prompt)
        self.calls.append((role, model, prompt))
        if role in self.fail:
            raise RuntimeError("down")
        return "Đây là trả lời:\n" + json.dumps(self.overrides.get(role, answer(role)), ensure_ascii=False)


class Env:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ("current", "logs", "research/calendar", "current/commands", "current/remote"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.t = T0
        self.status(near=0.2, open_=0)
        self.live(T0)
        self.write("account_snapshot.json", {"balance": 10000, "equity": 10000})
        self.write("news_state.json", {"symbols": [{"symbol": "XAUUSD", "state": "NORMAL", "next": "", "next_utc": 0}]})
        (self.root / "research/calendar/calendar_2026.csv").write_text(
            "time_utc,time_server,time_calendar,currency,importance,sector,event_id,name,actual,forecast,previous\n", encoding="utf-8")

    def write(self, name, obj):
        (self.root / "current" / name).write_text(json.dumps(obj), encoding="utf-8")

    def status(self, near=0.2, open_=0, open_risk=0.0, day0=10000):
        self.write("bots_status.json", {"guard": {"capital": 10000, "day_start_equity": day0, "daily_loss_pct": 6.0,
                                                  "open_risk_pct": open_risk, "max_open_risk_pct": 12.0},
                                        "bots": [{"code": "S07", "mode": "LIVE", "active": True, "open": open_, "near": near,
                                                  "status": "", "near_text": ""}]})

    def live(self, written):
        self.write("live_status.json", {"written_at_utc": written, "session": "ACTIVE", "modes": {"S07": "LIVE"}})

    def news(self, at, name="CPI m/m"):
        with (self.root / "research/calendar/calendar_2026.csv").open("a", encoding="utf-8") as f:
            f.write(f"{at},{at + 7200},{at + 10800},USD,HIGH,4,1,{name},,0.3,0.2\n")

    def journal(self, event, bot="S07", mode="LIVE", **data):
        p = self.root / "logs" / f"bots-{time.strftime('%Y%m', time.gmtime(self.t))}.jsonl"
        self.t += 1
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at_utc": self.t, "server": "", "bot": bot, "event": event, "mode": mode, "text": event, "data": data}) + "\n")

    def council(self, model=None):
        cfg = council.load_config(None)
        return council.Council(self.root, cfg, call=model or FakeModel(), clock=lambda: self.t)


# ------------------------------------------------------------------------------------------------------------- 1. validator
class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.codes = cr.kb_codes()
        self.ctx = {"tin": {"su_kien": [{"ten": "CPI"}]}}

    def test_codes_parsed(self):
        for c in ("A1", "A14", "B8", "B21", "C11", "C18", "E2", "D"):
            self.assertIn(c, self.codes)

    def test_valid_answer_kept(self):
        a = answer("tin_tuc", ly_do=[{"noi_dung": "tin CPI", "dan_chung": ["ctx.tin.su_kien.0.ten", "A14"]}])
        ok, p = cr.validate("tin_tuc", a, self.codes, self.ctx)
        self.assertTrue(ok, p)

    def test_rejections(self):
        cases = {
            "menu": answer("tin_tuc", de_xuat="mo_lenh_mua"),
            "no evidence": answer("tin_tuc", ly_do=[{"noi_dung": "cảm thấy", "dan_chung": []}]),
            "unknown code": answer("tin_tuc", ly_do=[{"noi_dung": "x", "dan_chung": ["A999"]}]),
            "missing field": answer("tin_tuc", ly_do=[{"noi_dung": "x", "dan_chung": ["ctx.tin.khong_co"]}]),
            "C as reason": answer("tin_tuc", ly_do=[{"noi_dung": "trước tin hay đảo", "dan_chung": ["C18"]}]),
            "wrong agent": answer("thuc_thi"),
        }
        for name, a in cases.items():
            ok, _ = cr.validate("tin_tuc", a, self.codes, self.ctx)
            self.assertFalse(ok, name)
        self.assertFalse(cr.validate("tin_tuc", None, self.codes, self.ctx)[0])

    def test_c_allowed_to_reject(self):
        a = answer("phan_bien", ly_do=[{"noi_dung": "tình huống không báo hướng", "dan_chung": ["C18"]}],
                   bac_bo=[{"doi_tuong": "tin_tuc: giá sẽ đảo", "dan_chung": ["C18", "B8"]}])
        self.assertTrue(cr.validate("phan_bien", a, self.codes, self.ctx)[0])

    def test_judge_fields(self):
        bad = answer("tham_phan", thoi_han_phut=9999)
        self.assertFalse(cr.validate("tham_phan", bad, self.codes, self.ctx)[0])
        bad = answer("tham_phan", ke_hoach=[{"neu": "giá > 4000", "thi": "mua_them"}])
        self.assertFalse(cr.validate("tham_phan", bad, self.codes, self.ctx)[0])
        self.assertTrue(cr.validate("tham_phan", answer("tham_phan"), self.codes, self.ctx)[0])

    def test_role_sees_only_its_slice_and_codes(self):
        ctx = {"thoi_gian": 1, "kich_hoat": 2, "tin": 3, "bot": 4, "mo_neo": 5, "thuc_thi": 6, "giam_sat": 7, "tai_khoan": 8}
        self.assertEqual(set(cp.slice_ctx("tin_tuc", ctx)), {"thoi_gian", "kich_hoat", "tin", "bot", "mo_neo"})
        self.assertNotIn("A1", cp.allowed_codes("tin_tuc", self.codes))
        self.assertIn("C5", cp.allowed_codes("phan_bien", self.codes))
        self.assertEqual(cp.allowed_codes("tham_phan", self.codes), self.codes)
        prompt = cp.build("tin_tuc", ctx, self.codes)
        self.assertIn("| A14 |", prompt)
        self.assertNotIn("| A1 |", prompt)


# ------------------------------------------------------------------------------------------------------------- 2. budget
class BudgetTests(unittest.TestCase):
    def test_limit_day_roll_and_low(self):
        t = [T0]
        st = {}
        b = cr.Budget(st, 20, 6, 3, clock=lambda: t[0])
        for _ in range(25):
            if b.left() > 0:
                b.spend()
        self.assertEqual(b.left(), 0)
        self.assertFalse(b.can_meet(1, 1)[0])
        t[0] += 86400
        self.assertEqual(b.left(), 20)
        for _ in range(14):
            b.spend()
        self.assertTrue(b.can_meet(2, 4)[0])
        self.assertFalse(b.can_meet(3, 4)[0])
        self.assertFalse(b.can_meet(4, 4)[0])

    def test_never_over_20_calls_in_a_day(self):
        env = Env()
        env.status(near=0.9, open_=1)
        model = FakeModel()
        c = env.council(model)
        for k in range(10):                       # many triggers in one day
            env.news(env.t + 1800 + k * 7200)
            env.journal("FILL", position=k)
            env.journal("ERROR")
            c.tick()
            env.t += 600
        self.assertLessEqual(len(model.calls), 20)
        self.assertLessEqual(c.state["calls"], 20)


# ------------------------------------------------------------------------------------------------------------- 3. triggers
class TriggerTests(unittest.TestCase):
    def test_news_needs_exposure_and_groups_once(self):
        env = Env()
        env.news(T0 + 1800, "CPI m/m")
        env.news(T0 + 1800, "Core CPI m/m")
        model = FakeModel()
        c = env.council(model)
        c.tick()
        self.assertEqual(model.calls, [])        # nothing open, no bot close to a signal
        env.status(near=0.9)
        env.news(T0 + 2400, "CPI y/y")
        c = env.council(model)
        c.tick()
        roles = [r for r, _, _ in model.calls]
        self.assertEqual(roles, ["tin_tuc", "logic_bot", "phan_bien", "tham_phan"])
        c.tick()
        self.assertEqual(len(model.calls), 4)    # same event: no second meeting
        rec = json.loads((env.root / "logs").glob("council-*.jsonl").__next__().read_text(encoding="utf-8").splitlines()[-1])
        self.assertIn("CPI m/m", rec["kich_hoat"]["mo_ta"])
        self.assertIn("Core CPI m/m", rec["kich_hoat"]["mo_ta"])

    def test_fill_and_error(self):
        env = Env()
        model = FakeModel()
        c = env.council(model)
        env.journal("FILL", position=77)
        c.tick()
        self.assertEqual([r for r, _, _ in model.calls], ["logic_bot", "phan_bien", "tham_phan"])
        env.journal("ERROR")
        c.tick()
        self.assertEqual([r for r, _, _ in model.calls][3:], ["thuc_thi", "logic_bot", "phan_bien", "tham_phan"])
        c.tick()
        self.assertEqual(len(model.calls), 7)

    def test_stale_status_and_daily_loss(self):
        env = Env()
        env.live(T0 - 600)
        env.status(day0=10500)                   # equity 10000: -5 % of 10000 vs 6 % limit -> 83 %
        model = FakeModel()
        c = env.council(model)
        trig = c.triggers()
        kinds = sorted(t["khoa"].split(":")[0] for t in trig)
        self.assertEqual(kinds, ["loss", "stale"])
        self.assertTrue(all(t["loai"] == "thuc_thi" for t in trig))

    def test_council_lines_are_not_read_back(self):
        env = Env()
        model = FakeModel()
        c = env.council(model)
        env.journal("FILL", position=1)
        c.tick()
        c.tick()
        self.assertEqual(len(model.calls), 3)
        lines = (env.root / "logs" / f"bots-{time.strftime('%Y%m', time.gmtime(env.t))}.jsonl").read_text(encoding="utf-8")
        self.assertIn('"bot":"COUNCIL"', lines)


# ------------------------------------------------------------------------------------------------------------- 4. judge
class JudgeTests(unittest.TestCase):
    def test_clamp_to_anchor(self):
        a = answer("tham_phan", xac_suat={"huong_sau_pha_muc_vang": 0.8, "khac": 0.9})
        notes = cr.judge_clamp(a, cr.ANCHOR)
        self.assertAlmostEqual(a["xac_suat"]["huong_sau_pha_muc_vang"], 0.56)
        self.assertEqual(a["xac_suat"]["khac"], 0.9)
        self.assertEqual(len(notes), 1)

    def test_invalid_or_failed_judge_keeps_rules(self):
        env = Env()
        for model in (FakeModel(overrides={"tham_phan": answer("tham_phan", phan_quyet="mua")}), FakeModel(fail={"tham_phan"})):
            c = env.council(model)
            env.journal("FILL", position=random.randint(1000, 9999))
            rec = None
            c.tick()
            rec = json.loads(sorted((env.root / "logs").glob("council-*.jsonl"))[-1].read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(rec["phan_quyet"]["phan_quyet"], "giu_nguyen")
            self.assertFalse(rec["tham_phan"]["hop_le"])

    def test_failed_analyst_is_logged_not_fatal(self):
        env = Env()
        model = FakeModel(fail={"logic_bot"})
        c = env.council(model)
        env.journal("FILL", position=5)
        c.tick()
        rec = json.loads(sorted((env.root / "logs").glob("council-*.jsonl"))[-1].read_text(encoding="utf-8").splitlines()[-1])
        self.assertFalse(rec["vong1"][0]["hop_le"])
        self.assertTrue(rec["tham_phan"]["hop_le"])


# ------------------------------------------------------------------------------------------------------------- 5. CUSUM
class CusumTests(unittest.TestCase):
    def setUp(self):
        fp = cr.load_fingerprints()["S07"]
        self.mu, self.sd = fp["mu"], fp["sigma"]

    def test_normal_stream_rarely_alarms(self):
        rng = random.Random(1)
        alarms = 0
        for run in range(50):
            c = cr.Cusum(self.mu, self.sd)
            for _ in range(200):
                if c.update(rng.gauss(self.mu, self.sd)) == "LECH_HAN":
                    alarms += 1
                    c.s = 0.0
        self.assertLess(alarms / (50 * 200), 0.01)

    def test_mean_drop_alarms_within_30(self):
        rng = random.Random(2)
        hits = []
        for run in range(50):
            c = cr.Cusum(self.mu, self.sd)
            for k in range(1, 200):
                if c.update(rng.gauss(self.mu - self.sd, self.sd)) == "LECH_HAN":
                    hits.append(k)
                    break
        self.assertGreaterEqual(len(hits), 45)
        self.assertLessEqual(sorted(hits)[len(hits) // 2], 30)

    def test_close_lines_feed_cusum_and_alarm(self):
        env = Env()
        model = FakeModel()
        c = env.council(model)
        for _ in range(40):
            env.journal("CLOSE", money=-150.0)     # -1R at 1.5 % of 10 000
        c.tick()
        self.assertEqual([r for r, _, _ in model.calls], ["giam_sat_bot", "logic_bot", "phan_bien", "tham_phan"])


# ------------------------------------------------------------------------------------------------------------- 6. no commands
class NoCommandTests(unittest.TestCase):
    def test_never_writes_command_files(self):
        env = Env()
        env.status(near=0.9, open_=1, open_risk=10.0)
        env.news(T0 + 1200)
        model = FakeModel(overrides={"tham_phan": answer("tham_phan", phan_quyet="tam_dung_bot")})
        c = env.council(model)
        env.journal("FILL", position=3)
        env.journal("ERROR")
        for _ in range(5):
            c.tick()
            env.t += 300
        self.assertEqual(list((env.root / "current" / "commands").iterdir()), [])
        self.assertEqual(list((env.root / "current" / "remote").iterdir()), [])
        src = (ROOT / "bridge" / "council.py").read_text(encoding="utf-8")
        for token in ("bot_commands", "commands/", "remote/", "OrderSend"):
            self.assertNotIn(token, src)

    def test_supervisor_only_with_flag(self):
        import supervisor
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "t.json"
            cfg.write_text(json.dumps({"token": "x"}), encoding="utf-8")
            self.assertNotIn("council", [s["name"] for s in supervisor.services(Path(d), str(cfg))])
            cfg.write_text(json.dumps({"council": {"enabled": True}}), encoding="utf-8")
            self.assertIn("council", [s["name"] for s in supervisor.services(Path(d), str(cfg))])


if __name__ == "__main__":
    unittest.main()
