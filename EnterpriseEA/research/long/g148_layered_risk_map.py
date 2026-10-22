"""G148: layered risk map (candle -> indicators -> context -> volume/VWAP/volatility -> price action/liquidity -> time/news ->
distribution/FOMO) on an every-bar M30 trade universe (SL 1.5 ATR, TP 3 ATR, 48 bars). Stacked, stability-first selection on
05/2018-2021; validate 2022-2023, test 2024-06/2026. Plan: docs/superpowers/plans/2026-10-22-g148-layered-risk-map.md.

Usage: g148_layered_risk_map.py <data dir> <out.json>
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402
import g147_risk_map as rm  # noqa: E402
from g143_session_momentum import daily_atr  # noqa: E402

CAL = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
           r"\MQL5\Files\EnterpriseEA\research\calendar")
START = rm.START
PER = rm.PER
SEL_YEARS = rm.SEL_YEARS
MIN_SHARE, MIN_DELTA, PVAL, RUNS = 0.05, 0.03, 0.005, 200
H = 3600

LAYERS = {
    "1 Nến": ["N1 thân/ATR", "N2 râu từ chối", "N3 vị trí close", "N4 inside bar", "N5 nhấn chìm", "N6 chuỗi màu", "N7 biên độ nến"],
    "2 Indicator": ["I1 EMA20 vs EMA50", "I2 giá vs EMA20", "I3 giá vs EMA200", "I4 EMA21/55/100", "I5 MACD hist", "I6 MACD hist đổi",
                    "I7 RSI", "I8 Stochastic", "I9 ADX", "I10 ADX đổi", "I11 DI", "I12 Bollinger %b", "I13 kéo căng EMA20"],
    "3 Bối cảnh": ["C1 EMA200 H4", "C2 D1 SMA50/200", "C3 đi 20 ngày", "C4 cấu trúc M30", "C5 BOS", "C6 so biên hôm qua",
                   "C7 so biên tuần trước", "C8 dốc EMA200"],
    "4 Volume/VWAP/biến động": ["V1 tick volume", "V2 VWAP ngày", "V3 ATR/TB100", "V4 độ rộng BB", "V5 vol ít giá nhanh",
                                "V6 tốc độ/ATR D1", "V7 volume 6 vs 20"],
    "5 Price action/thanh khoản": ["P1 quét hôm qua", "P2 quét phiên Á", "P3 giá tròn phía trước", "P4 điểm tiếp diễn",
                                   "P5 chốt lời/chững", "P6 thanh khoản phía trước", "P7 retest mức vừa phá"],
    "6 Thời gian/tin": ["T1 giờ", "T2 thứ", "T3 trong tháng", "T4 tin USD HIGH", "T5 ngày NFP", "T6 ngày Fed", "T7 T2 sau T6 mạnh"],
    "7 Phân phối/FOMO": ["M1 cách EMA200 D1", "M2 RSI D1", "M3 chuỗi ngày", "M4 gần đỉnh/đáy 52 tuần", "M5 phân phối sau FOMO"],
}
FACTORS = [f for fs in LAYERS.values() for f in fs]


def calendar():
    high, nfp, fed = [], set(), set()
    for f in sorted(CAL.glob("calendar_*.csv")):
        with f.open(encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["currency"] != "USD" or r["importance"] != "HIGH":
                    continue
                t = int(r["time_server"])
                high.append(t)
                n = r["name"].lower()
                if "nonfarm payrolls" in n:
                    nfp.add(t // 86400)
                if "fed interest rate decision" in n:
                    fed.add(t // 86400)
    return np.array(sorted(set(high)), dtype=np.int64), nfp, fed


def ema(x, n):
    return g.ema(np.asarray(x, dtype=float), n)


def rsi(x, n=14):
    ch = np.diff(x, prepend=x[0])
    up, dn = g.rma(np.maximum(ch, 0.0), n), g.rma(np.maximum(-ch, 0.0), n)
    return 100 - 100 / (1 + up / np.maximum(dn, 1e-12))


def daily_context(D):
    """Per server day: OHLC; per bar: values of CLOSED days only."""
    t, o, h, l, c = D["t"], D["o"], D["h"], D["l"], D["c"]
    day = t // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    starts = np.r_[0, ends[:-1] + 1]
    days = day[ends]
    DO = o[starts]; DH = np.array([h[a:z + 1].max() for a, z in zip(starts, ends)])
    DL = np.array([l[a:z + 1].min() for a, z in zip(starts, ends)]); DC = c[ends]
    atrd = daily_atr(D)
    A = np.array([atrd.get(int(x), np.nan) for x in days])
    E200, R14 = ema(DC, 200), rsi(DC, 14)
    q = np.searchsorted(days, day, side="left") - 1           # last closed day index per bar
    ok = q >= 0
    qq = np.maximum(q, 0)
    X = {}
    X["dA"] = np.array([atrd.get(int(x), np.nan) for x in day])       # ATR20 D1 of the closed days before today
    X["dE200"], X["dRSI"], X["dC"] = E200[qq], R14[qq], DC[qq]
    ret20 = np.r_[np.full(20, np.nan), DC[20:] - DC[:-20]]
    X["d20"] = ret20[qq]
    up = np.sign(DC - DO)
    run = np.zeros(len(DC))
    for k in range(len(DC)):
        run[k] = (run[k - 1] + up[k] if k and np.sign(run[k - 1]) == up[k] else up[k])
    X["drun"] = run[qq]
    hi52 = np.array([DH[max(0, k - 259):k + 1].max() for k in range(len(DH))])
    lo52 = np.array([DL[max(0, k - 259):k + 1].min() for k in range(len(DL))])
    X["hi52"], X["lo52"] = hi52[qq], lo52[qq]
    rng = DH - DL
    import pandas as pd
    r5 = pd.Series(rng).rolling(5).mean().to_numpy()
    r20 = pd.Series(rng).rolling(20).mean().to_numpy()
    X["dist5"] = np.where(ok, (r5 / r20)[qq], np.nan)                    # last 5 closed days vs last 20
    # previous week (Monday-based server weeks)
    wk = (days + 3) // 7
    wkH, wkL = {}, {}
    for k, w in enumerate(wk):
        wkH[w] = max(wkH.get(w, -1e18), DH[k]); wkL[w] = min(wkL.get(w, 1e18), DL[k])
    bw = (day + 3) // 7
    X["pwH"] = np.array([wkH.get(w - 1, np.nan) for w in bw]); X["pwL"] = np.array([wkL.get(w - 1, np.nan) for w in bw])
    # Friday range for Monday
    fr = {int(days[k]): (DH[k] - DL[k]) / A[k] if A[k] == A[k] and A[k] > 0 else np.nan for k in range(len(days))}
    X["monday_after_big_friday"] = np.array([((int(x) + 3) % 7 == 0) and (fr.get(int(x) - 3, 0) or 0) >= 1.5 for x in day])
    # first / last 2 trading days of the month
    mon = days.astype("datetime64[D]").astype("datetime64[M]").astype(int)
    pos_in_m, from_end = np.zeros(len(days), int), np.zeros(len(days), int)
    for m_ in np.unique(mon):
        idx = np.nonzero(mon == m_)[0]
        pos_in_m[idx] = np.arange(len(idx)); from_end[idx] = np.arange(len(idx))[::-1]
    pm = dict(zip(days.tolist(), pos_in_m.tolist())); fe = dict(zip(days.tolist(), from_end.tolist()))
    X["mpos"] = np.array([pm.get(int(x), 5) for x in day]); X["mend"] = np.array([fe.get(int(x), 5) for x in day])
    return X


def bar_context(D):
    c, o, h, l, v, t, a = D["c"], D["o"], D["h"], D["l"], D["v"], D["t"], D["atr"]
    n = len(c)
    X = {}
    lo14 = np.array([l[max(0, i - 13):i + 1].min() for i in range(n)])
    hi14 = np.array([h[max(0, i - 13):i + 1].max() for i in range(n)])
    k = 100 * (c - lo14) / np.maximum(hi14 - lo14, 1e-9)
    X["stoch"] = np.convolve(k, np.ones(3) / 3, "full")[:n]
    sd = D["bw"] / 4
    X["pctb"] = (c - (D["sma20"] - 2 * sd)) / np.maximum(4 * sd, 1e-9)
    # day VWAP (typical price weighted by tick volume, from the server day start, bars <= i)
    day = t // 86400
    tp = (h + l + c) / 3
    vw = np.zeros(n); cum_pv = cum_v = 0.0; last = -1
    asia_h, asia_l = np.full(n, np.nan), np.full(n, np.nan); ah = al = None
    for i in range(n):
        if day[i] != last:
            cum_pv = cum_v = 0.0; last = day[i]; ah = al = None
        w = max(v[i], 1.0)
        cum_pv += tp[i] * w; cum_v += w
        vw[i] = cum_pv / cum_v
        hr = (t[i] % 86400) // H
        if hr < 9:
            ah = h[i] if ah is None else max(ah, h[i]); al = l[i] if al is None else min(al, l[i])
        if hr >= 9 and ah is not None:
            asia_h[i], asia_l[i] = ah, al
    X["vwap"], X["asia_h"], X["asia_l"] = vw, asia_h, asia_l
    # today's extremes so far (for sweeps / retests)
    th, tl = np.zeros(n), np.zeros(n)
    for i in range(n):
        if i == 0 or day[i] != day[i - 1]:
            th[i], tl[i] = h[i], l[i]
        else:
            th[i], tl[i] = max(th[i - 1], h[i]), min(tl[i - 1], l[i])
    X["today_h"], X["today_l"] = th, tl
    vs = np.convolve(v, np.ones(6) / 6, "full")[:n]
    v20 = np.r_[np.full(26, np.nan), np.array([v[i - 26:i - 6].mean() for i in range(26, n)])]
    X["v6v20"] = vs / v20
    return X


def states(D, B, C, i, d, hi_news, nfp, fed):
    c, o, h, l, a, E, adx, v = D["c"], D["o"], D["h"], D["l"], D["atr"], D["E"], D["adx"], D["v"]
    A = a[i]
    s = {}
    body = c[i] - o[i]; rg = max(h[i] - l[i], 1e-9)
    s["N1 thân/ATR"] = ("lớn cùng" if np.sign(body) == d else "lớn ngược") if abs(body) >= 0.6 * A else ("doji" if abs(body) < 0.15 * A else "vừa")
    low_w, up_w = min(o[i], c[i]) - l[i], h[i] - max(o[i], c[i])
    rej_for, rej_against = (low_w, up_w) if d == 1 else (up_w, low_w)
    s["N2 râu từ chối"] = "đẩy về chiều lệnh" if rej_for >= 0.5 * rg else ("đẩy ngược" if rej_against >= 0.5 * rg else "không")
    cp = (c[i] - l[i]) / rg; cp = cp if d == 1 else 1 - cp
    s["N3 vị trí close"] = "sát cực theo chiều" if cp >= 0.8 else ("sát cực ngược" if cp <= 0.2 else "giữa")
    s["N4 inside bar"] = "có" if h[i] < h[i - 1] and l[i] > l[i - 1] else "không"
    eng = (min(o[i], c[i]) <= min(o[i - 1], c[i - 1]) and max(o[i], c[i]) >= max(o[i - 1], c[i - 1])
           and np.sign(c[i] - o[i]) == -np.sign(c[i - 1] - o[i - 1]) != 0)
    s["N5 nhấn chìm"] = ("cùng" if np.sign(body) == d else "ngược") if eng else "không"
    col = np.sign(c[i - 2:i + 1] - o[i - 2:i + 1])
    s["N6 chuỗi màu"] = "≥3 cùng" if np.all(col == d) else ("≥3 ngược" if np.all(col == -d) else "khác")
    s["N7 biên độ nến"] = "bùng" if rg > 1.5 * A else ("lặng" if rg < 0.5 * A else "thường")
    side = lambda x: "cùng" if d * x > 0 else "ngược"
    s["I1 EMA20 vs EMA50"] = side(D["e20"][i] - D["e50"][i])
    s["I2 giá vs EMA20"] = side(c[i] - D["e20"][i])
    s["I3 giá vs EMA200"] = side(c[i] - E[200][i])
    od = 1 if E[21][i] > E[55][i] > E[100][i] else (-1 if E[21][i] < E[55][i] < E[100][i] else 0)
    s["I4 EMA21/55/100"] = "cùng" if od == d else ("ngược" if od == -d else "lẫn")
    s["I5 MACD hist"] = side(D["hist"][i])
    s["I6 MACD hist đổi"] = "mạnh lên" if d * (D["hist"][i] - D["hist"][i - 1]) > 0 else "yếu đi"
    r = D["rsi"][i] if d == 1 else 100 - D["rsi"][i]
    s["I7 RSI"] = ">70" if r > 70 else ("55–70" if r > 55 else ("45–55" if r >= 45 else ("30–45" if r >= 30 else "<30")))
    st = B["stoch"][i] if d == 1 else 100 - B["stoch"][i]
    s["I8 Stochastic"] = ">80" if st > 80 else ("<20" if st < 20 else "giữa")
    s["I9 ADX"] = "<20" if adx[i] < 20 else ("20–30" if adx[i] <= 30 else ">30")
    s["I10 ADX đổi"] = "tăng" if adx[i] > adx[i - 3] else "giảm"
    s["I11 DI"] = side(D["pdi"][i] - D["mdi"][i])
    pb = B["pctb"][i] if d == 1 else 1 - B["pctb"][i]
    s["I12 Bollinger %b"] = "ngoài dải cùng" if pb > 1 else ("ngoài dải ngược" if pb < 0 else "trong")
    st_ = d * (c[i] - D["e20"][i]) / A
    s["I13 kéo căng EMA20"] = ">2ATR" if st_ > 2 else ("<-2ATR" if st_ < -2 else "trong")
    s["C1 EMA200 H4"] = "cùng" if D["h4_side"][i] == d else "ngược"
    s["C2 D1 SMA50/200"] = "cùng" if D["d1"][i] == d else "ngược"
    dA = C["dA"][i]
    m20 = d * C["d20"][i] / dA if dA == dA and dA > 0 else 0
    s["C3 đi 20 ngày"] = ">+1,5" if m20 > 1.5 else ("<-1,5" if m20 < -1.5 else "giữa")
    PH, PL = rm_conf(D["ph"], i, 100), rm_conf(D["pl"], i, 100)
    if len(PH) >= 2 and len(PL) >= 2:
        upst = h[PH[-1]] > h[PH[-2]] and l[PL[-1]] > l[PL[-2]]
        dnst = h[PH[-1]] < h[PH[-2]] and l[PL[-1]] < l[PL[-2]]
        stc = 1 if upst else (-1 if dnst else 0)
        s["C4 cấu trúc M30"] = "cùng" if stc == d else ("ngược" if stc == -d else "lẫn")
        lvl = h[PH[-1]] if d == 1 else l[PL[-1]]
        s["C5 BOS"] = "có" if any(d * (c[j] - lvl) > 0 and d * (c[j - 1] - lvl) <= 0 for j in range(i - 2, i + 1)) else "không"
    else:
        s["C4 cấu trúc M30"], s["C5 BOS"] = "lẫn", "không"
    pdh, pdl = D["pdh"][i], D["pdl"][i]
    above, below = c[i] > pdh, c[i] < pdl
    s["C6 so biên hôm qua"] = ("vượt cùng" if (above and d == 1) or (below and d == -1) else
                              ("vượt ngược" if above or below else "trong"))
    pwh, pwl = C["pwH"][i], C["pwL"][i]
    above, below = c[i] > pwh, c[i] < pwl
    s["C7 so biên tuần trước"] = ("vượt cùng" if (above and d == 1) or (below and d == -1) else
                                 ("vượt ngược" if above or below else "trong"))
    slp = (E[200][i] - E[200][i - 48]) / A
    s["C8 dốc EMA200"] = "phẳng" if abs(slp) < 0.5 else ("cùng" if np.sign(slp) == d else "ngược")
    vr = v[i] / D["vavg"][i] if D["vavg"][i] > 0 else 1.0
    s["V1 tick volume"] = "cao" if vr >= 1.5 else ("thấp" if vr <= 0.7 else "thường")
    vd = d * (c[i] - B["vwap"][i]) / A
    s["V2 VWAP ngày"] = ">1ATR" if vd > 1 else ("<-1ATR" if vd < -1 else "trong")
    ar = D["atrr"][i]
    s["V3 ATR/TB100"] = "cao" if ar > 1.25 else ("thấp" if ar < 0.8 else "thường")
    rk = D["bwrank"][i]
    s["V4 độ rộng BB"] = "hẹp" if rk <= 0.2 else ("rộng" if rk >= 0.8 else "thường")
    s["V5 vol ít giá nhanh"] = "có" if rg >= 1.2 * A and vr <= 0.8 else "không"
    sp4 = d * (c[i] - c[i - 4]) / dA if dA == dA and dA > 0 else 0
    s["V6 tốc độ/ATR D1"] = ">0,5" if sp4 > 0.5 else ("<-0,5" if sp4 < -0.5 else "giữa")
    v6 = B["v6v20"][i]
    s["V7 volume 6 vs 20"] = "tăng" if v6 > 1.2 else ("giảm" if v6 < 0.8 else "thường")
    th, tl = B["today_h"][i], B["today_l"][i]
    if d == 1:
        p1 = "cùng" if tl < pdl and c[i] > pdl else ("ngược" if th > pdh and c[i] < pdh else "không")
    else:
        p1 = "cùng" if th > pdh and c[i] < pdh else ("ngược" if tl < pdl and c[i] > pdl else "không")
    s["P1 quét hôm qua"] = p1
    ah, al = B["asia_h"][i], B["asia_l"][i]
    if ah == ah:
        if d == 1:
            p2 = "cùng" if tl < al and c[i] > al else ("ngược" if th > ah and c[i] < ah else "không")
        else:
            p2 = "cùng" if th > ah and c[i] < ah else ("ngược" if tl < al and c[i] > al else "không")
    else:
        p2 = "không"
    s["P2 quét phiên Á"] = p2
    nxt = (np.floor(c[i] / 10) + 1) * 10 if d == 1 else np.ceil(c[i] / 10) * 10 - 10
    s["P3 giá tròn phía trước"] = "có" if abs(nxt - c[i]) <= 0.3 * A else "không"
    mv20 = d * (c[i] - c[i - 20]) / A
    mv4 = d * (c[i] - c[i - 4]) / A
    s["P4 điểm tiếp diễn"] = "có" if mv20 > 2 and mv4 <= -0.5 else "không"
    s["P5 chốt lời/chững"] = "có" if mv20 > 3 and (h[i - 3:i + 1].max() - l[i - 3:i + 1].min()) < A else "không"
    piv = rm_conf(D["ph"] if d == 1 else D["pl"], i, 100)
    lv = (h if d == 1 else l)[piv]
    ahead = [x for x in lv if 0 < d * (x - c[i]) <= 1.5 * A]
    eq = any(abs(p - q) <= 0.2 * A for k_, p in enumerate(ahead) for q in ahead[k_ + 1:])
    s["P6 thanh khoản phía trước"] = "có" if eq else "không"
    if d == 1:
        p7 = th > pdh and 0 <= c[i] - pdh <= 0.3 * A
    else:
        p7 = tl < pdl and 0 <= pdl - c[i] <= 0.3 * A
    s["P7 retest mức vừa phá"] = "có" if p7 else "không"
    hr = D["hour"][i]
    s["T1 giờ"] = "Á sớm" if 1 <= hr <= 5 else ("Á muộn" if hr <= 9 else ("London" if hr <= 14 else ("New York" if hr <= 19 else "tối")))
    s["T2 thứ"] = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")[int(D["wd"][i])]
    s["T3 trong tháng"] = "2 ngày đầu" if C["mpos"][i] <= 1 else ("2 ngày cuối" if C["mend"][i] <= 1 else "giữa")
    tclose = int(D["t"][i]) + 1800
    k_ = np.searchsorted(hi_news, tclose)
    nxt_t = hi_news[k_] if k_ < len(hi_news) else 10 ** 12
    prv_t = hi_news[k_ - 1] if k_ > 0 else -10 ** 12
    s["T4 tin USD HIGH"] = "2 giờ tới" if nxt_t - tclose <= 2 * H else ("2 giờ qua" if tclose - prv_t <= 2 * H else "không")
    dk = int(D["t"][i]) // 86400
    s["T5 ngày NFP"] = "có" if dk in nfp else "không"
    s["T6 ngày Fed"] = "có" if dk in fed else "không"
    s["T7 T2 sau T6 mạnh"] = "có" if C["monday_after_big_friday"][i] else "không"
    de = d * (c[i] - C["dE200"][i]) / dA if dA == dA and dA > 0 else 0
    s["M1 cách EMA200 D1"] = ">4 FOMO" if de > 4 else ("1–4" if de > 1 else ("0–1" if de >= 0 else "ngược"))
    rd = C["dRSI"][i] if d == 1 else 100 - C["dRSI"][i]
    s["M2 RSI D1"] = ">70" if rd > 70 else ("<30" if rd < 30 else "giữa")
    run = C["drun"][i]
    s["M3 chuỗi ngày"] = "≥4 cùng" if d * run >= 4 else ("≥4 ngược" if d * run <= -4 else "khác")
    near = (C["hi52"][i] - c[i] <= 2 * dA) if d == 1 else (c[i] - C["lo52"][i] <= 2 * dA)
    s["M4 gần đỉnh/đáy 52 tuần"] = "có" if near else "không"
    s["M5 phân phối sau FOMO"] = "có" if m20 * 1.0 > 5 / 1.0 and C["dist5"][i] < 0.7 else "không"
    return s


def rm_conf(piv, i, back):
    lo = np.searchsorted(piv, i - back, side="left")
    hi = np.searchsorted(piv, i - 4, side="right")
    return piv[lo:hi]


def build(D):
    hi_news, nfp, fed = calendar()
    B, C = bar_context(D), daily_context(D)
    codes = {f: {} for f in FACTORS}
    rows, S = [], []
    n = len(D["c"])
    for i in range(300, n - 2):
        srv = int(D["t"][i])
        if srv < START or D["hour"][i] in (23, 0):
            continue
        if not (np.isfinite(D["atrr"][i]) and np.isfinite(D["pdh"][i]) and np.isfinite(D["bwrank"][i]) and np.isfinite(C["pwH"][i])):
            continue
        p = rm.period(srv)
        if p is None:
            continue
        e, A = i + 1, D["atr"][i]
        for d in (1, -1):
            entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
            t = gp.run_trade(D, e, d, entry, entry - d * 1.5 * A, entry + d * 3.0 * A, 48)
            if t is None:
                continue
            st = states(D, B, C, i, d, hi_news, nfp, fed)
            S.append([codes[f].setdefault(st[f], len(codes[f])) for f in FACTORS])
            rows.append((i, t["x"], d, t["rh"], t["rh15"], ("chọn", "validate", "test", "sau").index(p),
                         int(np.datetime64(srv, "s").astype("datetime64[Y]").astype(int) + 1970), int(D["hour"][i]),
                         int(D["mon"][i])))
    R = np.array(rows, dtype=float)
    names = {f: {v: k for k, v in codes[f].items()} for f in FACTORS}
    return R, np.array(S, dtype=np.int16), names


def stat(x):
    x = np.asarray(x, dtype=float)
    return {"n": int(len(x)), "mean": round(float(x.mean()), 3), "total": round(float(x.sum()), 1)} if len(x) else {"n": 0}


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    R, S, names = build(D)
    i_, x_, d_, r_, r15_, p_, y_, h_, m_ = (R[:, k] for k in range(9))
    print("universe", len(R), flush=True)
    res = {"vũ trụ": {pn: {"mua": stat(r_[(p_ == k) & (d_ == 1)]), "bán": stat(r_[(p_ == k) & (d_ == -1)])}
                      for k, pn in enumerate(("chọn", "validate", "test", "sau"))}}
    sel = p_ == 0
    U = sel.copy()
    avoid, favour, layers_out, allrecs = [], [], {}, []
    for lname, fs in LAYERS.items():
        found = []
        for f in fs:
            fi = FACTORS.index(f)
            for code, sname in names[f].items():
                m = S[:, fi] == code
                share = (m & U).sum() / max(U.sum(), 1)
                deltas = []
                for y in SEL_YEARS:
                    for d in (1, -1):
                        cell = U & (y_ == y) & (d_ == d)
                        a, b = r_[cell & m], r_[cell & ~m]
                        deltas.append(a.mean() - b.mean() if len(a) and len(b) else np.nan)
                deltas = np.array(deltas)
                fin = np.isfinite(deltas)
                mean = float(np.nanmean(deltas)) if fin.any() else 0.0
                kind = None
                if share >= MIN_SHARE and fin.sum() >= 7 and abs(mean) >= MIN_DELTA:
                    if np.all(deltas[fin] < 0):
                        kind = "TRÁNH"
                    elif np.all(deltas[fin] > 0):
                        kind = "ƯU TIÊN"
                rec = dict(factor=f, state=sname, share=round(float(share), 3), delta=round(mean, 3),
                           cells_neg=int((deltas[fin] < 0).sum()), cells=int(fin.sum()), kind=kind)
                rec["ô (năm×chiều)"] = [None if not np.isfinite(x) else round(float(x), 3) for x in deltas]
                allrecs.append(dict(rec, layer=lname))
                if kind:
                    found.append(rec)
                    (avoid if kind == "TRÁNH" else favour).append((fi, code, f, sname))
        for fi, code, f, sname in [x for x in avoid if x[2] in fs]:
            U &= S[:, fi] != code
        # report only (no decision): unfiltered-by-score universe after this layer, validate / test
        keep = np.ones(len(R), bool)
        for fi, code, _, _ in avoid:
            keep &= S[:, fi] != code
        layers_out[lname] = {"chọn được": found, "vũ trụ còn lại (kỳ chọn)": int(U.sum()),
                             "sau tầng, validate": stat(r_[keep & (p_ == 1)]), "sau tầng, test": stat(r_[keep & (p_ == 2)])}
        print(lname, [(x["kind"], x["factor"], x["state"], x["delta"]) for x in found], flush=True)
    res["tầng"] = layers_out
    res["mọi trạng thái (kỳ chọn)"] = allrecs
    noavoid = np.ones(len(R), bool)
    for fi, code, _, _ in avoid:
        noavoid &= S[:, fi] != code
    score = np.zeros(len(R), int)
    for fi, code, _, _ in favour:
        score += S[:, fi] == code

    def system(mask):
        out, busy = [], {1: -1, -1: -1}
        for k in np.nonzero(mask)[0][np.lexsort((d_[mask], i_[mask]))]:
            d = int(d_[k])
            if i_[k] > busy[d]:
                out.append(k); busy[d] = x_[k]
        return np.array(out, dtype=int)

    pick = {}
    for T in range(5):
        ks = system(noavoid & (score >= T) & sel)
        pick[T] = (float(r_[ks].mean()) if len(ks) >= 300 else -9.0, len(ks))
    T = max(pick, key=lambda z: pick[z][0])
    res["chọn T"] = {str(k): [round(v[0], 3), v[1]] for k, v in pick.items()}
    res["T"] = T
    ks = system(noavoid & (score >= T))
    vt = ks[(p_[ks] == 1) | (p_[ks] == 2)]
    res["hệ thống theo kỳ"] = {pn: {"tất cả": stat(r_[ks[p_[ks] == k]]), "mua": stat(r_[ks[(p_[ks] == k) & (d_[ks] == 1)]]),
                                    "bán": stat(r_[ks[(p_[ks] == k) & (d_[ks] == -1)]])}
                               for k, pn in enumerate(("chọn", "validate", "test", "sau"))}
    res["theo năm"] = {str(y): stat(r_[ks[y_[ks] == y]]) for y in range(2018, 2027)}
    down = np.array([bool(D["down_month"].get(int(m))) for m in m_])
    res["validate+test"] = {"mua": stat(r_[vt[d_[vt] == 1]]), "bán": stat(r_[vt[d_[vt] == -1]]),
                            "tháng không tăng": stat(r_[vt[down[vt]]]), "phí×1,5": stat(r15_[vt]),
                            "bỏ 5 lệnh lớn nhất": stat(np.sort(r_[vt])[:-5])}
    mons = sorted(set(m_[(p_ == 1) | (p_ == 2)].astype(int)))
    ms = defaultdict(float)
    for k in vt:
        ms[int(m_[k])] += r_[k]
    seq = [ms[m] for m in mons]
    res["cửa sổ 6 tháng tệ nhất (R)"] = round(float(min(sum(seq[j:j + 6]) for j in range(len(seq) - 5))), 1)
    # confirmation of each chosen state in the final universe, validate / test x buy / sell
    conf = []
    for fi, code, f, sname in avoid + favour:
        cells = {}
        others = np.ones(len(R), bool)
        for fj, cj, _, _ in avoid:
            if (fj, cj) != (fi, code):
                others &= S[:, fj] != cj
        for k, pn in ((1, "validate"), (2, "test")):
            for d in (1, -1):
                cell = others & (p_ == k) & (d_ == d)
                a, b = r_[cell & (S[:, fi] == code)], r_[cell & (S[:, fi] != code)]
                cells[f"{pn} {'mua' if d == 1 else 'bán'}"] = round(float(a.mean() - b.mean()), 3) if len(a) and len(b) else None
        kind = "TRÁNH" if (fi, code, f, sname) in avoid else "ƯU TIÊN"
        sgn = -1 if kind == "TRÁNH" else 1
        vals = [v for v in cells.values() if v is not None]
        conf.append(dict(kind=kind, factor=f, state=sname, cells=cells, confirmed=len(vals) == 4 and all(sgn * v > 0 for v in vals)))
    res["xác nhận trạng thái"] = conf
    pool = defaultdict(list)
    uv = np.nonzero((p_ == 1) | (p_ == 2))[0]
    for k in uv:
        pool[(int(p_[k]), int(d_[k]), int(h_[k]))].append(r_[k])
    actual = float(r_[vt].mean()) if len(vt) else -9
    rng = random.Random(148)
    hits = sum(np.mean([rng.choice(pool[(int(p_[k]), int(d_[k]), int(h_[k]))]) for k in vt]) >= actual for _ in range(RUNS)) if len(vt) else RUNS
    res["p ngẫu nhiên"] = (hits + 1) / (RUNS + 1)
    h_s = res["hệ thống theo kỳ"]
    ok = (all(h_s[p]["tất cả"]["n"] >= 100 and h_s[p]["tất cả"]["mean"] > 0 for p in ("validate", "test"))
          and res["validate+test"]["mua"].get("mean", -1) > 0 and res["validate+test"]["bán"].get("mean", -1) > 0
          and res["validate+test"]["tháng không tăng"]["n"] >= 50 and res["validate+test"]["tháng không tăng"]["mean"] > 0
          and res["p ngẫu nhiên"] <= PVAL and res["validate+test"]["phí×1,5"]["mean"] > 0
          and res["cửa sổ 6 tháng tệ nhất (R)"] >= -15 and res["validate+test"]["bỏ 5 lệnh lớn nhất"]["mean"] > 0)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("tầng",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
