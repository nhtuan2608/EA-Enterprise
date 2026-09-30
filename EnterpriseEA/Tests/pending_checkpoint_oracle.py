"""Decimal, canonical-fingerprint oracle for synthetic pending-order restore."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json

VERSION = "pending-order-checkpoint-v1.1.0"
IDENTITY_KEYS = ("intent_id", "config_version", "broker_server",
                 "account_fingerprint", "order_ticket")


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def fingerprint(checkpoint):
    signed = {key: value for key, value in checkpoint.items()
              if key not in {"fingerprint", "recomputed_fingerprint"}}
    serialized = json.dumps(_jsonable(signed), sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def make_checkpoint(state, sequence, captured_at_utc, max_age_seconds, audit_anchor):
    payload = deepcopy(state)
    result = dict(schema_version=VERSION, integrity_marker="CHECKPOINT_OK",
                  checkpoint_sequence=sequence, captured_at_utc=captured_at_utc,
                  max_age_seconds=max_age_seconds, state=payload)
    result.update(deepcopy(audit_anchor))
    result["fingerprint"] = fingerprint(result)
    return result


def _valid_payload(p, captured):
    if (not isinstance(p, dict) or p.get("initialized") is not True or
            any(not p.get(k) for k in ("intent_id", "candidate_id", "setup_id", "setup_version",
                                         "config_version", "instrument_version", "canonical_symbol",
                                         "account_currency", "broker_server", "account_fingerprint",
                                         "order_ticket")) or
            p.get("trade_style") not in {"SCALP", "SWING"} or
            p.get("order_type") not in {"BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"} or
            p.get("status") not in {"WORKING", "PARTIAL", "CANCEL_REQUIRED", "CANCEL_REQUESTED",
                                    "FILLED", "CANCELLED", "EXPIRED", "BREACH_REVIEW",
                                    "PENDING_RACE_UNKNOWN"}):
        return False
    accepted = p.get("broker_accepted_at_utc", 0)
    if (not isinstance(accepted, int) or accepted <= 0 or
            p.get("effective_expires_at_utc", 0) <= accepted or captured < accepted or
            p.get("max_wait_closed_bars", 0) <= 0 or p.get("bars_waited", -1) < 0 or
            p.get("last_closed_bar_sequence", -1) < p["bars_waited"] or
            p.get("last_bar_closed_at_utc", 0) > captured or
            p.get("last_guard_at_utc", 0) > captured or
            p.get("last_event_at_utc", 0) < accepted or
            p["last_event_at_utc"] > captured or
            any(p.get(k, 0) > captured for k in
                ("cancel_required_at_utc", "cancel_requested_at_utc", "broker_confirmed_at_utc")) or
            p.get("last_event_sequence", -1) < 0):
        return False
    if ((p["last_event_sequence"] == 0 and
         (p.get("last_event_id") or p.get("last_event_fingerprint"))) or
            (p["last_event_sequence"] > 0 and
             (not p.get("last_event_id") or not p.get("last_event_fingerprint"))) or
            (p["bars_waited"] > 0 and
             (p.get("last_bar_closed_at_utc", 0) <= accepted or
              not p.get("last_bar_fingerprint") or not p.get("last_setup_snapshot_id"))) or
            (p.get("last_guard_at_utc", 0) > 0 and
             (not p.get("last_guard_snapshot_id") or not p.get("last_guard_fingerprint")))):
        return False
    numeric = ("requested_volume", "filled_volume", "cancelled_volume", "remaining_volume",
               "volume_step", "reserved_risk_per_lot_money", "max_committed_risk_money",
               "filled_initial_risk_money", "remaining_risk_reservation_money",
               "total_committed_risk_money")
    try:
        n = {key: Decimal(str(p[key])) for key in numeric}
    except (KeyError, ValueError, TypeError):
        return False
    if (any(not v.is_finite() for v in n.values()) or
            any(n[k] <= 0 for k in ("requested_volume", "volume_step",
                                       "reserved_risk_per_lot_money", "max_committed_risk_money")) or
            any(n[k] < 0 for k in ("filled_volume", "cancelled_volume", "remaining_volume",
                                      "filled_initial_risk_money", "remaining_risk_reservation_money",
                                      "total_committed_risk_money")) or
            n["requested_volume"] / n["volume_step"] !=
            (n["requested_volume"] / n["volume_step"]).to_integral_value() or
            n["requested_volume"] != n["filled_volume"] + n["cancelled_volume"] + n["remaining_volume"] or
            n["remaining_risk_reservation_money"] !=
            n["remaining_volume"] * n["reserved_risk_per_lot_money"] or
            n["total_committed_risk_money"] !=
            n["filled_initial_risk_money"] + n["remaining_risk_reservation_money"]):
        return False
    status = p["status"]
    if ((status == "WORKING" and
         (n["filled_volume"] > 0 or n["cancelled_volume"] > 0 or n["remaining_volume"] <= 0)) or
            (status == "PARTIAL" and
             (n["filled_volume"] <= 0 or n["remaining_volume"] <= 0)) or
            (status == "FILLED" and
             (n["remaining_volume"] > 0 or n["cancelled_volume"] > 0)) or
            (status in {"CANCELLED", "EXPIRED"} and
             (n["remaining_volume"] > 0 or n["cancelled_volume"] <= 0 or
              p.get("broker_confirmed_at_utc", 0) <= 0)) or
            (status in {"CANCEL_REQUIRED", "CANCEL_REQUESTED"} and
             (n["remaining_volume"] <= 0 or p.get("cancel_required_at_utc", 0) <= 0)) or
            (status == "CANCEL_REQUESTED" and
             (p.get("cancel_requested_at_utc", 0) <= 0 or not p.get("cancel_correlation_id")))):
        return False
    return True


def restore(existing, checkpoint, expected_identity, now_utc, guard=None):
    state = deepcopy(existing) if existing is not None else dict(initialized=False)
    g = deepcopy(guard) if guard is not None else dict(initialized=False, last_sequence=0,
                                                       last_fingerprint="", audit_tail_verified=False)

    def reject(reason):
        state.update(status="PENDING_RACE_UNKNOWN", reason_code=reason,
                     new_entries_blocked=True)
        return state, g, False, reason

    c = checkpoint if isinstance(checkpoint, dict) else {}
    identity = expected_identity if isinstance(expected_identity, dict) else {}
    payload = c.get("state")
    captured = c.get("captured_at_utc")
    if (c.get("schema_version") != VERSION or c.get("integrity_marker") != "CHECKPOINT_OK" or
            not c.get("fingerprint") or not isinstance(payload, dict) or
            c["fingerprint"] != fingerprint(c) or
            type(c.get("checkpoint_sequence")) is not int or c["checkpoint_sequence"] <= 0 or
            type(captured) is not int or captured <= 0 or
            type(c.get("max_age_seconds")) is not int or c["max_age_seconds"] <= 0 or
            type(now_utc) is not int or now_utc < captured or
            now_utc - captured > c["max_age_seconds"] or
            type(c.get("audit_sequence")) is not int or c["audit_sequence"] <= 0 or
            not c.get("audit_fingerprint") or not c.get("audit_event_id") or
            type(c.get("audit_observed_at_utc")) is not int or
            c["audit_observed_at_utc"] < payload.get("broker_accepted_at_utc", 0) or
            c["audit_observed_at_utc"] > captured or
            any(not identity.get(k) or payload.get(k) != identity[k]
                for k in IDENTITY_KEYS) or
            not _valid_payload(payload, captured)):
        return reject("PENDING_CHECKPOINT_REJECTED")
    if g["initialized"]:
        if c["checkpoint_sequence"] == g["last_sequence"] and c["fingerprint"] == g["last_fingerprint"]:
            return state, g, True, "PENDING_CHECKPOINT_REPLAY_IGNORED"
        if c["checkpoint_sequence"] <= g["last_sequence"]:
            return reject("PENDING_CHECKPOINT_SEQUENCE_REGRESSION")
    state = deepcopy(payload)
    state.update(status="PENDING_RACE_UNKNOWN",
                 reason_code="RESTORED_PENDING_BROKER_RECONCILIATION",
                 new_entries_blocked=True)
    g.update(initialized=True, last_sequence=c["checkpoint_sequence"],
             last_fingerprint=c["fingerprint"], audit_tail_verified=False)
    return state, g, True, "PENDING_CHECKPOINT_RESTORED_RECONCILIATION_REQUIRED"


def verify_audit_tail(state, checkpoint, tail, guard):
    from pending_audit_oracle import VERSION as AUDIT_VERSION, fingerprint as audit_fingerprint

    s = deepcopy(state)
    g = deepcopy(guard)
    c = checkpoint
    t = tail
    p = c.get("state", {})
    fields = ("intent_id", "candidate_id", "setup_id", "setup_version",
              "config_version", "instrument_version", "broker_server",
              "account_fingerprint", "order_ticket")
    numeric = (("filled_volume_after", "filled_volume"),
               ("cancelled_volume_after", "cancelled_volume"),
               ("remaining_volume_after", "remaining_volume"),
               ("filled_risk_after", "filled_initial_risk_money"),
               ("remaining_reservation_after", "remaining_risk_reservation_money"))
    if (not g.get("initialized") or c.get("checkpoint_sequence") != g.get("last_sequence") or
            c.get("fingerprint") != g.get("last_fingerprint") or
            not c.get("fingerprint") or c["fingerprint"] != fingerprint(c) or
            t.get("schema_version") != AUDIT_VERSION or
            t.get("audit_sequence") != c.get("audit_sequence") or
            not t.get("fingerprint") or t["fingerprint"] != audit_fingerprint(t) or
            t["fingerprint"] != c.get("audit_fingerprint") or
            t.get("event_id") != c.get("audit_event_id") or
            t.get("observed_at_utc") != c.get("audit_observed_at_utc") or
            any(t.get(k) != p.get(k) for k in fields) or
            t.get("state_after") != p.get("status") or
            t.get("reason_code") != p.get("reason_code") or
            t.get("effective_expires_at_utc") != p.get("effective_expires_at_utc") or
            t.get("bars_waited_after") != p.get("bars_waited") or
            t.get("broker_event_sequence_after") != p.get("last_event_sequence") or
            any(t.get(a) != p.get(b) for a, b in numeric) or
            s.get("status") != "PENDING_RACE_UNKNOWN" or
            s.get("remaining_volume") != p.get("remaining_volume") or
            s.get("total_committed_risk_money") != p.get("total_committed_risk_money")):
        g["audit_tail_verified"] = False
        s.update(status="PENDING_RACE_UNKNOWN", reason_code="PENDING_CHECKPOINT_AUDIT_TAIL_MISMATCH",
                 new_entries_blocked=True)
        return s, g, False, "PENDING_CHECKPOINT_AUDIT_TAIL_MISMATCH"
    g["audit_tail_verified"] = True
    s["new_entries_blocked"] = True
    return s, g, True, "PENDING_CHECKPOINT_AUDIT_TAIL_MATCHED_BROKER_RECONCILIATION_REQUIRED"
