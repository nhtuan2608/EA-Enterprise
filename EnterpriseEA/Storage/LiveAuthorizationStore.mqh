#ifndef ENTERPRISE_EA_LIVE_AUTHORIZATION_STORE_MQH
#define ENTERPRISE_EA_LIVE_AUTHORIZATION_STORE_MQH

#include "AtomicWriter.mqh"
#include "../Runtime/LiveAuthorizationGate.mqh"

string EEA_LiveAuthorizationStoreField(const string json,const string name)
  {
   string key="\""+name+"\":";
   int at=StringFind(json,key);
   if(at<0) return "";
   int start=at+StringLen(key);
   if(start<StringLen(json) && StringGetCharacter(json,start)==34)
     {
      start++;
      int end=StringFind(json,"\"",start);
      if(end<0) return "";
      return StringSubstr(json,start,end-start);
     }
   int end=StringFind(json,",",start);
   if(end<0) end=StringFind(json,"}",start);
   if(end<0) return "";
   return StringSubstr(json,start,end-start);
  }

bool EEA_LiveAuthorizationStoreRead(const string path,string &json)
  {
   json="";
   if(path=="" || !FileIsExist(path,0)) return false;
   int handle=FileOpen(path,FILE_READ|FILE_BIN|FILE_SHARE_READ);
   if(handle==INVALID_HANDLE) return false;
   ulong size=FileSize(handle);
   if(size==0 || size>131072) { FileClose(handle); return false; }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size) { FileClose(handle); return false; }
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return false;
   json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   return StringLen(json)>0;
  }

bool EEA_LiveAuthorizationStoreBool(const string json,const string name)
  { return EEA_LiveAuthorizationStoreField(json,name)=="true"; }

bool EEA_LiveAuthorizationStoreLoad(const string path,
                                    const string expected_config_version,
                                    const string expected_account_fingerprint,
                                    const string expected_broker_server,
                                    const string expected_broker_symbol,
                                    EEA_LiveAuthorizationContext &context,
                                    EEA_LiveAuthorizationDecision &decision,
                                    string &reason)
  {
   EEA_LiveAuthorizationDefaults(context);
   EEA_LiveAuthorizationDecisionDefaults(decision);
   reason="LIVE_AUTHORIZATION_FILE_UNAVAILABLE";
   string json;
   if(!EEA_LiveAuthorizationStoreRead(path,json)) return false;
   if(EEA_LiveAuthorizationStoreField(json,"schema_version")!="live-authorization-v1.0.0")
     { reason="LIVE_AUTHORIZATION_SCHEMA_INVALID"; return false; }

   context.explicit_human_approval=EEA_LiveAuthorizationStoreBool(json,"explicit_human_approval");
   context.account_identity_confirmed=EEA_LiveAuthorizationStoreBool(json,"account_identity_confirmed");
   context.risk_policy_confirmed=EEA_LiveAuthorizationStoreBool(json,"risk_policy_confirmed");
   context.broker_specs_confirmed=EEA_LiveAuthorizationStoreBool(json,"broker_specs_confirmed");
   context.retained_runtime_evidence=EEA_LiveAuthorizationStoreBool(json,"retained_runtime_evidence");
   context.execution_path_compiled=EEA_LiveAuthorizationStoreBool(json,"execution_path_compiled");
   context.demo_execution_evidence=EEA_LiveAuthorizationStoreBool(json,"demo_execution_evidence");
   context.restart_reconciliation_evidence=EEA_LiveAuthorizationStoreBool(json,"restart_reconciliation_evidence");
   context.emergency_stop_tested=EEA_LiveAuthorizationStoreBool(json,"emergency_stop_tested");
   context.rollback_tested=EEA_LiveAuthorizationStoreBool(json,"rollback_tested");
   context.ai_policy_confirmed=EEA_LiveAuthorizationStoreBool(json,"ai_policy_confirmed");
   context.news_policy_confirmed=EEA_LiveAuthorizationStoreBool(json,"news_policy_confirmed");
   context.limits_locked=EEA_LiveAuthorizationStoreBool(json,"limits_locked");
   context.config_backup_ready=EEA_LiveAuthorizationStoreBool(json,"config_backup_ready");
   context.monitoring_ready=EEA_LiveAuthorizationStoreBool(json,"monitoring_ready");
   context.no_unknown_state=EEA_LiveAuthorizationStoreBool(json,"no_unknown_state");
   context.no_open_blockers=EEA_LiveAuthorizationStoreBool(json,"no_open_blockers");
   context.live_account_intended=EEA_LiveAuthorizationStoreBool(json,"live_account_intended");
   context.authorization_id=EEA_LiveAuthorizationStoreField(json,"authorization_id");
   context.build_hash=EEA_LiveAuthorizationStoreField(json,"build_hash");
   context.account_fingerprint=EEA_LiveAuthorizationStoreField(json,"account_fingerprint");
   context.candidate_id=EEA_LiveAuthorizationStoreField(json,"candidate_id");
   context.intent_id=EEA_LiveAuthorizationStoreField(json,"intent_id");
   context.risk_policy_id=EEA_LiveAuthorizationStoreField(json,"risk_policy_id");
   context.config_version=EEA_LiveAuthorizationStoreField(json,"config_version");
   context.broker_server=EEA_LiveAuthorizationStoreField(json,"broker_server");
   context.account_mode=EEA_LiveAuthorizationStoreField(json,"account_mode");
   context.broker_symbol=EEA_LiveAuthorizationStoreField(json,"broker_symbol");
   context.authorization_valid_until_utc=StringToInteger(
      EEA_LiveAuthorizationStoreField(json,"authorization_valid_until_utc"));

   if(context.config_version!=expected_config_version ||
      context.account_fingerprint!=expected_account_fingerprint ||
      context.broker_server!=expected_broker_server ||
      (expected_broker_symbol!="" && context.broker_symbol!=expected_broker_symbol))
     { reason="LIVE_AUTHORIZATION_IDENTITY_MISMATCH"; return false; }
   if(!EEA_EvaluateLiveAuthorization(context,decision))
     { reason=decision.reason_code; return false; }
   reason="LIVE_AUTHORIZATION_LOADED";
   return true;
  }

#endif
