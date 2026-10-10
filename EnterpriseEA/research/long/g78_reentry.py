"""G78: S07 re-entry after the base trade closed (stop-out or exit) while price is still in the setup.
Pre-registered plan: docs/superpowers/plans/2026-10-10-g78-reentry.md. MT5 data only.

  python g78_reentry.py

Sub-bar simulation of G73 (g73_early): M15 inside M30 (from 07/2021), M5 inside M30 as a check (from 05/2024).
"""
from __future__ import annotations

import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g73_early as e73  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g78-reentry.md"
WINDOW_SEC = 2 * 3600
DECIDE = ("train", "validate", "test")
KEYS = ("train", "validate", "test", "examples")
MODES = ("C0", "C-SL", "C-ALL")
RUNS = 200


def provisional(ctx, p, k):
    """Forming main bar p seen at the close of sub-bar k: close, the four EMAs, +DI, -DI, ATR (G73 V1 formulas)."""
    P, S = ctx["P"], ctx["S"]
    q, a = p - 1, 1.0 / 14
    f = ctx["first"][p]
    hp, lp, cp = float(S["h"][f:k + 1].max()), float(S["l"][f:k + 1].min()), float(S["c"][k])
    pc = P["c"][q]
    tr = max(hp - lp, abs(hp - pc), abs(lp - pc))
    up, dn = hp - P["h"][q], P["l"][q] - lp
    pdm = up if (up > dn and up > 0) else 0.0
    mdm = dn if (dn > up and dn > 0) else 0.0
    ts = P["atr"][q] + a * (tr - P["atr"][q])
    pd_ = P["pdms"][q] + a * (pdm - P["pdms"][q])
    md_ = P["mdms"][q] + a * (mdm - P["mdms"][q])
    ep = [P["E"][n][q] + 2.0 / (n + 1) * (cp - P["E"][n][q]) for n in (21, 55, 100, 200)]
    return cp, ep, 100 * pd_ / ts, 100 * md_ / ts, ts


def in_setup(ctx, k, d):
    p = int(ctx["par"][k])
    if p <= 1 or ctx["first"][p] < 0 or ctx["P"]["h4_side"][p] != d:
        return None
    cp, ep, pdi, mdi, atr_p = provisional(ctx, p, k)
    ok = (cp > max(ep) and pdi > mdi) if d == 1 else (cp < min(ep) and mdi > pdi)
    return atr_p if ok else None


def reentry(ctx, i, d, base):
    P, S = ctx["P"], ctx["S"]
    x = base["x"]
    k0 = x + 1 if base["reason"] == "TIME" else x
    ns = len(S["t"])
    a0 = e73.anchor_start(P["t"], i, i - ctx["comp"])
    box = float(np.min(P["l"][a0:i + 1])) if d == 1 else float(np.max(P["h"][a0:i + 1]))
    e_base = base["e"]
    for k in range(k0, ns - 1):
        if S["t"][k] - S["t"][x] > WINDOW_SEC:
            break
        atr_p = in_setup(ctx, k, d)
        if atr_p is None:
            continue
        e = k + 1
        entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
        seg = S["l"][e_base:k + 1].min() if d == 1 else S["h"][e_base:k + 1].max()
        anchor = (min(box, seg) - e73.BUF * atr_p) if d == 1 else (max(box, seg) + e73.BUF * atr_p)
        dist = d * (entry - anchor)
        if dist <= 0 or dist > e73.SMAX * atr_p:
            continue
        dist = max(dist, e73.SMIN * atr_p)
        t = e73.finish(ctx, e73.walk(ctx, e, entry, d, dist), i, atr_p, "RE")
        t["gap_min"] = float((S["t"][e] - S["t"][x]) / 60)
        t["after"] = base["reason"]
        return t
    return None


