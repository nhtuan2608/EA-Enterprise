"""G133: the moving-average map on gold, small and large timeframes.
Part 1 dip entries at SMA50 / SMA100 in a golden (death) cross state, M15..D1; part 2 golden/death cross state of
H1/H4/D1 as an S07 filter; part 3 EMA5>10>20 pullback to EMA20 with the higher-timeframe SMA200 side, M15/M30/H1.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g133-moving-average-map.md. MT5 data only.

  python g133_ma_map.py
"""
from __future__ import annotations

import pickle
import random
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g133-moving-average-map.md"
COMM = 0.06
SEC = {"M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def ts(s):
    return int(pd.Timestamp(s).timestamp())


def periods(tf):
    if tf == "M15":
        return [("train", ts("2021-08-01"), ts("2024-01-01")), ("validate", ts("2024-01-01"), ts("2026-01-01")),
                ("test", ts("2026-01-01"), ts("2026-10-10"))]
    return [("train", ts("2018-03-05"), ts("2022-01-01")), ("validate", ts("2022-01-01"), ts("2026-01-01")),
            ("test", ts("2026-01-01"), ts("2026-10-10"))]


def wilder(x, n=14):
    out, a = np.empty(len(x)), None
    for i, v in enumerate(x):
        a = v if a is None else a + (v - a) / n
        out[i] = a
    return out


class Bars:
    def __init__(self, tf):
        self.tf = tf
        if tf == "M15":
            m = pd.read_csv(HERE / "data" / "m15v" / "XAUUSD.csv")
        else:
            m = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
            m = m[m["time"] >= ts("2017-06-01")]           # daily bars before 2018: dropped after warm-up below
            if tf != "M30":
                m = m.assign(b=m["time"] // SEC[tf]).groupby("b").agg(time=("time", "first"), open=("open", "first"),
                    high=("high", "max"), low=("low", "min"), close=("close", "last"), spread=("spread", "max")).reset_index(drop=True)
                m["time"] = (m["time"] // SEC[tf]) * SEC[tf]
        m = m.reset_index(drop=True)
        self.t = m["time"].to_numpy()
        self.o, self.h, self.l, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01
        self.med = float(np.median(self.sp[self.t >= ts("2024-03-01")]))
        cs = pd.Series(self.c)
        self.ema = {n: cs.ewm(span=n, adjust=False).mean().to_numpy() for n in (5, 10, 20)}
        self.sma = {n: cs.rolling(n).mean().to_numpy() for n in (50, 100, 200)}
        pc = np.r_[self.c[0], self.c[:-1]]
        self.atr = wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.per = periods(tf)
        self.hour = (self.t % 86400) // 3600
        self.day = self.t // 86400

    def period(self, t):
        for p, a, b in self.per:
            if a <= t < b:
                return p
        return None

    def htf_side(self, H):
        """+1/-1: close of the last COMPLETED bar of H vs its SMA200, for every bar of self (0 when unknown)."""
        sec = SEC[H.tf]
        b = (self.t + SEC[self.tf]) // sec          # bucket of this bar's close time
        hb = H.t // sec
        idx = np.searchsorted(hb, b, side="left") - 1  # last H bar starting before the bucket of our close
        ok = idx >= 0
        s = np.where(ok, np.sign(H.c[np.maximum(idx, 0)] - H.sma[200][np.maximum(idx, 0)]), 0)
        return np.nan_to_num(s)


def walk(B, e, d, stop, exit_kind, cap, r_mult=None):
    entry = B.o[e] + (B.sp[e] if d == 1 else 0.0) + d * 0.5 * B.med
    risk = d * (entry - stop)
    if risk <= 0:
        return None
    tgt = entry + d * r_mult * risk if r_mult else None
    for j in range(e, min(e + cap, len(B.t) - 1)):
        s = B.sp[j] if d == -1 else 0.0
        if (d == 1 and B.l[j] + s <= stop) or (d == -1 and B.h[j] + s >= stop):
            px = min(stop, B.o[j] + s) if d == 1 else max(stop, B.o[j] + s)
            return (d * (px - entry) - 0.5 * B.med - COMM) / risk, j
        if tgt is not None and ((d == 1 and B.h[j] + s >= tgt) or (d == -1 and B.l[j] + s <= tgt)):
            px = max(tgt, B.o[j] + s) if d == 1 else min(tgt, B.o[j] + s)
            return (d * (px - entry) - 0.5 * B.med - COMM) / risk, j
        if exit_kind is not None and d * (B.c[j] - exit_kind[j]) < 0:
            px = B.o[j + 1] + (B.sp[j + 1] if d == -1 else 0.0)
            return (d * (px - entry) - 0.5 * B.med - COMM) / risk, j + 1
    j = min(e + cap, len(B.t) - 1)
    return (d * (B.c[j] + (B.sp[j] if d == -1 else 0.0) - entry) - 0.5 * B.med - COMM) / risk, j


def stop_for(B, i, d):
    a = B.atr[i]
    stop = (B.l[i] - 0.1 * a) if d == 1 else (B.h[i] + 0.1 * a)
    if d * (B.o[i + 1] - stop) < 0.5 * a:
        stop = B.o[i + 1] - d * 0.5 * a
    return stop


def part1(B, ma, exit_name):
    M, S50, S200 = B.sma[ma], B.sma[50], B.sma[200]
    out, free = [], {1: -1, -1: -1}
    for i in range(210, len(B.t) - 2):
        p = B.period(int(B.t[i]))
        if p is None:
            continue
        for d in (1, -1):
            if i <= free[d]:
                continue
            state = d * (S50[i] - S200[i]) > 0 and d * (B.c[i] - S200[i]) > 0
            if not state:
                continue
            touch = (B.l[i] <= M[i]) if d == 1 else (B.h[i] >= M[i])
            if not (touch and d * (B.c[i] - M[i]) > 0 and d * (B.c[i - 1] - M[i - 1]) > 0):
                continue
            st = stop_for(B, i, d)
            res = walk(B, i + 1, d, st, B.ema[20] if exit_name == "X2" else None, 100, 2.0 if exit_name == "X1" else None)
            if res:
                out.append(dict(p=p, d=d, r=res[0], e=i + 1, ratr=d * (B.o[i + 1] - st) / B.atr[i], exit=exit_name))
                free[d] = res[1]
    return out


def part3(B, side, exit_name):
    E5, E10, E20 = B.ema[5], B.ema[10], B.ema[20]
    out, free = [], {1: -1, -1: -1}
    for i in range(210, len(B.t) - 2):
        p = B.period(int(B.t[i]))
        if p is None:
            continue
        for d in (1, -1):
            if i <= free[d] or side[i] != d:
                continue
            stack = d * (E5[i - 1] - E10[i - 1]) > 0 and d * (E10[i - 1] - E20[i - 1]) > 0
            touch = (B.l[i] <= E20[i]) if d == 1 else (B.h[i] >= E20[i])
            if not (stack and touch and d * (B.c[i] - E20[i]) > 0 and d * (E10[i] - E20[i]) > 0):
                continue
            st = stop_for(B, i, d)
            res = walk(B, i + 1, d, st, E10 if exit_name == "Y2" else None, 48, 1.5 if exit_name == "Y1" else None)
            if res:
                out.append(dict(p=p, d=d, r=res[0], e=i + 1, ratr=d * (B.o[i + 1] - st) / B.atr[i], exit=exit_name))
                free[d] = res[1]
    return out


def control(B, trades, p, exit_kind, r_mult, cap, reps=100, seed=133):
    rng = random.Random(seed)
    obs = [x for x in trades if x["p"] == p]
    if not obs:
        return float("nan"), float("nan")
    pool = {}
    for i in range(210, len(B.t) - cap - 2):
        if B.period(int(B.t[i])) == p:
            pool.setdefault(int(B.hour[i]), []).append(i)
    means = []
    for _ in range(reps):
        rs = []
        for x in obs:
            cand = pool.get(int(B.hour[x["e"]]), [])
            for _t in range(10):
                i = rng.choice(cand)
                if B.day[i] == B.day[x["e"]]:
                    continue
                st = B.o[i] - x["d"] * x["ratr"] * B.atr[i - 1]
                res = walk(B, i, x["d"], st, exit_kind, cap, r_mult)
                if res:
                    rs.append(res[0])
                    break
        means.append(statistics.fmean(rs) if rs else float("nan"))
    ok = [v for v in means if v == v]
    m = statistics.fmean(x["r"] for x in obs)
    return statistics.fmean(ok), sum(1 for v in ok if v >= m) / len(ok)


def mean(x):
    return statistics.fmean(x) if x else 0.0


def cell(tr, p, d=None):
    x = [t["r"] for t in tr if t["p"] == p and (d is None or t["d"] == d)]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def lower90(xs, runs=3000, seed=133):
    if len(xs) < 2:
        return float("nan")
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


def judge(B, tr, exit_kind, r_mult, cap, L, label, tests):
    a = [t["r"] for t in tr if t["p"] == "train"]
    b = [t["r"] for t in tr if t["p"] == "validate"]
    base = len(a) >= 20 and len(b) >= 20 and mean(a) > 0 and mean(b) > 0
    ctl, p = control(B, tr, "validate", exit_kind, r_mult, cap) if base else (float("nan"), float("nan"))
    ok = base and p < 0.10
    L.append(f"| {label} | {cell(tr, 'train')} | {cell(tr, 'validate')} | {cell(tr, 'train', 1)} · {cell(tr, 'validate', 1)} | "
             f"{cell(tr, 'train', -1)} · {cell(tr, 'validate', -1)} | {ctl:+.3f} | {p:.3f} | {'**chọn**' if ok else ''} |")
    if ok:
        tests.append((label, B, tr, exit_kind, r_mult, cap))


def main():
    bars = {tf: Bars(tf) for tf in ("M15", "M30", "H1", "H4", "D1")}
    L = ["# G133: bảng tra MA trên vàng, khung nhỏ và khung lớn — kết quả", "",
         "Kế hoạch: `plans/2026-10-20-g133-moving-average-map.md`. Chi phí khắt khe. Ô: số lệnh / R mỗi lệnh. Train / validate theo "
         "khung (M15 08/2021–2023 / 2024–2025; khung khác 03/2018–2021 / 2022–2025); 2026 chỉ mở cho ô được chọn.", "",
         "## Phần 1 — điều chỉnh về SMA50 / SMA100 khi golden (bán: death)", "",
         "| Khung · MA · thoát | Train | Validate | Mua (train · val) | Bán (train · val) | Ngẫu nhiên val | p | Chọn? |",
         "|---|---|---|---|---|---|---|---|"]
    tests = []
    for tf, B in bars.items():
        for ma in (50, 100):
            for ex in ("X1", "X2"):
                tr = part1(B, ma, ex)
                judge(B, tr, B.ema[20] if ex == "X2" else None, 2.0 if ex == "X1" else None, 100, L,
                      f"{tf} · SMA{ma} · {'TP 2R' if ex == 'X1' else 'đóng dưới EMA20'}", tests)
        print("part1", tf, flush=True)
    L += ["", "## Phần 3 — scalp chuỗi EMA5 > 10 > 20, hồi về EMA20, cùng phía SMA200 khung lớn", "",
          "| Khung · thoát | Train | Validate | Mua (train · val) | Bán (train · val) | Ngẫu nhiên val | p | Chọn? |",
          "|---|---|---|---|---|---|---|---|"]
    for tf, H in (("M15", "H4"), ("M30", "H4"), ("H1", "D1")):
        B = bars[tf]
        side = B.htf_side(bars[H])
        for ex in ("Y1", "Y2"):
            tr = part3(B, side, ex)
            judge(B, tr, B.ema[10] if ex == "Y2" else None, 1.5 if ex == "Y1" else None, 48, L,
                  f"{tf} (khung lớn {H}) · {'TP 1,5R' if ex == 'Y1' else 'đóng dưới EMA10'}", tests)
        print("part3", tf, flush=True)
    L.append("")
    # Part 2: golden/death cross state as an S07 filter
    import g107_portfolio as p107
    import g67_dmi_ema as g67
    cache = HERE / "out" / "g133_s07_legs.pkl"
    if cache.exists():
        legs = pickle.loads(cache.read_bytes())
    else:
        legs = [dict(d=int(x["d"]), t=int((x["t_in"] - pd.Timestamp(0)).total_seconds()), r=float(x["r"]))
                for x in p107.s07_to_server(p107.s07_legs())]
        cache.write_bytes(pickle.dumps(legs))
    L += ["## Phần 2 — golden / death cross (SMA50 vs SMA200) cùng chiều lệnh, làm bộ lọc cho S07", "",
          "| Khung nhãn | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ | Giữ bộ lọc? | 2026: giữ / bỏ |", "|---|---|---|---|---|---|"]
    PER = periods("H1")
    for tf in ("H1", "H4", "D1"):
        B = bars[tf]
        sec = SEC[tf]
        rows = []
        for x in legs:
            k = np.searchsorted(B.t, x["t"] - x["t"] % sec, side="left") - 1     # last completed bar
            if k < 200:
                continue
            st = np.sign(B.sma[50][k] - B.sma[200][k])
            p = next((pp for pp, a, b in PER if a <= x["t"] < b), None)
            if p:
                rows.append(dict(p=p, r=x["r"], keep=bool(st == x["d"])))
        cells, ok = [], True
        for p in ("train", "validate"):
            a = [r["r"] for r in rows if r["p"] == p and r["keep"]]
            b = [r["r"] for r in rows if r["p"] == p and not r["keep"]]
            cells.append(f"{len(a)} {mean(a):+.3f} / {len(b)} {mean(b):+.3f}")
            ok = ok and bool(a) and bool(b) and mean(a) > mean(b)
        tv = [r for r in rows if r["p"] != "test"]
        share = sum(r["keep"] for r in tv) / max(len(tv), 1)
        ok = ok and share >= 0.4
        t26 = "—"
        if ok:
            a = [r["r"] for r in rows if r["p"] == "test" and r["keep"]]
            b = [r["r"] for r in rows if r["p"] == "test" and not r["keep"]]
            t26 = f"{len(a)} {mean(a):+.3f} / {len(b)} {mean(b):+.3f} → **{'đạt' if a and b and mean(a) > mean(b) else 'không'}**"
        L.append(f"| {tf} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} | {t26} |")
    L.append("")
    L += ["## Test 2026 (phần 1 và 3, mở một lần cho ô được chọn)", ""]
    if not tests:
        L += ["Không ô nào được chọn → 2026 không mở cho phần 1 và 3.", ""]
    else:
        L += ["| Ô | 2026 | Mua · Bán | Cận dưới 90% | Ngẫu nhiên / p | Đạt? |", "|---|---|---|---|---|---|"]
        for label, B, tr, ek, rm, cap in tests:
            x = [t["r"] for t in tr if t["p"] == "test"]
            ctl, p = control(B, tr, "test", ek, rm, cap)
            lo = lower90(x)
            ok = len(x) > 1 and mean(x) > 0 and lo > 0 and p < 0.10
            L.append(f"| {label} | {cell(tr, 'test')} | {cell(tr, 'test', 1)} · {cell(tr, 'test', -1)} | {lo:+.3f} | "
                     f"{ctl:+.3f} / {p:.3f} | {'**ĐẠT**' if ok else 'không'} |")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
