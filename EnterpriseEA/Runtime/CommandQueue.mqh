#ifndef ENTERPRISE_EA_COMMAND_QUEUE_MQH
#define ENTERPRISE_EA_COMMAND_QUEUE_MQH

// Command queue and manual trade actions (G8, master specification 9.1-9.2, design
// 2026-10-04, decisions C1-C6). Every manual action is written as a command with an id,
// source and expiry before anything is sent; the EA validates it (source, TTL, account,
// duplicate, unchanged position) and executes it through the same adapter, authorization
// and idempotency path as the Trade Manager. Only EA positions and EA pending orders are
// eligible (C1) and every action reduces or keeps risk: close, partial, break-even,
// trail, cancel and close-all. Sources: PANEL only in v1; AI is never accepted.

#include "TradeManagerRuntime.mqh"

#define EEA_CMD_SCHEMA "ea-command-v1.0.0"
#define EEA_CMD_TTL_SECONDS 60            // C5
#define EEA_CMD_MAX_RESULTS 48

struct EEA_Command
  {
   string id;
   string source;              // PANEL (v1)
   string action;              // CLOSE | PARTIAL | BE | TRAIL | CANCEL | CLOSE_ALL_EA
   string ticket_kind;         // POSITION | ORDER | ALL
   long   ticket;
   double expected_volume;
   double expected_sl;
   double partial_fraction;
   long   issued_at_utc;
   long   expires_at_utc;
   string account_fingerprint;
   string config_version;
   string operator_id;
  };

void EEA_CommandDefaults(EEA_Command &c)
  {
   c.id=""; c.source=""; c.action=""; c.ticket_kind=""; c.ticket=0; c.expected_volume=0.0; c.expected_sl=0.0;
   c.partial_fraction=0.0; c.issued_at_utc=0; c.expires_at_utc=0; c.account_fingerprint=""; c.config_version="";
   c.operator_id="";
  }

bool EEA_CommandActionAllowed(const string action)
  {
   return action=="CLOSE" || action=="PARTIAL" || action=="BE" || action=="TRAIL" || action=="CANCEL" ||
          action=="CLOSE_ALL_EA";
  }

string EEA_CommandDir(const string root) { return root+"/current/commands"; }

string EEA_CommandToJson(const EEA_Command &c)
  {
   return "{\"schema_version\":\""+EEA_CMD_SCHEMA+"\",\"command_id\":\""+EEA_JsonEscape(c.id)+"\",\"source\":\""+c.source+
      "\",\"action\":\""+c.action+"\",\"ticket_kind\":\""+c.ticket_kind+"\",\"ticket\":"+IntegerToString(c.ticket)+
      ",\"expected_volume\":"+DoubleToString(c.expected_volume,8)+",\"expected_sl\":"+DoubleToString(c.expected_sl,8)+
      ",\"partial_fraction\":"+DoubleToString(c.partial_fraction,4)+",\"issued_at_utc\":"+IntegerToString(c.issued_at_utc)+
      ",\"expires_at_utc\":"+IntegerToString(c.expires_at_utc)+",\"account_fingerprint\":\""+EEA_JsonEscape(c.account_fingerprint)+
      "\",\"config_version\":\""+EEA_JsonEscape(c.config_version)+"\",\"operator_id\":\""+EEA_JsonEscape(c.operator_id)+"\"}";
  }

bool EEA_CommandParse(const string json,EEA_Command &c)
  {
   EEA_CommandDefaults(c);
   if(EEA_RiskLedgerField(json,"schema_version")!=EEA_CMD_SCHEMA) return false;
   c.id=EEA_RiskLedgerField(json,"command_id"); c.source=EEA_RiskLedgerField(json,"source");
   c.action=EEA_RiskLedgerField(json,"action"); c.ticket_kind=EEA_RiskLedgerField(json,"ticket_kind");
   c.ticket=StringToInteger(EEA_RiskLedgerField(json,"ticket"));
   c.expected_volume=StringToDouble(EEA_RiskLedgerField(json,"expected_volume"));
   c.expected_sl=StringToDouble(EEA_RiskLedgerField(json,"expected_sl"));
   c.partial_fraction=StringToDouble(EEA_RiskLedgerField(json,"partial_fraction"));
   c.issued_at_utc=StringToInteger(EEA_RiskLedgerField(json,"issued_at_utc"));
   c.expires_at_utc=StringToInteger(EEA_RiskLedgerField(json,"expires_at_utc"));
   c.account_fingerprint=EEA_RiskLedgerField(json,"account_fingerprint");
   c.config_version=EEA_RiskLedgerField(json,"config_version");
   c.operator_id=EEA_RiskLedgerField(json,"operator_id");
   return c.id!="";
  }

