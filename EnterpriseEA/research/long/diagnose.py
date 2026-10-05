"""G24: why a setup loses. Diagnostics on the long-history data (research/long/data).

  python diagnose.py

For S02 SWING (H1 2010-2025), S02 SCALP (M5 2024-06..2025-10) and, as references, S04 SWING
and S06 SWING (live configurations):
  (a) gross vs net expectancy and the average cost per trade in R
  (b) edge curve: signed move in ATR after the trigger at 1/3/6/12/24 bars (no stop, no target)
  (c) path: share reaching +1R before -1R, losers that were +1R first, median MFE / MAE
  (d) sensitivity to the stop buffer and the target
  (e) segments: HTF aligned or not, session hour, volatility (ATR percentile)
"""
from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import datetime, timezone

import long_study as ls
import replay
import setups

HORIZONS = (1, 3, 6, 12, 24)


def cands_for(setup: str, profile: str, symbol: str):
    c = ls.ctx(symbol, profile)
    if c is None:
        return None, []
    if setup == "S06":
        return c, setups.s06(c, ls.S06_LIVE)
    raw = replay.candidates(c, setup, replay.engine_params(setup, profile))
    return c, [x for x in raw if x.get("kind") != "LIMIT"]


def mean_ci(xs: list[float]):
    if len(xs) < 2:
        return (xs[0] if xs else 0.0, 0.0)
    return statistics.fmean(xs), 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))


def edge_curve(c, cands) -> dict:
    out = {h: [] for h in HORIZONS}
    bars = c["entry"]
    for x in cands:
        i, d, atr = x["i"], x["direction"], x["signal_atr"] or bars[x["i"]]["atr"]
        if atr <= 0:
            continue
        for h in HORIZONS:
            if i + h < len(bars):
                out[h].append(d * (bars[i + h]["close"] - bars[i]["close"]) / atr)
    return out


def path_stats(c, cands, buffer_atr=0.10) -> list[dict]:
    """+1R / -1R race from the trigger close, stop at the setup anchor plus buffer, 48 bars max."""
    rows = []
    bars = c["entry"]
    for x in cands:
        i, d = x["i"], x["direction"]
        entry = bars[i]["close"]
        stop = x["extreme"] - d * max(buffer_atr * x["signal_atr"], 0.0)
        risk = d * (entry - stop)
        if risk <= 0:
            continue
        mfe = mae = 0.0
        first = None
        for b in range(i + 1, min(len(bars), i + 49)):
            up = d * ((bars[b]["high"] if d == 1 else bars[b]["low"]) - entry) / risk
            dn = d * ((bars[b]["low"] if d == 1 else bars[b]["high"]) - entry) / risk
            mfe, mae = max(mfe, up), min(mae, dn)
            if first is None:
                if dn <= -1.0:
                    first = "SL"
                elif up >= 1.0:
                    first = "1R"
        rows.append({"first": first, "mfe": mfe, "mae": mae, "risk_atr": risk / max(x["signal_atr"], 1e-12)})
    return rows


def evaluate(setup, profile, trade: dict, symbols=ls.SYMBOLS) -> list[dict]:
    rows = []
    for s in symbols:
        c, cs = cands_for(setup, profile, s)
        if c is None:
            continue
        rows += [replay.evaluate(c, x, setup, profile, "tm", dict(trade)) for x in cs]
    return [r for r in rows if r["status"] == "EVALUATED"]


