"""Pure oracle for the paperless controlled-live release gate."""


_REQUIRED_GATES = (
    ("explicit_human_approval", "LIVE_HUMAN_APPROVAL_REQUIRED"),
    ("account_identity_confirmed", "LIVE_ACCOUNT_IDENTITY_UNCONFIRMED"),
    ("risk_policy_confirmed", "LIVE_RISK_POLICY_UNCONFIRMED"),
    ("broker_specs_confirmed", "LIVE_BROKER_SPEC_UNCONFIRMED"),
    ("retained_runtime_evidence", "LIVE_RUNTIME_EVIDENCE_PENDING"),
    ("execution_path_compiled", "LIVE_EXECUTION_PATH_UNCOMPILED"),
    ("demo_execution_evidence", "LIVE_DEMO_EVIDENCE_PENDING"),
    ("restart_reconciliation_evidence", "LIVE_RESTART_RECONCILIATION_PENDING"),
    ("emergency_stop_tested", "LIVE_EMERGENCY_STOP_NOT_PROVEN"),
    ("rollback_tested", "LIVE_GATE_ROLLBACK_NOT_PROVEN"),
    ("ai_policy_confirmed", "LIVE_AI_POLICY_UNCONFIRMED"),
    ("news_policy_confirmed", "LIVE_NEWS_POLICY_UNCONFIRMED"),
    ("limits_locked", "LIVE_LIMITS_NOT_LOCKED"),
    ("config_backup_ready", "LIVE_CONFIG_BACKUP_MISSING"),
    ("monitoring_ready", "LIVE_MONITORING_NOT_READY"),
    ("no_unknown_state", "LIVE_UNKNOWN_STATE_PRESENT"),
    ("no_open_blockers", "LIVE_OPEN_BLOCKERS_PRESENT"),
    ("live_account_intended", "LIVE_ACCOUNT_NOT_SELECTED"),
)


def context(**overrides):
    result = {
        "explicit_human_approval": False,
        "account_identity_confirmed": False,
        "risk_policy_confirmed": False,
        "broker_specs_confirmed": False,
        "retained_runtime_evidence": False,
        "execution_path_compiled": False,
        "demo_execution_evidence": False,
        "restart_reconciliation_evidence": False,
        "emergency_stop_tested": False,
        "rollback_tested": False,
        "ai_policy_confirmed": False,
        "news_policy_confirmed": False,
        "limits_locked": False,
        "config_backup_ready": False,
        "monitoring_ready": False,
        "no_unknown_state": False,
        "no_open_blockers": False,
        "live_account_intended": False,
        "authorization_id": "",
        "build_hash": "",
        "config_version": "",
        "broker_server": "",
        "account_mode": "",
        "broker_symbol": "",
    }
    result.update(overrides)
    return result


def evaluate_live_authorization(value):
    for field, reason in _REQUIRED_GATES:
        if not value.get(field, False):
            return {"authorized": False, "status": "NOT_AUTHORIZED", "reason_code": reason}
    if not value.get("authorization_id"):
        return {"authorized": False, "status": "NOT_AUTHORIZED", "reason_code": "LIVE_AUTHORIZATION_ID_MISSING"}
    if not value.get("build_hash"):
        return {"authorized": False, "status": "NOT_AUTHORIZED", "reason_code": "LIVE_BUILD_HASH_MISSING"}
    if not value.get("config_version"):
        return {"authorized": False, "status": "NOT_AUTHORIZED", "reason_code": "LIVE_CONFIG_VERSION_MISSING"}
    if not value.get("broker_server") or not value.get("account_mode") or not value.get("broker_symbol"):
        return {"authorized": False, "status": "NOT_AUTHORIZED", "reason_code": "LIVE_RUNTIME_IDENTITY_MISSING"}
    return {"authorized": True, "status": "AUTHORIZED_CONTROLLED_LIVE", "reason_code": "LIVE_GATES_PASSED"}
