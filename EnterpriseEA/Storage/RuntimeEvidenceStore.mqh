#ifndef ENTERPRISE_EA_RUNTIME_EVIDENCE_STORE_MQH
#define ENTERPRISE_EA_RUNTIME_EVIDENCE_STORE_MQH

#include "AtomicWriter.mqh"
#include "SharedStateStore.mqh"
#include "..\Core\Events.mqh"
#include "..\Runtime\RuntimeEvidence.mqh"
#include "..\Runtime\ExecutionContracts.mqh"

string EEA_RuntimeBoolJson(const bool value) { return value ? "true" : "false"; }
string EEA_RuntimeDoubleJson(const double value) { return DoubleToString(value,12); }

bool EEA_RuntimeStoreWriteAccount(const string root,const EEA_RuntimeAccountSnapshot &account)
  {
   string json="{\"schema_version\":\""+EEA_JsonEscape(account.schema_version)+
      "\",\"document_version\":\"runtime-account-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(account.config_version)+"\",\"snapshot_id\":\""+EEA_JsonEscape(account.snapshot_id)+
      "\",\"observed_at_utc\":\""+EEA_IsoUtc((datetime)account.observed_at_utc)+
      "\",\"valid_until_utc\":\""+EEA_IsoUtc((datetime)account.valid_until_utc)+
      "\",\"account_fingerprint\":\""+EEA_JsonEscape(account.account_fingerprint)+
      "\",\"broker_server\":\""+EEA_JsonEscape(account.broker_server)+
      "\",\"account_currency\":\""+EEA_JsonEscape(account.account_currency)+
      "\",\"account_margin_mode\":\""+EEA_JsonEscape(account.account_margin_mode)+"\"}";
   return EEA_WriteAtomicText(root+"/current/account_snapshot.json",json);
  }

bool EEA_RuntimeStoreWriteSymbols(const string root,const string &canonical[],
                                  const EEA_RuntimeSymbolSpec &symbols[],const int count,
                                  const string config_version,const string account_fingerprint)
  {
   string rows="[";
   for(int i=0;i<count;i++)
     {
      if(i>0) rows+=",";
      rows+="{\"canonical_symbol\":\""+EEA_JsonEscape(canonical[i])+"\",\"broker_symbol\":\""+
         EEA_JsonEscape(symbols[i].broker_symbol)+"\",\"digits\":"+IntegerToString(symbols[i].digits)+
         ",\"point\":"+EEA_RuntimeDoubleJson(symbols[i].point)+",\"tick_size\":"+
         EEA_RuntimeDoubleJson(symbols[i].tick_size)+",\"tick_value\":"+
         EEA_RuntimeDoubleJson(symbols[i].tick_value)+",\"contract_size\":"+
         EEA_RuntimeDoubleJson(symbols[i].contract_size)+",\"volume_min\":"+
         EEA_RuntimeDoubleJson(symbols[i].volume_min)+",\"volume_max\":"+
         EEA_RuntimeDoubleJson(symbols[i].volume_max)+",\"volume_step\":"+
         EEA_RuntimeDoubleJson(symbols[i].volume_step)+",\"stops_level_points\":"+
         IntegerToString(symbols[i].stops_level_points)+",\"freeze_level_points\":"+
         IntegerToString(symbols[i].freeze_level_points)+",\"trade_mode\":\""+
         EEA_JsonEscape(symbols[i].trade_mode)+"\",\"order_mode\":\""+
         EEA_JsonEscape(symbols[i].order_mode)+"\",\"expiration_mode\":\""+
         EEA_JsonEscape(symbols[i].expiration_mode)+"\",\"calculation_mode\":\""+
         EEA_JsonEscape(symbols[i].calculation_mode)+"\",\"base_currency\":\""+
         EEA_JsonEscape(symbols[i].base_currency)+"\",\"profit_currency\":\""+
         EEA_JsonEscape(symbols[i].profit_currency)+"\",\"margin_currency\":\""+
         EEA_JsonEscape(symbols[i].margin_currency)+"\"}";
     }
   rows+="]";
   string json="{\"schema_version\":\"runtime-evidence-v0.1.0\",\"document_version\":\"runtime-symbols-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"account_fingerprint\":\""+
      EEA_JsonEscape(account_fingerprint)+"\",\"symbols\":"+rows+"}";
   return EEA_WriteAtomicText(root+"/current/symbol_registry.json",json);
  }

