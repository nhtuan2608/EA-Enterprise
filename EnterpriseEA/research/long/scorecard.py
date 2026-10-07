"""G55: one scorecard of every setup x symbol x profile, same costs, same periods, same verdict rule. MT5 data only.

  python scorecard.py              # writes results/scorecard.md and prints it

Rows (R per trade after costs, Trade Manager of each profile, stops that a bar opens beyond fill at the open):
  SWING H1   S02 (live config), S04, S06 (live config), S06B, S06B with the USD flow (USD pairs, live filter)
  POSITION   T2 (H4 Donchian 60, D1 EMA200 side, momentum close; ATR trail), one trade per symbol at a time
  SCALP M5   S02, S04 (M5 history 2024-06 .. 2025-10 only, split in two halves at 2025-02-01)
Symbols: EURUSD, GBPUSD, USDJPY (2010-2025), XAUUSD, BTCUSD (2018-2025), the eight pairs of G36 and XAGUSD, ETHUSD,
USOUSD, SP500 (shorter MT5 history: only the periods they cover).

Verdict, fixed before this run (07/10/2026):
  TIN CẬY   mean > 0 in every period the symbol covers (train 2010-16, validate 2017-20, test 2021-25; at least two
            periods, each with >= 10 trades) and the 90% bootstrap lower bound of the whole-period mean > 0
  THEO DÕI  whole-period mean > 0 and the latest period > 0, but not TIN CẬY
  KHÔNG     anything else; "ít lệnh" when the symbol has < 20 trades
  SCALP: the two halves play the role of the periods.
Reading it: one row per symbol is many comparisons; a single TIN CẬY row among many is weaker evidence than a setup
positive on most symbols. The pooled row of each setup is the main line.
"""
from __future__ import annotations

import random
import statistics
from datetime import datetime, timezone

import long_study as ls  # noqa: F401  (sets the research data path first)
import context  # noqa: E402
import candidates_eval as ce  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402
import t2_news_be as nb  # noqa: E402

FX_OLD = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]
FX_NEW = ["AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP"]
TREND = ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
PERIODS = ("train", "validate", "test")
FROM_UTC = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())


def period_of(utc: int) -> str | None:
    y = datetime.fromtimestamp(utc, timezone.utc).year
    return "train" if 2010 <= y <= 2016 else "validate" if 2017 <= y <= 2020 else "test" if 2021 <= y <= 2025 else None


def lower90(rs: list[float], runs: int = 3000, seed: int = 55) -> float:
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(rs, k=len(rs))) for _ in range(runs))
    return means[int(0.05 * runs)]


def verdict(rows: list[dict], keys=PERIODS) -> tuple[str, dict]:
    rs = [r["r"] for r in rows]
    per = {k: [r["r"] for r in rows if r["period"] == k] for k in keys}
    if len(rs) < 20:
        return "ít lệnh", per
    covered = [k for k in keys if len(per[k]) >= 10]
    latest = next((k for k in reversed(keys) if per[k]), None)
    mean = statistics.fmean(rs)
    if len(covered) >= 2 and all(statistics.fmean(per[k]) > 0 for k in keys if per[k]) and lower90(rs) > 0:
        return "TIN CẬY", per
    if mean > 0 and latest and statistics.fmean(per[latest]) > 0:
        return "THEO DÕI", per
    return "KHÔNG", per


def swing_rows(setup: str, symbol: str, usd: dict, dxy: dict) -> list[dict]:
    c = ls.ctx(symbol, "SWING")
    if c is None:
        return []
    shift = c["entry"][0]["time"] - c["entry"][0]["utc"]
    out = []
    if setup in ("S06B", "S06B_USD"):
        if setup == "S06B_USD" and symbol not in filters.USD_SIGN:
            return []
        for t in exits.trades(setup, symbol, usd, dxy):
            out.append({"utc": t["utc"], "r": pyramid.run(c, t, pyramid.CURRENT)["r"]})
    else:
        if setup == "S06":
            t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "aligned", "costs": True}
            res = [replay.evaluate(c, x, "S06", "SWING", "tm", t) for x in setups.s06(c, ls.S06_LIVE)]
        else:
            cands = [x for x in replay.candidates(c, setup, replay.engine_params(setup, "SWING")) if x.get("kind") != "LIMIT"]
            res = [replay.evaluate(c, x, setup, "SWING", "tm", {"costs": True}) for x in cands]
        out = [{"utc": r["time"] - shift, "r": r["r"]} for r in res if r["status"] == "EVALUATED"]
    for r in out:
        r["period"] = period_of(r["utc"])
    return [r for r in out if r["period"]]


