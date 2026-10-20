"""G131: top / bottom after repeated RSI extremes on H4 gold - reversal close (+ doji), a range bar back to EMA21 with the
RSI turning, a retest, then an engulfing or dry-volume close; swing to the H4 EMA200 or the opposite RSI extreme.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g131-rsi-exhaustion-top.md. MT5 data only.

  python g131_rsi_exhaustion.py

d = trade direction: -1 sells a top (after overbought), +1 buys a bottom (after oversold).
"""
from __future__ import annotations

import itertools
import random
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
import os
V = os.environ.get("G131_V", "a")          # "b" = the G131b relaxation (plan section G131b)
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / ("2026-10-20-g131-rsi-exhaustion-top.md" if V == "a" else f"2026-10-20-g131{V}-rsi-exhaustion-top.md")
H4S = 14400
COMM = 0.06
T0 = int(pd.Timestamp("2018-03-05").timestamp())
T_VAL = int(pd.Timestamp("2022-01-01").timestamp())
T_26 = int(pd.Timestamp("2026-01-01").timestamp())
T_END = int(pd.Timestamp("2026-10-10").timestamp())
VARIANTS = list(itertools.product(("X1", "X2", "X3"), ("T1", "T2"), ("E1", "E2", "E3")))


def period(t):
    return None if t < T0 or t >= T_END else "train" if t < T_VAL else "validate" if t < T_26 else "2026"


def wilder(x, n=14):
    out, a = np.empty(len(x)), None
    for i, v in enumerate(x):
        a = v if a is None else a + (v - a) / n
        out[i] = a
    return out


class H4:
    def __init__(self):
        m = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
        m = m[m["time"] >= T0 - 120 * 86400]
        g = m.assign(b=m["time"] // H4S).groupby("b").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"),
                                                         c=("close", "last"), v=("tickvol", "sum"), sp=("spread", "max"))
        self.t = g.index.to_numpy() * H4S
        self.o, self.h, self.l, self.c, self.v = (g[k].to_numpy(float) for k in ("o", "h", "l", "c", "v"))
        self.sp = g["sp"].to_numpy(float) * 0.01
        self.med = float(np.median(self.sp[self.t >= int(pd.Timestamp("2024-03-01").timestamp())]))
        ch = np.diff(self.c, prepend=self.c[0])
        gg, ll = wilder(np.maximum(ch, 0)), wilder(np.maximum(-ch, 0))
        self.rsi = 100 - 100 / (1 + gg / np.maximum(ll, 1e-12))
        self.rma = pd.Series(self.rsi).rolling(14).mean().to_numpy()
        pc = np.r_[self.c[0], self.c[:-1]]
        self.atr = wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.e21 = pd.Series(self.c).ewm(span=21, adjust=False).mean().to_numpy()
        self.e200 = pd.Series(self.c).ewm(span=200, adjust=False).mean().to_numpy()
        self.vavg = pd.Series(self.v).rolling(20).mean().shift(1).to_numpy()
        self.hour = (self.t % 86400) // 3600
        self.day = self.t // 86400


def extreme(H, j, d, ma=False):
    x = H.rma[j] if ma else H.rsi[j]
    return x >= 70 if d == -1 else x <= 30


def colored(H, j, d):
    return d * (H.c[j] - H.o[j]) > 0


def reversal(H, j, d):
    if not colored(H, j, d):
        return False
    beyond = H.c[j] < H.l[j - 1] if d == -1 else H.c[j] > H.h[j - 1]
    engulf = (colored(H, j - 1, -d) and d * (H.c[j] - H.o[j - 1]) >= 0 and d * (H.o[j] - H.c[j - 1]) <= 0)
    return beyond or engulf


def engulfing(H, j, d):
    beyond = H.c[j] < H.l[j - 1] if d == -1 else H.c[j] > H.h[j - 1]
    return (colored(H, j, d) and colored(H, j - 1, -d) and d * (H.c[j] - H.o[j - 1]) >= 0
            and d * (H.o[j] - H.c[j - 1]) <= 0 and (beyond or V in ("b", "c")))


def doji(H, j):
    rng = H.h[j] - H.l[j]
    return rng > 0 and abs(H.c[j] - H.o[j]) <= 0.25 * rng


def context(H, f, d, X):
    lo = max(1, f - 40)
    ext = np.array([extreme(H, j, d) for j in range(lo, f + 1)])
    if not ext.any():
        return False
    last = lo + int(np.flatnonzero(ext)[-1])
    if f - last > 12 or (last >= f and V == "a"):
        return False
    if X == "X3":
        return any(extreme(H, j, d, ma=True) for j in range(lo, f + 1))
    episodes = int(ext[0]) + int(np.sum(ext[1:] & ~ext[:-1]))
    return episodes >= (2 if X == "X1" else 3)


