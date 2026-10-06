"""G43 parts C3 and F: reversal exits and candle patterns, each against a random control. MT5 data only.

  python g43_reversal.py

C3  Reversal exits for T2 (H4 Donchian 60, D1 EMA200 side, stop 2 ATR, trail 3): the trade runs as in the research
    and is closed earlier, at the bar close, when a reversal shows while it is still open:
      EMA20      close beyond the EMA20 against the trade
      EMA20+1R   the same, only once the trade has been +1R (close)
      DON30      close beyond the opposite 30-bar channel (classic turtle exit)
      ENGULF+1R  an engulfing candle against the trade once it has been +1R
    Control: each early exit is moved to a random bar between entry and the original exit (300 runs).
F   Candle patterns as an entry filter on T2 (H4), S06B and S04 (H1) signals: keep a signal only when the signal
    bar or the bar before shows the pattern in the trade direction (engulfing, pin bar, momentum close, inside bar
    before the signal). Control: the same share of signals kept at random (300 runs).
Every result per period (train 2010-2016 / validate 2017-2020 / test 2021-2025); a variant counts only if it is
better in all three and beats its control (p < 0.05).
"""
from __future__ import annotations

import statistics
import sys

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import robustness as rb  # noqa: E402
from g43_low_risk import PERIODS, T2  # noqa: E402

RUNS = 300


# ---------------------------------------------------------------------------
# Patterns (on arrays o, h, l, c; bar j, direction d)
# ---------------------------------------------------------------------------
def engulf(o, h, l, c, j, d):
    if j < 1:
        return False
    if d == 1:
        return c[j] > o[j] and c[j - 1] < o[j - 1] and o[j] <= c[j - 1] and c[j] >= o[j - 1]
    return c[j] < o[j] and c[j - 1] > o[j - 1] and o[j] >= c[j - 1] and c[j] <= o[j - 1]


def pin(o, h, l, c, j, d):
    rng = h[j] - l[j]
    if rng <= 0:
        return False
    body = abs(c[j] - o[j])
    if d == 1:
        wick = min(o[j], c[j]) - l[j]
        return wick >= 2 * body and wick >= 0.6 * rng and c[j] >= l[j] + 0.66 * rng
    wick = h[j] - max(o[j], c[j])
    return wick >= 2 * body and wick >= 0.6 * rng and c[j] <= h[j] - 0.66 * rng


def momentum(o, h, l, c, j, d, atr):
    rng = h[j] - l[j]
    if rng <= 0 or atr[j] <= 0 or rng < atr[j]:
        return False
    return (c[j] >= h[j] - 0.25 * rng) if d == 1 else (c[j] <= l[j] + 0.25 * rng)


def inside_before(o, h, l, c, j, d):
    return j >= 2 and h[j - 1] < h[j - 2] and l[j - 1] > l[j - 2]


PATTERNS = {"nhấn chìm": engulf, "pin bar": pin, "nến đà": None, "inside bar trước": inside_before}


def has_pattern(name, A, j, d):
    o, h, l, c, atr = A
    if name == "nến đà":
        return momentum(o, h, l, c, j, d, atr) or momentum(o, h, l, c, j - 1, d, atr)
    f = PATTERNS[name]
    if name == "inside bar trước":
        return f(o, h, l, c, j, d)
    return f(o, h, l, c, j, d) or f(o, h, l, c, j - 1, d)


def arrays(bars):
    return (np.array([b["open"] for b in bars]), np.array([b["high"] for b in bars]), np.array([b["low"] for b in bars]),
            np.array([b["close"] for b in bars]), np.array([b.get("atr", 0.0) for b in bars]))


def ema(x, n):
    out = np.empty_like(x)
    k = 2 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + k * (x[i] - out[i - 1])
    return out


# ---------------------------------------------------------------------------
# T2 trades with their bar path
# ---------------------------------------------------------------------------
def t2_paths() -> list[dict]:
    tf, _, sig, rule_fn = dv.FAMILIES["T2"]
    rule = rule_fn(T2)
    out = []
    for s in ls.SYMBOLS:
        B = dv.load(s, tf)
        bars, busy = B["bars"], -1
        A = arrays(bars)
        e20 = B.setdefault("ema20", ema(B["c"], 20))
        lo30 = np.array([B["l"][max(0, i - 30):i].min() if i >= 1 else B["l"][0] for i in range(len(bars))])
        hi30 = np.array([B["h"][max(0, i - 30):i].max() if i >= 1 else B["h"][0] for i in range(len(bars))])
        fee = replay.COMMISSION.get(s, 0.0)
        for i, d, stop_atr in sig(B, T2):
            if i <= busy or i >= len(bars) - 2:
                continue
            b = bars[i]
            entry = b["close"] + (b["spread"] * B["point"] if d == 1 else 0.0)
            risk = stop_atr * B["atr"][i]
            if risk <= 0:
                continue
            t = {"symbol": s, "i": i, "dir": d, "entry": entry, "stop": entry - d * risk,
                 "target": entry + d * 3 * risk, "zl": 0.0, "zh": 0.0}
            res = pyramid.run(B["ctx"], t, rule)
            busy = res["exit_i"]
            out.append({"symbol": s, "in": int(B["utc"][i]), "i": i, "exit_i": res["exit_i"], "dir": d, "entry": entry,
                        "risk": risk, "fee": fee, "r": res["r"], "B": B, "A": A, "e20": e20, "lo30": lo30, "hi30": hi30})
    return out


def close_r(t, j):
    B = t["B"]
    px = B["c"][j] - (B["bars"][j]["spread"] * B["point"] if t["dir"] == -1 else 0.0)
    return t["dir"] * (px - t["entry"]) / t["risk"] - t["fee"] / t["risk"]


