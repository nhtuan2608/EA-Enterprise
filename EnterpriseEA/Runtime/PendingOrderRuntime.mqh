#ifndef ENTERPRISE_EA_PENDING_ORDER_RUNTIME_MQH
#define ENTERPRISE_EA_PENDING_ORDER_RUNTIME_MQH

#include "..\TradeManager\PendingOrderLifecycle.mqh"
#include "..\Storage\RiskLedgerStore.mqh"
#include "..\Storage\LiveAuthorizationStore.mqh"
#include "ExecutionAdapter.mqh"
#include "ObserverRuntime.mqh"
#include "StrategyCandidateRuntime.mqh"

// REQ-021 runtime: tracks every LIMIT/STOP order the EA placed, reconciles it with the
// broker on each timer (fills, partial fills, cancellations, expiries), observes each
// closed setup bar, and requests cancellation when the deadline, the bar limit, the
// setup or the risk/quote premise ends. Risk of the unfilled remainder stays reserved
// until the broker confirms the order is gone. Anything ambiguous blocks new entries.
#define EEA_PENDING_MAX_TRACKED 16
#define EEA_PENDING_DOCUMENT "pending-order-v1.0.0"

struct EEA_PendingTracked
  {
   bool   active;
   string timeframe;            // setup entry timeframe: M5 (SCALP) or H1 (SWING)
   string broker_symbol;
   string authorization_path;
   string symbol_fingerprint;   // instrument spec at placement
   double max_spread_points;    // quote premise at placement
   long   last_bar_time;        // last observed closed entry bar (server time)
   long   bar_sequence;
   int    cancel_attempts;
   EEA_ExecutionIntent intent;  // the placement intent; cancellation reuses its lineage
   EEA_PendingState state;
  };

struct EEA_PendingRuntime
  {
   int count;
   bool loaded;
   bool entries_blocked;
   string reason;
   EEA_PendingTracked items[EEA_PENDING_MAX_TRACKED];
  };

void EEA_PendingRuntimeDefaults(EEA_PendingRuntime &rt)
  {
   rt.count=0; rt.loaded=false; rt.entries_blocked=false; rt.reason="PENDING_RUNTIME_IDLE";
   for(int i=0;i<EEA_PENDING_MAX_TRACKED;i++) rt.items[i].active=false;
  }

bool EEA_PendingRuntimeHasCandidate(const EEA_PendingRuntime &rt,const string candidate_id)
  {
   for(int i=0;i<rt.count;i++)
      if(rt.items[i].active && rt.items[i].state.candidate_id==candidate_id) return true;
   return false;
  }

bool EEA_PendingRuntimeHasEngine(const EEA_PendingRuntime &rt,const string canonical,const string timeframe)
  {
   for(int i=0;i<rt.count;i++)
      if(rt.items[i].active && rt.items[i].state.canonical_symbol==canonical && rt.items[i].timeframe==timeframe)
         return true;
   return false;
  }

long EEA_PendingServerOffset()
  {
   return (long)MathRound(((double)TimeTradeServer()-(double)TimeGMT())/900.0)*900;
  }

ENUM_TIMEFRAMES EEA_PendingTimeframe(const string timeframe)
  {
   return timeframe=="H1" ? PERIOD_H1 : PERIOD_M5;
  }

string EEA_PendingOrderTypeName(const int order_type)
  {
   if(order_type==ORDER_TYPE_BUY_LIMIT) return "BUY_LIMIT";
   if(order_type==ORDER_TYPE_SELL_LIMIT) return "SELL_LIMIT";
   if(order_type==ORDER_TYPE_BUY_STOP) return "BUY_STOP";
   if(order_type==ORDER_TYPE_SELL_STOP) return "SELL_STOP";
   return "";
  }

// ---------------------------------------------------------------------------
// Persistence: one file per tracked order, restored on attach.
// ---------------------------------------------------------------------------
string EEA_PendingPath(const string root,const string ticket) { return root+"/current/pending_"+ticket+".json"; }

string EEA_PendingS(const string name,const string value) { return "\""+name+"\":\""+EEA_JsonEscape(value)+"\","; }
string EEA_PendingN(const string name,const double value) { return "\""+name+"\":"+DoubleToString(value,10)+","; }
string EEA_PendingL(const string name,const long value) { return "\""+name+"\":"+IntegerToString(value)+","; }

