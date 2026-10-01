#ifndef ENTERPRISE_EA_EXECUTION_GATE_MQH
#define ENTERPRISE_EA_EXECUTION_GATE_MQH

#include "ExecutionContracts.mqh"
#include "RuntimeEvidence.mqh"
#include "..\Market\SymbolRegistry.mqh"

bool EEA_ExecutionGateCheck(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
                            const bool execution_enabled,
                            EEA_ExecutionResult &result)
{
   EEA_ExecutionResultDefaults(result);
   result.intent_id=intent.intent_id;
   result.correlation_id=intent.correlation_id;
   result.idempotency_key=intent.idempotency_key;
   result.observed_at_utc=TimeCurrent();

   if(!execution_enabled)
     {
      result.confirmation_state="NOT_SENT";
      result.reason_code="EXECUTION_DISABLED";
      result.request_sent=false;
      return false;
     }

   if(!reconciliation.positions_complete || !reconciliation.orders_complete || !reconciliation.deals_complete)
     {
      result.confirmation_state="NOT_SENT";
      result.reason_code="RECONCILIATION_STALE";
      result.request_sent=false;
      return false;
     }

   if(intent.account_fingerprint!=account.account_fingerprint ||
      intent.broker_server!=account.broker_server)
     {
      result.confirmation_state="NOT_SENT";
      result.reason_code="ACCOUNT_IDENTITY_MISMATCH";
      result.request_sent=false;
      return false;
     }

   if(symbol.broker_symbol=="" || symbol.trade_mode=="DISABLED" || symbol.trade_mode=="CLOSE_ONLY")
     {
      result.confirmation_state="NOT_SENT";
      result.reason_code="SYMBOL_SPEC_INVALID";
      result.request_sent=false;
      return false;
     }

   if(intent.volume<symbol.volume_min || intent.volume>symbol.volume_max)
     {
      result.confirmation_state="NOT_SENT";
      result.reason_code="SYMBOL_SPEC_INVALID";
      result.request_sent=false;
      return false;
     }

   result.confirmation_state="PREFLIGHT_ACCEPTED";
   result.reason_code="OK";
   result.request_sent=false;
   return true;
}

#endif
