#ifndef ENTERPRISE_EA_BOT_STATE_MQH
#define ENTERPRISE_EA_BOT_STATE_MQH

// Bots host (design docs/superpowers/specs/2026-10-16-bots-host-design.md): the registry of the
// strategies the EA runs and their Active flags. A flag only gates NEW entries; positions and
// pending orders already open keep their management (decision 16/10/2026).
// State lives in current/bots_state.json, bound to the account and config:
//   missing file      -> Active flags from the inputs, file written (BOTS_STATE_BOOTSTRAP)
//   unreadable / other account or config -> every bot Inactive (fail closed, BOTS_STATE_FAIL_CLOSED)
// A change is committed (file written) before it is adopted.

#include "../Storage/AtomicWriter.mqh"
#include "../Storage/AuditLog.mqh"
#include "../Storage/RiskLedgerStore.mqh"
#include "../Runtime/PendingOrderRuntime.mqh"

#define EEA_BOTS_STATE_DOCUMENT "bots-state-v1.0.0"
#define EEA_BOT_COUNT 4
#define EEA_BOT_S07 0
#define EEA_BOT_VHEDGE 1
#define EEA_BOT_XRT 2
#define EEA_BOT_CTXLIMIT 3

enum EEA_BotModeInput { BOT_OFF=0, BOT_SHADOW=1, BOT_LIVE=2 };

string EEA_BotCode(const int id)
  {
   switch(id)
     {
      case EEA_BOT_S07:      return "S07";
      case EEA_BOT_VHEDGE:   return "VHEDGE";
      case EEA_BOT_XRT:      return "XRT";
      case EEA_BOT_CTXLIMIT: return "CTXLIMIT";
     }
   return "";
  }

string EEA_BotTitle(const int id)
  {
   switch(id)
     {
      case EEA_BOT_S07:      return "S07";
      case EEA_BOT_VHEDGE:   return "VHedge G119";
      case EEA_BOT_XRT:      return "XauRegime";
      case EEA_BOT_CTXLIMIT: return "CtxLimit";
     }
   return "";
  }

string EEA_BotModeName(const EEA_BotModeInput m) { return m==BOT_LIVE ? "LIVE" : (m==BOT_SHADOW ? "SHADOW" : "OFF"); }

// Accepts the code, the title or a loose alias ("vhedge", "g119", "xau", "ctx", "s07") -> id, or -1.
int EEA_BotFind(const string name)
  {
   string s=name;
   StringToUpper(s);
   StringReplace(s," ","");
   StringReplace(s,"_","");
   StringReplace(s,"-","");
   if(s=="") return -1;
   for(int i=0;i<EEA_BOT_COUNT;i++)
     {
      string t=EEA_BotTitle(i);
      StringToUpper(t);
      StringReplace(t," ","");
      if(s==EEA_BotCode(i) || s==t) return i;
     }
   if(StringFind(s,"VHEDGE")>=0 || StringFind(s,"HEDGE")>=0 || s=="G119" || s=="VH") return EEA_BOT_VHEDGE;
   if(StringFind(s,"XAUREGIME")>=0 || StringFind(s,"REGIME")>=0 || s=="XRT") return EEA_BOT_XRT;
   if(StringFind(s,"CTX")>=0) return EEA_BOT_CTXLIMIT;
   if(StringFind(s,"S07")>=0) return EEA_BOT_S07;
   return -1;
  }

struct EEA_BotsState
  {
   bool   loaded;
   bool   active[EEA_BOT_COUNT];
   string account_id;
   string config_version;
   long   state_version;
   long   last_gateway_sequence;
   long   last_mcp_sequence;      // MCP commands (Claude / scripts over the data folder) have their own counter
   string last_command_id;
   int    pending_bot;            // a Telegram enable waiting for /confirm (-1 = none)
   string pending_nonce;
   string pending_chat_id;
   string pending_user_id;
   long   pending_expires_at_utc;
   string reason;
  };

EEA_BotsState g_bots_state;
bool          g_bots_layer_enabled=false;   // InpBotsEnabled; when false the S07 flag is not consulted

void EEA_BotsStateDefaults(EEA_BotsState &s)
  {
   s.loaded=false;
   for(int i=0;i<EEA_BOT_COUNT;i++) s.active[i]=false;
   s.account_id=""; s.config_version=""; s.state_version=0; s.last_gateway_sequence=0; s.last_mcp_sequence=0; s.last_command_id="";
   s.pending_bot=-1; s.pending_nonce=""; s.pending_chat_id=""; s.pending_user_id=""; s.pending_expires_at_utc=0;
   s.reason="";
  }

