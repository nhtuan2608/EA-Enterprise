"""G108 step 4: the locked candidate (rr3 label, C3 = LightGBM without the M5 path, top 10 % EV, one trade at a time
per direction) on the sealed 2026 test, once, on both sources (ea, raw), BUY and SELL scored separately.
Lock: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md, section "Bước 4".

  python g108_test.py            # runs both sources in child processes, then writes the report
"""
from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g108-test-2026.md"
TEST0, TEST1 = int(pd.Timestamp("2026-01-01").timestamp()), int(pd.Timestamp("2026-10-14").timestamp())
FIRST, LAST = "2024-12-01", "2026-10-01"
SOURCES = ("ea", "raw")


def child(source: str):
    import g108_data as g
    import g108_features as gf
    import g108_models as gm
    from g108_patterns import boot_lower, dedupe
    # Plans are rebuilt from the same bar frame the features use: the ea source reads a sliding 99,000-bar terminal
    # window, so a cached plan file built earlier can be shifted against a newer window (look-ahead found 20/10/2026).
    m5 = g.load_m5()
    tt = m5["time"].to_numpy(np.int64)
    raw = g.build(m5)
    raw["period"] = g.period(raw["time"])
    X = dedupe(raw).reset_index(drop=True)
    assert (tt[X["i"].to_numpy()] == X["time"].to_numpy()).all(), "plan index / bar time mismatch"
    X["exit_time"] = tt[np.minimum(X["exit_i"].to_numpy(), len(tt) - 1)] + 300
    X["month"] = pd.to_datetime(X["time"], unit="s").dt.strftime("%Y-%m")
    F = gf.features(m5, X, gf.long_m30())
    y = (X["outcome"] == 1).to_numpy().astype(int)
    names = ["C3 no path", "lgbm", "C2 time", "C4 shuffled"]
    pred = {k: np.full(len(X), np.nan) for k in names}
    rng = np.random.default_rng(108)
    for m0 in pd.date_range(FIRST, LAST, freq="MS"):
        s, e = int(m0.timestamp()), int((m0 + pd.offsets.MonthBegin(1)).timestamp())
        tr = gm.train_mask(X, s)
        te = ((X["time"] >= s) & (X["time"] < e)).to_numpy()
        if te.sum() == 0:
            continue
        assert X.loc[tr, "exit_time"].max() < s and X.loc[te, "time"].min() >= s
        for name in ("C3 no path", "lgbm", "C2 time"):
            cols = gm.SETS[name]
            pred[name][te] = gm.fit_predict_lgbm(F.loc[tr, cols], y[tr], F.loc[te, cols])
        Fs = F.loc[te, gf.FEATS].copy()
        Fs[gf.F_PATH] = Fs[gf.F_PATH].to_numpy()[rng.permutation(len(Fs))]
        pred["C4 shuffled"][te] = gm.fit_predict_lgbm(F.loc[tr, gf.FEATS], y[tr], Fs)
        print(source, m0.strftime("%Y-%m"), int(tr.sum()), int(te.sum()), flush=True)
    rr = X["rr"].to_numpy()
    tmask = ((X["time"] >= TEST0) & (X["time"] < TEST1)).to_numpy()
    out = {"source": source, "plans_test": int(tmask.sum()), "dirs": {}}
    for d in (1, -1):
        dm = tmask & (X["d"] == d).to_numpy()
        res = {"all_plans": gm.trades(X, dm)["R"].mean() if dm.any() else float("nan")}
        T = {}
        for name in names:
            sel = gm.select(X, gm.ev(pred[name], rr), "top 10%")
            T[name] = gm.trades(X, sel & dm)
            T[name] = T[name][T[name]["d"] == d]
            res[name] = dict(n=len(T[name]), mean=float(T[name]["R"].mean()) if len(T[name]) else float("nan"))
        C = T["C3 no path"].copy()
        sel = gm.select(X, gm.ev(pred["C3 no path"], rr), "top 10%")
        chosen = X[sel & dm]
        draws = []
        for _ in range(200):
            idx = np.concatenate([rng.choice(X.index[dm & (X["month"] == mo).to_numpy()], size=c, replace=False)
                                  for mo, c in chosen.groupby("month").size().items()]) if len(chosen) else np.array([], int)
            draws.append(X.loc[idx, "R"].mean() if len(idx) else np.nan)
        draws = np.array(draws)
        res["c1"] = dict(chosen_mean=float(chosen["R"].mean()) if len(chosen) else float("nan"),
                         rand_mean=float(np.nanmean(draws)), p=float(np.nanmean(draws >= chosen["R"].mean())) if len(chosen) else 1.0)
        if len(C):
            C["month"] = pd.to_datetime(C["time"], unit="s").dt.strftime("%Y-%m")
            C["hour"] = (C["time"] % 86400) // 3600
            res["lb"] = boot_lower(C["R"].to_numpy(), (C["time"] // 86400).to_numpy())
            bm = C.groupby("month")["R"].sum().idxmax()
            bh = C.groupby("hour")["R"].sum().idxmax()
            res["ex_month"] = dict(month=bm, mean=float(C.loc[C["month"] != bm, "R"].mean()))
            res["ex_hour"] = dict(hour=int(bh), mean=float(C.loc[C["hour"] != bh, "R"].mean()))
            eq = C.sort_values("time")["R"].cumsum().to_numpy()
            res["dd"] = float(np.max(np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq))
            res["total"] = float(C["R"].sum())
            res["by_month"] = {k: [int(v.count()), float(v.sum())] for k, v in C.groupby("month")["R"]}
        vm = ((X["time"] >= int(pd.Timestamp("2025-04-01").timestamp())) & (X["time"] < TEST0)).to_numpy() & (X["d"] == d).to_numpy()
        V = gm.trades(X, gm.select(X, gm.ev(pred["C3 no path"], rr), "top 10%") & vm)
        res["validate_c3"] = [int(len(V)), float(V["R"].mean()) if len(V) else float("nan")]
        out["dirs"][str(d)] = res
    print("RESULT " + json.dumps(out, default=float), flush=True)


def s07_dd_2026():
    L = pickle.loads((HERE / "out" / "g128_legs.pkl").read_bytes())
    s = sorted((x for x in L if x["bot"] == "S07" and TEST0 - 10800 <= x["t_in"] < TEST1), key=lambda x: x["t_out"])
    eq = np.cumsum([x["r"] * x["w"] for x in s])
    return float(np.max(np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq)) if len(eq) else float("nan"), len(s), float(eq[-1]) if len(eq) else 0.0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(os.environ["G108_SOURCE"])
        return
    res = {}
    for src in SOURCES:
        env = dict(os.environ, G108_SOURCE=src, G108_LABEL="rr3", PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, cwd=str(HERE),
                           encoding="utf-8")
        line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
        if not line:
            print(src, "FAILED", p.stderr[-3000:])
            return
        res[src] = json.loads(line[-1][7:])
    s07_dd, s07_n, s07_tot = s07_dd_2026()
    L = ["# G108 bước 4: test 2026 của ứng viên C3 (mở một lần)", "",
         "Khóa trước khi mở: `plans/2026-10-13-g108-m30-path-plans.md`, mục \"Bước 4\". Nhãn rr3 (SL swing M5, TP 3R, tối đa 24 giờ), "
         "mô hình C3 (LightGBM bỏ đường đi M5, học lại hàng tháng), top 10% EV, mỗi chiều một lệnh mỗi lúc. "
         "Test 01/01–13/10/2026. R theo 1R mỗi lệnh, spread thật.", "",
         f"S07 cùng kỳ (đối chiếu DD): {s07_n} chân, tổng {s07_tot:+.1f}R (R × trọng số), DD {s07_dd:.1f}R.", ""]
    verdict = {}
    for d, dn in (("1", "MUA"), ("-1", "BÁN")):
        L += [f"## {dn}", "", "| Tiêu chí | ea | raw |", "|---|---|---|"]
        rows, oks = {}, {}
        for src in SOURCES:
            r = res[src]["dirs"][d]
            c3 = r["C3 no path"]
            c = {}
            c["n"] = c3["n"] >= 100
            c["mean"] = c3["mean"] > 0 and r.get("lb", -1) > 0
            c["controls"] = (r["c1"]["p"] < 0.05 and all(c3["mean"] > r[k]["mean"] for k in ("lgbm", "C2 time", "C4 shuffled")))
            c["spread"] = r.get("ex_month", {}).get("mean", -1) > 0 and r.get("ex_hour", {}).get("mean", -1) > 0
            c["dd"] = r.get("dd", 1e9) <= s07_dd
            oks[src] = c
            rows[src] = r
        def cell(src, txt, key):
            return f"{txt} {'✔' if oks[src][key] else '✘'}"
        L.append("| 1. ≥ 100 lệnh | " + " | ".join(cell(s, str(rows[s]['C3 no path']['n']), 'n') for s in SOURCES) + " |")
        L.append("| 2. R/lệnh (cận dưới 90%) | " + " | ".join(
            cell(s, f"{rows[s]['C3 no path']['mean']:+.3f} ({rows[s].get('lb', float('nan')):+.3f})", 'mean') for s in SOURCES) + " |")
        L.append("| 3. Đối chứng: C1 ngẫu nhiên (p) · lgbm · C2 · C4 | " + " | ".join(
            cell(s, f"p {rows[s]['c1']['p']:.3f} · {rows[s]['lgbm']['mean']:+.3f} · {rows[s]['C2 time']['mean']:+.3f} · "
                    f"{rows[s]['C4 shuffled']['mean']:+.3f}", 'controls') for s in SOURCES) + " |")
        L.append("| 4. Bỏ tháng tốt nhất · bỏ giờ tốt nhất | " + " | ".join(
            cell(s, f"{rows[s].get('ex_month', {}).get('mean', float('nan')):+.3f} ({rows[s].get('ex_month', {}).get('month', '—')}) · "
                    f"{rows[s].get('ex_hour', {}).get('mean', float('nan')):+.3f} ({rows[s].get('ex_hour', {}).get('hour', '—')}h)", 'spread')
            for s in SOURCES) + " |")
        L.append("| 5. DD (R) so với S07 | " + " | ".join(cell(s, f"{rows[s].get('dd', float('nan')):.1f}R", 'dd') for s in SOURCES) + " |")
        L.append("| Tái lập validate 04–12/2025 (C3) | " + " | ".join(f"{rows[s]['validate_c3'][0]} / {rows[s]['validate_c3'][1]:+.3f}" for s in SOURCES) + " |")
        L.append("| Vào mọi plan (tham khảo) | " + " | ".join(f"{rows[s]['all_plans']:+.3f}" for s in SOURCES) + " |")
        L.append("| Tổng R | " + " | ".join(f"{rows[s].get('total', 0.0):+.1f}" for s in SOURCES) + " |")
        ok = all(all(oks[s].values()) for s in SOURCES)
        verdict[dn] = ok
        L += ["", f"**{dn}: {'ĐẠT' if ok else 'KHÔNG ĐẠT'}** (cần đạt mọi tiêu chí trên cả hai nguồn).", ""]
        L += ["Theo tháng (ea): " + ", ".join(f"{k} {v[0]} lệnh {v[1]:+.1f}R" for k, v in rows["ea"].get("by_month", {}).items()), ""]
    L += [f"## Kết luận theo luật: MUA {'ĐẠT' if verdict['MUA'] else 'không đạt'}, BÁN {'ĐẠT' if verdict['BÁN'] else 'không đạt'}.", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
