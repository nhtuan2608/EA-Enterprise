"""Python mirror of News/NewsReaction.mqh (News Reaction Recorder, R1-R6)."""
import math

HORIZONS = [1, 5, 15, 60, 240]
MIN_HISTORY = 8
MIN_SAMPLES = 6


def surprise(actual, forecast, digits, history):
    """actual/forecast may be None. history: list of past (actual - forecast)."""
    if actual is None:
        return {"quality": "NO_ACTUAL", "side": "", "std": None}
    if forecast is None:
        return {"quality": "NO_FORECAST", "side": "", "std": None}
    raw = actual - forecast
    half = 0.5 * 10 ** (-max(0, digits))
    side = "INLINE" if abs(raw) <= half else ("ABOVE" if raw > 0 else "BELOW")
    if len(history) < MIN_HISTORY:
        return {"quality": "SURPRISE_HISTORY_INSUFFICIENT", "side": side, "std": None, "raw": raw}
    mean = sum(history) / len(history)
    sigma = math.sqrt(sum((d - mean) ** 2 for d in history) / (len(history) - 1))
    if sigma <= 0:
        return {"quality": "SURPRISE_SIGMA_ZERO", "side": side, "std": None, "raw": raw}
    return {"quality": "OK", "side": side, "std": raw / sigma, "raw": raw}


def closing_by(bars, t):
    found = -1
    for i, b in enumerate(bars):
        if b["t"] + b.get("seconds", 60) <= t:
            found = i
        else:
            break
    return found


def path(bars, T, atr):
    """bars: list of dict(t,o,h,l,c) with open time UTC, sorted."""
    r = {"move_ok": [False] * 5, "move": [0.0] * 5}
    if atr <= 0:
        r["quality"] = "INCOMPLETE_NO_ATR"
        return r
    i0 = closing_by(bars, T)
    if i0 < 0 or bars[i0]["t"] < T - 600:
        r["quality"] = "INCOMPLETE_NO_PRE_PRICE"
        return r
    p0 = bars[i0]["c"]
    last_close = bars[-1]["t"] + bars[-1].get("seconds", 60) if bars else 0
    for h, k_min in enumerate(HORIZONS):
        target = T + k_min * 60
        k = closing_by(bars, target)
        r["move_ok"][h] = k > i0 and last_close >= target - 120
        if r["move_ok"][h]:
            r["move"][h] = bars[k]["c"] - p0
    window = [b for b in bars if T <= b["t"] < T + 3600]
    r["max_up_60"] = max([b["h"] for b in window] + [p0]) - p0
    r["max_down_60"] = p0 - min([b["l"] for b in window] + [p0])
    m5, m60 = r["move"][1], r["move"][3]
    r["first_direction"] = "" if not r["move_ok"][1] else ("FLAT" if abs(m5) < 0.1 * atr else ("UP" if m5 > 0 else "DOWN"))
    r["reversal_60"] = bool(r["move_ok"][1] and r["move_ok"][3] and abs(m5) >= 0.3 * atr
                            and abs(m60) >= 0.3 * atr and m5 * m60 < 0)
    r["vol_recovery_min"] = -1
    for j in range(48):
        w = [b for b in bars if T + j * 300 <= b["t"] < T + j * 300 + 300]
        if w and max(b["h"] for b in w) - min(b["l"] for b in w) <= atr:
            r["vol_recovery_min"] = (j + 1) * 5
            break
    r["quality"] = "OK" if r["move_ok"][3] else "INCOMPLETE_NO_60M_PRICE"
    return r


def percentile(values, q):
    s = sorted(values)
    idx = max(0, min(len(s) - 1, math.ceil(q * len(s)) - 1))
    return s[idx]


def median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def stats(rows):
    """rows: dict(move15_atr, move60_atr, spread_ratio, recovery_min, reversal)."""
    n = len(rows)
    if n == 0:
        return {"n": 0, "has_suggestion": False}
    out = {
        "n": n,
        "median_move15_atr": median([abs(r["move15_atr"]) for r in rows]),
        "p80_move60_atr": percentile([abs(r["move60_atr"]) for r in rows], 0.8),
        "has_suggestion": n >= MIN_SAMPLES,
    }
    if out["has_suggestion"]:
        out["suggested_post_min"] = int(math.ceil(percentile([r["recovery_min"] for r in rows], 0.8) / 5.0) * 5)
        out["suggested_pre"] = "REDUCE" if out["p80_move60_atr"] < 0.5 else "KEEP"
    return out
