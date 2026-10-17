#ifndef ENTERPRISE_EA_REMOTE_MODE_RUNTIME_MQH
#define ENTERPRISE_EA_REMOTE_MODE_RUNTIME_MQH

#include "RemoteModeGate.mqh"
#include "../Storage/AtomicWriter.mqh"
#include "../Storage/AuditLog.mqh"
#include "../Storage/RiskLedgerStore.mqh"
#include "../Runtime/PendingOrderRuntime.mqh"

// G19 (design 2026-10-05-telegram-gateway-v1, REQ-019): the operator entry mode set from
// Telegram. State lives in current/operator_mode.json (all of EEA_RemoteModeState); the
// gateway drops commands in current/remote/commands and reads results from
// current/remote/results. Every decision is made by EEA_EvaluateRemoteModeCommand; the new
// state is adopted only after it was written (commit, then apply). PAUSED blocks new
// entries only: positions, pending orders and the Trade Manager keep running (O-12).
// T1: a missing state file starts RUNNING (nothing remote was ever issued);
// T2: an unreadable file or one bound to another account/config starts PAUSED.

#define EEA_REMOTE_MODE_DOCUMENT "operator-mode-v1.0.0"

// Signs (seconds > 0) or revokes (seconds == 0) the live session for an applied Telegram
// command. The EA shell passes EEA_RemoteSessionAction, which runs the panel's own checks.
typedef bool (*EEA_RemoteSessionHandler)(const long seconds,string &reason);

string EEA_RemoteModePath(const string root) { return root+"/current/operator_mode.json"; }
string EEA_RemoteCommandDir(const string root) { return root+"/current/remote/commands"; }
string EEA_RemoteResultDir(const string root) { return root+"/current/remote/results"; }

string EEA_RemoteModeName(const EEA_RemoteModeState &s) { return s.operator_paused ? "PAUSED_ENTRIES" : "RUNNING"; }

string EEA_RemoteModeToJson(const EEA_RemoteModeState &s,const string reason,const long now)
  {
   return "{\"document_version\":\""+EEA_REMOTE_MODE_DOCUMENT+"\",\"mode\":\""+EEA_RemoteModeName(s)+
      "\",\"operator_paused\":"+(s.operator_paused ? "true" : "false")+
      ",\"account_id\":\""+EEA_JsonEscape(s.account_id)+"\",\"config_version\":\""+EEA_JsonEscape(s.config_version)+
      "\",\"state_version\":"+IntegerToString(s.state_version)+
      ",\"last_gateway_sequence\":"+IntegerToString(s.last_gateway_sequence)+
      ",\"last_telegram_update_id\":"+IntegerToString(s.last_telegram_update_id)+
      ",\"last_command_id\":\""+EEA_JsonEscape(s.last_command_id)+"\",\"pending_nonce\":\""+EEA_JsonEscape(s.pending_nonce)+
      "\",\"pending_chat_id\":\""+EEA_JsonEscape(s.pending_chat_id)+"\",\"pending_user_id\":\""+EEA_JsonEscape(s.pending_user_id)+
      "\",\"pending_expires_at_utc\":"+IntegerToString((long)s.pending_expires_at_utc)+
      ",\"pending_action\":\""+EEA_JsonEscape(s.pending_action)+"\",\"pending_session_seconds\":"+
      IntegerToString(s.pending_session_seconds)+
      ",\"reason\":\""+EEA_JsonEscape(reason)+"\",\"written_at_utc\":"+IntegerToString(now)+"}";
  }

bool EEA_RemoteModeParse(const string json,EEA_RemoteModeState &s)
  {
   EEA_RemoteModeDefaults(s);
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_REMOTE_MODE_DOCUMENT) return false;
   const string paused=EEA_RiskLedgerField(json,"operator_paused");
   if(paused!="true" && paused!="false") return false;
   s.operator_paused=(paused=="true");
   s.account_id=EEA_RiskLedgerField(json,"account_id");
   s.config_version=EEA_RiskLedgerField(json,"config_version");
   s.state_version=StringToInteger(EEA_RiskLedgerField(json,"state_version"));
   s.last_gateway_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_gateway_sequence"));
   s.last_telegram_update_id=StringToInteger(EEA_RiskLedgerField(json,"last_telegram_update_id"));
   s.last_command_id=EEA_RiskLedgerField(json,"last_command_id");
   s.pending_nonce=EEA_RiskLedgerField(json,"pending_nonce");
   s.pending_chat_id=EEA_RiskLedgerField(json,"pending_chat_id");
   s.pending_user_id=EEA_RiskLedgerField(json,"pending_user_id");
   s.pending_expires_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"pending_expires_at_utc"));
   s.pending_action=EEA_RiskLedgerField(json,"pending_action");
   s.pending_session_seconds=StringToInteger(EEA_RiskLedgerField(json,"pending_session_seconds"));
   if(s.account_id=="" || s.config_version=="" || s.state_version<=0) return false;
   s.initialized=true;
   return true;
  }

