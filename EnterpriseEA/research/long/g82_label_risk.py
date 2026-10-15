"""G82: risk by the ordered-ribbon label for S07 M30 buys. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g82-ribbon-label-risk.md. MT5 data only.

  python g82_label_risk.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g70_pyramid as gp  # noqa: E402
import g74_pullback_adds as p4  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g82-ribbon-label-risk.md"
FOUR = ("pre", "train", "validate", "test")
PLANS = {"K0": (0.015, 0.015), "K1": (0.015, 0.010), "K3": (0.015, 0.0075), "K2": (0.020, 0.015)}
RANGES = {"09/2018–06/2026": FOUR, "07/2021–06/2026": ("train", "validate", "test")}
ADD_RISK = 0.015
PERMS = 5000


def labelled(D, i):
    E, c = D["E"], D["c"]
    return bool(E[21][i] > E[55][i] > E[100][i] and c[i] > E[21][i])


def legs_of(cl, plan, with_adds, keys):
    lab, unl = PLANS[plan]
    out = []
    for c in cl:
        if c["p"] not in keys:
            continue
        b = c["base"]
        out.append((b["rh"], b["eout"], b["ein"], lab if c["label"] else unl))
        if with_adds:
            out += [(L["rh"], L["eout"], L["ein"], ADD_RISK) for L in c["add_legs"]]
    return sorted(out, key=lambda z: z[1])


def path(legs):
    eq = pk = 1.0
    dd = 0.0
    for r, _, _, risk in legs:
        eq *= 1 + risk * r
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    return eq, dd


def risk_stats(legs):
    yrs = (legs[-1][1] - min(z[2] for z in legs)) / (365.25 * 86400)
    eq, dd = path(legs)
    n = max(10, int(len(legs) / yrs))
    rng = np.random.default_rng(82)
    res = [path(legs[s:s + n]) for s in rng.integers(0, max(1, len(legs) - n), 3000)]
    dds = np.array([x[1] for x in res])
    rets = np.array([x[0] - 1 for x in res])
    py = (eq ** (1 / yrs) - 1) * 100
    d90 = float(np.percentile(dds, 90)) * 100
    return dict(py=py, dd=dd * 100, d90=d90, c20=float(np.mean(dds >= 0.2)) * 100, c30=float(np.mean(dds >= 0.3)) * 100,
                p10=float(np.percentile(rets, 10)) * 100, ratio=py / max(d90, 1e-9))


def main():
    book = gp.BOOKS["Mua"]
    all_legs = p4.base_book(book)
    D = p4._D[book["base"]]
    pool = sorted([L for tf in p4.TFP if tf != book["base"] for L in all_legs[tf][0].values()], key=lambda x: x["sig"])
    cl = p4.assemble(book, all_legs, lambda b: [L for L in pool if b["ein"] < L["sig"] < b["eout"]])
    for c in cl:
        c["label"] = labelled(D, c["base"]["i"])
    L = ["# G82: Rủi ro theo nhãn \"dải EMA xếp thứ tự\" cho lệnh mua S07 — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g82-ribbon-label-risk.md`. Sổ mua S07 (gốc M30 + bồi S07A, tối đa 3 lệnh mở), XAUUSD, "
         "chi phí khắt khe G68. Nhãn: EMA21 > EMA55 > EMA100 và giá > EMA21 ở nến tín hiệu M30.", "",
         "## Phần 1 — nhãn trên tập con lệnh gốc", "",
         "| Kỳ | Có nhãn: n / R | Không nhãn: n / R |", "|---|---|---|"]
    better = 0
    for q in FOUR:
        a = [c["base"]["rh"] for c in cl if c["p"] == q and c["label"]]
        b = [c["base"]["rh"] for c in cl if c["p"] == q and not c["label"]]
        better += int(bool(a) and bool(b) and np.mean(a) > np.mean(b))
        L.append(f"| {v.NAMES[q]} | {len(a)} / {np.mean(a):+.3f} | {len(b)} / {np.mean(b):+.3f} |")
    r = np.array([c["base"]["rh"] for c in cl if c["p"] in FOUR])
    k = np.array([c["label"] for c in cl if c["p"] in FOUR])
    rng = np.random.default_rng(1)
    sims = np.array([r[rng.permutation(len(r))[:k.sum()]].mean() for _ in range(PERMS)])
    p = float(np.mean(sims >= r[k].mean()))
    # also the whole cluster (base + adds) by label
    ca = [c["total"] for c in cl if c["p"] in FOUR and c["label"]]
    cb = [c["total"] for c in cl if c["p"] in FOUR and not c["label"]]
    real = better >= 3 and p < 0.05
    L += ["", f"Gộp 2018–06/2026: có nhãn {k.sum()} lệnh / {r[k].mean():+.3f}R, không nhãn {(~k).sum()} / {r[~k].mean():+.3f}R; "
          f"tốt hơn ở {better}/4 kỳ; hoán vị p = {p:.3f}. Cả cụm (gốc + bồi): có nhãn {np.mean(ca):+.2f}R/cụm, không nhãn {np.mean(cb):+.2f}.",
          "", f"**Phần 1: nhãn {'có thật' if real else 'KHÔNG đạt'}.**", ""]
    L += ["## Phần 2 — mức rủi ro", ""]
    res = {}
    for with_adds, title in ((True, "Sổ đầy đủ (gốc + bồi)"), (False, "Chỉ lệnh gốc")):
        L += [f"### {title}", "", "| Mức | Giai đoạn | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | 1 năm xấu (p10) | %/năm ÷ DD p90 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for plan in PLANS:
            for rn, keys in RANGES.items():
                s = risk_stats(legs_of(cl, plan, with_adds, keys))
                res[(with_adds, plan, rn)] = s
                L.append(f"| {plan} {PLANS[plan][0] * 100:.2f}% / {PLANS[plan][1] * 100:.2f}% | {rn} | {s['py']:+.0f}% | {s['dd']:.0f}% | "
                         f"{s['d90']:.0f}% | {s['c20']:.0f}% | {s['c30']:.0f}% | {s['p10']:+.0f}% | {s['ratio']:.2f} |")
        L.append("")
    passed = []
    if real:
        for plan in ("K1", "K3", "K2"):
            ok = all(res[(True, plan, rn)]["ratio"] > res[(True, "K0", rn)]["ratio"] and
                     res[(True, plan, rn)]["c30"] <= res[(True, "K0", rn)]["c30"] and
                     res[(True, plan, rn)]["py"] >= 0.85 * res[(True, "K0", rn)]["py"] for rn in RANGES)
            L.append(f"- {plan}: {'đạt' if ok else 'không đạt'}")
            if ok:
                passed.append(plan)
    within = [x for x in passed if x in ("K1", "K3")]
    pick = (max(within, key=lambda x: res[(True, x, "07/2021–06/2026")]["ratio"]) if within else
            ("K2" if "K2" in passed else None))
    L += ["", f"**Kết luận theo luật: {'chọn ' + pick if pick else 'giữ K0 (1,5% mọi lệnh)'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