bool EEA_RuntimeStoreWriteReconciliation(const string root,const EEA_RuntimeReconciliationSnapshot &s)
  {
   string positions="[";
   for(int i=0;i<s.position_count;i++)
     {
      if(i>0) positions+=",";
      positions+="{\"ticket\":"+IntegerToString(s.positions[i].ticket)+",\"position_id\":\""+
         EEA_JsonEscape(s.positions[i].position_id)+"\",\"symbol\":\""+EEA_JsonEscape(s.positions[i].symbol)+
         "\",\"type\":\""+EEA_JsonEscape(s.positions[i].type)+"\",\"volume\":"+
         EEA_RuntimeDoubleJson(s.positions[i].volume)+",\"price_open\":"+
         EEA_RuntimeDoubleJson(s.positions[i].price_open)+",\"current_price\":"+
         EEA_RuntimeDoubleJson(s.positions[i].current_price)+",\"profit\":"+
         EEA_RuntimeDoubleJson(s.positions[i].profit)+",\"swap\":"+
         EEA_RuntimeDoubleJson(s.positions[i].swap)+",\"opened_at_utc\":\""+
         EEA_IsoUtc((datetime)s.positions[i].time_open_utc)+"\"}";
     }
   positions+="]";
   string orders="[";
   for(int i=0;i<s.order_count;i++)
     {
      if(i>0) orders+=",";
      orders+="{\"ticket\":"+IntegerToString(s.orders[i].ticket)+",\"order_id\":\""+
         EEA_JsonEscape(s.orders[i].order_id)+"\",\"symbol\":\""+EEA_JsonEscape(s.orders[i].symbol)+
         "\",\"type\":\""+EEA_JsonEscape(s.orders[i].type)+"\",\"volume_current\":"+
         EEA_RuntimeDoubleJson(s.orders[i].volume)+",\"price_open\":"+
         EEA_RuntimeDoubleJson(s.orders[i].price)+",\"sl\":"+EEA_RuntimeDoubleJson(s.orders[i].sl)+
         ",\"tp\":"+EEA_RuntimeDoubleJson(s.orders[i].tp)+",\"setup_at_utc\":\""+
         EEA_IsoUtc((datetime)s.orders[i].time_setup_utc)+"\",\"expiration_at_utc\":\""+
         EEA_IsoUtc((datetime)s.orders[i].expiration_utc)+"\"}";
     }
   orders+="]";
   string deals="[";
   for(int i=0;i<s.deal_count;i++)
     {
      if(i>0) deals+=",";
      deals+="{\"deal_ticket\":"+IntegerToString(s.deals[i].deal_ticket)+",\"order_ticket\":"+
         IntegerToString(s.deals[i].order_ticket)+",\"position_id\":\""+
         EEA_JsonEscape(s.deals[i].position_id)+"\",\"symbol\":\""+EEA_JsonEscape(s.deals[i].symbol)+
         "\",\"type\":\""+EEA_JsonEscape(s.deals[i].type)+"\",\"entry\":\""+
         EEA_JsonEscape(s.deals[i].entry)+"\",\"volume\":"+EEA_RuntimeDoubleJson(s.deals[i].volume)+
         ",\"price\":"+EEA_RuntimeDoubleJson(s.deals[i].price)+",\"profit\":"+
         EEA_RuntimeDoubleJson(s.deals[i].profit)+",\"commission\":"+
         EEA_RuntimeDoubleJson(s.deals[i].commission)+",\"swap\":"+
         EEA_RuntimeDoubleJson(s.deals[i].swap)+",\"fee\":"+EEA_RuntimeDoubleJson(s.deals[i].fee)+
         ",\"time_utc\":\""+EEA_IsoUtc((datetime)s.deals[i].time_utc)+
         "\",\"time_msc\":"+IntegerToString(s.deals[i].time_msc)+"}";
     }
   deals+="]";
   string json="{\"schema_version\":\""+EEA_JsonEscape(s.schema_version)+
      "\",\"document_version\":\"runtime-reconciliation-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(s.config_version)+"\",\"snapshot_id\":\""+EEA_JsonEscape(s.snapshot_id)+
      "\",\"observed_at_utc\":\""+EEA_IsoUtc((datetime)s.observed_at_utc)+
      "\",\"valid_until_utc\":\""+EEA_IsoUtc((datetime)s.valid_until_utc)+
      "\",\"history_from_utc\":\""+EEA_IsoUtc((datetime)s.history_from_utc)+
      "\",\"history_lookback_days\":"+IntegerToString((int)s.history_lookback_days)+
      ",\"account_fingerprint\":\""+EEA_JsonEscape(s.account_fingerprint)+
      "\",\"positions_complete\":"+EEA_RuntimeBoolJson(s.positions_complete)+
      ",\"orders_complete\":"+EEA_RuntimeBoolJson(s.orders_complete)+
      ",\"deals_complete\":"+EEA_RuntimeBoolJson(s.deals_complete)+
      ",\"position_count\":"+IntegerToString(s.position_count)+",\"order_count\":"+
      IntegerToString(s.order_count)+",\"deal_count\":"+IntegerToString(s.deal_count)+
      ",\"deal_watermark\":"+IntegerToString(s.deal_watermark)+
      ",\"deal_watermark_time_msc\":"+IntegerToString(s.deal_watermark_time_msc)+
      ",\"positions\":"+positions+",\"orders\":"+orders+",\"deals\":"+deals+"}";
   return EEA_WriteAtomicText(root+"/current/broker_reconciliation.json",json);
  }

