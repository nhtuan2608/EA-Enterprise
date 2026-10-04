#ifndef ENTERPRISE_EA_TRADE_MANAGER_RUNTIME_MQH
#define ENTERPRISE_EA_TRADE_MANAGER_RUNTIME_MQH

// REQ-005 Trade Manager (master specification section 6). Manages only positions the EA
// opened itself: each one is registered at submission with its candidate lineage and
// linked to the broker position through the entry deal. Per closed bar of the setup
// timeframe it tracks MFE/MAE in R, time to 0.5R/1R/2R and the lifecycle
// ENTERED -> PROVING -> WORKING -> MATURE -> EXITED. Actions follow the SCALP or SWING
// profile (never shared, CHK-TM-02): partial, break-even, trail, structure invalidation
// and time stop. Every action is a normal authorized, idempotent, gated request.
// When the session was revoked or expired, the manager only moves a profitable
// position's stop to break-even; it never closes or trails on its own.
// Thresholds are PROPOSED seeds (S02 design section 10), to be confirmed by forward data.

#include "PendingOrderRuntime.mqh"
#include "../News/NewsCalendar.mqh"

#define EEA_TM_MAX 32
#define EEA_TM_DOCUMENT "managed-trade-v1.0.0"
#define EEA_TM_TRAIL_ATR 1
#define EEA_TM_TRAIL_STRUCTURE 2

struct EEA_TradeProfile
  {
   double be_at_r;             // move the stop to break-even once MFE reaches this
   double partial_at_r;        // close part of the position at this MFE
   double partial_fraction;
   double trail_start_r;       // start trailing at this MFE
   int    trail_mode;
   double trail_atr_mult;
   int    structure_bars;      // STRUCTURE trail: extreme of the last N closed bars
   int    underperform_bars;   // TC-012: flag (no exit) when MFE is still low here
   double underperform_mfe_r;
   int    timeout_bars;        // time stop unless the trade is already trailing
  };

void EEA_TradeProfileFor(const string profile,EEA_TradeProfile &p)
  {
   if(profile=="SWING")
     {
      p.be_at_r=1.0; p.partial_at_r=1.5; p.partial_fraction=0.33; p.trail_start_r=2.0;
      p.trail_mode=EEA_TM_TRAIL_STRUCTURE; p.trail_atr_mult=0.0; p.structure_bars=5;
      p.underperform_bars=15; p.underperform_mfe_r=0.5; p.timeout_bars=120;   // H1: 5 days
      return;
     }
   p.be_at_r=1.0; p.partial_at_r=1.0; p.partial_fraction=0.5; p.trail_start_r=1.5;
   p.trail_mode=EEA_TM_TRAIL_ATR; p.trail_atr_mult=1.0; p.structure_bars=0;
   p.underperform_bars=8; p.underperform_mfe_r=0.5; p.timeout_bars=36;        // M5: 3 hours
  }

struct EEA_ManagedTrade
  {
   bool   active;
   string profile;
   string timeframe;
   string authorization_path;
   string entry_ticket_kind;     // DEAL (market) or ORDER (pending)
   long   entry_ticket;
   string position_id;
   long   position_ticket;
   int    direction;
   double entry_price;
   double initial_sl;
   double initial_tp;
   double initial_volume;
   double zone_low;
   double zone_high;
   long   registered_at_utc;
   long   opened_at_utc;
   long   last_bar_time;
   int    bars;
   double mfe_r;
   double mae_r;
   int    bar_05r;
   int    bar_1r;
   int    bar_2r;
   string state;
   bool   be_done;
   bool   partial_done;
   bool   trail_active;
   bool   underperforming;
   int    action_seq;
   string last_reason;
   string exit_request;          // pending exit (structure/time stop) retried until the broker confirms
   EEA_ExecutionIntent intent;   // entry intent: every management request reuses its lineage
  };

struct EEA_TradeManagerRuntime
  {
   int count;
   bool loaded;
   string reason;
   EEA_ManagedTrade items[EEA_TM_MAX];
  };

void EEA_TradeManagerDefaults(EEA_TradeManagerRuntime &rt)
  {
   rt.count=0; rt.loaded=false; rt.reason="TRADE_MANAGER_IDLE";
   for(int i=0;i<EEA_TM_MAX;i++) rt.items[i].active=false;
  }

// ---------------------------------------------------------------------------
// Persistence: one file per managed trade, restored on attach.
// ---------------------------------------------------------------------------
string EEA_TradeManagerPath(const string root,const long entry_ticket)
  { return root+"/current/trade_"+IntegerToString(entry_ticket)+".json"; }

