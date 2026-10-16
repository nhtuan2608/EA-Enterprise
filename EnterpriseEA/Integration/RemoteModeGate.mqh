#ifndef ENTERPRISE_EA_REMOTE_MODE_GATE_MQH
#define ENTERPRISE_EA_REMOTE_MODE_GATE_MQH

// Pure offline command validator. A caller must authenticate the Telegram
// update, attest the evidence, durably persist next, then adopt it and reply.
// No Telegram, file, terminal or order APIs are used here.
#define EEA_REMOTE_COMMAND_VERSION "remote-command-v1.0.0"
#define EEA_REMOTE_MAX_NONCE_SECONDS 120
// Telegram live-session authorization (17/10/2026): the only durations the panel offers.
#define EEA_REMOTE_SESSION_24H_SECONDS 86400
#define EEA_REMOTE_SESSION_7D_SECONDS  (7*86400)

struct EEA_RemoteModeState
  {
   bool initialized;
   bool operator_paused;
   string account_id;
   string config_version;
   long state_version;
   long last_gateway_sequence;
   long last_telegram_update_id;
   string last_command_id;
   string pending_nonce;
   string pending_chat_id;
   string pending_user_id;
   datetime pending_expires_at_utc;
   string pending_action;          // RESUME | SESSION_SIGN ("" in files written before 17/10/2026 = RESUME)
   long pending_session_seconds;   // SESSION_SIGN only
  };

struct EEA_RemoteCommand
  {
   string schema_version;
   string command_id;
   string action; // PAUSE_ENTRIES | REQUEST_RESUME | CONFIRM_RESUME |
                  // REQUEST_SESSION_SIGN | CONFIRM_SESSION_SIGN | REVOKE_SESSION
   string role;   // OPERATOR only for state changes
   string chat_id;
   string user_id;
   long telegram_update_id;
   long gateway_sequence; // Monotonic durable local sequence, not Telegram update_id
   string account_id;
   string config_version;
   long expected_state_version;
   datetime issued_at_utc;
   datetime expires_at_utc;
   string confirmation_nonce;
   datetime nonce_expires_at_utc;
   long session_seconds;  // REQUEST_SESSION_SIGN: 86400 or 7*86400
   bool private_chat_attested;
   bool sender_authenticated;
   bool source_authenticated;
  };

struct EEA_RemoteResumeEvidence
  {
   bool account_wide_reconciled;
   bool risk_gate_ready;
   bool news_gate_ready;
   bool broker_connected;
   bool mt5_trade_allowed;
   bool protective_management_ready;
   bool evidence_fresh;
   bool session_remote_sign_allowed;   // InpSessionRemoteSignAllowed; revoke never needs it
  };

struct EEA_RemoteModeDecision
  {
   string status; // REJECTED | DUPLICATE_IGNORED | VALIDATED_PENDING_COMMIT
   string reason_code;
   bool state_change_proposed;
   bool entries_may_be_considered_after_commit;
   long session_sign_seconds;   // > 0: sign a live session of this length after the commit
   bool session_revoke;         // revoke the live session after the commit
  };

void EEA_RemoteModeDefaults(EEA_RemoteModeState &s)
  {
   s.initialized=false;
   s.operator_paused=true;
   s.account_id="";
   s.config_version="";
   s.state_version=0;
   s.last_gateway_sequence=0;
   s.last_telegram_update_id=0;
   s.last_command_id="";
   s.pending_nonce="";
   s.pending_chat_id="";
   s.pending_user_id="";
   s.pending_expires_at_utc=0;
   s.pending_action="";
   s.pending_session_seconds=0;
  }

void EEA_RemoteModeDecisionDefaults(EEA_RemoteModeDecision &d)
  {
   d.status="REJECTED";
   d.reason_code="REMOTE_COMMAND_INVALID";
   d.state_change_proposed=false;
   d.entries_may_be_considered_after_commit=false;
   d.session_sign_seconds=0;
   d.session_revoke=false;
  }