// Envelope checks that need no broker state (TC-CQ-03, TC-CQ-11).
string EEA_CommandValidateEnvelope(const EEA_Command &c,const long now,const string account_fingerprint,
                                   const string config_version,const bool execution_enabled)
  {
   if(c.source!="PANEL") return "COMMAND_SOURCE_NOT_ALLOWED";
   if(!EEA_CommandActionAllowed(c.action)) return "COMMAND_ACTION_INVALID";
   if(c.expires_at_utc<=0 || now>c.expires_at_utc) return "COMMAND_EXPIRED";
   if(c.expires_at_utc-c.issued_at_utc>EEA_CMD_TTL_SECONDS) return "COMMAND_TTL_INVALID";
   if(c.account_fingerprint!=account_fingerprint || c.config_version!=config_version) return "COMMAND_IDENTITY_MISMATCH";
   if(!execution_enabled) return "COMMAND_EA_NOT_ARMED";                        // C3
   if(c.action=="PARTIAL" && (c.partial_fraction<0.1 || c.partial_fraction>0.9)) return "COMMAND_PARTIAL_INVALID";
   if(c.action!="CLOSE_ALL_EA" && c.ticket<=0) return "COMMAND_TICKET_INVALID";
   return "";
  }

int EEA_CommandFindTrade(const EEA_TradeManagerRuntime &trades,const long position_ticket)
  {
   for(int i=0;i<trades.count;i++)
      if(trades.items[i].active && trades.items[i].position_ticket==position_ticket) return i;
   return -1;
  }

int EEA_CommandFindPosition(const EEA_ObserverRuntimeContext &observer,const long ticket)
  {
   for(int i=0;i<observer.reconciliation.position_count;i++)
      if(observer.reconciliation.positions[i].ticket==ticket) return i;
   return -1;
  }

int EEA_CommandFindPending(const EEA_PendingRuntime &pending,const long order_ticket)
  {
   for(int i=0;i<pending.count;i++)
      if(pending.items[i].active && pending.items[i].state.order_ticket==IntegerToString(order_ticket) &&
         (pending.items[i].state.status=="WORKING" || pending.items[i].state.status=="PARTIAL")) return i;
   return -1;
  }

// Trail level for the trade's profile (SCALP: ATR, SWING: structure); 0 when unavailable.
double EEA_CommandTrailPrice(const EEA_ManagedTrade &t)
  {
   EEA_TradeProfile p; EEA_TradeProfileFor(t.profile,p);
   MqlRates last; double atr=EEA_TradeManagerAtr(t,last);
   if(atr<=0.0) return 0.0;
   if(p.trail_mode==EEA_TM_TRAIL_STRUCTURE)
     {
      double extreme=0.0;
      if(!EEA_TradeManagerSwingExtreme(t,p.structure_bars,extreme)) return 0.0;
      return extreme-t.direction*0.1*atr;
     }
   return last.close-t.direction*p.trail_atr_mult*atr;
  }

