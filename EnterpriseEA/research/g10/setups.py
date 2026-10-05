"""G10/G12 offline prototypes of the remaining setup families (spec 4.4). Research only:
each detector turns a cached context into MARKET candidates in the format replay.evaluate
understands ("extreme" is the stop anchor, the zone is what the Trade Manager guards).

S01 Asian Range Break   range 00-07 UTC -> break -> acceptance -> (optional retest) -> trigger
S03 PDH/PDL Break       previous-day level -> break -> acceptance -> (retest) -> reaction
S05 Trend Pullback      HTF trend -> pullback to EMA20 -> reclaim -> continuation trigger
S06 Compression Expansion  compression box -> release bar -> expansion confirmation
"""
from __future__ import annotations

import replay
import s02_oracle


def _body_ok(b, d, ratio):
    rng = b["high"] - b["low"]
    if rng <= 0:
        return False
    return (b["close"] > b["open"] if d > 0 else b["close"] < b["open"]) and abs(b["close"] - b["open"]) >= ratio * rng


def _cand(ctx, i, d, anchor, zl, zh, atr):
    lvl = ctx["levels"].get(ctx["bar_level"][i])
    return {"kind": "MARKET", "i": i, "time": ctx["entry"][i]["time"], "direction": d, "extreme": anchor,
            "zone_low": zl, "zone_high": zh, "signal_atr": atr,
            "points": lvl["points"] if lvl else [], "structure": lvl["structure"] if lvl else "NEUTRAL"}


def _live(ctx, i):
    b = ctx["entry"][i]
    return b["time"] >= ctx["from_server"] and i >= 60 and b["atr"] > 0 and ctx["bar_level"][i] in ctx["levels"]


