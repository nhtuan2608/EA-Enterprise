"""Extract original (not quoted) signals from OCR rows: bot blocks and manual calls, with date, time, levels and outcome replies."""
import json
import re
import unicodedata

MON = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}


def norm(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D")


def ttime(s):
    m = re.search(r"(\d{1,2}):(\d{2})\s*$", s)
    if not m:
        return None
    h = int(m.group(1)[-2:])
    h = h if h < 24 else int(m.group(1)[-1:])
    return f"{h:02d}:{m.group(2)}"


rows = sorted((y, x, norm(t), c) for y, x, t, c in json.load(open("ocr_dedup.json", encoding="utf-8")))
date = None
dated = []
for y, x, t, c in rows:
    tl = t.lower().replace(" ", "")
    md = re.fullmatch(r"(january|february|march|april|may|june|july|august|september|october|november|december)(\d{1,2})", tl)
    if md and x > 500:
        date = (MON[md.group(1)], int(md.group(2)))
        continue
    dated.append((y, x, t, tl, date))

HEAD_BOT = re.compile(r"^(xauusd|xagusd|usousd)(\d{1,2})\|(buy|sell)")
HEAD_MAN = re.compile(r"^(?:@all|@ail|@a11)?(sell|buy)(limit|stop|now)?(gold|vang|xauusd|xau|btcusd|btc|bitcoin|eurusd|euro|eur|dau|oil|bac|xagusd|xag|silver)?(now|limit|stop)?(?:quanh|vung|zone|:)?(\d{1,6}(?:\.\d+)?)(?:-(\d{1,6}(?:\.\d+)?))?")
HEAD_SPLIT = re.compile(r"^(?:@all)?(sell|buy)(limit|stop|now)?(gold|vang|xau|btc|eurusd|euro|eur|dau|oil|bac|xag)(now|limit|stop)?$")
SYMMAP = {"gold": "XAUUSD", "vang": "XAUUSD", "xauusd": "XAUUSD", "xau": "XAUUSD", "btcusd": "BTCUSD", "btc": "BTCUSD", "bitcoin": "BTCUSD", "eurusd": "EURUSD", "euro": "EURUSD", "eur": "EURUSD", "dau": "USOUSD", "oil": "USOUSD", "bac": "XAGUSD", "xagusd": "XAGUSD", "xag": "XAGUSD", "silver": "XAGUSD", None: "XAUUSD"}


def levels(lines):
    sl, tps, entry = None, [], None
    for t, tl in lines:
        m = re.search(r"sl[:;]?(\d{1,5}(?:\.\d+)?)", tl)
        if m and sl is None:
            sl = float(m.group(1))
        if tl.startswith("entry"):
            m2 = re.search(r"(\d{2,5}(?:\.\d+)?)", tl)
            entry = float(m2.group(1)) if m2 else None
        for m3 in re.finditer(r"tp\d?[:;]?((?:\d{1,5}(?:\.\d+)?[-,]?)+)", tl):
            tps += [float(v) for v in re.findall(r"\d{1,5}(?:\.\d+)?", m3.group(1))]
    return entry, sl, tps


out = []
n = len(dated)
for k, (y, x, t, tl, date) in enumerate(dated):
    if x > 262:
        continue
    quoted = any("doitinhieu" in dated[j][3] and 0 <= y - dated[j][0] < 22 for j in range(max(0, k - 4), k))
    if quoted:
        continue
    tl = re.sub(r"^[^a-z@]+", "", tl).replace("g0ld", "gold").replace("goid", "gold").replace("l1mit", "limit").replace("oilcash", "oil")
    tl = re.sub(r"^limit(buy|sell)", r"limit", tl)
    if HEAD_SPLIT.match(tl) and k + 1 < n and dated[k + 1][0] - y < 30:
        nxt = re.sub(r"^[^a-z0-9@]+", "", dated[k + 1][3])
        tl = tl + re.sub(r"^(entry|entey|entrv)[:;]?", "", nxt)
    mb, mm = HEAD_BOT.match(tl), HEAD_MAN.match(tl)
    if not (mb or mm):
        continue
    # body: following original-column rows until a time stamp at the bubble's right edge or 260 px
    body, tm = [(t, tl)], None
    for j in range(k + 1, min(n, k + 14)):
        y2, x2, t2, tl2, _ = dated[j]
        if y2 - y > 260:
            break
        if x2 > 262 and ttime(t2) is None:
            continue
        if "doitinhieu" in tl2:
            break
        if ttime(t2) and x2 > 280:
            tm = ttime(t2)
            break
        tl2 = re.sub(r"^[^a-z@]+", "", tl2)
        if x2 <= 262 and (HEAD_BOT.match(tl2) or HEAD_MAN.match(tl2) or tl2.startswith("lfxbot")):
            break
        body.append((t2, tl2))
    # status line just above a bot head
    status = None
    if mb:
        for j in range(k - 1, max(-1, k - 3), -1):
            if "lfxbot" in dated[j][3] or "lfx bot" in dated[j][2].lower():
                status = "duyet" if "duyet" in dated[j][3] else ("tuchoi" if "chox" in dated[j][3] or "choi" in dated[j][3] else "?")
                break
    entry, sl, tps = levels(body)
    rec = {"date": date, "time": tm, "y": y, "raw": " | ".join(b[0] for b in body)[:200]}
    if mb:
        rec.update(kind="bot", sym=mb.group(1).upper(), tf=int(mb.group(2)), side=mb.group(3), status=status, entry=entry, sl=sl, tps=tps)
        sc = re.search(r"score[:;]?(\d+)/100", " ".join(b[1] for b in body))
        rec["score"] = int(sc.group(1)) if sc else None
    else:
        lo, hi = mm.group(5), mm.group(6)
        sym = SYMMAP.get(mm.group(3), "XAUUSD")
        order = mm.group(2) or mm.group(4) or "now"
        if sym == "BTCUSD":
            fix = lambda v: (float(v) * 1000 if v and "." in v and float(v) < 1000 else (float(v) if v else None))  # noqa: E731
            lo, hi = fix(lo), fix(hi)
            sl = sl * 1000 if sl and sl < 1000 else sl
            tps = [t * 1000 if t < 1000 else t for t in tps]
        rec.update(kind="manual", sym=sym, side=mm.group(1), order=order, zone=[lo, hi], sl=sl, tps=tps)
        e2, s2, t2 = levels([(t, tl)])
        if rec["sl"] is None:
            rec["sl"] = s2
    out.append(rec)

# drop exact duplicates (same date, side, zone/entry) keeping the first
seen, sigs = set(), []
for r in out:
    key = (r["date"], r["kind"], r["side"], tuple(r.get("zone") or []) if r["kind"] == "manual" else r.get("entry"))
    if key in seen:
        continue
    seen.add(key)
    sigs.append(r)
json.dump(sigs, open("extracted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bots = [s for s in sigs if s["kind"] == "bot"]
man = [s for s in sigs if s["kind"] == "manual"]
print("bot", len(bots), "manual", len(man))
for s in sigs:
    if s["kind"] == "manual":
        print(s["date"], s["time"], s["side"], s["order"], s["zone"], "SL", s["sl"], "TP", s["tps"][:4], "||", s["raw"][:90])
print("--- bot")
for s in bots:
    print(s["date"], s["time"], s["sym"], s["tf"], s["side"], s["status"], s["entry"], s["sl"], s["tps"], s["score"])