bool EEA_RemoteModeSave(const EEA_RemoteModeState &s,const string root,const string reason)
  {
   FolderCreate(root+"/current",0);
   return EEA_WriteAtomicText(EEA_RemoteModePath(root),EEA_RemoteModeToJson(s,reason,(long)TimeGMT()));
  }

void EEA_RemoteModeAudit(CAuditLog &audit,const string event_type,const string entity,const string before,
                         const string after,const string reason,const string config_version,const string details)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),"",entity,before,after,
                 StringFind(event_type,"REJECTED")>=0 || StringFind(event_type,"FAIL")>=0 ? "DEGRADED" : "OK");
   event.config_version=config_version;
   EEAEvent_AddReason(event,reason);
   event.details_json=details;
   audit.Append(event,"EA_REMOTE_MODE");
  }

// Loads or bootstraps the mode for this account and config. Returns the state to use;
// reason names how it was obtained. Never returns RUNNING for a file it could not trust.
void EEA_RemoteModeLoad(EEA_RemoteModeState &s,const string root,const string account_id,const string config_version,
                        CAuditLog &audit,string &reason)
  {
   EEA_RemoteModeDefaults(s);                       // operator_paused=true until proven otherwise
   s.account_id=account_id; s.config_version=config_version;
   const string path=EEA_RemoteModePath(root);
   if(!FileIsExist(path,0))
     {
      s.initialized=true; s.operator_paused=false; s.state_version=1;
      reason=EEA_RemoteModeSave(s,root,"OPERATOR_MODE_BOOTSTRAP") ? "OPERATOR_MODE_BOOTSTRAP" : "OPERATOR_MODE_BOOTSTRAP_UNSAVED";
      EEA_RemoteModeAudit(audit,"OPERATOR_MODE_BOOTSTRAP","operator-mode","","RUNNING",reason,config_version,"{}");
      return;
     }
   string json;
   EEA_RemoteModeState loaded;
   if(!EEA_PendingReadText(path,json) || !EEA_RemoteModeParse(json,loaded))
      reason="OPERATOR_MODE_UNREADABLE";
   else if(loaded.account_id!=account_id || loaded.config_version!=config_version)
     {
      reason="OPERATOR_MODE_IDENTITY_MISMATCH";
      s.state_version=loaded.state_version;
      s.last_gateway_sequence=loaded.last_gateway_sequence;
      s.last_telegram_update_id=loaded.last_telegram_update_id;
      s.last_command_id=loaded.last_command_id;
     }
   else { s=loaded; reason="OPERATOR_MODE_LOADED"; return; }
   // T2: fail closed, rebound to this account/config so /pause and /resume work again.
   s.initialized=true; s.operator_paused=true;
   if(s.state_version<=0) s.state_version=1;
   EEA_RemoteClearPending(s);
   EEA_RemoteModeSave(s,root,reason);
   EEA_RemoteModeAudit(audit,"OPERATOR_MODE_FAIL_CLOSED","operator-mode","","PAUSED_ENTRIES",reason,config_version,"{}");
  }

// Command ids name result files: letters, digits, '-' and '_' only, 8..64 characters.
bool EEA_RemoteSafeId(const string id)
  {
   const int len=StringLen(id);
   if(len<8 || len>64) return false;
   for(int i=0;i<len;i++)
     {
      const ushort ch=StringGetCharacter(id,i);
      if(!((ch>='a' && ch<='z') || (ch>='A' && ch<='Z') || (ch>='0' && ch<='9') || ch=='-' || ch=='_')) return false;
     }
   return true;
  }

bool EEA_RemoteCommandParse(const string json,EEA_RemoteCommand &c)
  {
   c.schema_version=EEA_RiskLedgerField(json,"schema_version");
   c.command_id=EEA_RiskLedgerField(json,"command_id");
   c.action=EEA_RiskLedgerField(json,"action");
   c.role=EEA_RiskLedgerField(json,"role");
   c.chat_id=EEA_RiskLedgerField(json,"chat_id");
   c.user_id=EEA_RiskLedgerField(json,"user_id");
   c.telegram_update_id=StringToInteger(EEA_RiskLedgerField(json,"telegram_update_id"));
   c.gateway_sequence=StringToInteger(EEA_RiskLedgerField(json,"gateway_sequence"));
   c.account_id=EEA_RiskLedgerField(json,"account_id");
   c.config_version=EEA_RiskLedgerField(json,"config_version");
   c.expected_state_version=StringToInteger(EEA_RiskLedgerField(json,"expected_state_version"));
   c.issued_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"issued_at_utc"));
   c.expires_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"expires_at_utc"));
   c.confirmation_nonce=EEA_RiskLedgerField(json,"confirmation_nonce");
   c.nonce_expires_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"nonce_expires_at_utc"));
   c.session_seconds=StringToInteger(EEA_RiskLedgerField(json,"session_seconds"));
   c.private_chat_attested=(EEA_RiskLedgerField(json,"private_chat_attested")=="true");
   c.sender_authenticated=(EEA_RiskLedgerField(json,"sender_authenticated")=="true");
   c.source_authenticated=(EEA_RiskLedgerField(json,"source_authenticated")=="true");
   return EEA_RemoteSafeId(c.command_id);
  }