bool EEA_TradeManagerWrite(const string root,const EEA_ManagedTrade &t)
  {
   const EEA_ExecutionIntent i=t.intent;
   string json="{\"document_version\":\""+EEA_TM_DOCUMENT+"\","+
      EEA_PendingS("profile",t.profile)+EEA_PendingS("timeframe",t.timeframe)+
      EEA_PendingS("authorization_path",t.authorization_path)+EEA_PendingS("entry_ticket_kind",t.entry_ticket_kind)+
      EEA_PendingL("entry_ticket",t.entry_ticket)+EEA_PendingS("position_id",t.position_id)+
      EEA_PendingL("position_ticket",t.position_ticket)+EEA_PendingL("direction",t.direction)+
      EEA_PendingN("entry_price",t.entry_price)+EEA_PendingN("initial_sl",t.initial_sl)+
      EEA_PendingN("initial_tp",t.initial_tp)+EEA_PendingN("initial_volume",t.initial_volume)+
      EEA_PendingN("zone_low",t.zone_low)+EEA_PendingN("zone_high",t.zone_high)+
      EEA_PendingL("registered_at_utc",t.registered_at_utc)+EEA_PendingL("opened_at_utc",t.opened_at_utc)+
      EEA_PendingL("last_bar_time",t.last_bar_time)+EEA_PendingL("bars",t.bars)+
      EEA_PendingN("mfe_r",t.mfe_r)+EEA_PendingN("mae_r",t.mae_r)+EEA_PendingL("bar_05r",t.bar_05r)+
      EEA_PendingL("bar_1r",t.bar_1r)+EEA_PendingL("bar_2r",t.bar_2r)+EEA_PendingS("state",t.state)+
      EEA_PendingL("be_done",t.be_done ? 1 : 0)+EEA_PendingL("partial_done",t.partial_done ? 1 : 0)+
      EEA_PendingL("trail_active",t.trail_active ? 1 : 0)+EEA_PendingL("underperforming",t.underperforming ? 1 : 0)+
      EEA_PendingL("action_seq",t.action_seq)+EEA_PendingS("last_reason",t.last_reason)+
      EEA_PendingS("exit_request",t.exit_request)+
      EEA_PendingS("i_schema_version",i.schema_version)+EEA_PendingS("i_intent_id",i.intent_id)+
      EEA_PendingS("i_correlation_id",i.correlation_id)+EEA_PendingS("i_idempotency_key",i.idempotency_key)+
      EEA_PendingS("i_config_version",i.config_version)+EEA_PendingS("i_risk_policy_id",i.risk_policy_id)+
      EEA_PendingS("i_account_fingerprint",i.account_fingerprint)+EEA_PendingS("i_broker_server",i.broker_server)+
      EEA_PendingS("i_canonical_symbol",i.canonical_symbol)+EEA_PendingS("i_broker_symbol",i.broker_symbol)+
      EEA_PendingS("i_symbol_fingerprint",i.symbol_fingerprint)+EEA_PendingS("i_candidate_id",i.candidate_id)+
      EEA_PendingS("i_setup_id",i.setup_id)+EEA_PendingS("i_setup_version",i.setup_version)+
      EEA_PendingS("i_risk_decision_id",i.risk_decision_id)+EEA_PendingS("i_risk_decision_status",i.risk_decision_status)+
      EEA_PendingS("i_risk_policy_snapshot_id",i.risk_policy_snapshot_id)+
      EEA_PendingS("i_portfolio_snapshot_id",i.portfolio_snapshot_id)+EEA_PendingS("i_quote_snapshot_id",i.quote_snapshot_id)+
      EEA_PendingS("i_reconciliation_snapshot_id",i.reconciliation_snapshot_id)+EEA_PendingS("i_entry_reference",i.entry_reference)+
      EEA_PendingN("i_risk_budget",i.risk_budget)+EEA_PendingN("i_projected_loss",i.projected_loss)+
      EEA_PendingN("i_net_reward_risk",i.net_reward_risk)+
      EEA_PendingL("i_reconciliation_observed_at_utc",i.reconciliation_observed_at_utc)+
      EEA_PendingL("i_order_type",i.order_type)+EEA_PendingN("i_volume",i.volume)+EEA_PendingN("i_price",i.price)+
      EEA_PendingN("i_sl",i.sl)+EEA_PendingN("i_tp",i.tp)+EEA_PendingL("i_magic",i.magic)+
      EEA_PendingL("i_deviation",i.deviation)+EEA_PendingL("i_filling_mode",i.filling_mode)+
      "\"active\":"+(t.active ? "true" : "false")+"}";
   return EEA_WriteAtomicText(EEA_TradeManagerPath(root,t.entry_ticket),json);
  }

