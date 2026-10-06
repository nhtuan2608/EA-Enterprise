"""G36: S06B and S04 on eight more pairs, as a pure out-of-sample check. MT5 data only.

  python pairs_study.py

Pairs exported 06/10/2026: AUDUSD, NZDUSD, USDCAD, USDCHF (USD side known), EURJPY, GBPJPY, AUDJPY,
EURGBP (crosses: no USD flow). The terminal's bar limit gave 2024-02-20 .. 2026-10-06 only, so
nothing is chosen on these pairs: every parameter was fixed on the five original symbols
(2010-2016). The USD flow comes from EURUSD, GBPUSD and USDJPY, whose data end on 2025-10-09, so the
filtered variant is measured up to that day. Stops that a bar opens beyond fill at the open.
The original five symbols over the same window are shown for comparison. Account: FTMO 1-Step
replay at 0.3% per trade over 2024-02-20 .. 2025-10-09, the window every symbol covers.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import fixed_lot as fl  # noqa: E402
import pyramid  # noqa: E402
import statistics  # noqa: E402

NEW = ["AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP"]
USD_PAIRS = [s for s in NEW if s in filters.USD_SIGN]
START = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())
USD_END = int(datetime(2025, 10, 9, tzinfo=timezone.utc).timestamp())


def result(c_of: dict, sig: list[dict], add_at=None) -> list[dict]:
    return [{"symbol": t["symbol"], "utc": t["utc"], "r": pyramid.run(c_of[t["symbol"]], t, pyramid.CURRENT, add_at)["r"]}
            for t in sig]


def stats(rows: list[dict]) -> str:
    if not rows:
        return "n=0"
    rs = [x["r"] for x in rows]
    total = sum(rs)
    eq = peak = dd = 0.0
    for x in sorted(rows, key=lambda x: x["utc"]):
        eq += x["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return f"{statistics.fmean(rs):+.3f} (n={len(rs)}, thắng {sum(r > 0 for r in rs) / len(rs):.0%}, tổng {total:+.1f}R, DD {dd:.1f})"


def by_year(rows: list[dict]) -> str:
    y = defaultdict(list)
    for x in rows:
        y[datetime.fromtimestamp(x["utc"], timezone.utc).year].append(x["r"])
    return ", ".join(f"{k}: {sum(v):+.1f}R/{len(v)}" for k, v in sorted(y.items()))


def acc_line(name: str, s: dict) -> str:
    return (f"| {name} | {s['taken']} | {s['return_pct']:+.2f}% | {s['per_year_pct']:+.2f}% | {s['max_dd_pct']:.1f}% | "
            f"{s['worst_day_pct']:+.2f}% |")


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS + NEW}
    window = lambda sig, end=None: [t for t in sig if t["utc"] >= START and (end is None or t["utc"] < end)]  # noqa: E731
    new = {name: window([t for s in NEW for t in exits.trades(name, s, usd, dxy)]) for name in ("S06B", "S04")}
    for t in new["S06B"]:
        t["usd_ok"] = None
    filters_tagged = []
    for s in USD_PAIRS:
        rows = [t for t in new["S06B"] if t["symbol"] == s]
        filters.tag(rows, s, usd, dxy)
        filters_tagged += rows
    old = {name: window([t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)]) for name in ("S06B", "S06B_USD", "S04")}

    lines = ["# G36: S06B và S04 trên 8 cặp mới, kiểm tra ngoài mẫu (chỉ dữ liệu MT5)", "",
             "Dữ liệu cặp mới: 2024-02-20 .. 2026-10-06 (giới hạn số nến khi xuất). Không chọn tham số nào trên các cặp này. "
             "Lọc USD đo tới 2025-10-09 (dữ liệu EURUSD, GBPUSD, USDJPY). R trung bình mỗi lệnh.", "",
             "## Từng cặp (S06B, cả giai đoạn)", "", "| Cặp | S06B | S06B + bồi +1R | S04 |", "|---|---|---|---|"]
    for s in NEW:
        b = [t for t in new["S06B"] if t["symbol"] == s]
        a = [t for t in new["S04"] if t["symbol"] == s]
        lines.append(f"| {s} | {stats(result(c_of, b))} | {stats(result(c_of, b, 1.0))} | {stats(result(c_of, a))} |")

    lines += ["", "## Gộp", "", "| Nhóm | Kết quả | Theo năm |", "|---|---|---|"]
    groups = [
        ("8 cặp mới, S06B", new["S06B"], None),
        ("8 cặp mới, S06B + bồi +1R", new["S06B"], 1.0),
        ("4 cặp USD mới, S06B (tới 2025-10-09)", [t for t in new["S06B"] if t["symbol"] in USD_PAIRS and t["utc"] < USD_END], None),
        ("4 cặp USD mới, S06B lọc USD (tới 2025-10-09)", [t for t in filters_tagged if t["f"]["USD_FLOW"] and t["utc"] < USD_END], None),
        ("4 cặp USD mới, S06B ngược USD (tới 2025-10-09)", [t for t in filters_tagged if not t["f"]["USD_FLOW"] and t["utc"] < USD_END], None),
        ("4 cặp chéo, S06B", [t for t in new["S06B"] if t["symbol"] not in USD_PAIRS], None),
        ("8 cặp mới, S04", new["S04"], None),
        ("5 symbol cũ cùng giai đoạn, S06B", old["S06B"], None),
        ("5 symbol cũ cùng giai đoạn, S06B lọc USD + bồi", old["S06B_USD"], 1.0),
        ("5 symbol cũ cùng giai đoạn, S04", old["S04"], None),
    ]
    for name, sig, add in groups:
        res = result(c_of, sig, add)
        lines.append(f"| {name} | {stats(res)} | {by_year(res)} |")

    # Account over the window every symbol covers.
    end = USD_END
    base = (exits.account_rows(c_of, [t for t in old["S04"] if t["utc"] < end], pyramid.CURRENT, None, "S04")
            + exits.account_rows(c_of, [t for t in old["S06B_USD"] if t["utc"] < end], pyramid.CURRENT, 1.0, "S06B"))
    usd_new = [t for t in filters_tagged if t["f"]["USD_FLOW"] and t["utc"] < end]
    cross = [t for t in new["S06B"] if t["symbol"] not in USD_PAIRS and t["utc"] < end]
    all_new = [t for t in new["S06B"] if t["utc"] < end]
    lines += ["", "## Tài khoản FTMO 1-Step, 0,3%/lệnh, 2024-02-20 .. 2025-10-09", "",
              "| Danh mục | Lệnh vào | Lợi nhuận | %/năm | DD tối đa | Ngày tệ nhất |", "|---|---|---|---|---|---|"]
    lines.append(acc_line("5 symbol (đang dùng)", fl.simulate(base, "risk", {})))
    lines.append(acc_line("+ S06B lọc USD + bồi trên 4 cặp USD mới", fl.simulate(
        base + exits.account_rows(c_of, usd_new, pyramid.CURRENT, 1.0, "S06B_NEW"), "risk", {})))
    lines.append(acc_line("+ trên đó, S06B + bồi trên 4 cặp chéo", fl.simulate(
        base + exits.account_rows(c_of, usd_new, pyramid.CURRENT, 1.0, "S06B_NEW")
        + exits.account_rows(c_of, cross, pyramid.CURRENT, 1.0, "S06B_X"), "risk", {})))
    lines.append(acc_line("+ S06B + bồi trên cả 8 cặp mới, không lọc", fl.simulate(
        base + exits.account_rows(c_of, all_new, pyramid.CURRENT, 1.0, "S06B_ALL"), "risk", {})))
    text = "\n".join(lines) + "\n"
    (ls.OUT / "pairs_study.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
