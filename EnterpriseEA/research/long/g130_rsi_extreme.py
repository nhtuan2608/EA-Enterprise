"""G130: H4 RSI extremes + RSI / RSI-MA cross + DMI (signal A), retest of the old low/high (R), EMA200 break
continuation (B); entries on M15 (E1 RSI cross, E2 EMA21 cross) or at the next H4 open (E0); management on H4 closes:
X = RSI back to 50 and an EMA touched -> M1 take, M2 lock half the open profit then hold to RSI 70/30, M3 hold to 70/30.
Counter-trend trades (buy under a bearish ribbon, sell under a bullish one) always M1, at most 12 H4 bars.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g130-h4-rsi-extreme-scalp.md. MT5 data only.

  python g130_rsi_extreme.py
"""
from __future__ import annotations

import itertools
import random
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g130-h4-rsi-extreme-scalp.md"
H4S, M15S = 14400, 900
COMM = 0.06
T_TRAIN0 = int(pd.Timestamp("2021-08-01").timestamp())
T_VAL = int(pd.Timestamp("2024-01-01").timestamp())
T_TEST = int(pd.Timestamp("2026-01-01").timestamp())
T_END = int(pd.Timestamp("2026-10-10").timestamp())
VARIANTS = list(itertools.product(("D0", "D1", "D2"), ("E0", "E1", "E2"), ("M1", "M2", "M3")))


def period(t):
    return None if t < T_TRAIN0 or t >= T_END else "train" if t < T_VAL else "validate" if t < T_TEST else "test"


def wilder(x, n=14):
    out, a = np.empty(len(x)), None
    for i, v in enumerate(x):
        a = v if a is None else a + (v - a) / n
        out[i] = a
    return out


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def rsi(c, n=14):
    ch = np.diff(c, prepend=c[0])
    g, l = wilder(np.maximum(ch, 0), n), wilder(np.maximum(-ch, 0), n)
    return 100 - 100 / (1 + g / np.maximum(l, 1e-12))


def dmi(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    up, dn = h - np.r_[h[0], h[:-1]], np.r_[l[0], l[:-1]] - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    trs, ps, ms = wilder(tr, n), wilder(pdm, n), wilder(mdm, n)
    pdi, mdi = 100 * ps / np.maximum(trs, 1e-12), 100 * ms / np.maximum(trs, 1e-12)
    adx = wilder(100 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9), n)
    return pdi, mdi, adx, trs


