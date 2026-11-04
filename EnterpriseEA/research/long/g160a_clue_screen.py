"""G160a: clue screen - sideways gates K1-K5 (market and account measures) first, then 15 untested clues (oscillators, Elliott /
harmonic on an H4 ZigZag, Ichimoku, Heikin Ashi, SAR, daily pivots). Plan: docs/superpowers/plans/2026-11-04-g160a-clue-screen.md.

Usage: g160a_clue_screen.py <data dir> <raw D1 csv> <out dir>
"""
import json
import random
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g158_hedge_recovery as g8  # noqa: E402
import g159a_modules as m9  # noqa: E402

START, SPLIT, END = g8.START, g8.SPLIT, g8.END
PER = [("05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–10/2026", g.ts(2024, 1, 1), END)]
BOOT, SEED, HORIZON, GAP = 2000, 160, 4, 4
WEEK = 7 * 86400


# ---------------------------------------------------------------------------------------------------------------- helpers
def sma(x, n):
    out = np.full(len(x), np.nan)
    cs = np.cumsum(np.r_[0.0, x])
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def roll_max(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = x[i - n + 1:i + 1].max()
    return out


def roll_min(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = x[i - n + 1:i + 1].min()
    return out


def days_of(t, h, l, c):
    day = t // 86400
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], len(t)]
    dh = np.array([h[a:z].max() for a, z in zip(starts, ends)])
    dl = np.array([l[a:z].min() for a, z in zip(starts, ends)])
    return {"t": day[starts] * 86400, "h": dh, "l": dl, "c": c[ends - 1], "starts": starts, "ends": ends,
            "idx": np.searchsorted(starts, np.arange(len(t)), side="right") - 1}


def compare(tc, yc, t0, y0, alpha, rng, boot=BOOT):
    """P(y) of clue rows vs control rows: pooled, per period, week-block bootstrap CI of the difference."""
    tc, yc, t0, y0 = map(np.asarray, (tc, yc, t0, y0))
    res = {"theo kỳ": {}}
    signs = []
    for pn, a, z in PER:
        m1, m0 = (tc >= a) & (tc < z), (t0 >= a) & (t0 < z)
        n1, n0 = int(m1.sum()), int(m0.sum())
        d = float(yc[m1].mean() - y0[m0].mean()) if n1 and n0 else None
        res["theo kỳ"][pn] = {"n": n1, "chênh": round(d, 3) if d is not None else None}
        if d is not None and n1 >= 30:
            signs.append(np.sign(d))
    m1, m0 = (tc >= START) & (tc < END), (t0 >= START) & (t0 < END)
    n1, n0 = int(m1.sum()), int(m0.sum())
    if not n1 or not n0:
        res.update({"n": n1, "chênh": None, "CI": None})
        return res, signs
    p1, p0 = float(yc[m1].mean()), float(y0[m0].mean())
    weeks = {}
    for tt, yy, k in ((tc[m1], yc[m1], 0), (t0[m0], y0[m0], 2)):
        for a, b in zip(tt // WEEK, yy):
            w = weeks.setdefault(int(a), [0.0, 0.0, 0.0, 0.0])
            w[k] += b
            w[k + 1] += 1
    W = np.array(list(weeks.values()))
    bs = []
    for _ in range(boot):
        S = W[rng.integers(0, len(W), len(W))].sum(0)
        if S[1] > 0 and S[3] > 0:
            bs.append(S[0] / S[1] - S[2] / S[3])
    ci = [round(float(np.percentile(bs, 100 * alpha / 2)), 4), round(float(np.percentile(bs, 100 * (1 - alpha / 2))), 4)]
    res.update({"n": n1, "n đối chứng": n0, "P": round(p1, 3), "P đối chứng": round(p0, 3), "chênh": round(p1 - p0, 4), "CI": ci})
    return res, signs


# ---------------------------------------------------------------------------------------------------------------- part A: gates
def adx(h, l, c, n=14):
    ph, pl, pc = np.r_[h[0], h[:-1]], np.r_[l[0], l[:-1]], np.r_[c[0], c[:-1]]
    up, dn = h - ph, pl - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = g.rma(tr, n)
    pdi, mdi = 100 * g.rma(pdm, n) / atr, 100 * g.rma(mdm, n) / atr
    dx = 100 * abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9)
    return g.rma(dx, n)


