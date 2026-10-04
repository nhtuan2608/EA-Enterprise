#ifndef ENTERPRISE_EA_EXECUTION_RECOVERY_STORE_MQH
#define ENTERPRISE_EA_EXECUTION_RECOVERY_STORE_MQH

#include "AtomicWriter.mqh"
#include "../Runtime/ExecutionContracts.mqh"

string EEA_ExecutionRecoveryField(const string json,const string name)
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

bool EEA_ExecutionRecoveryRead(const string path,string &json)
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

bool EEA_ExecutionRecoveryLoad(const string root,EEA_ExecutionResult &result,bool &found)
  {
   EEA_ExecutionResultDefaults(result); found=false;
   string json;
   if(!EEA_ExecutionRecoveryRead(root+"/current/execution_result.json",json)) return true;
   if(EEA_ExecutionRecoveryField(json,"document_version")!="execution-result-v0.1.0") return false;
   result.schema_version=EEA_ExecutionRecoveryField(json,"schema_version");
   result.intent_id=EEA_ExecutionRecoveryField(json,"intent_id");
   result.correlation_id=EEA_ExecutionRecoveryField(json,"correlation_id");
   result.idempotency_key=EEA_ExecutionRecoveryField(json,"idempotency_key");
   result.risk_decision_id=EEA_ExecutionRecoveryField(json,"risk_decision_id");
   result.authorization_id=EEA_ExecutionRecoveryField(json,"authorization_id");
   result.build_hash=EEA_ExecutionRecoveryField(json,"build_hash");
   result.request_sent=EEA_ExecutionRecoveryField(json,"request_sent")=="true";
   result.request_retcode=EEA_ExecutionRecoveryField(json,"request_retcode");
   result.request_ticket=StringToInteger(EEA_ExecutionRecoveryField(json,"request_ticket"));
   result.request_ticket_kind=EEA_ExecutionRecoveryField(json,"request_ticket_kind");
   result.confirmation_state=EEA_ExecutionRecoveryField(json,"confirmation_state");
   result.reason_code=EEA_ExecutionRecoveryField(json,"reason_code");
   found=true;
   return result.intent_id!="" && result.idempotency_key!="" && result.confirmation_state!="";
  }

// Only an entry whose outcome is unknown blocks new entries. A pending cancel or a
// Trade Manager action (modify/close) targets an order or position that may be gone
// once it succeeded, so it is reconciled by its own runtime and never by this gate.
bool EEA_ExecutionRecoveryIsEntryKey(const string idempotency_key)
  {
   return StringFind(idempotency_key,"-cancel-")<0 && StringFind(idempotency_key,"manage-")!=0;
  }

bool EEA_ExecutionRecoveryNeedsReconciliation(const EEA_ExecutionResult &result)
  {
   return result.request_sent && result.confirmation_state=="EXECUTION_UNKNOWN" &&
          result.request_ticket>0 && result.request_ticket_kind!="" &&
          EEA_ExecutionRecoveryIsEntryKey(result.idempotency_key);
  }

#endif
