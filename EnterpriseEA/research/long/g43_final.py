"""G43 final: combine what passed, choose on 2010-2016, stress-test the choice. MT5 data only.

  python g43_final.py

Candidates (from g43_low_risk.py B/C, g43_reversal.py F, g43_oos.py):
  G0  P0 = S04 + S06B (USD flow, add) + T2 on five symbols, equal risk                 (baseline)
  G1  G0 with mean/variance risk weights by setup (estimated on 2010-2016, capped 0.5-2x)
  G2  G1 with the T2 momentum-close filter
  G3  G1 with the T2 add at +1R (weights estimated again on 2010-2016)
  G4  G2 + G3 together
The choice is the best 2010-2016 score (p10 %/year / p90 DD of the bootstrap of months); validate and test are
reported, not used. Checks on the choice: commission x2 + 0.1R slippage, leave one symbol out, without the best
10 trades, the T2 asset-class rule (no T2 on FX), and the same portfolio at 0.5% per trade (CUSTOM account).
"""
from __future__ import annotations

import sys

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import g43_low_risk as g  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
from g43_reversal import arrays, has_pattern  # noqa: E402


def t2_variant(momentum: bool, add_at) -> list[dict]:
    rows = g.t2_rows(g.T2, ls.SYMBOLS, add_at=add_at)
    if not momentum:
        return rows
    keep = []
    for s in ls.SYMBOLS:
        B = dv.load(s, "H4")
        A = arrays(B["bars"])
        idx = {int(u): i for i, u in enumerate(B["utc"])}
        for t in rows:
            if t["symbol"] == s and has_pattern("nến đà", A, idx[t["in"]], t["dir"]):
                keep.append(t)
    return keep


def weighted(rows):
    w = g.weights_on_train(rows, "meanvar")
    return w, (lambda t, s, w=w: w[t["setup"]])


def main() -> None:
    pyramid.GAP_FILL = True
    base = g.base_rows()
    t2 = {(m, a): t2_variant(m, a) for m in (False, True) for a in (None, 1.0)}
    cands = {"G0 bằng nhau": (base + t2[(False, None)], None),
             "G1 kỳ vọng/phương sai": (base + t2[(False, None)], "w"),
             "G2 G1 + lọc nến đà T2": (base + t2[(True, None)], "w"),
             "G3 G1 + bồi T2 +1R": (base + t2[(False, 1.0)], "w"),
             "G4 G1 + nến đà + bồi": (base + t2[(True, 1.0)], "w")}
    lines = ["# G43 kết quả cuối: ghép phương án và kiểm tra căng thẳng (chỉ dữ liệu MT5)", "",
             "Chọn theo điểm 2010–2016; 2017–2020 và 2021–2025 chỉ để kiểm chứng. 0,3%/lệnh trước khi nhân trọng số.", "",
             *g.HEAD]
    res, mults = {}, {}
    for name, (rows, mode) in cands.items():
        mult = None
        if mode == "w":
            w, mult = weighted(rows)
            name = f"{name} ({', '.join(f'{k} {v:.2f}' for k, v in sorted(w.items()))})"
        res[name] = (rows, g.by_period(rows, mult=mult))
        mults[name] = mult
        lines += g.table(name, res[name][1])
    choice = max(res, key=lambda k: res[k][1]["train"]["score"])
    rows, mult = res[choice][0], mults[choice]
    lines += ["", f"**Chọn (điểm 2010–2016 cao nhất): {choice}**", "", "## Kiểm tra căng thẳng phương án chọn (toàn kỳ)", "", *g.HEAD]

    def stress(label, rs, m=mult, per_trade=None):
        old = g.PER_TRADE
        if per_trade:
            g.PER_TRADE = per_trade
        try:
            lines.append(g.row(label, "all", g.metrics(g.simulate(rs, mult=m))))
        finally:
            g.PER_TRADE = old

    stress("gốc", rows)
    fee = []
    for t in rows:
        extra = replay.COMMISSION.get(t["symbol"], 0.0) / max(t["dist"], 1e-12)
        fee.append(dict(t, r=t["r"] - extra - 0.1))
    stress("phí ×2 + trượt 0,1R", fee)
    for s in ls.SYMBOLS:
        stress(f"bỏ {s}", [t for t in rows if t["symbol"] != s])
    top = {id(t) for t in sorted(rows, key=lambda t: t["r"], reverse=True)[:10]}
    stress("bỏ 10 lệnh lời nhất", [t for t in rows if id(t) not in top])
    stress("không T2 trên FX (quy tắc loại tài sản)", [t for t in rows if not (t["setup"] == "T2" and t["symbol"] in ("EURUSD", "GBPUSD", "USDJPY"))])
    stress("0,5%/lệnh (CUSTOM)", rows, per_trade=0.005)
    old_open = g.OPEN_RISK
    lines += ["", "## Theo năm (phương án chọn, 0,3%)", "", "| Năm | % |", "|---|---|"]
    s_all = g.simulate(rows, mult=mult)
    for y, v in sorted(s_all["by_year"].items()):
        lines.append(f"| {y} | {v / g.CAPITAL * 100:+.2f}% |")
    g.OPEN_RISK = old_open
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g43_final.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
