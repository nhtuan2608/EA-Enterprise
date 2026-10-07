"""G53: News Guard rules on 2010-2025 with the MT5 calendar the EA exported. MT5 data only.

  python news_rules_long.py

Plan, registered 07/10/2026 before the calendar export existed (no number of this study was seen before):

A. T2 before a HIGH event (G51/G52 on years instead of nine months). Research T2 trades (t2_oracle, momentum
   filter) on the long H4/D1 bars of EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD, XAGUSD, ETHUSD, USOUSD. Variants at the
   bar holding event - 15 min, when the trade is >= 0.3R at the bar's open: NONE (research model), BE (the EA
   today), TRAIL k = 1.0 / 1.5 / 2.0 ATR from the open. Events: HIGH, the EA's InpNewsIgnoreKeywords removed, the
   symbol's currencies (USD for metals, crypto, oil), matched on the server clock of the bars.
   Decision: replace BE by a TRAIL k for T2 only if that k beats BE in train 2010-2016, validate 2017-2020 and
   test 2021-2025 alike, and the paired 90% interval over 2010-2025 is above zero. Otherwise BE stays.
   NONE vs BE is reported but decides nothing (the user chose to keep the guard).
Gate: the calendar_history checks (NFP at 12:30/13:30 UTC, NFP bars move >= 1.5x) must pass, else no result.
"""
from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import long_study as ls  # noqa: F401  (sets the research data path first)
import context  # noqa: E402
import calendar_history as ch  # noqa: E402
import candidates_eval as ce  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import t2_news_be as nb  # noqa: E402

EA_ROOT = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
               r"\MQL5\Files\EnterpriseEA")
SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "XAGUSD", "ETHUSD", "USOUSD")
PERIODS = (("train", 2010, 2016), ("validate", 2017, 2020), ("test", 2021, 2025))
FROM_UTC = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())
VARIANTS = ("none", "be") + tuple(f"k{k}" for k in nb.TRAIL_K)


def period_of(utc: int) -> str | None:
    y = datetime.fromtimestamp(utc, timezone.utc).year
    return next((name for name, a, b in PERIODS if a <= y <= b), None)


def gate(events: list[dict]) -> tuple[bool, str]:
    n, share = ch.nfp_utc_share(events)
    m, ratio = ch.nfp_bar_ratio(events, context.load_bars("EURUSD", "H1"))
    ok = n >= 100 and share >= 0.95 and ratio >= 1.5
    return ok, f"NFP {n}, đúng giờ UTC {share:.0%}; nến NFP {m}, biến động ×{ratio:.2f}"


def study_t2(events: list[dict]) -> list[dict]:
    rows = []
    gap = pyramid.GAP_FILL
    pyramid.GAP_FILL = True
    try:
        for s in SYMBOLS:
            if not (context.DATA / f"bars_{s}_H4.csv").exists():
                continue
            ev = ch.times_for(events, s, "time_server")
            for x in nb.trades(s, FROM_UTC, all_daily=True):
                c, t = x["c"], x["t"]
                risk = t["dir"] * (t["entry"] - t["stop"])
                fee = replay.COMMISSION.get(s, 0.0) / risk
                row = {"symbol": s, "utc": c["entry"][t["i"]]["utc"] if "utc" in c["entry"][t["i"]] else
                       c["entry"][t["i"]]["time"] - int(context.meta()["server_offset_now"]),
                       "none": nb.walk(c, t, ce.T2_RULE)[0] - fee}
                r_be, _, used = nb.walk(c, t, ce.T2_RULE, ev, 0)       # server clock on both sides
                row["be"], row["used"] = r_be - fee, used
                for k in nb.TRAIL_K:
                    row[f"k{k}"] = nb.walk(c, t, ce.T2_RULE, ev, 0, news_k=k)[0] - fee
                row["period"] = period_of(row["utc"])
                rows.append(row)
    finally:
        pyramid.GAP_FILL = gap
    return [r for r in rows if r["period"]]


def decide(rows: list[dict]) -> tuple[str | None, list[str]]:
    lines, chosen = [], None
    for k in nb.TRAIL_K:
        key = f"k{k}"
        per = {p: statistics.fmean(r[key] - r["be"] for r in rows if r["period"] == p) if
               any(r["period"] == p for r in rows) else 0.0 for p, _, _ in PERIODS}
        lo, hi = nb.paired_ci([r[key] - r["be"] for r in rows])
        ok = all(v > 0 for v in per.values()) and lo > 0
        lines.append(f"  k={k} − BE: " + " / ".join(f"{p} {v:+.3f}" for p, v in per.items())
                     + f"; toàn kỳ [{lo:+.3f}, {hi:+.3f}] → {'ĐẠT' if ok else 'không đạt'}")
        if ok and chosen is None:
            chosen = key
    return chosen, lines


def main(argv: list[str]) -> None:
    events = ch.load(ch.folder(EA_ROOT), ("HIGH",), nb.ignore_keywords())
    if not events:
        print("Chưa có lịch tin EA xuất (research/calendar). Bật InpResearchExportCalendar và chờ EA xuất.")
        return
    ok, why = gate(events)
    print(f"Kiểm đồng hồ lịch tin: {why} → {'OK' if ok else 'KHÔNG ĐẠT, dừng'}")
    if not ok:
        return
    rows = study_t2(events)
    print(f"A. T2 trước tin HIGH, {len(rows)} lệnh 2010–2025, hòa vốn/siết kích hoạt {sum(r['used'] for r in rows)} lần")
    print("| Biến thể | " + " | ".join(p for p, _, _ in PERIODS) + " | toàn kỳ |")
    for v in VARIANTS:
        cells = [statistics.fmean(r[v] for r in rows if r["period"] == p) for p, _, _ in PERIODS]
        print(f"| {v} | " + " | ".join(f"{x:+.3f}R" for x in cells) + f" | {statistics.fmean(r[v] for r in rows):+.3f}R |")
    lo, hi = nb.paired_ci([r["be"] - r["none"] for r in rows])
    print(f"BE − NONE (chỉ báo cáo): {statistics.fmean(r['be'] - r['none'] for r in rows):+.3f}R [{lo:+.3f}, {hi:+.3f}]")
    chosen, lines = decide(rows)
    print("\n".join(lines))
    print(f"Quyết định (theo kế hoạch): {'thay BE bằng ' + chosen + ' cho T2' if chosen else 'giữ BE'}")


if __name__ == "__main__":
    main(sys.argv[1:])
