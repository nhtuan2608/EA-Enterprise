"""Oracle for execution preflight, idempotency and result reconciliation."""

import math


def _reject(reason):
    return {
        "confirmation_state": "NOT_SENT",
        "reason_code": reason,
        "request_sent": False,
    }


def _aligned(value, step):
    if not math.isfinite(value) or not math.isfinite(step) or step <= 0:
        return False
    rounded = round(value / step)
    return abs(value - rounded * step) <= max(step * 1e-8, 1e-12)


def _finite_intent(intent):
    return all(math.isfinite(float(intent.get(field, 0.0)))
               for field in ("volume", "price", "sl", "tp"))

def preflight(intent, context):
    if not context.get("execution_enabled", False):
        return _reject("EXECUTION_DISABLED")

    for field, reason in (
        ("intent_id", "INTENT_ID_MISSING"),
        ("correlation_id", "CORRELATION_ID_MISSING"),
        ("idempotency_key", "IDEMPOTENCY_KEY_MISSING"),
    ):
        if not intent.get(field):
            return _reject(reason)

    if intent.get("schema_version") != "0.1.0":
        return _reject("INTENT_SCHEMA_INVALID")
    if not intent.get("config_version"):
        return _reject("CONFIG_VERSION_MISSING")
    if not context.get("config_version"):
        return _reject("CONFIG_VERSION_MISSING")
    if context.get("config_version") != intent.get("config_version"):
        return _reject("CONFIG_VERSION_MISMATCH")

    if context.get("runtime_state") != "OBSERVING":
        return _reject("EXECUTION_STATE_INVALID")
    if not context.get("reconciliation_fresh", True):
        return _reject("RECONCILIATION_STALE")

    if not context.get("account_snapshot_id") or context.get("account_observed_at_utc", 0) <= 0:
        return _reject("ACCOUNT_SNAPSHOT_INVALID")
    if context.get("account_schema_version") != "runtime-evidence-v0.1.0":
        return _reject("ACCOUNT_SNAPSHOT_INVALID")
    if not context.get("reconciliation_snapshot_id"):
        return _reject("RECONCILIATION_STALE")
    if context.get("reconciliation_schema_version") != "runtime-evidence-v0.1.0":
        return _reject("RECONCILIATION_STALE")
    now = context.get("now_utc", 0)
    if (now <= 0 or context.get("account_valid_until_utc", 0) <= now or
            context.get("account_observed_at_utc", 0) > now or
            context.get("reconciliation_valid_until_utc", 0) <= now or
            context.get("reconciliation_observed_at_utc", 0) <= 0 or
            context.get("reconciliation_observed_at_utc", 0) > now):
        return _reject("RECONCILIATION_STALE")
    if (context.get("reconciliation_account_fingerprint") != context.get("account_fingerprint") or
            context.get("reconciliation_broker_server") != context.get("broker_server")):
        return _reject("ACCOUNT_IDENTITY_MISMATCH")
    if (not context.get("positions_complete", False) or
            not context.get("orders_complete", False) or
            not context.get("deals_complete", False) or
            not context.get("history_orders_complete", False)):
        return _reject("RECONCILIATION_STALE")

    if not intent.get("account_fingerprint") or not intent.get("broker_server"):
        return _reject("ACCOUNT_IDENTITY_MISSING")
    if context.get("account_fingerprint") != intent.get("account_fingerprint") or \
       context.get("broker_server") != intent.get("broker_server"):
        return _reject("ACCOUNT_IDENTITY_MISMATCH")

    for field in ("canonical_symbol", "broker_symbol"):
        if not intent.get(field) or not context.get(field):
            return _reject("SYMBOL_BINDING_MISSING")
    if not intent.get("symbol_fingerprint") or not context.get("symbol_fingerprint"):
        return _reject("SYMBOL_FINGERPRINT_MISSING")
    if context.get("canonical_symbol") != intent.get("canonical_symbol"):
        return _reject("CANONICAL_SYMBOL_MISMATCH")
    if context.get("broker_symbol") != intent.get("broker_symbol"):
        return _reject("BROKER_SYMBOL_MISMATCH")
    if context.get("symbol_fingerprint") != intent.get("symbol_fingerprint"):
        return _reject("SYMBOL_FINGERPRINT_MISMATCH")

    if not context.get("symbol_spec_valid", True):
        return _reject("SYMBOL_SPEC_INVALID")
    if not context.get("symbol_snapshot_valid", True):
        return _reject("BROKER_SYMBOL_MISMATCH")

    if context.get("trade_mode") in ("DISABLED", "CLOSE_ONLY", "0", "3"):
        return _reject("SYMBOL_SPEC_INVALID")
    if not _finite_intent(intent):
        return _reject("EXECUTION_CONTRACT_INVALID")

    valid_actions = {"SUBMIT_MARKET", "SUBMIT_PENDING", "MODIFY_PROTECTIVE", "CANCEL_PENDING", 0, 1, 2, 3}
    valid_order_types = {"BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP",
                         "BUY_STOP_LIMIT", "SELL_STOP_LIMIT"}
    if (intent.get("action") not in valid_actions or
            (intent.get("order_type") not in valid_order_types and not
             (isinstance(intent.get("order_type"), int) and 0 <= intent.get("order_type") <= 7))):
        return _reject("EXECUTION_CONTRACT_INVALID")

    volume_min = context.get("volume_min", 0.0)
    volume_max = context.get("volume_max", 0.0)
    volume_step = context.get("volume_step", 0.0)
    spec_values = (context.get("point", 0.0), context.get("tick_size", 0.0),
                   context.get("tick_value", 0.0), context.get("contract_size", 0.0),
                   volume_min, volume_max, volume_step)
    if (not all(math.isfinite(float(value)) for value in spec_values) or
            volume_min <= 0 or volume_max < volume_min or volume_step <= 0):
        return _reject("SYMBOL_SPEC_INVALID")
    if (context.get("digits", -1) < 0 or context.get("point") <= 0 or
            context.get("tick_value") <= 0 or context.get("contract_size") <= 0 or
            context.get("stops_level_points", -1) < 0 or
            context.get("freeze_level_points", -1) < 0 or
            not context.get("base_currency") or not context.get("profit_currency") or
            not context.get("margin_currency")):
        return _reject("SYMBOL_SPEC_INVALID")
    if intent.get("action") in ("SUBMIT_MARKET", "SUBMIT_PENDING", 0, 1):
        if intent.get("volume") < volume_min or intent.get("volume") > volume_max:
            return _reject("SYMBOL_SPEC_INVALID")
        if not _aligned(intent.get("volume") - volume_min, volume_step):
            return _reject("VOLUME_STEP_INVALID")
        if intent.get("action") in ("SUBMIT_PENDING", 1) and intent.get("price", 0.0) <= 0.0:
            return _reject("PRICE_GEOMETRY_INVALID")

    tick_size = context.get("tick_size", 0.0)
    if not math.isfinite(float(tick_size)) or tick_size <= 0:
        return _reject("SYMBOL_SPEC_INVALID")
    for field in ("price", "sl", "tp"):
        value = intent.get(field, 0.0)
        if value != 0.0 and not _aligned(value, tick_size):
            return _reject("PRICE_GEOMETRY_INVALID")

    filling_mode = intent.get("filling_mode", 0)
    supported_filling = context.get("supported_filling_modes", [0, 1, 2])
    if filling_mode not in supported_filling:
        return _reject("SYMBOL_FILLING_UNSUPPORTED")
    return {
        "confirmation_state": "PREFLIGHT_ACCEPTED",
        "reason_code": "OK",
        "request_sent": False,
    }

