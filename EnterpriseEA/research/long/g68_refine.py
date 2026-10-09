"""G68: refine the G67 DMI + EMA compression setup on XAUUSD M30 (4-hour compression window). Pre-registered
plan: docs/superpowers/plans/2026-10-09-g68-dmi-ema-refine.md. MT5 data only.

  python g68_refine.py            # steps 1-3, writes reports/2026-10-09-g68-dmi-ema-refine.md
  python g68_refine.py portfolio  # step 3 portfolio check with S04 + S06B (G58 rows)
"""
from __future__ import annotations

import itertools
import sys
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-09-g68-dmi-ema-refine.md"
PRE = (g.ts(2018, 9, 1), g.ts(2021, 7, 20))
KEYS = ("pre", "train", "validate", "test", "examples")
NAMES = {"pre": "09/2018–07/2021", "train": "Train 2021–2023", "validate": "Validate 2024–06/2025",
         "test": "Test 07/2025–06/2026", "examples": "07/2026–nay"}
BASE = dict(adx_low=20.0, di_gap=6.0, rise=10.0, comp=8, exit="E2", buy_only=False, sell_d1=False, gap=False)
RISK = 0.015


def configure(p):
    g.set_tf("M30") if g.BAR_SEC != 1800 else None
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = p["comp"], 4, 240
    g.ADX_LOW, g.DI_GAP, g.ADX_RISE, g.GAP_AWARE = p["adx_low"], p["di_gap"], p["rise"], p["gap"]


def period(t) -> str:
    return "pre" if PRE[0] <= t["utc"] < PRE[1] else g.period_of(t["utc"])


def rows(p) -> list[dict]:
    configure(p)
    D = g.load("XAUUSD")
    sg = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    if p["buy_only"]:
        sg = [(i, d) for i, d in sg if d == 1]
    if p["sell_d1"]:
        sg = [(i, d) for i, d in sg if d == 1 or D["d1_side"][i] == -1]
    out = g.trades("XAUUSD", p["exit"], 8.0, None, sg)
    for t in out:
        t["p"] = period(t)
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
    return [t for t in out if t["p"] != "none"]


