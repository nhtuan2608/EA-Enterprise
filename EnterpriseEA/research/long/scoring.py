"""G33 (part 1): can a trade-quality score raise the odds of the entries? MT5 data only.

  python scoring.py

Every candidate of S04, S06B, S06 (12-bar box, confirm, any HTF side) and S02 (MARKET), SWING H1
2010-2025, evaluated with the current Trade Manager (costs on). Features at the entry bar's close:
  adx         ADX14 H1 / 50
  atr_rank    ATR14 percentile over the previous 500 bars
  d1          +1 with the D1 EMA200 side, -1 against, 0 unknown
  usd         +1 with the USD flow (G27), -1 against, 0 not a USD pair
  htf         +1 with the H4 structure, -1 against, 0 neutral
  ext         distance of the close from EMA50 in the trade's direction, ATR (clipped +-5) / 5
  rsi         (RSI14 - 50) in the trade's direction / 50
  london, ny  entry hour (UTC) 7-12, 12-17
  body        body / range of the entry bar
  range       entry bar range / ATR (clipped 4) / 4
  tickvol     tick volume / mean of the 24 bars before (clipped 4) / 4
  room        distance to the nearest level beyond the entry (H4 levels), ATR (clipped 10) / 10
  stop        stop distance / ATR (clipped 6) / 6
One logistic regression (P(trade ends positive)), L2-regularised, fitted on 2010-2016 only, with
setup indicators, on all four setups pooled (S06 gives most of the rows). The 2010-2016 score
terciles become fixed thresholds; validate 2017-2020 and test 2021-2025 show expectancy per
tercile. A score helps only if the top tercile beats the bottom one in every period and keeping the
top two thirds beats random removal of the same share (90th percentile).
"""
from __future__ import annotations

import json
import math
import random
import statistics

import long_study as ls  # sets the research data path and sys.path first
import crowd  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

FEATURES = ["adx", "atr_rank", "d1", "usd", "htf", "ext", "rsi", "london", "ny", "body", "range", "tickvol", "room", "stop"]
SETUPS = ["S04", "S06B", "S06", "S02"]
S06_ANY = dict(ls.S06_LIVE)


def candidates(name: str, c: dict) -> list[tuple[dict, dict]]:
    if name == "S04":
        cands = replay.candidates(c, "S04", replay.engine_params("S04", "SWING"))
        return [(x, replay.evaluate(c, x, "S04", "SWING", "tm", {"costs": True})) for x in cands]
    if name in ("S06", "S06B"):
        p = S06_ANY if name == "S06" else filters.S06B
        t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
        return [(x, replay.evaluate(c, x, "S06", "SWING", "tm", t)) for x in setups.s06(c, p)]
    cands = [x for x in replay.candidates(c, "S02", replay.engine_params("S02", "SWING")) if x.get("kind") != "LIMIT"]
    return [(x, replay.evaluate(c, x, "S02", "SWING", "tm", {"costs": True})) for x in cands]


