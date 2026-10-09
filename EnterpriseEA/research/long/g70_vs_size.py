"""G70 supplement: pyramiding against simply sizing the base trades up (same drawdown budget)."""
import sys

import g70_cap as c
import g70_pyramid as p

if __name__ == "__main__":
    book = p.BOOKS["Mua"]
    all_legs = {tf: p.legs_for(tf, book["rule"], book["side"]) for tf in p.TFP}
    base = p.clusters(book, all_legs, None, False)
    L = ["", "### So sánh: bồi lệnh hay chỉ tăng rủi ro lệnh gốc (cùng sổ Mua)", "",
         "| Bản | Rủi ro | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% |", "|---|---|---|---|---|---|---|"]
    for risk in (0.015, 0.025, 0.03):
        r = p.risk_stats(base, risk)
        L.append(f"| Không bồi | {risk:.1%}/lệnh | {r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% |")
    for vn, src in (("Bồi cùng khung", "same"), ("Bồi khung khác", "other"), ("Bồi cả hai", "both")):
        r = p.risk_stats(c.capped(p.clusters(book, all_legs, src, False)), 0.015)
        L.append(f"| {vn} (tối đa 3 lệnh mở) | 1.5%/lệnh | {r['per_year']:+.0f}% | {r['dd']:.0f}% | {r['dd90']:.0f}% | {r['c20']:.0f}% | {r['c30']:.0f}% |")
    with open(p.REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))