def guard(trs, kind):
    """R6: after 2 losing trades closed the same UTC day, skip new entries that day.
    R7: after the trades closed this ISO week lost >= 4R, skip new entries that week."""
    out = []
    for t in sorted(trs, key=lambda x: x["utc"]):
        done = [x for x in out if x["out_utc"] <= t["utc"]]
        if kind == "R6":
            day = t["utc"] // 86400
            if sum(1 for x in done if x["out_utc"] // 86400 == day and x["r"] < 0) >= 2:
                continue
        else:
            wk = datetime.fromtimestamp(t["utc"], timezone.utc).isocalendar()[:2]
            if sum(x["r"] for x in done if datetime.fromtimestamp(x["out_utc"], timezone.utc).isocalendar()[:2] == wk) <= -4:
                continue
        out.append(t)
    return out


def harsh(t, D):
    """Execution stress: +0.5 x median spread slippage each way, spread x3 at rollover (23:30-01:00 server), commission x2."""
    extra = 2 * 0.5 * D["sp_med"] + D["comm"]
    for s, sp in ((t["srv_in"], t["sp_in"]), (t["srv_out"], t["sp_out"])):
        m = s % 86400
        if m >= 23 * 3600 + 1800 or m < 3600:
            extra += 2 * sp
    return t["r"] - extra / t["risk"]


def per(trs, key="r"):
    return {k: g.stats([t[key] for t in trs if t["p"] == k]) for k in KEYS}


def cell(s):
    return f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"


def path(r, days, risk):
    eq = peak = 1.0; dd = 0.0
    for x in r:
        eq *= 1 + risk * x; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return eq, dd


def dd_p90(trs, risk=RISK, seed=1):
    trs = sorted(trs, key=lambda x: x["utc"])
    if len(trs) < 20:
        return 0.0
    rs = np.array([t["r"] for t in trs])
    yrs = (trs[-1]["utc"] - trs[0]["utc"]) / (365.25 * 86400)
    n = max(10, int(len(rs) / max(yrs, 0.1)))
    rng = np.random.default_rng(seed)
    dds = [path(rs[s:s + n], None, risk)[1] for s in rng.integers(0, max(1, len(rs) - n), 2000)]
    return float(np.percentile(dds, 90))


def risk_line(trs, risk):
    trs = sorted(trs, key=lambda x: x["utc"])
    rs = np.array([t["r"] for t in trs])
    yrs = (trs[-1]["utc"] - trs[0]["utc"]) / (365.25 * 86400)
    eq, dd = path(rs, None, risk)
    n = max(10, int(len(rs) / yrs))
    rng = np.random.default_rng(7)
    res = [path(rs[s:s + n], None, risk) for s in rng.integers(0, max(1, len(rs) - n), 3000)]
    rets, dds = np.array([x[0] - 1 for x in res]), np.array([x[1] for x in res])
    return (f"| {risk:.1%} | {(eq ** (1 / yrs) - 1) * 100:+.0f}% | {dd * 100:.0f}% | {np.median(rets) * 100:+.0f}% | "
            f"{np.percentile(rets, 10) * 100:+.0f}% | {np.percentile(dds, 90) * 100:.0f}% | {np.mean(dds >= 0.1) * 100:.0f}% | "
            f"{np.mean(dds >= 0.2) * 100:.0f}% |")


def neighbour_job(v):
    p = dict(BASE, adx_low=v[0], di_gap=v[1], rise=v[2], comp=v[3])
    ps = per(rows(p))
    return v, ps


def tv(ps, key="exp"):
    return ps["train"][key], ps["validate"][key]


def main():
    L = ["# G68: Chau chuốt setup nén → bung DMI + EMA (XAUUSD M30) — kết quả", "",
         "Kế hoạch đăng ký trước: `plans/2026-10-09-g68-dmi-ema-refine.md`. Chỉ dữ liệu MT5. "
         "Ô: số lệnh / R trung bình mỗi lệnh sau spread + commission. Quyết định chỉ dựa trên train + validate.", ""]
    base = rows(BASE)
    D = g.load("XAUUSD")
    pb = per(base)
    L += ["## C0 (bản gốc)", "", "| " + " | ".join(NAMES[k] for k in KEYS) + " |", "|" + "---|" * len(KEYS),
          "| " + " | ".join(cell(pb[k]) for k in KEYS) + " |", ""]

    # step 1a: neighbours
    grid = list(itertools.product((18.0, 20.0, 22.0), (4.0, 6.0, 8.0), (8.0, 10.0, 12.0), (6, 8, 10)))
    with Pool(12) as pool:
        nb = pool.map(neighbour_job, grid)
    tv_ok = sum(1 for _, ps in nb if ps["train"]["exp"] > 0 and ps["validate"]["exp"] > 0)
    oos_ok = sum(1 for _, ps in nb if ps["pre"]["exp"] > 0 and ps["test"]["exp"] > 0)
    all_ok = sum(1 for _, ps in nb if all(ps[k]["exp"] > 0 for k in ("pre", "train", "validate", "test")))
    exps = [np.mean([ps[k]["exp"] for k in ("pre", "train", "validate", "test")]) for _, ps in nb]
    step1a = tv_ok / len(nb) >= 0.6 and oos_ok / len(nb) >= 0.6
    L += ["## Bước 1 — độ bền", "", f"**1a. 81 bộ lân cận** (ADX đáy 18/20/22 × DI 4/6/8 × ADX tăng 8/10/12 × cửa sổ 6/8/10 nến):", "",
          f"- Dương cả train và validate: {tv_ok}/81 ({tv_ok / 81:.0%})",
          f"- Dương cả 2018–2021 và test: {oos_ok}/81 ({oos_ok / 81:.0%})",
          f"- Dương cả 4 kỳ: {all_ok}/81 ({all_ok / 81:.0%})",
          f"- R/lệnh trung bình 4 kỳ: thấp nhất {min(exps):+.3f}, trung vị {np.median(exps):+.3f}, cao nhất {max(exps):+.3f}",
          f"- **{'ĐẠT' if step1a else 'KHÔNG ĐẠT'}** (cần ≥ 60% ở cả hai)", ""]
    worst = sorted(nb, key=lambda x: np.mean([x[1][k]["exp"] for k in ("pre", "train", "validate", "test")]))[:3]
    L += ["Ba bộ yếu nhất: " + "; ".join(f"ADX≤{v[0]:g} DI≤{v[1]:g} tăng≤{v[2]:g} {v[3]} nến" for v, _ in worst), ""]

    # step 1b: harsh execution
    for t in base:
        t["rh"] = harsh(t, D)
    ph = per(base, "rh")
    all_h = float(np.mean([t["rh"] for t in base if t["p"] in ("pre", "train", "validate", "test")]))
    step1b = all_h > 0 and ph["test"]["exp"] > 0
    L += ["**1b. Khớp lệnh khắt khe** (trượt 0,5 × spread mỗi chiều, spread ×3 lúc chuyển ngày, commission ×2):", "",
          "| " + " | ".join(NAMES[k] for k in KEYS) + " | 2018–06/2026 |", "|" + "---|" * (len(KEYS) + 1),
          "| " + " | ".join(cell(ph[k]) for k in KEYS) + f" | {all_h:+.3f} |", "",
          f"**{'ĐẠT' if step1b else 'KHÔNG ĐẠT'}** (cần > 0 ở toàn kỳ và ở test).", ""]
    if not (step1a and step1b):
        L += ["**Bước 1 không đạt: dừng, không chau chuốt (theo kế hoạch).**"]
        REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
        sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
        return

    # step 2: one change at a time
    changes = {"R1": ("Chỉ lệnh mua", dict(BASE, buy_only=True)),
               "R2": ("Bán chỉ khi D1 dưới EMA200 D1", dict(BASE, sell_d1=True)),
               "R3": ("SL bỏ nến trước khoảng trống > 6 giờ", dict(BASE, gap=True)),
               "R4": ("Thoát khi cạn đà (EMA21 hết dốc + ADX giảm)", dict(BASE, exit="E4")),
               "R5": ("≥ 3R thì thoát theo EMA100", dict(BASE, exit="E2X"))}
    L += ["## Bước 2 — mỗi thay đổi thử riêng so với C0", "",
          "| # | Thay đổi | " + " | ".join(NAMES[k] for k in KEYS) + " | Lệnh còn | Giữ? |", "|" + "---|" * (len(KEYS) + 4),
          "| C0 | (gốc) | " + " | ".join(cell(pb[k]) for k in KEYS) + " | 100% | |"]
    kept, results = [], {}
    n_tv = pb["train"]["n"] + pb["validate"]["n"]
    tv_base = np.mean([t["r"] for t in base if t["p"] in ("train", "validate")])
    for key, (name, p) in changes.items():
        rs = rows(p)
        ps = per(rs)
        share = (ps["train"]["n"] + ps["validate"]["n"]) / n_tv
        keep = ps["train"]["exp"] > pb["train"]["exp"] and ps["validate"]["exp"] > pb["validate"]["exp"] and share >= 0.5
        gain = np.mean([t["r"] for t in rs if t["p"] in ("train", "validate")]) - tv_base
        if keep:
            kept.append((key, gain))
        results[key] = (p, rs, ps)
        L.append(f"| {key} | {name} | " + " | ".join(cell(ps[k]) for k in KEYS) + f" | {share:.0%} | {'giữ' if keep else 'bỏ'} |")
    base_tv = [t for t in base if t["p"] in ("train", "validate")]
    base_dd, base_tot = dd_p90(base_tv), sum(t["r"] for t in base_tv)
    guards = {}
    for key, name in (("R6", "Chặn ngày: 2 lệnh thua → nghỉ hết ngày"), ("R7", "Chặn tuần: lỗ ≥ 4R → nghỉ hết tuần")):
        rs = guard(base, key)
        ps = per(rs)
        tvs = [t for t in rs if t["p"] in ("train", "validate")]
        dd, tot = dd_p90(tvs), sum(t["r"] for t in tvs)
        keep = dd < base_dd and tot >= 0.9 * base_tot
        guards[key] = keep
        share = (ps["train"]["n"] + ps["validate"]["n"]) / n_tv
        L.append(f"| {key} | {name} | " + " | ".join(cell(ps[k]) for k in KEYS) +
                 f" | {share:.0%} | {'giữ' if keep else 'bỏ'} (DD p90 1 năm ở 1,5%: {dd:.0%} so với {base_dd:.0%}; "
                 f"tổng R train+val {tot:+.0f} so với {base_tot:+.0f}) |")

    # combine kept rule changes greedily, then the kept guards
    kept.sort(key=lambda x: -x[1])
    final_p, final_name = dict(BASE), ["C0"]
    best_tv = (pb["train"]["exp"], pb["validate"]["exp"])
    final_rows = base
    for key, _ in kept:
        trial = dict(final_p)
        for k2, v2 in results[key][0].items():
            if v2 != BASE[k2]:
                trial[k2] = v2
        rs = rows(trial)
        ps = per(rs)
        if ps["train"]["exp"] > best_tv[0] and ps["validate"]["exp"] > best_tv[1] or final_name == ["C0"]:
            final_p, final_rows, best_tv = trial, rs, (ps["train"]["exp"], ps["validate"]["exp"])
            final_name.append(key)
    final_guards = [k for k, v in guards.items() if v]
    for key in final_guards:
        rs = guard(final_rows, key)
        tvs = [t for t in rs if t["p"] in ("train", "validate")]
        cur = [t for t in final_rows if t["p"] in ("train", "validate")]
        if dd_p90(tvs) < dd_p90(cur) and sum(t["r"] for t in tvs) >= 0.9 * sum(t["r"] for t in cur):
            final_rows = rs
            final_name.append(key)
    label = " + ".join(final_name) if len(final_name) > 1 else "C0 (không thay đổi nào được giữ)"
    L += ["", f"**Bản cuối: {label}**", ""]

    # step 3: final checks
    pf = per(final_rows)
    for t in final_rows:
        t["rh"] = harsh(t, D)
    phf = per(final_rows, "rh")
    dec = [t for t in final_rows if t["p"] in ("train", "validate", "test")]
    real = float(np.mean([t["r"] for t in dec]))
    import json
    REPORT.with_suffix(".final.json").write_text(json.dumps(dict(final_p, guards=[k for k in final_name if k in ("R6", "R7")])),
                                                 encoding="utf-8")
    configure(final_p)
    jobs = [("XAUUSD", dec, final_p["exit"], 8.0, None, 6800 + k, 20) for k in range(10)]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(final_p, j) for j in jobs]) for m in ch]
    p_rand = float(np.mean(np.array(sims) >= real))
    L += ["## Bước 3 — phương án tốt nhất so với C0", "",
          "| Bản | " + " | ".join(NAMES[k] for k in KEYS) + " |", "|" + "---|" * (len(KEYS) + 1),
          "| C0 | " + " | ".join(cell(pb[k]) for k in KEYS) + " |",
          f"| {label} | " + " | ".join(cell(pf[k]) for k in KEYS) + " |",
          f"| {label}, khớp khắt khe | " + " | ".join(cell(phf[k]) for k in KEYS) + " |", "",
          f"- Ngẫu nhiên (200 lần): TB {np.mean(sims):+.3f}R, p = {p_rand:.3f} ({'đạt' if p_rand < 0.01 else 'không đạt'} p < 0,01)."]
    allp = [t for t in final_rows if t["p"] in ("pre", "train", "validate", "test")]
    rs_all = [t["r"] for t in allp]
    wins = [x for x in rs_all if x > 0]
    holds = [t["hold_h"] for t in allp]
    reasons = defaultdict(int)
    for t in allp:
        reasons[t["reason"]] += 1
    st = g.stats(rs_all)
    L += [f"- 2018–06/2026: {len(rs_all)} lệnh, {st['exp']:+.3f}R/lệnh, thắng {len(wins) / len(rs_all):.0%}, "
          f"lệnh thắng TB {np.mean(wins):+.2f}R, DD {st['dd']:.1f}R, tổng {st['total']:+.0f}R.",
          f"- Giữ lệnh: trung vị {np.median(holds):.1f} giờ, 90% ≤ {np.percentile(holds, 90):.0f} giờ. Thoát: " +
          ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())), ""]
    by_dir = {d: g.stats([t["r"] for t in allp if t["d"] == d]) for d in (1, -1)}
    L += [f"- Theo chiều (2018–06/2026): mua {cell(by_dir[1])}, bán {cell(by_dir[-1])}.", ""]
    years = defaultdict(list)
    for t in final_rows:
        years[datetime.fromtimestamp(t["utc"], timezone.utc).year].append(t["r"])
    L += ["Theo năm: " + ", ".join(f"{y}: {len(v)} lệnh {np.mean(v):+.2f}R" for y, v in sorted(years.items())), ""]
    L += ["### Rủi ro mỗi lệnh (lãi kép, 2018–06/2026)", "",
          "| Rủi ro | %/năm | DD lớn nhất | 1 năm: trung vị | 1 năm: p10 | DD p90 1 năm | Chạm DD 10% | Chạm DD 20% |",
          "|---|---|---|---|---|---|---|---|", risk_line(allp, 0.01), risk_line(allp, 0.015)]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


