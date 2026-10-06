"""G28 (part 1 after G27): exit management and pyramiding for the setups that have an edge.

  python exits.py

Signals: S04 SWING (structural target) and S06B (24-bar box, entry on release, 3R), with and
without the USD-flow filter (G27). MT5 data only (research/long/data, 2010-2025).

1. Path statistics: with only the initial stop, how far do trades run before it is hit?
   P(MFE >= k R) and P(reach 3R | reached 1R), within 240 bars.
2. Exit rules, walked bar by bar with the same conventions as replay._walk_tm (exits on the
   closing side, a stop touch wins over a target touch in one bar, commission per leg):
   target R, break-even, partial close, trailing (structure or ATR), time stop. The current
   SWING Trade Manager is one of the rules and must reproduce replay.evaluate.
3. Pyramiding: one add of the same risk unit at the close of the bar where the trade first
   reaches +k R, both legs' stop at the first entry (break-even), so open risk never exceeds
   one unit. The add follows the same exit rule.
Selection on 2010-2016 only (expectancy > 0, share of positive years, max drawdown, return /
drawdown), validate 2017-2020 and test 2021-2025 reported. The chosen rules are replayed on
the FTMO 1-Step account (fixed_lot.simulate, 0.3% per trade).
"""
from __future__ import annotations

import itertools
import statistics
from collections import defaultdict
from datetime import datetime, timezone

import filters
import fixed_lot as fl
import long_study as ls
import replay
import setups
from pyramid import CURRENT, add_bar, run, target_of, walk  # noqa: F401  (G29: shared with candidates_eval)



def rules() -> list[dict]:
    out = [CURRENT]
    for target, be, partial, trail, timeout in itertools.product(
            ["plan", 2.0, 3.0, 4.0, 6.0, None],
            [None, 1.0, 1.5],
            [None, (1.0, 0.5), (1.5, 0.33), (2.0, 0.5)],
            [None, ("STRUCT", 2.0, 5), ("STRUCT", 1.5, 10), ("ATR", 1.5, 2.0), ("ATR", 2.0, 3.0)],
            [120, 240]):
        if target is None and trail is None:
            continue                                 # needs some way to take profit
        if partial and target not in (None, "plan") and partial[0] >= target:
            continue
        name = (f"TP {target if target else 'không'}{'R' if isinstance(target, float) else ''}"
                f" | BE {be or '-'} | chốt {f'{partial[1]:.0%}@{partial[0]}R' if partial else '-'}"
                f" | trail {f'{trail[0]} từ {trail[1]}R ({trail[2]})' if trail else '-'} | {timeout} nến")
        out.append({"name": name, "target": target, "be": be, "partial": partial, "trail": trail,
                    "timeout": timeout, "struct_exit": True})
    return out


def trades(name: str, symbol: str, usd: dict, dxy: dict) -> list[dict]:
    """Planned trades (entry, stop, target) with the bar index of entry; same models as G23/G27."""
    c = ls.ctx(symbol, "SWING")
    if c is None:
        return []
    if name == "S04":
        pairs = [(x, replay.evaluate(c, x, "S04", "SWING", "tm", {"costs": True}))
                 for x in replay.candidates(c, "S04", replay.engine_params("S04", "SWING"))]
    else:
        t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
        pairs = [(x, replay.evaluate(c, x, "S06", "SWING", "tm", t)) for x in setups.s06(c, filters.S06B)]
    bars = c["entry"]
    shift = bars[0]["time"] - bars[0]["utc"]
    out = []
    for x, r in pairs:
        if r["status"] != "EVALUATED" or x.get("kind") == "LIMIT":
            continue
        out.append({"symbol": symbol, "i": x["i"], "time": bars[x["i"]]["time"], "utc": bars[x["i"]]["time"] - shift,
                    "dir": x["direction"], "entry": r["entry"], "stop": r["stop"], "target": r["target"],
                    "zl": x["zone_low"], "zh": x["zone_high"], "r_replay": r["r"]})
    if name == "S06B_USD":
        filters.tag(out, symbol, usd, dxy)
        out = [t for t in out if t["f"]["USD_FLOW"]]
    return out


