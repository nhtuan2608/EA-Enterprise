"""Offline reference oracle for the S04 Failed Break engine (Setups/FailedBreak.mqh).

Design: docs/superpowers/specs/2026-10-04-s04-failed-break-v1-design.md. Passing these
checks is design evidence only, not MQL5 runtime proof.
"""
from __future__ import annotations

ACCEPT_CLOSES = 2


def config(profile: str = "SCALP") -> dict:
    return {
        "version": "s04-v1-swing-0.1.0" if profile == "SWING" else "s04-v1-scalp-0.1.0",
        "break_buffer_atr": 0.10, "break_body_ratio": 0.50,
        "return_window": 3, "trigger_window": 3,
        "trigger_body_ratio": 0.40, "trigger_progress_atr": 0.05,
        "invalidation_buffer_atr": 0.10, "ttl": 2,
    }


def body_ok(b: dict, direction: int, ratio: float) -> bool:
    rng = b["high"] - b["low"]
    if rng <= 0:
        return False
    aligned = b["close"] > b["open"] if direction > 0 else b["close"] < b["open"]
    return aligned and abs(b["close"] - b["open"]) >= ratio * rng


class Engine:
    def __init__(self, cfg: dict):
        self.c = cfg
        self.reset()

    def reset(self):
        self.state = "IDLE"
        self.direction = 0
        self.key = 0.0
        self.extreme = 0.0
        self.invalidation = 0.0
        self.returned_ref = 0.0
        self.atr = 0.0
        self.since_break = 0
        self.beyond = 0
        self.since_return = 0
        self.age = 0
        self.zone = (0.0, 0.0)
        self.reason = ""

    def step(self, b: dict, zone_low: float, zone_high: float) -> str:
        c = self.c
        if self.state in ("INVALIDATED", "EXPIRED"):
            self.reset()
        if self.state == "IDLE":
            if b["close"] > zone_high + c["break_buffer_atr"] * b["atr"] and body_ok(b, 1, c["break_body_ratio"]):
                self._start(b, zone_low, zone_high, 1)
            elif b["close"] < zone_low - c["break_buffer_atr"] * b["atr"] and body_ok(b, -1, c["break_body_ratio"]):
                self._start(b, zone_low, zone_high, -1)
            return self.state
        bd = -self.direction
        lost = b["close"] > self.invalidation if bd > 0 else b["close"] < self.invalidation
        beyond = b["close"] > self.key if bd > 0 else b["close"] < self.key
        if self.state in ("BREAK_ATTEMPT", "RETURNED"):
            self.extreme = max(self.extreme, b["high"]) if bd > 0 else min(self.extreme, b["low"])
            self.beyond = self.beyond + 1 if beyond else 0
        if self.state == "BREAK_ATTEMPT":
            self.since_break += 1
            if lost:
                self._end("INVALIDATED", "THESIS_INVALIDATED")
            elif not beyond:
                self.returned_ref = b["low"] if bd > 0 else b["high"]
                self.since_return = 0
                self.state, self.reason = "RETURNED", "CLOSED_BACK_INSIDE_ZONE"
            elif self.beyond >= ACCEPT_CLOSES:
                self._end("INVALIDATED", "BREAK_ACCEPTED")
            elif self.since_break >= c["return_window"]:
                self._end("EXPIRED", "NO_RETURN_INSIDE")
            if self.state in ("BREAK_ATTEMPT", "RETURNED"):
                self.invalidation = self.extreme + bd * c["invalidation_buffer_atr"] * self.atr
            return self.state
        if self.state == "RETURNED":
            self.since_return += 1
            d = self.direction
            prog = c["trigger_progress_atr"] * self.atr
            trig = (b["close"] < b["open"] and b["close"] < self.returned_ref - prog) if d < 0 else \
                   (b["close"] > b["open"] and b["close"] > self.returned_ref + prog)
            trig = trig and body_ok(b, d, c["trigger_body_ratio"])
            if lost:
                self._end("INVALIDATED", "THESIS_INVALIDATED")
            elif self.beyond >= ACCEPT_CLOSES:
                self._end("INVALIDATED", "BREAK_ACCEPTED")
            elif trig:
                self.state, self.reason, self.age = "TRIGGERED", "FAILED_BREAK_REJECTION_CONFIRMED", 0
            elif self.since_return >= c["trigger_window"]:
                self._end("EXPIRED", "TRIGGER_EXPIRED")
            if self.state == "RETURNED":
                self.invalidation = self.extreme + bd * c["invalidation_buffer_atr"] * self.atr
            return self.state
        if self.state == "TRIGGERED":
            self.age += 1
            if self.age >= c["ttl"]:
                self._end("EXPIRED", "CANDIDATE_TTL_REACHED")
        return self.state

    def _start(self, b, zl, zh, bd):
        self.direction = -bd
        self.key = zh if bd > 0 else zl
        self.zone = (zl, zh)
        self.atr = b["atr"]
        self.extreme = b["high"] if bd > 0 else b["low"]
        self.invalidation = self.extreme + bd * self.c["invalidation_buffer_atr"] * b["atr"]
        self.since_break = self.beyond = self.since_return = 0
        self.state, self.reason = "BREAK_ATTEMPT", "BREAK_ATTEMPT_ABOVE_ZONE" if bd > 0 else "BREAK_ATTEMPT_BELOW_ZONE"

    def _end(self, state, reason):
        self.state, self.reason = state, reason


def plan(direction: int, extreme: float, atr: float, spread: float, entry: float,
         zone: tuple, levels: list[float]) -> dict | None:
    """SL beyond the failed-break extreme, TP the nearest level beyond the far zone edge and >= 1R."""
    buffer = max(0.10 * atr, 1.5 * spread)
    stop = extreme + buffer if direction < 0 else extreme - buffer
    risk = abs(entry - stop)
    far = zone[0] if direction < 0 else zone[1]
    need = max(risk, direction * (far - entry))
    best = None
    for p in levels:
        dist = direction * (p - entry)
        if dist < need:
            continue
        if best is None or dist < direction * (best - entry):
            best = p
    if best is None:
        return None
    return {"stop": stop, "target": best, "risk": risk}
