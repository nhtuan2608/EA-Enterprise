"""G69: the DMI + EMA compression setup, two-sided, on every timeframe, then robustness and refinements.
Pre-registered plan: docs/superpowers/plans/2026-10-09-g69-two-sided.md. MT5 data only.

  python g69_two_sided.py
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402  (guard, harsh, risk_line, dd_p90, cell)

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-09-g69-two-sided.md"
KEYS = ("pre", "train", "validate", "test", "examples")
FOUR = ("pre", "train", "validate", "test")
NAMES = {"pre": "09/2018–07/2021", "train": "Train 2021–2023", "validate": "Validate 2024–06/2025",
         "test": "Test 07/2025–06/2026", "examples": "07/2026–nay"}
C0 = dict(tf="M30", comp=8, cool=4, hold=240, adx_low=20.0, di_gap=6.0, rise=10.0, exit="E2",
          sell_d1=False, buy_d1=False, gap=False, buy_only=False)
TFS = [("M15", 16, 8, 480, "16 nến (4 giờ)"), ("M30", 16, 8, 480, "16 nến (8 giờ)"), ("M30", 8, 4, 240, "8 nến (4 giờ)"),
       ("H1", 16, 8, 480, "16 nến (16 giờ)"), ("H1", 4, 2, 120, "4 nến (4 giờ)"), ("H4", 16, 8, 480, "16 nến (64 giờ)"),
       ("H4", 8, 4, 240, "8 nến (32 giờ)"), ("M5", 16, 8, 480, "16 nến (80 phút)"), ("M5", 48, 24, 1440, "48 nến (4 giờ)")]
EXAMPLES = [("Bán 23/9", -1, "2026-09-23T05:00", "2026-09-23T16:00"), ("Bán 25–28/9", -1, "2026-09-25T20:00", "2026-09-28T12:00"),
            ("Mua 05/8", 1, "2026-08-05T06:00", "2026-08-05T12:00"), ("Mua 19/8", 1, "2026-08-19T14:00", "2026-08-19T22:00")]


def configure(p):
    if g.BAR_SEC != {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[p["tf"]] or \
            g.DATA.name != f"{p['tf'].lower()}v":
        g.set_tf(p["tf"])
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = p["comp"], p["cool"], p["hold"]
    g.ADX_LOW, g.DI_GAP, g.ADX_RISE, g.GAP_AWARE = p["adx_low"], p["di_gap"], p["rise"], p["gap"]


def period(t):
    return "pre" if h.PRE[0] <= t["utc"] < h.PRE[1] else g.period_of(t["utc"])


def rows(p):
    configure(p)
    D = g.load("XAUUSD")
    sg = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    if p["buy_only"]:
        sg = [(i, d) for i, d in sg if d == 1]
    if p["sell_d1"]:
        sg = [(i, d) for i, d in sg if d == 1 or D["d1_side"][i] == -1]
    if p["buy_d1"]:
        sg = [(i, d) for i, d in sg if d == -1 or D["d1_side"][i] == 1]
    out = g.trades("XAUUSD", p["exit"], 8.0, None, sg)
    for t in out:
        t["p"] = period(t)
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
    return [t for t in out if t["p"] != "none"]


def per(trs, key="r", d=None):
    return {k: g.stats([t[key] for t in trs if t["p"] == k and (d is None or t["d"] == d)]) for k in KEYS}


def pooled(trs, keys, d=None, key="r"):
    x = [t[key] for t in trs if t["p"] in keys and (d is None or t["d"] == d)]
    return float(np.mean(x)) if x else 0.0, len(x)


def cell(s):
    return h.cell(s)


def rand_job(arg):
    p, job = arg
    configure(p)
    return g.random_job(job)


def p_random(p, trs):
    dec = [t for t in trs if t["p"] in ("train", "validate", "test")]
    real = float(np.mean([t["r"] for t in dec]))
    jobs = [(p, ("XAUUSD", dec, p["exit"], 8.0, None, 6900 + k, 20)) for k in range(10)]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, jobs) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def neighbour_job(arg):
    p, v = arg
    q = dict(p, adx_low=v[0], di_gap=v[1], rise=v[2], comp=v[3])
    return v, per(rows(q))


def neighbours(p):
    comps = sorted({max(2, int(round(p["comp"] * f))) for f in (0.75, 1.0, 1.25)})
    grid = list(itertools.product((18.0, 20.0, 22.0), (4.0, 6.0, 8.0), (8.0, 10.0, 12.0), comps))
    with Pool(12) as pool:
        return pool.map(neighbour_job, [(p, v) for v in grid])


def examples(trs):
    out = []
    for name, d, a, z in EXAMPLES:
        a = datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        z = datetime.fromisoformat(z).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        hit = [t for t in trs if t["d"] == d and a <= t["utc"] <= z]
        if hit:
            t = hit[0]
            vn = datetime.fromtimestamp(t["utc"] + g.BAR_SEC + 7 * 3600, timezone.utc)
            out.append(f"{name}: **bắt được** {vn:%d/%m %H:%M} VN, {t['r']:+.2f}R ({t['reason']}, giữ {t['hold_h']:.0f} giờ)")
        else:
            out.append(f"{name}: không vào lệnh trong khung giờ đó")
    return out


def portfolio_lines(trs, risk=0.015):
    import g43_low_risk as gl
    live = gl.base_rows()
    a, z = h.PRE[0], g.ts(2025, 10, 1)
    day = defaultdict(lambda: [0.0, 0.0])
    w = {"S04": 0.65, "S06B": 1.0}
    for t in live:
        if a <= t["out"] < z:
            day[t["out"] // 86400][0] += t["r"] * 0.005 * w.get(t["setup"], 1.0)
    for t in trs:
        if a <= t["out_utc"] < z:
            day[t["out_utc"] // 86400][1] += t["r"] * risk
    keys = sorted(day)
    A = np.array([day[k][0] for k in keys]); B = np.array([day[k][1] for k in keys])
    yrs = (z - a) / (365.25 * 86400)

    def mdd(x):
        eq = np.cumsum(x); return float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    both = (A != 0) & (B != 0)
    corr = np.corrcoef(A[both], B[both])[0, 1] if both.sum() > 2 else float("nan")
    return ["", "### Danh mục với S04 + S06B (09/2018–09/2025, không lãi kép)", "",
            f"- Tương quan lãi/lỗ theo ngày ({both.sum()} ngày cả hai có lệnh đóng): {corr:+.2f}", "",
            "| Danh mục | %/năm | DD lớn nhất |", "|---|---|---|",
            f"| S04 + S06B (0,5%) | {A.sum() / yrs * 100:+.1f}% | {mdd(A) * 100:.1f}% |",
            f"| Setup này ({risk:.1%}) | {B.sum() / yrs * 100:+.1f}% | {mdd(B) * 100:.1f}% |",
            f"| Cả ba | {(A + B).sum() / yrs * 100:+.1f}% | {mdd(A + B) * 100:.1f}% |"]


def side_table(name, trs):
    a, b = per(trs, d=1), per(trs, d=-1)
    return [f"| {name} — mua | " + " | ".join(cell(a[k]) for k in KEYS) + " |",
            f"| {name} — bán | " + " | ".join(cell(b[k]) for k in KEYS) + " |"]


def main():
    L = ["# G69: Setup nén → bung DMI + EMA hai chiều, mọi khung — kết quả", "",
         "Kế hoạch đăng ký trước: `plans/2026-10-09-g69-two-sided.md`. Chỉ dữ liệu MT5, XAUUSD. "
         "Ô: số lệnh / R trung bình mỗi lệnh sau spread + commission. Quyết định chỉ trên train + validate.", ""]
    head = "| " + " | ".join(NAMES[k] for k in KEYS) + " |"

    # ---------------- A: timeframes
    L += ["## A. Chọn khung (C0 hai chiều)", "",
          "| Khung | Cửa sổ | " + " | ".join(NAMES[k] for k in KEYS) + " | Train+val | Mua train+val | Bán train+val | Ngẫu nhiên p |",
          "|" + "---|" * (len(KEYS) + 6)]
    cands = []
    for tf, comp, cool, hold, label in TFS:
        p = dict(C0, tf=tf, comp=comp, cool=cool, hold=hold)
        trs = rows(p)
        ps = per(trs)
        tv, n_tv = pooled(trs, ("train", "validate"))
        tvb, _ = pooled(trs, ("train", "validate"), 1)
        tvs, _ = pooled(trs, ("train", "validate"), -1)
        _, pr = p_random(p, trs)
        L.append(f"| {tf} | {label} | " + " | ".join(cell(ps[k]) for k in KEYS) +
                 f" | {n_tv} / {tv:+.3f} | {tvb:+.3f} | {tvs:+.3f} | {pr:.3f} |")
        if tf != "M5" and n_tv >= 150:
            cands.append((tv, p, label))
        print(L[-1], flush=True)
    tv_best, P0, label0 = max(cands, key=lambda x: x[0])
    L += ["", f"**Khung được chọn: {P0['tf']}, cửa sổ {label0}** (R/lệnh train+validate {tv_best:+.3f}).", ""]

    # ---------------- B1: robustness
    base = rows(P0)
    configure(P0)
    D = g.load("XAUUSD")
    for t in base:
        t["rh"] = h.harsh(t, D)
    nb = neighbours(P0)
    tv_ok = sum(1 for _, q in nb if q["train"]["exp"] > 0 and q["validate"]["exp"] > 0)
    has_pre = per(base)["pre"]["n"] > 0
    oos_ok = sum(1 for _, q in nb if (q["pre"]["exp"] > 0 or not has_pre) and q["test"]["exp"] > 0)
    ph = per(base, "rh")
    all_h, _ = pooled(base, FOUR, key="rh")
    gate = tv_ok / len(nb) >= 0.6 and oos_ok / len(nb) >= 0.6 and all_h > 0 and ph["test"]["exp"] > 0
    L += ["## B1. Độ bền của C0 trên khung đã chọn", "",
          f"- 81 lân cận: dương cả train và validate {tv_ok}/81; dương cả 2018–2021 và test {oos_ok}/81.",
          f"- Khớp khắt khe: " + ", ".join(f"{NAMES[k]} {cell(ph[k])}" for k in KEYS) + f"; toàn kỳ {all_h:+.3f}.",
          f"- **{'ĐẠT' if gate else 'KHÔNG ĐẠT'}**", ""]
    if not gate:
        L += ["Theo kế hoạch: dừng ở đây."]
        REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
        return

    # ---------------- B2: changes one at a time
    pb = per(base)
    changes = {"S1": ("Bán chỉ khi D1 dưới EMA200", dict(P0, sell_d1=True)),
               "S2": ("Mua chỉ khi D1 trên EMA200", dict(P0, buy_d1=True)),
               "S3": ("Theo chiều EMA200 D1 cả hai phía", dict(P0, sell_d1=True, buy_d1=True)),
               "S4": ("SL bỏ nến trước khoảng trống > 6 giờ", dict(P0, gap=True)),
               "S5": ("Thoát khi cạn đà (EMA21 + ADX)", dict(P0, exit="E4")),
               "S6": ("≥ 3R thì thoát theo EMA100", dict(P0, exit="E2X"))}
    L += ["## B2. Mỗi thay đổi thử riêng so với C0", "",
          "| # | Thay đổi | " + " | ".join(NAMES[k] for k in KEYS) + " | Bán train+val | Lệnh còn | Giữ? |",
          "|" + "---|" * (len(KEYS) + 5),
          "| C0 | (gốc) | " + " | ".join(cell(pb[k]) for k in KEYS) + f" | {pooled(base, ('train', 'validate'), -1)[0]:+.3f} | 100% | |"]
    n_tv = pb["train"]["n"] + pb["validate"]["n"]
    tv0, _ = pooled(base, ("train", "validate"))
    kept, res = [], {}
    for key, (name, p) in changes.items():
        trs = rows(p)
        ps = per(trs)
        share = (ps["train"]["n"] + ps["validate"]["n"]) / n_tv
        sell_tv, n_sell = pooled(trs, ("train", "validate"), -1)
        keep = (ps["train"]["exp"] > pb["train"]["exp"] and ps["validate"]["exp"] > pb["validate"]["exp"]
                and share >= 0.5 and (n_sell == 0 or sell_tv >= 0))
        gain = pooled(trs, ("train", "validate"))[0] - tv0
        if keep:
            kept.append((key, gain))
        res[key] = (p, trs)
        L.append(f"| {key} | {name} | " + " | ".join(cell(ps[k]) for k in KEYS) +
                 f" | {sell_tv:+.3f} | {share:.0%} | {'giữ' if keep else 'bỏ'} |")
    base_tv = [t for t in base if t["p"] in ("train", "validate")]
    bdd, btot = h.dd_p90(base_tv), sum(t["r"] for t in base_tv)
    guard_keep = {}
    for key, gk, name in (("S7", "R6", "Chặn ngày: 2 lệnh thua → nghỉ"), ("S8", "R7", "Chặn tuần: lỗ ≥ 4R → nghỉ")):
        trs = h.guard(base, gk)
        ps = per(trs)
        tvs = [t for t in trs if t["p"] in ("train", "validate")]
        dd, tot = h.dd_p90(tvs), sum(t["r"] for t in tvs)
        keep = dd < bdd and tot >= 0.9 * btot
        guard_keep[key] = (gk, keep)
        L.append(f"| {key} | {name} | " + " | ".join(cell(ps[k]) for k in KEYS) +
                 f" | | {(ps['train']['n'] + ps['validate']['n']) / n_tv:.0%} | {'giữ' if keep else 'bỏ'} "
                 f"(DD p90 1 năm ở 1,5%: {dd:.0%} so với {bdd:.0%}) |")

    # greedy combine; S1/S2/S3 mutually exclusive (keep the best of them only)
    kept.sort(key=lambda x: -x[1])
    d1_taken = False
    final_p, final_name, final = dict(P0), ["C0"], base
    best = (pb["train"]["exp"], pb["validate"]["exp"])
    for key, _ in kept:
        if key in ("S1", "S2", "S3"):
            if d1_taken:
                continue
        trial = dict(final_p)
        for k2, v2 in res[key][0].items():
            if v2 != P0[k2]:
                trial[k2] = v2
        trs = rows(trial)
        ps = per(trs)
        if (ps["train"]["exp"] > best[0] and ps["validate"]["exp"] > best[1]) or final_name == ["C0"]:
            final_p, final, best = trial, trs, (ps["train"]["exp"], ps["validate"]["exp"])
            final_name.append(key)
            d1_taken = d1_taken or key in ("S1", "S2", "S3")
    guards_used = []
    for key, (gk, keep) in guard_keep.items():
        if not keep:
            continue
        trs = h.guard(final, gk)
        tvs = [t for t in trs if t["p"] in ("train", "validate")]
        cur = [t for t in final if t["p"] in ("train", "validate")]
        if h.dd_p90(tvs) < h.dd_p90(cur) and sum(t["r"] for t in tvs) >= 0.9 * sum(t["r"] for t in cur):
            final = trs
            final_name.append(key)
            guards_used.append(gk)
    label = " + ".join(final_name)
    REPORT.with_suffix(".final.json").write_text(json.dumps(dict(final_p, guards=guards_used)), encoding="utf-8")
    L += ["", f"**Bản cuối hai chiều: {label}** (khung {final_p['tf']}, cửa sổ {final_p['comp']} nến)", ""]

    # ---------------- C: final checks
    configure(final_p)
    D = g.load("XAUUSD")
    for t in final:
        t["rh"] = h.harsh(t, D)
    pf, phf = per(final), per(final, "rh")
    rand_mean, pr = p_random(final_p, final)
    nbf = neighbours(final_p)
    nb_ok = sum(1 for _, q in nbf if all(q[k]["exp"] > 0 or (k == "pre" and not has_pre) for k in FOUR))
    buy_in, _ = pooled(final, ("train", "validate"), 1)
    sell_in, n_sell = pooled(final, ("train", "validate"), -1)
    buy_out, _ = pooled(final, ("pre", "test"), 1)
    sell_out, _ = pooled(final, ("pre", "test"), -1)
    all_h, _ = pooled(final, FOUR, key="rh")
    checks = {
        "dương 4 kỳ": all(pf[k]["exp"] > 0 for k in FOUR if pf[k]["n"] > 0),
        "mua dương (train+val và trước+test)": buy_in > 0 and buy_out > 0,
        "bán dương (train+val và trước+test)": n_sell > 0 and sell_in > 0 and sell_out > 0,
        "ngẫu nhiên p < 0,01": pr < 0.01,
        "khớp khắt khe > 0 (toàn kỳ và test)": all_h > 0 and phf["test"]["exp"] > 0,
        "≥ 60% lân cận dương 4 kỳ": nb_ok / len(nbf) >= 0.6,
    }
    g68 = None
    try:
        q = json.loads(h.REPORT.with_suffix(".final.json").read_text(encoding="utf-8"))
        q.pop("guards", None)
        q.update(tf="M30", cool=4, hold=240, buy_d1=False)
        g68 = rows(q)
    except Exception:  # noqa: BLE001
        g68 = None
    L += ["## C. Phương án tốt nhất", "", "| Bản | " + " | ".join(NAMES[k] for k in KEYS) + " |", "|" + "---|" * (len(KEYS) + 1),
          f"| C0 ({P0['tf']}) | " + " | ".join(cell(pb[k]) for k in KEYS) + " |",
          f"| **{label}** | " + " | ".join(cell(pf[k]) for k in KEYS) + " |",
          f"| {label}, khớp khắt khe | " + " | ".join(cell(phf[k]) for k in KEYS) + " |"]
    if g68:
        pg = per(g68)
        L.append("| G68 chỉ mua (đối chiếu) | " + " | ".join(cell(pg[k]) for k in KEYS) + " |")
    L += ["", "Theo chiều:", "", "| Bản / chiều | " + " | ".join(NAMES[k] for k in KEYS) + " |", "|" + "---|" * (len(KEYS) + 1)]
    L += side_table(label, final)
    L += ["", "Tiêu chí:", ""] + [f"- {k}: {'ĐẠT' if v else 'KHÔNG ĐẠT'}" for k, v in checks.items()]
    L += [f"- (ngẫu nhiên TB {rand_mean:+.3f}R; lân cận dương 4 kỳ {nb_ok}/81)", "",
          f"**Kết luận: {'bản hai chiều ĐẠT tất cả tiêu chí' if all(checks.values()) else 'bản hai chiều KHÔNG đạt đủ tiêu chí'}.**", ""]
    allp = [t for t in final if t["p"] in FOUR]
    rs = [t["r"] for t in allp]
    st = g.stats(rs)
    holds = [t["hold_h"] for t in allp]
    reasons = defaultdict(int)
    for t in allp:
        reasons[t["reason"]] += 1
    years = defaultdict(list)
    for t in final:
        years[datetime.fromtimestamp(t["utc"], timezone.utc).year].append(t["r"])
    L += [f"- Toàn kỳ: {st['n']} lệnh, {st['exp']:+.3f}R/lệnh, thắng {st['win']:.0%}, lệnh thắng TB {st['avg_win']:+.2f}R, "
          f"DD {st['dd']:.1f}R, tổng {st['total']:+.0f}R. Giữ lệnh trung vị {np.median(holds):.1f} giờ, 90% ≤ {np.percentile(holds, 90):.0f} giờ.",
          "- Thoát: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())),
          "- Theo năm: " + ", ".join(f"{y}: {len(v)} lệnh {np.mean(v):+.2f}R" for y, v in sorted(years.items())), "",
          "### Rủi ro mỗi lệnh (lãi kép, toàn kỳ)", "",
          "| Rủi ro | %/năm | DD lớn nhất | 1 năm: trung vị | 1 năm: p10 | DD p90 1 năm | Chạm DD 10% | Chạm DD 20% |",
          "|---|---|---|---|---|---|---|---|", h.risk_line(allp, 0.01), h.risk_line(allp, 0.015), "",
          "### 4 ví dụ của người dùng", ""] + [f"- {x}" for x in examples(final)]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    try:
        extra = portfolio_lines(final)
    except Exception as e:  # noqa: BLE001
        extra = ["", f"(Danh mục: lỗi {e})"]
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(extra) + "\n")
    sys.stdout.buffer.write(("\n".join(L + extra) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
