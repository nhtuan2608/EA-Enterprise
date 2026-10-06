"""G32: FTMO 2-Step, challenge and funded account, by risk per trade and per phase. MT5 data only.

  python ftmo2_odds.py

Trades: S04 SWING (current Trade Manager) + S06B with the USD flow (G27), with and without the
+1R add (G28/G31), SWING H1 2010-2025. Stops that a bar opens beyond fill at that open (gaps,
pyramid.GAP_FILL): the only way the replay can lose more than planned.

2-Step rules (EA: Risk/FtmoHeadroom.mqh, DailyResetLedger.mqh; FTMO): phase 1 target +10%,
phase 2 target +5%, each phase on a fresh 10,000 USD balance; daily loss 5% of the initial
balance against the day's opening balance; overall floor static at the initial balance - 10%;
at least 4 trading days per phase; no time limit. Phase 2 starts when phase 1 is passed.
Funded account: same loss rules, no target; measured over 12 months.

The EA switched to FTMO_2_STEP derives (Risk/RiskLimitsProfile.mqh): per trade 0.5%, open 2%,
internal daily 2%, weekly 4%, safety buffer 0.5%. The replay uses open 4r, daily min(4r, 4.5%),
weekly min(8r, 5%) (equal to the EA at 0.5%) and the EA-like headroom check (every open stop
plus the new one, all hit today, keeps 0.5% above both floors). Floating losses are not modelled.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

import exits
import filters
import ftmo_odds as fo
import long_study as ls
import pyramid

PHASE1 = {"target": 0.10, "daily": 0.05, "overall": 0.10, "trailing": False, "min_days": 4}
PHASE2 = dict(PHASE1, target=0.05)
FUNDED = dict(PHASE1, target=10.0, min_days=0)          # never reached: runs until fail or the end
SCHEMES = [(0.003, 0.003), (0.005, 0.005), (0.0075, 0.005), (0.0075, 0.0075), (0.01, 0.005), (0.01, 0.0075),
           (0.01, 0.01), (0.015, 0.0075), (0.015, 0.01), (0.02, 0.01)]
FUNDED_RISKS = [0.003, 0.005, 0.0075, 0.01, 0.015]
YEAR = 365 * 86400


def two_step(rows: list[dict], r1: float, r2: float, start: int) -> dict:
    p1 = fo.challenge(rows, r1, start, rules=PHASE1)
    if p1["result"] != "PASS":
        return dict(p1, phase=1)
    when = start + int(p1["days"] * fo.DAY)
    p2 = fo.challenge(rows, r2, when + 1, rules=PHASE2)
    days = None if p2["days"] is None else p1["days"] + p2["days"]
    return dict(p2, phase=2, days=days, p1_days=p1["days"])


def summary(res: list[dict]) -> dict:
    s = fo.summary(res)
    n = len(res)
    s["p1_pass"] = sum(1 for x in res if x["result"] == "PASS" or x.get("phase") == 2) / n
    s["fail_p1"] = sum(1 for x in res if x["result"].startswith("FAIL") and x.get("phase") == 1) / n
    s["fail_p2"] = sum(1 for x in res if x["result"].startswith("FAIL") and x.get("phase") == 2) / n
    p1 = [x["p1_days"] for x in res if "p1_days" in x]
    s["p1_median"] = statistics.median(p1) if p1 else None
    return s


def funded_year(rows: list[dict], r: float, start: int) -> dict:
    """One year of a funded 2-Step account: final return, worst drawdown, breach."""
    path = [t for t in rows if start <= t["in"] < start + YEAR]
    res = fo.challenge(path, r, start, rules=FUNDED)
    return {"fail": res["result"].startswith("FAIL"), "ret": res["bal"] / fo.CAPITAL - 1}


def main() -> None:
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    c_of = {s: ls.ctx(s, "SWING") for s in ls.SYMBOLS}
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    s04 = exits.account_rows(c_of, sig["S04"], exits.CURRENT, None, "S04")
    mixes = {
        "S04 + S06B lọc USD": s04 + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, None, "S06B"),
        "S04 + S06B lọc USD, bồi +1R": s04 + exits.account_rows(c_of, sig["S06B_USD"], exits.CURRENT, 1.0, "S06B"),
    }
    gaps = sum(1 for rows in mixes.values() for t in rows if t["r"] < -1.05)
    first = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    last = int(datetime(2024, 12, 30, tzinfo=timezone.utc).timestamp())
    last_funded = int(datetime(2024, 10, 1, tzinfo=timezone.utc).timestamp())
    lines = ["# G32: FTMO 2-Step, thi và tài khoản được cấp vốn (chỉ dữ liệu MT5)", "",
             "Vòng 1 +10%, vòng 2 +5% (mỗi vòng số dư mới), lỗ ngày ≤ 5% vốn đầu, sàn cố định vốn đầu − 10%, ≥ 4 ngày giao dịch mỗi vòng. "
             f"Dừng lỗ bị gap khớp ở giá mở cửa ({gaps} lệnh lỗ quá 1,05R trong hai bộ lệnh). "
             "Mỗi ô: bắt đầu mỗi thứ Hai 2010–2024 theo lịch sử / 3.000 đường xáo tháng.", ""]
    for name, rows in mixes.items():
        rows = sorted(rows, key=lambda x: x["in"])
        lines += [f"## {name}: thi 2 vòng", "",
                  "| Rủi ro vòng 1 / vòng 2 | Qua vòng 1 | Qua cả 2 | Cả 2 ≤ 6 tháng | ≤ 12 tháng | ≤ 24 tháng | Trượt | Vòng 1 (trung vị) | Cả 2 (trung vị) |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r1, r2 in SCHEMES:
            cells = []
            for res in ([two_step(rows, r1, r2, s) for s in range(first, last, fo.WEEK)],
                        fo.bootstrap(rows, 0, 3000, 7, runner=lambda path, _r, st: two_step(path, r1, r2, st))):
                cells.append(summary(res))
            a, b = cells

            def pair(key, fmt="{:.0%}"):
                return f"{fmt.format(a[key])} / {fmt.format(b[key])}"

            def days(key):
                return " / ".join(f"{x[key] / 365:.1f} năm" if x[key] is not None else "-" for x in (a, b))
            lines.append(f"| {r1:.2%} / {r2:.2%} | {pair('p1_pass')} | {pair('pass')} | {pair('pass_182')} | {pair('pass_365')} | "
                         f"{pair('pass_730')} | {pair('fail')} | {days('p1_median')} | {days('median_days')} |")
        lines += ["", f"## {name}: tài khoản được cấp vốn, 12 tháng", "",
                  "| Rủi ro/lệnh | Lãi 12 tháng (trung vị) | Năm tệ nhất | Năm tốt nhất | Năm lỗ | Mất tài khoản |", "|---|---|---|---|---|---|"]
        for r in FUNDED_RISKS:
            ys = [funded_year(rows, r, s) for s in range(first, last_funded, 4 * fo.WEEK)]
            rets = sorted(y["ret"] for y in ys)
            lines.append(f"| {r:.2%} | {statistics.median(rets):+.1%} | {rets[0]:+.1%} | {rets[-1]:+.1%} | "
                         f"{sum(1 for x in rets if x < 0) / len(rets):.0%} | {sum(1 for y in ys if y['fail']) / len(ys):.0%} |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "ftmo2_odds.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
