"""G51: what does the News Guard break-even (D2) cost a T2 trade? MT5 data only, read-only.

  python t2_news_be.py

The EA moves a profitable position (>= be_min_r 0.3R) to break-even from be_before_min (15) minutes before
a HIGH event of one of its currencies (InpNewsIgnoreKeywords excluded), for every profile, T2 included
(user decision 07/10: keep). The research T2 model (candidates_eval.T2_RULE) has no such step, so the edge
monitor compares live T2 with a model that never breaks even before news.

Trades: the research T2 generator (t2_oracle, momentum filter) on the bars the EA exported (D1 from the H1 server
days when there is no D1 file, as in signal_parity), one trade per symbol at a time, entries from 2026-01-06 (the
EA's news log starts 2026-01). Events: the HIGH events the EA recorded (logs/news_reactions.jsonl, impact DIRECT
for the symbol). Each trade is walked twice with the T2 walk of pyramid: as the research model, and with the
break-even set at the start of the H4 bar that holds the moment event - 15 min, when the trade is >= 0.3R at that
bar's open. H4 bars do not tell whether the bar's extreme came before or after that moment, so a single trade can
be off either way. The sample is small (nine months): it measures the size of the gap, not a new rule.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import candidates_eval as ce
import context
import pyramid
import replay
import signal_parity as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Tests"))
import t2_oracle  # noqa: E402

FROM_UTC = int(datetime(2026, 1, 6, tzinfo=timezone.utc).timestamp())
BE_BEFORE_MIN = 15
BE_MIN_R = 0.3
SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD")


def ignore_keywords() -> list[str]:
    shell = (HERE.parents[1] / "EnterpriseEA.mq5").read_text(encoding="utf-8")
    line = shell.split("input string InpNewsIgnoreKeywords", 1)[1].split(";", 1)[0]
    return [k.strip().lower() for k in line.split('"')[1].split(",") if k.strip()]


def news_times(path: Path, symbol: str, keys: list[str]) -> list[int]:
    """UTC times of the HIGH events that put this symbol's trades at break-even."""
    out = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("symbol") != symbol or r.get("impact") != "DIRECT":
                continue
            if any(k in str(r.get("event", "")).lower() for k in keys):
                continue
            out.add(int(r["event_utc"]))
    return sorted(out)


def walk(c: dict, t: dict, rule: dict, triggers: list[int] = (), offset: int = 0) -> tuple[float, int, bool]:
    """pyramid.walk for the T2 rule (no target, partial, break-even or structure exit; ATR trail), plus the News
    Guard break-even: (R before costs, exit bar, break-even used). Without triggers it is pyramid.walk exactly.

    At the start of a bar holding a trigger (event - 15 min, server time), a trade >= BE_MIN_R at the bar's open
    gets its stop at entry + spread, unless the trail already holds it there or beyond."""
    bars, point, d = c["entry"], c["point"], t["dir"]
    entry = t["entry"]
    risk = d * (entry - t["stop"])
    sl, trail, mfe, used, n = t["stop"], False, 0.0, False, 0
    limit = min(len(bars) - 1, t["i"] + rule["timeout"] * 3)
    kind, start_r, k = rule["trail"]
    b = t["i"]
    for b in range(t["i"] + 1, limit + 1):
        n += 1
        bar = bars[b]
        if triggers and not used and any(bar["time"] <= x + offset - BE_BEFORE_MIN * 60 < bar["time"] + 4 * 3600
                                         for x in triggers):
            if d * (bar["open"] - entry) / risk >= BE_MIN_R:
                be_stop = entry + d * bar["spread"] * point
                if d * (be_stop - sl) > 0:
                    sl = be_stop
                    used = True
        sp = bar["spread"] * point if d == -1 else 0.0
        hi, lo, close = bar["high"] + sp, bar["low"] + sp, bar["close"] + sp
        if (d == 1 and lo <= sl) or (d == -1 and hi >= sl):
            fill = sl
            if pyramid.GAP_FILL:
                o = bar["open"] + sp
                if (d == 1 and o < sl) or (d == -1 and o > sl):
                    fill = o
            return d * (fill - entry) / risk, b, used
        mfe = max(mfe, d * ((hi if d == 1 else lo) - entry) / risk)
        if n >= rule["timeout"] and not trail:
            return d * (close - entry) / risk, b, used
        if trail or mfe >= start_r:
            trail = True
            level = bar["close"] - d * k * bar["atr"]
            if d * (level - entry) > 0 and d * (level - sl) >= 0.1 * risk:
                sl = level
    return d * (bars[b]["close"] - entry) / risk, b, used