class Data:
    def __init__(self):
        m30 = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
        m30 = m30[m30["time"] >= int(pd.Timestamp("2018-03-05").timestamp())]
        H = m30.assign(b=m30["time"] // H4S).groupby("b").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"),
                                                            c=("close", "last")).reset_index()
        self.hb = H["b"].to_numpy()
        self.ho, self.hh, self.hl, self.hc = (H[k].to_numpy() for k in ("o", "h", "l", "c"))
        self.rsi = rsi(self.hc)
        self.rma = pd.Series(self.rsi).rolling(14).mean().to_numpy()
        self.pdi, self.mdi, self.adx, self.hatr = dmi(self.hh, self.hl, self.hc)
        self.E = {n: ema(self.hc, n) for n in (21, 55, 100, 200)}
        lo3 = np.minimum.reduce([self.E[21], self.E[55], self.E[100]])
        hi3 = np.maximum.reduce([self.E[21], self.E[55], self.E[100]])
        self.regime = np.where(hi3 < self.E[200], -1, np.where(lo3 > self.E[200], 1, 0))
        self.hpos = {int(b): k for k, b in enumerate(self.hb)}
        m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
        self.t = m["time"].to_numpy()
        self.o, self.h, self.l, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01
        self.med = float(np.median(self.sp[self.t >= int(pd.Timestamp("2024-03-01").timestamp())]))
        self.r15 = rsi(self.c)
        self.r15ma = pd.Series(self.r15).rolling(14).mean().to_numpy()
        self.e15 = ema(self.c, 21)
        pc = np.r_[self.c[0], self.c[:-1]]
        self.a15 = wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.mpos = {int(x): i for i, x in enumerate(self.t)}
        self.last_of_bucket = np.r_[(self.t[1:] // H4S) != (self.t[:-1] // H4S), True]
        self.days = {}
        for i, x in enumerate(self.t):
            self.days.setdefault(int(x // 86400), []).append(i)

    def m15_index_at(self, ts):
        return int(np.searchsorted(self.t, ts, side="left"))


# ---------------------------------------------------------------------------
def dmi_ok(D, k, d, kind):
    if kind == "D0":
        return True
    if kind == "D1":
        return D.adx[k] >= 25 and D.adx[k] < D.adx[k - 1]
    falling, rising = (D.mdi, D.pdi) if d == 1 else (D.pdi, D.mdi)
    return falling[k] < falling[k - 1] and rising[k] > rising[k - 1]


def cross(D, k, d):
    return d * (D.rsi[k] - D.rma[k]) > 0 and d * (D.rsi[k - 1] - D.rma[k - 1]) <= 0


def setups(D, dmi_kind):
    """(k, d, type, window_end_k): signal at the close of H4 bar k, entries allowed until the close of bar window_end_k."""
    out = []
    last = {1: [], -1: []}           # previous A/R setups per direction: (k0, extreme)
    for k in range(210, len(D.hb) - 1):
        for d in (1, -1):
            ext = 30 if d == 1 else 70
            touched = (D.rsi[k - 5:k + 1].min() <= ext) if d == 1 else (D.rsi[k - 5:k + 1].max() >= ext)
            typ = None
            if cross(D, k, d) and touched and dmi_ok(D, k, d, dmi_kind):
                typ = "A"
            elif cross(D, k, d) and D.regime[k] == -d and dmi_ok(D, k, d, "D2" if dmi_kind == "D0" else dmi_kind):
                for k0, x0 in reversed(last[d]):
                    if k - k0 > 30:
                        break
                    seg = D.hl[k0 + 1:k + 1] if d == 1 else D.hh[k0 + 1:k + 1]
                    if len(seg) and ((d == 1 and seg.min() <= x0) or (d == -1 and seg.max() >= x0)):
                        typ = "R"
                        break
            if typ:
                x0 = D.hl[k - 5:k + 1].min() if d == 1 else D.hh[k - 5:k + 1].max()
                last[d].append((k, x0))
                out.append((k, d, typ, k + 12))
            e2 = D.E[200]
            if d * (D.hc[k] - e2[k]) > 0 and d * (D.hc[k - 1] - e2[k - 1]) <= 0:
                out.append((k, d, "B", k + 1))
    return out


def entry_index(D, k, d, wend, mode):
    """M15 index of the entry bar (entry at its open), or None."""
    start_t = int(D.hb[k] + 1) * H4S                         # close of H4 bar k
    end_t = int(D.hb[min(wend, len(D.hb) - 1)] + 1) * H4S
    i0 = D.m15_index_at(start_t)
    if i0 >= len(D.t) - 2:
        return None
    if mode == "E0":
        return i0
    for j in range(i0, len(D.t) - 1):
        if D.t[j] + M15S > end_t:
            return None
        # stop waiting once the H4 RSI is back at 50 (A / R windows)
        if D.last_of_bucket[j]:
            kk = D.hpos.get(int(D.t[j] // H4S))
            if kk is not None and kk > k and wend > k + 1 and d * (D.rsi[kk] - 50) >= 0:
                return None
        if mode == "E1":
            if d * (D.r15[j] - D.r15ma[j]) > 0 and d * (D.r15[j - 1] - D.r15ma[j - 1]) <= 0 and d * (D.r15[j] - 50) < 0:
                return j + 1
        else:
            if d * (D.c[j] - D.e15[j]) > 0 and d * (D.c[j - 1] - D.e15[j - 1]) <= 0:
                return j + 1
    return None


def manage(D, e, d, M, counter):
    """Walk from M15 bar e (entry at its open). Returns R after costs, exit index."""
    entry = D.o[e] + (D.sp[e] if d == 1 else 0.0) + d * 0.5 * D.med
    w0 = max(0, e - 12)
    a15 = D.a15[e - 1]
    stop = (D.l[w0:e].min() - 0.1 * a15) if d == 1 else (D.h[w0:e].max() + 0.1 * a15)
    if d * (entry - stop) < a15:
        stop = entry - d * a15
    risk = d * (entry - stop)
    mode = "M1" if counter else M
    max_h4 = 12 if counter else 60
    locked = False
    h4_seen = 0
    exit_next = False
    for j in range(e, len(D.t)):
        if exit_next:
            px = D.o[j] + (D.sp[j] if d == -1 else 0.0)
            return (d * (px - entry) - 0.5 * D.med - COMM) / risk, j
        s = D.sp[j] if d == -1 else 0.0
        if (d == 1 and D.l[j] + s <= stop) or (d == -1 and D.h[j] + s >= stop):
            px = min(stop, D.o[j] + s) if d == 1 else max(stop, D.o[j] + s)
            return (d * (px - entry) - 0.5 * D.med - COMM) / risk, j
        if not D.last_of_bucket[j]:
            continue
        kk = D.hpos.get(int(D.t[j] // H4S))
        if kk is None:
            continue
        h4_seen += 1
        r_ = D.rsi[kk]
        if d * (r_ - (70 if d == 1 else 30)) >= 0 or h4_seen >= max_h4:
            exit_next = True
            continue
        if d * (r_ - 50) >= 0:
            a = D.hatr[kk]
            touch = any(D.hl[kk] - 0.25 * a <= D.E[n][kk] <= D.hh[kk] + 0.25 * a for n in (21, 55, 100, 200))
            if touch:
                if mode == "M1":
                    exit_next = True
                elif mode == "M2" and not locked:
                    locked = True
                    gain = d * (D.hc[kk] - entry)
                    if gain > 0:
                        stop = entry + d * 0.5 * gain
    return float("nan"), len(D.t) - 1


def book(D, var, keep_meta=False):
    dk, E, M = var
    out, free = [], {1: -1, -1: -1}
    for k, d, typ, wend in sorted(setups(D, dk)):
        e = entry_index(D, k, d, wend, E)
        if e is None or e <= free[d] or e >= len(D.t) - 2:
            continue
        p = period(int(D.t[e]))
        if p is None:
            continue
        counter = D.regime[k] == -d
        r, x = manage(D, e, d, M, counter)
        if r != r:
            continue
        free[d] = x
        out.append(dict(p=p, r=r, d=d, typ=typ, counter=bool(counter), e=e, M=M))
    return out


def control(D, trades, p, reps=200, seed=130):
    rng = random.Random(seed)
    obs = [x for x in trades if x["p"] == p]
    if not obs:
        return float("nan"), float("nan")
    days = [d for d in D.days if period(d * 86400) == p]
    means = []
    for _ in range(reps):
        rs = []
        for x in obs:
            tod = int(D.t[x["e"]] % 86400)
            for _try in range(6):
                dd = rng.choice(days)
                if dd == int(D.t[x["e"]] // 86400):
                    continue
                cand = [i for i in D.days[dd] if int(D.t[i] % 86400) == tod]
                if not cand or cand[0] < 20 or cand[0] >= len(D.t) - 2:
                    continue
                r, _ = manage(D, cand[0], x["d"], x["M"], x["counter"])
                if r == r:
                    rs.append(r)
                break
        means.append(statistics.fmean(rs) if rs else float("nan"))
    m_obs = statistics.fmean(x["r"] for x in obs)
    ok = [v for v in means if v == v]
    return statistics.fmean(ok), sum(1 for v in ok if v >= m_obs) / len(ok)


def mean(x):
    return statistics.fmean(x) if x else 0.0


def cell(tr, p, f=lambda x: True):
    x = [t["r"] for t in tr if t["p"] == p and f(t)]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def lower90(xs, runs=3000, seed=130):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


def main():
    D = Data()
    L = ["# G130: RSI H4 quá bán / quá mua + RSI cắt MA + DMI, vào M15 — kết quả", "",
         "Kế hoạch (kèm bổ sung của người dùng): `plans/2026-10-20-g130-h4-rsi-extreme-scalp.md`. XAUUSD, H4 dựng từ M30, "
         "vào lệnh M15 từ 08/2021. Train 08/2021–2023, validate 2024–2025, 2026 niêm phong. Chi phí khắt khe. "
         "Ô: số lệnh / R mỗi lệnh (SL ban đầu = đáy/đỉnh 12 nến M15, tối thiểu 1 ATR M15).", "",
         "## 27 biến thể (A + R + B gộp, mua + bán)", "",
         "| DMI | Vào | Quản lý | Train | Validate | Mua (train · val) | Bán (train · val) | Ngẫu nhiên validate | p | Chọn? |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    books, chosen = {}, []
    for var in VARIANTS:
        tr = book(D, var)
        books[var] = tr
        a = [t["r"] for t in tr if t["p"] == "train"]
        b = [t["r"] for t in tr if t["p"] == "validate"]
        base_ok = len(a) >= 20 and len(b) >= 20 and mean(a) > 0 and mean(b) > 0
        ctl, p = control(D, tr, "validate") if base_ok else (float("nan"), float("nan"))
        ok = base_ok and p < 0.10
        if ok:
            chosen.append((min(mean(a), mean(b)), var))
        L.append(f"| {var[0]} | {var[1]} | {var[2]} | {cell(tr, 'train')} | {cell(tr, 'validate')} | "
                 f"{cell(tr, 'train', lambda t: t['d'] == 1)} · {cell(tr, 'validate', lambda t: t['d'] == 1)} | "
                 f"{cell(tr, 'train', lambda t: t['d'] == -1)} · {cell(tr, 'validate', lambda t: t['d'] == -1)} | "
                 f"{ctl:+.3f} | {p:.3f} | {'**chọn**' if ok else ''} |")
        print(var, flush=True)
    L.append("")
    L += ["Ngẫu nhiên / p chỉ tính cho biến thể đã dương ở cả train và validate với ≥ 20 lệnh.", ""]
    # descriptive breakdowns on the D0 / E0..E2 / M1..M3 books
    L += ["## Mô tả: theo loại tín hiệu và cùng / ngược xu hướng (DMI D0, quản lý M2)", "",
          "| Vào | Loại | Train | Validate |", "|---|---|---|---|"]
    for E in ("E0", "E1", "E2"):
        tr = books[("D0", E, "M2")]
        for name, f in (("A quá bán/mua", lambda t: t["typ"] == "A"), ("R quét đáy/đỉnh cũ", lambda t: t["typ"] == "R"),
                        ("B phá EMA200", lambda t: t["typ"] == "B"), ("cùng xu hướng", lambda t: not t["counter"]),
                        ("ngược xu hướng (M1, ≤ 12 nến)", lambda t: t["counter"])):
            L.append(f"| {E} | {name} | {cell(tr, 'train', f)} | {cell(tr, 'validate', f)} |")
    L.append("")
    L += ["## Mô tả: chốt (M1) / dời SL (M2) / gồng (M3), DMI D0", "", "| Vào | M1 train · val | M2 train · val | M3 train · val |",
          "|---|---|---|---|"]
    for E in ("E0", "E1", "E2"):
        L.append(f"| {E} | " + " | ".join(f"{cell(books[('D0', E, M)], 'train')} · {cell(books[('D0', E, M)], 'validate')}"
                                          for M in ("M1", "M2", "M3")) + " |")
    L.append("")
    L += ["## Test 2026 (mở một lần)", ""]
    if not chosen:
        L += ["Không biến thể nào được chọn → **2026 vẫn niêm phong**.", ""]
    else:
        _, var = max(chosen)
        tr = books[var]
        x = [t["r"] for t in tr if t["p"] == "test"]
        ctl, p = control(D, tr, "test")
        lo = lower90(x) if len(x) > 1 else float("nan")
        ok = len(x) > 1 and mean(x) > 0 and lo > 0 and p < 0.10
        L += [f"Biến thể chọn: **{var}**.", "", f"2026: {cell(tr, 'test')} (mua {cell(tr, 'test', lambda t: t['d'] == 1)}, bán "
              f"{cell(tr, 'test', lambda t: t['d'] == -1)}); cận dưới 90% {lo:+.3f}; ngẫu nhiên {ctl:+.3f}, p {p:.3f}. "
              f"**{'ĐẠT' if ok else 'KHÔNG ĐẠT'}**.", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
