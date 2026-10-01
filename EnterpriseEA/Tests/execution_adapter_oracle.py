"""Oracle for execution preflight, idempotency and result reconciliation."""

def preflight(intent, context):
    if not context.get("execution_enabled", False):
        return {
            "confirmation_state": "NOT_SENT",
            "reason_code": "EXECUTION_DISABLED",
            "request_sent": False
        }
    if not context.get("reconciliation_fresh", True):
        return {
            "confirmation_state": "NOT_SENT",
            "reason_code": "RECONCILIATION_STALE",
            "request_sent": False
        }
    if context.get("account_fingerprint") != intent.get("account_fingerprint") or \
       context.get("broker_server") != intent.get("broker_server"):
        return {
            "confirmation_state": "NOT_SENT",
            "reason_code": "ACCOUNT_IDENTITY_MISMATCH",
            "request_sent": False
        }
    if not context.get("symbol_spec_valid", True):
        return {
            "confirmation_state": "NOT_SENT",
            "reason_code": "SYMBOL_SPEC_INVALID",
            "request_sent": False
        }
    return {
        "confirmation_state": "PREFLIGHT_ACCEPTED",
        "reason_code": "OK",
        "request_sent": False
    }

def idempotency_decision(state, key):
    accepted_keys = state.get("accepted_keys", [])
    if key in accepted_keys:
        return {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"}
    return {"accepted": True, "reason_code": "OK"}

def apply_result(state, result):
    if result.get("request_sent", False) and not result.get("broker_confirmed", False):
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
        "expiration": 0
    }

def context(execution_enabled=False, reconciliation_fresh=True, account_fingerprint="acc-fp-001", broker_server="DemoServer", symbol_spec_valid=True):
    return {
        "execution_enabled": execution_enabled,
        "reconciliation_fresh": reconciliation_fresh,
        "account_fingerprint": account_fingerprint,
        "broker_server": broker_server,
        "canonical_symbol": "EURUSD",
        "broker_symbol": "EURUSD.m",
        "symbol_spec_valid": symbol_spec_valid
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
