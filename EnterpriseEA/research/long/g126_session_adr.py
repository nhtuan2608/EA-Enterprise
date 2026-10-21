"""G126: gold session chain (Asia+Europe move, New York follow / reversal -> next sessions) and ADR exhaustion
(fades at k x ADR with confirmation), standalone and as S07 / VHedge filters.
Pre-registered plan: docs/superpowers/plans/2026-10-20-g126-session-chain-adr.md. MT5 data only.

  python g126_session_adr.py

Bars are broker server time; converted to UTC with the g67 rule. Intraday gold bars exist from 03/2018.
2026 is sealed: it is only read for items selected on train + validate, once, at the end.
"""
from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g67_dmi_ema as g67  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-20-g126-session-chain-adr.md"
START = int(datetime(2018, 3, 5, tzinfo=timezone.utc).timestamp())
VAL = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp())
TEST = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 10, tzinfo=timezone.utc).timestamp())
COMM = 0.06
DAY = 86400


def period(u):
    if u < START or u >= END:
        return None
    return "train" if u < VAL else "validate" if u < TEST else "test"


def to_utc(t):
    return np.array([x - (10800 if g67.us_dst(int(x) - 7200) else 7200) for x in t], dtype=np.int64)


def load(tf):
    m = pd.read_csv(HERE / "data" / f"{tf.lower()}v" / "XAUUSD.csv")
    m["utc"] = to_utc(m["time"].to_numpy())
    m = m[m["utc"] >= START - 40 * DAY].reset_index(drop=True)
    m["sp"] = m["spread"] * 0.01
    m["day"] = m["utc"] // DAY
    m["hr"] = (m["utc"] % DAY) // 3600
    m["mn"] = (m["utc"] % DAY) // 60
    return m


def wilder(x, n=14):
    out, a = np.empty(len(x)), None
    for i, v in enumerate(x):
        a = v if a is None else a + (v - a) / n
        out[i] = a
    return out


def daily(m):
    D = m.groupby("day").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = np.r_[D["c"].iloc[0], D["c"].to_numpy()[:-1]]
    tr = np.maximum(D["h"].to_numpy(), pc) - np.minimum(D["l"].to_numpy(), pc)
    D["atr_prev"] = np.r_[np.nan, wilder(tr)[:-1]]                    # known at the day's start
    D["adr_prev"] = (D["h"] - D["l"]).rolling(10).mean().shift(1)
    D["pdh"], D["pdl"] = D["h"].shift(1), D["l"].shift(1)
    return D


def mean(x):
    return statistics.fmean(x) if x else 0.0


def tstat(x):
    if len(x) < 3:
        return 0.0
    s = statistics.stdev(x)
    return mean(x) / (s / math.sqrt(len(x))) if s > 0 else 0.0


def lower90(xs, runs=3000, seed=126):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.1 * runs)]


# ---------------------------------------------------------------------------
# Part A / B: session chain on H1
# ---------------------------------------------------------------------------
WINDOWS = {"Á hôm sau": (0, 7), "Âu hôm sau": (7, 13), "Mỹ hôm sau": (13, 21), "cả ngày hôm sau": (0, 21)}
NYC = ("đẩy tiếp", "giằng co", "đảo nhẹ", "đảo mạnh")
BINS = ("<0,5%", "0,5–1%", "≥1%")


def price_at(day_bars, hour, kind):
    """open of the bar starting at `hour` UTC, or close of the bar ending at `hour` (starting hour-1)."""
    if kind == "open":
        r = day_bars[day_bars["hr"] == hour]
        return float(r["open"].iat[0]) if len(r) else None
    r = day_bars[day_bars["hr"] == hour - 1]
    return float(r["close"].iat[0]) if len(r) else None


