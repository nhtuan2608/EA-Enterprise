"""G83: features at the S07 signal that separate one-way expansions from sideways chop; base for 3% risk.
Pre-registered plan: docs/superpowers/plans/2026-10-10-g83-expansion-vs-sideway.md. MT5 data only.

  python g83_expansion.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g81_relaxed as r81  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g83-expansion-vs-sideway.md"
r81.TF["H4"] = dict(comp=8, cool=4, hold=240)
TFS = ("M15", "M30", "H1", "H4")
SEC = {"M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}
FEATS = ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12", "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20"]
NAMES = {"f1": "số nến ADX<20 (48 nến)", "f2": "ADX đáy cửa sổ", "f3": "ATR / ATR 48–96 nến trước", "f4": "bề rộng vùng nén / ATR",
         "f5": "biên độ nến bung / ATR", "f6": "thân / biên độ", "f7": "vị trí giá đóng trong nến", "f8": "bước nhảy khoảng cách DI",
         "f9": "dải EMA xếp thứ tự", "f10": "(EMA21−EMA100)/ATR", "f11": "độ dốc EMA200 / ATR", "f12": "khoảng cách tới EMA200 / ATR",
         "f13": "dải EMA H4 xếp thứ tự", "f14": "ADX H4", "f15": "D1 cùng phía EMA200", "f16": "volume nến bung (tương đối)",
         "f17": "volume vùng nén (tương đối)", "f18": "số lần bung hụt (2W nến trước)", "f19": "số tín hiệu S07 cùng chiều (4W nến trước)",
         "f20": "phá đỉnh/đáy 96 nến"}
PLANS = {"P0": (0.015, 0.015), "P1": (0.03, 0.015), "P2": (0.03, 0.0), "P3": (0.03, 0.03)}
RANGES = {"09/2018–06/2026": ("pre", "train", "validate", "test"), "07/2021–06/2026": ("train", "validate", "test")}


def features(D, H4, i, d, sig_set):
    c, o, hh, ll, E, atr, adx, gap = D["c"], D["o"], D["h"], D["l"], D["E"], D["atr"], D["adx"], D["gap"]
    W = r81.TF[D["tf"]]["comp"]
    a = atr[i]
    rng_ = max(hh[i] - ll[i], 1e-9)
    mid = (hh[i] + ll[i]) / 2
    f = {}
    f["f1"] = float(np.sum(adx[i - 48:i] < 20))
    f["f2"] = float(D["minA"][i])
    f["f3"] = float(a / max(np.mean(atr[i - 96:i - 48]), 1e-9))
    f["f4"] = float((hh[i - W:i + 1].max() - ll[i - W:i + 1].min()) / a)
    f["f5"] = float(rng_ / a)
    f["f6"] = float(abs(c[i] - o[i]) / rng_)
    f["f7"] = float(d * (c[i] - mid) / rng_)
    f["f8"] = float(d * (gap[i] - gap[i - 1]))
    f["f9"] = float((E[21][i] > E[55][i] > E[100][i]) if d == 1 else (E[21][i] < E[55][i] < E[100][i]))
    f["f10"] = float(d * (E[21][i] - E[100][i]) / a)
    f["f11"] = float(d * (E[200][i] - E[200][i - W]) / a)
    f["f12"] = float(d * (c[i] - E[200][i]) / a)
    tc = D["t"][i] + SEC[D["tf"]]
    k = int(np.searchsorted(H4["t"] + 14400, tc, side="right")) - 1
    E4 = H4["E"]
    f["f13"] = float(k > 0 and ((E4[21][k] > E4[55][k] > E4[100][k]) if d == 1 else (E4[21][k] < E4[55][k] < E4[100][k])))
    f["f14"] = float(H4["adx"][k]) if k > 0 else np.nan
    f["f15"] = float(D["d1_side"][i] == d)
    f["f16"] = float(D["rv"][i]) if not np.isnan(D["rv"][i]) else np.nan
    rv = D["rv"][i - W:i]
    rv = rv[~np.isnan(rv)]
    f["f17"] = float(rv.mean()) if len(rv) else np.nan
    lo = (D["elo"] if d == -1 else D["ehi"])
    beyond = (d * (c[i - 2 * W:i] - lo[i - 2 * W:i]) > 0)
    f["f18"] = float(np.sum(beyond[1:] & ~beyond[:-1])) if len(beyond) > 1 else 0.0
    f["f19"] = float(sum(1 for j in range(i - 4 * W, i) if j in sig_set))
    prior = hh[i - 96:i].max() if d == 1 else ll[i - 96:i].min()
    f["f20"] = float(d * (c[i] - prior) > 0)
    return f


def collect(d):
    rows = []
    H4 = r81.load("H4")
    H4c = {k: H4[k] for k in ("t", "E", "adx")}
    for tf in TFS:
        D = r81.load(tf)
        sig = r81.signals(D, d, "RB4", "K0", "DS")
        sig_set = set(int(x) for x in sig)
        trs = r81.book(D, sig, d, "X1")
        for t in trs:
            if t["i"] < 200:
                continue
            t.update(features(D, H4c, t["i"], d, sig_set))
            t["tf"] = tf
            t["hour"] = int(((D["utc"][t["i"]] + SEC[tf]) // 3600) % 24)
            rows.append(t)
    return rows


def score_rows(rows):
    """Spearman on train (pooled), features with p < 0.05, z by train per timeframe, top-tercile threshold of train per timeframe."""
    tr = [t for t in rows if t["p"] == "train"]
    uni = {}
    for f in FEATS:
        x = np.array([t[f] for t in tr], dtype=float)
        y = np.array([t["rh"] for t in tr])
        m = ~np.isnan(x)
        rho, p = spearmanr(x[m], y[m]) if m.sum() > 20 and np.std(x[m]) > 0 else (np.nan, 1.0)
        res = {}
        for q in ("validate", "test"):
            sub = [t for t in rows if t["p"] == q]
            xs = np.array([t[f] for t in sub], dtype=float)
            ys = np.array([t["rh"] for t in sub])
            mm = ~np.isnan(xs)
            res[q] = spearmanr(xs[mm], ys[mm])[0] if mm.sum() > 20 and np.std(xs[mm]) > 0 else np.nan
        uni[f] = (rho, p, res["validate"], res["test"])
    chosen = [f for f, (rho, p, _, _) in uni.items() if not np.isnan(rho) and p < 0.05]
    for tf in TFS:
        trt = [t for t in tr if t["tf"] == tf]
        stats = {}
        for f in chosen:
            x = np.array([t[f] for t in trt], dtype=float)
            stats[f] = (np.nanmean(x), np.nanstd(x) or 1.0)
        for t in rows:
            if t["tf"] != tf:
                continue
            s = 0.0
            for f in chosen:
                val = t[f]
                if np.isnan(val):
                    continue
                s += np.sign(uni[f][0]) * (val - stats[f][0]) / stats[f][1]
            t["score"] = s
        thr = np.percentile([t["score"] for t in trt], 200 / 3) if trt else np.inf
        for t in rows:
            if t["tf"] == tf:
                t["top"] = t["score"] >= thr
    return uni, chosen


def path(legs):
    eq = pk = 1.0
    dd = 0.0
    for r, _, risk in legs:
        eq *= 1 + risk * r
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    return eq, dd


def risk_stats(trs, plan, keys):
    top, rest = PLANS[plan]
    legs = sorted([(t["rh"], t["srv_out"], top if t["top"] else rest) for t in trs if t["p"] in keys], key=lambda z: z[1])
    legs = [z for z in legs if z[2] > 0]
    t0 = min(t["srv_in"] for t in trs if t["p"] in keys)
    yrs = (legs[-1][1] - t0) / (365.25 * 86400)
    eq, dd = path(legs)
    n = max(10, int(len(legs) / yrs))
    rng = np.random.default_rng(83)
    res = [path(legs[s:s + n]) for s in rng.integers(0, max(1, len(legs) - n), 3000)]
    dds = np.array([x[1] for x in res])
    py = (eq ** (1 / yrs) - 1) * 100
    d90 = float(np.percentile(dds, 90)) * 100
    return dict(py=py, dd=dd * 100, d90=d90, c20=float(np.mean(dds >= 0.2)) * 100, c30=float(np.mean(dds >= 0.3)) * 100,
                ratio=py / max(d90, 1e-9), n=len(legs))


def grp(trs):
    if not trs:
        return "—"
    rs = [t["rh"] for t in trs]
    sl = np.mean([t["reason"] == "SL" for t in trs])
    return f"{len(rs)} / {np.mean(rs):+.3f} / SL {sl:.0%}"


def main():
    L = ["# G83: Phân biệt mở biên một chiều và sideway ở tín hiệu S07 — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g83-expansion-vs-sideway.md`. XAUUSD, S07 chuẩn ở M15/M30/H1/H4 (mua có lọc H4, bán không), "
         "thoát E2X TP 8R, chi phí khắt khe G68. Ô nhóm: số lệnh / R mỗi lệnh / tỉ lệ chạm SL.", ""]
    for d, dn in ((1, "Mua"), (-1, "Bán")):
        rows = collect(d)
        uni, chosen = score_rows(rows)
        L += [f"## {dn}", "", f"Tổng {len(rows)} lệnh (4 khung).", "",
              "### Đơn biến (tương quan hạng với R/lệnh)", "",
              "| Đặc trưng | Train ρ | p (train) | Validate ρ | Test ρ | Dùng |", "|---|---|---|---|---|---|"]
        for f, (rho, p, rv_, rt) in sorted(uni.items(), key=lambda z: z[1][1]):
            L.append(f"| {NAMES[f]} | {rho:+.3f} | {p:.3f} | {rv_:+.3f} | {rt:+.3f} | {'✓' if f in chosen else ''} |")
        L += ["", f"Đặc trưng đưa vào điểm số: {', '.join(NAMES[f] for f in chosen) if chosen else 'không có'}.", ""]
        if not chosen:
            L += [f"**{dn}: không có đặc trưng nào đủ mạnh trên train → không có nhóm mở biên.**", ""]
            continue
        L += ["### Nhóm mở biên (điểm ≥ tam phân vị trên của train) so với toàn bộ", "",
              "| Khung | Kỳ | Mở biên | Còn lại | Toàn bộ |", "|---|---|---|---|---|"]
        for tf in TFS + ("Gộp",):
            for q in ("pre", "train", "validate", "test", "examples"):
                sub = [t for t in rows if t["p"] == q and (tf == "Gộp" or t["tf"] == tf)]
                if not sub:
                    continue
                L.append(f"| {tf} | {v.NAMES[q]} | {grp([t for t in sub if t['top']])} | {grp([t for t in sub if not t['top']])} | {grp(sub)} |")
        ok_group = True
        for q in ("validate", "test"):
            sub = [t for t in rows if t["p"] == q]
            top = [t for t in sub if t["top"]]
            all_r, top_r = np.mean([t["rh"] for t in sub]), (np.mean([t["rh"] for t in top]) if top else -9)
            sl_all, sl_top = np.mean([t["reason"] == "SL" for t in sub]), (np.mean([t["reason"] == "SL" for t in top]) if top else 1)
            ok_q = top_r >= max(1.5 * all_r, 0.5) and sl_top < sl_all
            ok_group &= ok_q
            L.append(f"\n- {v.NAMES[q]}: mở biên {top_r:+.3f} vs toàn bộ {all_r:+.3f} (cần ≥ {max(1.5 * all_r, 0.5):+.3f}); "
                     f"SL {sl_top:.0%} vs {sl_all:.0%} → {'đạt' if ok_q else 'KHÔNG'}")
        L += ["", f"**Nhóm mở biên ({dn}): {'ĐẠT' if ok_group else 'không đạt'}.**", ""]
        # hour table (report only)
        L += ["Theo giờ UTC của tín hiệu (gộp 4 khung, train + validate + test): " +
              ", ".join(f"{hh:02d}h {np.mean([t['rh'] for t in rows if t['hour'] == hh and t['p'] in ('train', 'validate', 'test')]):+.2f}"
                        f" ({sum(1 for t in rows if t['hour'] == hh and t['p'] in ('train', 'validate', 'test'))})"
                        for hh in range(24) if any(t['hour'] == hh and t['p'] in ('train', 'validate', 'test') for t in rows)), ""]
        m30 = [t for t in rows if t["tf"] == "M30"]
        L += ["### Rủi ro (sổ lệnh gốc M30, không bồi)", "",
              "| Phương án | Giai đoạn | Lệnh | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | %/năm ÷ DD p90 |",
              "|---|---|---|---|---|---|---|---|---|"]
        res = {}
        for plan in PLANS:
            for rn, keys in RANGES.items():
                s = risk_stats(m30, plan, keys)
                res[(plan, rn)] = s
                L.append(f"| {plan} {PLANS[plan][0] * 100:.1f}% / {PLANS[plan][1] * 100:.1f}% | {rn} | {s['n']} | {s['py']:+.0f}% | {s['dd']:.0f}% | "
                         f"{s['d90']:.0f}% | {s['c20']:.0f}% | {s['c30']:.0f}% | {s['ratio']:.2f} |")
        if ok_group:
            acc = [pl for pl in ("P1", "P2") if all(res[(pl, rn)]["c30"] <= 5 and res[(pl, rn)]["d90"] <= 25 and
                                                     res[(pl, rn)]["ratio"] > res[("P0", rn)]["ratio"] for rn in RANGES)]
            L += ["", f"**Rủi ro 3% ({dn}): {'chấp nhận ' + ', '.join(acc) if acc else 'không phương án 3% nào đạt'}.**", ""]
        else:
            L += ["", f"**Rủi ro 3% ({dn}): không xét vì nhóm mở biên không đạt.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
