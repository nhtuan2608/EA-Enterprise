"""G92: S04 (Failed Break) extended for FX - zone sources, timeframes, exits, filters; select on 2010-2020,
test on 2021-10/2025. Pre-registered plan: docs/superpowers/plans/2026-10-11-g92-s04-plus.md. MT5 data only.

  python g92_s04_plus.py
"""
from __future__ import annotations

import copy
import pickle
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_study as ls  # noqa: E402,F401  (sets the research data path)
import context  # noqa: E402
import filters  # noqa: E402
import replay  # noqa: E402

REPORT = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "reports" / "2026-10-11-g92-s04-plus.md"
SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY")
FROM = ls.FROM
PERIOD = lambda u: "train" if u < ls.VALIDATE else ("validate" if u < ls.TEST else "test")
EXITS = {"T0": {"costs": True}, "T1": {"costs": True, "target": "fixed", "fixed_r": 2.0},
         "T2": {"costs": True, "target": "fixed", "fixed_r": 1.5, "min_rr": 1.5, "tm": False}}
COMBOS = [("Z0", "SWING"), ("Z0", "SWING4"), ("Z1", "SWING"), ("Z1", "SWING4"), ("Z2", "SWING"), ("Z3", "SWING")]
FILTERS = ("F1", "F2", "F3", "F4", "F5")
PENALTY = 0.10


# ---------------------------------------------------------------------------
# contexts
# ---------------------------------------------------------------------------
def base_ctx(symbol, profile):
    return context.build(symbol, profile, FROM)


def all_zone_ctx(symbol, profile):
    """Z1: every zone built from the same levels with one source allowed (width rule unchanged)."""
    key = context.CACHE / f"g92_allzones_{symbol}_{profile}.pkl"
    if key.exists():
        return pickle.loads(key.read_bytes())
    m = context.meta()
    entry = context.load_bars(symbol, context.ENTRY_TF[profile])
    level = context.load_bars(symbol, context.LEVEL_TF[profile])
    es, lsec = context.TF_SECONDS[context.ENTRY_TF[profile]], context.TF_SECONDS[context.LEVEL_TF[profile]]
    now_offset, now_utc = int(m["server_offset_now"]), int(m["exported_at_utc"])
    from_server = FROM + context.server_offset_at(FROM, now_offset, now_utc)
    for i in range(len(entry)):
        entry[i]["atr"] = context.atr_at(entry, i)
        approx = entry[i]["time"] - now_offset
        entry[i]["utc"] = entry[i]["time"] - context.server_offset_at(approx, now_offset, now_utc)
    levels, bar_level, li = {}, [], -1
    for b in entry:
        asof = b["time"] + es
        while li + 1 < len(level) and level[li + 1]["time"] + lsec <= asof:
            li += 1
        bar_level.append(li)
        if b["time"] < from_server or li + 1 < context.MIN_LEVEL_BARS or li in levels:
            continue
        window = level[max(0, li + 1 - context.LEVEL_BARS[profile]): li + 1]
        catr = context.atr_at(level, li)
        off = context.server_offset_at(asof - now_offset, now_offset, now_utc)
        pts = context.levels_from_bars(window, profile, asof, off)
        zones = context.lv.build_zones(pts, 0.25 * catr, 0.5 * catr, 1) if catr > 0 else []
        levels[li] = {"points": [p[2] for p in pts], "zones": [z for z in zones if z["qualified"]],
                      "structure": context.lv.htf_structure(window, context.WING)}
    ctx = {"symbol": symbol, "profile": profile, "from_server": from_server, "entry": entry, "bar_level": bar_level,
           "levels": levels, "point": float(m["by_symbol"][symbol]["point"]), "digits": int(m["by_symbol"][symbol]["digits"])}
    key.write_bytes(pickle.dumps(ctx))
    return ctx


