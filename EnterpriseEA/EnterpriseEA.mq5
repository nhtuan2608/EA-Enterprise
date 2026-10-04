#property strict
#property version   "1.000"
#property description "Observer-first core with an explicitly armed, fail-closed paperless market-live profile."

#include "Core/Config.mqh"
#include "Core/State.mqh"
#include "Core/Events.mqh"
#include "Storage/AtomicWriter.mqh"
#include "Storage/AuditLog.mqh"
#include "Storage/SharedStateStore.mqh"
#include "Storage/PolicySettingsStore.mqh"
#include "Storage/ControllerStateStore.mqh"
#include "Runtime/ObserverRuntime.mqh"
#include "Runtime/ExecutionAdapter.mqh"
#include "Runtime/ExecutionControllerState.mqh"
#include "Runtime/LiveAuthorizationGate.mqh"
#include "Runtime/TradeQuoteAdapter.mqh"
#include "Runtime/SymbolSelectionPanel.mqh"
#include "Risk/RiskDecision.mqh"
#include "Integration/RiskDecisionRelease.mqh"
#include "Runtime/ExecutionIntentBuilder.mqh"
#include "Runtime/StrategyCandidateRuntime.mqh"
#include "Integration/ControlledLiveRuntime.mqh"
// S02 v1: confluence levels drive the strategy runtime; O-04 limits are wired with the risk path (plan step 5).
#include "Market/ConfluenceLevels.mqh"
#include "Risk/RiskLimitsProfile.mqh"
#include "Runtime/AccountAutoProfile.mqh"
#include "Storage/RiskLedgerStore.mqh"
#include "News/NewsReactionRecorder.mqh"

input bool   InpObserverOnly           = true;
input bool   InpExecutionEnabled       = false;
input bool   InpLiveTradeArmed         = false;
input string InpDataRoot               = "EnterpriseEA";
input bool   InpRuntimeEvidenceEnabled = true;
input int    InpRuntimeRefreshSeconds  = 30;
input int    InpHistoryLookbackDays    = 7;
input string InpCanonicalSymbols       = "EURUSD,GBPUSD,XAUUSD,BTCUSD,USDJPY";
input bool   InpShowSymbolPanel        = true;
input int    InpPanelSubWindow         = 0; // OBJPROP_SUBWINDOW is represented by ObjectCreate sub_window.
input bool   InpStrategyRuntimeEnabled=false; // S02 strategy engine (scan setups)
input bool   InpS02UsePrototype        = false; // S02 old prototype (keep false = v1 confluence zones)
input string InpStrategyConfigVersion  = "";
input double InpS02BreakBufferAtr      = 0.0;
input double InpS02AcceptanceBufferAtr = 0.0;
input double InpS02RetestToleranceAtr  = 0.0;
input double InpS02InvalidationBufferAtr=0.0;
input double InpS02HoldBufferAtr        = 0.0;
input int    InpS02MaxBarsToAccept      = 0;
input int    InpS02MaxBarsToRetest      = 0;
input int    InpS02MaxBarsForReaction   = 0;
input int    InpS02CandidateTtlBars     = 0;
input string InpLiveAuthorizationPath  = "";
input int    InpSessionMaxScalpPerDay   = 6;      // session: SCALP (M5) entries per Prague day
input int    InpSessionMaxSwingPerDay   = 2;      // session: SWING (H1) entries per Prague day
input bool   InpSessionAllowRealAccount = false;  // a session on a REAL account needs this set explicitly
input string InpOperatorId              = "operator"; // recorded on session and controller documents
input bool   InpNewsGuardEnabled        = true;   // News Guard: MT5 economic calendar, HIGH impact only
input int    InpNewsScalpBlockBeforeMin = 60;     // News Guard: SCALP blocks new entries this long before
input int    InpNewsSwingBlockBeforeMin = 180;    // News Guard: SWING blocks new entries this long before
input int    InpNewsActiveMin           = 5;      // News Guard: ACTIVE window after the event
input int    InpNewsPostMin             = 15;     // News Guard: POST_NEWS ends, stability check starts
input int    InpNewsMaxNormalizeMin     = 60;     // News Guard: longest wait for a stable market
input int    InpNewsBreakEvenBeforeMin  = 15;     // News Guard: break-even for profitable trades this long before
input double InpNewsBreakEvenMinR       = 0.3;    // News Guard: minimum profit (R) for that break-even
input bool   InpNewsAllowWhenUnknown    = false;  // News Guard: allow entries when the calendar is unreadable
input string InpNewsIgnoreKeywords      = "";     // News Guard: comma list of HIGH event names to ignore (empty = none)
input string InpLiveSetupVersion        = "";
input double InpLiveInitialCapital      = 0.0;
input double InpLiveSafetyBufferMoney   = 0.0;
input double InpLiveBalanceAtDailyReset = 0.0;
input long   InpLiveDailyResetUtc       = 0;
input double InpLiveHighWaterBalance    = 0.0;
input double InpLiveBaseRiskFraction    = 0.0;
input double InpLivePerTradeCapMoney    = 0.0;
input double InpLivePortfolioRemaining  = 0.0;
input double InpLiveMinimumNetRR        = 0.0;
input double InpLiveStopBufferTicks     = 0.0;
input double InpLiveTargetRMultiple     = 0.0;
input double InpLiveMaxSpreadPoints     = 0.0;
input int    InpLiveQuoteFreshnessSec   = 30;
input int    InpLiveReleaseTtlSec       = 20;
input long   InpLiveMagic               = 888888;
input int    InpLiveDeviation           = 20;
input int    InpLiveFillingMode         = 0;

CEAConfig g_config;
CSharedState g_state;
CAuditLog g_audit;
bool g_state_checkpoint_writable=true;
EEA_ObserverRuntimeContext g_runtime;
EEA_StrategyCandidateRuntime g_strategy_runtime;
bool g_strategy_checkpoints_loaded=false;
EEA_ExecutionControllerState g_controller;
EEA_ControllerStateLoadStatus g_controller_load_status=EEA_CONTROLLER_STATE_MISSING;
bool g_controller_allows_market=false;
EEA_ControlledLiveConfig g_live_config;
EEA_ControlledLiveRuntimeState g_live_runtime;

