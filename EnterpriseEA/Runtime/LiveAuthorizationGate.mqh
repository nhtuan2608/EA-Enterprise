#ifndef ENTERPRISE_EA_LIVE_AUTHORIZATION_GATE_MQH
#define ENTERPRISE_EA_LIVE_AUTHORIZATION_GATE_MQH

// Pure release gate. It never sends, modifies, or cancels an order.
// Every field is supplied by an independently verified runtime/operator process.
struct EEA_LiveAuthorizationContext
  {
   bool explicit_human_approval;
   bool account_identity_confirmed;
   bool risk_policy_confirmed;
   bool broker_specs_confirmed;
   bool retained_runtime_evidence;
   bool execution_path_compiled;
   bool demo_execution_evidence;
   bool restart_reconciliation_evidence;
   bool emergency_stop_tested;
   bool rollback_tested;
   bool ai_policy_confirmed;
   bool news_policy_confirmed;
   bool limits_locked;
   bool config_backup_ready;
   bool monitoring_ready;
   bool no_unknown_state;
   bool no_open_blockers;
   bool live_account_intended;
   string authorization_id;
   string build_hash;
   string account_fingerprint;
   string candidate_id;
   string intent_id;
   string risk_policy_id;
   string config_version;
   string broker_server;
   string account_mode;
   string broker_symbol;
   long authorization_valid_until_utc;
  };

struct EEA_LiveAuthorizationDecision
  {
   bool authorized;
   string status;
   string reason_code;
   string authorization_id;
   string build_hash;
   string account_fingerprint;
   string candidate_id;
   string intent_id;
   string risk_policy_id;
   string config_version;
   string broker_server;
   string account_mode;
   string broker_symbol;
   long authorization_valid_until_utc;
  };

void EEA_LiveAuthorizationDefaults(EEA_LiveAuthorizationContext &c)
  {
   c.explicit_human_approval=false;
   c.account_identity_confirmed=false;
   c.risk_policy_confirmed=false;
   c.broker_specs_confirmed=false;
   c.retained_runtime_evidence=false;
   c.execution_path_compiled=false;
   c.demo_execution_evidence=false;
   c.restart_reconciliation_evidence=false;
   c.emergency_stop_tested=false;
   c.rollback_tested=false;
   c.ai_policy_confirmed=false;
   c.news_policy_confirmed=false;
   c.limits_locked=false;
   c.config_backup_ready=false;
   c.monitoring_ready=false;
   c.no_unknown_state=false;
   c.no_open_blockers=false;
   c.live_account_intended=false;
   c.authorization_id="";
   c.build_hash="";
   c.account_fingerprint="";
   c.candidate_id="";
   c.intent_id="";
   c.risk_policy_id="";
   c.config_version="";
   c.broker_server="";
   c.account_mode="";
   c.broker_symbol="";
   c.authorization_valid_until_utc=0;
  }

void EEA_LiveAuthorizationDecisionDefaults(EEA_LiveAuthorizationDecision &d)
  {
   d.authorized=false;
   d.status="NOT_AUTHORIZED";
   d.reason_code="LIVE_HUMAN_APPROVAL_REQUIRED";
   d.authorization_id="";
   d.build_hash="";
   d.account_fingerprint="";
   d.candidate_id="";
   d.intent_id="";
   d.risk_policy_id="";
   d.config_version="";
   d.broker_server="";
   d.account_mode="";
   d.broker_symbol="";
   d.authorization_valid_until_utc=0;
  }

