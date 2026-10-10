"""G79: audit of the S07 entry filters on the subset of base trades (no substitution after a block).

  python g79_filter_audit.py

G67-G71 judged a filter by re-running the trades on the filtered signals: a blocked signal frees the cool-down and
other signals enter instead, so the result mixes the filter's selection with that reshuffle. Here every trade of the
unfiltered base keeps its place; a filter splits the trades into kept / removed. Lift = R/trade of the kept trades
minus R/trade of all trades (harsh costs), per period, with a permutation p (random subsets of the same size).
Base for B6 (H4 EMA200 side): all S07 signals. Base for the other filters: S07 signals with B6 (the current rule).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402
import g71_sell as s71  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g79-filter-audit.md"
TFS = [("M15", 16, 8, 480), ("M30", 8, 4, 240), ("H1", 4, 2, 120), ("H4", 8, 4, 240)]
KEYS = ("pre", "train", "validate", "test")
NAMES = {"B6": "cùng phía EMA200 H4 (đang dùng)", "B1": "giờ mở phiên", "B2": "nến đóng :00/:30", "B3": "nén volume thấp",
         "B7": "spread ≤ 2× trung vị", "D1": "cùng phía EMA200 D1", "L1": "bán: đẩy lên thất bại", "L2": "bán: chạm EMA200 H4 (S07S)"}
PERMS = 5000


def base_trades(tf, comp, cool, hold, with_b6):
    p = dict(v.C0, tf=tf, comp=comp, cool=cool, hold=hold, gap=True, exit="E2X")
    v.configure(p)
    D = g.load("XAUUSD")
    sg = [(i, d) for i, d in g.signals(D) if (not with_b6 or g.block_ok(D, i, d, "B6"))]
    out = g.trades("XAUUSD", "E2X", 8.0, None, sg)
    for t in out:
        t["p"] = v.period(t)
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        t["rh"] = h.harsh(t, D)
    return D, [t for t in out if t["p"] in KEYS]


def keep(D, t, f, comp):
    i, d = t["i"], t["d"]
    if f in ("B1", "B2", "B3", "B6", "B7"):
        return g.block_ok(D, i, d, f)
    if f == "D1":
        return D["d1_side"][i] == d
    if f in ("L1", "L2"):
        return d == -1 and s71.loc_ok(D, i, f, comp)
    raise ValueError(f)


def audit(trs, mask, rng):
    r = np.array([t["rh"] for t in trs])
    k = np.array(mask)
    if k.sum() < 5 or (~k).sum() < 5:
        return None
    real = r[k].mean()
    sims = np.array([r[rng.permutation(len(r))[:k.sum()]].mean() for _ in range(PERMS)])
    per = {}
    for q in KEYS:
        kk = np.array([t["p"] == q for t in trs])
        per[q] = (int((k & kk).sum()), float(r[k & kk].mean()) if (k & kk).any() else float("nan"),
                  int((~k & kk).sum()), float(r[~k & kk].mean()) if (~k & kk).any() else float("nan"))
    return dict(n=len(r), kept=int(k.sum()), all=float(r.mean()), kmean=float(real), rmean=float(r[~k].mean()),
                p=float(np.mean(sims >= real)), per=per)


def main():
    rng = np.random.default_rng(79)
    L = ["# G79: Rà soát các bộ lọc vào lệnh S07 trên đúng tập lệnh gốc", "",
         "Cách cũ (G67–G71) chạy lại lệnh trên tín hiệu đã lọc: tín hiệu bị chặn làm hết thời gian nghỉ sớm hơn, lệnh khác chen vào. "
         "Ở đây mỗi lệnh của sổ chưa lọc giữ nguyên chỗ; bộ lọc chỉ chia lệnh thành **giữ** / **bỏ**. "
         "R/lệnh với chi phí khắt khe G68, XAUUSD, thoát E2X, TP 8R. "
         "p = xác suất một tập con ngẫu nhiên cùng cỡ có R/lệnh ≥ nhóm giữ (5000 lần). "
         "Ô kỳ: giữ n / R — bỏ n / R.", "",
         "Đánh giá: bộ lọc **có tác dụng** khi nhóm giữ tốt hơn nhóm bỏ ở ≥ 3/4 kỳ và p < 0,05; **ngược** khi nhóm bỏ tốt hơn ở ≥ 3/4 kỳ.", ""]
    for tf, comp, cool, hold in TFS:
        for with_b6, filters in ((False, ["B6"]), (True, ["B1", "B2", "B3", "B7", "D1", "L1", "L2"])):
            D, trs = base_trades(tf, comp, cool, hold, with_b6)
            for d, dn in ((1, "Mua"), (-1, "Bán")):
                x = [t for t in trs if t["d"] == d]
                rows = []
                for f in filters:
                    if f in ("L1", "L2") and d == 1:
                        continue
                    if f == "B2" and tf != "M15":
                        continue           # every M30+ bar closes on :00/:30
                    a = audit(x, [keep(D, t, f, comp) for t in x], rng)
                    if a is None:
                        continue
                    better = sum(1 for q in KEYS if a["per"][q][0] and a["per"][q][2] and a["per"][q][1] > a["per"][q][3])
                    worse = sum(1 for q in KEYS if a["per"][q][0] and a["per"][q][2] and a["per"][q][1] < a["per"][q][3])
                    verdict = "**có tác dụng**" if better >= 3 and a["p"] < 0.05 else ("**ngược**" if worse >= 3 else "không rõ")
                    cells = " | ".join(f"{a['per'][q][0]} / {a['per'][q][1]:+.2f} — {a['per'][q][2]} / {a['per'][q][3]:+.2f}"
                                       if a["per"][q][0] and a["per"][q][2] else "—" for q in KEYS)
                    rows.append(f"| {NAMES[f]} | {a['kept']}/{a['n']} | {a['kmean']:+.3f} | {a['rmean']:+.3f} | {cells} | {a['p']:.3f} | {verdict} |")
                if rows:
                    L += [f"## {tf} {dn} — gốc: {'S07 có B6' if with_b6 else 'mọi tín hiệu S07 (chưa lọc H4)'}", "",
                          "| Bộ lọc | Giữ / tổng | R giữ | R bỏ | " + " | ".join(v.NAMES[q] for q in KEYS) + " | p | Đánh giá |",
                          "|---|---|---|---|---|---|---|---|---|---|"] + rows + [""]
        sys.stdout.buffer.write(f"done {tf}\n".encode()); sys.stdout.flush()
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
