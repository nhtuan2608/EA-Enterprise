"""G70: pyramiding the DMI + EMA compression setup across timeframes. Pre-registered plan:
docs/superpowers/plans/2026-10-09-g70-pyramid.md. MT5 data only.

  python g70_pyramid.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-09-g70-pyramid.md"
TFP = {"M15": (16, 8, 480), "M30": (8, 4, 240), "H1": (4, 2, 120), "H4": (8, 4, 240)}
BOOKS = {"Mua": dict(base="M30", side=1, rule=dict(v.C0, gap=True, exit="E2X")),
         "Bán": dict(base="H1", side=-1, rule=dict(v.C0, gap=False, exit="E2"))}
MAX_ADDS, SPACING = 2, 3600
VARIANTS = [("Không bồi", None, False), ("Bồi cùng khung", "same", False), ("Bồi cùng khung + BE", "same", True),
            ("Bồi khung khác", "other", False), ("Bồi khung khác + BE", "other", True),
            ("Bồi cả hai", "both", False), ("Bồi cả hai + BE", "both", True)]


def legs_for(tf, rule, side):
    comp, cool, hold = TFP[tf]
    p = dict(rule, tf=tf, comp=comp, cool=cool, hold=hold)
    v.configure(p)
    D = g.load("XAUUSD")
    sg = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6") and d == side]
    legs = {}
    for i, d in sg:
        tr = g.walk(D, i, d, p["exit"], 8.0, None)
        if tr is None:
            continue
        e0, x = tr["e0"], tr["x"]
        entry = D["o"][e0] + (D["sp"][e0] if d == 1 else 0.0)
        tr.update(tf=tf, sig=int(D["utc"][i]) + g.BAR_SEC, ein=int(D["utc"][e0]), eout=int(D["utc"][x]) + g.BAR_SEC,
                  entry=float(entry), bs=g.BAR_SEC, comm=D["comm"],
                  U=D["utc"][e0:x + 1].copy(), LO=D["l"][e0:x + 1].copy(),
                  HI=(D["h"][e0:x + 1] + D["sp"][e0:x + 1]).copy(), C=D["c"][e0:x + 1].copy())
        tr["p"] = v.period(tr)
        legs[i] = tr
    base_idx = {t["i"] for t in g.trades("XAUUSD", p["exit"], 8.0, None, sg)}
    return legs, base_idx


def floating_ok(b, ts):
    """Base leg is in profit at the close of a bar ending at ts."""
    k = np.nonzero(b["U"] + b["bs"] <= ts)[0]
    if len(k) == 0:
        return False
    return b["d"] * (b["C"][k[-1]] - b["entry"]) > 0


def be_r(leg, t_be):
    """R of a leg whose stop moved to its entry from t_be on (one time)."""
    k_end = len(leg["U"]) - (2 if leg["reason"] == "TREND" else 1)
    for k in range(len(leg["U"])):
        if leg["U"][k] < t_be or k > k_end:
            continue
        hit = leg["LO"][k] <= leg["entry"] if leg["d"] == 1 else leg["HI"][k] >= leg["entry"]
        if hit:
            return -leg["comm"] / leg["risk"], int(leg["U"][k]) + leg["bs"]
    return leg["r"], leg["eout"]


def clusters(book, all_legs, source, be):
    base_tf, side = book["base"], book["side"]
    base_legs, base_idx = all_legs[base_tf]
    pool = []
    for tf, (lg, _) in all_legs.items():
        if source == "same" and tf != base_tf:
            continue
        if source == "other" and tf == base_tf:
            continue
        pool += list(lg.values())
    pool.sort(key=lambda x: x["sig"])
    out = []
    for i in sorted(base_idx):
        b = base_legs[i]
        legs = [b]
        if source:
            for L in pool:
                if len(legs) > MAX_ADDS:
                    break
                if not (b["ein"] < L["sig"] < b["eout"]) or (L["tf"] == base_tf and L["i"] == b["i"]):
                    continue
                if L["ein"] - legs[-1]["ein"] < SPACING or not floating_ok(b, L["sig"]):
                    continue
                legs.append(L)
        res = []
        for j, L in enumerate(legs):
            r, t_out = L["r"], L["eout"]
            if be and j + 1 < len(legs):
                r, t_out = be_r(L, legs[j + 1]["ein"])
            res.append((r, t_out, L["ein"], L["tf"]))
        out.append({"p": b["p"], "utc": b["utc"], "legs": res, "total": sum(x[0] for x in res), "adds": len(legs) - 1})
    return out


def summary(cl):
    s = {}
    for k in v.KEYS:
        c = [x for x in cl if x["p"] == k]
        s[k] = (len(c), float(np.mean([x["total"] for x in c])) if c else 0.0, sum(x["total"] for x in c),
                sum(x["adds"] for x in c))
    return s


def flat(cl, keys=v.FOUR):
    return sorted([leg for x in cl if x["p"] in keys for leg in x["legs"]], key=lambda z: z[1])


def risk_stats(cl, risk=0.015):
    legs = flat(cl)
    rs = np.array([z[0] for z in legs])
    if len(rs) < 10:
        return None
    eq = np.cumsum(rs)
    dd_r = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    yrs = (legs[-1][1] - legs[0][1]) / (365.25 * 86400)

    def path(r):
        e = pk = 1.0; dd = 0.0
        for x in r:
            e *= 1 + risk * x; pk = max(pk, e); dd = max(dd, 1 - e / pk)
        return e, dd
    e, dd = path(rs)
    n = max(10, int(len(rs) / yrs))
    rng = np.random.default_rng(70)
    res = [path(rs[s:s + n]) for s in rng.integers(0, max(1, len(rs) - n), 3000)]
    dds = np.array([x[1] for x in res]); rets = np.array([x[0] - 1 for x in res])
    events = sorted([(z[2], 1) for z in legs] + [(z[1], -1) for z in legs])
    cur = mx = 0
    for _, dlt in events:
        cur += dlt; mx = max(mx, cur)
    return dict(dd_r=dd_r, per_year=(e ** (1 / yrs) - 1) * 100, dd=dd * 100, med=np.median(rets) * 100,
                p10=np.percentile(rets, 10) * 100, dd90=np.percentile(dds, 90) * 100,
                c10=np.mean(dds >= 0.1) * 100, c20=np.mean(dds >= 0.2) * 100, c30=np.mean(dds >= 0.3) * 100, open=mx)


def main():
    L = ["# G70: Bồi lệnh cho setup nén → bung DMI + EMA — kết quả", "",
         "Kế hoạch đăng ký trước: `plans/2026-10-09-g70-pyramid.md`. Chỉ dữ liệu MT5, XAUUSD. Mỗi lệnh (gốc hoặc bồi) rủi ro 1R = 1,5%. "
         "Ô: số lệnh gốc / tổng R trung bình mỗi lệnh gốc (gồm lệnh bồi) / số lệnh bồi.", ""]
    for name, book in BOOKS.items():
        all_legs = {tf: legs_for(tf, book["rule"], book["side"]) for tf in TFP}
        res = {vn: clusters(book, all_legs, src, be) for vn, src, be in VARIANTS}
        sums = {vn: summary(c) for vn, c in res.items()}
        L += [f"## Sổ {name} (lệnh gốc {book['base']})", "",
              "| Bản | " + " | ".join(v.NAMES[k] for k in v.KEYS) + " | Tổng R train+val |",
              "|" + "---|" * (len(v.KEYS) + 2)]
        for vn in sums:
            s = sums[vn]
            tv = s["train"][2] + s["validate"][2]
            L.append(f"| {vn} | " + " | ".join(f"{s[k][0]} / {s[k][1]:+.2f} / {s[k][3]}" if s[k][0] else "—" for k in v.KEYS) +
                     f" | {tv:+.0f} |")
        L += ["", "Rủi ro 1,5% mỗi lệnh, lãi kép theo thứ tự đóng lệnh (2018–06/2026):", "",
              "| Bản | DD (R) | %/năm | DD lớn nhất | 1 năm: trung vị | 1 năm: p10 | DD p90 1 năm | Chạm 10% | Chạm 20% | Chạm 30% | Lệnh mở tối đa |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for vn, c in res.items():
            r = risk_stats(c)
            if r:
                L.append(f"| {vn} | {r['dd_r']:.1f} | {r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['med']:+.0f}% | {r['p10']:+.0f}% | "
                         f"{r['dd90']:.0f}% | {r['c10']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% | {r['open']} |")
        if name == "Mua":
            base = sums["Không bồi"]
            ok = [vn for vn in sums if vn != "Không bồi" and sums[vn]["train"][1] > base["train"][1]
                  and sums[vn]["validate"][1] > base["validate"][1]]
            pick = max(ok, key=lambda vn: sums[vn]["train"][2] + sums[vn]["validate"][2]) if ok else None
            L += ["", f"**Theo luật đăng ký trước: {pick or 'không bản bồi nào tốt hơn không bồi ở cả train và validate'}.**"]
            if pick:
                s = sums[pick]
                L += [f"Ngoài mẫu: 2018–2021 {s['pre'][1]:+.2f}R/lệnh gốc (không bồi {base['pre'][1]:+.2f}), "
                      f"test {s['test'][1]:+.2f} (không bồi {base['test'][1]:+.2f})."]
            by_tf = defaultdict(list)
            for c in res["Bồi cả hai"]:
                for leg in c["legs"][1:]:
                    by_tf[leg[3]].append(leg[0])
            L += ["", "Lệnh bồi theo khung nguồn (bản 'Bồi cả hai', không BE): " +
                  ", ".join(f"{tf} {len(x)} lệnh {np.mean(x):+.2f}R" for tf, x in sorted(by_tf.items())), ""]
        else:
            L += ["", "Sổ bán chỉ để mô tả (lệnh bán chưa có lợi thế đã kiểm chứng ở G69).", ""]
        sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8")); sys.stdout.flush()
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
