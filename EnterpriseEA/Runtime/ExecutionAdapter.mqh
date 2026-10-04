#ifndef ENTERPRISE_EA_EXECUTION_ADAPTER_MQH
#define ENTERPRISE_EA_EXECUTION_ADAPTER_MQH

#include "ExecutionContracts.mqh"
#include "ExecutionGate.mqh"
#include "ExecutionReconciliation.mqh"
#include "ExecutionControllerState.mqh"
#include "LiveAuthorizationGate.mqh"
#include "..\Risk\RiskDecision.mqh"
#include "../Storage/AuditLog.mqh"
#include "../Storage/RuntimeEvidenceStore.mqh"

string EEA_ExecutionResolveRoot(const string data_root)
{
   return (data_root == "") ? "EnterpriseEA" : data_root;
}

bool EEA_ExecutionIsDuplicateIdempotency(const string root, const string idempotency_key)
{
   if(idempotency_key == "") return false;
   // Marker index first: O(1) and unaffected by the audit log size. Until the one-time
   // migration of older keys succeeded, fail closed.
   if(!EEA_IdempotencyIndexReady(root)) return true;
   if(FileIsExist(EEA_IdempotencyMarkerPath(root, idempotency_key), 0)) return true;
   return EEA_ExecutionIsDuplicateIdempotencyInLog(root, idempotency_key);
}

// Legacy scan of the audit log. Above 1MB the marker index (complete after the migration)
// is authoritative, so a large log no longer blocks every request.
bool EEA_ExecutionIsDuplicateIdempotencyInLog(const string root, const string idempotency_key)
{
   string path = root + "/logs/execution_audit.jsonl";
   if(!FileIsExist(path, 0)) return false;
   int h = FileOpen(path, FILE_READ|FILE_BIN|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE) return true; // Fail closed on unreadable log
   ulong size = FileSize(h);
   if(size > 1048576) { FileClose(h); return false; } // Marker index is authoritative (>1MB)
   if(size == 0) { FileClose(h); return false; }
   uchar bytes[];
   if(ArrayResize(bytes, (int)size) != (int)size) { FileClose(h); return true; }
   uint read = FileReadArray(h, bytes, 0, (int)size);
   FileClose(h);
   if(read != (uint)size) return true; // Fail closed on incomplete read
   string content = CharArrayToString(bytes, 0, (int)read, CP_UTF8);
   
   string lines[];
   int count = StringSplit(content, '\n', lines);
   for(int i = 0; i < count; i++)
     {
      string line = lines[i];
      string escaped_key = EEA_JsonEscape(idempotency_key);
      if(StringFind(line, "\"idempotency_key\":\"" + escaped_key + "\"") >= 0)
        {
         return true;
        }
     }
   return false;
}

void EEA_AuditExecutionFailure(CAuditLog &audit, const string intent_id, const string reason_code)
{
   EEAEvent err_event;
   EEAEvent_Init(err_event, "EXECUTION_REJECTED", TimeGMT(), "", "", "", "", "UNKNOWN");
   err_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent_id) + "\",\"reason_code\":\"" + EEA_JsonEscape(reason_code) + "\"}";
   audit.Append(err_event, "EA_EXECUTION");
}

bool EEA_ExecutionRetcodeAcknowledged(const uint retcode,const int action)
{
   if(action==EEA_EXEC_ACTION_SUBMIT_MARKET)
      return retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL;
   if(action==EEA_EXEC_ACTION_SUBMIT_PENDING)
      return retcode==TRADE_RETCODE_PLACED || retcode==TRADE_RETCODE_DONE ||
             retcode==TRADE_RETCODE_DONE_PARTIAL;
   if(action==EEA_EXEC_ACTION_MODIFY_PROTECTIVE)
      return retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_ORDER_CHANGED ||
             retcode==TRADE_RETCODE_NO_CHANGES;
   if(action==EEA_EXEC_ACTION_CANCEL_PENDING)
      return retcode==TRADE_RETCODE_DONE;
   return false;
}

