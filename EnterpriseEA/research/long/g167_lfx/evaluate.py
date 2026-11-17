"""Evaluate the extracted signals on MT5 prices: time-zone alignment, price reconstruction, SL/TP first touch, R outcomes."""
import json
import re
from datetime import datetime

import numpy as np
import pandas as pd

YEAR = 2026
SYM = {"XAUUSD": "XAUUSD-VIP", "XAGUSD": "XAGUSD-VIP", "USOUSD": "USOUSD-VIP", "BTCUSD": "BTCUSD-VIP", "EURUSD": "EURUSD-VIP"}


def load(sym):
    m5 = pd.read_csv(f"{sym}_M5.csv")
    try:
        m1 = pd.read_csv(f"{sym}_M1.csv")
    except FileNotFoundError:
        m1 = None
    return m5, m1


DATA = {k: load(v) for k, v in SYM.items()}


def bars_from(sym, t_srv, hours=96):
    """M1 bars when available for the window, else M5; t in server seconds."""
    m5, m1 = DATA[sym]
    if m1 is not None and t_srv >= m1["time"].iloc[0]:
        d = m1
    else:
        d = m5
    a = int(np.searchsorted(d["time"].to_numpy(), t_srv))
    z = int(np.searchsorted(d["time"].to_numpy(), t_srv + hours * 3600))
    return d.iloc[a:z], ("M1" if d is m1 else "M5")


def price_at(sym, t_srv):
    m5 = DATA[sym][0]
    k = int(np.searchsorted(m5["time"].to_numpy(), t_srv, side="right")) - 1
    return float(m5["close"].iloc[k]) if 0 <= k < len(m5) else None


S = json.load(open("extracted.json", encoding="utf-8"))
rows = sorted(json.load(open("ocr_dedup.json", encoding="utf-8")))


def find_time(y):
    for yy, x, t, c in rows:
        if yy <= y:
            continue
        if yy - y > 700:
            break
        m = re.search(r"(\d{1,2}):(\d{2})\s*$", t)
        if m and x > 280:
            h = int(m.group(1)[-2:])
            h = h if h < 24 else int(m.group(1)[-1:])
            return f"{h:02d}:{m.group(2)}"
    return None


for s in S:
    if not s.get("time"):
        s["time"] = find_time(s["y"])
        s["time_guessed"] = True


def t_local(s):
    if not s.get("date") or not s.get("time"):
        return None
    mo, d = s["date"]
    h, mi = map(int, s["time"].split(":"))
    return datetime(YEAR, mo, d, h, mi)


# ---- time-zone alignment on bot entries: server = local + off hours
bots = [s for s in S if s["kind"] == "bot" and s.get("entry") and t_local(s)]
best = None
for off in range(-10, 11):
    errs = []
    for s in bots:
        tl = t_local(s)
        ts = int((pd.Timestamp(tl) + pd.Timedelta(hours=off)).timestamp())
        p = price_at(s["sym"], ts)
        if p:
            errs.append(abs(p / s["entry"] - 1))
    if errs:
        med = float(np.median(errs))
        if best is None or med < best[1]:
            best = (off, med, len(errs))
print("time offset (server = Telegram time + h):", best)
OFF = best[0]


def us_dst(d):
    from datetime import date, timedelta
    mar = date(d.year, 3, 8) + timedelta(days=(6 - date(d.year, 3, 8).weekday()) % 7)
    nov = date(d.year, 11, 1) + timedelta(days=(6 - date(d.year, 11, 1).weekday()) % 7)
    return mar <= d < nov


def srv_ts(s):
    """Telegram shows UTC+7; broker server is UTC+3 in US DST, else UTC+2."""
    tl = t_local(s)
    if not tl:
        return None
    off = (3 if us_dst(tl.date()) else 2) - 7
    return int((pd.Timestamp(tl) + pd.Timedelta(hours=off)).timestamp())


def expand(v, ref):
    """Rebuild an abbreviated price (e.g. '52' with ref 4461 -> 4452) as the value nearest to ref with the same trailing digits."""
    if v is None:
        return None
    v = float(v)
    if v >= ref * 0.5:
        return v
    digits = len(str(int(v)))
    base = 10 ** digits
    cands = [np.floor(ref / base) * base + v + k * base for k in (-1, 0, 1)]
    return float(min(cands, key=lambda c: abs(c - ref)))