def idempotency_decision(state, key):
    if not key:
        return {"accepted": False, "reason_code": "IDEMPOTENCY_KEY_MISSING"}
    accepted_keys = state.get("accepted_keys", [])
    if key in accepted_keys:
        return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"}
    return {"accepted": True, "reason_code": "OK"}

def idempotency_decision_scan(log_content, key, max_size=1048576, markers=None, index_ready=True):
    """Mirror of EEA_ExecutionIsDuplicateIdempotency: marker index first, then the log.

    Until the one-time migration built the index, every check fails closed. Once ready,
    the index is authoritative and a log above max_size no longer blocks requests.
    """
    if not key:
        return {"accepted": False, "reason_code": "IDEMPOTENCY_KEY_MISSING"}
    if not index_ready:
        return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"} # Fail closed
    if markers is not None and key in markers:
        return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"}
    if log_content is None:
        return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"} # Fail closed
    if len(log_content) > max_size:
        return {"accepted": True, "reason_code": "OK"}
    for line in log_content.splitlines():
        if f'"idempotency_key":"{key}"' in line or f'"idempotency_key": "{key}"' in line:
            return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"}
    return {"accepted": True, "reason_code": "OK"}

def apply_result(state, result):
    if result.get("request_sent", False):
        retcode = str(result.get("request_retcode", ""))
        if not retcode:
            return {
                "confirmation_state": "REJECTED",
                "reason_code": "REQUEST_RETCODE_MISSING",
                "request_sent": True,
            }
        if retcode not in ("DONE", "10009"):
            action = result.get("request_action", "SUBMIT_MARKET")
            prefix = {
                "MODIFY_PROTECTIVE": "MODIFY_FAILED_",
                "CANCEL_PENDING": "CANCEL_FAILED_",
            }.get(action, "ORDER_SEND_FAILED_")
            return {
                "confirmation_state": "REJECTED",
                "reason_code": prefix + retcode,
                "request_sent": True,
            }
        if not result.get("broker_confirmed", False):
            return {
                "confirmation_state": "EXECUTION_UNKNOWN",
                "reason_code": "RECONCILIATION_PENDING_UNKNOWN",
                "request_sent": True
            }
    return {
        "confirmation_state": result.get("confirmation_state", "NOT_SENT"),
        "reason_code": result.get("reason_code", "OK"),
        "request_sent": result.get("request_sent", False)
    }

