"""Python mirror of Market/Sentiment.mqh (decisions M1-M6)."""

CCY = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]


def config(**overrides):
    c = dict(enabled=True, against=-0.3, strong=-0.8, consensus=0.7, factor=0.5, floor=0.25, regime=0.3)
    c.update(overrides)
    return c


def pair(symbol, z4, z24, kind="FX"):
    return {"symbol": symbol, "base": symbol[:3], "quote": symbol[3:6], "kind": kind, "z4": z4, "z24": z24}


def compute(pairs, c):
    s4 = {k: 0.0 for k in CCY}
    s24 = {k: 0.0 for k in CCY}
    n = {k: 0 for k in CCY}
    fx = 0
    gold = index = None
    for p in pairs:
        if p["kind"] == "GOLD":
            gold = p
            continue
        if p["kind"] == "INDEX":
            index = index or p
            continue
        if p["kind"] != "FX" or p["base"] not in s4 or p["quote"] not in s4:
            continue
        s4[p["base"]] += p["z4"]; s24[p["base"]] += p["z24"]; n[p["base"]] += 1
        s4[p["quote"]] -= p["z4"]; s24[p["quote"]] -= p["z24"]; n[p["quote"]] += 1
        fx += 1
    for k in CCY:
        if n[k]:
            s4[k] /= n[k]; s24[k] /= n[k]
    if fx < 4 or n["USD"] < 3:
        return {"ok": False, "reason": "SENTIMENT_TOO_FEW_PAIRS"}
    r4, r24, parts = s4["JPY"] + s4["CHF"], s24["JPY"] + s24["CHF"], 2
    if gold:
        r4 += gold["z4"]; r24 += gold["z24"]; parts += 1
    if index:
        r4 -= index["z4"]; r24 -= index["z24"]; parts += 1
    r4 /= parts; r24 /= parts
    regime = "RISK_OFF" if r4 >= c["regime"] else ("RISK_ON" if r4 <= -c["regime"] else "NEUTRAL")
    return {"ok": True, "s4": s4, "s24": s24, "n": n, "regime4": r4, "regime24": r24, "regime": regime}


def against_share(pairs, exclude, legs, h24):
    total = against = 0
    for p in pairs:
        if p["kind"] != "FX" or p["symbol"] == exclude:
            continue
        if not any(c in (p["base"], p["quote"]) for c, _ in legs):
            continue
        z = p["z24"] if h24 else p["z4"]
        support = 0.0
        for c, sign in legs:
            if p["base"] == c:
                support += sign * z
            if p["quote"] == c:
                support -= sign * z
        total += 1
        if support < 0:
            against += 1
    return against / total if total else 0.0


def align(snap, pairs, c, symbol, direction, profile):
    if not c["enabled"]:
        return {"verdict": "UNAVAILABLE", "factor": 1.0, "block": False}
    if not snap["ok"]:
        return {"verdict": "UNAVAILABLE", "factor": 1.0, "block": False}
    base, quote = symbol[:3], symbol[3:6]
    if base in ("XAU", "BTC"):
        tilt = 0.5 if base == "XAU" else -0.5
        a4 = direction * (-snap["s4"]["USD"] + tilt * snap["regime4"])
        a24 = direction * (-snap["s24"]["USD"] + tilt * snap["regime24"])
        legs = [("USD", -direction)]
    else:
        a4 = direction * (snap["s4"].get(base, 0.0) - snap["s4"].get(quote, 0.0))
        a24 = direction * (snap["s24"].get(base, 0.0) - snap["s24"].get(quote, 0.0))
        legs = [(base, direction), (quote, -direction)]
    ag4 = against_share(pairs, symbol, legs, False)
    ag24 = against_share(pairs, symbol, legs, True)
    against = a4 <= c["against"] and a24 <= c["against"]
    strong = a4 <= c["strong"] and a24 <= c["strong"] and ag4 >= c["consensus"] and ag24 >= c["consensus"]
    if strong:
        return {"verdict": "STRONGLY_AGAINST", "factor": c["factor"], "block": profile == "SWING", "a4": a4, "a24": a24}
    if against:
        return {"verdict": "AGAINST", "factor": c["factor"], "block": False, "a4": a4, "a24": a24}
    verdict = "ALIGNED" if a4 >= -c["against"] and a24 >= -c["against"] else "NEUTRAL"
    return {"verdict": verdict, "factor": 1.0, "block": False, "a4": a4, "a24": a24}
