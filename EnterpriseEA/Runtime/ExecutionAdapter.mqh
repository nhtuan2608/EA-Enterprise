#ifndef ENTERPRISE_EA_EXECUTION_ADAPTER_MQH
#define ENTERPRISE_EA_EXECUTION_ADAPTER_MQH

#include "ExecutionContracts.mqh"
#include "ExecutionGate.mqh"
#include "ExecutionReconciliation.mqh"
#include "../Storage/AuditLog.mqh"
#include "../Storage/RuntimeEvidenceStore.mqh"

string EEA_ExecutionResolveRoot(const string data_root)
{
   return (data_root == "") ? "EnterpriseEA" : data_root;
}

bool EEA_ExecutionIsDuplicateIdempotency(const string root, const string idempotency_key)
{
   if(idempotency_key == "") return false;
   string path = root + "/logs/execution_audit.jsonl";
   if(!FileIsExist(path, 0)) return false;
   int h = FileOpen(path, FILE_READ|FILE_BIN|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE) return true; // Fail closed on unreadable log
   ulong size = FileSize(h);
   if(size > 1048576) { FileClose(h); return true; } // Fail closed on oversized log (>1MB)
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
      if(StringFind(line, "\"idempotency_key\":\"" + idempotency_key + "\"") >= 0 ||
         StringFind(line, "\"idempotency_key\":\"" + idempotency_key + '"') >= 0)
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

bool EEA_ExecutionPreflight(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
                            const bool execution_enabled,
                            EEA_ExecutionResult &result)
{
   return EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, execution_enabled, result);
}

