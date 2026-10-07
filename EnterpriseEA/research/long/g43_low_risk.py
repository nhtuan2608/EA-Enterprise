"""G43 part 1: low risk with a good reward-to-risk at the portfolio level (S04 + S06B + T2). MT5 data only.

  python g43_low_risk.py            # every part
  python g43_low_risk.py A B C      # some parts

Plan: docs/superpowers/plans/2026-10-06-g43-low-risk-high-rr.md. Every choice is made on 2010-2016 (train) and
reported on 2017-2020 (validate) and 2021-2025 (test). The account follows fixed_lot.simulate (0.3% per trade
on min(equity, capital), daily 1.2% / weekly 2.4% stops, open risk cap, one trade per symbol + side + profile,
no opposite trades), with a risk multiplier hook for the management layers:
  A   baseline: M5 (S04 + S06B USD flow + add) + T2 on five symbols, and + T2 on XAU/BTC only (the live list)
  B1  risk weight by setup: equal, inverse R standard deviation, mean / variance (capped), estimated on train
  B2  drawdown throttle: risk x0.5 while the drawdown from the peak exceeds d; control = the same share of
      trades at half risk picked at random (300 runs)
  B3  equity-curve filter by setup: skip a setup while the sum of its last N results (virtual) is below 0;
      control = the same number of trades skipped at random (300 runs)
  B4  open risk cap
  C1  T2 exits: initial stop x ATR trail grid (per-trade expectancy, reward-to-risk, three periods)
  C2  T2 add at +1R / +2R (same money risk, stop of the first leg at break-even)
Metrics: %/year, max DD, MAR, Ulcer, worst year, share of positive weeks / months / years, median and p10 of
weekly and monthly results, bootstrap of months (p10 %/year, p90 DD) and the score p10 / DD p90.
"""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import robustness as rb  # noqa: E402

CAPITAL = 10_000.0
PER_TRADE, OPEN_RISK, DAILY, WEEKLY = 0.003, 0.012, 0.012, 0.024
QUOTA = {"SCALP": 10, "SWING": 5, "POSITION": 5}
T2 = {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}
Y2017 = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp())
Y2021 = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2025, 10, 10, tzinfo=timezone.utc).timestamp())
PERIODS = {"train": (0, Y2017), "validate": (Y2017, Y2021), "test": (Y2021, END), "all": (0, END)}
BOOT_RNG = 43


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------
def t2_rows(p: dict, symbols: list[str], add_at=None, start: int = 0) -> list[dict]:
    """T2 account rows (discovery.trades with an optional add)."""
    tf, _, sig, rule_fn = dv.FAMILIES["T2"]
    rule = rule_fn(p)
    out = []
    for s in symbols:
        B = dv.load(s, tf)
        if B is None:
            continue
        bars, busy = B["bars"], -1
        for i, d, stop_atr in sig(B, p):
            if i <= busy or B["utc"][i] < start or i >= len(bars) - 2:
                continue
            b = bars[i]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = stop_atr * B["atr"][i]
            if risk <= 0:
                continue
            t = {"symbol": s, "i": i, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * 3 * risk, "zl": 0.0, "zh": 0.0}
            res = pyramid.run(B["ctx"], t, rule, add_at)
            busy = res["exit_i"]
            out.append({"setup": "T2", "profile": "POSITION", "symbol": s, "dir": d, "in": int(B["utc"][i]),
                        "out": int(B["utc"][min(res["exit_i"], len(bars) - 1)]), "dist": risk, "price": entry,
                        "r": res["r"]})
    return out


