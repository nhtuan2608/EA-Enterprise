#ifndef ENTERPRISE_EA_S06B_PYRAMID_RUNTIME_MQH
#define ENTERPRISE_EA_S06B_PYRAMID_RUNTIME_MQH

#include "ControlledLiveRuntime.mqh"

// G31 (research G28, shadow G29): one pyramiding add for a live S06B trade. OFF by default
// (InpS06BPyramidLive). When a closed bar of the trade's timeframe closes at least
// EEA_S06B_ADD_AT_R (+1R of the first trade) and the first trade's stop is already at
// break-even, one MARKET add of the same risk unit is sent with its stop at that break-even
// stop and the first trade's target, so the open risk of the pair never exceeds one unit.
// The add passes every check of a normal entry (session authorization, FTMO headroom,
// portfolio budget, currency exposure, volume, economics, news window); only its plan is
// built here instead of from a setup engine. The Trade Manager then manages the add as in the
// research (pyramid.py rule2): no break-even move (already there), no partial, no structure
// exit; trailing from +2R of its own risk; time stop as SWING. One add per trade, ever
// (ManagedTrade.add_candidate, persisted).

#define EEA_S06B_ADD_AT_R 1.0
#define EEA_S06B_ADD_SUFFIX "-ADD1"
#define EEA_S06B_ADD_MIN_RR 1.5     // +1R add to a 3R target: about 2R gross before costs
#define EEA_T2_ADD_AT_R 1.0         // G43/G44: T2 add at +1R (research/long/g43_low_risk.py C2)

bool   g_s06b_pyramid_live=false;
bool   g_t2_pyramid_live=false;     // G44: one add for a LIVE T2 trade (InpT2PyramidLive, off by default)
string g_s06b_pyramid_reason="PYRAMID_OFF";

bool EEA_S06BIsAddCandidate(const string candidate_id)
  {
   const int n=StringLen(candidate_id), k=StringLen(EEA_S06B_ADD_SUFFIX);
   return n>k && StringSubstr(candidate_id,n-k)==EEA_S06B_ADD_SUFFIX;
  }

// Engine slot of the S06B setup for a symbol (its mode and config version are reused).
int EEA_S06BEngineIndex(const EEA_StrategyCandidateRuntime &strategy,const string canonical,const string setup="S06B")
  {
   for(int i=0;i<strategy.symbol_count;i++)
      if(strategy.setup[i]==setup && strategy.engines[i].canonical_symbol==canonical) return i;
   return -1;
  }

// The last closed bar of the trade timeframe closes at +add_at_r or better.
bool EEA_S06BAddBarReady(const EEA_ManagedTrade &t,const double add_at_r,datetime &bar_time)
  {
   const double r=MathAbs(t.entry_price-t.initial_sl);
   if(r<=0.0) return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   if(CopyRates(t.intent.broker_symbol,EEA_PendingTimeframe(t.timeframe),1,1,rates)!=1) return false;
   bar_time=rates[0].time;
   return t.direction*(rates[0].close-t.entry_price)>=add_at_r*r;
  }

