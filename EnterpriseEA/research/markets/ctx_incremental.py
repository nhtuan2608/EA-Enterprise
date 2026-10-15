"""Bar-by-bar (incremental) version of the MKT03/MKT04 context features - the exact algorithm CtxLimitTester.mq5
implements in MQL5. Checked against the pandas features on the gold M30 history.

  python ctx_incremental.py
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

import mkt03_context as m3
import mkt04_context_h4 as m4

NAN = float("nan")


class Wilder:
    def __init__(self, n):
        self.n, self.v, self.ok = n, 0.0, False

    def add(self, x):
        self.v = x if not self.ok else self.v + (x - self.v) / self.n
        self.ok = True
        return self.v


class Ema:
    def __init__(self, n):
        self.k, self.v, self.ok = 2.0 / (n + 1), 0.0, False

    def add(self, x):
        self.v = x if not self.ok else self.v + self.k * (x - self.v)
        self.ok = True
        return self.v


class Htf:
    """Last COMPLETED bucket of `sec` seconds: close, EMA(n) of bucket closes, Wilder ATR14 of buckets."""

    def __init__(self, sec, n=200):
        self.sec, self.n = sec, n
        self.cur, self.h, self.l, self.c = None, 0.0, 0.0, 0.0
        self.prev_c = None
        self.ema, self.atr = Ema(n), Wilder(14)
        self.done = 0
        self.last_c = self.last_e = self.last_a = NAN

    def add(self, t, h, l, c):
        b = t // self.sec
        if self.cur is not None and b != self.cur:
            pc = self.c if self.prev_c is None else self.prev_c
            tr = max(self.h, pc) - min(self.l, pc)
            self.last_e = self.ema.add(self.c)
            self.last_a = self.atr.add(tr)
            self.last_c = self.c
            self.prev_c = self.c
            self.done += 1
            self.cur = None
        if self.cur is None:
            self.cur, self.h, self.l = b, h, l
        else:
            self.h, self.l = max(self.h, h), min(self.l, l)
        self.c = c


class Context:
    def __init__(self):
        self.k = -1
        self.prev_c = None
        self.prev_h = self.prev_l = None
        self.atr, self.atr100 = Wilder(14), Wilder(100)
        self.pdm, self.mdm, self.dx = Wilder(14), Wilder(14), Wilder(14)
        self.gain, self.loss = Wilder(14), Wilder(14)
        self.e21, self.e55, self.e100, self.e200 = Ema(21), Ema(55), Ema(100), Ema(200)
        self.closes = deque(maxlen=97)
        self.highs, self.lows = deque(maxlen=16), deque(maxlen=16)
        self.h4, self.d1 = Htf(14400), Htf(86400)
        self.day, self.dmax, self.dmin, self.pv, self.vv = None, 0.0, 0.0, 0.0, 0.0
        self.pdh = self.pdl = NAN
        self.slots: dict = {}
        self.f: dict = {}
        self.a14 = NAN

    def add(self, t, o, h, l, c, v):
        self.k += 1
        pc = c if self.prev_c is None else self.prev_c
        tr = max(h, pc) - min(l, pc)
        a = self.atr.add(tr)
        a100 = self.atr100.add(tr)
        ph = h if self.prev_h is None else self.prev_h
        pl = l if self.prev_l is None else self.prev_l
        up, dn = h - ph, pl - l
        pdm = up if (up > dn and up > 0) else 0.0
        mdm = dn if (dn > up and dn > 0) else 0.0
        pds, mds = self.pdm.add(pdm), self.mdm.add(mdm)
        pdi, mdi = 100 * pds / max(a, 1e-12), 100 * mds / max(a, 1e-12)
        adx = self.dx.add(100 * abs(pdi - mdi) / max(pdi + mdi, 1e-9))
        ch = c - pc
        gg, ll = self.gain.add(max(ch, 0.0)), self.loss.add(max(-ch, 0.0))
        rsi = 100 - 100 / (1 + gg / max(ll, 1e-12))
        e21, e55, e100, e200 = self.e21.add(c), self.e55.add(c), self.e100.add(c), self.e200.add(c)
        self.closes.append(c)
        self.highs.append(h)
        self.lows.append(l)
        self.h4.add(t, h, l, c)
        self.d1.add(t, h, l, c)
        day = t // 86400
        if day != self.day:
            if self.day is not None:
                self.pdh, self.pdl = self.dmax, self.dmin
            self.day, self.dmax, self.dmin, self.pv, self.vv = day, h, l, 0.0, 0.0
        else:
            self.dmax, self.dmin = max(self.dmax, h), min(self.dmin, l)
        w = max(v, 1.0)
        self.pv += w * (h + l + c) / 3
        self.vv += w
        sod = t % 86400
        hist = self.slots.setdefault(sod, deque(maxlen=20))
        mean20 = sum(hist) / len(hist) if len(hist) >= 10 else NAN
        hist.append(v)

        def back(n):
            return (c - self.closes[-1 - n]) / a if len(self.closes) > n else NAN

        f = {}
        f["r1"], f["r4"], f["r16"], f["r48"] = back(1), back(4), back(16), back(48)
        f["d_e21"], f["e21_e55"], f["e55_e200"] = (c - e21) / a, (e21 - e55) / a, (e55 - e200) / a
        for name, x in (("h4", self.h4), ("d1", self.d1)):
            ok = x.done >= 201
            f[f"{name}_side"] = (1.0 if x.last_c > x.last_e else -1.0 if x.last_c < x.last_e else 0.0) if ok else NAN
            f[f"{name}_dist"] = (c - x.last_e) / a if ok else NAN
        f["adx"], f["di"], f["rsi"] = adx, pdi - mdi, rsi
        f["atr_ratio"] = a / a100
        f["comp16"] = (max(self.highs) - min(self.lows)) / a if len(self.highs) == 16 else NAN
        f["d_pdh"], f["d_pdl"] = (c - self.pdh) / a, (c - self.pdl) / a
        f["day_pos"] = (c - self.dmin) / max(self.dmax - self.dmin, 1e-12)
        f["d_vwap"] = (c - self.pv / self.vv) / a
        step = 10.0 ** (math.floor(math.log10(c)) - 2)
        f["round"] = math.fmod(c, step) / step
        f["ny_hour"] = float(((sod // 3600) - 7) % 24)
        f["dow"] = float(((t - 7 * 3600) // 86400 + 3) % 7)
        f["ny_min"] = (sod - (16 * 3600 + 1800)) / 60 if 16 * 3600 + 1800 <= sod <= 23 * 3600 else -1.0
        f["vol_ratio"] = v / mean20 if mean20 == mean20 else NAN
        f["lead_r1"], f["lead_r4"] = f["r1"], f["r4"]
        f["r96"] = back(96)
        A = self.h4.last_a if self.h4.done >= 15 else NAN
        f["atr_vs_h4"] = a / A
        f["sym"] = 0.0
        self.f, self.a14, self.A = f, a, A
        self.prev_c, self.prev_h, self.prev_l = c, h, l
        return f


def main():
    df = m4.load("XAUUSD")
    lead = m4.leader_frame("XAUUSD")
    ref, _ = m3.context(df, lead)
    ref["r96"] = (df["close"] - df["close"].shift(96)) / _
    ref["atr_vs_h4"] = _ / m4.h4_atr(df)
    ref["sym"] = 0.0
    feats = [c for c in ref.columns if c != "time"]
    ctx = Context()
    worst = {k: 0.0 for k in feats}
    for i, r in enumerate(df.itertuples(index=False)):
        f = ctx.add(r.time, r.open, r.high, r.low, r.close, r.tickvol)
        if i < 12000:
            continue
        for k in feats:
            a, b = f[k], ref.at[i, k]
            if (a != a) != (b != b):
                worst[k] = float("inf")
            elif a == a:
                worst[k] = max(worst[k], abs(a - b) / max(1.0, abs(b)))
    for k, v in worst.items():
        print(f"{k:10s} {v:.2e}")


if __name__ == "__main__":
    main()