void EEA_BotsClearPending(EEA_BotsState &s)
  { s.pending_bot=-1; s.pending_nonce=""; s.pending_chat_id=""; s.pending_user_id=""; s.pending_expires_at_utc=0; }

// S07 is gated only when the bots layer runs (otherwise EnterpriseEA behaves as before).
bool EEA_BotS07EntriesAllowed()
  {
   return !g_bots_layer_enabled || (g_bots_state.loaded && g_bots_state.active[EEA_BOT_S07]);
  }

// Fail closed: an unloaded state never reports a bot Active.
bool EEA_BotActive(const int id)
  {
   if(id<0 || id>=EEA_BOT_COUNT) return false;
   return g_bots_state.loaded && g_bots_state.active[id];
  }

string EEA_BotsStatePath(const string root) { return root+"/current/bots_state.json"; }

string EEA_BotsStateToJson(const EEA_BotsState &s,const string reason,const long now)
  {
   string bots="";
   for(int i=0;i<EEA_BOT_COUNT;i++)
      bots+=",\""+EEA_BotCode(i)+"_active\":"+(s.active[i] ? "true" : "false");
   return "{\"document_version\":\""+EEA_BOTS_STATE_DOCUMENT+"\",\"account_id\":\""+EEA_JsonEscape(s.account_id)+
      "\",\"config_version\":\""+EEA_JsonEscape(s.config_version)+"\",\"state_version\":"+IntegerToString(s.state_version)+
      bots+",\"last_gateway_sequence\":"+IntegerToString(s.last_gateway_sequence)+
      ",\"last_mcp_sequence\":"+IntegerToString(s.last_mcp_sequence)+
      ",\"last_command_id\":\""+EEA_JsonEscape(s.last_command_id)+"\",\"pending_bot\":\""+
      (s.pending_bot>=0 ? EEA_BotCode(s.pending_bot) : "")+"\",\"pending_nonce\":\""+EEA_JsonEscape(s.pending_nonce)+
      "\",\"pending_chat_id\":\""+EEA_JsonEscape(s.pending_chat_id)+"\",\"pending_user_id\":\""+EEA_JsonEscape(s.pending_user_id)+
      "\",\"pending_expires_at_utc\":"+IntegerToString(s.pending_expires_at_utc)+",\"reason\":\""+EEA_JsonEscape(reason)+
      "\",\"written_at_utc\":"+IntegerToString(now)+"}";
  }

bool EEA_BotsStateParse(const string json,EEA_BotsState &s)
  {
   EEA_BotsStateDefaults(s);
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_BOTS_STATE_DOCUMENT) return false;
   for(int i=0;i<EEA_BOT_COUNT;i++)
     {
      const string v=EEA_RiskLedgerField(json,EEA_BotCode(i)+"_active");
      if(v!="true" && v!="false") return false;
      s.active[i]=(v=="true");
     }
   s.account_id=EEA_RiskLedgerField(json,"account_id");
   s.config_version=EEA_RiskLedgerField(json,"config_version");
   s.state_version=StringToInteger(EEA_RiskLedgerField(json,"state_version"));
   s.last_gateway_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_gateway_sequence"));
   s.last_mcp_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_mcp_sequence"));   // absent in older files: 0
   s.last_command_id=EEA_RiskLedgerField(json,"last_command_id");
   s.pending_bot=EEA_BotFind(EEA_RiskLedgerField(json,"pending_bot"));
   s.pending_nonce=EEA_RiskLedgerField(json,"pending_nonce");
   s.pending_chat_id=EEA_RiskLedgerField(json,"pending_chat_id");
   s.pending_user_id=EEA_RiskLedgerField(json,"pending_user_id");
   s.pending_expires_at_utc=StringToInteger(EEA_RiskLedgerField(json,"pending_expires_at_utc"));
   if(s.account_id=="" || s.config_version=="" || s.state_version<=0) return false;
   s.loaded=true;
   return true;
  }

bool EEA_BotsStateSave(const EEA_BotsState &s,const string root,const string reason)
  {
   FolderCreate(root+"/current",0);
   return EEA_WriteAtomicText(EEA_BotsStatePath(root),EEA_BotsStateToJson(s,reason,(long)TimeGMT()));
  }

