"""G127: ADR-used filter for VHedge G119 (keep a group when the UTC day has used < 0.8 ADR at entry).
Pre-registered plan: docs/superpowers/plans/2026-10-20-g127-vhedge-adr-filter.md. MT5 data only.

  python g127_vhedge_adr.py

Step 1: discovery period 05/2024-12/2025 (descriptive only). Step 2: 2026, opened once.
"""
from __future__ import annotations

import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g126_session_adr as g126  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g127-vhedge-adr-filter.md"
TEST0 = g126.TEST
END = g126.END
THR = 0.8
CURVE = (0.6, 0.7, 0.8, 0.9, 1.0)
HOURS = ((0, 7), (7, 13), (13, 21), (21, 24))
RISK = 0.015


def mean(x):
    return statistics.fmean(x) if x else 0.0


def server_state():
    """Same day state but with the broker server day (what the EA can compute without a clock offset)."""
    M = g126.load("M30")
    M["utc"] = M["time"]                     # treat server time as the clock
    M["day"] = M["utc"] // g126.DAY
    M["mn"] = (M["utc"] % g126.DAY) // 60
    return g126.DayState(M, g126.daily(M))


def rows():
    import g120_combo as g120
    M = g126.load("M30")
    S_utc = g126.DayState(M, g126.daily(M))
    S_srv = server_state()
    V = g120.vhedge()["G119"]
    out = []
    for r in V.itertuples():
        srv = int(r.t_in)
        u = int(g126.to_utc(np.array([srv]))[0])
        if u >= END:
            continue
        x, y = S_utc.at(u), S_srv.at(srv)
        if x is None or not x["adr"] > 0:
            continue
        out.append(dict(u=u, t_out=int(r.t_out), r=float(r.U), used=(x["h"] - x["l"]) / x["adr"],
                        used_srv=((y["h"] - y["l"]) / y["adr"]) if (y and y["adr"] > 0) else np.nan,
                        hr=(u % g126.DAY) // 3600, year=datetime.fromtimestamp(u, timezone.utc).year,
                        test=u >= TEST0))
    return out


def split(rs, thr, key="used"):
    keep = [x["r"] for x in rs if x[key] < thr]
    drop = [x["r"] for x in rs if x[key] >= thr]
    return keep, drop


def cell(x):
    return f"{len(x)} / {mean(x):+.3f} / tổng {sum(x):+.1f}"


def curve_table(rs, L, title):
    L += [f"### {title}", "", "| Ngưỡng | Giữ: lệnh / R/lệnh / tổng R | Bỏ: lệnh / R/lệnh / tổng R | Chênh (giữ − bỏ) |", "|---|---|---|---|"]
    for t in CURVE:
        k, d = split(rs, t)
        L.append(f"| {t} | {cell(k)} | {cell(d)} | {mean(k) - mean(d):+.3f} |")
    L.append("")


def perm_p(rs, thr, reps=5000, seed=127):
    k, d = split(rs, thr)
    obs = mean(k) - mean(d)
    allr = [x["r"] for x in rs]
    nk = len(k)
    rng = random.Random(seed)
    hit = 0
    for _ in range(reps):
        rng.shuffle(allr)
        if mean(allr[:nk]) - mean(allr[nk:]) >= obs:
            hit += 1
    return hit / reps


def equity(rs):
    eq = pk = 1.0
    dd = 0.0
    for x in sorted(rs, key=lambda z: z["t_out"]):
        eq *= 1 + RISK * x["r"]
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    return eq, dd