bool EEA_RuntimeStoreWriteStatus(const string root,const EEA_RuntimeStatus &status,
                                 const string config_version,const string account_fingerprint,
                                 const long observed_at_utc)
  {
   string json="{\"schema_version\":\"runtime-evidence-v0.1.0\",\"document_version\":\"runtime-status-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"observed_at_utc\":\""+
      EEA_IsoUtc((datetime)observed_at_utc)+"\",\"account_fingerprint\":\""+
      EEA_JsonEscape(account_fingerprint)+"\",\"runtime_state\":\""+
      EEA_JsonEscape(status.runtime_state)+"\",\"reason_code\":\""+
      EEA_JsonEscape(status.reason_code)+"\",\"new_entries_blocked\":"+
      EEA_RuntimeBoolJson(status.new_entries_blocked)+
      ",\"runtime_instance_id\":"+IntegerToString(status.runtime_instance_id)+
      ",\"refresh_sequence\":"+IntegerToString(status.refresh_sequence)+
      ",\"refresh_generation\":"+IntegerToString(status.refresh_generation)+
      ",\"selection_revision\":"+IntegerToString(status.selection_revision)+
      ",\"checkpoint_written_at_utc\":"+IntegerToString(status.checkpoint_written_at_utc)+
      ",\"broker_observed_at_utc\":"+IntegerToString(status.broker_observed_at_utc)+
      ",\"selected_symbols_fingerprint\":\""+EEA_JsonEscape(status.selected_symbols_fingerprint)+
      "\",\"timer_tick_count\":"+IntegerToString(status.timer_tick_count)+
      ",\"refresh_attempt_count\":"+IntegerToString(status.refresh_attempt_count)+
      ",\"refresh_success_count\":"+IntegerToString(status.refresh_success_count)+
      ",\"refresh_failure_count\":"+IntegerToString(status.refresh_failure_count)+
      ",\"last_timer_at_utc\":"+IntegerToString(status.last_timer_at_utc)+
      ",\"last_refresh_duration_ms\":"+IntegerToString(status.last_refresh_duration_ms)+
      ",\"max_refresh_duration_ms\":"+IntegerToString(status.max_refresh_duration_ms)+
      ",\"consecutive_refresh_failures\":"+IntegerToString(status.consecutive_refresh_failures)+
      ",\"transaction_callback_count\":"+IntegerToString(status.transaction_callback_count)+
      ",\"transaction_invalidation_generation\":"+IntegerToString(status.transaction_invalidation_generation)+
      ",\"pending_refresh\":"+EEA_RuntimeBoolJson(status.pending_refresh)+
      ",\"refresh_in_progress\":"+EEA_RuntimeBoolJson(status.refresh_in_progress)+
      "}";
   return EEA_WriteAtomicText(root+"/current/runtime_status.json",json);
  }

