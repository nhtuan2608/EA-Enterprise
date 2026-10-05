"""G11 part 2 (market-sentiment design section 7): rebuild the cross-pair sentiment at the time of
every recorded news reaction and measure whether it relates to the direction of the reaction.
Research only: it creates no signal and changes no parameter.

Inputs (written by the EA):
  research/bars_<PAIR>_H1.csv   the 13 sentiment reference pairs (selected symbols + reference_h1)
  research/bars_meta.json       server offset at export time
  logs/news_reactions.jsonl     one record per HIGH event x symbol (moves in ATR after the release)

  python sentiment_news.py            # writes results/sentiment_news.md and prints it

The sentiment uses only H1 bars closed before the release, with the EA's formula
(Market/SentimentRuntime.mqh EEA_SentMeasure, Market/Sentiment.mqh via Tests/sentiment_oracle.py).
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "g10"))
sys.path.insert(0, str(HERE.parents[1] / "Tests"))

import context  # noqa: E402
import sentiment_oracle as so  # noqa: E402

FX = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY"]
OTHER = {"XAUUSD": "GOLD", "BTCUSD": "BTC"}
WINDOW = 40                    # EEA_SentMeasure copies 40 closed H1 bars
STRONG = 0.5                   # |score| above this counts as a clear sentiment
OUT = HERE / "results"


def load_closes(symbol: str):
    path = context.DATA / f"bars_{symbol}_H1.csv"
    if not path.exists():
        return None
    bars = context.load_bars(symbol, "H1")
    return {"time": [b["time"] for b in bars], "bars": bars}


def measure(series: dict, before_server: int):
    """z4, z24 of one pair from the 40 H1 bars closed at or before before_server (EA formula)."""
    times = series["time"]
    last = bisect.bisect_right(times, before_server - 3600) - 1      # bar open + 1h <= release
    if last < WINDOW - 1:
        return None
    rates = series["bars"][last - WINDOW + 1:last + 1]
    tr = 0.0
    for i in range(WINDOW - 14, WINDOW):
        tr += max(rates[i]["high"], rates[i - 1]["close"]) - min(rates[i]["low"], rates[i - 1]["close"])
    atr = tr / 14.0
    if atr <= 0:
        return None
    c0 = rates[-1]["close"]
    return {"z4": (c0 - rates[-5]["close"]) / (atr * 2.0), "z24": (c0 - rates[-25]["close"]) / (atr * math.sqrt(24.0))}


def snapshot(series_by_pair: dict, before_server: int):
    pairs = []
    for sym, series in series_by_pair.items():
        z = measure(series, before_server)
        if z is None:
            continue
        kind = OTHER.get(sym, "FX")
        pairs.append({"symbol": sym, "base": sym[:3], "quote": sym[3:6], "kind": kind, "z4": z["z4"], "z24": z["z24"]})
    snap = so.compute(pairs, so.config())
    snap["pairs"] = {p["symbol"]: p for p in pairs}
    return snap


def direction_score(snap: dict, symbol: str, horizon: str = "s4"):
    """Sentiment pull on the symbol: base strength minus quote strength (gold: against USD)."""
    s = snap[horizon]
    base, quote = symbol[:3], symbol[3:6]
    if base in s and quote in s:
        return s[base] - s[quote]
    if base == "XAU" and "USD" in s:
        return -s["USD"]
    return None


def surprise_direction(rec: dict):
    """Naive expected direction of the symbol from the surprise (above forecast = currency stronger)."""
    side = rec.get("surprise_side")
    if side not in ("ABOVE", "BELOW") or rec.get("surprise_quality") != "OK":
        return 0
    c, sym = rec.get("currency"), rec.get("symbol", "")
    sign = 1 if side == "ABOVE" else -1
    if sym[:3] == c:
        return sign
    if sym[3:6] == c:
        return -sign
    return 0


def wilson(hits: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = hits / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, centre - half, centre + half)


def sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


def analyse(records: list[dict], series_by_pair: dict, offset_at) -> dict:
    rows = []
    for rec in records:
        if rec.get("quality") != "OK" or not rec.get("replay_ok"):
            continue
        sym = rec.get("symbol", "")
        utc = int(rec["event_utc"])
        snap = snapshot(series_by_pair, utc + offset_at(utc))
        if not snap.get("ok"):
            continue
        score4 = direction_score(snap, sym, "s4")
        if score4 is None:
            continue
        own = snap["pairs"].get(sym)
        rows.append({"symbol": sym, "group": rec.get("group", ""), "regime": snap["regime"],
                     "score4": score4, "score24": direction_score(snap, sym, "s24"),
                     "own4": own["z4"] if own else None,
                     "m15": float(rec.get("move_15m_atr", 0.0)), "m60": float(rec.get("move_60m_atr", 0.0)),
                     "surprise": surprise_direction(rec)})
    return {"rows": rows, "summary": summarise(rows)}


def hit_rate(rows: list[dict], key: str, move: str, strong: float = 0.0) -> dict:
    sel = [r for r in rows if r.get(key) is not None and abs(r[key]) > strong and sign(r[move]) != 0]
    hits = sum(1 for r in sel if sign(r[key]) == sign(r[move]))
    p, lo, hi = wilson(hits, len(sel))
    return {"n": len(sel), "hit": p, "lo": lo, "hi": hi}


def summarise(rows: list[dict]) -> dict:
    out = {"n": len(rows), "tests": {}}
    for key, label in (("score4", "Sentiment 4h"), ("score24", "Sentiment 24h"), ("own4", "Own pair momentum 4h")):
        for move in ("m15", "m60"):
            out["tests"][f"{label} -> {move}"] = hit_rate(rows, key, move)
            out["tests"][f"{label} (mạnh >{STRONG}) -> {move}"] = hit_rate(rows, key, move, STRONG)
    agree = [r for r in rows if r["surprise"] and sign(r["score4"]) == r["surprise"]]
    against = [r for r in rows if r["surprise"] and sign(r["score4"]) == -r["surprise"]]
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
    out["surprise"] = {
        "with_sentiment": {"n": len(agree), "follow_m60": mean([r["surprise"] * r["m60"] for r in agree])},
        "against_sentiment": {"n": len(against), "follow_m60": mean([r["surprise"] * r["m60"] for r in against])},
    }
    out["regime"] = {}
    for reg in ("RISK_ON", "NEUTRAL", "RISK_OFF"):
        for sym in ("XAUUSD", "USDJPY"):
            sel = [r["m60"] for r in rows if r["regime"] == reg and r["symbol"] == sym]
            out["regime"][f"{reg} {sym}"] = {"n": len(sel), "mean_m60": mean(sel)}
    return out


def markdown(s: dict, missing: list[str]) -> str:
    lines = ["# G11 phần 2: sentiment trước tin và hướng phản ứng", "",
             f"Bản ghi dùng được: {s['n']}." + (f" Thiếu nến H1 của: {', '.join(missing)}." if missing else ""), "",
             "| Phép thử | n | Trùng hướng | 95% CI |", "|---|---|---|---|"]
    for name, t in s["tests"].items():
        lines.append(f"| {name} | {t['n']} | {t['hit']:.1%} | {t['lo']:.1%}–{t['hi']:.1%} |")
    sp = s["surprise"]
    lines += ["", "Tin bất ngờ (chiều ngây thơ: trên dự báo = đồng tiền mạnh lên), mức đi theo hướng bất ngờ sau 60 phút (ATR):",
              f"- Cùng chiều sentiment: n={sp['with_sentiment']['n']}, {sp['with_sentiment']['follow_m60']:+.2f}",
              f"- Ngược chiều sentiment: n={sp['against_sentiment']['n']}, {sp['against_sentiment']['follow_m60']:+.2f}",
              "", "Regime và phản ứng 60 phút (ATR, có dấu):"]
    for k, v in s["regime"].items():
        lines.append(f"- {k}: n={v['n']}, {v['mean_m60']:+.2f}")
    lines += ["", "Đọc kết quả: khoảng tin cậy chứa 50% nghĩa là không thấy liên hệ. Chỉ là nghiên cứu; không đổi tham số."]
    return "\n".join(lines) + "\n"


def main() -> None:
    meta = context.meta()
    now_offset, now_utc = int(meta["server_offset_now"]), int(meta["exported_at_utc"])
    series, missing = {}, []
    for sym in FX + list(OTHER):
        s = load_closes(sym)
        if s is None:
            missing.append(sym)
        else:
            series[sym] = s
    path = context.DATA.parent / "logs" / "news_reactions.jsonl"
    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    result = analyse(records, series, lambda utc: context.server_offset_at(utc, now_offset, now_utc))
    text = markdown(result["summary"], missing)
    OUT.mkdir(exist_ok=True)
    (OUT / "sentiment_news.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
