#ifndef ENTERPRISE_EA_DRILL_RUNTIME_MQH
#define ENTERPRISE_EA_DRILL_RUNTIME_MQH

#include "ControlledLiveRuntime.mqh"

// G66 D1: one live drill entry on the demo account. OFF by default (InpDrillEntry=false, empty nonce).
// When enabled, exactly one candidate "DRILL-<canonical>-<nonce>" (setup DRILL, profile SWING) is built:
// the stop is 1.0 x ATR14 of the closed H1 bars, the target is 1R, the volume is the broker minimum.
// The candidate is sent through the SAME risk pipeline as an entry (see EEA_S06BPyramidOnTimer): live
// session authorization, News Guard, plan, session cap, news risk, risk context, dry-run gate, risk
// release and store, execution intent, authorization audit, execution adapter, reconciliation and
// Trade Manager registration. The adapter is the only place that sends an order. One run per nonce:
// the result is persisted in <root>/current/drill_state.json before the order is sent.

#define EEA_DRILL_STATE_DOCUMENT "drill-state-v1.0.0"
#define EEA_DRILL_SETUP "DRILL"
#define EEA_DRILL_CONFIG_VERSION "drill-v1.0.0"
// 1.0 x ATR: a 0.3 x ATR stop (~3.6 pips on EURUSD) is too tight for the spread rule (spread <= 25% of the stop).
#define EEA_DRILL_STOP_ATR 1.0
#define EEA_DRILL_TARGET_R 1.0
#define EEA_DRILL_ATR_PERIOD 14
#define EEA_DRILL_CAP_FACTOR 1.01          // per-trade cap = risk money of volume_min x 1.01
#define EEA_DRILL_MIN_NET_RR 0.25          // a 1R target after costs; the plumbing is under test, not the edge
#define EEA_DRILL_MAX_ATTEMPTS 20
#define EEA_DRILL_QUOTE_MAX_AGE_SECONDS 180

// Inputs, copied by the shell in OnInit (an include cannot see the inputs).
bool   g_drill_enabled=false;
string g_drill_nonce="";
string g_drill_symbol="EURUSD";
int    g_drill_direction=1;                // +1 buy, -1 sell

// Runtime state (mirror of drill_state.json).
bool   g_drill_loaded=false;
string g_drill_state_nonce="";
string g_drill_state="";                   // WAITING, SUBMITTED, DONE or REJECTED
string g_drill_reason="DRILL_OFF";
string g_drill_candidate_id="";
long   g_drill_ticket=0;
long   g_drill_at_utc=0;
int    g_drill_attempts=0;
string g_drill_done_nonces="";             // comma list of nonces that never run again
bool   g_drill_nonce_invalid_reported=false;

string EEA_DrillStatePath(const string root) { return root+"/current/drill_state.json"; }

string EEA_DrillCandidateId(const string canonical,const string nonce)
  { return "DRILL-"+canonical+"-"+nonce; }

// The nonce becomes part of a candidate id, a file name and a JSON text: letters, digits, '-' and '_' only.
bool EEA_DrillNonceValid(const string nonce)
  {
   const int n=StringLen(nonce);
   if(n<1 || n>32) return false;
   for(int i=0;i<n;i++)
     {
      const ushort c=StringGetCharacter(nonce,i);
      const bool ok=(c>='0' && c<='9') || (c>='A' && c<='Z') || (c>='a' && c<='z') || c=='-' || c=='_';
      if(!ok) return false;
     }
   return true;
  }

bool EEA_DrillNonceDone(const string nonce)
  { return StringFind(","+g_drill_done_nonces+",",","+nonce+",")>=0; }

void EEA_DrillMarkNonceDone(const string nonce)
  {
   if(EEA_DrillNonceDone(nonce)) return;
   g_drill_done_nonces=(g_drill_done_nonces=="" ? nonce : g_drill_done_nonces+","+nonce);
  }

// Transient: the same drill may be tried again on a later timer (news block, spread, market closed, no quote).
// Everything else is final.
bool EEA_DrillReasonTransient(const string reason)
  {
   if(StringFind(reason,"NEWS")==0) return true;
   if(reason=="LIVE_SPREAD_LIMIT_EXCEEDED" || reason=="SPREAD_TOO_WIDE_FOR_STOP" || reason=="DRILL_MARKET_CLOSED") return true;
   if(reason=="LIVE_ENTRY_QUOTE_UNAVAILABLE" || reason=="TRADE_QUOTE_UNAVAILABLE") return true;
   // The cap is sized from one quote and the risk context reads the next tick: a tick in between can
   // push the volume below the minimum for one pass.
   if(reason=="LIVE_VOLUME_BELOW_SYMBOL_MINIMUM") return true;
   return false;
  }