bool EEA_TradeManagerParse(const string json,EEA_ManagedTrade &t)
  {
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_TM_DOCUMENT) return false;
   EEA_ExecutionIntentDefaults(t.intent);
   t.active=StringFind(json,"\"active\":true")>=0;
   t.profile=EEA_RiskLedgerField(json,"profile"); t.timeframe=EEA_RiskLedgerField(json,"timeframe");
   t.authorization_path=EEA_RiskLedgerField(json,"authorization_path");
   t.entry_ticket_kind=EEA_RiskLedgerField(json,"entry_ticket_kind");
   t.entry_ticket=StringToInteger(EEA_RiskLedgerField(json,"entry_ticket"));
   t.position_id=EEA_RiskLedgerField(json,"position_id");
   t.position_ticket=StringToInteger(EEA_RiskLedgerField(json,"position_ticket"));
   t.direction=(int)StringToInteger(EEA_RiskLedgerField(json,"direction"));
   t.entry_price=StringToDouble(EEA_RiskLedgerField(json,"entry_price"));
   t.initial_sl=StringToDouble(EEA_RiskLedgerField(json,"initial_sl"));
   t.initial_tp=StringToDouble(EEA_RiskLedgerField(json,"initial_tp"));
   t.initial_volume=StringToDouble(EEA_RiskLedgerField(json,"initial_volume"));
   t.zone_low=StringToDouble(EEA_RiskLedgerField(json,"zone_low"));
   t.zone_high=StringToDouble(EEA_RiskLedgerField(json,"zone_high"));
   t.registered_at_utc=StringToInteger(EEA_RiskLedgerField(json,"registered_at_utc"));
   t.opened_at_utc=StringToInteger(EEA_RiskLedgerField(json,"opened_at_utc"));
   t.last_bar_time=StringToInteger(EEA_RiskLedgerField(json,"last_bar_time"));
   t.bars=(int)StringToInteger(EEA_RiskLedgerField(json,"bars"));
   t.mfe_r=StringToDouble(EEA_RiskLedgerField(json,"mfe_r"));
   t.mae_r=StringToDouble(EEA_RiskLedgerField(json,"mae_r"));
   t.bar_05r=(int)StringToInteger(EEA_RiskLedgerField(json,"bar_05r"));
   t.bar_1r=(int)StringToInteger(EEA_RiskLedgerField(json,"bar_1r"));
   t.bar_2r=(int)StringToInteger(EEA_RiskLedgerField(json,"bar_2r"));
   t.state=EEA_RiskLedgerField(json,"state");
   t.be_done=EEA_RiskLedgerField(json,"be_done")=="1";
   t.partial_done=EEA_RiskLedgerField(json,"partial_done")=="1";
   t.trail_active=EEA_RiskLedgerField(json,"trail_active")=="1";
   t.underperforming=EEA_RiskLedgerField(json,"underperforming")=="1";
   t.action_seq=(int)StringToInteger(EEA_RiskLedgerField(json,"action_seq"));
   t.last_reason=EEA_RiskLedgerField(json,"last_reason");
   t.exit_request=EEA_RiskLedgerField(json,"exit_request");
   EEA_ExecutionIntent i=t.intent;
   i.schema_version=EEA_RiskLedgerField(json,"i_schema_version");
   i.intent_id=EEA_RiskLedgerField(json,"i_intent_id");
   i.correlation_id=EEA_RiskLedgerField(json,"i_correlation_id");
   i.idempotency_key=EEA_RiskLedgerField(json,"i_idempotency_key");
   i.config_version=EEA_RiskLedgerField(json,"i_config_version");
   i.risk_policy_id=EEA_RiskLedgerField(json,"i_risk_policy_id");
   i.account_fingerprint=EEA_RiskLedgerField(json,"i_account_fingerprint");
   i.broker_server=EEA_RiskLedgerField(json,"i_broker_server");
   i.canonical_symbol=EEA_RiskLedgerField(json,"i_canonical_symbol");
   i.broker_symbol=EEA_RiskLedgerField(json,"i_broker_symbol");
   i.symbol_fingerprint=EEA_RiskLedgerField(json,"i_symbol_fingerprint");
   i.candidate_id=EEA_RiskLedgerField(json,"i_candidate_id");
   i.setup_id=EEA_RiskLedgerField(json,"i_setup_id");
   i.setup_version=EEA_RiskLedgerField(json,"i_setup_version");
   i.risk_decision_id=EEA_RiskLedgerField(json,"i_risk_decision_id");
   i.risk_decision_status=EEA_RiskLedgerField(json,"i_risk_decision_status");
   i.risk_policy_snapshot_id=EEA_RiskLedgerField(json,"i_risk_policy_snapshot_id");
   i.portfolio_snapshot_id=EEA_RiskLedgerField(json,"i_portfolio_snapshot_id");
   i.quote_snapshot_id=EEA_RiskLedgerField(json,"i_quote_snapshot_id");
   i.reconciliation_snapshot_id=EEA_RiskLedgerField(json,"i_reconciliation_snapshot_id");
   i.entry_reference=EEA_RiskLedgerField(json,"i_entry_reference");
   i.risk_budget=StringToDouble(EEA_RiskLedgerField(json,"i_risk_budget"));
   i.projected_loss=StringToDouble(EEA_RiskLedgerField(json,"i_projected_loss"));
   i.net_reward_risk=StringToDouble(EEA_RiskLedgerField(json,"i_net_reward_risk"));
   i.reconciliation_observed_at_utc=StringToInteger(EEA_RiskLedgerField(json,"i_reconciliation_observed_at_utc"));
   i.order_type=(int)StringToInteger(EEA_RiskLedgerField(json,"i_order_type"));
   i.volume=StringToDouble(EEA_RiskLedgerField(json,"i_volume"));
   i.price=StringToDouble(EEA_RiskLedgerField(json,"i_price"));
   i.sl=StringToDouble(EEA_RiskLedgerField(json,"i_sl"));
   i.tp=StringToDouble(EEA_RiskLedgerField(json,"i_tp"));
   i.magic=StringToInteger(EEA_RiskLedgerField(json,"i_magic"));
   i.deviation=(int)StringToInteger(EEA_RiskLedgerField(json,"i_deviation"));
   i.filling_mode=(int)StringToInteger(EEA_RiskLedgerField(json,"i_filling_mode"));
   t.intent=i;
   return t.entry_ticket>0 && (t.direction==1 || t.direction==-1) && t.initial_sl>0.0 && i.intent_id!="";
  }

