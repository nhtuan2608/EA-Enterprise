"""G38: setup discovery pipeline. Six setup families, one set of anti-overfitting checks. MT5 data only.

  python discovery.py            # scan every family, then check the best of each
  python discovery.py T1 T3      # only these families

Data: research/long/data, five symbols 2010-2025 (XAUUSD, BTCUSD from 2018) on H1 / H4 / D1, and eight more
pairs 2024-02 .. 2026-10 (out-of-sample by symbol). Entries at the signal bar's close (ask for a long),
exits bar by bar with pyramid.walk (stop touch first, gap fills at the open, commission per leg).
One open trade per symbol and family at a time.

Families (docs/superpowers/plans/2026-10-06-g38-setup-discovery.md):
  T1  D1 Donchian breakout, ATR stop, ATR trailing, no target
  T2  H4 Donchian breakout, optional D1 EMA200 side, ATR stop, ATR trailing
  T3  H1 pullback in the D1 trend: RSI(2) extreme against the trend, ATR stop, fixed R, time stop
  T4  H1 range fade: low ADX, close outside a Bollinger band, ATR stop, fixed R, time stop
  T5  H1 London breakout of the 00-07 UTC range, stop at the far side or the middle, fixed R, out by 21 UTC
  T6  D1 momentum turn: sign of the N-day change flips, ATR stop, ATR trailing
Checks for the best set of each family (chosen on 2010-2016 only):
  periods   positive in 2017-2020 and 2021-2025
  random    beats random entries with the same stop and exit (p, 500 runs)
  neighbours share of the family's sets one step away that are positive in all three periods
  symbols   the same set on the eight new pairs (2024-2026)
  costs     commission x2 and 0.1R slippage per trade
  loo       worst mean R when one symbol is left out
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import context  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402

SYMBOLS = ls.SYMBOLS
NEW = ["AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP"]
VALIDATE, TEST = ls.VALIDATE, ls.TEST
RANDOM_RUNS = 500
_BARS: dict = {}


# ---------------------------------------------------------------------------
# Bars and indicators
# ---------------------------------------------------------------------------
def load(symbol: str, tf: str) -> dict | None:
    key = (symbol, tf)
    if key in _BARS:
        return _BARS[key]
    path = context.DATA / f"bars_{symbol}_{tf}.csv"
    if not path.exists():
        _BARS[key] = None
        return None
    m = context.meta()
    now_offset, now_utc = int(m["server_offset_now"]), int(m["exported_at_utc"])
    bars = context.load_bars(symbol, tf)
    o = np.array([b["open"] for b in bars]); h = np.array([b["high"] for b in bars])
    lo = np.array([b["low"] for b in bars]); c = np.array([b["close"] for b in bars])
    t = np.array([b["time"] for b in bars])
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h, pc) - np.minimum(lo, pc)
    atr = np.convolve(tr, np.ones(14) / 14, mode="full")[:len(tr)]
    atr[:14] = 0.0
    utc = np.array([b["time"] - context.server_offset_at(b["time"] - now_offset, now_offset, now_utc) for b in bars])
    for b, a, u in zip(bars, atr, utc):
        b["atr"] = float(a)
        b["utc"] = int(u)
    point = float(m["by_symbol"][symbol]["point"])
    B = {"symbol": symbol, "tf": tf, "bars": bars, "o": o, "h": h, "l": lo, "c": c, "t": t, "atr": atr, "utc": utc,
         "point": point, "ctx": {"entry": bars, "point": point, "symbol": symbol}}
    _BARS[key] = B
    return B


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.empty_like(x)
    k = 2.0 / (n + 1)
    e = x[0]
    for i, v in enumerate(x):
        e = v if i == 0 else e + k * (v - e)
        out[i] = e
    return out


def rsi(c: np.ndarray, n: int) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    up, dn = np.maximum(d, 0), np.maximum(-d, 0)
    a = 1.0 / n
    ru = np.empty_like(c); rd = np.empty_like(c)
    u = v = 0.0
    for i in range(len(c)):
        u = u + a * (up[i] - u); v = v + a * (dn[i] - v)
        ru[i], rd[i] = u, v
    return np.where(rd > 0, 100 - 100 / (1 + ru / np.maximum(rd, 1e-12)), 50.0)


def adx(B: dict, n: int = 14) -> np.ndarray:
    if "adx" in B:
        return B["adx"]
    h, lo, c = B["h"], B["l"], B["c"]
    out = np.zeros(len(c))
    tr_s = p_s = m_s = 0.0
    dx_s = None
    for i in range(1, len(c)):
        up, dn = h[i] - h[i - 1], lo[i - 1] - lo[i]
        pdm = up if up > dn and up > 0 else 0.0
        mdm = dn if dn > up and dn > 0 else 0.0
        tr = max(h[i], c[i - 1]) - min(lo[i], c[i - 1])
        tr_s, p_s, m_s = tr_s - tr_s / n + tr, p_s - p_s / n + pdm, m_s - m_s / n + mdm
        if i < n or tr_s <= 0:
            continue
        pdi, mdi = 100 * p_s / tr_s, 100 * m_s / tr_s
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi > 0 else 0.0
        dx_s = dx if dx_s is None else dx_s + (dx - dx_s) / n
        out[i] = dx_s
    B["adx"] = out
    return out


def d1_side(B: dict, n: int = 200) -> np.ndarray:
    """+1 / -1: previous closed day's close above / below the EMA(n) of daily closes (server days)."""
    key = f"d1_{n}"
    if key in B:
        return B[key]
    day = B["t"] // 86400
    days, closes = [], []
    for d, c in zip(day, B["c"]):
        if days and days[-1] == d:
            closes[-1] = c
        else:
            days.append(d); closes.append(c)
    e = ema(np.array(closes), n)
    side = {}
    for k in range(1, len(days)):
        side[days[k]] = 0 if k - 1 < n else (1 if closes[k - 1] > e[k - 1] else -1)
    out = np.array([side.get(d, 0) for d in day])
    B[key] = out
    return out


