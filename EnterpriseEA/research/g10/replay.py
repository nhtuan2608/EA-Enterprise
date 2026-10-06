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
S02_BASE["SWING4"] = S02_BASE["SWING"]   # G35: same engine on H4 entries

TM = {  # EEA_TradeProfileFor
    "SCALP": {"be_at_r": 1.0, "partial_at_r": 1.0, "partial_fraction": 0.5, "trail_start_r": 1.5,
              "trail": "ATR", "trail_atr_mult": 1.0, "structure_bars": 0, "timeout_bars": 36},
    "SWING": {"be_at_r": 1.0, "partial_at_r": 1.5, "partial_fraction": 0.33, "trail_start_r": 2.0,
              "trail": "STRUCTURE", "trail_atr_mult": 0.0, "structure_bars": 5, "timeout_bars": 120},
}
TM["SWING4"] = TM["SWING"]   # the EA manages a trade on its own timeframe's bars
HORIZON = {"SCALP": 48, "SWING": 72, "SWING4": 72}
MIN_RR = {"SCALP": 1.5, "SWING": 2.0, "SWING4": 2.0}


def engine_params(setup: str, profile: str, over: dict | None = None) -> dict:
    if setup == "S02":
        p = dict(S02_BASE[profile])
    else:
        p = s04_oracle.config("SWING" if profile == "SWING4" else profile)
    p.update(over or {})
    return p


def candidates(ctx: dict, setup: str, params: dict) -> list[dict]:
    """Every TRIGGERED transition with what the evaluation needs."""
    """S02 also yields LIMIT opportunities (kind LIMIT): while ARMED, HTF aligned and price at
    least 0.25 ATR beyond the zone edge, the live path places a LIMIT at the edge
    (EEA_S02SelectEntryMode / EEA_ControlledLiveResolveV1Plan)."""
    entry, bar_level, levels = ctx["entry"], ctx["bar_level"], ctx["levels"]
    out = []
    open_limits = {}
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
                    _close_limits(open_limits, eng, i)
                    continue
                s02_oracle.process_zone(eng, bar, z["low"], z["high"], params)
            else:
                s02_oracle.process_zone(eng, bar, eng["zone_low"], eng["zone_high"], params)
            _close_limits(open_limits, eng, i)
            key = eng["breakout_bar"]
            if eng["state"] == "ARMED" and key not in open_limits and htf_aligned(lvl["structure"], eng["direction"]):
                d = eng["direction"]
                edge = eng["zone_high"] if d == 1 else eng["zone_low"]
                if d * (b["close"] - edge) >= 0.25 * eng["signal_atr"]:
                    lim = {"kind": "LIMIT", "i": i, "time": b["time"], "breakout": key, "direction": d, "edge": edge,
                           "extreme": eng["zone_low"] if d == 1 else eng["zone_high"],
                           "zone_low": eng["zone_low"], "zone_high": eng["zone_high"], "signal_atr": eng["signal_atr"],
                           "points": lvl["points"], "structure": lvl["structure"], "invalid_at": None,
                           "bars_left": params["max_bars_to_retest"] - eng["bars_since_acceptance"] + params["max_bars_for_reaction"]}
                    open_limits[key] = lim
                    out.append(lim)
            if eng["state"] != "TRIGGERED" or before == "TRIGGERED":
                continue
            d, extreme = eng["direction"], eng["candidate"]["retest_extreme"]
            zl, zh, satr = eng["zone_low"], eng["zone_high"], eng["signal_atr"]
            out.append({"kind": "MARKET", "i": i, "time": b["time"], "breakout": key, "direction": d, "extreme": extreme,
                        "zone_low": zl, "zone_high": zh, "signal_atr": satr, "points": lvl["points"],
                        "structure": lvl["structure"]})
            continue
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
        out.append({"kind": "MARKET", "i": i, "time": b["time"], "direction": d, "extreme": extreme, "zone_low": zl,
                    "zone_high": zh, "signal_atr": satr, "points": lvl["points"], "structure": lvl["structure"]})
    return out