def base_rows() -> list[dict]:
    pyramid.GAP_FILL = True
    rb.init_worker()
    usd, dxy = filters.usd_index(), filters.real_dxy()
    s04 = [t for s in ls.SYMBOLS for t in exits.trades("S04", s, usd, dxy)]
    s06 = [t for s in ls.SYMBOLS for t in exits.trades("S06B_USD", s, usd, dxy)]
    return (exits.account_rows(rb._C, s04, pyramid.CURRENT, None, "S04")
            + exits.account_rows(rb._C, s06, pyramid.CURRENT, 1.0, "S06B"))


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
def simulate(rows: list[dict], mult=None, open_risk: float | None = None, skip: set | None = None,
             start: int = 0, end: int = END) -> dict:
    """fixed_lot.simulate with a risk multiplier mult(trade, state) -> factor (0 = skip).

    open_risk None = the module's OPEN_RISK at call time (G58: a default bound at definition time ignored a later
    change of OPEN_RISK, so a per-trade risk above 1.2% was never taken)."""
    if open_risk is None:
        open_risk = OPEN_RISK
    eq = peak = CAPITAL
    max_dd, ulcer = 0.0, []
    open_trades: list[dict] = []
    day_pnl, week_pnl = defaultdict(float), defaultdict(float)
    day_count = defaultdict(int)
    by_year, by_month, by_week = defaultdict(float), defaultdict(float), defaultdict(float)
    taken = []
    history = defaultdict(list)          # setup -> virtual results in exit order (for the equity-curve filter)
    pending = sorted([t for t in rows if start <= t["in"] < end], key=lambda x: x["out"])
    hist_i = 0
    day_of = lambda t: t // 86400  # noqa: E731
    week_of = lambda t: (t // 86400 + 3) // 7  # noqa: E731

    def close_until(t):
        nonlocal eq, peak, max_dd
        for tr in sorted([x for x in open_trades if x["out"] <= t], key=lambda x: x["out"]):
            open_trades.remove(tr)
            eq += tr["pnl"]
            day_pnl[day_of(tr["out"])] += tr["pnl"]
            week_pnl[week_of(tr["out"])] += tr["pnl"]
            dt = datetime.fromtimestamp(tr["out"], timezone.utc)
            by_year[dt.year] += tr["pnl"]
            by_month[(dt.year, dt.month)] += tr["pnl"]
            by_week[week_of(tr["out"])] += tr["pnl"]
            peak = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / peak)
            ulcer.append(((peak - eq) / peak) ** 2)

    state = {"history": history}
    for k, t in enumerate(sorted([x for x in rows if start <= x["in"] < end], key=lambda x: x["in"])):
        close_until(t["in"])
        while hist_i < len(pending) and pending[hist_i]["out"] <= t["in"]:
            history[pending[hist_i]["setup"]].append(pending[hist_i]["r"])
            hist_i += 1
        d, w = day_of(t["in"]), week_of(t["in"])
        state.update(eq=eq, peak=peak, dd=(peak - eq) / peak)
        f = mult(t, state) if mult else 1.0
        if skip is not None and id(t) in skip:
            f = 0.0
        if f <= 0.0:
            continue
        risk = min(PER_TRADE * eq, PER_TRADE * CAPITAL) * f
        if day_pnl[d] <= -DAILY * CAPITAL or week_pnl[w] <= -WEEKLY * CAPITAL:
            continue
        if day_count[(d, t["profile"])] >= QUOTA[t["profile"]]:
            continue
        if any(o["symbol"] == t["symbol"] and o["dir"] == -t["dir"] for o in open_trades):
            continue
        if any(o["symbol"] == t["symbol"] and o["dir"] == t["dir"] and o["profile"] == t["profile"] for o in open_trades):
            continue
        if sum(o["risk"] for o in open_trades) + risk > open_risk * CAPITAL + 1e-9:
            continue
        day_count[(d, t["profile"])] += 1
        tr = dict(t, risk=risk, pnl=t["r"] * risk, f=f)
        open_trades.append(tr)
        taken.append(tr)
    close_until(10 ** 12)
    return {"eq": eq, "max_dd": max_dd, "ulcer": float(np.sqrt(np.mean(ulcer))) if ulcer else 0.0, "taken": taken,
            "by_year": dict(by_year), "by_month": dict(by_month), "by_week": dict(by_week), "start": start, "end": end}


def months_array(s: dict) -> np.ndarray:
    lo = datetime.fromtimestamp(max(s["start"], int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())), timezone.utc)
    hi = datetime.fromtimestamp(min(s["end"], END) - 1, timezone.utc)
    keys, y, m = [], lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        keys.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return np.array([s["by_month"].get(k, 0.0) / CAPITAL * 100 for k in keys])