def chain_days(H, D):
    days = sorted(H["day"].unique())
    by = {d: H[H["day"] == d] for d in days}
    rows = []
    for k in range(len(days) - 1):
        d, n = days[k], days[k + 1]
        if n - d > 3:
            continue
        b, nb = by[d], by[n]
        o0, c13, c21 = price_at(b, 0, "open"), price_at(b, 13, "close"), price_at(b, 21, "close")
        atr = D.at[n, "atr_prev"]
        if None in (o0, c13, c21) or not atr > 0:
            continue
        ae = (c13 - o0) / o0
        s = 1 if ae > 0 else -1
        q = s * (c21 - c13) / abs(c13 - o0) if c13 != o0 else 0.0
        bin_ = BINS[0] if abs(ae) < 0.005 else BINS[1] if abs(ae) < 0.01 else BINS[2]
        nyc = NYC[0] if q >= 0.25 else NYC[1] if q > -0.25 else NYC[2] if q > -0.75 else NYC[3]
        out = {}
        for w, (a, z) in WINDOWS.items():
            po, pc_ = price_at(nb, a, "open"), price_at(nb, z, "close")
            out[w] = None if po is None or pc_ is None else s * (pc_ - po) / atr
        brk = (nb["high"].max() > b["high"].max()) if s == 1 else (nb["low"].min() < b["low"].min())
        u = int(d) * DAY
        rows.append(dict(day=d, next=n, p=period(u), s=s, ae=ae, bin=bin_, nyc=nyc, brk=brk, atr=atr, **out))
    return pd.DataFrame(rows)


def part_a(C, L):
    L += ["## Phần A — chuỗi phiên (mô tả)", "",
          "Ô: số ngày / trung bình theo chiều s (ATR ngày) / t. Kết quả dương = hôm sau đi tiếp chiều Á+Âu hôm nay.", ""]
    picks = []
    for w in WINDOWS:
        L += [f"### {w}", "", "| \\|AE\\| | Phiên Mỹ | Train | Validate | Đáng chú ý? |", "|---|---|---|---|---|"]
        for b in BINS:
            for c in NYC:
                cells, ok, signs = [], True, []
                for p in ("train", "validate"):
                    x = C[(C.p == p) & (C.bin == b) & (C.nyc == c)][w].dropna().tolist()
                    cells.append(f"{len(x)} / {mean(x):+.3f} / {tstat(x):+.1f}")
                    ok = ok and len(x) >= 30 and abs(tstat(x)) >= 2
                    signs.append(np.sign(mean(x)))
                ok = ok and signs[0] == signs[1]
                if ok and b != BINS[0]:
                    picks.append((b, c, w, int(signs[0])))
                L.append(f"| {b} | {c} | {cells[0]} | {cells[1]} | {'**có**' if ok else ''} |")
        L.append("")
    L += ["### Hôm sau phá đỉnh (s=+1) / đáy (s=−1) của hôm nay", "", "| \\|AE\\| | Phiên Mỹ | Train | Validate |", "|---|---|---|---|"]
    for b in BINS:
        for c in NYC:
            cells = []
            for p in ("train", "validate"):
                x = C[(C.p == p) & (C.bin == b) & (C.nyc == c)]["brk"]
                cells.append(f"{len(x)} / {x.mean():.0%}" if len(x) else "—")
            L.append(f"| {b} | {c} | {cells[0]} | {cells[1]} |")
    L += ["", f"Ô đáng chú ý (bỏ nhóm <0,5%): {', '.join(f'{b} {c} → {w} ({x:+d})' for b, c, w, x in picks) or 'không có'}.", ""]
    return picks


def chain_trades(H, C, pick):
    b, c, w, sign = pick
    a, z = WINDOWS[w]
    med = float(H.loc[H.utc >= int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp()), "sp"].median())
    out = []
    for r in C[(C.bin == b) & (C.nyc == c)].itertuples():
        d = sign * r.s
        nb = H[(H.day == r.next) & (H.hr >= a) & (H.hr < z)]
        if len(nb) < (z - a) * 0.8:
            continue
        unit = 0.5 * r.atr
        first = nb.iloc[0]
        entry = first["open"] + (first["sp"] if d == 1 else 0.0) + d * 0.5 * med
        stop = entry - d * unit
        px = None
        for x in nb.itertuples():
            sp = x.sp if d == -1 else 0.0
            if (d == 1 and x.low + sp <= stop) or (d == -1 and x.high + sp >= stop):
                px = min(stop, x.open + sp) if d == 1 else max(stop, x.open + sp)
                break
        if px is None:
            last = nb.iloc[-1]
            px = last["close"] + (last["sp"] if d == -1 else 0.0)
        R = (d * (px - entry) - 0.5 * med - COMM) / unit
        out.append(dict(p=r.p, r=R, d=d, utc=int(r.next) * DAY))
    return out