bool EEA_PendingWrite(const string root,const EEA_PendingTracked &t)
  {
   const EEA_PendingState s=t.state;
   const EEA_ExecutionIntent i=t.intent;
   string json="{\"document_version\":\""+EEA_PENDING_DOCUMENT+"\","+
      EEA_PendingS("timeframe",t.timeframe)+EEA_PendingS("broker_symbol",t.broker_symbol)+
      EEA_PendingS("authorization_path",t.authorization_path)+EEA_PendingS("symbol_fingerprint",t.symbol_fingerprint)+
      EEA_PendingN("max_spread_points",t.max_spread_points)+EEA_PendingL("last_bar_time",t.last_bar_time)+
      EEA_PendingL("bar_sequence",t.bar_sequence)+EEA_PendingL("cancel_attempts",t.cancel_attempts)+
      EEA_PendingS("status",s.status)+EEA_PendingS("reason_code",s.reason_code)+EEA_PendingS("cancel_reason",s.cancel_reason)+
      EEA_PendingS("intent_id",s.intent_id)+EEA_PendingS("candidate_id",s.candidate_id)+EEA_PendingS("setup_id",s.setup_id)+
      EEA_PendingS("setup_version",s.setup_version)+EEA_PendingS("config_version",s.config_version)+
      EEA_PendingS("instrument_version",s.instrument_version)+EEA_PendingS("canonical_symbol",s.canonical_symbol)+
      EEA_PendingS("account_currency",s.account_currency)+EEA_PendingS("broker_server",s.broker_server)+
      EEA_PendingS("account_fingerprint",s.account_fingerprint)+EEA_PendingS("order_ticket",s.order_ticket)+
      EEA_PendingS("trade_style",s.trade_style)+EEA_PendingS("order_type",s.order_type)+
      EEA_PendingL("broker_accepted_at_utc",(long)s.broker_accepted_at_utc)+
      EEA_PendingL("effective_expires_at_utc",(long)s.effective_expires_at_utc)+
      EEA_PendingL("cancel_required_at_utc",(long)s.cancel_required_at_utc)+
      EEA_PendingL("cancel_requested_at_utc",(long)s.cancel_requested_at_utc)+
      EEA_PendingL("broker_confirmed_at_utc",(long)s.broker_confirmed_at_utc)+
      EEA_PendingS("cancel_correlation_id",s.cancel_correlation_id)+
      EEA_PendingL("last_closed_bar_sequence",s.last_closed_bar_sequence)+
      EEA_PendingL("last_bar_closed_at_utc",(long)s.last_bar_closed_at_utc)+
      EEA_PendingS("last_bar_fingerprint",s.last_bar_fingerprint)+EEA_PendingS("last_setup_snapshot_id",s.last_setup_snapshot_id)+
      EEA_PendingL("max_wait_closed_bars",s.max_wait_closed_bars)+EEA_PendingL("bars_waited",s.bars_waited)+
      EEA_PendingL("last_event_sequence",s.last_event_sequence)+EEA_PendingL("last_event_at_utc",(long)s.last_event_at_utc)+
      EEA_PendingS("last_event_id",s.last_event_id)+EEA_PendingS("last_event_fingerprint",s.last_event_fingerprint)+
      EEA_PendingN("requested_volume",s.requested_volume)+EEA_PendingN("filled_volume",s.filled_volume)+
      EEA_PendingN("cancelled_volume",s.cancelled_volume)+EEA_PendingN("remaining_volume",s.remaining_volume)+
      EEA_PendingN("volume_step",s.volume_step)+EEA_PendingN("reserved_risk_per_lot_money",s.reserved_risk_per_lot_money)+
      EEA_PendingN("max_committed_risk_money",s.max_committed_risk_money)+
      EEA_PendingN("filled_initial_risk_money",s.filled_initial_risk_money)+
      EEA_PendingN("remaining_risk_reservation_money",s.remaining_risk_reservation_money)+
      EEA_PendingN("total_committed_risk_money",s.total_committed_risk_money)+
      EEA_PendingS("i_schema_version",i.schema_version)+EEA_PendingS("i_correlation_id",i.correlation_id)+
      EEA_PendingS("i_idempotency_key",i.idempotency_key)+EEA_PendingS("i_risk_policy_id",i.risk_policy_id)+
      EEA_PendingS("i_symbol_fingerprint",i.symbol_fingerprint)+EEA_PendingS("i_risk_decision_id",i.risk_decision_id)+
      EEA_PendingS("i_risk_decision_status",i.risk_decision_status)+
      EEA_PendingS("i_risk_policy_snapshot_id",i.risk_policy_snapshot_id)+
      EEA_PendingS("i_portfolio_snapshot_id",i.portfolio_snapshot_id)+EEA_PendingS("i_quote_snapshot_id",i.quote_snapshot_id)+
      EEA_PendingS("i_reconciliation_snapshot_id",i.reconciliation_snapshot_id)+EEA_PendingS("i_entry_reference",i.entry_reference)+
      EEA_PendingN("i_risk_budget",i.risk_budget)+EEA_PendingN("i_projected_loss",i.projected_loss)+
      EEA_PendingN("i_net_reward_risk",i.net_reward_risk)+
      EEA_PendingL("i_reconciliation_observed_at_utc",i.reconciliation_observed_at_utc)+
      EEA_PendingL("i_order_type",i.order_type)+EEA_PendingN("i_volume",i.volume)+EEA_PendingN("i_price",i.price)+
      EEA_PendingN("i_sl",i.sl)+EEA_PendingN("i_tp",i.tp)+EEA_PendingL("i_magic",i.magic)+
      EEA_PendingL("i_deviation",i.deviation)+EEA_PendingL("i_filling_mode",i.filling_mode)+
      EEA_PendingL("i_expiration",(long)i.expiration)+
      "\"active\":"+(t.active ? "true" : "false")+"}";
   return EEA_WriteAtomicText(EEA_PendingPath(root,s.order_ticket),json);
  }

