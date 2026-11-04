"""G165: XAU / XAG spread mean-reversion hedge bot (feasibility), D1 sampled at 18:00 UTC, 07/2016 - 11/2026.
s = ln XAU - beta ln XAG (M1 beta 1, M2 rolling 120-day OLS), z over N days; enter |z| >= k against z, exit z back to 0, stop at |z| >= k + 2,
time 10 days. Plan: docs/superpowers/plans/2026-11-04-g165-xau-xag-pair-hedge.md (with the pre-run amendment).

Usage: g165_xau_xag_pair.py <research data dir> <ingest dir> <MT5 raw XAU D1 csv> <g165 results dir>
"""
import itertools
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SEL0, SEL1, END = pd.Timestamp("2016-07-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2026-11-05")
H1_REAL = pd.Timestamp("2018-03-19")
CAP_R = 1.0
SP = {"XAU": 0.28, "XAG": 0.031}                      # MT5 median spread, USD per ounce
LOT = {"XAU": 100.0, "XAG": 5000.0}
COMM = 6.0                                             # USD per lot per leg, round turn
SWAP = {("XAU", 1): -74.18, ("XAU", -1): 28.54, ("XAG", 1): -47.0, ("XAG", -1): 23.2}   # USD per lot per night
HOLD, SEED, RUNS = 10, 165, 200


# ---------------------------------------------------------------------------------------------------- data
def us_dst(d):
    y = d.year
    mar = date(y, 3, 8) + timedelta(days=(6 - date(y, 3, 8).weekday()) % 7)     # second Sunday of March
    nov = date(y, 11, 1) + timedelta(days=(6 - date(y, 11, 1).weekday()) % 7)   # first Sunday of November
    return mar <= d < nov


def h1_at_18utc(df, tcol="time"):
    """{date: close of the H1 bar 17:00-18:00 UTC} from server-time bars (server = UTC + 3 in US DST, else + 2)."""
    srv = pd.to_datetime(df[tcol], unit="s")
    off = np.array([3 if us_dst(x.date()) else 2 for x in srv])
    utc = srv - pd.to_timedelta(off, unit="h")
    m = utc.dt.hour == 17
    return dict(zip(utc[m].dt.normalize(), df["close"][m].astype(float)))


def build(data_dir, ingest_dir, raw_xau, res_dir):
    xau_h1 = pd.read_csv(Path(data_dir) / "h1v" / "XAUUSD.csv")
    mt5_xau = pd.read_csv(Path(res_dir) / "mt5_XAUUSD_H1.csv")
    mt5_xag = pd.read_csv(Path(res_dir) / "mt5_XAGUSD_H1.csv")
    xau18 = h1_at_18utc(xau_h1[pd.to_datetime(xau_h1["time"], unit="s") >= H1_REAL])
    xau18.update({k: v for k, v in h1_at_18utc(mt5_xau).items() if k not in xau18})
    xag18_mt5 = h1_at_18utc(mt5_xag)
    raw = pd.read_csv(raw_xau, sep="\t")
    xau_d1 = dict(zip(pd.to_datetime(raw["<DATE>"], format="%Y.%m.%d"), raw["<CLOSE>"].astype(float)))
    ing = pd.read_csv(Path(ingest_dir) / "XAGUSD" / "XAGUSD_1d.csv.gz")
    ing["date"] = pd.to_datetime(ing["time_utc"]).dt.normalize()
    xag_ing = dict(zip(ing["date"], ing["close"].astype(float)))
    junction = ing["date"].max()
    rows = []
    days = pd.bdate_range(SEL0 - pd.Timedelta(days=200), END)
    for d in days:
        b = xag_ing.get(d) if d <= junction else xag18_mt5.get(d)
        if d < H1_REAL:
            a, sync = xau_d1.get(d), False
        else:
            a, sync = xau18.get(d), True
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
            continue
        rows.append((d, a, b, sync))
    D = pd.DataFrame(rows, columns=["date", "xau", "xag", "sync"])
    mt5_only = pd.DataFrame([(d, xau18[d], xag18_mt5[d]) for d in sorted(set(xau18) & set(xag18_mt5))], columns=["date", "xau", "xag"])
    mt5_only["sync"] = True
    return D, mt5_only, junction


