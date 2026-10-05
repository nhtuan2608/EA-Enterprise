"""G23: long-history validation of the setups on the 2010-2025 MT5 exports (research/long/data).

  python long_study.py live      # A: the configurations trading LIVE now, no tuning, per year and symbol
  python long_study.py scalp     # B: SCALP on M5 2024-06..2025-10 (outside the G10 window), live configs + grids
  python long_study.py grid      # C: SWING grids, chosen on 2010-2016, checked on 2017-2020, final 2021-2025

Same models as G10 (replay.evaluate "tm": spread + estimated commission, SWING/SCALP Trade Manager,
in a bar the stop wins over the target). News Guard is not applied (no calendar before 2026).
Spreads are floored at the 2024-2025 median (convert_raw.py). Results: results/long_<part>.json/.md.
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["EEA_RESEARCH_DATA"] = str(HERE / "data")
sys.path.insert(0, str(HERE.parent / "g10"))

import context  # noqa: E402

context.CACHE = HERE / ".cache"
import replay  # noqa: E402
import setups  # noqa: E402
import sweep  # noqa: E402

SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
FROM = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())
VALIDATE = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp())
TEST = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
SCALP_FROM = int(datetime(2024, 6, 10, tzinfo=timezone.utc).timestamp())
SCALP_SPLIT = int(datetime(2025, 2, 1, tzinfo=timezone.utc).timestamp())
OUT = HERE / "results"
S06_LIVE = {"box": 12, "max_box_atr": 3.0, "contraction": 0.85, "mode": "confirm", "sl": "far"}
_CTX: dict = {}


def ctx(symbol: str, profile: str):
    key = (symbol, profile)
    if key not in _CTX:
        path = context.DATA / f"bars_{symbol}_{'M5' if profile == 'SCALP' else 'H1'}.csv"
        if not path.exists():
            _CTX[key] = None
        else:
            _CTX[key] = context.build(symbol, profile, SCALP_FROM if profile == "SCALP" else FROM)
    return _CTX[key]


def utc_of(r: dict) -> int:
    c = ctx(r["symbol"], r["profile"])
    return r["time"] - (c["entry"][0]["time"] - c["entry"][0]["utc"])


def year_of(r: dict) -> int:
    return datetime.fromtimestamp(utc_of(r), timezone.utc).year


def period(r: dict) -> str:
    u = utc_of(r)
    return "train" if u < VALIDATE else "validate" if u < TEST else "test"


# ---------------------------------------------------------------------------
# A: live configurations
# ---------------------------------------------------------------------------
def live_rows(setup: str, profile: str) -> list[dict]:
    rows = []
    for s in SYMBOLS:
        c = ctx(s, profile)
        if c is None:
            continue
        if setup == "S06":
            cands = setups.s06(c, S06_LIVE)
            t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "aligned", "costs": True}
            rows += [replay.evaluate(c, x, "S06", profile, "tm", t) for x in cands]
        elif setup == "S02":
            cands = replay.candidates(c, "S02", replay.engine_params("S02", profile))
            rows += replay.evaluate_all(c, cands, "S02", profile, {"costs": True}, "both")
        else:
            cands = replay.candidates(c, setup, replay.engine_params(setup, profile))
            rows += [replay.evaluate(c, x, setup, profile, "tm", {"costs": True}) for x in cands]
    return rows


def by(rows: list[dict], key) -> dict:
    groups: dict = {}
    for r in rows:
        if r["status"] == "EVALUATED":
            groups.setdefault(key(r), []).append(r)
    return {k: replay.summarize(v) for k, v in sorted(groups.items())}


def part_live() -> dict:
    out = {}
    for setup in ("S02", "S04", "S06"):
        rows = live_rows(setup, "SWING")
        out[f"{setup}_SWING"] = {"all": replay.summarize(rows), "by_year": by(rows, year_of),
                                 "by_symbol": by(rows, lambda r: r["symbol"]), "by_period": by(rows, period)}
    return out


# ---------------------------------------------------------------------------
# B: SCALP on M5 2024-06..2025-10
# ---------------------------------------------------------------------------
def scalp_half(r: dict) -> str:
    return "first" if utc_of(r) < SCALP_SPLIT else "second"


def run_scalp_grid(job):
    name, p = job
    out = []
    cands = {}
    for s in SYMBOLS:
        c = ctx(s, "SCALP")
        if c is None:
            continue
        cands[s] = (replay.candidates(c, name, replay.engine_params(name, "SCALP", p)) if name in ("S02", "S04")
                    else setups.DETECTORS[name](c, p))
    for t in [dict(x, costs=True) for x in sweep.NEW_TRADE_GRID]:
        rows = []
        for s, cs in cands.items():
            c = ctx(s, "SCALP")
            rows += [replay.evaluate(c, x, name, "SCALP", "tm", dict(t)) for x in cs if x.get("kind") != "LIMIT"]
        out.append({"setup": name, "engine": p, "trade": t, "first": replay.summarize([r for r in rows if scalp_half(r) == "first"]),
                    "second": replay.summarize([r for r in rows if scalp_half(r) == "second"])})
    return out


def part_scalp() -> dict:
    live = {}
    for setup in ("S02", "S04"):
        rows = live_rows(setup, "SCALP")
        live[f"{setup}_SCALP"] = {"all": replay.summarize(rows), "by_half": by(rows, scalp_half),
                                  "by_symbol": by(rows, lambda r: r["symbol"])}
    jobs = [("S02", p) for p in sweep.grid(sweep.S02_GRID)] + [("S04", p) for p in sweep.grid(sweep.S04_GRID)]
    jobs += [(n, p) for n in ("S01", "S03", "S05", "S06") for p in sweep.grid(setups.GRIDS[n])]
    with Pool() as pool:
        results = [r for chunk in pool.imap_unordered(run_scalp_grid, jobs) for r in chunk]
    grid = {}
    for name in ("S01", "S02", "S03", "S04", "S05", "S06"):
        rows = sorted([r for r in results if r["setup"] == name and r["first"]["n"] >= 80],
                      key=lambda r: r["first"]["exp"], reverse=True)
        grid[name] = {"eligible": len(rows), "positive_both": sum(1 for r in rows if r["first"]["exp"] > 0 and r["second"]["exp"] > 0),
                      "best_first": rows[:3]}
    return {"live": live, "grid": grid}


# ---------------------------------------------------------------------------
# C: SWING grids over three periods
# ---------------------------------------------------------------------------
TRADES = [dict(t, htf=h, costs=True, news=False) for t in
          [{"target": "structural", "min_rr": 1.0}, {"target": "structural", "min_rr": 2.0},
           {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0}, {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0}]
          for h in ("any", "aligned")]


def run_swing_grid(job):
    name, p = job
    cands = {}
    for s in SYMBOLS:
        c = ctx(s, "SWING")
        if c is None:
            continue
        cands[s] = (replay.candidates(c, name, replay.engine_params(name, "SWING", p)) if name in ("S02", "S04")
                    else setups.DETECTORS[name](c, p))
    out = []
    for t in TRADES:
        rows = []
        for s, cs in cands.items():
            c = ctx(s, "SWING")
            if name == "S02":
                rows += replay.evaluate_all(c, cs, name, "SWING", dict(t), "market")
            else:
                rows += [replay.evaluate(c, x, name, "SWING", "tm", dict(t)) for x in cs]
        res = {k: replay.summarize([r for r in rows if period(r) == k]) for k in ("train", "validate", "test")}
        res["by_symbol_test"] = by([r for r in rows if period(r) == "test"], lambda r: r["symbol"])
        out.append({"setup": name, "engine": p, "trade": t, **res})
    return out


def part_grid() -> dict:
    jobs = [("S02", p) for p in sweep.grid(sweep.S02_GRID)] + [("S04", p) for p in sweep.grid(sweep.S04_GRID)]
    jobs += [(n, p) for n in ("S03", "S05", "S06") for p in sweep.grid(setups.GRIDS[n])]
    with Pool() as pool:
        results = [r for chunk in pool.imap_unordered(run_swing_grid, jobs) for r in chunk]
    out = {}
    for name in ("S02", "S03", "S04", "S05", "S06"):
        rows = sorted([r for r in results if r["setup"] == name and r["train"]["n"] >= 60],
                      key=lambda r: r["train"]["exp"], reverse=True)
        out[name] = {"eligible": len(rows),
                     "positive_all3": sum(1 for r in rows if min(r["train"]["exp"], r["validate"]["exp"], r["test"]["exp"]) > 0),
                     "best_train": rows[:3]}
    return out


# ---------------------------------------------------------------------------
def fmt(s: dict) -> str:
    return f"n={s['n']} {s['exp']:+.3f}R win {s['win']:.0%}" if s.get("n") else "n=0"


def report_live(r: dict) -> str:
    lines = ["# G23 A: cấu hình LIVE trên 2010-2025 (SWING, không tối ưu)", ""]
    for key, v in r.items():
        lines += [f"## {key}: {fmt(v['all'])}, sụt giảm tối đa {v['all'].get('dd', 0):.1f}R", "",
                  "Theo giai đoạn: " + "; ".join(f"{k} {fmt(s)}" for k, s in v["by_period"].items()),
                  "Theo symbol: " + "; ".join(f"{k} {fmt(s)}" for k, s in v["by_symbol"].items()),
                  "Theo năm: " + "; ".join(f"{k} {s['exp']:+.2f} ({s['n']})" for k, s in v["by_year"].items()), ""]
    return "\n".join(lines)


def main(part: str) -> None:
    OUT.mkdir(exist_ok=True)
    result = {"live": part_live, "scalp": part_scalp, "grid": part_grid}[part]()
    (OUT / f"long_{part}.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    text = report_live(result) if part == "live" else json.dumps(result, indent=1, default=str)[:20000]
    if part == "live":
        (OUT / "long_live.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1])
