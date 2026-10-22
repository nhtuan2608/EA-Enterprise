"""G151 part 2: S07 Python book (G89) vs S07Tester in the MT5 Strategy Tester, trade by trade.
Plan: docs/superpowers/plans/2026-10-22-g151-bot-time-map.md (section "Việc 2"). Inputs: research/long/parity/S07Tester_parity.set.

  python g151_parity_s07.py <data dir> <tester report .htm> <out.json>

Matching: same direction, entry within 30 minutes (server time), preferring the same setup name (S07, S07E, S07R, S07A, ...).
Thresholds written before the run: >= 80% of trades matched on each side, |total R difference| <= 10%.
"""
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402

T0, T1 = g.ts(2024, 2, 20), g.ts(2026, 10, 20)


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.in_cell = [], None, "", False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.in_cell, self.cell = True, ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None:
            self.row.append(self.cell.strip()); self.in_cell = False
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row); self.row = None

    def handle_data(self, data):
        if self.in_cell:
            self.cell += data


def srv(s):
    return int(datetime.strptime(s.strip(), "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


def num(s):
    s = s.replace(" ", "").replace("\xa0", "")
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def tester_positions(report):
    raw = Path(report).read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="replace")
    p = Rows(); p.feed(text)
    rows = p.rows
    # 1) a "Positions" table, if the build writes one
    for k, r in enumerate(rows):
        if r and r[0] == "Time" and "Position" in r and "S / L" in r:
            hdr = r
            out = []
            for q in rows[k + 1:]:
                if len(q) < len(hdr) - 1 or not re.match(r"\d{4}\.\d\d\.\d\d", q[0]):
                    break
                ix = {h: i for i, h in enumerate(hdr)}
                typ = q[ix["Type"]].lower()
                op, sl = num(q[ix["Price"]]), num(q[ix["S / L"]])
                cp = num(q[hdr.index("Price", ix["Price"] + 1)])
                tclose = q[hdr.index("Time", 1)]
                d = 1 if typ.startswith("buy") else -1
                out.append(dict(t=srv(q[0]), t_out=srv(tclose), d=d, entry=op, sl=sl, exit=cp, comment=q[ix["Comment"]] if "Comment" in ix else ""))
            return out, "positions"
    # 2) fall back to the deals table: the stop of each "in" deal from the Orders table (by order ticket); pair each "in" with
    #    the "out" of the opposite type and the same volume - an out at "sl <price>" goes to the open leg with that stop, else FIFO
    sl_of = {}
    for k, r in enumerate(rows):
        if r and r[0] == "Open Time" and "S / L" in r:
            ix = {h: i for i, h in enumerate(r)}
            for q in rows[k + 1:]:
                if len(q) < len(r) - 1 or not re.match(r"\d{4}\.\d\d\.\d\d", q[0]):
                    break
                sl_of[q[ix["Order"]]] = num(q[ix["S / L"]])
            break
    for k, r in enumerate(rows):
        if r and r[0] == "Time" and "Deal" in r and "Direction" in r:
            hdr = r; ix = {h: i for i, h in enumerate(hdr)}
            opens, out = [], []
            for q in rows[k + 1:]:
                if len(q) < len(hdr) - 1 or not re.match(r"\d{4}\.\d\d\.\d\d", q[0]):
                    continue
                dirn, typ = q[ix["Direction"]].lower(), q[ix["Type"]].lower()
                vol, price = num(q[ix["Volume"]]), num(q[ix["Price"]])
                if dirn == "in":
                    opens.append(dict(t=srv(q[0]), d=1 if typ == "buy" else -1, entry=price, vol=vol, comment=q[ix["Comment"]],
                                      sl=sl_of.get(q[ix["Order"]])))
                elif dirn == "out":
                    d_closed = -1 if typ == "buy" else 1
                    cm = q[ix["Comment"]].lower()
                    want = num(cm.split()[1]) if cm.startswith("sl ") and len(cm.split()) > 1 else None
                    cands = [o for o in opens if o["d"] == d_closed and o["vol"] == vol and "exit" not in o]
                    if want is not None:
                        cands = [o for o in cands if o["sl"] is not None and abs(o["sl"] - want) < 0.02] or cands
                    if cands:
                        cands[0].update(exit=price, t_out=srv(q[0]))
            return [o for o in opens if "exit" in o], "deals"
    raise SystemExit("no Positions or Deals table found in the report")


def python_book(root):
    g.HERE = root.parent
    import g89_full_book as fb
    legs = []
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            bases += fb.base_book(fb.e73.context(main, sub), d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                if T0 <= int(L["srv_in"]) < T1:
                    kind = L.get("kind", "S07") if j == 0 else ("S07A" if d == 1 else "S07AS")
                    legs.append(dict(t=int(L["srv_in"]), d=d, kind=kind, r=float(L["r"]), rh=float(L["rh"])))
    return legs


def main():
    root, report, outp = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3])
    tp, how = tester_positions(report)
    tp = [x for x in tp if T0 <= x["t"] < T1]
    for x in tp:
        x["r"] = (x["d"] * (x["exit"] - x["entry"]) / abs(x["entry"] - x["sl"])) if x.get("sl") else None
        x["kind"] = re.match(r"(S07[A-Z]*)", x.get("comment", "") or "").group(1) if re.match(r"S07", x.get("comment", "") or "") else ""
    py = python_book(root)
    used, pairs = set(), []
    for x in sorted(tp, key=lambda z: z["t"]):
        best = None
        for k, L in enumerate(py):
            if k in used or L["d"] != x["d"] or abs(L["t"] - x["t"]) > 1800:
                continue
            score = (L["kind"] == x["kind"], -abs(L["t"] - x["t"]))
            if best is None or score > best[0]:
                best = (score, k)
        if best:
            used.add(best[1]); pairs.append((x, py[best[1]]))
    m_t = len(pairs) / max(len(tp), 1)
    m_p = len(pairs) / max(len(py), 1)
    rt = [x["r"] for x, _ in pairs if x["r"] is not None]
    rp = [L["r"] for x, L in pairs if x["r"] is not None]
    res = {"đọc từ bảng": how, "lệnh tester": len(tp), "lệnh Python": len(py), "khớp": len(pairs),
           "tỷ lệ khớp (tester / Python)": [round(m_t, 3), round(m_p, 3)],
           "R lệnh khớp: tổng tester / Python": [round(float(np.sum(rt)), 1), round(float(np.sum(rp)), 1)] if rt else None,
           "chênh R trung vị mỗi lệnh khớp": round(float(np.median(np.array(rt) - np.array(rp))), 3) if rt else None,
           "tương quan R": round(float(np.corrcoef(rt, rp)[0, 1]), 3) if len(rt) > 2 else None,
           "cùng tên setup": round(float(np.mean([x["kind"] == L["kind"] for x, L in pairs])), 3) if pairs else None,
           "chỉ có ở tester": [dict(t=datetime.fromtimestamp(x["t"], timezone.utc).strftime("%Y-%m-%d %H:%M"), d=x["d"], kind=x["kind"])
                               for x in tp if all(x is not y for y, _ in pairs)][:40],
           "chỉ có ở Python": [dict(t=datetime.fromtimestamp(L["t"], timezone.utc).strftime("%Y-%m-%d %H:%M"), d=L["d"], kind=L["kind"])
                               for k, L in enumerate(py) if k not in used][:40]}
    if rt:
        res["chênh tổng R (%)"] = round(100 * (np.sum(rt) - np.sum(rp)) / max(abs(np.sum(rp)), 1e-9), 1)
        res["kết luận"] = ("TIN CẬY" if min(m_t, m_p) >= 0.8 and abs(res["chênh tổng R (%)"]) <= 10 else "LỆCH: ghi chú độ lệch cho nghiên cứu Python")
    outp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("chỉ có")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
