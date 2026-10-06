"""G18 virtual results for every live candidate (design 2026-10-05-setup-arbitration-and-
candidate-ledger, section 4). Reads <data root>/logs/candidates.jsonl written by the EA and
evaluates each candidate with the G10 "tm" model (costs on, HTF and news filters off: the
filters already show in the candidate's reason).

  python candidates_eval.py                  # all candidates
  python candidates_eval.py --since 2026-10-05

Groups: EXECUTED, SHADOW_MODE, and one group per blocking reason. "ALL" is the setup as if it
had run alone. A candidate whose trade cannot finish inside the exported bars is NO_BARS_YET.
G29: S06B also gets ALL_ADD_1R (the same candidates with one add at +1R, pyramid.py, research
G28) and USD_ALIGNED / USD_COUNTER / USD_UNKNOWN (the USD flow flag the EA logged, research G27).
G38: T2 (POSITION, H4) is walked on the exported H4 bars with its research exit (ATR trail 3, at most
180 bars x 3, gap fills at the open); one T2 trade per symbol at a time, so a T2 candidate that starts
while the previous T2 trade of its symbol is still open is T2_POSITION_OPEN (not counted).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import context
import pyramid
import replay

FROM_UTC = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
TRADE = {
    "S06": {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True},
    "S06B": {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True},
    "S04": {"htf": "any", "costs": True},
    "S02": {"htf": "any", "costs": True},
}
OUT = Path(__file__).resolve().parent / "results"
ADD_AT = {"S06B": 1.0}      # G28/G29: virtual add (pyramiding) at +1R
T2_RULE = {"target": None, "be": None, "partial": None, "trail": ("ATR", 0.0, 3.0), "timeout": 180,
           "struct_exit": False}   # research/long/discovery.py trend_rule, T2 set (G38)


def ledger_path() -> Path:
    return context.DATA.parent / "logs" / "candidates.jsonl"


def load(path: Path, since_utc: int = 0) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            r = json.loads(line)
            if int(r.get("closed_utc", 0)) >= since_utc:
                rows.append(r)
    return rows


def group_of(row: dict) -> str:
    if row["disposition"] == "EXECUTED":
        return "EXECUTED"
    reason = row.get("reason", "")
    return reason.split(":", 1)[0] if reason.startswith("NOT_EVALUATED") else reason


def t2_context(symbol: str) -> dict:
    """Exported H4 bars with the research ATR (simple mean of 14 true ranges) for the T2 walk."""
    bars = context.load_bars(symbol, "H4")
    for i in range(len(bars)):
        bars[i]["atr"] = context.atr_at(bars, i)
    return {"entry": bars, "point": float(context.meta()["by_symbol"][symbol]["point"]), "symbol": symbol}


def context_for(row: dict, cache: dict) -> dict:
    key = (row["symbol"], row["profile"])
    if key not in cache:
        cache[key] = t2_context(row["symbol"]) if row["profile"] == "POSITION" else \
            context.build(row["symbol"], row["profile"], FROM_UTC)
    return cache[key]


def evaluate_t2(row: dict, ctx: dict, base: dict) -> dict:
    bars, point = ctx["entry"], ctx["point"]
    i = next((k for k, b in enumerate(bars) if b["time"] == int(row["bar_time"])), None)
    if i is None:
        return dict(base, status="NO_BARS_YET")
    d = int(row["direction"])
    entry = bars[i]["close"] + (bars[i]["spread"] * point if d == 1 else 0.0)
    stop = float(row["extreme"])
    if d * (entry - stop) <= 0:
        return dict(base, status="STRUCTURE_INVALID")
    t = {"symbol": row["symbol"], "i": i, "dir": d, "entry": entry, "stop": stop, "target": 0.0, "zl": 0.0, "zh": 0.0}
    gap = pyramid.GAP_FILL
    pyramid.GAP_FILL = True
    try:
        res = pyramid.run(ctx, t, T2_RULE)
    finally:
        pyramid.GAP_FILL = gap
    if res["exit_i"] >= len(bars) - 1:
        return dict(base, status="NO_BARS_YET")
    return dict(base, status="EVALUATED", r=res["r"], exit_time=bars[res["exit_i"]]["time"],
                usd=row.get("usd_alignment", "UNKNOWN"))


def mark_t2_overlaps(evaluated: list[dict]) -> None:
    """One T2 trade per symbol at a time (research discovery.trades): later overlapping ones drop out."""
    busy = {}
    for e in sorted((e for e in evaluated if e["setup"] == "T2"), key=lambda e: e["time"]):
        until = busy.get(e["symbol"], 0)
        if e["time"] <= until:
            e["status"] = "T2_POSITION_OPEN"
            continue
        if e["status"] == "EVALUATED":
            busy[e["symbol"]] = e["exit_time"]
        elif e["status"] == "NO_BARS_YET":
            busy[e["symbol"]] = 10 ** 12


def evaluate_rows(rows: list[dict]) -> list[dict]:
    cache: dict = {}
    out = [evaluate_row(r, context_for(r, cache)) for r in rows]
    mark_t2_overlaps(out)
    return out


def evaluate_row(row: dict, ctx: dict) -> dict:
    """Virtual result of one ledger line against a research context of its symbol/profile."""
    setup, profile = row["setup"], row["profile"]
    base = {"candidate_id": row["candidate_id"], "setup": setup, "profile": profile, "symbol": row["symbol"],
            "group": group_of(row), "time": int(row["bar_time"]), "r": 0.0}
    if setup == "T2":
        return evaluate_t2(row, ctx, base)
    bars = ctx["entry"]
    index = {b["time"]: k for k, b in enumerate(bars)}
    i = index.get(int(row["bar_time"]))
    if not row["bar_time"] or i is None:
        return dict(base, status="NO_BARS_YET")
    lvl = ctx["levels"].get(ctx["bar_level"][i]) or {"points": [], "structure": "NEUTRAL"}
    cand = {"kind": "MARKET", "i": i, "time": bars[i]["time"], "direction": int(row["direction"]),
            "extreme": float(row["extreme"]), "zone_low": float(row["zone_low"]),
            "zone_high": float(row["zone_high"]), "signal_atr": float(row["signal_atr"]) or bars[i]["atr"],
            "points": lvl["points"], "structure": lvl["structure"]}
    res = replay.evaluate(ctx, cand, setup, profile, "tm", dict(TRADE.get(setup, {})))
    if res.get("result") == "OPEN" and i + replay.TM[profile]["timeout_bars"] * 3 > len(bars) - 1:
        return dict(base, status="NO_BARS_YET")
    out = dict(base, status=res["status"], r=res.get("r", 0.0), result=res.get("result", ""),
               usd=row.get("usd_alignment", "UNKNOWN"))
    if setup in ADD_AT and res["status"] == "EVALUATED":
        t = {"symbol": row["symbol"], "i": i, "dir": cand["direction"], "entry": res["entry"], "stop": res["stop"],
             "target": res["target"], "zl": cand["zone_low"], "zh": cand["zone_high"]}
        out["r_add"] = pyramid.run(ctx, t, pyramid.CURRENT, ADD_AT[setup])["r"]
    return out


def report(evaluated: list[dict]) -> dict:
    out = {}
    for key in sorted({(e["setup"], e["profile"]) for e in evaluated}):
        rows = [e for e in evaluated if (e["setup"], e["profile"]) == key]
        groups = {"ALL": replay.summarize(rows)}
        for g in sorted({e["group"] for e in rows}):
            groups[g] = replay.summarize([e for e in rows if e["group"] == g])
        if any("r_add" in e for e in rows):
            groups["ALL_ADD_1R"] = replay.summarize([dict(e, r=e["r_add"]) for e in rows if "r_add" in e])
            for u in ("ALIGNED", "COUNTER", "UNKNOWN"):
                groups[f"USD_{u}"] = replay.summarize([e for e in rows if e.get("usd") == u])
        groups["NO_BARS_YET"] = {"n": sum(1 for e in rows if e["status"] == "NO_BARS_YET")}
        out[f"{key[0]}_{key[1]}"] = groups
    return out


def main(argv: list[str]) -> None:
    since = 0
    if "--since" in argv:
        since = int(datetime.fromisoformat(argv[argv.index("--since") + 1]).replace(tzinfo=timezone.utc).timestamp())
    rows = load(ledger_path(), since)
    if not rows:
        print("no candidates in", ledger_path())
        return
    evaluated = evaluate_rows(rows)
    rep = report(evaluated)
    OUT.mkdir(exist_ok=True)
    (OUT / "candidates_eval.json").write_text(json.dumps({"report": rep, "rows": evaluated}, indent=1), encoding="utf-8")
    for key, groups in rep.items():
        print("==", key)
        for g, s in groups.items():
            if g == "NO_BARS_YET":
                print(f"  {g:34s} n={s['n']}")
            else:
                print(f"  {g:34s} n={s['n']:4d} exp={s['exp']:+.3f}R win={s['win']:.0%}")


if __name__ == "__main__":
    main(sys.argv[1:])