bool EEA_DrillStateWrite(const string root)
  {
   const string json="{\"document_version\":\""+EEA_DRILL_STATE_DOCUMENT+"\",\"nonce\":\""+EEA_JsonEscape(g_drill_state_nonce)+
      "\",\"candidate_id\":\""+EEA_JsonEscape(g_drill_candidate_id)+"\",\"state\":\""+EEA_JsonEscape(g_drill_state)+
      "\",\"reason\":\""+EEA_JsonEscape(g_drill_reason)+"\",\"ticket\":"+IntegerToString(g_drill_ticket)+
      ",\"at_utc\":"+IntegerToString(g_drill_at_utc)+",\"attempts\":"+IntegerToString(g_drill_attempts)+
      ",\"done_nonces\":\""+EEA_JsonEscape(g_drill_done_nonces)+"\"}";
   return EEA_WriteAtomicText(EEA_DrillStatePath(root),json);
  }

void EEA_DrillStateLoad(const string root)
  {
   g_drill_loaded=true;
   string json;
   if(!FileIsExist(EEA_DrillStatePath(root),0) || !EEA_PendingReadText(EEA_DrillStatePath(root),json)) return;
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_DRILL_STATE_DOCUMENT) return;
   g_drill_state_nonce=EEA_RiskLedgerField(json,"nonce");
   g_drill_candidate_id=EEA_RiskLedgerField(json,"candidate_id");
   g_drill_state=EEA_RiskLedgerField(json,"state");
   g_drill_reason=EEA_RiskLedgerField(json,"reason");
   g_drill_ticket=StringToInteger(EEA_RiskLedgerField(json,"ticket"));
   g_drill_at_utc=StringToInteger(EEA_RiskLedgerField(json,"at_utc"));
   g_drill_attempts=(int)StringToInteger(EEA_RiskLedgerField(json,"attempts"));
   g_drill_done_nonces=EEA_RiskLedgerField(json,"done_nonces");
   // A drill that was SUBMITTED or DONE, or whose rejection is final, never runs again.
   if(g_drill_state_nonce!="" &&
      (g_drill_state=="SUBMITTED" || g_drill_state=="DONE" ||
       (g_drill_state=="REJECTED" && (!EEA_DrillReasonTransient(g_drill_reason) || g_drill_attempts>=EEA_DRILL_MAX_ATTEMPTS))))
      EEA_DrillMarkNonceDone(g_drill_state_nonce);
  }

void EEA_DrillAudit(CAuditLog &audit,const string event_type,const string canonical,const string candidate_id,
                    const string reason,const string config_version,const long ticket)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),canonical,candidate_id,"",g_drill_state,"OK");
   event.config_version=config_version;
   EEAEvent_AddReason(event,reason);
   event.details_json="{\"candidate_id\":\""+EEA_JsonEscape(candidate_id)+"\",\"nonce\":\""+EEA_JsonEscape(g_drill_state_nonce)+
      "\",\"reason\":\""+EEA_JsonEscape(reason)+"\",\"ticket\":"+IntegerToString(ticket)+
      ",\"attempts\":"+IntegerToString(g_drill_attempts)+"}";
   audit.Append(event,"EA_DRILL");
  }

// A rejected attempt: transient reasons count towards the retry cap, everything else is final.
void EEA_DrillReject(CAuditLog &audit,const string root,const string canonical,const string reason,const string config_version)
  {
   g_drill_attempts++;
   g_drill_state="REJECTED";
   g_drill_reason=reason;
   g_drill_at_utc=(long)TimeGMT();
   if(!EEA_DrillReasonTransient(reason))
      EEA_DrillMarkNonceDone(g_drill_state_nonce);
   else if(g_drill_attempts>=EEA_DRILL_MAX_ATTEMPTS)
     {
      g_drill_reason="DRILL_RETRY_LIMIT_REACHED_"+reason;
      EEA_DrillMarkNonceDone(g_drill_state_nonce);
     }
   EEA_DrillStateWrite(root);
   EEA_DrillAudit(audit,"DRILL_ENTRY_REJECTED",canonical,g_drill_candidate_id,g_drill_reason,config_version,0);
  }