def roll_max(x: np.ndarray, n: int) -> np.ndarray:
    """max of the n values before each index (exclusive), nan for the first n."""
    out = np.full(len(x), np.nan)
    from numpy.lib.stride_tricks import sliding_window_view
    if len(x) > n:
        w = sliding_window_view(x, n)[:-1]
        out[n:] = w.max(axis=1)
    return out


def roll_min(x: np.ndarray, n: int) -> np.ndarray:
    return -roll_max(-x, n)


# ---------------------------------------------------------------------------
# Families: tf, grid, signals(B, p) -> [(i, direction, stop distance in ATR)], exit rule(p)
# ---------------------------------------------------------------------------
def sig_t1(B, p):
    hi, lo = roll_max(B["h"], p["n"]), roll_min(B["l"], p["n"])
    c = B["c"]
    out = []
    for i in range(p["n"], len(c)):
        if B["atr"][i] <= 0:
            continue
        if c[i] > hi[i]:
            out.append((i, 1, p["stop"]))
        elif c[i] < lo[i]:
            out.append((i, -1, p["stop"]))
    return out


def sig_t2(B, p):
    side = d1_side(B) if p["d1"] else None
    out = []
    for i, d, s in sig_t1(B, p):
        if side is not None and side[i] != d:
            continue
        out.append((i, d, s))
    return out


def sig_t3(B, p):
    side, r2 = d1_side(B), B.setdefault("rsi2", rsi(B["c"], 2))
    out = []
    for i in range(300, len(r2)):
        if B["atr"][i] <= 0 or side[i] == 0:
            continue
        if side[i] == 1 and r2[i] < p["th"]:
            out.append((i, 1, p["stop"]))
        elif side[i] == -1 and r2[i] > 100 - p["th"]:
            out.append((i, -1, p["stop"]))
    return out


def sig_t4(B, p):
    a = adx(B)
    c = B["c"]
    key = "bb20"
    if key not in B:
        from numpy.lib.stride_tricks import sliding_window_view
        w = sliding_window_view(c, 20)
        mid = np.full(len(c), np.nan); sd = np.full(len(c), np.nan)
        mid[19:] = w.mean(axis=1); sd[19:] = w.std(axis=1)
        B[key] = (mid, sd)
    mid, sd = B[key]
    out = []
    for i in range(60, len(c)):
        if B["atr"][i] <= 0 or a[i] >= p["adx"] or np.isnan(sd[i]):
            continue
        if c[i] > mid[i] + p["k"] * sd[i]:
            out.append((i, -1, p["stop"]))
        elif c[i] < mid[i] - p["k"] * sd[i]:
            out.append((i, 1, p["stop"]))
    return out


