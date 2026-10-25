#!/usr/bin/env python3
"""EnterpriseEA AI council, step 3b-1 (phase A: log only).

Reads the files the EA already writes (news state and calendar, bots status and journal, live status, account snapshot), finds
the triggers of docs/superpowers/plans/2026-10-25-council-3b.md, and when the daily budget allows holds a meeting: analyst roles
(round 1), red team, judge. Answers are validated against the knowledge base and the anchor; everything is logged to
logs/council-YYYYMM.jsonl and one line per meeting goes to the bots journal. It never writes a command, a bot command or an order.

    python council.py --queue-root "<MQL5/Files/EnterpriseEA>" --loop
    python council.py --queue-root ... --once
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ai_bridge  # noqa: E402  (same provider call: claude CLI, empty working directory, no tools)
import council_market as cm  # noqa: E402
import council_prompts as cp  # noqa: E402
import council_rules as cr  # noqa: E402

VERSION = "council-3b1-v1.0.0"
DEFAULT_CONFIG = {
    "interval_seconds": 60,
    "timeout_seconds": 180,
    "provider": "claude",
    "calls_per_day": 20,
    "low_calls": 6,
    "max_meetings_per_day": 3,
    "news_window_minutes": 60,
    "near_threshold": 0.8,
    "stale_status_seconds": 180,
    "daily_loss_share": 0.6,
    "open_risk_share": 0.75,
    "symbol": "XAUUSD",
    "commands": {"claude": ["claude", "-p", "--output-format", "text", "--tools", "", "--no-session-persistence"]},
}
ROUND1 = {  # trigger kind -> analyst roles (red team and judge always follow)
    "thuc_thi": ["thuc_thi", "logic_bot"],
    "tin": ["tin_tuc", "logic_bot"],
    "lenh_moi": ["logic_bot"],
    "lech_bot": ["giam_sat_bot", "logic_bot"],
}
PRIORITY = {"thuc_thi": 1, "tin": 2, "lenh_moi": 3, "lech_bot": 4}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def write_atomic(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, path)


def append_line(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def provider_call(model: str, prompt: str, config: dict) -> str:
    cfg = dict(config)
    cfg["commands"] = {p: list(c) + (["--model", model] if p == "claude" else []) for p, c in config["commands"].items()}
    return ai_bridge.call_provider(config["provider"], prompt, cfg)


class Council:
    def __init__(self, queue_root: Path, config: dict, call=provider_call, clock=time.time):
        self.root = Path(queue_root)
        self.cfg = config
        self.call = call
        self.clock = clock
        self.state_path = self.root / "current" / "council_state.json"
        self.state = read_json(self.state_path) or {}
        self.state.setdefault("seen", [])
        self.state.setdefault("journal_utc", 0)
        self.state.setdefault("cusum", {})
        self.budget = cr.Budget(self.state, config["calls_per_day"], config["low_calls"], config["max_meetings_per_day"], clock)
        self.codes = cr.kb_codes()
        self.prints = cr.load_fingerprints()

    # ------------------------------------------------------------------------------------------------------ inputs
    def cur(self, name):
        return read_json(self.root / "current" / name) or {}

    def journal_since(self, since: int) -> list[dict]:
        out = []
        for p in sorted((self.root / "logs").glob("bots-*.jsonl"))[-2:]:
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(e, dict) and int(e.get("at_utc", 0) or 0) > since and e.get("bot") != "COUNCIL":
                        out.append(e)
            except OSError:
                pass
        return sorted(out, key=lambda e: int(e.get("at_utc", 0)))

    def calendar_rows(self, t0: int, t1: int) -> list[dict]:
        rows = []
        for year in {time.gmtime(t0).tm_year, time.gmtime(t1).tm_year}:
            p = self.root / "research" / "calendar" / f"calendar_{year}.csv"
            if not p.exists():
                continue
            with p.open(encoding="utf-8", errors="replace", newline="") as fh:
                for r in csv.DictReader(fh):
                    if r.get("currency") != "USD" or r.get("importance") != "HIGH":
                        continue
                    try:
                        tu = int(r["time_utc"])
                    except (KeyError, ValueError):
                        continue
                    if t0 <= tu <= t1:
                        rows.append({"ten": r.get("name", ""), "gio_utc": tu, "du_bao": r.get("forecast", ""),
                                     "ky_truoc": r.get("previous", ""), "thuc_te": r.get("actual", "")})
        return sorted(rows, key=lambda x: x["gio_utc"])

    # ------------------------------------------------------------------------------------------------------ context
    def context(self, trigger: dict) -> dict:
        now = int(self.clock())
        bots = self.cur("bots_status.json")
        live = self.cur("live_status.json")
        acct = self.cur("account_snapshot.json")
        guard = bots.get("guard", {}) if isinstance(bots, dict) else {}
        news = self.cur("news_state.json")
        sym = next((s for s in news.get("symbols", []) if s.get("symbol") == self.cfg["symbol"]), {}) if isinstance(news, dict) else {}
        ctx = {
            "thoi_gian": {"utc": now, "gio_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)), "thi_truong_mo": cr.market_open(now)},
            "kich_hoat": trigger,
            "tai_khoan": {"so_du": acct.get("balance"), "von_chu_so_huu": acct.get("equity"), "von_ban_dau": guard.get("capital"),
                          "von_dau_ngay": guard.get("day_start_equity"), "gioi_han_lo_ngay_pct": guard.get("daily_loss_pct"),
                          "rui_ro_mo_pct": guard.get("open_risk_pct"), "tran_rui_ro_mo_pct": guard.get("max_open_risk_pct")},
            "bot": {"bots": [{k: b.get(k) for k in ("code", "mode", "active", "open", "floating", "today", "status", "near", "near_text")}
                             for b in bots.get("bots", [])] if isinstance(bots, dict) else [],
                    "phien_live": live.get("session"), "che_do_engine": live.get("modes")},
            "tin": {"trang_thai": {k: sym.get(k) for k in ("state", "event", "next", "next_utc")},
                    "su_kien": self.calendar_rows(now - 3600, now + 48 * 3600)[:12]},
            "thuc_thi": {"status_tre_giay": now - int(live.get("written_at_utc", now) or now), "ly_do_cuoi": live.get("last_reason"),
                         "tam_dung": live.get("operator_paused"), "khoa_recovery": live.get("recovery_blocked")},
            "giam_sat": {"dau_van_tay": self.prints, "cusum": self.state.get("cusum", {})},
            "mo_neo": cr.ANCHOR,
        }
        doc = cm.load(self.root)
        if doc:
            mk = cm.analyse(doc, now)
            ctx["gia"] = {"the_trang_thai": mk["gia"], "tinh_huong": mk["tinh_huong"], "tuoi_file_giay": mk["tuoi_giay"]}
        return ctx

    # ------------------------------------------------------------------------------------------------------ triggers
    def triggers(self) -> list[dict]:
        now = int(self.clock())
        out = []
        bots = self.cur("bots_status.json")
        live = self.cur("live_status.json")
        acct = self.cur("account_snapshot.json")
        blist = bots.get("bots", []) if isinstance(bots, dict) else []
        guard = bots.get("guard", {}) if isinstance(bots, dict) else {}
        # 1. execution / safety
        new = self.journal_since(int(self.state["journal_utc"]))
        for e in new:
            if e.get("event") == "ERROR":
                out.append({"loai": "thuc_thi", "khoa": f"err:{e.get('at_utc')}:{e.get('bot')}", "mo_ta": f"{e.get('bot')} ERROR: {e.get('text')}"})
        age = now - int(live.get("written_at_utc", now) or now) if live else 0
        if live and cr.market_open(now) and age > self.cfg["stale_status_seconds"]:
            out.append({"loai": "thuc_thi", "khoa": f"stale:{int(live.get('written_at_utc', 0)) // 3600}",
                        "mo_ta": f"live_status.json cũ {age} giây trong giờ mở cửa"})
        cap, d0, eq = guard.get("capital"), guard.get("day_start_equity"), acct.get("equity")
        if cap and d0 and eq is not None and guard.get("daily_loss_pct"):
            loss_pct = 100.0 * (float(d0) - float(eq)) / float(cap)
            if loss_pct >= self.cfg["daily_loss_share"] * float(guard["daily_loss_pct"]):
                out.append({"loai": "thuc_thi", "khoa": f"loss:{time.strftime('%Y%m%d', time.gmtime(now))}",
                            "mo_ta": f"lỗ trong ngày {loss_pct:.2f} % / giới hạn {guard['daily_loss_pct']} %"})
        orp, mx = guard.get("open_risk_pct"), guard.get("max_open_risk_pct")
        if orp is not None and mx and float(orp) >= self.cfg["open_risk_share"] * float(mx):
            out.append({"loai": "thuc_thi", "khoa": f"risk:{time.strftime('%Y%m%d%H', time.gmtime(now))}",
                        "mo_ta": f"rủi ro mở {orp} % / trần {mx} %"})
        doc = cm.load(self.root)
        if doc:
            for a in cm.analyse(doc, now)["bat_thuong"]:
                out.append({"loai": "thuc_thi", "khoa": a["khoa"], "mo_ta": a["mo_ta"]})
        # 2. USD HIGH news within the window while XAUUSD is exposed or a bot is close to a signal
        exposed = any((b.get("open") or 0) > 0 for b in blist) or any(
            b.get("active") and (b.get("near") or 0) >= self.cfg["near_threshold"] for b in blist)
        rows = self.calendar_rows(now, now + self.cfg["news_window_minutes"] * 60)
        if rows and exposed:
            first = rows[0]["gio_utc"]
            group = [r["ten"] for r in rows if r["gio_utc"] - first < 3600]
            out.append({"loai": "tin", "khoa": f"news:{first}", "mo_ta": f"tin USD HIGH lúc {time.strftime('%H:%M UTC', time.gmtime(first))}: "
                        + "; ".join(group[:4])})
        # 3. new LIVE fills, 4. drift after closes
        fp = self.prints.get("S07") if isinstance(self.prints, dict) else None
        for e in new:
            data = e.get("data") if isinstance(e.get("data"), dict) else {}
            if e.get("event") == "FILL" and e.get("mode") == "LIVE":
                out.append({"loai": "lenh_moi", "khoa": f"fill:{data.get('position')}", "mo_ta": f"{e.get('bot')}: {e.get('text')}"})
            if e.get("event") == "CLOSE" and e.get("bot") == "S07" and fp and cap:
                r = cr.r_from_money(float(data.get("money", 0) or 0), float(cap), float(fp["risk_percent"]))
                st = self.state["cusum"].get("S07", {"s": 0.0})
                cs = cr.Cusum(fp["mu"], fp["sigma"], s=float(st.get("s", 0.0)))
                level = cs.update(r)
                self.state["cusum"]["S07"] = {"s": round(cs.s, 4), "muc": level, "r_cuoi": round(r, 3), "luc": e.get("at_utc")}
                if level == "LECH_HAN":
                    out.append({"loai": "lech_bot", "khoa": f"drift:S07:{e.get('at_utc')}", "mo_ta": f"S07 lệch dấu vân tay (CUSUM {cs.s:.2f})"})
                    self.state["cusum"]["S07"]["s"] = 0.0                    # restart after an alarm
        if new:
            self.state["journal_utc"] = max(int(e.get("at_utc", 0)) for e in new)
        seen = set(self.state["seen"])
        return sorted([t for t in out if t["khoa"] not in seen], key=lambda t: PRIORITY[t["loai"]])

    # ------------------------------------------------------------------------------------------------------ meeting
    def ask(self, role: str, ctx: dict) -> dict:
        prompt = cp.build(role, ctx, self.codes)
        self.budget.spend()
        self.save()
        rec = {"vai": role, "model": cp.ROLES[role]["model"]}
        try:
            text = self.call(cp.ROLES[role]["model"], prompt, self.cfg)
        except Exception as exc:          # provider failures are logged; the rules decide
            rec.update(hop_le=False, van_de=[f"lỗi gọi: {getattr(exc, 'code', type(exc).__name__)}"],
                       chi_tiet=str(getattr(exc, "detail", exc))[-300:])
            return rec
        ans = cr.extract_json(text)
        allowed = cp.allowed_codes(role, self.codes)
        ok, problems = cr.validate(role, ans, allowed, cp.slice_ctx(role, ctx) if role != "tham_phan" else ctx)
        rec.update(tra_loi=ans, hop_le=ok, van_de=problems)
        return rec

    def meeting(self, trig: dict) -> dict:
        ctx = self.context(trig)
        roles = ROUND1[trig["loai"]]
        rec = {"version": VERSION, "luc_utc": int(self.clock()), "kich_hoat": trig, "vong1": []}
        opinions = {}
        for role in roles:
            if role == "logic_bot":
                ctx["y_kien"] = opinions
            r = self.ask(role, ctx)
            rec["vong1"].append(r)
            if r.get("hop_le"):
                opinions[role] = r["tra_loi"]
        ctx["y_kien"] = opinions
        rb = self.ask("phan_bien", ctx)
        rec["phan_bien"] = rb
        if rb.get("hop_le"):
            ctx["y_kien"] = dict(opinions, phan_bien=rb["tra_loi"])
        jd = self.ask("tham_phan", ctx)
        if jd.get("hop_le"):
            verdict = jd["tra_loi"]
            jd["kep"] = cr.judge_clamp(verdict, cr.ANCHOR)
        else:
            verdict = cr.safe_verdict("thẩm phán không hợp lệ: " + "; ".join(jd.get("van_de", [])[:3]))
        rec["tham_phan"] = jd
        rec["phan_quyet"] = verdict
        rec["giai_doan"] = "A (chỉ ghi lại)"
        rec["luot_con_lai"] = self.budget.left()
        self.budget.meeting()
        self.state["seen"] = (self.state["seen"] + [trig["khoa"]])[-500:]
        month = time.strftime("%Y%m", time.gmtime(self.clock()))
        append_line(self.root / "logs" / f"council-{month}.jsonl", rec)
        append_line(self.root / "logs" / f"bots-{month}.jsonl",
                    {"at_utc": int(self.clock()), "server": "", "bot": "COUNCIL", "event": "DECISION", "mode": "SHADOW",
                     "text": f"[{trig['loai']}] {verdict.get('phan_quyet')} — {verdict.get('tom_tat_vi', '')}"[:400],
                     "data": {"khoa": trig["khoa"], "phan_quyet": verdict.get("phan_quyet"), "giai_doan": "A"}})
        self.save()
        return rec

    def skip(self, trig: dict, reason: str):
        self.state["seen"] = (self.state["seen"] + [trig["khoa"]])[-500:]
        month = time.strftime("%Y%m", time.gmtime(self.clock()))
        append_line(self.root / "logs" / f"council-{month}.jsonl",
                    {"version": VERSION, "luc_utc": int(self.clock()), "kich_hoat": trig, "bo_qua": reason})

    def save(self):
        write_atomic(self.state_path, self.state)
        write_atomic(self.root / "current" / "council_status.json",
                     {"version": VERSION, "written_at_utc": int(self.clock()), "ngay": self.state.get("day"),
                      "luot_da_dung": self.state.get("calls", 0), "luot_toi_da": self.cfg["calls_per_day"],
                      "cuoc_hop": self.state.get("meetings", 0), "cusum": self.state.get("cusum", {})})

    def tick(self) -> int:
        trig = self.triggers()
        held = 0
        for t in trig:
            need = len(ROUND1[t["loai"]]) + 2
            ok, why = self.budget.can_meet(PRIORITY[t["loai"]], need)
            if not ok:
                self.skip(t, why)
                continue
            if held:                       # at most one meeting per tick; the rest wait for the next tick
                break
            self.meeting(t)
            held += 1
        self.save()
        return held


def load_config(path: str | None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        data = read_json(Path(path)) or {}
        cfg.update({k: v for k, v in (data.get("council") or {}).items() if k != "enabled"})
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue-root", required=True)
    ap.add_argument("--config")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    c = Council(Path(a.queue_root), cfg)
    if not a.loop:
        c.tick()
        return 0
    while True:
        try:
            c.tick()
        except Exception as exc:           # a bad file must not stop the loop
            append_line(Path(a.queue_root) / "logs" / "council-errors.jsonl", {"luc_utc": int(time.time()), "loi": repr(exc)[:300]})
        time.sleep(cfg["interval_seconds"])


if __name__ == "__main__":
    sys.exit(main())