# ---------------------------------------------------------------------------
# Part C: ADR fades on M30
# ---------------------------------------------------------------------------
KS = (0.8, 1.0, 1.2)
ENTRIES = ("E0", "E1", "E2")


class Fade:
    def __init__(self, M, D):
        self.M, self.D = M, D
        self.o, self.h, self.l, self.c, self.sp = (M[k].to_numpy() for k in ("open", "high", "low", "close", "sp"))
        self.utc, self.day, self.mn = M["utc"].to_numpy(), M["day"].to_numpy(), M["mn"].to_numpy()
        pc = np.r_[self.c[0], self.c[:-1]]
        self.atr = wilder(np.maximum(self.h, pc) - np.minimum(self.l, pc))
        self.med = float(np.median(self.sp[self.utc >= int(datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp())]))
        self.idx = {d: np.flatnonzero(self.day == d) for d in np.unique(self.day)}
        self.days_by_p = {}
        for d in self.idx:
            p = period(int(d) * DAY)
            if p:
                self.days_by_p.setdefault(p, []).append(d)

    def walk(self, e, d, entry, stop, tgt, end):
        for j in range(e, end):
            sp = self.sp[j] if d == -1 else 0.0
            hi, lo, op = self.h[j] + sp, self.l[j] + sp, self.o[j] + sp
            if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
                return min(stop, op) if d == 1 else max(stop, op)
            if (d == 1 and hi >= tgt) or (d == -1 and lo <= tgt):
                return max(tgt, op) if d == 1 else min(tgt, op)
        sp = self.sp[end - 1] if d == -1 else 0.0
        return self.c[end - 1] + sp

    def day_end(self, ix):
        """index after the last bar ending by 21:00 UTC."""
        ok = ix[self.mn[ix] + 30 <= 21 * 60]
        return ok[-1] + 1 if len(ok) else None

    def trades(self, k, entry_mode):
        out = []
        for dday, ix in self.idx.items():
            p = period(int(dday) * DAY)
            if p is None or dday not in self.D.index:
                continue
            adr, pdh, pdl = self.D.at[dday, "adr_prev"], self.D.at[dday, "pdh"], self.D.at[dday, "pdl"]
            if not adr > 0:
                continue
            end = self.day_end(ix)
            if end is None:
                continue
            H, Lo = -1e18, 1e18
            done = {1: False, -1: False}
            for pos, j in enumerate(ix):
                H, Lo = max(H, self.h[j]), min(Lo, self.l[j])
                close_mn = self.mn[j] + 30
                if close_mn <= 7 * 60 or close_mn > 20 * 60 or j + 1 >= end:
                    continue
                rng = H - Lo
                if rng < k * adr:
                    continue
                for d in (-1, 1):             # -1 = sell fade at the top, +1 = buy fade at the bottom
                    if done[d]:
                        continue
                    top = self.c[j] >= Lo + 0.8 * rng
                    bot = self.c[j] <= Lo + 0.2 * rng
                    if (d == -1 and not top) or (d == 1 and not bot):
                        continue
                    done[d] = True
                    m = None
                    if entry_mode == "E0":
                        m = j
                    elif entry_mode == "E1":
                        for q in range(j + 1, min(j + 5, end - 1)):
                            if (d == -1 and self.c[q] < self.o[q] and self.c[q] < self.l[q - 1]) or \
                               (d == 1 and self.c[q] > self.o[q] and self.c[q] > self.h[q - 1]):
                                m = q
                                break
                    else:
                        if not ((d == -1 and pdh == pdh and H > pdh) or (d == 1 and pdl == pdl and Lo < pdl)):
                            continue
                        for q in range(j, min(j + 5, end - 1)):
                            if (d == -1 and self.c[q] < pdh) or (d == 1 and self.c[q] > pdl):
                                m = q
                                break
                    if m is None or m + 1 >= end:
                        continue
                    e = m + 1
                    hh, ll = max(H, self.h[j:e].max()), min(Lo, self.l[j:e].min())
                    entry = self.o[e] + (self.sp[e] if d == 1 else 0.0) + d * 0.5 * self.med
                    stop = (ll - 0.3 * self.atr[j]) if d == 1 else (hh + 0.3 * self.atr[j])
                    tgt = 0.5 * (hh + ll)
                    risk = d * (entry - stop)
                    if risk <= 0 or d * (tgt - entry) < risk:
                        continue
                    px = self.walk(e, d, entry, stop, tgt, end)
                    R = (d * (px - entry) - 0.5 * self.med - COMM) / risk
                    out.append(dict(p=p, r=R, d=d, utc=int(self.utc[e]), e=e, tmn=int(self.mn[e]),
                                    s_atr=risk / self.atr[j], t_atr=d * (tgt - entry) / self.atr[j], day=dday))
        return out

    def control(self, tr, p, reps=200, seed=7):
        """Same direction, stop / target in ATR(M30), same UTC entry time, on another random day of the period."""
        rng = random.Random(seed)
        days = self.days_by_p[p]
        obs = [x for x in tr if x["p"] == p]
        if not obs:
            return float("nan"), float("nan")
        means = []
        for _ in range(reps):
            rs = []
            for x in obs:
                for _try in range(5):
                    dd = rng.choice(days)
                    if dd == x["day"]:
                        continue
                    ix = self.idx[dd]
                    hit = ix[self.mn[ix] == x["tmn"]]
                    end = self.day_end(ix)
                    if not len(hit) or end is None or hit[0] >= end:
                        continue
                    e = hit[0]
                    a = self.atr[e - 1]
                    d = x["d"]
                    entry = self.o[e] + (self.sp[e] if d == 1 else 0.0) + d * 0.5 * self.med
                    stop, tgt = entry - d * x["s_atr"] * a, entry + d * x["t_atr"] * a
                    px = self.walk(e, d, entry, stop, tgt, end)
                    rs.append((d * (px - entry) - 0.5 * self.med - COMM) / (x["s_atr"] * a))
                    break
            means.append(mean(rs))
        m_obs = mean([x["r"] for x in obs])
        return mean(means), sum(1 for v in means if v >= m_obs) / reps


