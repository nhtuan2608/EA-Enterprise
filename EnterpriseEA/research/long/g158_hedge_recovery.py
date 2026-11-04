"""G158: no-stop hedge / averaging recovery on XAUUSD with price-action entry families vs random entries, real account model
(margin, stop-out at 50 % margin level, swap both sides), profit-time netting reduction to one runner plus runner exits taken from
earlier studies. Plan: docs/superpowers/plans/2026-11-04-g158-hedge-recovery.md.

Usage: g158_hedge_recovery.py <data dir> <raw D1 csv> <out dir>
"""
import calendar
import csv
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

START, SPLIT, END = g.ts(2018, 5, 1), g.ts(2023, 1, 1), g.ts(2026, 11, 1)
CAPITAL, BASE_LOT, CONTRACT = 10_000.0, 0.10, 100.0
COMM_PER_LOT = 6.0
SEED, RANDOM_RUNS = 158, 50


@dataclass(frozen=True)
class Cfg:
    mech: str = "R1"        # R1 grid averaging same side, R2 zone recovery (alternating hedge)
    mult: float = 1.0       # lot multiplier per new leg
    step: float = 1.0       # S = step x ATR14 D1 at basket start
    levels: int = 6         # max legs
    exit: str = "X0"        # runner exit
    leverage: float = 500.0
    swap: float = 30.0      # USD per lot per night, both sides (Wednesday x3)
    cost_mult: float = 1.0


# ---------------------------------------------------------------------------------------------------------------- data
def load_h1(root):
    g.set_tf("H1")
    g.DATA = root / "h1v"
    D = g.load("XAUUSD")
    return D


def daily(D):
    """Closed-day values per bar: ATR14 D1, R1 regime, previous day high / low; Asia range of today (from 08:00)."""
    t, h, l, c = D["t"], D["h"], D["l"], D["c"]
    n = len(c)
    day = t // 86400
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], n]
    dh = np.array([h[a:z].max() for a, z in zip(starts, ends)])
    dl = np.array([l[a:z].min() for a, z in zip(starts, ends)])
    dc = c[ends - 1]
    pc = np.r_[dc[0], dc[:-1]]
    tr = np.maximum(dh - dl, np.maximum(abs(dh - pc), abs(dl - pc)))
    atr = g.rma(tr, 14)
    e50 = g.ema(dc, 50)
    reg = np.zeros(len(dc), int)
    for k in range(60, len(dc)):
        if dc[k] > e50[k] and e50[k] > e50[k - 10]:
            reg[k] = 1
        elif dc[k] < e50[k] and e50[k] < e50[k - 10]:
            reg[k] = -1
    pos = np.searchsorted(day[starts], day) - 1                 # last closed day
    ok = pos >= 0
    P = lambda a: np.where(ok, a[np.maximum(pos, 0)], np.nan)  # noqa: E731
    hr = (t % 86400) // 3600
    ah, al = np.full(n, np.nan), np.full(n, np.nan)
    for a, z in zip(starts, ends):
        asia = (hr[a:z] >= 1) & (hr[a:z] <= 7)
        if asia.any():
            after = hr[a:z] >= 8
            ah[a:z][after] = h[a:z][asia].max()
            al[a:z][after] = l[a:z][asia].min()
    return {"atr_d1": P(atr), "reg": np.where(ok, reg[np.maximum(pos, 0)], 0), "pdh": P(dh), "pdl": P(dl), "ah": ah, "al": al}


def h4_frame(D):
    """H4 bars built from H1 and, per H1 bar, the number of H4 bars fully closed by its close."""
    t, o, h, l, c = D["t"], D["o"], D["h"], D["l"], D["c"]
    b = t // 14400
    starts = np.r_[0, np.nonzero(np.diff(b))[0] + 1]
    ends = np.r_[starts[1:], len(t)]
    H = {"o": o[starts], "h": np.array([h[a:z].max() for a, z in zip(starts, ends)]),
         "l": np.array([l[a:z].min() for a, z in zip(starts, ends)]), "c": c[ends - 1]}
    pc = np.r_[H["c"][0], H["c"][:-1]]
    H["atr"] = g.rma(np.maximum(H["h"] - H["l"], np.maximum(abs(H["h"] - pc), abs(H["l"] - pc))), 14)
    closed = np.zeros(len(t), int)
    k = 0
    end_idx = ends - 1
    for i in range(len(t)):
        while k < len(end_idx) and end_idx[k] <= i:
            k += 1
        closed[i] = k                                            # H4 bars 0..k-1 closed at the close of H1 bar i
    H["closed"] = closed
    return H