bool EEA_LivePanelAllowed()
  {
   // Tester and optimization are non-live contexts; never expose live
   // controls or observer dashboard surfaces there.
   return MQLInfoInteger(MQL_TESTER)==0 && MQLInfoInteger(MQL_OPTIMIZATION)==0;
  }

void EEA_LoadDurableControllerState()
  {
   EEA_ExecutionControllerStateDefaults(g_controller);
   g_controller_allows_market=false;
   if(!g_runtime.initialized || g_runtime.status.runtime_state!="OBSERVING" ||
      g_runtime.account.account_fingerprint=="" || g_runtime.account.broker_server=="")
     {
      g_controller_load_status=EEA_CONTROLLER_STATE_MISSING;
      return;
     }
   g_controller_load_status=EEA_ControllerStateStoreLoad(
      g_config.data_root+"/current/execution_controller_state.json",
      g_config.config_version,g_runtime.account.account_fingerprint,
      g_runtime.account.broker_server,"MARKET_ENTRY",1,TimeGMT(),g_controller);
   g_controller_allows_market=(g_controller_load_status==EEA_CONTROLLER_STATE_LOADED &&
      EEA_ExecutionControllerAllowsNewRequest(g_controller,"MARKET_ENTRY",TimeGMT()));
  }

EEA_RiskLedger g_risk_ledger;
EEA_PendingRuntime g_pending_runtime;
EEA_LiveSessionRuntime g_live_session;
EEA_TradeManagerRuntime g_trade_manager;
EEA_NewsRuntime g_news;
EEA_NewsReactionRuntime g_news_reaction;
bool g_risk_ledger_loaded=false;
bool g_daily_stats_loaded=false;

// Restores and maintains data that must survive EA removal: per-day realized stats
// for the calendar and the FTMO risk ledger (initial capital, Prague reset balance,
// high-water mark). Broker positions, orders and deals are re-read on every refresh.
void EEA_MaintainDurableState()
  {
   if(!g_runtime.initialized || g_runtime.status.runtime_state!="OBSERVING" ||
      g_runtime.account.account_fingerprint=="" || g_runtime.account.broker_server=="") return;
   string root=g_config.data_root;
   long offset=EEA_SymbolPanelLocalOffsetSeconds();
   if(!g_daily_stats_loaded)
     {
      EEA_DailyStatsLoad(root,g_daily_stats,g_config.config_version,g_runtime.account.account_fingerprint,offset);
      g_daily_stats_loaded=true;
     }
   if(EEA_DailyStatsMerge(g_daily_stats,g_runtime.reconciliation,offset,(long)TimeGMT()) && g_daily_stats.dirty &&
      EEA_DailyStatsWrite(root,g_daily_stats,g_config.config_version,g_runtime.account.account_fingerprint))
      g_daily_stats.dirty=false;
   if(!g_risk_ledger_loaded)
     {
      if(!EEA_RiskLedgerLoad(root,g_config.config_version,g_runtime.account.account_fingerprint,
                             g_runtime.account.broker_server,g_risk_ledger))
        {
         EEA_RiskLedgerDefaults(g_risk_ledger);
         g_risk_ledger.config_version=g_config.config_version;
         g_risk_ledger.account_fingerprint=g_runtime.account.account_fingerprint;
         g_risk_ledger.broker_server=g_runtime.account.broker_server;
        }
      g_risk_ledger_loaded=true;
     }
   // An explicit input always wins; otherwise the first deposit of the account history.
   if(InpLiveInitialCapital>0.0 && g_risk_ledger.initial_capital!=InpLiveInitialCapital)
     {
      g_risk_ledger.initial_capital=InpLiveInitialCapital; g_risk_ledger.initial_capital_source="INPUT";
      g_risk_ledger.high_water_balance=MathMax(g_risk_ledger.high_water_balance,InpLiveInitialCapital);
      g_risk_ledger.last_reset_utc=0;
     }
   if(g_risk_ledger.initial_capital<=0.0)
     {
      double first_deposit=EEA_InitialCapitalFromHistory();
      if(first_deposit<=0.0) return;
      g_risk_ledger.initial_capital=first_deposit; g_risk_ledger.initial_capital_source="HISTORY_FIRST_DEPOSIT";
      g_risk_ledger.high_water_balance=first_deposit;
     }
   string reason;
   if(EEA_RiskLedgerAdvance(g_risk_ledger,g_runtime.reconciliation,g_runtime.account.balance,(long)TimeGMT(),reason))
      EEA_RiskLedgerWrite(root,g_risk_ledger);
  }

// ---------------------------------------------------------------------------
// Session authorization (control center). Signing writes one time-boxed session and
// releases the controller kill switch for the same window; revoking does the reverse.
// Each step is re-checked against live account, policy, ledger and broker state.
// ---------------------------------------------------------------------------
void EEA_LiveSessionReload()
  {
   bool present=false;
   EEA_LiveSessionRuntime fresh; EEA_LiveSessionRuntimeDefaults(fresh);
   fresh.last_action=g_live_session.last_action;
   if(!EEA_LiveSessionLoad(g_config.data_root,fresh.session,present))
     { fresh.present=true; fresh.session.status="INVALID"; fresh.reason="LIVE_SESSION_FILE_INVALID"; }
   else
      fresh.present=present;
   if(!EEA_LiveSessionUsageLoad(g_config.data_root,fresh.usage))
     { fresh.usage_failed=true; fresh.reason="LIVE_SESSION_USAGE_FILE_INVALID"; }
   fresh.loaded=true;
   g_live_session=fresh;
  }

string EEA_LiveSessionStateText(string &reason)
  {
   reason="";
   if(!g_live_session.present) return "NONE";
   if(EEA_LiveSessionActive(g_live_session.session,(long)TimeGMT(),reason))
      return g_live_session.usage_failed ? "INVALID" : "ACTIVE";
   if(reason=="LIVE_SESSION_REVOKED") return "REVOKED";
   if(reason=="LIVE_SESSION_EXPIRED") return "EXPIRED";
   return "INVALID";
  }

