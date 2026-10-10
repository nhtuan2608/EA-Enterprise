"""G75: S07 adds on M15 EMA pullbacks with DMI confirmation (G74 P4C1), robustness. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g75-m15-ema21-adds.md. MT5 data only.

  python g75_m15_adds.py
"""
from __future__ import annotations

import itertools
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g70_pyramid as gp  # noqa: E402
import g74_pullback_adds as p4  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g75-m15-ema21-adds.md"
DECIDE = ("train", "validate", "test")
YEARS = (2021, 2022, 2023, 2024, 2025)
BASE = dict(tol=0.1, adx=20.0, ema=21)
GRID = list(itertools.product((0.05, 0.1, 0.2), (15.0, 20.0, 25.0), (13, 21, 34)))


def m15_legs(b, book, tol, adx_min, ema_n):
    """G74 P4C1 with its three parameters: touch tolerance (ATR), ADX threshold, EMA period (M15)."""
    D = p4.data("M15", book["rule"])
    if ema_n not in D["E"]:
        D["E"][ema_n] = g.ema(D["c"], ema_n)
    d = book["side"]
    o, hh, ll, c, atr, E, adx, pdi, mdi = D["o"], D["h"], D["l"], D["c"], D["atr"], D["E"], D["adx"], D["pdi"], D["mdi"]
    hold = p4.TFP["M15"][2]
    a, z = p4.span(D, b, 900)
    out, touched, ext = [], False, None
    for j in range(max(a, 1), z):
        lv = E[ema_n][j]
        touch = d * (ll[j] if d == 1 else hh[j]) <= d * (lv + d * tol * atr[j]) and d * (c[j] - E[55][j]) >= 0
        if touch:
            ext = (ll[j] if d == 1 else hh[j]) if not touched else (min(ext, ll[j]) if d == 1 else max(ext, hh[j]))
            touched = True
        elif touched:
            ext = min(ext, ll[j]) if d == 1 else max(ext, hh[j])
        if not touched:
            continue
        trig = d * (c[j] - (hh[j - 1] if d == 1 else ll[j - 1])) > 0 and d * (c[j] - lv) > 0
        trig = trig and (pdi[j] > mdi[j] if d == 1 else mdi[j] > pdi[j]) and adx[j] >= adx_min
        if not trig:
            continue
        touched = False
        e0 = j + 1
        entry = o[e0] + (D["sp"][e0] if d == 1 else 0.0)
        dist = d * (entry - (ext - d * 0.1 * atr[j]))
        if dist <= 0 or dist > 4.0 * atr[j]:
            continue
        dist = max(dist, atr[j])
        t = p4.walk_leg(D, e0, d, entry, dist, book["rule"]["exit"], hold)
        t.update(d=d, tf="M15", i=j, sig=int(D["utc"][j]) + 900, ein=int(D["utc"][e0]), eout=int(D["utc"][t["x"]]) + 900,
                 dist_atr=float(dist / atr[j]), kind="P4C1")
        p4.harsh_leg(t, D)
        out.append(t)
    return out


def decide_only(cl):
    return [c for c in cl if c["p"] in DECIDE]


def metrics(cl):
    dec = decide_only(cl)
    r = gp.risk_stats(dec)
    s = gp.summary(cl)
    a = p4.add_stats(cl)
    years = {}
    for y in YEARS:
        x = [L["rh"] for c in dec for L in c["add_legs"] if datetime.fromtimestamp(L["ein"], timezone.utc).year == y]
        years[y] = (len(x), float(np.mean(x)) if x else 0.0)
    return dict(r=r, s=s, a=a, years=years, ratio=r["per_year"] / max(r["dd90"], 1e-9))


def scaled(cl, k):
    """Same clusters with the harsh extra cost multiplied by k (rh = r - extra)."""
    out = []
    for c in cl:
        legs = []
        for (rh, t_out, t_in, tf), L in zip(c["legs"], [c["base"]] + c["add_legs"]):
            legs.append((L["r"] - k * (L["r"] - rh), t_out, t_in, tf))
        out.append(dict(c, legs=legs, total=sum(x[0] for x in legs)))
    return out


