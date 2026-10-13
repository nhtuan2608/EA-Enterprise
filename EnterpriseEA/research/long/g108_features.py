"""G108 step 3 features of a plan at its decision bar (docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md,
section 2). Everything uses bars <= i and is expressed in the trade direction (x d), in ATR14 M30 units.

  path   the last 12 M5 closes vs the current close; the forming M30 bar so far (move, room to its high / low,
         position 1-6)
  m30    closed-M30 EMA21/55/100/200 distances and 4-bar slopes, EMA order, ADX and DI+ - DI- (Wilder 14)
  htf    H1 / H4 EMA200 distance and side, D1 regime (close vs EMA50 and its 10-day slope) - from the long M30
         history (research data/m30v, 2010-) followed by the M5-built bars
  day    distance to the prior server-day high / low, position in today's range, today's range
  plan   risk, reward (ATR), RR
  time   server hour, weekday, session
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g108_data as g

PATH_N = 12
F_PATH = [f"p{k}" for k in range(1, PATH_N + 1)] + ["f_move", "f_room_up", "f_room_dn", "pos"]
F_TIME = ["hour", "dow", "sess"]
F_CTX = ["e21", "e55", "e100", "e200", "s21", "s55", "s100", "s200", "ordered", "adx", "di",
         "h1_dist", "h4_dist", "h4_side", "d1_state", "d1_dist", "pdh", "pdl", "day_pos", "day_rng",
         "risk_atr", "reward_atr", "rr", "struct", "band"]
FEATS = ["d"] + F_PATH + F_TIME + F_CTX


def dmi(h, l, c, n=14):
    a = 1.0 / n
    P = np.zeros(len(c)); M = np.zeros(len(c)); A = np.zeros(len(c))
    ts = ps = ms = ad = 0.0
    for i in range(len(c)):
        pc = c[0] if i == 0 else c[i - 1]
        tr = max(h[i] - l[i], abs(h[i] - pc), abs(l[i] - pc))
        up = 0.0 if i == 0 else h[i] - h[i - 1]
        dn = 0.0 if i == 0 else l[i - 1] - l[i]
        pdm = up if (up > dn and up > 0) else 0.0
        mdm = dn if (dn > up and dn > 0) else 0.0
        if i == 0:
            ts, ps, ms = tr, pdm, mdm
        else:
            ts += a * (tr - ts); ps += a * (pdm - ps); ms += a * (mdm - ms)
        P[i] = 100 * ps / ts if ts > 0 else 0.0
        M[i] = 100 * ms / ts if ts > 0 else 0.0
        s = P[i] + M[i]
        dx = 100 * abs(P[i] - M[i]) / s if s > 1e-9 else 0.0
        ad = dx if i == 0 else ad + a * (dx - ad)
        A[i] = ad
    return P, M, A


def long_m30() -> pd.DataFrame:
    df = pd.read_csv(g.DATA / "m30v" / "XAUUSD.csv")
    return df[["time", "high", "low", "close"]]


def htf_closes(m5: pd.DataFrame, hist: pd.DataFrame | None, sec: int):
    """Closes of completed `sec` buckets: the long history, then buckets built from M5 after it."""
    t = m5["time"].to_numpy(np.int64)
    a = pd.DataFrame({"b": t // sec, "c": m5["close"].to_numpy(float)}).groupby("b")["c"].last()
    if hist is not None and len(hist):
        hb = pd.DataFrame({"b": hist["time"].to_numpy(np.int64) // sec, "c": hist["close"].to_numpy(float)}).groupby("b")["c"].last()
        hb = hb.iloc[:-1]                                        # its last bucket may be incomplete: M5 takes over
        a = pd.concat([hb, a[a.index > hb.index.max()]])
    return a.index.to_numpy(np.int64), a.to_numpy(float)


def last_closed(buckets: np.ndarray, sec: int, T: np.ndarray) -> np.ndarray:
    """Index of the last bucket whose end (b + 1) * sec <= T."""
    return np.searchsorted((buckets + 1) * sec, T, side="right") - 1


def features(m5: pd.DataFrame, D: pd.DataFrame, hist: pd.DataFrame | None = None) -> pd.DataFrame:
    t = m5["time"].to_numpy(np.int64)
    o, h, l, c = (m5[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    T = t + 300
    n = len(t)
    # closed M30 from M5 (as in g108_data)
    b30 = t // 1800
    G = pd.DataFrame({"b": b30, "h": h, "l": l, "c": c}).groupby("b").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    m30b = G.index.to_numpy(np.int64)
    gh, gl, gc = (G[k].to_numpy(float) for k in ("h", "l", "c"))
    E = {p: g.ema(gc, p) for p in (21, 55, 100, 200)}
    atr = g.wilder_atr(gh, gl, gc)
    P, M, A = dmi(gh, gl, gc)
    k30 = last_closed(m30b, 1800, T)
    # forming M30 so far and today so far (cumulative within the bucket / day, bars <= i)
    frame = pd.DataFrame({"b": b30, "day": t // 86400, "h": h, "l": l})
    f_hi = frame.groupby("b")["h"].cummax().to_numpy(); f_lo = frame.groupby("b")["l"].cummin().to_numpy()
    d_hi = frame.groupby("day")["h"].cummax().to_numpy(); d_lo = frame.groupby("day")["l"].cummin().to_numpy()
    f_open = o[np.searchsorted(t, b30 * 1800)]
    day = t // 86400
    dg = frame.groupby("day").agg(h=("h", "max"), l=("l", "min"))
    days = dg.index.to_numpy(np.int64)
    k_prev = np.searchsorted(days, day) - 1                      # prior trading day
    pdh = np.where(k_prev >= 0, dg["h"].to_numpy()[np.maximum(k_prev, 0)], np.nan)
    pdl = np.where(k_prev >= 0, dg["l"].to_numpy()[np.maximum(k_prev, 0)], np.nan)
    # higher frames
    def at(x, k):                                                # value of the last closed bucket; NaN before the first
        return np.where(k >= 0, x[np.maximum(k, 0)], np.nan)

    out = {}
    for name, sec, per in (("h1", 3600, 200), ("h4", 14400, 200)):
        b, cl = htf_closes(m5, hist, sec)
        e = g.ema(cl, per)
        k = last_closed(b, sec, T)
        out[name] = (at(cl, k), at(e, k))                        # per M5 bar
    bd, cd = htf_closes(m5, hist, 86400)
    ed = g.ema(cd, 50)
    kd = last_closed(bd, 86400, T)
    d_ema = at(ed, kd)
    d_side = np.sign(at(cd, kd) - d_ema)
    d_slope = np.sign(d_ema - at(ed, kd - 10))
    d_state = np.where(d_side == d_slope, d_side, 0)

    i = D["i"].to_numpy(np.int64)
    d = D["d"].to_numpy(float)
    k = k30[i]
    a = atr[k]
    ci = c[i]
    F = pd.DataFrame(index=D.index)
    F["d"] = d
    for j in range(1, PATH_N + 1):
        F[f"p{j}"] = d * (ci - c[np.maximum(i - j, 0)]) / a
    F["f_move"] = d * (ci - f_open[i]) / a
    up_room, dn_room = (f_hi[i] - ci) / a, (ci - f_lo[i]) / a
    F["f_room_up"] = np.where(d == 1, up_room, dn_room)
    F["f_room_dn"] = np.where(d == 1, dn_room, up_room)
    F["pos"] = D["pos"].to_numpy()
    F["hour"] = (t[i] % 86400) // 3600
    F["dow"] = ((t[i] // 86400) + 3) % 7                         # 0 = Monday (1970-01-01 was a Thursday)
    F["sess"] = D["sess"].to_numpy()
    for p in (21, 55, 100, 200):
        F[f"e{p}"] = d * (ci - E[p][k]) / a
        F[f"s{p}"] = d * (E[p][k] - E[p][np.maximum(k - 4, 0)]) / a
    ob = (E[21][k] > E[55][k]) & (E[55][k] > E[100][k]) & (E[100][k] > E[200][k])
    os_ = (E[21][k] < E[55][k]) & (E[55][k] < E[100][k]) & (E[100][k] < E[200][k])
    F["ordered"] = np.where(d == 1, ob, os_).astype(float) - np.where(d == 1, os_, ob).astype(float)
    F["adx"] = A[k]
    F["di"] = d * (P[k] - M[k])
    for name in ("h1", "h4"):
        F[f"{name}_dist"] = d * (ci - out[name][1][i]) / a
    F["h4_side"] = d * np.sign(out["h4"][0][i] - out["h4"][1][i])
    F["d1_state"] = d * d_state[i]
    F["d1_dist"] = d * (ci - d_ema[i]) / a
    F["pdh"] = d * (ci - pdh[i]) / a
    F["pdl"] = d * (ci - pdl[i]) / a
    rng = np.maximum(d_hi[i] - d_lo[i], 1e-9)
    pos_day = (ci - d_lo[i]) / rng
    F["day_pos"] = np.where(d == 1, pos_day, 1 - pos_day)
    F["day_rng"] = rng / a
    F["risk_atr"] = D["risk"].to_numpy() / a
    F["reward_atr"] = D["rr"].to_numpy() * D["risk"].to_numpy() / a
    F["rr"] = D["rr"].to_numpy()
    F["struct"] = d * D["struct"].to_numpy()
    F["band"] = d * D["band"].to_numpy()
    return F[FEATS]