def reconcile_result(result, snapshot, request_ticket, request_action, intent_fields, request_ticket_kind="ORDER"):
    if result.get("confirmation_state") == "CONFIRMED":
        return result

    deals = snapshot.get("deals", [])
    orders = snapshot.get("orders", [])
    positions = snapshot.get("positions", [])

    if request_action in ("SUBMIT_MARKET", "SUBMIT_PENDING"):
        found = False
        if request_ticket_kind == "DEAL":
            found = any(d.get("deal_ticket") == request_ticket or d.get("order_ticket") == request_ticket for d in deals)
        elif request_ticket_kind == "POSITION":
            found = any(p.get("ticket") == request_ticket for p in positions)
        else:
            order_found = any(o.get("ticket") == request_ticket for o in orders)
            deal_found = any(d.get("order_ticket") == request_ticket for d in deals)
            found = order_found or deal_found
        
        if found:
            result["confirmation_state"] = "CONFIRMED"
            result["reason_code"] = "OK"
        else:
            result["confirmation_state"] = "EXECUTION_UNKNOWN"
            result["reason_code"] = "EVIDENCE_MISSING"

    elif request_action == "CANCEL_PENDING":
        order_found = any(o.get("ticket") == request_ticket for o in orders)
        deal_found = any(d.get("order_ticket") == request_ticket for d in deals)
        history_orders = snapshot.get("history_orders", [])
        hist_order_found = any(o.get("ticket") == request_ticket for o in history_orders)
        
        if not order_found and (deal_found or hist_order_found):
            result["confirmation_state"] = "CONFIRMED"
            result["reason_code"] = "OK"
        else:
            result["confirmation_state"] = "EXECUTION_UNKNOWN"
            result["reason_code"] = "EVIDENCE_MISSING_OR_ACTIVE"

    elif request_action == "MODIFY_PROTECTIVE":
        sl = intent_fields.get("sl")
        tp = intent_fields.get("tp")
        matched = False
        if request_ticket_kind == "POSITION":
            pos = next((p for p in positions if p.get("ticket") == request_ticket), None)
            if pos and _close(pos.get("sl"), sl) and _close(pos.get("tp"), tp):
                matched = True
        else:
            order = next((o for o in orders if o.get("ticket") == request_ticket), None)
            if order and _close(order.get("sl"), sl) and _close(order.get("tp"), tp):
                matched = True
            else:
                pos = next((p for p in positions if p.get("ticket") == request_ticket), None)
                if pos and _close(pos.get("sl"), sl) and _close(pos.get("tp"), tp):
                    matched = True
        
        if matched:
            result["confirmation_state"] = "CONFIRMED"
            result["reason_code"] = "OK"
        else:
            result["confirmation_state"] = "EXECUTION_UNKNOWN"
            result["reason_code"] = "MODIFICATION_NOT_REFLECTED"
            
    return result