# ---------------------------------------------------------------------------------------------------------------- entries
def order_blocks(H):
    """H4 order blocks: (confirm H4 index, d, lo, hi). Bullish = last bearish H4 bar before a >= 2 ATR displacement within 3 bars
    that closes above its high and the previous 10-bar high (break of structure). Mirror for bearish."""
    o, h, l, c, A = H["o"], H["h"], H["l"], H["c"], H["atr"]
    out = []
    for k in range(10, len(c) - 3):
        if c[k] < o[k]:
            for m in (1, 2, 3):
                j = k + m
                if c[j] - c[k] >= 2 * A[k] and c[j] > h[k] and c[j] > h[k - 10:k].max():
                    out.append((j, 1, l[k], h[k]))
                    break
        if c[k] > o[k]:
            for m in (1, 2, 3):
                j = k + m
                if c[k] - c[j] >= 2 * A[k] and c[j] < l[k] and c[j] < l[k - 10:k].min():
                    out.append((j, -1, l[k], h[k]))
                    break
    return out


def entries(D, F, H):
    t, o, h, l, c, v = D["t"], D["o"], D["h"], D["l"], D["c"], D["v"]
    n = len(c)
    a1, E = D["atr"], D["E"]
    reg = F["reg"]
    fam = {k: [] for k in ("E1", "E2", "E3", "E4", "E5", "E6")}
    # H1 bar ranges per H4 index (first H1 bar after H4 bar j closed)
    first_after = np.searchsorted(H["closed"], np.arange(len(H["c"]) + 1), side="left")
    obs = order_blocks(H)
    for j, d, lo, hi in obs:
        i0 = first_after[j + 1] if j + 1 < len(first_after) else n
        i1 = first_after[min(j + 31, len(first_after) - 1)] if j + 31 < len(first_after) else n
        touched = None
        for i in range(i0, min(i1, n)):
            if (d == 1 and c[i] < lo) or (d == -1 and c[i] > hi):
                break                                               # invalidated
            inside = lo <= c[i] <= hi
            if inside and touched is None:
                touched = i
                fam["E1"].append((i, d))
                pad = 0.25 * H["atr"][j]
                levels = [x for x in (np.floor(lo / 25) * 25 + 25 * k for k in range(0, 3))]
                rn = any(lo - pad <= x <= hi + pad for x in levels)
                pd_ = any(np.isfinite(x) and lo - pad <= x <= hi + pad for x in (F["pdh"][i], F["pdl"][i]))
                if rn or pd_:
                    fam["E3"].append((i, d))
            if touched is not None and i - touched <= 6 and i > 0:
                engulf = (d == 1 and c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]) or \
                         (d == -1 and c[i] < o[i] and c[i - 1] > o[i - 1] and c[i] <= o[i - 1] and o[i] >= c[i - 1])
                disp = i >= 10 and ((d == 1 and c[i] - o[i] >= 1.5 * a1[i] and c[i] > h[i - 10:i].max()) or
                                    (d == -1 and o[i] - c[i] >= 1.5 * a1[i] and c[i] < l[i - 10:i].min()))
                if engulf or disp:
                    fam["E2"].append((i, d))
                    break
            if touched is not None and i - touched > 6:
                break
    e21, e50 = E[21], g.ema(c, 50)
    for i in range(14, n):
        d = int(reg[i])
        if d == 0:
            continue
        pb = all(d * (c[i - k] - c[i - k - 1]) < 0 for k in (1, 2, 3))
        if pb:
            ext = h[i - 10:i].max() if d == 1 else l[i - 10:i].min()
            deep = d * (ext - c[i - 1]) >= a1[i]
            band = (l[i - 1] <= max(e21[i - 1], e50[i - 1])) if d == 1 else (h[i - 1] >= min(e21[i - 1], e50[i - 1]))
            vpb = v[i - 3:i].mean()
            quiet = vpb < 0.8 * v[i - 13:i - 3].mean()
            resume = (d == 1 and c[i] > h[i - 1] and c[i] > o[i]) or (d == -1 and c[i] < l[i - 1] and c[i] < o[i])
            if deep and band and quiet and resume and v[i] > 1.2 * vpb:
                fam["E4"].append((i, d))
        lv = (min(x for x in (F["pdl"][i], F["al"][i]) if np.isfinite(x)) if d == 1 and np.isfinite(F["pdl"][i]) else
              (max(x for x in (F["pdh"][i], F["ah"][i]) if np.isfinite(x)) if d == -1 and np.isfinite(F["pdh"][i]) else None))
        if lv is not None and ((d == 1 and l[i] < lv < c[i]) or (d == -1 and h[i] > lv > c[i])):
            fam["E6"].append((i, d))
    # E5 OTE on confirmed 5/5 H1 pivots
    K = 5
    piv_h = [k for k in range(K, n - K) if h[k] == h[k - K:k + K + 1].max()]
    piv_l = [k for k in range(K, n - K) if l[k] == l[k - K:k + K + 1].min()]
    for d, A_, B_ in ((1, piv_l, piv_h), (-1, piv_h, piv_l)):
        bi = 0
        for a in A_:
            while bi < len(B_) and B_[bi] <= a:
                bi += 1
            if bi >= len(B_):
                break
            b = B_[bi]
            lo_, hi_ = (l[a], h[b]) if d == 1 else (l[b], h[a])
            if hi_ - lo_ < 3 * a1[b]:
                continue
            z1, z2 = (hi_ - 0.786 * (hi_ - lo_), hi_ - 0.618 * (hi_ - lo_)) if d == 1 else (lo_ + 0.618 * (hi_ - lo_), lo_ + 0.786 * (hi_ - lo_))
            for i in range(b + K + 1, min(b + K + 60, n)):
                if (d == 1 and c[i] < lo_) or (d == -1 and c[i] > hi_):
                    break
                if z1 <= c[i] <= z2 and reg[i] == d:
                    fam["E5"].append((i, d))
                    break
    return {k: sorted(set(x)) for k, x in fam.items()}