// Restores every active managed trade. An unreadable file is reported; the position
// itself keeps its broker stop, so nothing is left unprotected.
bool EEA_TradeManagerLoad(EEA_TradeManagerRuntime &rt,const string root)
  {
   EEA_TradeManagerDefaults(rt);
   rt.loaded=true;
   string name;
   long handle=FileFindFirst(root+"/current/trade_*.json",name);
   if(handle==INVALID_HANDLE) { rt.reason="TRADE_MANAGER_EMPTY"; return true; }
   bool ok=true;
   do
     {
      string json;
      EEA_ManagedTrade t;
      if(!EEA_PendingReadText(root+"/current/"+name,json) || !EEA_TradeManagerParse(json,t))
        { ok=false; continue; }
      if(!t.active || rt.count>=EEA_TM_MAX) continue;
      rt.items[rt.count]=t; rt.count++;
     }
   while(FileFindNext(handle,name));
   FileFindClose(handle);
   rt.reason=ok ? "TRADE_MANAGER_LOADED" : "TRADE_MANAGER_FILE_UNREADABLE";
   return ok;
  }

// Registers a position-to-be right after the broker acknowledged the entry (market deal
// or pending order). The entry intent carries the full risk lineage.
bool EEA_TradeManagerRegister(EEA_TradeManagerRuntime &rt,const string root,const EEA_ExecutionIntent &intent,
                              const long ticket,const string ticket_kind,const string profile,
                              const string timeframe,const double zone_low,const double zone_high,
                              const string authorization_path,string &reason)
  {
   if(ticket<=0 || intent.sl<=0.0) { reason="TRADE_MANAGER_REGISTER_INVALID"; return false; }
   int slot=-1;
   for(int i=0;i<rt.count;i++) if(!rt.items[i].active) { slot=i; break; }
   if(slot<0)
     {
      if(rt.count>=EEA_TM_MAX) { reason="TRADE_MANAGER_FULL"; return false; }
      slot=rt.count; rt.count++;
     }
   EEA_ManagedTrade t;
   t.active=true; t.profile=profile; t.timeframe=timeframe; t.authorization_path=authorization_path;
   t.entry_ticket_kind=ticket_kind; t.entry_ticket=ticket; t.position_id=""; t.position_ticket=0;
   t.direction=EEA_OrderTypeDirection(intent.order_type);
   t.entry_price=intent.price; t.initial_sl=intent.sl; t.initial_tp=intent.tp; t.initial_volume=intent.volume;
   t.zone_low=zone_low; t.zone_high=zone_high; t.registered_at_utc=(long)TimeGMT(); t.opened_at_utc=0;
   t.last_bar_time=0; t.bars=0; t.mfe_r=0.0; t.mae_r=0.0; t.bar_05r=-1; t.bar_1r=-1; t.bar_2r=-1;
   t.state="ENTERED"; t.be_done=false; t.partial_done=false; t.trail_active=false; t.underperforming=false;
   t.action_seq=0; t.last_reason="REGISTERED"; t.exit_request=""; t.intent=intent;
   rt.items[slot]=t;
   if(!EEA_TradeManagerWrite(root,t)) { reason="TRADE_MANAGER_PERSISTENCE_FAILED"; return false; }
   reason="TRADE_MANAGER_REGISTERED";
   return true;
  }

bool EEA_TradeManagerHasCandidate(const EEA_TradeManagerRuntime &rt,const string candidate_id)
  {
   for(int i=0;i<rt.count;i++)
      if(rt.items[i].active && rt.items[i].intent.candidate_id==candidate_id) return true;
   return false;
  }

