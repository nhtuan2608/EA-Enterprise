#ifndef ENTERPRISE_EA_BOT_HOST_MQH
#define ENTERPRISE_EA_BOT_HOST_MQH

// Bots host: runs the bot modules next to the EnterpriseEA engines, keeps their Active flags, takes
// Telegram on/off commands and publishes current/bots_status.json (for /bots and the panel).
// S07 is EnterpriseEA's own engine: the host only owns its Active flag (checked in EEA_S07EntryAllowed)
// and reports it; the shell fills g_bots_host.s07_* each timer.
// Telegram commands (current/remote/bot_commands/*.json, results in current/remote/results):
//   BOT_DISABLE          applied at once
//   BOT_REQUEST_ENABLE   stores a one-time nonce (<= 120 s) for that bot, user and chat
//   BOT_CONFIRM_ENABLE   same nonce, user, chat, before expiry -> Active
// Every command: schema, OPERATOR role, authenticated private chat, this account and config, TTL, a
// gateway sequence above the last one (no replay). A disable never needs a confirmation.

#include "BotState.mqh"
#include "PortfolioGuard.mqh"
#include "VHedgeBot.mqh"
#include "XrtBot.mqh"
#include "CtxLimitBot.mqh"

#define EEA_BOT_COMMAND_VERSION "bot-command-v1.0.0"
#define EEA_BOTS_STATUS_DOCUMENT "bots-status-v1.0.0"
#define EEA_BOT_MAX_NONCE_SECONDS 120

struct EEA_BotsHost
  {
   bool   initialized;
   string root;
   string symbol;
   bool   defaults[EEA_BOT_COUNT];
   EEA_BotModeInput modes[EEA_BOT_COUNT];
   long   magics[EEA_BOT_COUNT];
   // S07 (EnterpriseEA engine), filled by the shell
   string s07_mode;
   string s07_status;
   string last_command;
   string status_text[EEA_BOT_COUNT];
  };

EEA_BotsHost g_bots_host;
CVHedgeBot   g_bot_vhedge;
CXrtBot      g_bot_xrt;
CCtxLimitBot g_bot_ctx;

void EEA_BotsHostDefaults(EEA_BotsHost &h)
  {
   h.initialized=false; h.root=""; h.symbol=""; h.s07_mode="OFF"; h.s07_status=""; h.last_command="";
   for(int i=0;i<EEA_BOT_COUNT;i++) { h.defaults[i]=false; h.modes[i]=BOT_OFF; h.magics[i]=0; h.status_text[i]=""; }
  }

// ------------------------------------------------------------------------------------------------------ stats
// Open positions / pending orders, floating P/L and today's closed P/L (server day) of one magic.
void EEA_BotMagicStats(const long magic,const string symbol,int &open_count,double &floating,double &today)
  {
   open_count=0; floating=0.0; today=0.0;
   if(magic<=0) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong t=PositionGetTicket(i);
      if(t==0 || !PositionSelectByTicket(t) || PositionGetInteger(POSITION_MAGIC)!=magic) continue;
      if(symbol!="" && PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      open_count++;
      floating+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong t=OrderGetTicket(i);
      if(t>0 && OrderSelect(t) && OrderGetInteger(ORDER_MAGIC)==magic && (symbol=="" || OrderGetString(ORDER_SYMBOL)==symbol))
         open_count++;
     }
   const datetime day=(datetime)((long)(TimeTradeServer()/86400)*86400);
   if(!HistorySelect(day,TimeTradeServer()+60)) return;
   for(int i=HistoryDealsTotal()-1;i>=0;i--)
     {
      const ulong d=HistoryDealGetTicket(i);
      if(d==0 || HistoryDealGetInteger(d,DEAL_MAGIC)!=magic) continue;
      if(symbol!="" && HistoryDealGetString(d,DEAL_SYMBOL)!=symbol) continue;
      today+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_COMMISSION);
     }
  }