bool EEA_ExecutionAuthorizationBinds(const EEA_LiveAuthorizationDecision &authorization,
                                      const EEA_ExecutionIntent &intent,
                                      const EEA_RuntimeAccountSnapshot &account,
                                      const EEA_RuntimeSymbolSpec &symbol)
{
   return authorization.authorized && authorization.status=="AUTHORIZED_CONTROLLED_LIVE" &&
      authorization.authorization_valid_until_utc>TimeGMT() &&
      authorization.account_fingerprint==account.account_fingerprint &&
      authorization.account_fingerprint==intent.account_fingerprint &&
      authorization.candidate_id==intent.candidate_id &&
      authorization.intent_id==intent.intent_id &&
      authorization.config_version==intent.config_version &&
      authorization.broker_server==intent.broker_server &&
      authorization.broker_symbol==intent.broker_symbol &&
      authorization.broker_symbol==symbol.broker_symbol &&
      authorization.account_mode==account.account_margin_mode &&
      authorization.risk_policy_id==intent.risk_policy_id;
}

void EEA_ExecutionBindAuthorization(EEA_ExecutionResult &result,
                                     const EEA_LiveAuthorizationDecision &authorization)
  {
   result.authorization_id=authorization.authorization_id;
   result.build_hash=authorization.build_hash;
  }

void EEA_ExecutionBindIntentLineage(EEA_ExecutionResult &result,
                                    const EEA_ExecutionIntent &intent)
  {
   result.risk_decision_id=intent.risk_decision_id;
  }

bool EEA_ExecutionPersistUnknownAfterFailure(const string root,
                                              EEA_ExecutionResult &result,
                                              const string intent_id)
{
   result.confirmation_state="EXECUTION_UNKNOWN";
   result.reason_code="EXECUTION_RESULT_PERSISTENCE_FAILED";
   string failure_json="{\"intent_id\":\""+EEA_JsonEscape(intent_id)+
      "\",\"reason_code\":\"EXECUTION_RESULT_PERSISTENCE_FAILED\"}";
   bool marker_written=EEA_WriteAtomicText(root+"/current/execution_persistence_failure.json",failure_json) &&
      EEA_WriteAtomicAppendText(root+"/logs/execution_persistence_failures.jsonl",failure_json+"\r\n");
   if(!marker_written) result.reason_code="EXECUTION_PERSISTENCE_FAILURE_UNDURABLE";
   bool result_rewritten=EEA_ExecutionStoreWriteResult(root,result);
   if(!result_rewritten && result.reason_code!="EXECUTION_PERSISTENCE_FAILURE_UNDURABLE")
      result.reason_code="EXECUTION_PERSISTENCE_FAILURE_UNDURABLE";
   return false;
}

bool EEA_ExecutionPersistAfterSend(CAuditLog &audit,
                                   const string root,
                                   EEA_ExecutionResult &result,
                                   const string intent_id)
{
   bool result_written=EEA_ExecutionStoreWriteResult(root,result);
   if(!result_written)
      return EEA_ExecutionPersistUnknownAfterFailure(root,result,intent_id);

   EEAEvent ack_event;
   EEAEvent_Init(ack_event, "EXECUTION_ACKNOWLEDGED", TimeGMT(), "", "", "", "", "UNKNOWN");
   ack_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent_id) + "\",\"ticket\":" + IntegerToString(result.request_ticket) + "}";
   bool audit_written=audit.Append(ack_event, "EA_EXECUTION");
   if(!audit_written)
      return EEA_ExecutionPersistUnknownAfterFailure(root,result,intent_id);
   return true;
}

bool EEA_ExecutionPersistBeforeSend(CAuditLog &audit,
                                     const string root,
                                     const EEA_ExecutionIntent &intent,
                                     const string details_json)
{
   if(!EEA_ExecutionStoreWriteIntent(root, intent))
      return false;

   EEAEvent req_event;
   EEAEvent_Init(req_event, "EXECUTION_REQUESTED", TimeGMT(), "", "", "", "", "UNKNOWN");
   req_event.details_json = details_json;
   return audit.Append(req_event, "EA_EXECUTION");
}