// ---------------------------------------------------------------------------
// Broker linkage
// ---------------------------------------------------------------------------
// Finds the entry deal of a trade (market: the deal itself; pending: the IN deal of the
// order) and returns its position id and fill price.
bool EEA_TradeManagerFindEntryDeal(const EEA_ManagedTrade &t,const EEA_RuntimeReconciliationSnapshot &r,
                                   string &position_id,double &price,long &time_utc)
  {
   for(int i=0;i<r.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      bool match=(t.entry_ticket_kind=="DEAL") ? r.deals[i].deal_ticket==t.entry_ticket :
                 (r.deals[i].order_ticket==t.entry_ticket && r.deals[i].entry=="0");
      if(!match || r.deals[i].position_id=="" || r.deals[i].position_id=="0") continue;
      position_id=r.deals[i].position_id; price=r.deals[i].price; time_utc=r.deals[i].time_utc;
      return true;
     }
   return false;
  }

int EEA_TradeManagerFindPosition(const EEA_ManagedTrade &t,const EEA_RuntimeReconciliationSnapshot &r)
  {
   if(t.position_id=="") return -1;
   for(int i=0;i<r.position_count;i++) if(r.positions[i].position_id==t.position_id) return i;
   return -1;
  }

bool EEA_TradeManagerOrderPending(const EEA_ManagedTrade &t,const EEA_RuntimeReconciliationSnapshot &r)
  {
   if(t.entry_ticket_kind!="ORDER") return false;
   for(int i=0;i<r.order_count;i++) if(r.orders[i].ticket==t.entry_ticket) return true;
   return false;
  }

// ---------------------------------------------------------------------------
// Management actions
// ---------------------------------------------------------------------------
bool EEA_TradeManagerAuthorization(const EEA_ManagedTrade &t,const string account_mode,
                                   EEA_LiveAuthorizationDecision &authorization,string &reason)
  {
   if(StringFind(t.authorization_path,"live_session.json")>=0)
      return EEA_LiveSessionCancelAuthorization(t.authorization_path,t.intent.intent_id,t.intent.candidate_id,
                                                t.intent.config_version,t.intent.account_fingerprint,
                                                t.intent.broker_server,account_mode,t.intent.broker_symbol,
                                                t.intent.risk_policy_id,authorization,reason);
   EEA_LiveAuthorizationContext context;
   return EEA_LiveAuthorizationStoreLoad(t.authorization_path,t.intent.config_version,t.intent.account_fingerprint,
                                         t.intent.broker_server,t.intent.broker_symbol,context,authorization,reason);
  }

bool EEA_TradeManagerAudit(CAuditLog &audit,const EEA_ManagedTrade &t,const string event_type,const string reason)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),t.intent.canonical_symbol,t.intent.candidate_id,"",t.state,"OK");
   event.config_version=t.intent.config_version;
   EEAEvent_AddReason(event,reason);
   event.details_json="{\"position_id\":\""+EEA_JsonEscape(t.position_id)+"\",\"profile\":\""+EEA_JsonEscape(t.profile)+
      "\",\"bars\":"+IntegerToString(t.bars)+",\"mfe_r\":"+DoubleToString(t.mfe_r,3)+
      ",\"mae_r\":"+DoubleToString(t.mae_r,3)+",\"bar_05r\":"+IntegerToString(t.bar_05r)+
      ",\"bar_1r\":"+IntegerToString(t.bar_1r)+",\"bar_2r\":"+IntegerToString(t.bar_2r)+
      ",\"reason\":\""+EEA_JsonEscape(reason)+"\"}";
   return audit.Append(event,"EA_TRADE_MANAGER");
  }

int EEA_TradeManagerSymbolRow(const EEA_ObserverRuntimeContext &observer,const string broker_symbol)
  {
   for(int k=0;k<observer.symbol_count;k++) if(observer.broker_symbols[k]==broker_symbol) return k;
   return -1;
  }

