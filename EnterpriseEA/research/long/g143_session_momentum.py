"""G143: gold intraday session momentum. Plan: docs/superpowers/plans/2026-10-22-g143-session-momentum.md.

NY : move 15:30 -> 16:30 server (4 M15 bars), enter at the 16:30 open in its direction, exit at the close of the 20:15 bar.
LDN: move 10:00 -> 11:00 server, enter at the 11:00 open, exit at the close of the 15:00 bar.
Signal when |move| >= 0.4 x ATR20 D1 (closed server days). SL = the window's first open. No TP.

Usage: g143_session_momentum.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402

CELLS = {"NY": (15 * 3600 + 1800, 16 * 3600 + 1800, 20 * 3600 + 900), "LDN": (10 * 3600, 11 * 3600, 15 * 3600)}
THR = 0.4
RUNS, PVAL = 200, 0.025
DECIDE = ("train", "validate", "test")


def daily_atr(D):
    t, h, l, c = D["t"], D["h"], D["l"], D["c"]
    day = t // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    starts = np.r_[0, ends[:-1] + 1]
    days = day[ends]
    H = np.array([h[a:z + 1].max() for a, z in zip(starts, ends)])
    L = np.array([l[a:z + 1].min() for a, z in zip(starts, ends)])
    C = c[ends]
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atr = np.full(len(tr), np.nan)
    for k in range(20, len(tr)):
        atr[k] = tr[k - 20:k].mean()                   # days k-20 .. k-1: closed before day k
    return dict(zip(days.tolist(), atr.tolist()))


def sessions(D, cell):
    """Per day: (index of the window's first bar, index of the entry bar, index of the exit bar) when all bars exist."""
    w0, e_s, x_s = CELLS[cell]
    t = D["t"]
    tod = t % 86400
    pos = {int(x): k for k, x in enumerate(t)}
    out = []
    for k in np.nonzero(tod == w0)[0]:
        day0 = int(t[k]) - w0
        idx = [pos.get(day0 + w0 + 900 * q) for q in range(4)]
        e, x = pos.get(day0 + e_s), pos.get(day0 + x_s)
        if None in idx or e is None or x is None or x <= e:
            continue
        out.append((int(k), int(e), int(x), day0 // 86400))
    return out


def trade(D, k, e, x, d, sl):
    entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
    if d * (entry - sl) <= 0:
        return None
    return gp.run_trade(D, e, d, entry, sl, entry + d * 1e6, x - e + 1)


def run_cell(D, atrd, cell, thr, control=False):
    S = sessions(D, cell)
    rows = []
    for k, e, x, day in S:
        A = atrd.get(day)
        if not A or A != A:
            continue
        move = D["c"][k + 3] - D["o"][k]
        if abs(move) < thr * A:
            continue
        d = 1 if move > 0 else -1
        t = trade(D, k, e, x, d, D["o"][k])
        if t:
            t["k_atr"] = d * ((D["o"][e] + (D["sp"][e] if d == 1 else 0)) - D["o"][k]) / A
            rows.append(t)
    rows = [t for t in rows if t["p"]]
    out = {"per": {p: gp.cell(t["rh"] for t in rows if t["p"] == p) for p, _, _ in gp.PER}}
    if not control:
        return rows, out, S
    out["x1.5"] = {p: gp.cell(t["rh15"] for t in rows if t["p"] == p) for p in DECIDE}
    out["mua"] = {p: gp.cell(t["rh"] for t in rows if t["p"] == p and t["d"] == 1) for p in DECIDE}
    out["bán"] = {p: gp.cell(t["rh"] for t in rows if t["p"] == p and t["d"] == -1) for p in DECIDE}
    # control: random day of the same period and direction, same times, same stop in D1 ATR
    byp = {}
    for k, e, x, day in S:
        p = gp.period(int(D["utc"][e]))
        if p and atrd.get(day) == atrd.get(day):
            byp.setdefault(p, []).append((k, e, x, day))
    tv = [t for t in rows if t["p"] in ("train", "validate")]
    actual = float(np.mean([t["rh"] for t in tv]))
    rng = random.Random(143)
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in tv:
            for _ in range(20):
                k, e, x, day = rng.choice(byp[t["p"]])
                A = atrd.get(day)
                entry = D["o"][e] + (D["sp"][e] if t["d"] == 1 else 0.0)
                r = trade(D, k, e, x, t["d"], entry - t["d"] * t["k_atr"] * A)
                if r:
                    u.append(r["rh"]); break
        hits += float(np.mean(u)) >= actual
    out["p đối chứng (train+validate)"] = (hits + 1) / (RUNS + 1)
    per = {p: [t["rh"] for t in rows if t["p"] == p] for p in DECIDE}
    ok = (all(len(v) >= 40 and np.mean(v) > 0 for v in per.values())
          and np.mean([t["rh15"] for t in tv]) > 0 and out["p đối chứng (train+validate)"] <= PVAL)
    out["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return rows, out, S


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M15")
    g.DATA = root / "m15v"
    D = g.load("XAUUSD")
    atrd = daily_atr(D)
    res = {}
    for cell in CELLS:
        rows, out, S = run_cell(D, atrd, cell, THR, control=True)
        out["số ngày có đủ nến"] = len(S)
        out["độ nhạy (báo cáo)"] = {str(th): run_cell(D, atrd, cell, th)[1]["per"] for th in (0.25, 0.6)}
        res[cell] = out
        print(cell, json.dumps(out, ensure_ascii=False), flush=True)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
