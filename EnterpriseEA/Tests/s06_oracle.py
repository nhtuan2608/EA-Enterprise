"""Python mirror of Setups/CompressionExpansion.mqh (S06 v1, SWING H1).

Bars are dicts with time, open, high, low, close, atr (oldest first). run() walks them the
way EEA_StrategyRuntimeScanZoneEngine feeds the engine and returns the TRIGGERED candidates.
"""
from __future__ import annotations

BOX_BARS = 12
MAX_BOX_ATR = 3.0
CONTRACTION = 0.85
CONTRACTION_LOOKBACK = 48
RELEASE_BUFFER_ATR = 0.10
RELEASE_BODY_RATIO = 0.50
RELEASE_MIN_RANGE_ATR = 1.0
TARGET_R = 3.0
ATR_PERIOD = 14
WARM = ATR_PERIOD + CONTRACTION_LOOKBACK


def body_ok(b, d, ratio):
    rng = b["high"] - b["low"]
    if rng <= 0:
        return False
    aligned = b["close"] > b["open"] if d > 0 else b["close"] < b["open"]
    return aligned and abs(b["close"] - b["open"]) >= ratio * rng


def compressed(box_low, box_high, ref_atr, old_atr):
    if ref_atr <= 0 or old_atr <= 0 or box_high < box_low:
        return False
    return box_high - box_low <= MAX_BOX_ATR * ref_atr and ref_atr <= CONTRACTION * old_atr


def release_direction(b, box_low, box_high, ref_atr):
    if b["high"] - b["low"] < RELEASE_MIN_RANGE_ATR * ref_atr:
        return 0
    if b["close"] - box_high > RELEASE_BUFFER_ATR * ref_atr and body_ok(b, 1, RELEASE_BODY_RATIO):
        return 1
    if box_low - b["close"] > RELEASE_BUFFER_ATR * ref_atr and body_ok(b, -1, RELEASE_BODY_RATIO):
        return -1
    return 0


class Engine:
    def __init__(self):
        self.state = "IDLE"
        self.direction = 0
        self.zone_low = self.zone_high = self.key_level = self.far_edge = 0.0
        self.signal_atr = 0.0

    def step(self, b, box_low, box_high, ref_atr, old_atr):
        """Returns the triggered candidate of this bar, or None."""
        if self.state in ("TRIGGERED", "EXPIRED"):
            self.__init__()
        if self.state == "RELEASED":
            if self.direction * (b["close"] - self.key_level) > 0:
                self.state = "TRIGGERED"
                self.signal_atr = b["atr"]
                return {"time": b["time"], "direction": self.direction, "anchor": self.far_edge,
                        "zone_low": self.zone_low, "zone_high": self.zone_high, "signal_atr": b["atr"]}
            self.state = "EXPIRED"
            return None
        if not compressed(box_low, box_high, ref_atr, old_atr):
            return None
        d = release_direction(b, box_low, box_high, ref_atr)
        if d == 0:
            return None
        self.state, self.direction = "RELEASED", d
        self.zone_low, self.zone_high = box_low, box_high
        self.key_level = box_high if d > 0 else box_low
        self.far_edge = box_low if d > 0 else box_high
        self.signal_atr = ref_atr
        return None


def run(bars, first=WARM):
    eng, out = Engine(), []
    for i in range(max(first, WARM), len(bars)):
        box = bars[i - BOX_BARS:i]
        hi, lo = max(x["high"] for x in box), min(x["low"] for x in box)
        c = eng.step(bars[i], lo, hi, bars[i - 1]["atr"], bars[i - CONTRACTION_LOOKBACK]["atr"])
        if c is not None:
            c["i"] = i
            out.append(c)
    return out


def plan(c, entry, spread):
    """Live plan (EEA_ControlledLiveResolveV1Plan for S06): stop beyond the far edge, 3R target."""
    d = c["direction"]
    buffer = max(0.10 * c["signal_atr"], 1.5 * spread)
    stop = c["anchor"] - buffer if d == 1 else c["anchor"] + buffer
    risk = abs(entry - stop)
    return {"stop": stop, "target": entry + d * TARGET_R * risk, "risk": risk}
