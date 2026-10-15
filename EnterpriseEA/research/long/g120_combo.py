"""G120 combos rebuilt: S07 + VHedge (G119 / BIGV) on one 10k account, closed-trade curves, with the S07 legs moved
from UTC to server time (the earlier ad-hoc comparison mixed UTC S07 exits with server-time VHedge exits).

  python g120_combo.py

S07: G89/G107 port legs (1.5% x weight of 10,000, harsh costs). VHedge: G120 E0 (TP 5R, BE +1R), profiles G119 (stop
1.5 ATR) and BIGV (1.0 ATR), one unit U = the two stops' gap = 2 leg risks; money per U = 2 x leg risk.
Window: VHedge groups from 05/2024 to 10/2026; S07 legs entered in the same window. Drawdown = (peak - equity) / peak
on the closed-trade balance, risk on the initial 10,000 (INITIAL).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g116_v_hedge as g
import g118_v_combos as g118
import g119_v_m5_native as q
import g120_vhedge_v2 as v2
import g107_portfolio as p107

CAPITAL = 10_000.0


class SimExit(v2.SimV2):
    """E0 management of G120 that also records the bar where the last leg closed."""

    def manage(self, t, d, legs, surv_entry, surv_sl, mode, k):
        o, h, l, c, sp = self.o, self.H0, self.L0, self.c, self.sp
        R = d * (surv_entry - surv_sl)
        if R <= 0:
            return None
        tp = surv_entry + d * k * R
        pnl, open_, best, be = 0.0, [True] * len(legs), surv_entry, False
        end = min(len(c) - 1, t + g.CAP)
        j = t + 1
        while j <= end:
            for i, L in enumerate(legs):
                if open_[i] and ((d == 1 and l[j] <= L[1]) or (d == -1 and h[j] + sp[j] >= L[1])):
                    pnl += d * (L[1] - L[0]); open_[i] = False
            if not any(open_):
                self.last_j = j
                return pnl
            if (d == 1 and h[j] >= tp) or (d == -1 and l[j] + sp[j] <= tp):
                pnl += sum(d * (tp - L[0]) for i, L in enumerate(legs) if open_[i])
                self.last_j = j
                return pnl
            best = max(best, h[j]) if d == 1 else min(best, l[j])
            if not be and d * (best - surv_entry) / R >= 1:
                be = True
                for L in legs:
                    if d * (L[0] - L[1]) > 0:
                        L[1] = L[0]
            j += 1
        jj = min(j, end)
        px = c[jj] + (sp[jj] if d == -1 else 0.0)
        pnl += sum(d * (px - L[0]) for i, L in enumerate(legs) if open_[i])
        self.last_j = jj
        return pnl

    def group(self, v, j, mult):
        mid = self.o[j + 1]
        self.h[v], self.l[v] = mid + mult * self.atr[j], mid - mult * self.atr[j]
        self.last_j = None
        res = self.hedge(v, j, 0.1, 3, "K", "SAME", "E0", 5.0)
        self._reset(v)
        if res is None:
            return None
        r, d, t = res
        x = self.last_j if self.last_j is not None else t
        return r, int(self.m["time"].iat[x]) + 300


def vhedge():
    m = g118.load("M5")
    gr = g.find_groups(m)
    F = q.raw_features(m, gr)
    BF = q.binarize(F, F[F.t < "2025-01-01"])
    PF = v2.profiles(BF, v2.m30_context(m, F))
    S = SimExit(m)
    out = {}
    for prof, mult in (("G119", 1.5), ("BIGV", 1.0)):
        rows = []
        for k in np.flatnonzero(PF[prof]):
            v, j = gr[k]
            res = S.group(v, j, mult)
            if res is not None:
                rows.append(dict(t_in=int(m["time"].iat[j + 1]), t_out=res[1], U=res[0]))
        out[prof] = pd.DataFrame(rows)
    return out


def curve(events):
    e = events.sort_values("t_out")
    eq = CAPITAL + np.cumsum(e["usd"].to_numpy())
    peak = np.maximum.accumulate(np.r_[CAPITAL, eq])[1:]
    return eq[-1] - CAPITAL, float(((peak - eq) / peak).max())


def main():
    V = vhedge()
    a = min(x.t_in.min() for x in V.values())
    L = pd.DataFrame(p107.s07_legs())
    utc_in = (L.t_in - pd.Timestamp(0)).dt.total_seconds().astype(int)
    utc_out = (L.t_out - pd.Timestamp(0)).dt.total_seconds().astype(int)
    srv = p107.s07_to_server(p107.s07_legs())
    srv_in = np.array([int((x["t_in"] - pd.Timestamp(0)).total_seconds()) for x in srv])
    srv_out = np.array([int((x["t_out"] - pd.Timestamp(0)).total_seconds()) for x in srv])
    keep = srv_in >= a
    s07 = {"UTC (before)": pd.DataFrame({"t_out": utc_out[keep], "r": L.r[keep], "money": L.money[keep]}),
           "server (fixed)": pd.DataFrame({"t_out": srv_out[keep], "r": L.r[keep], "money": L.money[keep]})}
    print(f"window from {pd.to_datetime(a, unit='s')}: S07 legs {keep.sum()}, G119 groups {len(V['G119'])}, "
          f"BIGV groups {len(V['BIGV'])}")
    rows = []
    for leg_pct in (0.75, 1.5):
        for clock, s in s07.items():
            ev = {"S07": s.assign(usd=s.r * s.money)[["t_out", "usd"]]}
            for prof, x in V.items():
                ev[prof] = x.assign(usd=x.U * CAPITAL * 2 * leg_pct / 100)[["t_out", "usd"]]
            combos = {"S07": ["S07"], "G119": ["G119"], "BIGV": ["BIGV"], "G119+BIGV": ["G119", "BIGV"],
                      "S07+G119": ["S07", "G119"], "S07+G119+BIGV": ["S07", "G119", "BIGV"]}
            for name, parts in combos.items():
                tot, dd = curve(pd.concat([ev[k] for k in parts]))
                rows.append(dict(leg_pct=leg_pct, s07_clock=clock, combo=name, profit=round(tot), dd_pct=round(100 * dd, 1),
                                 ratio=round(tot / CAPITAL / dd, 1) if dd > 0 else np.nan))
    T = pd.DataFrame(rows)
    T.to_csv(p107.HERE / "out" / "g120_combo.csv", index=False)
    pd.set_option("display.width", 200)
    print(T.pivot_table(index=["leg_pct", "combo"], columns="s07_clock", values=["profit", "dd_pct", "ratio"]).to_string())


if __name__ == "__main__":
    main()