def hurst(x):
    rs = []
    for n in (10, 20, 25, 50):
        ch = x.reshape(-1, n)
        dev = np.cumsum(ch - ch.mean(1, keepdims=True), 1)
        R, S = dev.max(1) - dev.min(1), ch.std(1)
        ok = S > 0
        if not ok.any():
            return np.nan
        rs.append((R[ok] / S[ok]).mean())
    return float(np.polyfit(np.log([10, 20, 25, 50]), np.log(rs), 1)[0])


def gates_h4(H):
    """K1, K3, K5 on H4 bars (1 = sideways, 0 = not, nan = warm-up)."""
    h, l, c = H["h"], H["l"], H["c"]
    n = len(c)
    a = adx(h, l, c)
    mid = sma(c, 20)
    sd = np.array([c[max(0, i - 19):i + 1].std() if i >= 19 else np.nan for i in range(n)])
    bbw = 4 * sd / mid
    k1 = np.full(n, np.nan)
    for i in range(520, n):
        rank = float(np.mean(bbw[i - 500:i] < bbw[i]))
        k1[i] = float(a[i] < 20 and rank < 0.30)
    e50 = g.ema(c, 50)
    side = np.sign(c - e50)
    cross = np.r_[0, (side[1:] != side[:-1]) & (side[1:] != 0)].astype(float)
    k3 = np.full(n, np.nan)
    cs = np.cumsum(cross)
    for i in range(110, n):
        k3[i] = float(cs[i] - cs[i - 60] >= 4)
    lr = np.r_[0.0, np.diff(np.log(c))]
    k5 = np.full(n, np.nan)
    for i in range(101, n):
        hv = hurst(lr[i - 99:i + 1])
        k5[i] = float(hv < 0.45) if np.isfinite(hv) else np.nan
    return {"K1": k1, "K3": k3, "K5": k5}


def gates_d1(dh, dl, dc):
    n = len(dc)
    adr = sma(dh - dl, 20)
    k2, k4 = np.full(n, np.nan), np.full(n, np.nan)
    for k in range(21, n):
        path = np.abs(np.diff(dc[k - 20:k + 1])).sum()
        if path > 0:
            k2[k] = float(abs(dc[k] - dc[k - 20]) / path < 0.3)
        k4[k] = float(dh[k - 9:k + 1].max() - dl[k - 9:k + 1].min() < 1.5 * adr[k])
    return {"K2": k2, "K4": k4}, adr


def one_way(dc, adr, k=10, m=2.0):
    n = len(dc)
    y = np.full(n, np.nan)
    y[:n - k] = (np.abs(dc[k:] - dc[:-k]) >= m * adr[:n - k]).astype(float)
    return y


def part_a_market(name, K, y, td, rng, alpha):
    ok = np.isfinite(K) & np.isfinite(y) & (td >= START) & (td < END)
    Kv, yv, tv = K[ok], y[ok], td[ok]
    frac = float(Kv.mean())
    r, signs = compare(tv[Kv == 1], yv[Kv == 1], tv[Kv == 0], yv[Kv == 0], alpha, rng)
    nulls = []
    for _ in range(500):
        lag = int(rng.integers(60, len(Kv) - 60))
        Ks = np.roll(Kv, lag)
        nulls.append(yv[Ks == 1].mean() - yv[Ks == 0].mean())
    beat = float(np.mean(np.array(nulls) > r["chênh"])) if r["chênh"] is not None else 0.0
    neg = sum(1 for s in signs if s < 0)
    r.update({"tỷ lệ ngày bật": round(frac, 3), "null dịch: tỷ lệ chênh dịch > chênh thật": round(beat, 3),
              "số kỳ âm": f"{neg}/{len(signs)}"})
    r["đạt (A-i)"] = bool(r["CI"] is not None and r["CI"][1] < 0 and beat >= 0.95 and neg >= 2 and 0.15 <= frac <= 0.85)
    return r


