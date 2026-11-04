"""G166: FX pair hedge (EURGBP / EURJPY / GBPJPY spreads built from EURUSD, GBPUSD, USDJPY legs).

Plan: docs/superpowers/plans/2026-11-05-g166-fx-pair-hedge.md (pre-registered, commit 9f84cc6).
Preliminary run on the QTL ingest H1 series (UTC), not broker MT5 data.
Usage: g166_fx_pair_hedge.py <dir with EURUSD_1h.csv GBPUSD_1h.csv USDJPY_1h.csv [XAUUSD_1h.csv]> <out.json>
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SYMS = ["EURUSD", "GBPUSD", "USDJPY"]
PIP = {"EURUSD": 1e-4, "GBPUSD": 1e-4, "USDJPY": 1e-2}
SPREAD = {"EURUSD": 1.0, "GBPUSD": 1.5, "USDJPY": 1.2}
SLIP, COMM, SWAP = 0.2, 6e-5, 0.5               # pip per side, fraction round trip per leg, pip per night per leg
CROSSES = {"X1": ("EURUSD", "GBPUSD", -1), "X2": ("EURUSD", "USDJPY", 1), "X3": ("GBPUSD", "USDJPY", 1)}
SAMPLE_HOURS = {"H4": {3, 7, 11, 15, 19, 23}, "D1": {23}}
PERIODS = [("sel", "2010-01-01", "2018-01-01"), ("t1", "2018-01-01", "2022-01-01"),
           ("t2", "2022-01-01", "2025-11-01"), ("look", "2026-06-26", "2026-12-31")]
GAP_H = 120
RUNS = 200
rng = np.random.default_rng(166)


def load(root):
    fr = {}
    for s in SYMS:
        d = pd.read_csv(root / f"{s}_1h.csv", index_col=0, parse_dates=True)
        fr[s] = d[["open", "close"]].rename(columns=lambda c: f"{s}_{c}")
    df = pd.concat(fr.values(), axis=1, join="inner").sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC")
    return df


def period_of(t):
    for name, a, b in PERIODS:
        if pd.Timestamp(a, tz="UTC") <= t < pd.Timestamp(b, tz="UTC"):
            return name
    return None


class Market:
    def __init__(self, df):
        self.t = df.index
        self.ts = df.index.as_unit("s").asi8      # pandas 3 defaults to microseconds
        self.o = {s: df[f"{s}_open"].to_numpy() for s in SYMS}
        self.c = {s: df[f"{s}_close"].to_numpy() for s in SYMS}
        gap = np.r_[0, np.diff(self.ts)] > GAP_H * 3600
        self.gapcum = np.cumsum(gap)
        # rollovers at 21:00 UTC: count of 21:00 boundaries crossed, Wednesday x3
        self.hours = df.index.hour.to_numpy()
        self.dow = df.index.dayofweek.to_numpy()

    def nights(self, i, j):
        t0, t1 = self.ts[i], self.ts[j]
        d0, d1 = (t0 - 21 * 3600) // 86400, (t1 - 21 * 3600) // 86400
        n = 0
        for d in range(int(d0) + 1, int(d1) + 1):
            wd = (d + 3) % 7                      # 1970-01-01 is Thursday -> Monday = 0
            if wd < 5:
                n += 3 if wd == 2 else 1
        return n


def leg_cost(sym, price, nights, cm, sm):
    pip = PIP[sym] / price
    return cm * ((SPREAD[sym] + 2 * SLIP) * pip + COMM) + sm * SWAP * pip * nights


class Cross:
    def __init__(self, mk, code, tf, beta_mode, N):
        self.mk, self.code = mk, code
        a, b, sg = CROSSES[code]
        self.a, self.b, self.sg = a, b, sg
        idx = np.nonzero(np.isin(mk.hours, list(SAMPLE_HOURS[tf])))[0]
        idx = idx[idx < len(mk.ts) - 1]
        self.idx = idx
        la = np.log(mk.c[a][idx])
        x = -sg * np.log(mk.c[b][idx])                     # s = la - beta * x
        self.la, self.x = la, x
        n = len(idx)
        beta = np.full(n, np.nan)
        if beta_mode == "M1":
            beta[:] = 1.0
        else:
            sa = pd.Series(la).rolling(N); sx = pd.Series(x).rolling(N)
            cov = pd.Series(la).rolling(N).cov(pd.Series(x))
            beta = (cov / sx.var()).to_numpy()
        s = la - beta * x
        ss = pd.Series(s)
        if beta_mode == "M1":
            m = ss.rolling(N).mean().to_numpy(); sd = ss.rolling(N).std().to_numpy()
        else:
            # residual of the window regression, evaluated at the current bar
            m = np.full(n, np.nan); sd = np.full(n, np.nan)
            for k in range(N - 1, n):
                w = la[k - N + 1:k + 1] - beta[k] * x[k - N + 1:k + 1]
                m[k] = w.mean(); sd[k] = w.std(ddof=1)
        self.beta, self.s, self.z, self.sd = beta, s, (s - m) / sd, sd

    def basket(self, k0, d, k_entry, exit_mode, N, cm=1.0, sm=1.0):
        """Open at sample k0 (signal), direction d (+1 buy spread), return dict or None."""
        mk = self.mk
        i_in = self.idx[k0] + 1
        beta, sig = self.beta[k0], self.sd[k0]
        if not np.isfinite(beta) or not np.isfinite(sig) or sig <= 0:
            return None
        stop_z = k_entry + 1.5
        k_end = min(len(self.idx) - 1, k0 + 3 * N)
        k_exit, why = k_end, "time"
        g0 = mk.gapcum[i_in]
        i_out = None
        for k in range(k0 + 1, k_end + 1):
            j = self.idx[k]
            if mk.gapcum[j] != g0:                           # data gap inside the basket
                j_gap = np.searchsorted(mk.gapcum, g0 + 1)
                i_out, why = j_gap, "gap"
                break
            z = self.z[k]
            if not np.isfinite(z):
                continue
            if -d * z >= stop_z:
                k_exit, why = k, "sl"; break
            if (exit_mode == "X0" and d * z >= 0) or (exit_mode == "X5" and abs(z) <= 0.5):
                k_exit, why = k, "mean"; break
        if i_out is None:
            i_out = self.idx[k_exit] + 1
        if i_out >= len(mk.ts):
            return None
        a, b = self.a, self.b
        ra = np.log(mk.o[a][i_out] / mk.o[a][i_in])
        rx = -self.sg * np.log(mk.o[b][i_out] / mk.o[b][i_in])
        gross = d * (ra - beta * rx)
        nights = mk.nights(i_in, i_out)
        cost = leg_cost(a, mk.o[a][i_in], nights, cm, sm) + abs(beta) * leg_cost(b, mk.o[b][i_in], nights, cm, sm)
        return {"t": mk.t[i_in], "d": d, "r": (gross - cost) / (1.5 * sig), "r_mom": (-gross - cost) / (1.5 * sig),
                "gross": gross, "why": why,
                "i_in": int(i_in), "i_out": int(i_out), "cost_r": cost / (1.5 * sig)}

    def run(self, k_entry, exit_mode, N, cm=1.0, sm=1.0):
        out, k = [], N
        n = len(self.idx)
        while k < n - 1:
            z = self.z[k]
            d = 0
            if np.isfinite(z):
                if z >= k_entry: d = -1
                elif z <= -k_entry: d = 1
            if d:
                b = self.basket(k, d, k_entry, exit_mode, N, cm, sm)
                if b:
                    out.append(b)
                    k = int(np.searchsorted(self.idx, b["i_out"] - 1)) + 1
                    continue
            k += 1
        return out


def stats(rs):
    rs = list(rs)
    if not rs:
        return {"n": 0, "R": 0.0, "PF": None, "DD": 0.0, "MAR": None}
    a = np.array(rs)
    eq = np.cumsum(a); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(a) else 0.0
    pos, neg = a[a > 0].sum(), -a[a < 0].sum()
    return {"n": len(a), "R": round(float(a.sum()), 2), "avg": round(float(a.mean()), 3),
            "PF": round(float(pos / neg), 2) if neg > 0 else None, "DD": round(dd, 2),
            "MAR": round(float(a.sum() / dd), 2) if dd > 0 else None, "win": round(float((a > 0).mean()), 3)}


def by_period(bs, key="r"):
    out = {}
    for name, _, _ in PERIODS:
        out[name] = stats(b[key] for b in bs if period_of(b["t"]) == name)
    return out


def half_life(s):
    s = s[np.isfinite(s)]
    ds, lag = np.diff(s), s[:-1]
    b = np.polyfit(lag, ds, 1)[0]
    return float(-np.log(2) / np.log(1 + b)) if -1 < b < 0 else None


def random_control(cx, bs, k_entry, exit_mode, N):
    """Total R over t1+t2 for random entries with the same count and directions per period."""
    totals = np.zeros(RUNS)
    for per in ("t1", "t2"):
        act = [b for b in bs if period_of(b["t"]) == per]
        if not act:
            continue
        a, b_ = [p for p in PERIODS if p[0] == per][0][1:]
        times = cx.mk.t[cx.idx]
        ks = np.nonzero((times >= pd.Timestamp(a, tz="UTC")) & (times < pd.Timestamp(b_, tz="UTC"))
                        & np.isfinite(cx.z) & np.isfinite(cx.sd))[0]
        ks = ks[ks < len(cx.idx) - 1]
        dirs = [x["d"] for x in act]
        for r in range(RUNS):
            tot = 0.0
            for d in dirs:
                for _ in range(20):
                    x = cx.basket(int(rng.choice(ks)), d, k_entry, exit_mode, N)
                    if x:
                        tot += x["r"]; break
            totals[r] += tot
    return totals


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    df = load(root)
    mk = Market(df)
    xau = None
    if (root / "XAUUSD_1h.csv").exists():
        xau = pd.read_csv(root / "XAUUSD_1h.csv", index_col=0, parse_dates=True)["close"]
        xau.index = pd.DatetimeIndex(xau.index).tz_localize("UTC")
    res = {"data": {"bars": len(df), "first": str(df.index[0]), "last": str(df.index[-1]),
                    "gaps_over_120h": int(mk.gapcum[-1])}, "configs": {}, "chosen": {}}
    cache = {}
    grid = list(itertools.product(CROSSES, ["H4", "D1"], ["M1", "M2"], [20, 60], [2.0, 2.5], ["X0", "X5"]))
    for code, tf, bm, N, ke, ex in grid:
        key = (code, tf, bm, N)
        if key not in cache:
            cache[key] = Cross(mk, code, tf, bm, N)
        bs = cache[key].run(ke, ex, N)
        name = f"{code}_{tf}_{bm}_N{N}_k{ke}_{ex}"
        res["configs"][name] = {"periods": by_period(bs),
                                "exits": {w: sum(1 for b in bs if b["why"] == w) for w in ("mean", "sl", "time", "gap")}}
        print(name, res["configs"][name]["periods"]["sel"], flush=True)
    for code in CROSSES:
        hl = {tf: half_life(Cross(mk, code, tf, "M1", 20).s[: np.searchsorted(mk.t[Cross(mk, code, tf, "M1", 20).idx],
                                                                               pd.Timestamp("2018-01-01", tz="UTC"))])
              for tf in ("H4", "D1")}
        cands = [(n, c) for n, c in res["configs"].items() if n.startswith(code + "_") and c["periods"]["sel"]["n"] >= 30
                 and (c["periods"]["sel"]["MAR"] or -1e9) > 0]
        entry = {"half_life_sel_bars": hl}
        if not cands:
            entry["verdict"] = "KHÔNG ĐẠT (không cấu hình nào MAR > 0 ở kỳ chọn với >= 30 rổ)"
            best = max(((n, c) for n, c in res["configs"].items() if n.startswith(code + "_")),
                       key=lambda nc: nc[1]["periods"]["sel"]["R"])
            entry["best_sel_by_R"] = {"name": best[0], **best[1]}
            res["chosen"][code] = entry
            continue
        name, c = max(cands, key=lambda nc: nc[1]["periods"]["sel"]["MAR"])
        _, tf, bm, Ns, ks, ex = name.split("_")
        N, ke = int(Ns[1:]), float(ks[1:])
        cx = cache[(code, tf, bm, N)]
        bs = cx.run(ke, ex, N)
        test = [b for b in bs if period_of(b["t"]) in ("t1", "t2")]
        act_total = sum(b["r"] for b in test)
        rand = random_control(cx, bs, ke, ex, N)
        p = float((np.sum(rand >= act_total) + 1) / (RUNS + 1))
        pess = cx.run(ke, ex, N, cm=1.5, sm=2.0)
        pess_total = sum(b["r"] for b in pess if period_of(b["t"]) in ("t1", "t2"))
        buy = sum(b["r"] for b in test if b["d"] == 1); sell = sum(b["r"] for b in test if b["d"] == -1)
        neigh = []
        for alt in ({"k": 2.5 if ke == 2.0 else 2.0}, {"N": 60 if N == 20 else 20}, {"ex": "X5" if ex == "X0" else "X0"}):
            nk, nN, nex = alt.get("k", ke), alt.get("N", N), alt.get("ex", ex)
            nn = f"{code}_{tf}_{bm}_N{nN}_k{nk}_{nex}"
            pr = res["configs"][nn]["periods"]
            neigh.append({"name": nn, "R_t1_t2": round(pr["t1"]["R"] + pr["t2"]["R"], 2)})
        corr = None
        if xau is not None and test:
            xr, br = [], []
            for b in test:
                t0, t1 = mk.t[b["i_in"]], mk.t[min(b["i_out"], len(mk.t) - 1)]
                a0 = xau.asof(t0); a1 = xau.asof(t1)
                if np.isfinite(a0) and np.isfinite(a1):
                    xr.append(np.log(a1 / a0)); br.append(b["gross"])
            if len(xr) > 5:
                corr = round(float(np.corrcoef(xr, br)[0, 1]), 3)
        P = c["periods"]
        crit = {k_: bool(v_) for k_, v_ in {
            "1_t1_t2_R_PF_n": all(P[p]["R"] > 0 and (P[p]["PF"] or 0) >= 1.2 and P[p]["n"] >= 20 for p in ("t1", "t2")),
            "2_random_p": p <= 0.0167,
            "3_buy_sell": buy >= 0 and sell >= 0,
            "4_pessimistic_costs": pess_total > 0,
            "5_dd": max(P["t1"]["DD"], P["t2"]["DD"]) <= 1.5 * max(P["sel"]["DD"], 1e-9),
            "6_neighbours": sum(n_["R_t1_t2"] > 0 for n_ in neigh) >= 2,
        }.items()
        }
        entry.update({"name": name, "periods": P, "exits": c["exits"], "random_p": round(p, 4),
                      "random_p50": round(float(np.median(rand)), 2), "random_p95": round(float(np.percentile(rand, 95)), 2),
                      "actual_t1_t2": round(act_total, 2), "buy_R": round(buy, 2), "sell_R": round(sell, 2),
                      "pessimistic_t1_t2": round(pess_total, 2), "momentum_same_holding_periods": by_period(bs, "r_mom"),
                      "neighbours": neigh, "corr_xau": corr,
                      "avg_cost_r": round(float(np.mean([b["cost_r"] for b in bs])), 3),
                      "criteria": crit, "passed": int(sum(crit.values())),
                      "verdict": "ĐẠT" if all(crit.values()) else "KHÔNG ĐẠT"})
        res["chosen"][code] = entry
        print(code, json.dumps(entry, ensure_ascii=False, default=str)[:1500], flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
