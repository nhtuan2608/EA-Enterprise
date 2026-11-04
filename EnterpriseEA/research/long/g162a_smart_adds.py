"""G162a: confirmed structure adds (S2), half-then-trail runner (X9) and a 1 ADR lock (H4) on the G161 E4 basket-stop grid,
vs fixed-step adds (A0), a single trade with the same stop (C1), random entries (C2) and random-bar adds.
Plan: docs/superpowers/plans/2026-11-04-g162-smart-adds.md (branch A). With S2 / X9 / H4 off the engine reproduces G161 with P1 off.

Usage: g162a_smart_adds.py <data dir> <raw D1 csv> <out dir>
"""
import itertools
import json
import random
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g158_hedge_recovery as g8  # noqa: E402
import g159a_modules as m9  # noqa: E402
import g161_grid_sl as g1  # noqa: E402

START, SPLIT, END = g8.START, g8.SPLIT, g8.END
CAPITAL, BASE_LOT, CONTRACT, COMM = g8.CAPITAL, g8.BASE_LOT, g8.CONTRACT, g8.COMM_PER_LOT
SEED = 162
S_A, S_Z = g.ts(2010, 3, 1), g.ts(2018, 3, 1)
LOOKBACK = 240                   # swing levels older than this many bars are dropped


@dataclass(frozen=True)
class Cfg:
    mult: float = 1.0
    step: float = 0.5
    levels: int = 4
    sl: float = 0.04
    s2: bool = False
    x9: bool = False
    h4: bool = False
    rand_add: float = 0.0        # > 0: add with this probability on eligible bars instead of S2 (random-bar control)
    swap: float = 30.0
    cost_mult: float = 1.0
    leverage: float = 500.0


def structure(B, K=5):
    """Per bar: confirmed pivot lows / highs (confirm index, price), previous-day low / high, Asia low / high (nan if not known), ADR20."""
    t, h, l = B["t"], B["h"], B["l"]
    n = len(h)
    plo, phi = [], []
    for k in range(K, n - K):
        if l[k] == l[k - K:k + K + 1].min():
            plo.append((k + K, float(l[k])))
        if h[k] == h[k - K:k + K + 1].max():
            phi.append((k + K, float(h[k])))
    day = t // 86400
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], n]
    rng_d = np.array([h[a:z].max() - l[a:z].min() for a, z in zip(starts, ends)])
    adr = np.convolve(rng_d, np.ones(20) / 20, "full")[:len(rng_d)]
    adr[:19] = np.nan
    pos = np.searchsorted(starts, np.arange(n), side="right") - 2            # last closed day
    B["adr20"] = np.where(pos >= 0, adr[np.maximum(pos, 0)], np.nan)
    B["plo"], B["phi"] = plo, phi
    if "pdl" not in B:
        B["pdl"] = np.r_[np.nan, l[:-1]]
        B["pdh"] = np.r_[np.nan, h[:-1]]
        B["al"] = np.full(n, np.nan)
        B["ah"] = np.full(n, np.nan)
    return B