# ---------------------------------------------------------------------------------------------------------------- part B: clues
def first_passage(h, l, c, A):
    n = len(c)
    up, dn = c + A, c - A
    r = np.zeros(n, int)
    done = np.zeros(n, bool)
    for k in range(1, HORIZON + 1):
        j = np.minimum(np.arange(n) + k, n - 1)
        valid = (np.arange(n) + k) <= n - 1
        hu, hd = (h[j] >= up) & valid, (l[j] <= dn) & valid
        both = ~done & hu & hd
        r[both] = 2
        fu, fd = ~done & hu & ~hd, ~done & hd & ~hu
        r[fu], r[fd] = 1, -1
        done |= both | fu | fd
    r[np.arange(n) >= n - HORIZON] = 0
    return r


def dedupe(ev):
    out, last = [], -10 ** 9
    for i, d in sorted(ev):
        if d != 0 and i - last >= GAP:
            out.append((int(i), int(d)))
            last = i
    return out


def zigzag(h, l, A, k):
    """Pivots (extreme index, price, +1 high / -1 low, confirm index); a pivot is known only at its confirm index."""
    piv = []
    d, ei, ep = 0, 0, None
    hi_i, lo_i = 0, 0
    for i in range(1, len(h)):
        if not np.isfinite(A[i]):
            continue
        if d == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if l[i] < l[lo_i]:
                lo_i = i
            if h[hi_i] - l[i] >= k * A[i] and hi_i < i:
                piv.append((hi_i, h[hi_i], 1, i)); d, ei, ep = -1, i, l[i]
            elif h[i] - l[lo_i] >= k * A[i] and lo_i < i:
                piv.append((lo_i, l[lo_i], -1, i)); d, ei, ep = 1, i, h[i]
            continue
        if d == 1:
            if h[i] > ep:
                ei, ep = i, h[i]
            elif ep - l[i] >= k * A[i]:
                piv.append((ei, ep, 1, i)); d, ei, ep = -1, i, l[i]
        else:
            if l[i] < ep:
                ei, ep = i, l[i]
            elif h[i] - ep >= k * A[i]:
                piv.append((ei, ep, -1, i)); d, ei, ep = 1, i, h[i]
    return piv


def elliott(piv):
    i1, i2 = [], []
    for m in range(4, len(piv)):
        P = piv[m - 4:m + 1]
        s = -P[4][2]                                   # +1 up impulse when P4 is a low
        if P[0][2] != -s:
            continue
        p = [x[1] * s for x in P]                      # mirrored prices: impulse always "up"
        if p[2] > p[0] and (p[3] - p[2]) >= (p[1] - p[0]) and p[4] > p[1] and p[1] > p[0] and p[3] > p[1]:
            i1.append((P[4][3], s))
    for m in range(8, len(piv)):
        P = piv[m - 8:m + 1]
        s = -P[8][2]
        if P[0][2] != -s:
            continue
        p = [x[1] * s for x in P]
        imp = p[2] > p[0] and (p[3] - p[2]) >= (p[1] - p[0]) and p[4] > p[1] and p[1] > p[0] and p[3] > p[1] and p[5] > p[3]
        A_, B_, C_ = p[5] - p[6], p[7], p[7] - p[8]
        if imp and A_ > 0 and B_ <= p[5] and A_ <= C_ <= 1.618 * A_:
            i2.append((P[8][3], s))
    return i1, i2


HARM = (("Gartley", (0.618, 0.618), 0.786), ("Bat", (0.382, 0.5), 0.886), ("Butterfly", (0.786, 0.786), 1.27),
        ("Crab", (0.382, 0.618), 1.618))


