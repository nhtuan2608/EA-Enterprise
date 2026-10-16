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
// Every command: schema, OPERATOR role, this account and config, TTL, a sequence above the last one of its
// source (no replay). A disable never needs a confirmation. Two sources:
//   Telegram gateway  authenticated private chat (the gateway's attestation flags), gateway_sequence
//   MCP               source "MCP" (bridge/eea_mcp_server.py --allow-control: whoever can write the data folder,
//                     e.g. Claude Code over SSH), mcp_sequence with its own counter; off with InpBotsMcpCommands.
//                     It does not claim the Telegram flags: an MCP file carrying them is rejected.

#include "BotState.mqh"
#include "PortfolioGuard.mqh"
#include "VHedgeBot.mqh"
#include "XrtBot.mqh"
#include "CtxLimitBot.mqh"

#define EEA_BOT_COMMAND_VERSION "bot-command-v1.0.0"
#define EEA_BOTS_STATUS_DOCUMENT "bots-status-v1.0.0"
#define EEA_BOT_MAX_NONCE_SECONDS 120

bool g_bots_allow_mcp=true;                 // InpBotsMcpCommands

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
double       g_bot_s07_near=0.0;          // collapsed panel: S07 conditions met on the last closed M30 bar
string       g_bot_s07_near_text="";
datetime     g_bot_s07_near_bar=0;
datetime     g_bot_near_logged_bar=0;      // journal: last M30 bar with the NEAR lines
ulong        g_bot_deal_seen=0;            // journal: highest deal ticket already looked at (0 = not scanned yet)
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

// ------------------------------------------------------------------------------------------------------ closeness
// Read-only view of the S07 rule on the last closed M30 bar (the engine itself decides; this only counts
// which of its five conditions are met, for the better direction): 1 compression in the window, 2 ADX turns up
// within 10 of the low, 3 DI with the side and widening, 4 close beyond the four EMAs, 5 H4 close on that side
// of the H4 EMA200.
void EEA_BotsS07Near(const string sym)
  {
   const datetime bar=iTime(sym,PERIOD_M30,1);
   if(bar==0 || bar==g_bot_s07_near_bar) return;
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(sym,PERIOD_M30,1,600,r);
   if(n<300) { g_bot_s07_near=0.0; g_bot_s07_near_text="chưa đủ nến M30"; return; }
   double e21[],e55[],e100[],e200[],pdi[],mdi[],adx[],atr[];
   EEA_S07Ema(r,n,21,e21); EEA_S07Ema(r,n,55,e55); EEA_S07Ema(r,n,100,e100); EEA_S07Ema(r,n,200,e200);
   EEA_S07Dmi(r,n,pdi,mdi,adx,atr);
   int h4_side=0;
   MqlRates h[];
   ArraySetAsSeries(h,false);
   const int nh=CopyRates(sym,PERIOD_H4,1,400,h);
   if(nh>=210)
     {
      double eh[];
      EEA_S07Ema(h,nh,200,eh);
      h4_side=(h[nh-1].close>eh[nh-1] ? 1 : (h[nh-1].close<eh[nh-1] ? -1 : 0));
     }
   const int i=n-1, window=EEA_S07WindowBars("M30");
   int k=i-window;
   for(int j=i-window+1;j<i;j++) if(adx[j]<adx[k]) k=j;
   const bool c1=(adx[k]<=EEA_S07_ADX_LOW && MathAbs(pdi[k]-mdi[k])<=EEA_S07_DI_GAP);
   const bool c2=(adx[i]>adx[i-1] && adx[i]-adx[k]<=EEA_S07_ADX_RISE);
   const double gap=pdi[i]-mdi[i], gap_prev=pdi[i-1]-mdi[i-1];
   const double hi=MathMax(MathMax(e21[i],e55[i]),MathMax(e100[i],e200[i]));
   const double lo=MathMin(MathMin(e21[i],e55[i]),MathMin(e100[i],e200[i]));
   int best_d=1, best_n=-1;
   bool b3=false, b4=false, b5=false;
   for(int s=0;s<2;s++)
     {
      const int d=(s==0 ? 1 : -1);
      const bool c3=(d*gap>0.0 && d*gap>d*gap_prev);
      const bool c4=(d==1 ? r[i].close>hi : r[i].close<lo);
      const bool c5=(h4_side==d);
      const int cnt=(c1 ? 1 : 0)+(c2 ? 1 : 0)+(c3 ? 1 : 0)+(c4 ? 1 : 0)+(c5 ? 1 : 0);
      if(cnt>best_n) { best_n=cnt; best_d=d; b3=c3; b4=c4; b5=c5; }
     }
   g_bot_s07_near=best_n/5.0;
   g_bot_s07_near_text=StringFormat("%s %d/5: nén ADX %s | ADX lên %s | DI %s | vượt 4 EMA %s | H4 %s (M30 %s)",
                                    best_d==1 ? "MUA" : "BÁN",best_n,PnlMark(c1),PnlMark(c2),PnlMark(b3),PnlMark(b4),
                                    PnlMark(b5),PnlHm(bar+1800));
   g_bot_s07_near_bar=bar;
  }