void EEA_BotsAudit(CAuditLog &audit,const string event_type,const string entity,const string before,const string after,
                   const string reason,const string config_version,const string details)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),"",entity,before,after,
                 StringFind(event_type,"REJECTED")>=0 || StringFind(event_type,"FAIL")>=0 ? "DEGRADED" : "OK");
   event.config_version=config_version;
   EEAEvent_AddReason(event,reason);
   event.details_json=details;
   audit.Append(event,"EA_BOTS");
  }

string EEA_BotsActiveText(const EEA_BotsState &s)
  {
   string t="";
   for(int i=0;i<EEA_BOT_COUNT;i++) t+=(i>0 ? "," : "")+EEA_BotCode(i)+"="+(s.active[i] ? "ON" : "OFF");
   return t;
  }

// Loads or bootstraps the flags for this account and config. defaults[] = the input flags.
void EEA_BotsStateLoad(EEA_BotsState &s,const string root,const string account_id,const string config_version,
                       const bool &defaults[],CAuditLog &audit)
  {
   EEA_BotsStateDefaults(s);
   s.account_id=account_id; s.config_version=config_version;
   const string path=EEA_BotsStatePath(root);
   if(!FileIsExist(path,0))
     {
      for(int i=0;i<EEA_BOT_COUNT;i++) s.active[i]=defaults[i];
      s.state_version=1; s.loaded=true;
      s.reason=EEA_BotsStateSave(s,root,"BOTS_STATE_BOOTSTRAP") ? "BOTS_STATE_BOOTSTRAP" : "BOTS_STATE_BOOTSTRAP_UNSAVED";
      EEA_BotsAudit(audit,"BOTS_STATE_BOOTSTRAP","bots-state","",EEA_BotsActiveText(s),s.reason,config_version,"{}");
      return;
     }
   string json;
   EEA_BotsState loaded;
   string reason="";
   if(!EEA_PendingReadText(path,json) || !EEA_BotsStateParse(json,loaded)) reason="BOTS_STATE_UNREADABLE";
   else if(loaded.account_id!=account_id || loaded.config_version!=config_version)
     {
      reason="BOTS_STATE_IDENTITY_MISMATCH";
      s.state_version=loaded.state_version;
      s.last_gateway_sequence=loaded.last_gateway_sequence;
      s.last_mcp_sequence=loaded.last_mcp_sequence;
      s.last_command_id=loaded.last_command_id;
     }
   else { s=loaded; s.reason="BOTS_STATE_LOADED"; return; }
   for(int i=0;i<EEA_BOT_COUNT;i++) s.active[i]=false;            // fail closed
   if(s.state_version<=0) s.state_version=1;
   EEA_BotsClearPending(s);
   s.loaded=true;
   s.reason=reason;
   EEA_BotsStateSave(s,root,reason);
   EEA_BotsAudit(audit,"BOTS_STATE_FAIL_CLOSED","bots-state","",EEA_BotsActiveText(s),reason,config_version,"{}");
  }

// Commit, then apply. source: PANEL | TELEGRAM | MCP. Returns false when the write failed (flag unchanged).
bool EEA_BotsSetActive(EEA_BotsState &s,const int id,const bool active,const string root,const string source,
                       const string detail,CAuditLog &audit,string &reason)
  {
   if(!s.loaded) { reason="BOTS_STATE_NOT_LOADED"; return false; }
   if(id<0 || id>=EEA_BOT_COUNT) { reason="BOT_UNKNOWN"; return false; }
   EEA_BotsState next=s;
   next.active[id]=active;
   next.state_version=s.state_version+1;
   if(next.pending_bot==id) EEA_BotsClearPending(next);
   reason=(active ? "BOT_ENABLED_" : "BOT_DISABLED_")+source;
   if(!EEA_BotsStateSave(next,root,reason)) { reason="BOTS_STATE_COMMIT_FAILED"; return false; }
   const string before=(s.active[id] ? "ACTIVE" : "INACTIVE");
   s=next;
   s.reason=reason;
   EEA_BotsAudit(audit,active ? "BOT_ENABLED" : "BOT_DISABLED",EEA_BotCode(id),before,active ? "ACTIVE" : "INACTIVE",reason,
                 s.config_version,"{\"source\":\""+source+"\",\"detail\":\""+EEA_JsonEscape(detail)+"\"}");
   return true;
  }

#endif
