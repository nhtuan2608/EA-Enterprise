"""Offline reference oracle only; this is not a second EA runtime."""
from __future__ import annotations

import json


IDLE, DETECTED, ARMED, RETESTING, TRIGGERED, INVALIDATED, EXPIRED = (
    "IDLE", "DETECTED", "ARMED", "RETESTING", "TRIGGERED", "INVALIDATED", "EXPIRED"
)
TERMINAL = {INVALIDATED, EXPIRED}


def new_engine(identity: dict, config: dict) -> dict:
    return {
        "canonical_symbol": identity["canonical_symbol"],
        "timeframe": identity["timeframe"],
        "config_version": config["config_version"],
        "state": IDLE,
        "direction": 0,
        "last_processed_bar": 0,
        "breakout_bar": 0,
        "key_level": 0.0,
        "signal_atr": 0.0,
        "invalidation_price": 0.0,
        "retest_close": 0.0,
        "bars_since_break": 0,
        "bars_since_acceptance": 0,
        "bars_since_retest": 0,
        "candidate": None,
    }


def _event(engine: dict, time: int, event_type: str, reason: str, before: str | None = None) -> dict:
    candidate = engine["candidate"]
    return {
        "time": time,
        "event": event_type,
        "state_before": before or engine["state"],
        "state": engine["state"],
        "reason": reason,
        "candidate_id": candidate["candidate_id"] if candidate else "",
        "canonical_symbol": engine["canonical_symbol"],
        "timeframe": engine["timeframe"],
        "config_version": engine["config_version"],
    }