bool EEA_LiveSessionAudit(const string event_type,const string reason)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),"","","","",reason=="OK" ? "OK" : "DEGRADED");
   event.config_version=g_config.config_version;
   if(reason!="OK") EEAEvent_AddReason(event,reason);
   event.details_json="{\"session_id\":\""+EEA_JsonEscape(g_live_session.session.session_id)+
      "\",\"operator_id\":\""+EEA_JsonEscape(g_live_session.session.operator_id)+
      "\",\"valid_until_utc\":"+IntegerToString(g_live_session.session.valid_until_utc)+
      ",\"allowed_symbols\":\""+EEA_JsonEscape(g_live_session.session.allowed_symbols)+
      "\",\"risk_policy_id\":\""+EEA_JsonEscape(g_live_session.session.risk_policy_id)+"\"}";
   return g_audit.Append(event,"EA_OPERATOR");
  }

bool EEA_LiveSessionWriteController(const bool kill_active,const long valid_until,const string reference,string &reason)
  {
   string path=g_config.data_root+"/current/execution_controller_state.json";
   EEA_ExecutionControllerState existing; bool exists=false;
   if(!EEA_ControllerStateStoreReadExisting(path,g_config.config_version,g_runtime.account.account_fingerprint,
                                            g_runtime.account.broker_server,existing,exists))
     { reason="CONTROLLER_STATE_UNREADABLE"; return false; }
   EEA_ExecutionControllerState next;
   EEA_ExecutionControllerStateDefaults(next);
   next.kill_active=kill_active;
   next.revision=(exists ? existing.revision : 0)+1;
   next.config_version=g_config.config_version;
   next.account_fingerprint=g_runtime.account.account_fingerprint;
   next.broker_server=g_runtime.account.broker_server;
   next.operator_id=InpOperatorId;
   next.reference=reference;
   next.valid_from_utc=TimeGMT();
   next.valid_until_utc=(datetime)valid_until;
   next.operation_scope=EEA_LIVE_SESSION_SCOPE;
   if(!EEA_ControllerStateStoreWrite(path,next,g_config.config_version,g_runtime.account.account_fingerprint,
                                     g_runtime.account.broker_server,TimeGMT()))
     { reason="CONTROLLER_STATE_WRITE_FAILED"; return false; }
   return true;
  }

bool EEA_LiveSessionSign(const long seconds,string &reason)
  {
   long now=(long)TimeGMT();
   if(!g_runtime.initialized || g_runtime.status.runtime_state!="OBSERVING" ||
      g_runtime.account.account_fingerprint=="" || g_runtime.account.broker_server=="")
     { reason="SESSION_RUNTIME_NOT_OBSERVING"; return false; }
   if(seconds<=0 || seconds>EEA_LIVE_SESSION_MAX_SECONDS) { reason="SESSION_DURATION_INVALID"; return false; }
   if(!EEA_ExecutionControllerOpaqueIdentifierValid(InpOperatorId)) { reason="SESSION_OPERATOR_ID_INVALID"; return false; }
   bool real_account=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL);
   if(real_account && !InpSessionAllowRealAccount) { reason="SESSION_REAL_ACCOUNT_NOT_ALLOWED"; return false; }
   if(InpSessionMaxScalpPerDay<1 || InpSessionMaxScalpPerDay>50 ||
      InpSessionMaxSwingPerDay<1 || InpSessionMaxSwingPerDay>50) { reason="SESSION_ENTRY_LIMIT_INVALID"; return false; }
   if(g_live_runtime.recovery_blocked) { reason="EXECUTION_UNKNOWN_RECOVERY_REQUIRED"; return false; }
   if(g_pending_runtime.entries_blocked) { reason=g_pending_runtime.reason; return false; }
   EEA_PolicySettings policy;
   if(!EEA_ControlledLiveResolvePolicy(g_config.data_root,g_config.config_version,g_runtime.account,policy,reason))
      return false;
   EEA_RiskLimits limits;
   if(!EEA_RiskLimitsForPolicy(policy.committed_policy,limits,reason)) return false;
   if(g_risk_ledger.initial_capital<=0.0) { reason="LIVE_INITIAL_CAPITAL_UNKNOWN"; return false; }
   string symbols="";
   for(int i=0;i<g_runtime.symbol_count;i++)
      if(g_runtime.broker_symbols[i]!="") symbols+=(symbols=="" ? "" : ",")+g_runtime.broker_symbols[i];
   if(symbols=="") { reason="SESSION_NO_RESOLVED_SYMBOLS"; return false; }

   EEA_LiveSession session; EEA_LiveSessionDefaults(session);
   MqlDateTime t; TimeToStruct((datetime)now,t);
   session.session_id=StringFormat("session-%04d%02d%02dT%02d%02d%02dZ",t.year,t.mon,t.day,t.hour,t.min,t.sec);
   session.status="ACTIVE";
   session.operator_id=InpOperatorId;
   session.config_version=g_config.config_version;
   session.account_fingerprint=g_runtime.account.account_fingerprint;
   session.broker_server=g_runtime.account.broker_server;
   session.account_mode=g_runtime.account.account_margin_mode;
   session.risk_policy_id=policy.committed_policy;
   session.build_hash="build-"+IntegerToString((long)__DATETIME__);
   session.allowed_symbols=symbols;
   session.scope=EEA_LIVE_SESSION_SCOPE;
   session.signed_at_utc=now; session.valid_from_utc=now; session.valid_until_utc=now+seconds;
   session.max_risk_per_trade_fraction=limits.per_trade_fraction;
   session.max_daily_loss_fraction=limits.internal_daily_fraction;
   session.max_scalp_entries_per_day=InpSessionMaxScalpPerDay;
   session.max_swing_entries_per_day=InpSessionMaxSwingPerDay;
   session.real_account=real_account;
   if(!EEA_LiveSessionActive(session,now,reason)) return false;
   if(!EEA_LiveSessionWrite(g_config.data_root,session)) { reason="SESSION_PERSISTENCE_FAILED"; return false; }
   if(!EEA_LiveSessionWriteController(false,session.valid_until_utc,session.session_id,reason))
     {
      // Never leave an active session without its controller window.
      session.status="REVOKED"; session.revoked_at_utc=now;
      EEA_LiveSessionWrite(g_config.data_root,session);
      EEA_LiveSessionReload();
      return false;
     }
   EEA_LiveSessionReload();
   EEA_LoadDurableControllerState();
   if(!EEA_LiveSessionAudit("LIVE_SESSION_SIGNED","OK")) { reason="SESSION_AUDIT_FAILED"; return false; }
   reason="SESSION_SIGNED";
   return true;
  }

