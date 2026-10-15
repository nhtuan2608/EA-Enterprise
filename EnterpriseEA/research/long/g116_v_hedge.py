"""G116: M5 EMA200 V-candle return hedge with an add on the surviving side (plan docs/superpowers/plans/2026-10-14-g116-ema200-v-hedge.md).

  python g116_v_hedge.py            -> grid on train / validate, OCO and random controls for the train pick
  python g116_v_hedge.py examples   -> the user's 06-07/10/2026 examples (sealed test period: illustration only)

Units: U = V high - V low + 2 x buffer (the group's loss when both legs are stopped, before spread).
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from g97_forming_bar import dmi, ema

HERE = Path(__file__).resolve().parent
PERIODS = {"train": ("2024-05-14", "2025-07-01"), "validate": ("2025-07-01", "2026-01-01"), "test": ("2026-01-01", "2027-01-01")}
RET_BARS = 6
CAP = 288


def load():
    m = pd.read_csv(HERE / "data" / "m5v" / "XAUUSD.csv")
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    c = m["close"].to_numpy()
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * 0.01
    return m


def find_groups(m, pseudo=False):
    """(v, j): V candle v and its return bar j (entry at j+1 open). pseudo: V = a bar near EMA200 that does not cross."""
    o, c, h, l, e, a = (m[k].to_numpy() for k in ("open", "close", "high", "low", "e200", "atr"))
    body = ((o < e) & (c > e)) | ((o > e) & (c < e))
    if pseudo:
        cand = (~body) & (np.abs(c - e) < a) & ~((h > e) & (l < e))
    else:
        cand = body
    out, used = [], set()
    for v in np.flatnonzero(cand):
        if v < 300:
            continue
        left = False
        for j in range(v + 1, min(v + 1 + RET_BARS, len(c) - 1)):
            if l[v] <= c[j] <= h[v]:
                if left:
                    if j not in used:
                        used.add(j)
                        out.append((v, j))
                    break
            else:
                left = True
    return out


class Sim:
    def __init__(self, m):
        self.m = m
        self.o, self.h, self.l, self.c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sp, self.atr, self.adx = m["sp"].to_numpy(), m["atr"].to_numpy(), m["adx"].to_numpy()
        self.e21, self.e55, self.e100 = m["e21"].to_numpy(), m["e55"].to_numpy(), m["e100"].to_numpy()

    def manage(self, t, d, legs, surv_entry, surv_sl, mode, k):
        """legs: list of [entry, sl] in direction d, opened by bar t (management from t+1). Returns pnl (price units)."""
        o, h, l, c, sp = self.o, self.h, self.l, self.c, self.sp
        R = d * (surv_entry - surv_sl)
        if R <= 0:
            return None
        tp = surv_entry + d * k * R
        hold = False
        if mode == "X3":
            fan = (self.e21[t] > self.e55[t] > self.e100[t]) if d == 1 else (self.e21[t] < self.e55[t] < self.e100[t])
            hold = fan and self.adx[t] > self.adx[t - 1]
            if not hold:
                tp = surv_entry + d * 2.0 * R
        best = surv_entry
        closed = [None] * len(legs)
        be_done = False
        end = min(len(c) - 1, t + CAP)
        j = t + 1
        exit_all = None
        while j <= end:
            for i, L in enumerate(legs):
                if closed[i] is None and ((d == 1 and l[j] <= L[1]) or (d == -1 and h[j] + sp[j] >= L[1])):
                    closed[i] = L[1]
            if all(x is not None for x in closed):
                break
            if not hold and ((d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp)):
                exit_all = tp
                break
            best = max(best, h[j]) if d == 1 else min(best, l[j])
            if not be_done and d * (best - surv_entry) >= R:
                be_done = True
                for i, L in enumerate(legs):
                    if d * (L[0] - L[1]) > 0 and d * (L[0] - L[1]) > 0:
                        L[1] = L[0] if d * (L[0] - L[1]) > 0 else L[1]
            if hold:
                emax = self.e100[j] if d * (best - surv_entry) >= 3 * R else self.e55[j]
                if d * (c[j] - emax) < 0:
                    exit_all = c[j] + (sp[j] if d == -1 else 0.0)
                    break
            j += 1
        if exit_all is None and any(x is None for x in closed):
            jj = min(j, end)
            exit_all = c[jj] + (sp[jj] if d == -1 else 0.0)
        pnl = 0.0
        for i, L in enumerate(legs):
            px = closed[i] if closed[i] is not None else exit_all
            pnl += d * (px - L[0])
        return pnl

    def hedge(self, v, j, B, N, H, S, X, k):
        o, h, l, c, sp = self.o, self.h, self.l, self.c, self.sp
        e = j + 1
        if e + 2 >= len(c):
            return None
        b = B * self.atr[j]
        VH, VL = h[v], l[v]
        U = VH - VL + 2 * b
        buy_e, sell_e = o[e] + sp[e], o[e]
        buy_sl, sell_sl = VL - b, VH + b
        if not (buy_sl < buy_e and sell_sl > sell_e):
            return None
        mid = 0.5 * (VH + VL)
        t = e
        end = min(len(c) - 1, e + CAP)
        while t <= end:
            bs = l[t] <= buy_sl
            ss = h[t] + sp[t] >= sell_sl
            if bs and ss:
                return ((buy_sl - buy_e) + (sell_e - sell_sl)) / U, 0, t
            if bs or ss:
                d = -1 if bs else 1
                lost = (buy_sl - buy_e) if bs else (sell_e - sell_sl)
                surv_entry, surv_sl = (sell_e, sell_sl) if bs else (buy_e, buy_sl)
                add_e = buy_sl if bs else sell_sl
                add_sl = surv_sl if S == "SAME" else mid
                legs = [[surv_entry, surv_sl]]
                if d * (add_e - add_sl) > 0:
                    legs.append([add_e, add_sl])
                p = self.manage(t, d, legs, surv_entry, surv_sl, X, k)
                if p is None:
                    return None
                return (lost + p) / U, d, t
            if H == "C" and t - e + 1 >= N:
                return ((c[t] - buy_e) + (sell_e - (c[t] + sp[t]))) / U, 0, t
            t += 1
        return ((c[end] - buy_e) + (sell_e - (c[end] + sp[end]))) / U, 0, end

    def oco(self, v, j, B, N, H, S, X, k):
        o, h, l, c, sp = self.o, self.h, self.l, self.c, self.sp
        e = j + 1
        if e + 2 >= len(c):
            return None
        b = B * self.atr[j]
        VH, VL = h[v], l[v]
        U = VH - VL + 2 * b
        up, dn = VH + b, VL - b
        if not (o[e] + sp[e] < up and o[e] > dn):
            return None
        mid = 0.5 * (VH + VL)
        end = min(len(c) - 1, e + CAP)
        t = e
        while t <= end:
            bu = h[t] + sp[t] >= up
            bd = l[t] <= dn
            if bu and bd:
                return -1.0 - sp[t] / U, 0, t
            if bu or bd:
                d = 1 if bu else -1
                entry = up if bu else dn
                sl = dn if bu else up
                add_sl = sl if S == "SAME" else mid
                legs = [[entry, sl], [entry, add_sl]] if d * (entry - add_sl) > 0 else [[entry, sl]]
                p = self.manage(t, d, legs, entry, sl, X, k)
                if p is None:
                    return None
                return (p - (0.0 if d == -1 else 0.0)) / U, d, t
            if H == "C" and t - e + 1 >= N:
                return 0.0, 0, t
            t += 1
        return 0.0, 0, end


def run(S_, groups, fn, cfg):
    rows = []
    ts = S_.m["ts"].to_numpy()
    for v, j in groups:
        res = fn(v, j, *cfg)
        if res is None:
            continue
        r, d, t = res
        rows.append((ts[j], r, d))
    return pd.DataFrame(rows, columns=["t", "r", "d"])


def stats(t, p):
    a, b = PERIODS[p]
    x = t[(t["t"] >= a) & (t["t"] < b)].sort_values("t")
    if x.empty:
        return dict(n=0, R=np.nan)
    eq = x["r"].cumsum().to_numpy()
    return dict(n=len(x), R=x["r"].mean(), tot=x["r"].sum(), win=(x["r"] > 0).mean(),
                dd=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
                buyR=x.loc[x["d"] == 1, "r"].mean(), sellR=x.loc[x["d"] == -1, "r"].mean(),
                none=(x["d"] == 0).mean())


GRID = list(itertools.product((0.1, 0.2), (2, 3, 6), ("C", "K"), ("SAME", "MID"),
                              (("X2", 1.5), ("X2", 2.0), ("X2", 3.0), ("X3", 2.0))))


def cell_name(c):
    B, N, H, S, (X, k) = c
    return f"B{B}-N{N}-{H}-{S}-{X}{'' if X == 'X3' else k}"


def main():
    m = load()
    S_ = Sim(m)
    groups = find_groups(m)
    lim = pd.Timestamp(PERIODS["test"][0])
    groups = [(v, j) for v, j in groups if m["ts"].iat[j] < lim]
    print("groups (V + return) before 2026:", len(groups))
    rows = []
    books = {}
    for c in GRID:
        B, N, H, S, (X, k) = c
        t = run(S_, groups, S_.hedge, (B, N, H, S, X, k))
        books[c] = t
        row = {"cell": cell_name(c)}
        for p in ("train", "validate"):
            for kk, vv in stats(t, p).items():
                row[f"{p[:3]}_{kk}"] = vv
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("cell")
    tab.to_csv("out/g116_cells.csv")
    pd.set_option("display.width", 260)
    cols = ["tra_n", "tra_R", "tra_win", "tra_dd", "tra_buyR", "tra_sellR", "tra_none", "val_n", "val_R", "val_win", "val_dd",
            "val_buyR", "val_sellR"]
    print(tab.sort_values("tra_R", ascending=False)[cols].round(3).head(20).to_string())
    print(f"\ncells positive: train {(tab.tra_R > 0).sum()}/{len(tab)}, validate {(tab.val_R > 0).sum()}, both "
          f"{((tab.tra_R > 0) & (tab.val_R > 0)).sum()}")
    ok = tab[tab["tra_n"] >= 200]
    pick_name = ok["tra_R"].idxmax()
    pick = next(c for c in GRID if cell_name(c) == pick_name)
    print("\npick on train:", pick_name, tab.loc[pick_name, ["tra_R", "val_R", "val_n"]].round(3).to_dict())
    # neighbours: one parameter changed
    def neigh(c):
        out = []
        for c2 in GRID:
            diff = sum(1 for a, b in zip(c[:4], c2[:4]) if a != b) + (c[4] != c2[4])
            if diff == 1:
                out.append(c2)
        return out
    nb = neigh(pick)
    share = float(np.mean([tab.loc[cell_name(c), "val_R"] > 0 for c in nb]))
    print(f"neighbours positive on validate: {share:.0%} of {len(nb)}")
    # OCO equivalent
    B, N, H, S, (X, k) = pick
    to = run(S_, groups, S_.oco, (B, N, H, S, X, k))
    print("OCO equivalent:", {p: {kk: round(vv, 3) for kk, vv in stats(to, p).items() if kk in ("n", "R", "tot")} for p in ("train", "validate")})
    # random control on validate
    pg = [(v, j) for v, j in find_groups(m, pseudo=True) if m["ts"].iat[j] < lim]
    a, b = PERIODS["validate"]
    pg_val = [(v, j) for v, j in pg if a <= str(m["ts"].iat[j]) < b]
    real = stats(books[pick], "validate")
    rng = np.random.default_rng(116)
    sims = []
    for _ in range(100):
        pick_idx = rng.choice(len(pg_val), size=min(real["n"], len(pg_val)), replace=False)
        t = run(S_, [pg_val[i] for i in pick_idx], S_.hedge, (B, N, H, S, X, k))
        sims.append(t["r"].mean())
    sims = np.array(sims)
    print(f"random control (validate): median {np.nanmedian(sims):+.3f}, real {real['R']:+.3f}, p {np.mean(sims >= real['R']):.2f}")
    print(f"criteria: validate R>0 {real['R'] > 0} | p<0.10 {np.mean(sims >= real['R']) < 0.10} | neighbours>=2/3 {share >= 2 / 3}")


def examples():
    m = load()
    S_ = Sim(m)
    g = find_groups(m)
    ts = m["ts"]
    for v, j in g:
        vn = ts.iat[j] + pd.Timedelta(hours=4)
        if pd.Timestamp("2026-10-06 05:00") <= vn < pd.Timestamp("2026-10-07 11:00"):
            res = S_.hedge(v, j, 0.1, 3, "K", "SAME", "X3", 2.0)
            r = res[0] if res else float("nan")
            d = res[1] if res else 0
            print(f"V {ts.iat[v] + pd.Timedelta(hours=4):%d/%m %H:%M} -> entry after {vn:%H:%M} VN: {r:+.2f}U, side {'BUY' if d == 1 else 'SELL' if d == -1 else '-'}")


if __name__ == "__main__":
    examples() if len(sys.argv) > 1 and sys.argv[1] == "examples" else main()