bool EEA_PendingReadText(const string path,string &json)
  {
   json="";
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   ulong size=FileSize(handle);
   if(size==0 || size>65536) { FileClose(handle); return false; }
   uchar bytes[];
   ArrayResize(bytes,(int)size);
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return false;
   json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   return true;
  }

bool EEA_PendingParse(const string json,EEA_PendingTracked &t)
  {
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_PENDING_DOCUMENT) return false;
   EEA_PendingDefaults(t.state);
   EEA_ExecutionIntentDefaults(t.intent);
   EEA_PendingState s=t.state;
   t.active=StringFind(json,"\"active\":true")>=0;
   t.timeframe=EEA_RiskLedgerField(json,"timeframe");
   t.broker_symbol=EEA_RiskLedgerField(json,"broker_symbol");
   t.authorization_path=EEA_RiskLedgerField(json,"authorization_path");
   t.symbol_fingerprint=EEA_RiskLedgerField(json,"symbol_fingerprint");
   t.max_spread_points=StringToDouble(EEA_RiskLedgerField(json,"max_spread_points"));
   t.last_bar_time=StringToInteger(EEA_RiskLedgerField(json,"last_bar_time"));
   t.bar_sequence=StringToInteger(EEA_RiskLedgerField(json,"bar_sequence"));
   t.cancel_attempts=(int)StringToInteger(EEA_RiskLedgerField(json,"cancel_attempts"));
   s.initialized=true;
   s.status=EEA_RiskLedgerField(json,"status"); s.reason_code=EEA_RiskLedgerField(json,"reason_code");
   s.cancel_reason=EEA_RiskLedgerField(json,"cancel_reason"); s.intent_id=EEA_RiskLedgerField(json,"intent_id");
   s.candidate_id=EEA_RiskLedgerField(json,"candidate_id"); s.setup_id=EEA_RiskLedgerField(json,"setup_id");
   s.setup_version=EEA_RiskLedgerField(json,"setup_version"); s.config_version=EEA_RiskLedgerField(json,"config_version");
   s.instrument_version=EEA_RiskLedgerField(json,"instrument_version");
   s.canonical_symbol=EEA_RiskLedgerField(json,"canonical_symbol");
   s.account_currency=EEA_RiskLedgerField(json,"account_currency");
   s.broker_server=EEA_RiskLedgerField(json,"broker_server");
   s.account_fingerprint=EEA_RiskLedgerField(json,"account_fingerprint");
   s.order_ticket=EEA_RiskLedgerField(json,"order_ticket"); s.trade_style=EEA_RiskLedgerField(json,"trade_style");
   s.order_type=EEA_RiskLedgerField(json,"order_type");
   s.broker_accepted_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"broker_accepted_at_utc"));
   s.effective_expires_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"effective_expires_at_utc"));
   s.cancel_required_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"cancel_required_at_utc"));
   s.cancel_requested_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"cancel_requested_at_utc"));
   s.broker_confirmed_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"broker_confirmed_at_utc"));
   s.cancel_correlation_id=EEA_RiskLedgerField(json,"cancel_correlation_id");
   s.last_closed_bar_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_closed_bar_sequence"));
   s.last_bar_closed_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"last_bar_closed_at_utc"));
   s.last_bar_fingerprint=EEA_RiskLedgerField(json,"last_bar_fingerprint");
   s.last_setup_snapshot_id=EEA_RiskLedgerField(json,"last_setup_snapshot_id");
   s.max_wait_closed_bars=(int)StringToInteger(EEA_RiskLedgerField(json,"max_wait_closed_bars"));
   s.bars_waited=(int)StringToInteger(EEA_RiskLedgerField(json,"bars_waited"));
   s.last_event_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_event_sequence"));
   s.last_event_at_utc=(datetime)StringToInteger(EEA_RiskLedgerField(json,"last_event_at_utc"));
   s.last_event_id=EEA_RiskLedgerField(json,"last_event_id");
   s.last_event_fingerprint=EEA_RiskLedgerField(json,"last_event_fingerprint");
   s.requested_volume=StringToDouble(EEA_RiskLedgerField(json,"requested_volume"));
   s.filled_volume=StringToDouble(EEA_RiskLedgerField(json,"filled_volume"));
   s.cancelled_volume=StringToDouble(EEA_RiskLedgerField(json,"cancelled_volume"));
   s.remaining_volume=StringToDouble(EEA_RiskLedgerField(json,"remaining_volume"));
   s.volume_step=StringToDouble(EEA_RiskLedgerField(json,"volume_step"));
   s.reserved_risk_per_lot_money=StringToDouble(EEA_RiskLedgerField(json,"reserved_risk_per_lot_money"));
   s.max_committed_risk_money=StringToDouble(EEA_RiskLedgerField(json,"max_committed_risk_money"));
   s.filled_initial_risk_money=StringToDouble(EEA_RiskLedgerField(json,"filled_initial_risk_money"));
   s.remaining_risk_reservation_money=StringToDouble(EEA_RiskLedgerField(json,"remaining_risk_reservation_money"));
   s.total_committed_risk_money=StringToDouble(EEA_RiskLedgerField(json,"total_committed_risk_money"));
   s.new_entries_blocked=(s.status!="WORKING" && s.status!="PARTIAL");
   EEA_ExecutionIntent i=t.intent;
   i.schema_version=EEA_RiskLedgerField(json,"i_schema_version");
   i.intent_id=s.intent_id; i.correlation_id=EEA_RiskLedgerField(json,"i_correlation_id");
   i.idempotency_key=EEA_RiskLedgerField(json,"i_idempotency_key");
   i.config_version=s.config_version; i.risk_policy_id=EEA_RiskLedgerField(json,"i_risk_policy_id");
   i.account_fingerprint=s.account_fingerprint; i.broker_server=s.broker_server;
   i.canonical_symbol=s.canonical_symbol; i.broker_symbol=t.broker_symbol;
   i.symbol_fingerprint=EEA_RiskLedgerField(json,"i_symbol_fingerprint");
   i.candidate_id=s.candidate_id; i.setup_id=s.setup_id; i.setup_version=s.setup_version;
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
   i.action=EEA_EXEC_ACTION_SUBMIT_PENDING;
   i.order_type=(int)StringToInteger(EEA_RiskLedgerField(json,"i_order_type"));
   i.volume=StringToDouble(EEA_RiskLedgerField(json,"i_volume"));
   i.price=StringToDouble(EEA_RiskLedgerField(json,"i_price"));
   i.sl=StringToDouble(EEA_RiskLedgerField(json,"i_sl"));
   i.tp=StringToDouble(EEA_RiskLedgerField(json,"i_tp"));
   i.magic=StringToInteger(EEA_RiskLedgerField(json,"i_magic"));
   i.deviation=(int)StringToInteger(EEA_RiskLedgerField(json,"i_deviation"));
   i.filling_mode=(int)StringToInteger(EEA_RiskLedgerField(json,"i_filling_mode"));
   i.expiration=(datetime)StringToInteger(EEA_RiskLedgerField(json,"i_expiration"));
   i.ticket=StringToInteger(s.order_ticket);
   t.state=s;
   t.intent=i;
   return s.order_ticket!="" && s.intent_id!="" && s.requested_volume>0.0 && s.volume_step>0.0;
  }

