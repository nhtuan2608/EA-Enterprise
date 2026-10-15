"""G112 step 1: chase entries (buy / sell into momentum), excursion distributions, adds / stop-adding / exits vs
random (docs/superpowers/plans/2026-10-13-g112-chase-and-adds.md).

  G108_SYMBOL=XAUUSD [G109_NOFILTER=1] python g112_chase.py     # -> data/g112_chase_<SYMBOL>[_nf].pkl

Signals at the close of M5 bar j (entry at the open of j+1, the ask for buys):
  C1 impulse      the last 6 bars moved >= 1.0 ATR14 M30 one way and the close makes a new 24-bar high / low
  C2 day extreme  after 10:00 server, the close goes beyond the day's high / low so far
  C3 held break   a G110 break event (2 closes beyond a level) followed by a close further beyond on the next bar
First signal of each type per direction and 30-minute bucket; no entry 23:00-01:00.
Initial stop: the latest confirmed M5 swing on the other side +/- spread, at least 0.5 ATR M30 away (else 0.5 ATR),
skipped beyond 3 ATR; cost filter as G109 (off with G109_NOFILTER=1). The spread is always paid.
Position (R = multiples of the initial risk, every unit the same size):
  adds A    one more unit at the next open when the first unit is >= +1R on the close, after a pullback of >= 0.3
            ATR M30 from the running extreme, on a close making a new extreme; >= 6 bars apart, at most 2; on an add
            the stop of all units goes to the first entry (break-even)
  stop-adding (first that holds) S1 price within 0.25 ATR of the target zone / FVG ahead, S2 price / 12-bar delta
            divergence, S3 ADX H1 turning down, S4 two adds done
  random adds  the same number of adds at random in-profit bars (>= 6 apart), same stop handling
  exits X1 2R TP; X2 trailing behind the latest confirmed M5 swing; X3 trailing 1.5 ATR M30 from the best price;
        X4 TP at the nearest real zone / unfilled FVG ahead (none: stop and time only); X5 TP at the train median MFE
        of the same signal type and direction; all: at most 48 bars, then the close; same bar: stop first
Features use bars <= j; add / stop-adding decisions use bars <= k (entry at k + 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import g108_data as g8
import g108_features as gf
import g109_setups as gs
import g109_zones as gz
import g110_breaks as gb

OUT = g8.DATA / f"g112_chase_{gz.SYMBOL}{gs.SUF}.pkl"
MAX_BARS, IMP_BARS, IMP_ATR, NEWX_BARS = 48, 6, 1.0, 24
MIN_STOP_ATR, MAX_STOP_ATR = 0.5, 3.0
ADD_R, PULL_ATR, ADD_GAP, MAX_ADDS, NEAR_ATR = 1.0, 0.3, 6, 2, 0.25
TRAIL_ATR = 1.5
EXITS = ("X1", "X2", "X3", "X4", "X5")
ADD_MODES = ("none", "rule", "random")


# --------------------------------------------------------------------------------------------- position engine
def run_position(d: int, entry: float, stop0: float, a30: float, o, h, l, c, sp, swing_trail, stop_add, exit_mode: str,
                 target: float | None, add_mode: str, rand_bars=None):
    """Bars from the entry bar (index 0). swing_trail[k] = latest confirmed M5 swing on the stop side as of bar k
    (NaN if none). stop_add[k] = True when a stop-adding condition holds at the close of bar k. target: TP price for
    X1 / X4 / X5 (None = no TP). Returns dict(R, units, adds, bars, mfe, mae) with R in initial-risk units."""
    risk = d * (entry - stop0)
    units = [entry]
    stop = stop0
    best = entry
    ext = entry                                                   # running extreme in the trade direction (closes)
    pulled = False
    last_add = 0
    adds = 0
    adding_open = add_mode != "none"
    mfe = mae = 0.0
    n = min(len(h), MAX_BARS)
    rand_set = set(rand_bars or [])
    exit_px = None
    k = 0
    for k in range(n):
        bid_hi, bid_lo, ask_hi, ask_lo = h[k], l[k], h[k] + sp[k], l[k] + sp[k]
        # stop first, then target
        if (d == 1 and bid_lo <= stop) or (d == -1 and ask_hi >= stop):
            exit_px = stop
            break
        if target is not None and ((d == 1 and bid_hi >= target) or (d == -1 and ask_lo <= target)):
            exit_px = target
            break
        fav = (bid_hi - units[0]) if d == 1 else (units[0] - ask_lo)
        adv = (units[0] - bid_lo) if d == 1 else (ask_hi - units[0])
        mfe = max(mfe, fav / risk); mae = max(mae, adv / risk)
        best = max(best, bid_hi) if d == 1 else min(best, ask_lo)
        # trailing stops (effective from the next bar)
        if exit_mode == "X2" and np.isfinite(swing_trail[k]):
            cand = swing_trail[k] - sp[k] if d == 1 else swing_trail[k] + sp[k]
            stop = max(stop, cand) if d == 1 else min(stop, cand)
        if exit_mode == "X3":
            cand = best - d * TRAIL_ATR * a30
            stop = max(stop, cand) if d == 1 else min(stop, cand)
        # adds, decided on the close of bar k, filled at the open of k + 1
        ck = c[k]
        if d * (ck - ext) > 0:
            new_ext = True
            ext = ck
        else:
            new_ext = False
            if d * (ext - ck) >= PULL_ATR * a30:
                pulled = True
        if add_mode == "rule" and adding_open and stop_add[k]:      # stop-adding applies to the rule adds only
            adding_open = False
        if adding_open and adds < MAX_ADDS and k + 1 < n and k - last_add >= ADD_GAP:
            in_r = d * (ck - units[0]) / risk
            go = False
            if add_mode == "rule":
                go = in_r >= ADD_R and pulled and new_ext
            elif add_mode == "random":
                go = k in rand_set and in_r > 0
            if go:
                units.append(o[k + 1] + (sp[k + 1] if d == 1 else 0.0))
                adds += 1
                last_add = k
                pulled = False
                stop = max(stop, units[0]) if d == 1 else min(stop, units[0])
                if adds >= MAX_ADDS:
                    adding_open = False
    if exit_px is None:
        k = n - 1
        exit_px = c[k] if d == 1 else c[k] + sp[k]
    R = sum(d * (exit_px - u) for u in units) / risk
    return dict(R=R, units=len(units), adds=adds, bars=k + 1, mfe=mfe, mae=mae)


def first_touch_r(d: int, entry: float, risk: float, h, l, sp, levels=(1.0, 2.0, 3.0)) -> dict:
    """For each level L: 1 if +L R is reached before -1R within MAX_BARS (stop first on the same bar)."""
    out = {}
    for L in levels:
        tgt, stp = entry + d * L * risk, entry - d * risk
        res = 0
        for k in range(min(len(h), MAX_BARS)):
            if (d == 1 and l[k] <= stp) or (d == -1 and h[k] + sp[k] >= stp):
                break
            if (d == 1 and h[k] >= tgt) or (d == -1 and l[k] + sp[k] <= tgt):
                res = 1
                break
        out[f"hit{int(L)}"] = res
    return out


# --------------------------------------------------------------------------------------------- build
def stop_adding(s: int, idx: np.ndarray, t_ahead, a30: float, P: dict) -> np.ndarray:
    """S1 near the target ahead, S2 price / 12-bar delta divergence, S3 ADX H1 turning down, at the close of each bar."""
    c = P["c"]
    near_t = np.zeros(len(idx), bool) if t_ahead is None or not np.isfinite(t_ahead) else (s * (t_ahead - c[idx]) <= NEAR_ATR * a30)
    dl = P["delta12"][idx]
    div = (np.sign(P["price12"][idx] * s) != np.sign(dl * s)) & np.isfinite(dl)
    return near_t | div | (P["adx_at"][idx] < P["adx_prev"][idx])


def per_bar(df: pd.DataFrame) -> dict:
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(t)
    rv = gb.rel_volume(t, df["tickvol"].to_numpy(float))
    cl = gb.clv(o, h, l, c)
    H1 = gz.bars(t, o, h, l, c, np.zeros(n), 3600)
    _, _, A1 = gf.dmi(H1["h"].to_numpy(), H1["l"].to_numpy(), H1["c"].to_numpy())
    k1 = np.searchsorted((H1.index.to_numpy(np.int64) + 1) * 3600, t + g8.BAR_SEC, side="right") - 1
    num = pd.Series(cl * np.nan_to_num(rv)).rolling(12).sum().to_numpy()
    den = pd.Series(np.nan_to_num(rv)).rolling(12).sum().to_numpy()
    sh, sl = g8.fractals(h, l)
    return dict(c=c, rv=rv, adx_at=A1[np.maximum(k1, 0)], adx_prev=A1[np.maximum(k1 - 1, 0)],
                delta12=np.where(den > 0, num / np.where(den > 0, den, 1), np.nan),
                price12=c - np.r_[np.full(12, np.nan), c[:-12]],
                sh_last=g8.last_two_confirmed(sh, h, n)[0], sl_last=g8.last_two_confirmed(sl, l, n)[0])


def build(df: pd.DataFrame, Z: pd.DataFrame, D: pd.DataFrame, E: pd.DataFrame | None, hist=None, seed: int = 112):
    P = per_bar(df)
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    tv = df["tickvol"].to_numpy(float)
    n = len(t)
    hour = (t % 86400) // 3600
    day = t // 86400
    atr5 = g8.wilder_atr(h, l, c)
    rv = gb.rel_volume(t, tv)
    cl = gb.clv(o, h, l, c)
    M30 = gz.bars(t, o, h, l, c, np.zeros(n), 1800)
    atr30 = g8.wilder_atr(M30["h"].to_numpy(), M30["l"].to_numpy(), M30["c"].to_numpy())
    k30 = np.searchsorted((M30.index.to_numpy(np.int64) + 1) * 1800, t + g8.BAR_SEC, side="right") - 1
    a30_at = atr30[np.maximum(k30, 0)]
    H1 = gz.bars(t, o, h, l, c, np.zeros(n), 3600)
    P1, M1, A1 = gf.dmi(H1["h"].to_numpy(), H1["l"].to_numpy(), H1["c"].to_numpy())
    k1 = np.searchsorted((H1.index.to_numpy(np.int64) + 1) * 3600, t + g8.BAR_SEC, side="right") - 1
    adx_at = A1[np.maximum(k1, 0)]
    adx_prev = A1[np.maximum(k1 - 1, 0)]
    b4, c4 = gf.htf_closes(df, hist, 14400)
    e4 = g8.ema(c4, 200)
    k4 = np.searchsorted((b4 + 1) * 14400, t + g8.BAR_SEC, side="right") - 1
    h4_side = np.where(k4 >= 0, np.sign(c - e4[np.maximum(k4, 0)]), 0.0)
    sh, sl = g8.fractals(h, l)
    sh_last, _ = g8.last_two_confirmed(sh, h, n)
    sl_last, _ = g8.last_two_confirmed(sl, l, n)
    hmax, lmin = g8.RangeExt(h, np.maximum), g8.RangeExt(l, np.minimum)
    fv = gb.m5_fvgs(h, l)
    # 12-bar delta / price for divergence at every bar
    num = pd.Series(cl * np.nan_to_num(rv)).rolling(12).sum().to_numpy()
    den = pd.Series(np.nan_to_num(rv)).rolling(12).sum().to_numpy()
    delta12 = np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)
    price12 = c - np.r_[np.full(12, np.nan), c[:-12]]
    first_of = pd.Series(np.arange(n)).groupby(day).min().to_dict()
    last_of = pd.Series(np.arange(n)).groupby(day).max().to_dict()
    Dd = D.set_index("day")
    zones_by_day = {}
    for z in Z[~Z["fake"]].itertuples():
        zones_by_day.setdefault(int(z.day), []).append((z.center, z.w, int(z.from_i)))
    # signals
    sig = []
    seen = set()
    held = set()
    if E is not None and len(E):
        for r in E.itertuples():
            j = int(r.j)
            if j + 1 < n and r.s * (c[j + 1] - c[j]) > 0 and day[j + 1] == day[j]:
                held.add((j + 1, int(r.s)))
    for dd in sorted(first_of):
        if dd not in Dd.index:
            continue
        a, e_day = first_of[dd], last_of[dd]
        for j in range(max(a, NEWX_BARS + 40), e_day):
            if hour[j + 1] >= 23 or hour[j + 1] < 1:
                continue
            a30 = a30_at[j]
            cand = []
            mv = c[j] - c[j - IMP_BARS]
            if abs(mv) >= IMP_ATR * a30:
                s = 1 if mv > 0 else -1
                if (s == 1 and c[j] > hmax.q(j - NEWX_BARS, j - 1)) or (s == -1 and c[j] < lmin.q(j - NEWX_BARS, j - 1)):
                    cand.append(("C1", s))
            if hour[j] >= 10 and j > a:
                if c[j] > hmax.q(a, j - 1):
                    cand.append(("C2", 1))
                elif c[j] < lmin.q(a, j - 1):
                    cand.append(("C2", -1))
            for s in (1, -1):
                if (j, s) in held:
                    cand.append(("C3", s))
            for typ, s in cand:
                key = (typ, s, int(t[j] // 1800))
                if key in seen:
                    continue
                seen.add(key)
                sig.append((dd, j, typ, s))
    rng = np.random.default_rng(seed)
    rows = []
    for dd, j, typ, s in sig:
        e = j + 1
        a30 = a30_at[j]
        entry = o[e] + (sp[e] if s == 1 else 0.0)
        sw = sl_last[j] if s == 1 else sh_last[j]
        stop = (sw - sp[j]) if (s == 1 and np.isfinite(sw)) else ((sw + sp[j]) if np.isfinite(sw) else np.nan)
        if not np.isfinite(stop) or s * (entry - stop) < MIN_STOP_ATR * a30:
            stop = entry - s * MIN_STOP_ATR * a30
        risk = s * (entry - stop)
        if risk > MAX_STOP_ATR * a30 or risk < gs.MIN_STOP_SPREADS * sp[e] or atr5[j] < gs.MIN_ATR5_SPREADS * sp[e]:
            continue
        # targets ahead as of j: nearest real zone near edge, nearest unfilled FVG near edge
        zl = [(cz, wz) for cz, wz, fz in zones_by_day.get(dd, []) if fz <= j]
        tz = gs.next_zone(s, entry, zl)
        vd, _ = gb.void_ahead(j, s, c[j], fv, hmax, lmin, a30)
        tf = (c[j] + s * vd * a30) if vd < 9.0 else None
        ahead = [x for x in (tz, tf) if x is not None and s * (x - entry) > 0]
        t_ahead = min(ahead, key=lambda x: s * (x - entry)) if ahead else None
        fwd = slice(e, min(n, e + MAX_BARS))
        idx = np.arange(e, min(n, e + MAX_BARS))
        swing_trail = (sl_last if s == 1 else sh_last)[idx]
        stop_add = stop_adding(s, idx, t_ahead, a30, P)
        rec = dict(day=dd, time=int(t[j]), j=j, e=e, typ=typ, d=s, entry=entry, stop=stop, risk=risk, risk_atr=risk / a30,
                   t_ahead=t_ahead, a30=a30)
        rec.update(first_touch_r(s, entry, risk, h[fwd], l[fwd], sp[fwd]))
        base = run_position(s, entry, stop, a30, o[fwd], h[fwd], l[fwd], c[fwd], sp[fwd], swing_trail, stop_add, "none-exit", None, "none")
        rec["mfe"], rec["mae"] = base["mfe"], base["mae"]
        for X in EXITS:
            if X == "X5":
                continue                                          # needs the train median MFE: filled in finish()
            tgt = entry + s * 2 * risk if X == "X1" else (t_ahead if X == "X4" else None)
            for A in ADD_MODES:
                rb = None
                if A == "random":
                    nr = rec.get(f"{X}_rule_adds", 0)
                    cand_k = [k for k in range(1, len(idx) - 1) if s * (c[idx[k]] - entry) > 0]
                    rb = sorted(rng.choice(cand_k, size=min(nr, len(cand_k)), replace=False).tolist()) if nr and cand_k else []
                r = run_position(s, entry, stop, a30, o[fwd], h[fwd], l[fwd], c[fwd], sp[fwd], swing_trail, stop_add, X, tgt, A, rb)
                rec[f"{X}_{A}"] = r["R"]; rec[f"{X}_{A}_adds"] = r["adds"]; rec[f"{X}_{A}_bars"] = r["bars"]
        # features (bars <= j)
        q = j
        d12 = slice(q - 11, q + 1)
        rec.update(hour=int(hour[j]), sess=g8.session_of(int(hour[j])), adx_h1=float(adx_at[j]), adx_up=float(adx_at[j] >= adx_prev[j]),
                   d1_with=s * int(Dd.loc[dd, "regime"]), h4_side=s * float(h4_side[j]),
                   rv1=float(rv[j]), rv6=float(np.nanmean(rv[j - 5:j + 1])), delta12=s * float(delta12[j]) if np.isfinite(delta12[j]) else np.nan,
                   diverg=float(np.sign(price12[j] * s) != np.sign(delta12[j] * s)) if np.isfinite(delta12[j]) else np.nan,
                   move6=s * (c[j] - c[j - IMP_BARS]) / a30, body=s * (c[j] - o[j]) / max(atr5[j], 1e-12),
                   void_ahead=vd, zone_ahead=(s * (tz - c[j]) / a30 if tz is not None else 9.0),
                   room=(s * (t_ahead - entry) / risk if t_ahead is not None else 9.0),
                   compress=(h[j - 25:j - 13].max() - l[j - 25:j - 13].min()) / a30,
                   day_pos=float((c[j] - lmin.q(first_of[dd], j)) / max(hmax.q(first_of[dd], j) - lmin.q(first_of[dd], j), 1e-12)))
        # random control: same day, direction, stop distance, 2R
        rr = []
        for _ in range(5):
            qq = int(rng.integers(first_of[dd], last_of[dd] + 1))
            if hour[qq] >= 23 or hour[qq] < 1:
                continue
            en = o[qq] + (sp[qq] if s == 1 else 0.0)
            f2 = slice(qq, min(n, qq + MAX_BARS))
            rr.append(gs.simulate(s, en, en - s * risk, en + s * 2 * risk, h[f2], l[f2], c[f2], sp[f2])["a"])
        rec["rand_X1"] = float(np.mean(rr)) if rr else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def finish(df: pd.DataFrame, C: pd.DataFrame, seed: int = 113) -> pd.DataFrame:
    """X5: TP at the median MFE (R) of the train signals of the same type and direction (no adds / rule adds)."""
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    n = len(t)
    med = C[C["period"] == "train"].groupby(["typ", "d"])["mfe"].median().to_dict()
    P = per_bar(df)
    sh_last, sl_last = P["sh_last"], P["sl_last"]
    rng = np.random.default_rng(seed)
    out = {f"X5_{A}": [] for A in ADD_MODES}
    out.update({f"X5_{A}_adds": [] for A in ADD_MODES})
    out.update({f"X5_{A}_bars": [] for A in ADD_MODES})
    for r in C.itertuples():
        m = med.get((r.typ, r.d), np.nan)
        e = int(r.e); s = int(r.d)
        fwd = slice(e, min(n, e + MAX_BARS)); idx = np.arange(e, min(n, e + MAX_BARS))
        swing_trail = (sl_last if s == 1 else sh_last)[idx]
        stop_add = stop_adding(s, idx, r.t_ahead if r.t_ahead is not None else None, r.a30, P)
        tgt = r.entry + s * max(m, 0.5) * r.risk if np.isfinite(m) else None
        nr = 0
        for A in ADD_MODES:
            rb = None
            if A == "random":
                cand_k = [k for k in range(1, len(idx) - 1) if s * (c[idx[k]] - r.entry) > 0]
                rb = sorted(rng.choice(cand_k, size=min(nr, len(cand_k)), replace=False).tolist()) if nr and cand_k else []
            res = run_position(s, r.entry, r.stop, r.a30, o[fwd], h[fwd], l[fwd], c[fwd], sp[fwd], swing_trail, stop_add, "X5", tgt, A, rb)
            if A == "rule":
                nr = res["adds"]
            out[f"X5_{A}"].append(res["R"]); out[f"X5_{A}_adds"].append(res["adds"]); out[f"X5_{A}_bars"].append(res["bars"])
    for k, v in out.items():
        C[k] = v
    return C


def random_control(df: pd.DataFrame, C: pd.DataFrame, seed: int = 114, draws: int = 5) -> np.ndarray:
    """Fair random control: entries at random bars of OTHER days of the same period (never the signal's own day,
    whose direction the signal already reveals), same direction, stop distance and 2R target."""
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = df["sp"].to_numpy(float)
    n = len(t)
    hour = (t % 86400) // 3600
    day = t // 86400
    ok = np.nonzero((hour >= 1) & (hour < 23))[0]
    per = g8.period(pd.Series(t)).to_numpy()
    rng = np.random.default_rng(seed)
    out = np.full(len(C), np.nan)
    for k, r in enumerate(C.itertuples()):
        pool = ok[(per[ok] == r.period) & (day[ok] != r.day)]
        rr = []
        for _ in range(draws):
            q = int(rng.choice(pool))
            en = o[q] + (sp[q] if r.d == 1 else 0.0)
            f = slice(q, min(n, q + MAX_BARS))
            rr.append(gs.simulate(int(r.d), en, en - r.d * r.risk, en + r.d * 2 * r.risk, h[f], l[f], c[f], sp[f])["a"])
        out[k] = float(np.mean(rr))
    return out


def main():
    df = g8.load_m5_raw()
    Z, D = pd.read_pickle(gz.OUT_Z), pd.read_pickle(gz.OUT_D)
    E = pd.read_pickle(g8.DATA / f"g110_events_{gz.SYMBOL}{g8.TFSUF}.pkl")
    D = D[D["period"] != "test"]                                  # sealed
    C = build(df, Z, D, E, gf.long_m30())
    C["period"] = g8.period(C["time"])
    C = C[C["period"] != "test"].reset_index(drop=True)
    C = finish(df, C)
    C["rand_X1"] = random_control(df, C)                          # replaces the same-day draws (they leak the day's direction)
    C.to_pickle(OUT)
    print(gz.SYMBOL, gs.SUF or "(filtered)", "signals", len(C), C.groupby(["typ"]).size().to_dict(), "->", OUT.name)


if __name__ == "__main__":
    main()
