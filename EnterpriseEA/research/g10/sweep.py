"""G10 parameter study with a walk-forward split.

  python sweep.py parity            # Python "ea" model vs logs/setup_replay.jsonl
  python sweep.py baseline          # current parameters under the managed ("tm") model
  python sweep.py sweep             # grid on train (Jan-Jun), report on test (Jul-)

Selection uses the TRAIN period only; the TEST period is reported, never optimised.
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import context
import replay

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
FROM_UTC = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
SPLIT_UTC = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp())
MIN_TRAIN = {"SCALP": 80, "SWING": 15}
OUT = Path(__file__).resolve().parent / "results"

S02_GRID = {"max_bars_to_retest": [6, None], "max_bars_for_reaction": [2, 3, 5],
            "retest_tolerance_atr": [0.10, 0.15, 0.25], "trigger_body_ratio": [0.30, 0.40, 0.55]}
S04_GRID = {"return_window": [2, 3, 4], "trigger_window": [2, 3, 5],
            "trigger_body_ratio": [0.30, 0.40, 0.55], "break_body_ratio": [0.50, 0.65]}
TRADE_GRID = {"buffer_atr": [0.10, 0.25, 0.50], "min_rr": [1.0, 1.5, 2.0], "htf": ["any", "aligned"],
              "hours": [None, (7, 20)], "target": ["structural", "fixed"]}

_CTX: dict = {}


def ctx(symbol, profile):
    k = (symbol, profile)
    if k not in _CTX:
        _CTX[k] = context.build(symbol, profile, FROM_UTC)
    return _CTX[k]


def grid(g: dict):
    keys = list(g)
    for vals in itertools.product(*(g[k] for k in keys)):
        yield {k: v for k, v in zip(keys, vals) if v is not None}


def run_engine(job):
    setup, profile, over = job
    params = replay.engine_params(setup, profile, over)
    cands = {s: replay.candidates(ctx(s, profile), setup, params) for s in SYMBOLS}
    rows_by_trade = []
    for trade in grid(TRADE_GRID):
        t = dict(trade)
        if t["target"] == "fixed":
            t["fixed_r"] = t["min_rr"]
        rows = []
        for s in SYMBOLS:
            c = ctx(s, profile)
            rows += [replay.evaluate(c, x, setup, profile, "tm", t) for x in cands[s]]
        train = replay.summarize([r for r in rows if _utc(r) < SPLIT_UTC])
        test = replay.summarize([r for r in rows if _utc(r) >= SPLIT_UTC])
        by_symbol = {s: replay.summarize([r for r in rows if r["symbol"] == s and _utc(r) >= SPLIT_UTC]) for s in SYMBOLS}
        rows_by_trade.append({"engine": over, "trade": trade, "train": train, "test": test, "test_by_symbol": by_symbol})
    return setup, profile, rows_by_trade


def _utc(r):
    c = ctx(r["symbol"], r["profile"])
    return r["time"] - (c["entry"][0]["time"] - c["entry"][0]["utc"])


def parity():
    path = context.DATA.parent / "logs" / "setup_replay.jsonl"
    ea = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for setup, profile in itertools.product(["S02", "S04"], ["SCALP", "SWING"]):
        mine = []
        for s in SYMBOLS:
            c = ctx(s, profile)
            for x in replay.candidates(c, setup, replay.engine_params(setup, profile)):
                if x.get("kind") == "LIMIT":
                    continue
                r = replay.evaluate(c, x, setup, profile, "ea")
                mine.append((s, x["time"], x["direction"], r))
        theirs = {(e["symbol"], e["bar_time"], e["direction"]): e for e in ea
                  if e["setup"] == setup and e["profile"] == profile}
        ours = {(s, t, d): r for s, t, d, r in mine}
        both = set(ours) & set(theirs)
        same_status = sum(1 for k in both if (ours[k]["status"] == theirs[k]["status"]))
        same_result = sum(1 for k in both if ours[k]["status"] == "EVALUATED" and ours[k].get("result") == theirs[k]["result"])
        print(f"{setup} {profile}: EA {len(theirs)} python {len(ours)} common {len(both)} "
              f"same_status {same_status} same_result {same_result}")


def realistic():
    """Current parameters, spread + Trade Manager + commission + News Guard, per entry branch."""
    trade = {"costs": True, "news": True}
    for setup, profile in itertools.product(["S02", "S04"], ["SCALP", "SWING"]):
        params = replay.engine_params(setup, profile)
        for branches in (["market", "limit", "both"] if setup == "S02" else ["market"]):
            rows = []
            for s in SYMBOLS:
                c = ctx(s, profile)
                rows += replay.evaluate_all(c, replay.candidates(c, setup, params), setup, profile, trade, branches)
            tr = replay.summarize([r for r in rows if _utc(r) < SPLIT_UTC])
            te = replay.summarize([r for r in rows if _utc(r) >= SPLIT_UTC])
            print(f"{setup} {profile} {branches:6s}: train n={tr['n']:4d} exp={tr['exp']:+.3f} win={tr['win']:.0%} | "
                  f"test n={te['n']:4d} exp={te['exp']:+.3f} win={te['win']:.0%} dd={te['dd']:.1f}")
            for s in SYMBOLS:
                a = replay.summarize([r for r in rows if r["symbol"] == s])
                print(f"      {s}: n={a['n']:3d} exp={a['exp']:+.3f}")


def baseline():
    for setup, profile in itertools.product(["S02", "S04"], ["SCALP", "SWING"]):
        params = replay.engine_params(setup, profile)
        for model in ("ea", "tm"):
            rows = []
            for s in SYMBOLS:
                c = ctx(s, profile)
                rows += [replay.evaluate(c, x, setup, profile, model) for x in replay.candidates(c, setup, params)]
            tr = replay.summarize([r for r in rows if _utc(r) < SPLIT_UTC])
            te = replay.summarize([r for r in rows if _utc(r) >= SPLIT_UTC])
            print(f"{setup} {profile} {model}: train n={tr['n']} exp={tr['exp']:+.3f} | test n={te['n']} exp={te['exp']:+.3f}")


def sweep():
    OUT.mkdir(exist_ok=True)
    jobs = [("S02", p, o) for p in ("SCALP", "SWING") for o in grid(S02_GRID)]
    jobs += [("S04", p, o) for p in ("SCALP", "SWING") for o in grid(S04_GRID)]
    results = {}
    with Pool() as pool:
        for setup, profile, rows in pool.imap_unordered(run_engine, jobs):
            results.setdefault(f"{setup}_{profile}", []).extend(rows)
            print(".", end="", flush=True)
    print()
    report = {}
    for key, rows in results.items():
        profile = key.split("_")[1]
        eligible = [r for r in rows if r["train"]["n"] >= MIN_TRAIN[profile]]
        eligible.sort(key=lambda r: r["train"]["exp"], reverse=True)
        report[key] = eligible[:15]
        (OUT / f"{key}.json").write_text(json.dumps(rows, indent=0, default=str), encoding="utf-8")
    (OUT / "top.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    for key, top in report.items():
        print("==", key)
        for r in top[:8]:
            print(f"  train n={r['train']['n']:4d} exp={r['train']['exp']:+.3f} | test n={r['test']['n']:4d} "
                  f"exp={r['test']['exp']:+.3f} dd={r['test']['dd']:.1f} | {r['engine']} {r['trade']}")


if __name__ == "__main__" and sys.argv[1] != "newsetups":
    {"parity": parity, "baseline": baseline, "realistic": realistic, "sweep": sweep}[sys.argv[1]]()


NEW_TRADE_GRID = [{"target": "structural", "min_rr": 1.0}, {"target": "structural", "min_rr": 1.5},
                  {"target": "fixed", "fixed_r": 1.5, "min_rr": 1.5}, {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0}]


def run_new(job):
    import setups
    name, profile, p = job
    out = []
    cands = {s: setups.DETECTORS[name](ctx(s, profile), p) for s in SYMBOLS}
    for base in NEW_TRADE_GRID:
        for htf in ("any", "aligned"):
            t = dict(base, htf=htf, costs=True, news=True)
            rows = []
            for s in SYMBOLS:
                rows += [replay.evaluate(ctx(s, profile), c, name, profile, "tm", t) for c in cands[s]]
            out.append({"engine": p, "trade": t,
                        "train": replay.summarize([r for r in rows if _utc(r) < SPLIT_UTC]),
                        "test": replay.summarize([r for r in rows if _utc(r) >= SPLIT_UTC])})
    return name, profile, out


def newsetups():
    import setups
    OUT.mkdir(exist_ok=True)
    jobs = [(n, pr, p) for n in setups.DETECTORS for pr in setups.PROFILES[n] for p in grid(setups.GRIDS[n])]
    results = {}
    with Pool() as pool:
        for name, profile, rows in pool.imap_unordered(run_new, jobs):
            results.setdefault(f"{name}_{profile}", []).extend(rows)
    (OUT / "new_setups.json").write_text(json.dumps(results, default=str), encoding="utf-8")
    for key in sorted(results):
        rows = results[key]
        profile = key.split("_")[1]
        eligible = sorted([r for r in rows if r["train"]["n"] >= MIN_TRAIN[profile]], key=lambda r: r["train"]["exp"], reverse=True)
        both = sum(1 for r in eligible if r["train"]["exp"] > 0 and r["test"]["exp"] > 0)
        print(f"== {key}: variants {len(rows)} eligible {len(eligible)} positive_both {both}")
        for r in eligible[:4]:
            print(f"  train n={r['train']['n']:4d} exp={r['train']['exp']:+.3f} | test n={r['test']['n']:4d} "
                  f"exp={r['test']['exp']:+.3f} dd={r['test']['dd']:.1f} | {r['engine']} {r['trade']['target']} "
                  f"rr{r['trade']['min_rr']} {r['trade']['htf']}")


if __name__ == "__main__" and sys.argv[1] == "newsetups":
    newsetups()