def harmonic(piv):
    """(confirm H4 index of C, D level, d): X-A-B-C pivots with the AB / BC ratios of a pattern; d = trade side at D."""
    out = []
    for m in range(3, len(piv)):
        X, A_, B_, C_ = piv[m - 3:m + 1]
        if X[2] != -1 and X[2] != 1:
            continue
        s = -X[2]                                      # bullish when X is a low (A high, B low, C high), buy at D
        x, a, b, cc = (v[1] * s for v in (X, A_, B_, C_))
        xa = a - x
        if xa <= 0 or a - b <= 0:
            continue
        ab, bc = (a - b) / xa, (cc - b) / (a - b)
        if not (0.382 * 0.95 <= bc <= 0.886 * 1.05):
            continue
        for _, (lo, hi), dr in HARM:
            if lo * 0.95 <= ab <= hi * 1.05:
                out.append((C_[3], (a - dr * xa) * s, s))
    return out


def sar(h, l, af0=0.02, afmax=0.2):
    n = len(h)
    trend = np.zeros(n, int)
    up, ps, ep, af = True, l[0], h[0], af0
    for i in range(1, n):
        ps = ps + af * (ep - ps)
        if up:
            ps = min(ps, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < ps:
                up, ps, ep, af = False, ep, l[i], af0
            elif h[i] > ep:
                ep, af = h[i], min(af + af0, afmax)
        else:
            ps = max(ps, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > ps:
                up, ps, ep, af = True, ep, h[i], af0
            elif l[i] < ep:
                ep, af = l[i], min(af + af0, afmax)
        trend[i] = 1 if up else -1
    return trend


def clue_events(D, F, H, h4_close_bar):
    t, o, h, l, c = D["t"], D["o"], D["h"], D["l"], D["c"]
    n = len(c)
    reg = F["reg"]
    ev = {}
    # H2 stochastic 14-3-3
    hh, ll = roll_max(h, 14), roll_min(l, 14)
    k = sma(np.nan_to_num(100 * (c - ll) / np.maximum(hh - ll, 1e-9)), 3)
    dd = sma(np.nan_to_num(k), 3)
    e = []
    for i in range(20, n):
        if k[i - 1] <= dd[i - 1] and k[i] > dd[i] and k[i] < 20 and dd[i] < 20:
            e.append((i, 1))
        if k[i - 1] >= dd[i - 1] and k[i] < dd[i] and k[i] > 80 and dd[i] > 80:
            e.append((i, -1))
    ev["H2 Stochastic cắt trong 20 / 80"] = (e, "Đ")
    # H3 CCI20
    tp = (h + l + c) / 3
    m = sma(tp, 20)
    mad = np.array([np.abs(tp[i - 19:i + 1] - m[i]).mean() if i >= 19 else np.nan for i in range(n)])
    cci = (tp - m) / (0.015 * mad)
    e = [(i, 1) for i in range(21, n) if cci[i - 1] < -200 <= cci[i]] + [(i, -1) for i in range(21, n) if cci[i - 1] > 200 >= cci[i]]
    ev["H3 CCI quay lại từ ± 200"] = (e, "Đ")
    # H4 Williams %R with the D1 regime
    wr = -100 * (hh - c) / np.maximum(hh - ll, 1e-9)
    e = [(i, 1) for i in range(15, n) if wr[i - 1] < -80 <= wr[i] and reg[i] == 1] + \
        [(i, -1) for i in range(15, n) if wr[i - 1] > -20 >= wr[i] and reg[i] == -1]
    ev["H4 Williams %R cùng chiều D1"] = (e, "R")
    # H5 MACD histogram divergence at 5/5 pivots, known 5 bars later
    macd = g.ema(c, 12) - g.ema(c, 26)
    hist = macd - g.ema(macd, 9)
    e, plo, phi = [], None, None
    for j in range(40, n - 5):
        if l[j] == l[j - 5:j + 6].min():
            if plo is not None and l[j] < l[plo] and hist[j] > hist[plo]:
                e.append((j + 5, 1))
            plo = j
        if h[j] == h[j - 5:j + 6].max():
            if phi is not None and h[j] > h[phi] and hist[j] < hist[phi]:
                e.append((j + 5, -1))
            phi = j
    ev["H5 phân kỳ histogram MACD"] = (e, "Đ")
    # I1-I3 on the H4 ZigZag
    for kz in (2, 3):
        piv = zigzag(H["h"], H["l"], H["atr"], kz)
        i1, i2 = elliott(piv)
        ev[f"I1-{kz} Elliott vào sóng 5"] = ([(h4_close_bar[a], s) for a, s in i1], "T")
        ev[f"I2-{kz} Elliott sau ABC"] = ([(h4_close_bar[a], s) for a, s in i2], "T")
        e = []
        for a, lvl, s in harmonic(piv):
            i0 = h4_close_bar[a] + 1
            for i in range(i0, min(n, i0 + 120)):
                if (s == 1 and l[i] <= lvl) or (s == -1 and h[i] >= lvl):
                    e.append((i, s))
                    break
        ev[f"I3-{kz} harmonic chạm D"] = (e, "Đ")
    # J1 Ichimoku H4
    Hh, Hl, Hc = H["h"], H["l"], H["c"]
    ten = (roll_max(Hh, 9) + roll_min(Hl, 9)) / 2
    kij = (roll_max(Hh, 26) + roll_min(Hl, 26)) / 2
    sa = np.r_[np.full(26, np.nan), ((ten + kij) / 2)[:-26]]
    sb = np.r_[np.full(26, np.nan), ((roll_max(Hh, 52) + roll_min(Hl, 52)) / 2)[:-26]]
    e = []
    for a in range(80, len(Hc)):
        top, bot = max(sa[a], sb[a]), min(sa[a], sb[a])
        if ten[a - 1] <= kij[a - 1] and ten[a] > kij[a] and Hc[a] > top:
            e.append((h4_close_bar[a], 1))
        if ten[a - 1] >= kij[a - 1] and ten[a] < kij[a] and Hc[a] < bot:
            e.append((h4_close_bar[a], -1))
    ev["J1 Ichimoku Tenkan / Kijun ngoài mây"] = (e, "T")
    # J5 Heikin Ashi H4
    hc = (H["o"] + Hh + Hl + Hc) / 4
    ho = np.zeros(len(hc))
    ho[0] = (H["o"][0] + Hc[0]) / 2
    for a in range(1, len(hc)):
        ho[a] = (ho[a - 1] + hc[a - 1]) / 2
    col = np.sign(hc - ho)
    e = []
    for a in range(6, len(col)):
        if col[a] == 1 and (col[a - 5:a] == -1).all():
            e.append((h4_close_bar[a], 1))
        if col[a] == -1 and (col[a - 5:a] == 1).all():
            e.append((h4_close_bar[a], -1))
    ev["J5 Heikin Ashi đổi màu sau 5 nến"] = (e, "Đ")
    # J7 SAR flip with the D1 regime
    tr = sar(Hh, Hl)
    e = []
    for a in range(2, len(tr)):
        if tr[a] != tr[a - 1]:
            i = h4_close_bar[a]
            if i < n and reg[i] == tr[a]:
                e.append((i, int(tr[a])))
    ev["J7 Parabolic SAR lật cùng chiều D1"] = (e, "R")
    return ev


def pivot_touches(D):
    """Daily classic pivots: reversal >= 0.5 ATR before a 0.5 ATR follow-through within 2 bars after a touch; real vs midpoints."""
    t, h, l, c, A = D["t"], D["h"], D["l"], D["c"], D["atr"]
    dd = days_of(t, h, l, c)
    out = {"thật": ([], []), "giả": ([], [])}
    for i in range(1, len(c) - 2):
        k = dd["idx"][i] - 1
        if k < 0 or not np.isfinite(A[i]) or dd["idx"][i - 1] != dd["idx"][i]:
            continue
        H_, L_, C_ = dd["h"][k], dd["l"][k], dd["c"][k]
        P = (H_ + L_ + C_) / 3
        lv = [L_ - 2 * (H_ - P), P - (H_ - L_), 2 * P - H_, P, 2 * P - L_, P + (H_ - L_), H_ + 2 * (P - L_)]
        mids = [(lv[j] + lv[j + 1]) / 2 for j in range(6)]
        x = 0.5 * A[i]
        for kind, levels in (("thật", [(v, 1) for v in lv[3:]] + [(v, -1) for v in lv[:4]]),
                             ("giả", [(v, 1) for v in mids[3:]] + [(v, -1) for v in mids[:3]])):
            for v, s in levels:                        # s = +1 approached from below, -1 from above
                if s == 1 and not (c[i - 1] < v <= h[i]):
                    continue
                if s == -1 and not (c[i - 1] > v >= l[i]):
                    continue
                if s * ((h[i] if s == 1 else l[i]) - v) >= x:
                    y = 0.0
                else:
                    y = 0.0
                    for j in (i + 1, i + 2):
                        rev = (l[j] <= v - x) if s == 1 else (h[j] >= v + x)
                        cont = (h[j] >= v + x) if s == 1 else (l[j] <= v - x)
                        if rev and cont:
                            y = None
                            break
                        if rev:
                            y = 1.0
                            break
                        if cont:
                            break
                if y is not None:
                    out[kind][0].append(int(t[i]))
                    out[kind][1].append(y)
    return out


def rows(events, r, t):
    tt, yy = [], []
    for i, d in events:
        if 0 <= i < len(r) and r[i] in (1, -1):
            tt.append(int(t[i]))
            yy.append(1.0 if r[i] == d else 0.0)
    return tt, yy


def judge(res, signs, alpha_min_n=100):
    pos = sum(1 for s in signs if s > 0)
    return bool(res.get("n", 0) >= alpha_min_n and res["CI"] is not None and res["CI"][0] > 0 and pos >= 2)


# ---------------------------------------------------------------------------------------------------------------- main
def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    D = g8.load_h1(root)
    F = g8.daily(D)
    H = g8.h4_frame(D)
    t, h, l, c = D["t"], D["h"], D["l"], D["c"]
    n = len(c)
    closed = H["closed"]
    h4_close_bar = np.searchsorted(closed, np.arange(1, len(H["c"]) + 1), side="left")
    res = {"phần A — cổng đi ngang": {}, "phần B — manh mối": {}}

    # ----- part A
    dd = days_of(t, h, l, c)
    KD, adr = gates_d1(dd["h"], dd["l"], dd["c"])
    K4h = gates_h4(H)
    last_bar = dd["ends"] - 1
    Kday = dict(KD)
    for kname, arr in K4h.items():
        idx = closed[last_bar] - 1
        Kday[kname] = np.where(idx >= 0, arr[np.maximum(idx, 0)], np.nan)
    y = one_way(dd["c"], adr)
    # account measure inputs
    B = m9.add_structure_h1(g8.bars_h1(D, F), D, H, F)
    fams = g8.entries(D, F, H)
    sig_all = {i: d for i, d in fams["E4"]}
    base = m9.Cfg()
    Kh1 = {}
    for kname in ("K1", "K3", "K5"):
        idx = closed - 1
        Kh1[kname] = np.where(idx >= 0, K4h[kname][np.maximum(idx, 0)], np.nan)
    for kname in ("K2", "K4"):
        di = dd["idx"] - 1
        Kh1[kname] = np.where(di >= 0, KD[kname][np.maximum(di, 0)], np.nan)
    # raw D1 2010-2018 for K2 / K4
    Bd = m9.add_structure_d1(g8.bars_d1(raw_d1))
    KR, adr_r = gates_d1(Bd["h"], Bd["l"], Bd["c"])
    yr = one_way(Bd["c"], adr_r)
    sidx = list(np.nonzero((Bd["t"] >= g.ts(2010, 3, 1)) & (Bd["t"] < g.ts(2018, 3, 1)))[0])
    prng = random.Random(SEED)
    stress_sets = [{int(i): prng.choice((1, -1)) for i in prng.sample(sidx, 60)} for _ in range(20)]
    stress_base = [m9.simulate(Bd, s, base, g.ts(2010, 3, 1), g.ts(2018, 3, 1)) for s in stress_sets]
    res["phần A — cổng đi ngang"]["nền E4 không cổng"] = {
        "cả kỳ": m9.simulate(B, sig_all, base, START, END),
        "stress: số lần chạy cháy / 20 (không cổng)": sum(1 for x in stress_base if x["cháy"] > 0)}
    alpha_a = 0.05 / 5
    for kname in ("K1", "K2", "K3", "K4", "K5"):
        r = {"A-i thị trường": part_a_market(kname, Kday[kname], y, dd["t"], rng, alpha_a)}
        if kname in KR:
            ok = np.isfinite(KR[kname]) & np.isfinite(yr) & (Bd["t"] < g.ts(2018, 3, 1))
            on, off = ok & (KR[kname] == 1), ok & (KR[kname] == 0)
            r["A-i D1 2010–02/2018 (chỉ báo cáo)"] = {"P(Y | bật)": round(float(yr[on].mean()), 3), "n bật": int(on.sum()),
                                                      "P(Y | tắt)": round(float(yr[off].mean()), 3), "n tắt": int(off.sum())}
        Kg = np.nan_to_num(Kh1[kname]) == 1
        sig = {i: d for i, d in sig_all.items() if Kg[i]}
        sel, chk, full = (m9.simulate(B, sig, base, a, z) for a, z in ((START, SPLIT), (SPLIT, END), (START, END)))
        rr = m9.rolling_ruin(B, sig, base)
        ctl = []
        span = 60 * 23
        for _ in range(50):
            lag = int(rng.integers(span, n - span))
            Ks = np.roll(Kg, lag)
            ctl.append(m9.simulate(B, {i: d for i, d in sig_all.items() if Ks[i]}, base, START, END))
        beat_dd = sum(1 for x in ctl if full["DD lớn nhất"] < x["DD lớn nhất"])
        beat_es = sum(1 for x in ctl if full["ES 5 % rổ"] > x["ES 5 % rổ"])
        acc = {"số tín hiệu E4 được mở": len([1 for i in sig if START <= t[i] < END]),
               "số tín hiệu E4 (không cổng)": len([1 for i in sig_all if START <= t[i] < END]),
               "kỳ chọn": sel, "kỳ kiểm": chk, "cả kỳ": full, "cháy 12 tháng": rr,
               "chuỗi dịch: DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in ctl])), 3),
               "chuỗi dịch: % lần có cháy": round(float(np.mean([x["cháy"] > 0 for x in ctl])), 2),
               "thắng chuỗi dịch về DD / 50": beat_dd, "thắng chuỗi dịch về ES / 50": beat_es}
        crit = {"0 cháy hai kỳ, lãi > 0": sel["cháy"] == 0 and chk["cháy"] == 0 and sel["lãi ròng"] > 0 and chk["lãi ròng"] > 0,
                "cháy 12 tháng = 0": rr == 0, "DD < 50 %": full["DD lớn nhất"] < 0.5,
                "DD và ES thắng ≥ 48 / 50 chuỗi dịch": beat_dd >= 48 and beat_es >= 48}
        if kname in KR:
            Kr = np.nan_to_num(KR[kname]) == 1
            st, st_ctl = [], []
            for s in stress_sets:
                kept = {i: d for i, d in s.items() if Kr[i]}
                st.append(m9.simulate(Bd, kept, base, g.ts(2010, 3, 1), g.ts(2018, 3, 1)))
                rand = {int(i): prng.choice((1, -1)) for i in prng.sample(sidx, len(kept))}
                st_ctl.append(m9.simulate(Bd, rand, base, g.ts(2010, 3, 1), g.ts(2018, 3, 1)))
            acc["stress: số lần chạy cháy / 20 (có cổng)"] = sum(1 for x in st if x["cháy"] > 0)
            acc["stress: số lần chạy cháy / 20 (cùng số entry, không cổng)"] = sum(1 for x in st_ctl if x["cháy"] > 0)
            acc["stress: entry giữ lại TB"] = round(float(np.mean([len([1 for i in s if Kr[i]]) for s in stress_sets])), 1)
            crit["stress 0 cháy"] = acc["stress: số lần chạy cháy / 20 (có cổng)"] == 0
        acc["tiêu chí"] = crit
        acc["đạt (A-ii)"] = all(crit.values()) and kname in KR
        acc["ứng viên chờ stress"] = all(crit.values()) and kname not in KR
        r["A-ii tài khoản"] = acc
        r["qua vòng"] = bool(r["A-i thị trường"]["đạt (A-i)"] and acc["đạt (A-ii)"])
        res["phần A — cổng đi ngang"][kname] = r
        ai = r["A-i thị trường"]
        print(kname, "| A-i chênh", ai["chênh"], ai["CI"], "null", ai["null dịch: tỷ lệ chênh dịch > chênh thật"], ai["số kỳ âm"],
              "bật", ai["tỷ lệ ngày bật"], "| A-ii", sel["cháy"], sel["lãi ròng"], chk["cháy"], chk["lãi ròng"], "DD", full["DD lớn nhất"],
              "12th", rr, "dịch DD/ES", beat_dd, beat_es, "stress", acc.get("stress: số lần chạy cháy / 20 (có cổng)"),
              acc.get("stress: số lần chạy cháy / 20 (cùng số entry, không cổng)"), flush=True)
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

    # ----- part B
    alpha_b = 0.05 / 15
    r1 = first_passage(h, l, c, D["atr"])
    reg = F["reg"]
    ret8 = np.sign(c - np.r_[np.full(8, np.nan), c[:-8]])
    allb = list(range(10, n))
    ctl_ev = {"Đ": dedupe([(i, -int(np.nan_to_num(ret8[i]))) for i in allb]),
              "T": dedupe([(i, int(np.nan_to_num(ret8[i]))) for i in allb]),
              "R": dedupe([(i, int(reg[i])) for i in allb])}
    ctl_rows = {k: rows(v, r1, t) for k, v in ctl_ev.items()}
    ev = clue_events(D, F, H, h4_close_bar)
    real_pass = 0
    clue_rows = {}
    for name, (e, ck) in ev.items():
        tc, yc = rows(dedupe(e), r1, t)
        clue_rows[name] = (tc, yc, ck)
        rr_, signs = compare(tc, yc, *ctl_rows[ck], alpha_b, rng)
        rr_["đối chứng"] = ck
        rr_["số kỳ dương"] = f"{sum(1 for s in signs if s > 0)}/{len(signs)}"
        rr_["đạt"] = judge(rr_, signs)
        real_pass += rr_["đạt"]
        res["phần B — manh mối"][name] = rr_
        print(name, "| n", rr_.get("n"), "P", rr_.get("P"), "vs", rr_.get("P đối chứng"), "chênh", rr_.get("chênh"), rr_.get("CI"),
              rr_["số kỳ dương"], "ĐẠT" if rr_["đạt"] else "", flush=True)
    pt = pivot_touches(D)
    rr_, signs = compare(*pt["thật"], *pt["giả"], alpha_b, rng)
    rr_["số kỳ dương"] = f"{sum(1 for s in signs if s > 0)}/{len(signs)}"
    rr_["đạt"] = judge(rr_, signs)
    real_pass += rr_["đạt"]
    res["phần B — manh mối"]["J4 pivot ngày: chỗ dừng (thật vs giữa hai mức)"] = rr_
    print("J4 pivot", rr_.get("n"), rr_.get("P"), "vs", rr_.get("P đối chứng"), rr_.get("chênh"), rr_.get("CI"), rr_["số kỳ dương"], flush=True)
    # family-wise shifted-label null (only meaningful if something passed)
    fam = {"số manh mối đạt thật": real_pass}
    if real_pass:
        cnt = []
        for _ in range(200):
            lag = int(rng.integers(500, n - 500))
            rs = np.roll(r1, lag)
            cr = {k: rows(v, rs, t) for k, v in ctl_ev.items()}
            k_ = 0
            for name, (e, ck) in ev.items():
                tc, yc = rows(dedupe(e), rs, t)
                x, sg = compare(tc, yc, *cr[ck], alpha_b, rng, boot=300)
                k_ += judge(x, sg)
            cnt.append(k_)
        fam["null: phân vị 95 % số manh mối đạt"] = float(np.percentile(cnt, 95))
        fam["vượt null"] = bool(real_pass > np.percentile(cnt, 95))
    res["null dịch nhãn toàn họ"] = fam
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("family", fam, "done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