void EEA_ExecutionRecordPersistenceFailure(CAuditLog &audit,
                                            const string root,
                                            const EEA_ExecutionIntent &intent,
                                            EEA_ExecutionResult &result)
{
   result.request_sent = false;
   result.confirmation_state = "NOT_SENT";
   result.reason_code = "EXECUTION_PERSISTENCE_FAILED";
   EEA_ExecutionStoreWriteResult(root, result);
   EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
}

bool EEA_ExecutionPreflight(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
                            const EEA_RuntimeStatus &status,
                            const bool execution_enabled,
                            EEA_ExecutionResult &result)
{
   return EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, status, execution_enabled, result);
}

bool EEA_ExecutionSubmit(CAuditLog &audit,
                         const string data_root,
                         const EEA_ExecutionIntent &intent,
                         const EEA_RiskDecision &decision,
                         const EEA_ExecutionControllerState &controller,
                         const string requested_scope,
                         const EEA_RuntimeAccountSnapshot &account,
                         const EEA_RuntimeReconciliationSnapshot &reconciliation,
                         const EEA_RuntimeSymbolSpec &symbol,
                         const EEA_RuntimeStatus &status,
                         const bool execution_enabled,
                         const EEA_LiveAuthorizationDecision &authorization,
                         EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;
   EEA_ExecutionBindIntentLineage(result,intent);

   // REQ-021 pending entries need the pending controller scope in addition to the
   // same authorization, risk release and gate checks as a market entry.
   if(intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING && requested_scope!="PENDING_ENTRY")
     {
      EEA_ExecutionResultReject(result,"CONTROLLER_SCOPE_REJECTED");
      return false;
     }
   EEA_ExecutionBindAuthorization(result,authorization);
   if(!EEA_ExecutionAuthorizationBinds(authorization,intent,account,symbol))
     {
      EEA_ExecutionResultReject(result,"LIVE_AUTHORIZATION_REQUIRED");
      return false;
     }
   if(intent.action!=EEA_EXEC_ACTION_SUBMIT_MARKET && intent.action!=EEA_EXEC_ACTION_SUBMIT_PENDING)
     {
      EEA_ExecutionResultReject(result,"EXECUTION_ACTION_MISMATCH");
      return false;
     }
   if(!EEA_ExecutionControllerIdentityMatches(controller,intent.config_version,
                                              account.account_fingerprint,account.broker_server) ||
      !EEA_ExecutionControllerAllowsNewRequest(controller,requested_scope,TimeGMT()))
     {
      EEA_ExecutionResultReject(result,"CONTROLLER_SCOPE_REJECTED");
      return false;
     }

   if(EEA_ExecutionIsDuplicateIdempotency(root, intent.idempotency_key))
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "DUPLICATE_IDEMPOTENCY_KEY";
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionGateCheckReleased(intent, decision, account, reconciliation, symbol, status, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionPersistBeforeSend(audit, root, intent,
      "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"correlation_id\":\"" + EEA_JsonEscape(intent.correlation_id) + "\"}"))
     {
      EEA_ExecutionRecordPersistenceFailure(audit, root, intent, result);
      return false;
     }

   MqlTradeRequest request;
   MqlTradeResult trade_result;
   ZeroMemory(request);
   ZeroMemory(trade_result);

   request.action = (intent.action == EEA_EXEC_ACTION_SUBMIT_MARKET) ? TRADE_ACTION_DEAL : TRADE_ACTION_PENDING;
   request.symbol = intent.broker_symbol;
   request.volume = intent.volume;
   request.price = intent.price;
   request.sl = intent.sl;
   request.tp = intent.tp;
   request.type = (ENUM_ORDER_TYPE)intent.order_type;
   request.type_filling = (ENUM_ORDER_TYPE_FILLING)intent.filling_mode;
   request.deviation = intent.deviation;
   request.magic = intent.magic;

   if(intent.action == EEA_EXEC_ACTION_SUBMIT_PENDING)
     {
      // Broker-enforced expiry only; a GTC order is never used for a strategy deadline.
      // The broker compares the expiration in server time.
      long server_offset=(long)TimeTradeServer()-(long)TimeGMT();
      request.type_time = ORDER_TIME_SPECIFIED;
      request.expiration = (datetime)((long)intent.expiration+server_offset);
      request.type_filling = ORDER_FILLING_RETURN;
      MqlTick tick;
      ZeroMemory(tick);
      double point=SymbolInfoDouble(intent.broker_symbol,SYMBOL_POINT);
      double min_distance=(double)SymbolInfoInteger(intent.broker_symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
      bool geometry_ok=SymbolInfoTick(intent.broker_symbol,tick) && tick.bid>0.0 && tick.ask>0.0;
      if(geometry_ok && intent.order_type==ORDER_TYPE_BUY_LIMIT)  geometry_ok=intent.price<=tick.ask-min_distance;
      if(geometry_ok && intent.order_type==ORDER_TYPE_SELL_LIMIT) geometry_ok=intent.price>=tick.bid+min_distance;
      if(geometry_ok && intent.order_type==ORDER_TYPE_BUY_STOP)   geometry_ok=intent.price>=tick.ask+min_distance;
      if(geometry_ok && intent.order_type==ORDER_TYPE_SELL_STOP)  geometry_ok=intent.price<=tick.bid-min_distance;
      if(!geometry_ok)
        {
         result.confirmation_state = "REJECTED";
         result.reason_code = "PENDING_PRICE_GEOMETRY_INVALID";
         result.request_sent = false;
         EEA_ExecutionStoreWriteResult(root, result);
         EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
         return false;
        }
     }

   bool sent = OrderSend(request, trade_result);
   bool broker_acknowledged = EEA_ExecutionRetcodeAcknowledged(trade_result.retcode,intent.action);
   result.request_sent = sent || broker_acknowledged;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = (intent.action == EEA_EXEC_ACTION_SUBMIT_MARKET && trade_result.deal > 0) ? "DEAL" : "ORDER";
   result.request_ticket = (result.request_ticket_kind == "DEAL") ? (long)trade_result.deal : (long)trade_result.order;
   result.observed_at_utc = TimeCurrent();

   if(!broker_acknowledged)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "ORDER_SEND_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   if(!EEA_ExecutionPersistAfterSend(audit, root, result, intent.intent_id))
      return false;
   return true;
}

bool EEA_ExecutionModifyProtective(CAuditLog &audit,
                                    const string data_root,
                                    const EEA_ExecutionIntent &intent,
                                    const EEA_RuntimeAccountSnapshot &account,
                                    const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                    const EEA_RuntimeSymbolSpec &symbol,
                                    const EEA_RuntimeStatus &status,
                                    const bool execution_enabled,
                                    const EEA_LiveAuthorizationDecision &authorization,
                                    EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;
   EEA_ExecutionBindIntentLineage(result,intent);

   if(intent.position_ticket<=0)
     {
      EEA_ExecutionResultReject(result,"PENDING_RUNTIME_NOT_IMPLEMENTED");
      return false;
     }
   EEA_ExecutionBindAuthorization(result,authorization);
   if(!EEA_ExecutionAuthorizationBinds(authorization,intent,account,symbol))
     {
      EEA_ExecutionResultReject(result,"LIVE_AUTHORIZATION_REQUIRED");
      return false;
     }
   if(intent.action!=EEA_EXEC_ACTION_MODIFY_PROTECTIVE)
     {
      EEA_ExecutionResultReject(result,"EXECUTION_ACTION_MISMATCH");
      return false;
     }

   if(EEA_ExecutionIsDuplicateIdempotency(root, intent.idempotency_key))
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "DUPLICATE_IDEMPOTENCY_KEY";
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(intent.ticket <= 0 && intent.position_ticket <= 0)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "INVALID_TICKET";
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, status, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionPersistBeforeSend(audit, root, intent,
      "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(intent.position_ticket > 0 ? intent.position_ticket : intent.ticket) + "}"))
     {
      EEA_ExecutionRecordPersistenceFailure(audit, root, intent, result);
      return false;
     }

   MqlTradeRequest request;
   MqlTradeResult trade_result;
   ZeroMemory(request);
   ZeroMemory(trade_result);

   request.symbol = intent.broker_symbol;
   request.sl = intent.sl;
   request.tp = intent.tp;
   request.magic = intent.magic;

   if(intent.position_ticket > 0)
     {
      request.action = TRADE_ACTION_SLTP;
      request.position = (ulong)intent.position_ticket;
     }
   else
     {
      request.action = TRADE_ACTION_MODIFY;
      request.order = (ulong)intent.ticket;
      request.price = intent.price;
     }

   bool sent = OrderSend(request, trade_result);
   bool broker_acknowledged = EEA_ExecutionRetcodeAcknowledged(trade_result.retcode,intent.action);
   result.request_sent = sent || broker_acknowledged;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = intent.position_ticket > 0 ? "POSITION" : "ORDER";
   result.request_ticket = intent.position_ticket > 0 ? intent.position_ticket : intent.ticket;
   result.observed_at_utc = TimeCurrent();

   if(!broker_acknowledged)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "MODIFY_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   if(!EEA_ExecutionPersistAfterSend(audit, root, result, intent.intent_id))
      return false;
   return true;
}

bool EEA_ExecutionCancelPending(CAuditLog &audit,
                                const string data_root,
                                const EEA_ExecutionIntent &intent,
                                const EEA_RuntimeAccountSnapshot &account,
                                const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                const EEA_RuntimeSymbolSpec &symbol,
                                const EEA_RuntimeStatus &status,
                                const bool execution_enabled,
                                const EEA_LiveAuthorizationDecision &authorization,
                                EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;
   EEA_ExecutionBindIntentLineage(result,intent);

   // Every send path, cancellation included, stays bound to the live authorization.
   // When that authorization has lapsed, the broker-enforced expiration (mandatory for
   // REQ-021 orders) still removes the order at its deadline.
   EEA_ExecutionBindAuthorization(result,authorization);
   if(!EEA_ExecutionAuthorizationBinds(authorization,intent,account,symbol))
     {
      EEA_ExecutionResultReject(result,"LIVE_AUTHORIZATION_REQUIRED");
      return false;
     }
   if(intent.ticket>0 && (!OrderSelect((ulong)intent.ticket) ||
      OrderGetInteger(ORDER_MAGIC)!=intent.magic || OrderGetString(ORDER_SYMBOL)!=intent.broker_symbol))
     {
      EEA_ExecutionResultReject(result,"PENDING_ORDER_NOT_ACTIVE_OR_NOT_OWNED");
      return false;
     }
   if(intent.action!=EEA_EXEC_ACTION_CANCEL_PENDING)
     {
      EEA_ExecutionResultReject(result,"EXECUTION_ACTION_MISMATCH");
      return false;
     }

   if(EEA_ExecutionIsDuplicateIdempotency(root, intent.idempotency_key))
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "DUPLICATE_IDEMPOTENCY_KEY";
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(intent.ticket <= 0)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "INVALID_TICKET";
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, status, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   if(!EEA_ExecutionPersistBeforeSend(audit, root, intent,
      "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(intent.ticket) + "}"))
     {
      EEA_ExecutionRecordPersistenceFailure(audit, root, intent, result);
      return false;
     }

   MqlTradeRequest request;
   MqlTradeResult trade_result;
   ZeroMemory(request);
   ZeroMemory(trade_result);

   request.action = TRADE_ACTION_REMOVE;
   request.symbol = intent.broker_symbol;
   request.order = (ulong)intent.ticket;
   request.magic = intent.magic;

   bool sent = OrderSend(request, trade_result);
   bool broker_acknowledged = EEA_ExecutionRetcodeAcknowledged(trade_result.retcode,intent.action);
   result.request_sent = sent || broker_acknowledged;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = "ORDER";
   result.request_ticket = intent.ticket;
   result.observed_at_utc = TimeCurrent();

   if(!broker_acknowledged)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "CANCEL_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   if(!EEA_ExecutionPersistAfterSend(audit, root, result, intent.intent_id))
      return false;
   return true;
}

#endif