bool EEA_EvaluateLiveAuthorization(const EEA_LiveAuthorizationContext &c,
                                   EEA_LiveAuthorizationDecision &d)
  {
   EEA_LiveAuthorizationDecisionDefaults(d);
   if(!c.explicit_human_approval) { d.reason_code="LIVE_HUMAN_APPROVAL_REQUIRED"; return false; }
   if(!c.account_identity_confirmed) { d.reason_code="LIVE_ACCOUNT_IDENTITY_UNCONFIRMED"; return false; }
   if(!c.risk_policy_confirmed) { d.reason_code="LIVE_RISK_POLICY_UNCONFIRMED"; return false; }
   if(!c.broker_specs_confirmed) { d.reason_code="LIVE_BROKER_SPEC_UNCONFIRMED"; return false; }
   if(!c.retained_runtime_evidence) { d.reason_code="LIVE_RUNTIME_EVIDENCE_PENDING"; return false; }
   if(!c.execution_path_compiled) { d.reason_code="LIVE_EXECUTION_PATH_UNCOMPILED"; return false; }
   if(!c.demo_execution_evidence) { d.reason_code="LIVE_DEMO_EVIDENCE_PENDING"; return false; }
   if(!c.restart_reconciliation_evidence) { d.reason_code="LIVE_RESTART_RECONCILIATION_PENDING"; return false; }
   if(!c.emergency_stop_tested) { d.reason_code="LIVE_EMERGENCY_STOP_NOT_PROVEN"; return false; }
   if(!c.rollback_tested) { d.reason_code="LIVE_GATE_ROLLBACK_NOT_PROVEN"; return false; }
   if(!c.ai_policy_confirmed) { d.reason_code="LIVE_AI_POLICY_UNCONFIRMED"; return false; }
   if(!c.news_policy_confirmed) { d.reason_code="LIVE_NEWS_POLICY_UNCONFIRMED"; return false; }
   if(!c.limits_locked) { d.reason_code="LIVE_LIMITS_NOT_LOCKED"; return false; }
   if(!c.config_backup_ready) { d.reason_code="LIVE_CONFIG_BACKUP_MISSING"; return false; }
   if(!c.monitoring_ready) { d.reason_code="LIVE_MONITORING_NOT_READY"; return false; }
   if(!c.no_unknown_state) { d.reason_code="LIVE_UNKNOWN_STATE_PRESENT"; return false; }
   if(!c.no_open_blockers) { d.reason_code="LIVE_OPEN_BLOCKERS_PRESENT"; return false; }
   if(!c.live_account_intended) { d.reason_code="LIVE_ACCOUNT_NOT_SELECTED"; return false; }
   if(c.authorization_id=="") { d.reason_code="LIVE_AUTHORIZATION_ID_MISSING"; return false; }
   if(c.build_hash=="") { d.reason_code="LIVE_BUILD_HASH_MISSING"; return false; }
   if(c.account_fingerprint=="") { d.reason_code="LIVE_ACCOUNT_FINGERPRINT_MISSING"; return false; }
   if(c.candidate_id=="") { d.reason_code="LIVE_CANDIDATE_ID_MISSING"; return false; }
   if(c.intent_id=="") { d.reason_code="LIVE_INTENT_ID_MISSING"; return false; }
   if(c.risk_policy_id=="") { d.reason_code="LIVE_RISK_POLICY_ID_MISSING"; return false; }
   if(c.config_version=="") { d.reason_code="LIVE_CONFIG_VERSION_MISSING"; return false; }
   if(c.broker_server=="" || c.account_mode=="" || c.broker_symbol=="")
     { d.reason_code="LIVE_RUNTIME_IDENTITY_MISSING"; return false; }
   if(c.authorization_valid_until_utc<=TimeGMT())
     { d.reason_code="LIVE_AUTHORIZATION_EXPIRED"; return false; }
   d.authorized=true;
   d.status="AUTHORIZED_CONTROLLED_LIVE";
   d.reason_code="LIVE_GATES_PASSED";
   d.authorization_id=c.authorization_id;
   d.build_hash=c.build_hash;
   d.account_fingerprint=c.account_fingerprint;
   d.candidate_id=c.candidate_id;
   d.intent_id=c.intent_id;
   d.risk_policy_id=c.risk_policy_id;
   d.config_version=c.config_version;
   d.broker_server=c.broker_server;
   d.account_mode=c.account_mode;
   d.broker_symbol=c.broker_symbol;
   d.authorization_valid_until_utc=c.authorization_valid_until_utc;
   return true;
  }

#endif