def simulate(B, sig, cfg: Cfg, start, end, rng=None, stats=None):
    t, o, h, l, c, sp, atr_b = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["atr"]
    atr_d1, adr = B["atr_d1"], B["adr20"]
    slip = 0.5 * B["sp_med"] * cfg.cost_mult
    comm = COMM * cfg.cost_mult
    bal = CAPITAL
    legs, runner, hedge = [], None, None
    S, last_add, first_px = 0.0, 0.0, 0.0
    used = set()
    ruins, peak, mdd, max_lots, swap_paid = 0, CAPITAL, 0.0, 0.0, 0.0
    bal_start, pending = CAPITAL, None
    baskets = []
    n_adds = n_elig = n_locks = 0
    i0, i1 = int(np.searchsorted(t, start)), int(np.searchsorted(t, end))
    plo, phi = B["plo"], B["phi"]
    jlo = jhi = 0
    act_lo, act_hi = [], []

    def xpx(side, p, spread):
        return (p - slip) if side == 1 else (p + spread + slip)

    def pnl_of(x, p, spread):
        return x[0] * (xpx(x[0], p, spread) - x[2]) * x[1] * CONTRACT

    def all_legs():
        out = list(legs)
        if runner:
            out.append([runner["side"], runner["lots"], runner["price"]])
        if hedge:
            out.append(hedge)
        return out

    def floating(p, spread):
        return sum(pnl_of(x, p, spread) for x in all_legs())

    def margin(p):
        al = all_legs()
        return max(sum(x[1] for x in al if x[0] == 1), sum(x[1] for x in al if x[0] == -1)) * CONTRACT * p / cfg.leverage

    def open_leg(side, lots, p, spread):
        nonlocal bal
        bal -= comm * lots
        return [side, lots, p + spread + slip if side == 1 else p - slip]

    def close_basket(reason):
        nonlocal bal_start
        baskets.append((bal - bal_start, cfg.sl * bal_start, reason))
        bal_start = bal

    def stop_price(spread, p):
        thr = bal_start * (1 - cfg.sl)
        e0, e1 = bal + floating(p, spread), bal + floating(p + 1.0, spread)
        slope = e1 - e0
        return None if abs(slope) < 1e-6 else p + (thr - e0) / slope

    for i in range(max(i0, 1), i1):
        spread = sp[i]
        while jlo < len(plo) and plo[jlo][0] <= i:
            act_lo.append(plo[jlo]); jlo += 1
        while jhi < len(phi) and phi[jhi][0] <= i:
            act_hi.append(phi[jhi]); jhi += 1
        if i % 50 == 0:
            act_lo = [x for x in act_lo if i - x[0] <= LOOKBACK]
            act_hi = [x for x in act_hi if i - x[0] <= LOOKBACK]
        if t[i] // 86400 != t[i - 1] // 86400:
            lots_open = sum(x[1] for x in all_legs())
            if lots_open:
                cost = cfg.swap * lots_open * (3 if ((t[i] // 86400) + 3) % 7 == 3 else 1)
                bal -= cost
                swap_paid += cost
        if pending is not None and not legs and runner is None and hedge is None:
            d = pending
            S = cfg.step * atr_d1[i] if np.isfinite(atr_d1[i]) else 0.0
            if S > 0:
                bal_start = bal
                legs = [open_leg(d, BASE_LOT, o[i], spread)]
                last_add = first_px = legs[0][2]
                used = set()
            pending = None
        if legs or runner or hedge:
            side0 = legs[0][0] if legs else (runner["side"] if runner else -hedge[0])
            path = [l[i], h[i]] if side0 == 1 else [h[i], l[i]]
            for p in path:
                stopped = False
                if legs and runner is None and hedge is None and not cfg.s2 and cfg.rand_add == 0:
                    d = legs[0][0]
                    while len(legs) < cfg.levels and d * (p - (last_add - d * S)) <= 0:
                        lvl = last_add - d * S
                        sp_ = stop_price(spread, lvl)
                        if sp_ is not None and d * (lvl - sp_) <= 0:
                            break
                        legs.append(open_leg(d, BASE_LOT * cfg.mult ** len(legs), lvl, spread))
                        last_add = lvl
                if runner is not None and runner["side"] * (p - runner["price"]) <= -S:
                    legs = [[runner["side"], runner["lots"], runner["price"]]]
                    last_add = runner["price"]
                    runner = None
                if legs or runner or hedge:
                    d = side0
                    if hedge is not None:
                        hit = bal + floating(p, spread) <= bal_start * (1 - cfg.sl)
                        fill = p
                    else:
                        sp_ = stop_price(spread, p)
                        hit = sp_ is not None and d * (p - sp_) <= 0
                        fill = (o[i] if d * (o[i] - sp_) < 0 else sp_) if hit else p
                    if hit:
                        bal += floating(fill, spread)
                        legs, runner, hedge = [], None, None
                        close_basket("SL")
                        stopped = True
                max_lots = max(max_lots, sum(x[1] for x in all_legs()))
                fl = floating(p, spread)
                eq = bal + fl
                mg = margin(p)
                mdd = min(1.0, max(mdd, 1 - eq / peak)) if peak > 0 else mdd
                if stopped:
                    break
                if eq <= 0 or (mg > 0 and eq / mg < 0.5):
                    ruins += 1
                    baskets.append((-bal_start, cfg.sl * bal_start, "cháy"))
                    bal, legs, runner, hedge, pending = CAPITAL, [], None, None, None
                    bal_start, peak = CAPITAL, CAPITAL
                    break
                target = 0.5 * S * BASE_LOT * CONTRACT
                if hedge is not None and fl >= target:
                    bal += fl
                    legs, runner, hedge = [], None, None
                    close_basket("mục tiêu (khóa)")
                    break
                if legs and fl >= target:
                    win_side = 1 if p > legs[-1][2] else -1
                    cand = [x for x in legs if x[0] == win_side and pnl_of(x, p, spread) > 0]
                    keep = cand[-1] if cand else None
                    rest = [x for x in legs if x is not keep]
                    realized = sum(pnl_of(x, p, spread) for x in rest)
                    if keep is None or realized < 0:
                        bal += fl
                        legs = []
                        if runner is None:
                            close_basket("mục tiêu")
                    else:
                        bal += realized
                        runner = {"side": keep[0], "lots": keep[1], "price": keep[2], "tp": keep[2] + keep[0] * 3 * S,
                                  "half": False, "best": p}
                        legs = []
                if runner is not None:
                    rs = runner["side"]
                    if not cfg.x9 and rs * (p - runner["tp"]) >= 0:
                        bal += rs * (xpx(rs, runner["tp"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                        runner = None
                        close_basket("lệnh chạy")
                    elif cfg.x9 and not runner["half"] and rs * (p - (runner["price"] + rs * S)) >= 0:
                        px = runner["price"] + rs * S
                        half = runner["lots"] / 2
                        bal += rs * (xpx(rs, px, spread) - runner["price"]) * half * CONTRACT
                        runner["lots"] -= half
                        runner["half"] = True
            # bar-close actions
            if legs and runner is None and hedge is None and (cfg.s2 or cfg.rand_add > 0) and len(legs) < cfg.levels:
                d = legs[0][0]
                lim = last_add - d * 0.5 * S
                eligible = d * (c[i] - lim) <= 0 or d * ((l[i] if d == 1 else h[i]) - lim) <= 0
                if eligible:
                    n_elig += 1
                do_add = False
                if cfg.rand_add > 0:
                    do_add = eligible and rng.random() < cfg.rand_add
                else:
                    rngb = h[i] - l[i]
                    wick = (min(o[i], c[i]) - l[i]) if d == 1 else (h[i] - max(o[i], c[i]))
                    conf = rngb > 0 and wick >= 0.5 * rngb and d * (c[i] - o[i]) > 0
                    if conf:
                        cands = [x[1] for x in (act_lo if d == 1 else act_hi)]
                        for v in ((B["pdl"][i], B["al"][i]) if d == 1 else (B["pdh"][i], B["ah"][i])):
                            if np.isfinite(v):
                                cands.append(float(v))
                        r0 = np.floor(lim / 25) * 25 if d == 1 else np.ceil(lim / 25) * 25
                        cands.append(float(r0))
                        for v in cands:
                            key = round(v, 2)
                            if key in used or d * (v - lim) > 0:
                                continue
                            touched = (l[i] <= v < c[i]) if d == 1 else (h[i] >= v > c[i])
                            if touched:
                                used.add(key)
                                do_add = True
                                break
                if do_add:
                    sp_ = stop_price(spread, c[i])
                    if not (sp_ is not None and d * (c[i] - sp_) <= 0):
                        legs.append(open_leg(d, BASE_LOT * cfg.mult ** len(legs), c[i], spread))
                        last_add = c[i]
                        n_adds += 1
            if cfg.h4 and legs and hedge is None and runner is None and np.isfinite(adr[i]):
                d = legs[0][0]
                if d * (first_px - c[i]) >= adr[i]:
                    hedge = open_leg(-d, sum(x[1] for x in legs), c[i], spread)
                    n_locks += 1
            elif hedge is not None and legs:
                d = legs[0][0]
                if pnl_of(hedge, c[i], spread) >= S * hedge[1] * CONTRACT or d * (first_px - c[i]) <= 0.5 * adr[i]:
                    bal += pnl_of(hedge, c[i], spread)
                    hedge = None
                    last_add = c[i]
        if runner is not None and cfg.x9:
            rs = runner["side"]
            runner["best"] = max(runner["best"], c[i]) if rs == 1 else min(runner["best"], c[i])
            if runner["half"] and rs * (c[i] - runner["best"]) <= -3 * atr_b[i]:
                bal += rs * (xpx(rs, c[i], spread) - runner["price"]) * runner["lots"] * CONTRACT
                runner = None
                close_basket("lệnh chạy")
        peak = max(peak, bal + floating(c[i], sp[i]))
        if i in sig and not legs and runner is None and hedge is None and pending is None:
            pending = sig[i]
    final = bal + (floating(c[i1 - 1], sp[i1 - 1]) if (legs or runner or hedge) and i1 > 0 else 0.0)
    if stats is not None:
        stats.update(adds=n_adds, eligible=n_elig, locks=n_locks)
    bp = np.array([b[0] for b in baskets]) if baskets else np.zeros(1)
    R = np.array([b[1] for b in baskets]) if baskets else np.ones(1)
    wins, losses = bp[bp > 0], bp[bp <= 0]
    gross = float(wins.sum())
    reasons = {}
    for b in baskets:
        reasons[b[2]] = reasons.get(b[2], 0) + 1
    net = final - CAPITAL * (1 + ruins)
    return {"cháy": ruins, "lãi ròng": round(net, 0), "DD lớn nhất": round(mdd, 3), "MAR": round(net / max(mdd, 1e-3) / CAPITAL, 2),
            "số rổ": len(baskets), "tỷ lệ rổ thắng": round(float(len(wins) / len(bp)), 3) if baskets else None,
            "PF": round(gross / abs(float(losses.sum())), 2) if losses.sum() < 0 else None,
            "kỳ vọng R": round(float(np.mean(bp / np.where(R > 0, R, np.nan))), 3) if baskets else None,
            "lý do kết thúc": reasons, "lot mở tối đa": round(max_lots, 2), "swap / lãi gộp": round(swap_paid / gross, 3) if gross > 0 else None,
            "số lần bồi (S2 / ngẫu nhiên)": n_adds, "số lần khóa": n_locks}


def rolling(B, sig, cfg):
    ruin = dd30 = n = 0
    a = g.ts(2018, 5, 1)
    while a + 365 * 86400 <= END:
        x = simulate(B, sig, cfg, a, a + 365 * 86400)
        ruin += x["cháy"] > 0
        dd30 += x["DD lớn nhất"] >= 0.30
        n += 1
        a += 30 * 86400
    return round(ruin / n, 3), round(dd30 / n, 3)


def neighbours(cfg):
    ls = {0.02: (0.04,), 0.04: (0.02, 0.06), 0.06: (0.04,)}[cfg.sl]
    return [replace(cfg, sl=x) for x in ls] + [replace(cfg, step=1.0 if cfg.step == 0.5 else 0.5),
                                               replace(cfg, levels=6 if cfg.levels == 4 else 4),
                                               replace(cfg, mult=1.5 if cfg.mult == 1.0 else 1.0)]


def name(cfg):
    return "A0" if not (cfg.s2 or cfg.x9 or cfg.h4) else {(True, False, False): "A1", (True, True, False): "A2", (True, False, True): "A3",
                                                         (True, True, True): "A4"}[(cfg.s2, cfg.x9, cfg.h4)]


def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    D = g8.load_h1(root)
    F = g8.daily(D)
    H = g8.h4_frame(D)
    B = g8.bars_h1(D, F)
    B.update(pdl=F["pdl"], pdh=F["pdh"], al=F["al"], ah=F["ah"])
    B = structure(B)
    sig = {i: d for i, d in g8.entries(D, F, H)["E4"]}
    mine = simulate(B, sig, Cfg(sl=0.06), START, SPLIT)
    ref = g1.simulate(B, sig, g1.Cfg(mult=1.0, step=0.5, levels=4, sl=0.06, p1=False), START, SPLIT)
    same = (mine["cháy"], mine["lãi ròng"], mine["DD lớn nhất"]) == (ref["cháy"], ref["lãi ròng"], ref["DD lớn nhất"])
    print("check vs G161 (P1 off):", "khớp" if same else f"LỆCH {mine['lãi ròng']} {mine['DD lớn nhất']} vs {ref['lãi ròng']} {ref['DD lớn nhất']}",
          flush=True)
    res = {"kiểm code (A0 = G161 tắt P1)": bool(same), "A0": {}, "cấu hình": [], "lệnh đơn C1": {}}
    for L in (0.02, 0.04, 0.06):
        c1 = g1.Cfg(sl=L, single=True, p1=False)
        res["lệnh đơn C1"][f"L {L:.0%}"] = {"kỳ chọn": g1.simulate(B, sig, c1, START, SPLIT), "kỳ kiểm": g1.simulate(B, sig, c1, SPLIT, END)}
        a0 = Cfg(sl=L)
        res["A0"][f"L {L:.0%}"] = {"kỳ chọn": simulate(B, sig, a0, START, SPLIT), "kỳ kiểm": simulate(B, sig, a0, SPLIT, END)}
    grid = [Cfg(sl=L, s2=True, x9=x9, h4=h4) for (x9, h4), L in itertools.product(((False, False), (True, False), (False, True), (True, True)),
                                                                                  (0.02, 0.04, 0.06))]
    for cfg in grid:
        sel = simulate(B, sig, cfg, START, SPLIT)
        kk = simulate(B, sig, cfg, SPLIT, END)
        res["cấu hình"].append({"mã": name(cfg), "L": cfg.sl, "kỳ chọn": sel, "kỳ kiểm (chỉ báo cáo)": kk})
        print(name(cfg), cfg.sl, "| chọn", sel["cháy"], sel["lãi ròng"], "DD", sel["DD lớn nhất"], "MAR", sel["MAR"], "PF", sel["PF"],
              "bồi", sel["số lần bồi (S2 / ngẫu nhiên)"], "khóa", sel["số lần khóa"], "| kiểm", kk["lãi ròng"], kk["MAR"], sel["lý do kết thúc"],
              flush=True)
    for k, v in res["A0"].items():
        print("A0", k, "| chọn", v["kỳ chọn"]["lãi ròng"], v["kỳ chọn"]["MAR"], "| kiểm", v["kỳ kiểm"]["lãi ròng"], v["kỳ kiểm"]["MAR"], flush=True)
    ok = [(r, c) for r, c in zip(res["cấu hình"], grid) if r["kỳ chọn"]["cháy"] == 0 and r["kỳ chọn"]["lãi ròng"] > 0]
    if not ok:
        res["kết luận"] = "không cấu hình nào 0 cháy và lãi > 0 ở kỳ chọn"
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        print("none selectable")
        return
    row, cfg = max(ok, key=lambda rc: rc[0]["kỳ chọn"]["MAR"])
    kk = row["kỳ kiểm (chỉ báo cáo)"]
    full_stats = {}
    full = simulate(B, sig, cfg, START, END, stats=full_stats)
    harsh = simulate(B, sig, replace(cfg, swap=60.0, cost_mult=1.5), START, END)
    rr, dd30 = rolling(B, sig, cfg)
    # D1 stress (structure from D1 bars: pivots, previous-day levels, round numbers; no Asia range)
    Bd = structure(m9.add_structure_d1(g8.bars_d1(raw_d1)))
    prng = random.Random(SEED)
    sidx = list(np.nonzero((Bd["t"] >= S_A) & (Bd["t"] < S_Z))[0])
    st = [simulate(Bd, {int(i): prng.choice((1, -1)) for i in prng.sample(sidx, 60)}, cfg, S_A, S_Z) for _ in range(20)]
    c1k = res["lệnh đơn C1"][f"L {cfg.sl:.0%}"]["kỳ kiểm"]
    a0k = res["A0"][f"L {cfg.sl:.0%}"]["kỳ kiểm"]
    valid = list(np.nonzero((D["t"] >= START) & (D["t"] < END))[0])
    n_sig = len([1 for i in sig if START <= D["t"][i] < END])
    ctl = [simulate(B, {int(i): prng.choice((1, -1)) for i in prng.sample(valid, n_sig)}, cfg, START, END) for _ in range(50)]
    cp = [x["lãi ròng"] for x in ctl]
    # random-bar adds with the same add rate
    q = full_stats["adds"] / max(full_stats["eligible"], 1)
    nrng = np.random.default_rng(SEED)
    radd = [simulate(B, sig, replace(cfg, s2=False, rand_add=q), START, END, rng=nrng) for _ in range(50)]
    rp = [x["lãi ròng"] for x in radd]
    nb_rows, nb_ok = [], 0
    for x_cfg in neighbours(cfg):
        b = simulate(B, sig, x_cfg, SPLIT, END)
        fx = simulate(B, sig, x_cfg, START, END)
        good = b["cháy"] == 0 and b["lãi ròng"] > 0 and (b["PF"] or 0) >= 1.1 and fx["DD lớn nhất"] < 0.30
        nb_ok += good
        nb_rows.append({"cfg": {"mult": x_cfg.mult, "levels": x_cfg.levels, "step": x_cfg.step, "L": x_cfg.sl}, "kỳ kiểm": b,
                        "DD cả kỳ": fx["DD lớn nhất"], "thỏa 1 và 2": good})
    crit = {
        "1 kỳ kiểm 0 cháy, lãi > 0, PF ≥ 1,1": kk["cháy"] == 0 and kk["lãi ròng"] > 0 and (kk["PF"] or 0) >= 1.1,
        "2 DD < 30 %": full["DD lớn nhất"] < 0.30,
        "3 cháy 12 tháng = 0, DD ≥ 30 % ≤ 5 %": rr == 0 and dd30 <= 0.05,
        "4 khắc nghiệt lãi > 0": harsh["lãi ròng"] > 0,
        "5 stress 0 cháy, DD trung vị < 30 %": sum(x["cháy"] > 0 for x in st) == 0 and float(np.median([x["DD lớn nhất"] for x in st])) < 0.30,
        "6 MAR kỳ kiểm > lệnh đơn": kk["MAR"] > c1k["MAR"],
        "7 hơn p95 ngẫu nhiên": full["lãi ròng"] > float(np.percentile(cp, 95)),
        "8 láng giềng ≥ 2/3": nb_ok >= int(np.ceil(2 * len(nb_rows) / 3)),
        "9 MAR kỳ kiểm > A0 cùng L": kk["MAR"] > a0k["MAR"],
    }
    res["được chọn"] = {
        "mã": row["mã"], "L": cfg.sl, "kỳ chọn": row["kỳ chọn"], "kỳ kiểm": kk, "cả kỳ": full, "khắc nghiệt": harsh,
        "cháy 12 tháng": rr, "DD 12 tháng ≥ 30 %": dd30,
        "stress: lần cháy / 20": sum(x["cháy"] > 0 for x in st), "stress DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in st])), 3),
        "stress lãi ròng trung vị": float(np.median([x["lãi ròng"] for x in st])),
        "lệnh đơn C1 kỳ kiểm": c1k, "A0 kỳ kiểm": a0k,
        "ngẫu nhiên C2": {"lãi ròng p50 / p95": [float(np.percentile(cp, 50)), float(np.percentile(cp, 95))],
                          "% lần chạy có cháy": round(float(np.mean([x["cháy"] > 0 for x in ctl])), 2)},
        "bồi ở nến ngẫu nhiên (cùng tỷ lệ)": {"tỷ lệ bồi mỗi nến đủ điều kiện": round(q, 4),
                                              "lãi ròng p50 / p95": [float(np.percentile(rp, 50)), float(np.percentile(rp, 95))],
                                              "phân vị của S2": round(float(np.mean(np.array(rp) < full["lãi ròng"])), 3)},
        "láng giềng": nb_rows, "láng giềng đạt": f"{nb_ok}/{len(nb_rows)}", "tiêu chí": crit, "đạt": all(crit.values())}
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    s = res["được chọn"]
    print("chosen", s["mã"], cfg.sl, "\n kiểm", kk, "\n full", full, "\n C1", c1k["lãi ròng"], c1k["MAR"], "| A0", a0k["lãi ròng"], a0k["MAR"],
          "\n C2", s["ngẫu nhiên C2"], "\n rand adds", s["bồi ở nến ngẫu nhiên (cùng tỷ lệ)"], "\n stress", s["stress: lần cháy / 20"],
          s["stress DD trung vị"], "| 12th", rr, dd30, "| nb", s["láng giềng đạt"], "\n crit", crit, "\ndone", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
