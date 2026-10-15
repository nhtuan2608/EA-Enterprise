"""Plain-loop reference for ProbSetupEA (ProbSetup/ProbSignals.mqh): the G112 chase signals C1 / C2 on closed bars of
the trading timeframe, their stop / filters, the X1 outcome (stop first, 2R target, at most 48 bars) and the G114
factors, written independently of research/long/g112_chase.py so it can check both the research tables and the EA.

Inputs are plain arrays (closed bars only):
  bars  time (bar open, server), open, high, low, close, tickvol, sp (spread in price) of the trading timeframe
  h1    time, high, low, close of H1 bars        (ADX14, Wilder, seeded on the first bar)
  h4    time, close of H4 bars                   (EMA200 seeded on the first close)
  d1    time, close of D1 bars                   (EMA50, regime = close side == 10-day EMA slope side)
"""
from __future__ import annotations

import math

IMP_BARS, IMP_ATR, NEWX_BARS, MAX_BARS = 6, 1.0, 24, 48
MIN_STOP_ATR, MAX_STOP_ATR, MIN_STOP_SPREADS, MIN_ATR_SPREADS = 0.5, 3.0, 8.0, 3.0
FRACTAL, VOL_DAYS, VOL_MIN = 2, 20, 10


def wilder(x, n=14):
    out, v = [], None
    for a in x:
        v = a if v is None else v + (a - v) / n
        out.append(v)
    return out


def ema(x, p):
    k, out, v = 2.0 / (p + 1), [], None
    for a in x:
        v = a if v is None else v + k * (a - v)
        out.append(v)
    return out


def true_range(h, l, c):
    return [max(h[i], c[i - 1] if i else c[0]) - min(l[i], c[i - 1] if i else c[0]) for i in range(len(c))]


def adx(h, l, c, n=14):
    a = 1.0 / n
    out = []
    ts = ps = ms = ad = 0.0
    for i in range(len(c)):
        pc = c[i - 1] if i else c[0]
        tr = max(h[i] - l[i], abs(h[i] - pc), abs(l[i] - pc))
        up = h[i] - h[i - 1] if i else 0.0
        dn = l[i - 1] - l[i] if i else 0.0
        pdm = up if (up > dn and up > 0) else 0.0
        mdm = dn if (dn > up and dn > 0) else 0.0
        if i == 0:
            ts, ps, ms = tr, pdm, mdm
        else:
            ts += a * (tr - ts); ps += a * (pdm - ps); ms += a * (mdm - ms)
        P = 100 * ps / ts if ts > 0 else 0.0
        M = 100 * ms / ts if ts > 0 else 0.0
        dx = 100 * abs(P - M) / (P + M) if P + M > 1e-9 else 0.0
        ad = dx if i == 0 else ad + a * (dx - ad)
        out.append(ad)
    return out


def last_closed(times, sec, at):
    """Index of the last bar with time + sec <= at (-1 if none); times ascending."""
    lo, hi = 0, len(times)
    while lo < hi:
        m = (lo + hi) // 2
        if times[m] + sec <= at:
            lo = m + 1
        else:
            hi = m
    return lo - 1


def band(x, cuts):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return -1
    return sum(1 for v in cuts if x >= v)


def session(hour):
    return 0 if hour < 10 else (1 if hour < 15 else 2)