void EEA_BotNear(const int id,double &score,string &text)
  {
   score=0.0; text="";
   if(id==EEA_BOT_S07)
     {
      score=g_bot_s07_near; text=g_bot_s07_near_text;
      int open_count=0; double fl=0.0, today=0.0;
      EEA_BotMagicStats(g_bots_host.magics[id],"",open_count,fl,today);
      if(open_count>0) { score=1.0; text=StringFormat("đang giữ %d lệnh S07",open_count); }
      if(g_bots_host.s07_mode=="OFF") { score=0.0; text="OFF"; }
     }
   else if(id==EEA_BOT_VHEDGE)
     {
      score=g_bot_vhedge.near_score; text=g_bot_vhedge.near_text;
      if(g_bot_vhedge.OpenGroups()>0) { score=1.0; text=StringFormat("đang có %d nhóm hedge",g_bot_vhedge.OpenGroups()); }
      if(g_bot_vhedge.ModeText()=="OFF") { score=0.0; text="OFF"; }
     }
   else if(id==EEA_BOT_XRT) g_bot_xrt.Near(score,text);
   else if(id==EEA_BOT_CTXLIMIT) g_bot_ctx.Near(score,text);
   if(!EEA_BotActive(id)) score=0.0;
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
   g_bot_journal_root=root;
   for(int i=0;i<EEA_BOT_COUNT;i++) g_bot_journal_block[i]="";
   g_bot_near_logged_bar=0; g_bot_deal_seen=0;
   EEA_BotLog(-1,"START","",StringFormat("EA khởi động trên %s: VHedge %s, XauRegime %s, CtxLimit %s",g_bots_host.symbol,
              g_bot_vhedge.ModeText(),g_bot_xrt.ModeText(),g_bot_ctx.ModeText()),"\"symbol\":\""+EEA_JsonEscape(g_bots_host.symbol)+"\"");
  }

int EEA_BotByMagic(const long magic)
  {
   if(magic<=0) return -1;
   for(int i=0;i<EEA_BOT_COUNT;i++) if(g_bots_host.magics[i]==magic) return i;
   return -1;
  }

// Journal: every new broker deal of a bot magic (fills and exits of LIVE bots, S07 included) with its money.
// The first scan after a start only records where it is, so a restart does not repeat old deals.
void EEA_BotsJournalDeals()
  {
   const datetime now=TimeTradeServer();
   if(!HistorySelect(now-3*86400,now+60)) return;
   ulong top=g_bot_deal_seen;
   const bool first=(g_bot_deal_seen==0);
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      const ulong d=HistoryDealGetTicket(i);
      if(d==0 || d<=g_bot_deal_seen) continue;
      if(d>top) top=d;
      if(first) continue;
      const int bot=EEA_BotByMagic(HistoryDealGetInteger(d,DEAL_MAGIC));
      if(bot<0) continue;
      const long type=HistoryDealGetInteger(d,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      const long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
      const long why=HistoryDealGetInteger(d,DEAL_REASON);
      const double money=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_COMMISSION);
      const string side=(type==DEAL_TYPE_BUY ? "MUA" : "BÁN");
      const string how=(why==DEAL_REASON_SL ? "SL" : (why==DEAL_REASON_TP ? "TP" : (why==DEAL_REASON_SO ? "stop out" : "")));
      const bool in=(entry==DEAL_ENTRY_IN);
      const string text=(in ? StringFormat("khớp %s %.2f lot tại %s",side,HistoryDealGetDouble(d,DEAL_VOLUME),
                                           DoubleToString(HistoryDealGetDouble(d,DEAL_PRICE),2))
                            : StringFormat("đóng (%s %.2f lot tại %s%s): %+.2f",side,HistoryDealGetDouble(d,DEAL_VOLUME),
                                           DoubleToString(HistoryDealGetDouble(d,DEAL_PRICE),2),how!="" ? ", "+how : "",money))+
                        " | "+HistoryDealGetString(d,DEAL_COMMENT);
      EEA_BotLog(bot,in ? "FILL" : "CLOSE","LIVE",text,
                 "\"deal\":"+IntegerToString((long)d)+",\"position\":"+IntegerToString(HistoryDealGetInteger(d,DEAL_POSITION_ID))+
                 ",\"symbol\":\""+EEA_JsonEscape(HistoryDealGetString(d,DEAL_SYMBOL))+"\","+
                 EEA_BotJsonNum("volume",HistoryDealGetDouble(d,DEAL_VOLUME),2)+","+EEA_BotJsonNum("price",HistoryDealGetDouble(d,DEAL_PRICE),2)+
                 ","+EEA_BotJsonNum("money",money,2)+",\"reason\":\""+how+"\"");
     }
   g_bot_deal_seen=(top>0 ? top : 1);
  }