def main():
    book = gp.BOOKS["Mua"]
    all_legs = p4.base_book(book)
    pool = sorted([L for tf in p4.TFP if tf != book["base"] for L in all_legs[tf][0].values()], key=lambda x: x["sig"])

    def a1(b):
        return [L for L in pool if b["ein"] < L["sig"] < b["eout"]]

    def p4c1(b, prm=BASE):
        return m15_legs(b, book, prm["tol"], prm["adx"], prm["ema"])

    res = {"A1": p4.assemble(book, all_legs, a1),
           "R": p4.assemble(book, all_legs, p4c1),
           "U": p4.assemble(book, all_legs, lambda b: a1(b) + p4c1(b))}
    m = {k: metrics(cl) for k, cl in res.items()}
    rnd = {}
    for k in ("R", "U"):
        dec = [L["rh"] for c in res[k] if c["p"] in DECIDE for L in c["add_legs"]]
        rnd[k] = p4.random_p(res[k], book, float(np.mean(dec)))
    # neighbours: 27 parameter sets, replace (R) and union (U)
    a1_dd = m["A1"]["r"]["dd90"]
    neigh = {"R": [], "U": []}
    for tol, adx_min, ema_n in GRID:
        prm = dict(tol=tol, adx=adx_min, ema=ema_n)
        for k, fn in (("R", lambda b, prm=prm: p4c1(b, prm)), ("U", lambda b, prm=prm: a1(b) + p4c1(b, prm))):
            cl = p4.assemble(book, all_legs, fn)
            mm = metrics(cl)
            ok = (mm["r"]["c30"] <= 2.0 and mm["r"]["dd90"] <= a1_dd - 5.0 and
                  all(mm["a"][q][0] and mm["a"][q][1] > 0 for q in DECIDE))
            neigh[k].append((prm, ok, mm))

    L = ["# G75: Bồi S07 bằng hồi EMA21 trên M15 + DMI — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g75-m15-ema21-adds.md`. Sổ mua S07 M30, XAUUSD, dữ liệu MT5, chi phí khắt khe G68, "
         "rủi ro 1,5%/lệnh, tối đa 2 lệnh bồi và 3 lệnh mở. Rủi ro và tiêu chí tính trên 07/2021–06/2026 (train + validate + test). "
         "Đây là kiểm tra độ vững, không phải ngoài mẫu (P4C1 đã được nhìn ở G74).", "",
         "| Bản | Train | Validate | Test | 07/2026– | Lệnh bồi R/lệnh: train / validate / test | Lệnh bồi theo năm 2021…2025 | "
         "%/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | %/năm ÷ DD p90 | Chi phí ×1,5: %/năm / DD p90 | Ngẫu nhiên (TB / p) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, name in (("A1", "A1 bồi hiện tại"), ("R", "R thay bằng P4C1"), ("U", "U gộp A1 + P4C1")):
        mm, r = m[k], m[k]["r"]
        r15 = gp.risk_stats(decide_only(scaled(res[k], 1.5)))
        yrs = " / ".join(f"{mm['years'][y][1]:+.2f} ({mm['years'][y][0]})" for y in YEARS)
        rm, pv = rnd.get(k, (float("nan"), float("nan")))
        L.append(f"| {name} | " + " | ".join(p4.cell(mm["s"][q]) for q in ("train", "validate", "test", "examples")) +
                 f" | {mm['a']['train'][1]:+.2f} / {mm['a']['validate'][1]:+.2f} / {mm['a']['test'][1]:+.2f} | {yrs} | "
                 f"{r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% | {mm['ratio']:.2f} | "
                 f"{r15['per_year']:+.0f}% / {r15['dd90']:.0f}% | {'—' if np.isnan(pv) else f'{rm:+.2f} / {pv:.3f}'} |")
    L.append("")
    verdicts = {}
    for k in ("R", "U"):
        mm, r = m[k], m[k]["r"]
        a1r = m["A1"]["r"]
        share = float(np.mean([ok for _, ok, _ in neigh[k]]))
        checks = {
            "1 chạm 30% ≤ 2% và DD p90 ≤ A1 − 5": r["c30"] <= 2.0 and r["dd90"] <= a1r["dd90"] - 5.0,
            "2 %/năm ≥ 85% A1": r["per_year"] >= 0.85 * a1r["per_year"],
            "3 %/năm ÷ DD p90 > A1": mm["ratio"] > m["A1"]["ratio"],
            "4 lệnh bồi dương ≥ 4/5 năm": sum(1 for y in YEARS if mm["years"][y][0] and mm["years"][y][1] > 0) >= 4,
            f"5 lân cận đạt ≥ 60% ({share:.0%})": share >= 0.6,
            "6 thắng ngẫu nhiên p < 0,025": (not np.isnan(rnd[k][1])) and rnd[k][1] < 0.025,
        }
        verdicts[k] = all(checks.values())
        L.append(f"- **{k}**: " + "; ".join(f"{c}: {'đạt' if x else 'KHÔNG'}" for c, x in checks.items()) +
                 f" → **{'ĐẠT' if verdicts[k] else 'không đạt'}**")
    L += ["", "### 27 bộ lân cận (độ chạm × ADX × EMA): %/năm / DD p90 / chạm 30% / đạt điều 1 + lệnh bồi dương 3 kỳ", "",
          "| Độ chạm | ADX | EMA | R | U |", "|---|---|---|---|---|"]
    for (prm, okr, mr), (_, oku, mu) in zip(neigh["R"], neigh["U"]):
        f = lambda mm, ok: f"{mm['r']['per_year']:+.0f}% / {mm['r']['dd90']:.0f}% / {mm['r']['c30']:.0f}% / {'✓' if ok else '✗'}"
        L.append(f"| {prm['tol']} | {prm['adx']:.0f} | {prm['ema']} | {f(mr, okr)} | {f(mu, oku)} |")
    passed = [k for k in ("R", "U") if verdicts[k]]
    pick = max(passed, key=lambda k: m[k]["ratio"]) if passed else None
    L += ["", f"**Kết luận theo luật: {'chọn ' + pick + ' → thêm engine SHADOW song song với S07A' if pick else 'giữ A1'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