def paired_ci(diff: list[float], runs: int = 5000, seed: int = 51) -> tuple[float, float]:
    """90% bootstrap interval of the mean of paired differences."""
    import random
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diff, k=len(diff))) for _ in range(runs))
    return means[int(0.05 * runs)], means[int(0.95 * runs) - 1]


def trades(symbol: str) -> list[dict]:
    h4 = context.load_bars(symbol, "H4")
    for i in range(len(h4)):
        h4[i]["atr"] = context.atr_at(h4, i)
    d1 = context.DATA / f"bars_{symbol}_D1.csv"
    daily = context.load_bars(symbol, "D1")[-1000:] if d1.exists() else sp.daily_from_h1(context.load_bars(symbol, "H1"))
    offset = int(context.meta()["server_offset_now"])
    first = max(75, next((i for i, b in enumerate(h4) if b["time"] - offset >= FROM_UTC), len(h4)))
    point = float(context.meta()["by_symbol"][symbol]["point"])
    c = {"entry": h4, "point": point, "symbol": symbol}
    out, busy = [], -1
    for s in t2_oracle.run(h4, daily, first=first, momentum=True):
        i = s["i"]
        if i <= busy:
            continue
        d = s["direction"]
        entry = h4[i]["close"] + (h4[i]["spread"] * point if d == 1 else 0.0)
        t = {"symbol": symbol, "i": i, "dir": d, "entry": entry, "stop": s["anchor"], "target": 0.0, "zl": 0.0, "zh": 0.0}
        r, exit_i, _ = walk(c, t, ce.T2_RULE)
        busy = exit_i
        out.append({"c": c, "t": t, "exit_i": exit_i, "open": exit_i >= len(h4) - 1})
    return out


def main() -> None:
    path = context.DATA.parent / "logs" / "news_reactions.jsonl"
    keys = ignore_keywords()
    offset = int(context.meta()["server_offset_now"])
    gap = pyramid.GAP_FILL
    pyramid.GAP_FILL = True
    rows = []
    try:
        for s in SYMBOLS:
            ev = news_times(path, s, keys)
            for x in trades(s):
                c, t = x["c"], x["t"]
                risk = t["dir"] * (t["entry"] - t["stop"])
                fee = replay.COMMISSION.get(s, 0.0) / risk
                base, _, _ = walk(c, t, ce.T2_RULE)
                assert abs(base - pyramid.walk(c, t, ce.T2_RULE, t["i"], t["entry"], t["stop"], None)[0]) < 1e-9
                be, _, used = walk(c, t, ce.T2_RULE, ev, offset)
                rows.append({"symbol": s, "time": c["entry"][t["i"]]["time"] - offset, "base": base - fee,
                             "be": be - fee, "used": used, "open": x["open"]})
    finally:
        pyramid.GAP_FILL = gap
    print(f"T2 từ {datetime.fromtimestamp(FROM_UTC, timezone.utc):%Y-%m-%d}, {len(rows)} lệnh "
          f"({sum(r['open'] for r in rows)} còn mở, tính tới nến cuối)")
    for s in SYMBOLS + ("ALL",):
        rs = [r for r in rows if s == "ALL" or r["symbol"] == s]
        if not rs:
            continue
        hit = [r for r in rs if r["used"]]
        print(f"{s:7} n={len(rs):3}  mô hình {statistics.fmean(r['base'] for r in rs):+.2f}R "
              f"(tổng {sum(r['base'] for r in rs):+.1f})  có BE tin {statistics.fmean(r['be'] for r in rs):+.2f}R "
              f"(tổng {sum(r['be'] for r in rs):+.1f})  BE kích hoạt {len(hit)}"
              + (f", trên các lệnh đó {statistics.fmean(r['base'] for r in hit):+.2f} → "
                 f"{statistics.fmean(r['be'] for r in hit):+.2f}R" if hit else ""))
    diff = [r["be"] - r["base"] for r in rows]
    lo, hi = paired_ci(diff)
    print(f"Chênh lệch mỗi lệnh (có BE tin − mô hình): {statistics.fmean(diff):+.3f}R, "
          f"khoảng 90% bootstrap [{lo:+.3f}, {hi:+.3f}]")
    for r in rows:
        if r["used"]:
            print(f"  {r['symbol']} {datetime.fromtimestamp(r['time'], timezone.utc):%Y-%m-%d %H:%M} "
                  f"{r['base']:+.2f}R → {r['be']:+.2f}R{' (còn mở)' if r['open'] else ''}")


if __name__ == "__main__":
    main()
