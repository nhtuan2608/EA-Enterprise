"""G157: the G156a2 / G156b / G156c predictability tests (symmetric break outcome, anchors, named situations) on EURUSD, GBPUSD,
USDJPY (H1 2010-) and BTCUSD (H1 2018-). Plan: docs/superpowers/plans/2026-10-24-g157-fx-btc-predictability.md.

Usage: g157_markets.py <data dir> <out dir>            all four markets
       g157_markets.py <data dir> <out dir> --verify   XAUUSD M30 through this code, compared with results/g156c/summary.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g156a_questions as qa  # noqa: E402
import g156b_anchor as gb  # noqa: E402
from g148_layered_risk_map import calendar  # noqa: E402

SEED = 157
FX_PER = [("2011–2015", g.ts(2011, 1, 1), g.ts(2016, 1, 1)), ("2016–2020", g.ts(2016, 1, 1), g.ts(2021, 1, 1)),
          ("2021–06/2026", g.ts(2021, 1, 1), g.ts(2026, 7, 1))]
BTC_PER = [("2019–2021", g.ts(2019, 1, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
           ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1))]
GOLD_PER = [("05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
            ("2024–06/2026", g.ts(2024, 1, 1), g.ts(2026, 7, 1))]
MARKETS = {  # symbol: (tf, periods, anchor select years, anchor check years, news sign vs a USD-positive surprise)
    "EURUSD": ("H1", FX_PER, list(range(2013, 2020)), [2020, 2021, 2022, 2023, 2024, 2025, 2026], -1),
    "GBPUSD": ("H1", FX_PER, list(range(2013, 2020)), [2020, 2021, 2022, 2023, 2024, 2025, 2026], -1),
    "USDJPY": ("H1", FX_PER, list(range(2013, 2020)), [2020, 2021, 2022, 2023, 2024, 2025, 2026], 1),
    "BTCUSD": ("H1", BTC_PER, [2020, 2021, 2022], [2023, 2024, 2025, 2026], -1),
}
N_TESTS_SIT = 44


def first_passage(D, horizon):
    h, l, c, A = D["h"], D["l"], D["c"], D["atr"]
    n = len(c)
    up, dn = c + A, c - A
    r = np.zeros(n, int)
    done = np.zeros(n, bool)
    for k in range(1, horizon + 1):
        j = np.minimum(np.arange(n) + k, n - 1)
        valid = (np.arange(n) + k) <= n - 1
        hu, hd = (h[j] >= up) & valid, (l[j] <= dn) & valid
        both = ~done & hu & hd
        fu, fd = ~done & hu & ~hd, ~done & hd & ~hu
        r[both], r[fu], r[fd] = 2, 1, -1
        done |= both | fu | fd
    r[np.arange(n) >= n - horizon] = 0
    return r


def dedupe(idx, gap=4):
    out, last = [], -10 ** 9
    for i in sorted(set(int(x) for x in idx)):
        if i - last >= gap:
            out.append(i)
            last = i
    return out


def situation_stats(t, r, sit, ctl, per, start, end, alpha, rng, boot=2000):
    def rows(lst):
        out = []
        for i, d in lst:
            if d == 0 or t[i] < start:
                continue
            if r[i] in (1, -1):
                out.append((i, 1 if r[i] == d else -1))
        return out
    S, C = rows(sit), rows(ctl)

    def cnt(R, a, z):
        x = [o for i, o in R if a <= t[i] < z]
        return sum(1 for o in x if o == 1), len(x)
    out = {"tình huống": {}, "đối chứng": {}, "chênh theo kỳ": {}}
    signs = []
    for pn, a, z in per:
        s1, n1 = cnt(S, a, z)
        s0, n0 = cnt(C, a, z)
        out["tình huống"][pn] = {"n": n1, "P": round(s1 / n1, 3) if n1 else None}
        out["đối chứng"][pn] = {"n": n0, "P": round(s0 / n0, 3) if n0 else None}
        if n1 >= 30 and n0:
            out["chênh theo kỳ"][pn] = round(s1 / n1 - s0 / n0, 3)
            signs.append(np.sign(s1 / n1 - s0 / n0))
    s1, n1 = cnt(S, start, end)
    s0, n0 = cnt(C, start, end)
    diff = s1 / n1 - s0 / n0 if n1 and n0 else None
    weeks = {}
    for R, k in ((S, 0), (C, 2)):
        for i, o in R:
            if start <= t[i] < end:
                w = weeks.setdefault(int(t[i] // (7 * 86400)), [0, 0, 0, 0])
                w[k] += o == 1
                w[k + 1] += 1
    W = np.array(list(weeks.values()), float)
    ci = None
    if len(W) and n1 and n0:
        b = []
        for _ in range(boot):
            Sx = W[rng.integers(0, len(W), len(W))].sum(0)
            if Sx[1] > 0 and Sx[3] > 0:
                b.append(Sx[0] / Sx[1] - Sx[2] / Sx[3])
        ci = [round(float(np.percentile(b, 50 * alpha)), 3), round(float(np.percentile(b, 100 - 50 * alpha)), 3)]
    out["gộp"] = {"n tình huống": n1, "P tình huống": round(s1 / n1, 3) if n1 else None, "n đối chứng": n0,
                  "P đối chứng": round(s0 / n0, 3) if n0 else None, "chênh": round(diff, 3) if diff is not None else None, "CI": ci}
    a2, b2 = cnt(S, end, 2 ** 40), cnt(C, end, 2 ** 40)
    out["sau 07/2026"] = {"tình huống": f"{a2[0]}/{a2[1]}", "đối chứng": f"{b2[0]}/{b2[1]}"}
    every = all(out["tình huống"][pn]["n"] >= 30 for pn, _, _ in per)
    same = diff is not None and sum(1 for s in signs if s == np.sign(diff)) >= 2
    ok = n1 >= 100 and every and ci is not None and (ci[0] > 0 or ci[1] < 0) and same
    out["phân loại"] = "CÓ GIÁ TRỊ DỰ BÁO" if ok else "chỉ cảnh báo / giải thích"
    return out


def analyse(root, sym, tf, per, news_sign, alpha, rng, include_t7=False):
    bar = {"M30": 1800, "H1": 3600}[tf]
    horizon = 8 if tf == "M30" else 4
    start, end = per[0][1], per[-1][2]
    g.set_tf(tf)
    g.DATA = root / f"{tf.lower()}v"
    D = g.load(sym)
    F = qa.features(D)
    t, o, h, l, c, v, A = D["t"], D["o"], D["h"], D["l"], D["c"], D["v"], D["atr"]
    n = len(c)
    r = first_passage(D, horizon)
    hour = (t % 86400) // 3600
    reg = F["chế độ D1"]
    news = calendar()[0]
    close_t = t + bar
    kn = np.searchsorted(news, close_t, side="left")
    nxt = np.where(kn < len(news), news[np.minimum(kn, len(news) - 1)] - close_t, np.inf)
    prv = np.where(kn > 0, close_t - news[np.maximum(kn - 1, 0)], np.inf)
    quiet = (nxt > 3 * 3600) & (prv > 3 * 3600)
    ret4 = np.sign(c - np.r_[np.full(4, np.nan), c[:-4]])
    cand = np.sign(c - o)
    ret8 = c - np.r_[np.full(8, np.nan), c[:-8]]

    def with_dir(idx, darr):
        idx = dedupe(idx)
        return [(i, int(darr[i]) if np.isfinite(darr[i]) else 0) for i in idx]

    S = {}
    ev = np.nonzero((nxt >= 1800) & (nxt <= 3600))[0]
    S["T1 trước tin"] = (with_dir(ev, ret4), with_dir(np.nonzero(quiet & np.isin(hour, list(set(hour[ev].tolist()))))[0], ret4))
    bar_of = np.searchsorted(t, news, side="right") - 1
    ev2 = [int(i) for i, tn in zip(bar_of, news) if 0 <= i < n and t[i] <= tn < t[i] + bar]
    S["T2 nến tin"] = (with_dir(ev2, cand), with_dir(np.nonzero(quiet & np.isin(hour, list(set(hour[ev2].tolist()))))[0], cand))
    pos = {int(x): i for i, x in enumerate(t)}
    day = t // 86400
    n1530 = {int(tn // 86400) for tn in news if tn % 86400 == 15 * 3600 + 1800}
    any_15 = {int(tn // 86400) for tn in news if 15 * 3600 <= tn % 86400 < 16 * 3600 + 1800}
    nb_start = (15 * 3600 + 1800) // bar * bar
    e3, c3 = [], []
    for dk in sorted(set(day.tolist())):
        a_, b_ = pos.get(dk * 86400 + nb_start), pos.get(dk * 86400 + 16 * 3600)
        if a_ is None or b_ is None:
            continue
        dd = int(np.sign(c[b_] - o[a_]))
        if dk in n1530:
            e3.append((b_, dd))
        elif dk not in any_15:
            c3.append((b_, dd))
    S["T3 tin đã ra, chưa mở phiên Mỹ"] = (e3, c3)
    sw = []
    for i in range(1, n):
        dd = 0
        for lv in (F["_lv"]["PDL"][i], F["_lv"]["Á dưới"][i]):
            if np.isfinite(lv) and l[i] < lv < c[i]:
                dd = 1
        for lv in (F["_lv"]["PDH"][i], F["_lv"]["Á trên"][i]):
            if np.isfinite(lv) and h[i] > lv > c[i]:
                dd = -1 if dd == 0 else 0
        if dd:
            sw.append((i, dd))
    dmap = dict(sw)
    allreg = dedupe(np.nonzero(reg != 0)[0])
    e4 = dedupe([i for i, d in sw if reg[i] == d])
    e5 = dedupe([i for i, d in sw if reg[i] == -d])
    S["T4 quét rồi rút cùng chiều D1"] = ([(i, dmap[i]) for i in e4], [(i, int(reg[i])) for i in allreg])
    S["T5 quét rồi rút ngược D1"] = ([(i, dmap[i]) for i in e5], [(i, int(-reg[i])) for i in allreg])
    vv = np.convolve(v, np.ones(4) / 4, "full")[:n]
    vr = vv / np.r_[np.full(4, np.nan), vv[:-4]]
    big = np.abs(ret8) >= 1.5 * A
    S["T6 giá chạy mà volume giảm"] = (with_dir(np.nonzero(big & (vr < 0.8))[0], np.sign(ret8)),
                                       with_dir(np.nonzero(big & (vr >= 1.0))[0], np.sign(ret8)))
    import g129_gold_news as g129
    sur, _, _ = g129.events()
    e8, c8 = [], []
    for e in sur:
        i = int(np.searchsorted(t, e["t"], side="right")) - 1
        if i < 0 or not (t[i] <= e["t"] < t[i] + bar) or abs(c[i] - o[i]) < 0.5 * A[i]:
            continue
        expect = e["d"] * (1 if news_sign == -1 else -1)          # e["d"]: gold-like direction (down when USD is stronger)
        (e8 if cand[i] == -expect else c8).append(i)
    S["T8 phản ứng ngược kỳ vọng tin"] = (with_dir(e8, cand), with_dir(c8, cand))
    ema50 = g.ema(c, 50)
    swings = qa.swing_levels(D)
    sw_L = np.array([s[2] for s in swings]); sw_a = np.array([s[3] for s in swings]); sw_dir = np.array([s[1] for s in swings])
    sw_end = np.full(len(swings), n)
    for k, (_, d, L, a, life) in enumerate(swings):
        for i in range(a, n):
            if t[i] >= life or (d == 1 and c[i] > L and c[i - 1] <= L) or (d == -1 and c[i] < L and c[i - 1] >= L):
                sw_end[k] = i
                break
    fam = {"Á trên": "Á", "Á dưới": "Á", "PDH": "PD", "PDL": "PD", "PWH": "PW", "PWL": "PW", "swing đỉnh": "swing", "swing đáy": "swing"}
    q1 = [(i, d, name, L) for i, d, name, L in qa.q1_events(D, F) if t[i] >= start]
    L9 = {k: [] for k in ("e9", "c9", "e10", "c10", "e11", "c11", "e12", "c12")}
    for i, d, name, L in q1:
        tfs = [np.sign(c[i] - ema50[i]), np.sign(c[i] - D["E"][100][i]), D["h4_side"][i], reg[i]]
        L9["e9" if all(x == d for x in tfs) else "c9"].append((i, d))
        near = sum(1 for nm, arr in F["_lv"].items() if fam[nm] != fam[name] and np.isfinite(arr[i]) and abs(arr[i] - L) <= 0.5 * A[i])
        if fam[name] != "swing":
            near += int(((sw_a <= i) & (sw_end > i) & (np.abs(sw_L - L) <= 0.5 * A[i])).sum())
        L9["e10" if near >= 1 else "c10"].append((i, d))
        if fam[name] == "swing":
            k = int(np.argmin(np.abs(sw_L - L) + (sw_dir != d) * 1e9 + (sw_a > i) * 1e9))
            s0 = sw_a[k]
        elif fam[name] == "PW":
            s0 = int(np.searchsorted(t, ((t[i] // 86400 + 3) // 7 * 7 - 3) * 86400))
        else:
            s0 = int(np.searchsorted(t, (t[i] // 86400) * 86400 + (8 * 3600 if fam[name] == "Á" else 0)))
        seg = slice(max(s0, 0), i)
        touch = int(((h[seg] >= L - 0.25 * A[seg]) & (c[seg] <= L)).sum()) if d == 1 else int(((l[seg] <= L + 0.25 * A[seg]) & (c[seg] >= L)).sum())
        if touch >= 3:
            L9["e11"].append((i, d))
        elif touch <= 1:
            L9["c11"].append((i, d))
        if fam[name] in ("PD", "PW"):
            L9["c12"].append((i, d))
            for j in range(i + 1, min(i + 7, n)):
                if (d == 1 and c[j] <= L) or (d == -1 and c[j] >= L):
                    break
                if (d == 1 and l[j] <= L + 0.25 * A[j]) or (d == -1 and h[j] >= L - 0.25 * A[j]):
                    L9["e12"].append((j, d))
                    break

    def pairs(lst):
        dm = dict(lst)
        return [(i, dm[i]) for i in dedupe([i for i, _ in lst])]
    for key, a_, b_ in (("T9 đồng thuận đa khung", "e9", "c9"), ("T10 key level hợp lưu", "e10", "c10"),
                        ("T11 key level đã test nhiều lần", "e11", "c11"), ("T12 phá + retest giữ", "e12", "c12")):
        S[key] = (pairs(L9[a_]), pairs(L9[b_]))
    res = {}
    for key, (sit, ctl) in S.items():
        res[key] = situation_stats(t, r, sit, ctl, per, start, end, alpha, rng)
    # Q1b dataset for the anchor (as G156a2, on this timeframe)
    news_rows = []
    for i, d, name, L in q1:
        o_ = r[i]
        lab = "CẢ HAI" if o_ == 2 else ("LƯỠNG LỰ" if o_ == 0 else ("ĐI TIẾP" if o_ == d else "GIẢ"))
        row = {"loại": "Q1", "nến": int(i), "giờ server đóng": int(t[i] + bar)}
        row.update(qa.packet(F, i))
        row.update(qa.news_fields(news, int(t[i] + bar)))
        row.update({"mức": name, "chiều": d, "vượt mức/atr": float(d * (c[i] - L) / A[i]), "đáp án": lab})
        news_rows.append(row)
    return res, pd.DataFrame(news_rows)


def anchor(df, select, check):
    gb.SELECT, gb.CHECK = select, check
    gb.CI_ALPHA = 0.05 / 4
    df = df[~df["đáp án"].isin(["LƯỠNG LỰ", "CẢ HAI"])].reset_index(drop=True)
    df, X, y, strata = gb.prepare(df, "Q1")
    preds = gb.walk(df, X, y, strata, False)
    res, best, verdict = gb.evaluate_class(df, y, preds, np.random.default_rng(SEED))
    short = {m: {k: v for k, v in r.items() if k in ("chọn", "kiểm", "kiểm theo năm (kỹ năng)")} for m, r in res.items()}
    verdict = {k: v for k, v in verdict.items() if k != "hiệu chỉnh (kiểm)"}
    # "≥ 2 / 3 of the latest check years" for the multi-year FX check set
    yrs = res[best].get("kiểm theo năm (kỹ năng)", {})
    last3 = [yrs[k] for k in sorted(yrs)[-3:]]
    verdict["bối cảnh có giá trị"] = bool(best != "M0" and verdict.get("kỹ năng kiểm 95 %") and verdict["kỹ năng kiểm 95 %"][0] > 0
                                           and sum(x > 0 for x in last3) >= 2)
    return {"n": int(len(df)), "ĐI TIẾP": round(float(y.mean()), 3), "mô hình": short, "kết luận": verdict,
            "trường quan trọng": gb.importance(df, X, y, False)[:6]}


def main():
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    rng = np.random.default_rng(SEED)
    if "--verify" in sys.argv:
        res, _ = analyse(root, "XAUUSD", "M30", GOLD_PER, -1, 0.05 / 12, np.random.default_rng(156))
        ref = json.loads((out.parent / "g156c" / "summary.json").read_text(encoding="utf-8"))
        bad = 0
        for k, v in res.items():
            a_, b_ = v["gộp"], ref[k]["gộp"]
            same = (a_["n tình huống"], a_["P tình huống"], a_["n đối chứng"], a_["P đối chứng"]) == \
                   (b_["n tình huống"], b_["P tình huống"], b_["n đối chứng"], b_["P đối chứng"])
            bad += not same
            print(k, "khớp" if same else f"LỆCH {a_} vs {b_}", flush=True)
        print("verify:", "OK" if bad == 0 else f"{bad} lệch")
        return
    summary = {}
    for sym, (tf, per, sel, chk, ns) in MARKETS.items():
        res, q1 = analyse(root, sym, tf, per, ns, 0.05 / N_TESTS_SIT, rng)
        q1.to_csv(out / f"{sym}_Q1.csv", index=False, encoding="utf-8")
        dec = q1[q1["đáp án"].isin(["ĐI TIẾP", "GIẢ"])]
        yr = pd.to_datetime(dec["giờ server đóng"], unit="s").dt.year
        summary[sym] = {"Q1b": {"n": int(len(q1)), "phân bố": {k: round(float(x), 3) for k, x in q1["đáp án"].value_counts(normalize=True).items()},
                                "ĐI TIẾP theo năm": {int(y_): round(float((grp["đáp án"] == "ĐI TIẾP").mean()), 3) for y_, grp in dec.groupby(yr)}},
                        "mỏ neo": anchor(q1, sel, chk), "tình huống": res}
        print(sym, summary[sym]["mỏ neo"]["kết luận"], {k: v["phân loại"] for k, v in res.items()}, flush=True)
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
