"""SWING (H1 entry, H4 levels) study on long history with three periods:
  TRAIN    2023-01-01 .. 2024-12-31   parameters are chosen here only
  VALIDATE 2025-01-01 .. 2025-12-31   first out-of-sample check
  TEST     2026-01-01 .. now          held out until the end

News Guard is not applied (the recorded calendar starts in 2026). Costs (spread +
estimated commission) and the SWING Trade Manager profile are applied.

  python longswing.py control     # random entries: the cost floor
  python longswing.py study       # S02, S03, S04, S05, S06 grids
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from datetime import datetime, timezone
from multiprocessing import Pool

import context
import replay
import setups
import sweep

FROM = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
VALIDATE = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
TEST = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
MIN_TRAIN = 40
PROFILE = "SWING"
_CTX = {}


def ctx(symbol):
    if symbol not in _CTX:
        _CTX[symbol] = context.build(symbol, PROFILE, FROM)
    return _CTX[symbol]


def period(r):
    c = ctx(r["symbol"])
    utc = r["time"] - (c["entry"][0]["time"] - c["entry"][0]["utc"])
    return "train" if utc < VALIDATE else "validate" if utc < TEST else "test"


def split(rows):
    return {p: replay.summarize([r for r in rows if period(r) == p]) for p in ("train", "validate", "test")}


def engine_candidates(name, p, symbol):
    c = ctx(symbol)
    if name in ("S02", "S04"):
        return replay.candidates(c, name, replay.engine_params(name, PROFILE, p))
    return setups.DETECTORS[name](c, p)


TRADES = [dict(t, htf=h, costs=True, news=False) for t in
          [{"target": "structural", "min_rr": 1.0}, {"target": "structural", "min_rr": 1.5},
           {"target": "structural", "min_rr": 2.0}, {"target": "fixed", "fixed_r": 1.5, "min_rr": 1.5},
           {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0}, {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0}]
          for h in ("any", "aligned")]


def run(job):
    name, p = job
    cands = {s: engine_candidates(name, p, s) for s in sweep.SYMBOLS}
    out = []
    for t in TRADES:
        rows = []
        for s in sweep.SYMBOLS:
            if name == "S02":
                rows += replay.evaluate_all(ctx(s), cands[s], name, PROFILE, t, "market")
            else:
                rows += [replay.evaluate(ctx(s), c, name, PROFILE, "tm", t) for c in cands[s]]
        res = split(rows)
        res["by_symbol"] = {s: replay.summarize([r for r in rows if r["symbol"] == s and period(r) != "train"])
                            for s in sweep.SYMBOLS}
        out.append({"setup": name, "engine": p, "trade": t, **res})
    return out


def grids():
    yield from (("S02", p) for p in sweep.grid(sweep.S02_GRID))
    yield from (("S04", p) for p in sweep.grid(sweep.S04_GRID))
    for name in ("S03", "S05", "S06"):
        yield from ((name, p) for p in sweep.grid(setups.GRIDS[name]))


def control():
    random.seed(11)
    rows = []
    for s in sweep.SYMBOLS:
        c = ctx(s)
        bars = c["entry"]
        for i in range(60, len(bars) - 200, 8):
            b = bars[i]
            if b["time"] < c["from_server"] or b["atr"] <= 0 or c["bar_level"][i] not in c["levels"]:
                continue
            d = random.choice((1, -1))
            cand = {"kind": "MARKET", "i": i, "time": b["time"], "direction": d, "extreme": b["close"] - d * 1.5 * b["atr"],
                    "zone_low": 0, "zone_high": 0, "signal_atr": b["atr"], "points": [], "structure": "NEUTRAL"}
            rows.append(replay.evaluate(c, cand, "RND", PROFILE, "tm",
                                        {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0, "costs": True}))
    for p, v in split(rows).items():
        print(f"random {p}: n={v['n']} exp={v['exp']:+.3f}")


def study():
    for s in sweep.SYMBOLS:
        c = ctx(s)
        print(s, "H1 bars", len(c["entry"]), "from", datetime.fromtimestamp(c["entry"][0]["time"], timezone.utc).date())
    with Pool() as pool:
        results = [r for chunk in pool.imap_unordered(run, list(grids())) for r in chunk]
    (sweep.OUT).mkdir(exist_ok=True)
    (sweep.OUT / "long_swing.json").write_text(json.dumps(results, default=str), encoding="utf-8")
    for name in ("S02", "S03", "S04", "S05", "S06"):
        rows = [r for r in results if r["setup"] == name and r["train"]["n"] >= MIN_TRAIN]
        rows.sort(key=lambda r: r["train"]["exp"], reverse=True)
        all3 = [r for r in rows if r["train"]["exp"] > 0 and r["validate"]["exp"] > 0 and r["test"]["exp"] > 0]
        print(f"== {name}: eligible {len(rows)} positive in all three periods {len(all3)}")
        for r in rows[:5]:
            print(f"  train n={r['train']['n']:4d} {r['train']['exp']:+.3f} | val n={r['validate']['n']:4d} "
                  f"{r['validate']['exp']:+.3f} | test n={r['test']['n']:4d} {r['test']['exp']:+.3f} "
                  f"| {r['engine']} {r['trade']['target']} rr{r['trade']['min_rr']} {r['trade']['htf']}")


if __name__ == "__main__":
    {"control": control, "study": study}[sys.argv[1]]()
