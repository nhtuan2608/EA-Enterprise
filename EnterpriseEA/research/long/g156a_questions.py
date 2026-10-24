"""G156a: rule-based question generator (Q1 level breaks, Q2 S07 signals, Q3 S07 4/5 early, Q4 open-leg management), the context
packet and the objective labels, rebuilt on XAUUSD M30 history. Plan: docs/superpowers/plans/2026-10-24-g156a-questions-context-labels.md.

Times: bar times and the S07 legs' srv_in / srv_out are broker server time (the legs' ein / eout are UTC and are not used here).
Usage: g156a_questions.py <data dir> <out dir>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
from g148_layered_risk_map import calendar  # noqa: E402

START = g.ts(2018, 5, 1)
PER = [("05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1)), ("sau 07/2026", g.ts(2026, 7, 1), 2 ** 40)]
BAR = 1800
WIN, ADX_LOW, DI_GAP, ADX_RISE = 8, 20.0, 6.0, 10.0          # S07 M30 (EEA_S07WindowBars("M30") = 8)
SWING_K, SWING_LIFE = 6, 5 * 86400
Q1_BARS, Q1_ATR = 8, 1.0
Q3_BARS = 4
LOOKAHEAD_CHECKS = 300


def period(t):
    return next((p for p, a, z in PER if a <= t < z), None)


# ------------------------------------------------------------------------------------------------ features
def features(D, n=None):
    """Context packet for every bar 0..n-1, computed only from bars 0..n-1 (n=None: all)."""
    n = len(D["c"]) if n is None else n
    t, o, h, l, c = D["t"][:n], D["o"][:n], D["h"][:n], D["l"][:n], D["c"][:n]
    v, sp, atr = D["v"][:n], D["sp"][:n], D["atr"][:n]
    adx, pdi, mdi = D["adx"][:n], D["pdi"][:n], D["mdi"][:n]
    E = {k: D["E"][k][:n] for k in (21, 55, 100, 200)}
    F = {}
    F["giờ"] = (t % 86400) // 3600
    day = t // 86400
    F["thứ"] = (day + 3) % 7
    hr = F["giờ"]
    F["phiên"] = np.where((hr >= 1) & (hr <= 7), "Á", np.where((hr >= 8) & (hr <= 13), "Âu", np.where((hr >= 14) & (hr <= 19), "Mỹ", "muộn")))
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    F["atr"] = atr
    F["atr14/atr100"] = atr / g.rma(tr, 100)
    F["phân vị atr 1 năm"] = pd.Series(atr).rolling(11500, min_periods=2000).rank(pct=True).to_numpy()
    F["adx"], F["di_gap"] = adx, pdi - mdi
    hi4 = np.maximum.reduce([E[21], E[55], E[100], E[200]])
    lo4 = np.minimum.reduce([E[21], E[55], E[100], E[200]])
    F["dải EMA xếp"] = np.where((E[21] > E[55]) & (E[55] > E[100]) & (c > E[21]), 1,
                                np.where((E[21] < E[55]) & (E[55] < E[100]) & (c < E[21]), -1, 0))
    F["h4_side"] = D["h4_side"][:n]
    F["spread/atr"] = sp / atr
    F["lợi nhuận 4 nến/atr"] = (c - np.r_[np.full(4, np.nan), c[:-4]]) / atr
    F["lợi nhuận 16 nến/atr"] = (c - np.r_[np.full(16, np.nan), c[:-16]]) / atr
    # server days: closed-day values, today so far, VWAP, Asia range
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], n]
    dh = np.array([h[a:z].max() for a, z in zip(starts, ends)])
    dl = np.array([l[a:z].min() for a, z in zip(starts, ends)])
    dc = c[ends - 1]
    nd = len(starts)
    adr = np.full(nd, np.nan)
    for k in range(20, nd):
        adr[k] = (dh[k - 20:k] - dl[k - 20:k]).mean()
    e50 = g.ema(dc, 50)
    reg = np.zeros(nd, int)
    for k in range(60, nd):
        if dc[k] > e50[k] and e50[k] > e50[k - 10]:
            reg[k] = 1
        elif dc[k] < e50[k] and e50[k] < e50[k - 10]:
            reg[k] = -1
    s50 = pd.Series(dc).rolling(50).mean().to_numpy()
    s200 = pd.Series(dc).rolling(200).mean().to_numpy()
    e200d = g.ema(dc, 200)
    dpos = np.searchsorted(day[starts], day)                 # index of today among the days
    prev = dpos - 1
    okp = prev >= 0
    pick = lambda arr: np.where(okp, arr[np.maximum(prev, 0)], np.nan)  # noqa: E731
    F["chế độ D1"] = np.where(okp, reg[np.maximum(prev, 0)], 0)
    F["SMA50/200 D1"] = np.sign(pick(s50) - pick(s200))
    F["EMA200 D1 /atr"] = (c - pick(e200d)) / atr
    adr_t = np.where(dpos < nd, adr[np.minimum(dpos, nd - 1)], np.nan)
    pdh, pdl = pick(dh), pick(dl)
    vwap = np.empty(n)
    run_h, run_l = np.empty(n), np.empty(n)
    ah, al = np.full(n, np.nan), np.full(n, np.nan)
    tp_ = (h + l + c) / 3
    for a, z in zip(starts, ends):
        vv = np.maximum(v[a:z], 1.0)
        vwap[a:z] = np.cumsum(tp_[a:z] * vv) / np.cumsum(vv)
        run_h[a:z] = np.maximum.accumulate(h[a:z])
        run_l[a:z] = np.minimum.accumulate(l[a:z])
        asia = (hr[a:z] >= 1) & (hr[a:z] <= 7)
        after = hr[a:z] >= 8
        if asia.any() and after.any():
            ah[a:z][after] = h[a:z][asia].max()
            al[a:z][after] = l[a:z][asia].min()
    F["phạm vi ngày/ADR20"] = (run_h - run_l) / adr_t
    F["biên Á/ADR20"] = (ah - al) / adr_t
    # previous server week (Monday-based)
    wk = (day + 3) // 7
    wk_days = (day[starts] + 3) // 7
    wkh, wkl = {}, {}
    for k in range(nd):
        w = int(wk_days[k])
        wkh[w] = max(wkh.get(w, -np.inf), dh[k])
        wkl[w] = min(wkl.get(w, np.inf), dl[k])
    pwh = np.array([wkh.get(int(w) - 1, np.nan) for w in wk])
    pwl = np.array([wkl.get(int(w) - 1, np.nan) for w in wk])
    for name, lv in (("VWAP", vwap), ("biên Á trên", ah), ("biên Á dưới", al), ("PDH", pdh), ("PDL", pdl), ("PWH", pwh), ("PWL", pwl)):
        F[f"cách {name}/atr"] = (c - lv) / atr
    F["_lv"] = {"Á trên": ah, "Á dưới": al, "PDH": pdh, "PDL": pdl, "PWH": pwh, "PWL": pwl}
    F["_hi4"], F["_lo4"] = hi4, lo4
    return F


PUBLIC = ["giờ", "thứ", "phiên", "chế độ D1", "SMA50/200 D1", "h4_side", "dải EMA xếp", "adx", "di_gap", "atr", "atr14/atr100",
          "phân vị atr 1 năm", "phạm vi ngày/ADR20", "biên Á/ADR20", "cách VWAP/atr", "cách biên Á trên/atr", "cách biên Á dưới/atr",
          "cách PDH/atr", "cách PDL/atr", "cách PWH/atr", "cách PWL/atr", "EMA200 D1 /atr", "lợi nhuận 4 nến/atr",
          "lợi nhuận 16 nến/atr", "spread/atr"]


def packet(F, i):
    out = {}
    for k in PUBLIC:
        x = F[k][i]
        out[k] = x.item() if hasattr(x, "item") else x
    return out


def news_fields(news, close_time):
    k = int(np.searchsorted(news, close_time, side="left"))
    nxt = (news[k] - close_time) / 60 if k < len(news) else np.nan
    lst = (close_time - news[k - 1]) / 60 if k > 0 else np.nan
    return {"phút tới tin USD HIGH": float(nxt), "phút từ tin USD HIGH": float(lst)}


# ------------------------------------------------------------------------------------------------ S07 conditions and legs
def s07_conditions(D, F):
    adx, gap, c = D["adx"], F["di_gap"], D["c"]
    n = len(c)
    W = np.lib.stride_tricks.sliding_window_view(adx, WIN)          # row r = adx[r .. r+WIN-1]
    kmin = np.full(n, -1)
    kmin[WIN:] = np.argmin(W[:n - WIN], axis=1) + np.arange(n - WIN)  # bar of the lowest ADX in [i-WIN, i-1]
    ok = kmin >= 0
    k = np.maximum(kmin, 0)
    c1 = ok & (adx[k] <= ADX_LOW) & (np.abs(gap[k]) <= DI_GAP)
    c2 = ok & (adx > np.r_[np.nan, adx[:-1]]) & (adx - adx[k] <= ADX_RISE)
    gp = np.r_[np.nan, gap[:-1]]
    cond = {}
    for d in (1, -1):
        c3 = (d * gap > 0) & (d * gap > d * gp)
        c4 = (c > F["_hi4"]) if d == 1 else (c < F["_lo4"])
        c5 = F["h4_side"] == d
        cond[d] = np.vstack([c1, c2, c3, c4, c5])
    return cond


def s07_legs(root):
    """S07 M30 book (G89 port) with the base / add flag, server times, entry and stop distance (as g152_news_breakeven.legs)."""
    import g89_full_book as fb
    out = []
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            bases += fb.base_book(fb.e73.context(main, sub), d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                out.append(dict(d=d, base=j == 0, kind=L.get("kind", "S07") if j == 0 else "ADD", srv_in=int(L["srv_in"]),
                                srv_out=int(L["srv_out"]), entry=float(L["entry"]), dist=float(L["risk"]), rh=float(L["rh"])))
    g.set_tf("M30")
    g.DATA = root / "m30v"
    return out


# ------------------------------------------------------------------------------------------------ Q1 levels and labels
def swing_levels(D):
    h, l, t = D["h"], D["l"], D["t"]
    n = len(h)
    out = []
    K = SWING_K
    for k in range(K, n - K):
        if h[k] == h[k - K:k + K + 1].max():
            out.append(("swing đỉnh", 1, float(h[k]), k + K + 1, t[k] + SWING_LIFE))
        if l[k] == l[k - K:k + K + 1].min():
            out.append(("swing đáy", -1, float(l[k]), k + K + 1, t[k] + SWING_LIFE))
    return out


def q1_events(D, F):
    t, h, l, c = D["t"], D["h"], D["l"], D["c"]
    n = len(c)
    day = t // 86400
    ev = []
    # day / week levels: one event per level instance (value constant inside its validity)
    for name, d in (("Á trên", 1), ("Á dưới", -1), ("PDH", 1), ("PDL", -1), ("PWH", 1), ("PWL", -1)):
        lv = F["_lv"][name]
        key = day if name in ("Á trên", "Á dưới", "PDH", "PDL") else (day + 3) // 7
        done = set()
        for i in range(1, n):
            L = lv[i]
            if not np.isfinite(L) or key[i] in done:
                continue
            # crossing: this close beyond the level, the previous close not (on a level's first bar the previous close is
            # yesterday's / last week's close or the 07:30 close, which cannot be beyond the range it belongs to)
            if (d == 1 and c[i] > L and c[i - 1] <= L) or (d == -1 and c[i] < L and c[i - 1] >= L):
                done.add(key[i])
                ev.append((i, d, name, L))
    for name, d, L, a, life in swing_levels(D):
        for i in range(a, n):
            if t[i] >= life:
                break
            if (d == 1 and c[i] > L and c[i - 1] <= L) or (d == -1 and c[i] < L and c[i - 1] >= L):
                ev.append((i, d, name, L))
                break
    return ev


def q1_label(D, i, d, L, A):
    h, l, c = D["h"], D["l"], D["c"]
    for j in range(i + 1, min(i + 1 + Q1_BARS, len(c))):
        if d == 1:
            if h[j] >= L + Q1_ATR * A:
                return "ĐI TIẾP"
            if c[j] <= L:
                return "GIẢ"
        else:
            if l[j] <= L - Q1_ATR * A:
                return "ĐI TIẾP"
            if c[j] >= L:
                return "GIẢ"
    return "LƯỠNG LỰ"


# ------------------------------------------------------------------------------------------------ main
def main():
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = g.load("XAUUSD")
    t, c, h, l = D["t"], D["c"], D["h"], D["l"]
    F = features(D)
    news = calendar()[0]
    legs = s07_legs(root)
    D = g.load("XAUUSD")                                        # s07_legs switched timeframes: reload the M30 bars
    rows = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}

    def base_row(q, i, extra):
        r = {"loại": q, "nến": int(i), "giờ server đóng": int(t[i] + BAR), "kỳ": period(int(t[i]))}
        r.update(packet(F, i))
        r.update(news_fields(news, int(t[i] + BAR)))
        r.update(extra)
        return r

    # Q1
    for i, d, name, L in q1_events(D, F):
        if t[i] < START:
            continue
        A = D["atr"][i]
        lab = q1_label(D, i, d, L, A)
        rows["Q1"].append(base_row("Q1", i, {"mức": name, "chiều": d, "vượt mức/atr": float(d * (c[i] - L) / A), "đáp án": lab}))
    # Q2 / Q3 / Q4 from the S07 book
    idx_of = lambda srv: int(np.searchsorted(t, srv, side="right")) - 1   # noqa: E731  bar containing srv
    bases = [L for L in legs if L["base"] and L["srv_in"] >= START]
    for L in bases:
        i = int(np.searchsorted(t, L["srv_in"] - BAR, side="right")) - 1     # last M30 bar closed at or before the entry
        if i < 0:
            continue
        rows["Q2"].append(base_row("Q2", i, {"chiều": L["d"], "loại lệnh": L["kind"], "R": L["rh"],
                                             "đáp án": "DƯƠNG" if L["rh"] > 0 else "ÂM"}))
    cond = s07_conditions(D, F)
    for d in (1, -1):
        cnt = cond[d].sum(0)
        prev_cnt = np.r_[0, cnt[:-1]]
        for i in np.nonzero((cnt == 4) & (prev_cnt < 4))[0]:
            if t[i] < START:
                continue
            close_t = t[i] + BAR
            nxt = [L for L in bases if L["d"] == d and close_t < L["srv_in"] <= close_t + Q3_BARS * BAR]
            ex = {"chiều": d, "điều kiện S07": "".join("1" if x else "0" for x in cond[d][:, i])}
            if nxt:
                L = min(nxt, key=lambda x: x["srv_in"])
                ex.update({"đáp án": "S07 VÀO", "giá tốt hơn (R)": float(d * (L["entry"] - c[i]) / L["dist"]), "R của lệnh S07": L["rh"]})
            else:
                ex.update({"đáp án": "S07 KHÔNG VÀO"})
            rows["Q3"].append(base_row("Q3", i, ex))
    for L in legs:
        if L["srv_in"] < START:
            continue
        a = idx_of(L["srv_in"])
        z = idx_of(L["srv_out"])
        d, E0, R = L["d"], L["entry"], L["dist"]
        for i in range(a + 1, z):
            if (t[i] + BAR) % 3600:
                continue
            p0 = c[i]
            lab = "ĐÓNG TRƯỚC"
            for j in range(i + 1, z + 1):
                up = (h[j] >= p0 + R) if d == 1 else (l[j] <= p0 - R)
                back = (l[j] <= E0) if d == 1 else (h[j] >= E0)
                if up and back:
                    lab = "QUAY VỀ"                                    # both in one bar: counted conservatively (see report)
                    break
                if back:
                    lab = "QUAY VỀ"
                    break
                if up:
                    lab = "ĐI TIẾP"
                    break
            rnow = d * (p0 - E0) / R
            rows["Q4"].append(base_row("Q4", i, {"chiều": d, "lệnh gốc": L["base"], "R đang có": float(rnow),
                                                 "giờ đã giữ": float((t[i] + BAR - L["srv_in"]) / 3600),
                                                 "đang lời": bool(rnow > 0), "đáp án": lab}))
    frames = {q: pd.DataFrame(r) for q, r in rows.items()}
    for q, df in frames.items():
        df.to_csv(out / f"{q}.csv", index=False, encoding="utf-8")

    # ---------------------------------------------------------------- checks
    rng = random.Random(156)
    allq = pd.concat([frames[q][["nến"]] for q in ("Q1", "Q2", "Q3", "Q4")])
    picks = rng.sample(sorted(set(allq["nến"].tolist())), min(LOOKAHEAD_CHECKS, allq["nến"].nunique()))
    bad = 0
    for i in picks:
        Ft = features(D, i + 1)
        for k in PUBLIC:
            a_, b_ = F[k][i], Ft[k][i]
            if isinstance(a_, str) or isinstance(b_, str):
                same = a_ == b_
            else:
                same = (np.isnan(a_) and np.isnan(b_)) or abs(float(a_) - float(b_)) <= 1e-9 * max(1.0, abs(float(a_)))
            if not same:
                bad += 1
                print("look-ahead?", i, k, a_, b_, flush=True)
                break
    q13 = pd.concat([frames[q][["giờ server đóng", "kỳ"]] for q in ("Q1", "Q2", "Q3")])
    q13 = q13[q13["kỳ"].notna()]
    q13["ngày"] = q13["giờ server đóng"] // 86400
    q13["giờ"] = q13["giờ server đóng"] // 3600
    trading_days = len(set((t[t >= START] // 86400).tolist()))
    hours_per_day = q13["giờ"].nunique() / trading_days
    weeks = trading_days / 5
    summary = {"kiểm tra nhìn trước": {"số sự kiện": len(picks), "sai lệch": bad, "đạt": bad == 0},
               "giờ họp trung bình / ngày (Q1–Q3)": round(hours_per_day, 2), "đạt ≤ 6": bool(hours_per_day <= 6),
               "số câu hỏi / tuần": {q: round(len(df) / weeks, 1) for q, df in frames.items()}}
    for q in ("Q1", "Q2", "Q3", "Q4"):
        df = frames[q]
        dist = {}
        for pn, _, _ in PER:
            s = df[df["kỳ"] == pn]["đáp án"].value_counts(normalize=True)
            dist[pn] = {k: round(float(v), 3) for k, v in s.items()}
        dist["tất cả"] = {k: round(float(v), 3) for k, v in df["đáp án"].value_counts(normalize=True).items()}
        summary[f"{q} đáp án theo kỳ"] = dist
        if q in ("Q1", "Q4"):
            summary[f"{q} đáp án ≥ 5 %"] = bool(df["đáp án"].value_counts(normalize=True).min() >= 0.05)
    q1 = frames["Q1"]
    summary["Q1 theo loại mức"] = {m: {**{k: round(float(v), 3) for k, v in grp["đáp án"].value_counts(normalize=True).items()},
                                       "n": int(len(grp))} for m, grp in q1.groupby("mức")}
    q1["năm"] = pd.to_datetime(q1["giờ server đóng"], unit="s").dt.year
    summary["Q1 GIẢ theo năm"] = {int(y): round(float((grp["đáp án"] == "GIẢ").mean()), 3) for y, grp in q1.groupby("năm")}
    q3 = frames["Q3"]
    hit = q3[q3["đáp án"] == "S07 VÀO"]
    summary["Q3"] = {"n": int(len(q3)), "S07 vào trong 2 giờ": round(float(len(hit) / max(len(q3), 1)), 3),
                     "giá tốt hơn (R) trung vị": round(float(hit["giá tốt hơn (R)"].median()), 3) if len(hit) else None,
                     "giá tốt hơn (R) trung bình": round(float(hit["giá tốt hơn (R)"].mean()), 3) if len(hit) else None}
    q4 = frames["Q4"]
    summary["Q4 theo đang lời"] = {str(k): {**{a: round(float(b), 3) for a, b in grp["đáp án"].value_counts(normalize=True).items()},
                                            "n": int(len(grp))} for k, grp in q4.groupby("đang lời")}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
