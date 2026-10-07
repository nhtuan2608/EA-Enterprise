"""G57: re-check InpNewsIgnoreKeywords with the corrected calendar clock (G54). MT5 data only.

  python news_keywords_check.py

G30 chose the ignore list from logs/news_reactions.jsonl, where US-winter events were one hour late. The recorder
does not record ignored events, so its corrected backfill cannot re-check them. This script measures every HIGH event
straight from the calendar the EA exported (format 2: time_server = bar clock of the date) on the M5 history
2024-06 .. 2025-10 (EURUSD, GBPUSD, XAUUSD, USDJPY), with the G30 measure and rule unchanged:
  exc60   largest distance from the release-minute open within 60 minutes, in ATR (14 M5 bars ending 5 min before)
  ratio   median exc60 / median exc60 of the same UTC half-hour on ordinary weekdays (news_impact.baseline)
  shock   share of releases with exc60 > 1.5 x the 90th percentile of the ordinary half-hour
  rule    "có thể bỏ qua" when ratio < 1.25 and shock < 15%, at least 4 releases (G30)
Releases are counted alone (no other HIGH event of the symbol's currencies in the same minute) and in clusters.
"""
from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

import long_study as ls  # noqa: F401  (research data path first)
import calendar_history as ch  # noqa: E402
import context  # noqa: E402
import news_impact as ni  # noqa: E402
import news_rules_long as nr  # noqa: E402

SYMBOLS = ni.SYMBOLS
FROM = int(datetime(2024, 6, 10, tzinfo=timezone.utc).timestamp())
TO = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp())


def shell_keywords() -> list[str]:
    """InpNewsIgnoreKeywords of EnterpriseEA.mq5 (lower case)"""
    import t2_news_be as nb
    return nb.ignore_keywords()


def measure(bars: list[dict], index: dict, server_time: int) -> float | None:
    k = index.get(server_time - server_time % 300)
    if k is None or k < 20 or k + 12 >= len(bars) or bars[k + 12]["time"] - bars[k]["time"] != 3600:
        return None
    tr = [max(bars[j]["high"], bars[j - 1]["close"]) - min(bars[j]["low"], bars[j - 1]["close"]) for j in range(k - 15, k - 1)]
    atr = sum(tr) / 14
    if atr <= 0:
        return None
    p0 = bars[k]["open"]
    win = bars[k:k + 12]
    return max(max(x["high"] for x in win) - p0, p0 - min(x["low"] for x in win)) / atr


def main(argv: list[str]) -> None:
    keys = shell_keywords()
    events = [e for e in ch.load(ch.folder(nr.EA_ROOT), ("HIGH",)) if FROM <= e["time_utc"] < TO]
    base = {s: ni.baseline(s) for s in SYMBOLS}
    bars = {s: context.load_bars(s, "M5") for s in SYMBOLS}
    index = {s: {b["time"]: k for k, b in enumerate(bars[s])} for s in SYMBOLS}
    same_minute = defaultdict(set)
    for e in events:
        same_minute[(e["time_utc"], e["currency"])].add(e["name"])
    groups = defaultdict(list)
    for e in events:
        for s in SYMBOLS:
            if e["currency"] not in ch.currencies_of(s):
                continue
            exc = measure(bars[s], index[s], e["time_server"])
            if exc is None:
                continue
            dt = datetime.fromtimestamp(e["time_utc"], timezone.utc)
            b = base[s].get((dt.hour, dt.minute - dt.minute % 30))
            if not b or len(b["exc60"]) < 50:
                continue
            alone = all(len(same_minute[(e["time_utc"], c)] - ({e["name"]} if c == e["currency"] else set())) == 0
                        for c in ch.currencies_of(s))
            groups[(e["currency"], e["name"])].append({"ratio": exc / statistics.median(b["exc60"]),
                                                      "shock": exc > 1.5 * ni.pct(b["exc60"], 0.9),
                                                      "alone": alone, "t": e["time_utc"]})
    rows = []
    for (cur, name), rs in groups.items():
        releases = len({r["t"] for r in rs})
        if releases < ni.MIN_EVENTS:
            continue
        al = [r for r in rs if r["alone"]]
        ratio = statistics.median(r["ratio"] for r in rs)
        shock = sum(r["shock"] for r in rs) / len(rs)
        ignored = any(k in name.lower() for k in keys)
        rows.append({"name": f"{cur} {name}", "releases": releases, "ratio": ratio, "shock": shock,
                     "alone": (statistics.median(r["ratio"] for r in al), len({r["t"] for r in al})) if al else None,
                     "rule_ignore": ratio < 1.25 and shock < 0.15, "ignored": ignored})
    rows.sort(key=lambda x: -x["ratio"])
    lines = ["# G57: kiểm lại danh sách tin bỏ qua với giờ lịch đã sửa (chỉ dữ liệu MT5)", "",
             f"Lịch MT5 EA xuất (format 2), tin HIGH 2024-06-10 → 2025-10-01, M5 EURUSD/GBPUSD/XAUUSD/USDJPY; cùng thước đo và "
             f"luật G30. Từ khóa đang bỏ qua: {', '.join(keys)}.", "",
             "| Tin | Lần ra tin | Biên độ 60 phút / bình thường | Cú sốc | Riêng lẻ (tỉ lệ, lần) | Luật G30 | Trong EA |",
             "|---|---|---|---|---|---|---|"]
    for x in rows:
        alone = f"×{x['alone'][0]:.2f} ({x['alone'][1]})" if x["alone"] else "–"
        flag = ""
        if x["ignored"] and not x["rule_ignore"]:
            flag = " **← đang bỏ qua nhưng nên chặn**"
        lines.append(f"| {x['name']} | {x['releases']} | ×{x['ratio']:.2f} | {x['shock']:.0%} | {alone} | "
                     f"{'có thể bỏ qua' if x['rule_ignore'] else 'giữ chặn'} | {'bỏ qua' if x['ignored'] else 'chặn'}{flag} |")
    wrong = [x["name"] for x in rows if x["ignored"] and not x["rule_ignore"]]
    lines += ["", f"Đang bỏ qua nhưng luật G30 nói nên chặn: {', '.join(wrong) if wrong else 'không có'}."]
    text = "\n".join(lines) + "\n"
    (ls.OUT / "news_keywords_check.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