def metrics(s: dict, boot: bool = True) -> dict:
    months = months_array(s)
    years = max(len(months) / 12, 1e-9)
    total = (s["eq"] / CAPITAL - 1) * 100
    per_year = total / years
    dd = s["max_dd"] * 100
    yrs = [v / CAPITAL * 100 for v in s["by_year"].values()]
    weeks = np.array([v / CAPITAL * 100 for v in s["by_week"].values()]) if s["by_week"] else np.zeros(1)
    wins = [t["r"] for t in s["taken"] if t["r"] > 0]
    losses = [-t["r"] for t in s["taken"] if t["r"] <= 0]
    out = {"n": len(s["taken"]), "per_year": per_year, "dd": dd, "mar": per_year / max(dd, 0.01),
           "ulcer": s["ulcer"] * 100, "worst_year": min(yrs) if yrs else 0.0,
           "pos_years": sum(v > 0 for v in yrs) / max(len(yrs), 1),
           "pos_months": float(np.mean(months > 0)) if len(months) else 0.0,
           "pos_weeks": float(np.mean(weeks > 0)), "month_p10": float(np.quantile(months, 0.10)) if len(months) else 0.0,
           "month_med": float(np.median(months)) if len(months) else 0.0, "worst_month": float(months.min()) if len(months) else 0.0,
           "week_p10": float(np.quantile(weeks, 0.10)), "worst_week": float(weeks.min()),
           "win": len(wins) / max(len(s["taken"]), 1),
           "rr": (statistics.fmean(wins) / statistics.fmean(losses)) if wins and losses else 0.0,
           "exp_r": statistics.fmean(t["r"] for t in s["taken"]) if s["taken"] else 0.0}
    if boot and len(months) >= 24:
        b = rb.bootstrap(months, np.random.default_rng(BOOT_RNG))
        out.update(ann_p10=b["ann_p10"], dd_p90=b["dd_p90"], score=b["ann_p10"] / max(b["dd_p90"], 0.1))
    else:
        out.update(ann_p10=0.0, dd_p90=0.0, score=0.0)
    return out


def by_period(rows, **kw) -> dict:
    return {k: metrics(simulate(rows, start=a, end=b, **kw)) for k, (a, b) in PERIODS.items()}


