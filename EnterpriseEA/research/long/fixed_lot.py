"""G25: FTMO 1-Step account simulation, fixed lot per symbol vs fixed risk (0.3%) per trade.

  python fixed_lot.py [--lots EURUSD=0.10,GBPUSD=0.10,USDJPY=0.10,XAUUSD=0.02,BTCUSD=0.01]

Trades come from the long-history study (research/long, same models as G23). They are replayed
in time order on a 10,000 USD account with the EA's FTMO_1_STEP limits (Risk/RiskLimitsProfile.mqh):
per trade 0.3%, open risk 1.2%, internal daily 1.2% / weekly 2.4% loss stops, session quota
(10 SCALP / 5 SWING entries a day), one trade per symbol/side/profile, no opposite exposure,
FTMO floors 3% daily / 10% overall. Fixed lot: a trade whose loss at the stop exceeds the
per-trade cap or the open-risk room is skipped (user decision 05/10). Fixed risk: the trade is
sized to 0.3% (lot rounding ignored). Daily limits use realised results (no floating P/L).
Without --lots, each symbol's lot is the one that loses about 0.3% at its median SWING stop.
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

import long_study as ls
import replay
import setups

CAPITAL = 10_000.0
PER_TRADE, OPEN_RISK, DAILY, WEEKLY = 0.003, 0.012, 0.012, 0.024
FTMO_DAILY, FTMO_OVERALL = 0.03, 0.10
QUOTA = {"SCALP": 10, "SWING": 5}
CONTRACT = {"EURUSD": 100_000, "GBPUSD": 100_000, "USDJPY": 100_000, "XAUUSD": 100, "BTCUSD": 1}
STEP = 0.01
S06_BOX24 = {"box": 24, "max_box_atr": 3.0, "contract": None}


def usd_per_price_lot(symbol: str, price: float) -> float:
    """USD value of a 1.0 price move for one lot (USDJPY profit is in JPY)."""
    v = CONTRACT[symbol]
    return v / price if symbol == "USDJPY" else v


def trades(setup: str, profile: str, variant: dict | None = None) -> list[dict]:
    out = []
    for s in ls.SYMBOLS:
        c = ls.ctx(s, profile)
        if c is None:
            continue
        if setup == "S06":
            p = variant or ls.S06_LIVE
            t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "aligned" if variant is None else "any", "costs": True}
            rows = [replay.evaluate(c, x, "S06", profile, "tm", t) for x in setups.s06(c, p)]
        elif setup == "S02":
            rows = replay.evaluate_all(c, replay.candidates(c, "S02", replay.engine_params("S02", profile)), "S02", profile,
                                       {"costs": True}, "both")
        else:
            rows = [replay.evaluate(c, x, setup, profile, "tm", {"costs": True})
                    for x in replay.candidates(c, setup, replay.engine_params(setup, profile))]
        index = {b["time"]: k for k, b in enumerate(c["entry"])}
        shift = c["entry"][0]["time"] - c["entry"][0]["utc"]
        for r in rows:
            if r["status"] != "EVALUATED":
                continue
            t_in = r.get("fill_time", r["time"])
            # A LIMIT stopped out on its fill bar never reaches the walk (no exit_i): it closes there.
            t_out = c["entry"][r["exit_i"]]["utc"] if "exit_i" in r else c["entry"][index[t_in]]["utc"]
            out.append({"setup": setup if variant is None else setup + "v24", "profile": profile, "symbol": s,
                        "dir": r["direction"], "in": t_in - shift, "out": t_out,
                        "dist": abs(r["entry"] - r["stop"]), "price": r["entry"], "r": r["r"]})
    return out


def default_lots(rows: list[dict]) -> dict:
    lots = {}
    for s in ls.SYMBOLS:
        d = [t["dist"] * usd_per_price_lot(s, t["price"]) for t in rows if t["symbol"] == s and t["profile"] == "SWING"]
        if d:
            lots[s] = max(STEP, math.floor(PER_TRADE * CAPITAL / statistics.median(d) / STEP) * STEP)
    return lots


def simulate(rows: list[dict], mode: str, lots: dict) -> dict:
    eq = CAPITAL
    peak, max_dd = CAPITAL, 0.0
    open_trades: list[dict] = []
    blocked = defaultdict(int)
    taken = 0
    day_pnl = defaultdict(float)
    week_pnl = defaultdict(float)
    day_count = defaultdict(int)
    by_setup = defaultdict(float)
    by_year = defaultdict(float)
    ftmo_fail = None
    day_of = lambda t: t // 86400  # noqa: E731
    week_of = lambda t: (t // 86400 + 3) // 7  # noqa: E731  Monday-based

    def close_until(t):
        nonlocal eq, peak, max_dd, ftmo_fail
        for tr in sorted([x for x in open_trades if x["out"] <= t], key=lambda x: x["out"]):
            open_trades.remove(tr)
            eq += tr["pnl"]
            day_pnl[day_of(tr["out"])] += tr["pnl"]
            week_pnl[week_of(tr["out"])] += tr["pnl"]
            by_setup[tr["setup"] + " " + tr["profile"]] += tr["pnl"]
            by_year[datetime.fromtimestamp(tr["out"], timezone.utc).year] += tr["pnl"]
            peak = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / peak)
            if ftmo_fail is None and (day_pnl[day_of(tr["out"])] <= -FTMO_DAILY * CAPITAL or eq <= (1 - FTMO_OVERALL) * CAPITAL):
                ftmo_fail = datetime.fromtimestamp(tr["out"], timezone.utc).strftime("%Y-%m-%d")

    for t in sorted(rows, key=lambda x: x["in"]):
        close_until(t["in"])
        d, w = day_of(t["in"]), week_of(t["in"])
        cap = min(PER_TRADE * eq, PER_TRADE * CAPITAL)
        if mode == "fixed":
            risk = t["dist"] * usd_per_price_lot(t["symbol"], t["price"]) * lots[t["symbol"]]
        else:
            risk = cap
        reason = None
        if day_pnl[d] <= -DAILY * CAPITAL:
            reason = "DAILY_STOP"
        elif week_pnl[w] <= -WEEKLY * CAPITAL:
            reason = "WEEKLY_STOP"
        elif day_count[(d, t["profile"])] >= QUOTA[t["profile"]]:
            reason = "SESSION_QUOTA"
        elif any(o["symbol"] == t["symbol"] and o["dir"] == -t["dir"] for o in open_trades):
            reason = "OPPOSITE_ACTIVE"
        elif any(o["symbol"] == t["symbol"] and o["dir"] == t["dir"] and o["profile"] == t["profile"] for o in open_trades):
            reason = "DUPLICATE_SAME_SIDE"
        elif mode == "fixed" and risk > cap + 1e-9:
            reason = "FIXED_LOT_OVER_RISK_CAP"
        elif sum(o["risk"] for o in open_trades) + risk > OPEN_RISK * CAPITAL + 1e-9:
            reason = "OPEN_RISK_CAP"
        if reason:
            blocked[reason] += 1
            continue
        taken += 1
        day_count[(d, t["profile"])] += 1
        open_trades.append(dict(t, risk=risk, pnl=t["r"] * risk))
    close_until(10 ** 12)
    years = max(1e-9, (max(x["out"] for x in rows) - min(x["in"] for x in rows)) / (365.25 * 86400)) if rows else 1
    worst_day = min(day_pnl.values(), default=0.0) / CAPITAL
    return {"mode": mode, "taken": taken, "blocked": dict(blocked), "final": eq, "return_pct": (eq / CAPITAL - 1) * 100,
            "per_year_pct": ((eq / CAPITAL) ** (1 / years) - 1) * 100 if eq > 0 else -100.0,
            "max_dd_pct": max_dd * 100, "worst_day_pct": worst_day * 100, "ftmo_fail": ftmo_fail,
            "by_setup": {k: round(v, 2) for k, v in by_setup.items()},
            "by_year_pct": {k: round(v / CAPITAL * 100, 2) for k, v in sorted(by_year.items())}}


def line(name: str, s: dict) -> str:
    blocked = ", ".join(f"{k} {v}" for k, v in sorted(s["blocked"].items(), key=lambda x: -x[1])) or "-"
    return (f"| {name} | {s['mode']} | {s['taken']} | {s['return_pct']:+.1f}% ({s['per_year_pct']:+.2f}%/năm) | "
            f"{s['max_dd_pct']:.1f}% | {s['worst_day_pct']:+.2f}% | {s['ftmo_fail'] or 'không'} | {blocked} |")


def main(argv: list[str]) -> None:
    swing = {k: trades(*k) for k in (("S02", "SWING"), ("S04", "SWING"), ("S06", "SWING"))}
    swing[("S06v24", "SWING")] = trades("S06", "SWING", {"box": 24, "max_box_atr": 3.0, "contraction": 0.85,
                                                         "mode": "immediate", "sl": "far"})
    scalp = {k: trades(*k) for k in (("S02", "SCALP"), ("S04", "SCALP"))}
    all_rows = [t for v in list(swing.values()) + list(scalp.values()) for t in v]
    lots = default_lots(all_rows)
    if "--lots" in argv:
        for part in argv[argv.index("--lots") + 1].split(","):
            k, v = part.split("=")
            lots[k] = float(v)
    window_from = min(t["in"] for v in scalp.values() for t in v)
    window_to = max(t["out"] for v in scalp.values() for t in v)
    in_window = lambda rows: [t for t in rows if window_from <= t["in"] <= window_to]  # noqa: E731
    scenarios = [
        ("SWING live hiện tại (S02+S04+S06), 2010-2025", swing[("S02", "SWING")] + swing[("S04", "SWING")] + swing[("S06", "SWING")]),
        ("Chỉ S04 SWING, 2010-2025", swing[("S04", "SWING")]),
        ("S04 SWING + S06 hộp 24, 2010-2025", swing[("S04", "SWING")] + swing[("S06v24", "SWING")]),
        ("Toàn bộ live gồm SCALP, 06/2024-10/2025",
         in_window(swing[("S02", "SWING")] + swing[("S04", "SWING")] + swing[("S06", "SWING")]) + scalp[("S02", "SCALP")] + scalp[("S04", "SCALP")]),
        ("Chỉ S04 SWING, 06/2024-10/2025", in_window(swing[("S04", "SWING")])),
    ]
    out = ["# G25: mô phỏng tài khoản FTMO 1-Step (10.000 USD)", "",
           "Lot cố định theo symbol: " + ", ".join(f"{k} {v:.2f}" for k, v in lots.items()), "",
           "| Phương án | Cách tính lot | Lệnh vào | Lợi nhuận | Sụt giảm tối đa | Ngày tệ nhất | Vi phạm FTMO | Lệnh bị bỏ |",
           "|---|---|---|---|---|---|---|---|"]
    details = []
    for name, rows in scenarios:
        for mode in ("fixed", "risk"):
            s = simulate(rows, mode, lots)
            out.append(line(name, s))
            details.append(f"- {name} / {mode}: theo setup " + ", ".join(f"{k} {v:+.0f}" for k, v in s["by_setup"].items())
                           + "; theo năm " + ", ".join(f"{k} {v:+.1f}%" for k, v in s["by_year_pct"].items()))
    text = "\n".join(out + ["", "Chi tiết (USD theo setup, % theo năm):"] + details) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "fixed_lot.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