// New stop for the position. Only ever tightens and respects the broker stop distance.
bool EEA_TradeManagerModifyStop(EEA_ManagedTrade &t,CAuditLog &audit,const string root,
                                const EEA_ObserverRuntimeContext &observer,const EEA_RuntimePositionRow &position,
                                const bool execution_enabled,double new_sl,const string why,string &reason)
  {
   int row=EEA_TradeManagerSymbolRow(observer,t.intent.broker_symbol);
   if(row<0) { reason="TRADE_MANAGER_SYMBOL_UNAVAILABLE"; return false; }
   const EEA_RuntimeSymbolSpec spec=observer.symbol_specs[row];
   new_sl=MathRound(new_sl/spec.tick_size)*spec.tick_size;
   if(position.sl>0.0 && t.direction*(new_sl-position.sl)<=spec.tick_size*0.5)
     { reason="TRADE_MANAGER_STOP_NOT_TIGHTER"; return false; }
   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(t.intent.broker_symbol,tick)) { reason="TRADE_MANAGER_QUOTE_UNAVAILABLE"; return false; }
   const double exit_price=(t.direction==1 ? tick.bid : tick.ask);
   const double min_gap=MathMax(spec.stops_level_points,spec.freeze_level_points)*spec.point+spec.tick_size;
   if(t.direction*(exit_price-new_sl)<min_gap) { reason="TRADE_MANAGER_STOP_TOO_CLOSE"; return false; }
   EEA_LiveAuthorizationDecision authorization;
   if(!EEA_TradeManagerAuthorization(t,observer.account.account_margin_mode,authorization,reason)) return false;
   EEA_ExecutionIntent modify=t.intent;
   modify.action=EEA_EXEC_ACTION_MODIFY_PROTECTIVE;
   modify.position_ticket=position.ticket;
   modify.ticket=0;
   modify.sl=new_sl;
   modify.tp=position.tp;
   modify.volume=position.volume;
   t.action_seq++;
   modify.idempotency_key="manage-"+t.intent.candidate_id+"-sl-"+IntegerToString(t.action_seq);
   modify.intent_created_at_utc=TimeGMT();
   EEA_ExecutionResult result;
   if(!EEA_ExecutionModifyProtective(audit,root,modify,observer.account,observer.reconciliation,spec,
                                     observer.status,execution_enabled,authorization,result))
     { reason="TRADE_MANAGER_MODIFY_FAILED_"+result.reason_code; return false; }
   reason=why;
   return true;
  }

bool EEA_TradeManagerClose(EEA_ManagedTrade &t,CAuditLog &audit,const string root,
                           const EEA_ObserverRuntimeContext &observer,const EEA_RuntimePositionRow &position,
                           const bool execution_enabled,const double volume,const string why,string &reason)
  {
   int row=EEA_TradeManagerSymbolRow(observer,t.intent.broker_symbol);
   if(row<0) { reason="TRADE_MANAGER_SYMBOL_UNAVAILABLE"; return false; }
   const EEA_RuntimeSymbolSpec spec=observer.symbol_specs[row];
   EEA_LiveAuthorizationDecision authorization;
   if(!EEA_TradeManagerAuthorization(t,observer.account.account_margin_mode,authorization,reason)) return false;
   EEA_ExecutionIntent close=t.intent;
   close.action=EEA_EXEC_ACTION_CLOSE_POSITION;
   close.position_ticket=position.ticket;
   close.ticket=0;
   close.order_type=(t.direction==1 ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
   close.volume=volume;
   close.sl=0.0; close.tp=0.0;
   t.action_seq++;
   close.idempotency_key="manage-"+t.intent.candidate_id+"-close-"+IntegerToString(t.action_seq);
   close.intent_created_at_utc=TimeGMT();
   EEA_ExecutionResult result;
   if(!EEA_ExecutionClosePosition(audit,root,close,observer.account,observer.reconciliation,spec,
                                  observer.status,execution_enabled,authorization,result))
     { reason="TRADE_MANAGER_CLOSE_FAILED_"+result.reason_code; return false; }
   reason=why;
   return true;
  }

// Extreme of the last `count` closed bars on the trade timeframe (STRUCTURE trail).
bool EEA_TradeManagerSwingExtreme(const EEA_ManagedTrade &t,const int count,double &extreme)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   if(count<1 || CopyRates(t.intent.broker_symbol,EEA_PendingTimeframe(t.timeframe),1,count,rates)!=count) return false;
   extreme=(t.direction==1 ? rates[0].low : rates[0].high);
   for(int i=1;i<count;i++)
      extreme=(t.direction==1 ? MathMin(extreme,rates[i].low) : MathMax(extreme,rates[i].high));
   return true;
  }

double EEA_TradeManagerAtr(const EEA_ManagedTrade &t,MqlRates &last_closed)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(t.intent.broker_symbol,EEA_PendingTimeframe(t.timeframe),1,EEA_STRATEGY_RUNTIME_ATR_PERIOD+1,rates);
   if(copied<EEA_STRATEGY_RUNTIME_ATR_PERIOD+1) return 0.0;
   last_closed=rates[copied-1];
   return EEA_StrategyRuntimeAtrFromRates(rates,copied-1,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
  }

