"""Pure-Python mirror of Setups/DmiEmaCompression.mqh (G72 S07). No third-party libraries.

bars: list of dicts with time (server epoch), open, high, low, close, oldest first.
"""
from __future__ import annotations

ADX_LOW, DI_GAP, ADX_RISE, PERIOD = 20.0, 6.0, 10.0, 14
STOP_BUFFER_ATR, STOP_MIN_ATR, STOP_MAX_ATR, GAP_SECONDS = 0.10, 1.0, 4.0, 21600
TARGET_R, TRAIL_SWITCH_R, L2_ATR = 8.0, 3.0, 0.5
MAX_ADDS, MAX_OPEN_LEGS, ADD_SPACING = 2, 3, 3600
WINDOW = {"M15": 16, "M30": 8, "H1": 4, "H4": 8}
HOLD = {"M15": 480, "M30": 240, "H1": 120, "H4": 240}


def ema(closes, n):
    out, k = [], 2.0 / (n + 1)
    for i, c in enumerate(closes):
        out.append(c if i == 0 else out[-1] + k * (c - out[-1]))
    return out


def dmi(bars):
    a = 1.0 / PERIOD
    pdi, mdi, adx, atr = [], [], [], []
    tr_s = pdm_s = mdm_s = adx_s = 0.0
    for i, b in enumerate(bars):
        pc = bars[0]["close"] if i == 0 else bars[i - 1]["close"]
        tr = max(b["high"] - b["low"], abs(b["high"] - pc), abs(b["low"] - pc))
        up = 0.0 if i == 0 else b["high"] - bars[i - 1]["high"]
        dn = 0.0 if i == 0 else bars[i - 1]["low"] - b["low"]
        pdm = up if (up > dn and up > 0) else 0.0
        mdm = dn if (dn > up and dn > 0) else 0.0
        if i == 0:
            tr_s, pdm_s, mdm_s = tr, pdm, mdm
        else:
            tr_s += a * (tr - tr_s); pdm_s += a * (pdm - pdm_s); mdm_s += a * (mdm - mdm_s)
        p = 100 * pdm_s / tr_s if tr_s > 0 else 0.0
        m = 100 * mdm_s / tr_s if tr_s > 0 else 0.0
        dx = 100 * abs(p - m) / (p + m) if p + m > 1e-9 else 0.0
        adx_s = dx if i == 0 else adx_s + a * (dx - adx_s)
        pdi.append(p); mdi.append(m); adx.append(adx_s); atr.append(tr_s)
    return pdi, mdi, adx, atr


def indicators(bars):
    closes = [b["close"] for b in bars]
    e = {n: ema(closes, n) for n in (21, 55, 100, 200)}
    pdi, mdi, adx, atr = dmi(bars)
    return dict(e=e, pdi=pdi, mdi=mdi, adx=adx, atr=atr)


def signal_at(bars, ind, i, window, h4_side):
    if i < window + 1:
        return 0
    adx, pdi, mdi, e = ind["adx"], ind["pdi"], ind["mdi"], ind["e"]
    k = i - window
    for j in range(i - window + 1, i):
        if adx[j] < adx[k]:
            k = j
    if adx[k] > ADX_LOW or abs(pdi[k] - mdi[k]) > DI_GAP:
        return 0
    if not (adx[i] > adx[i - 1] and adx[i] - adx[k] <= ADX_RISE):
        return 0
    gap, gp = pdi[i] - mdi[i], pdi[i - 1] - mdi[i - 1]
    hi = max(e[21][i], e[55][i], e[100][i], e[200][i])
    lo = min(e[21][i], e[55][i], e[100][i], e[200][i])
    d = 1 if (gap > 0 and gap > gp and bars[i]["close"] > hi) else -1 if (gap < 0 and gap < gp and bars[i]["close"] < lo) else 0
    return d if d != 0 and h4_side == d else 0


def stop_anchor(bars, i, window, d):
    a0 = i - window
    for k in range(i, i - window, -1):
        if bars[k]["time"] - bars[k - 1]["time"] > GAP_SECONDS:
            a0 = k
            break
    seg = bars[a0:i + 1]
    return min(b["low"] for b in seg) if d == 1 else max(b["high"] for b in seg)


def plan(entry, anchor, d, atr):
    """Stop and target as EEA_ControlledLiveResolveV1Plan for S07; None when the stop is too wide."""
    stop = anchor - d * STOP_BUFFER_ATR * atr
    dist = abs(entry - stop)
    if dist > STOP_MAX_ATR * atr:
        return None
    if dist < STOP_MIN_ATR * atr:
        stop = entry - d * STOP_MIN_ATR * atr
        dist = abs(entry - stop)
    return {"stop": stop, "target": entry + d * TARGET_R * dist, "risk": dist}


def add_allowed(legs_open, base_open, base_in_profit, adds_done, seconds_since_last_leg):
    """Mirror of EEA_S07EntryAllowed for an S07A add."""
    if legs_open >= MAX_OPEN_LEGS:
        return "S07_MAX_OPEN_LEGS"
    if not base_open:
        return "S07A_NO_OPEN_BASE"
    if adds_done >= MAX_ADDS:
        return "S07A_MAX_ADDS"
    if seconds_since_last_leg < ADD_SPACING:
        return "S07A_TOO_CLOSE_TO_PREVIOUS_LEG"
    if not base_in_profit:
        return "S07A_BASE_NOT_IN_PROFIT"
    return "S07A_ADD_ALLOWED"


def trend_exit(direction, close, ema55, ema100, mfe_r):
    ema_used = ema100 if mfe_r >= TRAIL_SWITCH_R else ema55
    return direction * (close - ema_used) < 0


def sell_location(bars, i, window, h4_ema, atr):
    """Mirror of EEA_S07SellLocation (S07S, G71 L2): the window top reached the H4 EMA200 less 0.5 ATR."""
    if h4_ema <= 0 or atr <= 0:
        return False
    return max(b["high"] for b in bars[i - window:i + 1]) >= h4_ema - L2_ATR * atr


def h4_sides(bars, h4, h4_ema_period=200):
    """Per bar of `bars`: (side, h4 EMA200) of the last completed H4 bar before the bar's H4 bucket (server time),
    as EEA_StrategyRuntimeScanS07Engine."""
    e = ema([b["close"] for b in h4], h4_ema_period)
    out, h = [], 0
    for b in bars:
        bucket = b["time"] - b["time"] % 14400
        while h + 1 < len(h4) and h4[h + 1]["time"] < bucket:
            h += 1
        ok = bool(h4) and h4[h]["time"] < bucket and h >= h4_ema_period
        side = 0 if not ok else (1 if h4[h]["close"] > e[h] else -1 if h4[h]["close"] < e[h] else 0)
        out.append((side, e[h] if ok else 0.0))
    return out


def run(bars, h4, setup, tf, first=0):
    """S07 / S07A (buy) or S07S (sell + location) signals on `bars` from index `first`: list of (i, direction)."""
    window = WINDOW[tf]
    ind = indicators(bars)
    sides = h4_sides(bars, h4)
    out = []
    for i in range(max(first, window + 1), len(bars)):
        side, h4e = sides[i]
        d = signal_at(bars, ind, i, window, side)
        if setup == "S07S":
            d = -1 if d == -1 and sell_location(bars, i, window, h4e, ind["atr"][i]) else 0
        elif d != 1:
            d = 0
        if d:
            out.append((i, d))
    return out