def _close_limits(open_limits, eng, i):
    """A working LIMIT is cancelled at the close of the bar where its setup stops being valid."""
    for key, lim in open_limits.items():
        if lim["invalid_at"] is None and (key != eng["breakout_bar"] or eng["state"] in ("IDLE", "INVALIDATED", "EXPIRED")):
            lim["invalid_at"] = i


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
    factor = 1.0
    if t.get("news"):
        blocked, factor = news_status(ctx["symbol"], profile, bars[i]["utc"])
        if blocked:
            res["status"] = "FILTER_NEWS"
            return res
    spread = bars[i]["spread"] * point
    entry = bars[i]["close"] + (spread if (model == "tm" and d == 1) else 0.0)
    if c.get("kind") == "LIMIT":
        entry = c["edge"]
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
    res.update(entry=entry, stop=stop, target=target, rr=rr, kind=c.get("kind", "MARKET"))
    if model == "ea":
        return _walk_ea(bars, i, d, entry, stop, target, risk, rr, HORIZON[profile], res)
    start = i
    if c.get("kind") == "LIMIT":
        start = _limit_fill(bars, c, point)
        if start is None:
            res["status"] = "LIMIT_NOT_FILLED"
            return res
        res["fill_time"] = bars[start]["time"]
        # The fill bar can already reach the stop (stop touch wins).
        sp = bars[start]["spread"] * point if d == -1 else 0.0
        if (d == 1 and bars[start]["low"] <= stop) or (d == -1 and bars[start]["high"] + sp >= stop):
            res.update(result="SL", r=-1.0)
            return _apply_costs(ctx, res, risk, t, factor)
    _walk_tm(bars, start, d, entry, stop, target, risk, profile, c, point, res, t["tm"])
    return _apply_costs(ctx, res, risk, t, factor)


# Round-trip commission in price units per unit volume (assumption: raw-spread account,
# USD 6 per lot round trip on FX and gold, none on BTC). Set "costs": False to ignore.
COMMISSION = {"EURUSD": 0.00006, "GBPUSD": 0.00006, "USDJPY": 0.009, "XAUUSD": 0.06, "BTCUSD": 0.0,
              # G36: USD 6 per lot in the quote currency (approximate rates)
              "AUDUSD": 0.00006, "NZDUSD": 0.00006, "USDCAD": 0.000083, "USDCHF": 0.000048, "EURGBP": 0.000045,
              "EURJPY": 0.009, "GBPJPY": 0.009, "AUDJPY": 0.009,
              # G41 (assumed, the export has no fees): USD 6 per lot on silver (5,000 oz) and oil (1,000 bbl);
              # index and crypto CFDs pay the spread only
              "XAGUSD": 0.0012, "USOUSD": 0.006, "SP500": 0.0, "ETHUSD": 0.0}


def _apply_costs(ctx, res, risk, t, factor):
    if t.get("costs", True):
        res["r"] -= COMMISSION.get(ctx["symbol"], 0.0) / risk
    res["r"] *= factor
    return res


def _limit_fill(bars, c, point):
    """First bar after placement where the working LIMIT is touched, before it expires or
    its setup is cancelled (the cancel happens at the close of the invalidating bar)."""
    d, edge = c["direction"], c["edge"]
    last = c["i"] + max(0, c["bars_left"])
    if c["invalid_at"] is not None:
        last = min(last, c["invalid_at"])
    for j in range(c["i"] + 1, min(last, len(bars) - 1) + 1):
        b = bars[j]
        ask_low = b["low"] + b["spread"] * point
        if (d == 1 and ask_low <= edge) or (d == -1 and b["high"] >= edge):
            return j
    return None


_NEWS = None


def news_status(symbol: str, profile: str, utc: int):
    """News Guard from the recorded HIGH events (logs/news_reactions.jsonl): DIRECT blocks
    SCALP from T-60 and SWING from T-180 until the market was normal again; INDIRECT
    (yellow) blocks SWING from T-180 to T+15 and halves SCALP risk in that window."""
    global _NEWS
    if _NEWS is None:
        import json
        import context
        path = context.DATA.parent / "logs" / "news_reactions.jsonl"
        _NEWS = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            normal = e.get("guard_normal_min") or 60
            _NEWS.setdefault(e["symbol"], []).append((int(e["event_utc"]), e["impact"], int(normal)))
    before = 180 if profile == "SWING" else 60
    factor = 1.0
    for t0, impact, normal in _NEWS.get(symbol, []):
        if not (t0 - before * 60 <= utc <= t0 + max(15, normal) * 60):
            continue
        if impact == "DIRECT":
            return True, 1.0
        if utc <= t0 + 15 * 60:
            if profile == "SWING":
                return True, 1.0
            factor = 0.5
    return False, factor


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
    # Bar of the exit (or of the walk limit): account simulations need the holding period.
    res["exit_i"] = b if limit >= i + 1 else i
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


def evaluate_all(ctx: dict, cands: list[dict], setup: str, profile: str, trade: dict | None = None,
                 branches: str = "both") -> list[dict]:
    """Live-like entry selection: a filled LIMIT owns its breakout, so the MARKET trigger of
    the same breakout is not taken again. branches: market | limit | both."""
    rows, filled = [], set()
    for c in sorted(cands, key=lambda x: (x["i"], x.get("kind") != "LIMIT")):
        kind = c.get("kind", "MARKET")
        if branches == "market" and kind == "LIMIT":
            continue
        if branches == "limit" and kind == "MARKET" and setup == "S02":
            continue
        if kind == "MARKET" and c.get("breakout") in filled:
            continue
        r = evaluate(ctx, c, setup, profile, "tm", trade)
        if kind == "LIMIT" and r["status"] == "EVALUATED":
            filled.add(c["breakout"])
        rows.append(r)
    return rows
