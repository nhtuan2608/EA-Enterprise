#ifndef ENTERPRISE_EA_CONTROLLER_STATE_STORE_MQH
#define ENTERPRISE_EA_CONTROLLER_STATE_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Runtime\ExecutionControllerState.mqh"

enum EEA_ControllerStateLoadStatus
  {
   EEA_CONTROLLER_STATE_MISSING=0,
   EEA_CONTROLLER_STATE_CORRUPT=1,
   EEA_CONTROLLER_STATE_IDENTITY_MISMATCH=2,
   EEA_CONTROLLER_STATE_SCOPE_MISMATCH=3,
   EEA_CONTROLLER_STATE_REVISION_ROLLBACK=4,
   EEA_CONTROLLER_STATE_STALE=5,
   EEA_CONTROLLER_STATE_LOADED=6
  };

string EEA_ControllerStateStoreJsonEscape(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort ch=StringGetCharacter(value,i);
      if(ch==34) out+="\\\"";
      else if(ch==92) out+="\\\\";
      else if(ch==10) out+="\\n";
      else if(ch==13) out+="\\r";
      else if(ch==9) out+="\\t";
      else out+=ShortToString(ch);
     }
   return out;
  }

string EEA_ControllerStateStoreToJson(const EEA_ExecutionControllerState &state)
  {
   return "{\"schema_version\":\"controller-state-v0.1.0\",\"document_version\":\"execution-controller-state-v1.0.0\",\"config_version\":\""+
      EEA_ControllerStateStoreJsonEscape(state.config_version)+"\",\"account_fingerprint\":\""+
      EEA_ControllerStateStoreJsonEscape(state.account_fingerprint)+"\",\"broker_server\":\""+
      EEA_ControllerStateStoreJsonEscape(state.broker_server)+"\",\"revision\":"+IntegerToString(state.revision)+
      ",\"kill_active\":"+(state.kill_active ? "true" : "false")+",\"operator_id\":\""+
      EEA_ControllerStateStoreJsonEscape(state.operator_id)+"\",\"reference\":\""+EEA_ControllerStateStoreJsonEscape(state.reference)+
      "\",\"valid_from_utc\":"+IntegerToString((long)state.valid_from_utc)+
      ",\"valid_until_utc\":"+IntegerToString((long)state.valid_until_utc)+
      ",\"operation_scope\":\""+EEA_ControllerStateStoreJsonEscape(state.operation_scope)+"\"}";
  }

bool EEA_ControllerStateStoreReadFile(const string path,string &json)
  {
   json="";
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE)
      return false;
   ulong size=FileSize(handle);
   if(size==0 || size>65536)
     {
      FileClose(handle);
      return false;
     }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size)
     {
      FileClose(handle);
      return false;
     }
   uint count=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(count!=(uint)size)
      return false;
   json=CharArrayToString(bytes,0,(int)count,CP_UTF8);
   return StringLen(json)>0;
  }

bool EEA_ControllerStateStoreTakeLiteral(const string json,int &cursor,const string literal)
  {
   int length=StringLen(literal);
   if(cursor<0 || cursor+length>StringLen(json) || StringSubstr(json,cursor,length)!=literal)
      return false;
   cursor+=length;
   return true;
  }

bool EEA_ControllerStateStoreReadJsonString(const string json,int &cursor,string &value)
  {
   value="";
   if(cursor>=StringLen(json) || StringGetCharacter(json,cursor)!=34)
      return false;
   cursor++;
   while(cursor<StringLen(json))
     {
      ushort ch=StringGetCharacter(json,cursor++);
      if(ch==34)
         return true;
      if(ch<32)
         return false;
      if(ch!=92)
        {
         value+=ShortToString(ch);
         continue;
        }
      if(cursor>=StringLen(json))
         return false;
      ushort escaped=StringGetCharacter(json,cursor++);
      if(escaped==34 || escaped==92)
         value+=ShortToString(escaped);
      else if(escaped=='n')
         value+="\n";
      else if(escaped=='r')
         value+="\r";
      else if(escaped=='t')
         value+="\t";
      else
         return false;
     }
   return false;
  }

bool EEA_ControllerStateStoreReadPositiveLong(const string json,int &cursor,long &value)
  {
   int start=cursor;
   while(cursor<StringLen(json))
     {
      ushort ch=StringGetCharacter(json,cursor);
      if(ch<'0' || ch>'9')
         break;
      cursor++;
     }
   int length=cursor-start;
   if(length<=0 || (length>1 && StringGetCharacter(json,start)=='0'))
      return false;
   value=StringToInteger(StringSubstr(json,start,length));
   return value>0;
  }

bool EEA_ControllerStateStoreReadBoolean(const string json,int &cursor,bool &value)
  {
   if(EEA_ControllerStateStoreTakeLiteral(json,cursor,"true"))
     {
      value=true;
      return true;
     }
   if(EEA_ControllerStateStoreTakeLiteral(json,cursor,"false"))
     {
      value=false;
      return true;
     }
   return false;
  }

bool EEA_ControllerStateStoreReadStringField(const string json,int &cursor,const string name,string &value)
  {
   return EEA_ControllerStateStoreTakeLiteral(json,cursor,"\""+name+"\":") &&
          EEA_ControllerStateStoreReadJsonString(json,cursor,value);
  }

