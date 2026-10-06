"""G33 (part 2): where should the stop and the target be for a better reward/risk? MT5 data only.

  python stops_targets.py

Signals: S04 SWING and S06B with the USD flow (G27), SWING H1 2010-2025, current Trade Manager
(pyramid.CURRENT), stops that a bar opens beyond fill at the open (pyramid.GAP_FILL).

1. Adverse excursion: how far against the entry do the trades that later reach +2R go first?
   If almost every good trade stays within 0.6R, a tighter stop raises the reward/risk.
2. Stop distance: the structural stop scaled by k (0.5 .. 1.5) with the same target price
   (a tighter stop = more R to the same target), and S06B with the stop at the middle of the box.
3. Target by regime: the target R (2, 3, 4, 6) chosen per ADX tercile on 2010-2016 only.
R is always per unit of the trade's own risk, so expectancies compare directly at a fixed % risk.
Selection on 2010-2016; 2017-2020 and 2021-2025 only report. Account replay: FTMO 1-Step,
0.3% per trade (fixed_lot.simulate).
"""
from __future__ import annotations

import statistics

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import fixed_lot as fl  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

SCALES = [0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5]
TARGETS = [2.0, 3.0, 4.0, 6.0]
S06B_MID = dict(filters.S06B, sl="mid")


def mae_before(c: dict, t: dict, reach: float, horizon: int = 240):
    """(MAE in R before the trade first reaches +reach R, reached?) with only the initial stop."""
    bars, point, d = c["entry"], c["point"], t["dir"]
    risk = d * (t["entry"] - t["stop"])
    mae = 0.0
    for b in range(t["i"] + 1, min(len(bars) - 1, t["i"] + horizon) + 1):
        sp = bars[b]["spread"] * point if d == -1 else 0.0
        hi, lo = bars[b]["high"] + sp, bars[b]["low"] + sp
        adverse = d * (t["entry"] - (lo if d == 1 else hi)) / risk
        if (d == 1 and lo <= t["stop"]) or (d == -1 and hi >= t["stop"]):
            return 1.0, False
        mae = max(mae, adverse)
        if d * ((hi if d == 1 else lo) - t["entry"]) / risk >= reach:
            return mae, True
    return mae, False


def scaled(t: dict, k: float, keep_target: bool = True) -> dict:
    risk = t["dir"] * (t["entry"] - t["stop"])
    out = dict(t, stop=t["entry"] - t["dir"] * k * risk)
    if not keep_target:
        out["target"] = t["entry"] + t["dir"] * (t["dir"] * (t["target"] - t["entry"]) / risk) * k * risk
    return out


def evaluate(c_of: dict, sig: list[dict], rule: dict = pyramid.CURRENT) -> list[dict]:
    return [{"utc": t["utc"], "r": pyramid.run(c_of[t["symbol"]], t, rule)["r"]} for t in sig]


def account(c_of: dict, parts: list[tuple[list[dict], str]]) -> dict:
    rows = [x for sig, label in parts for x in exits.account_rows(c_of, sig, pyramid.CURRENT, None, label)]
    return fl.simulate(rows, "risk", {})