def rand_job(arg):
    p, job = arg
    configure(p)
    return g.random_job(job)


def portfolio():
    """Final rule at 1.5% with S04 + S06B (G58 rows, 0.5% x weights 0.65 / 1.00), 09/2018-10/2025."""
    import g43_low_risk as gl
    live = gl.base_rows()
    p = dict(BASE)
    import json
    cfg = REPORT.with_suffix(".final.json")
    guards_used = []
    if cfg.exists():
        p = json.loads(cfg.read_text(encoding="utf-8"))
        guards_used = p.pop("guards", [])
    mine = rows(p)
    for k in guards_used:
        mine = guard(mine, k)
    a, z = PRE[0], g.ts(2025, 10, 1)
    day = defaultdict(lambda: [0.0, 0.0])
    w = {"S04": 0.65, "S06B": 1.0}
    for t in live:
        if a <= t["out"] < z:
            day[t["out"] // 86400][0] += t["r"] * 0.005 * w.get(t["setup"], 1.0)
    for t in mine:
        if a <= t["out_utc"] < z:
            day[t["out_utc"] // 86400][1] += t["r"] * RISK
    keys = sorted(day)
    A = np.array([day[k][0] for k in keys]); B = np.array([day[k][1] for k in keys])
    yrs = (z - a) / (365.25 * 86400)

    def mdd(x):
        eq = np.cumsum(x); return float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    both = (A != 0) & (B != 0)
    lines = ["", "### Danh mục với S04 + S06B (09/2018–09/2025, không lãi kép)", "",
             f"- Tương quan lãi/lỗ theo ngày (ngày cả hai có lệnh đóng, {both.sum()} ngày): {np.corrcoef(A[both], B[both])[0, 1]:+.2f}",
             "", "| Danh mục | %/năm | DD lớn nhất |", "|---|---|---|",
             f"| S04 + S06B (0,5%) | {A.sum() / yrs * 100:+.1f}% | {mdd(A) * 100:.1f}% |",
             f"| Setup này (1,5%) | {B.sum() / yrs * 100:+.1f}% | {mdd(B) * 100:.1f}% |",
             f"| Cả ba | {(A + B).sum() / yrs * 100:+.1f}% | {mdd(A + B) * 100:.1f}% |"]
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    portfolio() if sys.argv[1:] == ["portfolio"] else main()
