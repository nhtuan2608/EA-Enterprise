"""G128: risk allocation for S07 + VHedge G119 - volatility scaling (A), open-risk cap (B), drawdown scaling (C),
VHedge weight (D), per-bot loss-streak scaling (E). Same trades, only sizes change.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g128-risk-allocation.md. MT5 data only.

  python g128_risk_alloc.py

DD p90 = 90th percentile of the max drawdown over 1-year windows starting every month inside the period
(the sizing rules are path dependent, so each window is a fresh simulation from 10,000).
"""
from __future__ import annotations

import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g126_session_adr as g126  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g128-risk-allocation.md"
CACHE = HERE / "out" / "g128_legs.pkl"
CAP0 = 10_000.0
YEAR = 365.25 * 86400


def ts(y, m=1, d=1):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


P_TRAIN, P_VAL, P_TEST = (ts(2018, 3, 5), ts(2022)), (ts(2022), ts(2026)), (ts(2026), g126.END)
P_JOINT = (ts(2024, 5, 1), ts(2026))


def legs():
    if CACHE.exists():
        return pickle.loads(CACHE.read_bytes())
    import g107_portfolio as p107
    import g120_combo as g120
    out = []
    for L in p107.s07_legs():
        out.append(dict(bot="S07", t_in=int((L["t_in"] - pd.Timestamp(0)).total_seconds()),
                        t_out=int((L["t_out"] - pd.Timestamp(0)).total_seconds()), r=float(L["r"]),
                        w=float(L["money"]) / (CAP0 * 0.015)))
    V = g120.vhedge()["G119"]
    tin = g126.to_utc(V["t_in"].to_numpy(dtype=np.int64))
    tout = g126.to_utc(V["t_out"].to_numpy(dtype=np.int64))
    for a, b, r in zip(tin, tout, V["U"].to_numpy()):
        out.append(dict(bot="VH", t_in=int(a), t_out=int(b), r=float(r), w=1.0))
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_bytes(pickle.dumps(out))
    return out


def vol_table():
    M = g126.load("M30")
    D = g126.daily(M)
    pct = D["atr_prev"] / D["o"]
    med = pct.rolling(250, min_periods=120).median().shift(1)
    m = (med / pct).clip(0.5, 1.5)
    return {int(k): float(v) for k, v in m.items() if v == v}


VOL = None


