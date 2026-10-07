"""G53: the MT5 economic calendar the EA exports (research/calendar/calendar_<YEAR>.csv), MT5 data only.

  python calendar_history.py             # counts per year and the two time checks

Rows: time_utc, time_server, currency, importance (HIGH / MODERATE), sector, event_id, name, actual, forecast,
previous. time_server is the calendar time as the terminal gives it (the broker's server time), so it matches bar
times directly; time_utc applies the broker offset valid at the event (EEA_NewsServerOffsetAt).

Checks before any study uses the file:
  NFP_UTC   US Nonfarm Payrolls must fall at 12:30 or 13:30 UTC (US summer / winter time)
  NFP_BARS  the H1 bar holding each NFP (server time) must move clearly more than the same hour on other
            Fridays of the same symbol's bars (EURUSD): proves that calendar and bars share one clock
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import context

NFP = "nonfarm payrolls"
METALS_CRYPTO = {"XAU", "XAG", "BTC", "ETH", "USO", "SP5"}


def folder(root: Path | None = None) -> Path:
    return (root or context.DATA.parent) / "research" / "calendar"


def load(path: Path, importance: tuple[str, ...] = ("HIGH",), ignore: list[str] = ()) -> list[dict]:
    """Events of every calendar_<YEAR>.csv in the folder, by time; `ignore` = lower-case name keywords."""
    out = []
    for f in sorted(path.glob("calendar_*.csv")):
        with f.open(encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["importance"] not in importance:
                    continue
                name = r["name"]
                if any(k in name.lower() for k in ignore):
                    continue
                out.append({"time_utc": int(r["time_utc"]), "time_server": int(r["time_server"]),
                            "currency": r["currency"], "importance": r["importance"], "name": name})
    out.sort(key=lambda e: e["time_server"])
    return out


def currencies_of(symbol: str) -> set[str]:
    """The currencies whose news the EA's guard applies to (EEA_NewsSymbolCurrencies: metal, crypto, oil = USD)."""
    base, quote = symbol[:3], symbol[3:6]
    if base in METALS_CRYPTO or not quote:
        return {"USD"}
    return {base, quote}


def times_for(events: list[dict], symbol: str, clock: str = "time_server") -> list[int]:
    cur = currencies_of(symbol)
    return sorted({e[clock] for e in events if e["currency"] in cur})


def nfp_utc_share(events: list[dict]) -> tuple[int, float]:
    """(NFP count, share at 12:30 or 13:30 UTC)."""
    nfp = [e for e in events if e["currency"] == "USD" and NFP in e["name"].lower()]
    ok = sum(1 for e in nfp if (e["time_utc"] % 86400) in (12 * 3600 + 1800, 13 * 3600 + 1800))
    return len(nfp), ok / len(nfp) if nfp else 0.0


def nfp_bar_ratio(events: list[dict], h1: list[dict]) -> tuple[int, float]:
    """(NFP bars found, median range of the NFP H1 bar / median range of the same server hour on other Fridays)."""
    by_time = {b["time"]: b for b in h1}
    nfp = [e["time_server"] - e["time_server"] % 3600 for e in events
           if e["currency"] == "USD" and NFP in e["name"].lower()]
    hit = [by_time[t] for t in nfp if t in by_time]
    if not hit:
        return 0, 0.0
    hours = Counter((b["time"] % 86400) // 3600 for b in hit)
    nfp_set = {b["time"] for b in hit}
    other = [b["high"] - b["low"] for b in h1 if b["time"] not in nfp_set
             and datetime.fromtimestamp(b["time"], timezone.utc).weekday() == 4
             and (b["time"] % 86400) // 3600 in hours]
    if not other:
        return len(hit), 0.0
    return len(hit), statistics.median(b["high"] - b["low"] for b in hit) / statistics.median(other)


def main(argv: list[str]) -> None:
    path = folder()
    events = load(path, ("HIGH", "MODERATE"))
    if not events:
        print(f"Chưa có lịch tin trong {path} (EA xuất khi InpResearchExportCalendar=true).")
        return
    years = Counter(datetime.fromtimestamp(e["time_utc"], timezone.utc).year for e in events)
    high = Counter(datetime.fromtimestamp(e["time_utc"], timezone.utc).year for e in events if e["importance"] == "HIGH")
    print("Năm: " + ", ".join(f"{y} {years[y]} ({high[y]} HIGH)" for y in sorted(years)))
    n, share = nfp_utc_share(events)
    print(f"NFP_UTC: {n} tin NFP, {share:.0%} lúc 12:30/13:30 UTC" + (" — OK" if share >= 0.95 else " — LỆCH GIỜ"))
    h1 = context.load_bars("EURUSD", "H1") if (context.DATA / "bars_EURUSD_H1.csv").exists() else []
    m, ratio = nfp_bar_ratio(events, h1)
    print(f"NFP_BARS: {m} nến H1 EURUSD, biến động nến NFP / cùng giờ thứ Sáu khác = {ratio:.2f}"
          + (" — OK" if ratio >= 1.5 else " — KIỂM TRA ĐỒNG HỒ"))


if __name__ == "__main__":
    main(sys.argv[1:])
