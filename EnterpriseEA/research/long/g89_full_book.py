"""G89: the S07Tester rules over ~10 years of the user's MT5 data (Python port; the MT5 tester only has 2024+).

  python g89_full_book.py

Per side (buy, sell), on the M30 base:
  base     S07 / S07S on the M30 close (sell with the L2 location), the H4 EMA200 side filter;
  early    S07E / S07ES at every closed sub-bar inside the forming M30 bar (G73 V1);
  re-entry S07R / S07RS within 2 h after a base closed (not at target) when price is back beyond the four EMAs;
  one base slot per side (first trigger enters), 4 M30 bars cool-down after a base (not for re-entries);
  base exits: SL, 8R target, close beyond EMA55 (EMA100 after 3R), ADX >= 50 turning down, 240 M30 bars;
  adds     S07A / S07AS from M15 / H1 / H4 signals while the base is in profit (2 adds, 3 legs, 1 h apart).
Risk: 1.5% x weight (base without the ordered ribbon 0.67, adds 0.67), compounded in exit order. Harsh G68 costs.
Sub-bars: M15 from 2021-07-20 (early and re-entry need them); before that the M30 bar is its own sub-bar (no
early entries; re-entries at M30 closes). M15 adds exist from 2021-07 only.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g70_pyramid as gp  # noqa: E402
import g73_early as e73  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g89-full-book-10y.md"
START = g.ts(2016, 10, 1)
SPLIT = g.ts(2021, 7, 20)
END = g.ts(2026, 10, 10)
RISK = 0.015
W_UNORD, W_ADD = 0.67, 0.67
REENTRY_SEC, COOL_BARS = 7200, 4
ADX_EXH = 50.0


def ordered(E, i, c, d):
    return (E[21][i] > E[55][i] > E[100][i] and c > E[21][i]) if d == 1 else (E[21][i] < E[55][i] < E[100][i] and c < E[21][i])


def walk(ctx, e, entry, d, dist):
    """Base leg on sub-bars: SL / 8R on sub-bars; EMA55->EMA100 and ADX exhaustion at M30 closes; 240 M30 bars."""
    P, S, par, last = ctx["P"], ctx["S"], ctx["par"], ctx["last"]
    o, hh, ll, c, sp = S["o"], S["h"], S["l"], S["c"], S["sp"]
    ns = len(c)
    sl, tp = entry - d * dist, entry + d * 8.0 * dist
    best, nb = entry, 0
    exit_px, x, reason = None, None, "TIME"
    for j in range(e, ns):
        sj = sp[j] if d == -1 else 0.0
        bh, bl, bo = hh[j] + sj, ll[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px, x, reason = (min(sl, bo) if d == 1 else max(sl, bo)), j, "SL"
            break
        if (d == 1 and bh >= tp) or (d == -1 and bl <= tp):
            exit_px, x, reason = (max(tp, bo) if d == 1 else min(tp, bo)), j, "TP"
            break
        best = max(best, hh[j]) if d == 1 else min(best, ll[j] + sj)
        if last[j] and par[j] > 0:
            p = par[j]
            nb += 1
            ema = P["E"][100][p] if d * (best - entry) >= 3 * dist else P["E"][55][p]
            out = d * (P["c"][p] - ema) < 0 or (P["adx"][p - 1] >= ADX_EXH and P["adx"][p] < P["adx"][p - 1])
            if out and j + 1 < ns:
                x = j + 1
                exit_px = o[x] + (sp[x] if d == -1 else 0.0)
                reason = "TREND"
                break
            if nb >= 240:
                x, exit_px = j, c[j] + sj
                break
    if exit_px is None:
        x = ns - 1
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - P["comm"] / dist
    t = {"d": d, "e": int(e), "x": int(x), "r": float(r), "risk": float(dist), "reason": reason, "entry": float(entry),
         "srv_in": int(S["t"][e]), "srv_out": int(S["t"][x]), "sp_in": float(sp[e]), "sp_out": float(sp[x]),
         "ein": int(S["utc"][e]), "eout": int(S["utc"][x]), "utc": int(S["utc"][e])}
    t["rh"] = h.harsh(t, S)
    sub_sec = e73.SEC[ctx["sub"]]
    t.update(U=S["utc"][e:x + 1].copy(), C=S["c"][e:x + 1].copy(), bs=sub_sec)
    return t


def provisional(ctx, k):
    P, S = ctx["P"], ctx["S"]
    p = int(ctx["par"][k])
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
    pdi, mdi = 100 * pd_ / ts, 100 * md_ / ts
    dx = 100 * abs(pdi - mdi) / max(pdi + mdi, 1e-9)
    adx_p = P["adx"][q] + a * (dx - P["adx"][q])
    ep = {n: P["E"][n][q] + 2.0 / (n + 1) * (cp - P["E"][n][q]) for n in (21, 55, 100, 200)}
    return dict(p=p, q=q, hp=hp, lp=lp, c=cp, atr=ts, pdi=pdi, mdi=mdi, adx=adx_p, E=ep)


def base_candidates(ctx, d, t0, t1):
    """Base entries in time: (entry sub index, kind, signal atr, anchor, ordered)."""
    P, S = ctx["P"], ctx["S"]
    W = 8
    out = []
    g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = W, 20.0, 6.0, 10.0
    for i, dd in g.signals(P):
        if dd != d or P["h4_side"][i] != d or i + 1 >= len(P["t"]):
            continue
        e = ctx["first"][i + 1]
        if e < 0 or not (t0 <= S["utc"][e] < t1):
            continue
        if d == -1:
            top = float(P["h"][i - W:i + 1].max())
            if not (P["h4_val"][i] > 0 and top >= P["h4_val"][i] - 0.5 * P["atr"][i]):
                continue
        a0 = e73.anchor_start(P["t"], i, i - W)
        anchor = float(P["l"][a0:i + 1].min()) if d == 1 else float(P["h"][a0:i + 1].max())
        out.append((int(e), "S07" if d == 1 else "S07S", float(P["atr"][i]), anchor, ordered(P["E"], i, P["c"][i], d)))
    if ctx["sub"] != ctx["main"]:
        for k in range(len(S["t"]) - 1):
            if ctx["last"][k] or ctx["par"][k] <= 410 or not (t0 <= S["utc"][k] < t1):
                continue
            p = int(ctx["par"][k])
            q = p - 1
            k0 = q - W + 1 + int(np.argmin(P["adx"][q - W + 1:q + 1]))
            if P["adx"][k0] > 20 or abs(P["gap"][k0]) > 6 or P["h4_side"][p] != d:
                continue
            pv = provisional(ctx, k)
            if not (pv["adx"] > P["adx"][q] and pv["adx"] - P["adx"][k0] <= 10):
                continue
            gp_ = pv["pdi"] - pv["mdi"]
            hi, lo = max(pv["E"].values()), min(pv["E"].values())
            ok = (gp_ > 0 and gp_ > P["gap"][q] and pv["c"] > hi) if d == 1 else (gp_ < 0 and gp_ < P["gap"][q] and pv["c"] < lo)
            if not ok:
                continue
            if d == -1:
                top = max(float(P["h"][q - W + 1:q + 1].max()), pv["hp"])
                if not (P["h4_val"][p] > 0 and top >= P["h4_val"][p] - 0.5 * pv["atr"]):
                    continue
            a0 = e73.anchor_start(P["t"], p, p - W)
            if d == 1:
                anchor = min(float(P["l"][a0:p].min()), pv["lp"]) if a0 < p else pv["lp"]
            else:
                anchor = max(float(P["h"][a0:p].max()), pv["hp"]) if a0 < p else pv["hp"]
            ordd = (pv["E"][21] > pv["E"][55] > pv["E"][100] and pv["c"] > pv["E"][21]) if d == 1 else \
                   (pv["E"][21] < pv["E"][55] < pv["E"][100] and pv["c"] < pv["E"][21])
            out.append((int(k + 1), "S07E" if d == 1 else "S07ES", pv["atr"], anchor, ordd))
    return sorted(out)


def open_leg(ctx, e, d, atr, anchor):
    S = ctx["S"]
    if e >= len(S["t"]) - 1:
        return None
    entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
    stop = anchor - d * 0.1 * atr
    dist = d * (entry - stop)
    if dist <= 0 or dist > 4 * atr:
        return None
    dist = max(dist, atr)
    return walk(ctx, e, entry, d, dist)


def reentry(ctx, d, base, t1):
    """First sub-bar within 2 h after the base exit where price is back in the setup (S07R / S07RS)."""
    S, P = ctx["S"], ctx["P"]
    x = base["x"]
    start = x + 1 if base["reason"] == "TIME" else x
    for k in range(start, len(S["t"]) - 1):
        if S["utc"][k] - S["utc"][x] > REENTRY_SEC or S["utc"][k] >= t1:
            return None
        if ctx["par"][k] <= 410:
            continue
        pv = provisional(ctx, k)
        p = pv["p"]
        hi, lo = max(pv["E"].values()), min(pv["E"].values())
        ok = (pv["c"] > hi and pv["pdi"] > pv["mdi"]) if d == 1 else (pv["c"] < lo and pv["mdi"] > pv["pdi"])
        if not ok or P["h4_side"][p] != d:
            continue
        seg = S["l"][base["e"]:k + 1].min() if d == 1 else S["h"][base["e"]:k + 1].max()
        anchor = min(base["entry"] - d * base["risk"], seg) if d == 1 else max(base["entry"] - d * base["risk"], seg)
        leg = open_leg(ctx, k + 1, d, pv["atr"], anchor)
        if leg:
            leg["kind"] = "S07R" if d == 1 else "S07RS"
            leg["ord"] = (pv["E"][21] > pv["E"][55] > pv["E"][100] and pv["c"] > pv["E"][21]) if d == 1 else \
                         (pv["E"][21] < pv["E"][55] < pv["E"][100] and pv["c"] < pv["E"][21])
            return leg
    return None


def base_book(ctx, d, t0, t1, early=True, re=True):
    cands = base_candidates(ctx, d, t0, t1)
    if not early:
        cands = [c for c in cands if c[1] in ("S07", "S07S")]
    out, free_k = [], 0
    S = ctx["S"]
    cool = COOL_BARS * 1800
    ci = 0
    while ci < len(cands):
        e, kind, atr, anchor, ordd = cands[ci]
        ci += 1
        if e < free_k:
            continue
        leg = open_leg(ctx, e, d, atr, anchor)
        if leg is None:
            continue
        leg["kind"], leg["ord"] = kind, ordd
        out.append(leg)
        cur = leg
        while True:
            free_k = int(np.searchsorted(S["utc"], S["utc"][cur["x"]] + cool))
            if not re or cur["reason"] == "TP":
                break
            r_ = reentry(ctx, d, cur, t1)
            if r_ is None:
                break
            out.append(r_)
            cur = r_
        free_k = max(free_k, cur["x"] + 1)
    return out


def add_pool(side):
    rule = dict(v.C0, gap=True, exit="E2X")
    pool = []
    for tf in ("M15", "H1", "H4"):
        legs, _ = gp.legs_for(tf, rule, side)
        D = g.load("XAUUSD")
        for t in legs.values():
            t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
            t["rh"] = h.harsh(t, D)
            pool.append(t)
    return sorted(pool, key=lambda x: x["sig"])


def attach_adds(bases, pool):
    """G70 option B rules + the 3-legs-open cap (per side)."""
    legs, open_exits = [], []
    for b in sorted(bases, key=lambda x: x["ein"]):
        live = [z for z in open_exits if z > b["ein"]]
        if len(live) >= 3:
            continue
        cluster = [b]
        open_exits.append(b["eout"])
        for L in pool:
            if len(cluster) > 2:
                break
            if not (b["ein"] < L["sig"] < b["eout"]):
                continue
            if L["ein"] - cluster[-1]["ein"] < 3600 or not gp.floating_ok(b, L["sig"]):
                continue
            if len([z for z in open_exits if z > L["ein"]]) >= 3:
                continue
            cluster.append(L)
            open_exits.append(L["eout"])
        legs.append(cluster)
    return legs


def equity(rows):
    rows = sorted(rows, key=lambda z: z[1])
    eq = pk = 1.0
    dd = 0.0
    curve = []
    for r, t_out, w in rows:
        eq *= 1 + w * r
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
        curve.append((t_out, eq))
    return eq, dd, curve


def dd_p90(rows):
    rows = sorted(rows, key=lambda z: z[1])
    yrs = (rows[-1][1] - rows[0][1]) / (365.25 * 86400)
    n = max(10, int(len(rows) / max(yrs, 0.1)))
    rng = np.random.default_rng(89)
    dds, hit20, hit30 = [], 0, 0
    for s in rng.integers(0, max(1, len(rows) - n), 3000):
        _, dd, _ = equity(rows[s:s + n])
        dds.append(dd)
    dds = np.array(dds)
    return float(np.percentile(dds, 90)), float(np.mean(dds >= 0.2)), float(np.mean(dds >= 0.3))


def run(variant):
    rows, legs_all = [], []
    for d in variant["sides"]:
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", START, SPLIT), ("M30", "M15", SPLIT, END)):
            ctx = e73.context(main, sub)
            bases += base_book(ctx, d, t0, t1, early=variant["early"], re=variant["re"])
        if variant["adds"]:
            clusters = attach_adds(bases, add_pool(d))
        else:
            clusters = [[b] for b in bases]
        for cl in clusters:
            for j, L in enumerate(cl):
                if j == 0:
                    w = 1.0 if L.get("ord") else W_UNORD
                    kind = L["kind"]
                else:
                    w = W_ADD
                    kind = ("S07A" if d == 1 else "S07AS") + "-" + L["tf"]
                rows.append((L["rh"], L["eout"], RISK * w))
                legs_all.append(dict(kind=kind, d=d, rh=L["rh"], eout=L["eout"], ein=L["ein"], w=w))
    return rows, legs_all


def main():
    variants = {
        "Đầy đủ (mua + bán, vào sớm, vào lại, bồi)": dict(sides=(1, -1), early=True, re=True, adds=True),
        "Chỉ mua (vào sớm, vào lại, bồi)": dict(sides=(1,), early=True, re=True, adds=True),
        "Chỉ mua, lõi (gốc + bồi, không vào sớm / vào lại)": dict(sides=(1,), early=False, re=False, adds=True),
        "Chỉ bán (vào sớm, vào lại, bồi)": dict(sides=(-1,), early=True, re=True, adds=True),
    }
    L = ["# G89: Quy tắc S07Tester trên 10 năm dữ liệu MT5 (10/2016 – 10/2026)", "",
         "Bản Python của `S07Tester.mq5` (tester MT5 của broker chỉ có dữ liệu từ 02/2024). XAUUSD, chi phí khắt khe G68, "
         "rủi ro 1,5% × trọng số (gốc không nhãn EMA xếp thứ tự 0,67; bồi 0,67), lãi kép theo thứ tự đóng lệnh. "
         "Vào sớm / vào lại / bồi M15 chỉ có từ 20/07/2021 (cần nến M15). Không có số liệu ngoài mẫu: đây là chạy lại toàn kỳ.", ""]
    summary = []
    for name, var in variants.items():
        rows, legs = run(var)
        eq, dd, curve = equity(rows)
        yrs = (END - START) / (365.25 * 86400)
        d90, h20, h30 = dd_p90(rows)
        summary.append((name, len(rows), (eq ** (1 / yrs) - 1) * 100, dd * 100, d90 * 100, h20 * 100, h30 * 100, eq))
        # per year
        L += [f"## {name}", "", "| Năm | Lệnh | R tổng (theo trọng số) | Lãi năm | DD trong năm |", "|---|---|---|---|---|"]
        for y in range(2016, 2027):
            a, z = g.ts(y, 1, 1), g.ts(y + 1, 1, 1)
            yr = [x for x in rows if a <= x[1] < z]
            if not yr:
                continue
            eqy, ddy, _ = equity(yr)
            L.append(f"| {y} | {len(yr)} | {sum(r * w / RISK for r, _, w in yr):+.1f} | {(eqy - 1) * 100:+.0f}% | {ddy * 100:.0f}% |")
        kinds = {}
        for x in legs:
            k = x["kind"].split("-")[0]
            kinds.setdefault(k, []).append(x["rh"])
        L += ["", "Theo loại lệnh: " + "; ".join(f"{k} {len(v_)} lệnh {np.mean(v_):+.2f}R" for k, v_ in sorted(kinds.items())), ""]
        sys.stdout.buffer.write(f"done {name}\n".encode()); sys.stdout.flush()
    L += ["## Tổng hợp 10/2016 – 10/2026", "",
          "| Bản | Lệnh | %/năm (lãi kép) | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | Vốn cuối (×) |",
          "|---|---|---|---|---|---|---|---|"]
    for name, n, py, dd, d90, h20, h30, eq in summary:
        L.append(f"| {name} | {n} | {py:+.0f}% | {dd:.0f}% | {d90:.0f}% | {h20:.0f}% | {h30:.0f}% | {eq:.1f} |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
