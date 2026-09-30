"""Independent Decimal oracle for synthetic pending-order lifecycle fixtures."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation


def _d(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def _aligned(value, step):
    return (value is not None and step is not None and value > 0 and step > 0 and
            value / step == (value / step).to_integral_value())


def initialize(seed, now_utc):
    required = ("intent_id", "candidate_id", "setup_id", "setup_version",
                "config_version", "instrument_version", "canonical_symbol", "account_currency",
                "broker_server", "account_fingerprint", "order_ticket")
    dates = ("setup_valid_until_utc", "session_end_at_utc", "broker_expiration_at_utc")
    volume = _d(seed.get("requested_volume"))
    step = _d(seed.get("volume_step"))
    per_lot = _d(seed.get("reserved_risk_per_lot_money"))
    budget = _d(seed.get("max_committed_risk_money"))
    triggered = seed.get("candidate_triggered_at_utc")
    submitted = seed.get("submitted_at_utc")
    accepted = seed.get("broker_accepted_at_utc")
    if (any(not seed.get(k) for k in required) or
            seed.get("trade_style") not in {"SCALP", "SWING"} or
            seed.get("order_type") not in {"BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"} or
            not all(isinstance(x, int) and not isinstance(x, bool) for x in
                    (triggered, submitted, accepted, now_utc, *(seed.get(k) for k in dates))) or
            triggered <= 0 or submitted < triggered or accepted < submitted or now_utc < accepted or
            any(seed[k] <= accepted for k in dates) or
            not isinstance(seed.get("placed_after_closed_bar_sequence"), int) or
            seed["placed_after_closed_bar_sequence"] < 0 or
            not isinstance(seed.get("max_wait_closed_bars"), int) or seed["max_wait_closed_bars"] <= 0 or
            seed.get("placement_validated") is not True or
            seed.get("broker_expiration_attested") is not True or
            not _aligned(volume, step) or per_lot is None or per_lot <= 0 or
            budget is None or budget <= 0):
        return None
    expiry = min(seed[k] for k in dates)
    reserved = volume * per_lot
    if now_utc >= expiry or reserved > budget:
        return None
    state = {k: seed[k] for k in required}
    state.update(trade_style=seed["trade_style"], order_type=seed["order_type"],
                 initialized=True, status="WORKING", reason_code="PENDING_ACCEPTED_RESERVED",
                 cancel_reason="", broker_accepted_at_utc=accepted,
                 effective_expires_at_utc=expiry, cancel_required_at_utc=0,
                 cancel_requested_at_utc=0, broker_confirmed_at_utc=0,
                 cancel_correlation_id="",
                 last_closed_bar_sequence=seed["placed_after_closed_bar_sequence"],
                 last_bar_closed_at_utc=0, last_bar_fingerprint="", last_setup_snapshot_id="",
                 last_guard_snapshot_id="", last_guard_fingerprint="", last_guard_at_utc=0,
                 max_wait_closed_bars=seed["max_wait_closed_bars"], bars_waited=0,
                 last_event_sequence=0, last_event_at_utc=accepted, last_event_id="",
                 last_event_fingerprint="", requested_volume=volume, filled_volume=Decimal(0),
                 cancelled_volume=Decimal(0), remaining_volume=volume, volume_step=step,
                 reserved_risk_per_lot_money=per_lot, max_committed_risk_money=budget,
                 filled_initial_risk_money=Decimal(0), remaining_risk_reservation_money=reserved,
                 total_committed_risk_money=reserved, new_entries_blocked=False)
    return state


def _unknown(s, reason):
    s.update(status="PENDING_RACE_UNKNOWN", reason_code=reason, new_entries_blocked=True)
    return s, False


def _require_cancel(s, at_utc, reason):
    if s["status"] in {"WORKING", "PARTIAL"} and s["remaining_volume"] > 0:
        s.update(status="CANCEL_REQUIRED", reason_code="PENDING_CANCEL_REQUIRED",
                 cancel_reason=reason, cancel_required_at_utc=at_utc, new_entries_blocked=True)


def check_deadline(state, now_utc):
    s = deepcopy(state)
    if not s["initialized"] or now_utc < s["broker_accepted_at_utc"]:
        return s, False
    if now_utc >= s["effective_expires_at_utc"]:
        _require_cancel(s, now_utc, "UTC_DEADLINE_REACHED")
    return s, True


def observe(state, bar):
    s = deepcopy(state)
    if not s["initialized"] or s["status"] not in {"WORKING", "PARTIAL", "CANCEL_REQUIRED"}:
        return s, False
    if (bar.get("closed_bar_sequence") == s["last_closed_bar_sequence"] and
            s["last_bar_fingerprint"] and bar.get("intent_id") == s["intent_id"] and
            bar.get("config_version") == s["config_version"] and
            bar.get("bar_fingerprint") == s["last_bar_fingerprint"] and
            bar.get("setup_snapshot_id") == s["last_setup_snapshot_id"] and
            bar.get("closed_at_utc") == s["last_bar_closed_at_utc"]):
        return s, True
    if (bar.get("intent_id") != s["intent_id"] or
            bar.get("config_version") != s["config_version"] or
            not bar.get("setup_snapshot_id") or not bar.get("bar_fingerprint") or
            bar.get("closed_bar_sequence") != s["last_closed_bar_sequence"] + 1 or
            bar.get("closed_at_utc", 0) <= max(s["broker_accepted_at_utc"],
                                               s["last_bar_closed_at_utc"]) or
            bar.get("bar_closed_confirmed") is not True or bar.get("data_quality") != "OK"):
        return _unknown(s, "PENDING_BAR_MISSING_CONFLICTING_OR_UNTRUSTED")
    s.update(last_closed_bar_sequence=bar["closed_bar_sequence"],
             last_bar_closed_at_utc=bar["closed_at_utc"],
             last_bar_fingerprint=bar["bar_fingerprint"],
             last_setup_snapshot_id=bar["setup_snapshot_id"], bars_waited=s["bars_waited"] + 1)
    if bar["closed_at_utc"] >= s["effective_expires_at_utc"]:
        _require_cancel(s, bar["closed_at_utc"], "UTC_DEADLINE_REACHED")
    elif s["bars_waited"] >= s["max_wait_closed_bars"]:
        _require_cancel(s, bar["closed_at_utc"], "MAX_WAIT_CLOSED_BARS_REACHED")
    elif any(bar.get(k) is not True for k in
             ("setup_valid", "session_open", "risk_entry_allowed", "news_entry_allowed",
              "quote_premise_valid", "config_spec_unchanged")):
        _require_cancel(s, bar["closed_at_utc"], "SETUP_OR_POLICY_INVALIDATED")
    return s, True


def observe_guard(state, guard):
    s = deepcopy(state)
    if not s["initialized"] or s["status"] not in {"WORKING", "PARTIAL", "CANCEL_REQUIRED"}:
        return s, False
    if (guard.get("intent_id") == s["intent_id"] and
            guard.get("config_version") == s["config_version"] and
            guard.get("snapshot_id") and guard["snapshot_id"] == s["last_guard_snapshot_id"] and
            guard.get("content_fingerprint") == s["last_guard_fingerprint"] and
            guard.get("observed_at_utc") == s["last_guard_at_utc"]):
        return s, True
    if (guard.get("intent_id") != s["intent_id"] or
            guard.get("config_version") != s["config_version"] or
            not guard.get("snapshot_id") or not guard.get("content_fingerprint") or
            guard.get("observed_at_utc", 0) <= max(s["broker_accepted_at_utc"],
                                                   s["last_guard_at_utc"]) or
            guard.get("data_quality") != "OK"):
        return _unknown(s, "PENDING_GUARD_MISSING_CONFLICTING_OR_UNTRUSTED")
    s.update(last_guard_snapshot_id=guard["snapshot_id"],
             last_guard_fingerprint=guard["content_fingerprint"],
             last_guard_at_utc=guard["observed_at_utc"])
    if guard["observed_at_utc"] >= s["effective_expires_at_utc"]:
        _require_cancel(s, guard["observed_at_utc"], "UTC_DEADLINE_REACHED")
    elif any(guard.get(k) is not True for k in
             ("setup_valid", "session_open", "risk_entry_allowed", "news_entry_allowed",
              "quote_premise_valid", "config_spec_unchanged")):
        _require_cancel(s, guard["observed_at_utc"], "SETUP_OR_POLICY_INVALIDATED")
    return s, True


def apply_broker_event(state, event):
    s = deepcopy(state)
    if not s["initialized"]:
        return s, False
    if (event.get("event_sequence", 0) > 0 and event.get("event_sequence") == s["last_event_sequence"] and
            event.get("event_id") == s["last_event_id"] and
            event.get("content_fingerprint") == s["last_event_fingerprint"]):
        return s, True
    if (not event.get("event_id") or not event.get("content_fingerprint") or
            event.get("event_sequence") != s["last_event_sequence"] + 1 or
            any(event.get(k) != s[k] for k in
                ("intent_id", "config_version", "instrument_version", "broker_server",
                 "account_fingerprint", "order_ticket")) or
            event.get("occurred_at_utc", 0) < s["last_event_at_utc"] or
            event.get("data_quality") != "OK"):
        return _unknown(s, "PENDING_BROKER_EVENT_MISSING_OR_CONFLICTING")
    kind = event.get("event_kind")
    if kind == "FILL":
        if s["status"] not in {"WORKING", "PARTIAL", "CANCEL_REQUIRED", "CANCEL_REQUESTED", "BREACH_REVIEW"}:
            return _unknown(s, "FILL_AFTER_TERMINAL_OR_UNKNOWN_STATE")
        volume = _d(event.get("fill_volume"))
        risk = _d(event.get("filled_initial_risk_money"))
        if not _aligned(volume, s["volume_step"]) or volume > s["remaining_volume"] or risk is None or risk <= 0:
            return _unknown(s, "PENDING_FILL_VOLUME_OR_RISK_INVALID")
        late = (event["occurred_at_utc"] >= s["effective_expires_at_utc"] or
                s["status"] in {"CANCEL_REQUIRED", "CANCEL_REQUESTED", "BREACH_REVIEW"})
        s["filled_volume"] += volume
        s["remaining_volume"] -= volume
        s["filled_initial_risk_money"] += risk
        s["remaining_risk_reservation_money"] = s["remaining_volume"] * s["reserved_risk_per_lot_money"]
        s["total_committed_risk_money"] = s["filled_initial_risk_money"] + s["remaining_risk_reservation_money"]
        if late or s["total_committed_risk_money"] > s["max_committed_risk_money"]:
            s.update(status="BREACH_REVIEW", reason_code=("FILL_DURING_CANCEL_OR_AFTER_DEADLINE" if late else
                                                          "FILLED_RISK_EXCEEDS_BUDGET"), new_entries_blocked=True)
        else:
            s.update(status="FILLED" if s["remaining_volume"] == 0 else "PARTIAL",
                     reason_code="PENDING_FULLY_FILLED" if s["remaining_volume"] == 0 else
                                 "PENDING_PARTIALLY_FILLED")
    elif kind == "CANCEL_REQUESTED":
        if s["status"] not in {"CANCEL_REQUIRED", "BREACH_REVIEW"}:
            return s, False
        if not event.get("correlation_id") or s["remaining_volume"] <= 0 or s["cancel_requested_at_utc"] > 0:
            return _unknown(s, "CANCEL_REQUEST_INVALID")
        s.update(status="CANCEL_REQUESTED", cancel_correlation_id=event["correlation_id"],
                 cancel_requested_at_utc=event["occurred_at_utc"],
                 reason_code="CANCEL_SENT_AWAITING_BROKER_CONFIRMATION", new_entries_blocked=True)
    elif kind in {"CANCEL_CONFIRMED", "EXPIRE_CONFIRMED"}:
        remaining = _d(event.get("confirmed_remaining_volume"))
        if s["status"] not in {"WORKING", "PARTIAL", "CANCEL_REQUESTED",
                               "CANCEL_REQUIRED", "BREACH_REVIEW"}:
            return s, False
        if (s["remaining_volume"] <= 0 or remaining != s["remaining_volume"] or
                (kind == "CANCEL_CONFIRMED" and s["cancel_requested_at_utc"] > 0 and
                 (not event.get("correlation_id") or event["correlation_id"] != s["cancel_correlation_id"]))):
            return _unknown(s, "CANCEL_CONFIRM_VOLUME_OR_ID_MISMATCH")
        was_breach = s["status"] == "BREACH_REVIEW"
        s["cancelled_volume"] += s["remaining_volume"]
        s.update(remaining_volume=Decimal(0), remaining_risk_reservation_money=Decimal(0),
                 total_committed_risk_money=s["filled_initial_risk_money"],
                 broker_confirmed_at_utc=event["occurred_at_utc"],
                 status="BREACH_REVIEW" if was_breach else
                        ("CANCELLED" if kind == "CANCEL_CONFIRMED" else "EXPIRED"),
                 reason_code="REMAINDER_INACTIVE_AFTER_BREACH" if was_breach else
                             "PENDING_REMAINDER_BROKER_CONFIRMED_INACTIVE", new_entries_blocked=True)
    else:
        return _unknown(s, "PENDING_BROKER_EVENT_KIND_UNKNOWN")
    if s["requested_volume"] != s["filled_volume"] + s["cancelled_volume"] + s["remaining_volume"]:
        return _unknown(s, "PENDING_VOLUME_OR_RISK_INVARIANT_BROKEN")
    s.update(last_event_sequence=event["event_sequence"], last_event_at_utc=event["occurred_at_utc"],
             last_event_id=event["event_id"], last_event_fingerprint=event["content_fingerprint"])
    return s, True
