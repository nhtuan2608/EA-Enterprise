"""FX01: EURUSD/GBPUSD entries led by the USD index (retest of swing highs/lows, structure break), the pair's own
supply/demand zones and news-surprise drift; market vs LIMIT entries; M15/M30/H1; time/indicator filters scored as
G79. Pre-registered plan: docs/superpowers/plans/2026-10-11-fx01-usd-led-limit.md. MT5 data only.

  python fx01_usd_led.py
"""
from __future__ import annotations

import csv
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "long"))
import g93_s04_s06b_fx as g93  # noqa: E402  (registers the M15/M30 profiles and the data path)
import context  # noqa: E402
import filters  # noqa: E402
import g92_s04_plus as g92  # noqa: E402
import replay  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-fx01-usd-led-limit.md"
CALENDAR = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
                r"\MQL5\Files\EnterpriseEA\research\calendar")
SYMBOLS = g93.SYMBOLS
TFS = g93.TFS
PENALTY = 0.10
EXPIRY = 3
EXITS = {"T1": {"costs": True, "target": "fixed", "fixed_r": 2.0, "min_rr": 2.0},
         "T2": {"costs": True, "target": "fixed", "fixed_r": 1.5, "min_rr": 1.5, "tm": False}}
SETUPS = ("U1", "U2", "U3", "N")
FILTERS = {"U1": ("F1", "F2", "F3", "F5", "F6"), "U2": ("F1", "F2", "F3", "F5", "F6"),
           "U3": ("F1", "F2", "F3", "F4", "F5", "F6"), "N": ("F1", "F2", "F3", "F6")}
INVERTED = ("unemployment", "jobless", "claims")


def variants(setup):
    base = [(e, t) for e in ("E0", "E1") for t in EXITS]
    return [v + (u,) for v in base for u in ("U0", "U1")] if setup == "U3" else base


def vname(v):
    return "/".join(v)


# ---------------------------------------------------------------------------
# USD index on the entry timeframe
# ---------------------------------------------------------------------------
_IDX: dict = {}


def usd_bars(tf):
    """time -> OHLC of mean(-log EURUSD, -log GBPUSD, +log USDJPY) (high/low from the components' extremes)."""
    if tf in _IDX:
        return _IDX[tf]
    comp = {}
    for s, sgn in (("EURUSD", -1), ("GBPUSD", -1), ("USDJPY", 1)):
        for b in context.load_bars(s, tf):
            hi, lo = (b["high"], b["low"]) if sgn == 1 else (b["low"], b["high"])
            comp.setdefault(b["time"], []).append((sgn * math.log(b["open"]), sgn * math.log(hi),
                                                   sgn * math.log(lo), sgn * math.log(b["close"])))
    bars = []
    for t in sorted(comp):
        v = comp[t]
        if len(v) != 3:
            continue
        o, h, l, c = (sum(x[k] for x in v) / 3 for k in range(4))
        bars.append({"time": t, "open": o, "high": h, "low": l, "close": c})
    for i in range(len(bars)):
        bars[i]["atr"] = context.atr_at(bars, i)
    ema = filters.ema([b["close"] for b in bars], 50)
    for b, e in zip(bars, ema):
        b["ema50"] = e
    _IDX[tf] = bars
    return bars


