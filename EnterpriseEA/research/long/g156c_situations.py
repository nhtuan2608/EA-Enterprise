"""G156c: 12 named situations (news timing, sweeps vs the D1 regime, volume divergence, gold-USD same direction, contrarian news
reaction, multi-timeframe agreement, confluent / multi-tested key levels, break-retest-hold), each vs its own control on a symmetric
+/-1 ATR M30 first-passage outcome over 4 h. Plan: docs/superpowers/plans/2026-10-24-g156c-situation-library.md.

Usage: g156c_situations.py <data dir> <out dir>
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g156a_questions as qa  # noqa: E402
from g148_layered_risk_map import calendar  # noqa: E402

BAR, HORIZON, GAP = 1800, 8, 4
START, END = g.ts(2018, 5, 1), g.ts(2026, 7, 1)
PER = [("05/2018–2021", g.ts(2018, 5, 1), g.ts(2022, 1, 1)), ("2022–2023", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("2024–06/2026", g.ts(2024, 1, 1), END)]
BOOT, ALPHA, SEED = 2000, 0.05 / 12, 156


def first_passage(D):
    """r[i]: +1 up 1 ATR first, -1 down first, 0 neither in 8 bars, 2 both in one bar (from the close of bar i)."""
    h, l, c, A = D["h"], D["l"], D["c"], D["atr"]
    n = len(c)
    up, dn = c + A, c - A
    r = np.zeros(n, int)
    done = np.zeros(n, bool)
    for k in range(1, HORIZON + 1):
        j = np.minimum(np.arange(n) + k, n - 1)
        valid = (np.arange(n) + k) <= n - 1
        hu, hd = (h[j] >= up) & valid, (l[j] <= dn) & valid
        both = ~done & hu & hd
        r[both] = 2
        first_up = ~done & hu & ~hd
        first_dn = ~done & hd & ~hu
        r[first_up] = 1
        r[first_dn] = -1
        done |= both | first_up | first_dn
    r[np.arange(n) >= n - HORIZON] = 0
    return r


def dedupe(idx):
    out, last = [], -10 ** 9
    for i in sorted(set(int(x) for x in idx)):
        if i - last >= GAP:
            out.append(i)
            last = i
    return out


class Book:
    def __init__(self, D, r):
        self.D, self.r = D, r

    def rows(self, idx, dirs):
        """(bar, d, outcome +1 THEO / -1 NGƯỢC) for decided events inside 05/2018–06/2026 and after."""
        t = self.D["t"]
        out = []
        for i, d in zip(idx, dirs):
            if d == 0 or t[i] < START:
                continue
            o = self.r[i]
            if o in (1, -1):
                out.append((int(i), int(d), 1 if o == d else -1))
        return out


def stats(D, sit, ctl, rng):
    t = D["t"]
    def per(rows, a, z):
        x = [o for i, d, o in rows if a <= t[i] < z]
        return (sum(1 for o in x if o == 1), len(x))
    res = {"tình huống": {}, "đối chứng": {}, "chênh theo kỳ": {}}
    signs = []
    for pn, a, z in PER:
        s1, n1 = per(sit, a, z)
        s0, n0 = per(ctl, a, z)
        p1 = s1 / n1 if n1 else None
        p0 = s0 / n0 if n0 else None
        res["tình huống"][pn] = {"n": n1, "P(THEO)": round(p1, 3) if p1 is not None else None}
        res["đối chứng"][pn] = {"n": n0, "P(THEO)": round(p0, 3) if p0 is not None else None}
        if p1 is not None and p0 is not None and n1 >= 30:
            res["chênh theo kỳ"][pn] = round(p1 - p0, 3)
            signs.append(np.sign(p1 - p0))
    s1, n1 = per(sit, START, END)
    s0, n0 = per(ctl, START, END)
    diff = (s1 / n1 - s0 / n0) if n1 and n0 else None
    # week-block bootstrap of the pooled difference
    wk = lambda i: int(t[i] // (7 * 86400))  # noqa: E731
    weeks = {}
    for rows, k in ((sit, 0), (ctl, 2)):
        for i, d, o in rows:
            if START <= t[i] < END:
                w = weeks.setdefault(wk(i), [0, 0, 0, 0])
                w[k] += o == 1
                w[k + 1] += 1
    W = np.array(list(weeks.values()), float)
    ci = None
    if len(W) and n1 and n0:
        b = []
        for _ in range(BOOT):
            S = W[rng.integers(0, len(W), len(W))].sum(0)
            if S[1] > 0 and S[3] > 0:
                b.append(S[0] / S[1] - S[2] / S[3])
        ci = [round(float(np.percentile(b, 100 * ALPHA / 2)), 3), round(float(np.percentile(b, 100 * (1 - ALPHA / 2))), 3)]
    after = (per(sit, END, 2 ** 40), per(ctl, END, 2 ** 40))
    res["gộp"] = {"n tình huống": n1, "P tình huống": round(s1 / n1, 3) if n1 else None, "n đối chứng": n0,
                  "P đối chứng": round(s0 / n0, 3) if n0 else None, "chênh": round(diff, 3) if diff is not None else None,
                  "CI 99,6 %": ci}
    res["sau 07/2026"] = {"tình huống": f"{after[0][0]}/{after[0][1]}", "đối chứng": f"{after[1][0]}/{after[1][1]}"}
    return res, signs


def main():
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = g.load("XAUUSD")
    F = qa.features(D)
    legs = qa.s07_legs(root)
    D = g.load("XAUUSD")
    t, o, h, l, c, v, A = D["t"], D["o"], D["h"], D["l"], D["c"], D["v"], D["atr"]
    n = len(c)
    r = first_passage(D)
    bk = Book(D, r)
    rng = np.random.default_rng(SEED)
    hour = (t % 86400) // 3600
    reg = F["chế độ D1"]
    news = calendar()[0]
    close_t = t + BAR
    k_next = np.searchsorted(news, close_t, side="left")
    nxt = np.where(k_next < len(news), news[np.minimum(k_next, len(news) - 1)] - close_t, np.inf)
    prv = np.where(k_next > 0, close_t - news[np.maximum(k_next - 1, 0)], np.inf)
    quiet = (nxt > 3 * 3600) & (prv > 3 * 3600)
    ret4 = np.sign(c - np.r_[np.full(4, np.nan), c[:-4]])
    cand = np.sign(c - o)
    S = {}

    # T1 before news
    ev = np.nonzero((nxt >= 1800) & (nxt <= 3600))[0]
    hrs = set(hour[ev].tolist())
    ctl = np.nonzero(quiet & np.isin(hour, list(hrs)))[0]
    S["T1 trước tin"] = (dedupe(ev), "ret4", dedupe(ctl), "ret4")
    # T2 news candle
    bar_of = np.searchsorted(t, news, side="right") - 1
    ev2 = [int(i) for i, tn in zip(bar_of, news) if 0 <= i < n and t[i] <= tn < t[i] + BAR]
    hrs2 = set(hour[ev2].tolist())
    ctl2 = np.nonzero(quiet & np.isin(hour, list(hrs2)))[0]
    S["T2 nến tin"] = (dedupe(ev2), "cand", dedupe(ctl2), "cand")
    # T3 news at 15:30 server, measured at the 16:30 close (New York open)
    pos = {int(x): i for i, x in enumerate(t)}
    day = t // 86400
    news_1530 = {int(tn // 86400) for tn in news if tn % 86400 == 15 * 3600 + 1800}
    any_15_16 = {int(tn // 86400) for tn in news if 15 * 3600 <= tn % 86400 < 16 * 3600 + 1800}
    ev3, d3, ctl3, dc3 = [], [], [], []
    for dk in sorted(set(day.tolist())):
        a_, b_ = pos.get(dk * 86400 + 15 * 3600 + 1800), pos.get(dk * 86400 + 16 * 3600)
        if a_ is None or b_ is None:
            continue
        dd = int(np.sign(c[b_] - o[a_]))
        if dk in news_1530:
            ev3.append(b_); d3.append(dd)
        elif dk not in any_15_16:
            ctl3.append(b_); dc3.append(dd)
    S["T3 tin đã ra, chưa mở phiên Mỹ"] = (ev3, d3, ctl3, dc3)
    # T4 / T5 sweeps
    sw_i, sw_d = [], []
    for i in range(1, n):
        dd = 0
        for lv in (F["_lv"]["PDL"][i], F["_lv"]["Á dưới"][i]):
            if np.isfinite(lv) and l[i] < lv < c[i]:
                dd = 1
        for lv in (F["_lv"]["PDH"][i], F["_lv"]["Á trên"][i]):
            if np.isfinite(lv) and h[i] > lv > c[i]:
                dd = -1 if dd == 0 else 0
        if dd:
            sw_i.append(i); sw_d.append(dd)
    sw_i, sw_d = np.array(sw_i), np.array(sw_d)
    with_d1 = reg[sw_i] == sw_d
    against = reg[sw_i] == -sw_d
    allreg = np.nonzero(reg != 0)[0]
    e4 = dedupe(sw_i[with_d1]); d4 = {int(i): int(d) for i, d in zip(sw_i, sw_d)}
    S["T4 quét rồi rút cùng chiều D1"] = (e4, [d4[i] for i in e4], dedupe(allreg), "reg")
    e5 = dedupe(sw_i[against])
    S["T5 quét rồi rút ngược D1"] = (e5, [d4[i] for i in e5], dedupe(allreg), "-reg")
    # T6 volume divergence
    ret8 = c - np.r_[np.full(8, np.nan), c[:-8]]
    vv = np.convolve(v, np.ones(4) / 4, "full")[:n]                       # mean of v[i-3..i]
    vr = vv / np.r_[np.full(4, np.nan), vv[:-4]]
    big = np.abs(ret8) >= 1.5 * A
    S["T6 giá chạy mà volume giảm"] = (dedupe(np.nonzero(big & (vr < 0.8))[0]), "ret8", dedupe(np.nonzero(big & (vr >= 1.0))[0]), "ret8")
    # T7 gold and DXY in the same direction
    dxy = {}
    with open(root / "m30v" / "DXY.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            dxy[int(row["time"])] = (float(row["high"]), float(row["low"]), float(row["close"]))
    dt = np.array(sorted(dxy))
    dh = np.array([dxy[x][0] for x in dt]); dl = np.array([dxy[x][1] for x in dt]); dcl = np.array([dxy[x][2] for x in dt])
    dpc = np.r_[dcl[0], dcl[:-1]]
    datr = g.rma(np.maximum(dh - dl, np.maximum(abs(dh - dpc), abs(dl - dpc))), 14)
    dret8 = dcl - np.r_[np.full(8, np.nan), dcl[:-8]]
    dpos = {int(x): k for k, x in enumerate(dt)}
    e7, c7 = [], []
    for i in np.nonzero(np.abs(ret8) >= A)[0]:
        k = dpos.get(int(t[i]))
        if k is None or not np.isfinite(dret8[k]) or datr[k] <= 0:
            continue
        s = np.sign(ret8[i])
        if np.sign(dret8[k]) == s and abs(dret8[k]) >= datr[k]:
            e7.append(i)
        elif np.sign(dret8[k]) == -s and abs(dret8[k]) >= 0.5 * datr[k]:
            c7.append(i)
    S["T7 vàng và USD cùng chiều"] = (dedupe(e7), "ret8", dedupe(c7), "ret8")
    # T8 contrarian news reaction (G129 surprise sign: d = direction the surprise implies for gold)
    import g129_gold_news as g129
    sur, _, _ = g129.events()
    e8, c8 = [], []
    for e in sur:
        i = int(np.searchsorted(t, e["t"], side="right")) - 1
        if i < 0 or not (t[i] <= e["t"] < t[i] + BAR) or abs(c[i] - o[i]) < 0.5 * A[i]:
            continue
        (e8 if cand[i] == -e["d"] else c8).append(i)
    S["T8 phản ứng ngược kỳ vọng tin"] = (dedupe(e8), "cand", dedupe(c8), "cand")
    # T9-T12 on the G156a level-break events
    ema50 = g.ema(c, 50)
    swings = qa.swing_levels(D)
    sw_L = np.array([s[2] for s in swings]); sw_a = np.array([s[3] for s in swings]); sw_life = np.array([s[4] for s in swings])
    sw_dir = np.array([s[1] for s in swings])
    sw_end = np.full(len(swings), n)
    for k, (name, d, L, a, life) in enumerate(swings):
        for i in range(a, n):
            if t[i] >= life:
                sw_end[k] = i; break
            if (d == 1 and c[i] > L and c[i - 1] <= L) or (d == -1 and c[i] < L and c[i - 1] >= L):
                sw_end[k] = i; break
    fam = {"Á trên": "Á", "Á dưới": "Á", "PDH": "PD", "PDL": "PD", "PWH": "PW", "PWL": "PW", "swing đỉnh": "swing", "swing đáy": "swing"}
    q1 = [(i, d, name, L) for i, d, name, L in qa.q1_events(D, F) if t[i] >= START]
    e9, c9, e10, c10, e11, c11, e12, d12, c12 = [], [], [], [], [], [], [], [], []
    for i, d, name, L in q1:
        a_i = A[i]
        tf = [np.sign(c[i] - ema50[i]), np.sign(c[i] - D["E"][100][i]), D["h4_side"][i], reg[i]]
        (e9 if all(x == d for x in tf) else c9).append((i, d))
        near = 0
        for nm, lvarr in F["_lv"].items():
            if fam[nm] != fam[name] and np.isfinite(lvarr[i]) and abs(lvarr[i] - L) <= 0.5 * a_i:
                near += 1
        if fam[name] != "swing":
            m = (sw_a <= i) & (sw_end > i) & (np.abs(sw_L - L) <= 0.5 * a_i)
            near += int(m.sum())
        (e10 if near >= 1 else c10).append((i, d))
        # touches during the level's validity (start of day / week / 08:00 / swing confirmation)
        if fam[name] == "swing":
            k = int(np.argmin(np.abs(sw_L - L) + (sw_dir != d) * 1e9 + (sw_a > i) * 1e9))
            s0 = sw_a[k]
        elif fam[name] == "PW":
            s0 = int(np.searchsorted(t, ((t[i] // 86400 + 3) // 7 * 7 - 3) * 86400))
        else:
            s0 = int(np.searchsorted(t, (t[i] // 86400) * 86400 + (8 * 3600 if fam[name] == "Á" else 0)))
        seg = slice(max(s0, 0), i)
        if d == 1:
            touch = int(((h[seg] >= L - 0.25 * A[seg]) & (c[seg] <= L)).sum())
        else:
            touch = int(((l[seg] <= L + 0.25 * A[seg]) & (c[seg] >= L)).sum())
        if touch >= 3:
            e11.append((i, d))
        elif touch <= 1:
            c11.append((i, d))
        if fam[name] in ("PD", "PW"):
            c12.append((i, d))
            for j in range(i + 1, min(i + 7, n)):
                if (d == 1 and c[j] <= L) or (d == -1 and c[j] >= L):
                    break
                if (d == 1 and l[j] <= L + 0.25 * A[j]) or (d == -1 and h[j] >= L - 0.25 * A[j]):
                    e12.append((j, d)); break

    def pairs(lst):
        kept = dedupe([i for i, _ in lst]); dm = dict(lst)
        return kept, [dm[i] for i in kept]

    for key, (ev_, ct_) in (("T9 đồng thuận đa khung", (e9, c9)), ("T10 key level hợp lưu", (e10, c10)),
                            ("T11 key level đã test nhiều lần", (e11, c11)), ("T12 phá + retest giữ", (e12, c12))):
        a1, b1 = pairs(ev_); a0, b0 = pairs(ct_)
        S[key] = (a1, b1, a0, b0)

    def dirs(idx, spec):
        idx = np.asarray(idx, int)
        if not isinstance(spec, str):
            return list(spec)
        if spec == "ret4":
            return [int(x) if np.isfinite(x) else 0 for x in ret4[idx]]
        if spec == "cand":
            return [int(x) for x in cand[idx]]
        if spec == "ret8":
            return [int(np.sign(x)) if np.isfinite(x) else 0 for x in ret8[idx]]
        if spec == "reg":
            return [int(x) for x in reg[idx]]
        if spec == "-reg":
            return [int(-x) for x in reg[idx]]
        raise ValueError(spec)

    # S07 base legs: signal bar within the 2 bars after a situation event (report only)
    base = [L for L in legs if L["base"] and START <= L["srv_in"] < END]
    sig_bar = np.array([int(np.searchsorted(t, L["srv_in"] - BAR, side="right")) - 1 for L in base])
    base_r = np.array([L["rh"] for L in base])
    summary = {"S07 tất cả lệnh gốc": {"n": int(len(base_r)), "R TB": round(float(base_r.mean()), 3)}}
    for key, (ei, ed, ci, cd) in S.items():
        sit = bk.rows(ei, dirs(ei, ed))
        ctl = bk.rows(ci, dirs(ci, cd))
        res, signs = stats(D, sit, ctl, rng)
        g_ = res["gộp"]
        need = 2 if key.startswith("T7") else 2
        periods_ok = sum(1 for p, x in res["tình huống"].items() if x["n"] >= 30)
        same = len(signs) >= 2 and g_["chênh"] is not None and sum(1 for s in signs if s == np.sign(g_["chênh"])) >= need
        if key.startswith("T7"):
            same = all(p in res["chênh theo kỳ"] for p in ("2022–2023", "2024–06/2026")) and \
                np.sign(res["chênh theo kỳ"]["2022–2023"]) == np.sign(res["chênh theo kỳ"]["2024–06/2026"]) == np.sign(g_["chênh"])
            periods_ok = 3 if all(res["tình huống"][p]["n"] >= 30 for p in ("2022–2023", "2024–06/2026")) else 0
        ok = (g_["n tình huống"] >= 100 and periods_ok >= (3 if not key.startswith("T7") else 3) and g_["CI 99,6 %"] is not None
              and (g_["CI 99,6 %"][0] > 0 or g_["CI 99,6 %"][1] < 0) and same)
        res["phân loại"] = "CÓ GIÁ TRỊ DỰ BÁO" if ok else "chỉ cảnh báo / giải thích"
        ev_set = set(int(x) for x in ei)
        hit = np.array([any((s - k) in ev_set for k in (0, 1, 2)) for s in sig_bar])
        res["S07 lệnh gốc trùng tình huống"] = {"n": int(hit.sum()), "R TB": round(float(base_r[hit].mean()), 3) if hit.any() else None}
        summary[key] = res
        print(key, g_, res["chênh theo kỳ"], res["phân loại"], flush=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
