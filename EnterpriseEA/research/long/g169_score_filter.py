"""G169: LFX-style multi-timeframe score (trend alignment minus counter extremes) as a filter on neutral M15 triggers
(T1 hourly both sides, T2 M15 rejection candle), LFX bot geometry (SL 1.1 ATR M15, TP 1.5R / 2.5R halves, BE after TP1, 24 h).
Plan: docs/superpowers/plans/2026-11-17-g169-mtf-score-filter.md.

Usage: g169_score_filter.py <research data dir> <g168 results dir with mt5_XAUUSD_*.csv> <out dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

TS = lambda s: pd.Timestamp(s).value // 10**9  # noqa: E731
SEL0, SEL1, END = TS("2021-07-20"), TS("2024-01-01"), TS("2026-11-18")
HOLD0, HOLD1 = TS("2026-06-01"), TS("2026-07-01")            # hypothesis month, excluded
M5_FROM = TS("2024-05-15")
COMM_OZ, SWAP_OZ = 0.06, 0.30
BOOT, SEED = 2000, 169
ALPHA = 0.05 / 2


def merge(a, b):
    a = pd.read_csv(a)
    b = pd.read_csv(b)
    b = b[b["time"] > a["time"].max()]
    d = pd.concat([a, b[[c for c in a.columns if c in b.columns]]], ignore_index=True)
    d["sp"] = np.maximum(d["spread"].fillna(0).to_numpy() * 0.01, 0.10)
    return d


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).to_numpy()


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    return pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def resample(h1, sec):
    g = h1["time"] // sec
    return h1.groupby(g).agg(time=("time", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"),
                             close=("close", "last")).reset_index(drop=True)


def frame(d, sec):
    c, h, l = d["close"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy()
    e50 = ema(c, 50)
    return {"t_close": d["time"].to_numpy() + sec, "c": c, "h": h, "l": l, "e50": e50, "slope": np.r_[np.zeros(10), e50[10:] - e50[:-10]],
            "rsi": rsi(c)}


def build(root, res):
    h1 = merge(Path(root) / "h1v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_H1.csv")
    m15 = merge(Path(root) / "m15v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_M15.csv") if Path(res, "mt5_XAUUSD_M15.csv").exists() else \
        pd.read_csv(Path(root) / "m15v" / "XAUUSD.csv")
    if "sp" not in m15:
        m15["sp"] = np.maximum(m15["spread"].fillna(0).to_numpy() * 0.01, 0.10)
    m5 = merge(Path(root) / "m5v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_M5.csv")
    h4 = resample(h1, 14400)
    # D1 on server days with the R1 regime of each day
    day = h1["time"] // 86400
    d1 = h1.groupby(day).agg(time=("time", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"),
                             close=("close", "last")).reset_index(drop=True)
    d1["time"] = (d1["time"] // 86400) * 86400
    F = {"M15": frame(m15, 900), "H1": frame(h1, 3600), "H4": frame(h4, 14400), "D1": frame(d1, 86400)}
    e = F["D1"]["e50"]
    c = F["D1"]["c"]
    reg = np.zeros(len(c), int)
    for k in range(60, len(c)):
        if c[k] > e[k] and e[k] > e[k - 10]:
            reg[k] = 1
        elif c[k] < e[k] and e[k] < e[k - 10]:
            reg[k] = -1
    F["D1"]["reg"] = reg
    return m15, m5, F


def last_idx(fr, ts):
    return np.searchsorted(fr["t_close"], ts, side="right") - 1


def score_arrays(F, ts, close_now):
    """Raw score for buy (d=+1) and sell (d=-1) at times ts (array, seconds = bar close)."""
    ix = {k: last_idx(F[k], ts) for k in F}
    raw = {}
    for d in (1, -1):
        s = np.zeros(len(ts))
        h1, h4, dd, m15 = F["H1"], F["H4"], F["D1"], F["M15"]
        s += d * h1["slope"][ix["H1"]] > 0
        for k in ("M15", "H1", "H4", "D1"):
            s += d * (F[k]["c"][ix[k]] - F[k]["e50"][ix[k]]) > 0
        s += d * h4["slope"][ix["H4"]] > 0
        s += dd["reg"][ix["D1"]] == d
        for k in ("H4", "H1", "M15"):
            r = F[k]["rsi"][ix[k]]
            s -= (r >= 60) if d == -1 else (r <= 40)
        # position in the last 12 closed H1 bars
        hi = np.array([h1["h"][max(0, i - 11):i + 1].max() for i in ix["H1"]])
        lo = np.array([h1["l"][max(0, i - 11):i + 1].min() for i in ix["H1"]])
        pos = np.where(hi > lo, (close_now - lo) / np.where(hi > lo, hi - lo, 1), 0.5)
        s -= (pos >= 2 / 3) if d == -1 else (pos <= 1 / 3)
        raw[d] = s
    return raw, ix


def triggers(X, sec, kind):
    t, o, h, l, c = (X[k].to_numpy() for k in ("time", "open", "high", "low", "close"))
    close_t = t + sec
    if kind == "T1":
        k = np.nonzero((close_t % 3600) == 0)[0]
        return [(int(i), d) for i in k for d in (1, -1)]
    out = []
    rg = h - l
    for i in range(4, len(c)):
        if rg[i] <= 0:
            continue
        lw, uw = min(o[i], c[i]) - l[i], h[i] - max(o[i], c[i])
        if lw >= 0.5 * rg[i] and c[i] > o[i] and l[i] <= l[i - 3:i].min():
            out.append((i, 1))
        if uw >= 0.5 * rg[i] and c[i] < o[i] and h[i] >= h[i - 3:i].max():
            out.append((i, -1))
    return out


def book(X, sec, cands, sl_mult, cost_mult=1.0):
    t, o, h, l, c, sp = (X[k].to_numpy() for k in ("time", "open", "high", "low", "close", "sp"))
    A = atr(h, l, c)
    slip = 0.5 * float(np.median(sp)) * cost_mult
    comm = COMM_OZ * cost_mult
    hold = int(24 * 3600 / sec)
    busy = {1: -1, -1: -1}
    out = []
    for i, d, sc in sorted(cands):
        if i + 1 >= len(t) or i + 1 <= busy[d]:
            continue
        e = i + 1
        entry = o[e] + (sp[e] + slip if d == 1 else -slip)
        risk = sl_mult * A[i]
        if risk <= 0:
            continue
        sl, tp1, tp2 = entry - d * risk, entry + d * 1.5 * risk, entry + d * 2.5 * risk
        stop, got1, parts, end = sl, False, [None, None], None
        for k in range(e, min(len(t), e + hold)):
            adv = l[k] if d == 1 else h[k] + sp[k]
            fav = h[k] if d == 1 else l[k] + sp[k]
            if d * (adv - stop) <= 0:
                px = (min(stop, o[k]) if d == 1 else max(stop, o[k] + sp[k])) if k > e else stop
                r = d * (px - d * slip - entry) / risk
                for j in range(2):
                    if parts[j] is None:
                        parts[j] = r
                end = k
                break
            if not got1 and d * (fav - tp1) >= 0:
                parts[0], got1, stop = 1.5 - slip / risk, True, entry
            if got1 and d * (fav - tp2) >= 0:
                parts[1] = 2.5 - slip / risk
                end = k
                break
        if end is None:
            k = min(len(t), e + hold) - 1
            px = c[k] - (sp[k] if d == -1 else 0)
            r = d * (px - d * slip - entry) / risk
            parts = [p if p is not None else r for p in parts]
            end = k
        nights = int(t[end] // 86400 - t[e] // 86400)
        R = float(np.mean(parts)) - (comm + nights * SWAP_OZ * cost_mult) / risk
        out.append({"t": int(t[i] + sec), "d": d, "R": R, "tp1": got1, "score": sc})
        busy[d] = end
    return out


def keep(ts):
    return (ts >= SEL0) & (ts < END) & ~((ts >= HOLD0) & (ts < HOLD1))


def stats(tr, a, z):
    x = [q for q in tr if a <= q["t"] < z and not (HOLD0 <= q["t"] < HOLD1)]
    if not x:
        return {"n": 0}
    r = np.array([q["R"] for q in sorted(x, key=lambda q: q["t"])])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    return {"n": len(r), "lệnh/tuần": round(len(r) / ((z - a) / 604800), 2), "TP1 trước SL": round(float(np.mean([q["tp1"] for q in x])), 3),
            "R TB": round(float(r.mean()), 4), "tổng R": round(float(r.sum()), 1), "PF": round(float(pos / neg), 2) if neg > 0 else None,
            "DD R": round(dd, 1),
            "mua n / R TB": [sum(q["d"] == 1 for q in x), round(float(np.mean([q["R"] for q in x if q["d"] == 1])), 3) if any(q["d"] == 1 for q in x) else None],
            "bán n / R TB": [sum(q["d"] == -1 for q in x), round(float(np.mean([q["R"] for q in x if q["d"] == -1])), 3) if any(q["d"] == -1 for q in x) else None]}


def ci(tr, rng):
    x = [q for q in tr if SEL0 <= q["t"] < END and not (HOLD0 <= q["t"] < HOLD1)]
    wk = {}
    for q in x:
        wk.setdefault(q["t"] // 604800, []).append(q["R"])
    S = np.array([sum(v) for v in wk.values()]); N = np.array([len(v) for v in wk.values()])
    bs = []
    for _ in range(BOOT):
        i = rng.integers(0, len(S), len(S))
        bs.append(S[i].sum() / N[i].sum())
    return [round(float(np.percentile(bs, 100 * ALPHA / 2)), 4), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 4)]


def main():
    root, res, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    m15, m5, F = build(root, res)
    rng = np.random.default_rng(SEED)
    result = {"dữ liệu": {"M15": [str(pd.Timestamp(m15.time.iloc[0], unit="s")), str(pd.Timestamp(m15.time.iloc[-1], unit="s"))],
                          "M5 đến": str(pd.Timestamp(m5.time.iloc[-1], unit="s"))}}
    for exe, X, sec, slm in (("M15", m15, 900, 1.1), ("M5", m5, 300, 1.8)):
        tX = X["time"].to_numpy() + sec
        for trig in ("T1", "T2"):
            cand = [(i, d) for i, d in triggers(X, sec, trig) if keep(np.array([tX[i]]))[0] and (exe == "M15" or tX[i] >= M5_FROM)]
            idx = np.array([i for i, _ in cand])
            raw, _ = score_arrays(F, tX[idx], X["close"].to_numpy()[idx])
            regD1 = F["D1"]["reg"][last_idx(F["D1"], tX[idx])]
            sc = np.array([(raw[d][k] + 4) / 11 * 100 for k, (i, d) in enumerate(cand)])
            al = np.array([regD1[k] == d for k, (i, d) in enumerate(cand)])
            groups = {"≥70": sc >= 70, "50–69": (sc >= 50) & (sc < 70), "<50": sc < 50, "chỉ D1": al, "không lọc": np.ones(len(cand), bool)}
            books = {g: book(X, sec, [(cand[k][0], cand[k][1], float(sc[k])) for k in np.nonzero(m)[0]], slm) for g, m in groups.items()}
            key = f"{exe} {trig}"
            r = {"ứng viên": len(cand)}
            for g, tr in books.items():
                r[g] = {"kỳ chọn": stats(tr, SEL0, SEL1), "kỳ kiểm": stats(tr, SEL1, END), "cả kỳ": stats(tr, SEL0, END)}
            if exe == "M15":
                top = books["≥70"]
                r["CI R TB ≥70 (α 2,5 %)"] = ci(top, rng)
                harsh = book(X, sec, [(cand[k][0], cand[k][1], float(sc[k])) for k in np.nonzero(groups["≥70"])[0]], slm, cost_mult=1.5)
                r["≥70 chi phí × 1,5"] = stats(harsh, SEL0, END)
                if trig == "T1" and len(idx):
                    # code check: recompute the score of the first candidate by hand from raw frames
                    i0, d0 = cand[0]
                    ts0 = tX[i0]
                    def li(k):
                        return int(np.searchsorted(F[k]["t_close"], ts0, side="right") - 1)
                    s = 0
                    s += d0 * F["H1"]["slope"][li("H1")] > 0
                    s += sum(d0 * (F[k]["c"][li(k)] - F[k]["e50"][li(k)]) > 0 for k in ("M15", "H1", "H4", "D1"))
                    s += d0 * F["H4"]["slope"][li("H4")] > 0
                    s += F["D1"]["reg"][li("D1")] == d0
                    s -= sum(((F[k]["rsi"][li(k)] >= 60) if d0 == -1 else (F[k]["rsi"][li(k)] <= 40)) for k in ("H4", "H1", "M15"))
                    j = li("H1"); hi, lo = F["H1"]["h"][j - 11:j + 1].max(), F["H1"]["l"][j - 11:j + 1].min()
                    p = (X["close"].iat[i0] - lo) / (hi - lo)
                    s -= (p >= 2 / 3) if d0 == -1 else (p <= 1 / 3)
                    result["kiểm code: Score ứng viên đầu"] = {"engine": round(float(sc[0]), 2), "tay": round((s + 4) / 11 * 100, 2)}
            result[key] = r
            print(key, "| n cand", len(cand), flush=True)
            for g in groups:
                print(f"   {g:10s} chọn {r[g]['kỳ chọn']}\n              kiểm {r[g]['kỳ kiểm']}", flush=True)
            if exe == "M15":
                print("   CI≥70", r["CI R TB ≥70 (α 2,5 %)"], "| harsh", r["≥70 chi phí × 1,5"].get("R TB"), flush=True)
    crit = {}
    for trig in ("T1", "T2"):
        r = result[f"M15 {trig}"]
        mono = all(r["<50"][p].get("TP1 trước SL", 0) < r["50–69"][p].get("TP1 trước SL", 0) < r["≥70"][p].get("TP1 trước SL", 0) for p in ("kỳ chọn", "kỳ kiểm"))
        top = r["≥70"]
        c2 = top["kỳ chọn"].get("R TB", -1) > 0 and top["kỳ kiểm"].get("R TB", -1) > 0 and r["CI R TB ≥70 (α 2,5 %)"][0] > 0
        c3 = all(top[p].get("R TB", -9) > r["chỉ D1"][p].get("R TB", 9) for p in ("kỳ chọn", "kỳ kiểm"))
        sides = [top["cả kỳ"]["mua n / R TB"], top["cả kỳ"]["bán n / R TB"]]
        c4 = all(v[0] < 15 or (v[1] is not None and v[1] >= -0.05) for v in sides)
        c5 = r["≥70 chi phí × 1,5"].get("R TB", -1) > 0
        c6 = result[f"M5 {trig}"]["≥70"]["cả kỳ"].get("R TB", -1) > 0
        c7 = top["cả kỳ"].get("lệnh/tuần", 0) >= 1
        crit[trig] = {"1 đơn điệu hai kỳ": mono, "2 ≥70 dương hai kỳ, CI > 0": c2, "3 hơn chỉ D1 hai kỳ": c3, "4 hai chiều ≥ −0,05": c4,
                      "5 chi phí × 1,5 > 0": c5, "6 M5 dương": c6, "7 ≥ 1 lệnh/tuần": c7, "đạt": all([mono, c2, c3, c4, c5, c6, c7])}
    result["tiêu chí"] = crit
    (out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("crit", json.dumps(crit, ensure_ascii=False), "\ncheck", result.get("kiểm code: Score ứng viên đầu"), "\ndone", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