def path_stats(c: dict, t: dict, horizon: int = 240) -> float:
    """Max favourable R before the initial stop is touched (no other exit)."""
    bars, point, d = c["entry"], c["point"], t["dir"]
    risk = d * (t["entry"] - t["stop"])
    mfe = 0.0
    for b in range(t["i"] + 1, min(len(bars) - 1, t["i"] + horizon) + 1):
        sp = bars[b]["spread"] * point if d == -1 else 0.0
        hi, lo = bars[b]["high"] + sp, bars[b]["low"] + sp
        if (d == 1 and lo <= t["stop"]) or (d == -1 and hi >= t["stop"]):
            break
        mfe = max(mfe, d * ((hi if d == 1 else lo) - t["entry"]) / risk)
    return mfe


def stats(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "exp": 0.0, "pos_years": 0.0, "dd": 0.0, "ret_dd": 0.0, "total": 0.0}
    rows = sorted(rows, key=lambda x: x["utc"])
    eq = peak = dd = 0.0
    years = defaultdict(float)
    for x in rows:
        eq += x["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        years[datetime.fromtimestamp(x["utc"], timezone.utc).year] += x["r"]
    total = sum(x["r"] for x in rows)
    return {"n": len(rows), "exp": total / len(rows), "total": total,
            "pos_years": sum(1 for v in years.values() if v > 0) / len(years), "dd": dd,
            "ret_dd": total / dd if dd > 0 else (99.0 if total > 0 else 0.0)}


def period(utc: int) -> str:
    return "train" if utc < ls.VALIDATE else "validate" if utc < ls.TEST else "test"


def split(rows: list[dict]) -> dict:
    return {p: stats([x for x in rows if period(x["utc"]) == p]) for p in ("train", "validate", "test")} | {"all": stats(rows)}


def score(v: dict):
    s = v["train"]
    return (s["exp"] > 0, round(s["pos_years"], 2), -round(s["dd"], 1), s["ret_dd"])


def fmt(s: dict) -> str:
    return f"{s['exp']:+.3f} (n={s['n']}, DD {s['dd']:.1f})" if s["n"] else "n=0"


def account_rows(c_of, sig: list[dict], rule: dict, add_at, label: str) -> list[dict]:
    out = []
    for t in sig:
        c = c_of[t["symbol"]]
        res = run(c, t, rule, add_at)
        shift = c["entry"][0]["time"] - c["entry"][0]["utc"]
        out.append({"setup": label, "profile": "SWING", "symbol": t["symbol"], "dir": t["dir"], "in": t["utc"],
                    "out": c["entry"][res["exit_i"]]["time"] - shift, "dist": abs(t["entry"] - t["stop"]),
                    "price": t["entry"], "r": res["r"]})
    return out


def main() -> None:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    signals = {name: [t for s in ls.SYMBOLS for t in trades(name, s, usd, dxy)] for name in ("S04", "S06B", "S06B_USD")}
    all_rules = rules()
    lines = ["# G28: quản lý thoát lệnh, gồng lệnh và bồi lệnh (chỉ dữ liệu MT5, chọn trên 2010–2016)", ""]

    # 1. Path statistics.
    lines += ["## 1. Lệnh chạy được bao xa trước khi chạm dừng lỗ ban đầu (240 nến H1)", "",
              "| Setup | Lệnh | ≥1R | ≥2R | ≥3R | ≥5R | ≥8R | P(≥3R khi đã ≥1R) | P(≥5R khi đã ≥2R) |", "|---|---|---|---|---|---|---|---|---|"]
    for name, sig in signals.items():
        m = [path_stats(c_of[t["symbol"]], t) for t in sig]
        p = lambda k: sum(1 for v in m if v >= k) / len(m)  # noqa: E731
        lines.append(f"| {name} | {len(m)} | {p(1):.0%} | {p(2):.0%} | {p(3):.0%} | {p(5):.0%} | {p(8):.0%} | "
                     f"{p(3) / p(1):.0%} | {p(5) / p(2):.0%} |")

    # Check: the current Trade Manager rule reproduces replay.evaluate.
    worst = max(abs(run(c_of[t["symbol"]], t, CURRENT)["r"] - t["r_replay"]) for sig in signals.values() for t in sig)
    lines += ["", f"Kiểm tra: quy tắc TM hiện tại khớp replay.evaluate, sai lệch lớn nhất {worst:.2e} R.", ""]

    # 2 + 3. Exit rules and pyramiding.
    chosen = {}
    for name, sig in signals.items():
        results = []
        for rule in all_rules:
            for add_at in (None, 1.0, 2.0):
                rows = [{"utc": t["utc"], "r": run(c_of[t["symbol"]], t, rule, add_at)["r"]} for t in sig]
                results.append((rule, add_at, split(rows)))
        base = next(v for r, a, v in results if r is CURRENT and a is None)
        ranked = sorted(results, key=lambda x: score(x[2]), reverse=True)
        chosen[name] = ranked[0][:2]
        lines += [f"## 2. {name}: quy tắc thoát lệnh (R trung bình mỗi lệnh, DD theo R)", "",
                  f"TM hiện tại: train {fmt(base['train'])} | validate {fmt(base['validate'])} | test {fmt(base['test'])} | "
                  f"năm dương {base['all']['pos_years']:.0%}", "",
                  "| # | Quy tắc | Bồi lệnh | Train | Validate | Test | Năm dương (cả kỳ) | DD cả kỳ |", "|---|---|---|---|---|---|---|---|"]
        for k, (rule, add_at, v) in enumerate(ranked[:10], 1):
            lines.append(f"| {k} | {rule['name']} | {f'+{add_at:g}R' if add_at else '-'} | {fmt(v['train'])} | {fmt(v['validate'])} | "
                         f"{fmt(v['test'])} | {v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} |")
        # Effect of pyramiding alone on the current rule.
        for add_at in (1.0, 2.0):
            v = next(v for r, a, v in results if r is CURRENT and a == add_at)
            lines.append(f"\nTM hiện tại + bồi lệnh ở +{add_at:g}R: train {fmt(v['train'])} | validate {fmt(v['validate'])} | "
                         f"test {fmt(v['test'])} | năm dương {v['all']['pos_years']:.0%}")
        lines.append("")

    # Account replay of the chosen rules.
    lines += ["## 3. Tài khoản FTMO 1-Step, rủi ro 0,3%/lệnh, 2010–2025", "",
              "| Phương án | Lệnh | %/năm | DD tối đa | Ngày tệ nhất | Năm dương | Vi phạm FTMO |", "|---|---|---|---|---|---|---|"]
    wide = {"name": "TP 4R, không BE, trail cấu trúc từ 2R", "target": 4.0, "be": None, "partial": None,
            "trail": ("STRUCT", 2.0, 5), "timeout": 240, "struct_exit": True}
    combos = [("S04 + S06B lọc USD, TM hiện tại", [("S04", CURRENT, None), ("S06B_USD", CURRENT, None)]),
              ("… + bồi lệnh S06B ở +2R", [("S04", CURRENT, None), ("S06B_USD", CURRENT, 2.0)]),
              ("… + bồi lệnh cả S04 và S06B ở +2R", [("S04", CURRENT, 2.0), ("S06B_USD", CURRENT, 2.0)]),
              ("… S06B TP 4R + trail, bồi +2R", [("S04", CURRENT, None), ("S06B_USD", wide, 2.0)]),
              ("… + bồi lệnh S06B ở +1R", [("S04", CURRENT, None), ("S06B_USD", CURRENT, 1.0)]),
              ("S04 + S06B (không lọc), bồi S06B +2R", [("S04", CURRENT, None), ("S06B", CURRENT, 2.0)]),
              ("S04 + S06B lọc USD, quy tắc xếp hạng cao nhất trên train",
               [("S04", *chosen["S04"]), ("S06B_USD", *chosen["S06B_USD"])])]
    for label, parts in combos:
        rows = [x for name, rule, add_at in parts for x in account_rows(c_of, signals[name], rule, add_at, name)]
        s = fl.simulate(rows, "risk", {})
        y = s["by_year_pct"]
        lines.append(f"| {label} | {s['taken']} | {s['per_year_pct']:+.2f}% | {s['max_dd_pct']:.1f}% | {s['worst_day_pct']:+.2f}% | "
                     f"{sum(1 for v in y.values() if v > 0)}/{len(y)} | {s['ftmo_fail'] or 'không'} |")
    lines.append("")
    for name, (rule, add_at) in chosen.items():
        lines.append(f"- Chọn cho {name}: {rule['name']}, bồi lệnh {f'+{add_at:g}R' if add_at else 'không'}")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "exits.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
