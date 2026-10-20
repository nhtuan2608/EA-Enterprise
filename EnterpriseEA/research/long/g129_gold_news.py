"""G129: gold after USD news surprises (MT5 calendar actual vs forecast) on M30 - follow the surprise (S), follow with
a confirming release bar (C), follow a big release bar (B); sign-shuffle and no-news controls.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g129-gold-news-surprise.md. MT5 data only.

  python g129_gold_news.py
"""
from __future__ import annotations

import csv
import math
import random
import re
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g126_session_adr as g126  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g129-gold-news-surprise.md"
CALENDAR = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
                r"\MQL5\Files\EnterpriseEA\research\calendar")
INVERTED = ("unemployment", "jobless", "claims")
EXCLUDED = ("crude oil",)
BAR = 1800
COMM = 0.06
VARIANTS = [(s, z, x) for s in ("S", "C") for z in (0.0, 1.0) for x in ("X1", "X2")] + [("B", None, x) for x in ("X1", "X2")]


def num(s):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", s or "")
    return float(m.group(1)) if m else None


def events():
    rows, high_times, nfp = [], [], []
    for f in sorted(CALENDAR.glob("calendar_*.csv")):
        with f.open(encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["importance"] != "HIGH" or r["currency"] != "USD":
                    continue
                ts_ = int(r["time_server"])
                high_times.append(ts_)
                if "nonfarm payrolls" == r["name"].lower().strip():
                    nfp.append((int(r["time_utc"]), ts_))
                if any(k in r["name"].lower() for k in EXCLUDED):
                    continue
                a, fc = num(r["actual"]), num(r["forecast"])
                if a is None or fc is None:
                    continue
                rows.append(dict(t=ts_, name=r["name"], s=a - fc))
    rows.sort(key=lambda x: x["t"])
    hist: dict = {}
    by_t: dict = {}
    for e in rows:
        h = hist.setdefault(e["name"], [])
        z = e["s"] / statistics.pstdev(h) if len(h) >= 8 and statistics.pstdev(h) > 0 else float("nan")
        h.append(e["s"])
        if e["s"] == 0:
            continue
        usd = 1 if e["s"] > 0 else -1
        if any(k in e["name"].lower() for k in INVERTED):
            usd = -usd
        g = by_t.setdefault(e["t"], {"sum": 0, "z": float("nan")})
        g["sum"] += usd
        if z == z:
            g["z"] = abs(z) if g["z"] != g["z"] else max(g["z"], abs(z))
    ev = [dict(t=t, d=(-1 if g["sum"] > 0 else 1), z=g["z"]) for t, g in sorted(by_t.items()) if g["sum"] != 0]
    return ev, sorted(set(high_times)), nfp


class Bars:
    def __init__(self):
        M = g126.load("M30")
        self.t = M["time"].to_numpy()
        self.utc = M["utc"].to_numpy()
        self.o, self.h, self.l, self.c, self.sp = (M[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
        pc = np.r_[self.c[0], self.c[:-1]]
        self.atr = g126.wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.med = float(np.median(self.sp[self.utc >= g126.ts(2024, 3, 1)])) if hasattr(g126, "ts") else float(np.median(self.sp))
        self.pos = {int(x): i for i, x in enumerate(self.t)}
        # H4 EMA200 side of the last completed H4 bucket (server time)
        b = self.t // 14400
        last = np.r_[b[1:] != b[:-1], True]
        closes, buckets = self.c[last], b[last]
        ema = pd.Series(closes).ewm(span=200, adjust=False).mean().to_numpy()
        bp = {k: j for j, k in enumerate(buckets)}
        idx = np.array([bp[k] - 1 for k in b])
        self.h4side = np.where(idx >= 200, np.sign(closes[np.maximum(idx, 0)] - ema[np.maximum(idx, 0)]), 0)

    def trade(self, k, d, exit_):
        """Release bar k; entry at the open of k + 1; stop beyond the release bar's extreme against d."""
        if k + 17 >= len(self.t):
            return None
        a = self.atr[k - 1]
        e = k + 1
        slip = max(0.5 * self.med, self.sp[e])
        entry = self.o[e] + (self.sp[e] if d == 1 else 0.0) + d * slip
        stop = (self.l[k] - 0.1 * a) if d == 1 else (self.h[k] + 0.1 * a)
        risk = d * (entry - stop)
        if risk <= 0:
            return None
        tgt = entry + d * 2 * risk if exit_ == "X1" else None
        last = e + (7 if exit_ == "X1" else 15)
        px = None
        for j in range(e, last + 1):
            sp = self.sp[j] if d == -1 else 0.0
            hi, lo, op = self.h[j] + sp, self.l[j] + sp, self.o[j] + sp
            if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
                px = min(stop, op) if d == 1 else max(stop, op)
                break
            if tgt is not None and ((d == 1 and hi >= tgt) or (d == -1 and lo <= tgt)):
                px = max(tgt, op) if d == 1 else min(tgt, op)
                break
        if px is None:
            px = self.c[last] + (self.sp[last] if d == -1 else 0.0)
        return (d * (px - entry) - 0.5 * self.med - COMM) / risk

    def bar_ok(self, k, d, rng_atr):
        a = self.atr[k - 1]
        rng = self.h[k] - self.l[k]
        return a > 0 and rng >= rng_atr * a and d * (self.c[k] - self.o[k]) >= 0.5 * rng


def run(B, ev, var, signs=None):
    sig, zmin, ex = var
    out = []
    for n, e in enumerate(ev):
        k = B.pos.get(e["t"] - e["t"] % BAR)
        if k is None or k < 20:
            continue
        p = g126.period(int(B.utc[k]))
        if p is None:
            continue
        d, z = (e["d"], e["z"]) if signs is None else signs[n]
        if sig == "B":
            rng = B.h[k] - B.l[k]
            d = 1 if B.c[k] > B.o[k] else -1
            if not B.bar_ok(k, d, 1.5):
                continue
        else:
            if zmin > 0 and not (z == z and z >= zmin):
                continue
            if sig == "C" and not B.bar_ok(k, d, 1.0):
                continue
        r = B.trade(k, d, ex)
        if r is not None:
            out.append(dict(p=p, r=r, d=d, k=k, side=int(B.h4side[k]) == d))
    return out


def mean(x):
    return statistics.fmean(x) if x else 0.0


def cell(tr, p, d=None):
    x = [t["r"] for t in tr if t["p"] == p and (d is None or t["d"] == d)]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def lower90(xs, runs=3000, seed=129):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


def shuffle_p(B, ev, var, obs, period="validate", reps=500, seed=11):
    rng = random.Random(seed)
    idx = [n for n, e in enumerate(ev) if (k := B.pos.get(e["t"] - e["t"] % BAR)) is not None and g126.period(int(B.utc[k])) == period]
    base = [(e["d"], e["z"]) for e in ev]
    hits, means = 0, []
    for _ in range(reps):
        perm = idx[:]
        rng.shuffle(perm)
        signs = base[:]
        for a, b in zip(idx, perm):
            signs[a] = base[b]
        tr = [t for t in run(B, ev, var, signs) if t["p"] == period]
        m = mean([t["r"] for t in tr])
        means.append(m)
        hits += m >= obs
    return mean(means), hits / reps


def nonews_p(B, ev_times, var, obs_tr, period="validate", reps=500, seed=13):
    """B control: the same big-bar rule at the same server times of day on bars without a USD HIGH event within 1 h."""
    near = set()
    for t in ev_times:
        for dt in range(-2, 3):
            near.add((t - t % BAR) + dt * BAR)
    sods = {int(B.t[t["k"]] % 86400) for t in obs_tr}
    pool = []
    for k in range(20, len(B.t) - 18):
        if int(B.t[k] % 86400) not in sods or int(B.t[k]) in near or g126.period(int(B.utc[k])) != period:
            continue
        d = 1 if B.c[k] > B.o[k] else -1
        if not B.bar_ok(k, d, 1.5):
            continue
        r = B.trade(k, d, var[2])
        if r is not None:
            pool.append(r)
    obs = [t["r"] for t in obs_tr]
    if not pool or not obs:
        return float("nan"), float("nan"), 0
    rng = random.Random(seed)
    m_obs = mean(obs)
    hits = sum(1 for _ in range(reps) if mean(rng.choices(pool, k=len(obs))) >= m_obs)
    return mean(pool), hits / reps, len(pool)


def gate(B, nfp):
    share = mean([1.0 if (u % 86400) in (12 * 3600 + 1800, 13 * 3600 + 1800) else 0.0 for u, _ in nfp])
    rng = B.h - B.l
    ks = [B.pos.get(s - s % BAR) for _, s in nfp]
    ks = [k for k in ks if k is not None]
    nfp_set = set(ks)
    ratios = []
    for k in ks:
        sod = int(B.t[k] % 86400)
        other = [rng[j] for j in range(max(0, k - 2000), min(len(B.t), k + 2000))
                 if int(B.t[j] % 86400) == sod and j not in nfp_set and pd.Timestamp(int(B.t[j]), unit="s").weekday() == 4]
        if other:
            ratios.append(rng[k] / statistics.median(other))
    return share, (statistics.median(ratios) if ratios else 0.0), len(ks)


def main():
    if not hasattr(g126, "ts"):
        g126.ts = lambda y, m=1, d=1: int(pd.Timestamp(year=y, month=m, day=d, tz="UTC").timestamp())
    ev, high_times, nfp = events()
    B = Bars()
    share, ratio, nk = gate(B, nfp)
    L = ["# G129: vàng sau tin USD bất ngờ — kết quả", "",
         "Kế hoạch: `plans/2026-10-20-g129-gold-news-surprise.md`. XAUUSD M30 từ 03/2018, tin USD HIGH có thực tế và "
         "dự báo (bỏ tồn kho dầu EIA). Chi phí khắt khe: trượt mỗi chiều max(0,5 × spread trung vị; spread nến vào) + $6/lot. "
         "Ô: số lệnh / R mỗi lệnh.", "",
         f"Kiểm tra đồng hồ: NFP lúc 12:30/13:30 UTC {share:.0%} ({len(nfp)} tin); nến M30 chứa NFP / cùng giờ thứ Sáu khác = "
         f"{ratio:.2f} ({nk} nến).", ""]
    if share < 0.95 or ratio < 1.5:
        L += ["**Kiểm tra đồng hồ không đạt → dừng, không có kết quả.**"]
        REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
        return
    L += [f"Số thời điểm tin (sau gộp, bỏ trung tính): {len(ev)}.", "",
          "## Biến thể (train 03/2018–2021, validate 2022–2025)", "",
          "| Tín hiệu | \\|z\\| ≥ | Thoát | Train | Validate | Mua (train · val) | Bán (train · val) | Đối chứng validate | p | Chọn? |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    selected = []
    for var in VARIANTS:
        tr = run(B, ev, var)
        a = [t["r"] for t in tr if t["p"] == "train"]
        b = [t["r"] for t in tr if t["p"] == "validate"]
        if var[0] == "B":
            ctl, p, npool = nonews_p(B, high_times, var, [t for t in tr if t["p"] == "validate"])
            ctl_s = f"không tin {ctl:+.3f} ({npool})"
        else:
            ctl, p = shuffle_p(B, ev, var, mean(b))
            ctl_s = f"xáo dấu {ctl:+.3f}"
        ok = len(a) >= 40 and len(b) >= 40 and mean(a) > 0 and mean(b) > 0 and p < 0.05
        if ok:
            selected.append((var, tr))
        zs = "—" if var[1] is None else ("mọi" if var[1] == 0 else "1")
        L.append(f"| {var[0]} | {zs} | {var[2]} | {cell(tr, 'train')} | {cell(tr, 'validate')} | "
                 f"{cell(tr, 'train', 1)} · {cell(tr, 'validate', 1)} | {cell(tr, 'train', -1)} · {cell(tr, 'validate', -1)} | "
                 f"{ctl_s} | {p:.3f} | {'**chọn**' if ok else ''} |")
        print(var, flush=True)
    L.append("")
    show = selected or [(VARIANTS[0], run(B, ev, VARIANTS[0]))]
    L += ["## Cùng / ngược phía EMA200 H4 (mô tả)", "", "| Biến thể | Kỳ | Cùng phía | Ngược phía |", "|---|---|---|---|"]
    for var, tr in show:
        for p in ("train", "validate"):
            x = [t["r"] for t in tr if t["p"] == p and t["side"]]
            y = [t["r"] for t in tr if t["p"] == p and not t["side"]]
            L.append(f"| {var[0]} {var[1]} {var[2]} | {p} | {len(x)} / {mean(x):+.3f} | {len(y)} / {mean(y):+.3f} |")
    L.append("")
    L += ["## Test 2026 (mở một lần)", ""]
    if not selected:
        L += ["Không có biến thể nào được chọn → **2026 vẫn niêm phong**.", ""]
    else:
        L += ["| Biến thể | 2026 | Mua · Bán | Cận dưới 90% | Đạt? |", "|---|---|---|---|---|"]
        for var, tr in selected:
            x = [t["r"] for t in tr if t["p"] == "test"]
            lo = lower90(x) if len(x) > 1 else float("nan")
            ok = len(x) > 1 and mean(x) > 0 and lo > 0
            L.append(f"| {var} | {len(x)} / {mean(x):+.3f} | {cell(tr, 'test', 1)} · {cell(tr, 'test', -1)} | {lo:+.3f} | "
                     f"{'**đạt**' if ok else 'không'} |")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
