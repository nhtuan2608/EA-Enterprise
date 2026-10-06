"""G28/G29: bar-by-bar exit rules and pyramiding, shared by the research (research/long/exits.py)
and the virtual results of live candidates (candidates_eval.py).

A trade dict needs: symbol, i (entry bar index in ctx["entry"]), dir, entry, stop, target, zl, zh.
A rule: target ("plan" | R multiple | None), be (R or None), partial ((R, fraction) or None),
trail (("STRUCT", start R, bars) | ("ATR", start R, multiple) | None), timeout (bars), struct_exit.
CURRENT is the SWING Trade Manager (replay.TM["SWING"]) and reproduces replay.evaluate exactly.
Pyramiding (add_at): one add of the same risk unit at the close of the bar where the trade first
closes at +add_at R, both legs' stop at the first entry, so open risk never exceeds one unit.
"""
from __future__ import annotations

import replay

CURRENT = {"name": "TM hiện tại", "target": "plan", "be": 1.0, "partial": (1.5, 0.33), "trail": ("STRUCT", 2.0, 5),
           "timeout": 120, "struct_exit": True}


def walk(c: dict, t: dict, rule: dict, start: int, entry: float, stop: float, target, be_done: bool = False):
    """Returns (R before costs, exit bar, max favourable R, bar where +k R first closed or None)."""
    bars, point, d = c["entry"], c["point"], t["dir"]
    risk = d * (entry - stop)
    open_frac, realized, sl = 1.0, 0.0, stop
    be, partial, trail = be_done, rule["partial"] is None, False
    mfe = 0.0
    n = 0
    limit = min(len(bars) - 1, start + rule["timeout"] * 3)
    b = start
    for b in range(start + 1, limit + 1):
        n += 1
        bar = bars[b]
        sp = bar["spread"] * point if d == -1 else 0.0
        hi, lo, close = bar["high"] + sp, bar["low"] + sp, bar["close"] + sp
        if (d == 1 and lo <= sl) or (d == -1 and hi >= sl):
            realized += open_frac * d * (sl - entry) / risk
            open_frac = 0.0
            break
        if target is not None and ((d == 1 and hi >= target) or (d == -1 and lo <= target)):
            realized += open_frac * d * (target - entry) / risk
            open_frac = 0.0
            break
        mfe = max(mfe, d * ((hi if d == 1 else lo) - entry) / risk)
        if rule["struct_exit"] and not be and t["zl"] > 0 and ((d == 1 and close < t["zl"]) or (d == -1 and close > t["zh"])):
            realized += open_frac * d * (close - entry) / risk
            open_frac = 0.0
            break
        if n >= rule["timeout"] and not trail:
            realized += open_frac * d * (close - entry) / risk
            open_frac = 0.0
            break
        # Same order as the Trade Manager: partial, else break-even, else trailing step.
        if not partial and mfe >= rule["partial"][0]:
            realized += rule["partial"][1] * rule["partial"][0]
            open_frac -= rule["partial"][1]
            partial = True
        elif not be and rule["be"] is not None and mfe >= rule["be"]:
            sl = entry + d * bar["spread"] * point
            be = True
        elif rule["trail"] and (trail or mfe >= rule["trail"][1]):
            trail = True
            kind, _, k = rule["trail"]
            if kind == "ATR":
                level = bar["close"] - d * k * bar["atr"]
            else:
                window = bars[max(0, b - k + 1): b + 1]
                ext = min(x["low"] for x in window) if d == 1 else max(x["high"] for x in window)
                level = ext - d * 0.1 * bar["atr"]
            if d * (level - entry) > 0 and d * (level - sl) >= 0.1 * risk:
                sl = level
    if open_frac > 0:
        realized += open_frac * d * (bars[b]["close"] - entry) / risk
    return realized, b, mfe


def target_of(t: dict, rule: dict):
    risk = t["dir"] * (t["entry"] - t["stop"])
    if rule["target"] == "plan":
        return t["target"]
    if rule["target"] is None:
        return None
    return t["entry"] + t["dir"] * rule["target"] * risk


def run(c: dict, t: dict, rule: dict, add_at=None) -> dict:
    """One trade (plus an optional add) under a rule; R in units of the 0.3% risk, after commission."""
    risk = t["dir"] * (t["entry"] - t["stop"])
    fee = replay.COMMISSION.get(t["symbol"], 0.0)
    target = target_of(t, rule)
    r, exit_i, mfe = walk(c, t, rule, t["i"], t["entry"], t["stop"], target)
    total = r - fee / risk
    if add_at is not None:
        add = add_bar(c, t, add_at, exit_i)
        if add is not None:
            j = add
            bars, point, d = c["entry"], c["point"], t["dir"]
            price = bars[j]["close"] + (bars[j]["spread"] * point if d == 1 else 0.0)
            stop2 = t["entry"] + d * bars[j]["spread"] * point            # shared break-even stop
            risk2 = d * (price - stop2)
            if risk2 > 0:
                rule2 = dict(rule, partial=None, struct_exit=False)
                r2, exit2, _ = walk(c, t, rule2, j, price, stop2, target, be_done=True)
                total += r2 - fee / risk2
                exit_i = max(exit_i, exit2)
    return {"r": total, "exit_i": exit_i, "mfe": mfe}


def add_bar(c: dict, t: dict, k: float, exit_i: int):
    """First bar (before the first leg exits) whose close is at least +k R."""
    bars, d = c["entry"], t["dir"]
    risk = d * (t["entry"] - t["stop"])
    for j in range(t["i"] + 1, exit_i):
        if d * (bars[j]["close"] - t["entry"]) >= k * risk:
            return j
    return None