# ---------------------------------------------------------------------------------------------------- engine
def signals(D, beta_mode, N):
    la, lb = np.log(D["xau"].to_numpy()), np.log(D["xag"].to_numpy())
    n = len(la)
    beta = np.ones(n)
    if beta_mode == "M2":
        beta = np.full(n, np.nan)
        for t in range(120, n):
            x, y = lb[t - 119:t + 1], la[t - 119:t + 1]
            beta[t] = np.polyfit(x, y, 1)[0]
    s = la - beta * lb
    z = np.full(n, np.nan)
    sd = np.full(n, np.nan)
    for t in range(N - 1, n):
        if not np.isfinite(beta[t]):
            continue
        # spread recomputed with today's beta over the window (known at the close of t)
        w = la[t - N + 1:t + 1] - beta[t] * lb[t - N + 1:t + 1]
        m, v = w.mean(), w.std()
        if v > 0:
            z[t], sd[t] = (s[t] - m) / v, v
    return z, sd, beta, s


def cost_frac(D, t0, t1, d, beta, mult=1.0):
    """Costs as a fraction of the gold-leg value (gold value 1, silver value beta). d = +1 long spread (long gold, short silver)."""
    a0, b0 = D["xau"].iat[t0], D["xag"].iat[t0]
    f = 0.0
    for sym, side, val, px in (("XAU", d, 1.0, a0), ("XAG", -d, beta, b0)):
        f += val * (2 * SP[sym] * mult) / px                               # spread + 2 x 0.5 spread slippage
        f += val * COMM * mult / (LOT[sym] * px)
        nights = 0
        for t in range(t0, t1):
            nights += 3 if D["date"].iat[t].weekday() == 2 else 1
        f -= val * nights * SWAP[(sym, side)] * (mult if SWAP[(sym, side)] < 0 else 1.0) / (LOT[sym] * px)
    return f


def run(D, beta_mode, N, k, mult=1.0, forced=None):
    """Trades: (entry idx, exit idx, d, R, reason). forced = list of (entry idx, d, hold) for the random control."""
    z, sd, beta, s = signals(D, beta_mode, N)
    a, b = D["xau"].to_numpy(), D["xag"].to_numpy()
    n = len(a)
    out = []
    t = 0
    plan = sorted(forced) if forced else None
    pi = 0
    while t < n - 1:
        if plan is not None:
            if pi >= len(plan):
                break
            e, d, hold = plan[pi]
            pi += 1
            if e < t or e + 1 >= n or not np.isfinite(sd[e]):
                continue
            ti, x = e + 1, min(n - 1, e + 1 + hold)
            reason = "ngẫu nhiên"
        else:
            if not (np.isfinite(z[t]) and abs(z[t]) >= k):
                t += 1
                continue
            e, d = t, -int(np.sign(z[t]))
            ti = e + 1
            x, reason = None, None
            for j in range(ti, n):
                if not np.isfinite(z[j]):
                    continue
                if d * z[j] >= 0:
                    x, reason = j + 1, "z về 0"
                elif -d * z[j] >= k + 2:
                    x, reason = j + 1, "SL tổng"
                elif j - ti + 1 >= HOLD:
                    x, reason = j + 1, "hết giờ"
                if x is not None:
                    break
            if x is None or x >= n:
                break
        bt = beta[e]
        gross = d * ((a[x] / a[ti] - 1) - bt * (b[x] / b[ti] - 1))
        c = cost_frac(D, ti, x, d, bt, mult)
        R = (gross - c) / (2 * sd[e])
        out.append({"e": e, "in": ti, "x": x, "d": d, "R": R, "gross_R": gross / (2 * sd[e]), "cost_R": c / (2 * sd[e]), "reason": reason,
                    "date": D["date"].iat[ti], "sync": bool(D["sync"].iat[ti]), "days": x - ti, "beta": bt, "sd": sd[e]})
        t = x
    return out


