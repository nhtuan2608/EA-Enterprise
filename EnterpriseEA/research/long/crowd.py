"""G28 (part 2): crowd behaviour proxies from MT5 data only, and losing-streak dependence.

  python crowd.py

Proxies at the entry bar's close (H1, research/long/data, tick volume from tickvol_<SYM>_H1.csv):
  VOL_SPIKE   tick volume >= 1.5 x the mean of the 24 bars before (participation surge)
  VOL_QUIET   tick volume <= 0.8 x that mean
  CHASE       price already more than 2 ATR beyond EMA50 in the trade's direction (buying late)
  NOT_CHASE   the opposite of CHASE
  STREAK_WITH 4+ consecutive closes in the trade's direction just before entry (FOMO run)
  STREAK_AGAINST 4+ consecutive closes against it (exhaustion of the other side)
  RSI_HOT     RSI14 > 70 for a long / < 30 for a short (greed / panic at entry)
  BIG_BAR     entry bar range > 2 ATR (emotional bar)
Same selection as G27 (filters.py): train 2010-2016 only, beat random removal (90th percentile),
validate 2017-2020 and test 2021-2025 reported.

Losing streaks: does a trade's expectancy depend on the previous results? Expectancy after
0, 1, 2, 3+ losses in a row, and a Wald-Wolfowitz runs test on win/loss order. If results are
independent, raising size to win back losses is a martingale and only raises the risk of ruin.
"""
from __future__ import annotations

import itertools
import math
import statistics
from collections import defaultdict

import long_study as ls  # sets the data path and sys.path first
import context  # noqa: E402
import filters  # noqa: E402

FEATURES = ["VOL_SPIKE", "VOL_QUIET", "CHASE", "NOT_CHASE", "STREAK_WITH", "STREAK_AGAINST", "RSI_HOT", "BIG_BAR"]
EXCLUSIVE = [{"VOL_SPIKE", "VOL_QUIET"}, {"CHASE", "NOT_CHASE"}, {"STREAK_WITH", "STREAK_AGAINST"}]


