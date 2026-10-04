#ifndef ENTERPRISE_EA_CONTROLLED_LIVE_RUNTIME_MQH
#define ENTERPRISE_EA_CONTROLLED_LIVE_RUNTIME_MQH

#include "../Runtime/StrategyCandidateRuntime.mqh"
#include "../Runtime/TradeQuoteAdapter.mqh"
#include "../Runtime/ExecutionAdapter.mqh"
#include "../Runtime/ExecutionReconciliation.mqh"
#include "../Runtime/LiveAuthorizationGate.mqh"
#include "../Storage/LiveAuthorizationStore.mqh"
#include "../Storage/RiskDecisionStore.mqh"
#include "../Storage/ExecutionRecoveryStore.mqh"
#include "../Storage/PolicySettingsStore.mqh"
#include "RiskDecisionRelease.mqh"
#include "../Runtime/ExecutionIntentBuilder.mqh"
#include "../Risk/StructuralLevels.mqh"
#include "../Risk/TradeEconomics.mqh"
#include "../Risk/FtmoHeadroom.mqh"
#include "../Risk/PortfolioBudget.mqh"
#include "../Risk/VolumeSizing.mqh"
#include "../Risk/RiskLimitsProfile.mqh"
#include "../Storage/RiskLedgerStore.mqh"
#include "../Runtime/PendingOrderRuntime.mqh"
#include "../Runtime/LiveSessionAuthorization.mqh"
#include "../Runtime/TradeManagerRuntime.mqh"
#include "../News/NewsCalendar.mqh"
#include "../Market/SentimentRuntime.mqh"

struct EEA_ControlledLiveConfig
  {
   bool enabled;
   bool armed;
   string authorization_path;
   string setup_version;
   double initial_capital;
   double safety_buffer_money;
   double balance_at_daily_reset;
   datetime daily_reset_at_utc;
   double prior_overall_high_water_balance;
   double base_risk_fraction;
   double per_trade_cap_money;
   double portfolio_remaining_money;
   double minimum_net_rr;
   double stop_buffer_ticks;
   double target_r_multiple;
   double max_spread_points;
   int quote_freshness_seconds;
   int release_ttl_seconds;
   long magic;
   int deviation;
   int filling_mode;
  };