def find_trades(H, var):
    X, T, E = var
    out = []
    for d in (-1, 1):
        f, free = 60, -1
        n = len(H.t)
        while f < n - 20:
            if f <= free or not reversal(H, f, d) or not context(H, f, d, X):
                f += 1
                continue
            start = f
            if T == "T2":
                dj = [j for j in range(f - 2, f + 3) if doji(H, j)]
                if not dj:
                    f += 1
                    continue
                start = max(f, max(dj))
            trade = None
            for m in range(start + 1, min(start + 11, n - 8)):
                rng = H.h[m] - H.l[m]
                body_min = 0.0 if V == "c" else 0.5 * rng      # G131c: range bar without a body ratio
                if not (rng >= 1.5 * H.atr[m - 1] and d * (H.c[m] - H.o[m]) > body_min - (0.0 if V == "c" else 1e-12)):
                    continue
                if not ((d == -1 and H.l[m] <= H.e21[m]) or (d == 1 and H.h[m] >= H.e21[m])):
                    continue
                if V == "a" and not any(d * (H.rsi[x] - H.rma[x]) > 0 and d * (H.rsi[x - 1] - H.rma[x - 1]) <= 0 for x in range(m - 2, m + 1)):
                    continue
                if V in ("b", "c") and not d * (H.rsi[m] - H.rma[m]) > 0:
                    continue
                mid = 0.5 * (H.o[m] + H.c[m])
                if V in ("b", "c"):                 # 38.2 % retrace of the range bar, from its far end
                    mid = (H.l[m] + 0.382 * rng) if d == -1 else (H.h[m] - 0.382 * rng)
                retested = False
                for q in range(m + 1, min(m + (7 if V == "a" else 13), n - 2)):
                    if (d == -1 and H.h[q] >= mid) or (d == 1 and H.l[q] <= mid):
                        retested = True
                    if not retested:
                        continue
                    e1 = engulfing(H, q, d)
                    e2 = colored(H, q, d) and H.vavg[q] > 0 and H.v[q] <= 0.7 * H.vavg[q]
                    if (E == "E1" and e1) or (E == "E2" and e2) or (E == "E3" and (e1 or e2)):
                        trade = (m, q)
                        break
                break                    # only the first range bar after the formation
            if trade is None:
                f += 1
                continue
            m, q = trade
            res = walk(H, q + 1, d, m)
            if res is not None:
                r, x, entry_t, risk_atr = res
                out.append(dict(d=d, r=r, t=entry_t, p=period(entry_t), e=q + 1, risk_atr=risk_atr, f=f))
                free = x
                f = x + 1
            else:
                f += 1
    return [t for t in out if t["p"]]


def walk(H, e, d, m, risk_atr=None):
    if e >= len(H.t) - 1:
        return None
    entry = H.o[e] + (H.sp[e] if d == 1 else 0.0) + d * 0.5 * H.med
    a = H.atr[e - 1]
    if risk_atr is None:
        stop = (H.h[m:e].max() + 0.1 * a) if d == -1 else (H.l[m:e].min() - 0.1 * a)
    else:
        stop = entry - d * risk_atr * a
    risk = d * (entry - stop)
    if risk <= 0 or d * (H.e200[e - 1] - entry) < risk:
        return None
    for j in range(e, min(e + 120, len(H.t))):
        s = H.sp[j] if d == -1 else 0.0
        if (d == -1 and H.h[j] + s >= stop) or (d == 1 and H.l[j] + s <= stop):
            px = max(stop, H.o[j] + s) if d == -1 else min(stop, H.o[j] + s)
            return (d * (px - entry) - 0.5 * H.med - COMM) / risk, j, int(H.t[e]), risk / a
        lvl = H.e200[j - 1]
        if (d == -1 and H.l[j] <= lvl) or (d == 1 and H.h[j] >= lvl):
            px = min(lvl, H.o[j]) + s if d == -1 else max(lvl, H.o[j])
            return (d * (px - entry) - 0.5 * H.med - COMM) / risk, j, int(H.t[e]), risk / a
        if (d == -1 and H.rsi[j] <= 30) or (d == 1 and H.rsi[j] >= 70):
            if j + 1 < len(H.t):
                px = H.o[j + 1] + (H.sp[j + 1] if d == -1 else 0.0)
                return (d * (px - entry) - 0.5 * H.med - COMM) / risk, j + 1, int(H.t[e]), risk / a
    j = min(e + 119, len(H.t) - 1)
    px = H.c[j] + (H.sp[j] if d == -1 else 0.0)
    return (d * (px - entry) - 0.5 * H.med - COMM) / risk, j, int(H.t[e]), risk / a


