"""G84: volatility-expansion + session + round-hour labels on S07, and the session-change sweep entry.
Pre-registered plan: docs/superpowers/plans/2026-10-10-g84-vol-session-sweep.md. MT5 data only.

  python g84_vol_session.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g73_early as e73  # noqa: E402
import g83_expansion as g83  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g84-vol-session-sweep.md"
TFS = ("M15", "M30", "H1")
LABELS = ("VX", "SES", "R00", "VX·SES", "VX·SES·R00")
FOUR = ("pre", "train", "validate", "test")
DEC3 = ("train", "validate", "test")
N_TESTS = 30
PERMS = 5000
SESSION_HOURS = set(range(6, 9)) | set(range(12, 15))
LIMIT_ATR, LIMIT_SUBS = 0.5, 4
PLANS = {"R0": 0.015, "R2": 0.02, "R25": 0.025, "R3": 0.03}


# ---------------------------------------------------------------------------
# Part A
# ---------------------------------------------------------------------------
def add_labels(rows):
    for tf in TFS:
        tr = [t for t in rows if t["tf"] == tf and t["p"] == "train"]
        med = {f: float(np.nanmedian([t[f] for t in tr])) for f in ("f3", "f4", "f16")}
        for t in rows:
            if t["tf"] != tf:
                continue
            vx = sum(1 for f in ("f3", "f4", "f16") if not np.isnan(t[f]) and t[f] > med[f]) >= 2
            ses = 11 <= t["hour"] <= 16
            r00 = (t["srv_in"] % 3600) == 0
            t["lab"] = {"VX": vx, "SES": ses, "R00": r00, "VX·SES": vx and ses, "VX·SES·R00": vx and ses and r00}


def audit(rows, tf, lab, rng):
    x = [t for t in rows if t["tf"] == tf and t["p"] in FOUR]
    if lab.endswith("R00") and tf == "H1":
        return None
    k = np.array([t["lab"][lab] for t in x])
    if k.sum() < 10 or (~k).sum() < 10:
        return None
    r = np.array([t["rh"] for t in x])
    sims = np.array([r[rng.permutation(len(r))[:k.sum()]].mean() for _ in range(PERMS)])
    per = {}
    for q in FOUR:
        m = np.array([t["p"] == q for t in x])
        if not m.any():
            continue
        a, b = r[k & m], r[~k & m]
        per[q] = (len(a), a.mean() if len(a) else np.nan, len(b), b.mean() if len(b) else np.nan)
    better_all = all(per[q][0] and per[q][2] and per[q][1] > per[q][3] for q in per)
    strong = all(q in per and per[q][0] and per[q][1] >= 0.5 for q in ("validate", "test"))
    p = float(np.mean(sims >= r[k].mean()))
    return dict(per=per, p=p, ok=better_all and strong and p < 0.05 / N_TESTS, n=int(k.sum()), all=len(r))


# ---------------------------------------------------------------------------
# Part B (sub-bar simulation, G73 framework)
# ---------------------------------------------------------------------------
def session_book(ctx, d, mode):
    P, S = ctx["P"], ctx["S"]
    g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = ctx["comp"], 20.0, 6.0, 10.0
    sigs = [i for i, dd in g.signals(P) if dd == d and (d == -1 or P["h4_side"][i] == d)]
    W, out, free = ctx["comp"], [], 0
    stats = {"session": 0, "filled": 0, "fill_bar_sl": 0}
    for i in sigs:
        if i < free or i + 1 >= len(P["t"]):
            continue
        e = ctx["first"][i + 1]
        if e < 0 or S["utc"][e] < ctx["start"]:
            continue
        hour = int(((P["utc"][i] + e73.SEC[ctx["main"]]) // 3600) % 24)
        sess = hour in SESSION_HOURS
        a0 = e73.anchor_start(P["t"], i, i - W)
        atr = P["atr"][i]
        anchor = (np.min(P["l"][a0:i + 1]) - 0.1 * atr) if d == 1 else (np.max(P["h"][a0:i + 1]) + 0.1 * atr)
        tr = None
        if mode == "LQ" and sess:
            stats["session"] += 1
            L = P["c"][i] - d * LIMIT_ATR * atr
            for k in range(e, min(e + LIMIT_SUBS, len(S["t"]) - 1)):
                sp = S["sp"][k]
                if d == 1 and S["l"][k] + sp <= L:
                    fill = min(L, S["o"][k] + sp)
                elif d == -1 and S["h"][k] >= L:
                    fill = max(L, S["o"][k])
                else:
                    continue
                dist = d * (fill - anchor)
                if dist <= 0 or dist > 4.0 * atr:
                    break
                dist = max(dist, atr)
                tr = e73.finish(ctx, e73.walk(ctx, k, fill, d, dist, fill_bar=True), i, atr, "LQ")
                stats["filled"] += 1
                stats["fill_bar_sl"] += int(tr["x"] == k and tr["reason"] == "SL")
                break
            if tr is None:
                continue
        else:
            entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
            dist = d * (entry - anchor)
            if dist > 4.0 * atr:
                continue
            dist = max(dist, atr)
            tr = e73.finish(ctx, e73.walk(ctx, e, entry, d, dist), i, atr, "MK")
        tr["sess"] = sess
        out.append(tr)
        free = ctx["par"][tr["x"]] + 1 + ctx["cool"]
    return out, stats


def sess_stats(trs, q):
    x = [t["rh"] for t in trs if t["sess"] and t["p"] == q]
    return len(x), (float(np.mean(x)) if x else 0.0), float(np.sum(x)) if x else 0.0


# ---------------------------------------------------------------------------
# Part C
# ---------------------------------------------------------------------------
def risk(trs, lab, plan, keys):
    legs = sorted([(t["rh"], t["srv_out"], PLANS[plan] if t["lab"][lab] else 0.015) for t in trs if t["p"] in keys], key=lambda z: z[1])
    t0 = min(t["srv_in"] for t in trs if t["p"] in keys)
    yrs = (legs[-1][1] - t0) / (365.25 * 86400)
    eq, dd = g83.path(legs)
    n = max(10, int(len(legs) / yrs))
    rng = np.random.default_rng(84)
    res = [g83.path(legs[s:s + n]) for s in rng.integers(0, max(1, len(legs) - n), 3000)]
    dds = np.array([x[1] for x in res])
    py = (eq ** (1 / yrs) - 1) * 100
    d90 = float(np.percentile(dds, 90)) * 100
    return dict(py=py, dd=dd * 100, d90=d90, c20=float(np.mean(dds >= 0.2)) * 100, c30=float(np.mean(dds >= 0.3)) * 100,
                ratio=py / max(d90, 1e-9))


def main():
    rng = np.random.default_rng(84)
    L = ["# G84: Biến động nở + giờ phiên + nến tròn giờ, và chờ quét khi giao phiên — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g84-vol-session-sweep.md`. XAUUSD, S07 chuẩn, thoát E2X TP 8R, chi phí khắt khe G68. "
         "Ô: có nhãn n / R — không nhãn n / R.", "", "## Phần A — nhãn", ""]
    passed = []
    for d, dn in ((1, "Mua"), (-1, "Bán")):
        rows = [t for t in g83.collect(d) if t["tf"] in TFS]
        add_labels(rows)
        L += [f"### {dn}", "", "| Khung | Nhãn | " + " | ".join(v.NAMES[q] for q in FOUR) + " | p | Đạt |", "|---|---|---|---|---|---|---|---|"]
        for tf in TFS:
            for lab in LABELS:
                a = audit(rows, tf, lab, rng)
                if a is None:
                    continue
                cells = " | ".join(f"{a['per'][q][0]} / {a['per'][q][1]:+.2f} — {a['per'][q][2]} / {a['per'][q][3]:+.2f}" if q in a["per"] else "—"
                                   for q in FOUR)
                L.append(f"| {tf} | {lab} | {cells} | {a['p']:.4f} | {'**ĐẠT**' if a['ok'] else ''} |")
                if a["ok"]:
                    passed.append((d, dn, tf, lab, rows))
        L.append("")
    L += [f"**Phần A: {'đạt — ' + ', '.join(f'{dn} {tf} {lab}' for _, dn, tf, lab, _ in passed) if passed else 'không nhãn nào đạt'}.**", ""]

    L += ["## Phần B — chờ quét khi giao phiên (M30, nến nhỏ M15; kiểm tra M5 từ 05/2024)", ""]
    for sub in ("M15", "M5"):
        ctx = e73.context("M30", sub)
        L += [f"### Nến nhỏ {sub}", "", "| Chiều | Cách vào | Tín hiệu giao phiên: train | validate | test | Toàn sổ: tổng R train+val+test | Khớp lệnh chờ | Chạm SL ngay nến khớp |",
              "|---|---|---|---|---|---|---|---|"]
        for d, dn in ((1, "Mua"), (-1, "Bán")):
            res = {}
            for mode in ("MK", "LQ"):
                trs, st = session_book(ctx, d, mode)
                res[mode] = trs
                cells = " | ".join((lambda n, m, s: f"{n} / {m:+.2f} / {s:+.1f}" if n else "—")(*sess_stats(trs, q)) for q in DEC3)
                tot = sum(t["rh"] for t in trs if t["p"] in DEC3)
                fill = f"{st['filled']}/{st['session']}" if mode == "LQ" else "—"
                fsl = f"{st['fill_bar_sl']}" if mode == "LQ" else "—"
                L.append(f"| {dn} | {mode} | {cells} | {tot:+.1f} | {fill} | {fsl} |")
            if sub == "M15":
                ok = all(sess_stats(res["LQ"], q)[2] >= sess_stats(res["MK"], q)[2] and sess_stats(res["LQ"], q)[1] > sess_stats(res["MK"], q)[1]
                         for q in DEC3)
                L.append(f"| {dn} | **LQ thay MK?** | {'ĐẠT' if ok else 'không'} | | | | | |")
        L.append("")
    L.append("Ô tín hiệu giao phiên: số lệnh / R mỗi lệnh / tổng R.")
    L.append("")

    L += ["## Phần C — rủi ro theo nhãn (sổ lệnh gốc M30, không bồi)", ""]
    m30 = [x for x in passed if x[2] == "M30" and x[0] == 1]
    if not m30:
        L += ["Không có nhãn mua M30 nào đạt Phần A → không xét mức rủi ro cao hơn. Giữ 1,5%.", ""]
    else:
        _, dn, tf, lab, rows = m30[0]
        trs = [t for t in rows if t["tf"] == "M30"]
        L += [f"Nhãn: {lab}.", "", "| Mức | Giai đoạn | %/năm | DD lớn nhất | DD p90 | Chạm 20% | Chạm 30% | Tỉ số |", "|---|---|---|---|---|---|---|---|"]
        res = {}
        for plan in PLANS:
            for rn, keys in g83.RANGES.items():
                s = risk(trs, lab, plan, keys)
                res[(plan, rn)] = s
                L.append(f"| {plan} | {rn} | {s['py']:+.0f}% | {s['dd']:.0f}% | {s['d90']:.0f}% | {s['c20']:.0f}% | {s['c30']:.0f}% | {s['ratio']:.2f} |")
        acc = [pl for pl in ("R2", "R25", "R3") if all(res[(pl, rn)]["c30"] <= 5 and res[(pl, rn)]["d90"] <= 25 and
                                                       res[(pl, rn)]["ratio"] > res[("R0", rn)]["ratio"] for rn in g83.RANGES)]
        L += ["", f"**Phần C: {'chấp nhận ' + acc[-1] if acc else 'không mức nào đạt, giữ 1,5%'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