def book(ctx, mode):
    P, S = ctx["P"], ctx["S"]
    g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = ctx["comp"], e73.ADX_LOW, e73.DI_GAP, e73.ADX_RISE
    sigs = [(i, d) for i, d in g.signals(P) if P["h4_side"][i] == d]
    out, free, W = [], 0, ctx["comp"]
    for i, d in sigs:
        if i < free or i + 1 >= len(P["t"]):
            continue
        e = ctx["first"][i + 1]
        if e < 0 or S["utc"][e] < ctx["start"]:
            continue
        entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
        a0 = e73.anchor_start(P["t"], i, i - W)
        anchor = (np.min(P["l"][a0:i + 1]) - e73.BUF * P["atr"][i]) if d == 1 else (np.max(P["h"][a0:i + 1]) + e73.BUF * P["atr"][i])
        dist = d * (entry - anchor)
        if dist > e73.SMAX * P["atr"][i]:
            continue
        dist = max(dist, e73.SMIN * P["atr"][i])
        b = e73.finish(ctx, e73.walk(ctx, e, entry, d, dist), i, P["atr"][i], "B0")
        out.append(b)
        last = b["x"]
        if mode != "C0" and b["reason"] != "TP" and (mode == "C-ALL" or b["reason"] == "SL"):
            r = reentry(ctx, i, d, b)
            if r is not None:
                out.append(r)
                last = r["x"]
        free = ctx["par"][last] + 1 + ctx["cool"]
    return out


def ran_after_stop(ctx, trs, d):
    """Share of SL'd base trades where price then ran >= 2R past the entry within one day."""
    S = ctx["S"]
    n = hit = 0
    for t in trs:
        if t["kind"] != "B0" or t["d"] != d or t["reason"] != "SL" or t["p"] not in DECIDE:
            continue
        n += 1
        x = t["x"]
        z = int(np.searchsorted(S["t"], S["t"][x] + 86400))
        if z <= x + 1:
            continue
        mfe = (S["h"][x:z].max() - t["entry"]) if d == 1 else (t["entry"] - S["l"][x:z].min())
        hit += int(mfe >= 2 * t["risk"])
    return n, hit


def rand_job(arg):
    main, sub, rows, pools_by, seed, runs = arg
    ctx = e73.context(main, sub)
    S = ctx["S"]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            pool = pools_by[(t["p"], t["d"], t["after"])]
            if not pool:
                continue
            x = pool[int(rng.integers(len(pool)))]
            z = int(np.searchsorted(S["t"], S["t"][x] + WINDOW_SEC, side="right")) - 1
            k = int(rng.integers(x, max(x + 1, z)))
            e = k + 1
            if e >= len(S["t"]) - 1:
                continue
            entry = S["o"][e] + (S["sp"][e] if t["d"] == 1 else 0.0)
            p = int(ctx["par"][k])
            tr = e73.walk(ctx, e, entry, t["d"], t["dist_atr"] * ctx["P"]["atr"][max(p - 1, 0)])
            rs.append(h.harsh(tr, S))
        means.append(float(np.mean(rs)) if rs else 0.0)
    return means