def usd_signals(tf, kind):
    """time -> USD direction (+1 USD up / -1 USD down) of U1 (retest rejection) or U2 (structure break)."""
    bars = usd_bars(tf)
    out = {}
    highs, lows = [], []          # confirmed pivots: [index, price, alive]
    last_h = last_l = None
    for k in range(7, len(bars)):
        p = k - 3
        if all(bars[p]["high"] > bars[j]["high"] for j in range(p - 3, p + 4) if j != p):
            highs.append([p, bars[p]["high"], True])
            last_h = bars[p]["high"]
        if all(bars[p]["low"] < bars[j]["low"] for j in range(p - 3, p + 4) if j != p):
            lows.append([p, bars[p]["low"], True])
            last_l = bars[p]["low"]
        highs = [x for x in highs if k - x[0] <= 120]
        lows = [x for x in lows if k - x[0] <= 120]
        b, a = bars[k], bars[k]["atr"]
        rng = b["high"] - b["low"]
        if a <= 0 or rng <= 0:
            continue
        if kind == "U1":
            for x in highs:
                if not x[2] or x[0] >= k - 3:
                    continue
                if b["close"] > x[1] + 0.25 * a:
                    x[2] = False
                elif b["high"] >= x[1] - 0.25 * a and b["close"] < x[1] and (b["open"] - b["close"]) >= 0.4 * rng:
                    out[b["time"]] = -1
                    x[2] = False
                    break
            for x in lows:
                if not x[2] or x[0] >= k - 3:
                    continue
                if b["close"] < x[1] - 0.25 * a:
                    x[2] = False
                elif b["low"] <= x[1] + 0.25 * a and b["close"] > x[1] and (b["close"] - b["open"]) >= 0.4 * rng:
                    out[b["time"]] = 1
                    x[2] = False
                    break
        else:
            prev = bars[k - 1]
            if last_h is not None and b["close"] > last_h + 0.1 * a and prev["close"] < prev["ema50"]:
                out[b["time"]] = 1
                last_h = None
            elif last_l is not None and b["close"] < last_l - 0.1 * a and prev["close"] > prev["ema50"]:
                out[b["time"]] = -1
                last_l = None
    return out


# ---------------------------------------------------------------------------
# news
# ---------------------------------------------------------------------------
_NEWS = None
_HIGH = None


def _num(s):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", s or "")
    return float(m.group(1)) if m else None


def news():
    """(server time, currency) -> surprise sign (+1 good for the currency), HIGH events with actual and forecast;
    also every HIGH event time of USD/EUR/GBP for F5."""
    global _NEWS, _HIGH
    if _NEWS is None:
        acc, high = {}, {}
        for f in sorted(CALENDAR.glob("calendar_*.csv")):
            with f.open(encoding="utf-8", errors="replace", newline="") as fh:
                for r in csv.DictReader(fh):
                    if r["importance"] != "HIGH" or r["currency"] not in ("USD", "EUR", "GBP"):
                        continue
                    t = int(r["time_server"])
                    high.setdefault(r["currency"], []).append(t)
                    a, fc = _num(r["actual"]), _num(r["forecast"])
                    if a is None or fc is None or a == fc:
                        continue
                    s = 1 if a > fc else -1
                    if any(k in r["name"].lower() for k in INVERTED):
                        s = -s
                    acc.setdefault((t, r["currency"]), []).append(s)
        _NEWS = {k: (1 if sum(v) > 0 else -1) for k, v in acc.items() if sum(v) != 0}
        _HIGH = {c: sorted(v) for c, v in high.items()}
    return _NEWS


def news_soon(symbol, t_close):
    import bisect
    news()
    for c in (symbol[:3], symbol[3:]):
        v = _HIGH.get(c, [])
        j = bisect.bisect_right(v, t_close)
        if j < len(v) and v[j] <= t_close + 3600:
            return True
    return False


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------
def body_ok(b, d, ratio):
    rng = b["high"] - b["low"]
    return rng > 0 and d * (b["close"] - b["open"]) >= ratio * rng


def signal_cand(bars, i, d, entry_mode):
    """U1/U2/N: stop beyond the signal bar's far end; E1 = LIMIT at its 50% (never worse than the close)."""
    b = bars[i]
    anchor = b["low"] if d == 1 else b["high"]
    c = {"i": i, "time": b["time"], "direction": d, "extreme": anchor, "signal_atr": b["atr"], "zone_low": 0.0,
         "zone_high": 0.0, "points": [], "structure": "NEUTRAL", "kind": "MARKET"}
    if entry_mode == "E1":
        mid = (b["high"] + b["low"]) / 2
        edge = min(mid, b["close"]) if d == 1 else max(mid, b["close"])
        c.update(kind="LIMIT", edge=edge, bars_left=EXPIRY, invalid_at=None)
    return c