string EEA_BotModeText(const int id)
  {
   if(id==EEA_BOT_S07) return g_bots_host.s07_mode;
   if(id==EEA_BOT_VHEDGE) return g_bot_vhedge.ModeText();
   if(id==EEA_BOT_XRT) return g_bot_xrt.ModeText();
   if(id==EEA_BOT_CTXLIMIT) return g_bot_ctx.ModeText();
   return EEA_BotModeName(g_bots_host.modes[id]);
  }

string EEA_BotStatusText(const int id)
  {
   if(id==EEA_BOT_S07) return g_bots_host.s07_status;
   if(id==EEA_BOT_VHEDGE) return g_bot_vhedge.StatusText();
   if(id==EEA_BOT_XRT) return g_bot_xrt.StatusText();
   if(id==EEA_BOT_CTXLIMIT) return g_bot_ctx.StatusText();
   return "";
  }

// ------------------------------------------------------------------------------------------------------ lifecycle
void EEA_BotsHostInit(const string root,const string symbol,const bool &defaults[],const EEA_BotModeInput &modes[],
                      const long &magics[],const VHedgeBotParams &vhedge,const XrtBotParams &xrt,
                      const CtxLimitBotParams &ctx)
  {
   EEA_BotsHostDefaults(g_bots_host);
   EEA_BotsStateDefaults(g_bots_state);
   EEA_BotGuardDefaults(g_bot_guard);
   g_bots_host.root=root;
   g_bots_host.symbol=(symbol=="" ? _Symbol : symbol);
   for(int i=0;i<EEA_BOT_COUNT;i++)
     { g_bots_host.defaults[i]=defaults[i]; g_bots_host.modes[i]=modes[i]; g_bots_host.magics[i]=magics[i]; }
   if(!SymbolSelect(g_bots_host.symbol,true))
      PrintFormat("BotsHost: symbol %s is not available; bots stay idle",g_bots_host.symbol);
   g_bot_vhedge.Init(vhedge,g_bots_host.symbol,root);
   g_bot_xrt.Init(xrt,g_bots_host.symbol,root);
   g_bot_ctx.Init(ctx,g_bots_host.symbol,root);
   g_bots_host.initialized=true;
  }

void EEA_BotsHostDeinit()
  {
   if(!g_bots_host.initialized) return;
   g_bot_vhedge.Deinit();
   g_bot_xrt.Deinit();
   g_bot_ctx.Deinit();
  }

// Every tick: bot management and new-bar signals. Never runs before the state was loaded.
void EEA_BotsHostTick()
  {
   if(!g_bots_host.initialized || !g_bots_state.loaded) return;
   EEA_BotGuardRollDay(g_bot_guard);
   g_bot_vhedge.OnTick();
   g_bot_xrt.OnTick();
   g_bot_ctx.OnTick();
  }

// ------------------------------------------------------------------------------------------------------ remote
string EEA_BotCommandDir(const string root) { return root+"/current/remote/bot_commands"; }

bool EEA_BotSafeId(const string id)
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

