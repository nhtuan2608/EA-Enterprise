"""Offline reference oracle for S02 v1 Location, HTF structure and O-04 limits.

Mirrors Market/ConfluenceLevels.mqh and Risk/RiskLimitsProfile.mqh. Passing these
checks is design evidence only, not MQL5 runtime proof.
"""
from __future__ import annotations

FIRM_RATES = {"FTMO_1_STEP": (3.0, 10.0), "FTMO_2_STEP": (5.0, 10.0), "BALANCE_BASED_FTMO_V1": (5.0, 10.0)}


def risk_limits(policy_id: str) -> dict | None:
    if policy_id not in FIRM_RATES:
        return None
    daily, overall = (x / 100.0 for x in FIRM_RATES[policy_id])
    internal_daily = min(0.4 * daily, 0.02)
    per_trade = internal_daily / 4.0
    return {
        "firm_daily": daily,
        "firm_overall": overall,
        "internal_daily": internal_daily,
        "per_trade": per_trade,
        "total_open": internal_daily,
        "currency_exposure": 2.5 * per_trade,
        "internal_weekly": min(2.0 * internal_daily, 0.4 * overall),
        "safety_buffer": per_trade,
        "htf_counter_trend_modifier": 0.5,
        "min_margin_level_percent": 300.0,
        "max_correlated_trades": 2,
    }


def trade_risk_money(limits: dict, equity: float, initial_capital: float, modifier: float) -> float:
    if equity <= 0 or initial_capital <= 0 or limits["per_trade"] <= 0:
        return 0.0
    bounded = max(0.0, min(1.0, modifier))
    return min(limits["per_trade"] * equity, limits["per_trade"] * initial_capital) * bounded


def range_extremes(bars: list[dict], start: int, end: int):
    inside = [b for b in bars if start <= b["time"] < end]
    if not inside:
        return None
    high = max(inside, key=lambda b: b["high"])  # first maximum, like the MQL strict '>'
    low = min(inside, key=lambda b: b["low"])
    return high["high"], high["time"], low["low"], low["time"]


def levels_previous_day(bars, now_server):
    today = (now_server // 86400) * 86400
    found = range_extremes(bars, today - 86400, today)
    if not found:
        return []
    h, ht, l, lt = found
    return [("PREV_DAY", "HIGH", h, ht), ("PREV_DAY", "LOW", l, lt)]


def week_start(server_time: int) -> int:
    day = server_time // 86400
    return (day - (day + 3) % 7) * 86400


def levels_previous_week(bars, now_server):
    week = week_start(now_server)
    found = range_extremes(bars, week - 7 * 86400, week)
    if not found:
        return []
    h, ht, l, lt = found
    return [("PREV_WEEK", "HIGH", h, ht), ("PREV_WEEK", "LOW", l, lt)]


def levels_session(bars, now_server, offset, start_hour, end_hour):
    now_utc = now_server - offset
    day = (now_utc // 86400) * 86400
    end = day + end_hour * 3600
    if end > now_utc:
        day -= 86400
        end -= 86400
    start = day + start_hour * 3600
    found = range_extremes(bars, start + offset, end + offset)
    if not found:
        return []
    h, ht, l, lt = found
    return [("SESSION", "HIGH", h, ht), ("SESSION", "LOW", l, lt)]


def is_fractal_high(bars, i, wing):
    if i - wing < 0 or i + wing >= len(bars):
        return False
    return all(bars[i - k]["high"] < bars[i]["high"] and bars[i + k]["high"] <= bars[i]["high"] for k in range(1, wing + 1))


def is_fractal_low(bars, i, wing):
    if i - wing < 0 or i + wing >= len(bars):
        return False
    return all(bars[i - k]["low"] > bars[i]["low"] and bars[i + k]["low"] >= bars[i]["low"] for k in range(1, wing + 1))


def levels_swings(bars, wing, lookback):
    out = []
    n = len(bars)
    for i in range(max(wing, n - lookback), n - wing):
        if is_fractal_high(bars, i, wing) and not any(b["close"] > bars[i]["high"] for b in bars[i + 1:]):
            out.append(("SWING", "HIGH", bars[i]["high"], bars[i]["time"]))
        if is_fractal_low(bars, i, wing) and not any(b["close"] < bars[i]["low"] for b in bars[i + 1:]):
            out.append(("SWING", "LOW", bars[i]["low"], bars[i]["time"]))
    return out


def build_zones(points, tolerance, max_width, min_sources=2):
    ordered = sorted(points, key=lambda p: p[2])  # stable, like the MQL insertion sort
    zones = []
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and ordered[end + 1][2] - ordered[end][2] <= tolerance:
            end += 1
        members = ordered[start:end + 1]
        used_sources, used_times = [], []
        for source, _, _, _ in members:
            if source in used_sources:
                continue
            pick = next((m for m in members if m[0] == source and m[3] not in used_times), None)
            if pick is None:
                continue
            used_sources.append(source)
            used_times.append(pick[3])
        low, high = members[0][2], members[-1][2]
        if len(used_sources) < min_sources:
            reason, ok = "CONFLUENCE_INSUFFICIENT", False
        elif high - low > max_width:
            reason, ok = "ZONE_TOO_WIDE", False
        else:
            reason, ok = "CONFLUENCE_ZONE", True
        zones.append({"low": low, "high": high, "members": len(members),
                      "independent_sources": len(used_sources), "sources": "+".join(used_sources),
                      "qualified": ok, "reason": reason})
        start = end + 1
    return zones


def htf_structure(bars, wing):
    highs, lows = [], []
    for i in range(len(bars) - 1 - wing, wing - 1, -1):
        if len(highs) >= 2 and len(lows) >= 2:
            break
        if len(highs) < 2 and is_fractal_high(bars, i, wing):
            highs.append(bars[i]["high"])
        if len(lows) < 2 and is_fractal_low(bars, i, wing):
            lows.append(bars[i]["low"])
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    if highs[0] > highs[1] and lows[0] > lows[1]:
        return "UP"
    if highs[0] < highs[1] and lows[0] < lows[1]:
        return "DOWN"
    return "NEUTRAL"


def htf_risk_modifier(structure: str, direction: int, counter: float = 0.5) -> float:
    if (structure == "UP" and direction < 0) or (structure == "DOWN" and direction > 0):
        return max(0.0, min(1.0, counter))
    return 1.0
