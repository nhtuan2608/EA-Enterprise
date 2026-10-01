#ifndef ENTERPRISE_EA_EXECUTION_CONTRACTS_MQH
#define ENTERPRISE_EA_EXECUTION_CONTRACTS_MQH

enum ENUM_EEA_EXECUTION_ACTION
  {
   EEA_EXEC_ACTION_SUBMIT_MARKET=0,
   EEA_EXEC_ACTION_SUBMIT_PENDING=1,
   EEA_EXEC_ACTION_MODIFY_PROTECTIVE=2,
   EEA_EXEC_ACTION_CANCEL_PENDING=3
  };

enum ENUM_EEA_CONFIRMATION_STATE
  {
   EEA_CONFIRM_NOT_SENT=0,
   EEA_CONFIRM_PREFLIGHT_ACCEPTED=1,
   EEA_CONFIRM_REQUEST_ACCEPTED=2,
   EEA_CONFIRM_CONFIRMED=3,
   EEA_CONFIRM_REJECTED=4,
   EEA_CONFIRM_UNKNOWN=5
  };

struct EEA_ExecutionIntent
  {
   string schema_version;
   string intent_id;
   string correlation_id;
   string idempotency_key;
   string config_version;
   string account_fingerprint;
   string broker_server;
   string canonical_symbol;
   string broker_symbol;
   string symbol_fingerprint;
   int action; // ENUM_EEA_EXECUTION_ACTION
   int order_type;
   double volume;
   double price;
   double sl;
   double tp;
   long ticket;
   long position_ticket;
   datetime expiration;
   long magic;
   int deviation;
   int filling_mode;
   string request_ticket_kind;
   datetime intent_created_at_utc;
  };

struct EEA_ExecutionResult
  {
   string schema_version;
   string intent_id;
   string correlation_id;
   string idempotency_key;
   bool request_sent;
   string request_retcode;
   long request_ticket;
   string request_ticket_kind;
   string confirmation_state; // NOT_SENT | PREFLIGHT_ACCEPTED | REQUEST_ACCEPTED | CONFIRMED | REJECTED | EXECUTION_UNKNOWN
   string reason_code;
   datetime observed_at_utc;
  };

struct EEA_ExecutionGateContext
  {
   bool execution_enabled;
   bool reconciliation_fresh;
   string account_fingerprint;
   string broker_server;
   string canonical_symbol;
   string broker_symbol;
   bool symbol_spec_valid;
  };

void EEA_ExecutionIntentDefaults(EEA_ExecutionIntent &intent)
  {
   intent.schema_version="0.1.0";
   intent.intent_id="";
   intent.correlation_id="";
   intent.idempotency_key="";
   intent.config_version="";
   intent.account_fingerprint="";
   intent.broker_server="";
   intent.canonical_symbol="";
   intent.broker_symbol="";
   intent.symbol_fingerprint="";
   intent.action=EEA_EXEC_ACTION_SUBMIT_MARKET;
   intent.order_type=0;
   intent.volume=0.0;
   intent.price=0.0;
   intent.sl=0.0;
   intent.tp=0.0;
   intent.ticket=0;
   intent.position_ticket=0;
   intent.expiration=0;
   intent.magic=888888;
   intent.deviation=20;
   intent.filling_mode=0;
   intent.request_ticket_kind="ORDER";
   intent.intent_created_at_utc=0;
  }

void EEA_ExecutionResultDefaults(EEA_ExecutionResult &result)
  {
   result.schema_version="0.1.0";
   result.intent_id="";
   result.correlation_id="";
   result.idempotency_key="";
   result.request_sent=false;
   result.request_retcode="";
   result.request_ticket=0;
   result.request_ticket_kind="ORDER";
   result.confirmation_state="NOT_SENT";
   result.reason_code="EXECUTION_DISABLED";
   result.observed_at_utc=0;
  }

#endif