// Pure decision for one command. Returns the reason code; applied state changes go through EEA_BotsSetActive.
string EEA_BotCommandEvaluate(const EEA_BotsState &s,const string json,const long now,string &action,int &bot,
                              string &nonce,string &chat,string &user,long &sequence,string &command_id)
  {
   command_id=EEA_RiskLedgerField(json,"command_id");
   action=EEA_RiskLedgerField(json,"action");
   bot=EEA_BotFind(EEA_RiskLedgerField(json,"bot"));
   nonce=EEA_RiskLedgerField(json,"confirmation_nonce");
   chat=EEA_RiskLedgerField(json,"chat_id");
   user=EEA_RiskLedgerField(json,"user_id");
   sequence=StringToInteger(EEA_RiskLedgerField(json,"gateway_sequence"));
   const long issued=StringToInteger(EEA_RiskLedgerField(json,"issued_at_utc"));
   const long expires=StringToInteger(EEA_RiskLedgerField(json,"expires_at_utc"));
   const long nonce_expires=StringToInteger(EEA_RiskLedgerField(json,"nonce_expires_at_utc"));
   if(!s.loaded) return "BOTS_STATE_NOT_LOADED";
   if(EEA_RiskLedgerField(json,"schema_version")!=EEA_BOT_COMMAND_VERSION || !EEA_BotSafeId(command_id) ||
      EEA_RiskLedgerField(json,"role")!="OPERATOR" || chat=="" || user=="" ||
      EEA_RiskLedgerField(json,"private_chat_attested")!="true" || EEA_RiskLedgerField(json,"sender_authenticated")!="true" ||
      EEA_RiskLedgerField(json,"source_authenticated")!="true" ||
      EEA_RiskLedgerField(json,"account_id")!=s.account_id || EEA_RiskLedgerField(json,"config_version")!=s.config_version ||
      issued<=0 || expires<=issued || now<issued-5 || now>expires)
      return "BOT_COMMAND_AUTH_IDENTITY_OR_TTL_INVALID";
   if(command_id==s.last_command_id) return "BOT_COMMAND_ALREADY_COMMITTED";
   if(sequence<=s.last_gateway_sequence) return "BOT_COMMAND_REPLAY_OR_SEQUENCE_REGRESSION";
   if(bot<0) return "BOT_UNKNOWN";
   if(action=="BOT_DISABLE") return "";
   if(action=="BOT_REQUEST_ENABLE")
     {
      if(s.active[bot]) return "BOT_ALREADY_ACTIVE";
      if(StringLen(nonce)!=6 || nonce_expires<=now || nonce_expires-now>EEA_BOT_MAX_NONCE_SECONDS || nonce==s.pending_nonce)
         return "BOT_ENABLE_CHALLENGE_INVALID";
      return "";
     }
   if(action=="BOT_CONFIRM_ENABLE")
     {
      if(s.pending_bot!=bot || s.pending_nonce=="" || nonce!=s.pending_nonce || chat!=s.pending_chat_id ||
         user!=s.pending_user_id || now>s.pending_expires_at_utc)
         return "BOT_ENABLE_CONFIRMATION_INVALID_OR_EXPIRED";
      return "";
     }
   return "BOT_ACTION_NOT_ALLOWED";
  }