def reversal_exit(t, kind) -> int | None:
    """First bar after entry and before the original exit where the reversal shows (exit at its close)."""
    B, d, A = t["B"], t["dir"], t["A"]
    c = B["c"]
    reached = False
    for j in range(t["i"] + 1, t["exit_i"]):
        if d * (c[j] - t["entry"]) >= t["risk"]:
            reached = True
        if kind == "EMA20" and d * (c[j] - t["e20"][j]) < 0:
            return j
        if kind == "EMA20+1R" and reached and d * (c[j] - t["e20"][j]) < 0:
            return j
        if kind == "DON30" and ((d == 1 and c[j] < t["lo30"][j]) or (d == -1 and c[j] > t["hi30"][j])):
            return j
        if kind == "ENGULF+1R" and reached and engulf(*A[:4], j, -d):
            return j
    return None


def per_period(rows, key="r"):
    return {k: [x[key] for x in rows if a <= x["in"] < b] for k, (a, b) in PERIODS.items()}


def fmt(rs):
    if not rs:
        return "n=0"
    w = [r for r in rs if r > 0]
    l_ = [-r for r in rs if r <= 0]
    rr = statistics.fmean(w) / statistics.fmean(l_) if w and l_ else 0.0
    return f"{statistics.fmean(rs):+.3f} (RR {rr:.2f}, thắng {len(w) / len(rs):.0%}, n={len(rs)})"


# ---------------------------------------------------------------------------
def main() -> None:
    pyramid.GAP_FILL = True
    lines = ["# G43 phần C3 + F: thoát khi đảo chiều và mô hình nến (chỉ dữ liệu MT5)", ""]

    # C3
    paths = t2_paths()
    rng = np.random.default_rng(433)
    lines += ["## C3. Thoát sớm khi đảo chiều — T2 (5 symbol)", "",
              "| Cách thoát | Train | Validate | Test | Tất cả | Lệnh bị thoát sớm | Ngẫu nhiên p |", "|---|---|---|---|---|---|---|"]
    base = per_period(paths)
    lines.append(f"| gốc (trail 3 ATR) | {fmt(base['train'])} | {fmt(base['validate'])} | {fmt(base['test'])} | {fmt(base['all'])} | - | - |")
    for kind in ("EMA20", "EMA20+1R", "DON30", "ENGULF+1R"):
        rows, early = [], []
        for t in paths:
            j = reversal_exit(t, kind)
            r = close_r(t, j) if j is not None else t["r"]
            rows.append({"in": t["in"], "r": r})
            if j is not None:
                early.append(t)
        real = statistics.fmean(x["r"] for x in rows)
        sims = []
        for _ in range(RUNS):
            tot = 0.0
            for t in paths:
                if t in early and t["exit_i"] - t["i"] > 1:
                    j = int(rng.integers(t["i"] + 1, t["exit_i"]))
                    tot += close_r(t, j)
                else:
                    tot += t["r"]
            sims.append(tot / len(paths))
        p = float(np.mean(np.array(sims) >= real))
        pp = per_period(rows)
        lines.append(f"| {kind} | {fmt(pp['train'])} | {fmt(pp['validate'])} | {fmt(pp['test'])} | {fmt(pp['all'])} | "
                     f"{len(early) / len(paths):.0%} | {p:.3f} |")
    lines.append("")

    # F
    rb.init_worker()
    usd, dxy = filters.usd_index(), filters.real_dxy()
    sets = {}
    tf, _, sig, rule_fn = dv.FAMILIES["T2"]
    sets["T2"] = [{"in": t["in"], "r": t["r"], "j": t["i"], "dir": t["dir"], "A": t["A"]} for t in paths]
    for name, label in (("S06B_USD", "S06B lọc USD"), ("S04", "S04")):
        rows = []
        for s in ls.SYMBOLS:
            c = rb._C[s]
            A = arrays(c["entry"])
            sig_ = exits.trades(name, s, usd, dxy)
            res = exits.account_rows(rb._C, sig_, pyramid.CURRENT, 1.0 if name.startswith("S06B") else None, label)
            for t, rr in zip(sig_, res):
                rows.append({"in": t["utc"], "r": rr["r"], "j": t["i"], "dir": t["dir"], "A": A})
        sets[label] = rows
    lines += ["## F. Mô hình nến làm bộ lọc vào lệnh", "",
              "| Setup | Mô hình | Giữ lại | Train | Validate | Test | Tất cả | Ngẫu nhiên p |", "|---|---|---|---|---|---|---|---|"]
    for label, rows in sets.items():
        pp = per_period(rows)
        lines.append(f"| {label} | (không lọc) | 100% | {fmt(pp['train'])} | {fmt(pp['validate'])} | {fmt(pp['test'])} | {fmt(pp['all'])} | - |")
        for pat in PATTERNS:
            kept = [x for x in rows if has_pattern(pat, x["A"], x["j"], x["dir"])]
            if len(kept) < 20:
                lines.append(f"| {label} | {pat} | {len(kept) / len(rows):.0%} | quá ít lệnh | | | | |")
                continue
            share = len(kept) / len(rows)
            real = statistics.fmean(x["r"] for x in kept)
            all_r = np.array([x["r"] for x in rows])
            sims = [all_r[rng.random(len(all_r)) < share].mean() for _ in range(RUNS)]
            p = float(np.mean(np.array(sims) >= real))
            kp = per_period(kept)
            lines.append(f"| {label} | {pat} | {share:.0%} | {fmt(kp['train'])} | {fmt(kp['validate'])} | {fmt(kp['test'])} | "
                         f"{fmt(kp['all'])} | {p:.3f} |")
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "g43_reversal.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
