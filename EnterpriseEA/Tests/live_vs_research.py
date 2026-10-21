"""Live bots vs research: rebuild what the research rules would have traded on the same bars and pair it with the
live positions of each bot.

Input = the folder written by Scripts/EEA_ExportDeals.mq5 (MQL5\\Files\\EEA_export\\: deals.csv, bars_M5/M15/M30/H1/H4.csv,
meta.json), from the VPS or the demo terminal. Read-only; nothing is sent to MT5.

  python Tests/live_vs_research.py --export "<MQL5>/Files/EEA_export" --since 2026-10-13
  python Tests/live_vs_research.py --export ... --since 2026-10-13 --out docs/superpowers/reports/live-vs-research.md

Research references (same rules as the bots, run on the exported bars):
  S07      g89 / S07Tester book (base, early, re-entry, adds), legs converted from UTC to server time
  VHEDGE   G119 signals (Tests/vhedge_reference.py: g116 V groups + g119 filter); research R not rebuilt
  CTXLIMIT frozen MKT04 gold models (CtxLimit/CtxGoldModel.mqh), incremental features, S07 gates, limit fills simulated
XRT, CtxBox and the advisor bots are listed from the live side only.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "long"))
sys.path.insert(0, str(ROOT / "research" / "markets"))
sys.path.insert(0, str(ROOT / "Tests"))

BOTS = {888888: "S07", 707070: "S07", 116119: "VHEDGE", 717171: "CTXLIMIT", 969696: "XRT", 106106: "CTXBOX",
        737373: "ADVISOR", 141414: "PROBSETUP"}
TF_DIRS = {"M5": "m5v", "M15": "m15v", "M30": "m30v", "H1": "h1v", "H4": "h4v"}


def srv(ts: str) -> int:
    return int(pd.Timestamp(ts).timestamp())


def fmt_t(t) -> str:
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%m-%d %H:%M")


# ---------------------------------------------------------------------------
# live side
# ---------------------------------------------------------------------------
def live_positions(export: Path, since: int) -> pd.DataFrame:
    d = pd.read_csv(export / "deals.csv")
    d = d[d["position"] > 0]
    rows = []
    for pid, g in d.groupby("position"):
        ins, outs = g[g["entry"] == 0], g[g["entry"].isin([1, 3])]
        if ins.empty:
            continue
        first = ins.sort_values("time").iloc[0]
        if first["time"] < since:
            continue
        direction = 1 if first["type"] == 0 else -1
        vin = ins["volume"].sum()
        open_px = float((ins["price"] * ins["volume"]).sum() / vin)
        close_px = float((outs["price"] * outs["volume"]).sum() / outs["volume"].sum()) if not outs.empty else np.nan
        sl = float(first["order_sl"]) if first["order_sl"] > 0 else np.nan
        money = float((g["profit"] + g["commission"] + g["swap"] + g["fee"]).sum())
        r = direction * (close_px - open_px) / abs(open_px - sl) if sl == sl and close_px == close_px and open_px != sl else np.nan
        rows.append(dict(position=pid, magic=int(first["magic"]), bot=BOTS.get(int(first["magic"]), f"magic {int(first['magic'])}"),
                         d=direction, t_open=int(first["time"]), t_close=int(outs["time"].max()) if not outs.empty else None,
                         open=open_px, close=close_px, sl=sl, volume=vin, money=money, r=r,
                         comment=str(first["comment"]), order_type=int(first["order_type"])))
    return pd.DataFrame(rows).sort_values("t_open") if rows else pd.DataFrame(columns=["bot"])


# ---------------------------------------------------------------------------
# research side: the exported bars as a research data folder
# ---------------------------------------------------------------------------
def research_root(export: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="eea_live_"))
    for tf, sub in TF_DIRS.items():
        (root / "data" / sub).mkdir(parents=True)
        src = export / f"bars_{tf}.csv"
        if src.exists():
            shutil.copy(src, root / "data" / sub / "XAUUSD.csv")
    return root


def s07_reference(root: Path, since: int, until: int) -> pd.DataFrame:
    import g67_dmi_ema as g67
    g67.HERE = root
    g67.set_tf("M15")
    import g89_full_book as fb
    import g107_portfolio as p107
    m30 = pd.read_csv(root / "data" / "m30v" / "XAUUSD.csv")
    m15 = pd.read_csv(root / "data" / "m15v" / "XAUUSD.csv")
    to_utc = lambda t: t - (10800 if g67.us_dst(int(t) - 7200) else 7200)
    fb.START = to_utc(max(int(m30["time"].iloc[0]) + 60 * 86400, since - 3 * 86400))
    fb.SPLIT = max(fb.START, to_utc(int(m15["time"].iloc[0]) + 10 * 86400))
    fb.END = to_utc(until)
    legs = p107.s07_to_server(p107.s07_legs())
    rows = []
    for L in legs:
        t_in = int((L["t_in"] - pd.Timestamp(0)).total_seconds())
        if t_in < since:
            continue
        rows.append(dict(d=int(L["d"]), t_open=t_in, t_close=int((L["t_out"] - pd.Timestamp(0)).total_seconds()),
                         open=float(L["entry"]), r=float(L["r"]), w=float(L["money"]) / (p107.CAPITAL * 0.015)))
    return pd.DataFrame(rows).sort_values("t_open") if rows else pd.DataFrame(columns=["d", "t_open"])


def vhedge_reference(root: Path, since: int) -> pd.DataFrame:
    import vhedge_reference as vr
    from g97_forming_bar import dmi, ema
    m = pd.read_csv(root / "data" / "m5v" / "XAUUSD.csv")
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    c = m["close"].to_numpy()
    for k in (21, 55, 100, 200):
        m[f"e{k}"] = ema(c, k)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * 0.01
    s = vr.signals(m, pd.to_datetime(since, unit="s"))
    if s.empty:
        return pd.DataFrame(columns=["t_open"])
    s = s[s["taken"]].copy() if "taken" in s.columns else s
    s["t_open"] = (pd.to_datetime(s["signal_time"]) - pd.Timestamp(0)).dt.total_seconds().astype(int) + 300
    return s


def _arrays(text: str, tag: str) -> dict:
    out = {}
    for name in ("FEAT", "THR", "LEFT", "RIGHT", "DLEFT", "MISS", "LEAF", "ROOT", "ROOTLEAF"):
        m = re.search(rf"CTX_{tag}_{name}\[\d+\]=\{{([^}}]*)\}}", text)
        vals = m.group(1).split(",")
        out[name.lower()] = [float(v) for v in vals] if name in ("THR", "LEAF") else [int(v) for v in vals]
    return dict(feat=out["feat"], thr=out["thr"], left=out["left"], right=out["right"], dleft=out["dleft"],
                miss=out["miss"], leaves=out["leaf"], roots=out["root"], root_leaf=out["rootleaf"])


def ctx_reference(root: Path, since: int, threshold=0.3825820347356539, pull=0.5, sl_a=1.0, tp_a=2.0, limit_bars=8,
                  hold_bars=96, unordered=0.67) -> pd.DataFrame:
    import ctx_export_model as cem
    import ctx_incremental as ci
    text = (ROOT / "CtxLimit" / "CtxGoldModel.mqh").read_text(encoding="utf-8")
    LL, LS = _arrays(text, "LL"), _arrays(text, "LS")
    m = pd.read_csv(root / "data" / "m30v" / "XAUUSD.csv")
    o, h, l, c, sp = (m[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close", "spread"))
    sp = sp * 0.01
    t = m["time"].to_numpy()
    ctx = ci.Context()
    feats = None
    pending, pos_until = [], -1
    rows = []
    for i in range(len(m)):
        f = ctx.add(int(t[i]), o[i], h[i], l[i], c[i], float(m["tickvol"].iat[i]))
        if feats is None:
            feats = list(f.keys())
        # pending limits: fill / expire on bar i
        if pending and i > pos_until:
            for p in sorted(pending, key=lambda z: z["placed"]):
                if i <= p["placed"] or i > p["placed"] + limit_bars:
                    continue
                if (p["d"] == 1 and l[i] + sp[i] < p["level"]) or (p["d"] == -1 and h[i] > p["level"]):
                    exit_i, r = _walk(o, h, l, c, sp, i, p, hold_bars)
                    rows.append(dict(d=p["d"], t_decision=int(t[p["placed"] - 1]) + 1800, t_open=int(t[i]), open=p["level"],
                                     r=r, w=p["w"], forecast=p["p"], t_close=int(t[exit_i])))
                    pos_until = exit_i
                    pending = []
                    break
            pending = [p for p in pending if i < p["placed"] + limit_bars]
        if int(t[i]) < since - 86400 or (int(t[i]) + 1800) % 3600 != 0 or i + 1 >= len(m) or i <= pos_until:
            continue
        if len(pending) >= 8:
            continue
        x = [f[k] for k in feats]
        pb, ps = cem.predict_flat(LL, x), cem.predict_flat(LS, x)
        best, d = -1e9, 0
        top9 = max(h[max(0, i - 8):i + 1])
        for dd, p in ((1, pb), (-1, ps)):
            if not (p > threshold and p > 0):
                continue
            if not (f["h4_side"] == f["h4_side"] and int(f["h4_side"]) == dd):
                continue
            if dd == -1:
                he = ctx.h4.last_e if ctx.h4.done >= 201 else float("nan")
                if not (he == he and top9 >= he - 0.5 * ctx.a14):
                    continue
            if p > best:
                best, d = p, dd
        if d == 0 or not ctx.A == ctx.A or int(t[i]) < since:
            continue
        x21, x55, x100 = ctx.e21.v, ctx.e55.v, ctx.e100.v
        ordered = (x21 > x55 > x100 and c[i] > x21) if d == 1 else (x21 < x55 < x100 and c[i] < x21)
        level = c[i] - d * pull * ctx.A
        pending.append(dict(d=d, level=level, stop=level - d * sl_a * ctx.A, tgt=level + d * tp_a * ctx.A, placed=i + 1,
                            w=1.0 if ordered else unordered, p=best))
    return pd.DataFrame(rows).sort_values("t_open") if rows else pd.DataFrame(columns=["d", "t_open"])


def _walk(o, h, l, c, sp, e, p, hold):
    d, stop, tgt = p["d"], p["stop"], p["tgt"]
    risk = abs(p["level"] - stop)
    if (d == 1 and l[e] <= stop) or (d == -1 and h[e] + sp[e] >= stop):
        return e, -1.0
    last = min(len(c) - 1, e + hold - 1)
    for j in range(e + 1, last + 1):
        s = sp[j] if d == -1 else 0.0
        if (d == 1 and l[j] + s <= stop) or (d == -1 and h[j] + s >= stop):
            return j, -1.0
        if (d == 1 and h[j] + s >= tgt) or (d == -1 and l[j] + s <= tgt):
            return j, (tgt - p["level"]) * d / risk
    return last, d * (c[last] + (sp[last] if d == -1 else 0.0) - p["level"]) / risk


# ---------------------------------------------------------------------------
# pairing and report
# ---------------------------------------------------------------------------
def pair(res: pd.DataFrame, live: pd.DataFrame, tol: int, use_dir=True):
    used, out = set(), []
    for r in res.itertuples():
        best, bd = None, tol + 1
        for k, x in live.iterrows():
            if k in used or (use_dir and "d" in res.columns and x["d"] != r.d):
                continue
            dt = abs(int(x["t_open"]) - int(r.t_open))
            if dt < bd:
                best, bd = k, dt
        if best is not None:
            used.add(best)
        out.append((r, live.loc[best] if best is not None else None))
    extra = live.loc[[k for k in live.index if k not in used]]
    return out, extra


def side(d):
    return "MUA" if d == 1 else "BÁN"


def section(name, res, live, tol, L, rcol="r", use_dir=True):
    L += [f"## {name}", ""]
    if res is None:
        L += ["(không dựng được lệnh nghiên cứu)", ""]
    pairs, extra = pair(res if res is not None else pd.DataFrame(columns=["t_open"]), live, tol, use_dir)
    matched = [(r, x) for r, x in pairs if x is not None]
    missed = [r for r, x in pairs if x is None]
    L.append(f"Nghiên cứu {len(pairs)} lệnh · live {len(live)} lệnh · khớp {len(matched)} · nghiên cứu có mà live không vào "
             f"{len(missed)} · live có mà nghiên cứu không có {len(extra)}.")
    if matched and rcol:
        dr = [float(x["r"]) - float(getattr(r, rcol)) for r, x in matched if x["r"] == x["r"]]
        if dr:
            L.append(f"R live − R nghiên cứu (lệnh khớp): trung bình {np.mean(dr):+.2f}, trung vị {np.median(dr):+.2f}.")
    L += ["", "| Trạng thái | Giờ nghiên cứu | Giờ live | Chiều | Giá vào NC → live | R nghiên cứu | R live | Tiền live |",
          "|---|---|---|---|---|---|---|---|"]
    for r, x in pairs:
        rr = getattr(r, rcol) if rcol and hasattr(r, rcol) else float("nan")
        dcol = side(r.d) if hasattr(r, "d") else "—"
        op = f"{getattr(r, 'open', float('nan')):.2f}"
        if x is None:
            L.append(f"| **thiếu live** | {fmt_t(r.t_open)} | — | {dcol} | {op} | {rr:+.2f} | — | — |")
        else:
            L.append(f"| khớp | {fmt_t(r.t_open)} | {fmt_t(x['t_open'])} | {dcol} | {op} → {x['open']:.2f} | {rr:+.2f} | "
                     f"{x['r']:+.2f} | {x['money']:+.2f} |")
    for _, x in extra.iterrows():
        L.append(f"| **thừa live** | — | {fmt_t(x['t_open'])} | {side(x['d'])} | → {x['open']:.2f} | — | {x['r']:+.2f} | {x['money']:+.2f} |")
    L.append("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--since", required=True, help="server date, e.g. 2026-10-13")
    ap.add_argument("--until", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    export = Path(a.export)
    meta = json.loads((export / "meta.json").read_text(encoding="utf-8-sig"))
    since = srv(a.since)
    m30 = pd.read_csv(export / "bars_M30.csv")
    until = srv(a.until) if a.until else int(m30["time"].iloc[-1]) + 1800
    offset_h = (meta["exported_server_time"] - meta["exported_gmt"]) / 3600
    live = live_positions(export, since)
    L = [f"# Live và nghiên cứu — {meta['symbol']} ({meta['server']}, tài khoản {meta['login']})", "",
         f"Từ {a.since} (giờ server) đến {fmt_t(until)}. Độ lệch giờ server lúc xuất: UTC{offset_h:+.0f}.", ""]
    if round(offset_h) not in (2, 3):
        L += [f"**Cảnh báo**: server UTC{offset_h:+.0f}, không phải UTC+2/+3 như dữ liệu nghiên cứu. Giờ phiên trong các "
              "thành phần ngữ cảnh (CtxLimit) và quy đổi UTC của S07 sẽ lệch.", ""]
    if not live.empty:
        L += ["## Tổng hợp live theo bot", "", "| Bot | Lệnh | Tiền | R trung bình (theo giá, SL ban đầu) |", "|---|---|---|---|"]
        for bot, g in live.groupby("bot"):
            L.append(f"| {bot} | {len(g)} | {g['money'].sum():+.2f} | {g['r'].mean():+.2f} |")
        L.append("")
    root = research_root(export)
    try:
        res = s07_reference(root, since, until)
    except Exception as ex:      # missing bars etc.
        res, L = None, L + [f"S07: lỗi dựng nghiên cứu ({ex})", ""]
    section("S07 (sổ G89 / S07Tester; bot live = magic 888888 hoặc 707070)", res,
            live[live["bot"] == "S07"] if not live.empty else live, 45 * 60, L)
    try:
        vh = vhedge_reference(root, since)
    except Exception as ex:
        vh, L = None, L + [f"VHedge: lỗi dựng nghiên cứu ({ex})", ""]
    vlive = live[live["bot"] == "VHEDGE"] if not live.empty else live
    if not vlive.empty:          # a group = live legs opened within 5 min
        vlive = vlive.sort_values("t_open")
        grp = (vlive["t_open"].diff().fillna(1e9) > 300).cumsum()
        vlive = vlive.groupby(grp).agg(t_open=("t_open", "first"), d=("d", "first"), open=("open", "first"),
                                       r=("r", "mean"), money=("money", "sum")).reset_index(drop=True)
    section("VHedge G119 (tín hiệu; mỗi nhóm live = các lệnh mở cách nhau ≤ 5 phút)", vh, vlive, 15 * 60, L, rcol=None, use_dir=False)
    try:
        cx = ctx_reference(root, since)
    except Exception as ex:
        cx, L = None, L + [f"CtxLimit: lỗi dựng nghiên cứu ({ex})", ""]
    section("CtxLimit (mô hình đóng băng, limit, lọc S07)", cx, live[live["bot"] == "CTXLIMIT"] if not live.empty else live,
            30 * 60, L)
    others = live[~live["bot"].isin(["S07", "VHEDGE", "CTXLIMIT"])] if not live.empty else live
    if not others.empty:
        L += ["## Bot khác (chỉ live)", "", "| Bot | Giờ | Chiều | Giá vào | R | Tiền |", "|---|---|---|---|---|---|"]
        for _, x in others.iterrows():
            L.append(f"| {x['bot']} | {fmt_t(x['t_open'])} | {side(x['d'])} | {x['open']:.2f} | {x['r']:+.2f} | {x['money']:+.2f} |")
        L.append("")
    shutil.rmtree(root, ignore_errors=True)
    text = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