void EEA_BotsProcessCommands(CAuditLog &audit)
  {
   const string root=g_bots_host.root;
   string name;
   long handle=FileFindFirst(EEA_BotCommandDir(root)+"/*.json",name);
   if(handle==INVALID_HANDLE) return;
   string files[];
   int n=0;
   do { ArrayResize(files,n+1); files[n++]=name; } while(FileFindNext(handle,name));
   FileFindClose(handle);
   ArraySort(files);
   FolderCreate(root+"/current/remote/results",0);
   for(int f=0;f<n;f++)
     {
      const string path=EEA_BotCommandDir(root)+"/"+files[f];
      string json="", action="", nonce="", chat="", user="", command_id="";
      int bot=-1; long sequence=0;
      string reason="";
      if(!EEA_PendingReadText(path,json)) reason="BOT_COMMAND_MALFORMED";
      else reason=EEA_BotCommandEvaluate(g_bots_state,json,(long)TimeGMT(),action,bot,nonce,chat,user,sequence,command_id);
      if(!EEA_BotSafeId(command_id))
        {
         command_id=StringSubstr(files[f],0,StringLen(files[f])-5);
         if(!EEA_BotSafeId(command_id)) command_id="malformed-"+IntegerToString((long)TimeGMT())+"-"+IntegerToString(f);
        }
      const string before=(bot>=0 ? (EEA_BotActive(bot) ? "ACTIVE" : "INACTIVE") : "");
      bool applied=false;
      if(reason=="")
        {
         if(action=="BOT_DISABLE" || action=="BOT_CONFIRM_ENABLE")
           {
            const bool on=(action=="BOT_CONFIRM_ENABLE");
            EEA_BotsState keep=g_bots_state;
            g_bots_state.last_gateway_sequence=sequence; g_bots_state.last_command_id=command_id;
            if(EEA_BotsSetActive(g_bots_state,bot,on,root,"TELEGRAM",command_id,audit,reason)) applied=true;
            else g_bots_state=keep;
           }
         else
           {
            EEA_BotsState next=g_bots_state;
            next.pending_bot=bot; next.pending_nonce=nonce; next.pending_chat_id=chat; next.pending_user_id=user;
            next.pending_expires_at_utc=StringToInteger(EEA_RiskLedgerField(json,"nonce_expires_at_utc"));
            next.last_gateway_sequence=sequence; next.last_command_id=command_id; next.state_version++;
            reason="BOT_ENABLE_CONFIRMATION_PENDING";
            if(EEA_BotsStateSave(next,root,reason)) { g_bots_state=next; applied=true; }
            else reason="BOTS_STATE_COMMIT_FAILED";
           }
        }
      const string after=(bot>=0 ? (EEA_BotActive(bot) ? "ACTIVE" : "INACTIVE") : "");
      const bool accepted=applied;
      const string result="{\"command_id\":\""+EEA_JsonEscape(command_id)+"\",\"action\":\""+EEA_JsonEscape(action)+
         "\",\"bot\":\""+(bot>=0 ? EEA_BotCode(bot) : "")+"\",\"accepted\":"+(accepted ? "true" : "false")+
         ",\"applied\":"+(applied ? "true" : "false")+",\"status\":\""+(applied ? "APPLIED" : "REJECTED")+
         "\",\"state_before\":\""+before+"\",\"state_after\":\""+after+"\",\"reason_codes\":[\""+reason+
         "\"],\"ea_state_version\":"+IntegerToString(g_bots_state.state_version)+",\"observed_at_utc\":"+
         IntegerToString((long)TimeGMT())+"}";
      EEA_WriteAtomicText(root+"/current/remote/results/"+command_id+".json",result);
      if(!applied)
         EEA_BotsAudit(audit,"BOT_COMMAND_REJECTED",bot>=0 ? EEA_BotCode(bot) : "bot",before,after,reason,
                       g_bots_state.config_version,"{\"action\":\""+EEA_JsonEscape(action)+"\"}");
      FileDelete(path,0);
      g_bots_host.last_command=action+" "+(bot>=0 ? EEA_BotCode(bot) : "?")+": "+reason;
     }
  }