def metrics(tr, a=None, z=None):
    x = [q for q in tr if (a is None or q["date"] >= a) and (z is None or q["date"] < z)]
    if not x:
        return {"n": 0, "tổng R": 0.0}
    r = np.array([q["R"] for q in x])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    reasons = {}
    for q in x:
        reasons[q["reason"]] = reasons.get(q["reason"], 0) + 1
    gross_pos = sum(max(q["gross_R"], 0) for q in x)
    return {"n": len(x), "tỷ lệ thắng": round(float(np.mean(r > 0)), 3), "R TB": round(float(r.mean()), 3),
            "PF": round(float(pos / neg), 2) if neg > 0 else None, "tổng R": round(float(r.sum()), 2), "DD R": round(dd, 2),
            "MAR": round(float(r.sum()) / dd, 2) if dd > 0 else None, "giữ TB (ngày)": round(float(np.mean([q["days"] for q in x])), 1),
            "chi phí TB (R)": round(float(np.mean([q["cost_R"] for q in x])), 3),
            "mua chênh lệch R": round(float(sum(q["R"] for q in x if q["d"] == 1)), 2),
            "bán chênh lệch R": round(float(sum(q["R"] for q in x if q["d"] == -1)), 2),
            "chi phí / lãi gộp dương": round(sum(q["cost_R"] for q in x) / gross_pos, 3) if gross_pos > 0 else None, "lý do thoát": reasons}


def neutrality(D, tr):
    """Correlation of the bot's daily marked-to-market R with gold's daily return, on days with an open basket."""
    a, b = D["xau"].to_numpy(), D["xag"].to_numpy()
    xs, ys = [], []
    for q in tr:
        for t in range(q["in"] + 1, q["x"] + 1):
            dr = q["d"] * ((a[t] / a[t - 1] - 1) - q["beta"] * (b[t] / b[t - 1] - 1)) * (a[t - 1] / a[q["in"]])
            xs.append(dr / (2 * q["sd"]))
            ys.append(a[t] / a[t - 1] - 1)
    return round(float(np.corrcoef(xs, ys)[0, 1]), 3) if len(xs) > 10 else None


def half_life(s):
    s = s[np.isfinite(s)]
    ds, lag = np.diff(s), s[:-1]
    bcoef = np.polyfit(lag, ds, 1)[0]
    return round(float(-np.log(2) / np.log(1 + bcoef)), 1) if -1 < bcoef < 0 else None