def control(H, trades, p, reps=200, seed=131):
    rng = random.Random(seed)
    obs = [x for x in trades if x["p"] == p]
    if not obs:
        return float("nan"), float("nan")
    idx_p = [i for i in range(250, len(H.t) - 2) if period(int(H.t[i])) == p]
    by_hour = {}
    for i in idx_p:
        by_hour.setdefault(int(H.hour[i]), []).append(i)
    means = []
    for _ in range(reps):
        rs = []
        for x in obs:
            pool = by_hour.get(int(H.hour[x["e"]]), [])
            for _try in range(20):
                i = rng.choice(pool)
                if H.day[i] == H.day[x["e"]]:
                    continue
                res = walk(H, i, x["d"], None, x["risk_atr"])
                if res is not None:
                    rs.append(res[0])
                    break
        means.append(statistics.fmean(rs) if rs else float("nan"))
    ok = [v for v in means if v == v]
    m_obs = statistics.fmean(x["r"] for x in obs)
    return statistics.fmean(ok), sum(1 for v in ok if v >= m_obs) / len(ok)


def mean(x):
    return statistics.fmean(x) if x else 0.0


def cell(tr, p, d=None):
    x = [t["r"] for t in tr if t["p"] == p and (d is None or t["d"] == d)]
    return f"{len(x)} / {mean(x):+.2f}" if x else "—"


def main():
    H = H4()
    L = [f"# G131{'' if V == 'a' else V}: đỉnh/đáy cạn đà sau nhiều lần RSI quá mua/quá bán — kết quả", "",
         "Kế hoạch: `plans/2026-10-20-g131-rsi-exhaustion-top.md`. XAUUSD H4 (từ M30, 03/2018+). Train 03/2018–2021, validate "
         "2022–2025. 2026 không phải test sạch (ví dụ thiết kế nằm trong 01–03/2026). Chi phí khắt khe. Ô: số lệnh / R mỗi lệnh "
         "(SL trên đỉnh test lại, thoát ở EMA200 H4 hoặc RSI cực trị bên kia).", "",
         "## 18 biến thể", "",
         "| Bối cảnh | Đỉnh | Vào | Train | Validate | Bán (train · val) | Mua (train · val) | Ngẫu nhiên validate | p | Chọn? |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    books, chosen = {}, []
    for var in VARIANTS:
        tr = find_trades(H, var)
        books[var] = tr
        a = [t["r"] for t in tr if t["p"] == "train"]
        b = [t["r"] for t in tr if t["p"] == "validate"]
        base = len(a) >= 10 and len(b) >= 10 and mean(a) > 0 and mean(b) > 0
        ctl, p = control(H, tr, "validate") if (b and base) else (float("nan"), float("nan"))
        ok = base and p < 0.10
        if ok:
            chosen.append((min(mean(a), mean(b)), var))
        L.append(f"| {var[0]} | {var[1]} | {var[2]} | {cell(tr, 'train')} | {cell(tr, 'validate')} | "
                 f"{cell(tr, 'train', -1)} · {cell(tr, 'validate', -1)} | {cell(tr, 'train', 1)} · {cell(tr, 'validate', 1)} | "
                 f"{ctl:+.2f} | {p:.3f} | {'**chọn**' if ok else ''} |")
        print(var, flush=True)
    L += ["", "Ngẫu nhiên / p chỉ tính cho biến thể dương ở cả hai kỳ với ≥ 10 lệnh mỗi kỳ.", ""]
    var = max(chosen)[1] if chosen else ("X1", "T1", "E3")
    tr = books[var]
    L += [f"## 2026 (không phải test sạch) — biến thể {'được chọn' if chosen else 'mặc định'} {var}", "",
          "| Vào lệnh (server) | Chiều | R |", "|---|---|---|"]
    for t in [t for t in tr if t["p"] == "2026"]:
        L.append(f"| {pd.Timestamp(t['t'], unit='s'):%Y-%m-%d %H:%M} | {'BÁN' if t['d'] == -1 else 'MUA'} | {t['r']:+.2f} |")
    L += ["", f"2026: {cell(tr, '2026')} (bán {cell(tr, '2026', -1)}, mua {cell(tr, '2026', 1)}).", ""]
    L += ["## Tất cả lệnh của biến thể đó (train + validate)", "", "| Vào lệnh | Chiều | R | Kỳ |", "|---|---|---|---|"]
    for t in [t for t in tr if t["p"] != "2026"]:
        L.append(f"| {pd.Timestamp(t['t'], unit='s'):%Y-%m-%d %H:%M} | {'BÁN' if t['d'] == -1 else 'MUA'} | {t['r']:+.2f} | {t['p']} |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
