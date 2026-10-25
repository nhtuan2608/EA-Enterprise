"""Council step 3b-2: state card, named situations and anomaly checks from current/council/context.json (written by the EA on
every closed M30 bar: 1000 M30 bars with tick volume and spread, 250 H4, 300 D1, bid / ask, server offset).
Plan: docs/superpowers/plans/2026-10-25-council-3b.md (3b-2). Definitions follow G156a / G156c. Standard library only.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import council_rules as cr

C18 = "không báo trước hướng (C18, G156c)"


def ema(xs: list[float], n: int) -> list[float]:
    out, a = [], 2.0 / (n + 1)
    for i, x in enumerate(xs):
        out.append(x if i == 0 else out[-1] + a * (x - out[-1]))
    return out


def wilder_atr(h, l, c, n=14) -> list[float]:
    out = []
    for i in range(len(c)):
        tr = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        out.append(tr if i == 0 else out[-1] + (tr - out[-1]) / n)
    return out


def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def load(root: Path):
    try:
        return json.loads((Path(root) / "current" / "council" / "context.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def analyse(doc: dict, now_utc: float | None = None) -> dict:
    """{'gia': state card, 'tinh_huong': [...], 'bat_thuong': [{'khoa', 'mo_ta'}], 'tuoi_giay': age}."""
    now_utc = time.time() if now_utc is None else now_utc
    m = doc.get("m30") or []
    if len(m) < 60:
        return {"gia": {"loi": "thiếu nến M30"}, "tinh_huong": [], "bat_thuong": [], "tuoi_giay": None}
    t = [int(r[0]) for r in m]
    o, h, l, c = ([float(r[k]) for r in m] for k in (1, 2, 3, 4))
    v = [float(r[5]) for r in m]
    sp = [float(r[6]) for r in m]
    pt = float(doc.get("point") or 0.01)
    off = int(doc.get("server_offset") or 0)
    atr = wilder_atr(h, l, c)
    A = atr[-1]
    e = {n: ema(c, n) for n in (21, 50, 55, 100, 200)}
    d1 = doc.get("d1") or []
    dc = [float(r[4]) for r in d1]
    dh = [float(r[2]) for r in d1]
    dl = [float(r[3]) for r in d1]
    regime = 0
    if len(dc) >= 61:
        e50 = ema(dc, 50)
        if dc[-1] > e50[-1] and e50[-1] > e50[-11]:
            regime = 1
        elif dc[-1] < e50[-1] and e50[-1] < e50[-11]:
            regime = -1
    sma_side = sign(sum(dc[-50:]) / 50 - sum(dc[-200:]) / 200) if len(dc) >= 200 else 0
    h4 = doc.get("h4") or []
    h4c = [float(r[4]) for r in h4]
    h4_side = sign(h4c[-1] - ema(h4c, 200)[-1]) if len(h4c) >= 200 else 0
    adr = statistics.fmean([dh[k] - dl[k] for k in range(-20, 0)]) if len(d1) >= 20 else None
    day = [x // 86400 for x in t]
    today = [i for i in range(len(t)) if day[i] == day[-1]]
    hour = [(x % 86400) // 3600 for x in t]
    asia = [i for i in today if 1 <= hour[i] <= 7]
    asia_ok = bool(asia) and hour[-1] >= 8
    ah = max(h[i] for i in asia) if asia_ok else None
    al = min(l[i] for i in asia) if asia_ok else None
    pdh, pdl = (dh[-1], dl[-1]) if d1 else (None, None)
    # previous Monday-based server week from the D1 bars
    wk = lambda ts_: (ts_ // 86400 + 3) // 7  # noqa: E731
    this_wk = wk(t[-1])
    prev = [r for r in d1 if wk(int(r[0])) == this_wk - 1]
    pwh = max(float(r[2]) for r in prev) if prev else None
    pwl = min(float(r[3]) for r in prev) if prev else None
    vol_today = [max(v[i], 1.0) for i in today]
    vwap = (sum((h[i] + l[i] + c[i]) / 3 * max(v[i], 1.0) for i in today) / sum(vol_today)) if today else None
    run_h, run_l = max(h[i] for i in today), min(l[i] for i in today)
    srt = sorted(atr[-1000:])
    pct = sum(1 for x in srt if x <= A) / len(srt)

    def dist(x):
        return round((c[-1] - x) / A, 2) if x is not None and A > 0 else None

    ribbon = 1 if e[21][-1] > e[55][-1] > e[100][-1] and c[-1] > e[21][-1] else (
        -1 if e[21][-1] < e[55][-1] < e[100][-1] and c[-1] < e[21][-1] else 0)
    card = {
        "nen_cuoi_server": time.strftime("%Y-%m-%d %H:%M", time.gmtime(t[-1])), "gia_dong": c[-1],
        "che_do_d1": regime, "sma50_200_d1": sma_side, "phia_ema200_h4": h4_side, "dai_ema_m30": ribbon,
        "atr14_m30": round(A, 3), "phan_vi_atr": round(pct, 2),
        "pham_vi_ngay_adr20": round((run_h - run_l) / adr, 2) if adr else None,
        "cach_atr": {"vwap": dist(vwap), "bien_a_tren": dist(ah), "bien_a_duoi": dist(al), "pdh": dist(pdh), "pdl": dist(pdl),
                     "pwh": dist(pwh), "pwl": dist(pwl), "ema200_m30": dist(e[200][-1])},
        "ghi_chu": "mô tả trạng thái, không dùng để đoán hướng (B8, C18)",
    }
    # named situations on the bar that just closed
    sit = []
    levels = [("PDL", pdl, 1), ("biên Á dưới", al, 1), ("PDH", pdh, -1), ("biên Á trên", ah, -1)]
    for name, lv, d in levels:
        if lv is None:
            continue
        if (d == 1 and l[-1] < lv < c[-1]) or (d == -1 and h[-1] > lv > c[-1]):
            sit.append({"ten": f"quét {name} rồi rút " + ("cùng chiều D1" if regime == d else ("ngược D1" if regime == -d else "(D1 trung tính)")),
                        "chieu": d, "ghi_chu": C18})
    for name, lv, d in (("PDH", pdh, 1), ("PDL", pdl, -1), ("PWH", pwh, 1), ("PWL", pwl, -1), ("biên Á trên", ah, 1), ("biên Á dưới", al, -1)):
        if lv is not None and ((d == 1 and c[-1] > lv >= c[-2]) or (d == -1 and c[-1] < lv <= c[-2])):
            sit.append({"ten": f"vừa phá {name}", "chieu": d, "ghi_chu": "đi tiếp hay giả khoảng 51 / 49 (B8); " + C18})
    if len(c) > 9 and A > 0 and abs(c[-1] - c[-9]) >= 1.5 * A:
        v_now, v_prev = statistics.fmean(v[-4:]), statistics.fmean(v[-8:-4])
        if v_prev > 0 and v_now < 0.8 * v_prev:
            sit.append({"ten": "giá chạy mà volume giảm", "chieu": sign(c[-1] - c[-9]), "ghi_chu": C18})
    tf = [sign(c[-1] - e[50][-1]), sign(c[-1] - e[100][-1]), h4_side, regime]
    if tf[0] != 0 and all(x == tf[0] for x in tf):
        sit.append({"ten": "4 khung cùng chiều", "chieu": tf[0], "ghi_chu": C18})
    # anomalies (agent 3)
    bad = []
    bid, ask = float(doc.get("bid") or 0), float(doc.get("ask") or 0)
    same_hour = [sp[i] for i in range(len(t)) if hour[i] == (int(now_utc) + off) % 86400 // 3600 and t[i] >= t[-1] - 20 * 86400]
    med = statistics.median(same_hour) if same_hour else 0
    spread_now = (ask - bid) / pt if ask > bid > 0 else 0
    if med > 0 and spread_now > 3 * med:
        bad.append({"khoa": f"spread:{int(now_utc) // 1800}", "mo_ta": f"spread {spread_now:.0f} điểm > 3 × trung vị cùng giờ ({med:.0f})"})
    if len(atr) > 2 and atr[-2] > 0 and h[-1] - l[-1] > 3 * atr[-2]:
        bad.append({"khoa": f"bigbar:{t[-1]}", "mo_ta": f"nến M30 vừa đóng {(h[-1] - l[-1]) / atr[-2]:.1f} ATR"})
    for i in range(max(1, len(t) - 48), len(t)):
        dt_ = t[i] - t[i - 1]
        if dt_ >= 2 * 86400 and atr[i - 1] > 0 and abs(o[i] - c[i - 1]) > 2 * atr[i - 1]:
            bad.append({"khoa": f"gap:{t[i]}", "mo_ta": f"gap đầu tuần {abs(o[i] - c[i - 1]) / atr[i - 1]:.1f} ATR"})
        elif 7200 < dt_ < 2 * 86400 and cr.market_open(t[i] - off):
            bad.append({"khoa": f"missing:{t[i]}", "mo_ta": f"thiếu nến M30: cách {dt_ // 60} phút trước {time.strftime('%H:%M', time.gmtime(t[i]))}"})
    age = int(now_utc) - int(doc.get("written_at_utc") or 0)
    if age > 2400 and cr.market_open(now_utc):
        bad.append({"khoa": f"ctxstale:{int(now_utc) // 3600}", "mo_ta": f"file bối cảnh cũ {age // 60} phút trong giờ mở cửa"})
    return {"gia": card, "tinh_huong": sit, "bat_thuong": bad, "tuoi_giay": age}
