"""G70 supplement (not pre-registered, not used to choose): the buy book with at most 3 legs open at any time."""
import sys

import numpy as np

import g69_two_sided as v
import g70_pyramid as p


def capped(cl, cap=3):
    out, open_exits = [], []
    for c in sorted(cl, key=lambda x: x["utc"]):
        legs = []
        for j, leg in enumerate(c["legs"]):
            r, t_out, t_in, tf = leg
            live = [e for e in open_exits if e > t_in]
            if len(live) >= cap:
                if j == 0:
                    break
                continue
            legs.append(leg)
            open_exits.append(t_out)
        if legs:
            out.append(dict(c, legs=legs, total=sum(x[0] for x in legs), adds=len(legs) - 1))
    return out


if __name__ == "__main__":
    book = p.BOOKS["Mua"]
    all_legs = {tf: p.legs_for(tf, book["rule"], book["side"]) for tf in p.TFP}
    L = ["", "## Bổ sung (không đăng ký trước, không dùng để chọn): sổ Mua, tối đa 3 lệnh mở cùng lúc (4,5%)", "",
         "| Bản | " + " | ".join(v.NAMES[k] for k in v.KEYS) + " | DD (R) | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% |",
         "|" + "---|" * (len(v.KEYS) + 7)]
    for vn, src, be in p.VARIANTS:
        cl = capped(p.clusters(book, all_legs, src, be))
        s = p.summary(cl)
        r = p.risk_stats(cl)
        L.append(f"| {vn} | " + " | ".join(f"{s[k][0]} / {s[k][1]:+.2f} / {s[k][3]}" if s[k][0] else "—" for k in v.KEYS) +
                 f" | {r['dd_r']:.1f} | {r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% |")
    with open(p.REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