// One position action. Checks the position still matches what the operator saw (TC-CQ-04).
string EEA_CommandPositionAction(const string action,const EEA_Command &c,EEA_TradeManagerRuntime &trades,
                                 CAuditLog &audit,const string root,const EEA_ObserverRuntimeContext &observer,
                                 const bool execution_enabled,const long position_ticket,const bool check_expected)
  {
   int ti=EEA_CommandFindTrade(trades,position_ticket);
   if(ti<0) return "COMMAND_NOT_EA_POSITION";                                     // C1
   int pi=EEA_CommandFindPosition(observer,position_ticket);
   if(pi<0) return "COMMAND_POSITION_NOT_FOUND";
   const EEA_RuntimePositionRow position=observer.reconciliation.positions[pi];
   EEA_ManagedTrade t=trades.items[ti];
   int row=EEA_TradeManagerSymbolRow(observer,t.intent.broker_symbol);
   if(row<0) return "COMMAND_SYMBOL_UNAVAILABLE";
   const EEA_RuntimeSymbolSpec spec=observer.symbol_specs[row];
   if(check_expected &&
      (MathAbs(position.volume-c.expected_volume)>spec.volume_step*0.5 ||
       MathAbs(position.sl-c.expected_sl)>spec.tick_size*0.5))
      return "COMMAND_STATE_CHANGED";
   string reason="";
   bool ok=false;
   if(action=="CLOSE")
     {
      ok=EEA_TradeManagerClose(t,audit,root,observer,position,execution_enabled,position.volume,"MANUAL_CLOSE",reason);
      if(ok) t.last_reason="MANUAL_CLOSE:"+c.id;
     }
   else if(action=="PARTIAL")
     {
      double part=MathFloor(position.volume*c.partial_fraction/spec.volume_step)*spec.volume_step;
      if(part<spec.volume_min || position.volume-part<spec.volume_min) return "COMMAND_PARTIAL_BELOW_MIN_VOLUME";
      ok=EEA_TradeManagerClose(t,audit,root,observer,position,execution_enabled,part,"MANUAL_PARTIAL",reason);
      if(ok) t.partial_done=true;
     }
   else if(action=="BE")
     {
      MqlTick tick; ZeroMemory(tick);
      if(!SymbolInfoTick(t.intent.broker_symbol,tick)) return "COMMAND_QUOTE_UNAVAILABLE";
      double be_price=t.entry_price+t.direction*(tick.ask-tick.bid);
      ok=EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,be_price,"MANUAL_BREAK_EVEN",reason);
      if(ok) t.be_done=true;
     }
   else if(action=="TRAIL")
     {
      double trail=EEA_CommandTrailPrice(t);                                         // C6: now, tighten only
      if(trail<=0.0) return "COMMAND_TRAIL_UNAVAILABLE";
      ok=EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,trail,"MANUAL_TRAIL",reason);
      // Trailing is switched on even when no tighter level exists yet; later timers trail it.
      if(!ok && (reason=="TRADE_MANAGER_STOP_NOT_TIGHTER" || reason=="TRADE_MANAGER_STOP_TOO_CLOSE")) ok=true;
      t.trail_active=true;
     }
   trades.items[ti]=t;
   EEA_TradeManagerWrite(root,t);
   return ok ? "" : (reason=="" ? "COMMAND_SEND_FAILED" : reason);
  }

string EEA_CommandCancelOrder(const EEA_Command &c,EEA_PendingRuntime &pending,CAuditLog &audit,const string root,
                              const EEA_ObserverRuntimeContext &observer,const bool execution_enabled,const long order_ticket)
  {
   int i=EEA_CommandFindPending(pending,order_ticket);
   if(i<0) return "COMMAND_NOT_EA_ORDER";
   EEA_PendingTracked t=pending.items[i];
   EEA_PendingRequireCancel(t.state,(datetime)TimeGMT(),"MANUAL_CANCEL");
   EEA_PendingRequestCancel(t,audit,root,observer,execution_enabled);
   EEA_PendingWrite(root,t);
   pending.items[i]=t;
   if(t.state.status=="CANCEL_REQUESTED") return "";
   return t.state.reason_code!="" ? t.state.reason_code : "COMMAND_CANCEL_FAILED";
  }

// Executes one command. Returns "" when applied; otherwise the rejection reason.
// `detail` lists the per-item results of CLOSE_ALL_EA.
string EEA_CommandExecute(const EEA_Command &c,EEA_TradeManagerRuntime &trades,EEA_PendingRuntime &pending,
                          CAuditLog &audit,const string root,const EEA_ObserverRuntimeContext &observer,
                          const bool execution_enabled,string &detail)
  {
   detail="";
   if(c.action=="CANCEL") return EEA_CommandCancelOrder(c,pending,audit,root,observer,execution_enabled,c.ticket);
   if(c.action!="CLOSE_ALL_EA")
      return EEA_CommandPositionAction(c.action,c,trades,audit,root,observer,execution_enabled,c.ticket,true);
   // CLOSE_ALL_EA (C2): every EA position closed, every EA pending order cancelled.
   int failures=0, done=0;
   for(int i=0;i<trades.count;i++)
     {
      if(!trades.items[i].active || trades.items[i].position_ticket<=0) continue;
      long ticket=trades.items[i].position_ticket;
      string r=EEA_CommandPositionAction("CLOSE",c,trades,audit,root,observer,execution_enabled,ticket,false);
      if(r=="COMMAND_POSITION_NOT_FOUND") continue;
      detail+=(detail=="" ? "" : ";")+"P"+IntegerToString(ticket)+"="+(r=="" ? "OK" : r);
      if(r=="") done++; else failures++;
     }
   for(int i=0;i<pending.count;i++)
     {
      if(!pending.items[i].active) continue;
      if(pending.items[i].state.status!="WORKING" && pending.items[i].state.status!="PARTIAL") continue;
      long ticket=StringToInteger(pending.items[i].state.order_ticket);
      string r=EEA_CommandCancelOrder(c,pending,audit,root,observer,execution_enabled,ticket);
      detail+=(detail=="" ? "" : ";")+"O"+IntegerToString(ticket)+"="+(r=="" ? "OK" : r);
      if(r=="") done++; else failures++;
     }
   if(done==0 && failures==0) return "COMMAND_NOTHING_TO_CLOSE";
   return failures>0 ? "COMMAND_PARTIAL_FAILURE" : "";
  }