def tickvol(symbol: str) -> dict:
    out = {}
    with open(context.DATA / f"tickvol_{symbol}_H1.csv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            t, v = line.split(",")
            out[int(t)] = int(v)
    return out


def rsi(closes: list[float], n: int = 14) -> list[float]:
    out = [50.0] * len(closes)
    up = dn = 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if i <= n:
            up += g / n
            dn += l / n
        else:
            up = (up * (n - 1) + g) / n
            dn = (dn * (n - 1) + l) / n
        if i >= n:
            out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def tag(rows: list[dict], symbol: str) -> None:
    bars = ls.ctx(symbol, "SWING")["entry"]
    tv = tickvol(symbol)
    vol = [tv.get(b["time"], 0) for b in bars]
    closes = [b["close"] for b in bars]
    e50 = filters.ema(closes, 50)
    r14 = rsi(closes)
    for t in rows:
        i, d = t["i"], t["dir"]
        prev = [v for v in vol[max(0, i - 24):i] if v > 0]
        ratio = vol[i] / statistics.fmean(prev) if prev and vol[i] > 0 else 1.0
        atr = bars[i]["atr"] or 1e-12
        ext = d * (bars[i]["close"] - e50[i]) / atr
        run_with = run_against = 0
        for k in range(i - 1, max(0, i - 12), -1):        # closes before the entry bar
            s = 1 if bars[k]["close"] > bars[k]["open"] else -1 if bars[k]["close"] < bars[k]["open"] else 0
            if s == d and run_against == 0:
                run_with += 1
            elif s == -d and run_with == 0:
                run_against += 1
            else:
                break
        t["f"] = {"VOL_SPIKE": ratio >= 1.5, "VOL_QUIET": ratio <= 0.8, "CHASE": ext > 2.0, "NOT_CHASE": ext <= 2.0,
                  "STREAK_WITH": run_with >= 4, "STREAK_AGAINST": run_against >= 4,
                  "RSI_HOT": (r14[i] > 70) if d == 1 else (r14[i] < 30),
                  "BIG_BAR": bars[i]["high"] - bars[i]["low"] > 2 * atr}


def signal_rows(name: str, usd: dict, dxy: dict) -> list[dict]:
    out = []
    for s in ls.SYMBOLS:
        rows = filters.base_rows("S06B" if name == "S06B_USD" else name, s)
        if not rows:
            continue
        if name == "S06B_USD":
            filters.tag(rows, s, usd, dxy)
            rows = [t for t in rows if t["f"]["USD_FLOW"]]
        tag(rows, s)
        out += rows
    return out


def streaks(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda t: t["utc"])
    after = defaultdict(list)
    losses = 0
    for t in rows:
        after[min(losses, 3)].append(t["r"])
        losses = losses + 1 if t["r"] < 0 else 0
    seq = [t["r"] > 0 for t in rows]
    n1, n2 = sum(seq), len(seq) - sum(seq)
    runs = 1 + sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    mu = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    return {"after": {k: (len(v), statistics.fmean(v)) for k, v in sorted(after.items())},
            "runs_z": (runs - mu) / math.sqrt(var) if var > 0 else 0.0, "win": n1 / len(seq)}


def main() -> None:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    combos = [()] + [(f,) for f in FEATURES] + [p for p in itertools.combinations(FEATURES, 2)
                                                if not any(set(p) <= e for e in EXCLUSIVE)]
    lines = ["# G28 phần 2: hành vi đám đông (chỉ dữ liệu MT5) và chuỗi thua", ""]
    signals = {name: signal_rows(name, usd, dxy) for name in ("S04", "S06B", "S06B_USD", "S02", "S06")}
    for name, rows in signals.items():
        res = {combo: filters.evaluate(rows, combo) for combo in combos}
        base = res[()]
        lines += [f"## {name}",
                  f"Không lọc: train {filters.fmt(base['train'])} | validate {filters.fmt(base['validate'])} | test {filters.fmt(base['test'])}", "",
                  "| Đặc điểm lúc vào lệnh | Train | Validate | Test | Năm dương (cả kỳ) | DD cả kỳ (R) | Thắng ngẫu nhiên | Ổn định 3 giai đoạn |",
                  "|---|---|---|---|---|---|---|---|"]
        ranked = sorted(((c, v) for c, v in res.items() if c and v["train"]["n"] >= 20), key=lambda kv: filters.score(kv[1]), reverse=True)
        singles = [(c, v) for c, v in res.items() if len(c) == 1]
        shown = ranked[:6] + [x for x in singles if x not in ranked[:6]]
        for combo, v in shown:
            beat = "có" if v["train"]["exp"] > v["random_p90_train"] else "không"
            steady = "có" if all(v[p]["n"] and v[p]["exp"] > base[p]["exp"] for p in ("train", "validate", "test")) else "không"
            lines.append(f"| {'+'.join(combo)} | {filters.fmt(v['train'])} | {filters.fmt(v['validate'])} | {filters.fmt(v['test'])} | "
                         f"{v['all']['pos_years']:.0%} | {v['all']['dd']:.1f} | {beat} | {steady} |")
        lines.append("")
    lines += ["## Chuỗi thua: lệnh kế tiếp có khác không?", "",
              "| Chuỗi lệnh | Tỷ lệ thắng | Sau 0 thua | Sau 1 thua | Sau 2 thua | Sau 3+ thua | Kiểm định runs (z) |",
              "|---|---|---|---|---|---|---|"]
    for name, rows in list(signals.items()) + [("S04 + S06B_USD (danh mục)", signals["S04"] + signals["S06B_USD"])]:
        s = streaks(rows)
        cells = " | ".join(f"{s['after'][k][1]:+.3f} (n={s['after'][k][0]})" if k in s["after"] else "-" for k in range(4))
        lines.append(f"| {name} | {s['win']:.0%} | {cells} | {s['runs_z']:+.2f} |")
    lines += ["", "|z| < 2: thứ tự thắng/thua không khác ngẫu nhiên (các lệnh độc lập)."]
    text = "\n".join(lines) + "\n"
    (ls.OUT / "crowd.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