// ATR14 (simple mean of the true ranges) of the last closed H1 bars, as the strategy runtime computes it.
double EEA_DrillAtrH1(const string broker_symbol)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   if(CopyRates(broker_symbol,PERIOD_H1,1,EEA_DRILL_ATR_PERIOD+1,rates)!=EEA_DRILL_ATR_PERIOD+1) return 0.0;
   return EEA_StrategyRuntimeAtrFromRates(rates,EEA_DRILL_ATR_PERIOD,EEA_DRILL_ATR_PERIOD);
  }

// The drill is a fresh TRIGGERED engine candidate, as the S06B add (no setup engine behind it).
void EEA_DrillEngine(const string canonical,const int direction,const string candidate_id,EEA_S02Engine &e)
  {
   e.canonical_symbol=canonical; e.timeframe="H1"; e.config_version=EEA_DRILL_CONFIG_VERSION;
   e.state=EEA_S02_TRIGGERED; e.direction=direction;
   e.last_processed_bar_utc=0; e.breakout_bar_utc=0; e.key_level=0.0; e.signal_atr=0.0; e.invalidation_price=0.0;
   e.retest_close=0.0; e.zone_low=0.0; e.zone_high=0.0; e.retest_extreme=0.0;
   e.bars_since_break=0; e.bars_since_acceptance=0; e.bars_since_retest=0;
   e.candidate.candidate_id=candidate_id;
   e.candidate.setup_id=EEA_DRILL_SETUP;
   e.candidate.direction=(direction==1 ? "LONG" : "SHORT");
   e.candidate.state="TRIGGERED";
   e.candidate.key_level=0.0; e.candidate.invalidation_price=0.0; e.candidate.zone_low=0.0; e.candidate.zone_high=0.0;
   e.candidate.retest_extreme=0.0;
   e.candidate.detected_at_utc=TimeGMT();
   e.candidate.triggered_at_utc=TimeGMT();
   e.candidate.expires_after_bars=1;
   e.candidate.age_after_trigger_bars=0;
   e.candidate.canonical_symbol=canonical;
   e.candidate.timeframe="H1";
   e.candidate.config_version=EEA_DRILL_CONFIG_VERSION;
   e.candidate.reason_code="DRILL_ENTRY";
  }

