"""Bot fingerprints for the council's drift monitor (council step 3b-1): mean and standard deviation of the risk-weighted R
per closed leg, which is what money / (capital x risk %) measures on a live account.
S07: the G89 M30 book (all legs: base, early, re-entry, adds), weights as the EA (unordered / add 0.67, against D1 x 0.5),
05/2018-06/2026. Other bots: no comparable book yet.

Usage: lab_fingerprints.py <data dir> <out json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g136_p1p4 as p1  # noqa: E402


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    d1 = p1.d1_from("M30")
    legs = [x for x in p1.m30_book() if g.ts(2018, 5, 1) <= x["srv"] < g.ts(2026, 7, 1)]
    wr = np.array([x["r"] * x["w"] * (1.0 if d1(x["srv"]) == x["d"] else 0.5) for x in legs])
    out = {"S07": {"n": int(len(wr)), "mu": round(float(wr.mean()), 4), "sigma": round(float(wr.std(ddof=1)), 4),
                   "p_win": round(float((wr > 0).mean()), 4), "risk_percent": 1.5,
                   "source": "G89 M30 book, all legs, weighted R (w x D1 0.5), 05/2018-06/2026"},
           "VHEDGE": None, "CTXLIMIT": None, "XRT": None}
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