bool EEA_LiveSessionRevoke(string &reason)
  {
   long now=(long)TimeGMT();
   if(g_runtime.account.account_fingerprint=="" || g_runtime.account.broker_server=="")
     { reason="SESSION_ACCOUNT_UNKNOWN"; return false; }
   bool ok=true;
   if(g_live_session.present && g_live_session.session.session_id!="")
     {
      EEA_LiveSession session=g_live_session.session;
      session.status="REVOKED"; session.revoked_at_utc=now;
      if(!EEA_LiveSessionWrite(g_config.data_root,session)) { ok=false; reason="SESSION_PERSISTENCE_FAILED"; }
     }
   string controller_reason;
   if(!EEA_LiveSessionWriteController(true,now+86400,"revoke-"+IntegerToString(now),controller_reason))
     { ok=false; reason=controller_reason; }
   EEA_LiveSessionReload();
   EEA_LoadDurableControllerState();
   g_pending_runtime.entry_permission_revoked=true;
   EEA_LiveSessionAudit("LIVE_SESSION_REVOKED",ok ? "OK" : reason);
   if(ok) reason="SESSION_REVOKED";
   return ok;
  }

string g_recovery_message="";

// Operator handling of an entry with an unknown outcome (panel Settings > System).
void EEA_RecoveryHandlePanelRequest()
  {
   string request=g_panel_state.recovery_request;
   if(request=="") return;
   g_panel_state.recovery_request="";
   string reason="";
   if(request=="RECHECK")
     {
      EEA_ObserverRuntimeOnTimer(g_runtime,g_audit);
      bool cleared=g_runtime.initialized &&
                   EEA_ControlledLiveReconcileRecovery(g_live_runtime,g_config.data_root,g_runtime.reconciliation,g_audit) &&
                   !g_live_runtime.recovery_blocked;
      reason=cleared ? "Broker confirmed the order: entries resume." :
                       "Broker still shows no matching order or deal ("+g_live_runtime.last_reason+").";
     }
   else if(request=="RESOLVE")
     {
      if(EEA_ControlledLiveResolveRecoveryByOperator(g_live_runtime,g_config.data_root,InpOperatorId,g_audit,reason))
         reason="Resolved by operator "+InpOperatorId+": entries resume.";
      else
         reason="FAILED: "+reason;
     }
   g_recovery_message=reason;
   EEA_SymbolPanelToast(reason,StringFind(reason,"FAILED")==0 ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_OK_COLOR);
  }

void EEA_LiveSessionHandlePanelRequest()
  {
   string request=g_panel_state.session_request;
   if(request=="") return;
   g_panel_state.session_request="";
   string reason="";
   bool ok=false;
   if(request=="SIGN_24H") ok=EEA_LiveSessionSign(86400,reason);
   else if(request=="SIGN_7D") ok=EEA_LiveSessionSign(EEA_LIVE_SESSION_MAX_SECONDS,reason);
   else if(request=="REVOKE") ok=EEA_LiveSessionRevoke(reason);
   g_live_session.last_action=(ok ? "" : "FAILED  ")+reason;
   EEA_SymbolPanelToast(ok ? reason : "FAILED: "+reason,ok ? EEA_PANEL_OK_COLOR : EEA_PANEL_DANGER_COLOR);
  }

string EEA_PanelControllerStatusText(const EEA_ControllerStateLoadStatus status)
  {
   switch(status)
     {
      case EEA_CONTROLLER_STATE_LOADED: return "LOADED";
      case EEA_CONTROLLER_STATE_CORRUPT: return "CORRUPT";
      case EEA_CONTROLLER_STATE_IDENTITY_MISMATCH: return "IDENTITY_MISMATCH";
      case EEA_CONTROLLER_STATE_SCOPE_MISMATCH: return "SCOPE_MISMATCH";
      case EEA_CONTROLLER_STATE_REVISION_ROLLBACK: return "REVISION_ROLLBACK";
      case EEA_CONTROLLER_STATE_STALE: return "STALE";
      default: return "MISSING";
     }
  }

