"""G156a2: Q1 and Q4 re-posed as symmetric first-passage from the current close (1 ATR M30 for level breaks, 1R for open S07
legs), with the G156a context packet. Plan: docs/superpowers/plans/2026-10-24-g156a2-repose-from-price.md.

Usage: g156a2_repose.py <data dir> <g156a results dir> <out dir>
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g156a_questions as qa  # noqa: E402
from g148_layered_risk_map import calendar  # noqa: E402


def first_passage(D, i, d, up, dn, last):
    """From bar i+1 to last: which of p0 + d*up / p0 - d*dn is touched first. Both in one bar -> 'CẢ HAI'."""
    h, l, c = D["h"], D["l"], D["c"]
    p0 = c[i]
    hi_t, lo_t = (p0 + up, p0 - dn) if d == 1 else (p0 + dn, p0 - up)
    for j in range(i + 1, min(last, len(c) - 1) + 1):
        hit_hi, hit_lo = h[j] >= hi_t, l[j] <= lo_t
        if hit_hi and hit_lo:
            return "CẢ HAI"
        if hit_hi:
            return "ĐI TIẾP" if d == 1 else "NGƯỢC"
        if hit_lo:
            return "NGƯỢC" if d == 1 else "ĐI TIẾP"
    return None


def main():
    root = Path(sys.argv[1]).resolve()
    src, out = Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = g.load("XAUUSD")
    F = qa.features(D)
    news = calendar()[0]
    legs = qa.s07_legs(root)
    D = g.load("XAUUSD")
    t, c = D["t"], D["c"]

    def base_row(q, i, extra):
        r = {"loại": q, "nến": int(i), "giờ server đóng": int(t[i] + qa.BAR), "kỳ": qa.period(int(t[i]))}
        r.update(qa.packet(F, i))
        r.update(qa.news_fields(news, int(t[i] + qa.BAR)))
        r.update(extra)
        return r

    q1 = []
    for i, d, name, L in qa.q1_events(D, F):
        if t[i] < qa.START:
            continue
        A = D["atr"][i]
        lab = first_passage(D, i, d, A, A, i + qa.Q1_BARS)
        lab = {"NGƯỢC": "GIẢ", None: "LƯỠNG LỰ"}.get(lab, lab)
        q1.append(base_row("Q1", i, {"mức": name, "chiều": d, "vượt mức/atr": float(d * (c[i] - L) / A), "đáp án": lab}))
    idx_of = lambda srv: int(np.searchsorted(t, srv, side="right")) - 1  # noqa: E731
    q4 = []
    for L in legs:
        if L["srv_in"] < qa.START:
            continue
        a, z = idx_of(L["srv_in"]), idx_of(L["srv_out"])
        d, E0, R = L["d"], L["entry"], L["dist"]
        for i in range(a + 1, z):
            if (t[i] + qa.BAR) % 3600:
                continue
            lab = first_passage(D, i, d, R, R, z) or "ĐÓNG TRƯỚC"
            rnow = d * (c[i] - E0) / R
            q4.append(base_row("Q4", i, {"chiều": d, "lệnh gốc": L["base"], "R đang có": float(rnow),
                                         "giờ đã giữ": float((t[i] + qa.BAR - L["srv_in"]) / 3600), "đang lời": bool(rnow > 0),
                                         "đáp án": lab}))
    f1, f4 = pd.DataFrame(q1), pd.DataFrame(q4)
    f1.to_csv(out / "Q1.csv", index=False, encoding="utf-8")
    f4.to_csv(out / "Q4.csv", index=False, encoding="utf-8")
    for q in ("Q2", "Q3"):
        shutil.copy(src / f"{q}.csv", out / f"{q}.csv")
    summary = {}
    for q, df in (("Q1b", f1), ("Q4b", f4)):
        s = {"n": int(len(df)), "tất cả": {k: round(float(v), 3) for k, v in df["đáp án"].value_counts(normalize=True).items()}}
        for pn, _, _ in qa.PER:
            s[pn] = {k: round(float(v), 3) for k, v in df[df["kỳ"] == pn]["đáp án"].value_counts(normalize=True).items()}
        yr = pd.to_datetime(df["giờ server đóng"], unit="s").dt.year
        dec = df["đáp án"].isin(["ĐI TIẾP", "GIẢ", "NGƯỢC"])
        s["ĐI TIẾP / (ĐI TIẾP + ngược) theo năm"] = {int(y): round(float((df[dec & (yr == y)]["đáp án"] == "ĐI TIẾP").mean()), 3)
                                                     for y in sorted(yr.unique())}
        summary[q] = s
    q1d = f1[f1["đáp án"].isin(["ĐI TIẾP", "GIẢ"])]
    summary["Q1b theo loại mức (ĐI TIẾP / quyết định)"] = {m: {"n": int(len(gp)), "ĐI TIẾP": round(float((gp["đáp án"] == "ĐI TIẾP").mean()), 3)}
                                                          for m, gp in q1d.groupby("mức")}
    q4d = f4[f4["đáp án"].isin(["ĐI TIẾP", "NGƯỢC"])]
    summary["Q4b theo đang lời (ĐI TIẾP / quyết định)"] = {str(k): {"n": int(len(gp)), "ĐI TIẾP": round(float((gp["đáp án"] == "ĐI TIẾP").mean()), 3)}
                                                           for k, gp in q4d.groupby("đang lời")}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