void EEA_RemoteClearPending(EEA_RemoteModeState &s)
  {
   s.pending_nonce="";
   s.pending_chat_id="";
   s.pending_user_id="";
   s.pending_expires_at_utc=0;
   s.pending_action="";
   s.pending_session_seconds=0;
  }

// A one-time code for REQUEST_RESUME and REQUEST_SESSION_SIGN: new, short-lived, inside the command TTL.
bool EEA_RemoteChallengeValid(const EEA_RemoteModeState &current,const EEA_RemoteCommand &c,const datetime now_utc)
  {
   return c.confirmation_nonce!="" && c.nonce_expires_at_utc>now_utc &&
          c.nonce_expires_at_utc<=c.expires_at_utc &&
          c.confirmation_nonce!=current.pending_nonce &&
          (c.nonce_expires_at_utc-now_utc)<=EEA_REMOTE_MAX_NONCE_SECONDS;
  }

// The code answers the pending challenge of this kind, from the same chat and user, in time.
bool EEA_RemoteConfirmationMatches(const EEA_RemoteModeState &current,const EEA_RemoteCommand &c,
                                   const string pending_action,const datetime now_utc)
  {
   const string action=(current.pending_action=="" ? "RESUME" : current.pending_action);
   return current.pending_nonce!="" && action==pending_action &&
          c.confirmation_nonce==current.pending_nonce &&
          c.chat_id==current.pending_chat_id && c.user_id==current.pending_user_id &&
          now_utc<=current.pending_expires_at_utc;
  }

bool EEA_RemoteResumeReady(const EEA_RemoteResumeEvidence &e)
  {
   return e.account_wide_reconciled && e.risk_gate_ready &&
          e.news_gate_ready && e.broker_connected && e.mt5_trade_allowed &&
          e.protective_management_ready && e.evidence_fresh;
  }

