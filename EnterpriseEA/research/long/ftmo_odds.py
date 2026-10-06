"""G30 (part 1): odds of passing the FTMO 1-Step challenge by risk per trade, MT5 data only.

  python ftmo_odds.py

Trades: S04 SWING (current Trade Manager) + S06B with the USD flow (G27), with and without the
+1R add (G28/G29), SWING H1 2010-2025 (exits.py). The challenge (EA: Risk/FtmoHeadroom.mqh,
DailyResetLedger.mqh): 10,000 USD, target +10%, daily loss 3% of the initial balance against the
day's opening balance, overall floor 10% below the highest end-of-day balance (trailing), no time
limit. FTMO also asks that the best day is at most 50% of the total profit when the target is
reached: reported as a separate check. Results are realized at the exit; floating losses are not
modelled (an open trade can only lose its stop, at most the open-risk cap).

Risk per trade r of the initial balance; the EA's internal limits scale with it (open risk 4r,
daily stop 4r, weekly stop 8r, capped below the FTMO limits: 2.5% and 5%). Like the EA's FTMO
headroom check (Risk/FtmoHeadroom.mqh), a trade is taken only if every open stop plus the new
one, all hit today, still leaves 0.5% above the daily and the overall floors.

Two ways to draw challenges:
  ROLLING   start on every Monday 2010-2024 and replay history in order (real overlap and order)
  BOOTSTRAP 3,000 paths of calendar months drawn at random with replacement (other orders of the
            same months, keeps the trades of a month together)
"""
from __future__ import annotations

import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import exits
import filters
import long_study as ls

CAPITAL = 10_000.0
TARGET, DAILY_FTMO, OVERALL_FTMO = 0.10, 0.03, 0.10
RISKS = [0.003, 0.005, 0.0075, 0.01, 0.015]
DAY, WEEK = 86400, 7 * 86400
HORIZON_DAYS = [91, 182, 365, 730]
BUFFER = 0.005
# G32: rule sets. 1-Step: trailing floor from the highest end-of-day balance, best-day check.
# 2-Step (each phase): static floor at the initial balance - 10%, daily 5%, 4 trading days.
ONE_STEP = {"target": TARGET, "daily": DAILY_FTMO, "overall": OVERALL_FTMO, "trailing": True, "min_days": 0}


def limits(r: float, rules: dict = ONE_STEP) -> dict:
    return {"open": 4 * r, "daily": min(4 * r, rules["daily"] - BUFFER), "weekly": min(8 * r, rules["overall"] / 2)}