def main():
    data_dir, ingest_dir, raw_xau, res = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
    D, M, junction = build(data_dir, ingest_dir, raw_xau, res)
    D = D.reset_index(drop=True)
    print("data", len(D), D["date"].min().date(), D["date"].max().date(), "async days", int((~D["sync"]).sum()), "junction", junction.date(),
          "| mt5-only", len(M), M["date"].min().date(), flush=True)
    # code check: one basket by hand
    out = {"dữ liệu": {"ngày": len(D), "từ": str(D["date"].min().date()), "đến": str(D["date"].max().date()),
                       "ngày lệch giờ (trước 19/03/2018)": int((~D["sync"]).sum()), "nối XAG ingest → MT5": str(junction.date())},
           "cấu hình": {}}
    trades = {}
    for bm, N, k in itertools.product(("M1", "M2"), (10, 20), (2.0, 2.5)):
        tr = run(D, bm, N, k)
        trades[(bm, N, k)] = tr
        key = f"{bm} N{N} k{k}"
        out["cấu hình"][key] = {"kỳ chọn": metrics(tr, SEL0, SEL1), "kỳ kiểm": metrics(tr, SEL1, END), "cả kỳ": metrics(tr, SEL0, END)}
        s_, k_ = out["cấu hình"][key]["kỳ chọn"], out["cấu hình"][key]["kỳ kiểm"]
        print(key, "| chọn n", s_["n"], "R", s_["tổng R"], "MAR", s_.get("MAR"), "PF", s_.get("PF"), "| kiểm n", k_["n"], "R", k_["tổng R"], "PF", k_.get("PF"),
              "| mua/bán", out["cấu hình"][key]["cả kỳ"].get("mua chênh lệch R"), out["cấu hình"][key]["cả kỳ"].get("bán chênh lệch R"), flush=True)
    # hand check of the first basket of the first configuration
    q = trades[("M1", 10, 2.0)][0]
    a0, a1, b0, b1 = D["xau"].iat[q["in"]], D["xau"].iat[q["x"]], D["xag"].iat[q["in"]], D["xag"].iat[q["x"]]
    hand = q["d"] * ((a1 / a0 - 1) - 1.0 * (b1 / b0 - 1)) / (2 * q["sd"])
    out["kiểm code: rổ đầu tính tay"] = {"engine gross R": round(q["gross_R"], 6), "tính tay": round(hand, 6), "khớp": abs(hand - q["gross_R"]) < 1e-12}
    cands = [(kk, v) for kk, v in out["cấu hình"].items() if v["kỳ chọn"]["n"] >= 15 and v["kỳ chọn"].get("MAR") is not None]
    key, row = max(cands, key=lambda kv: kv[1]["kỳ chọn"]["MAR"])
    bm, N, k = key.split()[0], int(key.split()[1][1:]), float(key.split()[2][1:])
    tr = trades[(bm, N, k)]
    full = row["cả kỳ"]
    rng = np.random.default_rng(SEED)
    holds = [q["days"] for q in tr]
    p_long = np.mean([q["d"] == 1 for q in tr])
    valid = [t for t in range(len(D) - 2) if SEL0 <= D["date"].iat[t] < END]
    rnd = []
    for _ in range(RUNS):
        es = sorted(rng.choice(valid, size=len(tr), replace=False))
        plan = [(int(e), 1 if rng.random() < p_long else -1, int(rng.choice(holds))) for e in es]
        rnd.append(metrics(run(D, bm, N, k, forced=plan), SEL0, END)["tổng R"])
    mom = sum(-q["gross_R"] - q["cost_R"] for q in tr if SEL0 <= q["date"] < END)
    harsh = metrics(run(D, bm, N, k, mult=1.5), SEL0, END)
    rho = neutrality(D, [q for q in tr if SEL0 <= q["date"] < END])
    z, sd, beta, s = signals(D, bm, N)
    hl = {"cả kỳ": half_life(s), "kỳ chọn": half_life(s[(D["date"] >= SEL0) & (D["date"] < SEL1)]), "kỳ kiểm": half_life(s[D["date"] >= SEL1])}
    kk = row["kỳ kiểm"]
    crit = {"1 kỳ kiểm R > 0, PF ≥ 1,2, ≥ 15 rổ": kk["tổng R"] > 0 and (kk.get("PF") or 0) >= 1.2 and kk["n"] >= 15,
            "2 mua và bán chênh lệch ≥ 0": full["mua chênh lệch R"] >= 0 and full["bán chênh lệch R"] >= 0,
            "3 hơn p90 ngẫu nhiên": full["tổng R"] > float(np.percentile(rnd, 90)),
            "4 hơn bản đánh theo đà": full["tổng R"] > mom,
            "5 |ρ| với vàng < 0,3": rho is not None and abs(rho) < 0.3,
            "6 chi phí × 1,5 vẫn R > 0": harsh["tổng R"] > 0}
    # sensitivity (not criteria): pure MT5 spot both legs, and before / after the synchronous-data date
    trm = run(M.reset_index(drop=True), bm, N, k)
    trm_mixed = [q for q in tr if q["date"] >= M["date"].min() + pd.Timedelta(days=60)]
    out["được chọn"] = {"cấu hình": key, "kỳ chọn": row["kỳ chọn"], "kỳ kiểm": kk, "cả kỳ": full,
                        "ngẫu nhiên tổng R p50 / p90": [round(float(np.percentile(rnd, 50)), 2), round(float(np.percentile(rnd, 90)), 2)],
                        "đánh theo đà tổng R": round(mom, 2), "chi phí × 1,5": harsh, "tương quan với lợi suất ngày của vàng": rho,
                        "half-life chênh lệch (ngày)": hl,
                        "trước 19/03/2018 (lệch giờ)": metrics([q for q in tr if not q["sync"]]),
                        "từ 19/03/2018 (cùng giờ)": metrics([q for q in tr if q["sync"]]),
                        "độ nhạy: 2 chân MT5 spot (02/2024–11/2026)": metrics(trm),
                        "cùng đoạn, dữ liệu gộp": metrics(trm_mixed),
                        "tiêu chí": crit, "đáng lấy dữ liệu dài": all(crit.values())}
    (res / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    sel = out["được chọn"]
    print("chosen", key, "\n kiểm", kk, "\n cả kỳ", full, "\n rand", sel["ngẫu nhiên tổng R p50 / p90"], "| mom", sel["đánh theo đà tổng R"],
          "| harsh", harsh["tổng R"], "| rho", rho, "| HL", hl, "\n pre2018", sel["trước 19/03/2018 (lệch giờ)"], "\n post", sel["từ 19/03/2018 (cùng giờ)"],
          "\n mt5 spot", sel["độ nhạy: 2 chân MT5 spot (02/2024–11/2026)"], "\n mixed same span", sel["cùng đoạn, dữ liệu gộp"], "\n crit", crit,
          "\n hand", out["kiểm code: rổ đầu tính tay"], flush=True)


if __name__ == "__main__":
    main()