def rel_volume(t, tv):
    """tick volume / median of the same time of day over the previous 20 occurrences (at least 10), else NaN."""
    hist, out = {}, []
    for i in range(len(t)):
        key = t[i] % 86400
        prev = hist.setdefault(key, [])
        last = prev[-VOL_DAYS:]
        if len(last) >= VOL_MIN:
            s = sorted(last)
            m = len(s)
            med = s[m // 2] if m % 2 else 0.5 * (s[m // 2 - 1] + s[m // 2])
            out.append(tv[i] / med if med > 0 else float("nan"))
        else:
            out.append(float("nan"))
        prev.append(tv[i])
    return out


def confirmed_swings(h, l, k=FRACTAL):
    """For every bar i: the latest swing low / high confirmed by bar i (fractal k/k, strict left, weak right)."""
    n = len(h)
    lo_at, hi_at = [float("nan")] * n, [float("nan")] * n
    cur_lo = cur_hi = float("nan")
    for i in range(n):
        j = i - k                                                 # a fractal at j is known once bar j + k closes
        if j >= k:
            if all(l[j] < l[j - m] for m in range(1, k + 1)) and all(l[j] <= l[j + m] for m in range(1, k + 1)):
                cur_lo = l[j]
            if all(h[j] > h[j - m] for m in range(1, k + 1)) and all(h[j] >= h[j + m] for m in range(1, k + 1)):
                cur_hi = h[j]
        lo_at[i], hi_at[i] = cur_lo, cur_hi
    return lo_at, hi_at


def simulate_x1(d, entry, stop, h, l, c, sp, e):
    """Market entry at the open of bar e; stop first, then 2R; at most 48 bars, then the close (ask for sells)."""
    risk = d * (entry - stop)
    target = entry + d * 2 * risk
    n = len(c)
    last = min(n, e + MAX_BARS) - 1
    for k in range(e, last + 1):
        if (d == 1 and l[k] <= stop) or (d == -1 and h[k] + sp[k] >= stop):
            return d * (stop - entry) / risk, k - e + 1, k
        if (d == 1 and h[k] >= target) or (d == -1 and l[k] + sp[k] <= target):
            return 2.0, k - e + 1, k
    px = c[last] if d == 1 else c[last] + sp[last]
    return d * (px - entry) / risk, last - e + 1, last


def signals(bars: dict, h1: dict, h4: dict, d1: dict, tf_sec: int, start: int = 0, outcomes: bool = True) -> list[dict]:
    t, o, h, l, c = bars["time"], bars["open"], bars["high"], bars["low"], bars["close"]
    tv, sp = bars["tickvol"], bars["sp"]
    n = len(t)
    hour = [(x % 86400) // 3600 for x in t]
    day = [x // 86400 for x in t]
    atr_tf = wilder(true_range(h, l, c))
    # M30 bars built from the trading-timeframe bars (their own buckets), Wilder ATR14
    m30_t, m30_h, m30_l, m30_c = [], [], [], []
    for i in range(n):
        b = t[i] // 1800 * 1800
        if m30_t and m30_t[-1] == b:
            m30_h[-1] = max(m30_h[-1], h[i]); m30_l[-1] = min(m30_l[-1], l[i]); m30_c[-1] = c[i]
        else:
            m30_t.append(b); m30_h.append(h[i]); m30_l.append(l[i]); m30_c.append(c[i])
    atr30 = wilder(true_range(m30_h, m30_l, m30_c))
    a_h1 = adx(h1["high"], h1["low"], h1["close"])
    e4 = ema(h4["close"], 200)
    e50 = ema(d1["close"], 50)
    rv = rel_volume(t, tv)
    clv = [((c[i] - l[i]) - (h[i] - c[i])) / (h[i] - l[i]) if h[i] > l[i] else 0.0 for i in range(n)]
    sw_lo, sw_hi = confirmed_swings(h, l)
    first_of = {}
    for i in range(n):
        first_of.setdefault(day[i], i)
    out, seen = [], set()
    for j in range(max(start, NEWX_BARS + 40), n - 1):
        e = j + 1
        if day[e] != day[j] or hour[e] >= 23 or hour[e] < 1:
            continue
        k30 = last_closed(m30_t, 1800, t[j] + tf_sec)
        if k30 < 0:
            continue
        a30 = atr30[k30]
        a = first_of[day[j]]
        cand = []
        mv = c[j] - c[j - IMP_BARS]
        if abs(mv) >= IMP_ATR * a30:
            s = 1 if mv > 0 else -1
            prev = h[j - NEWX_BARS:j] if s == 1 else l[j - NEWX_BARS:j]
            if (s == 1 and c[j] > max(prev)) or (s == -1 and c[j] < min(prev)):
                cand.append(("C1", s))
        if hour[j] >= 10 and j > a:
            if c[j] > max(h[a:j]):
                cand.append(("C2", 1))
            elif c[j] < min(l[a:j]):
                cand.append(("C2", -1))
        for typ, s in cand:
            key = (typ, s, t[j] // 1800)
            if key in seen:
                continue
            seen.add(key)
            entry = o[e] + (sp[e] if s == 1 else 0.0)
            sw = sw_lo[j] if s == 1 else sw_hi[j]
            stop = (sw - sp[j]) if s == 1 else (sw + sp[j])
            if math.isnan(sw) or s * (entry - stop) < MIN_STOP_ATR * a30:
                stop = entry - s * MIN_STOP_ATR * a30
            risk = s * (entry - stop)
            if risk > MAX_STOP_ATR * a30 or risk < MIN_STOP_SPREADS * sp[e] or atr_tf[j] < MIN_ATR_SPREADS * sp[e]:
                continue
            # factors (bars <= j)
            k1 = last_closed(h1["time"], 3600, t[j] + tf_sec)
            k4 = last_closed(h4["time"], 14400, t[j] + tf_sec)
            kd = last_closed(d1["time"], 86400, t[a])
            reg = 0
            if kd >= 10:
                sd = (d1["close"][kd] > e50[kd]) - (d1["close"][kd] < e50[kd])
                sl = (e50[kd] > e50[kd - 10]) - (e50[kd] < e50[kd - 10])
                reg = sd if sd == sl else 0
            h4s = 0 if k4 < 0 else (c[j] > e4[k4]) - (c[j] < e4[k4])
            rv6 = [x for x in rv[j - 5:j + 1] if not math.isnan(x)]
            num = sum(clv[q] * (0.0 if math.isnan(rv[q]) else rv[q]) for q in range(j - 11, j + 1))
            den = sum(0.0 if math.isnan(rv[q]) else rv[q] for q in range(j - 11, j + 1))
            if den > 0:
                delta12 = num / den
                price12 = c[j] - c[j - 12]
                sgn = lambda x: (x > 0) - (x < 0)
                div = int(sgn(price12 * s) != sgn(delta12 * s))
            else:
                div = -1
            dh, dl = max(h[a:j + 1]), min(l[a:j + 1])
            pos = (c[j] - dl) / max(dh - dl, 1e-12)
            rec = dict(j=j, time=t[j], typ=typ, d=s, entry=entry, stop=stop, risk=risk, a30=a30,
                       f_side=s, f_sess=session(hour[j]), f_d1=s * reg, f_h4=s * h4s,
                       f_adx=band(a_h1[k1] if k1 >= 0 else float("nan"), [20, 30]),
                       f_vol=band(sum(rv6) / len(rv6) if rv6 else float("nan"), [0.9, 1.3]),
                       f_div=div, f_pos=band(pos, [0.33, 0.67]))
            if outcomes:
                R, nb, kx = simulate_x1(s, entry, stop, h, l, c, sp, e)
                rec.update(R=R, bars=nb, exit_j=kx)
            out.append(rec)
    return out
