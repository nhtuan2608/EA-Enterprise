"""G32: odds of passing the FTMO 2-Step challenge by risk per trade, MT5 data only.

  python ftmo2_odds.py

Same trades and account replay as ftmo_odds.py (G30): S04 SWING + S06B with the USD flow,
with and without the +1R add, 2010-2025. 2-Step rules (EA: Risk/FtmoHeadroom.mqh,
DailyResetLedger.mqh; FTMO): phase 1 target +10%, phase 2 target +5%, each phase on a fresh
10,000 USD balance, daily loss 5% of the initial balance against the day's opening balance,
overall floor static at the initial balance - 10%, at least 4 trading days per phase, no time
limit. Phase 2 starts when phase 1 is passed. The EA-like headroom check keeps 0.5% above
both floors with every open stop hit; internal limits: open 4r, daily min(4r, 4.5%), weekly
min(8r, 5%). Floating losses and slippage are not modelled.
"""
from __future__ import annotations

from datetime import datetime, timezone

import exits
import filters
import ftmo_odds as fo
import long_study as ls

PHASE1 = {"target": 0.10, "daily": 0.05, "overall": 0.10, "trailing": False, "min_days": 4}
PHASE2 = dict(PHASE1, target=0.05)
RISKS = [0.003, 0.005, 0.0075, 0.01, 0.015, 0.02]


def two_step(rows: list[dict], r: float, start: int) -> dict:
    p1 = fo.challenge(rows, r, start, rules=PHASE1)
    if p1["result"] != "PASS":
        return dict(p1, phase=1)
    when = start + int(p1["days"] * fo.DAY)
    p2 = fo.challenge(rows, r, when + 1, rules=PHASE2)
    if p2["result"] != "PASS":
        return dict(p2, phase=2, days=None if p2["days"] is None else p1["days"] + p2["days"], p1_days=p1["days"])
    return {"result": "PASS", "phase": 2, "days": p1["days"] + p2["days"], "p1_days": p1["days"],
            "best_day_ok": None, "bal": p2["bal"]}


def summary(res: list[dict]) -> dict:
    s = fo.summary(res)
    n = len(res)
    s["p1_pass"] = sum(1 for x in res if x["result"] == "PASS" or x.get("phase") == 2) / n
    s["fail_p1"] = sum(1 for x in res if x["result"].startswith("FAIL") and x.get("phase") == 1) / n
    s["fail_p2"] = sum(1 for x in res if x["result"].startswith("FAIL") and x.get("phase") == 2) / n
    return s


def main() -> None:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    s04 = exits.account_rows(c_of, sig["S04"], exits.CURRENT, None, "S04")
    mixes = {
        "S04 + S06B lọc USD": s04 + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, None, "S06B"),
        "S04 + S06B lọc USD, bồi +1R": s04 + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, 1.0, "S06B"),
    }
    first = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    last = int(datetime(2024, 12, 30, tzinfo=timezone.utc).timestamp())
    lines = ["# G32: xác suất vượt FTMO 2-Step theo mức rủi ro (chỉ dữ liệu MT5)", "",
             "Vòng 1 +10%, vòng 2 +5% (mỗi vòng số dư mới), lỗ ngày ≤ 5% vốn đầu, sàn cố định vốn đầu − 10%, ≥ 4 ngày giao dịch mỗi vòng.", ""]
    for name, rows in mixes.items():
        rows = sorted(rows, key=lambda x: x["in"])
        lines += [f"## {name}", "",
                  "| Rủi ro/lệnh | Cách rút | Qua vòng 1 | Qua cả 2 vòng | Cả 2 vòng ≤ 6 tháng | ≤ 12 tháng | ≤ 24 tháng | Trượt vòng 1 | Trượt vòng 2 | Thời gian qua cả 2 (trung vị) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for r in RISKS:
            rolling = [two_step(rows, r, s) for s in range(first, last, fo.WEEK)]
            boot = fo.bootstrap(rows, r, 3000, 7, runner=two_step)
            for label, res in (("lịch sử, mỗi thứ Hai", rolling), ("xáo tháng ×3000", boot)):
                s = summary(res)
                md = f"{s['median_days']:.0f} ngày" if s["median_days"] is not None else "-"
                lines.append(f"| {r:.2%} | {label} | {s['p1_pass']:.0%} | {s['pass']:.0%} | {s['pass_182']:.0%} | {s['pass_365']:.0%} | "
                             f"{s['pass_730']:.0%} | {s['fail_p1']:.0%} | {s['fail_p2']:.0%} | {md} |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "ftmo2_odds.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