def raw_cands(symbol, tf, setup, entry_mode):
    ctx = g93.ctx_for(symbol, tf)
    bars = ctx["entry"]
    sec = context.TF_SECONDS[tf]
    out = []
    if setup in ("U1", "U2"):
        sig = usd_signals(tf, setup)
        for i, b in enumerate(bars):
            u = sig.get(b["time"])
            if u is None or b["atr"] <= 0 or i < 60:
                continue
            out.append(signal_cand(bars, i, filters.USD_SIGN[symbol] * u, entry_mode))
    elif setup == "N":
        ev = news()
        by_bar = {}
        for (t, cur), s in ev.items():
            if cur == "USD":
                d = filters.USD_SIGN[symbol] * s
            elif cur == symbol[:3]:
                d = s
            else:
                continue
            by_bar.setdefault(t - t % sec, []).append(d)
        for i, b in enumerate(bars):
            ds = by_bar.get(b["time"])
            if not ds or b["atr"] <= 0 or i < 60 or abs(sum(ds)) != len(ds):
                continue
            d = ds[0]
            if body_ok(b, d, 0.5) and b["high"] - b["low"] >= b["atr"]:
                out.append(signal_cand(bars, i, d, entry_mode))
    else:  # U3 supply/demand
        used_until = -1
        for i in range(60, len(bars)):
            if i <= used_until:
                continue
            found = None
            for m in (1, 2, 3):
                end = i - m
                a = bars[end]["atr"]
                if a <= 0:
                    continue
                for n in (4, 3, 2):
                    base = bars[end - n + 1:end + 1]
                    if any(x["high"] - x["low"] > 0.8 * a for x in base):
                        continue
                    hi, lo = max(x["high"] for x in base), min(x["low"] for x in base)
                    if bars[i]["close"] - hi >= 2 * a:
                        found = (1, lo, hi, a)
                    elif lo - bars[i]["close"] >= 2 * a:
                        found = (-1, lo, hi, a)
                    if found:
                        break
                if found:
                    break
            if not found:
                continue
            d, lo, hi, a = found
            used_until = i + 3
            anchor = lo if d == 1 else hi
            base_c = {"direction": d, "extreme": anchor, "signal_atr": a, "zone_low": 0.0, "zone_high": 0.0,
                      "points": [], "structure": "NEUTRAL"}
            if entry_mode == "E1":
                out.append(dict(base_c, i=i, time=bars[i]["time"], kind="LIMIT", edge=hi if d == 1 else lo,
                                bars_left=100, invalid_at=None))
            else:
                for k in range(i + 1, min(len(bars), i + 101)):
                    x = bars[k]
                    touched = x["low"] <= hi if d == 1 else x["high"] >= lo
                    if not touched:
                        continue
                    if lo <= x["close"] <= hi:
                        out.append(dict(base_c, i=k, time=x["time"], kind="MARKET"))
                    break
    for c in out:
        c["lab"] = labels(symbol, tf, ctx, c, sec)
    return ctx, sorted(out, key=lambda c: c["i"])