bool EEA_ControllerStateStoreReadLongField(const string json,int &cursor,const string name,long &value)
  {
   return EEA_ControllerStateStoreTakeLiteral(json,cursor,"\""+name+"\":") &&
          EEA_ControllerStateStoreReadPositiveLong(json,cursor,value);
  }

bool EEA_ControllerStateStoreParseDocument(const string json,EEA_ExecutionControllerState &state)
  {
   EEA_ExecutionControllerStateDefaults(state);
   int cursor=0;
   string schema_version="",document_version="";
   long revision=0,valid_from=0,valid_until=0;
   if(!EEA_ControllerStateStoreTakeLiteral(json,cursor,"{") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"schema_version",schema_version) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"document_version",document_version) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"config_version",state.config_version) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"account_fingerprint",state.account_fingerprint) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"broker_server",state.broker_server) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadLongField(json,cursor,"revision",revision) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,"\"kill_active\":") ||
      !EEA_ControllerStateStoreReadBoolean(json,cursor,state.kill_active) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"operator_id",state.operator_id) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"reference",state.reference) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadLongField(json,cursor,"valid_from_utc",valid_from) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadLongField(json,cursor,"valid_until_utc",valid_until) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,",") ||
      !EEA_ControllerStateStoreReadStringField(json,cursor,"operation_scope",state.operation_scope) ||
      !EEA_ControllerStateStoreTakeLiteral(json,cursor,"}") || cursor!=StringLen(json))
     {
      EEA_ExecutionControllerStateDefaults(state);
      return false;
     }
   if(schema_version!="controller-state-v0.1.0" || document_version!="execution-controller-state-v1.0.0")
     {
      EEA_ExecutionControllerStateDefaults(state);
      return false;
     }
   state.revision=revision;
   state.valid_from_utc=(datetime)valid_from;
   state.valid_until_utc=(datetime)valid_until;
   return true;
  }

bool EEA_ControllerStateStoreReadExisting(const string path,const string config_version,
                                          const string account_fingerprint,const string broker_server,
                                          EEA_ExecutionControllerState &state,bool &exists)
  {
   EEA_ExecutionControllerStateDefaults(state);
   exists=FileIsExist(path,0);
   if(!exists)
      return true;
   string json="";
   if(!EEA_ControllerStateStoreReadFile(path,json) ||
      !EEA_ControllerStateStoreParseDocument(json,state) ||
      !EEA_ExecutionControllerIdentityMatches(state,config_version,account_fingerprint,broker_server))
     {
      EEA_ExecutionControllerStateDefaults(state);
      return false;
     }
   return true;
  }

bool EEA_ControllerStateStoreWrite(const string path,const EEA_ExecutionControllerState &state,
                                   const string config_version,const string account_fingerprint,
                                   const string broker_server,const datetime now_utc)
  {
   if(!EEA_ExecutionControllerStateValid(state,now_utc) ||
      !EEA_ExecutionControllerIdentityMatches(state,config_version,account_fingerprint,broker_server))
      return false;
   EEA_ExecutionControllerState existing;
   bool exists=false;
   if(!EEA_ControllerStateStoreReadExisting(path,config_version,account_fingerprint,broker_server,existing,exists))
      return false;
   if(exists && state.revision<=existing.revision)
      return false;
   string json=EEA_ControllerStateStoreToJson(state);
   return EEA_WriteAtomicText(path,json);
  }

EEA_ControllerStateLoadStatus EEA_ControllerStateStoreLoad(const string path,
                                                            const string expected_config_version,
                                                            const string expected_account_fingerprint,
                                                            const string expected_broker_server,
                                                            const string expected_scope,
                                                            const long minimum_revision,
                                                            const datetime now_utc,
                                                            EEA_ExecutionControllerState &state)
  {
   EEA_ExecutionControllerStateDefaults(state);
   if(!EEA_ExecutionControllerOpaqueIdentifierValid(expected_config_version) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(expected_account_fingerprint) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(expected_broker_server) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(expected_scope) || minimum_revision<=0 || now_utc<=0)
      return EEA_CONTROLLER_STATE_CORRUPT;
   if(!FileIsExist(path,0))
      return EEA_CONTROLLER_STATE_MISSING;
   string json="";
   if(!EEA_ControllerStateStoreReadFile(path,json) ||
      !EEA_ControllerStateStoreParseDocument(json,state))
     {
      EEA_ExecutionControllerStateDefaults(state);
      return EEA_CONTROLLER_STATE_CORRUPT;
     }
   if(state.config_version!=expected_config_version ||
      state.account_fingerprint!=expected_account_fingerprint ||
      state.broker_server!=expected_broker_server)
     {
      EEA_ExecutionControllerStateDefaults(state);
      return EEA_CONTROLLER_STATE_IDENTITY_MISMATCH;
     }
   if(state.operation_scope!=expected_scope &&
      !EEA_ExecutionControllerScopeCovers(state.operation_scope,expected_scope))
     {
      EEA_ExecutionControllerStateDefaults(state);
      return EEA_CONTROLLER_STATE_SCOPE_MISMATCH;
     }
   if(state.revision<minimum_revision)
     {
      EEA_ExecutionControllerStateDefaults(state);
      return EEA_CONTROLLER_STATE_REVISION_ROLLBACK;
     }
   if(!EEA_ExecutionControllerStateValid(state,now_utc))
     {
      EEA_ExecutionControllerStateDefaults(state);
      return EEA_CONTROLLER_STATE_STALE;
     }
   return EEA_CONTROLLER_STATE_LOADED;
  }

#endif