// Feeds newly closed bars of the trade timeframe: excursions, milestones and lifecycle.
// Returns the exit reason when a closed bar invalidates the structure or the time stop hits.
string EEA_TradeManagerObserveBars(EEA_ManagedTrade &t,const EEA_TradeProfile &p,CAuditLog &audit)
  {
   const double r=MathAbs(t.entry_price-t.initial_sl);
   if(r<=0.0) return "";
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(t.intent.broker_symbol,EEA_PendingTimeframe(t.timeframe),1,64,rates);
   if(copied<=0) return "";
   long offset=EEA_PendingServerOffset();
   long tf_seconds=PeriodSeconds(EEA_PendingTimeframe(t.timeframe));
   string exit_reason="";
   for(int b=0;b<copied;b++)
     {
      long bar_time=(long)rates[b].time;
      if(bar_time<=t.last_bar_time) continue;
      if(bar_time-offset+tf_seconds<=t.opened_at_utc) continue;      // bar closed before the fill
      t.last_bar_time=bar_time;
      t.bars++;
      double favorable=t.direction==1 ? rates[b].high-t.entry_price : t.entry_price-rates[b].low;
      double adverse=t.direction==1 ? t.entry_price-rates[b].low : rates[b].high-t.entry_price;
      t.mfe_r=MathMax(t.mfe_r,favorable/r);
      t.mae_r=MathMax(t.mae_r,adverse/r);
      if(t.bar_05r<0 && t.mfe_r>=0.5) t.bar_05r=t.bars;
      if(t.bar_1r<0 && t.mfe_r>=1.0) t.bar_1r=t.bars;
      if(t.bar_2r<0 && t.mfe_r>=2.0) t.bar_2r=t.bars;
      string before=t.state;
      if(t.state=="ENTERED") t.state="PROVING";
      if(t.state=="PROVING" && t.mfe_r>=0.5) t.state="WORKING";
      if(t.state=="WORKING" && (t.mfe_r>=1.0 || t.trail_active)) t.state="MATURE";
      if(before!=t.state) EEA_TradeManagerAudit(audit,t,"TRADE_STATE_CHANGED",before+"->"+t.state);
      if(!t.underperforming && t.bars==p.underperform_bars && t.mfe_r<p.underperform_mfe_r)
        {
         t.underperforming=true;                                   // TC-012: flag only
         EEA_TradeManagerAudit(audit,t,"TRADE_UNDERPERFORMING","MFE_BELOW_EXPECTED_PATH");
        }
      // TC-013: a close back through the far edge of the zone ends the thesis before the SL.
      if(!t.be_done && t.zone_low>0.0 && t.zone_high>t.zone_low &&
         ((t.direction==1 && rates[b].close<t.zone_low) || (t.direction==-1 && rates[b].close>t.zone_high)))
         exit_reason="STRUCTURE_INVALIDATED";
      if(exit_reason=="" && t.bars>=p.timeout_bars && !t.trail_active) exit_reason="TIME_STOP";
     }
   return exit_reason;
  }

