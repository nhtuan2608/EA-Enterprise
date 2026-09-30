"""Reference behavior for synthetic remote-control fixtures, not MQL execution."""
from copy import deepcopy

VERSION = "remote-command-v1.0.0"
AI_VERSION = "telegram-ai-v1.0.0"
MAX_NONCE_SECONDS = 120
SCOPES = {"EA_STATUS", "RISK_SUMMARY", "MARKET_CONTEXT", "NEWS_CONTEXT", "AUDIT_SUMMARY"}
RESUME_GATES = ("account_wide_reconciled", "risk_gate_ready", "news_gate_ready",
                "broker_connected", "mt5_trade_allowed", "protective_management_ready", "evidence_fresh")


def evaluate(state, command, evidence, now):
    proposed = deepcopy(state)
    def reject(reason):
        return proposed, "REJECTED", reason

    if not state["initialized"] or not state["account_id"] or not state["config_version"] or state["state_version"] <= 0:
        return reject("DURABLE_REMOTE_STATE_REQUIRED")
    if (command.get("schema_version") != VERSION or not command.get("command_id") or
            command.get("role") != "OPERATOR" or not command.get("chat_id") or not command.get("user_id") or
            not all(command.get(k) is True for k in
                    ("private_chat_attested", "sender_authenticated", "source_authenticated")) or
            command.get("account_id") != state["account_id"] or
            command.get("config_version") != state["config_version"] or
            command.get("telegram_update_id", 0) <= 0 or command.get("gateway_sequence", 0) <= 0 or
            command.get("issued_at_utc", 0) <= 0 or
            command.get("expires_at_utc", 0) <= command.get("issued_at_utc", 0) or
            not command["issued_at_utc"] <= now <= command["expires_at_utc"]):
        return reject("REMOTE_AUTH_IDENTITY_OR_TTL_INVALID")
    if (command["gateway_sequence"] == state["last_gateway_sequence"] and
            command["command_id"] == state["last_command_id"] and
            command["telegram_update_id"] == state["last_telegram_update_id"]):
        return proposed, "DUPLICATE_IGNORED", "REMOTE_COMMAND_ALREADY_COMMITTED"
    if (command["gateway_sequence"] <= state["last_gateway_sequence"] or
            command["telegram_update_id"] == state["last_telegram_update_id"] or
            command["command_id"] == state["last_command_id"]):
        return reject("REMOTE_REPLAY_OR_SEQUENCE_REGRESSION")
    if command.get("expected_state_version") != state["state_version"]:
        return reject("REMOTE_STATE_VERSION_MISMATCH")

    action = command.get("action")
    if action == "PAUSE_ENTRIES":
        proposed["operator_paused"] = True
        _clear_pending(proposed)
        reason = "ENTRIES_PAUSE_PROPOSED"
    elif action == "REQUEST_RESUME":
        nonce_expiry = command.get("nonce_expires_at_utc", 0)
        if (not state["operator_paused"] or not command.get("confirmation_nonce") or
                not now < nonce_expiry <= command["expires_at_utc"] or
                nonce_expiry - now > MAX_NONCE_SECONDS or
                command["confirmation_nonce"] == state["pending_nonce"]):
            return reject("RESUME_CHALLENGE_INVALID")
        proposed.update(pending_nonce=command["confirmation_nonce"],
                        pending_chat_id=command["chat_id"], pending_user_id=command["user_id"],
                        pending_expires_at_utc=nonce_expiry)
        reason = "RESUME_CONFIRMATION_PENDING"
    elif action == "CONFIRM_RESUME":
        if (not state["operator_paused"] or not state["pending_nonce"] or
                command.get("confirmation_nonce") != state["pending_nonce"] or
                command["chat_id"] != state["pending_chat_id"] or
                command["user_id"] != state["pending_user_id"] or
                now > state["pending_expires_at_utc"]):
            return reject("RESUME_CONFIRMATION_INVALID_OR_EXPIRED")
        if not all(evidence.get(k) is True for k in RESUME_GATES):
            return reject("RESUME_SAFETY_EVIDENCE_NOT_READY")
        proposed["operator_paused"] = False
        _clear_pending(proposed)
        reason = "RESUME_PROPOSED_AFTER_SAFETY_CHECKS"
    else:
        return reject("REMOTE_ACTION_NOT_ALLOWED")

    proposed.update(state_version=state["state_version"] + 1,
                    last_gateway_sequence=command["gateway_sequence"],
                    last_telegram_update_id=command["telegram_update_id"],
                    last_command_id=command["command_id"])
    return proposed, "VALIDATED_PENDING_COMMIT", reason


def _clear_pending(state):
    state.update(pending_nonce="", pending_chat_id="", pending_user_id="", pending_expires_at_utc=0)


def ai_reply_acceptable(request, reply, now):
    """Transport validation only: an accepted reply never changes EA state."""
    return (request.get("schema_version") == AI_VERSION and reply.get("schema_version") == AI_VERSION and
            request.get("request_type") == "ASK_AI" and
            0 < len(request.get("question", "")) <= 1000 and
            0 < len(request.get("context_scope", [])) <= 5 and
            set(request["context_scope"]) <= SCOPES and
            0 < request.get("deadline_at_utc", 0) - request.get("created_at_utc", 0) <= 30 and
            now <= request["deadline_at_utc"] and
            reply.get("request_id") == request.get("request_id") and
            reply.get("chat_id") == request.get("chat_id") and
            reply.get("response_status") in {"OK", "TIMEOUT", "AI_OFFLINE", "MALFORMED", "CONTEXT_UNAVAILABLE"} and
            reply.get("created_at_utc", 0) <= reply.get("valid_until_utc", 0) and
            now <= reply.get("valid_until_utc", 0) and
            reply.get("context_captured_at_utc", 0) <= reply.get("created_at_utc", 0) and
            len(reply.get("answer", "")) <= 4000 and
            (reply["response_status"] != "OK" or
             (bool(reply["answer"]) and bool(reply.get("evidence_refs")) and
              set(reply["evidence_refs"]) <= set(request.get("context_snapshot_ids", [])))))
