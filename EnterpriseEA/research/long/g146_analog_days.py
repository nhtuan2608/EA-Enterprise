"""G146: analog-day forecast of the NY session (15:30 -> 20:30 server) from the day's context at 15:15.
Plan: docs/superpowers/plans/2026-10-22-g146-analog-days.md.

Usage: g146_analog_days.py <data dir> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
from g143_session_momentum import daily_atr, trade  # noqa: E402

H = 3600
T_FEAT_END, T_ENTRY, T_EXIT = 15 * H, 15 * H + 1800, 20 * H + 900     # last feature bar 15:00, entry bar 15:30, exit bar 20:15
MIN_HIST, MIN_ABS, MIN_AGREE = 250, 0.05, 0.60
PER = [("đầu 08/2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)), ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
       ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1)), ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
DECIDE = [p for p, _, _ in PER[:3]]


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def build_days(D):
    t, o, h, l, c = D["t"], D["o"], D["h"], D["l"], D["c"]
    day = t // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    starts = np.r_[0, ends[:-1] + 1]
    pos = {int(x): k for k, x in enumerate(t)}
    atrd = daily_atr(D)
    daily = {int(day[a]): dict(o=o[a], h=h[a:z + 1].max(), l=l[a:z + 1].min(), c=c[z]) for a, z in zip(starts, ends)}
    keys = sorted(daily)
    out = []
    for n, (a, z) in enumerate(zip(starts, ends)):
        dk = int(day[a])
        base = dk * 86400
        kf, ke, kx = pos.get(base + T_FEAT_END), pos.get(base + T_ENTRY), pos.get(base + T_EXIT)
        A = atrd.get(dk)
        if None in (kf, ke, kx) or not A or A != A or n < 21:
            continue
        prev = daily[keys[n - 1]]
        seg = slice(a, kf + 1)
        hi, lo, cl = h[seg].max(), l[seg].min(), c[kf]
        asia = [k for k in range(a, kf + 1) if t[k] - base < 9 * H]
        ldn = pos.get(base + 10 * H)
        if not asia or ldn is None:
            continue
        f = [(cl - o[a]) / A, (hi - lo) / A, (cl - lo) / max(hi - lo, 1e-9), (cl - prev["c"]) / A, (cl - prev["h"]) / A,
             (cl - prev["l"]) / A, (prev["c"] - prev["o"]) / A, (h[asia].max() - l[asia].min()) / A, (cl - o[ldn]) / A]
        trend = np.sign(prev["c"] - daily[keys[n - 21]]["c"])
        out.append(dict(day=dk, k=kf, e=ke, x=kx, A=A, f=np.array(f), y=(c[kx] - o[ke]) / A, trend=int(trend) or 1,
                        month=int(np.datetime64(base, "s").astype("datetime64[M]").astype(int))))
    # month "not up": the month's last close <= the previous month's last close
    mclose = {}
    for dk in keys:
        mclose[int(np.datetime64(dk * 86400, "s").astype("datetime64[M]").astype(int))] = daily[dk]["c"]
    for x in out:
        x["down_month"] = x["month"] - 1 in mclose and mclose[x["month"]] <= mclose[x["month"] - 1]
    return out


def forecast(days, K):
    F = np.array([x["f"] for x in days])
    Y = np.array([x["y"] for x in days])
    sig = []
    for i in range(MIN_HIST, len(days)):
        past = F[:i]
        mu, sd = past.mean(0), past.std(0) + 1e-9
        z = (past - mu) / sd
        q = (F[i] - mu) / sd
        nn = np.argsort(((z - q) ** 2).sum(1))[:K]
        m = Y[nn].mean()
        agree = (np.sign(Y[nn]) == np.sign(m)).mean()
        sig.append((i, int(np.sign(m)) if abs(m) >= MIN_ABS and agree >= MIN_AGREE else 0))
    return sig


def stat(xs):
    xs = list(xs)
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


def run(D, days, K, full=True):
    rows = []
    for i, d in forecast(days, K):
        if d == 0:
            continue
        x = days[i]
        res = {}
        for dd in (1, -1):
            entry = D["o"][x["e"]] + (D["sp"][x["e"]] if dd == 1 else 0.0)
            res[dd] = trade(D, x["k"], x["e"], x["x"], dd, entry - dd * 0.5 * x["A"])
        if res[1] is None or res[-1] is None:
            continue
        rows.append(dict(p=period(int(D["utc"][x["e"]])), d=d, r=res[d]["rh"], r15=res[d]["rh15"], rb=res[x["trend"]]["rh"],
                         rl=res[1]["rh"], rs=res[-1]["rh"], down=x["down_month"], year=int(np.datetime64(int(D["t"][x["e"]]), "s")
                                                                                              .astype("datetime64[Y]").astype(int) + 1970)))
    rows = [r for r in rows if r["p"]]
    out = {"theo kỳ": {p: stat(r["r"] for r in rows if r["p"] == p) for p, _, _ in PER}}
    if not full:
        return out
    dec = [r for r in rows if r["p"] in DECIDE]
    out["phí×1,5"] = stat(r["r15"] for r in dec)
    out["mua"] = stat(r["r"] for r in dec if r["d"] == 1)
    out["bán"] = stat(r["r"] for r in dec if r["d"] == -1)
    out["tháng không tăng"] = stat(r["r"] for r in dec if r["down"])
    out["tháng tăng"] = stat(r["r"] for r in dec if not r["down"])
    out["mốc xu hướng 20 ngày (cùng ngày)"] = stat(r["rb"] for r in dec)
    out["theo năm"] = {str(y): stat(r["r"] for r in rows if r["year"] == y) for y in range(2022, 2027)}
    rs = sorted(r["r"] for r in dec)
    out["bỏ 3 lệnh lớn nhất"] = stat(rs[:-3])
    rng = np.random.default_rng(146)
    diff = np.array([r["r"] - r["rb"] for r in dec])
    boots = np.array([diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(2000)])
    out["chênh so với mốc"] = round(float(diff.mean()), 3)
    out["p bootstrap (chênh ≤ 0)"] = float((boots <= 0).mean())
    actual = float(np.mean([r["r"] for r in dec]))
    L, S = np.array([r["rl"] for r in dec]), np.array([r["rs"] for r in dec])
    perm = [np.where(rng.random(len(dec)) < 0.5, L, S).mean() for _ in range(2000)]
    out["p hoán vị chiều"] = (sum(x >= actual for x in perm) + 1) / 2001
    per = out["theo kỳ"]
    ok = (all(per[p]["n"] and per[p]["mean"] > 0 for p in DECIDE) and len(dec) >= 150
          and out["chênh so với mốc"] > 0 and out["p bootstrap (chênh ≤ 0)"] <= 0.05
          and out["mua"]["n"] >= 40 and out["mua"]["mean"] > 0 and out["bán"]["n"] >= 40 and out["bán"]["mean"] > 0
          and out["tháng không tăng"]["n"] >= 40 and out["tháng không tăng"]["mean"] > 0
          and out["p hoán vị chiều"] <= 0.05 and out["phí×1,5"]["mean"] > 0)
    out["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M15")
    g.DATA = root / "m15v"
    D = g.load("XAUUSD")
    days = build_days(D)
    res = {"số ngày": len(days), "K=40 (quyết định)": run(D, days, 40)}
    res["độ nhạy K=20 / K=80 (báo cáo)"] = {"K=20": run(D, days, 20, False), "K=80": run(D, days, 80, False)}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
