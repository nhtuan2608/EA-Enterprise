"""G71: the sell side of the DMI + EMA compression setup with its own location and exits. Pre-registered plan:
docs/superpowers/plans/2026-10-09-g71-sell.md. MT5 data only.

  python g71_sell.py
"""
from __future__ import annotations

import itertools
import sys
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-09-g71-sell.md"
TFP = {"M15": (16, 8, 480), "M30": (8, 4, 240), "H1": (4, 2, 120), "H4": (8, 4, 240)}
LOCS = {"L0": "không lọc", "L1": "đẩy lên thất bại (vượt đỉnh 48 nến trước)", "L2": "chạm cản EMA200 H4"}
EXITS = {"X1": ("E2", 8.0, "EMA55, TP 8R"), "X2": ("E2X", 8.0, "EMA55→EMA100 sau 3R, TP 8R"), "X3": ("E2", 2.0, "EMA55, TP 2R"),
         "X4": ("E2", 3.0, "EMA55, TP 3R"), "X5": ("E1", 8.0, "EMA21 khi ADX giảm, TP 8R")}
ALPHA = 0.05 / 60


def params(tf, loc, ex, **over):
    comp, cool, hold = TFP[tf]
    p = dict(v.C0, tf=tf, comp=comp, cool=cool, hold=hold, loc=loc, ex=ex)
    p.update(over)
    return p


def loc_ok(D, i, loc, comp):
    if loc == "L0":
        return True
    w0 = i - comp
    top = float(np.max(D["h"][w0:i + 1]))
    if loc == "L1":
        prev = D["h"][max(0, w0 - 48):w0]
        return len(prev) > 0 and top > float(np.max(prev))
    return D["h4_val"][i] > 0 and top >= D["h4_val"][i] - 0.5 * D["atr"][i]


def rows(p):
    v.configure(p)
    D = g.load("XAUUSD")
    sg = [(i, d) for i, d in g.signals(D) if d == -1 and g.block_ok(D, i, d, "B6") and loc_ok(D, i, p["loc"], p["comp"])]
    ex, tp, _ = EXITS[p["ex"]]
    out = g.trades("XAUUSD", ex, tp, None, sg)
    for t in out:
        t["p"] = v.period(t)
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
    return [t for t in out if t["p"] != "none"]


def grid_job(key):
    tf, loc, ex = key
    trs = rows(params(tf, loc, ex))
    return key, v.per(trs)


def nb_job(arg):
    p, x = arg
    q = dict(p, adx_low=x[0], di_gap=x[1], rise=x[2], comp=x[3])
    return x, v.per(rows(q))


def rand_job(arg):
    p, job = arg
    v.configure(p)
    return g.random_job(job)