EEAStateLoadResult EEA_RuntimeStoreCheckStatus(const string path,const string config_version,
                                               const string account_fingerprint)
  {
   if(!FileIsExist(path,0)) return EEA_STATE_MISSING;
   int h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE) return EEA_STATE_INCOMPATIBLE;
   ulong size=FileSize(h);
   if(size==0 || size>1048576) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uint read=FileReadArray(h,bytes,0,(int)size);
   FileClose(h);
   if(read!=(uint)size) return EEA_STATE_INCOMPATIBLE;
   string json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   if(StringFind(json,"\"document_version\":\"runtime-status-v0.1.0\"")<0 ||
      StringFind(json,"\"config_version\":\""+EEA_JsonEscape(config_version)+"\"")<0 ||
      StringFind(json,"\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+"\"")<0)
      return EEA_STATE_INCOMPATIBLE;
   return EEA_STATE_COMPATIBLE;
  }

bool EEA_RuntimeStoreWriteSymbolSelection(const string root, const string config_version, const string account_fingerprint,
                                          const string broker_server, const long selection_revision,
                                          const string &canonical[], const string &broker[], const int count)
  {
   string canonical_array = "[";
   for(int i=0; i<count; i++)
     {
      if(i>0) canonical_array += ",";
      canonical_array += "\"" + EEA_JsonEscape(canonical[i]) + "\"";
     }
   canonical_array += "]";

   string broker_array = "[";
   for(int i=0; i<count; i++)
     {
      if(i>0) broker_array += ",";
      broker_array += "\"" + EEA_JsonEscape(broker[i]) + "\"";
     }
   broker_array += "]";

   string json="{\"document_version\":\"runtime-selection-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"account_fingerprint\":\""+
      EEA_JsonEscape(account_fingerprint)+"\",\"broker_server\":\""+
      EEA_JsonEscape(broker_server)+"\",\"selection_revision\":"+
      IntegerToString(selection_revision)+",\"canonical_symbols\":"+
      canonical_array+",\"broker_symbols\":"+broker_array+"}";
      
   return EEA_WriteAtomicText(root+"/current/symbol_selection.json",json);
  }

EEAStateLoadResult EEA_RuntimeStoreCheckSymbolSelection(const string path, const string config_version, const string account_fingerprint)
  {
   if(!FileIsExist(path,0)) return EEA_STATE_MISSING;
   int h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE) return EEA_STATE_INCOMPATIBLE;
   ulong size=FileSize(h);
   if(size==0 || size>1048576) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uint read=FileReadArray(h,bytes,0,(int)size);
   FileClose(h);
   if(read!=(uint)size) return EEA_STATE_INCOMPATIBLE;
   string json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   
   if(StringFind(json,"\"document_version\":\"runtime-selection-v0.1.0\"")<0 ||
      StringFind(json,"\"config_version\":\""+EEA_JsonEscape(config_version)+"\"")<0 ||
      StringFind(json,"\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+"\"")<0)
      return EEA_STATE_INCOMPATIBLE;
      
   // Never returning broker mappings as truth is a business logic trait handled by the Oracle logic,
   // here we just return the compatibility state.
   return EEA_STATE_COMPATIBLE;
  }