// Restores every non-terminal tracked order of this account. A file that cannot be
// parsed blocks new entries: an order the EA cannot account for is never ignored.
bool EEA_PendingRuntimeLoad(EEA_PendingRuntime &rt,const string root,const string account_fingerprint)
  {
   EEA_PendingRuntimeDefaults(rt);
   rt.loaded=true;
   string name;
   long handle=FileFindFirst(root+"/current/pending_*.json",name);
   if(handle==INVALID_HANDLE) return true;
   bool ok=true;
   do
     {
      string json;
      EEA_PendingTracked t;
      if(!EEA_PendingReadText(root+"/current/"+name,json) || !EEA_PendingParse(json,t))
        { ok=false; continue; }
      if(t.state.account_fingerprint!=account_fingerprint || !t.active) continue;
      if(rt.count>=EEA_PENDING_MAX_TRACKED) { ok=false; continue; }
      rt.items[rt.count]=t;
      rt.count++;
     }
   while(FileFindNext(handle,name));
   FileFindClose(handle);
   if(!ok) { rt.entries_blocked=true; rt.reason="PENDING_CHECKPOINT_UNREADABLE"; }
   return ok;
  }

// ---------------------------------------------------------------------------
// Broker evidence
// ---------------------------------------------------------------------------
bool EEA_PendingApplyEvent(EEA_PendingTracked &t,const string kind,const double fill_volume,
                           const double filled_risk,const string correlation_id)
  {
   EEA_PendingBrokerEvent e;
   e.event_sequence=t.state.last_event_sequence+1;
   e.event_id=t.state.order_ticket+"-"+IntegerToString(e.event_sequence);
   e.intent_id=t.state.intent_id; e.config_version=t.state.config_version;
   e.instrument_version=t.state.instrument_version; e.broker_server=t.state.broker_server;
   e.account_fingerprint=t.state.account_fingerprint; e.order_ticket=t.state.order_ticket;
   datetime now=TimeGMT();
   e.occurred_at_utc=(now>t.state.last_event_at_utc ? now : t.state.last_event_at_utc);
   e.data_quality="OK"; e.event_kind=kind; e.correlation_id=correlation_id;
   e.fill_volume=fill_volume; e.filled_initial_risk_money=filled_risk;
   e.confirmed_remaining_volume=t.state.remaining_volume;
   e.content_fingerprint=EEA_RuntimeFingerprint(e.event_id+"|"+kind,DoubleToString(fill_volume,8)+"|"+
                                                DoubleToString(filled_risk,8)+"|"+correlation_id);
   return EEA_PendingApplyBrokerEvent(t.state,e);
  }

