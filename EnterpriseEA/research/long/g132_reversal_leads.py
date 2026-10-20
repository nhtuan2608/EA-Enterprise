"""G132: news-spike fade on M15 (B) and the USD-divergence failed break as trades on H1 (C), both directions.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g132-reversal-leads.md. MT5 data only.

  python g132_reversal_leads.py      -> appends sections B and C to the report

B: 2026 is opened once for the selected variant. C: 07/2025-06/2026 (the G99 test) is opened once for both sides.
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g99_sell_context as g99  # noqa: E402
import g129_gold_news as g129  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g132-reversal-leads.md"
COMM = 0.06


def ts(s):
    return int(pd.Timestamp(s).timestamp())


def mean(x):
    return statistics.fmean(x) if x else 0.0


def lower90(xs, runs=3000, seed=132):
    if len(xs) < 2:
        return float("nan")
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


def cell(tr, p, d=None):
    x = [t["r"] for t in tr if t["p"] == p and (d is None or t["d"] == d)]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def wilder(x, n=14):
    out, a = np.empty(len(x)), None
    for i, v in enumerate(x):
        a = v if a is None else a + (v - a) / n
        out[i] = a
    return out


# ---------------------------------------------------------------------------
# B: news-spike fade (M15)
# ---------------------------------------------------------------------------
B_PER = [("train", ts("2021-08-01"), ts("2024-01-01")), ("validate", ts("2024-01-01"), ts("2026-01-01")),
         ("test", ts("2026-01-01"), ts("2026-10-10"))]


def bper(t):
    for p, a, b in B_PER:
        if a <= t < b:
            return p
    return None


class M15:
    def __init__(self):
        m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
        self.t = m["time"].to_numpy()
        self.o, self.h, self.l, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01
        self.med = float(np.median(self.sp[self.t >= ts("2024-03-01")]))
        pc = np.r_[self.c[0], self.c[:-1]]
        self.atr = wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.pos = {int(x): i for i, x in enumerate(self.t)}

    def fade(self, k, kmult, target):
        """Spike bar k; fade at the open of k + 1. None when the bar is not a spike."""
        a = self.atr[k - 1]
        body = self.c[k] - self.o[k]
        if not a > 0 or abs(body) < kmult * a or k + 10 >= len(self.t):
            return None
        d = -1 if body > 0 else 1
        e = k + 1
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0) + d * 0.5 * self.med
        stop = (self.h[k] + 0.25 * a) if d == -1 else (self.l[k] - 0.25 * a)
        risk = d * (entry - stop)
        if risk <= 0:
            return None
        tgt = (self.c[k] - 0.5 * body) if target == "half" else entry + d * 2 * risk
        if d * (tgt - entry) <= 0:
            return None
        last = e + 7
        px = None
        for j in range(e, last + 1):
            s = self.sp[j] if d == -1 else 0.0
            hi, lo, op = self.h[j] + s, self.l[j] + s, self.o[j] + s
            if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
                px = min(stop, op) if d == 1 else max(stop, op)
                break
            if (d == 1 and hi >= tgt) or (d == -1 and lo <= tgt):
                px = max(tgt, op) if d == 1 else min(tgt, op)
                break
        if px is None:
            px = self.c[last] + (self.sp[last] if d == -1 else 0.0)
        return d, (d * (px - entry) - 0.5 * self.med - COMM) / risk


def part_b(L):
    _, high_times, _ = g129.events()
    B = M15()
    news_bars = sorted({B.pos.get(t - t % 900) for t in high_times} - {None})
    near = set()
    for t in high_times:
        for dt in range(-4, 5):
            near.add(t - t % 900 + dt * 900)
    sods = {int(B.t[k] % 86400) for k in news_bars}
    ctrl_bars = [k for k in range(20, len(B.t) - 12) if int(B.t[k] % 86400) in sods and int(B.t[k]) not in near]
    L += ["## B — đánh ngược cú giật sau tin USD HIGH (M15)", "",
          f"Nến tin: {len(news_bars)}. Đối chứng: nến giật cùng giờ server ở ngày không có tin USD HIGH trong ±1 giờ.", "",
          "| k ATR | Mục tiêu | Train | Validate | Mua (train · val) | Bán (train · val) | Đối chứng train · val | Chọn? |",
          "|---|---|---|---|---|---|---|---|"]
    chosen = []
    books = {}
    for kmult in (2.0, 3.0):
        for target in ("half", "2R"):
            tr, ct = [], []
            for k in news_bars:
                if k < 20:
                    continue
                p = bper(int(B.t[k]))
                r = B.fade(k, kmult, target) if p else None
                if r:
                    tr.append(dict(p=p, d=r[0], r=r[1]))
            for k in ctrl_bars:
                p = bper(int(B.t[k]))
                if p not in ("train", "validate"):
                    continue
                r = B.fade(k, kmult, target)
                if r:
                    ct.append(dict(p=p, d=r[0], r=r[1]))
            a = [t["r"] for t in tr if t["p"] == "train"]
            b = [t["r"] for t in tr if t["p"] == "validate"]
            cb = [t["r"] for t in ct if t["p"] == "validate"]
            ok = len(a) >= 20 and len(b) >= 20 and mean(a) > 0 and mean(b) > 0 and mean(b) > mean(cb)
            if ok:
                chosen.append((min(mean(a), mean(b)), (kmult, target)))
            books[(kmult, target)] = tr
            L.append(f"| {kmult:.0f} | {'hồi 50%' if target == 'half' else '2R'} | {cell(tr, 'train')} | {cell(tr, 'validate')} | "
                     f"{cell(tr, 'train', 1)} · {cell(tr, 'validate', 1)} | {cell(tr, 'train', -1)} · {cell(tr, 'validate', -1)} | "
                     f"{cell(ct, 'train')} · {cell(ct, 'validate')} | {'**chọn**' if ok else ''} |")
    L.append("")
    res = None
    if chosen:
        var = max(chosen)[1]
        x = [t["r"] for t in books[var] if t["p"] == "test"]
        lo = lower90(x)
        ok = len(x) > 1 and mean(x) > 0 and lo > 0
        res = (f"B k{var[0]:.0f} {var[1]}", len(x), mean(x), lo, ok)
        L += [f"**Test 2026 (mở một lần), biến thể k {var[0]:.0f} / {var[1]}:** {cell(books[var], 'test')} "
              f"(mua {cell(books[var], 'test', 1)}, bán {cell(books[var], 'test', -1)}), cận dưới 90% {lo:+.3f} → "
              f"**{'ĐẠT' if ok else 'KHÔNG ĐẠT'}**.", ""]
    else:
        L += ["Không biến thể nào được chọn → **2026 vẫn niêm phong** cho ý này.", ""]
    return res


# ---------------------------------------------------------------------------
# C: USD-divergence failed break as trades (H1)
# ---------------------------------------------------------------------------
def part_c(L):
    h = g99.h1()
    F = g99.features(h)
    c, hi, lo, o = (h[k] for k in ("close", "high", "low", "open"))
    day = h["ts"].dt.normalize()
    dl20 = h.groupby(day)["low"].min()
    prior20l = dl20.rolling(20).min().shift(1)
    newlow = lo < day.map(prior20l)
    failed_low = newlow.rolling(48).max().fillna(0).astype(bool) & (c > day.map(prior20l))
    fx = {}
    for s in ("EURUSD", "USDJPY"):
        x = pd.read_csv(HERE / "data" / "h1v" / f"{s}.csv")
        x["ts"] = pd.to_datetime(x["time"], unit="s")
        fx[s] = x.set_index("ts")["close"].reindex(h["ts"], method="ffill").to_numpy()
    usd = pd.Series((-np.log(fx["EURUSD"]) + np.log(fx["USDJPY"])) / 2)
    gold_down_usd_down = ((c - c.shift(120)) < 0) & ((usd - usd.shift(120)) < 0)
    sell_base = (c < h["e21"]) & (h["mdi"] > h["pdi"])
    buy_base = (c > h["e21"]) & (h["pdi"] > h["mdi"])
    sell_sig = (F["F11"] & F["F12"] & F["F17"] & sell_base).to_numpy()
    buy_sig = (F["F11"] & failed_low.fillna(False) & gold_down_usd_down.fillna(False) & buy_base.fillna(False)).to_numpy()
    O, Hh, Ll, C = (h[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    A = h["atr"].to_numpy()
    sp = h["spread"].to_numpy(float) * 0.01
    med = float(np.median(sp[h["time"].to_numpy() >= ts("2024-03-01")]))
    per = {p: (ts(a), ts(b)) for p, (a, b) in g99.PERIODS.items()}

    def period(t):
        for p, (a, b) in per.items():
            if a <= t < b:
                return p
        return None

    def trade(i, d):
        e = i + 1
        if e + 2 >= len(C) or not A[i] > 0:
            return None
        entry = O[e] + (sp[e] if d == 1 else 0.0) + d * 0.5 * med
        stop, tgt = entry - d * 2 * A[i], entry + d * 6 * A[i]
        risk = 2 * A[i]
        for j in range(e, min(e + 120, len(C))):
            s = sp[j] if d == -1 else 0.0
            if (d == 1 and Ll[j] + s <= stop) or (d == -1 and Hh[j] + s >= stop):
                px = min(stop, O[j] + s) if d == 1 else max(stop, O[j] + s)
                return (d * (px - entry) - 0.5 * med - COMM) / risk
            if (d == 1 and Hh[j] + s >= tgt) or (d == -1 and Ll[j] + s <= tgt):
                px = max(tgt, O[j] + s) if d == 1 else min(tgt, O[j] + s)
                return (d * (px - entry) - 0.5 * med - COMM) / risk
        j = min(e + 119, len(C) - 1)
        return (d * (C[j] + (sp[j] if d == -1 else 0.0) - entry) - 0.5 * med - COMM) / risk

    def book(sig, d):
        out = []
        for i in g99.episodes(sig, 24):
            p = period(int(h["time"].iat[i]))
            r = trade(i, d) if p else None
            if r is not None:
                out.append(dict(p=p, d=d, r=r))
        return out

    L += ["## C — lệch USD + phá đỉnh/đáy 20 ngày thất bại (H1), thành lệnh (SL 2 ATR, TP 6 ATR)", "",
          "| Chiều | Train 2018–21 | Validate 2022–06/2025 | **Test 07/2025–06/2026** | Cận dưới 90% test | Đối chứng nền (test) | Đạt? |",
          "|---|---|---|---|---|---|---|"]
    res = []
    for d, sig, base, name in ((-1, sell_sig, sell_base.to_numpy(), "Bán (F11+F12+F17)"),
                               (1, buy_sig, buy_base.fillna(False).to_numpy(), "Mua (đối xứng)")):
        tr = book(sig, d)
        ct = book(base & ~sig, d)
        x = [t["r"] for t in tr if t["p"] == "test"]
        cx = [t["r"] for t in ct if t["p"] == "test"]
        lo = lower90(x)
        ok = len(x) > 1 and mean(x) > 0 and lo > 0 and mean(x) > mean(cx)
        res.append((f"C {name}", len(x), mean(x), lo, ok))
        L.append(f"| {name} | {cell(tr, 'train')} | {cell(tr, 'validate')} | {cell(tr, 'test')} | {lo:+.3f} | "
                 f"{cell(ct, 'test')} | {'**ĐẠT**' if ok else 'không'} |")
    L.append("")
    return res


def main():
    L = []
    rb = part_b(L)
    print("B done", flush=True)
    rc = part_c(L)
    print("C done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