def _close(a, b):
    import math
    if a is None or b is None: return False
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)

def intent():
    return {
        "schema_version": "0.1.0",
        "intent_id": "intent-001",
        "correlation_id": "corr-001",
        "idempotency_key": "idem-001",
        "config_version": "cfg-1.0.0",
        "account_fingerprint": "acc-fp-001",
        "broker_server": "DemoServer",
        "canonical_symbol": "EURUSD",
        "broker_symbol": "EURUSD.m",
        "symbol_fingerprint": "sym-fp-001",
        "action": "SUBMIT_MARKET",
        "order_type": "BUY",
        "volume": 0.1,
        "price": 0.0,
        "sl": 1.0800,
        "tp": 1.1000,
        "ticket": 0,
        "position_ticket": 0,
        "expiration": 0,
        "magic": 888888,
        "deviation": 20,
        "filling_mode": 0,
        "request_ticket_kind": "ORDER"
    }

def context(execution_enabled=False, reconciliation_fresh=True, account_fingerprint="acc-fp-001", broker_server="DemoServer", symbol_spec_valid=True, supported_filling_modes=None):
    if supported_filling_modes is None:
        supported_filling_modes = [0, 1, 2]
    return {
        "execution_enabled": execution_enabled,
        "reconciliation_fresh": reconciliation_fresh,
        "account_fingerprint": account_fingerprint,
        "broker_server": broker_server,
        "canonical_symbol": "EURUSD",
        "broker_symbol": "EURUSD.m",
        "symbol_spec_valid": symbol_spec_valid,
        "supported_filling_modes": supported_filling_modes,
        "config_version": "cfg-1.0.0",
        "account_schema_version": "runtime-evidence-v0.1.0",
        "reconciliation_schema_version": "runtime-evidence-v0.1.0",
        "reconciliation_account_fingerprint": account_fingerprint,
        "reconciliation_broker_server": broker_server,
        "symbol_fingerprint": "sym-fp-001",
        "symbol_snapshot_valid": True,
        "runtime_state": "OBSERVING",
        "account_snapshot_id": "acc-snap-001",
        "reconciliation_snapshot_id": "recon-snap-001",
        "account_observed_at_utc": 900,
        "account_valid_until_utc": 2000,
        "reconciliation_observed_at_utc": 900,
        "reconciliation_valid_until_utc": 2000,
        "now_utc": 1000,
        "positions_complete": True,
        "orders_complete": True,
        "deals_complete": True,
        "history_orders_complete": True,
        "volume_min": 0.01,
        "volume_max": 500.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "point": 0.00001,
        "tick_value": 1.0,
        "contract_size": 100000.0,
        "digits": 5,
        "stops_level_points": 0,
        "freeze_level_points": 0,
        "base_currency": "EUR",
        "profit_currency": "USD",
        "margin_currency": "EUR",
        "trade_mode": "FULL",
    }

def mutate(base, path, value):
    from copy import deepcopy
    copy = deepcopy(base)
    parts = path.split(".")
    target = copy
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = value
    elif value == "__DELETE__":
        del target[last]
    else:
        target[last] = value
    return copy