double EEA_PendingRoundStep(const double volume,const double step)
  {
   if(step<=0.0) return volume;
   return MathRound(volume/step)*step;
  }

// Reads the order from the active book, or from history once it has left the book,
// and turns any change into lifecycle events.
void EEA_PendingReconcileBroker(EEA_PendingTracked &t)
  {
   ulong ticket=(ulong)StringToInteger(t.state.order_ticket);
   double remaining_now=-1.0;
   string terminal="";
   if(OrderSelect(ticket))
      remaining_now=OrderGetDouble(ORDER_VOLUME_CURRENT);
   else
     {
      long offset=EEA_PendingServerOffset();
      HistorySelect((datetime)((long)t.state.broker_accepted_at_utc+offset-2*86400),TimeCurrent()+60);
      if(!HistoryOrderSelect(ticket))
        { EEA_PendingMarkUnknown(t.state,"PENDING_ORDER_NOT_FOUND_AT_BROKER"); return; }
      long order_state=HistoryOrderGetInteger(ticket,ORDER_STATE);
      remaining_now=HistoryOrderGetDouble(ticket,ORDER_VOLUME_CURRENT);
      if(order_state==ORDER_STATE_FILLED) { terminal="FILLED"; remaining_now=0.0; }
      else if(order_state==ORDER_STATE_CANCELED) terminal="CANCELED";
      else if(order_state==ORDER_STATE_EXPIRED) terminal="EXPIRED";
      else if(order_state==ORDER_STATE_PARTIAL) terminal="";
      else { EEA_PendingMarkUnknown(t.state,"PENDING_ORDER_STATE_UNEXPECTED"); return; }
     }
   if(!MathIsValidNumber(remaining_now) || remaining_now<0.0)
     { EEA_PendingMarkUnknown(t.state,"PENDING_ORDER_VOLUME_UNREADABLE"); return; }
   double filled_total=EEA_PendingRoundStep(t.state.requested_volume-remaining_now,t.state.volume_step);
   double new_fill=EEA_PendingRoundStep(filled_total-t.state.filled_volume,t.state.volume_step);
   if(new_fill>0.0000001)
      EEA_PendingApplyEvent(t,"FILL",new_fill,new_fill*t.state.reserved_risk_per_lot_money,"");
   if(t.state.status=="PENDING_RACE_UNKNOWN") return;
   if(terminal=="CANCELED" && t.state.remaining_volume>0.0)
      EEA_PendingApplyEvent(t,"CANCEL_CONFIRMED",0.0,0.0,t.state.cancel_correlation_id);
   else if(terminal=="EXPIRED" && t.state.remaining_volume>0.0)
      EEA_PendingApplyEvent(t,"EXPIRE_CONFIRMED",0.0,0.0,"");
  }