// Processes every queued command (oldest first). Each id executes at most once (TC-CQ-02):
// a marker "cmd-<id>" is written for every final outcome and the file moves to done/.
int EEA_CommandProcessQueue(EEA_TradeManagerRuntime &trades,EEA_PendingRuntime &pending,CAuditLog &audit,
                            const string root,const EEA_ObserverRuntimeContext &observer,const bool execution_enabled,
                            string &last_result)
  {
   string name;
   long handle=FileFindFirst(EEA_CommandDir(root)+"/*.json",name);
   if(handle==INVALID_HANDLE) return 0;
   string files[];
   int n=0;
   do { ArrayResize(files,n+1); files[n++]=name; } while(FileFindNext(handle,name));
   FileFindClose(handle);
   int processed=0;
   for(int f=0;f<n;f++)
     {
      string path=EEA_CommandDir(root)+"/"+files[f];
      string json;
      EEA_Command c;
      string reason="", detail="";
      bool parsed=EEA_PendingReadText(path,json) && EEA_CommandParse(json,c);
      if(!parsed) { reason="COMMAND_MALFORMED"; c.id=files[f]; c.action=""; }
      else if(FileIsExist(EEA_IdempotencyMarkerPath(root,"cmd-"+c.id),0)) reason="COMMAND_DUPLICATE";
      else
        {
         reason=EEA_CommandValidateEnvelope(c,(long)TimeGMT(),observer.account.account_fingerprint,
                                            observer.config_version,execution_enabled);
         if(reason=="") reason=EEA_CommandExecute(c,trades,pending,audit,root,observer,execution_enabled,detail);
        }
      string outcome=(reason=="" ? "APPLIED" : (reason=="COMMAND_EXPIRED" ? "EXPIRED" : "REJECTED"));
      if(parsed) EEA_IdempotencyMarkerWrite(root,"cmd-"+c.id);
      string line="{\"command_id\":\""+EEA_JsonEscape(c.id)+"\",\"source\":\""+c.source+"\",\"action\":\""+c.action+
         "\",\"ticket\":"+IntegerToString(c.ticket)+",\"outcome\":\""+outcome+"\",\"reason\":\""+reason+
         "\",\"detail\":\""+EEA_JsonEscape(detail)+"\",\"processed_at_utc\":"+IntegerToString((long)TimeGMT())+"}";
      EEA_WriteAtomicAppendText(root+"/logs/commands.jsonl",line+"\r\n");
      EEAEvent event;
      EEAEvent_Init(event,outcome=="APPLIED" ? "COMMAND_APPLIED" : (outcome=="EXPIRED" ? "COMMAND_EXPIRED" : "COMMAND_REJECTED"),
                    TimeGMT(),"",c.id,"",c.action,outcome=="APPLIED" ? "OK" : "DEGRADED");
      event.config_version=observer.config_version;
      if(reason!="") EEAEvent_AddReason(event,reason);
      event.details_json="{\"ticket\":"+IntegerToString(c.ticket)+",\"source\":\""+c.source+"\",\"detail\":\""+
                         EEA_JsonEscape(detail)+"\"}";
      audit.Append(event,"EA_COMMAND");
      FileMove(path,0,EEA_CommandDir(root)+"/done/"+files[f],FILE_REWRITE);
      last_result=c.action+" "+(c.ticket>0 ? "#"+IntegerToString(c.ticket)+" " : "")+outcome+(reason=="" ? "" : ": "+reason);
      processed++;
     }
   return processed;
  }

#endif