def cellr(tr, p, d=None):
    x = [t["r"] for t in tr if t["p"] == p and (d is None or t["d"] == d)]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


# ---------------------------------------------------------------------------
# Part D: labels on S07 legs and VHedge trades
# ---------------------------------------------------------------------------
class DayState:
    """Day open (00:00 UTC), high / low so far and ADR from the M30 bars, for any UTC time."""

    def __init__(self, M, D):
        self.M, self.D = M, D
        self.utc = M["utc"].to_numpy()
        self.h, self.l, self.o, self.day = M["high"].to_numpy(), M["low"].to_numpy(), M["open"].to_numpy(), M["day"].to_numpy()

    def at(self, u):
        dday = u // DAY
        if dday not in self.D.index:
            return None
        k = np.searchsorted(self.utc, u, side="left")          # bars that started before u
        first = np.searchsorted(self.utc, dday * DAY, side="left")
        last = k - 1
        while last >= first and self.utc[last] + 1800 > u:     # only bars closed by u
            last -= 1
        if last < first:
            return None
        return dict(o=self.o[first], h=self.h[first:last + 1].max(), l=self.l[first:last + 1].min(),
                    adr=self.D.at[dday, "adr_prev"])


def labels_for(S, u, d, entry, risk):
    x = S.at(u)
    if x is None or not x["adr"] > 0:
        return None
    move = (entry - x["o"]) / x["o"]
    return {"D1": abs(move) >= 0.005 and np.sign(move) == d,
            "D2": (x["h"] - x["l"]) / x["adr"] < 0.8,
            "D3": d * (x["o"] + d * x["adr"] - entry) >= risk}