def process(engine: dict, bar: dict, key_level: float, config: dict) -> dict:
    when = bar["time"]
    if when == engine["last_processed_bar"]:
        return _event(engine, when, "BAR_IGNORED", "DUPLICATE_CLOSED_BAR")
    if when < engine["last_processed_bar"]:
        return _event(engine, when, "BAR_IGNORED", "OUT_OF_ORDER_CLOSED_BAR")

    if engine["state"] in TERMINAL:
        last_processed = engine["last_processed_bar"]
        keep = {k: engine[k] for k in ("canonical_symbol", "timeframe", "config_version")}
        engine.clear()
        engine.update(new_engine({"canonical_symbol": keep["canonical_symbol"], "timeframe": keep["timeframe"]},
                                 {"config_version": keep["config_version"]}))
        engine["last_processed_bar"] = last_processed

    before = engine["state"]
    engine["last_processed_bar"] = when
    atr = bar["atr"]
    direction = engine["direction"]

    def transition(state: str, event: str, reason: str) -> dict:
        engine["state"] = state
        if engine["candidate"] is not None:
            engine["candidate"]["state"] = state
            engine["candidate"]["reason_code"] = reason
        return _event(engine, when, event, reason, before)

    if engine["state"] == IDLE:
        buffer = config["break_buffer_atr"] * atr
        if bar["close"] > key_level + buffer:
            direction = engine["direction"] = 1
            reason = "BREAK_CLOSED_ABOVE_KEY"
        elif bar["close"] < key_level - buffer:
            direction = engine["direction"] = -1
            reason = "BREAK_CLOSED_BELOW_KEY"
        else:
            return _event(engine, when, "NO_TRANSITION", "WAITING_FOR_BREAK", before)
        engine["key_level"] = key_level
        engine["signal_atr"] = atr
        engine["breakout_bar"] = when
        engine["invalidation_price"] = key_level - direction * config["invalidation_buffer_atr"] * atr
        symbol, timeframe, version = engine["canonical_symbol"], engine["timeframe"], engine["config_version"]
        engine["candidate"] = {
            "candidate_id": f"S02-{symbol}-{timeframe}-{version}-{when}",
            "setup_id": "S02",
            "direction": "LONG" if direction > 0 else "SHORT",
            "state": DETECTED,
            "canonical_symbol": symbol,
            "timeframe": timeframe,
            "config_version": version,
            "key_level": key_level,
            "invalidation_price": engine["invalidation_price"],
            "detected_at": when,
            "triggered_at": None,
            "expires_after_bars": config["candidate_ttl_bars"],
            "age_after_trigger_bars": 0,
            "reason_code": reason,
        }
        return transition(DETECTED, "BREAK_DETECTED", reason)

    if engine["state"] == DETECTED:
        engine["bars_since_break"] += 1
        accepted = (bar["close"] > engine["key_level"] + config["acceptance_buffer_atr"] * engine["signal_atr"]
                    if direction > 0 else
                    bar["close"] < engine["key_level"] - config["acceptance_buffer_atr"] * engine["signal_atr"])
        failed = bar["close"] < engine["invalidation_price"] if direction > 0 else bar["close"] > engine["invalidation_price"]
        if failed:
            return transition(INVALIDATED, "BREAK_INVALIDATED", "BREAK_REJECTED_BACK_THROUGH_INVALIDATION")
        if accepted:
            engine["bars_since_acceptance"] = 0
            return transition(ARMED, "BREAK_ACCEPTED", "ACCEPTANCE_CLOSED_BEYOND_KEY")
        if engine["bars_since_break"] >= config["max_bars_to_accept"]:
            return transition(EXPIRED, "SETUP_EXPIRED", "ACCEPTANCE_NOT_CONFIRMED")
        return _event(engine, when, "NO_TRANSITION", "WAITING_FOR_ACCEPTANCE", before)

    if engine["state"] == ARMED:
        engine["bars_since_acceptance"] += 1
        failed = bar["close"] < engine["invalidation_price"] if direction > 0 else bar["close"] > engine["invalidation_price"]
        if failed:
            return transition(INVALIDATED, "RETEST_INVALIDATED", "LEVEL_LOST_BEFORE_RETEST")
        tolerance = config["retest_tolerance_atr"] * engine["signal_atr"]
        touched = (bar["low"] <= engine["key_level"] + tolerance and bar["high"] >= engine["key_level"] - tolerance
                   if direction > 0 else
                   bar["high"] >= engine["key_level"] - tolerance and bar["low"] <= engine["key_level"] + tolerance)
        if touched:
            engine["retest_close"] = bar["close"]
            engine["bars_since_retest"] = 0
            return transition(RETESTING, "RETEST_TOUCHED", "RETEST_ZONE_TOUCHED")
        if engine["bars_since_acceptance"] >= config["max_bars_to_retest"]:
            return transition(EXPIRED, "SETUP_EXPIRED", "NO_RETEST_WITHIN_WINDOW")
        return _event(engine, when, "NO_TRANSITION", "WAITING_FOR_RETEST", before)

    if engine["state"] == RETESTING:
        engine["bars_since_retest"] += 1
        failed = bar["close"] < engine["invalidation_price"] if direction > 0 else bar["close"] > engine["invalidation_price"]
        reaction = (bar["close"] > engine["key_level"] + config["hold_buffer_atr"] * engine["signal_atr"] and
                    bar["close"] > bar["open"] and bar["close"] > engine["retest_close"] if direction > 0 else
                    bar["close"] < engine["key_level"] - config["hold_buffer_atr"] * engine["signal_atr"] and
                    bar["close"] < bar["open"] and bar["close"] < engine["retest_close"])
        if failed:
            return transition(INVALIDATED, "RETEST_INVALIDATED", "RETEST_CLOSED_THROUGH_INVALIDATION")
        if reaction:
            engine["candidate"]["triggered_at"] = when
            engine["candidate"]["age_after_trigger_bars"] = 0
            return transition(TRIGGERED, "CANDIDATE_TRIGGERED", "RETEST_HOLD_REACTION_CONFIRMED")
        if engine["bars_since_retest"] >= config["max_bars_for_reaction"]:
            return transition(EXPIRED, "SETUP_EXPIRED", "HOLD_REACTION_TIMEOUT")
        return _event(engine, when, "NO_TRANSITION", "WAITING_FOR_HOLD_REACTION", before)

    if engine["state"] == TRIGGERED:
        engine["candidate"]["age_after_trigger_bars"] += 1
        if engine["candidate"]["age_after_trigger_bars"] >= engine["candidate"]["expires_after_bars"]:
            return transition(EXPIRED, "CANDIDATE_EXPIRED", "CANDIDATE_TTL_REACHED")
        return _event(engine, when, "CANDIDATE_PENDING", "CANDIDATE_TTL_ACTIVE", before)
    return _event(engine, when, "NO_TRANSITION", "WAITING_FOR_BREAK", before)


def checkpoint(engine: dict) -> dict:
    """JSON round-trip used solely to compare restart parity in the oracle."""
    return json.loads(json.dumps(engine, sort_keys=True))
