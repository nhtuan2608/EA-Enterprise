"""G41: does T2 (and the other trend families) hold on trend assets it was never fitted on? MT5 data only.

  python trend_assets.py

Assets exported 06/10/2026 (MT5 window 2024-02-20 .. 2026-10-06): XAGUSD, ETHUSD, USOUSD (oil), SP500. Nothing is
chosen on them: T2 keeps the 2010-2016 set (H4 Donchian 60, D1 EMA200 side, stop 2 ATR, ATR trail 3). The D1 EMA200
needs about 200 days, so the T2 signals start around the end of 2024. Compared with the eight FX pairs of G36 and with
the five original symbols over the same window (their data end on 2025-10-09). T1 and T6 (D1 trend families of G38),
S06B and S04 are shown for reference. Random entries (same stop in ATR, same exit, 2,000 runs) test the pooled T2
trades of the four assets. Stops that a bar opens beyond fill at the open; fees as in replay.COMMISSION.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import pyramid  # noqa: E402

TREND = ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
FX8 = dv.NEW
OLD = dv.SYMBOLS
START = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())
OLD_END = int(datetime(2025, 10, 9, tzinfo=timezone.utc).timestamp())
SETS = {
    "T2": {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180},
    "T1": {"n": 40, "stop": 3.0, "trail": 4.0, "timeout": 120},
    "T6": {"n": 120, "stop": 3.0, "trail": 3.0, "timeout": 120},
}


def fmt(rs: list[float]) -> str:
    if not rs:
        return "n=0"
    win = sum(r > 0 for r in rs) / len(rs)
    gains, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    pf = gains / losses if losses > 0 else 99
    return f"{statistics.fmean(rs):+.3f} (n={len(rs)}, thắng {win:.0%}, PF {pf:.2f}, tổng {sum(rs):+.1f}R)"


def by_year(rows: list[dict]) -> str:
    y = defaultdict(float)
    for t in rows:
        y[datetime.fromtimestamp(t["utc"], timezone.utc).year] += t["r"]
    return ", ".join(f"{k}: {v:+.1f}R" for k, v in sorted(y.items()))


def random_p(rows: list[dict], family: str, p: dict, runs: int = 2000, seed: int = 41) -> tuple[float, float, float]:
    tf = dv.FAMILIES[family][0]
    rule = dv.FAMILIES[family][3](p)
    rng = np.random.default_rng(seed)
    pools = {}
    for s in {t["symbol"] for t in rows}:
        B = dv.load(s, tf)
        ok = np.where((B["atr"] > 0) & (np.arange(len(B["atr"])) > 300) & (np.arange(len(B["atr"])) < len(B["atr"]) - 2)
                      & (B["utc"] >= START))[0]
        pools[s] = ok
    real = statistics.fmean(t["r"] for t in rows)
    sims = []
    for _ in range(runs):
        tot = 0.0
        for x in rows:
            B = dv.load(x["symbol"], tf)
            j = int(pools[x["symbol"]][rng.integers(len(pools[x["symbol"]]))])
            d = 1 if rng.random() < 0.5 else -1
            b = B["bars"][j]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = x["stop_atr"] * B["atr"][j]
            t = {"symbol": x["symbol"], "i": j, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * 3 * risk, "zl": 0.0, "zh": 0.0}
            tot += pyramid.run(B["ctx"], t, rule)["r"]
        sims.append(tot / len(rows))
    sims = np.array(sims)
    return real, float(np.mean(sims >= real)), float(np.quantile(sims, 0.95))


def main() -> None:
    pyramid.GAP_FILL = True
    lines = ["# G41: T2 và các họ xu hướng trên tài sản xu hướng chưa từng dùng để chọn (chỉ dữ liệu MT5)", "",
             "Dữ liệu 2024-02-20 .. 2026-10-06; T2 có tín hiệu từ khoảng cuối 2024 (EMA200 D1). Không chọn tham số nào ở đây.", ""]
    rows = {f: {s: dv.trades(f, p, s, START) for s in TREND + FX8 + OLD} for f, p in SETS.items()}
    lines += ["## 1. T2 theo tài sản", "", "| Tài sản | T2 | Theo năm |", "|---|---|---|"]
    for s in TREND:
        rs = rows["T2"][s]
        lines.append(f"| {s} | {fmt([t['r'] for t in rs])} | {by_year(rs)} |")
    lines += ["", "## 2. So sánh nhóm (R trung bình mỗi lệnh)", "",
              "| Nhóm | T2 | T1 (D1 Donchian 40) | T6 (đà 120 ngày) |", "|---|---|---|---|"]
    groups = [("4 tài sản xu hướng mới (XAG, ETH, dầu, SP500)", TREND, None),
              ("8 cặp tiền G36", FX8, None),
              ("5 symbol cũ, cùng giai đoạn tới 2025-10-09", OLD, OLD_END),
              ("XAUUSD + BTCUSD (cùng giai đoạn)", ["XAUUSD", "BTCUSD"], OLD_END),
              ("EURUSD + GBPUSD + USDJPY (cùng giai đoạn)", ["EURUSD", "GBPUSD", "USDJPY"], OLD_END)]
    for label, syms, end in groups:
        cells = []
        for f in SETS:
            rs = [t["r"] for s in syms for t in rows[f][s] if end is None or t["utc"] < end]
            cells.append(fmt(rs))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    pooled = [dict(t) for s in TREND for t in rows["T2"][s]]
    real, p, p95 = random_p(pooled, "T2", SETS["T2"])
    lines += ["", f"Vào lệnh ngẫu nhiên (T2, 4 tài sản gộp, 2.000 lần): R thật {real:+.3f}, ngẫu nhiên p95 {p95:+.3f}, **p = {p:.3f}**", ""]
    # S06B (USD side where it exists) and S04 on the trend assets, for reference.
    usd, dxy = filters.usd_index(), filters.real_dxy()
    lines += ["## 3. S06B và S04 trên 4 tài sản (tham khảo)", "", "| Tài sản | S06B | S04 |", "|---|---|---|"]
    for s in TREND:
        c = ls.ctx(s, "SWING")
        s06 = [t for t in exits.trades("S06B", s, usd, dxy) if t["utc"] >= START]
        s04 = [t for t in exits.trades("S04", s, usd, dxy) if t["utc"] >= START]
        r06 = [pyramid.run(c, t, pyramid.CURRENT)["r"] for t in s06]
        r04 = [pyramid.run(c, t, pyramid.CURRENT)["r"] for t in s04]
        lines.append(f"| {s} | {fmt(r06)} | {fmt(r04)} |")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "trend_assets.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