def segment(setup, profile, trade) -> dict:
    out = {"htf_aligned": [], "htf_counter": [], "london_ny": [], "asia": [], "vol_low": [], "vol_mid": [], "vol_high": []}
    for s in ls.SYMBOLS:
        c, cs = cands_for(setup, profile, s)
        if c is None:
            continue
        atrs = sorted(b["atr"] for b in c["entry"] if b["atr"] > 0)
        q1, q2 = atrs[len(atrs) // 3], atrs[2 * len(atrs) // 3]
        for x in cs:
            r = replay.evaluate(c, x, setup, profile, "tm", dict(trade))
            if r["status"] != "EVALUATED":
                continue
            out["htf_aligned" if replay.htf_aligned(x["structure"], x["direction"]) else "htf_counter"].append(r["r"])
            hour = datetime.fromtimestamp(c["entry"][x["i"]]["utc"], timezone.utc).hour
            out["london_ny" if 7 <= hour < 20 else "asia"].append(r["r"])
            a = c["entry"][x["i"]]["atr"]
            out["vol_low" if a <= q1 else "vol_mid" if a <= q2 else "vol_high"].append(r["r"])
    return {k: (len(v), statistics.fmean(v) if v else 0.0) for k, v in out.items()}


def summary(rows):
    return (len(rows), statistics.fmean(r["r"] for r in rows) if rows else 0.0)


def diagnose(setup: str, profile: str) -> list[str]:
    lines = [f"## {setup} {profile}"]
    base = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "aligned"} if setup == "S06" else {}
    net = evaluate(setup, profile, dict(base, costs=True))
    gross = evaluate(setup, profile, dict(base, costs=False))
    n, e_net = summary(net)
    _, e_gross = summary(gross)
    lines.append(f"(a) n={n}: trước phí {e_gross:+.3f}R, sau phí {e_net:+.3f}R, chi phí ≈ {e_gross - e_net:.3f}R/lệnh")
    curves = {h: [] for h in HORIZONS}
    paths = []
    for s in ls.SYMBOLS:
        c, cs = cands_for(setup, profile, s)
        if c is None:
            continue
        for h, v in edge_curve(c, cs).items():
            curves[h] += v
        paths += path_stats(c, cs)
    parts = []
    for h in HORIZONS:
        m, ci = mean_ci(curves[h])
        parts.append(f"{h} nến {m:+.3f}±{ci:.3f}")
    lines.append("(b) đường lợi thế (ATR theo hướng lệnh): " + "; ".join(parts))
    if paths:
        win1r = sum(1 for p in paths if p["first"] == "1R") / len(paths)
        sl_first = sum(1 for p in paths if p["first"] == "SL") / len(paths)
        losers = [p for p in paths if p["first"] == "SL"]
        lines.append(f"(c) +1R trước −1R: {win1r:.0%}; −1R trước: {sl_first:.0%}; MFE trung vị {statistics.median(p['mfe'] for p in paths):.2f}R, "
                     f"MAE trung vị {statistics.median(p['mae'] for p in paths):.2f}R; khoảng SL trung vị "
                     f"{statistics.median(p['risk_atr'] for p in paths):.2f} ATR; lệnh SL-trước từng đạt ≥0,5R: "
                     f"{sum(1 for p in losers if p['mfe'] >= 0.5) / max(len(losers), 1):.0%}")
    sens = []
    for buf in (0.10, 0.50, 1.00):
        for tgt in ({"target": "structural"}, {"target": "fixed", "fixed_r": 1.5, "min_rr": 1.5},
                    {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0}):
            t = dict(base, **tgt, buffer_atr=buf, costs=True)
            n2, e2 = summary(evaluate(setup, profile, t))
            sens.append(f"đệm {buf} {tgt['target']}{tgt.get('fixed_r', '')}: {e2:+.3f} ({n2})")
    lines.append("(d) độ nhạy: " + "; ".join(sens))
    seg = segment(setup, profile, dict(base, costs=True))
    lines.append("(e) nhóm: " + "; ".join(f"{k} {e:+.3f} ({n})" for k, (n, e) in seg.items()))
    return lines


def random_control(profile: str) -> str:
    """Random direction at random bars, same stop/target model: the cost floor and noise level."""
    rnd = random.Random(7)
    rows = []
    for s in ls.SYMBOLS:
        c = ls.ctx(s, profile)
        if c is None:
            continue
        bars = c["entry"]
        for i in range(100, len(bars) - 100, 37):
            b = bars[i]
            if b["atr"] <= 0 or c["bar_level"][i] not in c["levels"]:
                continue
            d = rnd.choice((1, -1))
            x = {"kind": "MARKET", "i": i, "time": b["time"], "direction": d, "extreme": b["close"] - d * 1.5 * b["atr"],
                 "zone_low": 0, "zone_high": 0, "signal_atr": b["atr"], "points": [], "structure": "NEUTRAL"}
            r = replay.evaluate(c, x, "RND", profile, "tm", {"target": "fixed", "fixed_r": 2.0, "min_rr": 2.0, "costs": True})
            if r["status"] == "EVALUATED":
                rows.append(r["r"])
    return f"Đối chứng ngẫu nhiên {profile} (SL 1,5 ATR, TP 2R, có phí): n={len(rows)} {statistics.fmean(rows):+.3f}R"


def main() -> None:
    out = ["# G24 chẩn đoán", ""]
    for setup, profile in (("S02", "SWING"), ("S02", "SCALP"), ("S04", "SWING"), ("S06", "SWING")):
        out += diagnose(setup, profile) + [""]
        print("\n".join(out[-7:]), flush=True)
    out += [random_control("SWING"), random_control("SCALP")]
    text = "\n".join(out) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "diagnose.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