def rows_for(symbol: str, usd: dict) -> list[dict]:
    c = ls.ctx(symbol, "SWING")
    if c is None:
        return []
    bars = c["entry"]
    shift = bars[0]["time"] - bars[0]["utc"]
    a = filters.adx(bars)
    trend = filters.d1_trend(bars)
    closes = [b["close"] for b in bars]
    e50 = filters.ema(closes, 50)
    r14 = crowd.rsi(closes)
    tv = crowd.tickvol(symbol)
    vol = [tv.get(b["time"], 0) for b in bars]
    atrs = [b["atr"] for b in bars]
    out = []
    for name in SETUPS:
        for x, r in candidates(name, c):
            if r["status"] != "EVALUATED":
                continue
            i, d = x["i"], x["direction"]
            atr = atrs[i] or 1e-12
            window = [v for v in atrs[max(0, i - 500):i] if v > 0]
            prev = [v for v in vol[max(0, i - 24):i] if v > 0]
            flow = usd.get(bars[i]["time"], 0)
            usd_sign = filters.USD_SIGN.get(symbol, 0)
            beyond = [d * (p - r["entry"]) for p in x.get("points", []) if d * (p - r["entry"]) > 0.25 * atr]
            hour = (bars[i]["utc"] // 3600) % 24
            rng = bars[i]["high"] - bars[i]["low"]
            st = x.get("structure", "NEUTRAL")
            f = {"adx": a[i] / 50, "atr_rank": sum(1 for v in window if v < atr) / len(window) if window else 0.5,
                 "d1": 0 if trend[i] == 0 else (1 if trend[i] == d else -1),
                 "usd": 0 if flow == 0 or usd_sign == 0 else (1 if d * usd_sign == flow else -1),
                 "htf": 0 if st == "NEUTRAL" else (1 if (st == "UP") == (d == 1) else -1),
                 "ext": max(-5, min(5, d * (bars[i]["close"] - e50[i]) / atr)) / 5,
                 "rsi": d * (r14[i] - 50) / 50,
                 "london": 1 if 7 <= hour < 12 else 0, "ny": 1 if 12 <= hour < 17 else 0,
                 "body": abs(bars[i]["close"] - bars[i]["open"]) / rng if rng > 0 else 0,
                 "range": min(4, rng / atr) / 4,
                 "tickvol": min(4, vol[i] / statistics.fmean(prev)) / 4 if prev and vol[i] > 0 else 0.25,
                 "room": min(10, min(beyond) / atr) / 10 if beyond else 1.0,
                 "stop": min(6, abs(r["entry"] - r["stop"]) / atr) / 6}
            out.append({"setup": name, "symbol": symbol, "utc": bars[i]["time"] - shift, "r": r["r"], "f": f})
    return out


def vector(row: dict) -> list[float]:
    return [1.0] + [row["f"][k] for k in FEATURES] + [1.0 if row["setup"] == s else 0.0 for s in SETUPS[1:]]


def fit(rows: list[dict], l2: float = 1.0, steps: int = 3000, lr: float = 0.5) -> list[float]:
    """Logistic regression by full-batch gradient descent (no numpy on this machine)."""
    xs = [vector(r) for r in rows]
    ys = [1.0 if r["r"] > 0 else 0.0 for r in rows]
    w = [0.0] * len(xs[0])
    n = len(xs)
    for _ in range(steps):
        g = [0.0] * len(w)
        for x, y in zip(xs, ys):
            z = sum(a * b for a, b in zip(w, x))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            for k in range(len(w)):
                g[k] += (p - y) * x[k]
        for k in range(len(w)):
            w[k] -= lr * (g[k] / n + (l2 / n) * w[k] * (k > 0))
    return w


def score(w: list[float], row: dict) -> float:
    z = sum(a * b for a, b in zip(w, vector(row)))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def stats(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "exp": 0.0, "win": 0.0}
    return {"n": len(rows), "exp": statistics.fmean(r["r"] for r in rows), "win": sum(r["r"] > 0 for r in rows) / len(rows)}


def fmt(s: dict) -> str:
    return f"{s['exp']:+.3f} (n={s['n']}, thắng {s['win']:.0%})" if s["n"] else "n=0"


def random_p90(pool: list[dict], keep: int, seed: int = 3) -> float:
    if keep <= 0 or keep >= len(pool):
        return float("-inf")
    rnd = random.Random(seed)
    sims = sorted(statistics.fmean(t["r"] for t in rnd.sample(pool, keep)) for _ in range(300))
    return sims[int(0.9 * len(sims))]


def main() -> None:
    usd = filters.usd_index()
    rows = [r for s in ls.SYMBOLS for r in rows_for(s, usd)]
    for r in rows:
        r["period"] = exits.period(r["utc"])
    train = [r for r in rows if r["period"] == "train"]
    w = fit(train)
    for r in rows:
        r["score"] = score(w, r)
    lines = ["# G33 phần 1: điểm chất lượng lệnh (hồi quy logistic, chỉ dữ liệu MT5)", "",
             f"{len(rows)} lệnh ({len(train)} lệnh 2010–2016 để học). Hệ số (đặc trưng đã chuẩn hóa, dương = tăng xác suất thắng):", "",
             "| Đặc trưng | Hệ số |", "|---|---|"]
    names = ["hằng số"] + FEATURES + [f"setup {s}" for s in SETUPS[1:]]
    for nm, v in sorted(zip(names, w), key=lambda x: -abs(x[1])):
        lines.append(f"| {nm} | {v:+.2f} |")
    lines.append("")
    for name in SETUPS:
        mine = [r for r in rows if r["setup"] == name]
        tr = sorted(r["score"] for r in mine if r["period"] == "train")
        if len(tr) < 30:
            continue
        lo, hi = tr[len(tr) // 3], tr[2 * len(tr) // 3]
        lines += [f"## {name}", "",
                  f"Ngưỡng (từ 2010–2016): thấp < {lo:.3f} ≤ giữa < {hi:.3f} ≤ cao", "",
                  "| Giai đoạn | Tất cả | Điểm thấp | Điểm giữa | Điểm cao | Bỏ 1/3 thấp | Bỏ ngẫu nhiên cùng số (p90) |",
                  "|---|---|---|---|---|---|---|"]
        steady = True
        for p in ("train", "validate", "test"):
            rs = [r for r in mine if r["period"] == p]
            low = [r for r in rs if r["score"] < lo]
            mid = [r for r in rs if lo <= r["score"] < hi]
            top = [r for r in rs if r["score"] >= hi]
            keep = [r for r in rs if r["score"] >= lo]
            s_all, s_low, s_top, s_keep = stats(rs), stats(low), stats(top), stats(keep)
            rp = random_p90(rs, len(keep))
            steady &= s_top["n"] > 0 and s_low["n"] > 0 and s_top["exp"] > s_low["exp"] and s_keep["exp"] > s_all["exp"]
            lines.append(f"| {p} | {fmt(s_all)} | {fmt(s_low)} | {fmt(stats(mid))} | {fmt(s_top)} | {fmt(s_keep)} | {rp:+.3f} |")
        lines += ["", f"Điểm cao > điểm thấp và bỏ 1/3 thấp tốt hơn tất cả ở cả 3 giai đoạn: **{'có' if steady else 'không'}**", ""]
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    (ls.OUT / "scoring.md").write_text(text, encoding="utf-8")
    (ls.OUT / "scoring_weights.json").write_text(json.dumps(dict(zip(names, w)), indent=1), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
