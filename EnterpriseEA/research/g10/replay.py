"""G10 offline replay: S02/S04 engines over a cached context, then trade evaluation.

Two evaluation models:
  "ea"  mirrors EEA_SetupReplayEvaluate (market at trigger close, TP or SL first, bid
        bars, stop touch wins inside a bar). Used to check parity with the EA replay.
  "tm"  adds what the live path really does: ask/bid spread on entry and exits, and the
        Trade Manager profile (partial, break-even, trailing, structure exit, time stop).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Tests"))
import s02_oracle  # noqa: E402
import s04_oracle  # noqa: E402

S02_BASE = {
    "SCALP": {"config_version": "s02-v1-scalp-0.1.0", "break_buffer_atr": 0.10, "acceptance_buffer_atr": 0.0,
              "retest_tolerance_atr": 0.15, "invalidation_buffer_atr": 0.10, "hold_buffer_atr": 0.0,
              "max_bars_to_accept": 2, "max_bars_to_retest": 12, "max_bars_for_reaction": 3,
              "candidate_ttl_bars": 2, "break_body_ratio": 0.50, "trigger_body_ratio": 0.40,
              "trigger_progress_atr": 0.05, "fail_on_close_inside_zone": True},
}
S02_BASE["SWING"] = dict(S02_BASE["SCALP"], config_version="s02-v1-swing-0.1.0", max_bars_to_retest=10)

TM = {  # EEA_TradeProfileFor
    "SCALP": {"be_at_r": 1.0, "partial_at_r": 1.0, "partial_fraction": 0.5, "trail_start_r": 1.5,
              "trail": "ATR", "trail_atr_mult": 1.0, "structure_bars": 0, "timeout_bars": 36},
    "SWING": {"be_at_r": 1.0, "partial_at_r": 1.5, "partial_fraction": 0.33, "trail_start_r": 2.0,
              "trail": "STRUCTURE", "trail_atr_mult": 0.0, "structure_bars": 5, "timeout_bars": 120},
}
HORIZON = {"SCALP": 48, "SWING": 72}
MIN_RR = {"SCALP": 1.5, "SWING": 2.0}


def engine_params(setup: str, profile: str, over: dict | None = None) -> dict:
    if setup == "S02":
        p = dict(S02_BASE[profile])
    else:
        p = s04_oracle.config(profile)
    p.update(over or {})
    return p


def candidates(ctx: dict, setup: str, params: dict) -> list[dict]:
    """Every TRIGGERED transition with what the evaluation needs."""
    entry, bar_level, levels = ctx["entry"], ctx["bar_level"], ctx["levels"]
    out = []
    if setup == "S02":
        eng = s02_oracle.new_engine({"canonical_symbol": ctx["symbol"], "timeframe": "X"}, params)
    else:
        eng = s04_oracle.Engine(params)
    for i, b in enumerate(entry):
        if b["time"] < ctx["from_server"] or i < 14:
            continue
        lvl = levels.get(bar_level[i])
        if lvl is None or b["atr"] <= 0:
            continue
        bar = {"time": b["time"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "atr": b["atr"]}
        if setup == "S02":
            before = eng["state"]
            if before in ("IDLE", "INVALIDATED", "EXPIRED"):
                z = _pick(lvl["zones"], bar)
                if z is None:
                    eng["last_processed_bar"] = bar["time"]
                    continue
                s02_oracle.process_zone(eng, bar, z["low"], z["high"], params)
            else:
                s02_oracle.process_zone(eng, bar, eng["zone_low"], eng["zone_high"], params)
            if eng["state"] != "TRIGGERED" or before == "TRIGGERED":
                continue
            d, extreme = eng["direction"], eng["candidate"]["retest_extreme"]
            zl, zh, satr = eng["zone_low"], eng["zone_high"], eng["signal_atr"]
        else:
            before = eng.state
            if before in ("IDLE", "INVALIDATED", "EXPIRED"):
                z = _pick(lvl["zones"], bar)
                if z is None:
                    continue
                eng.step(bar, z["low"], z["high"])
            else:
                eng.step(bar, *eng.zone)
            if eng.state != "TRIGGERED" or before == "TRIGGERED":
                continue
            d, extreme = eng.direction, eng.extreme
            (zl, zh), satr = eng.zone, eng.atr
        out.append({"i": i, "time": b["time"], "direction": d, "extreme": extreme, "zone_low": zl, "zone_high": zh,
                    "signal_atr": satr, "points": lvl["points"], "structure": lvl["structure"]})
    return out


def _pick(zones, bar):
    for z in zones:
        if bar["open"] <= z["high"] < bar["close"]:
            return z
        if bar["open"] >= z["low"] > bar["close"]:
            return z
    return None


def structural_target(points, direction, entry, need):
    best = None
    for p in points:
        dist = direction * (p - entry)
        if dist < need:
            continue
        if best is None or dist < direction * (best - entry):
            best = p
    return best


def htf_aligned(structure: str, direction: int) -> bool:
    return not ((structure == "UP" and direction < 0) or (structure == "DOWN" and direction > 0))


def evaluate(ctx: dict, c: dict, setup: str, profile: str, model: str = "tm", trade: dict | None = None) -> dict:
    """trade: buffer_atr, min_rr, target ('structural' | 'fixed'), fixed_r, htf ('any' | 'aligned'),
    hours (None or (start_utc_hour, end_utc_hour))."""
    t = {"buffer_atr": 0.10, "min_rr": MIN_RR[profile], "target": "structural", "fixed_r": 2.0, "htf": "any",
         "hours": None, "tm": True}
    t.update(trade or {})
    bars, i, d = ctx["entry"], c["i"], c["direction"]
    point = ctx["point"]
    res = {"time": c["time"], "symbol": ctx["symbol"], "setup": setup, "profile": profile, "direction": d,
           "status": "EVALUATED", "r": 0.0, "mfe": 0.0, "mae": 0.0}
    if t["htf"] == "aligned" and not htf_aligned(c["structure"], d):
        res["status"] = "FILTER_HTF"
        return res
    if t["hours"] is not None:
        h = (bars[i]["utc"] // 3600) % 24
        s, e = t["hours"]
        if not (s <= h < e):
            res["status"] = "FILTER_HOURS"
            return res
    spread = bars[i]["spread"] * point
    entry = bars[i]["close"] + (spread if (model == "tm" and d == 1) else 0.0)
    buffer = max(t["buffer_atr"] * c["signal_atr"], 1.5 * spread)
    stop = c["extreme"] - buffer if d == 1 else c["extreme"] + buffer
    risk = d * (entry - stop)
    if c["extreme"] <= 0 or risk <= 0:
        res["status"] = "STRUCTURE_INVALID"
        return res
    need = risk
    if setup == "S04":
        far = c["zone_high"] if d == 1 else c["zone_low"]
        need = max(risk, d * (far - entry))
    if t["target"] == "fixed":
        target = entry + d * t["fixed_r"] * risk
        if setup == "S04" and d * (target - entry) < need:
            res["status"] = "NO_STRUCTURAL_TARGET"
            return res
    else:
        target = structural_target(c["points"], d, entry, need)
        if target is None:
            res["status"] = "NO_STRUCTURAL_TARGET"
            return res
    rr = d * (target - entry) / risk
    if rr < t["min_rr"]:
        res["status"] = "RR_TOO_LOW"
        return res
    res.update(entry=entry, stop=stop, target=target, rr=rr)
    if model == "ea":
        return _walk_ea(bars, i, d, entry, stop, target, risk, rr, HORIZON[profile], res)
    return _walk_tm(bars, i, d, entry, stop, target, risk, profile, c, point, res, t["tm"])


def _walk_ea(bars, i, d, entry, stop, target, risk, rr, horizon, res):
    last = min(len(bars) - 1, i + horizon)
    res["result"] = "OPEN"
    for b in range(i + 1, last + 1):
        fav = d * ((bars[b]["high"] if d == 1 else bars[b]["low"]) - entry) / risk
        adv = d * (entry - (bars[b]["low"] if d == 1 else bars[b]["high"])) / risk
        res["mfe"], res["mae"] = max(res["mfe"], fav), max(res["mae"], adv)
        if adv >= 1.0:
            res["result"], res["r"] = "SL", -1.0
            break
        if fav >= rr:
            res["result"], res["r"] = "TP", rr
            break
        if b == last:
            res["r"] = d * (bars[b]["close"] - entry) / risk
    return res


def _walk_tm(bars, i, d, entry, stop, target, risk, profile, c, point, res, manage):
    """Bar-level Trade Manager. Exits use the side the position closes on (bid for a long,
    ask = bid + spread for a short). A stop touch wins over a target touch in one bar."""
    p = TM[profile]
    open_frac, realized, sl = 1.0, 0.0, stop
    be = partial = trail = False
    zl, zh = c["zone_low"], c["zone_high"]
    n = 0
    res["result"] = "OPEN"
    limit = min(len(bars) - 1, i + p["timeout_bars"] * 3)
    for b in range(i + 1, limit + 1):
        n += 1
        bar = bars[b]
        sp = bar["spread"] * point if d == -1 else 0.0
        hi, lo, close = bar["high"] + sp, bar["low"] + sp, bar["close"] + sp
        if (d == 1 and lo <= sl) or (d == -1 and hi >= sl):
            realized += open_frac * d * (sl - entry) / risk
            res["result"] = "STOP_BE" if be or trail else "SL"
            open_frac = 0.0
            break
        if (d == 1 and hi >= target) or (d == -1 and lo <= target):
            realized += open_frac * d * (target - entry) / risk
            res["result"], open_frac = "TP", 0.0
            break
        fav = d * ((hi if d == 1 else lo) - entry) / risk
        res["mfe"] = max(res["mfe"], fav)
        res["mae"] = max(res["mae"], d * (entry - (lo if d == 1 else hi)) / risk)
        if not manage:
            continue
        # Bar close: structure exit and time stop, then the next management step.
        if not be and zl > 0 and ((d == 1 and close < zl) or (d == -1 and close > zh)):
            realized += open_frac * d * (close - entry) / risk
            res["result"], open_frac = "STRUCTURE_EXIT", 0.0
            break
        if n >= p["timeout_bars"] and not trail:
            realized += open_frac * d * (close - entry) / risk
            res["result"], open_frac = "TIME_STOP", 0.0
            break
        if not partial and res["mfe"] >= p["partial_at_r"]:
            realized += p["partial_fraction"] * p["partial_at_r"]
            open_frac -= p["partial_fraction"]
            partial = True
        elif not be and res["mfe"] >= p["be_at_r"]:
            sl = entry + d * bar["spread"] * point
            be = True
        elif trail or res["mfe"] >= p["trail_start_r"]:
            trail = True
            if p["trail"] == "ATR":
                level = bar["close"] - d * p["trail_atr_mult"] * bar["atr"]
            else:
                window = bars[max(0, b - p["structure_bars"] + 1): b + 1]
                ext = min(x["low"] for x in window) if d == 1 else max(x["high"] for x in window)
                level = ext - d * 0.1 * bar["atr"]
            if d * (level - entry) > 0 and d * (level - sl) >= 0.1 * risk:
                sl = level
    if open_frac > 0:
        realized += open_frac * d * (bars[limit]["close"] - entry) / risk
    res["r"] = realized
    return res


def summarize(rows: list[dict]) -> dict:
    taken = [r for r in rows if r["status"] == "EVALUATED"]
    n = len(taken)
    if n == 0:
        return {"n": 0, "exp": 0.0, "total": 0.0, "win": 0.0, "dd": 0.0}
    total, peak, dd, eq = 0.0, 0.0, 0.0, 0.0
    for r in sorted(taken, key=lambda x: x["time"]):
        eq += r["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        total += r["r"]
    return {"n": n, "exp": total / n, "total": total, "win": sum(1 for r in taken if r["r"] > 0) / n, "dd": dd}


def clone(x):
    return copy.deepcopy(x)