// News Guard facts for the dashboard News tab.
void EEA_PublishNewsView(EEA_SymbolPanelEngineView &view)
  {
   view.news_reason=g_news.reason;
   view.news_last_success_utc=g_news.last_success_utc;
   view.news_policy="SCALP blocks "+IntegerToString(g_news.cfg.scalp_block_before_min)+"m before, SWING "+
      IntegerToString(g_news.cfg.swing_block_before_min/60)+"h"+(g_news.cfg.swing_block_before_min%60>0 ?
      IntegerToString(g_news.cfg.swing_block_before_min%60)+"m" : "")+" before; break-even "+
      IntegerToString(g_news.cfg.be_before_min)+"m before at "+DoubleToString(g_news.cfg.be_min_r,1)+
      "R; unknown calendar: "+(g_news.cfg.allow_when_unknown ? "ALLOW" : "BLOCK")+
      (g_news.cfg.ignore_keywords=="" ? "" : "; ignoring: "+g_news.cfg.ignore_keywords)+
      "; indirect: SWING blocked, SCALP risk x"+DoubleToString(g_news.cfg.indirect_scalp_factor,1);
   long now=(long)TimeGMT();
   view.news_symbol_count=MathMin(g_news.symbol_count,EEA_PANEL_MAX_ROWS);
   for(int i=0;i<view.news_symbol_count;i++)
     {
      view.news_symbol[i]=g_news.symbols[i].canonical;
      view.news_state[i]=g_news.symbols[i].state;
      string detail="";
      if(g_news.symbols[i].event_utc>0)
         detail=g_news.symbols[i].event_label+(g_news.symbols[i].event_utc>now ? "  in " : "  ")+
                EEA_SymbolPanelDurationText(MathAbs(g_news.symbols[i].event_utc-now))+
                (g_news.symbols[i].event_utc>now ? "" : " ago");
      else if(g_news.symbols[i].next_event_utc>0)
         detail="next: "+g_news.symbols[i].next_label+"  in "+EEA_SymbolPanelDurationText(g_news.symbols[i].next_event_utc-now);
      else
         detail=g_news.symbols[i].currencies=="" ? "no calendar currency" : "no HIGH event in 7 days ("+g_news.symbols[i].currencies+")";
      view.news_detail[i]=detail;
     }
   // Focus symbol for reaction statistics: the chart symbol when selected, else the first.
   string focus=g_news.symbol_count>0 ? g_news.symbols[0].canonical : "";
   for(int i=0;i<g_news.symbol_count;i++) if(g_news.symbols[i].broker==_Symbol) focus=g_news.symbols[i].canonical;
   view.news_focus=focus;
   for(int i=0;i<view.news_symbol_count;i++)
      view.news_watch[i]=g_news.symbols[i].watch_event_utc>0 ?
         (g_news.symbols[i].indirect_swing_blocked ? (g_news.symbols[i].indirect_scalp_reduced ?
          "SWING blocked, SCALP x"+DoubleToString(g_news.cfg.indirect_scalp_factor,1)+": " : "SWING blocked: ") : "watch: ")+
         g_news.symbols[i].watch_label+(g_news.symbols[i].watch_event_utc>now ? "  in " : "  ")+
         EEA_SymbolPanelDurationText(MathAbs(g_news.symbols[i].watch_event_utc-now))+
         (g_news.symbols[i].watch_event_utc>now ? "" : " ago") : "";
   view.news_recent_count=g_news_reaction.recent_count;
   for(int i=0;i<g_news_reaction.recent_count && i<3;i++) view.news_recent[i]=g_news_reaction.recent[i];
   view.news_reaction_reason=g_news_reaction.reason;
   view.news_event_count=0;
   for(int i=0;i<g_news.count && view.news_event_count<EEA_PANEL_NEWS_ROWS;i++)
     {
      if(g_news.events[i].time_utc<now-3600) continue;
      int k=view.news_event_count;
      view.news_event_utc[k]=g_news.events[i].time_utc;
      view.news_event_text[k]=g_news.events[i].currency+"  "+g_news.events[i].name;
      view.news_event_values[k]="A "+(g_news.events[i].actual=="" ? "-" : g_news.events[i].actual)+
         "  F "+(g_news.events[i].forecast=="" ? "-" : g_news.events[i].forecast)+
         "  P "+(g_news.events[i].previous=="" ? "-" : g_news.events[i].previous);
      // History of this event on the focus symbol (R3: suggestions are display only).
      EEA_ReactionStats stats;
      if(focus!="" && EEA_NewsReactionStatsFor(g_news_reaction,g_news.events[i].currency,g_news.events[i].name,focus,stats))
         view.news_event_stats[k]=focus+" n="+IntegerToString(stats.n)+"  15m "+DoubleToString(stats.median_move15_atr,1)+
            "A  sp x"+DoubleToString(stats.median_spread_ratio,1)+"  ~"+DoubleToString(stats.median_recovery_min,0)+"m"+
            (stats.has_suggestion ? "  suggest post "+IntegerToString(stats.suggested_post_min)+"m, pre "+stats.suggested_pre : "");
      else
         view.news_event_stats[k]="";
      view.news_event_count++;
     }
  }

// Publishes read-only engine facts for the control center; the panel never
// derives execution, controller or strategy state on its own.
void EEA_PublishPanelEngineView()
  {
   EEA_SymbolPanelEngineView view;
   EEA_SymbolPanelEngineViewDefaults(view);
   view.observer_only=InpObserverOnly;
   view.execution_enabled=g_live_config.enabled;
   view.live_armed=g_live_config.armed;
   view.controller_status=EEA_PanelControllerStatusText(g_controller_load_status);
   view.controller_kill_active=g_controller.kill_active;
   view.controller_allows_market=g_controller_allows_market;
   view.recovery_blocked=g_live_runtime.recovery_blocked;
   view.live_reason=g_live_runtime.last_reason;
   view.strategy_enabled=g_strategy_runtime.enabled;
   view.strategy_reason=g_strategy_runtime.reason_code;
   view.trade_manager_reason=g_trade_manager.reason;
   EEA_PublishNewsView(view);
   view.recovery_message=g_recovery_message;
   if(g_live_runtime.recovery_blocked)
      view.recovery_detail="intent "+g_live_runtime.recovery_result.intent_id+"  ticket "+
         IntegerToString(g_live_runtime.recovery_result.request_ticket)+" ("+g_live_runtime.recovery_result.request_ticket_kind+
         ")  retcode "+g_live_runtime.recovery_result.request_retcode;
   string session_reason;
   view.session_state=EEA_LiveSessionStateText(session_reason);
   view.session_reason=(g_live_session.usage_failed ? g_live_session.reason : session_reason);
   view.session_id=g_live_session.session.session_id;
   view.session_until_utc=g_live_session.session.valid_until_utc;
   view.session_symbols=g_live_session.session.allowed_symbols;
   view.session_risk_fraction=g_live_session.session.max_risk_per_trade_fraction;
   view.session_daily_loss_fraction=g_live_session.session.max_daily_loss_fraction;
   long day_reset=EEA_PragueDailyResetUtc((long)TimeGMT());
   view.session_max_entries=g_live_session.session.max_scalp_entries_per_day;
   view.session_entries_today=EEA_LiveSessionEntriesToday(g_live_session,day_reset,"SCALP");
   view.session_max_swing_entries=g_live_session.session.max_swing_entries_per_day;
   view.session_swing_entries_today=EEA_LiveSessionEntriesToday(g_live_session,day_reset,"SWING");
   view.session_message=g_live_session.last_action!="" ? g_live_session.last_action :
                        (view.session_state=="ACTIVE" && g_live_session.reason!="LIVE_SESSION_NONE" ? g_live_session.reason : "");
   view.session_real_account=(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL);
   if(g_runtime.initialized && g_runtime.status.runtime_state=="OBSERVING")
     {
      double stress=0.0, floating=0.0; string stress_reason;
      view.active_risk_valid=EEA_ControlledLiveExistingStress(g_runtime,stress,floating,stress_reason);
      view.active_risk_money=stress;
      view.active_risk_capital=g_risk_ledger.initial_capital;
     }
   if(g_strategy_runtime.enabled)
      for(int i=0;i<g_strategy_runtime.symbol_count;i++)
        {
         // One panel row per symbol; v1 shows both profiles, e.g. "SC:ARMED SW:IDLE".
         string symbol=g_strategy_runtime.engines[i].canonical_symbol;
         int row=-1;
         for(int k=0;k<view.setup_count;k++) if(view.setup_symbol[k]==symbol) { row=k; break; }
         if(row<0)
           {
            if(view.setup_count>=EEA_PANEL_MAX_ROWS) continue;
            row=view.setup_count; view.setup_count++;
            view.setup_symbol[row]=symbol; view.setup_state[row]=""; view.setup_detail[row]="";
           }
         string state=g_strategy_runtime.has_candidate[i] ?
            g_strategy_runtime.candidates[i].state+" "+g_strategy_runtime.candidates[i].direction :
            EEA_S02StateName(g_strategy_runtime.engines[i].state);
         if(g_strategy_runtime.zone_mode)
           {
            string tag=(g_strategy_runtime.profile[i]=="SWING" ? "SW" : "SC");
            view.setup_state[row]+=(view.setup_state[row]=="" ? "" : " ")+tag+":"+EEA_S02StateName(g_strategy_runtime.engines[i].state);
            view.setup_detail[row]+=(view.setup_detail[row]=="" ? "" : " | ")+g_strategy_runtime.profile[i]+" "+state+
               " zone "+g_strategy_runtime.zone_text[i]+" HTF "+g_strategy_runtime.htf_structure[i]+
               (g_strategy_runtime.htf_risk_modifier[i]<1.0 ? " risk x"+DoubleToString(g_strategy_runtime.htf_risk_modifier[i],2) : "");
           }
         else
            view.setup_state[row]=state;
        }
   string universe[];
   int count=EEA_NormalizeCanonicalCsv(InpCanonicalSymbols,universe);
   for(int i=0;i<count && i<EEA_PANEL_MAX_ROWS;i++) view.universe[i]=universe[i];
   view.universe_count=count<EEA_PANEL_MAX_ROWS ? count : EEA_PANEL_MAX_ROWS;
   EEA_SymbolPanelSetEngineView(view);
  }