// Plan of the add: stop at the first trade's current (break-even) stop, target the first
// trade's target, limits and FTMO facts exactly as EEA_ControlledLiveResolveV1Plan.
bool EEA_S06BAddPlan(const EEA_ManagedTrade &t,const EEA_RuntimePositionRow &position,
                     const EEA_ObserverRuntimeContext &observer,const EEA_RuntimeSymbolSpec &symbol,
                     const EEA_PolicySettings &policy,const EEA_RiskLedger &ledger,const string setup_version,
                     EEA_ControlledLiveTradePlan &p,string &reason,const string setup="S06B")
  {
   EEA_ControlledLivePlanDefaults(p);
   const bool t2=(setup=="T2");
   EEA_RiskLimits limits;
   if(!EEA_RiskLimitsForPolicy(policy.committed_policy,limits,reason)) return false;
   if(ledger.initial_capital<=0.0) { reason="LIVE_INITIAL_CAPITAL_UNKNOWN"; return false; }
   if(ledger.last_reset_utc!=EEA_PragueDailyResetUtc((long)TimeGMT()) || ledger.last_reset_balance<=0.0)
     { reason="LIVE_DAILY_RESET_SNAPSHOT_STALE"; return false; }
   if(t.initial_tp<=0.0) { reason="S06B_ADD_NO_TARGET"; return false; }
   // S06B: the first trade is already at break-even. T2 (research pyramid.run): the add's stop is the
   // first trade's entry; the first trade keeps its own (ATR trail) stop, so both can be at risk.
   if(!t2 && (position.sl<=0.0 || t.direction*(position.sl-t.entry_price)<0.0))
     { reason="S06B_ADD_FIRST_STOP_NOT_AT_BREAK_EVEN"; return false; }
   const double tick=symbol.tick_size>0.0 ? symbol.tick_size : symbol.point;
   double median_spread=EEA_MedianSpreadPoints(symbol.broker_symbol,EEA_S02_SPREAD_MEDIAN_BARS);
   if(median_spread<=0.0) { reason="LIVE_SPREAD_MEDIAN_UNAVAILABLE"; return false; }
   bool learned=false;
   double cost=2.0*EEA_CommissionPerLotPerSide(observer.reconciliation,symbol.broker_symbol,learned);
   bool known=false;
   double swap=EEA_SwapMoneyPerLotPerNight(symbol,t.direction,known);
   if(swap<0.0) cost+=-swap*(t2 ? EEA_T2_EXPECTED_NIGHTS : EEA_S02_SWING_EXPECTED_NIGHTS);
   if(!known) learned=false;
   double loss_room=0.0;
   if(!EEA_ControlledLiveInternalLossRoom(observer,ledger,policy.committed_policy,limits,loss_room,reason)) return false;
   p.setup_version=setup_version;
   p.initial_capital=ledger.initial_capital;
   p.safety_buffer_money=limits.safety_buffer_fraction*ledger.initial_capital;
   p.balance_at_daily_reset=ledger.last_reset_balance;
   p.equity_at_daily_reset=EEA_LedgerDailyReference(ledger,policy.committed_policy);
   p.daily_reset_at_utc=(datetime)ledger.last_reset_utc;
   p.prior_overall_high_water_balance=MathMax(ledger.high_water_balance,ledger.initial_capital);
   const double weight=EEA_SetupRiskWeight(setup);
   p.base_risk_fraction=limits.per_trade_fraction*weight;
   p.per_trade_cap_money=MathMin(limits.per_trade_fraction*weight*ledger.initial_capital,loss_room);
   p.portfolio_cap_money=limits.total_open_fraction*ledger.initial_capital;
   p.portfolio_cap_includes_existing=true;
   // EEA_ProposeStructuralLevels puts the stop one buffer beyond the invalidation: one tick
   // inside the first trade's stop plus a one-tick buffer lands exactly on that stop.
   p.invalidation_price=(t2 ? t.entry_price : position.sl)+t.direction*tick;
   p.stop_buffer_price=tick;
   p.target_price=t.initial_tp;
   p.max_spread_points=2.0*median_spread;
   p.max_spread_stop_fraction=0.25;
   p.minimum_net_rr=EEA_S06B_ADD_MIN_RR;
   p.cost_per_lot_money=cost;
   p.cost_estimated=!learned;
   p.currency_cap_money=limits.currency_exposure_fraction*ledger.initial_capital;
   p.max_correlated_trades=limits.max_correlated_trades;
   p.min_margin_level_percent=limits.min_margin_level_percent;
   p.htf_risk_modifier=1.0;
   reason="S06B_ADD_PLAN_READY";
   return true;
  }

// The add as a candidate of its own: TRIGGERED now, expires after this bar.
void EEA_S06BAddEngine(const EEA_StrategyCandidateRuntime &strategy,const int index,const EEA_ManagedTrade &t,
                       const string add_id,EEA_S02Engine &e,const string setup="S06B")
  {
   e=strategy.engines[index];
   e.state=EEA_S02_TRIGGERED;
   e.direction=t.direction;
   e.zone_low=0.0; e.zone_high=0.0;
   e.candidate.candidate_id=add_id;
   e.candidate.setup_id=setup;
   e.candidate.direction=(t.direction==1 ? "LONG" : "SHORT");
   e.candidate.state="TRIGGERED";
   e.candidate.detected_at_utc=TimeGMT();
   e.candidate.triggered_at_utc=TimeGMT();
   e.candidate.expires_after_bars=1;
   e.candidate.age_after_trigger_bars=0;
   e.candidate.canonical_symbol=e.canonical_symbol;
   e.candidate.timeframe=e.timeframe;
   e.candidate.config_version=e.config_version;
   e.candidate.reason_code=setup+"_PYRAMID_ADD";
  }