def p_random(main, sub, trs, base_trs):
    rows = [t for t in trs if t["kind"] == "RE" and t["p"] in DECIDE]
    if len(rows) < 10:
        return float("nan"), float("nan")
    pools = {}
    for b in base_trs:
        if b["kind"] == "B0" and b["reason"] != "TP":
            for after in ("SL", "TREND", "TIME"):
                if b["reason"] == after:
                    pools.setdefault((b["p"], b["d"], after), []).append(b["x"])
    lite = [{"p": t["p"], "d": t["d"], "after": t["after"], "dist_atr": t["dist_atr"]} for t in rows]
    keys = {(t["p"], t["d"], t["after"]) for t in lite}
    pools = {k: pools.get(k, []) for k in keys}
    real = float(np.mean([t["rh"] for t in rows]))
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(main, sub, lite, pools, 7800 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def summary(trs, d):
    x = [t for t in trs if t["d"] == d]
    per = {q: g.stats([t["rh"] for t in x if t["p"] == q]) for q in KEYS}
    re = {q: g.stats([t["rh"] for t in x if t["p"] == q and t["kind"] == "RE"]) for q in KEYS}
    dec = [t for t in x if t["p"] in DECIDE]
    dd = h.dd_p90([{"utc": t["utc"], "r": t["rh"]} for t in dec], 0.015) if len(dec) >= 20 else float("nan")
    gaps = [t["gap_min"] for t in dec if t["kind"] == "RE"]
    return dict(per=per, re=re, dd=dd, total=float(sum(t["rh"] for t in dec)), gap=float(np.median(gaps)) if gaps else float("nan"),
                n_re=len(gaps), re_sl=sum(1 for t in dec if t["kind"] == "RE" and t["after"] == "SL"))


def tot(s, q):
    return s["per"][q]["total"] if s["per"][q]["n"] else 0.0


def main():
    L = ["# G78: Vào lại lệnh S07 sau khi bị quét SL / thoát — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g78-reentry.md`. XAUUSD, lệnh gốc S07 M30, mô phỏng trên nến nhỏ, chi phí khắt khe G68, "
         "rủi ro 1,5%/lệnh. Ô kỳ của sổ: số lệnh / tổng R. Ô lệnh vào lại: số lệnh / R mỗi lệnh.", ""]
    verdict = []
    for main_tf, sub in (("M30", "M15"), ("M30", "M5")):
        ctx = e73.context(main_tf, sub)
        primary = sub == "M15"
        res = {m: book(ctx, m) for m in MODES}
        L += [f"## Nến nhỏ {sub}" + ("" if primary else " (kiểm tra, từ 05/2024, chỉ báo cáo)"), "",
              "| Chiều | Bản | Sổ: train | validate | test | 07/2026– | Tổng R gộp | DD p90 | Lệnh vào lại: train | validate | test | "
              "Vào lại sau SL / tổng | Trung vị phút từ lúc đóng | Ngẫu nhiên (TB / p) | Đạt |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d, dn in ((1, "Mua"), (-1, "Bán")):
            s0 = summary(res["C0"], d)
            cands = []
            for m in MODES:
                s = summary(res[m], d)
                rm, p = (p_random(main_tf, sub, [t for t in res[m] if t["d"] == d], res["C0"]) if (primary and m != "C0")
                         else (float("nan"), float("nan")))
                ok = ""
                if primary and m != "C0":
                    c = [all(tot(s, q) > tot(s0, q) for q in DECIDE),
                         all(s["re"][q]["n"] and s["re"][q]["exp"] > 0 for q in DECIDE),
                         (not np.isnan(s["dd"])) and s["dd"] <= s0["dd"] + 0.02,
                         (not np.isnan(p)) and p < 0.025]
                    ok = "**ĐẠT**" if all(c) else "không (" + ", ".join(str(j + 1) for j, x in enumerate(c) if not x) + ")"
                    if all(c):
                        cands.append((s["total"], m))
                f = lambda st: f"{st['n']} / {st['total']:+.1f}" if st["n"] else "—"
                fr = lambda st: f"{st['n']} / {st['exp']:+.2f}" if st["n"] else "—"
                dd = "—" if np.isnan(s["dd"]) else f"{s['dd']:.0%}"
                gap = "—" if np.isnan(s["gap"]) else f"{s['gap']:.0f}"
                rnd = "—" if np.isnan(p) else f"{rm:+.2f} / {p:.3f}"
                L.append(f"| {dn} | {m} | {f(s['per']['train'])} | {f(s['per']['validate'])} | {f(s['per']['test'])} | {f(s['per']['examples'])} | "
                         f"{s['total']:+.1f} | {dd} | {fr(s['re']['train'])} | {fr(s['re']['validate'])} | {fr(s['re']['test'])} | "
                         f"{s['re_sl']} / {s['n_re']} | {gap} | {rnd} | {ok} |")
            if primary and d == 1:
                verdict.append(max(cands)[1] if cands else None)
            n, hit = ran_after_stop(ctx, res["C0"], d)
            L.append(f"| {dn} | (mô tả) | lệnh gốc bị quét SL: {n}; giá chạy tiếp ≥ 2R trong 1 ngày: {hit} ({hit / max(n, 1):.0%}) | | | | | | | | | | | | |")
        L.append("")
    pick = verdict[0] if verdict else None
    L += [f"**Theo tiêu chí (sổ mua, nến nhỏ M15): {'chọn ' + pick if pick else 'không bản nào đạt → không vào lại'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