def filter_table(rows, names, L, title):
    L += [f"### {title}", "", "| Nhãn | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ | Giữ nhãn? |", "|---|---|---|---|---|"]
    kept = []
    tv = [r for r in rows if r["p"] in ("train", "validate")]
    for f in names:
        ok, cells = True, []
        for p in ("train", "validate"):
            a = [r["r"] for r in rows if r["p"] == p and r["lab"][f]]
            b = [r["r"] for r in rows if r["p"] == p and not r["lab"][f]]
            cells.append(f"{len(a)} {mean(a):+.3f} / {len(b)} {mean(b):+.3f}")
            ok = ok and bool(a) and bool(b) and mean(a) > mean(b)
        share = sum(1 for r in tv if r["lab"][f]) / max(len(tv), 1)
        ok = ok and share >= 0.4
        if ok:
            kept.append(f)
        L.append(f"| {f} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} |")
    L.append("")
    return kept


def s07_rows(S):
    import g107_portfolio as p107
    out = []
    for L_ in p107.s07_legs():
        u = int((L_["t_in"] - pd.Timestamp(0)).total_seconds())      # S07 legs are UTC
        p = period(u)
        if p is None:
            continue
        lab = labels_for(S, u, L_["d"], L_["entry"], L_["risk"])
        if lab is None:
            continue
        out.append(dict(p=p, r=float(L_["r"]), d=L_["d"], lab=lab))
    return out


def vhedge_rows(S):
    import g120_combo as g120
    V = g120.vhedge()["G119"]
    out = []
    for r in V.itertuples():
        u = int(to_utc(np.array([int(r.t_in)]))[0])               # VHedge times are server time
        p = period(u)
        x = S.at(u) if p else None
        if x is None or not x["adr"] > 0:
            continue
        out.append(dict(p=p, r=float(r.U), lab={"D2": (x["h"] - x["l"]) / x["adr"] < 0.8}))
    return out