bool EEA_ExecutionStoreWriteIntent(const string root,const EEA_ExecutionIntent &intent)
  {
   string json="{\"schema_version\":\""+EEA_JsonEscape(intent.schema_version)+
      "\",\"document_version\":\"execution-intent-v0.1.0\",\"intent_id\":\""+
      EEA_JsonEscape(intent.intent_id)+"\",\"correlation_id\":\""+
      EEA_JsonEscape(intent.correlation_id)+"\",\"idempotency_key\":\""+
      EEA_JsonEscape(intent.idempotency_key)+"\",\"config_version\":\""+
      EEA_JsonEscape(intent.config_version)+"\",\"account_fingerprint\":\""+
      EEA_JsonEscape(intent.account_fingerprint)+"\",\"broker_server\":\""+
      EEA_JsonEscape(intent.broker_server)+"\",\"canonical_symbol\":\""+
      EEA_JsonEscape(intent.canonical_symbol)+"\",\"broker_symbol\":\""+
      EEA_JsonEscape(intent.broker_symbol)+"\",\"symbol_fingerprint\":\""+
      EEA_JsonEscape(intent.symbol_fingerprint)+"\",\"action\":"+
      IntegerToString(intent.action)+",\"order_type\":"+
      IntegerToString(intent.order_type)+",\"volume\":"+
      EEA_RuntimeDoubleJson(intent.volume)+",\"price\":"+
      EEA_RuntimeDoubleJson(intent.price)+",\"sl\":"+
      EEA_RuntimeDoubleJson(intent.sl)+",\"tp\":"+
      EEA_RuntimeDoubleJson(intent.tp)+",\"intent_created_at_utc\":\""+
      EEA_IsoUtc((datetime)intent.intent_created_at_utc)+"\"}";
   bool ok1=EEA_WriteAtomicText(root+"/current/execution_intent.json",json);
   bool ok2=EEA_WriteAtomicAppendText(root+"/logs/execution_audit.jsonl",json+"\r\n");
   return ok1 && ok2;
  }

bool EEA_ExecutionStoreWriteResult(const string root,const EEA_ExecutionResult &result)
  {
   string json="{\"schema_version\":\""+EEA_JsonEscape(result.schema_version)+
      "\",\"document_version\":\"execution-result-v0.1.0\",\"intent_id\":\""+
      EEA_JsonEscape(result.intent_id)+"\",\"correlation_id\":\""+
      EEA_JsonEscape(result.correlation_id)+"\",\"idempotency_key\":\""+
      EEA_JsonEscape(result.idempotency_key)+"\",\"request_sent\":"+
      (result.request_sent ? "true" : "false")+",\"request_retcode\":\""+
      EEA_JsonEscape(result.request_retcode)+"\",\"request_ticket\":"+
      IntegerToString(result.request_ticket)+",\"confirmation_state\":\""+
      EEA_JsonEscape(result.confirmation_state)+"\",\"reason_code\":\""+
      EEA_JsonEscape(result.reason_code)+"\",\"observed_at_utc\":\""+
      EEA_IsoUtc((datetime)result.observed_at_utc)+"\"}";
   bool ok1=EEA_WriteAtomicText(root+"/current/execution_result.json",json);
   bool ok2=EEA_WriteAtomicAppendText(root+"/logs/execution_audit.jsonl",json+"\r\n");
   return ok1 && ok2;
  }

#endif
