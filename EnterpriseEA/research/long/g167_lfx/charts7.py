"""The 7 LFX chart setups (XAUUSD M30 OANDA, 04-17/11/2026): price-feed offset vs MT5, fill / outcome replay, and multi-timeframe
context at the time of the call and at the fill (structure, Fibonacci of the last impulse, S/R flip, ATR, RSI, confirmation candle)."""
import json

import numpy as np
import pandas as pd

S = [  # id, VN time, side, zone lo-hi (entry area), SL, TPs, price on chart at post time
    ("1a sell", "2026-11-04 09:46", "sell", 3965.16, 3978.40, 3978.40, [3935.41], 3935.565),
    ("1b buy", "2026-11-04 09:46", "buy", 3895.87, 3899.0, 3877.29, [3935.23], 3935.565),
    ("2 buy", "2026-11-05 12:41", "buy", 4078.0, 4099.0, 4060.0, [4142.0, 4184.0], 4121.445),
    ("3 buy", "2026-11-06 10:58", "buy", 4028.0, 4036.16, 4014.10, [4055.76, 4070.75, 4088.84], 4043.665),
    ("4 sell", "2026-11-10 10:00", "sell", 4121.85, 4127.0, 4146.25, [4100.60, 4074.43], 4111.115),
    ("6 sell", "2026-11-11 09:05", "sell", 4067.0, 4073.0, 4091.0, [4053.02, 4040.88, 4029.17], 4043.92),
    ("5 sell", "2026-11-13 09:02", "sell", 3924.0, 3930.0, 3948.96, [3915.06, 3903.83, 3890.13], 3908.875),
    ("7 sell", "2026-11-17 11:01", "sell", 3888.0, 3896.0, 3910.38, [3877.87, 3863.34, 3851.97], 3870.775),
]
OFF_VN_TO_SRV = -5          # November: server UTC+2, Vietnam UTC+7


def load(tf):
    d = pd.read_csv(f"XAUUSD-VIP_{tf}.csv")
    return d


