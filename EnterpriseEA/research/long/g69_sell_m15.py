"""Descriptive (not a selection): the sell side of the setup on M15, base and three variants."""
import collections
import datetime as dt
import sys

import numpy as np

import g67_dmi_ema as g
import g68_refine as h
import g69_two_sided as v


def show(name, p):
    trs = [t for t in v.rows(p) if t["d"] == -1]
    v.configure(p)
    D = g.load("XAUUSD")
    for t in trs:
        t["rh"] = h.harsh(t, D)
    ps, ph = v.per(trs), v.per(trs, "rh")
    out = [f"\n## {name}", "  " + " | ".join(f"{k} {v.cell(ps[k])}" for k in v.KEYS),
           "  khat khe: " + " | ".join(f"{k} {v.cell(ph[k])}" for k in v.KEYS)]
    yrs = collections.defaultdict(list)
    for t in trs:
        yrs[dt.datetime.utcfromtimestamp(t["utc"]).year].append(t["r"])
    out.append("  nam: " + ", ".join(f"{y}:{len(x)}/{np.mean(x):+.2f}" for y, x in sorted(yrs.items())))
    rs = [t["r"] for t in trs if t["p"] in v.FOUR]
    st = g.stats(rs)
    out.append(f"  toan ky {st['n']} lenh {st['exp']:+.3f} thang {st['win']:.0%} DD {st['dd']:.1f}R "
               f"giu TV {np.median([t['hold_h'] for t in trs]):.1f}h")
    m, pr = v.p_random(p, trs)
    out.append(f"  ngau nhien TB {m:+.3f} p={pr:.3f}")
    out.append("  " + h.risk_line([t for t in trs if t["p"] in v.FOUR], 0.015))
    out.append("  vi du: " + " ; ".join(v.examples(trs)[:2]))
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    sys.stdout.flush()


if __name__ == "__main__":
    base = dict(v.C0, tf="M15", comp=16, cool=8, hold=480)
    show("M15 ban - C0 (nhu G67)", base)
    show("M15 ban - SL bo khoang trong + EMA100 sau 3R", dict(base, gap=True, exit="E2X"))
    show("M15 ban - thoat nhanh (can da EMA21+ADX)", dict(base, exit="E4"))
    show("M15 ban - chi khi D1 duoi EMA200", dict(base, sell_d1=True))
