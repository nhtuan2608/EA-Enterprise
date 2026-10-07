"""G58: which setups should trade live? S04 (LIVE today) against S06B with the USD flow (SHADOW), with and without
T2 on XAUUSD/BTCUSD. MT5 data only, research only (no EA change).

  python g58_live_mix.py           # writes results/g58_live_mix.md

Rows (2010-2025, five symbols, costs, gap fills): S04 SWING (current Trade Manager), S06B with the USD flow and the
+1R add (G29/G31), T2 on XAUUSD/BTCUSD with the momentum filter and the +1R add (G44). Setup risk weights as the EA
(G44): S04 0.65, S06B 1.00, T2 0.34. Account as the live session (FTMO 2-Step derives): 0.5% per trade, open risk 2%,
daily stop 2%, weekly 4%, one trade per symbol + side + profile, no opposite trades.
Mixes: V0 S04 alone (today), V1 S06B alone, V2 S04 + S06B, V3 S04 + S06B + T2, V4 S06B + T2.
Registered rule (written before the run): the recommended mix is the best train (2010-2016) score (bootstrap p10
%/year / p90 DD); it must also be positive in validate and test, else the next one. FTMO 2-Step odds (0.5% / 0.5%,
every Monday 2010-2024 and 1,000 bootstrap paths of months) are reported for the decision, not used to choose.
"""
from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone

import long_study as ls  # noqa: F401  (research data path first)
import ftmo2_odds as f2  # noqa: E402
import ftmo_odds as fo  # noqa: E402
import g43_final as gf  # noqa: E402
import g43_low_risk as g  # noqa: E402
import pyramid  # noqa: E402

WEIGHTS = {"S04": 0.65, "S06B": 1.00, "T2": 0.34}
TREND = ("XAUUSD", "BTCUSD")
MIXES = {"V0 S04 (đang LIVE)": ("S04",), "V1 S06B lọc USD": ("S06B",), "V2 S04 + S06B": ("S04", "S06B"),
         "V3 S04 + S06B + T2 XAU/BTC": ("S04", "S06B", "T2"), "V4 S06B + T2 XAU/BTC": ("S06B", "T2")}


def rows_all() -> list[dict]:
    pyramid.GAP_FILL = True
    base = g.base_rows()                                     # S04 + S06B (USD flow, +1R add)
    t2 = [t for t in gf.t2_variant(True, 1.0) if t["symbol"] in TREND]
    return base + t2


def main(argv: list[str]) -> None:
    g.PER_TRADE, g.OPEN_RISK, g.DAILY, g.WEEKLY = 0.005, 0.02, 0.02, 0.04
    rows = rows_all()
    mult = lambda t, s: WEIGHTS[t["setup"]]  # noqa: E731
    lines = ["# G58: setup nào nên LIVE — S04 so với S06B lọc USD, có/không T2 XAU/BTC (chỉ dữ liệu MT5)", "",
             "0,5%/lệnh × trọng số setup của EA (S04 0,65 / S06B 1,00 / T2 0,34), mở tối đa 2%, chặn ngày 2% / tuần 4%. "
             "Chọn theo điểm 2010–2016 (đăng ký trước), phải dương ở 2017–2020 và 2021–2025.", "", *g.HEAD]
    res = {}
    for name, setups in MIXES.items():
        rs = [t for t in rows if t["setup"] in setups]
        # open_risk passed explicitly: simulate() binds its default (1.2%) at definition time
        res[name] = (rs, g.by_period(rs, mult=mult, open_risk=g.OPEN_RISK))
        lines += g.table(name, res[name][1])
    order = sorted(res, key=lambda k: res[k][1]["train"]["score"], reverse=True)
    pick = next((k for k in order if res[k][1]["validate"]["per_year"] > 0 and res[k][1]["test"]["per_year"] > 0), None)
    lines += ["", f"**Theo luật đăng ký trước: {pick}**", "",
              "## FTMO 2-Step ở 0,5% / 0,5% (bắt đầu mỗi thứ Hai 2010–2024 / 1.000 đường xáo tháng)", "",
              "| Phương án | Qua vòng 1 | Qua cả 2 | Cả 2 ≤ 6 tháng | ≤ 12 tháng | Trượt | Cả 2 (trung vị) |",
              "|---|---|---|---|---|---|---|"]
    first = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    last = int(datetime(2024, 12, 30, tzinfo=timezone.utc).timestamp())
    for name, (rs, _) in res.items():
        w = sorted((dict(t, r=t["r"] * WEIGHTS[t["setup"]]) for t in rs), key=lambda x: x["in"])
        hist = f2.summary([f2.two_step(w, 0.005, 0.005, s) for s in range(first, last, fo.WEEK)])
        boot = f2.summary(fo.bootstrap(w, 0, 1000, 58, runner=lambda path, _r, st: f2.two_step(path, 0.005, 0.005, st)))

        def pair(key):
            return f"{hist[key]:.0%} / {boot[key]:.0%}"
        med = " / ".join(f"{x['median_days'] / 365:.1f} năm" if x["median_days"] is not None else "-" for x in (hist, boot))
        lines.append(f"| {name} | {pair('p1_pass')} | {pair('pass')} | {pair('pass_182')} | {pair('pass_365')} | "
                     f"{pair('fail')} | {med} |")
        print(lines[-1], flush=True)
    lines += ["", "## Theo năm (%, 0,5%/lệnh)", "", "| Năm | " + " | ".join(MIXES) + " |", "|---|" + "---|" * len(MIXES)]
    by_year = {name: g.simulate(rs, mult=mult, open_risk=g.OPEN_RISK)["by_year"] for name, (rs, _) in res.items()}
    lines += ["", "## Theo mức rủi ro mỗi lệnh (toàn kỳ; mở/ngày = 4×, tuần = 8×, tối đa 4% / 8% như EA)", "",
              "| Rủi ro/lệnh | Phương án | %/năm | DD | DD p90 (xáo tháng) | Năm tệ nhất |", "|---|---|---|---|---|---|"]
    for per in (0.005, 0.0075, 0.01, 0.015):
        g.PER_TRADE, g.OPEN_RISK, g.DAILY, g.WEEKLY = per, min(4 * per, 0.04), min(4 * per, 0.04), min(8 * per, 0.08)
        for name in ("V0 S04 (đang LIVE)", "V2 S04 + S06B", "V3 S04 + S06B + T2 XAU/BTC"):
            m = g.metrics(g.simulate(res[name][0], mult=mult, open_risk=g.OPEN_RISK))
            lines.append(f"| {per:.2%} | {name} | {m['per_year']:+.2f}% | {m['dd']:.1f}% | {m['dd_p90']:.1f}% | {m['worst_year']:+.1f}% |")
    g.PER_TRADE, g.OPEN_RISK, g.DAILY, g.WEEKLY = 0.005, 0.02, 0.02, 0.04
    for y in sorted({y for v in by_year.values() for y in v}):
        lines.append(f"| {y} | " + " | ".join(f"{by_year[n].get(y, 0) / g.CAPITAL * 100:+.1f}" for n in MIXES) + " |")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g58_live_mix.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))
    _ = statistics


if __name__ == "__main__":
    main(sys.argv[1:])
