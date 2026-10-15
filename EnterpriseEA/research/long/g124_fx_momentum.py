"""G124 R2: FX slow momentum basket with volatility weights (plan docs/superpowers/plans/2026-10-15-g124-r2-fx-momentum-basket.md).

  python g124_fx_momentum.py      -> train / validate for 8 variants, Markov random-sign control, then the test
                                     2023..10/2026 once for the selected variant (user agreed G124)

U6 = the six real majors (data/fx124 D1); U21 adds 15 crosses built from closes of the seven currencies.
Signal = sign of the L-day return (L60 / L120 / L250) or VOTE = mean of the three signs; weight = signal / 60-day stdev
of daily returns; rebalanced at the close of each week's last trading day; basket = mean over pairs, scaled by one
constant so the train after-cost volatility is 10%/yr. Costs: D1 bar spread + commission per leg on traded size;
+1 pip per leg stress column; swap at today's rates (3x on Wednesday) reported apart.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

HERE = __import__("pathlib").Path(__file__).resolve().parent
DATA = HERE / "data" / "fx124"
MAJORS = {"EURUSD": "EUR", "GBPUSD": "GBP", "AUDUSD": "AUD", "NZDUSD": "NZD", "USDCAD": "CAD", "USDJPY": "JPY"}
ORDER = ("EUR", "GBP", "AUD", "NZD", "CAD", "JPY")
COMM = {"EURUSD": 0.00006, "GBPUSD": 0.00006, "AUDUSD": 0.00006, "NZDUSD": 0.00006, "USDCAD": 0.000083, "USDJPY": 0.009}
PER = {"train": ("2010-01-01", "2019-01-01"), "validate": ("2019-01-01", "2023-01-01"), "test": ("2023-01-01", "2026-12-31")}
SIGNALS = ("L60", "L120", "L250", "VOTE")
UNIVERSES = ("U6", "U21")
REPS, TARGET_VOL = 200, 0.10
SEEN_END = "2025-10-10"                         # FX02 looked at EUR / GBP / JPY pairs up to here


def load():
    meta = json.load(open(DATA / "meta.json"))
    C, S = {}, {}
    for m in MAJORS:
        d = pd.read_csv(DATA / f"{m}_D1.csv")
        d["date"] = pd.to_datetime(d["time"], unit="s")
        d = d.set_index("date")
        C[m], S[m] = d["close"], d["spread"] * meta[m]["point"]
    C, S = pd.DataFrame(C).dropna(), pd.DataFrame(S)
    S = S.reindex(C.index).ffill()
    C = C[C.index >= "2009-01-01"]
    S = S.reindex(C.index)
    # per currency (vs USD): value, relative round-trip cost of one leg, +1 pip stress, swap per night
    val, cost, pip, sw_long, sw_short = {}, {}, {}, {}, {}
    for m, cur in MAJORS.items():
        px = C[m]
        rel = (S[m] + COMM[m]) / px
        p1 = (0.01 if m.endswith("JPY") else 0.0001) / px
        lo = meta[m]["swap_long"] * meta[m]["point"] / px
        sh = meta[m]["swap_short"] * meta[m]["point"] / px
        if m.startswith("USD"):                                 # currency = quote: long currency = short the major
            val[cur], sw_long[cur], sw_short[cur] = 1 / px, sh, lo
        else:
            val[cur], sw_long[cur], sw_short[cur] = px, lo, sh
        cost[cur], pip[cur] = rel, p1
    pairs = {}
    for m, cur in MAJORS.items():
        pairs[m] = dict(px=C[m], cost=cost[cur], pip=pip[cur], swl=sw_long[cur] if not m.startswith("USD") else sw_short[cur],
                        sws=sw_short[cur] if not m.startswith("USD") else sw_long[cur], cur=(cur,))
    for a, b in itertools.combinations(ORDER, 2):
        pairs[a + b] = dict(px=val[a] / val[b], cost=cost[a] + cost[b], pip=pip[a] + pip[b],
                            swl=sw_long[a] + sw_short[b], sws=sw_short[a] + sw_long[b], cur=(a, b))
    return C.index, pairs


def nights(index):
    prev = pd.Series(index, index=index).shift(1)
    return np.where(prev.dt.weekday.to_numpy() == 2, 3.0, 1.0)            # rollover after Wednesday counts 3


class Basket:
    def __init__(self, idx, pairs, names):
        self.idx, self.names = idx, list(names)
        self.P = pd.DataFrame({n: pairs[n]["px"] for n in names})
        self.r = self.P.pct_change().fillna(0.0).to_numpy()
        self.sig = self.P.pct_change().rolling(60).std().to_numpy()
        self.cost = pd.DataFrame({n: pairs[n]["cost"] for n in names}).to_numpy()
        self.pip = pd.DataFrame({n: pairs[n]["pip"] for n in names}).to_numpy()
        self.swl = pd.DataFrame({n: pairs[n]["swl"] for n in names}).to_numpy()
        self.sws = pd.DataFrame({n: pairs[n]["sws"] for n in names}).to_numpy()
        self.nights = nights(idx)
        wk = idx.to_series().dt.isocalendar()
        key = (wk["year"].astype(str) + "-" + wk["week"].astype(str)).to_numpy()
        self.rebal = np.r_[key[1:] != key[:-1], True]                       # last trading day of each week

    def signal(self, kind):
        P = self.P
        if kind == "VOTE":
            return np.mean([np.sign(P / P.shift(L) - 1).to_numpy() for L in (60, 120, 250)], axis=0)
        L = int(kind[1:])
        return np.sign(P / P.shift(L) - 1).to_numpy()

    def weights(self, s):
        target = np.nan_to_num(s / self.sig)
        w = np.zeros_like(target)
        cur = np.zeros(target.shape[1])
        for t in range(len(w)):
            if self.rebal[t]:
                cur = target[t]
            w[t] = cur
        return w

    def returns(self, w):
        """Daily basket returns (unscaled): gross, cost, stress (+1 pip), swap; weights at close t earn t+1."""
        wp = np.vstack([np.zeros(w.shape[1]), w[:-1]])                      # position held during day t
        gross = (wp * self.r).mean(1)
        dw = np.abs(np.diff(np.vstack([np.zeros(w.shape[1]), w]), axis=0))
        cost = (dw * np.nan_to_num(self.cost) / 2).mean(1)
        stress = (dw * np.nan_to_num(self.pip) / 2).mean(1)
        swap = (np.where(wp > 0, wp * np.nan_to_num(self.swl), -wp * np.nan_to_num(self.sws)) * self.nights[:, None]).mean(1)
        contrib = wp * self.r
        return gross, cost, stress, swap, contrib


def mask(idx, p):
    a, b = PER[p]
    return np.asarray((idx >= a) & (idx < b))


def sharpe(x):
    return float(np.mean(x) / np.std(x) * np.sqrt(252)) if np.std(x) > 0 else np.nan


def block_lower(x, idx, q=0.10, runs=2000, seed=124):
    months = pd.Series(x, index=idx).groupby(idx.to_period("M"))
    blocks = [g.to_numpy() for _, g in months]
    rng = np.random.default_rng(seed)
    out = [sharpe(np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])) for _ in range(runs)]
    return float(np.quantile(out, q))


def markov_signs(real, rebal, rng):
    """Random +-1 series per pair, flips only on rebalance days with the real flip frequency."""
    n, k = real.shape
    out = np.zeros_like(real)
    rd = np.flatnonzero(rebal)
    for j in range(k):
        s = np.sign(real[rd, j])
        s = s[s != 0]
        flips = np.mean(s[1:] != s[:-1]) if len(s) > 1 else 0.5
        cur = rng.choice((-1.0, 1.0))
        series = np.empty(len(rd))
        for t in range(len(rd)):
            if rng.random() < flips:
                cur = -cur
            series[t] = cur
        out[rd, j] = series
        # fill forward between rebalance days
        last = 0.0
        for t in range(n):
            if rebal[t]:
                last = out[t, j]
            out[t, j] = last
    return out


def neg_run(v):
    best = cur = 0
    for x in v:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def main(open_test=True):
    idx, pairs = load()
    unis = {"U6": list(MAJORS), "U21": list(pairs)}
    print("dates", idx[0].date(), "..", idx[-1].date(), "pairs", len(pairs), flush=True)
    rng = np.random.default_rng(1242)
    tr, va = mask(idx, "train"), mask(idx, "validate")
    rows, keep = [], {}
    for U, kind in itertools.product(UNIVERSES, SIGNALS):
        B = Basket(idx, pairs, unis[U])
        s = B.signal(kind)
        w = B.weights(s)
        g_, c_, st_, sw_, con = B.returns(w)
        net = g_ - c_
        k = TARGET_VOL / (np.std(net[tr]) * np.sqrt(252))
        net, stress, swap = net * k, (net - st_) * k, (net + sw_ * k)
        keep[(U, kind)] = (B, s, w, k, net, stress, swap, con * k)
        row = dict(universe=U, signal=kind, scale=k)
        for p, m in (("tra", tr), ("val", va)):
            row[f"{p}_sharpe"] = sharpe(net[m])
            row[f"{p}_pct_yr"] = 100 * net[m].mean() * 252
            row[f"{p}_stress_sh"] = sharpe(stress[m])
            row[f"{p}_swap_sh"] = sharpe(swap[m])
            row[f"{p}_cost_pct_yr"] = 100 * (c_[m] * k).mean() * 252
        tv = tr | va
        row["tv_low90"] = block_lower(net[tv], idx[tv])
        yr = pd.Series(net[tv], index=idx[tv]).groupby(idx[tv].year).sum()
        row["neg_run"] = neg_run(yr.to_numpy())
        row["worst_yr_pct"] = 100 * yr.min()
        pc = pd.Series(con[tv].sum(0) * k, index=unis[U])
        row["top_pair_share"] = float(pc.max() / pc[pc > 0].sum()) if (pc > 0).any() else np.nan
        eq = np.cumsum(net[tv])
        row["dd_pct"] = 100 * float((np.maximum.accumulate(eq) - eq).max())
        # Markov random-sign control on validate
        ctl = []
        for _ in range(REPS):
            ws = B.weights(markov_signs(s, B.rebal, rng))
            g2, c2, *_ = B.returns(ws)
            ctl.append(sharpe(((g2 - c2) * k)[va]))
        ctl = np.array(ctl)
        row["val_ctl_sh"], row["val_p"] = float(np.nanmedian(ctl)), float(np.nanmean(ctl >= row["val_sharpe"]))
        row["by_year"] = " ".join(f"{y}:{100 * v:+.0f}" for y, v in yr.items())
        c1 = row["tra_sharpe"] > 0 and row["val_sharpe"] > 0 and row["tv_low90"] > 0
        c2 = row["val_p"] < 0.10
        c3 = row["neg_run"] <= 2 and row["top_pair_share"] <= 0.5
        c4 = row["tra_stress_sh"] > 0 and row["val_stress_sh"] > 0
        row.update(c1=c1, c2=c2, c3=c3, c4=c4, passed=c1 and c2 and c3 and c4)
        rows.append(row)
        print(U, kind, f"sharpe tra {row['tra_sharpe']:+.2f} val {row['val_sharpe']:+.2f} p {row['val_p']:.2f}", flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / "out" / "g124_r2.csv", index=False)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_colwidth", 120)
    print(T.drop(columns=["by_year"]).round(3).to_string(index=False))
    for r in rows:
        print(r["universe"], r["signal"], "by year %:", r["by_year"])
    ok = T[T.passed]
    if ok.empty or not open_test:
        print("\nNo variant passes -> test 2023..10/2026 stays sealed.")
        return
    best = ok.assign(m=np.minimum(ok.tra_sharpe, ok.val_sharpe)).sort_values("m").iloc[-1]
    U, kind = best.universe, best.signal
    B, s, w, k, net, stress, swap, con = keep[(U, kind)]
    te = mask(idx, "test")
    print(f"\nSelected {U} {kind}. Opening the test 2023..10/2026 once.")
    for name, m in (("test", te), ("test seen part ..2025-10-09", te & np.asarray(idx < SEEN_END)),
                    ("test unseen part 2025-10-10..", te & np.asarray(idx >= SEEN_END))):
        eq = np.cumsum(net[m])
        print(f"  {name}: days {m.sum()}  sharpe {sharpe(net[m]):+.2f}  %/yr {100 * net[m].mean() * 252:+.1f}  "
              f"DD {100 * (np.maximum.accumulate(eq) - eq).max():.1f}%  +1pip sharpe {sharpe(stress[m]):+.2f}  "
              f"with swap {sharpe(swap[m]):+.2f}")
    ctl = []
    for _ in range(REPS):
        ws = B.weights(markov_signs(s, B.rebal, rng))
        g2, c2, *_ = B.returns(ws)
        ctl.append(sharpe(((g2 - c2) * k)[te]))
    print(f"  random control sharpe {np.nanmedian(ctl):+.2f}  p {np.nanmean(np.array(ctl) >= sharpe(net[te])):.3f}")
    print("  test by year %:", " ".join(f"{y}:{100 * v:+.1f}" for y, v in pd.Series(net[te], index=idx[te]).groupby(idx[te].year).sum().items()))
    pc = pd.Series(con[te].sum(0), index=B.names) * 100
    print("  test by pair %:", " ".join(f"{n}:{v:+.1f}" for n, v in pc.sort_values().items()))
    clean = [n for n in B.names if not any(c in n for c in ("EUR", "GBP", "JPY"))]
    print(f"  AUD/NZD/CAD/USD-only pairs ({', '.join(clean)}): {pc[clean].sum():+.1f}% over the test")
    pd.DataFrame({"date": idx, "net": net, "stress": stress, "swap": swap}).to_csv(HERE / "out" / "g124_r2_daily.csv", index=False)


if __name__ == "__main__":
    main()