def simulate(sym, side, entry, sl, tps, t0, kind, zone=None, order="now"):
    d = 1 if side == "buy" else -1
    bars, tf = bars_from(sym, t0)
    if len(bars) < 3:
        return None
    o, h, l, c, tt = (bars[k].to_numpy() for k in ("open", "high", "low", "close", "time"))
    start = 0
    if kind == "manual":
        lo, hi = min(zone), max(zone)
        if order == "limit":
            fill = None
            for j in range(len(h)):
                if (d == 1 and l[j] <= hi) or (d == -1 and h[j] >= lo):
                    fill = j
                    break
                if j > 0 and tt[j] - tt[0] > 24 * 3600:
                    break
            if fill is None:
                return {"filled": False}
            start, entry = fill, (hi if d == 1 else lo)
        else:
            entry = float(o[0])                                           # market at the message time
    risk = d * (entry - sl)
    if not risk or risk <= 0:
        return {"filled": True, "bad_levels": True, "entry": entry}
    hit = {}
    res = {"filled": True, "tf": tf, "entry": round(entry, 3), "risk": round(risk, 3), "in_zone": None}
    if kind == "manual" and zone:
        res["in_zone"] = bool(min(zone) - 0.5 <= entry <= max(zone) + 0.5)
    sl_t = None
    for j in range(start, len(h)):
        adv = l[j] if d == 1 else h[j]
        fav = h[j] if d == 1 else l[j]
        sl_now = d * (adv - sl) <= 0
        new = [k for k, tp in enumerate(tps) if k not in hit and d * (fav - tp) >= 0]
        if sl_now and new:
            # same bar: unknown order -> pessimistic, SL first
            sl_t = j
            break
        for k in new:
            hit[k] = j
        if sl_now:
            sl_t = j
            break
        if len(hit) == len(tps) and tps:
            break
    res["tp_hit"] = sorted(hit)
    res["tp_min"] = {k: round((tt[v] - tt[start]) / 60) for k, v in hit.items()}
    res["sl_hit"] = sl_t is not None
    res["sl_min"] = round((tt[sl_t] - tt[start]) / 60) if sl_t is not None else None
    res["tp_R"] = [round(d * (tp - entry) / risk, 2) for tp in tps]
    # outcomes under three management styles (R, before costs)
    n = len(tps)
    first_tp = 0 in hit
    res["R_tp1_all"] = res["tp_R"][0] if first_tp else (-1.0 if res["sl_hit"] else None)
    if n:
        parts = [res["tp_R"][k] if k in hit else (-1.0 if res["sl_hit"] else None) for k in range(n)]
        res["R_split"] = None if any(p is None for p in parts) else round(sum(parts) / n, 3)
        # split + break-even after TP1: remaining parts close at 0 if SL comes later
        if first_tp:
            parts_be = [res["tp_R"][k] if k in hit else 0.0 for k in range(n)]
            res["R_split_be"] = round(sum(parts_be) / n, 3) if (res["sl_hit"] or len(hit) == n) else None
        else:
            res["R_split_be"] = -1.0 if res["sl_hit"] else None
    return res


def h1_atr(sym, ts):
    d = pd.read_csv(f"{SYM[sym]}_H1.csv") if sym not in _H1 else _H1[sym]
    _H1[sym] = d
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    a = pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    k = int(np.searchsorted(d["time"].to_numpy(), ts, side="right")) - 2
    return float(a[max(k, 0)])


_H1 = {}


def target_of(s):
    if s["kind"] == "bot":
        return s.get("entry"), s.get("entry")
    z = [float(v) for v in (s.get("zone") or []) if v not in (None, "")]
    return (min(z), max(z)) if z else (None, None)


def dist(sym, ts, s):
    p = price_at(sym, ts)
    lo, hi = target_of(s)
    if p is None or lo is None:
        return None, p
    lo, hi = expand(lo, p), expand(hi, p)
    lo, hi = min(lo, hi), max(lo, hi)
    return (0.0 if lo <= p <= hi else min(abs(p - lo), abs(p - hi)) / p), p


out = []
for s in S:
    ts = srv_ts(s)
    if ts is None:
        continue
    sym = s.get("sym", "XAUUSD")
    if sym not in DATA:
        continue
    # date fix: an OCR-missed date header leaves the previous date; try the same clock time 0..4 days later
    best_k, best_d = 0, None
    for kday in range(0, 5):
        dd, p = dist(sym, ts + kday * 86400, s)
        if dd is None:
            continue
        if best_d is None or dd < best_d - 0.002:
            best_k, best_d = kday, dd
    ts += best_k * 86400
    ref = price_at(sym, ts)
    if ref is None:
        continue
    r = {k: s.get(k) for k in ("kind", "date", "time", "sym", "tf", "side", "status", "score", "order")}
    r["t_srv"] = ts
    r["price_at_msg"] = ref
    r["date_shift_days"] = best_k
    r["gap_to_zone_pct"] = round(best_d * 100, 3) if best_d is not None else None
    if s["kind"] == "bot":
        if not (s.get("entry") and s.get("sl") and s.get("tps")):
            continue
        tps = sorted(set(s["tps"]), reverse=(s["side"] == "sell"))[:2] if len(set(s["tps"])) else []
        tps = sorted(set(s["tps"]), key=lambda v: (v - s["entry"]) * (1 if s["side"] == "buy" else -1))
        r.update(entry_sig=s["entry"], sl=s["sl"], tps=tps)
        r["entry_gap_pct"] = round((ref / s["entry"] - 1) * 100, 3)
        sim = simulate(sym, s["side"], s["entry"], s["sl"], tps, ts, "bot")
    else:
        lo = expand(float(s["zone"][0]), ref)
        hi = s["zone"][1]
        hi = expand(float(hi), lo) if hi not in (None, "") else lo
        sl = expand(s.get("sl"), ref) if s.get("sl") else None
        tps = [expand(v, ref) for v in s.get("tps", []) if v and v < 100000]
        d = 1 if s["side"] == "buy" else -1
        if sl is None:
            a = h1_atr(sym, ts)
            edge = max(lo, hi) if d == -1 else min(lo, hi)
            sl = edge - d * a
            r["sl_assumed"] = True
            if not tps:
                tps = [edge + d * m * a for m in (0.9, 2.0, 3.0)]
        tps = [t for t in tps if d * (t - lo) > 0]
        tps = sorted(set(tps), key=lambda v: d * (v - lo))
        r.update(zone=[lo, hi], sl=sl, tps=tps)
        sim = simulate(sym, s["side"], None, sl, tps, ts, "manual", zone=[lo, hi], order=s.get("order") or "now")
    r["sim"] = sim
    out.append(r)
json.dump(out, open("evaluated.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
ok = [r for r in out if r.get("sim") and r["sim"].get("filled") and not r["sim"].get("bad_levels")]
print("evaluated", len(out), "simulated", len(ok))