int OnInit()
  {
   if(!EAConfig_LoadDefaults(g_config))
      return INIT_FAILED;
   g_config.observer_only=InpObserverOnly;
   if(InpObserverOnly==false && (!InpExecutionEnabled || !InpLiveTradeArmed))
     {
      Print("INIT_PARAMETERS_INCORRECT: live profile requires InpObserverOnly=false, InpExecutionEnabled=true and InpLiveTradeArmed=true.");
      return INIT_PARAMETERS_INCORRECT;
     }
   EEA_ControlledLiveConfigDefaults(g_live_config);
   EEA_ControlledLiveRuntimeStateDefaults(g_live_runtime);
   g_live_config.enabled=InpExecutionEnabled && !InpObserverOnly;
   g_live_config.armed=InpLiveTradeArmed;
   g_live_config.authorization_path=InpLiveAuthorizationPath;
   g_live_config.setup_version=InpLiveSetupVersion;
   g_live_config.initial_capital=InpLiveInitialCapital;
   g_live_config.safety_buffer_money=InpLiveSafetyBufferMoney;
   g_live_config.balance_at_daily_reset=InpLiveBalanceAtDailyReset;
   g_live_config.daily_reset_at_utc=(datetime)InpLiveDailyResetUtc;
   g_live_config.prior_overall_high_water_balance=InpLiveHighWaterBalance;
   g_live_config.base_risk_fraction=InpLiveBaseRiskFraction;
   g_live_config.per_trade_cap_money=InpLivePerTradeCapMoney;
   g_live_config.portfolio_remaining_money=InpLivePortfolioRemaining;
   g_live_config.minimum_net_rr=InpLiveMinimumNetRR;
   g_live_config.stop_buffer_ticks=InpLiveStopBufferTicks;
   g_live_config.target_r_multiple=InpLiveTargetRMultiple;
   g_live_config.max_spread_points=InpLiveMaxSpreadPoints;
   g_live_config.quote_freshness_seconds=InpLiveQuoteFreshnessSec;
   g_live_config.release_ttl_seconds=InpLiveReleaseTtlSec;
   g_live_config.magic=InpLiveMagic;
   g_live_config.deviation=InpLiveDeviation;
   g_live_config.filling_mode=InpLiveFillingMode;
   g_config.data_root=InpDataRoot;
   if(!EAConfig_Validate(g_config))
     {
      Print("INIT_PARAMETERS_INCORRECT: EAConfig_Validate failed; check InpDataRoot and core configuration.");
      return INIT_PARAMETERS_INCORRECT;
     }
   EEA_EnsureFolder(g_config.data_root);
   EEA_EnsureFolder(g_config.data_root+"/logs");
   EEA_EnsureFolder(g_config.data_root+"/current");
   g_state.schema_version=EEA_SCHEMA_VERSION;
   g_state.config_version=g_config.config_version;
   g_state.source="EA_CORE";
   g_state.data_quality="UNKNOWN";
   g_state.symbol_resolution="UNRESOLVED";
   g_state.policy_status="UNSELECTED";
   g_state.policy.status="UNSELECTED";
   g_state.policy.policy_id="";
   g_state.policy.config_version="";
   g_state.policy.source_url="";
   g_state.policy.policy_timezone="";
   g_state.policy.account_currency="";
   g_state.daily_snapshot.snapshot_id="core-daily-unselected";
   g_state.daily_snapshot.policy_version="";
   g_state.portfolio_snapshot.snapshot_id="core-portfolio-unknown";
   g_state.risk_status="POLICY_DATA_UNKNOWN";
   if(!g_audit.Open(g_config.data_root+"/logs/audit.jsonl"))
      return INIT_FAILED;
   string state_path=g_config.data_root+"/current/shared_state.json";
   EEAStateLoadResult recovery=EEA_StateCheckCheckpoint(state_path,g_config.config_version);
   if(recovery==EEA_STATE_INCOMPATIBLE)
     {
      g_state_checkpoint_writable=false;
      g_state.data_quality="DEGRADED";
      g_state.symbol_resolution="BLOCKED";
      g_state.policy_status="POLICY_DATA_UNKNOWN";
      g_state.policy.status="POLICY_DATA_UNKNOWN";
      g_state.risk_status="POLICY_DATA_UNKNOWN";
     }
   else if(recovery==EEA_STATE_MISSING && !EEA_StateSave(state_path,g_state))
     {
      Print("Unable to persist initial shared-state checkpoint.");
      return INIT_FAILED;
     }
   EEAEvent e;
   string boot_event=(recovery==EEA_STATE_COMPATIBLE ? "STATE_CHECKPOINT_COMPATIBLE" :
                      recovery==EEA_STATE_INCOMPATIBLE ? "STATE_CHECKPOINT_INCOMPATIBLE" : "EA_INITIALIZED");
   EEAEvent_Init(e,boot_event,TimeGMT(),"","","","",g_state.data_quality);
   e.config_version=g_config.config_version;
   string checkpoint_status=(recovery==EEA_STATE_COMPATIBLE ? "COMPATIBLE" :
                             recovery==EEA_STATE_INCOMPATIBLE ? "INCOMPATIBLE" : "MISSING");
   e.details_json="{\"mode\":\"OBSERVER_ONLY\",\"state_checkpoint\":\""+checkpoint_status+
                   "\",\"policy_status\":\""+g_state.policy_status+"\"}";
   EEAEvent_AddReason(e,recovery==EEA_STATE_INCOMPATIBLE ? "STATE_CHECKPOINT_INCOMPATIBLE" : "CORE_FOUNDATION_READY");
   if(!g_audit.Append(e,g_config.source))
      return INIT_FAILED;
   if(InpRuntimeEvidenceEnabled)
     {
      string canonical[];
      int count = EEA_NormalizeCanonicalCsv(InpCanonicalSymbols, canonical);
      if(count <= 0)
        {
         Print("INIT_PARAMETERS_INCORRECT: InpCanonicalSymbols is empty or invalid.");
         return INIT_PARAMETERS_INCORRECT;
        }

      EEA_S02Config strategy_config;
      EEA_S02ResearchSeedConfig(strategy_config);
      strategy_config.config_version=InpStrategyConfigVersion;
      strategy_config.break_buffer_atr=InpS02BreakBufferAtr;
      strategy_config.acceptance_buffer_atr=InpS02AcceptanceBufferAtr;
      strategy_config.retest_tolerance_atr=InpS02RetestToleranceAtr;
      strategy_config.invalidation_buffer_atr=InpS02InvalidationBufferAtr;
      strategy_config.hold_buffer_atr=InpS02HoldBufferAtr;
      strategy_config.max_bars_to_accept=InpS02MaxBarsToAccept;
      strategy_config.max_bars_to_retest=InpS02MaxBarsToRetest;
      strategy_config.max_bars_for_reaction=InpS02MaxBarsForReaction;
      strategy_config.candidate_ttl_bars=InpS02CandidateTtlBars;
      bool strategy_ready=InpS02UsePrototype ?
         EEA_StrategyCandidateRuntimeInit(g_strategy_runtime,canonical,count,
                                          strategy_config,InpStrategyRuntimeEnabled) :
         EEA_StrategyCandidateRuntimeInitV1(g_strategy_runtime,canonical,count,InpStrategyRuntimeEnabled);
      if(!strategy_ready && InpStrategyRuntimeEnabled)
        {
         Print("INIT_PARAMETERS_INCORRECT: strategy runtime configuration invalid: ",
               g_strategy_runtime.reason_code);
         return INIT_PARAMETERS_INCORRECT;
        }

      if(!EEA_ObserverRuntimeInit(g_runtime,g_audit,g_config.data_root,g_config.config_version,
                                  InpRuntimeRefreshSeconds,InpHistoryLookbackDays,
                                  canonical,count))
         {
          g_runtime.initialized=true;
          g_runtime.status.runtime_state="DEGRADED";
          g_runtime.status.reason_code="RUNTIME_INIT_DEGRADED";
          g_runtime.status.new_entries_blocked=true;
          if(!EEA_ObserverRuntimeAuditChecked(g_runtime,g_audit,"RUNTIME_INIT_DEGRADED",g_runtime.status))
             {
              g_runtime.status.runtime_state="BLOCKED";
              g_runtime.status.reason_code="AUDIT_PERSISTENCE_FAILED";
              g_runtime.status.new_entries_blocked=true;
              EEA_RuntimeStoreWriteStatus(g_runtime.root,g_runtime.status,g_runtime.config_version,
                 g_runtime.account.account_fingerprint,g_runtime.reconciliation.observed_at_utc);
             }
         }
       if(!EventSetTimer(InpRuntimeRefreshSeconds)) return INIT_FAILED;
     }
   EEA_LoadDurableControllerState();
   EEA_MaintainDurableState();
   EEA_LiveSessionReload();
   EEA_NewsConfig news_config; EEA_NewsConfigDefaults(news_config);
   news_config.enabled=InpNewsGuardEnabled;
   news_config.scalp_block_before_min=InpNewsScalpBlockBeforeMin;
   news_config.swing_block_before_min=InpNewsSwingBlockBeforeMin;
   news_config.active_min=InpNewsActiveMin; news_config.post_min=InpNewsPostMin;
   news_config.max_normalize_min=InpNewsMaxNormalizeMin;
   news_config.be_before_min=InpNewsBreakEvenBeforeMin; news_config.be_min_r=InpNewsBreakEvenMinR;
   news_config.allow_when_unknown=InpNewsAllowWhenUnknown;
   news_config.ignore_keywords=InpNewsIgnoreKeywords;
   EEA_NewsRuntimeInit(g_news,news_config,g_config.config_version);
   if(g_runtime.initialized)
      EEA_NewsUpdate(g_news,g_audit,g_config.data_root,g_runtime.canonical_symbols,g_runtime.broker_symbols,
                     g_runtime.symbol_count);
   string recovery_reason="";
   if(!EEA_ControlledLiveLoadRecovery(g_live_runtime,g_config.data_root,recovery_reason))
      Print("Execution recovery is fail-closed: ",recovery_reason);
   if(InpStrategyRuntimeEnabled && g_runtime.status.runtime_state=="OBSERVING")
     {
      EEA_StrategyRuntimeConfigurePersistence(g_strategy_runtime,g_config.data_root,
         g_runtime.account.account_fingerprint,g_runtime.account.broker_server);
      // Engines follow the restored selection, then resume from their checkpoints.
      EEA_StrategyRuntimeSyncSymbols(g_strategy_runtime,g_runtime.canonical_symbols,g_runtime.symbol_count,
                                     TimeGMT(),EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS);
      g_strategy_checkpoints_loaded=EEA_StrategyRuntimeLoadCheckpoints(g_strategy_runtime,TimeGMT(),
                                                                       EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS);
      if(!g_strategy_checkpoints_loaded)
        {
         g_strategy_runtime.enabled=false;
         g_strategy_runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINT_LOAD_FAILED";
        }
     }
   if(EEA_LivePanelAllowed() && InpShowSymbolPanel)
     {
      EEA_SymbolPanelInit(0, InpPanelSubWindow);
      EEA_PublishPanelEngineView();
      if(InpRuntimeEvidenceEnabled) EEA_SymbolPanelRefresh(0, g_runtime);
     }
   Print("EnterpriseEA observer runtime initialized without execution authority.");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(EEA_LivePanelAllowed() && InpShowSymbolPanel)
     {
      EEA_SymbolPanelDestroy(0);
     }
   EventKillTimer();
   if(InpRuntimeEvidenceEnabled)
      EEA_ObserverRuntimeShutdown(g_runtime,g_audit);
   if(g_audit.IsOpen())
     {
      EEAEvent e;
      EEAEvent_Init(e,"EA_STOPPED",TimeGMT(),"","","","",g_state.data_quality);
      e.config_version=g_config.config_version;
      e.details_json="{\"mode\":\"OBSERVER_ONLY\"}";
      EEAEvent_AddReason(e,"DEINIT_REASON_"+IntegerToString(reason));
      g_audit.Append(e,g_config.source);
      if(g_state_checkpoint_writable)
         EEA_StateSave(g_config.data_root+"/current/shared_state.json",g_state);
      g_audit.Close();
     }
  }

