"""G117: context filters and one-sided variants for the G116 V-candle return setup (user, 14/10/2026).

  python g117_v_filters.py examples   -> features of the user's 3 ticks and the cross (sealed test period, illustration)
  python g117_v_filters.py            -> filters x stops on train / validate, random-candle control, directional variants

Groups = G116 (V body cross of the M5 EMA200, close back inside the V range within 6 bars). Management = G116
(N 3, keep until a leg is stopped, add at the break with the survivor's stop, X3 with X2 k2 fallback, BE at +1R).
Stops: V = V range + 0.1 ATR | A2 / A3 = entry +- 2 / 3 ATR(M5).
Features at the V bar (closed data only): fan (EMA21/55/100 ordered), its side vs the V break, ADX H1 (last closed
hour), ADX M5, EMA200 slope over 4 h, EMA200 body crosses in the 4 h before, V body size, VN hour, H1 EMA200 side.
Directional: no hedge, one pending stop in a chosen direction (fan side / H1 EMA200 side / V side / return side)
with the opposite stop, same adds and exits.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import g116_v_hedge as g
from g97_forming_bar import dmi, ema

STOPS = ("V", "A2", "A3")


def features(m: pd.DataFrame, groups):
    o, c, h, l, e200 = (m[k].to_numpy() for k in ("open", "close", "high", "low", "e200"))
    e21, e55, e100, a, adx = (m[k].to_numpy() for k in ("e21", "e55", "e100", "atr", "adx"))
    # H1 from M5 (server hours), ADX and EMA200 on closed hours
    hk = m["ts"].dt.floor("h")
    H = m.groupby(hk).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    _, _, hadx, _ = dmi(H["h"].to_numpy(), H["l"].to_numpy(), H["c"].to_numpy())
    he = ema(H["c"].to_numpy(), 200)
    hidx = pd.Series(np.arange(len(H)), index=H.index)
    hpos = hk.map(hidx).to_numpy() - 1                          # last closed hour
    body = ((o < e200) & (c > e200)) | ((o > e200) & (c < e200))
    cs = np.cumsum(body)
    rows = []
    for v, j in groups:
        k = max(hpos[v], 0)
        fan = 1 if e21[v] > e55[v] > e100[v] else (-1 if e21[v] < e55[v] < e100[v] else 0)
        vdir = 1 if c[v] > e200[v] else -1
        rows.append(dict(v=v, j=j, t=m["ts"].iat[j], fan=fan, vdir=vdir, fan_v=int(fan == vdir), fan_any=int(fan != 0),
                         adx_h1=hadx[k], adx_m5=adx[v], adx_m5_up=int(adx[v] > adx[v - 1]),
                         slope=(e200[v] - e200[v - 48]) / a[v], crosses=int(cs[v - 1] - cs[v - 49]),
                         vbody=abs(c[v] - o[v]) / a[v], vrange=(h[v] - l[v]) / a[v],
                         hour_vn=int((m["ts"].iat[v] + pd.Timedelta(hours=4)).hour),
                         h1side=int(np.sign(H["c"].iat[k] - he[k]))))
    return pd.DataFrame(rows)


class Sim2(g.Sim):
    def __init__(self, m):
        super().__init__(m)
        self.h = self.h.copy(); self.l = self.l.copy()
        self.H0, self.L0 = self.h.copy(), self.l.copy()

    def _set(self, v, j, stop):
        if stop == "V":
            return
        mult = 2.0 if stop == "A2" else 3.0
        mid = self.o[j + 1]
        self.h[v], self.l[v] = mid + mult * self.atr[j], mid - mult * self.atr[j]

    def _reset(self, v):
        self.h[v], self.l[v] = self.H0[v], self.L0[v]

    def hedge_r(self, v, j, stop):
        self._set(v, j, stop)
        r = self.hedge(v, j, 0.1, 3, "K", "SAME", "X3", 2.0)
        self._reset(v)
        return (np.nan, 0) if r is None else (r[0], r[1])

    def single_r(self, v, j, stop, d):
        """One pending stop in direction d at the far edge, opposite stop, add at the trigger, same exits."""
        self._set(v, j, stop)
        o, h, l, c, sp = self.o, self.h, self.l, self.c, self.sp
        b = 0.1 * self.atr[j]
        VH, VL = h[v], l[v]
        U = VH - VL + 2 * b
        up, dn = VH + b, VL - b
        e = j + 1
        res = (np.nan, 0)
        if e + 2 < len(c) and o[e] + sp[e] < up and o[e] > dn:
            end = min(len(c) - 1, e + g.CAP)
            t = e
            while t <= end:
                trig = (h[t] + sp[t] >= up) if d == 1 else (l[t] <= dn)
                kill = (l[t] <= dn) if d == 1 else (h[t] + sp[t] >= up)
                if trig and kill:
                    res = (-1.0, d); break
                if kill:
                    res = (0.0, 0); break                 # price went the other way first: no trade
                if trig:
                    entry = up if d == 1 else dn
                    sl = dn if d == 1 else up
                    p = self.manage(t, d, [[entry, sl], [entry, sl]], entry, sl, "X3", 2.0)
                    res = (np.nan, 0) if p is None else (p / U, d)
                    break
                t += 1
        self._reset(v)
        return res


def run_all(m, groups):
    S = Sim2(m)
    F = features(m, groups)
    for stop in STOPS:
        out = [S.hedge_r(v, j, stop) for v, j in groups]
        F[f"r_{stop}"] = [x[0] for x in out]
        F[f"d_{stop}"] = [x[1] for x in out]
    return F, S


FILTERS = {
    "all": lambda F: np.ones(len(F), bool),
    "fan_any": lambda F: F.fan_any == 1,
    "fan_vdir": lambda F: F.fan_v == 1,
    "fan_against_v": lambda F: (F.fan != 0) & (F.fan_v == 0),
    "adxH1>=25": lambda F: F.adx_h1 >= 25,
    "adxH1>=30": lambda F: F.adx_h1 >= 30,
    "adxH1<20": lambda F: F.adx_h1 < 20,
    "adxM5>=25 up": lambda F: (F.adx_m5 >= 25) & (F.adx_m5_up == 1),
    "adxM5<25 (user ticks)": lambda F: F.adx_m5 < 25,
    "adxM5<20": lambda F: F.adx_m5 < 20,
    "V against EMA200 slope": lambda F: np.sign(F.slope) == -F.vdir,
    "V with EMA200 slope": lambda F: np.sign(F.slope) == F.vdir,
    "adxM5<25 & V against slope": lambda F: (F.adx_m5 < 25) & (np.sign(F.slope) == -F.vdir),
    "adxM5<25 & crosses=0": lambda F: (F.adx_m5 < 25) & (F.crosses == 0),
    "|slope|>=1": lambda F: F.slope.abs() >= 1,
    "|slope|<0.5": lambda F: F.slope.abs() < 0.5,
    "crosses4h=0": lambda F: F.crosses == 0,
    "crosses4h>=2": lambda F: F.crosses >= 2,
    "vbody>=0.8": lambda F: F.vbody >= 0.8,
    "VN 14-23": lambda F: (F.hour_vn >= 14) & (F.hour_vn <= 23),
    "fan_v & adxH1>=25": lambda F: (F.fan_v == 1) & (F.adx_h1 >= 25),
    "fan_any & crosses=0": lambda F: (F.fan_any == 1) & (F.crosses == 0),
    "adxH1>=25 & crosses=0": lambda F: (F.adx_h1 >= 25) & (F.crosses == 0),
}


def per(F, mask, col):
    out = {}
    for p in ("train", "validate"):
        a, b = g.PERIODS[p]
        x = F.loc[mask & (F.t >= a) & (F.t < b), col].dropna()
        out[p] = (len(x), x.mean() if len(x) else np.nan)
    return out


def main():
    m = g.load()
    lim = pd.Timestamp("2026-01-01")
    groups = [(v, j) for v, j in g.find_groups(m) if m["ts"].iat[j] < lim]
    F, S = run_all(m, groups)
    pseudo = [(v, j) for v, j in g.find_groups(m, pseudo=True) if m["ts"].iat[j] < lim]
    P, _ = run_all(m, pseudo)
    pd.set_option("display.width", 220)
    rows = []
    for name, f in FILTERS.items():
        mk, pm = np.asarray(f(F), bool), np.asarray(f(P), bool)
        for stop in STOPS:
            r = per(F, mk, f"r_{stop}")
            rp = per(P, pm, f"r_{stop}")
            rows.append(dict(filter=name, stop=stop, tra_n=r["train"][0], tra_R=r["train"][1], val_n=r["validate"][0],
                             val_R=r["validate"][1], rnd_tra=rp["train"][1], rnd_val=rp["validate"][1]))
    T = pd.DataFrame(rows)
    T["edge_tra"] = T.tra_R - T.rnd_tra
    T["edge_val"] = T.val_R - T.rnd_val
    T.to_csv("out/g117_filters.csv", index=False)
    print("HEDGE: filters x stops (R per group, U units); rnd = random candles near EMA200 through the same filter")
    print(T.round(3).to_string(index=False))
    ok = T[(T.tra_n >= 100) & (T.val_n >= 40)]
    print("\ncells with R > 0 in train AND validate:", len(ok[(ok.tra_R > 0) & (ok.val_R > 0)]), "of", len(ok))
    print("cells beating random in train AND validate:", len(ok[(ok.edge_tra > 0) & (ok.edge_val > 0)]))
    # directional (no hedge)
    rows = []
    for stop in ("V", "A2", "A3"):
        for rule, dfun in (("fan side", lambda r: r.fan), ("H1 EMA200 side", lambda r: r.h1side),
                           ("V side", lambda r: r.vdir), ("return side", lambda r: -r.vdir)):
            for frame, groups_, FF in (("real", groups, F), ("random", pseudo, P)):
                vals = []
                for (v, j), (_, r) in zip(groups_, FF.iterrows()):
                    d = int(dfun(r))
                    if d == 0:
                        vals.append(np.nan); continue
                    vals.append(S.single_r(v, j, stop, d)[0])
                FF[f"s_{stop}_{rule}"] = vals
            r = per(F, np.ones(len(F), bool), f"s_{stop}_{rule}")
            rp = per(P, np.ones(len(P), bool), f"s_{stop}_{rule}")
            rows.append(dict(stop=stop, direction=rule, tra_n=r["train"][0], tra_R=r["train"][1], val_n=r["validate"][0],
                             val_R=r["validate"][1], rnd_tra=rp["train"][1], rnd_val=rp["validate"][1]))
    D = pd.DataFrame(rows)
    D.to_csv("out/g117_directional.csv", index=False)
    print("\nONE-SIDED (no hedge): pending stop only in the chosen direction")
    print(D.round(3).to_string(index=False))


def examples():
    m = g.load()
    gr = g.find_groups(m)
    sel = [(v, j) for v, j in gr if pd.Timestamp("2026-10-06 01:00") <= m["ts"].iat[j] < pd.Timestamp("2026-10-07 07:00")]
    F = features(m, sel)
    F["vn"] = F.t + pd.Timedelta(hours=4)
    F["mark"] = ["tick", "tick", "CROSS", "tick"][:len(F)]
    print(F[["vn", "mark", "vdir", "fan", "adx_h1", "adx_m5", "adx_m5_up", "slope", "crosses", "vbody", "vrange", "h1side"]]
          .round(2).to_string(index=False))


if __name__ == "__main__":
    examples() if len(sys.argv) > 1 and sys.argv[1] == "examples" else main()