// Feeds each newly closed setup bar to the lifecycle: bar limit, setup validity,
// entry permission, quote premise and instrument spec.
void EEA_PendingObserveBars(EEA_PendingTracked &t,const EEA_StrategyCandidateRuntime &strategy,
                            const EEA_ObserverRuntimeContext &observer)
  {
   if(t.state.status!="WORKING" && t.state.status!="PARTIAL" && t.state.status!="CANCEL_REQUIRED") return;
   ENUM_TIMEFRAMES tf=EEA_PendingTimeframe(t.timeframe);
   long tf_seconds=PeriodSeconds(tf);
   long offset=EEA_PendingServerOffset();
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(t.broker_symbol,tf,1,64,rates);
   if(copied<=0) return;
   bool setup_valid=false;
   for(int e=0;e<strategy.symbol_count;e++)
      if(strategy.engines[e].canonical_symbol==t.state.canonical_symbol && strategy.engines[e].timeframe==t.timeframe)
        {
         setup_valid=strategy.engines[e].candidate.candidate_id==t.state.candidate_id &&
                     !EEA_S02IsTerminal(strategy.engines[e].state) && strategy.engines[e].state!=EEA_S02_IDLE;
         break;
        }
   bool spec_unchanged=false;
   for(int k=0;k<observer.symbol_count;k++)
      if(observer.broker_symbols[k]==t.broker_symbol)
        { spec_unchanged=observer.symbol_specs[k].metadata_fingerprint==t.symbol_fingerprint; break; }
   MqlTick tick; ZeroMemory(tick);
   double point=SymbolInfoDouble(t.broker_symbol,SYMBOL_POINT);
   bool quote_ok=SymbolInfoTick(t.broker_symbol,tick) && point>0.0 &&
                 (tick.ask-tick.bid)/point<=t.max_spread_points;
   for(int b=0;b<copied;b++)
     {
      long bar_time=(long)rates[b].time;
      long closed_utc=bar_time-offset+tf_seconds;
      if(bar_time<=t.last_bar_time || closed_utc<=(long)t.state.broker_accepted_at_utc) continue;
      EEA_PendingObservation o;
      o.intent_id=t.state.intent_id; o.config_version=t.state.config_version;
      o.setup_snapshot_id=t.state.candidate_id+"@"+IntegerToString(bar_time);
      o.bar_fingerprint=IntegerToString(bar_time)+"|"+DoubleToString(rates[b].open,8)+"|"+DoubleToString(rates[b].high,8)+"|"+
                        DoubleToString(rates[b].low,8)+"|"+DoubleToString(rates[b].close,8);
      o.closed_bar_sequence=t.state.last_closed_bar_sequence+1;
      o.closed_at_utc=(datetime)closed_utc;
      o.bar_closed_confirmed=true;
      o.setup_valid=setup_valid; o.session_open=true;
      o.risk_entry_allowed=(observer.status.runtime_state=="OBSERVING");
      o.news_entry_allowed=true;                  // O-16: no News Center, accepted
      o.quote_premise_valid=quote_ok;
      o.config_spec_unchanged=spec_unchanged;
      o.data_quality="OK";
      if(!EEA_PendingObserve(t.state,o)) break;
      t.last_bar_time=bar_time;
      t.bar_sequence=o.closed_bar_sequence;
      if(t.state.status=="CANCEL_REQUIRED") break;
     }
  }

