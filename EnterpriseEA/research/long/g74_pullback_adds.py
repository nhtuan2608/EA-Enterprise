"""G74: S07 adds on pullbacks to the EMAs / the old compression zone. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g74-pullback-adds.md. MT5 data only.

  python g74_pullback_adds.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g70_pyramid as gp  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g74-pullback-adds.md"
TFP = gp.TFP
MAX_ADDS, SPACING, CAP = 2, 3600, 3
TOUCH, ZONE_TOL = 0.1, 0.3
KINDS = ("P1", "P2", "P3", "P4")
KIND_NAMES = {"P1": "hồi EMA21 (khung gốc)", "P2": "hồi EMA55 (khung gốc)", "P3": "hồi mép vùng nén", "P4": "hồi EMA21 trên M15"}
N_TESTS = 8
RUNS = 200

_D: dict = {}


def data(tf, rule):
    """Bars of one timeframe with the indicators (g67 load), cached per timeframe."""
    if tf not in _D:
        comp, cool, hold = TFP[tf]
        v.configure(dict(rule, tf=tf, comp=comp, cool=cool, hold=hold))
        _D[tf] = g.load("XAUUSD")
    return _D[tf]


def harsh_leg(t, D):
    t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
    t["rh"] = h.harsh(t, D)
    return t


def base_book(book):
    """Base legs (cool-down filtered) and the other-timeframe S07 legs (A1 source)."""
    out = {}
    for tf in TFP:
        legs, idx = gp.legs_for(tf, book["rule"], book["side"])
        D = g.load("XAUUSD")
        _D[tf] = D
        for t in legs.values():
            harsh_leg(t, D)
        out[tf] = (legs, idx)
    return out


def walk_leg(D, e0, d, entry, dist, exit_rule, hold):
    """g67 walk from a given entry and stop distance (E2 / E2X, TP 8R)."""
    o, hh, ll, c, sp, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["E"]
    n = len(c)
    sl, tp = entry - d * dist, entry + d * 8.0 * dist
    best = entry
    exit_px, x, reason = None, None, "TIME"
    for j in range(e0, min(n, e0 + hold)):
        sj = sp[j] if d == -1 else 0.0
        bh, bl, bo = hh[j] + sj, ll[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px = min(sl, bo) if d == 1 else max(sl, bo)
            x, reason = j, "SL"
            break
        if (d == 1 and bh >= tp) or (d == -1 and bl <= tp):
            exit_px = max(tp, bo) if d == 1 else min(tp, bo)
            x, reason = j, "TP"
            break
        best = max(best, hh[j]) if d == 1 else min(best, ll[j] + sj)
        ema = E[100] if (exit_rule == "E2X" and d * (best - entry) >= 3 * dist) else E[55]
        if d * (c[j] - ema[j]) < 0 and j + 1 < n:
            x = j + 1
            exit_px = o[x] + (sp[x] if d == -1 else 0.0)
            reason = "TREND"
            break
    if exit_px is None:
        x = min(n - 1, e0 + hold - 1)
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - D["comm"] / dist
    return {"r": float(r), "e0": int(e0), "x": int(x), "risk": float(dist), "reason": reason,
            "sp_in": float(sp[e0]), "sp_out": float(sp[x])}


def span(D, b, bs):
    """Indices j of bars of D whose close falls inside the base trade and whose next open is before its exit."""
    u = D["utc"]
    a = int(np.searchsorted(u, b["ein"]))
    z = int(np.searchsorted(u, b["eout"] - bs))
    return a, min(z, len(u) - 2)


def pullback_legs(kind, conf, b, book, base_D):
    side, rule = book["side"], book["rule"]
    tf = "M15" if kind == "P4" else book["base"]
    D = data(tf, rule)
    comp, cool, hold = TFP[tf]
    bs = {"M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[tf]
    d = side
    o, hh, ll, c, atr, E, adx, pdi, mdi = D["o"], D["h"], D["l"], D["c"], D["atr"], D["E"], D["adx"], D["pdi"], D["mdi"]
    a, z = span(D, b, bs)
    if a >= z:
        return []
    if kind == "P3":
        W = TFP[book["base"]][0]
        i = b["i"]
        zone = float(np.max(base_D["h"][i - W:i + 1])) if d == 1 else float(np.min(base_D["l"][i - W:i + 1]))
    out = []
    touched, ext = False, None
    for j in range(max(a, 1), z):
        if kind in ("P1", "P4"):
            touch = d * (ll[j] if d == 1 else hh[j]) <= d * (E[21][j] + d * TOUCH * atr[j]) and d * (c[j] - E[55][j]) >= 0
            level = E[21][j]
        elif kind == "P2":
            touch = d * (ll[j] if d == 1 else hh[j]) <= d * (E[55][j] + d * TOUCH * atr[j]) and d * (c[j] - E[100][j]) >= 0
            level = E[55][j]
        else:
            touch = d * (ll[j] if d == 1 else hh[j]) <= d * (zone + d * ZONE_TOL * atr[j]) and d * (c[j] - (zone - d * ZONE_TOL * atr[j])) >= 0
            level = zone
        if touch:
            if not touched:
                touched, ext = True, (ll[j] if d == 1 else hh[j])
            else:
                ext = min(ext, ll[j]) if d == 1 else max(ext, hh[j])
        elif touched:
            ext = min(ext, ll[j]) if d == 1 else max(ext, hh[j])
        if not touched:
            continue
        trig = d * (c[j] - (hh[j - 1] if d == 1 else ll[j - 1])) > 0 and d * (c[j] - level) > 0
        if conf and trig:
            trig = (pdi[j] > mdi[j] if d == 1 else mdi[j] > pdi[j]) and adx[j] >= 20.0
        if not trig:
            continue
        touched = False
        e0 = j + 1
        entry = o[e0] + (D["sp"][e0] if d == 1 else 0.0)
        stop = ext - d * 0.1 * atr[j]
        dist = d * (entry - stop)
        if dist <= 0 or dist > 4.0 * atr[j]:
            continue
        dist = max(dist, 1.0 * atr[j])
        t = walk_leg(D, e0, d, entry, dist, rule["exit"], hold)
        t.update(d=d, tf=tf, i=j, sig=int(D["utc"][j]) + bs, ein=int(D["utc"][e0]), eout=int(D["utc"][t["x"]]) + bs,
                 dist_atr=float(dist / atr[j]), kind=kind)
        harsh_leg(t, D)
        out.append(t)
    return out


def assemble(book, all_legs, adds_for):
    """Clusters (G70 rules: base in profit at the add signal, spacing, 2 adds) and the 3-legs-open cap."""
    base_tf = book["base"]
    base_legs, base_idx = all_legs[base_tf]
    clusters = []
    for i in sorted(base_idx):
        b = base_legs[i]
        legs = [b]
        for L in sorted(adds_for(b), key=lambda x: x["sig"]):
            if len(legs) > MAX_ADDS:
                break
            if not (b["ein"] < L["sig"] < b["eout"]):
                continue
            if L["ein"] - legs[-1]["ein"] < SPACING or not gp.floating_ok(b, L["sig"]):
                continue
            legs.append(L)
        clusters.append((b, legs))
    out, open_exits = [], []
    for b, legs in sorted(clusters, key=lambda x: x[0]["utc"]):
        kept = []
        for j, L in enumerate(legs):
            if len([e for e in open_exits if e > L["ein"]]) >= CAP:
                if j == 0:
                    break
                continue
            kept.append(L)
            open_exits.append(L["eout"])
        if kept:
            out.append({"p": b["p"], "utc": b["utc"], "legs": [(L["rh"], L["eout"], L["ein"], L["tf"]) for L in kept],
                        "total": sum(L["rh"] for L in kept), "adds": len(kept) - 1, "add_legs": kept[1:], "base": b})
    return out


def add_stats(cl):
    s = {}
    for k in v.KEYS:
        x = [L["rh"] for c in cl if c["p"] == k for L in c["add_legs"]]
        s[k] = (len(x), float(np.mean(x)) if x else 0.0)
    return s


def random_p(cl, book, real_mean):
    """Random add timing: a random bar inside a random base trade of the same period while the base is in profit."""
    adds = [L for c in cl for L in c["add_legs"] if c["p"] in ("train", "validate", "test")]
    if len(adds) < 10:
        return float("nan"), float("nan")
    by_p = {}
    for c in cl:
        by_p.setdefault(c["p"], []).append(c["base"])
    rng = np.random.default_rng(74)
    means = []
    period_of = {id(L): c["p"] for c in cl for L in c["add_legs"]}
    for _ in range(RUNS):
        rs = []
        for L in adds:
            D = _D[L["tf"]]
            bs = {"M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[L["tf"]]
            comp, cool, hold = TFP[L["tf"]]
            for _try in range(20):
                b = by_p[period_of[id(L)]][int(rng.integers(len(by_p[period_of[id(L)]])))]
                a, z = span(D, b, bs)
                if z - a < 2:
                    continue
                j = int(rng.integers(a, z))
                if not gp.floating_ok(b, int(D["utc"][j]) + bs):
                    continue
                e0 = j + 1
                d = L["d"]
                entry = D["o"][e0] + (D["sp"][e0] if d == 1 else 0.0)
                t = walk_leg(D, e0, d, entry, L["dist_atr"] * D["atr"][j], book["rule"]["exit"], hold)
                rs.append(harsh_leg(t, D)["rh"])
                break
        means.append(float(np.mean(rs)))
    return float(np.mean(means)), float(np.mean(np.array(means) >= real_mean))


def zones(book, all_legs):
    """Part 1 (descriptive): pullbacks during the base trades."""
    base_tf = book["base"]
    D = _D[base_tf]
    base_legs, base_idx = all_legs[base_tf]
    W = TFP[base_tf][0]
    bs = {"M30": 1800, "H1": 3600}[base_tf]
    rows = {k: [] for k in ("EMA21", "EMA55", "EMA100", "Vùng")}
    n = 0
    for i in sorted(base_idx):
        b = base_legs[i]
        if b["p"] not in v.FOUR:
            continue
        n += 1
        d = b["d"]
        a, z = span(D, b, bs)
        zone = float(np.max(D["h"][i - W:i + 1])) if d == 1 else float(np.min(D["l"][i - W:i + 1]))
        for name in rows:
            for j in range(a, z + 1):
                lv = {"EMA21": D["E"][21][j], "EMA55": D["E"][55][j], "EMA100": D["E"][100][j], "Vùng": zone}[name]
                tol = (ZONE_TOL if name == "Vùng" else TOUCH) * D["atr"][j]
                px = D["l"][j] if d == 1 else D["h"][j]
                if d * (px - (lv + d * tol)) <= 0:
                    mfe_at = max(0.0, max(d * (D["h"][k] - b["entry"]) if d == 1 else d * (D["l"][k] - b["entry"])
                                          for k in range(a, j + 1)) / b["risk"])
                    after = D["h"][j:z + 1].max() - D["l"][j] if d == 1 else D["h"][j] - D["l"][j:z + 1].min()
                    rows[name].append((j - a + 1, mfe_at, after / D["atr"][j], b["rh"]))
                    break
    L = [f"Lệnh gốc 2018–06/2026: {n}.", "",
         "| Vùng chạm | % lệnh gốc có chạm | Trung vị: chạm sau (nến) | Lệnh gốc đã lời lúc chạm (R, trung vị) | Giá đi tiếp sau chạm (ATR, trung vị) | R lệnh gốc khi có chạm | R lệnh gốc khi không chạm |",
         "|---|---|---|---|---|---|---|"]
    all_r = {b["i"]: b["rh"] for i, b in base_legs.items() if i in base_idx and b["p"] in v.FOUR}
    for name, xs in rows.items():
        if not xs:
            continue
        touched_r = [x[3] for x in xs]
        none_r = list(all_r.values())
        n_none = len(none_r) - len(touched_r)
        none_txt = f"{(sum(none_r) - sum(touched_r)) / n_none:+.2f} ({n_none})" if n_none >= 10 else f"— ({n_none} lệnh)"
        L.append(f"| {name} | {len(xs) / max(n, 1):.0%} | {np.median([x[0] for x in xs]):.0f} | {np.median([x[1] for x in xs]):+.2f} | "
                 f"{np.median([x[2] for x in xs]):.1f} | {np.mean(touched_r):+.2f} | {none_txt} |")
    return L


def cell(s):
    return f"{s[0]} / {s[1]:+.2f} / {s[3]}" if s[0] else "—"


def main():
    out = ["# G74: Bồi lệnh S07 khi giá hồi về EMA / vùng — kết quả", "",
           "Kế hoạch: `plans/2026-10-10-g74-pullback-adds.md`. XAUUSD, dữ liệu MT5, chi phí khắt khe G68 cho mọi lệnh, "
           "rủi ro 1,5% mỗi lệnh, tối đa 2 lệnh bồi và 3 lệnh mở. Ô kỳ: số lệnh gốc / tổng R mỗi lệnh gốc (gồm bồi) / số lệnh bồi.", ""]
    for name, book in gp.BOOKS.items():
        _D.clear()
        all_legs = base_book(book)
        base_D = _D[book["base"]]
        others = [tf for tf in TFP if tf != book["base"]]
        pool = sorted([L for tf in others for L in all_legs[tf][0].values()], key=lambda x: x["sig"])
        variants = {"A0 không bồi": lambda b: [],
                    "A1 hiện tại (S07 khung khác)": lambda b: [L for L in pool if b["ein"] < L["sig"] < b["eout"]]}
        for kind in KINDS:
            for conf in (False, True):
                variants[f"{kind}{'C1' if conf else 'C0'} {KIND_NAMES[kind]}"] = \
                    (lambda kk, cc: (lambda b: pullback_legs(kk, cc, b, book, base_D)))(kind, conf)
        res = {vn: assemble(book, all_legs, fn) for vn, fn in variants.items()}
        out += [f"## Sổ {name} (lệnh gốc {book['base']})", "", "### Phần 1 — giá hồi về đâu trong lúc lệnh gốc chạy (mô tả)", ""]
        out += zones(book, all_legs)
        out += ["", "### Phần 2 — các cách bồi", "",
                "| Bản | " + " | ".join(v.NAMES[k] for k in v.KEYS) + " | Lệnh bồi: R/lệnh train / validate / test | "
                "DD (R) | %/năm | DD p90 1 năm | Chạm 20% | Chạm 30% | Ngẫu nhiên (TB / p) |",
                "|" + "---|" * (len(v.KEYS) + 7)]
        sums, info = {}, {}
        for vn, cl in res.items():
            s = gp.summary(cl)
            a = add_stats(cl)
            r = gp.risk_stats(cl)
            sums[vn], info[vn] = s, (a, r)
            dec = [L["rh"] for c in cl if c["p"] in ("train", "validate", "test") for L in c["add_legs"]]
            rm, p = (random_p(cl, book, float(np.mean(dec))) if (name == "Mua" and vn[:2] not in ("A0",) and dec) else
                     (float("nan"), float("nan")))
            info[vn] = (a, r, p)
            out.append(f"| {vn} | " + " | ".join(cell(s[k]) for k in v.KEYS) +
                       f" | {a['train'][1]:+.2f} / {a['validate'][1]:+.2f} / {a['test'][1]:+.2f} | "
                       f"{r['dd_r']:.1f} | {r['per_year']:+.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% | "
                       f"{'—' if np.isnan(p) else f'{rm:+.2f} / {p:.3f}'} |")
        if name == "Mua":
            a1 = sums["A1 hiện tại (S07 khung khác)"]
            a1_dd = info["A1 hiện tại (S07 khung khác)"][1]["dd90"]
            cand = [vn for vn in sums if vn[0] == "P" and sums[vn]["train"][1] > a1["train"][1] and sums[vn]["validate"][1] > a1["validate"][1]]
            out += ["", f"Ứng viên (tổng R/lệnh gốc > A1 ở cả train và validate): {', '.join(cand) if cand else 'không có'}."]
            if cand:
                pick = max(cand, key=lambda vn: sums[vn]["train"][2] + sums[vn]["validate"][2])
                s, (a, r, p) = sums[pick], info[pick]
                checks = {"test ≥ A1": s["test"][1] >= a1["test"][1],
                          "pre ≥ A1": True if pick.startswith("P4") else s["pre"][1] >= a1["pre"][1],
                          "lệnh bồi dương train/validate/test": all(a[k][0] and a[k][1] > 0 for k in ("train", "validate", "test")),
                          "DD p90 ≤ A1 + 2 điểm": r["dd90"] <= a1_dd + 2.0,
                          "thắng ngẫu nhiên": (not np.isnan(p)) and p < 0.05 / N_TESTS}
                ok = all(checks.values())
                out += [f"Chọn: **{pick}**. " + "; ".join(f"{k}: {'đạt' if x else 'KHÔNG'}" for k, x in checks.items()) + ".",
                        f"**Kết luận theo luật: {'thay A1 bằng ' + pick if ok else 'giữ A1 (bồi bằng tín hiệu S07 khung khác)'}.**"]
            else:
                out += ["**Kết luận theo luật: giữ A1 (bồi bằng tín hiệu S07 khung khác).**"]
        else:
            out += ["", "Sổ bán chỉ để mô tả (bên bán đang SHADOW, chưa có lợi thế đã kiểm chứng)."]
        out.append("")
        sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8")); sys.stdout.flush()
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