# ---------------------------------------------------------------------------
def main():
    L = ["# G126: chuỗi phiên Á–Âu–Mỹ và ADR trên vàng — kết quả", "",
         "Kế hoạch: `plans/2026-10-20-g126-session-chain-adr.md`. XAUUSD H1/M30 từ 03/2018, giờ UTC. Train 03/2018–2021, "
         "validate 2022–2025; 2026 niêm phong, chỉ mở cho mục được chọn. Chi phí khắt khe (spread + trượt 0,5 × spread "
         "trung vị mỗi chiều + $6/lot).", ""]
    H, M = load("H1"), load("M30")
    DH, DM = daily(H), daily(M)
    C = chain_days(H, DH)
    print("chain days", len(C), flush=True)
    picks = part_a(C, L)
    selected_tests = []
    L += ["## Phần B — giao dịch theo chuỗi phiên", ""]
    if not picks:
        L += ["Không có ô đáng chú ý → không có giao dịch.", ""]
    else:
        L += ["| Ô | Chiều | Train | Validate | Chọn? |", "|---|---|---|---|---|"]
        for pk in picks:
            tr = chain_trades(H, C, pk)
            ok = mean([t["r"] for t in tr if t["p"] == "train"]) > 0 and mean([t["r"] for t in tr if t["p"] == "validate"]) > 0
            L.append(f"| {pk[0]} {pk[1]} → {pk[2]} | {'theo' if pk[3] > 0 else 'ngược'} s | {cellr(tr, 'train')} | "
                     f"{cellr(tr, 'validate')} | {'**chọn**' if ok else ''} |")
            if ok:
                selected_tests.append((f"B: {pk[0]} {pk[1]} → {pk[2]}", tr))
        L.append("")
    print("part B done", flush=True)
    F = Fade(M, DM)
    L += ["## Phần C — đánh ngược khi đã dùng hết ADR (M30)", "",
          "Ô: số lệnh / R mỗi lệnh. Đối chứng: cùng chiều, cùng SL/TP theo ATR, cùng giờ UTC, ở ngày khác ngẫu nhiên (200 lần).", "",
          "| k | Vào | Train | Validate | Mua (train / val) | Bán (train / val) | Ngẫu nhiên validate | p validate | Chọn? |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k in KS:
        for e in ENTRIES:
            tr = F.trades(k, e)
            ctl, p = F.control(tr, "validate")
            a = [t["r"] for t in tr if t["p"] == "train"]
            b = [t["r"] for t in tr if t["p"] == "validate"]
            ok = len(a) >= 40 and len(b) >= 40 and mean(a) > 0 and mean(b) > 0 and p < 0.05
            L.append(f"| {k} | {e} | {cellr(tr, 'train')} | {cellr(tr, 'validate')} | {cellr(tr, 'train', 1)} · {cellr(tr, 'validate', 1)} | "
                     f"{cellr(tr, 'train', -1)} · {cellr(tr, 'validate', -1)} | {ctl:+.3f} | {p:.3f} | {'**chọn**' if ok else ''} |")
            if ok:
                selected_tests.append((f"C: k {k} {e}", tr))
            print("C", k, e, flush=True)
    L.append("")
    S = DayState(M, DM)
    L += ["## Phần D — nhãn ngày cho S07 và VHedge", "",
          "D1 thiên hướng ngày ≥ 0,5% cùng chiều lệnh; D2 ADR đã dùng < 0,8; D3 còn ≥ 1R tới mức giá mở ± ADR theo chiều lệnh. "
          "Ô: số lệnh R/lệnh, nhóm giữ / nhóm bỏ.", ""]
    s07 = s07_rows(S)
    kept = filter_table(s07, ("D1", "D2", "D3"), L, "S07 (mọi chân lệnh, R khắt khe)")
    for side, nm in ((1, "S07 mua"), (-1, "S07 bán")):
        filter_table([r for r in s07 if r["d"] == side], ("D1", "D2", "D3"), L, f"{nm} (chỉ mô tả)")
    for f in kept:
        selected_tests.append((f"D: S07 với {f}", [dict(r, keep=r["lab"][f]) for r in s07]))
    try:
        vh = vhedge_rows(S)
        filter_table(vh, ("D2",), L, "VHedge G119 (từ 05/2024, chỉ mô tả, không chọn)")
    except Exception as ex:      # VHedge data are optional for this study
        L += [f"VHedge: không chạy được ({ex}).", ""]
    print("part D done", flush=True)
    L += ["## Test 2026 (mở một lần, chỉ cho mục được chọn)", ""]
    if not selected_tests:
        L += ["Không có mục nào được chọn trên train + validate → **2026 vẫn niêm phong**.", ""]
    else:
        L += ["| Mục | 2026 | Cận dưới 90% | Đạt? |", "|---|---|---|---|"]
        for name, tr in selected_tests:
            if name.startswith("D:"):
                a = [t["r"] for t in tr if t["p"] == "test" and t["keep"]]
                b = [t["r"] for t in tr if t["p"] == "test" and not t["keep"]]
                ok = bool(a) and bool(b) and mean(a) > mean(b)
                L.append(f"| {name} | giữ {len(a)} {mean(a):+.3f} / bỏ {len(b)} {mean(b):+.3f} | | {'**đạt**' if ok else 'không'} |")
            else:
                x = [t["r"] for t in tr if t["p"] == "test"]
                lo = lower90(x) if len(x) > 1 else float("nan")
                ok = len(x) > 1 and mean(x) > 0 and lo > 0
                L.append(f"| {name} | {len(x)} / {mean(x):+.3f} | {lo:+.3f} | {'**đạt**' if ok else 'không'} |")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