// Sends the cancellation for an order whose lifecycle requires it. The request alone
// is not a cancellation: the remainder stays reserved until the broker confirms.
void EEA_PendingRequestCancel(EEA_PendingTracked &t,CAuditLog &audit,const string root,
                              const EEA_ObserverRuntimeContext &observer,const bool execution_enabled)
  {
   if(t.state.status!="CANCEL_REQUIRED") return;
   int row=-1;
   for(int k=0;k<observer.symbol_count;k++) if(observer.broker_symbols[k]==t.broker_symbol) { row=k; break; }
   if(row<0) { t.state.reason_code="PENDING_CANCEL_SYMBOL_UNAVAILABLE"; return; }
   EEA_LiveAuthorizationContext context; EEA_LiveAuthorizationDecision authorization; string reason;
   EEA_LiveAuthorizationStoreLoad(t.authorization_path,t.state.config_version,t.state.account_fingerprint,
                                  t.state.broker_server,t.broker_symbol,context,authorization,reason);
   EEA_ExecutionIntent cancel=t.intent;
   t.cancel_attempts++;
   cancel.action=EEA_EXEC_ACTION_CANCEL_PENDING;
   cancel.ticket=StringToInteger(t.state.order_ticket);
   cancel.idempotency_key=t.state.intent_id+"-cancel-"+IntegerToString(t.cancel_attempts);
   cancel.intent_created_at_utc=TimeGMT();
   EEA_ExecutionResult result;
   if(EEA_ExecutionCancelPending(audit,root,cancel,observer.account,observer.reconciliation,
                                 observer.symbol_specs[row],observer.status,execution_enabled,authorization,result))
      EEA_PendingApplyEvent(t,"CANCEL_REQUESTED",0.0,0.0,cancel.idempotency_key);
   else
      t.state.reason_code="PENDING_CANCEL_SEND_FAILED_"+result.reason_code;
  }

// One timer pass over every tracked order. Returns false when any order needs review.
bool EEA_PendingRuntimeUpdate(EEA_PendingRuntime &rt,CAuditLog &audit,const string root,
                              const EEA_StrategyCandidateRuntime &strategy,
                              const EEA_ObserverRuntimeContext &observer,const bool execution_enabled)
  {
   rt.entries_blocked=false;
   rt.reason="PENDING_RUNTIME_CLEAR";
   for(int i=0;i<rt.count;i++)
     {
      if(!rt.items[i].active) continue;
      EEA_PendingTracked t=rt.items[i];
      string before=t.state.status+"|"+IntegerToString(t.state.last_event_sequence)+"|"+
                    IntegerToString(t.state.bars_waited)+"|"+IntegerToString(t.cancel_attempts);
      EEA_PendingReconcileBroker(t);
      EEA_PendingObserveBars(t,strategy,observer);
      EEA_PendingCheckDeadline(t.state,TimeGMT());
      EEA_PendingRequestCancel(t,audit,root,observer,execution_enabled);
      string status=t.state.status;
      if(status=="FILLED" || status=="CANCELLED" || status=="EXPIRED") t.active=false;
      if(status=="PENDING_RACE_UNKNOWN" || status=="BREACH_REVIEW" || status=="CANCEL_REQUIRED" ||
         status=="CANCEL_REQUESTED")
        { rt.entries_blocked=true; rt.reason="PENDING_"+status+"_"+t.state.order_ticket; }
      string after=t.state.status+"|"+IntegerToString(t.state.last_event_sequence)+"|"+
                   IntegerToString(t.state.bars_waited)+"|"+IntegerToString(t.cancel_attempts);
      if(after!=before || !t.active)
        {
         if(!EEA_PendingWrite(root,t)) { rt.entries_blocked=true; rt.reason="PENDING_CHECKPOINT_WRITE_FAILED"; }
         if(audit.IsOpen())
           {
            EEAEvent e;
            EEAEvent_Init(e,"PENDING_ORDER_"+status,TimeGMT(),t.state.canonical_symbol,t.state.order_ticket,
                          "",status,"OK");
            e.config_version=t.state.config_version;
            EEAEvent_AddReason(e,t.state.reason_code);
            e.details_json="{\"candidate_id\":\""+EEA_JsonEscape(t.state.candidate_id)+"\",\"remaining_volume\":"+
               DoubleToString(t.state.remaining_volume,8)+",\"filled_volume\":"+DoubleToString(t.state.filled_volume,8)+
               ",\"reserved_risk\":"+DoubleToString(t.state.remaining_risk_reservation_money,2)+
               ",\"cancel_reason\":\""+EEA_JsonEscape(t.state.cancel_reason)+"\"}";
            audit.Append(e,"EA_PENDING_RUNTIME");
           }
        }
      rt.items[i]=t;
     }
   int kept=0;
   for(int i=0;i<rt.count;i++)
      if(rt.items[i].active) { if(kept!=i) rt.items[kept]=rt.items[i]; kept++; }
   rt.count=kept;
   if(!rt.loaded) { rt.entries_blocked=true; rt.reason="PENDING_RUNTIME_NOT_LOADED"; }
   return !rt.entries_blocked;
  }