bool EEA_ExecutionSubmit(CAuditLog &audit,
                         const string data_root,
                         const EEA_ExecutionIntent &intent,
                         const EEA_RuntimeAccountSnapshot &account,
                         const EEA_RuntimeReconciliationSnapshot &reconciliation,
                         const EEA_RuntimeSymbolSpec &symbol,
                         const bool execution_enabled,
                         EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;

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

   if(!EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   EEA_ExecutionStoreWriteIntent(root, intent);
   EEAEvent req_event;
   EEAEvent_Init(req_event, "EXECUTION_REQUESTED", TimeGMT(), "", "", "", "", "UNKNOWN");
   req_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"correlation_id\":\"" + EEA_JsonEscape(intent.correlation_id) + "\"}";
   audit.Append(req_event, "EA_EXECUTION");

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
   request.type_filling = (ENUM_ORDER_FILLING)intent.filling_mode;
   request.deviation = intent.deviation;
   request.magic = intent.magic;

   if(intent.action == EEA_EXEC_ACTION_SUBMIT_PENDING)
     {
      request.type_time = (intent.expiration > 0) ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC;
      request.expiration = intent.expiration;
     }

   bool sent = OrderSend(request, trade_result);
   result.request_sent = sent;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = (intent.action == EEA_EXEC_ACTION_SUBMIT_MARKET && trade_result.deal > 0) ? "DEAL" : "ORDER";
   result.request_ticket = (result.request_ticket_kind == "DEAL") ? trade_result.deal : trade_result.order;
   result.observed_at_utc = TimeCurrent();

   if(!sent || trade_result.retcode != TRADE_RETCODE_DONE)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "ORDER_SEND_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   EEA_ExecutionStoreWriteResult(root, result);
   EEAEvent ack_event;
   EEAEvent_Init(ack_event, "EXECUTION_ACKNOWLEDGED", TimeGMT(), "", "", "", "", "UNKNOWN");
   ack_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(result.request_ticket) + "}";
   audit.Append(ack_event, "EA_EXECUTION");
   return true;
}

bool EEA_ExecutionModifyProtective(CAuditLog &audit,
                                    const string data_root,
                                    const EEA_ExecutionIntent &intent,
                                    const EEA_RuntimeAccountSnapshot &account,
                                    const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                    const EEA_RuntimeSymbolSpec &symbol,
                                    const bool execution_enabled,
                                    EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;

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

   if(!EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   EEA_ExecutionStoreWriteIntent(root, intent);
   EEAEvent req_event;
   EEAEvent_Init(req_event, "EXECUTION_REQUESTED", TimeGMT(), "", "", "", "", "UNKNOWN");
   req_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(intent.position_ticket > 0 ? intent.position_ticket : intent.ticket) + "}";
   audit.Append(req_event, "EA_EXECUTION");

   MqlTradeRequest request;
   MqlTradeResult trade_result;
   ZeroMemory(request);
   ZeroMemory(trade_result);

   request.action = TRADE_ACTION_SLTP;
   request.symbol = intent.broker_symbol;
   request.sl = intent.sl;
   request.tp = intent.tp;
   request.magic = intent.magic;

   if(intent.position_ticket > 0)
      request.position = (ulong)intent.position_ticket;
   else
      request.order = (ulong)intent.ticket;

   bool sent = OrderSend(request, trade_result);
   result.request_sent = sent;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = intent.position_ticket > 0 ? "POSITION" : "ORDER";
   result.request_ticket = intent.position_ticket > 0 ? intent.position_ticket : intent.ticket;
   result.observed_at_utc = TimeCurrent();

   if(!sent || trade_result.retcode != TRADE_RETCODE_DONE)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "MODIFY_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   EEA_ExecutionStoreWriteResult(root, result);
   EEAEvent ack_event;
   EEAEvent_Init(ack_event, "EXECUTION_ACKNOWLEDGED", TimeGMT(), "", "", "", "", "UNKNOWN");
   ack_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(result.request_ticket) + "}";
   audit.Append(ack_event, "EA_EXECUTION");
   return true;
}

bool EEA_ExecutionCancelPending(CAuditLog &audit,
                                const string data_root,
                                const EEA_ExecutionIntent &intent,
                                const EEA_RuntimeAccountSnapshot &account,
                                const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                const EEA_RuntimeSymbolSpec &symbol,
                                const bool execution_enabled,
                                EEA_ExecutionResult &result)
{
   string root = EEA_ExecutionResolveRoot(data_root);
   EEA_ExecutionResultDefaults(result);
   result.intent_id = intent.intent_id;
   result.correlation_id = intent.correlation_id;
   result.idempotency_key = intent.idempotency_key;

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

   if(!EEA_ExecutionGateCheck(intent, account, reconciliation, symbol, execution_enabled, result))
     {
      result.request_sent = false;
      EEA_ExecutionStoreWriteIntent(root, intent);
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   EEA_ExecutionStoreWriteIntent(root, intent);
   EEAEvent req_event;
   EEAEvent_Init(req_event, "EXECUTION_REQUESTED", TimeGMT(), "", "", "", "", "UNKNOWN");
   req_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(intent.ticket) + "}";
   audit.Append(req_event, "EA_EXECUTION");

   MqlTradeRequest request;
   MqlTradeResult trade_result;
   ZeroMemory(request);
   ZeroMemory(trade_result);

   request.action = TRADE_ACTION_REMOVE;
   request.symbol = intent.broker_symbol;
   request.order = (ulong)intent.ticket;
   request.magic = intent.magic;

   bool sent = OrderSend(request, trade_result);
   result.request_sent = sent;
   result.request_retcode = IntegerToString(trade_result.retcode);
   result.request_ticket_kind = "ORDER";
   result.request_ticket = intent.ticket;
   result.observed_at_utc = TimeCurrent();

   if(!sent || trade_result.retcode != TRADE_RETCODE_DONE)
     {
      result.confirmation_state = "REJECTED";
      result.reason_code = "CANCEL_FAILED_" + result.request_retcode;
      EEA_ExecutionStoreWriteResult(root, result);
      EEA_AuditExecutionFailure(audit, intent.intent_id, result.reason_code);
      return false;
     }

   result.confirmation_state = "EXECUTION_UNKNOWN";
   result.reason_code = "REQUEST_ACKNOWLEDGED_RECONCILIATION_REQUIRED";
   EEA_ExecutionStoreWriteResult(root, result);
   EEAEvent ack_event;
   EEAEvent_Init(ack_event, "EXECUTION_ACKNOWLEDGED", TimeGMT(), "", "", "", "", "UNKNOWN");
   ack_event.details_json = "{\"intent_id\":\"" + EEA_JsonEscape(intent.intent_id) + "\",\"ticket\":" + IntegerToString(intent.ticket) + "}";
   audit.Append(ack_event, "EA_EXECUTION");
   return true;
}

#endif
