"""G85: liquidity sweep -> reclaim reversal setup (buy and sell), and the H4 filter after a sweep low for S07 buys.
Pre-registered plan: docs/superpowers/plans/2026-10-10-g85-sweep-reclaim.md. MT5 data only.

  python g85_sweep.py
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
import g81_relaxed as r81  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g85-sweep-reclaim.md"
CFG = {"M15": dict(N=48, K=12), "M30": dict(N=24, K=6)}
SEC = {"M15": 900, "M30": 1800}
RIB, EXITS, TIMES = ("E4", "E2"), ("X1", "X2", "X3"), ("T0", "TS", "TR")
KEYS = ("pre", "train", "validate", "test", "examples")
N_TESTS = 36
SESSION = set(range(23, 24)) | {0, 1} | set(range(6, 9)) | set(range(12, 15))
EXAMPLES = [("Bán 02/10", -1, "2026-10-02T18:00", "2026-10-03T01:00"), ("Bán 28/08", -1, "2026-08-28T00:00", "2026-08-28T23:59"),
            ("Bán 23/09", -1, "2026-09-23T04:00", "2026-09-23T12:00"), ("Mua 17/09", 1, "2026-09-17T03:00", "2026-09-17T16:00"),
            ("Mua 02/09", 1, "2026-09-02T08:00", "2026-09-02T20:00")]


def sweeps(D, d, N):
    """Bars that swept the N-bar extreme against the trade (sell: new high; buy: new low)."""
    hh, ll = D["h"], D["l"]
    n = len(hh)
    out = np.zeros(n, dtype=bool)
    from numpy.lib.stride_tricks import sliding_window_view as swv
    if d == -1:
        prior = np.full(n, np.inf)
        prior[N:] = swv(hh, N).max(1)[:n - N]
        out = hh > prior
    else:
        prior = np.full(n, -np.inf)
        prior[N:] = swv(ll, N).min(1)[:n - N]
        out = ll < prior
    out[:400] = False
    return out


def signals(D, d, rib, tfilt):
    tf = D["tf"]
    N, K = CFG[tf]["N"], CFG[tf]["K"]
    sw = sweeps(D, d, N)
    c, hh, ll, E, pdi, mdi, atr = D["c"], D["h"], D["l"], D["E"], D["pdi"], D["mdi"], D["atr"]
    n = len(c)
    sig = {}
    for s in np.nonzero(sw)[0]:
        close_utc = int(D["utc"][s]) + SEC[tf]
        if tfilt == "TS" and ((close_utc // 3600) % 24) not in SESSION:
            continue
        if tfilt == "TR" and (close_utc % 1800) != 0:
            continue
        for i in range(s + 1, min(s + K + 1, n - 1)):
            di_ok = (mdi[i] > pdi[i]) if d == -1 else (pdi[i] > mdi[i])
            back = (c[i] < ll[s]) if d == -1 else (c[i] > hh[s])
            if rib == "E4":
                rb = (c[i] < D["elo"][i]) if d == -1 else (c[i] > D["ehi"][i])
            else:
                rb = (c[i] < E[21][i] and c[i] < E[55][i]) if d == -1 else (c[i] > E[21][i] and c[i] > E[55][i])
            if di_ok and back and rb:
                ext = float(hh[s:i + 1].max()) if d == -1 else float(ll[s:i + 1].min())
                if i not in sig:
                    sig[i] = ext
                else:
                    sig[i] = max(sig[i], ext) if d == -1 else min(sig[i], ext)
                break
    return sig


def book(D, sig, d, ex):
    out, free = [], 0
    for i in sorted(sig):
        if i < free or i + 1 >= len(D["c"]):
            continue
        e0 = i + 1
        entry = D["o"][e0] + (D["sp"][e0] if d == 1 else 0.0)
        atr = D["atr"][i]
        stop = sig[i] + 0.1 * atr if d == -1 else sig[i] - 0.1 * atr
        dist = d * (entry - stop)
        if dist <= 0 or dist > 4.0 * atr:
            continue
        dist = max(dist, atr)
        t = r81.walk(D, int(i), d, ex, dist_override=dist / atr)
        if t is None:
            continue
        out.append(t)
        free = t["x"] + 1 + 4
    return out


def examples(trs, d, bar_sec):
    out = []
    for name, dd, a, z in EXAMPLES:
        if dd != d:
            continue
        a = datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        z = datetime.fromisoformat(z).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        hit = [t for t in trs if a <= t["utc"] <= z]
        if hit:
            t = hit[0]
            vn = datetime.fromtimestamp(t["utc"] + bar_sec + 7 * 3600, timezone.utc)
            out.append(f"{name}: vào {vn:%d/%m %H:%M} VN, {t['rh']:+.2f}R")
        else:
            out.append(f"{name}: không vào")
    return "; ".join(out)


def part_b(rng):
    L = ["## Phần B — lọc H4 với lệnh mua S07 sau cú quét đáy", "",
         "Tín hiệu mua S07 **bị lọc H4 chặn** (H4 dưới EMA200), chia theo có cú quét đáy trong 2W nến trước tín hiệu.", "",
         "| Khung | Kỳ | Có quét đáy: n / R | Không quét: n / R |", "|---|---|---|---|"]
    verdict = []
    for tf in ("M15", "M30"):
        D = r81.load(tf)
        W = r81.TF[tf]["comp"]
        g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = W, 20.0, 6.0, 10.0
        sig = [i for i, d in g.signals(D) if d == 1 and D["h4_side"][i] != 1]
        trs = r81.book(D, np.array(sig), 1, "X1")
        sw = sweeps(D, 1, CFG[tf]["N"])
        lab = {t["i"]: bool(sw[max(0, t["i"] - 2 * W):t["i"] + 1].any()) for t in trs}
        good = 0
        keys = [q for q in ("pre", "train", "validate", "test") if any(t["p"] == q for t in trs)]
        for q in keys:
            a = [t["rh"] for t in trs if t["p"] == q and lab[t["i"]]]
            b = [t["rh"] for t in trs if t["p"] == q and not lab[t["i"]]]
            ma, mb = (np.mean(a) if a else np.nan), (np.mean(b) if b else np.nan)
            good += int(bool(a) and ma > 0 and (not b or ma > mb))
            L.append(f"| {tf} | {v.NAMES[q]} | {len(a)} / {ma:+.3f} | {len(b)} / {mb:+.3f} |")
        x = [t for t in trs if t["p"] in keys]
        r = np.array([t["rh"] for t in x])
        k = np.array([lab[t["i"]] for t in x])
        p = float(np.mean([r[rng.permutation(len(r))[:k.sum()]].mean() >= r[k].mean() for _ in range(5000)])) if k.sum() else 1.0
        need = 3 if tf == "M30" else len(keys)
        ok = good >= need and p < 0.025
        verdict.append(ok)
        L.append(f"| {tf} | p hoán vị | {p:.3f} | {'**ĐẠT**' if ok else 'không'} |")
    L += ["", f"**Phần B: {'nới H4 khi vừa có cú quét đáy — đạt' if any(verdict) else 'giữ lọc H4'}.**", ""]
    return L


def main():
    L = ["# G85: Quét thanh khoản rồi đảo chiều (Sweep → Reclaim) — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g85-sweep-reclaim.md`. XAUUSD, chi phí khắt khe G68. Ô: số lệnh / R mỗi lệnh.", ""]
    for d, dn in ((-1, "Bán"), (1, "Mua")):
        grid, books = {}, {}
        for tf in ("M15", "M30"):
            D = r81.load(tf)
            for rib, tfilt in itertools.product(RIB, TIMES):
                sig = signals(D, d, rib, tfilt)
                for ex in EXITS:
                    trs = book(D, sig, d, ex)
                    grid[(tf, rib, ex, tfilt)] = r81.per(trs)
                    books[(tf, rib, ex, tfilt)] = trs
        L += [f"## {dn}", "", "| Khung | Dải EMA | Thoát | Giờ quét | " + " | ".join(v.NAMES[q] for q in KEYS) + " | Train+val |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        cell = lambda s: f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"
        for key, ps in grid.items():
            n, m = r81.tv(ps)
            L.append("| " + " | ".join(key) + " | " + " | ".join(cell(ps[q]) for q in KEYS) + f" | {n} / {m:+.3f} |")
        cands = [k for k, ps in grid.items() if ps["train"]["n"] and ps["validate"]["n"] and ps["train"]["exp"] > 0
                 and ps["validate"]["exp"] > 0 and r81.tv(ps)[0] >= 60]
        L += ["", f"Ứng viên: {len(cands)} / 36.", ""]
        if cands:
            pick = max(cands, key=lambda k: r81.tv(grid[k])[1])
            tf, rib, ex, tfilt = pick
            ps, trs = grid[pick], books[pick]
            rm, p = r81.p_random(tf, d, ex, trs)
            other = grid[("M30" if tf == "M15" else "M15", rib, ex, tfilt)]
            checks = {"test > 0": ps["test"]["n"] and ps["test"]["exp"] > 0,
                      "2018–2021 ≥ 0 (nếu có)": (not ps["pre"]["n"]) or ps["pre"]["exp"] >= 0,
                      f"thắng ngẫu nhiên p < 0,05/36 (p = {p:.4f}, TB ngẫu nhiên {rm:+.3f})": p < 0.05 / N_TESTS,
                      "khung còn lại dương train và validate": other["train"]["n"] and other["validate"]["n"] and
                      other["train"]["exp"] > 0 and other["validate"]["exp"] > 0}
            ok = all(checks.values())
            L += [f"Chọn: **{' / '.join(pick)}** — train+val {r81.tv(ps)[0]} lệnh / {r81.tv(ps)[1]:+.3f}R."]
            L += [f"- {c}: {'đạt' if x else 'KHÔNG'}" for c, x in checks.items()]
            L += [f"- Ví dụ: {examples(trs, d, SEC[tf])}", "", f"**{dn}: {'ĐẠT' if ok else 'không đạt'}.**", ""]
        else:
            L += [f"**{dn}: không bộ nào đủ điều kiện.**", ""]
        best_any = books[("M15", "E2", "X1", "T0")]
        L += [f"Ví dụ với bộ M15 / E2 / X1 / T0 (tham khảo): {examples(best_any, d, 900)}", ""]
    L += part_b(np.random.default_rng(85))
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
