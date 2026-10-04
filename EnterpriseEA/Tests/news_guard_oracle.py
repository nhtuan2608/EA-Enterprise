"""Python mirror of News/NewsState.mqh (News Guard state machine, decisions D1-D5)."""

TRACKED = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY"}

RANK = {"ACTIVE": 5, "POST_NEWS": 4, "PRE_NEWS_BLOCK": 3, "NORMALIZING": 2, "PRE_NEWS": 1, "NORMAL": 0}


def config(**overrides):
    c = dict(enabled=True, scalp_block_before_min=60, swing_block_before_min=180, active_min=5,
             post_min=15, max_normalize_min=60, be_before_min=15, be_min_r=0.3, allow_when_unknown=False)
    c.update(overrides)
    return c


def symbol_currencies(base, profit):
    out = []
    if base in TRACKED:
        out.append(base)
    if profit in TRACKED and profit != base:
        out.append(profit)
    return out


def event_state(t, now, c, normalized):
    if t <= now < t + c["active_min"] * 60:
        return "ACTIVE"
    if t + c["active_min"] * 60 <= now < t + c["post_min"] * 60:
        return "POST_NEWS"
    if t - c["scalp_block_before_min"] * 60 <= now < t:
        return "PRE_NEWS_BLOCK"
    if t + c["post_min"] * 60 <= now < t + c["max_normalize_min"] * 60 and not normalized:
        return "NORMALIZING"
    if t - c["swing_block_before_min"] * 60 <= now < t - c["scalp_block_before_min"] * 60:
        return "PRE_NEWS"
    return "NORMAL"


def evaluate(events, currencies, now, c, normalized_event_utc=0):
    """events: list of (time_utc, currency)."""
    state, event_utc, best = "NORMAL", 0, 0
    for t, currency in events:
        if currency not in currencies:
            continue
        s = event_state(t, now, c, normalized_event_utc >= t)
        rank = RANK[s]
        if rank > best or (rank == best and rank > 0 and t < event_utc):
            best, state, event_utc = rank, s, t
    return state, event_utc


def entry_block(state, profile, c):
    if not c["enabled"] or state == "DISABLED":
        return ""
    if state == "UNKNOWN":
        return "" if c["allow_when_unknown"] else "NEWS_UNKNOWN"
    if state == "PRE_NEWS":
        return "NEWS_PRE_BLOCK_SWING" if profile == "SWING" else ""
    if state == "PRE_NEWS_BLOCK":
        return "NEWS_PRE_BLOCK_SWING" if profile == "SWING" else "NEWS_PRE_BLOCK_SCALP"
    return {"ACTIVE": "NEWS_ACTIVE", "POST_NEWS": "NEWS_POST", "NORMALIZING": "NEWS_NORMALIZING"}.get(state, "")


def indirect_window(events, currencies, now, c):
    """events: list of (time_utc, currency, strength_sector). Returns (swing_blocked, scalp_reduced)."""
    swing = scalp = False
    if not c["enabled"]:
        return swing, scalp
    for t, currency, strength in events:
        if currency in currencies or not strength:
            continue
        swing |= t - c["swing_block_before_min"] * 60 <= now < t + c["post_min"] * 60
        scalp |= t - c["scalp_block_before_min"] * 60 <= now < t + c["post_min"] * 60
    return swing, scalp


def break_even_due(events, currencies, now, c):
    if not c["enabled"]:
        return False
    return any(t - c["be_before_min"] * 60 <= now < t + c["post_min"] * 60
               for t, currency in events if currency in currencies)