struct EEA_ControlledLiveRuntimeState
  {
   long last_attempt_utc;
   string last_candidate_id[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string last_reason;
   string news_blocked_candidate[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string sentiment_noted_candidate[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string shadow_noted_candidate[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   bool recovery_blocked;
   EEA_ExecutionResult recovery_result;
  };

void EEA_ControlledLiveConfigDefaults(EEA_ControlledLiveConfig &c)
  {
   c.enabled=false; c.armed=false; c.authorization_path="";
   c.setup_version=""; c.initial_capital=0.0; c.safety_buffer_money=0.0;
   c.balance_at_daily_reset=0.0; c.daily_reset_at_utc=0; c.prior_overall_high_water_balance=0.0;
   c.base_risk_fraction=0.0; c.per_trade_cap_money=0.0; c.portfolio_remaining_money=0.0;
   c.minimum_net_rr=0.0; c.stop_buffer_ticks=0.0; c.target_r_multiple=0.0;
   c.max_spread_points=0.0; c.quote_freshness_seconds=30; c.release_ttl_seconds=20;
   c.magic=888888; c.deviation=20; c.filling_mode=0;
  }

void EEA_ControlledLiveRuntimeStateDefaults(EEA_ControlledLiveRuntimeState &s)
  {
   s.last_attempt_utc=0; s.last_reason="CONTROLLED_LIVE_IDLE";
   s.recovery_blocked=false;
   EEA_ExecutionResultDefaults(s.recovery_result);
   for(int i=0;i<EEA_STRATEGY_RUNTIME_MAX_ENGINES;i++) { s.last_candidate_id[i]=""; s.news_blocked_candidate[i]=""; s.sentiment_noted_candidate[i]=""; s.shadow_noted_candidate[i]=""; }
  }

bool EEA_ControlledLiveLoadRecovery(EEA_ControlledLiveRuntimeState &state,const string root,string &reason)
  {
   bool found=false;
   if(!EEA_ExecutionRecoveryLoad(root,state.recovery_result,found))
     { state.recovery_blocked=true; reason="EXECUTION_RECOVERY_CHECKPOINT_INVALID"; return false; }
   state.recovery_blocked=found && EEA_ExecutionRecoveryNeedsReconciliation(state.recovery_result);
   reason=state.recovery_blocked ? "EXECUTION_UNKNOWN_RECOVERY_REQUIRED" : "EXECUTION_RECOVERY_CLEAR";
   return true;
  }

bool EEA_ControlledLiveReconcileRecovery(EEA_ControlledLiveRuntimeState &state,
                                         const string root,
                                         const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                         CAuditLog &audit)
  {
   if(!state.recovery_blocked) return true;
   if(!EEA_ExecutionReconcileResult(state.recovery_result,reconciliation,
                                    state.recovery_result.request_ticket,"SUBMIT_MARKET",
                                    0.0,0.0,state.recovery_result.request_ticket_kind))
      return false;
   if(!EEA_ExecutionStoreWriteResult(root,state.recovery_result))
     { state.last_reason="EXECUTION_RECOVERY_PERSISTENCE_FAILED"; return false; }
   EEAEvent event;
   EEAEvent_Init(event,"EXECUTION_RECOVERY_CONFIRMED",TimeGMT(),"","","","","OK");
   event.details_json="{\"intent_id\":\""+EEA_JsonEscape(state.recovery_result.intent_id)+"\"}";
   if(!audit.Append(event,"EA_EXECUTION"))
     { state.last_reason="EXECUTION_RECOVERY_AUDIT_FAILED"; return false; }
   state.recovery_blocked=false;
   state.last_reason="EXECUTION_RECOVERY_CONFIRMED";
   return true;
  }

// Operator resolution of an entry whose outcome stayed unknown (no broker evidence). The
// operator attests after checking the MT5 terminal (Trade and History tabs). The result
// is persisted as OPERATOR_RESOLVED with the operator id and audited before entries resume.
bool EEA_ControlledLiveResolveRecoveryByOperator(EEA_ControlledLiveRuntimeState &state,const string root,
                                                 const string operator_id,CAuditLog &audit,string &reason)
  {
   if(!state.recovery_blocked) { reason="EXECUTION_RECOVERY_NOT_BLOCKED"; return false; }
   EEA_ExecutionResult resolved=state.recovery_result;
   resolved.confirmation_state="OPERATOR_RESOLVED";
   resolved.reason_code="OPERATOR_VERIFIED_IN_TERMINAL";
   resolved.observed_at_utc=TimeGMT();
   EEAEvent event;
   EEAEvent_Init(event,"EXECUTION_RECOVERY_OPERATOR_RESOLVED",TimeGMT(),"","","","","OK");
   event.details_json="{\"intent_id\":\""+EEA_JsonEscape(resolved.intent_id)+
      "\",\"idempotency_key\":\""+EEA_JsonEscape(resolved.idempotency_key)+
      "\",\"request_ticket\":"+IntegerToString(resolved.request_ticket)+
      ",\"request_ticket_kind\":\""+EEA_JsonEscape(resolved.request_ticket_kind)+
      "\",\"operator_id\":\""+EEA_JsonEscape(operator_id)+"\"}";
   if(!audit.Append(event,"EA_OPERATOR")) { reason="EXECUTION_RECOVERY_AUDIT_FAILED"; return false; }
   if(!EEA_ExecutionStoreWriteResult(root,resolved)) { reason="EXECUTION_RECOVERY_PERSISTENCE_FAILED"; return false; }
   state.recovery_result=resolved;
   state.recovery_blocked=false;
   state.last_reason="EXECUTION_RECOVERY_OPERATOR_RESOLVED";
   reason=state.last_reason;
   return true;
  }

bool EEA_ControlledLiveAuditAuthorization(CAuditLog &audit,
                                          const EEA_LiveAuthorizationDecision &authorization,
                                          const EEA_RiskDecision &decision,
                                          const EEA_ExecutionIntent &intent,
                                          const string broker_symbol,
                                          const string entry_reason)
  {
   EEAEvent event;
   EEAEvent_Init(event,"LIVE_AUTHORIZATION_BOUND",TimeGMT(),decision.symbol,decision.candidate_id,
                 "","AUTHORIZED_CONTROLLED_LIVE","OK");
   event.details_json="{\"authorization_id\":\""+EEA_JsonEscape(authorization.authorization_id)+
      "\",\"intent_id\":\""+EEA_JsonEscape(authorization.intent_id)+
      "\",\"candidate_id\":\""+EEA_JsonEscape(decision.candidate_id)+
      "\",\"intent_risk_decision_id\":\""+EEA_JsonEscape(intent.risk_decision_id)+
      "\",\"broker_symbol\":\""+EEA_JsonEscape(broker_symbol)+
      "\",\"entry_selection\":\""+EEA_JsonEscape(entry_reason)+
      "\",\"risk_decision_id\":\""+EEA_JsonEscape(decision.decision_id)+
      "\",\"expires_at_utc\":"+IntegerToString((long)authorization.authorization_valid_until_utc)+"}";
   return audit.Append(event,"EA_EXECUTION");
  }

bool EEA_ControlledLiveResolvePolicy(const string root,const string config_version,
                                     const EEA_RuntimeAccountSnapshot &account,
                                     EEA_PolicySettings &policy,string &reason)
  {
   if(!EEA_PolicySettingsStoreLoad(root+"/current/policy_settings.json",config_version,
                                   account.account_fingerprint,account.broker_server,policy))
     { reason="LIVE_POLICY_SETTINGS_UNAVAILABLE"; return false; }
   if(policy.committed_policy=="UNSELECTED" || !policy.policy_confirmed)
     { reason="LIVE_POLICY_NOT_CONFIRMED"; return false; }
   reason="LIVE_POLICY_CONFIRMED";
   return true;
  }

void EEA_ControlledLiveFillEvidence(EEA_DryRunEvidence &ev,const int stage,
                                    const string quality,const string config_version,
                                    const string source_version,const string currency,
                                    const string canonical,const string broker,
                                    const string server,const string snapshot,
                                    const datetime captured,const int max_age)
  {
   ev.stage=stage; ev.quality=quality; ev.config_version=config_version;
   ev.source_version=source_version; ev.account_currency=currency;
   ev.canonical_symbol=canonical; ev.broker_symbol=broker; ev.broker_server=server;
   ev.source_snapshot_id=snapshot; ev.captured_at_utc=captured; ev.max_age_seconds=max_age;
  }

bool EEA_ControlledLiveExistingStress(const EEA_ObserverRuntimeContext &observer,
                                      double &stress_loss,double &floating_pnl,string &reason)
  {
   stress_loss=0.0; floating_pnl=0.0; reason="";
   for(int i=0;i<observer.reconciliation.position_count;i++)
     {
      EEA_RuntimePositionRow position=observer.reconciliation.positions[i];
      int spec_index=-1;
      for(int j=0;j<observer.symbol_count;j++)
         if(observer.symbol_specs[j].broker_symbol==position.symbol) { spec_index=j; break; }
      if(spec_index<0 || position.sl<=0.0)
        { reason="LIVE_EXISTING_POSITION_PROTECTION_UNAVAILABLE"; return false; }
      int order_type=(int)StringToInteger(position.type);
      if(order_type<ORDER_TYPE_BUY || order_type>ORDER_TYPE_SELL)
        { reason="LIVE_EXISTING_POSITION_TYPE_INVALID"; return false; }
      double loss=0.0;
      if(!OrderCalcProfit((ENUM_ORDER_TYPE)order_type,position.symbol,position.volume,
                          position.current_price,position.sl,loss) ||
         !EEA_IsFiniteDouble(loss) || loss>=0.0)
        { reason="LIVE_EXISTING_POSITION_STRESS_INVALID"; return false; }
      stress_loss-=loss;
      floating_pnl+=position.profit+position.swap+position.commission;
     }
   for(int i=0;i<observer.reconciliation.order_count;i++)
     {
      EEA_RuntimeOrderRow order=observer.reconciliation.orders[i];
      int spec_index=-1;
      for(int j=0;j<observer.symbol_count;j++)
         if(observer.symbol_specs[j].broker_symbol==order.symbol) { spec_index=j; break; }
      if(spec_index<0 || order.sl<=0.0)
        { reason="LIVE_EXISTING_ORDER_PROTECTION_UNAVAILABLE"; return false; }
      int order_type=(int)StringToInteger(order.type);
      if(order_type<ORDER_TYPE_BUY_LIMIT || order_type>ORDER_TYPE_SELL_STOP_LIMIT)
        { reason="LIVE_EXISTING_ORDER_TYPE_INVALID"; return false; }
      double loss=0.0;
      if(!OrderCalcProfit((ENUM_ORDER_TYPE)order_type,order.symbol,order.volume,
                          order.price,order.sl,loss) ||
         !EEA_IsFiniteDouble(loss) || loss>=0.0)
        { reason="LIVE_EXISTING_ORDER_STRESS_INVALID"; return false; }
      stress_loss-=loss;
     }
   if(!EEA_IsFiniteDouble(stress_loss) || stress_loss<0.0 || !EEA_IsFiniteDouble(floating_pnl))
     { reason="LIVE_EXISTING_EXPOSURE_CALCULATION_INVALID"; return false; }
   return true;
  }

// Everything the risk path needs for one candidate. The prototype builds it from the
// EA inputs; S02 v1 derives it from structure, broker data, the risk ledger and O-04.
#define EEA_S02_SWING_EXPECTED_NIGHTS 2.0
#define EEA_S02_SPREAD_MEDIAN_BARS 288

struct EEA_ControlledLiveTradePlan
  {
   string setup_version;
   double initial_capital;
   double safety_buffer_money;
   double balance_at_daily_reset;
   datetime daily_reset_at_utc;
   double prior_overall_high_water_balance;
   double base_risk_fraction;
   double per_trade_cap_money;
   double portfolio_cap_money;
   bool   portfolio_cap_includes_existing;  // cap is the total open risk; existing stress is subtracted
   double invalidation_price;
   double target_price;                     // > 0: structural target
   double target_r_multiple;                // prototype only
   double stop_buffer_price;
   double max_spread_points;
   double max_spread_stop_fraction;
   double minimum_net_rr;
   double cost_per_lot_money;               // round-trip commission plus expected swap
   bool   cost_estimated;
   double currency_cap_money;
   int    max_correlated_trades;
   double min_margin_level_percent;
   double htf_risk_modifier;
   double entry_price;          // > 0: pending entry price instead of the current quote
   bool   allow_armed;          // LIMIT_AT_ZONE is placed while the setup is ARMED
   int    pending_order_type;   // ORDER_TYPE_*_LIMIT / *_STOP, or -1 for market
   datetime pending_expiration_utc;
   int    pending_max_wait_bars;
  };

void EEA_ControlledLivePlanDefaults(EEA_ControlledLiveTradePlan &p)
  {
   p.setup_version=""; p.initial_capital=0.0; p.safety_buffer_money=0.0; p.balance_at_daily_reset=0.0;
   p.daily_reset_at_utc=0; p.prior_overall_high_water_balance=0.0; p.base_risk_fraction=0.0;
   p.per_trade_cap_money=0.0; p.portfolio_cap_money=0.0; p.portfolio_cap_includes_existing=false;
   p.invalidation_price=0.0; p.target_price=0.0; p.target_r_multiple=0.0; p.stop_buffer_price=0.0;
   p.max_spread_points=0.0; p.max_spread_stop_fraction=0.0; p.minimum_net_rr=0.0; p.cost_per_lot_money=0.0;
   p.cost_estimated=false; p.currency_cap_money=0.0; p.max_correlated_trades=0; p.min_margin_level_percent=0.0;
   p.htf_risk_modifier=1.0; p.entry_price=0.0; p.allow_armed=false; p.pending_order_type=-1;
   p.pending_expiration_utc=0; p.pending_max_wait_bars=0;
  }

// S02 v1 entry modes (design section 8, O-17): MARKET on the trigger bar, a LIMIT at the
// zone edge once the break is accepted, or a STOP one tick beyond the trigger bar.
#define EEA_S02_ENTRY_MARKET 0
#define EEA_S02_ENTRY_LIMIT_AT_ZONE 1
#define EEA_S02_ENTRY_STOP_ABOVE_TRIGGER 2

bool EEA_ControlledLiveTriggerBar(const string broker_symbol,const string timeframe,const datetime bar_time,
                                  MqlRates &bar)
  {
   ENUM_TIMEFRAMES tf=(timeframe=="H1" ? PERIOD_H1 : PERIOD_M5);
   int shift=iBarShift(broker_symbol,tf,bar_time,true);
   if(shift<0) return false;
   MqlRates rates[];
   if(CopyRates(broker_symbol,tf,shift,1,rates)!=1 || rates[0].time!=bar_time) return false;
   bar=rates[0];
   return true;
  }

// Automatic entry type (design section 8.4). The system picks the order type from the
// setup state instead of an operator input:
//   ARMED, HTF aligned, price at least 0.25 ATR away from the zone edge -> LIMIT at the edge
//   TRIGGERED, price beyond the trigger bar extreme (break confirmed)  -> MARKET
//   TRIGGERED, SCALP, HTF aligned, price within 0.25 ATR of the close  -> MARKET
//   TRIGGERED otherwise (SWING, counter-HTF, or price pulled back)     -> STOP beyond the trigger bar
// Returns -1 when the setup should wait (no order) and names the reason.
#define EEA_S02_AUTO_LIMIT_MIN_DISTANCE_ATR 0.25
#define EEA_S02_AUTO_MARKET_RETRACE_ATR 0.25
#define EEA_S02_AUTO_MAX_CHASE_ATR 0.50

int EEA_S02SelectEntryMode(const EEA_StrategyCandidateRuntime &strategy,const int index,
                           const string broker_symbol,string &reason)
  {
   EEA_S02Engine engine=strategy.engines[index];
   const int direction=engine.direction;
   if(direction!=1 && direction!=-1) { reason="ENTRY_AUTO_NO_DIRECTION"; return -1; }
   const double atr=engine.signal_atr;
   if(atr<=0.0) { reason="ENTRY_AUTO_ATR_UNAVAILABLE"; return -1; }
   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0)
     { reason="ENTRY_AUTO_QUOTE_UNAVAILABLE"; return -1; }
   const double price=(direction==1 ? tick.ask : tick.bid);
   const bool aligned=(strategy.htf_risk_modifier[index]>=1.0);
   const bool scalp=(strategy.profile[index]!="SWING");
   // S04 has no LIMIT entry: its edge is the confirmed rejection, not the zone (design 4).
   if(engine.state==EEA_S02_ARMED && strategy.setup[index]!="S04")
     {
      if(!aligned) { reason="ENTRY_AUTO_WAIT_TRIGGER_COUNTER_HTF"; return -1; }
      if(engine.zone_low<=0.0 || engine.zone_high<=engine.zone_low)
        { reason="ENTRY_AUTO_ZONE_INVALID"; return -1; }
      const double edge=(direction==1 ? engine.zone_high : engine.zone_low);
      if(direction*(price-edge)<EEA_S02_AUTO_LIMIT_MIN_DISTANCE_ATR*atr)
        { reason="ENTRY_AUTO_WAIT_TRIGGER_AT_ZONE"; return -1; }
      reason="ENTRY_AUTO_LIMIT_AT_ZONE";
      return EEA_S02_ENTRY_LIMIT_AT_ZONE;
     }
   if(engine.state!=EEA_S02_TRIGGERED) { reason="ENTRY_AUTO_NOT_READY"; return -1; }
   MqlRates trigger;
   if(!EEA_ControlledLiveTriggerBar(broker_symbol,engine.timeframe,engine.candidate.triggered_at_utc,trigger))
     { reason="ENTRY_AUTO_TRIGGER_BAR_UNAVAILABLE"; return -1; }
   const double extreme=(direction==1 ? trigger.high : trigger.low);
   const double chase=direction*(price-extreme);
   if(chase>EEA_S02_AUTO_MAX_CHASE_ATR*atr) { reason="ENTRY_AUTO_CHASE_TOO_FAR"; return -1; }
   if(chase>=0.0) { reason="ENTRY_AUTO_MARKET_BREAK_CONFIRMED"; return EEA_S02_ENTRY_MARKET; }
   const double retrace=direction*(trigger.close-price);
   if(scalp && aligned && retrace<=EEA_S02_AUTO_MARKET_RETRACE_ATR*atr)
     { reason="ENTRY_AUTO_MARKET_SCALP_ALIGNED"; return EEA_S02_ENTRY_MARKET; }
   reason="ENTRY_AUTO_STOP_CONFIRMATION";
   return EEA_S02_ENTRY_STOP_ABOVE_TRIGGER;
  }

void EEA_ControlledLivePlanFromConfig(const EEA_ControlledLiveConfig &config,const EEA_S02Engine &engine,
                                      const EEA_RuntimeSymbolSpec &symbol,EEA_ControlledLiveTradePlan &p)
  {
   EEA_ControlledLivePlanDefaults(p);
   p.setup_version=config.setup_version; p.initial_capital=config.initial_capital;
   p.safety_buffer_money=config.safety_buffer_money; p.balance_at_daily_reset=config.balance_at_daily_reset;
   p.daily_reset_at_utc=config.daily_reset_at_utc; p.prior_overall_high_water_balance=config.prior_overall_high_water_balance;
   p.base_risk_fraction=config.base_risk_fraction; p.per_trade_cap_money=config.per_trade_cap_money;
   p.portfolio_cap_money=config.portfolio_remaining_money; p.invalidation_price=engine.invalidation_price;
   p.target_r_multiple=config.target_r_multiple; p.stop_buffer_price=config.stop_buffer_ticks*symbol.tick_size;
   p.max_spread_points=config.max_spread_points; p.minimum_net_rr=config.minimum_net_rr;
  }

// Open risk per currency from positions and pending orders (spec 5.5). Every open
// exposure must carry a stop; one without fails closed.
bool EEA_ControlledLiveExposure(const EEA_ObserverRuntimeContext &observer,EEA_CurrencyExposure &exposure,
                                string &reason)
  {
   EEA_CurrencyExposureReset(exposure);
   for(int i=0;i<observer.reconciliation.position_count;i++)
     {
      EEA_RuntimePositionRow p=observer.reconciliation.positions[i];
      int type=(int)StringToInteger(p.type);
      int direction=(type==ORDER_TYPE_BUY ? 1 : -1);
      if(p.sl<=0.0) { reason="LIVE_EXISTING_POSITION_PROTECTION_UNAVAILABLE"; return false; }
      double loss=0.0;
      if(!OrderCalcProfit((ENUM_ORDER_TYPE)type,p.symbol,p.volume,p.current_price,p.sl,loss) || !EEA_IsFiniteDouble(loss))
        { reason="LIVE_EXISTING_POSITION_STRESS_INVALID"; return false; }
      if(!EEA_CurrencyExposureAddPosition(exposure,SymbolInfoString(p.symbol,SYMBOL_CURRENCY_BASE),
                                          SymbolInfoString(p.symbol,SYMBOL_CURRENCY_PROFIT),direction,MathMax(0.0,-loss)))
        { reason="CURRENCY_EXPOSURE_INVALID"; return false; }
     }
   for(int i=0;i<observer.reconciliation.order_count;i++)
     {
      EEA_RuntimeOrderRow o=observer.reconciliation.orders[i];
      int type=(int)StringToInteger(o.type);
      int direction=(type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT) ? 1 : -1;
      if(o.sl<=0.0) { reason="LIVE_EXISTING_ORDER_PROTECTION_UNAVAILABLE"; return false; }
      double loss=0.0;
      if(!OrderCalcProfit(direction>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,o.symbol,o.volume,o.price,o.sl,loss) ||
         !EEA_IsFiniteDouble(loss))
        { reason="LIVE_EXISTING_ORDER_STRESS_INVALID"; return false; }
      if(!EEA_CurrencyExposureAddPosition(exposure,SymbolInfoString(o.symbol,SYMBOL_CURRENCY_BASE),
                                          SymbolInfoString(o.symbol,SYMBOL_CURRENCY_PROFIT),direction,MathMax(0.0,-loss)))
        { reason="CURRENCY_EXPOSURE_INVALID"; return false; }
     }
   reason="CURRENCY_EXPOSURE_READY";
   return true;
  }

// O-04 internal loss limits: realized plus floating loss since the Prague daily reset
// and since the Prague Monday reset. Returns the money still allowed to be lost; a
// new trade's risk is capped by it. Fails closed when the week basis is unknown.
long EEA_PragueWeekResetUtc(const long now_utc)
  {
   long day_reset=EEA_PragueDailyResetUtc(now_utc);
   long local_day=(day_reset+EEA_PragueOffsetSeconds(day_reset+3*3600))/86400;
   long weekday=(local_day+4)%7;                 // 0 = Sunday
   long days_since_monday=(weekday+6)%7;
   if(days_since_monday==0) return day_reset;
   // The +3h keeps the probe inside the target Prague day across a DST change.
   return EEA_PragueDailyResetUtc(day_reset-days_since_monday*86400+3*3600);
  }

bool EEA_ControlledLiveInternalLossRoom(const EEA_ObserverRuntimeContext &observer,const EEA_RiskLedger &ledger,
                                        const EEA_RiskLimits &limits,double &room_money,string &reason)
  {
   room_money=0.0;
   const double equity=observer.account.equity;
   const double daily_loss=ledger.last_reset_balance-equity;
   const double daily_room=limits.internal_daily_fraction*ledger.initial_capital-daily_loss;
   if(daily_room<=0.0) { reason="INTERNAL_DAILY_LOSS_LIMIT_REACHED"; return false; }
   const long week_start=EEA_PragueWeekResetUtc((long)TimeGMT());
   double week_balance=0.0;
   if(!EEA_BalanceAtUtc(observer.reconciliation,observer.account.balance,week_start,week_balance,reason))
     { reason="INTERNAL_WEEKLY_BASIS_UNKNOWN"; return false; }
   const double weekly_room=limits.internal_weekly_fraction*ledger.initial_capital-(week_balance-equity);
   if(weekly_room<=0.0) { reason="INTERNAL_WEEKLY_LOSS_LIMIT_REACHED"; return false; }
   room_money=MathMin(daily_room,weekly_room);
   reason="INTERNAL_LOSS_ROOM_AVAILABLE";
   return true;
  }

// S02 v1 plan (design sections 8, 9, 11): structural SL beyond the retest extreme,
// nearest structural target at least 1R away, relative spread guard, broker-derived
// costs, O-04 limits scaled by the HTF modifier, FTMO facts from the risk ledger.
bool EEA_ControlledLiveResolveV1Plan(const EEA_StrategyCandidateRuntime &strategy,const int index,
                                     const EEA_ObserverRuntimeContext &observer,
                                     const EEA_RuntimeSymbolSpec &symbol,const EEA_PolicySettings &policy,
                                     const EEA_RiskLedger &ledger,const int entry_mode,
                                     EEA_ControlledLiveTradePlan &p,string &reason)
  {
   EEA_ControlledLivePlanDefaults(p);
   EEA_S02Engine engine=strategy.engines[index];
   bool limit_mode=(entry_mode==EEA_S02_ENTRY_LIMIT_AT_ZONE);
   bool stop_mode=(entry_mode==EEA_S02_ENTRY_STOP_ABOVE_TRIGGER);
   int required_state=limit_mode ? EEA_S02_ARMED : EEA_S02_TRIGGERED;
   if(engine.state!=required_state || (engine.direction!=1 && engine.direction!=-1) || symbol.broker_symbol=="")
     { reason="LIVE_CANDIDATE_NOT_TRIGGERED"; return false; }
   EEA_RiskLimits limits;
   if(!EEA_RiskLimitsForPolicy(policy.committed_policy,limits,reason)) return false;
   if(ledger.initial_capital<=0.0) { reason="LIVE_INITIAL_CAPITAL_UNKNOWN"; return false; }
   long reset=EEA_PragueDailyResetUtc((long)TimeGMT());
   if(ledger.last_reset_utc!=reset || ledger.last_reset_balance<=0.0)
     { reason="LIVE_DAILY_RESET_SNAPSHOT_STALE"; return false; }
   bool swing=(strategy.profile[index]=="SWING");
   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(symbol.broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0)
     { reason="LIVE_ENTRY_QUOTE_UNAVAILABLE"; return false; }
   int direction=engine.direction;
   double entry=(direction==1 ? tick.ask : tick.bid);
   double spread_price=tick.ask-tick.bid;
   EEA_S02Config profile_config=strategy.profile_config[index];
   long tf_seconds=PeriodSeconds(engine.timeframe=="H1" ? PERIOD_H1 : PERIOD_M5);
   double invalidation=engine.candidate.retest_extreme>0.0 ? engine.candidate.retest_extreme : engine.retest_extreme;
   if(limit_mode)
     {
      // Buy the retest of the zone edge; the far edge of the zone is the thesis invalidation.
      entry=(direction==1 ? engine.zone_high : engine.zone_low);
      invalidation=(direction==1 ? engine.zone_low : engine.zone_high);
      int bars_left=profile_config.max_bars_to_retest-engine.bars_since_acceptance+profile_config.max_bars_for_reaction;
      if(bars_left<1) { reason="LIVE_PENDING_WINDOW_ELAPSED"; return false; }
      p.pending_order_type=(direction==1 ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT);
      p.pending_max_wait_bars=bars_left;
      p.pending_expiration_utc=(datetime)((long)TimeGMT()+bars_left*tf_seconds);
      p.allow_armed=true;
     }
   if(stop_mode)
     {
      MqlRates trigger;
      if(!EEA_ControlledLiveTriggerBar(symbol.broker_symbol,engine.timeframe,engine.candidate.triggered_at_utc,trigger))
        { reason="LIVE_TRIGGER_BAR_UNAVAILABLE"; return false; }
      entry=(direction==1 ? trigger.high+symbol.tick_size : trigger.low-symbol.tick_size);
      int bars_left=engine.candidate.expires_after_bars-engine.candidate.age_after_trigger_bars;
      if(bars_left<1) { reason="LIVE_PENDING_WINDOW_ELAPSED"; return false; }
      p.pending_order_type=(direction==1 ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP);
      p.pending_max_wait_bars=bars_left;
      p.pending_expiration_utc=(datetime)((long)TimeGMT()+bars_left*tf_seconds);
     }
   if(limit_mode || stop_mode) p.entry_price=entry;
   if(invalidation<=0.0 || (direction==1 && invalidation>=entry) || (direction==-1 && invalidation<=entry))
     { reason="LIVE_STRUCTURE_INVALIDATION_INVALID"; return false; }
   double buffer=MathMax(0.10*engine.signal_atr,1.5*spread_price);
   if(buffer<=0.0) { reason="LIVE_STOP_BUFFER_INVALID"; return false; }
   double stop=(direction==1 ? invalidation-buffer : invalidation+buffer);
   double risk_distance=MathAbs(entry-stop);

   EEA_LevelPoint points[]; EEA_LevelBar bars[];
   int point_count=0, level_count=0; double context_atr=0.0;
   if(!EEA_StrategyRuntimeCollectLevels(symbol.broker_symbol,swing,points,point_count,bars,level_count,context_atr,reason))
      return false;
   double target=0.0;
   // S04 targets the other side of the zone: the target must also clear the far edge.
   double min_target=risk_distance;
   if(strategy.setup[index]=="S04")
     {
      double far_edge=(direction==1 ? engine.zone_high : engine.zone_low);
      min_target=MathMax(risk_distance,direction*(far_edge-entry));
     }
   if(!EEA_S02V1StructuralTarget(points,point_count,direction,entry,min_target,target))
     { reason="NO_STRUCTURAL_TARGET"; return false; }

   double median_spread=EEA_MedianSpreadPoints(symbol.broker_symbol,EEA_S02_SPREAD_MEDIAN_BARS);
   if(median_spread<=0.0) { reason="LIVE_SPREAD_MEDIAN_UNAVAILABLE"; return false; }
   bool learned=false;
   double cost=2.0*EEA_CommissionPerLotPerSide(observer.reconciliation,symbol.broker_symbol,learned);
   if(swing)
     {
      bool known=false;
      double swap=EEA_SwapMoneyPerLotPerNight(symbol,direction,known);
      if(swap<0.0) cost+=-swap*EEA_S02_SWING_EXPECTED_NIGHTS;
      if(!known) learned=false;
     }
   double htf=MathMax(0.0,MathMin(1.0,strategy.htf_risk_modifier[index]));
   double loss_room=0.0;
   if(!EEA_ControlledLiveInternalLossRoom(observer,ledger,limits,loss_room,reason)) return false;

   p.setup_version=engine.config_version;
   p.initial_capital=ledger.initial_capital;
   p.safety_buffer_money=limits.safety_buffer_fraction*ledger.initial_capital;
   p.balance_at_daily_reset=ledger.last_reset_balance;
   p.daily_reset_at_utc=(datetime)ledger.last_reset_utc;
   p.prior_overall_high_water_balance=MathMax(ledger.high_water_balance,ledger.initial_capital);
   p.base_risk_fraction=limits.per_trade_fraction*htf;
   p.per_trade_cap_money=MathMin(limits.per_trade_fraction*ledger.initial_capital,loss_room);
   p.portfolio_cap_money=limits.total_open_fraction*ledger.initial_capital;
   p.portfolio_cap_includes_existing=true;
   p.invalidation_price=invalidation;
   p.target_price=target;
   p.stop_buffer_price=buffer;
   p.max_spread_points=2.0*median_spread;
   p.max_spread_stop_fraction=0.25;
   p.minimum_net_rr=swing ? 2.0 : 1.5;
   p.cost_per_lot_money=cost;
   p.cost_estimated=!learned;
   p.currency_cap_money=limits.currency_exposure_fraction*ledger.initial_capital;
   p.max_correlated_trades=limits.max_correlated_trades;
   p.min_margin_level_percent=limits.min_margin_level_percent;
   p.htf_risk_modifier=htf;
   if(p.base_risk_fraction<=0.0) { reason="LIVE_RISK_REDUCED_TO_ZERO"; return false; }
   reason=learned ? "LIVE_V1_PLAN_READY" : "LIVE_V1_PLAN_READY_COST_ESTIMATED";
   return true;
  }

bool EEA_ControlledLiveBuildRiskContext(const EEA_ControlledLiveConfig &config,
                                        const EEA_ObserverRuntimeContext &observer,
                                        const EEA_S02Engine &engine,
                                        const EEA_RuntimeSymbolSpec &symbol,
                                        const EEA_PolicySettings &policy,
                                        EEA_DryRunContext &current,
                                        EEA_DryRunEvidence &evidence[],
                                        EEA_RuntimeTradeQuote &final_quote,
                                        string &reason)
  {
   EEA_ControlledLiveTradePlan plan;
   EEA_ControlledLivePlanFromConfig(config,engine,symbol,plan);
   return EEA_ControlledLiveBuildRiskContextPlan(config,plan,observer,engine,symbol,policy,current,evidence,
                                                 final_quote,reason);
  }

bool EEA_ControlledLiveBuildRiskContextPlan(const EEA_ControlledLiveConfig &config,
                                            const EEA_ControlledLiveTradePlan &plan,
                                        const EEA_ObserverRuntimeContext &observer,
                                        const EEA_S02Engine &engine,
                                        const EEA_RuntimeSymbolSpec &symbol,
                                        const EEA_PolicySettings &policy,
                                        EEA_DryRunContext &current,
                                        EEA_DryRunEvidence &evidence[],
                                        EEA_RuntimeTradeQuote &final_quote,
                                        string &reason)
  {
   reason="LIVE_RISK_CONTEXT_INVALID";
   if(plan.setup_version=="" || plan.initial_capital<=0.0 || plan.safety_buffer_money<0.0 ||
      plan.balance_at_daily_reset<=0.0 || plan.daily_reset_at_utc<=0 ||
      plan.base_risk_fraction<=0.0 || plan.base_risk_fraction>1.0 ||
      plan.per_trade_cap_money<=0.0 || plan.portfolio_cap_money<=0.0 ||
      plan.minimum_net_rr<=0.0 || plan.stop_buffer_price<=0.0 || plan.invalidation_price<=0.0 ||
      (plan.target_price<=0.0 && plan.target_r_multiple<=0.0) || plan.max_spread_points<=0.0 ||
      plan.cost_per_lot_money<0.0 || config.quote_freshness_seconds<1 || config.release_ttl_seconds<1)
     { reason="LIVE_RISK_INPUTS_INCOMPLETE"; return false; }
   bool state_ok=(engine.state==EEA_S02_TRIGGERED || (plan.allow_armed && engine.state==EEA_S02_ARMED));
   if(!state_ok || engine.candidate.candidate_id=="" ||
      (engine.direction!=1 && engine.direction!=-1) || symbol.broker_symbol=="")
     { reason="LIVE_CANDIDATE_NOT_TRIGGERED"; return false; }
   double existing_stress_loss=0.0, floating_pnl=0.0;
   if(!EEA_ControlledLiveExistingStress(observer,existing_stress_loss,floating_pnl,reason)) return false;

   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(symbol.broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0)
     { reason="LIVE_ENTRY_QUOTE_UNAVAILABLE"; return false; }
   const int order_type=(engine.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double entry=plan.entry_price>0.0 ? plan.entry_price : (engine.direction==1 ? tick.ask : tick.bid);
   const double distance=MathAbs(entry-plan.invalidation_price);
   const double target=plan.target_price>0.0 ? plan.target_price :
      (engine.direction==1 ? entry+distance*plan.target_r_multiple : entry-distance*plan.target_r_multiple);
   EEA_StructuralLevels levels;
   if(!EEA_ProposeStructuralLevels(engine.direction,entry,plan.invalidation_price,
                                    target,plan.stop_buffer_price,symbol.tick_size,levels))
     { reason="LIVE_STRUCTURAL_LEVELS_INVALID"; return false; }

   EEA_RuntimeTradeQuote unit_quote;
   string quote_reason;
   if(!EEA_ReadRuntimeTradeQuote(observer.account,symbol,order_type,entry,levels.stop_loss,
                                  levels.take_profit,1.0,config.quote_freshness_seconds,
                                  unit_quote,quote_reason))
     { reason=quote_reason; return false; }
   if(unit_quote.spread_points>plan.max_spread_points)
     { reason="LIVE_SPREAD_LIMIT_EXCEEDED"; return false; }
   if(plan.max_spread_stop_fraction>0.0 &&
      unit_quote.spread_points*symbol.point>plan.max_spread_stop_fraction*MathAbs(entry-levels.stop_loss))
     { reason="SPREAD_TOO_WIDE_FOR_STOP"; return false; }

   double gain_unit=0.0;
   if(!OrderCalcProfit((ENUM_ORDER_TYPE)order_type,symbol.broker_symbol,1.0,
                       unit_quote.entry_price,levels.take_profit,gain_unit) ||
      !EEA_IsFiniteDouble(gain_unit) || gain_unit<=0.0)
     { reason="LIVE_REWARD_CALCULATION_INVALID"; return false; }

   EEA_FtmoPolicy ftmo_policy;
   EEA_FtmoPolicyDefaults(ftmo_policy);
   ftmo_policy.policy_id=policy.committed_policy; ftmo_policy.status="ACTIVE";
   ftmo_policy.config_version=observer.config_version; ftmo_policy.source_version="policy-settings-v1.0.0";
   ftmo_policy.source_reference="policy-settings-revision-"+IntegerToString(policy.revision);
   ftmo_policy.policy_timezone="Europe/Prague"; ftmo_policy.account_currency=observer.account.account_currency;
   ftmo_policy.initial_capital=plan.initial_capital; ftmo_policy.safety_buffer_money=plan.safety_buffer_money;
   ftmo_policy.continue_after_daily_profit_target=policy.committed_daily_continuation;
   ftmo_policy.continue_after_overall_profit_target=policy.committed_overall_continuation;

   EEA_FtmoInputs ftmo_input; EEA_FtmoInputDefaults(ftmo_input);
   ftmo_input.daily_snapshot_config_version=observer.config_version;
   ftmo_input.daily_snapshot_currency=observer.account.account_currency;
   ftmo_input.daily_snapshot_quality="OK";
   ftmo_input.daily_snapshot_id="daily-"+IntegerToString((long)plan.daily_reset_at_utc);
   ftmo_input.daily_reset_at_utc=plan.daily_reset_at_utc; ftmo_input.daily_snapshot_valid=true;
   ftmo_input.reset_window_confirmed_by_caller=true;
   ftmo_input.balance_at_daily_reset=plan.balance_at_daily_reset;
   ftmo_input.current_balance=observer.account.balance;
   ftmo_input.floating_pnl_after_costs=floating_pnl;
   ftmo_input.proposed_stress_loss=MathMin(plan.per_trade_cap_money,
                                           observer.account.equity*plan.base_risk_fraction);
   ftmo_input.stress_loss_currency=observer.account.account_currency;
   ftmo_input.high_water_snapshot_valid=true; ftmo_input.high_water_snapshot_quality="OK";
   ftmo_input.high_water_config_version=observer.config_version;
   ftmo_input.high_water_as_of_utc=plan.daily_reset_at_utc;
   ftmo_input.prior_overall_high_water_balance=plan.prior_overall_high_water_balance;
   EEA_FtmoHeadroom headroom;
   if(!EEA_FtmoCalculate(ftmo_policy,ftmo_input,headroom) || headroom.headroom_status!="SUFFICIENT")
     { reason=headroom.reason_code; return false; }

   EEA_PortfolioBudgetInputs portfolio_input;
   portfolio_input.config_version=observer.config_version;
   portfolio_input.account_currency=observer.account.account_currency;
   portfolio_input.data_quality="OK"; portfolio_input.account_scope="ACCOUNT_WIDE";
   portfolio_input.reconciliation_status="RECONCILED";
   portfolio_input.policy_floor_calculation_valid=headroom.calculation_valid;
   portfolio_input.policy_headroom_quality="OK";
   portfolio_input.policy_config_version=observer.config_version;
   portfolio_input.policy_headroom_currency=observer.account.account_currency;
   portfolio_input.external_orders_included=true; portfolio_input.account_mode_reconciled=true;
   portfolio_input.portfolio_limits_confirmed=true;
   portfolio_input.equity_after_costs=observer.account.equity;
   portfolio_input.base_risk_fraction=plan.base_risk_fraction;
   portfolio_input.per_trade_cap_money=plan.per_trade_cap_money;
   portfolio_input.portfolio_remaining_money=plan.portfolio_cap_includes_existing ?
      MathMax(0.0,plan.portfolio_cap_money-existing_stress_loss) : plan.portfolio_cap_money;
   portfolio_input.policy_headroom_after_buffer_money=headroom.available_headroom;
   portfolio_input.existing_stress_loss_money=existing_stress_loss;
   EEA_PortfolioBudgetResult portfolio;
   if(!EEA_CalculatePortfolioBudget(portfolio_input,portfolio) || portfolio.budget_status!="BUDGET_AVAILABLE")
     { reason=portfolio.reason_code; return false; }

   if(plan.currency_cap_money>0.0)
     {
      EEA_CurrencyExposure exposure; string exposure_reason;
      if(!EEA_ControlledLiveExposure(observer,exposure,exposure_reason)) { reason=exposure_reason; return false; }
      if(!EEA_CurrencyExposureAllows(exposure,symbol.base_currency,symbol.profit_currency,engine.direction,
                                     portfolio.budget_money,plan.currency_cap_money,plan.max_correlated_trades,
                                     exposure_reason))
        { reason=exposure_reason; return false; }
     }
   // Costs per lot are part of the loss at the stop, so they reduce the volume.
   double raw_volume=portfolio.budget_money/(unit_quote.projected_loss+plan.cost_per_lot_money);
   double final_volume=MathFloor(MathMin(raw_volume,symbol.volume_max)/symbol.volume_step)*symbol.volume_step;
   if(!EEA_IsFiniteDouble(final_volume) || final_volume<symbol.volume_min)
     { reason="LIVE_VOLUME_BELOW_SYMBOL_MINIMUM"; return false; }
   if(!EEA_ReadRuntimeTradeQuote(observer.account,symbol,order_type,entry,levels.stop_loss,
                                 levels.take_profit,final_volume,config.quote_freshness_seconds,
                                 final_quote,quote_reason))
     { reason=quote_reason; return false; }
   if(final_quote.spread_points>plan.max_spread_points)
     { reason="LIVE_SPREAD_LIMIT_EXCEEDED"; return false; }
   if(plan.min_margin_level_percent>0.0)
     {
      double margin_after=observer.account.margin+final_quote.required_margin;
      if(margin_after>0.0 && observer.account.equity/margin_after*100.0<plan.min_margin_level_percent)
        { reason="MARGIN_LEVEL_TOO_LOW"; return false; }
     }
   double gain_final=0.0;
   if(!OrderCalcProfit((ENUM_ORDER_TYPE)order_type,symbol.broker_symbol,final_volume,
                       final_quote.entry_price,levels.take_profit,gain_final) ||
      !EEA_IsFiniteDouble(gain_final) || gain_final<=0.0)
     { reason="LIVE_REWARD_CALCULATION_INVALID"; return false; }

   EEA_VolumeSizingInput volume_input;
   volume_input.config_version=observer.config_version;
   volume_input.account_currency=observer.account.account_currency;
   volume_input.risk_budget=portfolio.budget_money;
   volume_input.loss_quote_valid=true; volume_input.loss_quote_quality="OK";
   volume_input.loss_quote_version=observer.config_version;
   volume_input.loss_quote_currency=observer.account.account_currency;
   volume_input.loss_per_lot_at_sl=unit_quote.projected_loss;
   volume_input.volume_min=symbol.volume_min; volume_input.volume_max=symbol.volume_max;
   volume_input.volume_step=symbol.volume_step;
   volume_input.final_loss_quote_valid=true; volume_input.final_loss_quote_quality="OK";
   volume_input.final_loss_quote_version=observer.config_version;
   volume_input.final_loss_quote_currency=observer.account.account_currency;
   volume_input.final_loss_quote_volume=final_volume;
   volume_input.final_loss_at_sl=final_quote.projected_loss;
   volume_input.margin_quote_valid=true; volume_input.margin_quote_quality="OK";
   volume_input.margin_quote_version=observer.config_version;
   volume_input.margin_quote_currency=observer.account.account_currency;
   volume_input.margin_quote_volume=final_volume;
   volume_input.required_margin=final_quote.required_margin;
   volume_input.available_margin=final_quote.available_margin;
   EEA_VolumeSizingResult sizing;
   if(!EEA_SizeVolume(volume_input,sizing) || sizing.volume!=final_volume)
     { reason=sizing.reason_code; return false; }

   EEA_TradeEconomicsInput economics_input;
   economics_input.config_version=observer.config_version;
   economics_input.account_currency=observer.account.account_currency;
   economics_input.quote_config_version=observer.config_version;
   economics_input.quote_currency=observer.account.account_currency;
   economics_input.quote_quality="OK"; economics_input.pricing_snapshot_id=final_quote.snapshot_id;
   economics_input.loss_quote_valid=true; economics_input.reward_quote_valid=true;
   economics_input.target_space_confirmed=true;
   economics_input.execution_constraints_confirmed=final_quote.spread_points<=plan.max_spread_points;
   economics_input.direction=engine.direction; economics_input.entry_reference=final_quote.entry_price;
   economics_input.stop_loss=levels.stop_loss; economics_input.take_profit=levels.take_profit;
   economics_input.final_volume=final_volume; economics_input.quote_volume=final_volume;
   economics_input.net_loss_at_sl_money=final_quote.projected_loss+plan.cost_per_lot_money*final_volume;
   economics_input.net_gain_at_tp_money=gain_final-plan.cost_per_lot_money*final_volume;
   economics_input.minimum_net_rr=plan.minimum_net_rr;
   EEA_TradeEconomicsResult economics;
   if(!EEA_CheckTradeEconomics(economics_input,economics) || economics.economics_status!="ECONOMICS_ACCEPTABLE")
     { reason=economics.reason_code; return false; }

   EEA_SymbolResolution resolution; EEA_SymbolResolutionDefaults(resolution,engine.canonical_symbol);
   resolution.resolved=true; resolution.status="RESOLVED"; resolution.broker_symbol=symbol.broker_symbol;
   resolution.broker_server=observer.account.broker_server; resolution.source_version="runtime-symbol-v1";
   resolution.metadata_version="runtime-symbol-v1"; resolution.metadata_fingerprint=symbol.metadata_fingerprint;
   current.config_version=observer.config_version; current.setup_config_version=engine.config_version;
   current.account_currency=observer.account.account_currency; current.canonical_symbol=engine.canonical_symbol;
   current.broker_symbol=symbol.broker_symbol; current.broker_server=observer.account.broker_server;
   current.levels_snapshot_id="levels-"+engine.candidate.candidate_id;
   current.portfolio_snapshot_id="portfolio-"+observer.reconciliation.snapshot_id+"-"+engine.candidate.candidate_id;
   current.volume_quote_snapshot_id=final_quote.snapshot_id; current.evaluated_at_utc=TimeGMT();
   current.symbol=resolution; current.candidate=engine.candidate; current.levels=levels;
   current.economics_input=economics_input; current.economics=economics; current.headroom=headroom;
   current.portfolio_input=portfolio_input; current.portfolio=portfolio; current.volume_input=volume_input;
   current.sizing=sizing;
   ArrayResize(evidence,EEA_DRYRUN_STAGE_COUNT);
   const int age=config.quote_freshness_seconds;
   EEA_ControlledLiveFillEvidence(evidence[0],EEA_DRYRUN_EVIDENCE_SYMBOL,"OK",observer.config_version,
      resolution.source_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,symbol.metadata_fingerprint,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[1],EEA_DRYRUN_EVIDENCE_CANDIDATE,"OK",observer.config_version,
      engine.config_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,engine.candidate.candidate_id,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[2],EEA_DRYRUN_EVIDENCE_LEVELS,"OK",observer.config_version,
      engine.config_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,current.levels_snapshot_id,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[3],EEA_DRYRUN_EVIDENCE_ECONOMICS,"OK",observer.config_version,
      observer.config_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,final_quote.snapshot_id,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[4],EEA_DRYRUN_EVIDENCE_FTMO,"OK",observer.config_version,
      ftmo_policy.source_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,headroom.snapshot_id,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[5],EEA_DRYRUN_EVIDENCE_PORTFOLIO,"OK",observer.config_version,
      observer.config_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,current.portfolio_snapshot_id,TimeGMT(),age);
   EEA_ControlledLiveFillEvidence(evidence[6],EEA_DRYRUN_EVIDENCE_VOLUME,"OK",observer.config_version,
      observer.config_version,observer.account.account_currency,engine.canonical_symbol,symbol.broker_symbol,
      observer.account.broker_server,final_quote.snapshot_id,TimeGMT(),age);
   reason="LIVE_RISK_CONTEXT_READY";
   return true;
  }

// The session caps risk per trade on top of O-04; it can only lower the plan's risk.
bool EEA_ControlledLiveApplySessionCap(const bool session_mode,const EEA_LiveSessionRuntime &session,
                                       const EEA_RiskLedger &ledger,EEA_ControlledLiveTradePlan &plan,string &reason)
  {
   if(!session_mode) return true;
   const double cap=session.session.max_risk_per_trade_fraction;
   if(cap<=0.0) { reason="LIVE_SESSION_LIMITS_INVALID"; return false; }
   plan.base_risk_fraction=MathMin(plan.base_risk_fraction,cap);
   plan.per_trade_cap_money=MathMin(plan.per_trade_cap_money,cap*ledger.initial_capital);
   return true;
  }

// News Guard: a pending order may not stay working into its profile's block window.
// Its broker expiry is capped at the block start; too little time left means no order.
bool EEA_ControlledLiveApplyNewsExpiry(const EEA_NewsRuntime &news,const string canonical,const string profile,
                                       const string timeframe,EEA_ControlledLiveTradePlan &plan,string &reason)
  {
   if(plan.pending_order_type<ORDER_TYPE_BUY_LIMIT) return true;
   const long block_start=EEA_NewsBlockStartFor(news,canonical,profile);
   if(block_start<=0) return true;
   const long now=(long)TimeGMT();
   const long tf_seconds=PeriodSeconds(timeframe=="H1" ? PERIOD_H1 : PERIOD_M5);
   if(block_start-now<tf_seconds) { reason="NEWS_WINDOW_TOO_CLOSE"; return false; }
   if((long)plan.pending_expiration_utc>block_start)
     {
      plan.pending_expiration_utc=(datetime)block_start;
      plan.pending_max_wait_bars=(int)MathMin((long)plan.pending_max_wait_bars,(block_start-now)/tf_seconds);
     }
   return true;
  }

// News Guard on working EA pending orders: when the order's profile is blocked, a
// non-bar guard observation requires the cancel at once (REQ-021 + design 7.2).
void EEA_PendingApplyNews(EEA_PendingRuntime &rt,EEA_NewsRuntime &news,CAuditLog &audit,const string root)
  {
   const long now=(long)TimeGMT();
   for(int i=0;i<rt.count;i++)
     {
      if(!rt.items[i].active) continue;
      EEA_PendingTracked t=rt.items[i];
      if(t.state.status!="WORKING" && t.state.status!="PARTIAL") continue;
      string reason=EEA_NewsDirectBlockFor(news,t.state.canonical_symbol,t.state.trade_style);
      if(reason=="") continue;
      EEA_PendingGuard g;
      g.intent_id=t.state.intent_id; g.config_version=t.state.config_version;
      g.snapshot_id="news-"+IntegerToString(now); g.content_fingerprint=reason;
      g.observed_at_utc=(datetime)now; g.setup_valid=true; g.session_open=true; g.risk_entry_allowed=true;
      g.news_entry_allowed=false; g.quote_premise_valid=true; g.config_spec_unchanged=true; g.data_quality="OK";
      if(!EEA_PendingObserveGuard(t.state,g)) continue;
      if(t.state.status=="CANCEL_REQUIRED")
        {
         EEAEvent event;
         EEAEvent_Init(event,"NEWS_PENDING_CANCEL",TimeGMT(),t.state.canonical_symbol,t.state.candidate_id,
                       "WORKING","CANCEL_REQUIRED","OK");
         event.config_version=t.state.config_version;
         EEAEvent_AddReason(event,reason);
         event.details_json="{\"order_ticket\":\""+EEA_JsonEscape(t.state.order_ticket)+"\",\"reason\":\""+reason+"\"}";
         audit.Append(event,"EA_NEWS_GUARD");
         EEA_NewsNoteEffect(news,t.state.canonical_symbol,"PENDING_CANCEL");
        }
      EEA_PendingWrite(root,t);
      rt.items[i]=t;
     }
  }

// Yellow (indirect) news: SCALP risk is reduced, never raised.
bool EEA_ControlledLiveApplyNewsRisk(const EEA_NewsRuntime &news,const string canonical,const string profile,
                                     EEA_ControlledLiveTradePlan &plan,string &reason)
  {
   double factor=EEA_NewsRiskFactorFor(news,canonical,profile);
   if(factor<=0.0 || factor>1.0) { reason="NEWS_RISK_FACTOR_INVALID"; return false; }
   plan.base_risk_fraction*=factor;
   plan.per_trade_cap_money*=factor;
   return true;
  }

// Market sentiment (M1-M6): reduce-only. A SWING trade strongly against the flow is
// blocked; against the flow halves the risk; when HTF x yellow news x sentiment falls
// below the floor the trade is skipped. Unavailable sentiment is neutral.
bool EEA_ControlledLiveApplySentiment(const EEA_SentimentRuntime &sentiment,const EEA_NewsRuntime &news,
                                      const EEA_StrategyCandidateRuntime &strategy,const int index,
                                      EEA_ControlledLiveTradePlan &plan,EEA_SentAlignment &alignment,string &reason)
  {
   const EEA_S02Engine engine=strategy.engines[index];
   const string profile=strategy.profile[index];
   EEA_SentimentAlignFor(sentiment,engine.canonical_symbol,engine.direction,profile,alignment);
   if(alignment.block) { reason="SENTIMENT_STRONGLY_AGAINST"; return false; }
   if(alignment.factor<=0.0 || alignment.factor>1.0) { reason="SENTIMENT_FACTOR_INVALID"; return false; }
   double combined=MathMax(0.0,MathMin(1.0,strategy.htf_risk_modifier[index]))*
                   EEA_NewsRiskFactorFor(news,engine.canonical_symbol,profile)*alignment.factor;
   if(combined<sentiment.cfg.min_combined_factor) { reason="RISK_MODIFIERS_TOO_LOW"; return false; }
   plan.base_risk_fraction*=alignment.factor;
   plan.per_trade_cap_money*=alignment.factor;
   return true;
  }

// D4 (G9): never two opposite EA exposures on one symbol, whichever setup came first.
bool EEA_ControlledLiveOppositeActive(const EEA_TradeManagerRuntime &trades,const EEA_PendingRuntime &pending,
                                      const string canonical,const int direction)
  {
   for(int i=0;i<trades.count;i++)
      if(trades.items[i].active && trades.items[i].intent.canonical_symbol==canonical &&
         trades.items[i].direction==-direction) return true;
   for(int i=0;i<pending.count;i++)
     {
      if(!pending.items[i].active || pending.items[i].state.canonical_symbol!=canonical) continue;
      int type=pending.items[i].intent.order_type;
      int d=(type==ORDER_TYPE_BUY || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP ||
             type==ORDER_TYPE_BUY_STOP_LIMIT) ? 1 : -1;
      if(d==-direction) return true;
     }
   return false;
  }

// SHADOW mode (S02 and S04): every triggered candidate of a setup in SHADOW is recorded once
// with the trade the live path would have planned (entry type, SL, TP, risk, volume,
// filters). Nothing is sent. An S02 LIMIT at the zone (ARMED) is not recorded.
void EEA_S04ShadowOnTimer(EEA_ControlledLiveRuntimeState &state,const EEA_StrategyCandidateRuntime &strategy,
                          const EEA_ObserverRuntimeContext &observer,const EEA_RiskLedger &ledger,
                          const EEA_NewsRuntime &news,const EEA_SentimentRuntime &sentiment,
                          const EEA_TradeManagerRuntime &trades,const EEA_PendingRuntime &pending,CAuditLog &audit)
  {
   if(!strategy.enabled) return;
   for(int i=0;i<strategy.symbol_count;i++)
     {
      if(EEA_StrategyRuntimeSetupMode(strategy,strategy.setup[i])!=EEA_S04_MODE_SHADOW ||
         !strategy.has_candidate[i] || strategy.engines[i].state!=EEA_S02_TRIGGERED) continue;
      const EEA_S02Engine engine=strategy.engines[i];
      const string candidate_id=engine.candidate.candidate_id;
      if(candidate_id=="" || state.shadow_noted_candidate[i]==candidate_id) continue;
      const int row=EEA_ObserverRuntimeIndexOf(observer,engine.canonical_symbol);
      if(row<0 || row>=ArraySize(observer.broker_symbols) || observer.broker_symbols[row]=="") continue;
      state.shadow_noted_candidate[i]=candidate_id;
      const string broker=observer.broker_symbols[row];
      string entry_reason, reason="SHADOW_PLAN_READY";
      int mode=EEA_S02SelectEntryMode(strategy,i,broker,entry_reason);
      EEA_ControlledLiveTradePlan plan; EEA_ControlledLivePlanDefaults(plan);
      EEA_SentAlignment alignment;
      alignment.ok=false; alignment.verdict="UNAVAILABLE"; alignment.factor=1.0; alignment.block=false; alignment.reason="";
      alignment.a4=0.0; alignment.a24=0.0; alignment.against4=0.0; alignment.against24=0.0;
      bool planned=false;
      EEA_PolicySettings policy;
      if(mode<0) reason=entry_reason;
      else if(EEA_ControlledLiveResolvePolicy(observer.root,observer.config_version,observer.account,policy,reason) &&
              EEA_ControlledLiveResolveV1Plan(strategy,i,observer,observer.symbol_specs[row],policy,ledger,mode,plan,reason) &&
              EEA_ControlledLiveApplyNewsRisk(news,engine.canonical_symbol,strategy.profile[i],plan,reason) &&
              EEA_ControlledLiveApplySentiment(sentiment,news,strategy,i,plan,alignment,reason))
        { planned=true; reason="SHADOW_PLAN_READY"; }
      MqlTick tick; ZeroMemory(tick);
      SymbolInfoTick(broker,tick);
      double entry=plan.entry_price>0.0 ? plan.entry_price : (engine.direction==1 ? tick.ask : tick.bid);
      double stop=planned ? (engine.direction==1 ? plan.invalidation_price-plan.stop_buffer_price :
                                                   plan.invalidation_price+plan.stop_buffer_price) : 0.0;
      double volume=0.0, risk_money=0.0;
      if(planned && entry>0.0 && stop>0.0)
        {
         risk_money=MathMin(plan.base_risk_fraction*ledger.initial_capital,plan.per_trade_cap_money);
         double loss=0.0;
         double step=observer.symbol_specs[row].volume_step;
         if(OrderCalcProfit(engine.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,broker,1.0,entry,stop,loss) &&
            loss<0.0 && step>0.0)
            volume=MathFloor(risk_money/(-loss)/step+1e-9)*step;
        }
      const string news_block=EEA_NewsEntryBlockFor(news,engine.canonical_symbol,strategy.profile[i]);
      const bool opposite=EEA_ControlledLiveOppositeActive(trades,pending,engine.canonical_symbol,engine.direction);
      const int digits=(int)SymbolInfoInteger(broker,SYMBOL_DIGITS);
      const string mode_name=(mode==EEA_S02_ENTRY_MARKET ? "MARKET" : mode==EEA_S02_ENTRY_STOP_ABOVE_TRIGGER ? "STOP" : "NONE");
      const string setup=strategy.setup[i];
      string details="{\"candidate_id\":\""+EEA_JsonEscape(candidate_id)+"\",\"setup\":\""+setup+
         "\",\"symbol\":\""+engine.canonical_symbol+
         "\",\"profile\":\""+strategy.profile[i]+"\",\"direction\":"+IntegerToString(engine.direction)+
         ",\"triggered_at\":"+IntegerToString((long)engine.candidate.triggered_at_utc)+
         ",\"zone_low\":"+DoubleToString(engine.zone_low,digits)+",\"zone_high\":"+DoubleToString(engine.zone_high,digits)+
         ",\"failed_extreme\":"+DoubleToString(engine.retest_extreme,digits)+
         ",\"entry_mode\":\""+mode_name+"\",\"entry_reason\":\""+entry_reason+
         "\",\"entry\":"+DoubleToString(entry,digits)+",\"sl\":"+DoubleToString(stop,digits)+
         ",\"tp\":"+DoubleToString(plan.target_price,digits)+",\"risk_fraction\":"+DoubleToString(plan.base_risk_fraction,5)+
         ",\"risk_money\":"+DoubleToString(risk_money,2)+",\"volume\":"+DoubleToString(volume,2)+
         ",\"htf\":\""+strategy.htf_structure[i]+"\",\"htf_modifier\":"+DoubleToString(strategy.htf_risk_modifier[i],2)+
         ",\"sentiment\":\""+alignment.verdict+"\",\"sentiment_factor\":"+DoubleToString(alignment.factor,2)+
         ",\"news_block\":\""+news_block+"\",\"opposite_active\":"+(opposite ? "true" : "false")+
         ",\"plan_reason\":\""+EEA_JsonEscape(reason)+"\"}";
      EEAEvent event;
      EEAEvent_Init(event,setup+"_SHADOW_CANDIDATE",TimeGMT(),engine.canonical_symbol,candidate_id,"","SHADOW","OK");
      event.config_version=observer.config_version;
      EEAEvent_AddReason(event,reason);
      event.details_json=details;
      audit.Append(event,"EA_"+setup+"_SHADOW");
      EEA_WriteAtomicAppendText(observer.root+(setup=="S04" ? "/logs/s04_shadow.jsonl" : "/logs/s02_shadow.jsonl"),
                                details+"\r\n");
     }
  }

bool EEA_ControlledLiveOnTimer(EEA_ControlledLiveRuntimeState &state,
                               const EEA_ControlledLiveConfig &config,
                               const EEA_StrategyCandidateRuntime &strategy,
                               const EEA_ObserverRuntimeContext &observer,
                               const EEA_ExecutionControllerState &controller,
                               const bool controller_allows_market,
                               CAuditLog &audit,
                               const EEA_RiskLedger &ledger,
                               EEA_PendingRuntime &pending,
                               EEA_LiveSessionRuntime &session,
                               EEA_TradeManagerRuntime &trades,
                               EEA_NewsRuntime &news,
                               const EEA_SentimentRuntime &sentiment)
  {
   state.last_attempt_utc=TimeGMT();
   if(!config.enabled || !config.armed) { state.last_reason="CONTROLLED_LIVE_NOT_ARMED"; return true; }
   if(state.recovery_blocked) { state.last_reason="EXECUTION_UNKNOWN_RECOVERY_REQUIRED"; return false; }
   if(!strategy.enabled || observer.status.runtime_state!="OBSERVING")
     { state.last_reason="CONTROLLED_LIVE_RUNTIME_BLOCKED"; return false; }
   // The entry type is chosen per candidate (EEA_S02SelectEntryMode); the controller
   // must grant at least one entry scope, and the chosen one is checked per candidate.
   const bool market_granted=EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT());
   const bool pending_granted=strategy.zone_mode &&
                              EEA_ExecutionControllerAllowsNewRequest(controller,"PENDING_ENTRY",TimeGMT());
   if(!controller_allows_market || (!market_granted && !pending_granted))
     { state.last_reason="CONTROLLED_LIVE_CONTROLLER_BLOCKED"; return false; }
   // REQ-021: any pending order in review, awaiting cancel confirmation or unreadable
   // blocks every new entry until it is resolved against the broker.
   if(pending.entries_blocked) { state.last_reason=pending.reason; return false; }
   for(int i=0;i<strategy.symbol_count;i++)
     {
      // Bind the strategy engine to the observer row by canonical name; a row
      // index can differ after a selection change and must never be reused.
      const int row=EEA_ObserverRuntimeIndexOf(observer,strategy.engines[i].canonical_symbol);
      if(row<0 || row>=ArraySize(observer.broker_symbols) || row>=ArraySize(observer.symbol_specs))
        { state.last_reason="LIVE_SYMBOL_CONTEXT_MISMATCH"; continue; }
      if(observer.broker_symbols[row]=="")
        { state.last_reason="LIVE_SYMBOL_UNRESOLVED"; continue; }
      // A setup sends orders only in LIVE mode; SHADOW is recorded by EEA_S04ShadowOnTimer.
      if(strategy.zone_mode && EEA_StrategyRuntimeSetupMode(strategy,strategy.setup[i])!=EEA_S04_MODE_LIVE) continue;
      bool limit_ready=(strategy.zone_mode && strategy.setup[i]=="S02" && strategy.engines[i].state==EEA_S02_ARMED);
      if(!limit_ready && (!strategy.has_candidate[i] || strategy.engines[i].state!=EEA_S02_TRIGGERED)) continue;
      const string candidate_id=strategy.engines[i].candidate.candidate_id;
      if(candidate_id=="" || candidate_id==state.last_candidate_id[i]) continue;
      if(EEA_TradeManagerHasCandidate(trades,candidate_id) ||
         EEA_PendingRuntimeHasCandidate(pending,candidate_id) ||
         EEA_PendingRuntimeHasEngine(pending,strategy.engines[i].canonical_symbol,strategy.engines[i].timeframe))
         continue;
      if(strategy.zone_mode &&
         EEA_ControlledLiveOppositeActive(trades,pending,strategy.engines[i].canonical_symbol,strategy.engines[i].direction))
        { state.last_reason="OPPOSITE_SETUP_ACTIVE"; continue; }
      int entry_mode=EEA_S02_ENTRY_MARKET;
      string entry_reason="ENTRY_PROTOTYPE_MARKET";
      if(strategy.zone_mode)
        {
         entry_mode=EEA_S02SelectEntryMode(strategy,i,observer.broker_symbols[row],entry_reason);
         if(entry_mode<0) { state.last_reason=entry_reason; continue; }
        }
      const bool pending_mode=(entry_mode!=EEA_S02_ENTRY_MARKET);
      const string scope=(pending_mode ? "PENDING_ENTRY" : "MARKET_ENTRY");
      if(pending_mode ? !pending_granted : !market_granted)
        { state.last_reason="CONTROLLED_LIVE_SCOPE_NOT_GRANTED_"+scope; continue; }
      // News Guard (design 7.1): blocked candidates are not consumed and may enter after the window.
      const string news_profile=(strategy.zone_mode ? strategy.profile[i] : "SCALP");
      const string news_block=EEA_NewsEntryBlockFor(news,strategy.engines[i].canonical_symbol,news_profile);
      if(news_block!="")
        {
         state.last_reason=news_block;
         if(state.news_blocked_candidate[i]!=candidate_id)
           {
            state.news_blocked_candidate[i]=candidate_id;
            EEAEvent event;
            EEAEvent_Init(event,"NEWS_ENTRY_BLOCKED",TimeGMT(),strategy.engines[i].canonical_symbol,candidate_id,
                          "",EEA_NewsStateFor(news,strategy.engines[i].canonical_symbol),"OK");
            event.config_version=observer.config_version;
            EEAEvent_AddReason(event,news_block);
            event.details_json="{\"profile\":\""+news_profile+"\",\"reason\":\""+news_block+"\"}";
            audit.Append(event,"EA_NEWS_GUARD");
            EEA_NewsNoteEffect(news,strategy.engines[i].canonical_symbol,"ENTRY_BLOCKED");
           }
         continue;
        }
      EEA_PolicySettings policy; string reason;
      if(!EEA_ControlledLiveResolvePolicy(observer.root,observer.config_version,observer.account,policy,reason))
        { state.last_reason=reason; continue; }
      EEA_LiveAuthorizationContext auth_context; EEA_LiveAuthorizationDecision authorization;
      string authorization_path=config.authorization_path;
      if(authorization_path=="") authorization_path=observer.root+"/current/live_authorization.json";
      // A signed session (control center) authorizes each candidate inside its limits;
      // without a session file the per-intent document remains the only path.
      const long day_reset=EEA_PragueDailyResetUtc((long)TimeGMT());
      const bool session_mode=session.present;
      const string entry_profile=(strategy.zone_mode ? strategy.profile[i] : "SCALP");
      if(session_mode)
        {
         const bool real_account=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL);
         if(!EEA_LiveSessionAuthorize(session,observer.config_version,observer.account.account_fingerprint,
               observer.account.broker_server,observer.account.account_margin_mode,policy.committed_policy,
               observer.broker_symbols[row],candidate_id,entry_profile,real_account,(long)TimeGMT(),day_reset,
               ledger.initial_capital,ledger.last_reset_balance,observer.account.equity,authorization,reason))
           { state.last_reason=reason; session.reason=reason; continue; }
         authorization_path=EEA_LiveSessionPath(observer.root);
        }
      else
        {
         if(!EEA_LiveAuthorizationStoreLoad(authorization_path,
               observer.config_version,observer.account.account_fingerprint,observer.account.broker_server,
               observer.broker_symbols[row],auth_context,authorization,reason))
           { state.last_reason=reason; continue; }
         if(auth_context.candidate_id!=candidate_id)
           { state.last_reason="LIVE_AUTHORIZATION_CANDIDATE_MISMATCH"; continue; }
        }
      EEA_DryRunContext current; EEA_DryRunEvidence evidence[]; EEA_RuntimeTradeQuote quote;
      // S02 v1 derives the whole plan (structure, costs, O-04, ledger); the prototype
      // keeps its explicit inputs. Both pass the same Risk Kernel checks afterwards.
      bool context_ready=false;
      EEA_ControlledLiveTradePlan plan;
      EEA_ControlledLivePlanDefaults(plan);
      EEA_SentAlignment alignment;
      alignment.ok=false; alignment.verdict="UNAVAILABLE"; alignment.factor=1.0; alignment.block=false; alignment.reason="";
      alignment.a4=0.0; alignment.a24=0.0; alignment.against4=0.0; alignment.against24=0.0;
      if(strategy.zone_mode)
        {
         context_ready=EEA_ControlledLiveResolveV1Plan(strategy,i,observer,observer.symbol_specs[row],policy,
                                                       ledger,entry_mode,plan,reason) &&
                       EEA_ControlledLiveApplySessionCap(session_mode,session,ledger,plan,reason) &&
                       EEA_ControlledLiveApplyNewsExpiry(news,strategy.engines[i].canonical_symbol,news_profile,
                                                         strategy.engines[i].timeframe,plan,reason) &&
                       EEA_ControlledLiveApplyNewsRisk(news,strategy.engines[i].canonical_symbol,news_profile,
                                                       plan,reason) &&
                       EEA_ControlledLiveApplySentiment(sentiment,news,strategy,i,plan,alignment,reason) &&
                       EEA_ControlledLiveBuildRiskContextPlan(config,plan,observer,strategy.engines[i],
                                                              observer.symbol_specs[row],policy,current,
                                                              evidence,quote,reason);
        }
      else
         context_ready=EEA_ControlledLiveBuildRiskContext(config,observer,strategy.engines[i],observer.symbol_specs[row],
                                                          policy,current,evidence,quote,reason);
      // Sentiment effect is audited once per candidate (blocked or reduced).
      if(strategy.zone_mode && alignment.ok && (alignment.block || alignment.factor<1.0) &&
         state.sentiment_noted_candidate[i]!=candidate_id)
        {
         state.sentiment_noted_candidate[i]=candidate_id;
         EEAEvent event;
         EEAEvent_Init(event,"SENTIMENT_APPLIED",TimeGMT(),strategy.engines[i].canonical_symbol,candidate_id,"",
                       alignment.verdict,"OK");
         event.config_version=observer.config_version;
         EEAEvent_AddReason(event,alignment.reason);
         event.details_json="{\"profile\":\""+strategy.profile[i]+"\",\"direction\":"+IntegerToString(strategy.engines[i].direction)+
            ",\"a4\":"+DoubleToString(alignment.a4,3)+",\"a24\":"+DoubleToString(alignment.a24,3)+
            ",\"against4\":"+DoubleToString(alignment.against4,2)+",\"against24\":"+DoubleToString(alignment.against24,2)+
            ",\"factor\":"+DoubleToString(alignment.factor,2)+",\"regime\":\""+sentiment.snap.regime+"\"}";
         audit.Append(event,"EA_SENTIMENT");
        }
      if(!context_ready) { state.last_reason=reason; continue; }
      EEA_DryRunDecision review; EEA_RiskDecision decision;
      if(!EEA_EvaluateDryRunCandidate(current,evidence,review)) { state.last_reason="LIVE_DRY_RUN_"+review.decision_status; continue; }
      EEA_RiskReleaseRecheck recheck; EEA_RiskReleaseRecheckDefaults(recheck);
      recheck.runtime_current=true; recheck.account_reconciled=true; recheck.quote_repriced=true;
      recheck.policy_rechecked=true; recheck.portfolio_reconciled=true; recheck.symbol_spec_unchanged=true;
      recheck.account_id=observer.account.account_fingerprint;
      recheck.reconciliation_fingerprint=observer.reconciliation.snapshot_id;
      recheck.quote_fingerprint=quote.snapshot_id; recheck.portfolio_fingerprint=current.portfolio_snapshot_id;
      recheck.release_reference="controlled-live-"+candidate_id; recheck.checked_at_utc=TimeGMT();
      recheck.expires_at_utc=(datetime)MathMin((long)recheck.checked_at_utc+config.release_ttl_seconds,
                                               MathMin(observer.account.valid_until_utc,observer.reconciliation.valid_until_utc));
      if(!EEA_RiskDecisionReleaseFromReview(current,review,evidence,observer.account,observer.reconciliation,
                                            recheck,TimeGMT(),decision))
        { state.last_reason=decision.reason_code; continue; }
      if(!EEA_RiskDecisionStoreWrite(observer.root,decision))
        { state.last_reason="LIVE_RISK_DECISION_PERSISTENCE_FAILED"; continue; }
      EEA_MarketIntentParameters params; EEA_MarketIntentParametersDefaults(params);
      params.canonical_symbol=current.canonical_symbol; params.setup_version=current.setup_config_version;
      params.risk_policy_snapshot_id="policy-"+IntegerToString(policy.revision);
      params.intent_id=authorization.intent_id; params.correlation_id=authorization.authorization_id;
      // One entry per candidate, whatever authorization or session releases it: a
      // re-signed session or a restart must never send the same candidate twice.
      params.idempotency_key="entry-"+candidate_id;
      params.entry_reference=decision.entry_reference; params.price=quote.entry_price;
      params.stop_loss=decision.stop_loss; params.take_profit=decision.take_profit;
      params.order_type=decision.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      params.deviation=config.deviation; params.filling_mode=config.filling_mode; params.magic=config.magic;
      EEA_ExecutionIntent intent; string intent_reason;
      bool pending_order=(pending_mode && plan.pending_order_type>=ORDER_TYPE_BUY_LIMIT);
      bool built=pending_order ?
         EEA_BuildPendingExecutionIntent(decision,observer.account,observer.reconciliation,observer.symbol_specs[row],
                                         observer.config_version,params,plan.pending_order_type,
                                         plan.pending_expiration_utc,TimeGMT(),intent,intent_reason) :
         EEA_BuildMarketExecutionIntent(decision,observer.account,observer.reconciliation,
                                        observer.symbol_specs[row],observer.config_version,params,TimeGMT(),intent,intent_reason);
      if(!built)
        { state.last_reason=intent_reason; continue; }
      if(!EEA_ControlledLiveAuditAuthorization(audit,authorization,decision,intent,observer.broker_symbols[row],
                                                entry_reason))
        { state.last_reason="LIVE_AUTHORIZATION_AUDIT_FAILED"; continue; }
      EEA_ExecutionResult result;
      // Observer evidence remains entry-blocked by design. Only the fully
      // released, identity-bound path receives a local execution status that
      // permits the execution gate to evaluate the remaining controls.
      EEA_RuntimeStatus execution_status=observer.status;
      execution_status.new_entries_blocked=false;
      bool submitted=EEA_ExecutionSubmit(audit,observer.root,intent,decision,controller,scope,
                                         observer.account,observer.reconciliation,observer.symbol_specs[row],
                                         execution_status,true,authorization,result);
      if(submitted)
        {
         EEA_ExecutionReconcileResult(result,observer.reconciliation,result.request_ticket,
                                      pending_order ? "SUBMIT_PENDING" : "SUBMIT_MARKET",
                                      intent.sl,intent.tp,result.request_ticket_kind);
         if(pending_order)
           {
            // Track the order from the broker acknowledgement on; an order that cannot
            // be tracked blocks every further entry.
            string track_reason;
            EEA_PendingRuntimeRegister(pending,observer.root,intent,result.request_ticket,
                                       strategy.engines[i].timeframe,strategy.profile[i],authorization_path,
                                       plan.max_spread_points,strategy.engines[i].candidate.triggered_at_utc,
                                       plan.pending_max_wait_bars,observer.symbol_specs[row].volume_step,
                                       observer.account.account_currency,track_reason);
           }
         if(!EEA_ExecutionStoreWriteResult(observer.root,result))
           {
            state.recovery_result=result;
            state.recovery_blocked=true;
            state.last_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";
            return false;
           }
         // REQ-005: the Trade Manager takes over the position from the entry acknowledgement.
         string manage_reason;
         if(strategy.zone_mode)
            EEA_TradeManagerRegister(trades,observer.root,intent,result.request_ticket,
                                     pending_order ? "ORDER" : result.request_ticket_kind,strategy.profile[i],
                                     strategy.engines[i].timeframe,strategy.engines[i].zone_low,
                                     strategy.engines[i].zone_high,authorization_path,manage_reason);
         if(session_mode && !EEA_LiveSessionRecordEntry(session,observer.root,day_reset,entry_profile))
            session.reason="LIVE_SESSION_USAGE_PERSISTENCE_FAILED";
         state.recovery_result=result;
         state.recovery_blocked=result.confirmation_state=="EXECUTION_UNKNOWN";
         state.last_candidate_id[i]=candidate_id;
         state.last_reason=result.confirmation_state;
         return true;
        }
      state.last_reason=result.reason_code;
     }
   return state.last_reason=="";
  }

#endif