// Plan of the drill: stop 1.0 x ATR14(H1) from the current quote, target 1R, and a per-trade cap that
// sizes exactly the broker minimum volume (risk money of volume_min at this stop, times 1.01). The
// weight of the drill is the literal 1.0 here; the shared setup weight table is not involved.
bool EEA_DrillPlan(const EEA_ObserverRuntimeContext &observer,const EEA_RuntimeSymbolSpec &symbol,
                   const EEA_PolicySettings &policy,const EEA_RiskLedger &ledger,const EEA_ControlledLiveConfig &config,
                   const int direction,EEA_ControlledLiveTradePlan &p,string &reason)
  {
   EEA_ControlledLivePlanDefaults(p);
   EEA_RiskLimits limits;
   if(!EEA_RiskLimitsForPolicy(policy.committed_policy,limits,reason)) return false;
   if(ledger.initial_capital<=0.0) { reason="LIVE_INITIAL_CAPITAL_UNKNOWN"; return false; }
   if(ledger.last_reset_utc!=EEA_PragueDailyResetUtc((long)TimeGMT()) || ledger.last_reset_balance<=0.0)
     { reason="LIVE_DAILY_RESET_SNAPSHOT_STALE"; return false; }
   if(symbol.volume_min<=0.0 || symbol.volume_step<=0.0 || symbol.tick_size<=0.0)
     { reason="DRILL_SYMBOL_SPEC_INVALID"; return false; }
   const double atr=EEA_DrillAtrH1(symbol.broker_symbol);
   if(atr<=0.0) { reason="DRILL_ATR_UNAVAILABLE"; return false; }
   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(symbol.broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0)
     { reason="LIVE_ENTRY_QUOTE_UNAVAILABLE"; return false; }
   const double entry=(direction==1 ? tick.ask : tick.bid);
   const double tick_size=symbol.tick_size;
   const double stop_distance=EEA_DRILL_STOP_ATR*atr;
   if(stop_distance<=2.0*tick_size) { reason="DRILL_STOP_DISTANCE_TOO_SMALL"; return false; }
   // EEA_ProposeStructuralLevels puts the stop one buffer beyond the invalidation and rounds it away
   // from the entry: invalidation = wanted stop + one tick, buffer = one tick lands on the wanted stop.
   const double wanted_stop=entry-direction*stop_distance;
   p.invalidation_price=wanted_stop+direction*tick_size;
   p.stop_buffer_price=tick_size;
   EEA_StructuralLevels probe;
   if(!EEA_ProposeStructuralLevels(direction,entry,p.invalidation_price,entry+direction*stop_distance,
                                   p.stop_buffer_price,tick_size,probe))
     { reason="DRILL_LEVELS_INVALID"; return false; }
   p.target_price=entry+direction*EEA_DRILL_TARGET_R*MathAbs(entry-probe.stop_loss);
   // Risk money of the broker minimum volume at this stop (quote loss + round-trip cost), times 1.01.
   EEA_RuntimeTradeQuote unit;
   string quote_reason;
   if(!EEA_ReadRuntimeTradeQuote(observer.account,symbol,direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,entry,
                                 probe.stop_loss,p.target_price,symbol.volume_min,config.quote_freshness_seconds,
                                 unit,quote_reason))
     { reason=quote_reason; return false; }
   const double median_spread=EEA_MedianSpreadPoints(symbol.broker_symbol,EEA_S02_SPREAD_MEDIAN_BARS);
   if(median_spread<=0.0) { reason="LIVE_SPREAD_MEDIAN_UNAVAILABLE"; return false; }
   bool learned=false;
   double cost=2.0*EEA_CommissionPerLotPerSide(observer.reconciliation,symbol.broker_symbol,learned);
   bool known=false;
   const double swap=EEA_SwapMoneyPerLotPerNight(symbol,direction,known);
   if(swap<0.0) cost+=-swap*EEA_S02_SWING_EXPECTED_NIGHTS;
   if(!known) learned=false;
   double loss_room=0.0;
   if(!EEA_ControlledLiveInternalLossRoom(observer,ledger,policy.committed_policy,limits,loss_room,reason)) return false;
   p.setup_version=EEA_DRILL_CONFIG_VERSION;
   p.initial_capital=ledger.initial_capital;
   p.safety_buffer_money=limits.safety_buffer_fraction*ledger.initial_capital;
   p.balance_at_daily_reset=ledger.last_reset_balance;
   p.equity_at_daily_reset=EEA_LedgerDailyReference(ledger,policy.committed_policy);
   p.daily_reset_at_utc=(datetime)ledger.last_reset_utc;
   p.prior_overall_high_water_balance=MathMax(ledger.high_water_balance,ledger.initial_capital);
   p.base_risk_fraction=limits.per_trade_fraction;                       // weight 1.0, only lowered by the cap below
   p.per_trade_cap_money=MathMin(EEA_DRILL_CAP_FACTOR*(unit.projected_loss+cost*symbol.volume_min),loss_room);
   p.portfolio_cap_money=limits.total_open_fraction*ledger.initial_capital;
   p.portfolio_cap_includes_existing=true;
   p.max_spread_points=2.0*median_spread;
   p.max_spread_stop_fraction=0.25;
   p.minimum_net_rr=EEA_DRILL_MIN_NET_RR;
   p.cost_per_lot_money=cost;
   p.cost_estimated=!learned;
   p.currency_cap_money=limits.currency_exposure_fraction*ledger.initial_capital;
   p.max_correlated_trades=limits.max_correlated_trades;
   p.min_margin_level_percent=limits.min_margin_level_percent;
   p.htf_risk_modifier=1.0;
   reason="DRILL_PLAN_READY";
   return true;
  }

bool EEA_DrillSymbolBusy(const EEA_TradeManagerRuntime &trades,const string canonical)
  {
   for(int k=0;k<trades.count;k++)
      if(trades.items[k].active && trades.items[k].intent.canonical_symbol==canonical) return true;
   return false;
  }

// The market is closed (or the feed is stale) when the last tick of the symbol is old.
bool EEA_DrillMarketOpen(const string broker_symbol)
  {
   if(SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_MODE)!=SYMBOL_TRADE_MODE_FULL) return false;
   MqlTick tick; ZeroMemory(tick);
   if(!SymbolInfoTick(broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0) return false;
   return (long)TimeTradeServer()-(long)tick.time<=EEA_DRILL_QUOTE_MAX_AGE_SECONDS;
  }