// One pass over the gateway's commands (oldest file name first). Each command gets one
// result file; the command file is removed afterwards. Returns commands handled.
int EEA_RemoteModeProcessInbox(EEA_RemoteModeState &s,const string root,const EEA_RemoteResumeEvidence &evidence,
                               EEA_RemoteSessionHandler session_handler,CAuditLog &audit,string &last_result)
  {
   string name;
   long handle=FileFindFirst(EEA_RemoteCommandDir(root)+"/*.json",name);
   if(handle==INVALID_HANDLE) return 0;
   string files[];
   int n=0;
   do { ArrayResize(files,n+1); files[n++]=name; } while(FileFindNext(handle,name));
   FileFindClose(handle);
   ArraySort(files);
   FolderCreate(EEA_RemoteResultDir(root),0);
   int handled=0;
   for(int f=0;f<n;f++)
     {
      const string path=EEA_RemoteCommandDir(root)+"/"+files[f];
      string json;
      EEA_RemoteCommand c;
      EEA_RemoteModeDecision d;
      EEA_RemoteModeDecisionDefaults(d);
      EEA_RemoteModeState next=s;
      const string before=EEA_RemoteModeName(s);
      bool applied=false;
      if(!EEA_PendingReadText(path,json) || !EEA_RemoteCommandParse(json,c))
        {
         c.command_id=StringSubstr(files[f],0,StringLen(files[f])-5);
         if(!EEA_RemoteSafeId(c.command_id)) c.command_id="malformed-"+IntegerToString((long)TimeGMT())+"-"+IntegerToString(f);
         c.action=""; d.reason_code="REMOTE_COMMAND_MALFORMED";
        }
      else
        {
         EEA_EvaluateRemoteModeCommand(s,c,evidence,TimeGMT(),next,d);
         if(d.status=="VALIDATED_PENDING_COMMIT")
           {
            // Commit, then apply: a failed write keeps the old state authoritative.
            if(EEA_RemoteModeSave(next,root,d.reason_code)) { s=next; applied=true; }
            else d.reason_code="REMOTE_STATE_COMMIT_FAILED";
           }
         // The code is spent once committed; a failed sign or revoke is reported, never retried.
         if(applied && (d.session_sign_seconds>0 || d.session_revoke))
           {
            string session_reason="";
            if(!session_handler(d.session_revoke ? 0 : d.session_sign_seconds,session_reason))
              { applied=false; d.status="REJECTED"; }
            d.reason_code=(session_reason=="" ? d.reason_code : session_reason);
           }
        }
      const bool accepted=(d.status=="VALIDATED_PENDING_COMMIT" || d.status=="DUPLICATE_IGNORED");
      const string after=EEA_RemoteModeName(s);
      const string result="{\"command_id\":\""+EEA_JsonEscape(c.command_id)+"\",\"action\":\""+EEA_JsonEscape(c.action)+
         "\",\"accepted\":"+(accepted ? "true" : "false")+",\"applied\":"+(applied ? "true" : "false")+
         ",\"status\":\""+d.status+"\",\"state_before\":\""+before+"\",\"state_after\":\""+after+
         "\",\"reason_codes\":[\""+d.reason_code+"\"],\"ea_state_version\":"+IntegerToString(s.state_version)+
         ",\"observed_at_utc\":"+IntegerToString((long)TimeGMT())+"}";
      EEA_WriteAtomicText(EEA_RemoteResultDir(root)+"/"+c.command_id+".json",result);
      EEA_RemoteModeAudit(audit,applied || d.status=="DUPLICATE_IGNORED" ? "REMOTE_COMMAND_APPLIED" : "REMOTE_COMMAND_REJECTED",
                          c.command_id,before,after,d.reason_code,s.config_version,
                          "{\"action\":\""+EEA_JsonEscape(c.action)+"\",\"status\":\""+d.status+"\"}");
      FileDelete(path,0);
      last_result=c.action+" "+(applied ? "APPLIED" : d.status)+": "+d.reason_code;
      handled++;
     }
   return handled;
  }

#endif