def simulate(L, a, b, rule):
    """rule: dict(vh=1.5, A=False, B=None, C=None, E=False). Returns (cagr, maxdd, final, n)."""
    sel = [x for x in L if a <= x["t_in"] < b and (rule.get("bots") is None or x["bot"] in rule["bots"])]
    if not sel:
        return 0.0, 0.0, CAP0, 0
    ev = []
    for k, x in enumerate(sel):
        ev.append((x["t_in"], 1, k))
        ev.append((x["t_out"], 0, k))            # exits before entries at the same second
    ev.sort()
    E = peak = CAP0
    maxdd = 0.0
    open_risk = {}
    dd_mode = False
    streak = {"S07": 0, "VH": 0}
    penalty = {"S07": 0, "VH": 0}
    n = 0
    for t, kind, k in ev:
        x = sel[k]
        if kind == 0:
            if k not in open_risk:
                continue
            money = open_risk.pop(k)
            E += money * x["r"]
            peak = max(peak, E)
            maxdd = max(maxdd, 1 - E / peak)
            if rule.get("E"):
                if x["r"] < 0:
                    streak[x["bot"]] += 1
                    if streak[x["bot"]] >= 3:
                        penalty[x["bot"]], streak[x["bot"]] = 3, 0
                else:
                    streak[x["bot"]] = 0
            continue
        base = (0.015 * x["w"]) if x["bot"] == "S07" else rule.get("vh", 1.5) / 100.0
        mult = 1.0
        if rule.get("A"):
            mult *= VOL.get(t // g126.DAY, 1.0)
        if rule.get("C"):
            dd = 1 - E / peak
            if dd_mode and dd < rule["C"] / 2:
                dd_mode = False
            if not dd_mode and dd >= rule["C"]:
                dd_mode = True
            if dd_mode:
                mult *= 0.5
        if rule.get("E") and penalty[x["bot"]] > 0:
            mult *= 0.5
            penalty[x["bot"]] -= 1
        risk = base * mult
        if rule.get("B"):
            used = sum(open_risk.values()) / E
            room = rule["B"] / 100.0 - used
            if room < 0.0025:
                continue
            risk = min(risk, room)
        open_risk[k] = E * risk
        n += 1
    yrs = max((b - a) / YEAR, 0.1)
    cagr = (E / CAP0) ** (1 / yrs) - 1 if E > 0 else -1.0
    return cagr, maxdd, E, n


def windows(a, b):
    out, y, m = [], datetime.fromtimestamp(a, timezone.utc).year, datetime.fromtimestamp(a, timezone.utc).month
    while True:
        s = ts(y, m)
        if s + YEAR > b:
            break
        if s >= a:
            out.append((s, int(s + YEAR)))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def stats(L, a, b, rule):
    cagr, dd, E, n = simulate(L, a, b, rule)
    w = [simulate(L, s, e, rule)[1] for s, e in windows(a, b)]
    p90 = float(np.percentile(w, 90)) if w else dd
    return dict(cagr=cagr, dd=dd, mar=cagr / dd if dd > 0 else float("inf"), p90=p90, n=n)


def fmt(s):
    return f"{s['cagr']:+.1%} / {s['dd']:.1%} / **{s['mar']:.2f}** / {s['p90']:.1%} / {s['n']}"


S07_RULES = {"A biến động": {"A": True}, "C sụt vốn 8%": {"C": 0.08}, "C sụt vốn 12%": {"C": 0.12}, "E chuỗi thua": {"E": True}}
JOINT_RULES = {"A biến động": {"A": True}, "B trần 4,5%": {"B": 4.5}, "B trần 6%": {"B": 6.0},
               "C sụt vốn 8%": {"C": 0.08}, "C sụt vốn 12%": {"C": 0.12},
               "D VHedge 1,0%": {"vh": 1.0}, "D VHedge 2,0%": {"vh": 2.0}, "E chuỗi thua": {"E": True}}


def pick(kept, names):
    """keep the better MAR among variants of the same letter."""
    best = {}
    for nm in names:
        if nm not in kept:
            continue
        letter = nm[0]
        if letter not in best or kept[nm] > kept[best[letter]]:
            best[letter] = nm
    return list(best.values())


def main():
    global VOL
    L = legs()
    VOL = vol_table()
    out = ["# G128: phân bổ rủi ro cho S07 + VHedge G119 — kết quả", "",
           "Kế hoạch: `plans/2026-10-20-g128-risk-allocation.md`. Vốn đầu 10.000, lãi kép, lệnh giữ nguyên, chỉ đổi khối "
           "lượng. Gốc: S07 1,5% × trọng số EA; VHedge 1,5%/nhóm. Ô: %/năm / DD lớn nhất / **MAR** / DD p90 (cửa sổ 1 năm "
           "bắt đầu mỗi tháng) / số lệnh.", "",
           f"Chân S07: {sum(1 for x in L if x['bot'] == 'S07')}; nhóm VHedge: {sum(1 for x in L if x['bot'] == 'VH')}.", ""]
    # ---- S07 alone
    s07 = {"bots": ("S07",)}
    out += ["## S07 một mình (train 03/2018–2021, validate 2022–2025)", "", "| Luật | Train | Validate | Giữ? |", "|---|---|---|---|"]
    b_tr, b_va = stats(L, *P_TRAIN, s07), stats(L, *P_VAL, s07)
    out.append(f"| Gốc | {fmt(b_tr)} | {fmt(b_va)} | |")
    kept_s07 = {}
    for nm, r in S07_RULES.items():
        rr = dict(s07, **r)
        a, v = stats(L, *P_TRAIN, rr), stats(L, *P_VAL, rr)
        ok = a["mar"] > b_tr["mar"] and v["mar"] > b_va["mar"] and v["p90"] <= b_va["p90"]
        if ok:
            kept_s07[nm] = v["mar"]
        out.append(f"| {nm} | {fmt(a)} | {fmt(v)} | {'**giữ**' if ok else ''} |")
    sel_s07 = pick(kept_s07, S07_RULES)
    final_s07 = dict(s07)
    for nm in sel_s07:
        final_s07.update(S07_RULES[nm])
    if sel_s07:
        a, v = stats(L, *P_TRAIN, final_s07), stats(L, *P_VAL, final_s07)
        out.append(f"| **Bộ cuối: {' + '.join(sel_s07)}** | {fmt(a)} | {fmt(v)} | |")
    out.append("")
    print("S07 done", sel_s07, flush=True)
    # ---- joint
    out += ["## S07 + VHedge (chọn trên 05/2024–12/2025)", "", "| Luật | 05/2024–12/2025 | Giữ? |", "|---|---|---|"]
    b_j = stats(L, *P_JOINT, {})
    out.append(f"| Gốc | {fmt(b_j)} | |")
    kept_j = {}
    for nm, r in JOINT_RULES.items():
        s = stats(L, *P_JOINT, r)
        ok = s["mar"] > b_j["mar"] and s["p90"] <= b_j["p90"]
        if ok:
            kept_j[nm] = s["mar"]
        out.append(f"| {nm} | {fmt(s)} | {'**giữ**' if ok else ''} |")
    sel_j = pick(kept_j, JOINT_RULES)
    final_j = {}
    for nm in sel_j:
        final_j.update(JOINT_RULES[nm])
    if sel_j:
        s = stats(L, *P_JOINT, final_j)
        best_single = max(kept_j.values())
        out.append(f"| **Bộ cuối: {' + '.join(sel_j)}** | {fmt(s)} | {'(kém luật tốt nhất đứng riêng)' if s['mar'] < best_single else ''} |")
    out.append("")
    print("joint done", sel_j, flush=True)
    # ---- 2026, once
    out += ["## Test 2026 (mở một lần)", ""]
    if not sel_s07 and not sel_j:
        out += ["Không có luật nào được giữ → **2026 không mở**.", ""]
    else:
        out += ["| Sổ | Gốc 2026 | Bộ cuối 2026 | Đạt? |", "|---|---|---|---|"]
        for name, base, fin, used in (("S07 một mình", s07, final_s07, sel_s07), ("S07 + VHedge", {}, final_j, sel_j)):
            if not used:
                continue
            g0, g1 = stats(L, *P_TEST, base), stats(L, *P_TEST, fin)
            ok = g1["mar"] >= g0["mar"] and g1["dd"] <= g0["dd"]
            out.append(f"| {name} ({' + '.join(used)}) | {fmt(g0)} | {fmt(g1)} | {'**đạt**' if ok else 'không'} |")
        out += ["", "DD p90 trên 2026 không có ý nghĩa (chưa đủ 1 năm); cột đó lặp lại DD lớn nhất.", ""]
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
