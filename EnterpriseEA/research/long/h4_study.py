"""G35: S04 and S06B on H4 entries (D1 levels), as extra independent trades. MT5 data only.

  python h4_study.py

Profile SWING4 (research/g10/context.py, replay.py): H4 entry bars, D1 levels and structure, the
SWING Trade Manager on H4 bars (as the EA manages a trade on its own timeframe). Setups, same
engines and parameters as on H1:
  S04      failed break of a D1 confluence zone, structural target
  S06B     24-bar compression (4 days), entry on the release, 3R
  S06B12   12-bar compression (2 days), entry on the release, 3R
each with and without the USD flow (flow of the last H1 bar inside the H4 bar) and the +1R add.
Stops that a bar opens beyond fill at the open (pyramid.GAP_FILL), H1 and H4 alike.
Selection on 2010-2016; 2017-2020 and 2021-2025 report. Account: FTMO 1-Step replay at 0.3%,
H1 and H4 trades together; an H4 trade on a symbol/side that already has an H1 trade is skipped
(the EA's one-SWING-per-symbol-and-side rule).
"""
from __future__ import annotations

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import fixed_lot as fl  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

VARIANTS = {"S04": None, "S06B": filters.S06B, "S06B12": dict(filters.S06B, box=12)}


def h4_trades(name: str, symbol: str, usd: dict) -> list[dict]:
    c = ls.ctx(symbol, "SWING4")
    if c is None:
        return []
    if name == "S04":
        pairs = [(x, replay.evaluate(c, x, "S04", "SWING4", "tm", {"costs": True}))
                 for x in replay.candidates(c, "S04", replay.engine_params("S04", "SWING4"))]
    else:
        t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
        pairs = [(x, replay.evaluate(c, x, "S06", "SWING4", "tm", t)) for x in setups.s06(c, VARIANTS[name])]
    bars = c["entry"]
    shift = bars[0]["time"] - bars[0]["utc"]
    sign = filters.USD_SIGN[symbol]
    out = []
    for x, r in pairs:
        if r["status"] != "EVALUATED" or x.get("kind") == "LIMIT":
            continue
        tm = bars[x["i"]]["time"]
        flow = usd.get(tm + 3 * 3600, 0)
        out.append({"symbol": symbol, "i": x["i"], "time": tm, "utc": tm - shift, "dir": x["direction"],
                    "entry": r["entry"], "stop": r["stop"], "target": r["target"], "zl": x["zone_low"], "zh": x["zone_high"],
                    "r_replay": r["r"], "usd_ok": flow != 0 and x["direction"] * sign == flow})
    return out


def evaluate(c_of: dict, sig: list[dict], add_at=None) -> dict:
    return exits.split([{"utc": t["utc"], "r": pyramid.run(c_of[t["symbol"]], t, pyramid.CURRENT, add_at)["r"]} for t in sig])


def acc_line(name: str, s: dict) -> str:
    y = s["by_year_pct"]
    return (f"| {name} | {s['taken']} | {s['per_year_pct']:+.2f}% | {s['max_dd_pct']:.1f}% | {s['worst_day_pct']:+.2f}% | "
            f"{sum(1 for v in y.values() if v > 0)}/{len(y)} |")


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c1 = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    c4 = {s: ls.ctx(s, "SWING4") for s in ls.SYMBOLS}
    h1 = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    h4 = {name: [t for s in ls.SYMBOLS for t in h4_trades(name, s, usd)] for name in VARIANTS}
    lines = ["# G35: S04 và S06B trên khung H4 (mức giá D1), thêm lệnh độc lập (chỉ dữ liệu MT5)", "",
             "| Setup H4 | Biến thể | Train | Validate | Test | Năm dương | DD (R) |", "|---|---|---|---|---|---|---|"]
    chosen = []
    for name, sig in h4.items():
        for label, rows, add in (("tất cả", sig, None), ("lọc USD", [t for t in sig if t["usd_ok"]], None),
                                 ("lọc USD + bồi +1R", [t for t in sig if t["usd_ok"]], 1.0), ("tất cả + bồi +1R", sig, 1.0)):
            if not rows:
                continue
            v = evaluate(c4, rows, add)
            lines.append(f"| {name} | {label} | {exits.fmt(v['train'])} | {exits.fmt(v['validate'])} | {exits.fmt(v['test'])} | "
                         f"{v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} |")
            if v["train"]["exp"] > 0.05 and v["train"]["n"] >= 20:
                chosen.append((name, label, rows, add, v))
    for name, sig in h1.items():
        v = evaluate(c1, sig, 1.0 if name == "S06B_USD" else None)
        lines.append(f"| {name} (H1, đang dùng) | {'bồi +1R' if name == 'S06B_USD' else 'TM'} | {exits.fmt(v['train'])} | "
                     f"{exits.fmt(v['validate'])} | {exits.fmt(v['test'])} | {v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} |")

    # Account replay: the H1 mix, then each H4 set kept on 2010-2016, then all of them.
    base = (exits.account_rows(c1, h1["S04"], pyramid.CURRENT, None, "S04")
            + exits.account_rows(c1, h1["S06B_USD"], pyramid.CURRENT, 1.0, "S06B"))
    lines += ["", "Chọn trên 2010–2016 (kỳ vọng > +0,05R, ≥ 20 lệnh): " +
              (", ".join(f"{n} {l}" for n, l, *_ in chosen) or "không có"), "",
              "## Tài khoản FTMO 1-Step, 0,3%/lệnh, 2010–2025 (H1 và H4 cùng lúc)", "",
              "| Phương án | Lệnh vào | %/năm | DD tối đa | Ngày tệ nhất | Năm dương |", "|---|---|---|---|---|---|"]
    lines.append(acc_line("H1: S04 + S06B lọc USD + bồi", fl.simulate(base, "risk", {})))
    best = {}
    for name, label, rows, add, v in chosen:
        extra = exits.account_rows(c4, rows, pyramid.CURRENT, add, f"{name}_H4")
        s = fl.simulate(base + extra, "risk", {})
        lines.append(acc_line(f"+ {name} H4 {label}", s))
        if name not in best or v["train"]["exp"] > best[name][1]["train"]["exp"]:
            best[name] = (extra, v)
    if best:
        allx = [t for extra, _ in best.values() for t in extra]
        lines.append(acc_line("+ tốt nhất mỗi setup H4 (theo train)", fl.simulate(base + allx, "risk", {})))
    text = "\n".join(lines) + "\n"
    (ls.OUT / "h4_study.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