def sig_t5(B, p):
    """London breakout of the 00-07 UTC range: first close beyond it between 07 and 12 UTC."""
    hours = (B["utc"] // 3600) % 24
    days = B["utc"] // 86400
    out = []
    i, n = 0, len(B["c"])
    while i < n:
        d0 = days[i]
        j = i
        while j < n and days[j] == d0:
            j += 1
        idx = [k for k in range(i, j) if hours[k] < 7]
        if len(idx) >= 5:
            rh, rl = B["h"][idx].max(), B["l"][idx].min()
            atr = B["atr"][idx[-1]]
            width_ok = atr > 0 and (rh - rl) <= p["width"] * atr * 7 ** 0.5
            if width_ok:
                for k in range(i, j):
                    if 7 <= hours[k] < 12 and B["atr"][k] > 0:
                        c = B["c"][k]
                        if c > rh or c < rl:
                            d = 1 if c > rh else -1
                            anchor = (rl if d == 1 else rh) if p["sl"] == "far" else (rh + rl) / 2
                            stop_atr = abs(c - anchor) / B["atr"][k] + 0.1
                            out.append((k, d, stop_atr))
                            break
        i = j
    return out


def sig_t6(B, p):
    c = B["c"]
    n = p["n"]
    out = []
    prev = 0
    for i in range(n, len(c)):
        s = 1 if c[i] > c[i - n] else -1
        if prev and s != prev and B["atr"][i] > 0:
            out.append((i, s, p["stop"]))
        prev = s
    return out


def trend_rule(p):
    return {"target": None, "be": None, "partial": None, "trail": ("ATR", 0.0, p["trail"]),
            "timeout": p.get("timeout", 60), "struct_exit": False}


def fixed_rule(p):
    return {"target": p["r"], "be": None, "partial": None, "trail": None, "timeout": p["timeout"], "struct_exit": False}


def grid(d: dict) -> list[dict]:
    return [dict(zip(d, v)) for v in itertools.product(*d.values())]


FAMILIES = {
    "T1": ("D1", grid({"n": [20, 40, 55, 80], "stop": [2.0, 3.0], "trail": [2.0, 3.0, 4.0], "timeout": [120]}), sig_t1, trend_rule),
    "T2": ("H4", grid({"n": [20, 40, 60], "stop": [2.0, 3.0], "trail": [3.0, 4.0], "d1": [False, True], "timeout": [180]}), sig_t2, trend_rule),
    "T3": ("H1", grid({"th": [5, 10, 15], "stop": [1.0, 1.5, 2.0], "r": [1.0, 1.5, 2.0], "timeout": [24]}), sig_t3, fixed_rule),
    "T4": ("H1", grid({"adx": [20, 25], "k": [2.0, 2.5], "stop": [1.0, 1.5], "r": [1.0, 1.5], "timeout": [24]}), sig_t4, fixed_rule),
    "T5": ("H1", grid({"width": [1.5, 2.5, 99.0], "sl": ["far", "mid"], "r": [1.5, 2.0, 3.0], "timeout": [14]}), sig_t5, fixed_rule),
    "T6": ("D1", grid({"n": [20, 60, 120], "stop": [3.0, 4.0], "trail": [3.0, 4.0], "timeout": [120]}), sig_t6, trend_rule),
}


# ---------------------------------------------------------------------------
# Trades and statistics
# ---------------------------------------------------------------------------
def trades(family: str, p: dict, symbol: str, start_utc: int = 0) -> list[dict]:
    tf, _, sig, rule_fn = FAMILIES[family]
    B = load(symbol, tf)
    if B is None:
        return []
    rule = rule_fn(p)
    bars, c = B["bars"], B["ctx"]
    out, busy_until = [], -1
    for i, d, stop_atr in sig(B, p):
        if i <= busy_until or B["utc"][i] < start_utc or i >= len(bars) - 2:
            continue
        b = bars[i]
        entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
        risk = stop_atr * B["atr"][i]
        if risk <= 0:
            continue
        t = {"symbol": symbol, "i": i, "dir": d, "entry": entry, "stop": entry - d * risk,
             "target": entry + d * 3 * risk, "zl": 0.0, "zh": 0.0}
        res = pyramid.run(c, t, rule)
        busy_until = res["exit_i"]
        out.append({"symbol": symbol, "utc": int(B["utc"][i]), "i": i, "dir": d, "r": res["r"], "stop_atr": stop_atr,
                    "exit_i": res["exit_i"], "dist": risk, "price": entry})
    return out


def period(u: int) -> str:
    return "train" if u < VALIDATE else "validate" if u < TEST else "test"


def stats(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "exp": 0.0, "pf": 0.0, "dd": 0.0}
    r = np.array([x["r"] for x in sorted(rows, key=lambda x: x["utc"])])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])))
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {"n": int(len(r)), "exp": float(r.mean()), "pf": float(gains / losses) if losses > 0 else 99.0, "dd": dd}


