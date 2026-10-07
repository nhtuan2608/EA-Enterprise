"""G56 phases B + C: setups from the two factors that survived the atlas, walk-forward and random control.

  python factor_setups.py          # writes results/factor_setups.md

Plan: docs/superpowers/plans/2026-10-07-g56-factor-atlas.md ("Bổ sung trước khi chạy B + C"), registered before any
number of this script.
  SW1  H1 SWING: first PDHL_SWEEP of the day, entry in the direction of the sweep (the atlas found continuation)
  SC1  M15 SCALP: ROUND_BREAK, entry in the direction of the break
Choice set (30): stop 1.0 / 1.5 / 2.0 ATR x exit TIME (24 bars) / TP2R / TP3R / RUNNER / TRAIL3 x MACD filter off / on.
Walk-forward: H1 test years 2014-2025 with the 4 years before as train; M15 test 2024 (train 2021-10..2023) and 2025
(train 2021-10..2024). Per window: the config with the best train mean (>= 30 trades), and only the symbols whose train
mean with it is > 0. Pass: pooled test mean > 0, >= 70% of test years positive, above the 90th percentile of 200
random-entry runs. C: the same walk-forward with the exit kind fixed (stop and filter still chosen in train).
"""
from __future__ import annotations

import random
import statistics
import sys
from datetime import datetime, timezone

import numpy as np

import factor_atlas as fa  # sets the research data path first (via long_study)
import replay  # noqa: E402

STOPS = (1.0, 1.5, 2.0)
EXITS = ("TIME", "TP2R", "TP3R", "RUNNER", "TRAIL3")
SETUPS = {
    "SW1": {"tf": "H1", "factor": "PDHL_SWEEP", "flip": -1, "first_of_day": True, "time_bars": 24, "max_bars": 240,
            "tests": list(range(2014, 2026)), "train_years": 4},
    "SC1": {"tf": "M15", "factor": "ROUND_BREAK", "flip": 1, "first_of_day": False, "time_bars": 24, "max_bars": 192,
            "tests": [2024, 2025], "train_years": None},
}
RANDOM_RUNS = 200


def simulate(d: dict, i: int, dirn: int, stop_atr: float, kind: str, time_bars: int, max_bars: int) -> tuple[float, int]:
    """R after costs and the exit bar. Longs pay the spread at entry, shorts at exit (ask = bid + spread); in a bar the
    stop is checked before the target; a bar that opens beyond the stop fills at its open."""
    o, h, l, c, sp, atr = d["open"], d["high"], d["low"], d["close"], d["spread"], d["atr"]
    point = d["point"]
    a = atr[i]
    entry = c[i] + (sp[i] * point if dirn == 1 else 0.0)
    risk = stop_atr * a
    sl = entry - dirn * risk
    tp = entry + dirn * {"TP2R": 2.0, "TP3R": 3.0}.get(kind, 0.0) * risk if kind in ("TP2R", "TP3R") else None
    fee = d["commission"] / risk
    open_frac, realized, partial = 1.0, 0.0, False
    last = min(len(c) - 1, i + (time_bars if kind == "TIME" else max_bars))
    b = i
    for b in range(i + 1, last + 1):
        s = sp[b] * point if dirn == -1 else 0.0
        hi, lo, cl, op = h[b] + s, l[b] + s, c[b] + s, o[b] + s
        if (dirn == 1 and lo <= sl) or (dirn == -1 and hi >= sl):
            fill = op if (dirn == 1 and op < sl) or (dirn == -1 and op > sl) else sl
            return realized + open_frac * dirn * (fill - entry) / risk - fee, b
        if tp is not None and ((dirn == 1 and hi >= tp) or (dirn == -1 and lo <= tp)):
            return realized + open_frac * dirn * (tp - entry) / risk - fee, b
        if kind == "RUNNER":
            if not partial and dirn * ((hi if dirn == 1 else lo) - entry) >= risk:
                realized += 0.5 * 1.0
                open_frac = 0.5
                partial = True
                sl = entry + dirn * sp[b] * point
            if partial:
                lvl = cl - dirn * 2.0 * atr[b]
                if dirn * (lvl - sl) > 0:
                    sl = lvl
        elif kind == "TRAIL3":
            lvl = cl - dirn * 3.0 * atr[b]
            if dirn * (lvl - sl) > 0:
                sl = lvl
    s = sp[b] * point if dirn == -1 else 0.0
    return realized + open_frac * dirn * (c[b] + s - entry) / risk - fee, b