// One timer pass over every managed trade. `entries_permitted` is false once the session
// was revoked or expired: then only a break-even move of a profitable position is allowed.
void EEA_TradeManagerUpdate(EEA_TradeManagerRuntime &rt,CAuditLog &audit,const string root,
                            const EEA_ObserverRuntimeContext &observer,const bool execution_enabled,
                            const bool entries_permitted,const EEA_NewsRuntime &news)
  {
   if(observer.status.runtime_state!="OBSERVING") { rt.reason="TRADE_MANAGER_WAIT_RUNTIME"; return; }
   int managed=0;
   for(int i=0;i<rt.count;i++)
     {
      if(!rt.items[i].active) continue;
      EEA_ManagedTrade t=rt.items[i];
      string fingerprint=t.state+"|"+IntegerToString(t.bars)+"|"+IntegerToString(t.action_seq)+"|"+t.position_id+t.exit_request+
                         (t.be_done ? "B" : "")+(t.partial_done ? "P" : "")+(t.trail_active ? "T" : "");
      string reason="";
      if(t.position_id=="")
        {
         string position_id=""; double price=0.0; long time_utc=0;
         if(EEA_TradeManagerFindEntryDeal(t,observer.reconciliation,position_id,price,time_utc))
           {
            t.position_id=position_id; t.entry_price=price; t.opened_at_utc=time_utc;
            EEA_TradeManagerAudit(audit,t,"TRADE_ENTERED","ENTRY_DEAL_LINKED");
           }
         else if(!EEA_TradeManagerOrderPending(t,observer.reconciliation) &&
                 (long)TimeGMT()-t.registered_at_utc>(t.entry_ticket_kind=="DEAL" ? 600 : 14*86400))
           {
            // Never filled (pending cancelled or expired) or no entry deal in history.
            t.active=false; t.state="EXITED"; t.last_reason="ENTRY_NOT_FILLED";
            EEA_TradeManagerAudit(audit,t,"TRADE_NOT_FILLED","ENTRY_NOT_FILLED");
           }
        }
      if(t.active && t.position_id!="")
        {
         int prow=EEA_TradeManagerFindPosition(t,observer.reconciliation);
         if(prow<0)
           {
            t.active=false; t.state="EXITED"; t.last_reason="POSITION_CLOSED";
            EEA_TradeManagerAudit(audit,t,"TRADE_EXITED","POSITION_CLOSED");
           }
         else
           {
            managed++;
            const EEA_RuntimePositionRow position=observer.reconciliation.positions[prow];
            t.position_ticket=position.ticket;
            EEA_TradeProfile p; EEA_TradeProfileFor(t.profile,p);
            string exit_reason=EEA_TradeManagerObserveBars(t,p,audit);
            if(exit_reason!="" && t.exit_request=="")
              { t.exit_request=exit_reason; EEA_TradeManagerAudit(audit,t,"TRADE_EXIT_REQUIRED",exit_reason); }
            const double r=MathAbs(t.entry_price-t.initial_sl);
            MqlTick tick; ZeroMemory(tick);
            bool quote=SymbolInfoTick(t.intent.broker_symbol,tick) && tick.bid>0.0 && tick.ask>0.0;
            double now_r=(quote && r>0.0) ? t.direction*((t.direction==1 ? tick.bid : tick.ask)-t.entry_price)/r : 0.0;
            if(quote && r>0.0) t.mfe_r=MathMax(t.mfe_r,now_r);
            double spread=quote ? tick.ask-tick.bid : 0.0;
            double be_price=t.entry_price+t.direction*spread;
            if(!entries_permitted)
              {
               // Session revoked or expired: break-even for a profitable position, nothing else.
               if(!t.be_done && quote && now_r>0.0 &&
                  EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,be_price,
                                             "SESSION_REVOKED_BREAK_EVEN",reason))
                  t.be_done=true;
              }
            else if(t.exit_request!="")
              {
               EEA_TradeManagerClose(t,audit,root,observer,position,execution_enabled,position.volume,t.exit_request,reason);
              }
            else if(!t.be_done && quote && r>0.0 && now_r>=news.cfg.be_min_r &&
                    EEA_NewsBreakEvenDueFor(news,t.intent.canonical_symbol))
              {
               // News Guard D2: a profitable position goes to break-even before a HIGH impact
               // event. The guard never closes a position (D5).
               if(EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,be_price,
                                             "NEWS_BREAK_EVEN",reason))
                  t.be_done=true;
              }
            else if(quote && r>0.0)
              {
               int row=EEA_TradeManagerSymbolRow(observer,t.intent.broker_symbol);
               double step=row>=0 ? observer.symbol_specs[row].volume_step : 0.0;
               double vmin=row>=0 ? observer.symbol_specs[row].volume_min : 0.0;
               if(!t.partial_done && t.mfe_r>=p.partial_at_r && step>0.0)
                 {
                  double part=MathFloor(position.volume*p.partial_fraction/step)*step;
                  if(part>=vmin && position.volume-part>=vmin)
                    {
                     if(EEA_TradeManagerClose(t,audit,root,observer,position,execution_enabled,part,
                                              "PARTIAL_AT_"+DoubleToString(p.partial_at_r,1)+"R",reason))
                        t.partial_done=true;
                    }
                  else
                    { t.partial_done=true; reason="PARTIAL_SKIPPED_MIN_VOLUME"; }
                 }
               else if(!t.be_done && t.mfe_r>=p.be_at_r)
                 {
                  if(EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,be_price,
                                                "BREAK_EVEN",reason))
                     t.be_done=true;
                 }
               else if(t.mfe_r>=p.trail_start_r)
                 {
                  t.trail_active=true;
                  double trail=0.0;
                  if(p.trail_mode==EEA_TM_TRAIL_STRUCTURE)
                    {
                     double extreme=0.0; MqlRates last; double atr=EEA_TradeManagerAtr(t,last);
                     if(EEA_TradeManagerSwingExtreme(t,p.structure_bars,extreme) && atr>0.0)
                        trail=extreme-t.direction*0.1*atr;
                    }
                  else
                    {
                     MqlRates last; double atr=EEA_TradeManagerAtr(t,last);
                     if(atr>0.0) trail=last.close-t.direction*p.trail_atr_mult*atr;
                    }
                  // A trail never loosens the stop below break-even.
                  if(trail>0.0 && t.direction*(trail-be_price)>0.0 &&
                     t.direction*(trail-position.sl)>=0.1*r)
                     EEA_TradeManagerModifyStop(t,audit,root,observer,position,execution_enabled,trail,
                                                p.trail_mode==EEA_TM_TRAIL_STRUCTURE ? "TRAIL_STRUCTURE" : "TRAIL_ATR",reason);
                 }
              }
            if(reason!="" && reason!=t.last_reason)
              {
               t.last_reason=reason;
               EEA_TradeManagerAudit(audit,t,"TRADE_MANAGEMENT",reason);
              }
           }
        }
      string after=t.state+"|"+IntegerToString(t.bars)+"|"+IntegerToString(t.action_seq)+"|"+t.position_id+t.exit_request+
                   (t.be_done ? "B" : "")+(t.partial_done ? "P" : "")+(t.trail_active ? "T" : "");
      if(after!=fingerprint || !t.active)
         EEA_TradeManagerWrite(root,t);
      rt.items[i]=t;
     }
   rt.reason="TRADE_MANAGER_ACTIVE_"+IntegerToString(managed);
  }

#endif