def labels(symbol, tf, ctx, c, sec):
    b = ctx["entry"][c["i"]]
    d = c["direction"]
    ind = g93.indicators(symbol, tf)
    flow = g93.usd_flow(b["time"] + sec)
    return {"F1": 7 <= (b["utc"] // 3600) % 24 < 17,
            "F2": (b["time"] + sec) % 3600 == 0,
            "F3": g92.h4_side(symbol, b["time"]) == d,
            "F4": flow != 0 and d == filters.USD_SIGN[symbol] * flow,
            "F5": not news_soon(symbol, b["time"] + sec),
            "F6": ind["adx"][c["i"]] > 20}


_RAW: dict = {}


def trades(symbol, tf, setup, var, keep=(), stats=None):
    key = (symbol, tf, setup, var[0])
    if key not in _RAW:
        _RAW[key] = raw_cands(symbol, tf, setup, var[0])
    ctx, cs = _RAW[key]
    need = tuple(keep) + (("F4",) if setup == "U3" and var[2] == "U1" else ())
    out, free = [], -1
    for c in cs:
        if c["i"] <= free or not all(c["lab"][f] for f in need):
            continue
        u = ctx["entry"][c["i"]]["utc"]
        p = g93.period(tf, u)
        if p is None:
            continue
        r = replay.evaluate(ctx, c, "FX01", TFS[tf][0], "tm", EXITS[var[1]])
        if stats is not None and c["kind"] == "LIMIT":
            stats["placed"] = stats.get("placed", 0) + 1
            stats["filled"] = stats.get("filled", 0) + (r["status"] == "EVALUATED")
        if r["status"] != "EVALUATED":
            continue
        free = r.get("exit_i", c["i"])
        out.append({"r": r["r"], "utc": u, "p": p, "sym": symbol, "lab": c["lab"]})
    return out


# ---------------------------------------------------------------------------
def main():
    out, cell, mean = g93.out, g93.cell, g93.mean
    L = []
    out(L, "# FX01: vào lệnh EUR/GBP theo USD, vùng cung/cầu, tin tức — lệnh limit, M15/M30/H1 — kết quả")
    out(L)
    out(L, "Kế hoạch: `plans/2026-10-11-fx01-usd-led-limit.md`. EURUSD + GBPUSD gộp, chi phí như G55, một lệnh mỗi lúc "
           "trên mỗi biến thể × cặp. Ô: số lệnh / R mỗi lệnh. E0 thị trường, E1 limit; T1 2R + TM, T2 1,5R chỉ SL/TP.")
    out(L)
    finals, cmp_rows = [], []
    for setup in SETUPS:
        for tf in ("H1", "M30", "M15"):
            out(L, f"## {setup} {tf} — biến thể")
            out(L)
            out(L, "| Biến thể | Train | Validate | Đạt? | Test | Limit khớp |")
            out(L, "|---|---|---|---|---|---|")
            best, best_score, rows_of = None, None, {}
            for var in variants(setup):
                st = {}
                rows = [t for s in SYMBOLS for t in trades(s, tf, setup, var, stats=st)]
                rows_of[var] = rows
                tr = [r["r"] for r in rows if r["p"] == "train"]
                va = [r["r"] for r in rows if r["p"] == "validate"]
                ok = bool(tr) and bool(va) and mean(tr) > 0 and mean(va) > 0 and len(tr) + len(va) >= g93.MIN_TV
                if ok and (best_score is None or min(mean(tr), mean(va)) > best_score):
                    best, best_score = var, min(mean(tr), mean(va))
                fill = f"{st['filled'] / st['placed']:.0%}" if st.get("placed") else "—"
                out(L, f"| {vname(var)} | {cell(rows, 'train')} | {cell(rows, 'validate')} | {'đạt' if ok else ''} | "
                       f"{cell(rows, 'test')} | {fill} |")
            for t in EXITS:
                for extra in (("U0",), ("U1",)) if setup == "U3" else ((),):
                    a, b = rows_of[("E0", t) + extra], rows_of[("E1", t) + extra]
                    cmp_rows.append(f"| {setup} {tf} {t}{'/' + extra[0] if extra else ''} | "
                                    f"{len(a)} / {mean([r['r'] for r in a]):+.3f} | {len(b)} / {mean([r['r'] for r in b]):+.3f} |")
            out(L)
            if best is None:
                out(L, f"**{setup} {tf}: không biến thể nào đạt → dừng.**")
                out(L)
                continue
            out(L, f"Chọn: **{vname(best)}** (min train/validate {best_score:+.3f}).")
            out(L)
            rows = rows_of[best]
            tv = [r for r in rows if r["p"] != "test"]
            out(L, "| Lọc | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ lệnh | Giữ lọc? |")
            out(L, "|---|---|---|---|---|")
            kept, gaps = [], {}
            for f in FILTERS[setup]:
                if (f == "F2" and tf == "H1") or (f == "F4" and setup == "U3" and best[2] == "U1"):
                    continue
                ok, cells, gap = True, [], []
                for q in ("train", "validate"):
                    a = [r["r"] for r in rows if r["p"] == q and r["lab"][f]]
                    b = [r["r"] for r in rows if r["p"] == q and not r["lab"][f]]
                    cells.append(f"{len(a)} {mean(a):+.2f} / {len(b)} {mean(b):+.2f}")
                    ok = ok and bool(a) and bool(b) and mean(a) > mean(b)
                    gap.append(mean(a) - mean(b))
                share = sum(1 for r in tv if r["lab"][f]) / max(len(tv), 1)
                ok = ok and share >= 0.4
                if ok:
                    kept.append(f)
                    gaps[f] = mean(gap)
                out(L, f"| {f} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} |")
            sel = [t for s in SYMBOLS for t in trades(s, tf, setup, best, kept)]
            if kept and len([r for r in sel if r["p"] != "test"]) < 30:
                kept = [max(gaps, key=gaps.get)]
                sel = [t for s in SYMBOLS for t in trades(s, tf, setup, best, kept)]
            out(L)
            out(L, f"Áp lọc **{', '.join(kept) or 'không'}**: train {cell(sel, 'train')}, validate {cell(sel, 'validate')}, "
                   f"**test {cell(sel, 'test')}**.")
            out(L)
            finals.append((setup, tf, best, kept, sel))
    out(L, "## Limit (E1) so với thị trường (E0), cùng tín hiệu, mọi kỳ")
    out(L)
    out(L, "| Ô | E0 thị trường | E1 limit |")
    out(L, "|---|---|---|")
    for r in cmp_rows:
        out(L, r)
    out(L)
    out(L, "## Kiểm tra cuối (kỳ test từng khung)")
    out(L)
    out(L, "| Ô | Biến thể + lọc | Lệnh test | Lệnh/năm | R/lệnh | Cận dưới 90% | Cận dưới 99,2% | Sau trừ 0,10R | %/năm @0,5% | DD @0,5% | Chuỗi thua | EUR | GBP | Đạt? |")
    out(L, "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for setup, tf, best, kept, sel in finals:
        test = sorted([r for r in sel if r["p"] == "test"], key=lambda r: r["utc"])
        rs = [r["r"] for r in test]
        if len(rs) < 2:
            out(L, f"| {setup} {tf} | {vname(best)} {'+'.join(kept)} | {len(rs)} | | | | | | | | | | | không |")
            continue
        yrs = (TFS[tf][4] - TFS[tf][3]) / (365.25 * 86400)
        m, l90, lb, mp = mean(rs), g93.lower(rs, 0.10), g93.lower(rs, 0.10 / 12), mean(rs) - PENALTY
        ok = m > 0 and l90 > 0 and mp > 0
        by = {s: [r["r"] for r in test if r["sym"] == s] for s in SYMBOLS}
        out(L, f"| {setup} {tf} | {vname(best)} {'+'.join(kept) or '—'} | {len(rs)} | {len(rs) / yrs:.0f} | {m:+.3f} | "
               f"{l90:+.3f} | {lb:+.3f} | {mp:+.3f} | {sum(rs) * 0.5 / yrs:+.1f} | {g93.dd_r(rs) * 0.5:.1f}% | "
               f"{g93.streak(rs)} | {len(by['EURUSD'])} {mean(by['EURUSD']):+.2f} | {len(by['GBPUSD'])} "
               f"{mean(by['GBPUSD']):+.2f} | {'**ĐẠT**' + (' (cả Bonferroni)' if lb > 0 else '') if ok else 'không'} |")
    out(L)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