TF = {tf: load(tf) for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1") if tf != "M30"}
m5 = TF["M5"]
m30 = m5.copy()
m30["g"] = m30["time"] // 1800
TF["M30"] = m30.groupby("g").agg(time=("time", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                close=("close", "last")).reset_index(drop=True)
SEC = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def atr(d, n=14):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    return pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def rsi(c, n=14):
    dd = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(dd, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-dd, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).to_numpy()


for tf, d in TF.items():
    c = d["close"].to_numpy()
    d["atr"], d["rsi"] = atr(d), rsi(c)
    d["e21"], d["e50"], d["e200"] = (pd.Series(c).ewm(span=n, adjust=False).mean().to_numpy() for n in (21, 50, 200))


def last_closed(tf, ts):
    d = TF[tf]
    k = int(np.searchsorted(d["time"].to_numpy(), ts - SEC[tf], side="right")) - 1
    return d.iloc[k]


def swings(tf, ts, k=3, look=200):
    """Confirmed pivot highs / lows (k bars each side) known at ts."""
    d = TF[tf]
    e = int(np.searchsorted(d["time"].to_numpy(), ts - SEC[tf], side="right"))
    d = d.iloc[max(0, e - look):e].reset_index(drop=True)
    h, l = d["high"].to_numpy(), d["low"].to_numpy()
    ph = [(int(d["time"][i]), h[i]) for i in range(k, len(d) - k) if h[i] == h[i - k:i + k + 1].max()]
    pl = [(int(d["time"][i]), l[i]) for i in range(k, len(d) - k) if l[i] == l[i - k:i + k + 1].min()]
    return ph, pl


def replay(side, lo, hi, sl, tps, ts):
    d = TF["M1"]
    t, o, h, l = (d[k].to_numpy() for k in ("time", "open", "high", "low"))
    a = int(np.searchsorted(t, ts))
    dirn = 1 if side == "buy" else -1
    fill, fill_px = None, None
    for j in range(a, min(len(t), a + 72 * 60)):
        if dirn == -1 and h[j] >= lo:
            fill, fill_px = j, max(lo, o[j]) if o[j] < hi + 50 else o[j]
            break
        if dirn == 1 and l[j] <= hi:
            fill, fill_px = j, min(hi, o[j])
            break
    if fill is None:
        return {"khớp": False}
    res = {"khớp": True, "giờ khớp (VN)": str(pd.Timestamp(t[fill], unit="s") - pd.Timedelta(hours=OFF_VN_TO_SRV)), "giá khớp": round(float(fill_px), 2),
           "chờ khớp (giờ)": round((t[fill] - ts) / 3600, 1)}
    risk = dirn * (fill_px - sl)
    res["R TP"] = [round(dirn * (tp - fill_px) / risk, 2) for tp in tps]
    hit, sl_j = {}, None
    for j in range(fill, len(t)):
        adv, fav = (l[j], h[j]) if dirn == 1 else (h[j], l[j])
        new = [i for i, tp in enumerate(tps) if i not in hit and dirn * (fav - tp) >= 0]
        if dirn * (adv - sl) <= 0:
            if j == fill and not new:
                sl_j = j
                break
            sl_j = j
            break
        for i in new:
            hit[i] = j
        if len(hit) == len(tps):
            break
    res["TP chạm"] = [i + 1 for i in sorted(hit)]
    res["SL chạm"] = sl_j is not None and len(hit) < len(tps)
    res["giờ tới kết quả"] = round(((t[sl_j] if res["SL chạm"] else t[max(hit.values())] if hit else t[-1]) - t[fill]) / 3600, 1)
    parts = [res["R TP"][i] if i in hit else (-1.0 if res["SL chạm"] else 0.0) for i in range(len(tps))]
    parts_be = [res["R TP"][i] if i in hit else (0.0 if hit else (-1.0 if res["SL chạm"] else 0.0)) for i in range(len(tps))]
    res["R chia đều"], res["R chia đều + BE sau TP1"] = round(float(np.mean(parts)), 2), round(float(np.mean(parts_be)), 2)
    res["còn mở"] = (not res["SL chạm"]) and len(hit) < len(tps)
    # confirmation at the fill: M5 / M15 candle that closes back out of the zone in the trade direction within 1 h
    conf = {}
    for tf in ("M5", "M15"):
        dd = TF[tf]
        tt = dd["time"].to_numpy()
        b = int(np.searchsorted(tt, t[fill] - SEC[tf] + 1))
        z = None
        for i in range(b, min(len(dd), b + 3600 // SEC[tf] + 1)):
            r = dd.iloc[i]
            rg = r["high"] - r["low"]
            wick = (min(r["open"], r["close"]) - r["low"]) if dirn == 1 else (r["high"] - max(r["open"], r["close"]))
            if rg > 0 and dirn * (r["close"] - r["open"]) > 0 and wick >= 0.4 * rg:
                z = round((tt[i] + SEC[tf] - t[fill]) / 60)
                break
        conf[tf] = z
    res["nến xác nhận đầu tiên sau khớp (phút, None = không có trong 1 h)"] = conf
    return res


out = []
for sid, vn, side, lo, hi, sl, tps, chart_px in S:
    ts = int((pd.Timestamp(vn) + pd.Timedelta(hours=OFF_VN_TO_SRV)).timestamp())
    m1 = TF["M1"]
    k = int(np.searchsorted(m1["time"].to_numpy(), ts, side="right")) - 1
    mt5_px = float(m1["close"].iloc[k])
    offset = round(chart_px - mt5_px, 2)                         # OANDA minus broker
    # shift the levels into broker prices
    lo2, hi2, sl2, tps2 = lo - offset, hi - offset, sl - offset, [x - offset for x in tps]
    d = 1 if side == "buy" else -1
    ctx = {}
    for tf in ("M15", "M30", "H1", "H4", "D1"):
        r = last_closed(tf, ts)
        ctx[tf] = {"giá vs EMA50": "trên" if r["close"] > r["e50"] else "dưới", "EMA21 vs EMA50": "trên" if r["e21"] > r["e50"] else "dưới",
                   "RSI": round(float(r["rsi"]), 1), "ATR": round(float(r["atr"]), 1)}
    # last H1 impulse: latest swing pair, and where the zone sits in it
    ph, pl = swings("H1", ts, k=3)
    hiP, loP = ph[-1], pl[-1]
    if hiP[0] > loP[0]:
        leg = ("lên", loP[1], hiP[1])
    else:
        leg = ("xuống", hiP[1], loP[1])
    mid = (lo2 + hi2) / 2
    a_, b_ = leg[1], leg[2]
    fib = round((b_ - mid) / (b_ - a_), 3) if b_ != a_ else None                # retracement of the last H1 leg
    # S/R flip: was the zone a swing high / low in the past 10 days on H1 that price has since crossed?
    ph10, pl10 = swings("H1", ts, k=3, look=240)
    near = [p for p in ph10 + pl10 if lo2 - 3 <= p[1] <= hi2 + 3]
    a1 = float(last_closed("H1", ts)["atr"])
    sim = replay(side, lo2, hi2, sl2, tps2, ts)
    row = {"kèo": sid, "giờ gửi (VN)": vn, "chiều": side, "lệch giá OANDA − MT5": offset,
           "vùng / SL / TP (giá MT5)": [round(lo2, 2), round(hi2, 2), round(sl2, 2), [round(x, 2) for x in tps2]],
           "khoảng cách từ giá tới vùng (ATR H1)": round(abs(mid - mt5_px) / a1, 2),
           "SL tính từ giữa vùng (USD / ATR H1 / ATR M30)": [round(abs(mid - sl2), 1), round(abs(mid - sl2) / a1, 2),
                                                            round(abs(mid - sl2) / float(last_closed("M30", ts)["atr"]), 2)],
           "nhịp H1 gần nhất": f"{leg[0]} {leg[1]:.1f} → {leg[2]:.1f}", "vùng ở Fibo hồi của nhịp đó": fib,
           "vùng trùng đỉnh/đáy swing H1 cũ (10 ngày)": [round(p[1], 1) for p in near][:4],
           "đa khung lúc gửi": ctx, "kết quả": sim}
    out.append(row)
json.dump(out, open("charts7.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
for r in out:
    print("\n==", r["kèo"], r["giờ gửi (VN)"], "| lệch", r["lệch giá OANDA − MT5"], "| tới vùng", r["khoảng cách từ giá tới vùng (ATR H1)"], "ATR H1",
          "| SL", r["SL tính từ giữa vùng (USD / ATR H1 / ATR M30)"], "| nhịp", r["nhịp H1 gần nhất"], "fib", r["vùng ở Fibo hồi của nhịp đó"],
          "| swing cũ", r["vùng trùng đỉnh/đáy swing H1 cũ (10 ngày)"])
    print("   ctx", {tf: (v["giá vs EMA50"], v["EMA21 vs EMA50"], v["RSI"]) for tf, v in r["đa khung lúc gửi"].items()})
    print("   kq", r["kết quả"])