void OnTick()
  {
   // Strategy scanning, risk release and any market request are timer-owned;
   // OnTick remains free of broker mutation and per-tick file writes.
  }

void OnTimer()
  {
   if(InpRuntimeEvidenceEnabled)
      {
       EEA_ObserverRuntimeOnTimer(g_runtime,g_audit);
       EEA_LoadDurableControllerState();
       EEA_MaintainDurableState();
       if(g_runtime.initialized)
          EEA_NewsUpdate(g_news,g_audit,g_config.data_root,g_runtime.canonical_symbols,g_runtime.broker_symbols,
                         g_runtime.symbol_count);
       if(g_runtime.initialized)
          EEA_ControlledLiveReconcileRecovery(g_live_runtime,g_config.data_root,
                                              g_runtime.reconciliation,g_audit);
       if(InpStrategyRuntimeEnabled && g_runtime.status.runtime_state=="OBSERVING" &&
          g_strategy_runtime.enabled)
         {
          EEA_StrategyRuntimeConfigurePersistence(g_strategy_runtime,g_config.data_root,
             g_runtime.account.account_fingerprint,g_runtime.account.broker_server);
          if(!g_strategy_checkpoints_loaded)
             g_strategy_checkpoints_loaded=EEA_StrategyRuntimeLoadCheckpoints(g_strategy_runtime,TimeGMT(),
                                                                              EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS);
          else
            {
             if(!EEA_StrategyRuntimeSyncSymbols(g_strategy_runtime,g_runtime.canonical_symbols,g_runtime.symbol_count,
                                                TimeGMT(),EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS))
               {
                g_strategy_runtime.enabled=false;
                g_strategy_runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINT_LOAD_FAILED";
               }
             EEA_StrategyRuntimeOnTimer(g_strategy_runtime,g_runtime.canonical_symbols,
                                        g_runtime.broker_symbols,g_runtime.symbol_count);
             EEA_StrategyRuntimeWriteCheckpoints(g_strategy_runtime,TimeGMT());
            }
          // REQ-021: every EA pending order is reconciled and its lifecycle enforced on each
          // timer, before any new entry is considered and even when entries are blocked.
          if(!g_pending_runtime.loaded)
             EEA_PendingRuntimeLoad(g_pending_runtime,g_config.data_root,g_runtime.account.account_fingerprint);
          // A revoked or expired session withdraws entry permission: working EA pending
          // orders are cancelled on their next closed bar (cancel only removes exposure).
          if(!g_live_session.loaded) EEA_LiveSessionReload();
          string session_reason;
          g_pending_runtime.entry_permission_revoked=g_live_session.present &&
             EEA_LiveSessionStateText(session_reason)!="ACTIVE";
          EEA_PendingApplyNews(g_pending_runtime,g_news,g_audit,g_config.data_root);
          EEA_PendingRuntimeUpdate(g_pending_runtime,g_audit,g_config.data_root,g_strategy_runtime,g_runtime,
                                   g_live_config.enabled && g_live_config.armed);
          // REQ-005: manage every EA position (also when entries are blocked). After a
          // revoked or expired session only a profitable position is moved to break-even.
          if(!g_trade_manager.loaded) EEA_TradeManagerLoad(g_trade_manager,g_config.data_root);
          EEA_TradeManagerUpdate(g_trade_manager,g_audit,g_config.data_root,g_runtime,
                                 g_live_config.enabled && g_live_config.armed,
                                 !g_pending_runtime.entry_permission_revoked,g_news);
          EEA_NewsReactionUpdate(g_news_reaction,g_audit,g_config.data_root,g_news,g_trade_manager);
          if(g_live_config.enabled && g_live_config.armed && !g_live_runtime.recovery_blocked)
             EEA_ControlledLiveOnTimer(g_live_runtime,g_live_config,g_strategy_runtime,g_runtime,
                                       g_controller,g_controller_allows_market,g_audit,g_risk_ledger,
                                       g_pending_runtime,g_live_session,g_trade_manager,g_news);
         }
       if(EEA_LivePanelAllowed() && InpShowSymbolPanel)
         {
          EEA_PublishPanelEngineView();
          EEA_SymbolPanelRefresh(0,g_runtime);
          EEA_SymbolPanelRefreshOpenOverlay(0,g_runtime);
         }
      }
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(InpRuntimeEvidenceEnabled)
      EEA_ObserverRuntimeMarkStale(g_runtime,"BROKER_TRANSACTION_OBSERVED",g_audit);
  }

void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
  {
   if(EEA_LivePanelAllowed() && InpShowSymbolPanel)
     {
      EEA_SymbolPanelHandleChartEvent(id, lparam, dparam, sparam, g_runtime, g_audit);
      if(g_panel_state.session_request!="" || g_panel_state.recovery_request!="")
        {
         EEA_LiveSessionHandlePanelRequest();
         EEA_RecoveryHandlePanelRequest();
         EEA_PublishPanelEngineView();
         EEA_SymbolPanelRefreshOpenOverlay(0,g_runtime);
         ChartRedraw(0);
        }
     }
  }