HEAD = ("| Phương án | Kỳ | %/năm | DD | MAR | Năm dương | Tháng dương | Tuần dương | Tháng p10 / tệ nhất | "
        "RR | Thắng | R TB | Điểm |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def row(name: str, period: str, m: dict) -> str:
    return (f"| {name} | {period} | {m['per_year']:+.2f}% | {m['dd']:.1f}% | {m['mar']:.2f} | {m['pos_years']:.0%} | "
            f"{m['pos_months']:.0%} | {m['pos_weeks']:.0%} | {m['month_p10']:+.2f}% / {m['worst_month']:+.2f}% | "
            f"{m['rr']:.2f} | {m['win']:.0%} | {m['exp_r']:+.3f} | {m['score']:.2f} |")


def table(name: str, res: dict, periods=("train", "validate", "test", "all")) -> list[str]:
    return [row(name, p, res[p]) for p in periods]


# ---------------------------------------------------------------------------
# Management layers
# ---------------------------------------------------------------------------
def weights_on_train(rows: list[dict], kind: str) -> dict:
    by = defaultdict(list)
    for t in rows:
        if t["in"] < Y2017:
            by[t["setup"]].append(t["r"])
    w = {}
    for k, v in by.items():
        sd = statistics.pstdev(v) or 1.0
        mu = statistics.fmean(v)
        w[k] = 1.0 if kind == "equal" else 1.0 / sd if kind == "invvol" else max(mu, 0.0) / sd ** 2
    mean_w = statistics.fmean(w.values()) or 1.0
    return {k: min(2.0, max(0.5, v / mean_w)) for k, v in w.items()}


def throttle(d: float, factor: float = 0.5):
    return lambda t, s: factor if s["dd"] > d else 1.0


def ecf(n: int):
    def f(t, s):
        h = s["history"][t["setup"]]
        return 0.0 if len(h) >= n and sum(h[-n:]) < 0 else 1.0
    return f


def random_control(rows, real_metric: float, kind: str, share: float, runs: int = 300, start=0, end=END) -> float:
    """p = share of random runs (same share of trades at half risk / skipped) whose score reaches the real one."""
    rng = np.random.default_rng(431)
    sel = [t for t in rows if start <= t["in"] < end]
    hits = 0
    for _ in range(runs):
        pick = {id(t) for t in sel if rng.random() < share}
        if kind == "half":
            s = simulate(rows, mult=lambda t, st, p=pick: 0.5 if id(t) in p else 1.0, start=start, end=end)
        else:
            s = simulate(rows, skip=pick, start=start, end=end)
        hits += metrics(s)["score"] >= real_metric
    return hits / runs


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    parts = set(argv) or {"A", "B", "C"}
    pyramid.GAP_FILL = True
    base = base_rows()
    t2_all = t2_rows(T2, ls.SYMBOLS)
    t2_live = [t for t in t2_all if t["symbol"] in ("XAUUSD", "BTCUSD")]
    p0 = base + t2_all
    lines = ["# G43 phần 1: rủi ro thấp, RR cao ở cấp danh mục (chỉ dữ liệu MT5)", "",
             "Chọn trên 2010–2016 (train), kiểm chứng 2017–2020 (validate) và 2021–2025 (test). 0,3%/lệnh, chặn ngày 1,2% / tuần 2,4%.", ""]

    if "A" in parts:
        lines += ["## A. Mốc", "", *HEAD]
        for name, rows in (("M5", base), ("P0 = M5 + T2 (5 symbol)", p0), ("P0b = M5 + T2 XAU/BTC", base + t2_live)):
            lines += table(name, by_period(rows))
        lines.append("")

    if "B" in parts:
        lines += ["## B1. Phân bổ rủi ro theo setup (ước trên 2010–2016, trần 0,5–2×)", "", *HEAD]
        for kind in ("equal", "invvol", "meanvar"):
            w = weights_on_train(p0, kind)
            res = by_period(p0, mult=lambda t, s, w=w: w[t["setup"]])
            lines += table(f"{kind} {', '.join(f'{k} {v:.2f}' for k, v in sorted(w.items()))}", res)
        lines += ["", "## B2. Giảm rủi ro ×0,5 khi DD từ đỉnh > d", "", *HEAD]
        for d in (0.02, 0.03, 0.04, 0.06):
            res = by_period(p0, mult=throttle(d))
            s_all = simulate(p0, mult=throttle(d))
            share = float(np.mean([t["f"] < 1.0 for t in s_all["taken"]])) if s_all["taken"] else 0.0
            p_ctrl = random_control(p0, res["all"]["score"], "half", max(share, 0.01))
            lines += table(f"d = {d:.0%} (lệnh ở nửa rủi ro {share:.0%}; ngẫu nhiên p = {p_ctrl:.2f})", res)
        lines += ["", "## B3. Lọc theo đường vốn của setup (bỏ khi tổng N lệnh gần nhất < 0)", "", *HEAD]
        for n in (10, 20, 30):
            res = by_period(p0, mult=ecf(n))
            share = max(0.0, 1 - len(simulate(p0, mult=ecf(n))["taken"]) / max(len(simulate(p0)["taken"]), 1))
            p_ctrl = random_control(p0, res["all"]["score"], "skip", max(share, 0.01))
            lines += table(f"N = {n} (bỏ {share:.0%} lệnh; ngẫu nhiên p = {p_ctrl:.2f})", res)
        lines += ["", "## B4. Trần rủi ro mở", "", *HEAD]
        for cap in (0.009, 0.012, 0.018, 0.024):
            lines += table(f"trần mở {cap:.1%}", by_period(p0, open_risk=cap))
        lines.append("")

    if "C" in parts:
        lines += ["## C1. Thoát lệnh T2 (5 symbol, theo lệnh)", "",
                  "| Dừng đầu × trail | Train R / RR / thắng | Validate R / RR / thắng | Test R / RR / thắng | Lệnh |", "|---|---|---|---|---|"]

        def st(rs):
            if not rs:
                return "n=0"
            w = [r for r in rs if r > 0]
            l_ = [-r for r in rs if r <= 0]
            rr = statistics.fmean(w) / statistics.fmean(l_) if w and l_ else 0.0
            return f"{statistics.fmean(rs):+.3f} / {rr:.2f} / {len(w) / len(rs):.0%}"
        for stop in (1.5, 2.0, 3.0):
            for trail in (2.0, 2.5, 3.0, 4.0, 5.0):
                rows = t2_rows(dict(T2, stop=stop, trail=trail), ls.SYMBOLS)
                per = {k: [t["r"] for t in rows if a <= t["in"] < b] for k, (a, b) in PERIODS.items()}
                lines.append(f"| {stop} × {trail} | {st(per['train'])} | {st(per['validate'])} | {st(per['test'])} | {len(rows)} |")
        lines += ["", "## C2. Bồi lệnh T2", "", *HEAD]
        for add in (None, 1.0, 2.0):
            rows = t2_rows(T2, ls.SYMBOLS, add_at=add)
            lines += table(f"M5 + T2 bồi {add if add else 'không'}", by_period(base + rows))
        lines.append("")

    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / f"g43_{'_'.join(sorted(parts))}.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv[1:])
