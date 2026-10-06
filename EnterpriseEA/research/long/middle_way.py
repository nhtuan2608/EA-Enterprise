"""G27 (step 3): FTMO 1-Step account replay of the "middle way" candidates from filters.py.

  python middle_way.py

Fixed risk 0.3% per trade, same limits as fixed_lot.py (G25), SWING H1 2010-2025.
Reports return, drawdown, worst day and the steadiness of months (share of positive months,
worst month, standard deviation of monthly results, longest run of losing months).
"""
from __future__ import annotations

import statistics

import filters
import fixed_lot as fl
import long_study as ls

S06B = filters.S06B


def usd_flow_keys() -> set:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    keys = set()
    for s in ls.SYMBOLS:
        rows = filters.base_rows("S06B", s)
        if rows:
            filters.tag(rows, s, usd, dxy)
            keys |= {(s, t["utc"], t["dir"]) for t in rows if t["f"]["USD_FLOW"]}
    return keys


def months(s: dict) -> dict:
    m = list(s["by_month_pct"].values())
    run = worst_run = 0
    for v in m:
        run = run + 1 if v < 0 else 0
        worst_run = max(worst_run, run)
    return {"months": len(m), "pos": sum(1 for v in m if v > 0) / len(m), "worst": min(m), "sd": statistics.pstdev(m),
            "run": worst_run}


def main() -> None:
    s04 = fl.trades("S04", "SWING")
    s06b = fl.trades("S06", "SWING", S06B)
    keys = usd_flow_keys()
    s06b_usd = [t for t in s06b if (t["symbol"], t["in"], t["dir"]) in keys]
    s06 = fl.trades("S06", "SWING")
    s02 = fl.trades("S02", "SWING")
    scenarios = [
        ("S02+S04+S06 (cấu hình cũ)", s02 + s04 + s06),
        ("Chỉ S04", s04),
        ("S04 + S06B", s04 + s06b),
        ("S04 + S06B lọc USD", s04 + s06b_usd),
        ("Chỉ S06B lọc USD", s06b_usd),
    ]
    out = ["# G27: tài khoản FTMO 1-Step, rủi ro 0,3%/lệnh, SWING H1 2010–2025", "",
           "| Phương án | Lệnh | Lợi nhuận | %/năm | DD tối đa | Ngày tệ nhất | Tháng dương | Tháng tệ nhất | Độ lệch tháng | Chuỗi tháng âm dài nhất | Năm dương | Vi phạm FTMO |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    years = []
    for name, rows in scenarios:
        s = fl.simulate(rows, "risk", {})
        m = months(s)
        y = s["by_year_pct"]
        out.append(f"| {name} | {s['taken']} | {s['return_pct']:+.1f}% | {s['per_year_pct']:+.2f}% | {s['max_dd_pct']:.1f}% | "
                   f"{s['worst_day_pct']:+.2f}% | {m['pos']:.0%} ({m['months']}) | {m['worst']:+.2f}% | {m['sd']:.2f}% | {m['run']} | "
                   f"{sum(1 for v in y.values() if v > 0)}/{len(y)} | {s['ftmo_fail'] or 'không'} |")
        years.append(f"- {name}: " + ", ".join(f"{k} {v:+.1f}%" for k, v in y.items()))
    text = "\n".join(out + ["", "Theo năm (% tài khoản):"] + years) + "\n"
    (ls.OUT / "middle_way.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
