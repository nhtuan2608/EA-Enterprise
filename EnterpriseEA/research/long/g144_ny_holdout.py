"""G144: the G143 NY session momentum rule on M30 bars over the unseen 19/03/2018-19/07/2021.
Plan: docs/superpowers/plans/2026-10-22-g144-ny-momentum-holdout.md.

Usage: g144_ny_holdout.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402
from g143_session_momentum import daily_atr, trade  # noqa: E402

W0, ENTRY, EXIT = 15 * 3600 + 1800, 16 * 3600 + 1800, 20 * 3600       # M30 bars: 15:30, 16:00 | entry 16:30 | exit bar 20:00
THR = 0.4
H0, HMID, H1_ = g.ts(2018, 3, 19), g.ts(2020, 1, 1), g.ts(2021, 7, 20)
RUNS = 200


def label(srv):
    if H0 <= srv < HMID:
        return "03/2018–12/2019"
    if HMID <= srv < H1_:
        return "01/2020–07/2021"
    for n, a, z in (("train 07/2021–2023", g.ts(2021, 7, 20), g.ts(2024, 1, 1)), ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
                    ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1)), ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))):
        if a <= srv < z:
            return n
    return None


def stat(xs):
    xs = list(xs)
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = g.load("XAUUSD")
    atrd = daily_atr(D)
    t = D["t"]
    pos = {int(x): k for k, x in enumerate(t)}
    days = []
    for k in np.nonzero((t % 86400) == W0)[0]:
        d0 = int(t[k]) - W0
        k2, e, x = pos.get(d0 + W0 + 1800), pos.get(d0 + ENTRY), pos.get(d0 + EXIT)
        if None in (k2, e, x) or int(t[k]) < H0:
            continue
        days.append((int(k), int(k2), int(e), int(x), d0 // 86400, label(int(t[e]))))
    rows = []
    for k, k2, e, x, day, lab in days:
        A = atrd.get(day)
        if not A or A != A or lab is None:
            continue
        move = D["c"][k2] - D["o"][k]
        if abs(move) < THR * A:
            continue
        d = 1 if move > 0 else -1
        tr = trade(D, k, e, x, d, D["o"][k])
        if tr:
            tr["lab"] = lab
            tr["k_atr"] = d * ((D["o"][e] + (D["sp"][e] if d == 1 else 0)) - D["o"][k]) / A
            rows.append(tr)
    labs = ["03/2018–12/2019", "01/2020–07/2021", "train 07/2021–2023", "validate", "test", "07/2026+"]
    res = {"theo kỳ": {l: stat(r["rh"] for r in rows if r["lab"] == l) for l in labs},
           "phí×1,5": {l: stat(r["rh15"] for r in rows if r["lab"] == l) for l in labs},
           "mua": {l: stat(r["rh"] for r in rows if r["lab"] == l and r["d"] == 1) for l in labs},
           "bán": {l: stat(r["rh"] for r in rows if r["lab"] == l and r["d"] == -1) for l in labs},
           "theo năm": {str(y): stat(r["rh"] for r in rows if g.ts(y, 1, 1) <= int(t[r["e"]]) < g.ts(y + 1, 1, 1))
                        for y in range(2018, 2027)}}
    hold = [r for r in rows if r["lab"] in labs[:2]]
    res["ngoài mẫu 03/2018–07/2021"] = stat(r["rh"] for r in hold)
    res["ngoài mẫu phí×1,5"] = stat(r["rh15"] for r in hold)
    byl = {}
    for k, k2, e, x, day, lab in days:
        if lab in labs[:2] and atrd.get(day) == atrd.get(day) and atrd.get(day):
            byl.setdefault(lab, []).append((k, e, x, day))
    actual = float(np.mean([r["rh"] for r in hold]))
    rng = random.Random(144)
    hits = 0
    for _ in range(RUNS):
        u = []
        for r in hold:
            for _ in range(20):
                k, e, x, day = rng.choice(byl[r["lab"]])
                entry = D["o"][e] + (D["sp"][e] if r["d"] == 1 else 0.0)
                q = trade(D, k, e, x, r["d"], entry - r["d"] * r["k_atr"] * atrd[day])
                if q:
                    u.append(q["rh"]); break
        hits += float(np.mean(u)) >= actual
    res["p đối chứng (ngoài mẫu)"] = (hits + 1) / (RUNS + 1)
    a, b = res["theo kỳ"][labs[0]], res["theo kỳ"][labs[1]]
    ok = (res["ngoài mẫu 03/2018–07/2021"]["n"] >= 40 and a.get("mean", -1) > 0 and b.get("mean", -1) > 0
          and res["ngoài mẫu phí×1,5"]["mean"] > 0 and res["p đối chứng (ngoài mẫu)"] <= 0.05)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