// Registers an order the broker acknowledged. Fails closed (blocks entries) when the
// lifecycle cannot be seeded, so an untracked order never exists silently.
bool EEA_PendingRuntimeRegister(EEA_PendingRuntime &rt,const string root,const EEA_ExecutionIntent &intent,
                                const long ticket,const string timeframe,const string trade_style,
                                const string authorization_path,const double max_spread_points,
                                const datetime candidate_triggered_at_utc,const int max_wait_closed_bars,
                                const double volume_step,const string account_currency,string &reason)
  {
   if(rt.count>=EEA_PENDING_MAX_TRACKED || ticket<=0)
     { rt.entries_blocked=true; reason="PENDING_TRACKER_FULL_OR_TICKET_INVALID"; return false; }
   datetime now=TimeGMT();
   EEA_PendingSeed seed;
   seed.intent_id=intent.intent_id; seed.candidate_id=intent.candidate_id; seed.setup_id=intent.setup_id;
   seed.setup_version=intent.setup_version; seed.config_version=intent.config_version;
   seed.instrument_version=intent.symbol_fingerprint; seed.canonical_symbol=intent.canonical_symbol;
   seed.account_currency=account_currency; seed.broker_server=intent.broker_server;
   seed.account_fingerprint=intent.account_fingerprint; seed.order_ticket=IntegerToString(ticket);
   seed.trade_style=trade_style; seed.order_type=EEA_PendingOrderTypeName(intent.order_type);
   seed.candidate_triggered_at_utc=(candidate_triggered_at_utc>0 && candidate_triggered_at_utc<now) ?
                                   candidate_triggered_at_utc : now;
   seed.submitted_at_utc=now; seed.broker_accepted_at_utc=now;
   seed.setup_valid_until_utc=intent.expiration; seed.session_end_at_utc=intent.expiration;
   seed.broker_expiration_at_utc=intent.expiration;
   seed.placed_after_closed_bar_sequence=0; seed.max_wait_closed_bars=max_wait_closed_bars;
   seed.placement_validated=true; seed.broker_expiration_attested=true;
   seed.requested_volume=intent.volume; seed.volume_step=volume_step;
   seed.reserved_risk_per_lot_money=intent.volume>0.0 ? intent.projected_loss/intent.volume : 0.0;
   seed.max_committed_risk_money=intent.risk_budget;
   EEA_PendingTracked t;
   t.active=true; t.timeframe=timeframe; t.broker_symbol=intent.broker_symbol;
   t.authorization_path=authorization_path; t.symbol_fingerprint=intent.symbol_fingerprint;
   t.max_spread_points=max_spread_points; t.cancel_attempts=0; t.bar_sequence=0;
   t.last_bar_time=(long)TimeTradeServer()-PeriodSeconds(EEA_PendingTimeframe(timeframe));
   t.intent=intent; t.intent.ticket=ticket;
   if(!EEA_PendingInit(seed,now,t.state))
     { rt.entries_blocked=true; reason=t.state.reason_code; return false; }
   rt.items[rt.count]=t;
   rt.count++;
   if(!EEA_PendingWrite(root,t))
     { rt.entries_blocked=true; reason="PENDING_CHECKPOINT_WRITE_FAILED"; return false; }
   reason="PENDING_ORDER_TRACKED";
   return true;
  }

#endif