// Journal: one NEAR line per bot on every closed M30 bar (what it waited for, how close it was).
// The bar seen at the start is skipped: the bots are still loading their history then.
void EEA_BotsJournalNear()
  {
   if(g_bot_s07_near_bar==0 || g_bot_s07_near_bar==g_bot_near_logged_bar) return;
   const bool first=(g_bot_near_logged_bar==0);
   g_bot_near_logged_bar=g_bot_s07_near_bar;
   if(first) return;
   for(int i=0;i<EEA_BOT_COUNT;i++)
     {
      double score=0.0; string text="";
      EEA_BotNear(i,score,text);
      EEA_BotLog(i,"NEAR",EEA_BotModeText(i),text,EEA_BotJsonNum("score",score,2)+",\"active\":"+(EEA_BotActive(i) ? "true" : "false"));
     }
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
                              string &nonce,string &chat,string &user,long &sequence,string &command_id,string &source)
  {
   source=EEA_RiskLedgerField(json,"source");
   const bool mcp=(source=="MCP");
   if(!mcp) source="TELEGRAM";
   command_id=EEA_RiskLedgerField(json,"command_id");
   action=EEA_RiskLedgerField(json,"action");
   bot=EEA_BotFind(EEA_RiskLedgerField(json,"bot"));
   nonce=EEA_RiskLedgerField(json,"confirmation_nonce");
   chat=EEA_RiskLedgerField(json,"chat_id");
   user=EEA_RiskLedgerField(json,"user_id");
   sequence=StringToInteger(EEA_RiskLedgerField(json,mcp ? "mcp_sequence" : "gateway_sequence"));
   const long issued=StringToInteger(EEA_RiskLedgerField(json,"issued_at_utc"));
   const long expires=StringToInteger(EEA_RiskLedgerField(json,"expires_at_utc"));
   const long nonce_expires=StringToInteger(EEA_RiskLedgerField(json,"nonce_expires_at_utc"));
   if(!s.loaded) return "BOTS_STATE_NOT_LOADED";
   if(mcp && !g_bots_allow_mcp) return "BOT_COMMAND_SOURCE_DISABLED";
   const bool attested=(EEA_RiskLedgerField(json,"private_chat_attested")=="true" &&
                        EEA_RiskLedgerField(json,"sender_authenticated")=="true" &&
                        EEA_RiskLedgerField(json,"source_authenticated")=="true");
   const bool claims=(EEA_RiskLedgerField(json,"private_chat_attested")!="" || EEA_RiskLedgerField(json,"sender_authenticated")!="" ||
                      EEA_RiskLedgerField(json,"source_authenticated")!="");
   if(EEA_RiskLedgerField(json,"schema_version")!=EEA_BOT_COMMAND_VERSION || !EEA_BotSafeId(command_id) ||
      EEA_RiskLedgerField(json,"role")!="OPERATOR" || chat=="" || user=="" ||
      (mcp ? claims : !attested) ||
      EEA_RiskLedgerField(json,"account_id")!=s.account_id || EEA_RiskLedgerField(json,"config_version")!=s.config_version ||
      issued<=0 || expires<=issued || now<issued-5 || now>expires)
      return "BOT_COMMAND_AUTH_IDENTITY_OR_TTL_INVALID";
   if(command_id==s.last_command_id) return "BOT_COMMAND_ALREADY_COMMITTED";
   if(sequence<=(mcp ? s.last_mcp_sequence : s.last_gateway_sequence)) return "BOT_COMMAND_REPLAY_OR_SEQUENCE_REGRESSION";
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
      string json="", action="", nonce="", chat="", user="", command_id="", source="TELEGRAM";
      int bot=-1; long sequence=0;
      string reason="";
      if(!EEA_PendingReadText(path,json)) reason="BOT_COMMAND_MALFORMED";
      else reason=EEA_BotCommandEvaluate(g_bots_state,json,(long)TimeGMT(),action,bot,nonce,chat,user,sequence,command_id,source);
      const bool mcp=(source=="MCP");
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
            if(mcp) g_bots_state.last_mcp_sequence=sequence; else g_bots_state.last_gateway_sequence=sequence;
            g_bots_state.last_command_id=command_id;
            if(EEA_BotsSetActive(g_bots_state,bot,on,root,source,command_id,audit,reason))
              {
               applied=true;
               EEA_BotLog(bot,"SWITCH",EEA_BotModeText(bot),(on ? "BẬT" : "TẮT")+(mcp ? " qua MCP" : " qua Telegram")+
                          (mcp ? " ("+user+")" : ""),
                          "\"active\":"+(on ? "true" : "false")+",\"source\":\""+source+"\",\"command_id\":\""+EEA_JsonEscape(command_id)+"\"");
              }
            else g_bots_state=keep;
           }
         else
           {
            EEA_BotsState next=g_bots_state;
            next.pending_bot=bot; next.pending_nonce=nonce; next.pending_chat_id=chat; next.pending_user_id=user;
            next.pending_expires_at_utc=StringToInteger(EEA_RiskLedgerField(json,"nonce_expires_at_utc"));
            if(mcp) next.last_mcp_sequence=sequence; else next.last_gateway_sequence=sequence;
            next.last_command_id=command_id; next.state_version++;
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
         "\"],\"source\":\""+source+"\",\"ea_state_version\":"+IntegerToString(g_bots_state.state_version)+",\"observed_at_utc\":"+
         IntegerToString((long)TimeGMT())+"}";
      EEA_WriteAtomicText(root+"/current/remote/results/"+command_id+".json",result);
      if(!applied)
         EEA_BotsAudit(audit,"BOT_COMMAND_REJECTED",bot>=0 ? EEA_BotCode(bot) : "bot",before,after,reason,
                       g_bots_state.config_version,"{\"action\":\""+EEA_JsonEscape(action)+"\",\"source\":\""+source+
                       "\",\"command_id\":\""+EEA_JsonEscape(command_id)+"\"}");
      FileDelete(path,0);
      g_bots_host.last_command=source+" "+action+" "+(bot>=0 ? EEA_BotCode(bot) : "?")+": "+reason;
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
      double near=0.0; string near_text="";
      EEA_BotNear(i,near,near_text);
      bots+=(i>0 ? "," : "")+"{\"code\":\""+EEA_BotCode(i)+"\",\"title\":\""+EEA_JsonEscape(EEA_BotTitle(i))+
            "\",\"active\":"+(EEA_BotActive(i) ? "true" : "false")+",\"mode\":\""+EEA_JsonEscape(EEA_BotModeText(i))+
            "\",\"magic\":"+IntegerToString(g_bots_host.magics[i])+",\"open\":"+IntegerToString(open_count)+
            ",\"floating\":"+DoubleToString(floating,2)+",\"today\":"+DoubleToString(today,2)+
            ",\"status\":\""+EEA_JsonEscape(EEA_BotStatusText(i))+"\",\"near\":"+DoubleToString(near,2)+
            ",\"near_text\":\""+EEA_JsonEscape(near_text)+"\"}";
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
      ",\"last_mcp_sequence\":"+IntegerToString(g_bots_state.last_mcp_sequence)+",\"mcp_commands\":"+(g_bots_allow_mcp ? "true" : "false")+
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
   EEA_BotsS07Near(g_bots_host.symbol);
   if(g_bots_state.loaded) { EEA_BotsJournalNear(); EEA_BotsJournalDeals(); }
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
   const bool on=!EEA_BotActive(id);
   if(!EEA_BotsSetActive(g_bots_state,id,on,g_bots_host.root,"PANEL","",audit,reason)) return false;
   EEA_BotLog(id,"SWITCH",EEA_BotModeText(id),(on ? "BẬT" : "TẮT")+string(" trên bảng điều khiển"),
              "\"active\":"+(on ? "true" : "false")+",\"source\":\"PANEL\"");
   return true;
  }

#endif