def main():
    R = rows()
    disc = [x for x in R if not x["test"]]
    test = [x for x in R if x["test"]]
    L = ["# G127: bộ lọc ADR cho VHedge G119 — kết quả", "",
         "Kế hoạch: `plans/2026-10-20-g127-vhedge-adr-filter.md`. Lệnh VHedge G119 (bộ sinh `g120_combo.vhedge`, R mỗi nhóm "
         "sau chi phí). ADR đã dùng = (cao − thấp từ 00:00 UTC đến nến M30 đã đóng trước lúc vào) ÷ ADR 10 ngày UTC. "
         f"Bộ lọc cố định: giữ khi < {THR}.", "",
         f"Giai đoạn phát hiện: {len(disc)} lệnh ({datetime.fromtimestamp(disc[0]['u'], timezone.utc):%m/%Y}–12/2025). "
         f"2026: {len(test)} lệnh.", "",
         "## Bước 1 — giai đoạn phát hiện (chỉ mô tả, không đổi bộ lọc)", ""]
    curve_table(disc, L, "1a. Đường ngưỡng")
    L += ["### 1b. Trong cùng nhóm giờ UTC lúc vào (ngưỡng 0,8)", "", "| Giờ UTC | Giữ | Bỏ | Chênh |", "|---|---|---|---|"]
    wsum = wdiff = 0.0
    for a, b in HOURS:
        sub = [x for x in disc if a <= x["hr"] < b]
        k, d = split(sub, THR)
        diff = mean(k) - mean(d) if k and d else float("nan")
        if k and d:
            w = min(len(k), len(d))
            wsum += w
            wdiff += w * diff
        L.append(f"| {a:02d}–{b:02d} | {cell(k)} | {cell(d)} | {diff:+.3f} |")
    L += ["", f"Chênh trung bình có trọng số (theo min(giữ, bỏ) mỗi nhóm giờ): **{(wdiff / wsum if wsum else float('nan')):+.3f}**.", ""]
    L += ["### 1c. Theo năm (ngưỡng 0,8)", "", "| Năm | Giữ | Bỏ |", "|---|---|---|"]
    for y in sorted({x["year"] for x in disc}):
        k, d = split([x for x in disc if x["year"] == y], THR)
        L.append(f"| {y} | {cell(k)} | {cell(d)} |")
    L.append("")
    srv = [x for x in disc if x["used_srv"] == x["used_srv"]]
    k, d = split(srv, THR, "used_srv")
    agree = sum(1 for x in srv if (x["used"] < THR) == (x["used_srv"] < THR)) / max(len(srv), 1)
    L += ["### 1d. Ngày server thay cho ngày UTC (ngưỡng 0,8)", "",
          f"Giữ {cell(k)}; bỏ {cell(d)}. Hai cách tính cho cùng quyết định ở {agree:.0%} số lệnh.", ""]
    print("step 1 done", flush=True)

    L += ["## Bước 2 — test 2026 (mở một lần)", ""]
    k, d = split(test, THR)
    c1 = bool(k) and bool(d) and mean(k) > mean(d)
    c2 = sum(d) <= 0
    c3 = len(d) >= 10
    p = perm_p(test, THR) if k and d else float("nan")
    L += ["| Nhóm | Lệnh / R/lệnh / tổng R |", "|---|---|", f"| Giữ (ADR đã dùng < 0,8) | {cell(k)} |",
          f"| Bỏ (≥ 0,8) | {cell(d)} |", f"| Tất cả | {cell([x['r'] for x in test])} |", "",
          f"1. R/lệnh giữ > bỏ: **{'đạt' if c1 else 'không'}** ({mean(k):+.3f} so với {mean(d):+.3f})",
          f"2. Tổng R nhóm bỏ ≤ 0: **{'đạt' if c2 else 'không'}** ({sum(d):+.1f})",
          f"3. ≥ 10 lệnh bị bỏ: **{'đạt' if c3 else 'không'}** ({len(d)})",
          f"- Hoán vị nhãn (một phía): p = {p:.3f}", ""]
    yrs = (END - TEST0) / (365.25 * 86400)
    for name, rs in (("Không lọc", test), ("Có lọc", [x for x in test if x["used"] < THR])):
        eq, dd = equity(rs)
        L.append(f"- {name}: {len(rs)} lệnh, {eq - 1:+.1%} trong 2026 ({(eq ** (1 / yrs) - 1):+.1%}/năm), DD {dd:.1%} (1,5%/nhóm, lãi kép)")
    L.append("")
    curve_table(test, L, "2026: đường ngưỡng (mô tả)")
    verdict = c1 and c2 and c3
    L += [f"**Kết luận theo luật: {'ĐẠT → được bật ở chế độ SHADOW (chỉ ghi nhận), chưa chặn lệnh thật' if verdict else 'KHÔNG ĐẠT → đóng ý này, VHedge giữ nguyên'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("verdict", verdict, flush=True)


if __name__ == "__main__":
    main()
