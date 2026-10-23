"""G154: evolutionary search for a gold M15 scalp (1 trigger + up to 3 filters + 1 exit, symmetric for buys and sells),
a 50-run shifted-outcome null of the whole search, the untouched 2024-06/2026 check and BTC / silver transfer.
Plan: docs/superpowers/plans/2026-10-23-g154-scalp-random-search.md.

Usage: g154_scalp_search.py <data dir> <out.json> [null runs]
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402

SEARCH = (g.ts(2021, 7, 20), g.ts(2024, 1, 1))
VALID = (g.ts(2024, 1, 1), g.ts(2026, 7, 1))
AFTER = (g.ts(2026, 7, 1), 2 ** 40)
EXITS = [(s, tp, hd) for s in (0.5, 1.0, 1.5) for tp in (1.0, 1.5, 2.0, 3.0) for hd in (8, 16, 32)]
POP, GENS, TOUR, PMUT, ELITE, SEED = 300, 40, 4, 0.2, 20, 154
MIN_N, MIN_SIDE = 150, 30
DAY_BARS = 92
TOP = 20
P_CTRL, CTRL_RUNS = 0.0025, 1000


# ------------------------------------------------------------------------------------------------ features
def rmax_prev(x, n):
    out = np.full(len(x), np.nan)
    out[n:] = np.lib.stride_tricks.sliding_window_view(x, n).max(1)[:len(x) - n]
    return out


def rmin_prev(x, n):
    out = np.full(len(x), np.nan)
    out[n:] = np.lib.stride_tricks.sliding_window_view(x, n).min(1)[:len(x) - n]
    return out


def prev(x):
    return np.r_[np.nan, x[:-1]]


def features(D):
    t, o, h, l, c, v, sp = D["t"], D["o"], D["h"], D["l"], D["c"], D["v"], D["sp"]
    n = len(c)
    F = {}
    F["hour"] = (t % 86400) // 3600
    day = t // 86400
    F["dow"] = (day + 3) % 7                                     # Monday = 0
    atr = D["atr"]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    F["atrr"] = atr / g.rma(tr, 100)
    e20, e50, e200 = g.ema(c, 20), g.ema(c, 50), D["E"][200]
    F["e20"], F["e50"], F["e200"] = e20, e50, e200
    F["slope"] = e200 - np.r_[np.full(16, np.nan), e200[:-16]]
    ch = np.diff(c, prepend=c[0])
    gain, loss = g.rma(np.maximum(ch, 0.0), 14), g.rma(np.maximum(-ch, 0.0), 14)
    F["rsi"] = 100 - 100 / (1 + gain / np.maximum(loss, 1e-12))
    W = np.lib.stride_tricks.sliding_window_view(c, 20)
    sma, sd = np.full(n, np.nan), np.full(n, np.nan)
    sma[19:], sd[19:] = W.mean(1), W.std(1)
    F["up"], F["lo"] = sma + 2 * sd, sma - 2 * sd
    bw = 4 * sd
    rank = np.full(n, np.nan)
    Wb = np.lib.stride_tricks.sliding_window_view(np.nan_to_num(bw, nan=np.inf), 120)
    rank[119:] = (Wb <= Wb[:, -1:]).mean(1)
    F["bwrank_prev"] = prev(rank)
    # daily VWAP (server day), previous day high / low, today's Asia range (hours 1..7, valid from 08:00)
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], n]
    vwap = np.empty(n)
    pdh, pdl = np.full(n, np.nan), np.full(n, np.nan)
    ah, al = np.full(n, np.nan), np.full(n, np.nan)
    tp_ = (h + l + c) / 3
    hour = F["hour"]
    for k, (a, z) in enumerate(zip(starts, ends)):
        vv = np.maximum(v[a:z], 1.0)
        vwap[a:z] = np.cumsum(tp_[a:z] * vv) / np.cumsum(vv)
        if k:
            pa, pz = starts[k - 1], ends[k - 1]
            pdh[a:z], pdl[a:z] = h[pa:pz].max(), l[pa:pz].min()
        asia = (hour[a:z] >= 1) & (hour[a:z] <= 7)
        if asia.any():
            after = hour[a:z] >= 8
            ah[a:z][after] = h[a:z][asia].max()
            al[a:z][after] = l[a:z][asia].min()
    F["vwap"], F["pdh"], F["pdl"], F["ah"], F["al"] = vwap, pdh, pdl, ah, al
    F["adx"] = D["adx"]
    F["imp"] = (h - l) / prev(atr)
    F["cost"] = sp / atr
    # XauRegime R1 of the last closed server day
    dc = c[ends - 1]
    e = g.ema(dc, 50)
    st = np.zeros(len(dc), int)
    for k in range(60, len(dc)):
        if dc[k] > e[k] and e[k] > e[k - 10]:
            st[k] = 1
        elif dc[k] < e[k] and e[k] < e[k - 10]:
            st[k] = -1
    q = np.searchsorted(day[starts], day, side="left") - 1
    F["reg"] = np.where(q >= 0, st[np.maximum(q, 0)], 0)
    return F


def triggers(D, F):
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    c1, o1, h1, l1 = prev(c), prev(o), prev(h), prev(l)
    c2, o2, h2, l2 = prev(c1), prev(o1), prev(h1), prev(l1)
    c3 = prev(c2)
    T = {}
    for N in (8, 20):
        hm, lm = rmax_prev(h, N), rmin_prev(l, N)
        T[f"phá {N} nến"] = (c > hm, c < lm)
        T[f"quét {N} nến"] = ((l < lm) & (c > lm), (h > hm) & (c < hm))
    e20, e50 = F["e20"], F["e50"]
    T["hồi EMA20"] = ((e20 > e50) & (l <= e20) & (c > e20), (e20 < e50) & (h >= e20) & (c < e20))
    lo_b, hi_b = np.minimum(o, c), np.maximum(o, c)
    lo_1, hi_1 = np.minimum(o1, c1), np.maximum(o1, c1)
    T["nhấn chìm"] = ((c > o) & (c1 < o1) & (lo_b <= lo_1) & (hi_b >= hi_1), (c < o) & (c1 > o1) & (lo_b <= lo_1) & (hi_b >= hi_1))
    rng, body = h - l, abs(c - o)
    T["pin bar"] = ((rng > 0) & (lo_b - l >= 2 * body) & (lo_b - l >= 0.5 * rng),
                    (rng > 0) & (h - hi_b >= 2 * body) & (h - hi_b >= 0.5 * rng))
    vw = F["vwap"]
    same = np.r_[False, np.diff(D["t"] // 86400) == 0]
    T["cắt VWAP"] = (same & (c1 < prev(vw)) & (c > vw), same & (c1 > prev(vw)) & (c < vw))
    ah, al, hr = F["ah"], F["al"], F["hour"]
    win = (hr >= 8) & (hr <= 16)
    T["phá biên Asia"] = (win & (c > ah) & (c1 <= ah), win & (c < al) & (c1 >= al))
    rsi = F["rsi"]
    T["RSI thoát 30/70"] = ((prev(rsi) < 30) & (rsi >= 30), (prev(rsi) > 70) & (rsi <= 70))
    inside = (h1 <= h2) & (l1 >= l2)
    T["phá inside bar"] = (inside & (c > h1), inside & (c < l1))
    T["3 nến đà"] = ((c > c1) & (c1 > c2) & (c2 > c3) & (c > o) & (c1 > o1) & (c2 > o2),
                     (c < c1) & (c1 < c2) & (c2 < c3) & (c < o) & (c1 < o1) & (c2 < o2))
    pdh, pdl = F["pdh"], F["pdl"]
    T["phá đỉnh/đáy ngày trước"] = ((c > pdh) & (c1 <= pdh), (c < pdl) & (c1 >= pdl))
    up, lo = F["up"], F["lo"]
    sq = F["bwrank_prev"] <= 0.2
    T["squeeze Bollinger"] = (sq & (c > up), sq & (c < lo))
    T["quay lại trong Bollinger"] = ((c1 < prev(lo)) & (c > lo), (c1 > prev(up)) & (c < up))
    return list(T.items())


def filters(D, F):
    c = D["c"]
    hr, atr = F["hour"], D["atr"]
    out = []

    def sym(name, m):
        out.append((name, (m, m)))

    for a, z, lab in ((1, 7, "Asia 1-7"), (8, 13, "London 8-13"), (14, 18, "NY 14-18"), (19, 22, "muộn 19-22")):
        sym(f"giờ {lab}", (hr >= a) & (hr <= z))
    reg = F["reg"]
    out.append(("D1 cùng chiều", (reg == 1, reg == -1)))
    out.append(("D1 ngược chiều", (reg == -1, reg == 1)))
    out.append(("D1 không ngược", (reg != -1, reg != 1)))
    e200 = F["e200"]
    out.append(("EMA200 M15 cùng phía", (c > e200, c < e200)))
    out.append(("EMA200 M15 ngược phía", (c < e200, c > e200)))
    ar = F["atrr"]
    sym("ATR14/ATR100 > 1,2", ar > 1.2)
    sym("ATR14/ATR100 < 0,8", ar < 0.8)
    sym("ATR14/ATR100 0,8-1,2", (ar >= 0.8) & (ar <= 1.2))
    x = (c - F["vwap"]) / atr
    out.append(("xa VWAP cùng chiều > 1 ATR", (x > 1, x < -1)))
    out.append(("xa VWAP ngược chiều > 1 ATR", (x < -1, x > 1)))
    sym("sát VWAP < 0,5 ATR", abs(x) < 0.5)
    adx = F["adx"]
    sym("ADX > 25", adx > 25)
    sym("ADX < 20", adx < 20)
    dow = F["dow"]
    sym("bỏ thứ Sáu", dow != 4)
    sym("bỏ thứ Hai", dow != 0)
    imp = F["imp"]
    sym("nến tín hiệu > 1,5 ATR", imp > 1.5)
    sym("nến tín hiệu < 0,7 ATR", imp < 0.7)
    rsi = F["rsi"]
    out.append(("RSI cùng phía 50", (rsi > 50, rsi < 50)))
    out.append(("RSI ngược phía 50", (rsi < 50, rsi > 50)))
    sl = F["slope"]
    out.append(("dốc EMA200 cùng chiều", (sl > 0, sl < 0)))
    out.append(("dốc EMA200 ngược chiều", (sl < 0, sl > 0)))
    ah, al = F["ah"], F["al"]
    out.append(("ngoài biên Asia cùng chiều", (c > ah, c < al)))
    sym("trong biên Asia", (c >= al) & (c <= ah))
    sym("spread/ATR < 0,03", F["cost"] < 0.03)
    return out


# ------------------------------------------------------------------------------------------------ exits
def outcomes(D, sl_k, tp_r, hold, d):
    """Per signal bar i (entry at the open of i+1): harsh R, R with x1.5 costs, exit bar. As gp.run_trade + g68 harsh."""
    t, o, h, l, c, sp, atr = D["t"], D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"]
    n = len(c)
    e = np.minimum(np.arange(n) + 1, n - 1)
    entry = o[e] + (sp[e] if d == 1 else 0.0)
    dist = sl_k * atr
    sl = entry - d * dist
    tp = entry + d * tp_r * dist
    end = np.minimum(e + hold - 1, n - 1)
    done = np.zeros(n, bool)
    px = np.where(d == 1, c[end], c[end] + sp[end])
    x = end.copy()
    for k in range(hold):
        j = np.minimum(e + k, n - 1)
        act = ~done & (e + k <= end)
        if d == 1:
            hs, ht = l[j] <= sl, h[j] >= tp
            spx = sl if k == 0 else np.minimum(sl, o[j])
            tpx = tp if k == 0 else np.maximum(tp, o[j])
        else:
            hs, ht = h[j] + sp[j] >= sl, l[j] + sp[j] <= tp
            spx = sl if k == 0 else np.maximum(sl, o[j] + sp[j])
            tpx = tp if k == 0 else np.minimum(tp, o[j] + sp[j])
        a1 = act & hs
        a2 = act & ~hs & ht
        px = np.where(a1, spx, np.where(a2, tpx, px))
        x = np.where(a1 | a2, j, x)
        done |= a1 | a2
    with np.errstate(divide="ignore", invalid="ignore"):
        r = d * (px - entry) / dist - D["comm"] / dist
        extra = 2 * 0.5 * D["sp_med"] + D["comm"]
        extra = extra + np.zeros(n)
        for s_, spv in ((t[e], sp[e]), (t[x], sp[x])):
            m = s_ % 86400
            extra = extra + np.where((m >= 23 * 3600 + 1800) | (m < 3600), 2 * spv, 0.0)
        rh = r - extra / dist
    r15 = r - 1.5 * (r - rh)
    ok = np.isfinite(rh) & (atr > 0) & (np.arange(n) < n - 1)
    rh = np.where(ok, rh, np.nan)
    return rh.astype(np.float32), r15.astype(np.float32), x.astype(np.int64)


class Book:
    def __init__(self, D, specs):
        self.D = D
        self.F = features(D)
        self.T = triggers(D, self.F)
        self.FL = filters(D, self.F)
        self.out = {}
        for s in specs:
            self.add(s)

    def add(self, s):
        if s in self.out:
            return
        sl_k, tp_r, hold = EXITS[s]
        self.out[s] = {d: outcomes(self.D, sl_k, tp_r, hold, d) for d in (1, -1)}


# ------------------------------------------------------------------------------------------------ evaluation
def trades(bk, gene, a, z, shift=None):
    """One-at-a-time trades of a gene for signal bars in [a, z): list of (i, d), harsh R, x1.5 R."""
    trig, slots, ex = gene
    ok = {}
    for k, d in ((0, 1), (1, -1)):
        m = bk.T[trig][1][k][a:z].copy()
        for s in slots:
            m &= bk.FL[s - 1][1][k][a:z]
        ok[d] = np.nonzero(m)[0] + a
    idx = np.r_[ok[1], ok[-1]]
    dirs = np.r_[np.ones(len(ok[1]), int), -np.ones(len(ok[-1]), int)]
    order = np.argsort(idx, kind="stable")
    idx, dirs = idx[order], dirs[order]
    O = bk.out[ex] if shift is None else shift[ex]
    taken, free = [], -1
    for i, d in zip(idx.tolist(), dirs.tolist()):
        if i + 1 > free:
            rh = O[d][0][i]
            if rh != rh:                                           # nan: no valid outcome
                continue
            taken.append((i, d))
            free = int(O[d][2][i])
    if not taken:
        return [], np.zeros(0), np.zeros(0)
    ii = np.array([x[0] for x in taken])
    dd = np.array([x[1] for x in taken])
    rh = np.where(dd == 1, O[1][0][ii], O[-1][0][ii]).astype(float)
    r15 = np.where(dd == 1, O[1][1][ii], O[-1][1][ii]).astype(float)
    return taken, rh, r15


def fitness(taken, rh):
    n = len(rh)
    if n < MIN_N:
        return -99.0
    dd = np.array([x[1] for x in taken])
    if (dd == 1).sum() < MIN_SIDE or (dd == -1).sum() < MIN_SIDE:
        return -99.0
    x = np.sort(rh)[:-5]
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(len(x))) if s > 0 else -99.0


def key(gene):
    trig, slots, ex = gene
    return (trig, tuple(sorted(set(s for s in slots if s))), ex)


def search(bk, a, z, rng, shift=None):
    nt, nf, ne = len(bk.T), len(bk.FL), len(EXITS)
    cache = {}

    def rand_gene():
        return (rng.randrange(nt), tuple(0 if rng.random() < 0.4 else rng.randrange(1, nf + 1) for _ in range(3)), rng.randrange(ne))

    def score(gene):
        k = key(gene)
        if k not in cache:
            taken, rh, _ = trades(bk, k, a, z, shift)
            cache[k] = fitness(taken, rh)
        return cache[k]

    pop = [rand_gene() for _ in range(POP)]
    for _ in range(GENS):
        sc = [score(p) for p in pop]
        order = sorted(range(POP), key=lambda i: -sc[i])
        nxt = [pop[i] for i in order[:ELITE]]
        while len(nxt) < POP:
            p1 = max(rng.sample(range(POP), TOUR), key=lambda i: sc[i])
            p2 = max(rng.sample(range(POP), TOUR), key=lambda i: sc[i])
            a1, b1 = pop[p1], pop[p2]
            trig = a1[0] if rng.random() < 0.5 else b1[0]
            slots = tuple(a1[1][j] if rng.random() < 0.5 else b1[1][j] for j in range(3))
            ex = a1[2] if rng.random() < 0.5 else b1[2]
            if rng.random() < PMUT:
                trig = rng.randrange(nt)
            slots = tuple((0 if rng.random() < 0.4 else rng.randrange(1, nf + 1)) if rng.random() < PMUT else s for s in slots)
            if rng.random() < PMUT:
                ex = rng.randrange(ne)
            nxt.append((trig, slots, ex))
        pop = nxt
    for p in pop:
        score(p)
    return cache


def shifted(bk, a, z, k):
    """Outcome arrays with R and holding time rolled by k bars inside [a, z) (signal -> outcome link cut)."""
    out = {}
    for ex, od in bk.out.items():
        out[ex] = {}
        for d, (rh, r15, x) in od.items():
            rh2, r152, x2 = rh.copy(), r15.copy(), x.copy()
            dur = (x[a:z] - np.arange(a, z))
            rh2[a:z] = np.roll(rh[a:z], k)
            r152[a:z] = np.roll(r15[a:z], k)
            x2[a:z] = np.arange(a, z) + np.roll(dur, k)
            out[ex][d] = (rh2, r152, x2)
    return out


# ------------------------------------------------------------------------------------------------ report helpers
def idx_range(D, a, z):
    t = D["t"]
    return int(np.searchsorted(t, a)), int(np.searchsorted(t, z))


def describe(bk, gene):
    trig, slots, ex = gene
    s, tp, hd = EXITS[ex]
    f = [bk.FL[x - 1][0] for x in slots]
    return f"{bk.T[trig][0]}" + (" + " + " + ".join(f) if f else "") + f" | SL {s} ATR, TP {tp}R, tối đa {hd} nến"


def stat(x):
    x = np.asarray(x, float)
    return {"n": int(len(x)), "R/lệnh": round(float(x.mean()), 3) if len(x) else None,
            "tổng R": round(float(x.sum()), 1) if len(x) else 0.0}


def quarters_pos(bk, taken, rh):
    t = bk.D["t"]
    q = {}
    for (i, _), r in zip(taken, rh):
        dt = np.datetime64(int(t[i]), "s").astype("datetime64[M]").astype(int)
        key_ = dt // 3
        q[key_] = q.get(key_, 0.0) + r
    return (sum(v > 0 for v in q.values()) / len(q)) if q else 0.0, len(q)


def control_p(bk, gene, taken, rh, a, z, rng):
    """Random entries: same direction, same server hour of the signal bar, same exit, signal bars in [a, z)."""
    O = bk.out[gene[2]]
    hour = bk.F["hour"]
    pools = {}
    for d in (1, -1):
        ok = np.isfinite(O[d][0][a:z])
        for hh in range(24):
            pools[(d, hh)] = np.nonzero(ok & (hour[a:z] == hh))[0] + a
    groups = {}
    for (i, d) in taken:
        groups[(d, int(hour[i]))] = groups.get((d, int(hour[i])), 0) + 1
    tot = np.zeros(CTRL_RUNS)
    nn = 0
    for (d, hh), cnt in groups.items():
        pool = pools[(d, hh)]
        if len(pool) == 0:
            continue
        pick = pool[rng.integers(0, len(pool), size=(CTRL_RUNS, cnt))]
        tot += O[d][0][pick].astype(float).sum(1)
        nn += cnt
    means = tot / max(nn, 1)
    return float(((means >= rh.mean()).sum() + 1) / (CTRL_RUNS + 1))


def load(root, sym):
    g.set_tf("M15")
    g.DATA = root / "m15v"
    return g.load(sym)


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    nulls = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    t0 = time.time()
    D = load(root, "XAUUSD")
    bk = Book(D, range(len(EXITS)))
    print(f"XAU loaded, {len(D['c'])} bars, {len(bk.T)} triggers, {len(bk.FL)} filter options, {time.time() - t0:.0f}s", flush=True)
    a, z = idx_range(D, *SEARCH)
    va, vz = idx_range(D, *VALID)
    fa, fz = idx_range(D, *AFTER)
    res = {"kỳ tìm (chỉ số nến)": [a, z], "kỳ kiểm": [va, vz]}

    cache = search(bk, a, z, random.Random(SEED))
    ranked = sorted(cache.items(), key=lambda kv: -kv[1])
    best_real = ranked[0][1]
    print(f"real search: {len(cache)} genes, best {best_real:.2f}, {time.time() - t0:.0f}s", flush=True)

    null_best = []
    nd = (z - a) // DAY_BARS
    rs = random.Random(SEED + 1)
    for r in range(nulls):
        k = DAY_BARS * rs.randint(20, nd - 20)
        sh = shifted(bk, a, z, k)
        c2 = search(bk, a, z, random.Random(SEED + 100 + r), sh)
        null_best.append(max(c2.values()))
        print(f"null {r + 1}/{nulls}: shift {k} bars, best {null_best[-1]:.2f}, {time.time() - t0:.0f}s", flush=True)
    p95 = float(np.percentile(null_best, 95)) if null_best else None
    g0 = p95 is not None and best_real > p95
    res["G0"] = {"điểm tốt nhất thật": round(best_real, 2), "null tốt nhất (50 lần)": [round(x, 2) for x in null_best],
                 "phân vị 95% null": round(p95, 2) if p95 is not None else None,
                 "p (null >= thật)": round((sum(x >= best_real for x in null_best) + 1) / (len(null_best) + 1), 3) if null_best else None,
                 "đạt": bool(g0)}

    top = [k for k, v in ranked[:TOP] if v > -99]
    # transfer books
    xfer = {}
    for sym, (ta, tz) in (("BTCUSD", (0, VALID[1])), ("XAGUSD", (0, VALID[1]))):
        Ds = load(root, sym)
        bks = Book(Ds, sorted(set(k[2] for k in top)))
        xfer[sym] = (bks, *idx_range(Ds, ta, tz))
        print(f"{sym} loaded, {len(Ds['c'])} bars", flush=True)
    rng = np.random.default_rng(SEED)
    rows = []
    for k in top:
        tk, rh, r15 = trades(bk, k, a, z)
        tv, rv, r15v = trades(bk, k, va, vz)
        ta_, ra, _ = trades(bk, k, fa, fz)
        dv = np.array([x[1] for x in tv]) if tv else np.zeros(0, int)
        buy, sell = rv[dv == 1], rv[dv == -1]
        qpos, nq = quarters_pos(bk, tv, rv)
        drop5 = float(np.sort(rv)[:-5].mean()) if len(rv) > 5 else None
        p = control_p(bk, k, tv, rv, va, vz, rng) if len(rv) else None
        tr = {}
        for sym, (bks, xa, xz) in xfer.items():
            _, rx, _ = trades(bks, k, xa, xz)
            tr[sym] = stat(rx)
        c1 = len(rv) >= 100 and rv.mean() > 0 and r15v.mean() > 0
        c2 = drop5 is not None and drop5 > 0
        c3 = all(len(x) < 30 or x.mean() >= -0.05 for x in (buy, sell))
        c4 = qpos >= 0.55
        c5 = p is not None and p <= P_CTRL
        cnt = [v for v in tr.values() if v["n"] >= 50]
        c6 = bool(cnt) and any(v["R/lệnh"] > 0 for v in cnt) and all(v["R/lệnh"] >= -0.05 for v in cnt)
        crit = [bool(c1), bool(c2), bool(c3), bool(c4), bool(c5), bool(c6)]
        row = {"tổ hợp": describe(bk, k), "điểm kỳ tìm": round(cache[k], 2), "kỳ tìm": stat(rh), "kỳ kiểm": stat(rv),
               "kiểm ×1,5": stat(r15v), "kiểm bỏ 5 lệnh lớn": round(drop5, 3) if drop5 is not None else None,
               "kiểm mua / bán": [stat(buy), stat(sell)], "kiểm quý dương": f"{qpos:.0%} / {nq} quý", "p đối chứng": p,
               "chuyển thị trường": tr, "kỳ sau (báo cáo)": stat(ra), "tiêu chí 1-6": crit,
               "kết luận": "ĐẠT" if all(crit) and g0 else "KHÔNG ĐẠT"}
        rows.append(row)
        print(row["tổ hợp"], row["kỳ tìm"], row["kỳ kiểm"], p, crit, flush=True)
    res["top 20"] = rows
    res["số tổ hợp đã chấm (thật)"] = len(cache)
    res["kết luận"] = ("ĐẠT: " + ", ".join(r["tổ hợp"] for r in rows if r["kết luận"] == "ĐẠT")) \
        if any(r["kết luận"] == "ĐẠT" for r in rows) else "KHÔNG ĐẠT"
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("done", time.time() - t0, flush=True)


if __name__ == "__main__":
    main()