def daily_ctx(base, kind):
    """Z2 (prior UTC day high/low) / Z3 (Asia 00-07 UTC range, from 07:00): zones per entry bar, targets and
    HTF structure from the base context."""
    ctx = copy.copy(base)
    entry = base["entry"]
    days = {}
    for b in entry:
        d = b["utc"] // 86400
        hr = (b["utc"] // 3600) % 24
        x = days.setdefault(d, {"hi": -1e18, "lo": 1e18, "ahi": -1e18, "alo": 1e18})
        x["hi"], x["lo"] = max(x["hi"], b["high"]), min(x["lo"], b["low"])
        if hr < 7:
            x["ahi"], x["alo"] = max(x["ahi"], b["high"]), min(x["alo"], b["low"])
    levels, bar_level = {}, []
    for i, b in enumerate(entry):
        d = b["utc"] // 86400
        hr = (b["utc"] // 3600) % 24
        li = base["bar_level"][i]
        bl = base["levels"].get(li)
        src = None
        if kind == "Z2" and (d - 1) in days:
            src = (days[d - 1]["hi"], days[d - 1]["lo"])
        if kind == "Z3" and hr >= 7 and days[d]["ahi"] > -1e17:
            src = (days[d]["ahi"], days[d]["alo"])
        if bl is None or src is None or b["atr"] <= 0:
            bar_level.append(None)
            continue
        k = (d, li)
        if k not in levels:
            a = 0.1 * b["atr"]
            levels[k] = {"points": bl["points"] + [src[0], src[1]], "structure": bl["structure"],
                         "zones": [{"low": src[0] - a, "high": src[0] + a}, {"low": src[1] - a, "high": src[1] + a}]}
        bar_level.append(k)
    ctx["levels"], ctx["bar_level"] = levels, bar_level
    return ctx


_CACHE: dict = {}


def ctx_for(symbol, zone, profile):
    key = (symbol, zone, profile)
    if key not in _CACHE:
        if zone == "Z0":
            _CACHE[key] = base_ctx(symbol, profile)
        elif zone == "Z1":
            _CACHE[key] = all_zone_ctx(symbol, profile)
        else:
            _CACHE[key] = daily_ctx(base_ctx(symbol, profile), zone)
    return _CACHE[key]


# ---------------------------------------------------------------------------
# labels for the filters
# ---------------------------------------------------------------------------
_H4: dict = {}
_USD = None


def h4_side_map(symbol):
    """server time of an H1/H4 bar -> side of the last completed H4 close vs its EMA200 (from H1 bars)."""
    if symbol in _H4:
        return _H4[symbol]
    bars = context.load_bars(symbol, "H1")
    closes, buckets = [], []
    for k, b in enumerate(bars):
        bk = b["time"] - b["time"] % 14400
        if k + 1 == len(bars) or (bars[k + 1]["time"] - bars[k + 1]["time"] % 14400) != bk:
            closes.append(b["close"]); buckets.append(bk)
    ema = filters.ema(closes, 200)
    side = {bk: (1 if c > e else -1) for bk, c, e in zip(buckets, closes, ema)}
    order = sorted(side)
    _H4[symbol] = (order, side)
    return _H4[symbol]


def h4_side(symbol, t):
    import bisect
    order, side = h4_side_map(symbol)
    bk = t - t % 14400
    j = bisect.bisect_left(order, bk) - 1
    return side[order[j]] if j >= 200 else 0


def labels(ctx, c, symbol, pd):
    global _USD
    if _USD is None:
        _USD = filters.usd_index()
    b = ctx["entry"][c["i"]]
    d = c["direction"]
    day = b["utc"] // 86400
    flow = _USD.get(b["time"] - b["time"] % 3600, 0)
    prev = pd.get(day - 1)
    return {"F1": replay.htf_aligned(c["structure"], d),
            "F2": h4_side(symbol, b["time"]) == d,
            "F3": 7 <= (b["utc"] // 3600) % 24 < 17,
            "F4": flow != 0 and d == filters.USD_SIGN[symbol] * flow,
            "F5": prev is not None and ((d == -1 and c["extreme"] > prev[0]) or (d == 1 and c["extreme"] < prev[1]))}


def prior_days(ctx):
    days = {}
    for b in ctx["entry"]:
        x = days.setdefault(b["utc"] // 86400, [-1e18, 1e18])
        x[0], x[1] = max(x[0], b["high"]), min(x[1], b["low"])
    return days


# ---------------------------------------------------------------------------
def trades(symbol, zone, profile, ex):
    ctx = ctx_for(symbol, zone, profile)
    pd = prior_days(ctx)
    cands = [x for x in replay.candidates(ctx, "S04", replay.engine_params("S04", profile)) if x.get("kind") != "LIMIT"]
    out, free = [], -1
    for c in cands:
        if c["i"] <= free:
            continue
        r = replay.evaluate(ctx, c, "S04", profile, "tm", EXITS[ex])
        if r["status"] != "EVALUATED":
            continue
        free = r.get("exit_i", c["i"])
        u = ctx["entry"][c["i"]]["utc"]
        out.append({"r": r["r"], "utc": u, "p": PERIOD(u), "sym": symbol, "lab": labels(ctx, c, symbol, pd)})
    return out


def mean(x):
    return statistics.fmean(x) if x else 0.0


def lower90(xs, runs=3000, seed=92):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


def book(rows, risk):
    rows = sorted(rows, key=lambda r: r["utc"])
    eq = pk = 1.0
    dd = 0.0
    for r in rows:
        eq *= 1 + risk * r["r"]
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    yrs = max((rows[-1]["utc"] - rows[0]["utc"]) / (365.25 * 86400), 0.1)
    return (eq ** (1 / yrs) - 1) * 100, dd * 100


def cell(rows, q):
    x = [r["r"] for r in rows if r["p"] == q]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def main():
    L = ["# G92: S04 mở rộng cho FX — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-g92-s04-plus.md`. EURUSD + GBPUSD + USDJPY gộp, chi phí như G55. Ô: số lệnh / R mỗi lệnh. "
         "Chọn trên 2010–2020; test 2021–10/2025 không dùng để chọn.", "",
         "## Phần A — nguồn vùng × khung × cách thoát", "",
         "| Vùng | Khung | Thoát | Train 2010–16 | Validate 2017–20 | Chọn? | Test 2021–25 |", "|---|---|---|---|---|---|---|"]
    res, chosen = {}, []
    for zone, profile in COMBOS:
        for ex in EXITS:
            rows = [t for s in SYMBOLS for t in trades(s, zone, profile, ex)]
            res[(zone, profile, ex)] = rows
            tv = [r for r in rows if r["p"] != "test"]
            pick = (mean([r["r"] for r in rows if r["p"] == "train"]) > 0 and mean([r["r"] for r in rows if r["p"] == "validate"]) > 0
                    and len(tv) >= 100)
            if pick:
                chosen.append((zone, profile, ex))
            tfname = "H1" if profile == "SWING" else "H4"
            L.append(f"| {zone} | {tfname} | {ex} | {cell(rows, 'train')} | {cell(rows, 'validate')} | {'**chọn**' if pick else ''} | {cell(rows, 'test')} |")
            sys.stdout.buffer.write((L[-1] + "\n").encode()); sys.stdout.flush()
    L += ["", f"Được chọn: {', '.join(' / '.join(k) for k in chosen) or 'không có'}.", ""]
    final = []
    if chosen:
        L += ["## Phần B — bộ lọc (chấm trên 2010–2020)", "",
              "| Bộ | Lọc | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ lệnh | Giữ lọc? |", "|---|---|---|---|---|---|"]
        for key in chosen:
            rows = res[key]
            tv = [r for r in rows if r["p"] != "test"]
            kept = []
            for f in FILTERS:
                ok = True
                cells = []
                for q in ("train", "validate"):
                    a = [r["r"] for r in rows if r["p"] == q and r["lab"][f]]
                    b = [r["r"] for r in rows if r["p"] == q and not r["lab"][f]]
                    cells.append(f"{len(a)} {mean(a):+.2f} / {len(b)} {mean(b):+.2f}")
                    ok = ok and bool(a) and bool(b) and mean(a) > mean(b)
                share = sum(1 for r in tv if r["lab"][f]) / max(len(tv), 1)
                ok = ok and share >= 0.4
                if ok:
                    kept.append(f)
                L.append(f"| {' / '.join(key)} | {f} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} |")
            sel = [r for r in rows if all(r["lab"][f] for f in kept)]
            final += [dict(r, combo=key) for r in sel]
            L.append(f"| {' / '.join(key)} | **áp: {', '.join(kept) or 'không lọc'}** | {cell(sel, 'train')} | {cell(sel, 'validate')} | | test {cell(sel, 'test')} |")
        test = [r for r in final if r["p"] == "test"]
        tr = [r["r"] for r in test]
        L += ["", "## Kiểm tra cuối (2021–10/2025)", ""]
        if tr:
            m, lo, mp = mean(tr), lower90(tr), mean([x - PENALTY for x in tr])
            yrs = 4.8
            checks = {"R/lệnh > 0": m > 0, "cận dưới 90% > 0": lo > 0, f"sau trừ {PENALTY:.2f}R > 0": mp > 0}
            L.append(f"Sổ gộp: {len(tr)} lệnh (~{len(tr) / yrs:.0f} lệnh/năm), R/lệnh {m:+.3f}, cận dưới 90% {lo:+.3f}, sau trừ {PENALTY:.2f}R {mp:+.3f}.")
            L += [f"- {k}: {'đạt' if v else 'KHÔNG'}" for k, v in checks.items()]
            for risk in (0.005, 0.01):
                py, dd = book(test, risk)
                py2, dd2 = book([dict(r, r=r["r"] - PENALTY) for r in test], risk)
                L.append(f"- {risk:.1%}/lệnh: {py:+.1f}%/năm, DD {dd:.0f}% (sau trừ {PENALTY:.2f}R: {py2:+.1f}%/năm, DD {dd2:.0f}%)")
            L.append("")
            L.append("Theo cặp (test): " + "; ".join(f"{s} {len([r for r in test if r['sym'] == s])} lệnh "
                                                    f"{mean([r['r'] for r in test if r['sym'] == s]):+.3f}" for s in SYMBOLS))
            L += ["", f"**Kết luận theo luật: {'ĐẠT' if all(checks.values()) else 'không đạt'}.**", ""]
        else:
            L += ["Không có lệnh test sau lọc.", ""]
    else:
        L += ["**Không bộ nào được chọn ở Phần A.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
