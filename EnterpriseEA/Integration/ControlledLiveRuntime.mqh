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
   for(int i=0;i<EEA_STRATEGY_RUNTIME_MAX_ENGINES;i++) s.last_candidate_id[i]="";
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

bool EEA_ControlledLiveAuditAuthorization(CAuditLog &audit,
                                          const EEA_LiveAuthorizationDecision &authorization,
                                          const EEA_RiskDecision &decision,
                                          const EEA_ExecutionIntent &intent,
                                          const string broker_symbol)
  {
   EEAEvent event;
   EEAEvent_Init(event,"LIVE_AUTHORIZATION_BOUND",TimeGMT(),"",decision.candidate_id,
                 decision.symbol,"AUTHORIZED_CONTROLLED_LIVE","OK");
   event.details_json="{\"authorization_id\":\""+EEA_JsonEscape(authorization.authorization_id)+
      "\",\"intent_id\":\""+EEA_JsonEscape(authorization.intent_id)+
      "\",\"candidate_id\":\""+EEA_JsonEscape(decision.candidate_id)+
      "\",\"intent_risk_decision_id\":\""+EEA_JsonEscape(intent.risk_decision_id)+
      "\",\"broker_symbol\":\""+EEA_JsonEscape(broker_symbol)+
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
   reason="LIVE_RISK_CONTEXT_INVALID";
   if(config.setup_version=="" || config.initial_capital<=0.0 || config.safety_buffer_money<0.0 ||
      config.balance_at_daily_reset<=0.0 || config.daily_reset_at_utc<=0 ||
      config.base_risk_fraction<=0.0 || config.base_risk_fraction>1.0 ||
      config.per_trade_cap_money<=0.0 || config.portfolio_remaining_money<=0.0 ||
      config.minimum_net_rr<=0.0 || config.stop_buffer_ticks<=0.0 ||
      config.target_r_multiple<=0.0 || config.max_spread_points<=0.0 ||
      config.quote_freshness_seconds<1 || config.release_ttl_seconds<1)
     { reason="LIVE_RISK_INPUTS_INCOMPLETE"; return false; }
   if(engine.state!=EEA_S02_TRIGGERED || engine.candidate.candidate_id=="" ||
      (engine.direction!=1 && engine.direction!=-1) || symbol.broker_symbol=="")
     { reason="LIVE_CANDIDATE_NOT_TRIGGERED"; return false; }
   double existing_stress_loss=0.0, floating_pnl=0.0;
   if(!EEA_ControlledLiveExistingStress(observer,existing_stress_loss,floating_pnl,reason)) return false;

   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(symbol.broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0)
     { reason="LIVE_ENTRY_QUOTE_UNAVAILABLE"; return false; }
   const int order_type=(engine.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double entry=(engine.direction==1 ? tick.ask : tick.bid);
   const double distance=MathAbs(entry-engine.invalidation_price);
   const double target=(engine.direction==1 ? entry+distance*config.target_r_multiple :
                                                entry-distance*config.target_r_multiple);
   EEA_StructuralLevels levels;
   if(!EEA_ProposeStructuralLevels(engine.direction,entry,engine.invalidation_price,
                                    target,config.stop_buffer_ticks*symbol.tick_size,
                                    symbol.tick_size,levels))
     { reason="LIVE_STRUCTURAL_LEVELS_INVALID"; return false; }

   EEA_RuntimeTradeQuote unit_quote;
   string quote_reason;
   if(!EEA_ReadRuntimeTradeQuote(observer.account,symbol,order_type,entry,levels.stop_loss,
                                  levels.take_profit,1.0,config.quote_freshness_seconds,
                                  unit_quote,quote_reason))
     { reason=quote_reason; return false; }
   if(unit_quote.spread_points>config.max_spread_points)
     { reason="LIVE_SPREAD_LIMIT_EXCEEDED"; return false; }

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
   ftmo_policy.initial_capital=config.initial_capital; ftmo_policy.safety_buffer_money=config.safety_buffer_money;
   ftmo_policy.continue_after_daily_profit_target=policy.committed_daily_continuation;
   ftmo_policy.continue_after_overall_profit_target=policy.committed_overall_continuation;

   EEA_FtmoInputs ftmo_input; EEA_FtmoInputDefaults(ftmo_input);
   ftmo_input.daily_snapshot_config_version=observer.config_version;
   ftmo_input.daily_snapshot_currency=observer.account.account_currency;
   ftmo_input.daily_snapshot_quality="OK";
   ftmo_input.daily_snapshot_id="daily-"+IntegerToString((long)config.daily_reset_at_utc);
   ftmo_input.daily_reset_at_utc=config.daily_reset_at_utc; ftmo_input.daily_snapshot_valid=true;
   ftmo_input.reset_window_confirmed_by_caller=true;
   ftmo_input.balance_at_daily_reset=config.balance_at_daily_reset;
   ftmo_input.current_balance=observer.account.balance;
   ftmo_input.floating_pnl_after_costs=floating_pnl;
   ftmo_input.proposed_stress_loss=MathMin(config.per_trade_cap_money,
                                           observer.account.equity*config.base_risk_fraction);
   ftmo_input.stress_loss_currency=observer.account.account_currency;
   ftmo_input.high_water_snapshot_valid=true; ftmo_input.high_water_snapshot_quality="OK";
   ftmo_input.high_water_config_version=observer.config_version;
   ftmo_input.high_water_as_of_utc=config.daily_reset_at_utc;
   ftmo_input.prior_overall_high_water_balance=config.prior_overall_high_water_balance;
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
   portfolio_input.base_risk_fraction=config.base_risk_fraction;
   portfolio_input.per_trade_cap_money=config.per_trade_cap_money;
   portfolio_input.portfolio_remaining_money=config.portfolio_remaining_money;
   portfolio_input.policy_headroom_after_buffer_money=headroom.available_headroom;
   portfolio_input.existing_stress_loss_money=existing_stress_loss;
   EEA_PortfolioBudgetResult portfolio;
   if(!EEA_CalculatePortfolioBudget(portfolio_input,portfolio) || portfolio.budget_status!="BUDGET_AVAILABLE")
     { reason=portfolio.reason_code; return false; }

   double raw_volume=portfolio.budget_money/unit_quote.projected_loss;
   double final_volume=MathFloor(MathMin(raw_volume,symbol.volume_max)/symbol.volume_step)*symbol.volume_step;
   if(!EEA_IsFiniteDouble(final_volume) || final_volume<symbol.volume_min)
     { reason="LIVE_VOLUME_BELOW_SYMBOL_MINIMUM"; return false; }
   if(!EEA_ReadRuntimeTradeQuote(observer.account,symbol,order_type,entry,levels.stop_loss,
                                 levels.take_profit,final_volume,config.quote_freshness_seconds,
                                 final_quote,quote_reason))
     { reason=quote_reason; return false; }
   if(final_quote.spread_points>config.max_spread_points)
     { reason="LIVE_SPREAD_LIMIT_EXCEEDED"; return false; }
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
   economics_input.execution_constraints_confirmed=final_quote.spread_points<=config.max_spread_points;
   economics_input.direction=engine.direction; economics_input.entry_reference=final_quote.entry_price;
   economics_input.stop_loss=levels.stop_loss; economics_input.take_profit=levels.take_profit;
   economics_input.final_volume=final_volume; economics_input.quote_volume=final_volume;
   economics_input.net_loss_at_sl_money=final_quote.projected_loss;
   economics_input.net_gain_at_tp_money=gain_final;
   economics_input.minimum_net_rr=config.minimum_net_rr;
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

bool EEA_ControlledLiveOnTimer(EEA_ControlledLiveRuntimeState &state,
                               const EEA_ControlledLiveConfig &config,
                               const EEA_StrategyCandidateRuntime &strategy,
                               const EEA_ObserverRuntimeContext &observer,
                               const EEA_ExecutionControllerState &controller,
                               const bool controller_allows_market,
                               CAuditLog &audit)
  {
   state.last_attempt_utc=TimeGMT();
   if(!config.enabled || !config.armed) { state.last_reason="CONTROLLED_LIVE_NOT_ARMED"; return true; }
   if(state.recovery_blocked) { state.last_reason="EXECUTION_UNKNOWN_RECOVERY_REQUIRED"; return false; }
   if(!strategy.enabled || observer.status.runtime_state!="OBSERVING")
     { state.last_reason="CONTROLLED_LIVE_RUNTIME_BLOCKED"; return false; }
   if(!controller_allows_market || !EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT()))
     { state.last_reason="CONTROLLED_LIVE_CONTROLLER_BLOCKED"; return false; }
   for(int i=0;i<strategy.symbol_count;i++)
     {
      // Bind the strategy engine to the observer row by canonical name; a row
      // index can differ after a selection change and must never be reused.
      const int row=EEA_ObserverRuntimeIndexOf(observer,strategy.engines[i].canonical_symbol);
      if(row<0 || row>=ArraySize(observer.broker_symbols) || row>=ArraySize(observer.symbol_specs))
        { state.last_reason="LIVE_SYMBOL_CONTEXT_MISMATCH"; continue; }
      if(observer.broker_symbols[row]=="")
        { state.last_reason="LIVE_SYMBOL_UNRESOLVED"; continue; }
      if(!strategy.has_candidate[i] || strategy.engines[i].state!=EEA_S02_TRIGGERED) continue;
      // S02 v1 candidates need the structural SL/TP and O-04 risk path (plan step 5);
      // until then they are observed only and never reach the execution path.
      if(strategy.zone_mode)
        { state.last_reason="LIVE_S02_V1_RISK_PATH_PENDING"; continue; }
      const string candidate_id=strategy.engines[i].candidate.candidate_id;
      if(candidate_id==state.last_candidate_id[i]) continue;
      EEA_PolicySettings policy; string reason;
      if(!EEA_ControlledLiveResolvePolicy(observer.root,observer.config_version,observer.account,policy,reason))
        { state.last_reason=reason; continue; }
      EEA_LiveAuthorizationContext auth_context; EEA_LiveAuthorizationDecision authorization;
      string authorization_path=config.authorization_path;
      if(authorization_path=="") authorization_path=observer.root+"/current/live_authorization.json";
      if(!EEA_LiveAuthorizationStoreLoad(authorization_path,
            observer.config_version,observer.account.account_fingerprint,observer.account.broker_server,
            observer.broker_symbols[row],auth_context,authorization,reason))
        { state.last_reason=reason; continue; }
      if(auth_context.candidate_id!=candidate_id)
        { state.last_reason="LIVE_AUTHORIZATION_CANDIDATE_MISMATCH"; continue; }
      EEA_DryRunContext current; EEA_DryRunEvidence evidence[]; EEA_RuntimeTradeQuote quote;
      if(!EEA_ControlledLiveBuildRiskContext(config,observer,strategy.engines[i],observer.symbol_specs[row],
                                             policy,current,evidence,quote,reason))
        { state.last_reason=reason; continue; }
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
      params.idempotency_key=authorization.intent_id+"-"+candidate_id;
      params.entry_reference=decision.entry_reference; params.price=quote.entry_price;
      params.stop_loss=decision.stop_loss; params.take_profit=decision.take_profit;
      params.order_type=decision.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      params.deviation=config.deviation; params.filling_mode=config.filling_mode; params.magic=config.magic;
      EEA_ExecutionIntent intent; string intent_reason;
      if(!EEA_BuildMarketExecutionIntent(decision,observer.account,observer.reconciliation,
                                         observer.symbol_specs[row],observer.config_version,params,TimeGMT(),intent,intent_reason))
        { state.last_reason=intent_reason; continue; }
      if(!EEA_ControlledLiveAuditAuthorization(audit,authorization,decision,intent,observer.broker_symbols[row]))
        { state.last_reason="LIVE_AUTHORIZATION_AUDIT_FAILED"; continue; }
      EEA_ExecutionResult result;
      // Observer evidence remains entry-blocked by design. Only the fully
      // released, identity-bound path receives a local execution status that
      // permits the execution gate to evaluate the remaining controls.
      EEA_RuntimeStatus execution_status=observer.status;
      execution_status.new_entries_blocked=false;
      bool submitted=EEA_ExecutionSubmit(audit,observer.root,intent,decision,controller,"MARKET_ENTRY",
                                         observer.account,observer.reconciliation,observer.symbol_specs[row],
                                         execution_status,true,authorization,result);
      if(submitted)
        {
         EEA_ExecutionReconcileResult(result,observer.reconciliation,result.request_ticket,
                                      "SUBMIT_MARKET",intent.sl,intent.tp,result.request_ticket_kind);
         if(!EEA_ExecutionStoreWriteResult(observer.root,result))
           {
            state.recovery_result=result;
            state.recovery_blocked=true;
            state.last_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";
            return false;
           }
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