// ------------------------------------------------------------------------------------------------------ status
string EEA_BotsStatusJson()
  {
   string bots="";
   for(int i=0;i<EEA_BOT_COUNT;i++)
     {
      int open_count=0; double floating=0.0, today=0.0;
      const string sym=(i==EEA_BOT_S07 ? "" : g_bots_host.symbol);
      EEA_BotMagicStats(g_bots_host.magics[i],sym,open_count,floating,today);
      if(i==EEA_BOT_VHEDGE && g_bot_vhedge.ModeText()=="SHADOW") open_count=g_bot_vhedge.OpenLegs();
      if(i==EEA_BOT_XRT && g_bot_xrt.ModeText()=="SHADOW") open_count=g_bot_xrt.OpenLegs();
      if(i==EEA_BOT_CTXLIMIT && g_bot_ctx.ModeText()=="SHADOW") open_count=g_bot_ctx.OpenLegs();
      bots+=(i>0 ? "," : "")+"{\"code\":\""+EEA_BotCode(i)+"\",\"title\":\""+EEA_JsonEscape(EEA_BotTitle(i))+
            "\",\"active\":"+(EEA_BotActive(i) ? "true" : "false")+",\"mode\":\""+EEA_JsonEscape(EEA_BotModeText(i))+
            "\",\"magic\":"+IntegerToString(g_bots_host.magics[i])+",\"open\":"+IntegerToString(open_count)+
            ",\"floating\":"+DoubleToString(floating,2)+",\"today\":"+DoubleToString(today,2)+
            ",\"status\":\""+EEA_JsonEscape(EEA_BotStatusText(i))+"\"}";
     }
   string guard="";
   double open_risk=0.0; string risk_reason="";
   const bool risk_ok=EEA_BotsAccountOpenRisk(open_risk,risk_reason);
   const double cap=g_bot_guard.capital;
   guard="{\"ready\":"+(g_bot_guard.ready ? "true" : "false")+",\"execution_live\":"+(g_bot_guard.execution_live ? "true" : "false")+
         ",\"operator_paused\":"+(g_bot_guard.operator_paused ? "true" : "false")+",\"capital\":"+DoubleToString(cap,2)+
         ",\"open_risk\":"+(risk_ok ? DoubleToString(open_risk,2) : "null")+",\"open_risk_pct\":"+
         (risk_ok && cap>0.0 ? DoubleToString(100.0*open_risk/cap,2) : "null")+",\"open_risk_reason\":\""+risk_reason+
         "\",\"max_open_risk_pct\":"+DoubleToString(g_bot_guard.max_open_risk_pct,2)+",\"day_start_equity\":"+
         DoubleToString(g_bot_guard.day_start_equity,2)+",\"daily_loss_pct\":"+DoubleToString(g_bot_guard.daily_loss_pct,2)+
         ",\"news_block\":\""+EEA_JsonEscape(g_bot_guard.news_block_scalp)+"\"}";
   return "{\"document_version\":\""+EEA_BOTS_STATUS_DOCUMENT+"\",\"account_id\":\""+EEA_JsonEscape(g_bots_state.account_id)+
      "\",\"config_version\":\""+EEA_JsonEscape(g_bots_state.config_version)+"\",\"state_version\":"+
      IntegerToString(g_bots_state.state_version)+",\"last_gateway_sequence\":"+IntegerToString(g_bots_state.last_gateway_sequence)+
      ",\"state_loaded\":"+(g_bots_state.loaded ? "true" : "false")+",\"state_reason\":\""+EEA_JsonEscape(g_bots_state.reason)+
      "\",\"symbol\":\""+EEA_JsonEscape(g_bots_host.symbol)+"\",\"pending_bot\":\""+
      (g_bots_state.pending_bot>=0 ? EEA_BotCode(g_bots_state.pending_bot) : "")+"\",\"pending_expires_at_utc\":"+
      IntegerToString(g_bots_state.pending_expires_at_utc)+",\"last_command\":\""+EEA_JsonEscape(g_bots_host.last_command)+
      "\",\"guard\":"+guard+",\"bots\":["+bots+"],\"written_at_utc\":"+IntegerToString((long)TimeGMT())+"}";
  }

// Every timer: load the flags once the account is known and run the Telegram commands.
void EEA_BotsHostTimer(const string account_id,const string config_version,CAuditLog &audit)
  {
   if(!g_bots_host.initialized || account_id=="" || config_version=="") return;
   if(!g_bots_state.loaded || g_bots_state.account_id!=account_id || g_bots_state.config_version!=config_version)
      EEA_BotsStateLoad(g_bots_state,g_bots_host.root,account_id,config_version,g_bots_host.defaults,audit);
   EEA_BotsProcessCommands(audit);
  }

// After the shell refreshed the guard and the S07 line: panel texts and current/bots_status.json.
void EEA_BotsWriteStatus()
  {
   if(!g_bots_host.initialized || !g_bots_state.loaded) return;
   for(int i=0;i<EEA_BOT_COUNT;i++) g_bots_host.status_text[i]=EEA_BotStatusText(i);
   EEA_WriteAtomicText(g_bots_host.root+"/current/bots_status.json",EEA_BotsStatusJson());
  }

// Panel toggle (local operator). Disabling applies at once; enabling is confirmed by the panel (second click).
bool EEA_BotsPanelToggle(const string code,CAuditLog &audit,string &reason)
  {
   const int id=EEA_BotFind(code);
   if(id<0) { reason="BOT_UNKNOWN"; return false; }
   return EEA_BotsSetActive(g_bots_state,id,!EEA_BotActive(id),g_bots_host.root,"PANEL","",audit,reason);
  }

#endif