def t2_rows(symbol: str) -> list[dict]:
    if not (context.DATA / f"bars_{symbol}_H4.csv").exists() or not (context.DATA / f"bars_{symbol}_D1.csv").exists():
        return []
    offset = int(context.meta()["server_offset_now"])
    out = []
    for x in nb.trades(symbol, FROM_UTC, all_daily=True):
        c, t = x["c"], x["t"]
        risk = t["dir"] * (t["entry"] - t["stop"])
        r = nb.walk(c, t, ce.T2_RULE)[0] - replay.COMMISSION.get(symbol, 0.0) / risk
        utc = c["entry"][t["i"]]["time"] - offset
        out.append({"utc": utc, "r": r, "period": period_of(utc)})
    return [r for r in out if r["period"]]


def scalp_rows(setup: str, symbol: str) -> list[dict]:
    c = ls.ctx(symbol, "SCALP")
    if c is None:
        return []
    shift = c["entry"][0]["time"] - c["entry"][0]["utc"]
    cands = [x for x in replay.candidates(c, setup, replay.engine_params(setup, "SCALP")) if x.get("kind") != "LIMIT"]
    res = [replay.evaluate(c, x, setup, "SCALP", "tm", {"costs": True}) for x in cands]
    out = [{"utc": r["time"] - shift, "r": r["r"]} for r in res if r["status"] == "EVALUATED"]
    for r in out:
        r["period"] = "first" if r["utc"] < ls.SCALP_SPLIT else "second"
    return out


def cell(rows: list[dict], keys=PERIODS) -> str:
    v, per = verdict(rows, keys)
    if not rows:
        return "–"
    parts = " / ".join(f"{statistics.fmean(per[k]):+.2f}" if per[k] else "·" for k in keys)
    return f"**{v}** {statistics.fmean(r['r'] for r in rows):+.2f}R n={len(rows)} ({parts})"


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    lines = ["# G55: bảng điểm mọi setup × symbol × profile (chỉ dữ liệu MT5)", "",
             "R/lệnh sau phí; trong ngoặc: 2010–16 / 2017–20 / 2021–25 (· = không có dữ liệu). Tiêu chí ghi trong "
             "`research/long/scorecard.py`, đặt trước khi chạy.", ""]
    swing = ("S02", "S04", "S06", "S06B", "S06B_USD")
    lines += ["## SWING H1 và POSITION H4 (T2)", "",
              "| Symbol | " + " | ".join(swing) + " | T2 |", "|---|" + "---|" * (len(swing) + 1)]
    pooled = {k: [] for k in swing + ("T2",)}
    for s in FX_OLD + FX_NEW + TREND:
        row = []
        for setup in swing:
            rs = swing_rows(setup, s, usd, dxy) if s not in TREND else []
            pooled[setup] += rs
            row.append(cell(rs))
        t2 = t2_rows(s)
        pooled["T2"] += t2
        row.append(cell(t2))
        lines.append(f"| {s} | " + " | ".join(row) + " |")
        print(lines[-1], flush=True)
    lines.append("| **Gộp** | " + " | ".join(cell(pooled[k]) for k in swing + ("T2",)) + " |")
    lines += ["", "## SCALP M5 (2024-06 → 2025-02 / 2025-02 → 2025-10)", "", "| Symbol | S02 | S04 |", "|---|---|---|"]
    sp = {"S02": [], "S04": []}
    for s in FX_OLD:
        row = []
        for setup in ("S02", "S04"):
            rs = scalp_rows(setup, s)
            sp[setup] += rs
            row.append(cell(rs, ("first", "second")))
        lines.append(f"| {s} | " + " | ".join(row) + " |")
    lines.append("| **Gộp** | " + " | ".join(cell(sp[k], ("first", "second")) for k in ("S02", "S04")) + " |")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "scorecard.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