def challenge(rows: list[dict], r: float, start: int, end: int | None = None, rules: dict = ONE_STEP) -> dict:
    """rows sorted by entry time; replays from `start` until pass, fail or the end of the rows."""
    lim = limits(r, rules)
    daily_ftmo, overall_ftmo, target = rules["daily"], rules["overall"], rules["target"]
    trading_days = set()
    bal, high_eod = CAPITAL, CAPITAL
    day_open = {}                 # day -> balance at the day's start (realized)
    day_pnl, week_pnl = defaultdict(float), defaultdict(float)
    open_trades: list[dict] = []
    events = []

    def day_of(t):
        return t // DAY

    def floor():
        return (high_eod if rules["trailing"] else CAPITAL) - overall_ftmo * CAPITAL

    def close_until(t):
        nonlocal bal, high_eod
        for tr in sorted([x for x in open_trades if x["out"] <= t], key=lambda x: x["out"]):
            open_trades.remove(tr)
            d = day_of(tr["out"])
            if d not in day_open:
                # new day: the previous end-of-day balance raises the trailing high water
                high_eod = max(high_eod, bal)
                day_open[d] = bal
            bal += tr["pnl"]
            day_pnl[d] += tr["pnl"]
            week_pnl[(tr["out"] // DAY + 3) // 7] += tr["pnl"]
            if bal - day_open[d] <= -daily_ftmo * CAPITAL:
                return "FAIL_DAILY", tr["out"]
            if bal <= floor() - 1e-9:
                return "FAIL_OVERALL", tr["out"]
            if bal >= CAPITAL * (1 + target) and len(trading_days) >= rules["min_days"]:
                return "PASS", tr["out"]
        return None, None

    for t in rows:
        if t["in"] < start:
            continue
        if end is not None and t["in"] >= end:
            break
        res, when = close_until(t["in"])
        if res:
            return finish(res, when, start, day_pnl, bal)
        d, w = day_of(t["in"]), (t["in"] // DAY + 3) // 7
        if day_pnl[d] <= -lim["daily"] * CAPITAL or week_pnl[w] <= -lim["weekly"] * CAPITAL:
            continue
        if any(o["symbol"] == t["symbol"] and (o["dir"] == -t["dir"] or o["dir"] == t["dir"]) for o in open_trades):
            continue
        risk = r * CAPITAL
        at_risk = sum(o["risk"] for o in open_trades) + risk
        if at_risk > lim["open"] * CAPITAL + 1e-9:
            continue
        start_today = day_open.get(d, bal)
        if (start_today - bal) + at_risk > (daily_ftmo - BUFFER) * CAPITAL + 1e-9:
            continue
        high_now = max(high_eod, bal if d not in day_open else high_eod) if rules["trailing"] else CAPITAL
        if bal - at_risk < high_now - (overall_ftmo - BUFFER) * CAPITAL - 1e-9:
            continue
        trading_days.add(d)
        open_trades.append(dict(t, risk=risk, pnl=t["r"] * risk))
    res, when = close_until(10 ** 12)
    if res:
        return finish(res, when, start, day_pnl, bal)
    return {"result": "OPEN", "days": None, "best_day_ok": None, "bal": bal}


def finish(res, when, start, day_pnl, bal) -> dict:
    out = {"result": res, "days": (when - start) / DAY, "bal": bal, "best_day_ok": None}
    if res == "PASS":
        profit = bal - CAPITAL
        out["best_day_ok"] = max(day_pnl.values()) <= 0.5 * profit
    return out


def summary(results: list[dict]) -> dict:
    n = len(results)
    passed = [x for x in results if x["result"] == "PASS"]
    failed = [x for x in results if x["result"].startswith("FAIL")]
    out = {"n": n, "pass": len(passed) / n, "fail": len(failed) / n, "open": 1 - (len(passed) + len(failed)) / n,
           "fail_daily": sum(1 for x in failed if x["result"] == "FAIL_DAILY") / n,
           "median_days": statistics.median(x["days"] for x in passed) if passed else None,
           "best_day_ok": sum(1 for x in passed if x["best_day_ok"]) / len(passed) if passed else None}
    for h in HORIZON_DAYS:
        out[f"pass_{h}"] = sum(1 for x in passed if x["days"] <= h) / n
    return out


def bootstrap(rows: list[dict], r: float, paths: int, seed: int, runner=None) -> list[dict]:
    """runner(path, r, start) -> result; default: one 1-Step challenge."""
    runner = runner or challenge
    months = defaultdict(list)
    for t in rows:
        dt = datetime.fromtimestamp(t["in"], timezone.utc)
        months[(dt.year, dt.month)].append(t)
    keys = sorted(months)
    starts = {k: int(datetime(k[0], k[1], 1, tzinfo=timezone.utc).timestamp()) for k in keys}
    rnd = random.Random(seed)
    span = 31 * DAY
    out = []
    for _ in range(paths):
        path = []
        for m in range(60):                       # up to 5 years of drawn months
            k = keys[rnd.randrange(len(keys))]
            shift = m * span - starts[k]
            path += [dict(t, **{"in": t["in"] + shift, "out": t["out"] + shift}) for t in months[k]]
        path.sort(key=lambda x: x["in"])
        out.append(runner(path, r, 0))
    return out


def main() -> None:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    mixes = {
        "S04 + S06B lọc USD": exits.account_rows(c_of, sig["S04"], exits.CURRENT, None, "S04")
        + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, None, "S06B"),
        "S04 + S06B lọc USD, bồi +1R": exits.account_rows(c_of, sig["S04"], exits.CURRENT, None, "S04")
        + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, 1.0, "S06B"),
    }
    lines = ["# G30 phần 1: xác suất vượt FTMO 1-Step theo mức rủi ro (chỉ dữ liệu MT5)", "",
             "Mục tiêu +10%; thua khi lỗ trong ngày ≥ 3% vốn đầu hoặc số dư ≤ đỉnh cuối ngày − 10%; không giới hạn thời gian.", ""]
    first = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    last = int(datetime(2024, 12, 30, tzinfo=timezone.utc).timestamp())
    for name, rows in mixes.items():
        rows = sorted(rows, key=lambda x: x["in"])
        lines += [f"## {name}", "",
                  "| Rủi ro/lệnh | Cách rút | Vượt (không giới hạn) | Vượt ≤ 3 tháng | ≤ 6 tháng | ≤ 12 tháng | ≤ 24 tháng | Trượt | Trượt do lỗ ngày | Thời gian vượt (trung vị) | Vượt mà ngày tốt nhất ≤ 50% |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in RISKS:
            rolling = [challenge(rows, r, s) for s in range(first, last, WEEK)]
            boot = bootstrap(rows, r, 3000, 7)
            for label, res in (("lịch sử, mỗi thứ Hai", rolling), ("xáo tháng ×3000", boot)):
                s = summary(res)
                md = f"{s['median_days']:.0f} ngày" if s["median_days"] is not None else "-"
                bd = f"{s['best_day_ok']:.0%}" if s["best_day_ok"] is not None else "-"
                lines.append(f"| {r:.2%} | {label} | {s['pass']:.0%} | {s['pass_91']:.0%} | {s['pass_182']:.0%} | {s['pass_365']:.0%} | "
                             f"{s['pass_730']:.0%} | {s['fail']:.0%} | {s['fail_daily']:.0%} | {md} | {bd} |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "ftmo_odds.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
