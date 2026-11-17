"""Describe the evaluated signals: outcomes, SL/TP geometry, timing, multi-timeframe context vs random bars (enrichment)."""
import json
from collections import Counter

import numpy as np
import pandas as pd

E = json.load(open("evaluated.json", encoding="utf-8"))
SYM = {"XAUUSD": "XAUUSD-VIP", "XAGUSD": "XAGUSD-VIP", "USOUSD": "USOUSD-VIP"}


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


FR = {}
for k, s in SYM.items():
    f = {}
    for tf in ("M5", "M15", "H1", "H4", "D1"):
        d = pd.read_csv(f"{s}_{tf}.csv")
        c, h, l = d["close"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy()
        e50 = ema(c, 50)
        f[tf] = {"t": d["time"].to_numpy(), "c": c, "h": h, "l": l, "o": d["open"].to_numpy(), "e21": ema(c, 21), "e50": e50, "e200": ema(c, 200),
                 "rsi": rsi(c), "atr": atr(h, l, c),
                 "slope": np.r_[np.zeros(10), e50[10:] - e50[:-10]]}
    FR[k] = f
SEC = {"M5": 300, "M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}


def ctx(sym, ts, d):
    """Context known at ts (last closed bar of each TF), expressed relative to the trade side d (+1 buy, -1 sell)."""
    out = {}
    for tf, F in FR[sym].items():
        k = int(np.searchsorted(F["t"], ts - SEC[tf], side="right")) - 1           # bar closed by ts
        if k < 60:
            return None
        c = F["c"][k]
        out[f"{tf} giá cùng phía EMA50"] = d * (c - F["e50"][k]) > 0
        out[f"{tf} EMA50 dốc cùng chiều"] = d * F["slope"][k] > 0
        if tf in ("M15", "H1", "H4"):
            out[f"{tf} RSI quá mua/bán ngược chiều lệnh"] = (F["rsi"][k] >= 70) if d == -1 else (F["rsi"][k] <= 30)
            out[f"{tf} RSI cực 60/40 ngược chiều"] = (F["rsi"][k] >= 60) if d == -1 else (F["rsi"][k] <= 40)
        if tf == "H1":
            hi12, lo12 = F["h"][k - 11:k + 1].max(), F["l"][k - 11:k + 1].min()
            pos = (c - lo12) / (hi12 - lo12) if hi12 > lo12 else 0.5
            out["H1 giá ở 1/3 biên 12h ngược chiều (bán ở đỉnh / mua ở đáy)"] = pos >= 2 / 3 if d == -1 else pos <= 1 / 3
            mv = c - F["c"][k - 4]
            out["H1 4 giờ trước đi ngược chiều lệnh (fade)"] = d * mv < 0
            out["H1 nến vừa đóng ngược chiều lệnh"] = d * (c - F["o"][k]) < 0
            out["H1 chạm EMA21"] = F["l"][k] <= F["e21"][k] <= F["h"][k]
            ex = F["h"][k] if d == -1 else F["l"][k]
            prev = F["h"][k - 24:k].max() if d == -1 else F["l"][k - 24:k].min()
            out["H1 quét đỉnh/đáy 24h rồi đóng lại (sweep)"] = (ex > prev and c < prev) if d == -1 else (ex < prev and c > prev)
        if tf == "D1":
            out["D1 chế độ EMA50 + dốc cùng chiều"] = (d * (c - F["e50"][k]) > 0) and d * F["slope"][k] > 0
            out["D1 chế độ ngược chiều"] = (d * (c - F["e50"][k]) < 0) and d * F["slope"][k] < 0
    rn = FR[sym]["M5"]
    k = int(np.searchsorted(rn["t"], ts, side="right")) - 1
    p = rn["c"][k]
    unit = 10 if sym == "XAUUSD" else (0.5 if sym == "XAGUSD" else 0.5)
    out["gần số tròn (≤ 20 % bước)"] = abs(p / unit - round(p / unit)) <= 0.2
    return out


def summarize(rs, label):
    n = len(rs)
    sims = [r["sim"] for r in rs]
    tp1 = [s for s in sims if 0 in s["tp_hit"]]
    sl_first = [s for s in sims if s["sl_hit"] and 0 not in s["tp_hit"]]
    open_ = [s for s in sims if not s["sl_hit"] and 0 not in s["tp_hit"]]
    def m(key):
        v = [s.get(key) for s in sims if s.get(key) is not None]
        return (round(float(np.mean(v)), 3), len(v)) if v else (None, 0)
    res = {"n": n, "TP1 trước SL": len(tp1), "SL trước TP1": len(sl_first), "chưa chạm": len(open_),
           "tỷ lệ TP1 (trong các lệnh đã ngã ngũ)": round(len(tp1) / max(1, len(tp1) + len(sl_first)), 3),
           "TP2 chạm": sum(1 for s in sims if 1 in s["tp_hit"]), "TP3 chạm": sum(1 for s in sims if 2 in s["tp_hit"]),
           "R TB – chốt hết ở TP1": m("R_tp1_all"), "R TB – chia đều các TP": m("R_split"), "R TB – chia đều + BE sau TP1": m("R_split_be"),
           "SL TB (giá)": round(float(np.mean([s["risk"] for s in sims])), 3),
           "TP1 / TP2 / TP3 theo R (trung vị)": [round(float(np.median([s["tp_R"][i] for s in sims if len(s["tp_R"]) > i])), 2)
                                                 if any(len(s["tp_R"]) > i for s in sims) else None for i in range(3)],
           "phút tới TP1 (trung vị)": float(np.median([s["tp_min"][0] if 0 in s["tp_min"] else s["tp_min"]["0"] for s in tp1])) if tp1 else None,
           "phút tới SL (trung vị)": float(np.median([s["sl_min"] for s in sl_first])) if sl_first else None}
    print(f"\n== {label}")
    for k, v in res.items():
        print(f"  {k}: {v}")
    return res


ok = [r for r in E if r.get("sim") and r["sim"].get("filled") and not r["sim"].get("bad_levels")]
for r in ok:
    r["sim"]["tp_min"] = {int(k): v for k, v in r["sim"]["tp_min"].items()}
bots = [r for r in ok if r["kind"] == "bot"]
man = [r for r in ok if r["kind"] == "manual"]
report = {}
report["bot tất cả"] = summarize(bots, "BOT – tất cả")
report["bot duyệt"] = summarize([r for r in bots if r["status"] == "duyet"], "BOT – DUYỆT")
report["bot từ chối"] = summarize([r for r in bots if r["status"] == "tuchoi"], "BOT – TỪ CHỐI")
report["bot không nhãn (sau 12/06)"] = summarize([r for r in bots if r["status"] is None], "BOT – không nhãn (15/06–07/2026)")
report["tay XAU"] = summarize(man, "KÈO TAY (vàng)")
report["tay mua"] = summarize([r for r in man if r["side"] == "buy"], "KÈO TAY – MUA")
report["tay bán"] = summarize([r for r in man if r["side"] == "sell"], "KÈO TAY – BÁN")
print("\nmanual in-zone at message time:", Counter(r["sim"].get("in_zone") for r in man), "limit unfilled:",
      sum(1 for r in E if r["kind"] == "manual" and r.get("sim") and not r["sim"].get("filled")))
print("bot score vs TP1:", [(sc, round(np.mean([0 in r["sim"]["tp_hit"] for r in bots if r.get("score") and lo <= r["score"] < hi]), 2),
                             sum(1 for r in bots if r.get("score") and lo <= r["score"] < hi)) for sc, lo, hi in (("<60", 0, 60), ("60-69", 60, 70), ("≥70", 70, 101))])
# timing (Telegram / Vietnam time)
hours = Counter(int(r["time"][:2]) for r in man)
print("\nmanual calls by VN hour:", sorted(hours.items()))
print("manual by weekday:", Counter(pd.Timestamp(r["t_srv"], unit="s").day_name()[:3] for r in man))
# SL size relative to ATR M5 / H1
for lab, rs in (("bot", bots), ("tay", man)):
    sl_atr = []
    for r in rs:
        F = FR[r["sym"]]
        for tf in ("M5", "M15", "H1"):
            k = int(np.searchsorted(F[tf]["t"], r["t_srv"], side="right")) - 2
            r.setdefault("sl_atr", {})[tf] = r["sim"]["risk"] / F[tf]["atr"][k]
    print(lab, "SL / ATR trung vị:", {tf: round(float(np.median([r["sl_atr"][tf] for r in rs])), 2) for tf in ("M5", "M15", "H1")})
# multi-timeframe context: share of signals with each feature vs random bars of the same symbol and side mix
rng = np.random.default_rng(7)
for lab, rs in (("KÈO TAY", man), ("BOT", bots)):
    feats = [ctx(r["sym"], r["t_srv"], 1 if r["side"] == "buy" else -1) for r in rs]
    feats = [f for f in feats if f]
    base = []
    t5 = FR["XAUUSD"]["M5"]["t"]
    for _ in range(3000):
        r = rs[int(rng.integers(len(rs)))]
        ts = int(rng.choice(t5[(t5 > t5[0] + 70 * 86400)]))
        f = ctx(r["sym"], ts, 1 if r["side"] == "buy" else -1)
        if f:
            base.append(f)
    print(f"\n== Bối cảnh đa khung – {lab} (n={len(feats)}) | % tín hiệu có đặc điểm / % nến ngẫu nhiên | tỷ lệ")
    rows = []
    for key in feats[0]:
        a = np.mean([f[key] for f in feats])
        b = np.mean([f[key] for f in base])
        rows.append((key, a, b, a / b if b else np.nan))
    for key, a, b, ratio in sorted(rows, key=lambda x: -abs(np.log(x[3] if x[3] > 0 else 1e-3))):
        print(f"  {key:62s} {a*100:5.1f}% / {b*100:5.1f}%  x{ratio:4.2f}")
json.dump(report, open("report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
