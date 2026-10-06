"""G30 (part 2): how much each HIGH news event really moves the market, MT5 data only.

  python news_impact.py

Events: logs/news_reactions.jsonl written by the EA (MT5 economic calendar, HIGH impact, since
2026-01), one line per event and symbol. Only cluster leads (one line for events released
together), impact DIRECT (the symbol carries the event currency) and quality OK are used.
Moves are in the EA's reference ATR (M5 ATR14 just before the event).

Normal market for comparison: the same symbol on the M5 history in research/long/data
(2024-06..2025-10), at the same UTC time of day on every weekday, measured the same way
(price at the minute, ATR14 of the M5 bars ending 5 minutes before). Those times also contain
some news days, so the comparison understates the news effect slightly.

Per event: median 60-minute excursion (largest distance from the price at release) and median
4-hour move, both divided by the normal median at that time of day; share of "shocks" (excursion
above the normal 90th percentile x 1.5); spread peak; minutes until volatility is normal again.
An event whose median excursion stays below 1.25x normal and shocks below 15% is a candidate for
InpNewsIgnoreKeywords; the decision stays with the operator.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import long_study as ls  # sets the research data path
import context  # noqa: E402

LOGS = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
            r"\MQL5\Files\EnterpriseEA\logs")
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]          # BTCUSD has no M5 history here
MIN_EVENTS = 4
DATA_END_UTC = 1759276800   # 2025-10-01, US summer time (offset UTC+3)


def events() -> list[dict]:
    out = []
    for line in (LOGS / "news_reactions.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("quality") != "OK" or r.get("impact") != "DIRECT" or r.get("cluster_lead") is False:
            continue
        if r["symbol"] not in SYMBOLS or any(r.get(k) is None for k in ("max_up_60m_atr", "max_down_60m_atr", "move_240m_atr")):
            continue
        r["exc60"] = max(abs(r["max_up_60m_atr"]), abs(r["max_down_60m_atr"]))
        r["abs240"] = abs(r["move_240m_atr"])
        out.append(r)
    return out


def baseline(symbol: str) -> dict:
    """(hour, minute) UTC -> {"exc60": [...], "abs240": [...]} on weekdays of the M5 history."""
    bars = context.load_bars(symbol, "M5")
    meta_shift = 10800             # research data are server time; convert with the summer/winter offset
    out = defaultdict(lambda: {"exc60": [], "abs240": []})
    index = {b["time"]: k for k, b in enumerate(bars)}
    for k, b in enumerate(bars):
        utc = b["time"] - server_offset(b["time"], meta_shift)
        dt = datetime.fromtimestamp(utc, timezone.utc)
        if dt.weekday() >= 5 or dt.minute % 30 or k < 20 or k + 48 >= len(bars):
            continue
        # The bar opening at the release minute: p0 is its open; ATR of the 14 bars ending 5 min before.
        if index.get(b["time"]) != k or bars[k + 12]["time"] - b["time"] != 3600 or bars[k + 48]["time"] - b["time"] != 4 * 3600:
            continue
        tr = [max(bars[j]["high"], bars[j - 1]["close"]) - min(bars[j]["low"], bars[j - 1]["close"]) for j in range(k - 15, k - 1)]
        atr = sum(tr) / 14
        if atr <= 0:
            continue
        p0 = b["open"]
        win = bars[k:k + 12]
        exc = max(max(x["high"] for x in win) - p0, p0 - min(x["low"] for x in win)) / atr
        out[(dt.hour, dt.minute)]["exc60"].append(exc)
        out[(dt.hour, dt.minute)]["abs240"].append(abs(bars[k + 47]["close"] - p0) / atr)
    return out


def server_offset(server_time: int, summer: int) -> int:
    """Broker on New York close: UTC+3 in US summer time, UTC+2 otherwise (data end: 10/2025, summer)."""
    return context.server_offset_at(server_time - summer, summer, DATA_END_UTC)


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> None:
    evs = events()
    base = {s: baseline(s) for s in SYMBOLS}
    groups = defaultdict(list)
    for r in evs:
        dt = datetime.fromtimestamp(r["event_utc"], timezone.utc)
        b = base[r["symbol"]].get((dt.hour, dt.minute - dt.minute % 30))
        if not b or len(b["exc60"]) < 50:
            continue
        r["exc_ratio"] = r["exc60"] / statistics.median(b["exc60"])
        r["move_ratio"] = r["abs240"] / statistics.median(b["abs240"])
        r["shock"] = r["exc60"] > 1.5 * pct(b["exc60"], 0.9)
        groups[(r["currency"], r["event"])].append(r)
    rows = []
    for (cur, name), rs in groups.items():
        days = {r["event_utc"] for r in rs}
        if len(days) < MIN_EVENTS:
            continue
        exc = statistics.median(r["exc_ratio"] for r in rs)
        shock = sum(r["shock"] for r in rs) / len(rs)
        rows.append({"cur": cur, "name": name, "events": len(days), "n": len(rs), "exc": exc,
                     "move": statistics.median(r["move_ratio"] for r in rs), "shock": shock,
                     "spread": statistics.median(r.get("spread_peak_ratio") or 1.0 for r in rs),
                     "recover": statistics.median(r.get("vol_recovery_min") or 0 for r in rs),
                     "ignore": exc < 1.25 and shock < 0.15})
    rows.sort(key=lambda x: (-x["exc"]))
    lines = ["# G30 phần 2: tin HIGH tác động thật bao nhiêu (chỉ dữ liệu MT5)", "",
             f"Nguồn: logs/news_reactions.jsonl của EA ({len(evs)} dòng hợp lệ, 2026). So với thị trường bình thường cùng giờ UTC "
             "trên dữ liệu M5 2024-06..2025-10 (EURUSD, GBPUSD, XAUUSD, USDJPY).", "",
             "| Tin | Số lần | Biên độ 60 phút / bình thường | Biến động 4 giờ / bình thường | Tỷ lệ cú sốc | Spread đỉnh | Phút để bình thường lại | Gợi ý |",
             "|---|---|---|---|---|---|---|---|"]
    for x in rows:
        hint = "có thể bỏ qua" if x["ignore"] else "giữ chặn"
        lines.append(f"| {x['cur']} {x['name']} | {x['events']} | ×{x['exc']:.2f} | ×{x['move']:.2f} | {x['shock']:.0%} | "
                     f"×{x['spread']:.2f} | {x['recover']:.0f} | {hint} |")
    lines += ["", "Cú sốc: biên độ 60 phút vượt 1,5 lần mức phân vị 90 của giờ bình thường.",
              f"Gợi ý \"có thể bỏ qua\": biên độ trung vị < ×1,25 và cú sốc < 15%, tối thiểu {MIN_EVENTS} lần ra tin."]
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "news_impact.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
