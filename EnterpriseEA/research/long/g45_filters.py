"""G45 part 2: supply / demand zones as filters for the setups that have an edge (T2, S06B, S04). MT5 data only.

  python g45_filters.py

Zones: Z1 bases on H1 (1-3 bars, range <= 1 ATR, impulse >= 1.5 ATR with a 60% body, close 1 ATR beyond the base),
fresh = not yet touched again (price has not come back to the near edge) and at most 240 H1 bars old.
For each trade of T2 (H4), S06B (USD flow, add) and S04 at its entry time:
  ROOM k    skip a long when a fresh supply zone's near edge is within k ATR above the entry (short: demand below)
  BASE k    keep a long only when a fresh demand zone's near edge is within k ATR below the entry (short: mirror)
Per period (train 2010-2016 / validate 2017-2020 / test 2021-2025); control: the same share of trades skipped at
random (300 runs), p = share of random subsets whose mean R reaches the filtered one.
"""
from __future__ import annotations

import bisect
import statistics
import sys

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import g45_zones as gz  # noqa: E402
import pyramid  # noqa: E402
import robustness as rb  # noqa: E402
from g43_low_risk import PERIODS, T2  # noqa: E402

RUNS = 300
MAX_AGE = 240


def zones(symbol):
    """Fresh-zone intervals per H1 symbol: list of (created_utc, untouched_until_utc, d, near_edge)."""
    B = dv.load(symbol, "H1")
    gz.prep(B)
    p = {"base": 3, "basek": 1.0, "imp": 1.5, "trend": False}
    out = []
    for created, d, _, level, stop, _, _ in gz.orders_z1(B, p):
        end = min(created + MAX_AGE, len(B["c"]) - 1)
        touched = end
        for j in range(created + 1, end + 1):
            if (d == 1 and B["l"][j] <= level) or (d == -1 and B["h"][j] >= level):
                touched = j
                break
        out.append((int(B["utc"][created]), int(B["utc"][touched]), d, level))
    return out


def near(zs, utc, d_zone, price, atr, k, above):
    """A fresh zone of direction d_zone whose near edge lies within k ATR above (or below) price at utc."""
    for created, until, d, edge in zs:
        if d != d_zone or not (created < utc < until):
            continue
        gap = (edge - price) if above else (price - edge)
        if 0 <= gap <= k * atr:
            return True
    return False


def stats(rs):
    if not rs:
        return "n=0"
    w = [r for r in rs if r > 0]
    l_ = [-r for r in rs if r <= 0]
    rr = statistics.fmean(w) / statistics.fmean(l_) if w and l_ else 0.0
    return f"{statistics.fmean(rs):+.3f} (RR {rr:.2f}, n={len(rs)})"


def main():
    pyramid.GAP_FILL = True
    rb.init_worker()
    usd, dxy = filters.usd_index(), filters.real_dxy()
    Z = {s: zones(s) for s in ls.SYMBOLS}
    sets = {}
    rows = []
    for t in (x for s in ls.SYMBOLS for x in dv.trades("T2", T2, s)):
        B = dv.load(t["symbol"], "H4")
        rows.append({"symbol": t["symbol"], "in": t["utc"], "dir": t["dir"], "price": t["price"], "atr": B["atr"][t["i"]], "r": t["r"]})
    sets["T2"] = rows
    for name, label, add in (("S06B_USD", "S06B lọc USD + bồi", 1.0), ("S04", "S04", None)):
        rows = []
        for s in ls.SYMBOLS:
            sig = exits.trades(name, s, usd, dxy)
            res = exits.account_rows(rb._C, sig, pyramid.CURRENT, add, label)
            c = rb._C[s]
            for t, rr in zip(sig, res):
                rows.append({"symbol": s, "in": t["utc"], "dir": t["dir"], "price": t["entry"],
                             "atr": c["entry"][t["i"]]["atr"], "r": rr["r"]})
        sets[label] = rows
    rng = np.random.default_rng(452)
    lines = ["# G45 phần 2: vùng supply/demand làm bộ lọc (chỉ dữ liệu MT5)", "",
             "| Setup | Bộ lọc | Giữ lại | Train | Validate | Test | Tất cả | Ngẫu nhiên p |", "|---|---|---|---|---|---|---|---|"]
    for label, rows in sets.items():
        per = lambda rs: {k: [x["r"] for x in rs if a <= x["in"] < b] for k, (a, b) in PERIODS.items()}  # noqa: E731
        pp = per(rows)
        lines.append(f"| {label} | (không) | 100% | {stats(pp['train'])} | {stats(pp['validate'])} | {stats(pp['test'])} | {stats(pp['all'])} | - |")
        all_r = np.array([x["r"] for x in rows])
        for kind in ("ROOM", "BASE"):
            for k in (1.0, 2.0, 3.0):
                kept = []
                for x in rows:
                    zs = Z[x["symbol"]]
                    if kind == "ROOM":
                        blocked = near(zs, x["in"], -x["dir"], x["price"], x["atr"], k, above=(x["dir"] == 1))
                        if not blocked:
                            kept.append(x)
                    else:
                        if near(zs, x["in"], x["dir"], x["price"], x["atr"], k, above=(x["dir"] == -1)):
                            kept.append(x)
                if len(kept) < 20 or len(kept) == len(rows):
                    lines.append(f"| {label} | {kind} {k:g} ATR | {len(kept) / len(rows):.0%} | (quá ít hoặc không đổi) | | | | |")
                    continue
                share = len(kept) / len(rows)
                real = statistics.fmean(x["r"] for x in kept)
                sims = [all_r[rng.random(len(all_r)) < share].mean() for _ in range(RUNS)]
                p = float(np.mean(np.array(sims) >= real))
                kp = per(kept)
                lines.append(f"| {label} | {kind} {k:g} ATR | {share:.0%} | {stats(kp['train'])} | {stats(kp['validate'])} | "
                             f"{stats(kp['test'])} | {stats(kp['all'])} | {p:.3f} |")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g45_filters.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