// One pass after the S06B pyramid pass, under the same guards. At most one attempt per timer.
bool EEA_DrillOnTimer(EEA_ControlledLiveRuntimeState &state,const EEA_ControlledLiveConfig &config,const EEA_StrategyCandidateRuntime &strategy,
                      const EEA_ObserverRuntimeContext &observer,const EEA_ExecutionControllerState &controller,
                      const bool controller_allows_market,CAuditLog &audit,const EEA_RiskLedger &ledger,
                      EEA_PendingRuntime &pending,EEA_LiveSessionRuntime &session,
                      EEA_TradeManagerRuntime &trades,const EEA_NewsRuntime &news)
  {
   if(!g_drill_enabled || g_drill_nonce=="") { g_drill_reason="DRILL_OFF"; return true; }
   if(!config.enabled || !config.armed) { g_drill_reason="CONTROLLED_LIVE_NOT_ARMED"; return true; }
   if(state.recovery_blocked) { g_drill_reason="EXECUTION_UNKNOWN_RECOVERY_REQUIRED"; return false; }
   if(!EEA_DrillNonceValid(g_drill_nonce))
     {
      g_drill_reason="DRILL_NONCE_INVALID";
      g_drill_state_nonce=g_drill_nonce; g_drill_candidate_id=""; g_drill_state="REJECTED";
      if(!g_drill_nonce_invalid_reported)
        {
         g_drill_nonce_invalid_reported=true;
         EEA_DrillAudit(audit,"DRILL_ENTRY_REJECTED","","",g_drill_reason,observer.config_version,0);
        }
      return true;
     }
   const string root=observer.root;
   if(!g_drill_loaded) EEA_DrillStateLoad(root);
   const string canonical=EEA_TrimUpper(g_drill_symbol);
   const string candidate_id=EEA_DrillCandidateId(canonical,g_drill_nonce);
   // Once per nonce: a nonce that was submitted, finished or finally rejected never runs again.
   if(EEA_DrillNonceDone(g_drill_nonce))
     {
      if(g_drill_state_nonce==g_drill_nonce)
         { if(g_drill_state=="REJECTED" && g_drill_reason=="") g_drill_reason="DRILL_DONE"; }
      else
         { g_drill_state_nonce=g_drill_nonce; g_drill_candidate_id=candidate_id; g_drill_state="DONE"; g_drill_reason="DRILL_NONCE_ALREADY_DONE"; g_drill_ticket=0; }
      return true;
     }
   const bool resumed=(g_drill_state_nonce==g_drill_nonce && (g_drill_state=="WAITING" || g_drill_state=="REJECTED"));
   if(!strategy.enabled || observer.status.runtime_state!="OBSERVING")
     { g_drill_reason="CONTROLLED_LIVE_RUNTIME_BLOCKED"; return false; }
   if(pending.entries_blocked) { g_drill_reason=pending.reason; return false; }
   if(!controller_allows_market || !EEA_ExecutionControllerAllowsNewRequest(controller,"MARKET_ENTRY",TimeGMT()))
     { g_drill_reason="CONTROLLED_LIVE_CONTROLLER_BLOCKED"; return false; }
   if(!session.present) { g_drill_reason="DRILL_NEEDS_LIVE_SESSION"; return false; }

   // Queue the drill (first pass of this nonce).
   if(!resumed)
     {
      g_drill_state_nonce=g_drill_nonce; g_drill_candidate_id=candidate_id; g_drill_state="WAITING";
      g_drill_reason="DRILL_QUEUED"; g_drill_ticket=0; g_drill_attempts=0; g_drill_at_utc=(long)TimeGMT();
      if(!EEA_DrillStateWrite(root)) { g_drill_reason="DRILL_STATE_PERSISTENCE_FAILED"; g_drill_state="REJECTED"; return false; }
      EEA_DrillAudit(audit,"DRILL_ENTRY_QUEUED",canonical,candidate_id,"DRILL_QUEUED",observer.config_version,0);
     }
   g_drill_candidate_id=candidate_id;

   // Symbol must be a selected, resolved symbol of the observer.
   const int row=EEA_ObserverRuntimeIndexOf(observer,canonical);
   if(row<0 || row>=ArraySize(observer.symbol_specs) || observer.broker_symbols[row]=="")
     { EEA_DrillReject(audit,root,canonical,"SYMBOL_NOT_SELECTED",observer.config_version); return false; }
   // Arbitration: no managed trade may be open on the symbol.
   if(EEA_DrillSymbolBusy(trades,canonical))
     { EEA_DrillReject(audit,root,canonical,"DRILL_SYMBOL_BUSY",observer.config_version); return false; }
   if(!EEA_DrillMarketOpen(observer.broker_symbols[row]))
     { EEA_DrillReject(audit,root,canonical,"DRILL_MARKET_CLOSED",observer.config_version); return false; }
   const string news_block=EEA_NewsEntryBlockFor(news,canonical,"SWING");
   if(news_block!="")
     { EEA_DrillReject(audit,root,canonical,news_block,observer.config_version); return false; }
   string reason;
   EEA_PolicySettings policy;
   if(!EEA_ControlledLiveResolvePolicy(observer.root,observer.config_version,observer.account,policy,reason))
     { EEA_DrillReject(audit,root,canonical,reason,observer.config_version); return false; }
   const long day_reset=EEA_PragueDailyResetUtc((long)TimeGMT());
   EEA_LiveAuthorizationDecision authorization;
   const bool real_account=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL);
   if(!EEA_LiveSessionAuthorize(session,observer.config_version,observer.account.account_fingerprint,
         observer.account.broker_server,observer.account.account_margin_mode,EEA_PolicySignedId(policy.committed_policy),
         observer.broker_symbols[row],candidate_id,"SWING",real_account,(long)TimeGMT(),day_reset,
         ledger.initial_capital,EEA_LedgerDailyReference(ledger,policy.committed_policy),observer.account.equity,authorization,reason))
     { EEA_DrillReject(audit,root,canonical,reason,observer.config_version); return false; }
   const string authorization_path=EEA_LiveSessionPath(observer.root);
   EEA_S02Engine engine;
   EEA_DrillEngine(canonical,g_drill_direction,candidate_id,engine);
   EEA_ControlledLiveTradePlan plan;
   EEA_DryRunContext current; EEA_DryRunEvidence evidence[]; EEA_RuntimeTradeQuote quote;
   if(!EEA_DrillPlan(observer,observer.symbol_specs[row],policy,ledger,config,g_drill_direction,plan,reason) ||
      !EEA_ControlledLiveApplySessionCap(true,session,ledger,plan,reason) ||
      !EEA_ControlledLiveApplyNewsRisk(news,canonical,"SWING",plan,reason) ||
      !EEA_ControlledLiveBuildRiskContextPlan(config,plan,observer,engine,observer.symbol_specs[row],policy,
                                              current,evidence,quote,reason))
     { EEA_DrillReject(audit,root,canonical,reason,observer.config_version); return false; }
   // Never more than the broker minimum: the sized volume is checked here and again on the intent.
   if(MathAbs(current.sizing.volume-observer.symbol_specs[row].volume_min)>observer.symbol_specs[row].volume_step*0.5)
     { EEA_DrillReject(audit,root,canonical,"DRILL_VOLUME_NOT_MIN",observer.config_version); return false; }
   EEA_DryRunDecision review; EEA_RiskDecision decision;
   if(!EEA_EvaluateDryRunCandidate(current,evidence,review))
     { EEA_DrillReject(audit,root,canonical,"LIVE_DRY_RUN_"+review.decision_status,observer.config_version); return false; }
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
     { EEA_DrillReject(audit,root,canonical,decision.reason_code,observer.config_version); return false; }
   if(!EEA_RiskDecisionStoreWrite(observer.root,decision))
     { EEA_DrillReject(audit,root,canonical,"LIVE_RISK_DECISION_PERSISTENCE_FAILED",observer.config_version); return false; }
   EEA_MarketIntentParameters params; EEA_MarketIntentParametersDefaults(params);
   params.canonical_symbol=current.canonical_symbol; params.setup_version=current.setup_config_version;
   params.risk_policy_snapshot_id="policy-"+IntegerToString(policy.revision);
   params.intent_id=authorization.intent_id; params.correlation_id=authorization.authorization_id;
   params.idempotency_key="entry-"+candidate_id;
   params.entry_reference=decision.entry_reference; params.price=quote.entry_price;
   params.stop_loss=decision.stop_loss; params.take_profit=decision.take_profit;
   params.order_type=decision.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   params.deviation=config.deviation; params.filling_mode=config.filling_mode; params.magic=config.magic;
   EEA_ExecutionIntent intent; string intent_reason;
   if(!EEA_BuildMarketExecutionIntent(decision,observer.account,observer.reconciliation,observer.symbol_specs[row],
                                      observer.config_version,params,TimeGMT(),intent,intent_reason))
     { EEA_DrillReject(audit,root,canonical,intent_reason,observer.config_version); return false; }
   if(MathAbs(intent.volume-observer.symbol_specs[row].volume_min)>observer.symbol_specs[row].volume_step*0.5)
     { EEA_DrillReject(audit,root,canonical,"DRILL_VOLUME_NOT_MIN",observer.config_version); return false; }
   if(!EEA_ControlledLiveAuditAuthorization(audit,authorization,decision,intent,observer.broker_symbols[row],
                                            "DRILL_ENTRY"))
     { EEA_DrillReject(audit,root,canonical,"LIVE_AUTHORIZATION_AUDIT_FAILED",observer.config_version); return false; }
   // Persisted before sending: whatever the broker answers (or if the EA stops), this nonce never sends a second order.
   g_drill_state="SUBMITTED"; g_drill_reason="DRILL_SUBMITTING"; g_drill_at_utc=(long)TimeGMT();
   EEA_DrillMarkNonceDone(g_drill_nonce);
   if(!EEA_DrillStateWrite(root))
     {
      g_drill_state="REJECTED"; g_drill_reason="DRILL_STATE_PERSISTENCE_FAILED";
      EEA_DrillAudit(audit,"DRILL_ENTRY_REJECTED",canonical,candidate_id,g_drill_reason,observer.config_version,0);
      return false;
     }
   EEA_ExecutionResult result;
   EEA_RuntimeStatus execution_status=observer.status;
   execution_status.new_entries_blocked=false;
   bool submitted=EEA_ExecutionSubmit(audit,observer.root,intent,decision,controller,"MARKET_ENTRY",
                                      observer.account,observer.reconciliation,observer.symbol_specs[row],
                                      execution_status,true,authorization,result);
   if(!submitted)
     {
      // The nonce stays used: the idempotency marker may already exist.
      g_drill_state="REJECTED"; g_drill_reason=result.reason_code; g_drill_at_utc=(long)TimeGMT();
      EEA_DrillStateWrite(root);
      EEA_DrillAudit(audit,"DRILL_ENTRY_REJECTED",canonical,candidate_id,result.reason_code,observer.config_version,0);
      return false;
     }
   EEA_ExecutionReconcileResult(result,observer.reconciliation,result.request_ticket,"SUBMIT_MARKET",
                                intent.sl,intent.tp,result.request_ticket_kind);
   // Same recovery rule as a normal entry: an unknown outcome or an unsaved result blocks
   // every further entry until it is reconciled.
   state.recovery_result=result;
   g_drill_ticket=result.request_ticket;
   if(!EEA_ExecutionStoreWriteResult(observer.root,result))
     {
      state.recovery_blocked=true;
      g_drill_reason="EXECUTION_RESULT_PERSISTENCE_FAILED";
      EEA_DrillStateWrite(root);
      return false;
     }
   state.recovery_blocked=(result.confirmation_state=="EXECUTION_UNKNOWN");
   string manage_reason;
   const bool registered=EEA_TradeManagerRegister(trades,observer.root,intent,result.request_ticket,result.request_ticket_kind,
                                                  "SWING","H1",0.0,0.0,authorization_path,manage_reason);
   if(!EEA_LiveSessionRecordEntry(session,observer.root,day_reset,"SWING"))
      session.reason="LIVE_SESSION_USAGE_PERSISTENCE_FAILED";
   g_drill_state=registered ? "DONE" : "SUBMITTED";
   g_drill_reason="DRILL_"+result.confirmation_state+(registered ? "" : "_"+manage_reason);
   g_drill_at_utc=(long)TimeGMT();
   EEA_DrillStateWrite(root);
   EEA_DrillAudit(audit,"DRILL_ENTRY_SUBMITTED",canonical,candidate_id,result.confirmation_state,observer.config_version,g_drill_ticket);
   return true;
  }

#endif