def scan_job(job) -> dict:
    family, p = job
    pyramid.GAP_FILL = True
    rows = [t for s in SYMBOLS for t in trades(family, p, s)]
    per = {k: stats([x for x in rows if period(x["utc"]) == k]) for k in ("train", "validate", "test")}
    return {"family": family, "p": p, **per}


# ---------------------------------------------------------------------------
# Checks on the chosen set
# ---------------------------------------------------------------------------
def random_job(job) -> list[float]:
    family, p, rows, seed, runs = job
    pyramid.GAP_FILL = True
    tf, _, _, rule_fn = FAMILIES[family]
    rule = rule_fn(p)
    rng = np.random.default_rng(seed)
    pools = {}
    for s in SYMBOLS:
        B = load(s, tf)
        if B is None:
            continue
        years = (B["utc"] // (365.25 * 86400)).astype(int)
        ok = np.where((B["atr"] > 0) & (np.arange(len(years)) > 300) & (np.arange(len(years)) < len(years) - 2))[0]
        pools[s] = {y: ok[years[ok] == y] for y in np.unique(years[ok])}
    out = []
    for _ in range(runs):
        tot = 0.0
        for x in rows:
            B = load(x["symbol"], tf)
            y = int(x["utc"] // (365.25 * 86400))
            pool = pools[x["symbol"]].get(y)
            if pool is None or len(pool) == 0:
                continue
            j = int(pool[rng.integers(len(pool))])
            d = 1 if rng.random() < 0.5 else -1
            b = B["bars"][j]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = x["stop_atr"] * B["atr"][j]
            t = {"symbol": x["symbol"], "i": j, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * 3 * risk, "zl": 0.0, "zh": 0.0}
            tot += pyramid.run(B["ctx"], t, rule)["r"]
        out.append(tot / len(rows))
    return out


def neighbours(family: str, p: dict, results: list[dict]) -> tuple[int, int]:
    _, g, _, _ = FAMILIES[family]
    keys = list(g[0].keys())
    values = {k: sorted({x[k] for x in g}, key=lambda v: (str(type(v)), v)) for k in keys}
    near = []
    for r in results:
        if r["family"] != family or r["p"] == p:
            continue
        diff = [k for k in keys if r["p"][k] != p[k]]
        if len(diff) == 1:
            k = diff[0]
            if abs(values[k].index(r["p"][k]) - values[k].index(p[k])) == 1:
                near.append(r)
    good = sum(1 for r in near if min(r[k]["exp"] for k in ("train", "validate", "test")) > 0)
    return good, len(near)


def check(family: str, p: dict, results: list[dict], pool: Pool) -> dict:
    pyramid.GAP_FILL = True
    rows = [t for s in SYMBOLS for t in trades(family, p, s)]
    real = statistics.fmean(x["r"] for x in rows)
    sims = [v for ch in pool.map(random_job, [(family, p, rows, 50 + k, RANDOM_RUNS // 10) for k in range(10)]) for v in ch]
    p_rand = float(np.mean(np.array(sims) >= real))
    good, near = neighbours(family, p, results)
    start = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())
    xs = [t for s in NEW for t in trades(family, p, s, start)]
    fee = [x["r"] - replay.COMMISSION.get(x["symbol"], 0.0) / max(x["dist"], 1e-12) - 0.1 for x in rows]
    loo = {s: statistics.fmean([x["r"] for x in rows if x["symbol"] != s]) for s in SYMBOLS}
    by_symbol = {s: stats([x for x in rows if x["symbol"] == s]) for s in SYMBOLS}
    return {"family": family, "p": p, "n": len(rows), "mean": real, "p_random": p_rand,
            "random_mean": float(np.mean(sims)), "random_p95": float(np.quantile(sims, 0.95)),
            "neighbours_good": good, "neighbours": near, "xsym": stats(xs), "costs_mean": statistics.fmean(fee),
            "loo_worst": min(loo.values()), "loo_worst_symbol": min(loo, key=loo.get), "by_symbol": by_symbol}


def verdict(c: dict, r: dict, n_families: int) -> tuple[bool, list[str]]:
    why = []
    if not (r["validate"]["exp"] > 0 and r["test"]["exp"] > 0):
        why.append("âm ở giai đoạn kiểm chứng")
    if c["p_random"] >= 0.05 / max(1, n_families) * 3:      # lenient Bonferroni across families
        why.append(f"không thắng ngẫu nhiên (p={c['p_random']:.3f})")
    if c["neighbours"] and c["neighbours_good"] / c["neighbours"] < 0.6:
        why.append(f"láng giềng yếu ({c['neighbours_good']}/{c['neighbours']})")
    if c["xsym"]["n"] >= 20 and c["xsym"]["exp"] < -0.1:
        why.append(f"âm trên cặp mới ({c['xsym']['exp']:+.2f})")
    if c["costs_mean"] <= 0:
        why.append("không chịu được phí ×2 + trượt 0,1R")
    if c["loo_worst"] <= 0:
        why.append(f"phụ thuộc {c['loo_worst_symbol']}")
    return not why, why


def fmt(s: dict) -> str:
    return f"{s['exp']:+.3f} (n={s['n']}, PF {s['pf']:.2f})" if s["n"] else "n=0"


def main(argv: list[str]) -> None:
    fams = [a for a in argv if a in FAMILIES] or list(FAMILIES)
    jobs = [(f, p) for f in fams for p in FAMILIES[f][1]]
    with Pool(12) as pool:
        results = pool.map(scan_job, jobs)
        lines = ["# G38: tìm setup mới — quét và kiểm chứng (chỉ dữ liệu MT5)", "",
                 f"{len(jobs)} bộ tham số trong {len(fams)} họ; chọn trên 2010–2016 (≥ 40 lệnh), kiểm chứng 2017–2020, 2021–2025.", ""]
        summary = {}
        for f in fams:
            rows = [r for r in results if r["family"] == f and r["train"]["n"] >= 40]
            pos3 = [r for r in rows if min(r[k]["exp"] for k in ("train", "validate", "test")) > 0]
            lines += [f"## {f} ({FAMILIES[f][0]})", "",
                      f"Bộ dương cả 3 giai đoạn: {len(pos3)}/{len(rows)}", "",
                      "| Tham số | Train | Validate | Test |", "|---|---|---|---|"]
            for r in sorted(rows, key=lambda r: -r["train"]["exp"])[:5]:
                lines.append(f"| {r['p']} | {fmt(r['train'])} | {fmt(r['validate'])} | {fmt(r['test'])} |")
            if not rows:
                lines.append("")
                continue
            best = max(rows, key=lambda r: r["train"]["exp"])
            c = check(f, best["p"], results, pool)
            ok, why = verdict(c, best, len(fams))
            summary[f] = {"best": best, "check": c, "pass": ok, "why": why}
            lines += ["", f"Bộ chọn (train cao nhất): `{best['p']}`",
                      f"- So với ngẫu nhiên: R thật {c['mean']:+.3f}, ngẫu nhiên TB {c['random_mean']:+.3f} / p95 {c['random_p95']:+.3f}, p = {c['p_random']:.3f}",
                      f"- Láng giềng dương cả 3 giai đoạn: {c['neighbours_good']}/{c['neighbours']}",
                      f"- 8 cặp mới 2024–2026: {fmt(c['xsym'])}",
                      f"- Phí ×2 + trượt 0,1R: {c['costs_mean']:+.3f}R; bỏ một symbol tệ nhất ({c['loo_worst_symbol']}): {c['loo_worst']:+.3f}R",
                      "- Theo symbol: " + ", ".join(f"{s} {fmt(v)}" for s, v in c["by_symbol"].items()),
                      f"- **Kết luận: {'ĐẠT' if ok else 'KHÔNG ĐẠT'}**" + ("" if ok else " — " + "; ".join(why)), ""]
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    tag = "_".join(fams)
    (ls.OUT / f"discovery_{tag}.md").write_text(text, encoding="utf-8")
    (ls.OUT / f"discovery_{tag}.json").write_text(json.dumps({"results": results, "summary": summary}, default=str), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