# ---------------------------------------------------------------------------------------------------------------- engine
def simulate(B, sig, cfg: Cfg, start, end, pessimistic=False):
    """B: bars dict (t, o, h, l, c, sp, atr (bar ATR), atr_d1, ema55, ema100). sig: {bar index: d}. Returns stats."""
    t, o, h, l, c, sp, atr_b = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["atr"]
    atr_d1, e55, e100 = B["atr_d1"], B["ema55"], B["ema100"]
    slip = 0.5 * B["sp_med"] * cfg.cost_mult
    comm = COMM_PER_LOT * cfg.cost_mult
    bal = CAPITAL
    legs = []                      # [side, lots, price]
    runner = None                  # dict(side, lots, price, best, S)
    S = 0.0
    last_add = 0.0
    ruins, ruin_times = 0, []
    peak, mdd = CAPITAL, 0.0
    max_lots, max_legs, swap_paid, first_leg_pnl, add_pnl, baskets = 0.0, 0, 0.0, 0.0, 0.0, 0
    worst_floating = 0.0
    equity_curve = []
    pending = None
    i0 = int(np.searchsorted(t, start))
    i1 = int(np.searchsorted(t, end))

    def exit_px(side, p, spread):          # closing price for a leg (sells close at ask)
        return (p - slip) if side == 1 else (p + spread + slip)

    def floating(p, spread, extra=()):
        tot = 0.0
        for s_, lt, e_ in list(legs) + list(extra):
            tot += s_ * (exit_px(s_, p, spread) - e_) * lt * CONTRACT
        return tot

    def margin(p):
        allv = list(legs) + ([(runner["side"], runner["lots"], runner["price"])] if runner else [])
        lg = sum(lt for s_, lt, _ in allv if s_ == 1)
        sh = sum(lt for s_, lt, _ in allv if s_ == -1)
        return max(lg, sh) * CONTRACT * p / cfg.leverage

    def open_leg(side, lots, p, spread):
        nonlocal bal
        e_ = p + spread + slip if side == 1 else p - slip
        bal -= comm * lots
        return [side, lots, e_]

    for i in range(max(i0, 1), i1):
        spread = sp[i]
        # swap at the day roll
        if t[i] // 86400 != t[i - 1] // 86400:
            lots_open = sum(x[1] for x in legs) + (runner["lots"] if runner else 0.0)
            if lots_open:
                mult = 3 if ((t[i] // 86400) + 3) % 7 == 3 else 1          # rollover into Thursday
                cost = cfg.swap * lots_open * mult
                bal -= cost
                swap_paid += cost
        # pending entry at the open
        if pending is not None and not legs and runner is None:
            d = pending
            S = cfg.step * atr_d1[i] if np.isfinite(atr_d1[i]) else 0.0
            if S > 0:
                legs = [open_leg(d, BASE_LOT, o[i], spread)]
                last_add = legs[0][2]
                baskets += 1
            pending = None
        # intrabar: adverse extreme first (adds, margin), then favourable (targets)
        if legs or runner:
            side0 = legs[0][0] if legs else runner["side"]
            path = [l[i], h[i]] if side0 == 1 else [h[i], l[i]]
            for p in path:
                # adds on the way (no stop)
                if legs and runner is None:
                    if cfg.mech == "R1":
                        d = legs[0][0]
                        while len(legs) < cfg.levels and d * (p - (last_add - d * S)) <= 0:
                            lvl = last_add - d * S
                            legs.append(open_leg(d, BASE_LOT * cfg.mult ** len(legs), lvl, spread))
                            last_add = lvl
                    else:   # R2 zone recovery: alternate sides at the two zone edges
                        top = legs[0][2] if legs[0][0] == 1 else legs[0][2] + S
                        bot = top - S
                        while len(legs) < cfg.levels:
                            cur = legs[-1][0]
                            edge = bot if cur == 1 else top
                            if (cur == 1 and p <= edge) or (cur == -1 and p >= edge):
                                legs.append(open_leg(-cur, legs[-1][1] * cfg.mult, edge, spread))
                            else:
                                break
                # runner turning against by S: becomes the first leg of a new cycle
                if runner is not None and runner["side"] * (p - runner["price"]) <= -S:
                    legs = [[runner["side"], runner["lots"], runner["price"]]]
                    last_add = runner["price"]
                    runner = None
                # margin / stop-out at this price
                lots_now = sum(x[1] for x in legs) + (runner["lots"] if runner else 0)
                max_lots = max(max_lots, lots_now)
                max_legs = max(max_legs, len(legs))
                fl = floating(p, spread, [(runner["side"], runner["lots"], runner["price"])] if runner else ())
                worst_floating = min(worst_floating, fl)
                eq = bal + fl
                mg = margin(p)
                mdd = min(1.0, max(mdd, 1 - eq / peak)) if peak > 0 else mdd   # 1.0 = wiped out
                if eq <= 0 or (mg > 0 and eq / mg < 0.5):
                    ruins += 1
                    ruin_times.append(int(t[i]))
                    bal, legs, runner, pending = CAPITAL, [], None, None
                    peak = CAPITAL
                    break
                # basket target -> netting reduction to one runner
                if legs:
                    target = 0.5 * S * BASE_LOT * CONTRACT
                    if floating(p, spread) >= target:
                        if cfg.exit == "X0":
                            pnl = floating(p, spread)
                            bal += pnl
                            first_leg_pnl += legs[0][0] * (exit_px(legs[0][0], p, spread) - legs[0][2]) * legs[0][1] * CONTRACT
                            add_pnl += pnl - legs[0][0] * (exit_px(legs[0][0], p, spread) - legs[0][2]) * legs[0][1] * CONTRACT
                            legs = []
                        else:
                            win_side = 1 if p > legs[-1][2] else -1
                            cand = [x for x in legs if x[0] == win_side and x[0] * (exit_px(x[0], p, spread) - x[2]) > 0]
                            keep = cand[-1] if cand else None
                            rest = [x for x in legs if x is not keep]
                            realized = sum(x[0] * (exit_px(x[0], p, spread) - x[2]) * x[1] * CONTRACT for x in rest)
                            if keep is None or realized < 0:
                                pnl = floating(p, spread)
                                bal += pnl
                                add_pnl += pnl
                                legs = []
                            else:
                                bal += realized
                                add_pnl += realized
                                runner = {"side": keep[0], "lots": keep[1], "price": keep[2], "best": p,
                                          "tp": keep[2] + keep[0] * 3 * S, "be": False}
                                legs = []
                # runner exits that can fill intrabar
                if runner is not None:
                    rs = runner["side"]
                    if cfg.exit == "X1" and rs * (p - runner["tp"]) >= 0:
                        bal += rs * (exit_px(rs, runner["tp"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                        runner = None
                    elif cfg.exit == "X4" and runner["be"] and rs * (p - runner["price"]) <= 0:
                        bal += rs * (exit_px(rs, runner["price"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                        runner = None
        # runner exits on the close
        if runner is not None:
            rs = runner["side"]
            runner["best"] = max(runner["best"], c[i]) if rs == 1 else min(runner["best"], c[i])
            runner["be"] = True
            done = False
            if cfg.exit in ("X2", "X4") and rs * (c[i] - runner["best"]) <= -3 * atr_b[i]:
                done = True
            if cfg.exit == "X3":
                ema = e100[i] if rs * (c[i] - runner["price"]) >= 3 * S else e55[i]
                done = rs * (c[i] - ema) < 0
            if done:
                bal += rs * (exit_px(rs, c[i], spread) - runner["price"]) * runner["lots"] * CONTRACT
                runner = None
        # equity on the close
        fl = floating(c[i], spread, [(runner["side"], runner["lots"], runner["price"])] if runner else ())
        eq = bal + fl
        peak = max(peak, eq)
        equity_curve.append((int(t[i]), eq))
        if i in sig and not legs and runner is None and pending is None:
            pending = sig[i]
    final = equity_curve[-1][1] if equity_curve else CAPITAL
    return {"cháy": ruins, "lúc cháy": ruin_times[:10], "vốn cuối": round(final, 0),
            "lãi ròng (bỏ qua các lần nạp lại)": round(final - CAPITAL * (1 + ruins), 0),
            "DD lớn nhất": round(mdd, 3), "lot mở tối đa": round(max_lots, 2), "số lệnh tối đa": max_legs,
            "swap đã trả": round(swap_paid, 0), "số rổ": baskets, "thả nổi tệ nhất": round(worst_floating, 0)}


def bars_h1(D, F):
    return {"t": D["t"], "o": D["o"], "h": D["h"], "l": D["l"], "c": D["c"], "sp": D["sp"], "sp_med": D["sp_med"], "atr": D["atr"],
            "atr_d1": F["atr_d1"], "ema55": D["E"][55], "ema100": D["E"][100]}


def bars_d1(path):
    rows = list(csv.reader(open(path, encoding="utf-8", errors="replace"), delimiter="\t"))[1:]
    t = np.array([calendar.timegm(time.strptime(r[0], "%Y.%m.%d")) for r in rows], dtype=np.int64)
    o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in (2, 3, 4, 5)) if len(rows[0]) > 8 else \
                 (np.array([float(r[k]) for r in rows]) for k in (1, 2, 3, 4))
    sp = np.array([float(r[-1]) for r in rows]) * 0.01
    sp = np.maximum(sp, 0.3)
    pc = np.r_[c[0], c[:-1]]
    atr = g.rma(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))), 14)
    atr_prev = np.r_[atr[0], atr[:-1]]
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "sp": sp, "sp_med": float(np.median(sp)), "atr": atr, "atr_d1": atr_prev,
            "ema55": g.ema(c, 55), "ema100": g.ema(c, 100)}


def grid():
    for mech, mult in (("R1", 1.0), ("R1", 1.5), ("R1", 2.0), ("R2", 1.5), ("R2", 2.0)):
        for step in (0.5, 1.0):
            for levels in (6, 10):
                for ex in ("X0", "X1", "X2", "X3", "X4"):
                    yield Cfg(mech=mech, mult=mult, step=step, levels=levels, exit=ex)


def neighbours(cfg):
    out = []
    for f, vals in (("step", (0.5, 1.0)), ("levels", (6, 10))):
        for v in vals:
            if getattr(cfg, f) != v:
                out.append(replace(cfg, **{f: v}))
    ladder = [("R1", 1.0), ("R1", 1.5), ("R1", 2.0)] if cfg.mech == "R1" else [("R2", 1.5), ("R2", 2.0)]
    k = ladder.index((cfg.mech, cfg.mult))
    for j in (k - 1, k + 1):
        if 0 <= j < len(ladder):
            out.append(replace(cfg, mech=ladder[j][0], mult=ladder[j][1]))
    return out


def rolling_ruin(B, sig, cfg):
    hits, n = 0, 0
    a = g.ts(2018, 5, 1)
    while a + 365 * 86400 <= END:
        r = simulate(B, sig, cfg, a, a + 365 * 86400)
        hits += r["cháy"] > 0
        n += 1
        a += 30 * 86400
    return hits / n if n else None


def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    D = load_h1(root)
    F = daily(D)
    H = h4_frame(D)
    fams = entries(D, F, H)
    B = bars_h1(D, F)
    sel_mask = lambda lst: [(i, d) for i, d in lst if START <= D["t"][i] < SPLIT]  # noqa: E731
    info = {k: {"tất cả": len([x for x in v if D["t"][x[0]] >= START]), "kỳ chọn": len(sel_mask(v))} for k, v in fams.items()}
    print("entries", info, f"{time.time() - t0:.0f}s", flush=True)
    res = {"số tín hiệu": info, "họ": {}}
    rng = random.Random(SEED)
    valid = np.nonzero((D["t"] >= START) & (D["t"] < END))[0]
    for fam, lst in fams.items():
        sig = {i: d for i, d in lst}
        rows = []
        for cfg in grid():
            r = simulate(B, sig, cfg, START, SPLIT)
            rows.append((cfg, r))
        ok = [x for x in rows if x[1]["cháy"] == 0]
        best_cfg, best = max(ok or rows, key=lambda x: x[1]["lãi ròng (bỏ qua các lần nạp lại)"])
        # random control with the same configuration and frequency (selection period)
        n_sel = max(1, len(sel_mask(lst)))
        pool = valid[(D["t"][valid] < SPLIT)]
        ctrl = []
        for k in range(RANDOM_RUNS):
            pick = rng.sample(list(pool), min(len(pool), n_sel))
            rs = {int(i): rng.choice((1, -1)) for i in pick}
            ctrl.append(simulate(B, rs, best_cfg, START, SPLIT))
        cp = [x["lãi ròng (bỏ qua các lần nạp lại)"] for x in ctrl]
        cr = [x["cháy"] for x in ctrl]
        entry_ok = best["lãi ròng (bỏ qua các lần nạp lại)"] > np.percentile(cp, 95) and best["cháy"] <= np.median(cr)
        # (B) viability of the best configuration
        chk = simulate(B, sig, best_cfg, SPLIT, END)
        row = {"cấu hình tốt nhất (kỳ chọn)": best_cfg.__dict__, "kỳ chọn": best, "kỳ kiểm": chk,
               "ngẫu nhiên cùng cấu hình": {"lãi ròng p50 / p95": [round(float(np.percentile(cp, 50)), 0), round(float(np.percentile(cp, 95)), 0)],
                                             "cháy p50 / max": [float(np.median(cr)), int(max(cr))],
                                             "tỷ lệ lần chạy có cháy": round(float(np.mean([x > 0 for x in cr])), 2)},
               "(A) entry có giá trị": bool(entry_ok),
               "số cấu hình 0 cháy kỳ chọn": len(ok), "trên tổng": len(rows)}
        rr = rolling_ruin(B, sig, best_cfg)
        harsh = simulate(B, sig, replace(best_cfg, swap=60.0, cost_mult=1.5), START, END)
        lev100 = simulate(B, sig, replace(best_cfg, leverage=100.0), START, END)
        nb = [simulate(B, sig, x, START, END) for x in neighbours(best_cfg)]
        row.update({"xác suất cháy trong 12 tháng": rr, "swap −60, chi phí × 1,5 (cả kỳ)": harsh, "đòn bẩy 1:100 (cả kỳ)": lev100,
                    "láng giềng 0 cháy": f"{sum(1 for x in nb if x['cháy'] == 0)}/{len(nb)}"})
        res["họ"][fam] = row
        print(fam, best_cfg, best, "| kiểm", chk, "| ctrl p95", np.percentile(cp, 95), "| rolling", rr, flush=True)
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    # stress: the recovery mechanisms of the best configurations on D1 2010-2018 with random entries (pessimistic path)
    Bd = bars_d1(raw_d1)
    st = {}
    for fam, row in res["họ"].items():
        cfg = Cfg(**row["cấu hình tốt nhất (kỳ chọn)"])
        idx = np.nonzero((Bd["t"] >= g.ts(2010, 3, 1)) & (Bd["t"] < g.ts(2018, 3, 1)))[0]
        runs = []
        for k in range(20):
            pick = rng.sample(list(idx), 60)
            runs.append(simulate(Bd, {int(i): rng.choice((1, -1)) for i in pick}, cfg, g.ts(2010, 3, 1), g.ts(2018, 3, 1), pessimistic=True))
        st[fam] = {"cấu hình": cfg.__dict__, "cháy trung bình / 8 năm": round(float(np.mean([x["cháy"] for x in runs])), 2),
                   "tỷ lệ lần chạy có cháy": round(float(np.mean([x["cháy"] > 0 for x in runs])), 2),
                   "DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in runs])), 3)}
        print("stress", fam, st[fam], flush=True)
    res["stress D1 2010–2018 (entry ngẫu nhiên, bi quan)"] = st
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