def acc_line(name: str, s: dict) -> str:
    y = s["by_year_pct"]
    return (f"| {name} | {s['taken']} | {s['per_year_pct']:+.2f}% | {s['max_dd_pct']:.1f}% | "
            f"{sum(1 for v in y.values() if v > 0)}/{len(y)} |")


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    # S06B with the stop at the middle of the box (USD flow kept), planned like exits.trades.
    mid = []
    for s in ls.SYMBOLS:
        c = c_of[s]
        bars = c["entry"]
        shift = bars[0]["time"] - bars[0]["utc"]
        tt = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
        rows = []
        for x in setups.s06(c, S06B_MID):
            r = replay.evaluate(c, x, "S06", "SWING", "tm", tt)
            if r["status"] == "EVALUATED":
                rows.append({"symbol": s, "i": x["i"], "time": bars[x["i"]]["time"], "utc": bars[x["i"]]["time"] - shift,
                             "dir": x["direction"], "entry": r["entry"], "stop": r["stop"], "target": r["target"],
                             "zl": x["zone_low"], "zh": x["zone_high"], "r_replay": r["r"]})
        filters.tag(rows, s, usd, dxy)
        mid += [t for t in rows if t["f"]["USD_FLOW"]]
    lines = ["# G33 phần 2: đặt SL/TP cho RR tốt hơn (chỉ dữ liệu MT5)", ""]

    # 1. Adverse excursion of the good trades.
    lines += ["## 1. Lệnh tốt đi ngược bao xa trước khi chạy (MAE, tính theo R của dừng lỗ hiện tại)", "",
              "| Setup | Lệnh chạm +2R | MAE trung vị | 75% | 90% | Lệnh chạm +2R mà MAE < 0,5R | < 0,75R |", "|---|---|---|---|---|---|---|"]
    for name, s in sig.items():
        good = [m for m, ok in (mae_before(c_of[t["symbol"]], t, 2.0) for t in s) if ok]
        if not good:
            continue
        q = sorted(good)
        lines.append(f"| {name} | {len(good)}/{len(s)} | {statistics.median(q):.2f} | {q[int(0.75 * len(q))]:.2f} | "
                     f"{q[int(0.9 * len(q))]:.2f} | {sum(1 for v in q if v < 0.5) / len(q):.0%} | {sum(1 for v in q if v < 0.75) / len(q):.0%} |")

    # 2. Stop distance.
    lines += ["", "## 2. Khoảng cách dừng lỗ (cùng giá chốt lời: dừng lỗ hẹp hơn = RR cao hơn)", "",
              "| Setup | Dừng lỗ × | Train | Validate | Test | Năm dương | DD (R) |", "|---|---|---|---|---|---|---|"]
    best_k = {}
    for name, s in sig.items():
        res = []
        for k in SCALES:
            v = exits.split(evaluate(c_of, [scaled(t, k) for t in s]))
            res.append((k, v))
            lines.append(f"| {name} | {k:.2f} | {exits.fmt(v['train'])} | {exits.fmt(v['validate'])} | {exits.fmt(v['test'])} | "
                         f"{v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} |")
        best_k[name] = max(res, key=lambda kv: exits.score(kv[1]))[0]
    v = exits.split(evaluate(c_of, mid))
    lines.append(f"| S06B_USD dừng lỗ giữa hộp | – | {exits.fmt(v['train'])} | {exits.fmt(v['validate'])} | {exits.fmt(v['test'])} | "
                 f"{v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} |")

    # 3. Target by ADX regime.
    lines += ["", "## 3. Chốt lời theo chế độ thị trường (ADX), chọn trên 2010–2016", "",
              "| Setup | ADX thấp | ADX giữa | ADX cao | Train | Validate | Test | Năm dương |", "|---|---|---|---|---|---|---|---|"]
    adaptive = {}
    for name, s in sig.items():
        by_tercile = {}
        adx_of = {}
        for sym in ls.SYMBOLS:
            a = filters.adx(c_of[sym]["entry"])
            for t in s:
                if t["symbol"] == sym:
                    adx_of[id(t)] = a[t["i"]]
        tr = sorted(adx_of[id(t)] for t in s if exits.period(t["utc"]) == "train")
        cut = (tr[len(tr) // 3], tr[2 * len(tr) // 3])
        group = lambda t: 0 if adx_of[id(t)] < cut[0] else (1 if adx_of[id(t)] < cut[1] else 2)  # noqa: E731
        choice = {}
        for g in range(3):
            part = [t for t in s if group(t) == g and exits.period(t["utc"]) == "train"]
            best = max(TARGETS, key=lambda R: statistics.fmean(
                pyramid.run(c_of[t["symbol"]], t, dict(pyramid.CURRENT, target=R))["r"] for t in part) if part else 0)
            choice[g] = best
        rows = [{"utc": t["utc"], "r": pyramid.run(c_of[t["symbol"]], t, dict(pyramid.CURRENT, target=choice[group(t)]))["r"]} for t in s]
        v = exits.split(rows)
        adaptive[name] = (choice, group)
        lines.append(f"| {name} | {choice[0]:g}R | {choice[1]:g}R | {choice[2]:g}R | {exits.fmt(v['train'])} | "
                     f"{exits.fmt(v['validate'])} | {exits.fmt(v['test'])} | {v['all']['pos_years']:.0%} |")
        base = exits.split(evaluate(c_of, s))
        lines.append(f"| {name} (hiện tại) | | | | {exits.fmt(base['train'])} | {exits.fmt(base['validate'])} | "
                     f"{exits.fmt(base['test'])} | {base['all']['pos_years']:.0%} |")

    # Account replay.
    lines += ["", "## 4. Tài khoản FTMO 1-Step, 0,3%/lệnh, 2010–2025", "",
              "| Phương án | Lệnh | %/năm | DD tối đa | Năm dương |", "|---|---|---|---|---|"]
    lines.append(acc_line("S04 + S06B lọc USD, hiện tại", account(c_of, [(sig["S04"], "S04"), (sig["S06B_USD"], "S06B")])))
    lines.append(acc_line(f"Dừng lỗ ×{best_k['S04']:g} (S04), ×{best_k['S06B_USD']:g} (S06B), chọn trên train",
                          account(c_of, [([scaled(t, best_k["S04"]) for t in sig["S04"]], "S04"),
                                         ([scaled(t, best_k["S06B_USD"]) for t in sig["S06B_USD"]], "S06B")])))
    lines.append(acc_line("S04 + S06B lọc USD dừng lỗ giữa hộp", account(c_of, [(sig["S04"], "S04"), (mid, "S06B")])))
    text = "\n".join(lines) + "\n"
    (ls.OUT / "stops_targets.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