def s01(ctx, p):
    """p: end_hour (window end, UTC), mode ('accept' | 'retest'), sl ('mid' | 'breakbar'),
    max_range_atr (range height in entry ATR)."""
    bars, out = ctx["entry"], []
    day, hi, lo, n_range = None, None, None, 0
    state, d, brk, armed_at, used = "WAIT", 0, None, 0, set()
    for i, b in enumerate(bars):
        u = b["utc"]
        if u // 86400 != day:
            day, hi, lo, n_range, state, used = u // 86400, None, None, 0, "WAIT", set()
        h = (u // 3600) % 24
        if h < 7:
            hi = b["high"] if hi is None else max(hi, b["high"])
            lo = b["low"] if lo is None else min(lo, b["low"])
            n_range += 1
            continue
        if hi is None or n_range < 48 or h >= p["end_hour"] or not _live(ctx, i):
            continue
        atr = b["atr"]
        if (hi - lo) > p["max_range_atr"] * atr:
            continue
        if state == "WAIT":
            for dd, edge in ((1, hi), (-1, lo)):
                if dd not in used and dd * (b["close"] - edge) > 0.10 * atr and _body_ok(b, dd, 0.5):
                    state, d, brk = "BROKEN", dd, b
                    break
            continue
        edge = hi if d == 1 else lo
        if state == "BROKEN":
            if d * (b["close"] - edge) > 0:
                anchor = (hi + lo) / 2 if p["sl"] == "mid" else (brk["low"] if d == 1 else brk["high"])
                if p["mode"] == "accept":
                    out.append(_cand(ctx, i, d, anchor, lo, hi, atr))
                    used.add(d)
                    state = "WAIT"
                else:
                    state, armed_at = "ARMED", i
            else:
                state = "WAIT"
            continue
        if state == "ARMED":
            if d * (b["close"] - edge) < 0 or i - armed_at > 12:
                state = "WAIT"
                used.add(d)
                continue
            touched = (b["low"] <= edge + 0.15 * atr) if d == 1 else (b["high"] >= edge - 0.15 * atr)
            if touched and _body_ok(b, d, 0.4):
                anchor = (hi + lo) / 2 if p["sl"] == "mid" else (b["low"] if d == 1 else b["high"])
                out.append(_cand(ctx, i, d, anchor, lo, hi, atr))
                used.add(d)
                state = "WAIT"
    return out


def _prev_day_levels(bars):
    """Previous broker-server day high/low for every bar (server time)."""
    days, order = {}, []
    for b in bars:
        k = b["time"] // 86400
        if k not in days:
            days[k] = [b["high"], b["low"]]
            order.append(k)
        else:
            days[k][0] = max(days[k][0], b["high"])
            days[k][1] = min(days[k][1], b["low"])
    prev, last = {}, None
    for k in order:
        prev[k] = days[last] if last is not None else None
        last = k
    return [prev[b["time"] // 86400] for b in bars]


def s03(ctx, p):
    """S02 sequence on the previous-day high/low alone (no confluence requirement).
    p: mode ('retest' = full S02 sequence | 'accept' = enter on acceptance close),
    max_bars_to_retest."""
    bars, out = ctx["entry"], []
    pdl = _prev_day_levels(bars)
    params = replay.engine_params("S02", ctx["profile"], {"max_bars_to_retest": p.get("max_bars_to_retest", 12)})
    eng = s02_oracle.new_engine({"canonical_symbol": ctx["symbol"], "timeframe": "X"}, params)
    for i, b in enumerate(bars):
        if not _live(ctx, i) or pdl[i] is None:
            continue
        bar = {k: b[k] for k in ("time", "open", "high", "low", "close", "atr")}
        before = eng["state"]
        if before in ("IDLE", "INVALIDATED", "EXPIRED"):
            level = None
            for lv in pdl[i]:
                if b["open"] <= lv < b["close"] or b["open"] >= lv > b["close"]:
                    level = lv
            if level is None:
                eng["last_processed_bar"] = bar["time"]
                continue
            s02_oracle.process_zone(eng, bar, level, level, params)
        else:
            s02_oracle.process_zone(eng, bar, eng["zone_low"], eng["zone_high"], params)
        d = eng["direction"]
        if p["mode"] == "accept" and eng["state"] == "ARMED" and before == "DETECTED":
            anchor = eng["key_level"] - d * 0.5 * eng["signal_atr"]
            out.append(_cand(ctx, i, d, anchor, eng["zone_low"], eng["zone_high"], eng["signal_atr"]))
            eng["state"] = "EXPIRED"
        elif p["mode"] == "retest" and eng["state"] == "TRIGGERED" and before != "TRIGGERED":
            out.append(_cand(ctx, i, d, eng["candidate"]["retest_extreme"], eng["zone_low"], eng["zone_high"],
                             eng["signal_atr"]))
    return out


def _ema(bars, period):
    k, e, out = 2.0 / (period + 1), None, []
    for b in bars:
        e = b["close"] if e is None else e + k * (b["close"] - e)
        out.append(e)
    return out


def s05(ctx, p):
    """p: ema (period), lookback (pullback bars), min_depth_atr, body."""
    bars, out = ctx["entry"], []
    ema = _ema(bars, p["ema"])
    cooldown = 0
    for i, b in enumerate(bars):
        if not _live(ctx, i):
            continue
        if cooldown > 0:
            cooldown -= 1
            continue
        structure = ctx["levels"][ctx["bar_level"][i]]["structure"]
        d = 1 if structure == "UP" else -1 if structure == "DOWN" else 0
        if d == 0:
            continue
        atr, lb = b["atr"], p["lookback"]
        window = bars[i - lb:i]
        touched = any((w["low"] <= ema[i - lb + k]) if d == 1 else (w["high"] >= ema[i - lb + k]) for k, w in enumerate(window))
        if not touched:
            continue
        swing = max(x["high"] for x in bars[i - 30:i]) if d == 1 else min(x["low"] for x in bars[i - 30:i])
        ext = min(x["low"] for x in window) if d == 1 else max(x["high"] for x in window)
        if d * (swing - ext) < p["min_depth_atr"] * atr:
            continue
        prev = bars[i - 1]
        trigger = (b["close"] > ema[i] and b["close"] > prev["high"]) if d == 1 else (b["close"] < ema[i] and b["close"] < prev["low"])
        if trigger and _body_ok(b, d, p["body"]):
            zl, zh = (ext, ema[i]) if d == 1 else (ema[i], ext)
            out.append(_cand(ctx, i, d, ext, min(zl, zh), max(zl, zh), atr))
            cooldown = lb
    return out


def s06(ctx, p):
    """p: box (bars), max_box_atr, contraction (ATR now / ATR 48 bars ago), mode
    ('immediate' | 'confirm'), sl ('mid' | 'far')."""
    bars, out = ctx["entry"], []
    pending = None
    for i, b in enumerate(bars):
        if not _live(ctx, i):
            continue
        atr = b["atr"]
        if pending is not None:
            d, bh, bl = pending
            pending = None
            edge = bh if d == 1 else bl
            if d * (b["close"] - edge) > 0:
                anchor = (bh + bl) / 2 if p["sl"] == "mid" else (bl if d == 1 else bh)
                out.append(_cand(ctx, i, d, anchor, bl, bh, atr))
            continue
        n = p["box"]
        box = bars[i - n:i]
        bh, bl = max(x["high"] for x in box), min(x["low"] for x in box)
        ref = bars[i - 1]["atr"]
        old = bars[i - 48]["atr"]
        if ref <= 0 or old <= 0 or (bh - bl) > p["max_box_atr"] * ref or ref > p["contraction"] * old:
            continue
        for d, edge in ((1, bh), (-1, bl)):
            if d * (b["close"] - edge) > 0.10 * ref and _body_ok(b, d, 0.5) and (b["high"] - b["low"]) >= 1.0 * ref:
                if p["mode"] == "immediate":
                    anchor = (bh + bl) / 2 if p["sl"] == "mid" else (bl if d == 1 else bh)
                    out.append(_cand(ctx, i, d, anchor, bl, bh, ref))
                else:
                    pending = (d, bh, bl)
                break
    return out


DETECTORS = {"S01": s01, "S03": s03, "S05": s05, "S06": s06}
GRIDS = {
    "S01": {"end_hour": [10, 12], "mode": ["accept", "retest"], "sl": ["mid", "breakbar"], "max_range_atr": [12, 24]},
    "S03": {"mode": ["accept", "retest"], "max_bars_to_retest": [6, 12]},
    "S05": {"ema": [20, 50], "lookback": [6, 12], "min_depth_atr": [1.0, 2.0], "body": [0.4, 0.55]},
    "S06": {"box": [12, 24], "max_box_atr": [2.0, 3.0], "contraction": [0.7, 0.85], "mode": ["immediate", "confirm"],
            "sl": ["mid", "far"]},
}
PROFILES = {"S01": ["SCALP"], "S03": ["SCALP", "SWING"], "S05": ["SCALP", "SWING"], "S06": ["SCALP", "SWING"]}