bool EEA_EvaluateRemoteModeCommand(const EEA_RemoteModeState &current,
                                   const EEA_RemoteCommand &c,
                                   const EEA_RemoteResumeEvidence &e,
                                   const datetime now_utc,
                                   EEA_RemoteModeState &next,
                                   EEA_RemoteModeDecision &d)
  {
   next=current;
   EEA_RemoteModeDecisionDefaults(d);
   if(!current.initialized || current.account_id=="" ||
      current.config_version=="" || current.state_version<=0)
     { d.reason_code="DURABLE_REMOTE_STATE_REQUIRED"; return false; }
   if(c.schema_version!=EEA_REMOTE_COMMAND_VERSION || c.command_id=="" ||
      c.role!="OPERATOR" || c.chat_id=="" || c.user_id=="" ||
      !c.private_chat_attested || !c.sender_authenticated ||
      !c.source_authenticated || c.account_id!=current.account_id ||
      c.config_version!=current.config_version || c.telegram_update_id<=0 ||
      c.gateway_sequence<=0 || c.issued_at_utc<=0 ||
      c.expires_at_utc<=c.issued_at_utc || now_utc<c.issued_at_utc ||
      now_utc>c.expires_at_utc)
     { d.reason_code="REMOTE_AUTH_IDENTITY_OR_TTL_INVALID"; return false; }
   if(c.gateway_sequence==current.last_gateway_sequence &&
      c.command_id==current.last_command_id &&
      c.telegram_update_id==current.last_telegram_update_id)
     {
      d.status="DUPLICATE_IGNORED";
      d.reason_code="REMOTE_COMMAND_ALREADY_COMMITTED";
      return true;
     }
   if(c.gateway_sequence<=current.last_gateway_sequence ||
      c.telegram_update_id==current.last_telegram_update_id ||
      c.command_id==current.last_command_id)
     { d.reason_code="REMOTE_REPLAY_OR_SEQUENCE_REGRESSION"; return false; }
   if(c.expected_state_version!=current.state_version)
     { d.reason_code="REMOTE_STATE_VERSION_MISMATCH"; return false; }

   if(c.action=="PAUSE_ENTRIES")
     {
      next.operator_paused=true;
      EEA_RemoteClearPending(next);
      d.reason_code="ENTRIES_PAUSE_PROPOSED";
     }
   else if(c.action=="REQUEST_RESUME")
     {
      if(!current.operator_paused || !EEA_RemoteChallengeValid(current,c,now_utc))
        { d.reason_code="RESUME_CHALLENGE_INVALID"; return false; }
      next.pending_nonce=c.confirmation_nonce;
      next.pending_chat_id=c.chat_id;
      next.pending_user_id=c.user_id;
      next.pending_expires_at_utc=c.nonce_expires_at_utc;
      next.pending_action="RESUME";
      next.pending_session_seconds=0;
      d.reason_code="RESUME_CONFIRMATION_PENDING";
     }
   else if(c.action=="CONFIRM_RESUME")
     {
      if(!current.operator_paused || !EEA_RemoteConfirmationMatches(current,c,"RESUME",now_utc))
        { d.reason_code="RESUME_CONFIRMATION_INVALID_OR_EXPIRED"; return false; }
      if(!EEA_RemoteResumeReady(e))
        { d.reason_code="RESUME_SAFETY_EVIDENCE_NOT_READY"; return false; }
      next.operator_paused=false;
      EEA_RemoteClearPending(next);
      d.reason_code="RESUME_PROPOSED_AFTER_SAFETY_CHECKS";
      d.entries_may_be_considered_after_commit=true;
     }
   // Live-session authorization from Telegram. The gate only checks the challenge; the EA
   // signs through the same EEA_LiveSessionSign checks as the panel after the commit.
   else if(c.action=="REQUEST_SESSION_SIGN")
     {
      if(!e.session_remote_sign_allowed)
        { d.reason_code="SESSION_REMOTE_SIGN_DISABLED"; return false; }
      if(c.session_seconds!=EEA_REMOTE_SESSION_24H_SECONDS && c.session_seconds!=EEA_REMOTE_SESSION_7D_SECONDS)
        { d.reason_code="SESSION_DURATION_INVALID"; return false; }
      if(!EEA_RemoteChallengeValid(current,c,now_utc))
        { d.reason_code="SESSION_CHALLENGE_INVALID"; return false; }
      next.pending_nonce=c.confirmation_nonce;
      next.pending_chat_id=c.chat_id;
      next.pending_user_id=c.user_id;
      next.pending_expires_at_utc=c.nonce_expires_at_utc;
      next.pending_action="SESSION_SIGN";
      next.pending_session_seconds=c.session_seconds;
      d.reason_code="SESSION_SIGN_CONFIRMATION_PENDING";
     }
   else if(c.action=="CONFIRM_SESSION_SIGN")
     {
      if(!e.session_remote_sign_allowed)
        { d.reason_code="SESSION_REMOTE_SIGN_DISABLED"; return false; }
      if(!EEA_RemoteConfirmationMatches(current,c,"SESSION_SIGN",now_utc))
        { d.reason_code="SESSION_CONFIRMATION_INVALID_OR_EXPIRED"; return false; }
      d.session_sign_seconds=current.pending_session_seconds;
      EEA_RemoteClearPending(next);
      d.reason_code="SESSION_SIGN_PROPOSED";
     }
   else if(c.action=="REVOKE_SESSION")
     {
      // Stopping new entries is always allowed, like /pause.
      EEA_RemoteClearPending(next);
      d.session_revoke=true;
      d.reason_code="SESSION_REVOKE_PROPOSED";
     }
   else
     { d.reason_code="REMOTE_ACTION_NOT_ALLOWED"; return false; }

   next.state_version=current.state_version+1;
   next.last_gateway_sequence=c.gateway_sequence;
   next.last_telegram_update_id=c.telegram_update_id;
   next.last_command_id=c.command_id;
   d.status="VALIDATED_PENDING_COMMIT";
   d.state_change_proposed=true;
   return true;
  }

#endif
