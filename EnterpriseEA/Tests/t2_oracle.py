"""G38 T2 oracle: Python mirror of Setups/DonchianTrend.mqh and EEA_StrategyRuntimeScanT2Engine.

run(h4, d1) walks closed H4 bars like the EA: the channel is the CHANNEL closed bars before each bar,
the ATR is the simple mean of the 14 true ranges ending at the bar, and the D1 side comes from the
EEA_T2_DAILY_BARS daily bars the EA would copy at that bar (EMA200 seeded with the first of them,
the previous closed day's close against it).
"""
CHANNEL = 60
STOP_ATR = 2.0
TRAIL_ATR = 3.0
EMA_DAYS = 200
DAILY_BARS = 1000
ATR_PERIOD = 14


def atr_at(bars, b, period=ATR_PERIOD):
    if b < period:
        return 0.0
    s = 0.0
    for i in range(b - period + 1, b + 1):
        pc = bars[i - 1]["close"]
        s += max(bars[i]["high"], pc) - min(bars[i]["low"], pc)
    return s / period


def daily_side(daily, bar_time):
    """EEA_StrategyRuntimeT2SideAt over the DAILY_BARS daily bars before the bar's day."""
    day_start = bar_time - bar_time % 86400
    closed = [d for d in daily if d["time"] < day_start][-DAILY_BARS:]
    if len(closed) < EMA_DAYS:
        return 0
    k = 2.0 / (EMA_DAYS + 1)
    e = closed[0]["close"]
    for d in closed[1:]:
        e = e + k * (d["close"] - e)
    c = closed[-1]["close"]
    return 1 if c > e else (-1 if c < e else 0)


def direction(close, lo, hi, side):
    if close > hi and side == 1:
        return 1
    if close < lo and side == -1:
        return -1
    return 0


MOMENTUM_QUARTER = 0.25


def momentum_close(bar, atr, d):
    """G43/G44 EEA_T2MomentumClose: range of at least the ATR, close in the quarter on the side of d."""
    rng = bar["high"] - bar["low"]
    if rng <= 0 or atr <= 0 or rng < atr:
        return False
    return bar["close"] >= bar["high"] - MOMENTUM_QUARTER * rng if d > 0 else bar["close"] <= bar["low"] + MOMENTUM_QUARTER * rng


def run(h4, daily, first=None, momentum=False):
    """Triggered candidates: dicts with i, direction, stop anchor, channel and ATR.

    momentum=True: InpT2MomentumFilter, the signal bar or the bar before closes with momentum in d."""
    out = []
    start = max(CHANNEL, ATR_PERIOD + 1) if first is None else first
    for b in range(start, len(h4)):
        win = h4[b - CHANNEL:b]
        hi, lo = max(x["high"] for x in win), min(x["low"] for x in win)
        atr = atr_at(h4, b)
        if atr <= 0:
            continue
        d = direction(h4[b]["close"], lo, hi, daily_side(daily, h4[b]["time"]))
        if d and momentum and not (momentum_close(h4[b], atr, d) or momentum_close(h4[b - 1], atr_at(h4, b - 1), d)):
            d = 0
        if d:
            out.append({"i": b, "direction": d, "anchor": h4[b]["close"] - d * STOP_ATR * atr,
                        "channel": (lo, hi), "atr": atr})
    return out
