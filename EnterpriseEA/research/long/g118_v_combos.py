"""G118: the G116 V-candle return setup on M5 / M15 / M30, condition combinations, per-year consistency.

User (14/10/2026): keep the G117 candidate, try many more cases, combine conditions, keep what works in every year
and report the probability of a high-RR outcome. 2026 is included (no sealed period left; forward data confirms).

  python g118_v_combos.py

Per timeframe (M5 from 05/2024, M15 from 07/2021, M30 from 2018) and stop (V range | +-2 ATR | +-3 ATR):
groups = V body cross of the EMA200 + close back inside the V range within 6 bars; G116 hedge management
(N 3, keep, add at the break, X3 with X2 k2 fallback, BE at +1R). Group result in U (gap between the two stops).
Conditions at the V bar (closed data): see COND. Combos of 1-3 conditions.
Pass: >= 60 groups, every calendar year with >= 8 groups has mean R > 0, beats random candles near EMA200 through
the same combo (pooled). Chance level: the same search on outcomes shuffled within each year (20 runs).
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

import g116_v_hedge as g
from g97_forming_bar import dmi, ema

HERE = Path(__file__).resolve().parent
TFS = {"M5": "m5v", "M15": "m15v", "M30": "m30v"}
START = {"M5": "2024-05-14", "M15": "2021-07-20", "M30": "2018-03-01"}
STOPS = ("V", "A2", "A3")


def load(tf):
    m = pd.read_csv(HERE / "data" / TFS[tf] / "XAUUSD.csv")
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    m = m[m["ts"] >= START[tf]].reset_index(drop=True)
    c = m["close"].to_numpy()
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * 0.01
    return m


def features(m, groups):
    o, c, h, l, e200 = (m[k].to_numpy() for k in ("open", "close", "high", "low", "e200"))
    e21, e55, e100, a, adx = (m[k].to_numpy() for k in ("e21", "e55", "e100", "atr", "adx"))
    hk = m["ts"].dt.floor("h")
    H = m.groupby(hk).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    _, _, hadx, _ = dmi(H["h"].to_numpy(), H["l"].to_numpy(), H["c"].to_numpy())
    he = ema(H["c"].to_numpy(), 200)
    hpos = hk.map(pd.Series(np.arange(len(H)), index=H.index)).to_numpy() - 1
    dk = m["ts"].dt.normalize()
    D = m.groupby(dk)["close"].last()
    de = ema(D.to_numpy(), 50)
    dside = pd.Series(np.roll(np.sign(D.to_numpy() - de), 1), index=D.index)
    body = ((o < e200) & (c > e200)) | ((o > e200) & (c < e200))
    cs = np.cumsum(body)
    rows = []
    for v, j in groups:
        k = max(hpos[v], 0)
        fan = 1 if e21[v] > e55[v] > e100[v] else (-1 if e21[v] < e55[v] < e100[v] else 0)
        vd = 1 if c[v] > e200[v] else -1
        lb = min(48, v - 1)
        slope = (e200[v] - e200[v - lb]) / a[v]
        hour = int((m["ts"].iat[v] + pd.Timedelta(hours=4)).hour)
        rows.append(dict(
            v=v, j=j, t=m["ts"].iat[j], year=m["ts"].iat[j].year, vdir=vd,
            fan_v=fan == vd, fan_against=(fan != 0) & (fan != vd), fan_none=fan == 0,
            adxH1_25=hadx[k] >= 25, adxH1_lt20=hadx[k] < 20,
            adx_lt25=adx[v] < 25, adx_ge25=adx[v] >= 25, adx_up=adx[v] > adx[v - 1],
            slope_with=np.sign(slope) == vd, slope_against=np.sign(slope) == -vd, slope_flat=abs(slope) < 0.5,
            clean=(cs[v - 1] - cs[max(v - 49, 0)]) == 0, choppy=(cs[v - 1] - cs[max(v - 49, 0)]) >= 2,
            big_body=abs(c[v] - o[v]) / a[v] >= 0.8, ldn_ny=14 <= hour <= 23, asia=hour < 14,
            h1_with=np.sign(H["c"].iat[k] - he[k]) == vd, d1_with=dside.get(dk.iat[v], 0) == vd))
    return pd.DataFrame(rows)


COND = ["fan_v", "fan_against", "fan_none", "adxH1_25", "adxH1_lt20", "adx_lt25", "adx_ge25", "adx_up", "slope_with",
        "slope_against", "slope_flat", "clean", "choppy", "big_body", "ldn_ny", "asia", "h1_with", "d1_with"]


def outcomes(m, groups):
    from g117_v_filters import Sim2
    S = Sim2(m)
    out = {}
    for stop in STOPS:
        r = [S.hedge_r(v, j, stop)[0] for v, j in groups]
        out[stop] = np.array(r, dtype=float)
    return out


def combos():
    for k in (1, 2, 3):
        for c in itertools.combinations(COND, k):
            # skip contradictory pairs
            bad = {("fan_v", "fan_against"), ("fan_v", "fan_none"), ("fan_against", "fan_none"), ("adx_lt25", "adx_ge25"),
                   ("adxH1_25", "adxH1_lt20"), ("slope_with", "slope_against"), ("clean", "choppy"), ("ldn_ny", "asia")}
            if any((a, b) in bad or (b, a) in bad for a, b in itertools.combinations(c, 2)):
                continue
            yield c


def evaluate(F, R, mask):
    x = R[mask]
    yrs = F.loc[mask, "year"].to_numpy()
    ok = ~np.isnan(x)
    x, yrs = x[ok], yrs[ok]
    if len(x) < 60:
        return None
    by = {}
    for y in np.unique(yrs):
        z = x[yrs == y]
        if len(z) >= 8:
            by[int(y)] = z.mean()
    return dict(n=len(x), R=x.mean(), win=(x > 0).mean(), p2=(x >= 2).mean(), p3=(x >= 3).mean(),
                years=len(by), years_pos=sum(v > 0 for v in by.values()), worst=min(by.values()) if by else np.nan,
                by=by)


def main():
    rows, null_counts = [], {}
    rng = np.random.default_rng(118)
    for tf in TFS:
        m = load(tf)
        gr = g.find_groups(m)
        pg = g.find_groups(m, pseudo=True)
        F, P = features(m, gr), features(m, pg)
        RO, PO = outcomes(m, gr), outcomes(m, pg)
        print(f"{tf}: {len(gr)} groups, {len(pg)} random candles, years {F.year.min()}-{F.year.max()}", flush=True)
        for stop in STOPS:
            R, PR = RO[stop], PO[stop]
            # chance level: shuffle outcomes within year, count combos passing the year rule
            nulls = []
            for _ in range(20):
                Rs = R.copy()
                for y in np.unique(F.year):
                    idx = np.flatnonzero(F.year.to_numpy() == y)
                    Rs[idx] = rng.permutation(Rs[idx])
                cnt = 0
                for c in combos():
                    mk = np.logical_and.reduce([F[k].to_numpy() for k in c])
                    ev = evaluate(F, Rs, mk)
                    if ev and ev["years"] >= 2 and ev["years_pos"] == ev["years"]:
                        cnt += 1
                nulls.append(cnt)
            null_counts[(tf, stop)] = (np.median(nulls), np.percentile(nulls, 90))
            for c in combos():
                mk = np.logical_and.reduce([F[k].to_numpy() for k in c])
                ev = evaluate(F, R, mk)
                if not ev:
                    continue
                pm = np.logical_and.reduce([P[k].to_numpy() for k in c])
                pv = PR[pm]
                pv = pv[~np.isnan(pv)]
                rows.append(dict(tf=tf, stop=stop, combo=" & ".join(c), k=len(c), n=ev["n"], R=ev["R"], win=ev["win"],
                                 p2=ev["p2"], p3=ev["p3"], years=ev["years"], years_pos=ev["years_pos"], worst=ev["worst"],
                                 rnd_R=pv.mean() if len(pv) >= 30 else np.nan,
                                 by_year=" ".join(f"{y}:{v:+.2f}" for y, v in ev["by"].items())))
    T = pd.DataFrame(rows)
    T["beats_rnd"] = T.R > T.rnd_R
    T["all_years"] = (T.years >= 2) & (T.years_pos == T.years)
    T.to_csv("out/g118_combos.csv", index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 80)
    print("\nchance level (combos passing 'every year positive' with shuffled outcomes): median / 90th pct")
    for k, v in null_counts.items():
        real = int(T[(T.tf == k[0]) & (T.stop == k[1]) & T.all_years].shape[0])
        print(f"  {k[0]} {k[1]}: real {real} | chance {v[0]:.0f} / {v[1]:.0f}")
    P_ = T[T.all_years & T.beats_rnd].copy()
    # same combo passing on several timeframes
    agg = P_.groupby(["combo", "stop"]).agg(tfs=("tf", lambda s: ",".join(sorted(s))), ntf=("tf", "size"),
                                             n=("n", "sum"), R=("R", "mean"), p2=("p2", "mean"), p3=("p3", "mean"))
    print("\ncombos passing every year AND beating random, on >= 2 timeframes:")
    print(agg[agg.ntf >= 2].sort_values(["ntf", "R"], ascending=False).round(3).head(30).to_string())
    print("\ntop single-timeframe passers by R (n >= 100):")
    print(P_[P_.n >= 100].sort_values("R", ascending=False)[["tf", "stop", "combo", "n", "R", "win", "p2", "p3", "worst", "rnd_R", "by_year"]]
          .round(3).head(25).to_string(index=False))
    cand = T[(T.combo == "fan_v & adxH1_25")]
    print("\nG117 candidate (fan with the break & ADX H1 >= 25) on every timeframe / stop:")
    print(cand[["tf", "stop", "n", "R", "win", "p2", "p3", "years_pos", "years", "rnd_R", "by_year"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