def prepare(name: str) -> list[dict]:
    """per symbol: data, events (index, direction, year, MACD agreement) and the result of every (stop, exit)"""
    spec = SETUPS[name]
    out = []
    for sym in fa.SYMBOLS:
        d = fa.load(sym, spec["tf"])
        if d is None:
            continue
        d["point"] = float(fa.context.meta()["by_symbol"][sym]["point"])
        d["commission"] = replay.COMMISSION.get(sym, 0.0)
        mask, dirn = fa.factors(d)[spec["factor"]]
        c = d["close"]
        macd = fa.ema(c, 12) - fa.ema(c, 26)
        hist = macd - fa.ema(macd, 9)
        idx = np.flatnonzero(mask)
        if spec["first_of_day"]:
            _, first = np.unique(d["day"][idx], return_index=True)
            idx = idx[np.sort(first)]
        idx = idx[idx < len(c) - 2]
        ev = []
        for i in idx:
            di = int(spec["flip"] * dirn[i])
            res = {(s, k): simulate(d, int(i), di, s, k, spec["time_bars"], spec["max_bars"]) for s in STOPS for k in EXITS}
            ev.append({"i": int(i), "dir": di, "year": int(d["year"][i]), "hour": int(d["hour"][i]),
                       "macd": bool(np.sign(hist[i]) == di), "res": res})
        out.append({"symbol": sym, "d": d, "events": ev})
        print(f"{name} {sym}: {len(ev)} sự kiện", flush=True)
    return out


def trades(sym_block: dict, stop: float, kind: str, macd: bool, years: set[int]) -> list[dict]:
    """one position per symbol at a time, in time order"""
    busy, out = -1, []
    for e in sym_block["events"]:
        if e["year"] not in years or (macd and not e["macd"]) or e["i"] <= busy:
            continue
        r, x = e["res"][(stop, kind)]
        busy = x
        out.append({"symbol": sym_block["symbol"], "year": e["year"], "r": r, "i": e["i"], "hour": e["hour"]})
    return out


def train_years(spec: dict, test: int, data: list[dict]) -> set[int]:
    if spec["train_years"]:
        return set(range(test - spec["train_years"], test))
    first = min(e["year"] for b in data for e in b["events"])
    return set(range(first, test))


def walk_forward(name: str, data: list[dict], kinds=EXITS) -> dict:
    spec = SETUPS[name]
    years_out, chosen, all_test = {}, {}, []
    for test in spec["tests"]:
        tr = train_years(spec, test, data)
        best = None
        for s in STOPS:
            for k in kinds:
                for m in (False, True):
                    rows = [t for b in data for t in trades(b, s, k, m, tr)]
                    if len(rows) < 30:
                        continue
                    mean = statistics.fmean(t["r"] for t in rows)
                    if best is None or mean > best[0]:
                        best = (mean, s, k, m)
        if best is None:
            continue
        _, s, k, m = best
        keep = [b for b in data if (lambda rs: rs and statistics.fmean(rs) > 0)(
            [t["r"] for t in trades(b, s, k, m, tr)])]
        test_rows = [t for b in keep for t in trades(b, s, k, m, {test})]
        chosen[test] = {"stop": s, "exit": k, "macd": m, "symbols": [b["symbol"] for b in keep], "train_mean": best[0]}
        years_out[test] = test_rows
        all_test += [dict(t, cfg=(s, k)) for t in test_rows]
    return {"years": years_out, "chosen": chosen, "all": all_test}


