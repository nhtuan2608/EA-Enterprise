"""G86: merged S07+ book, candle-context labels on S07, and a candle-only base-break setup (CB).
Pre-registered plan: docs/superpowers/plans/2026-10-10-g86-merge-candle-context.md. MT5 data only.

  python g86_merge_candles.py
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g70_pyramid as gp  # noqa: E402
import g74_pullback_adds as p4  # noqa: E402
import g81_relaxed as r81  # noqa: E402
import g82_label_risk as g82  # noqa: E402
import g85_sweep as g85  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g86-merge-candle-context.md"
FOUR = ("pre", "train", "validate", "test")
KEYS = ("pre", "train", "validate", "test", "examples")
RANGES = {"09/2018–06/2026": FOUR, "07/2021–06/2026": ("train", "validate", "test")}
KCTX = {"M15": 16, "M30": 8, "H1": 4}
SEC = {"M15": 900, "M30": 1800, "H1": 3600}


# ---------------------------------------------------------------------------
# candle arrays
# ---------------------------------------------------------------------------
def candles(D):
    if "cd" in D:
        return D["cd"]
    o, h, l, c, atr = D["o"], D["h"], D["l"], D["c"], D["atr"]
    n = len(c)
    rng = np.maximum(h - l, 1e-9)
    body = c - o
    po, pc_ = np.r_[o[0], o[:-1]], np.r_[c[0], c[:-1]]
    ph, pl = np.r_[h[0], h[:-1]], np.r_[l[0], l[:-1]]
    cd = dict(
        big=rng >= 1.5 * atr, narrow=rng <= 0.5 * atr, doji=np.abs(body) <= 0.15 * rng, inside=(h <= ph) & (l >= pl),
        up=body > 0, dn=body < 0,
        eng_up=(body > 0) & (pc_ < po) & (c >= po) & (o <= pc_),
        eng_dn=(body < 0) & (pc_ > po) & (c <= po) & (o >= pc_),
        marub=(np.abs(body) >= 0.7 * rng) & (rng >= 1.2 * atr),
        wick_top=(h - np.maximum(o, c)) >= 0.5 * rng, wick_bot=(np.minimum(o, c) - l) >= 0.5 * rng)
    hi48 = np.full(n, np.inf)
    lo48 = np.full(n, -np.inf)
    hi48[48:] = swv(h, 48).max(1)[:n - 48]
    lo48[48:] = swv(l, 48).min(1)[:n - 48]
    cd["new_hi"], cd["new_lo"] = h > hi48, l < lo48
    cd["hi48"], cd["lo48"] = hi48, lo48
    cd["stall"] = cd["narrow"] | cd["doji"] | cd["inside"]
    D["cd"] = cd
    return cd


def strong(cd, i, d):
    return bool((cd["eng_up"][i] or (cd["marub"][i] and cd["up"][i])) if d == 1 else (cd["eng_dn"][i] or (cd["marub"][i] and cd["dn"][i])))


def ctx_labels(D, i, d, K):
    cd = candles(D)
    rv = D["rv"]
    a = max(0, i - 3 * K)
    lab = {}
    # C1: climax against the trade (big + new extreme) followed by a strong candle with the trade
    c1 = False
    for j in range(a, i):
        against = (cd["big"][j] and ((cd["dn"][j] and cd["new_lo"][j]) if d == 1 else (cd["up"][j] and cd["new_hi"][j])))
        if against and any(strong(cd, k, d) or (cd["big"][k] and (cd["up"][k] if d == 1 else cd["dn"][k])) for k in range(j + 1, i + 1)):
            c1 = True
            break
    lab["C1"] = c1
    lab["C2"] = bool(cd["stall"][i - K:i].mean() >= 0.5)
    r = rv[a:i]
    mv = (cd["dn"][a:i] if d == 1 else cd["up"][a:i])
    lab["C3"] = bool(np.sum((~np.isnan(r)) & (np.nan_to_num(r) >= 1.8) & mv) >= 3)
    lab["C4"] = strong(cd, i, d)
    c5 = False
    for j in range(i - K, i + 1):
        if d == 1 and cd["wick_bot"][j] and cd["new_lo"][j] and D["c"][j] > cd["lo48"][j]:
            c5 = True
        if d == -1 and cd["wick_top"][j] and cd["new_hi"][j] and D["c"][j] < cd["hi48"][j]:
            c5 = True
    lab["C5"] = c5
    return lab


# ---------------------------------------------------------------------------
# Part A
# ---------------------------------------------------------------------------
def base_legs(book, exit_rule):
    D = r81.load("M30")
    sig = r81.signals(D, 1, "RB4", "K0", "DS")
    legs = {}
    for t in r81.book(D, sig, 1, exit_rule):
        e0, x = t["e0"], t["x"]
        t.update(tf="M30", sig=int(D["utc"][t["i"]]) + 1800, ein=int(D["utc"][e0]), eout=int(D["utc"][x]) + 1800,
                 entry=float(D["o"][e0] + D["sp"][e0]), bs=1800, U=D["utc"][e0:x + 1].copy(), C=D["c"][e0:x + 1].copy())
        legs[t["i"]] = t
    return legs, set(legs), D


def part_a():
    book = gp.BOOKS["Mua"]
    all_legs = p4.base_book(book)
    pool = sorted([L for tf in p4.TFP if tf != book["base"] for L in all_legs[tf][0].values()], key=lambda x: x["sig"])
    adds = lambda b: [L for L in pool if b["ein"] < L["sig"] < b["eout"]]
    books = {}
    for ex in ("X1", "X3"):
        legs, idx, D = base_legs(book, ex)
        al = dict(all_legs)
        al["M30"] = (legs, idx)
        cl = p4.assemble(book, al, adds)
        for c in cl:
            c["label"] = g82.labelled(D, c["base"]["i"])
        books[ex] = cl
    base_cfg = dict(exit="X1", lab=0.015, unl=0.015, add=0.015)
    changes = {"A1": dict(exit="X3"), "A2": dict(unl=0.010), "A3": dict(add=0.010)}
    names = {"A0": "A0 hiện tại", "A1": "A1 thoát X3", "A2": "A2 lệnh không nhãn 1,0%", "A3": "A3 bồi 1,0%"}

    def legs_of(cfg, keys):
        out = []
        for c in books[cfg["exit"]]:
            if c["p"] not in keys:
                continue
            b = c["base"]
            out.append((b["rh"], b["eout"], b["ein"], cfg["lab"] if c["label"] else cfg["unl"]))
            out += [(L["rh"], L["eout"], L["ein"], cfg["add"]) for L in c["add_legs"]]
        return sorted(out, key=lambda z: z[1])

    def stats(cfg):
        return {rn: g82.risk_stats(legs_of(cfg, keys)) for rn, keys in RANGES.items()}

    L = ["## Phần A — S07+ (sổ mua M30 + bồi S07A)", "",
         "Mỗi bước = nền đã giữ + một thay đổi (bước không đạt bị bỏ).", "",
         "| Bản | Giai đoạn | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | %/năm ÷ DD p90 |", "|---|---|---|---|---|---|---|---|"]

    def rows(label, st):
        for rn in RANGES:
            r = st[rn]
            L.append(f"| {label} | {rn} | {r['py']:+.0f}% | {r['dd']:.0f}% | {r['d90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% | {r['ratio']:.2f} |")

    cur_cfg, cur_name = dict(base_cfg), "A0 hiện tại"
    cur = stats(cur_cfg)
    rows(cur_name, cur)
    verdicts = []
    for s_, ch in changes.items():
        cfg = dict(cur_cfg, **ch)
        st = stats(cfg)
        label = f"{cur_name} + {names[s_][3:]}"
        rows(label, st)
        ok = all(st[rn]["ratio"] > cur[rn]["ratio"] and st[rn]["c30"] <= cur[rn]["c30"] and st[rn]["py"] >= 0.9 * cur[rn]["py"] for rn in RANGES)
        verdicts.append(f"- {label}: {'giữ' if ok else 'không giữ'}")
        if ok:
            cur_cfg, cur, cur_name = cfg, st, label
    L += [""] + verdicts
    # report only: adds at 1.0% on its own and the all-changes version
    for label, cfg in (("(tham khảo) A0 + bồi 1,0%", dict(base_cfg, add=0.010)),
                       ("(tham khảo) cả ba thay đổi", dict(base_cfg, exit="X3", unl=0.010, add=0.010))):
        L.append("")
        st = stats(cfg)
        L.append(f"{label}: " + "; ".join(f"{rn} {st[rn]['py']:+.0f}%/năm, DD p90 {st[rn]['d90']:.0f}%, chạm 30% {st[rn]['c30']:.0f}%, tỉ số {st[rn]['ratio']:.2f}" for rn in RANGES))
    cur = cur_name
    L += ["", f"**Phần A: bản cuối = {cur}.**", ""]
    return L


# ---------------------------------------------------------------------------
# Part B
# ---------------------------------------------------------------------------
def part_b(rng):
    L = ["## Phần B — nhãn bối cảnh nến trên tín hiệu S07", "", "Ô: có nhãn n / R — không nhãn n / R.", ""]
    passed = []
    for d, dn in ((1, "Mua"), (-1, "Bán")):
        L += [f"### {dn}", "", "| Khung | Nhãn | " + " | ".join(v.NAMES[q] for q in FOUR) + " | p | Đạt |", "|---|---|---|---|---|---|---|---|"]
        for tf in ("M15", "M30", "H1"):
            D = r81.load(tf)
            trs = [t for t in r81.book(D, r81.signals(D, d, "RB4", "K0", "DS"), d, "X1") if t["p"] in FOUR]
            labs = [ctx_labels(D, t["i"], d, KCTX[tf]) for t in trs]
            r = np.array([t["rh"] for t in trs])
            for lab in ("C1", "C2", "C3", "C4", "C5"):
                k = np.array([x[lab] for x in labs])
                if k.sum() < 10 or (~k).sum() < 10:
                    L.append(f"| {tf} | {lab} | quá ít lệnh có nhãn ({int(k.sum())}) | | | | | |")
                    continue
                per = {}
                for q in FOUR:
                    m = np.array([t["p"] == q for t in trs])
                    if m.any():
                        a, b = r[k & m], r[~k & m]
                        per[q] = (len(a), a.mean() if len(a) else np.nan, len(b), b.mean() if len(b) else np.nan)
                p = float(np.mean([r[rng.permutation(len(r))[:k.sum()]].mean() >= r[k].mean() for _ in range(5000)]))
                ok = (all(per[q][0] and per[q][2] and per[q][1] > per[q][3] for q in per) and
                      all(q in per and per[q][0] and per[q][1] >= 0.3 for q in ("validate", "test")) and p < 0.05 / 30)
                if ok:
                    passed.append(f"{dn} {tf} {lab}")
                cells = " | ".join(f"{per[q][0]} / {per[q][1]:+.2f} — {per[q][2]} / {per[q][3]:+.2f}" if q in per else "—" for q in FOUR)
                L.append(f"| {tf} | {lab} | {cells} | {p:.4f} | {'**ĐẠT**' if ok else ''} |")
        L.append("")
    L += [f"**Phần B: {'đạt — ' + ', '.join(passed) if passed else 'không nhãn nào đạt'}.**", ""]
    return L


# ---------------------------------------------------------------------------
# Part C
# ---------------------------------------------------------------------------
def cb_signals(D, d, ctx):
    cd = candles(D)
    E21, c, h, l = D["E"][21], D["c"], D["h"], D["l"]
    K = KCTX[D["tf"]]
    out = {}
    for i in range(400, len(c) - 1):
        if not strong(cd, i, d):
            continue
        if cd["stall"][i - 12:i].mean() < 0.5:
            continue
        top, bot = h[i - 12:i].max(), l[i - 12:i].min()
        if not ((c[i] > top and c[i] > E21[i]) if d == 1 else (c[i] < bot and c[i] < E21[i])):
            continue
        if ctx == "CTX":
            lab = ctx_labels(D, i, d, K)
            if not (lab["C1"] or lab["C3"] or lab["C5"]):
                continue
        out[i] = float(bot) if d == 1 else float(top)
    return out


def part_c():
    L = ["## Phần C — setup nến \"nền rồi nhấn chìm phá nền\" (CB)", ""]
    for d, dn in ((1, "Mua"), (-1, "Bán")):
        grid, books = {}, {}
        for tf in ("M15", "M30"):
            D = r81.load(tf)
            for ctx in ("NONE", "CTX"):
                sig = cb_signals(D, d, ctx)
                for ex in ("X1", "X2"):
                    trs = g85.book(D, sig, d, ex)
                    grid[(tf, ctx, ex)] = r81.per(trs)
                    books[(tf, ctx, ex)] = trs
        cell = lambda s: f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"
        L += [f"### {dn}", "", "| Khung | Bối cảnh | Thoát | " + " | ".join(v.NAMES[q] for q in KEYS) + " | Train+val |", "|---|---|---|---|---|---|---|---|---|"]
        for key, ps in grid.items():
            n, m = r81.tv(ps)
            L.append("| " + " | ".join(key) + " | " + " | ".join(cell(ps[q]) for q in KEYS) + f" | {n} / {m:+.3f} |")
        cands = [k for k, ps in grid.items() if ps["train"]["n"] and ps["validate"]["n"] and ps["train"]["exp"] > 0
                 and ps["validate"]["exp"] > 0 and r81.tv(ps)[0] >= 60]
        if cands:
            pick = max(cands, key=lambda k: r81.tv(grid[k])[1])
            tf, ctx, ex = pick
            ps, trs = grid[pick], books[pick]
            rm, p = r81.p_random(tf, d, ex, trs)
            other = grid[("M30" if tf == "M15" else "M15", ctx, ex)]
            checks = {"test > 0": ps["test"]["n"] and ps["test"]["exp"] > 0,
                      "2018–2021 ≥ 0 (nếu có)": (not ps["pre"]["n"]) or ps["pre"]["exp"] >= 0,
                      f"thắng ngẫu nhiên p < 0,05/8 (p = {p:.4f})": p < 0.05 / 8,
                      "khung còn lại dương train và validate": other["train"]["n"] and other["validate"]["n"] and
                      other["train"]["exp"] > 0 and other["validate"]["exp"] > 0}
            ok = all(checks.values())
            L += ["", f"Chọn: **{' / '.join(pick)}**."] + [f"- {c}: {'đạt' if x else 'KHÔNG'}" for c, x in checks.items()]
            L += [f"- Ví dụ: {g85.examples(trs, d, SEC[tf])}", "", f"**{dn}: {'ĐẠT' if ok else 'không đạt'}.**", ""]
        else:
            L += ["", f"**{dn}: không bộ nào dương ở train và validate với ≥ 60 lệnh.**", ""]
        L += [f"Ví dụ với M15 / NONE / X1 (tham khảo): {g85.examples(books[('M15', 'NONE', 'X1')], d, 900)}", ""]
    return L


def main():
    L = ["# G86: Gộp S07+ và bối cảnh nến — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g86-merge-candle-context.md`. XAUUSD, dữ liệu MT5, chi phí khắt khe G68.", ""]
    L += part_a()
    L += part_b(np.random.default_rng(86))
    L += part_c()
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
