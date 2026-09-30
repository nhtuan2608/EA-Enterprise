"""Independent synthetic audit-chain oracle for pending-order transitions."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json

VERSION = "pending-order-audit-v1.0.0"
IDENTITY = ("intent_id", "candidate_id", "setup_id", "setup_version", "config_version",
            "instrument_version", "broker_server", "account_fingerprint", "order_ticket")
NUMERIC = ("filled_volume", "cancelled_volume", "remaining_volume",
           "filled_initial_risk_money", "remaining_risk_reservation_money")


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def fingerprint(record):
    signed = {k: v for k, v in record.items() if k not in {"fingerprint", "recomputed_fingerprint"}}
    return hashlib.sha256(json.dumps(_jsonable(signed), sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def make_record(before, after, cause_kind, audit_sequence, previous_fingerprint,
                event_id, occurred_at_utc, observed_at_utc, source_fingerprint,
                broker_snapshot_id="", order_history_fingerprint="", deal_set_fingerprint="",
                data_quality="OK"):
    record = dict(schema_version=VERSION, audit_sequence=audit_sequence,
                  previous_fingerprint=previous_fingerprint, event_id=event_id,
                  cause_kind=cause_kind, source_fingerprint=source_fingerprint,
                  broker_snapshot_id=broker_snapshot_id,
                  order_history_fingerprint=order_history_fingerprint,
                  deal_set_fingerprint=deal_set_fingerprint,
                  occurred_at_utc=occurred_at_utc, observed_at_utc=observed_at_utc,
                  data_quality=data_quality, state_before=before["status"],
                  state_after=after["status"], reason_code=after["reason_code"],
                  effective_expires_at_utc=after["effective_expires_at_utc"],
                  bars_waited_before=before["bars_waited"],
                  bars_waited_after=after["bars_waited"],
                  broker_event_sequence_before=before["last_event_sequence"],
                  broker_event_sequence_after=after["last_event_sequence"])
    for key in IDENTITY:
        record[key] = after[key]
    for key in NUMERIC:
        label = {"filled_initial_risk_money": "filled_risk",
                 "remaining_risk_reservation_money": "remaining_reservation"}.get(key, key)
        record[label + "_before"] = before[key]
        record[label + "_after"] = after[key]
    record["fingerprint"] = fingerprint(record)
    return record


def cursor_defaults():
    return dict(initialized=False, blocked=False, last_sequence=0, last_fingerprint="",
                last_event_id="", last_observed_at_utc=0)


def accept(before, after, record, cursor):
    a = deepcopy(after)
    c = deepcopy(cursor)
    r = record
    seed_record = r.get("cause_kind") == "SEED_ACCEPTED"

    def reject():
        c["blocked"] = True
        a.update(status="PENDING_RACE_UNKNOWN", reason_code="PENDING_AUDIT_GAP_OR_CONFLICT",
                 new_entries_blocked=True)
        return a, c, False

    if (c["blocked"] or not a.get("initialized") or
            (seed_record and before.get("initialized")) or
            (not seed_record and not before.get("initialized")) or
            r.get("schema_version") != VERSION or not r.get("fingerprint") or
            r["fingerprint"] != fingerprint(r) or not r.get("event_id") or
            not r.get("source_fingerprint") or r.get("occurred_at_utc", 0) <= 0 or
            r.get("observed_at_utc", 0) < r["occurred_at_utc"] or
            r.get("data_quality") not in {"OK", "UNTRUSTED"} or
            (r.get("data_quality") == "UNTRUSTED" and
             a["status"] != "PENDING_RACE_UNKNOWN") or
            any((not seed_record and r.get(k) != before.get(k)) or r.get(k) != a.get(k)
                for k in IDENTITY) or
            r.get("state_before") != before["status"] or
            r.get("state_after") != a["status"] or
            r.get("reason_code") != a["reason_code"] or
            (not seed_record and
             r.get("effective_expires_at_utc") != before["effective_expires_at_utc"]) or
            r.get("effective_expires_at_utc") != a["effective_expires_at_utc"] or
            r.get("bars_waited_before") != before["bars_waited"] or
            r.get("bars_waited_after") != a["bars_waited"] or
            r.get("broker_event_sequence_before") != before["last_event_sequence"] or
            r.get("broker_event_sequence_after") != a["last_event_sequence"] or
            (not seed_record and before["requested_volume"] != a["requested_volume"]) or
            a["requested_volume"] != a["filled_volume"] + a["cancelled_volume"] + a["remaining_volume"]):
        return reject()
    for key in NUMERIC:
        label = {"filled_initial_risk_money": "filled_risk",
                 "remaining_risk_reservation_money": "remaining_reservation"}.get(key, key)
        if r.get(label + "_before") != before[key] or r.get(label + "_after") != a[key]:
            return reject()
    if (c["initialized"] and r["audit_sequence"] == c["last_sequence"] and
            r["fingerprint"] == c["last_fingerprint"] and r["event_id"] == c["last_event_id"]):
        return a, c, True
    if (r.get("audit_sequence", 0) <= 0 or
            (c["initialized"] and
             (r["audit_sequence"] != c["last_sequence"] + 1 or
              r.get("previous_fingerprint") != c["last_fingerprint"] or
              r["observed_at_utc"] < c["last_observed_at_utc"] or
              r["event_id"] == c["last_event_id"])) or
            (not c["initialized"] and
             (r["audit_sequence"] != 1 or r.get("previous_fingerprint") != "" or
              not seed_record))):
        return reject()
    unchanged = all(before[k] == a[k] for k in NUMERIC)
    cause = r.get("cause_kind")
    broker_same = a["last_event_sequence"] == before["last_event_sequence"]
    bars_same = a["bars_waited"] == before["bars_waited"]
    if cause == "SEED_ACCEPTED":
        valid = (not c["initialized"] and a["status"] == "WORKING" and
                 a["bars_waited"] == 0 and a["last_event_sequence"] == 0 and
                 before["requested_volume"] == 0 and a["filled_volume"] == 0 and
                 a["cancelled_volume"] == 0 and
                 a["remaining_volume"] == a["requested_volume"] and
                 a["remaining_risk_reservation_money"] == a["total_committed_risk_money"])
    elif cause == "BAR":
        valid = (unchanged and broker_same and a["bars_waited"] == before["bars_waited"] + 1 and
                 a["status"] in {before["status"], "CANCEL_REQUIRED", "PENDING_RACE_UNKNOWN"})
    elif cause in {"GUARD", "TIMER", "RESTORE", "UNKNOWN", "RECONCILE_EVIDENCE"}:
        valid = unchanged and broker_same and bars_same
        if cause in {"GUARD", "TIMER"}:
            valid = valid and a["status"] in {before["status"], "CANCEL_REQUIRED", "PENDING_RACE_UNKNOWN"}
        if cause in {"RESTORE", "UNKNOWN"}:
            valid = valid and a["status"] == "PENDING_RACE_UNKNOWN" and a["new_entries_blocked"]
        if cause == "RECONCILE_EVIDENCE":
            valid = (valid and before["status"] == "PENDING_RACE_UNKNOWN" and
                     a["status"] == "PENDING_RACE_UNKNOWN" and a["new_entries_blocked"] and
                     all(r.get(k) for k in ("broker_snapshot_id", "order_history_fingerprint",
                                            "deal_set_fingerprint")))
    elif cause == "BROKER_FILL":
        valid = (a["last_event_sequence"] == before["last_event_sequence"] + 1 and
                 a["filled_volume"] > before["filled_volume"] and
                 a["remaining_volume"] < before["remaining_volume"] and
                 a["filled_initial_risk_money"] > before["filled_initial_risk_money"] and
                 a["remaining_risk_reservation_money"] < before["remaining_risk_reservation_money"] and
                 a["cancelled_volume"] == before["cancelled_volume"] and
                 a["status"] in {"PARTIAL", "FILLED", "BREACH_REVIEW"})
    elif cause == "CANCEL_REQUEST":
        valid = (unchanged and a["last_event_sequence"] == before["last_event_sequence"] + 1 and
                 a["status"] == "CANCEL_REQUESTED")
    elif cause == "BROKER_TERMINAL":
        valid = (a["last_event_sequence"] == before["last_event_sequence"] + 1 and
                 a["remaining_volume"] == 0 and
                 a["cancelled_volume"] > before["cancelled_volume"] and
                 a["cancelled_volume"] - before["cancelled_volume"] == before["remaining_volume"] and
                 a["filled_volume"] == before["filled_volume"] and
                 a["filled_initial_risk_money"] == before["filled_initial_risk_money"] and
                 a["remaining_risk_reservation_money"] == 0 and
                 a["status"] in {"CANCELLED", "EXPIRED", "BREACH_REVIEW"})
    else:
        valid = False
    if not valid:
        return reject()
    c.update(initialized=True, last_sequence=r["audit_sequence"],
             last_fingerprint=r["fingerprint"], last_event_id=r["event_id"],
             last_observed_at_utc=r["observed_at_utc"])
    return a, c, True