void EEA_S06BPyramidAudit(CAuditLog &audit,const EEA_ManagedTrade &t,const string add_id,const string event_type,
                          const string reason,const string config_version)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),t.intent.canonical_symbol,add_id,"",t.state,"OK");
   event.config_version=config_version;
   EEAEvent_AddReason(event,reason);
   event.details_json="{\"first_candidate\":\""+EEA_JsonEscape(t.intent.candidate_id)+
      "\",\"add_candidate\":\""+EEA_JsonEscape(add_id)+"\",\"direction\":"+IntegerToString(t.direction)+
      ",\"first_entry\":"+DoubleToString(t.entry_price,8)+",\"first_sl\":"+DoubleToString(t.initial_sl,8)+
      ",\"first_tp\":"+DoubleToString(t.initial_tp,8)+",\"mfe_r\":"+DoubleToString(t.mfe_r,3)+
      ",\"reason\":\""+EEA_JsonEscape(reason)+"\"}";
   audit.Append(event,"EA_S06B_PYRAMID");
  }

// One pass after the entry pass: at most one add per timer.
bool EEA_S06BPyramidOnTimer(EEA_ControlledLiveRuntimeState &state,const EEA_ControlledLiveConfig &config,const EEA_StrategyCandidateRuntime &strategy,
                            const EEA_ObserverRuntimeContext &observer,const EEA_ExecutionControllerState &controller,
                            const bool controller_allows_market,CAuditLog &audit,const EEA_RiskLedger &ledger,
                            EEA_PendingRuntime &pending,EEA_LiveSessionRuntime &session,
                            EEA_TradeManagerRuntime &trades,const EEA_NewsRuntime &news)
  {
   if(!g_s06b_pyramid_live && !g_t2_pyramid_live) { g_s06b_pyramid_reason="PYRAMID_OFF"; return true; }
   if(!config.enabled || !config.armed) { g_s06b_pyramid_reason="CONTROLLED_LIVE_NOT_ARMED"; return true; }
   if(state.recovery_blocked) { g_s06b_pyramid_reason="EXECUTION_UNKNOWN_RECOVERY_REQUIRED"; return false; }
   if(!strategy.enabled || observer.status.runtime_state!="OBSERVING")
     { g_s06b_pyramid_reason="CONTROLLED_LIVE_RUNTIME_BLOCKED"; return false; }
   if(pending.entries_blocked) { g_s06b_pyramid_reason=pending.reason; return false; }
   if(!controller_allows_market || !EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT()))
     { g_s06b_pyramid_reason="CONTROLLED_LIVE_CONTROLLER_BLOCKED"; return false; }
   if(!session.present) { g_s06b_pyramid_reason="S06B_ADD_NEEDS_LIVE_SESSION"; return false; }
   for(int k=0;k<trades.count;k++)
     {
      if(!trades.items[k].active || trades.items[k].position_id=="") continue;
      EEA_ManagedTrade t=trades.items[k];
      const bool s06=(t.intent.setup_id=="S06B" && g_s06b_pyramid_live);
      const bool t2=(t.intent.setup_id=="T2" && g_t2_pyramid_live);
      if((!s06 && !t2) || t.add_candidate!="" || EEA_S06BIsAddCandidate(t.intent.candidate_id) ||
         t.exit_request!="" || (s06 && !t.be_done)) continue;
      const string setup=t.intent.setup_id;
      const string profile=(t2 ? "POSITION" : "SWING");
      const string add_id=t.intent.candidate_id+EEA_S06B_ADD_SUFFIX;
      if(EEA_TradeManagerHasCandidate(trades,add_id)) continue;
      const int engine_index=EEA_S06BEngineIndex(strategy,t.intent.canonical_symbol,setup);
      if(engine_index<0 || EEA_StrategyRuntimeEngineMode(strategy,engine_index)!=EEA_S04_MODE_LIVE)
        { g_s06b_pyramid_reason=setup+"_NOT_LIVE"; continue; }
      datetime bar_time=0;
      if(!EEA_S06BAddBarReady(t,t2 ? EEA_T2_ADD_AT_R : EEA_S06B_ADD_AT_R,bar_time)) { g_s06b_pyramid_reason=setup+"_ADD_WAIT_1R_CLOSE"; continue; }
      const int prow=EEA_TradeManagerFindPosition(t,observer.reconciliation);
      if(prow<0) continue;
      const EEA_RuntimePositionRow position=observer.reconciliation.positions[prow];
      const int row=EEA_ObserverRuntimeIndexOf(observer,t.intent.canonical_symbol);
      if(row<0 || row>=ArraySize(observer.symbol_specs) || observer.broker_symbols[row]=="")
        { g_s06b_pyramid_reason="LIVE_SYMBOL_UNRESOLVED"; continue; }
      const string news_block=EEA_NewsEntryBlockFor(news,t.intent.canonical_symbol,"SWING");   // POSITION follows SWING (G40)
      if(news_block!="") { g_s06b_pyramid_reason=news_block; continue; }
      string reason;
      EEA_PolicySettings policy;
      if(!EEA_ControlledLiveResolvePolicy(observer.root,observer.config_version,observer.account,policy,reason))
        { g_s06b_pyramid_reason=reason; continue; }
      const long day_reset=EEA_PragueDailyResetUtc((long)TimeGMT());
      EEA_LiveAuthorizationDecision authorization;
      const bool real_account=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL);
      if(!EEA_LiveSessionAuthorize(session,observer.config_version,observer.account.account_fingerprint,
            observer.account.broker_server,observer.account.account_margin_mode,EEA_PolicySignedId(policy.committed_policy),
            observer.broker_symbols[row],add_id,profile=="POSITION" ? "SWING" : profile,real_account,(long)TimeGMT(),day_reset,
            ledger.initial_capital,EEA_LedgerDailyReference(ledger,policy.committed_policy),observer.account.equity,authorization,reason))
        { g_s06b_pyramid_reason=reason; continue; }
      const string authorization_path=EEA_LiveSessionPath(observer.root);
      EEA_S02Engine engine;
      EEA_S06BAddEngine(strategy,engine_index,t,add_id,engine,setup);
      EEA_ControlledLiveTradePlan plan;
      EEA_DryRunContext current; EEA_DryRunEvidence evidence[]; EEA_RuntimeTradeQuote quote;
      if(!EEA_S06BAddPlan(t,position,observer,observer.symbol_specs[row],policy,ledger,engine.config_version,plan,reason,setup) ||
         !EEA_ControlledLiveApplySessionCap(true,session,ledger,plan,reason) ||
         !EEA_ControlledLiveApplyNewsRisk(news,t.intent.canonical_symbol,"SWING",plan,reason) ||
         !EEA_ControlledLiveBuildRiskContextPlan(config,plan,observer,engine,observer.symbol_specs[row],policy,
                                                 current,evidence,quote,reason))
        { g_s06b_pyramid_reason=reason; continue; }
      EEA_DryRunDecision review; EEA_RiskDecision decision;
      if(!EEA_EvaluateDryRunCandidate(current,evidence,review))
        { g_s06b_pyramid_reason="LIVE_DRY_RUN_"+review.decision_status; continue; }
      EEA_RiskReleaseRecheck recheck; EEA_RiskReleaseRecheckDefaults(recheck);
      recheck.runtime_current=true; recheck.account_reconciled=true; recheck.quote_repriced=true;
      recheck.policy_rechecked=true; recheck.portfolio_reconciled=true; recheck.symbol_spec_unchanged=true;
      recheck.account_id=observer.account.account_fingerprint;
      recheck.reconciliation_fingerprint=observer.reconciliation.snapshot_id;
      recheck.quote_fingerprint=quote.snapshot_id; recheck.portfolio_fingerprint=current.portfolio_snapshot_id;
      recheck.release_reference="controlled-live-"+add_id; recheck.checked_at_utc=TimeGMT();
      recheck.expires_at_utc=(datetime)MathMin((long)recheck.checked_at_utc+config.release_ttl_seconds,
                                               MathMin(observer.account.valid_until_utc,observer.reconciliation.valid_until_utc));
      if(!EEA_RiskDecisionReleaseFromReview(current,review,evidence,observer.account,observer.reconciliation,
                                            recheck,TimeGMT(),decision))
        { g_s06b_pyramid_reason=decision.reason_code; continue; }
      if(!EEA_RiskDecisionStoreWrite(observer.root,decision))
        { g_s06b_pyramid_reason="LIVE_RISK_DECISION_PERSISTENCE_FAILED"; continue; }
      EEA_MarketIntentParameters params; EEA_MarketIntentParametersDefaults(params);
      params.canonical_symbol=current.canonical_symbol; params.setup_version=current.setup_config_version;
      params.risk_policy_snapshot_id="policy-"+IntegerToString(policy.revision);
      params.intent_id=authorization.intent_id; params.correlation_id=authorization.authorization_id;
      params.idempotency_key="entry-"+add_id;
      params.entry_reference=decision.entry_reference; params.price=quote.entry_price;
      params.stop_loss=decision.stop_loss; params.take_profit=decision.take_profit;
      params.order_type=decision.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      params.deviation=config.deviation; params.filling_mode=config.filling_mode; params.magic=config.magic;
      EEA_ExecutionIntent intent; string intent_reason;
      if(!EEA_BuildMarketExecutionIntent(decision,observer.account,observer.reconciliation,observer.symbol_specs[row],
                                         observer.config_version,params,TimeGMT(),intent,intent_reason))
        { g_s06b_pyramid_reason=intent_reason; continue; }
      if(!EEA_ControlledLiveAuditAuthorization(audit,authorization,decision,intent,observer.broker_symbols[row],
                                                setup+"_PYRAMID_ADD"))
        { g_s06b_pyramid_reason="LIVE_AUTHORIZATION_AUDIT_FAILED"; continue; }
      // Marked before sending: whatever the broker answers, this trade never gets a second add.
      trades.items[k].add_candidate=add_id;
      EEA_TradeManagerWrite(observer.root,trades.items[k]);
      EEA_ExecutionResult result;
      EEA_RuntimeStatus execution_status=observer.status;
      execution_status.new_entries_blocked=false;
      bool submitted=EEA_ExecutionSubmit(audit,observer.root,intent,decision,controller,"MARKET_ENTRY",
                                         observer.account,observer.reconciliation,observer.symbol_specs[row],
                                         execution_status,true,authorization,result);
      if(!submitted)
        {
         g_s06b_pyramid_reason=result.reason_code;
         EEA_S06BPyramidAudit(audit,t,add_id,"S06B_PYRAMID_REJECTED",result.reason_code,observer.config_version);
         return false;
        }
      EEA_ExecutionReconcileResult(result,observer.reconciliation,result.request_ticket,"SUBMIT_MARKET",
                                   intent.sl,intent.tp,result.request_ticket_kind);
      // Same recovery rule as a normal entry: an unknown outcome or an unsaved result blocks
      // every further entry until it is reconciled.
      state.recovery_result=result;
      if(!EEA_ExecutionStoreWriteResult(observer.root,result))
        {
         state.recovery_blocked=true;
         g_s06b_pyramid_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";
         return false;
        }
      state.recovery_blocked=(result.confirmation_state=="EXECUTION_UNKNOWN");
      string manage_reason;
      if(EEA_TradeManagerRegister(trades,observer.root,intent,result.request_ticket,result.request_ticket_kind,
                                  profile,t.timeframe,0.0,0.0,authorization_path,manage_reason))
        {
         // research rule2: stop already at break-even, no partial (zone 0: no structure exit).
         for(int j=0;j<trades.count;j++)
            if(trades.items[j].active && trades.items[j].intent.candidate_id==add_id)
              {
               trades.items[j].be_done=true; trades.items[j].partial_done=true;
               trades.items[j].last_reason=setup+"_PYRAMID_ADD";
               EEA_TradeManagerWrite(observer.root,trades.items[j]);
              }
        }
      if(!EEA_LiveSessionRecordEntry(session,observer.root,day_reset,profile=="POSITION" ? "SWING" : profile))
         session.reason="LIVE_SESSION_USAGE_PERSISTENCE_FAILED";
      g_s06b_pyramid_reason="S06B_PYRAMID_"+result.confirmation_state;
      EEA_S06BPyramidAudit(audit,t,add_id,"S06B_PYRAMID_SUBMITTED",result.confirmation_state,observer.config_version);
      return true;
     }
   return true;
  }

#endif