def random_p90(name: str, data: list[dict], wf: dict, runs: int = RANDOM_RUNS, seed: int = 56) -> float:
    """same symbols, same count per (symbol, year), random bars of the same UTC hours, random direction, same config"""
    spec = SETUPS[name]
    rng = random.Random(seed)
    by_sym = {b["symbol"]: b["d"] for b in data}
    pools: dict[tuple[str, int, int], list[int]] = {}
    means = []
    for _ in range(runs):
        rs = []
        for t in wf["all"]:
            d = by_sym[t["symbol"]]
            key = (t["symbol"], t["year"], t["hour"])
            if key not in pools:
                pools[key] = [int(x) for x in np.flatnonzero((d["year"] == t["year"]) & (d["hour"] == t["hour"]) &
                                                             np.isfinite(d["atr"]) & (d["atr"] > 0))
                              if x < len(d["close"]) - 2]
            if not pools[key]:
                continue
            i = rng.choice(pools[key])
            s, k = t["cfg"]
            rs.append(simulate(d, i, rng.choice((-1, 1)), s, k, spec["time_bars"], spec["max_bars"])[0])
        if rs:
            means.append(statistics.fmean(rs))
    means.sort()
    return means[int(0.9 * len(means)) - 1] if means else 0.0


def fmt(rs: list[float]) -> str:
    if not rs:
        return "n=0"
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return f"{statistics.fmean(rs):+.3f}R n={len(rs)} thắng {sum(r > 0 for r in rs) / len(rs):.0%} tổng {sum(rs):+.1f}R DD {dd:.1f}R"


def main(argv: list[str]) -> None:
    lines = ["# G56 B + C: setup từ yếu tố sống sót, walk-forward (chỉ dữ liệu MT5)", "",
             "Kế hoạch: `docs/superpowers/plans/2026-10-07-g56-factor-atlas.md` (B + C đăng ký trước khi chạy). R sau phí.", ""]
    for name in ("SW1", "SC1"):
        data = prepare(name)
        wf = walk_forward(name, data)
        test_years = list(wf["years"])
        pos = sum(1 for y in test_years if wf["years"][y] and statistics.fmean(t["r"] for t in wf["years"][y]) > 0)
        rs = [t["r"] for y in test_years for t in sorted(wf["years"][y], key=lambda t: (t["year"], t["i"]))]
        p90 = random_p90(name, data, wf)
        mean = statistics.fmean(rs) if rs else 0.0
        share = pos / len(test_years) if test_years else 0.0
        ok = mean > 0 and share >= 0.70 and mean > p90
        spec = SETUPS[name]
        lines += [f"## {name} ({spec['tf']}, {spec['factor']})", "",
                  f"Walk-forward gộp: {fmt(rs)}; năm dương {pos}/{len(test_years)}; ngẫu nhiên p90 {p90:+.3f}R → "
                  f"**{'ĐẠT' if ok else 'KHÔNG ĐẠT'}**", "",
                  "| Năm kiểm | Cấu hình chọn trên train | Symbol giữ | Kết quả năm kiểm |", "|---|---|---|---|"]
        for y in test_years:
            ch = wf["chosen"][y]
            lines.append(f"| {y} | dừng {ch['stop']} ATR, {ch['exit']}, MACD {'bật' if ch['macd'] else 'tắt'} "
                         f"(train {ch['train_mean']:+.3f}R) | {', '.join(ch['symbols']) or '–'} | "
                         f"{fmt([t['r'] for t in wf['years'][y]])} |")
        lines += ["", f"C — cố định kiểu thoát (dừng lỗ và lọc vẫn chọn trên train), {name}:", "",
                  "| Kiểu thoát | Walk-forward gộp | Năm dương |", "|---|---|---|"]
        for k in EXITS:
            w = walk_forward(name, data, (k,))
            ys = list(w["years"])
            p = sum(1 for y in ys if w["years"][y] and statistics.fmean(t["r"] for t in w["years"][y]) > 0)
            lines.append(f"| {k} | {fmt([t['r'] for y in ys for t in w['years'][y]])} | {p}/{len(ys)} |")
        lines.append("")
        print("\n".join(lines[-12:]), flush=True)
    text = "\n".join(lines) + "\n"
    fa.ls.OUT.mkdir(exist_ok=True)
    (fa.ls.OUT / "factor_setups.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