def main():
    keys = [(tf, loc, ex) for tf in TFP for loc in LOCS for ex in EXITS]
    with Pool(12) as pool:
        res = dict(pool.map(grid_job, keys))
    L = ["# G71: Lệnh bán riêng cho setup nén → bung DMI + EMA (XAUUSD) — kết quả", "",
         "Kế hoạch đăng ký trước: `plans/2026-10-09-g71-sell.md`. Chỉ dữ liệu MT5. Ô: số lệnh / R trung bình mỗi lệnh (sau phí).", "",
         "## 1. Lưới 60 bộ", "", "| Khung | Vị trí | Thoát | " + " | ".join(v.NAMES[k] for k in v.KEYS) + " | Train+val |",
         "|" + "---|" * (len(v.KEYS) + 4)]
    cands = []
    for key in keys:
        ps = res[key]
        n = ps["train"]["n"] + ps["validate"]["n"]
        tv = (ps["train"]["total"] + ps["validate"]["total"]) / n if n else 0.0
        L.append(f"| {key[0]} | {key[1]} | {key[2]} | " + " | ".join(v.cell(ps[k]) for k in v.KEYS) + f" | {n} / {tv:+.3f} |")
        if ps["train"]["exp"] > 0 and ps["validate"]["exp"] > 0 and n >= 60:
            cands.append((tv, key))
    both = sum(1 for k in keys if all(res[k][x]["exp"] > 0 for x in ("train", "validate", "test")))
    L += ["", f"Bộ dương ở cả train, validate và test: {both}/60. Bộ đủ điều kiện chọn (dương train và validate, ≥ 60 lệnh): {len(cands)}.", ""]
    if not cands:
        L += ["**Không có bộ nào dương ở cả train và validate với ≥ 60 lệnh → bên bán không đạt; giữ SHADOW.**"]
        REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
        sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
        return
    _, best = max(cands)
    p = params(*best)
    trs = rows(p)
    v.configure(p)
    D = g.load("XAUUSD")
    for t in trs:
        t["rh"] = h.harsh(t, D)
    ps, ph = v.per(trs), v.per(trs, "rh")
    dec = [t for t in trs if t["p"] in ("train", "validate", "test")]
    real = float(np.mean([t["r"] for t in dec]))
    ex, tp, _ = EXITS[p["ex"]]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(p, ("XAUUSD", dec, ex, tp, None, 7100 + k, 20)) for k in range(10)]) for m in ch]
        comps = sorted({max(2, int(round(p["comp"] * f))) for f in (0.75, 1.0, 1.25)})
        nb = pool.map(nb_job, [(p, x) for x in itertools.product((18.0, 20.0, 22.0), (4.0, 6.0, 8.0), (8.0, 10.0, 12.0), comps)])
    p_rand = float(np.mean(np.array(sims) >= real))
    has_pre = ps["pre"]["n"] > 0
    nb_ok = sum(1 for _, q in nb if all(q[k]["exp"] > 0 for k in v.FOUR if k != "pre" or has_pre))
    all_h, _ = v.pooled(trs, v.FOUR, key="rh")
    checks = {"dương ở 2018–2021 (nếu có) và test": (ps["pre"]["exp"] > 0 or not has_pre) and ps["test"]["exp"] > 0,
              f"ngẫu nhiên p < {ALPHA:.4f}": p_rand < ALPHA,
              "khớp khắt khe > 0 (toàn kỳ và test)": all_h > 0 and ph["test"]["exp"] > 0,
              "≥ 60% lân cận dương 4 kỳ": nb_ok / len(nb) >= 0.6}
    tf, loc, exk = best
    L += [f"## 2. Bộ được chọn: {tf}, {LOCS[loc]}, thoát {EXITS[exk][2]}", "",
          "| | " + " | ".join(v.NAMES[k] for k in v.KEYS) + " |", "|" + "---|" * (len(v.KEYS) + 1),
          "| Thường | " + " | ".join(v.cell(ps[k]) for k in v.KEYS) + " |",
          "| Khớp khắt khe | " + " | ".join(v.cell(ph[k]) for k in v.KEYS) + " |", "",
          f"- Ngẫu nhiên: TB {np.mean(sims):+.3f}R, p = {p_rand:.3f}; lân cận dương 4 kỳ {nb_ok}/{len(nb)}; khớp khắt khe toàn kỳ {all_h:+.3f}R.", ""]
    L += [f"- {k}: {'ĐẠT' if ok else 'KHÔNG ĐẠT'}" for k, ok in checks.items()]
    passed = all(checks.values())
    L += ["", f"**Kết luận: bên bán {'ĐẠT' if passed else 'KHÔNG đạt'} tiêu chí.**", ""]
    allp = [t for t in trs if t["p"] in v.FOUR]
    st = g.stats([t["r"] for t in allp])
    years = defaultdict(list)
    for t in trs:
        years[datetime.fromtimestamp(t["utc"], timezone.utc).year].append(t["r"])
    L += [f"- Toàn kỳ {st['n']} lệnh, {st['exp']:+.3f}R/lệnh, thắng {st['win']:.0%}, lệnh thắng TB {st['avg_win']:+.2f}R, DD {st['dd']:.1f}R. "
          f"Giữ lệnh trung vị {np.median([t['hold_h'] for t in allp]):.1f} giờ.",
          "- Theo năm: " + ", ".join(f"{y}: {len(x)} lệnh {np.mean(x):+.2f}R" for y, x in sorted(years.items())), "",
          "| Rủi ro | %/năm | DD lớn nhất | 1 năm: trung vị | 1 năm: p10 | DD p90 1 năm | Chạm DD 10% | Chạm DD 20% |",
          "|---|---|---|---|---|---|---|---|", h.risk_line(allp, 0.015), "", "Ví dụ của người dùng:", ""]
    L += [f"- {x}" for x in v.examples(trs)[:2]]
    if passed:
        import g70_cap as c
        import g70_pyramid as pp
        book = pp.BOOKS["Mua"]
        legs = {k: pp.legs_for(k, book["rule"], book["side"]) for k in pp.TFP}
        buys = c.capped(pp.clusters(book, legs, "other", False))
        sells = [{"p": t["p"], "utc": t["utc"], "legs": [(t["r"], t["out_utc"], int(t["utc"]), tf)], "total": t["r"], "adds": 0}
                 for t in rows(p)]
        L += ["", "## 3. Hai chiều: sổ mua đã chốt (M30 + bồi khung khác, tối đa 3 lệnh mở) + bên bán này, 1,5%/lệnh", "",
              "| Danh mục | DD (R) | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | Lệnh mở tối đa |", "|---|---|---|---|---|---|---|---|"]
        for name, cl in (("Chỉ mua (B)", buys), ("Chỉ bán", sells), ("Mua (B) + bán", buys + sells)):
            r = pp.risk_stats(cl)
            L.append(f"| {name} | {r['dd_r']:.1f} | {r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% | {r['open']} |")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
