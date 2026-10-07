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
#include "Integration/CandidateLedger.mqh"
#include "Integration/S06BPyramidRuntime.mqh"
#include "Integration/RemoteModeRuntime.mqh"
#include "Runtime/SetupReplay.mqh"
#include "Runtime/BarExport.mqh"
// S02 v1: confluence levels drive the strategy runtime; O-04 limits are wired with the risk path (plan step 5).
#include "Market/ConfluenceLevels.mqh"
#include "Risk/RiskLimitsProfile.mqh"
#include "Runtime/AccountAutoProfile.mqh"
#include "Storage/RiskLedgerStore.mqh"
#include "News/NewsReactionRecorder.mqh"
#include "Runtime/AiBridgeClient.mqh"
#include "Runtime/CommandQueue.mqh"

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
enum EEA_S02ModeInput { S02_OFF=0, S02_SHADOW=1, S02_LIVE=2 };
input EEA_S02ModeInput InpS02Mode       = S02_SHADOW;   // S02 Break Retest: OFF, SHADOW (record only) or LIVE
enum EEA_S04ModeInput { S04_OFF=0, S04_SHADOW=1, S04_LIVE=2 };
input EEA_S04ModeInput InpS04Mode       = S04_LIVE;   // S04 Failed Break: OFF, SHADOW (record only) or LIVE (trades like S02)
enum EEA_S06ModeInput { S06_OFF=0, S06_SHADOW=1, S06_LIVE=2 };
input EEA_S06ModeInput InpS06Mode       = S06_SHADOW; // S06 Compression Expansion (SWING H1, fixed 3R): OFF, SHADOW or LIVE
enum EEA_S06BModeInput { S06B_OFF=0, S06B_SHADOW=1, S06B_LIVE=2 };
input EEA_S06BModeInput InpS06BMode     = S06B_SHADOW; // S06B (24-bar box, entry on the release bar): OFF, SHADOW or LIVE
enum EEA_T2ModeInput { T2_OFF=0, T2_SHADOW=1, T2_LIVE=2 };
input EEA_T2ModeInput InpT2Mode         = T2_SHADOW;   // G38/G40 T2 (H4 Donchian 60, D1 EMA200 side): LIVE only after shadow matches the research
input string InpT2LiveSymbols           = "XAUUSD,BTCUSD"; // G41: symbols T2 may trade LIVE (trend assets); others stay SHADOW
input string InpT2OnlySymbols           = "XAGUSD,ETHUSD,USOUSD"; // G42: extra trend assets that run T2 only (no S02/S04/S06/S06B)
input bool InpS06BRequireUsdFlow        = true;  // G29: S06B LIVE enters only with the USD flow (logged for every candidate)
input bool InpS06BPyramidLive           = false; // G31: one add at +1R for a LIVE S06B trade (stop at break-even, same target)
enum EEA_ScalpModeInput { SCALP_OFF=0, SCALP_SHADOW=1, SCALP_LIVE=2 };
input EEA_ScalpModeInput InpScalpMode   = SCALP_SHADOW; // G26 cap for every SCALP (M5) engine: OFF, SHADOW or LIVE
input bool   InpSetupReplayEnabled      = true;   // replay S02+S04 on history (measurement only, never trades)
input datetime InpSetupReplayFrom       = D'2026.01.01 00:00'; // setup replay start (UTC)
input bool   InpResearchExportBars      = true;   // G10: export M5/H1/H4 bars to research/ for offline tuning (read-only)
input datetime InpResearchExportFrom    = D'2023.01.01 00:00'; // G10: H1/H4 export start (SWING research on long history)
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
input string InpNewsIgnoreKeywords      = "Initial Jobless Claims,EIA Crude Oil,Lagarde Speech,CB Consumer Confidence,Durable Goods,Home Sales,ISM Non-Manufacturing,S&P Global Services PMI,Note Auction,Money Stock"; // News Guard: HIGH event names to ignore (G30: no larger move than a normal hour)
input datetime InpNewsReplayFrom        = D'2026.01.01 00:00'; // News replay: measure HIGH events from this date (UTC)
input bool   InpSentimentEnabled        = true;   // Market sentiment: reduce-only filter from cross-pair flow
input bool   InpAiEnabled               = true;   // AI Bridge v1 (Level 0/1: reports only, never trades)
input int    InpAiMaxCallsPerDay        = 30;     // AI Bridge: requests per local day
input string InpAiAnalysisProvider      = "claude"; // AI Bridge: provider for news/status analysis (claude or codex)
input string InpAiNewsReviewLocal       = "07:00"; // AI Bridge: daily news data review (operator local time)
input string InpAiDiagnosticsLocal      = "06:30"; // AI Bridge: daily EA diagnostics (operator local time)
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
input double InpScalpRiskWithSwingSameSide = 0.5;  // G18: SCALP risk factor while a same-side SWING is open (1 = off)

CEAConfig g_config;
CSharedState g_state;
CAuditLog g_audit;
bool g_state_checkpoint_writable=true;
EEA_ObserverRuntimeContext g_runtime;
EEA_StrategyCandidateRuntime g_strategy_runtime;
bool g_strategy_checkpoints_loaded=false;
EEA_ReplayRuntime g_setup_replay;
EEA_BarExportRuntime g_bar_export;
EEA_ExecutionControllerState g_controller;
EEA_ControllerStateLoadStatus g_controller_load_status=EEA_CONTROLLER_STATE_MISSING;
bool g_controller_allows_market=false;
EEA_ControlledLiveConfig g_live_config;
EEA_ControlledLiveRuntimeState g_live_runtime;
EEA_CandidateLedger g_candidate_ledger;
EEA_RemoteModeState g_remote_mode;       // G19 operator entry mode (Telegram /pause, /resume)
bool g_remote_loaded=false;
string g_remote_reason="OPERATOR_MODE_NOT_LOADED";
string g_remote_last="";

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
EEA_SentimentRuntime g_sentiment;
EEA_NewsHealthReport g_news_health;
long g_news_health_at=0;
string g_news_health_warn="";

void EEA_NewsHealthUpdate()
  {
   if(!g_news_reaction.loaded || (long)TimeGMT()-g_news_health_at<300) return;
   g_news_health_at=(long)TimeGMT();
   EEA_NewsHealthEvaluate(g_news_reaction,g_news,g_news_health);
   EEA_NewsHealthWrite(g_news_health,g_config.data_root);
   if(g_news_health.warn_signature!=g_news_health_warn)
     {
      g_news_health_warn=g_news_health.warn_signature;
      EEAEvent event;
      EEAEvent_Init(event,"NEWS_DATA_HEALTH",TimeGMT(),"","","",
                    IntegerToString(g_news_health.warn)+" WARN",g_news_health.warn>0 ? "DEGRADED" : "OK");
      event.config_version=g_config.config_version;
      for(int i=0;i<g_news_health.count;i++) if(g_news_health.severity[i]=="WARN") EEAEvent_AddReason(event,g_news_health.code[i]);
      event.details_json="{\"warn\":"+IntegerToString(g_news_health.warn)+",\"info\":"+IntegerToString(g_news_health.info)+"}";
      g_audit.Append(event,"EA_NEWS_HEALTH");
     }
  }
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
   if(StringLen(request)==0) return;   // NULL-safe: an unset string is not ""
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
   if(StringLen(request)==0) return;   // NULL-safe: an unset string is not ""
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

// Market sentiment for the dashboard Market tab and the Overview line.
void EEA_PublishSentimentView(EEA_SymbolPanelEngineView &view)
  {
   view.sentiment_ok=g_sentiment.snap.ok;
   view.sentiment_reason=g_sentiment.snap.reason;
   view.sentiment_regime=g_sentiment.snap.regime;
   view.sentiment_bar_time=g_sentiment.snap.bar_time;
   for(int c=0;c<EEA_SENT_CCY;c++)
     {
      view.sentiment_ccy[c]=EEA_SentCurrency(c);
      view.sentiment_s4[c]=g_sentiment.snap.s4[c];
      view.sentiment_s24[c]=g_sentiment.snap.s24[c];
     }
   view.sentiment_symbol_count=0;
   string strongest="", weakest="";
   double hi=-1e9, lo=1e9;
   for(int c=0;c<EEA_SENT_CCY;c++)
     {
      if(g_sentiment.snap.n[c]==0) continue;
      if(g_sentiment.snap.s4[c]>hi) { hi=g_sentiment.snap.s4[c]; strongest=EEA_SentCurrency(c); }
      if(g_sentiment.snap.s4[c]<lo) { lo=g_sentiment.snap.s4[c]; weakest=EEA_SentCurrency(c); }
     }
   view.sentiment_summary=g_sentiment.snap.ok ?
      "Strong "+strongest+"  weak "+weakest+EEA_SymbolPanelSep()+g_sentiment.snap.regime : g_sentiment.snap.reason;
   for(int i=0;i<g_runtime.symbol_count && view.sentiment_symbol_count<EEA_PANEL_MAX_ROWS;i++)
     {
      string canonical=g_runtime.canonical_symbols[i];
      if(g_runtime.broker_symbols[i]=="") continue;
      EEA_SentAlignment buy, sell;
      EEA_SentimentAlignFor(g_sentiment,canonical,1,"SCALP",buy);
      EEA_SentimentAlignFor(g_sentiment,canonical,-1,"SCALP",sell);
      int k=view.sentiment_symbol_count++;
      view.sentiment_symbol[k]=canonical;
      view.sentiment_symbol_text[k]=buy.ok ?
         "buy "+DoubleToString(buy.a4,2)+"/"+DoubleToString(buy.a24,2)+" "+buy.verdict+"   sell "+
         DoubleToString(sell.a4,2)+"/"+DoubleToString(sell.a24,2)+" "+sell.verdict : buy.reason;
     }
  }

// ---------------------------------------------------------------------------
// AI Bridge v1 (G7): schedule, allowlisted contexts, panel requests. Level 0/1 only:
// AI answers are shown, stored and audited; nothing here changes orders, risk or inputs.
// ---------------------------------------------------------------------------
EEA_AiClient g_ai;
bool g_ai_backfill_done_seen=false;
bool g_ai_backfill_known=false;   // the backfill state seen at start-up is history, not a finish event

int EEA_AiParseHm(const string hm)
  {
   string parts[];
   if(StringSplit(hm,':',parts)!=2) return -1;
   int h=(int)StringToInteger(parts[0]), m=(int)StringToInteger(parts[1]);
   return (h<0 || h>23 || m<0 || m>59) ? -1 : h*60+m;
  }

string EEA_AiNum(const double v,const int digits) { return DoubleToString(v,digits); }

string EEA_AiContextNewsData()
  {
   string json="{\"guard\":{\"scalp_block_before_min\":"+IntegerToString(g_news.cfg.scalp_block_before_min)+
      ",\"swing_block_before_min\":"+IntegerToString(g_news.cfg.swing_block_before_min)+
      ",\"post_min\":"+IntegerToString(g_news.cfg.post_min)+",\"max_normalize_min\":"+IntegerToString(g_news.cfg.max_normalize_min)+
      ",\"be_before_min\":"+IntegerToString(g_news.cfg.be_before_min)+",\"be_min_r\":"+EEA_AiNum(g_news.cfg.be_min_r,2)+
      ",\"unknown\":\""+(g_news.cfg.allow_when_unknown ? "ALLOW" : "BLOCK")+"\",\"indirect\":\"SWING blocked, SCALP x0.5\"}";
   json+=",\"health\":{\"warn\":"+IntegerToString(g_news_health.warn)+",\"info\":"+IntegerToString(g_news_health.info)+",\"findings\":[";
   for(int i=0;i<g_news_health.count;i++)
      json+=(i>0 ? "," : "")+"{\"code\":\""+g_news_health.code[i]+"\",\"severity\":\""+g_news_health.severity[i]+
            "\",\"detail\":\""+EEA_JsonEscape(g_news_health.detail[i])+"\"}";
   json+="]},\"backfill\":{\"cursor_utc\":"+IntegerToString(g_news_reaction.backfill_cursor_utc)+
      ",\"done\":"+(g_news_reaction.backfill_done ? "true" : "false")+",\"records\":"+IntegerToString(g_news_reaction.key_count)+"}";
   // Statistics of the 40 best-sampled cluster x symbol groups.
   string groups[]; int counts[]; int g=0;
   for(int i=0;i<g_news_reaction.summary_count && g<300;i++)
     {
      string name=g_news_reaction.summaries[i].group;
      int found=-1;
      for(int j=0;j<g;j++) if(groups[j]==name) { found=j; break; }
      if(found<0) { ArrayResize(groups,g+1); ArrayResize(counts,g+1); groups[g]=name; counts[g]=1; g++; }
      else counts[found]++;
     }
   json+=",\"groups\":[";
   int written=0;
   bool used[];
   ArrayResize(used,g);
   for(int i=0;i<g;i++) used[i]=false;
   while(written<40)
     {
      int best=-1;
      for(int j=0;j<g;j++) if(!used[j] && (best<0 || counts[j]>counts[best])) best=j;
      if(best<0) break;
      used[best]=true;
      EEA_ReactionStats st;
      EEA_NewsReactionStats(g_news_reaction.summaries,g_news_reaction.summary_count,groups[best],st);
      if(st.n==0) continue;
      json+=(written>0 ? "," : "")+"{\"group\":\""+EEA_JsonEscape(groups[best])+"\",\"n\":"+IntegerToString(st.n)+
            ",\"median_move15_atr\":"+EEA_AiNum(st.median_move15_atr,2)+",\"p80_move60_atr\":"+EEA_AiNum(st.p80_move60_atr,2)+
            ",\"median_spread_ratio\":"+EEA_AiNum(st.median_spread_ratio,2)+",\"median_recovery_min\":"+EEA_AiNum(st.median_recovery_min,0)+
            ",\"reversal_rate\":"+EEA_AiNum(st.reversal_rate,2)+",\"guard_covered_rate\":"+EEA_AiNum(st.covered_rate,2)+
            ",\"median_residual_atr\":"+EEA_AiNum(st.median_residual_atr,2)+
            (st.has_suggestion ? ",\"suggested_post_min\":"+IntegerToString(st.suggested_post_min)+",\"suggested_pre\":\""+st.suggested_pre+"\"" : "")+"}";
      written++;
     }
   json+="]}";
   return json;
  }

string EEA_AiContextNewsEvent()
  {
   string json="{\"records\":[";
   for(int i=0;i<g_news_reaction.live_event_count;i++) json+=(i>0 ? "," : "")+g_news_reaction.live_event_lines[i];
   json+="],\"history\":[";
   for(int i=0;i<g_news_reaction.live_event_count;i++)
     {
      string group=EEA_AiField(g_news_reaction.live_event_lines[i],"group");
      EEA_ReactionStats st;
      EEA_NewsReactionStats(g_news_reaction.summaries,g_news_reaction.summary_count,group,st);
      json+=(i>0 ? "," : "")+"{\"group\":\""+EEA_JsonEscape(group)+"\",\"n\":"+IntegerToString(st.n)+
            ",\"median_move15_atr\":"+EEA_AiNum(st.median_move15_atr,2)+",\"p80_move60_atr\":"+EEA_AiNum(st.p80_move60_atr,2)+
            ",\"median_spread_ratio\":"+EEA_AiNum(st.median_spread_ratio,2)+"}";
     }
   json+="]}";
   return json;
  }

// Last 24 hours of the audit log, summarised: counts per event type and the latest non-OK events.
string EEA_AiContextDiagnostics()
  {
   string path=g_config.data_root+"/logs/audit.jsonl";
   string types[]; int counts[]; int nt=0;
   string issues[]; int ni=0;
   int h=FileOpen(path,FILE_READ|FILE_BIN|FILE_SHARE_READ|FILE_SHARE_WRITE);
   int scanned=0;
   if(h!=INVALID_HANDLE)
     {
      ulong size=FileSize(h);
      ulong from=size>786432 ? size-786432 : 0;
      FileSeek(h,(long)from,SEEK_SET);
      uchar bytes[];
      int len=(int)(size-from);
      ArrayResize(bytes,len);
      int read=(int)FileReadArray(h,bytes,0,len);
      FileClose(h);
      string text=CharArrayToString(bytes,0,read,CP_UTF8);
      string lines[];
      int n=StringSplit(text,'\n',lines);
      string cutoff=EEA_IsoUtc((datetime)((long)TimeGMT()-86400));
      // The first line of a tail read starts mid-record: skip it.
      for(int i=(from>0 ? 1 : 0);i<n;i++)
        {
         string at=EEA_AiField(lines[i],"occurred_at_utc");
         if(at=="" || StringCompare(at,cutoff)<0) continue;
         scanned++;
         string type=EEA_AiField(lines[i],"event_type");
         int f=-1;
         for(int j=0;j<nt;j++) if(types[j]==type) { f=j; break; }
         if(f<0 && nt<60) { ArrayResize(types,nt+1); ArrayResize(counts,nt+1); types[nt]=type; counts[nt]=1; nt++; }
         else if(f>=0) counts[f]++;
         string quality=EEA_AiField(lines[i],"data_quality");
         if(quality!="OK" && quality!="")
           {
            int rc=StringFind(lines[i],"\"reason_codes\":[");
            string reasons=rc>=0 ? StringSubstr(lines[i],rc+16,MathMax(0,StringFind(lines[i],"]",rc)-rc-16)) : "";
            string item="{\"at\":\""+at+"\",\"type\":\""+type+"\",\"symbol\":\""+EEA_AiField(lines[i],"symbol")+
                        "\",\"quality\":\""+quality+"\",\"reasons\":\""+EEA_JsonEscape(StringSubstr(reasons,0,160))+"\"}";
            if(ni<15) { ArrayResize(issues,ni+1); issues[ni++]=item; }
            else { for(int k=0;k<14;k++) issues[k]=issues[k+1]; issues[14]=item; }
           }
        }
     }
   string json="{\"window_hours\":24,\"scanned_events\":"+IntegerToString(scanned)+",\"runtime\":{\"state\":\""+
      g_runtime.status.runtime_state+"\",\"reason\":\""+g_runtime.status.reason_code+"\",\"refresh_failures\":"+
      IntegerToString(g_runtime.status.refresh_failure_count)+"},\"live\":{\"last_reason\":\""+EEA_JsonEscape(g_live_runtime.last_reason)+
      "\",\"recovery_blocked\":"+(g_live_runtime.recovery_blocked ? "true" : "false")+"},\"event_counts\":{";
   for(int i=0;i<nt;i++) json+=(i>0 ? "," : "")+"\""+EEA_JsonEscape(types[i])+"\":"+IntegerToString(counts[i]);
   json+="},\"recent_issues\":[";
   for(int i=0;i<ni;i++) json+=(i>0 ? "," : "")+issues[i];
   json+="]}";
   return json;
  }

string EEA_AiContextStatus()
  {
   string session_reason;
   string json="{\"runtime\":{\"state\":\""+g_runtime.status.runtime_state+"\",\"reason\":\""+g_runtime.status.reason_code+
      "\"},\"session\":\""+EEA_LiveSessionStateText(session_reason)+"\",\"kill_switch\":"+(g_controller.kill_active ? "true" : "false")+
      ",\"positions\":"+IntegerToString(g_runtime.reconciliation.position_count)+",\"orders\":"+IntegerToString(g_runtime.reconciliation.order_count)+
      ",\"equity\":"+EEA_AiNum(g_runtime.account.equity,2)+",\"balance\":"+EEA_AiNum(g_runtime.account.balance,2)+
      ",\"live_last_decision\":\""+EEA_JsonEscape(g_live_runtime.last_reason)+"\",\"trade_manager\":\""+g_trade_manager.reason+
      "\",\"news\":[";
   for(int i=0;i<g_news.symbol_count;i++)
      json+=(i>0 ? "," : "")+"{\"symbol\":\""+g_news.symbols[i].canonical+"\",\"state\":\""+g_news.symbols[i].state+
            "\",\"next\":\""+EEA_JsonEscape(g_news.symbols[i].next_label)+"\",\"next_utc\":"+IntegerToString(g_news.symbols[i].next_event_utc)+
            ",\"indirect_swing_blocked\":"+(g_news.symbols[i].indirect_swing_blocked ? "true" : "false")+"}";
   json+="],\"sentiment\":{\"ok\":"+(g_sentiment.snap.ok ? "true" : "false")+",\"regime\":\""+g_sentiment.snap.regime+"\",\"strength_h4\":{";
   for(int c=0;c<EEA_SENT_CCY;c++) json+=(c>0 ? "," : "")+"\""+EEA_SentCurrency(c)+"\":"+EEA_AiNum(g_sentiment.snap.s4[c],2);
   json+="},\"strength_h24\":{";
   for(int c=0;c<EEA_SENT_CCY;c++) json+=(c>0 ? "," : "")+"\""+EEA_SentCurrency(c)+"\":"+EEA_AiNum(g_sentiment.snap.s24[c],2);
   json+="}},\"setups\":[";
   int w=0;
   for(int i=0;i<g_strategy_runtime.symbol_count;i++)
      json+=(w++>0 ? "," : "")+"{\"symbol\":\""+g_strategy_runtime.engines[i].canonical_symbol+"\",\"setup\":\""+
            g_strategy_runtime.setup[i]+"\",\"profile\":\""+g_strategy_runtime.profile[i]+"\",\"state\":\""+
            EEA_SetupStateName(g_strategy_runtime.setup[i],g_strategy_runtime.engines[i].state)+
            "\",\"htf\":\""+g_strategy_runtime.htf_structure[i]+"\"}";
   json+="],\"news_data_health\":{\"warn\":"+IntegerToString(g_news_health.warn)+",\"info\":"+IntegerToString(g_news_health.info)+"}}";
   return json;
  }

string EEA_AiAnalysisProvider() { return InpAiAnalysisProvider=="codex" ? "codex" : "claude"; }

void EEA_AiEnqueueReport(const string type,string &reason)
  {
   if(type=="NEWS_DATA_REVIEW")
      EEA_AiEnqueue(g_ai,g_audit,type,EEA_AiAnalysisProvider(),"[\"REPORT\",\"WARN\",\"RECOMMEND_WINDOW_CHANGE\",\"RECOMMEND_REVIEW\"]",
                    EEA_AiContextNewsData(),reason);
   else if(type=="EA_DIAGNOSTICS")
      EEA_AiEnqueue(g_ai,g_audit,type,"codex","[\"REPORT\",\"WARN\",\"RECOMMEND_REVIEW\"]",EEA_AiContextDiagnostics(),reason);
   else if(type=="ASK_AI")
      EEA_AiEnqueue(g_ai,g_audit,type,EEA_AiAnalysisProvider(),"[\"REPORT\",\"WARN\",\"RECOMMEND_REVIEW\"]",EEA_AiContextStatus(),reason);
   else if(type=="NEWS_EVENT_REVIEW")
      EEA_AiEnqueue(g_ai,g_audit,type,EEA_AiAnalysisProvider(),"[\"REPORT\",\"WARN\",\"RECOMMEND_REVIEW\"]",EEA_AiContextNewsEvent(),reason);
  }

void EEA_AiTimer()
  {
   if(!g_ai.enabled) return;
   EEA_AiPoll(g_ai,g_audit);
   long day; int minute;
   EEA_AiLocalClock(EEA_SymbolPanelLocalOffsetSeconds(),day,minute);
   EEA_AiRollDay(g_ai,day);
   string reason;
   int review_at=EEA_AiParseHm(InpAiNewsReviewLocal), diag_at=EEA_AiParseHm(InpAiDiagnosticsLocal);
   // A backfill already finished before this start must not queue a review on every re-init
   // (chart changes re-initialise the EA); only a finish observed while running does.
   if(g_news_reaction.loaded && !g_ai_backfill_known)
     { g_ai_backfill_done_seen=g_news_reaction.backfill_done; g_ai_backfill_known=true; }
   bool backfill_finished=(g_news_reaction.backfill_done && !g_ai_backfill_done_seen);
   if(g_news_reaction.loaded) g_ai_backfill_done_seen=g_news_reaction.backfill_done;
   if(g_news_reaction.loaded && ((review_at>=0 && minute>=review_at && g_ai.last_news_review_day!=day) || backfill_finished))
     {
      EEA_AiEnqueueReport("NEWS_DATA_REVIEW",reason);
      if(reason=="AI_REQUEST_QUEUED") { g_ai.last_news_review_day=day; EEA_AiSaveState(g_ai); }
     }
   if(diag_at>=0 && minute>=diag_at && g_ai.last_diag_day!=day)
     {
      EEA_AiEnqueueReport("EA_DIAGNOSTICS",reason);
      if(reason=="AI_REQUEST_QUEUED") { g_ai.last_diag_day=day; EEA_AiSaveState(g_ai); }
     }
   if(g_news_reaction.live_event_count>0 && !EEA_AiHasPending(g_ai,"NEWS_EVENT_REVIEW"))
     {
      EEA_AiEnqueueReport("NEWS_EVENT_REVIEW",reason);
      if(reason=="AI_REQUEST_QUEUED" || reason=="AI_DISABLED") g_news_reaction.live_event_count=0;
     }
  }

void EEA_AiHandlePanelRequest()
  {
   string request=g_panel_state.ai_request;
   if(StringLen(request)==0) return;   // NULL-safe: an unset string is not ""
   g_panel_state.ai_request="";
   string reason;
   EEA_AiEnqueueReport(request=="REVIEW" ? "NEWS_DATA_REVIEW" : "ASK_AI",reason);
   g_ai.last_reason=reason;
   EEA_SymbolPanelToast(reason=="AI_REQUEST_QUEUED" ? "AI request queued" : "AI: "+reason,
                        reason=="AI_REQUEST_QUEUED" ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
  }

void EEA_PublishAiView(EEA_SymbolPanelEngineView &view)
  {
   bool online=EEA_AiBridgeOnline(g_ai);
   view.ai_status=!g_ai.enabled ? "DISABLED" : (EEA_AiCircuitOpen(g_ai) ? "CIRCUIT OPEN" : (online ? "ONLINE" : "BRIDGE OFFLINE"));
   view.ai_status_line="Bridge "+(online ? "online "+g_ai.bridge_version : "offline (start bridge/ai_bridge.py)")+
      EEA_SymbolPanelSep()+"calls today "+IntegerToString(g_ai.calls_today)+"/"+IntegerToString(g_ai.max_calls_per_day)+
      EEA_SymbolPanelSep()+"pending "+IntegerToString(g_ai.pending_count)+EEA_SymbolPanelSep()+g_ai.last_reason;
   long offset=EEA_SymbolPanelLocalOffsetSeconds();
   for(int t=0;t<EEA_AI_TYPES;t++)
     {
      EEA_AiReport r=g_ai.reports[t];
      view.ai_title[t]=EEA_AiType(t)+(r.present ? "  "+TimeToString((datetime)(r.created_at_utc+offset),TIME_DATE|TIME_MINUTES)+
                       "  "+r.provider+(r.status=="ERROR" ? "  ERROR "+r.error : "") : "  no report yet");
      view.ai_line_count[t]=r.present ? r.line_count : 0;
      for(int i=0;i<8;i++) view.ai_lines[t*8+i]=(i<r.line_count ? r.lines[i] : "");
     }
  }

// ---------------------------------------------------------------------------
// Command queue (G8): panel confirmations become commands; the queue is processed
// immediately and on every timer through the same gates as automatic actions.
// ---------------------------------------------------------------------------
string g_command_last="";

// G19: the seven safety facts a /confirm needs before the operator pause is lifted.
void EEA_RemoteResumeEvidenceNow(EEA_RemoteResumeEvidence &e)
  {
   e.account_wide_reconciled=(g_runtime.status.runtime_state=="OBSERVING");
   e.risk_gate_ready=(g_risk_ledger.initial_capital>0.0 && !g_live_runtime.recovery_blocked);
   e.news_gate_ready=true;
   for(int i=0;i<g_runtime.symbol_count;i++)
      if(g_runtime.broker_symbols[i]!="" && EEA_NewsStateFor(g_news,g_runtime.canonical_symbols[i])=="UNKNOWN")
         e.news_gate_ready=false;
   e.broker_connected=(TerminalInfoInteger(TERMINAL_CONNECTED)!=0);
   e.mt5_trade_allowed=(TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)!=0 && MQLInfoInteger(MQL_TRADE_ALLOWED)!=0);
   e.protective_management_ready=(g_trade_manager.loaded && StringFind(g_trade_manager.reason,"FAILED")<0 &&
                                  StringFind(g_trade_manager.reason,"UNREADABLE")<0);
   e.evidence_fresh=((long)TimeGMT()-(long)g_runtime.status.last_timer_at_utc<=120);
  }

// G19: load (or bootstrap) the operator mode for this account, then apply queued remote commands.
void EEA_RemoteModeTimer()
  {
   if(!g_runtime.initialized || g_runtime.account.account_fingerprint=="") return;
   if(!g_remote_loaded || g_remote_mode.account_id!=g_runtime.account.account_fingerprint)
     {
      EEA_RemoteModeLoad(g_remote_mode,g_config.data_root,g_runtime.account.account_fingerprint,g_config.config_version,
                         g_audit,g_remote_reason);
      g_remote_loaded=true;
     }
   EEA_RemoteResumeEvidence evidence;
   EEA_RemoteResumeEvidenceNow(evidence);
   EEA_RemoteModeProcessInbox(g_remote_mode,g_config.data_root,evidence,g_audit,g_remote_last);
  }

// Entries stay blocked until the mode is known (fail closed) and while the operator paused them.
bool EEA_RemoteEntriesPaused() { return !g_remote_loaded || g_remote_mode.operator_paused; }

void EEA_CommandProcessNow()
  {
   if(!g_runtime.initialized || !g_trade_manager.loaded) return;
   EEA_CommandProcessQueue(g_trade_manager,g_pending_runtime,g_audit,g_config.data_root,g_runtime,
                           g_live_config.enabled && g_live_config.armed,g_command_last);
  }

void EEA_CommandHandlePanelRequest()
  {
   if(StringLen(g_panel_state.cmd_request_action)==0) return;
   EEA_Command c; EEA_CommandDefaults(c);
   const long now=(long)TimeGMT();
   c.id="cmd-"+IntegerToString(now)+"-"+IntegerToString(MathRand());
   c.source="PANEL"; c.action=g_panel_state.cmd_request_action; c.ticket_kind=g_panel_state.cmd_request_kind;
   c.ticket=g_panel_state.cmd_request_ticket; c.expected_volume=g_panel_state.cmd_request_volume;
   c.expected_sl=g_panel_state.cmd_request_sl; c.partial_fraction=g_panel_state.cmd_request_fraction;
   c.issued_at_utc=now; c.expires_at_utc=now+EEA_CMD_TTL_SECONDS;
   c.account_fingerprint=g_runtime.account.account_fingerprint; c.config_version=g_config.config_version;
   c.operator_id=InpOperatorId;
   g_panel_state.cmd_request_action="";
   if(!EEA_WriteAtomicText(EEA_CommandDir(g_config.data_root)+"/"+c.id+".json",EEA_CommandToJson(c)))
     { g_command_last=c.action+" FAILED: COMMAND_QUEUE_WRITE_FAILED"; EEA_SymbolPanelToast(g_command_last,EEA_PANEL_DANGER_COLOR); return; }
   EEAEvent event;
   EEAEvent_Init(event,"COMMAND_QUEUED",TimeGMT(),"",c.id,"","QUEUED","OK");
   event.config_version=g_config.config_version;
   event.details_json="{\"action\":\""+c.action+"\",\"ticket\":"+IntegerToString(c.ticket)+",\"source\":\"PANEL\"}";
   g_audit.Append(event,"EA_COMMAND");
   EEA_CommandProcessNow();
   EEA_SymbolPanelToast(g_command_last,StringFind(g_command_last,"APPLIED")>=0 ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
  }

// Which positions and pending orders the EA owns (C1), for the Trades tab.
void EEA_PublishCommandView(EEA_SymbolPanelEngineView &view)
  {
   view.cmd_armed=g_live_config.enabled && g_live_config.armed;
   view.cmd_last=g_command_last;
   view.ea_position_count=0;
   for(int i=0;i<g_trade_manager.count && view.ea_position_count<32;i++)
      if(g_trade_manager.items[i].active && g_trade_manager.items[i].position_ticket>0)
        {
         view.ea_position_ticket[view.ea_position_count]=g_trade_manager.items[i].position_ticket;
         view.ea_position_profile[view.ea_position_count]=g_trade_manager.items[i].profile;
         view.ea_position_count++;
        }
   view.ea_order_count=0;
   for(int i=0;i<g_pending_runtime.count && view.ea_order_count<16;i++)
      if(g_pending_runtime.items[i].active &&
         (g_pending_runtime.items[i].state.status=="WORKING" || g_pending_runtime.items[i].state.status=="PARTIAL"))
        {
         view.ea_order_ticket[view.ea_order_count]=StringToInteger(g_pending_runtime.items[i].state.order_ticket);
         view.ea_order_count++;
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
   view.news_health_line=g_news_health_at==0 ? "Data health: pending" :
      "Data health: "+IntegerToString(g_news_health.warn)+" WARN, "+IntegerToString(g_news_health.info)+" INFO"+
      (g_news_health.count>0 ? "  "+g_news_health.code[0]+" "+g_news_health.detail[0] : "");
   view.news_health_warn=g_news_health.warn;
   view.news_event_count=0;
   int focus_index=EEA_NewsSymbolIndex(g_news,focus);
   string focus_currencies=focus_index>=0 ? g_news.symbols[focus_index].currencies : "";
   for(int i=0;i<g_news.count && view.news_event_count<EEA_PANEL_NEWS_ROWS;i++)
     {
      if(g_news.events[i].time_utc<now-3600) continue;
      // Events released at the same time form one row (one cluster, one price path).
      if(i>0 && g_news.events[i-1].time_utc==g_news.events[i].time_utc && view.news_event_count>0 &&
         view.news_event_utc[view.news_event_count-1]==g_news.events[i].time_utc) continue;
      int same=0;
      string labels[]; int label_count=0;
      for(int j=i;j<g_news.count && g_news.events[j].time_utc==g_news.events[i].time_utc;j++)
        {
         same++;
         if(EEA_NewsAffects(focus_currencies,g_news.events[j].currency) ||
            EEA_NewsIndirectAffects(focus_currencies,g_news.events[j].currency,g_news.events[j].sector))
           { ArrayResize(labels,label_count+1); labels[label_count++]=g_news.events[j].currency+" "+g_news.events[j].name; }
        }
      string cluster=EEA_NewsClusterLabel(labels,label_count);
      int k=view.news_event_count;
      view.news_event_utc[k]=g_news.events[i].time_utc;
      view.news_event_text[k]=g_news.events[i].currency+"  "+g_news.events[i].name+(same>1 ? "  +"+IntegerToString(same-1) : "");
      view.news_event_values[k]="A "+(g_news.events[i].actual=="" ? "-" : g_news.events[i].actual)+
         "  F "+(g_news.events[i].forecast=="" ? "-" : g_news.events[i].forecast)+
         "  P "+(g_news.events[i].previous=="" ? "-" : g_news.events[i].previous);
      // History of this event on the focus symbol (R3: suggestions are display only).
      EEA_ReactionStats stats;
      if(focus!="" && cluster!="" && EEA_NewsReactionStatsForCluster(g_news_reaction,cluster,focus,stats))
         view.news_event_stats[k]=focus+" n="+IntegerToString(stats.n)+"  15m "+DoubleToString(stats.median_move15_atr,1)+
            "A  sp x"+DoubleToString(stats.median_spread_ratio,1)+"  ~"+DoubleToString(stats.median_recovery_min,0)+"m"+
            (stats.replay_n>0 ? "  guard cov "+DoubleToString(stats.covered_rate*100.0,0)+"%" : "")+
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
   view.operator_paused=EEA_RemoteEntriesPaused();
   view.operator_mode_reason=g_remote_loaded ? g_remote_last : g_remote_reason;
   view.controller_status=EEA_PanelControllerStatusText(g_controller_load_status);
   view.controller_kill_active=g_controller.kill_active;
   view.controller_allows_market=g_controller_allows_market;
   view.recovery_blocked=g_live_runtime.recovery_blocked;
   view.live_reason=g_live_runtime.last_reason;
   view.strategy_enabled=g_strategy_runtime.enabled;
   view.strategy_reason=g_strategy_runtime.reason_code;
   if(g_strategy_runtime.zone_mode)
      view.strategy_reason+=" | S02 "+EEA_SetupModeName(g_strategy_runtime.s02_mode)+
                            " | S04 "+EEA_SetupModeName(g_strategy_runtime.s04_mode)+
                            " | S06 "+EEA_SetupModeName(g_strategy_runtime.s06_mode)+
                            " | S06B "+EEA_SetupModeName(g_strategy_runtime.s06b_mode)+
                            " | SCALP max "+EEA_SetupModeName(g_strategy_runtime.scalp_mode)+
                            " | "+EEA_SetupReplayStatus(g_setup_replay);
   view.trade_manager_reason=g_trade_manager.reason;
   EEA_PublishNewsView(view);
   EEA_PublishSentimentView(view);
   EEA_PublishAiView(view);
   EEA_PublishCommandView(view);
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
         const string setup=g_strategy_runtime.setup[i];
         const string state_name=EEA_SetupStateName(setup,g_strategy_runtime.engines[i].state);
         string state=g_strategy_runtime.has_candidate[i] ?
            g_strategy_runtime.candidates[i].state+" "+g_strategy_runtime.candidates[i].direction : state_name;
         if(g_strategy_runtime.zone_mode)
           {
            // e.g. "SC:ARMED SW:IDLE S04-SC:RETURNED"; idle S04/S06 engines are left out of the row.
            string tag=(setup=="S02" ? "" : setup+"-")+(g_strategy_runtime.profile[i]=="SWING" ? "SW" : "SC");
            if(setup=="S02" || g_strategy_runtime.engines[i].state!=EEA_S02_IDLE)
               view.setup_state[row]+=(view.setup_state[row]=="" ? "" : " ")+tag+":"+state_name;
            view.setup_detail[row]+=(view.setup_detail[row]=="" ? "" : " | ")+setup+" "+g_strategy_runtime.profile[i]+" "+state+
               " zone "+g_strategy_runtime.zone_text[i]+" HTF "+g_strategy_runtime.htf_structure[i]+
               (g_strategy_runtime.htf_risk_modifier[i]<1.0 ? " risk x"+DoubleToString(g_strategy_runtime.htf_risk_modifier[i],2) : "");
           }
         else
            view.setup_state[row]=state;
        }
   string universe[];
   int count=EEA_UniverseSymbols(universe);
   for(int i=0;i<count && i<EEA_PANEL_MAX_ROWS;i++) view.universe[i]=universe[i];
   view.universe_count=count<EEA_PANEL_MAX_ROWS ? count : EEA_PANEL_MAX_ROWS;
   EEA_SymbolPanelSetEngineView(view);
  }

// G42: the EA universe is InpCanonicalSymbols plus, while T2 is not OFF, the T2-only trend assets
// (InpT2OnlySymbols). Those get a T2 engine only; every other setup keeps to InpCanonicalSymbols.
int EEA_UniverseSymbols(string &out[])
  {
   int n=EEA_NormalizeCanonicalCsv(InpCanonicalSymbols,out);
   if(n<=0 || InpT2Mode==T2_OFF || InpT2OnlySymbols=="") return n;
   string extra[];
   const int m=EEA_NormalizeCanonicalCsv(InpT2OnlySymbols,extra);
   for(int k=0;k<m;k++)
     {
      bool known=false;
      for(int i=0;i<n;i++) if(out[i]==extra[k]) { known=true; break; }
      if(known || n>=EEA_RUNTIME_MAX_SYMBOLS) continue;
      ArrayResize(out,n+1);
      out[n++]=extra[k];
     }
   return n;
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
   EEA_CandidateLedgerInit(g_candidate_ledger);
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
   g_live_config.scalp_risk_with_swing_same_side=MathMax(0.0,MathMin(1.0,InpScalpRiskWithSwingSameSide));
   EEA_UsdFlowInit(g_usd_flow);
   g_s06b_require_usd_flow=InpS06BRequireUsdFlow;
   g_s06b_pyramid_live=InpS06BPyramidLive;
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
      int count = EEA_UniverseSymbols(canonical);
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
         EEA_StrategyCandidateRuntimeInitV1(g_strategy_runtime,canonical,count,InpStrategyRuntimeEnabled,(int)InpS04Mode,
                                            (int)InpS02Mode,(int)InpS06Mode,(int)InpS06BMode,(int)InpScalpMode,
                                            (int)InpT2Mode,InpT2OnlySymbols);
      g_strategy_runtime.t2_live_symbols=InpT2LiveSymbols;   // G41: after the init, which resets the runtime
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
   EEA_SentConfig sentiment_config; EEA_SentConfigDefaults(sentiment_config);
   sentiment_config.enabled=InpSentimentEnabled;
   EEA_SentimentRuntimeInit(g_sentiment,sentiment_config);
   EEA_AiClientInit(g_ai,g_config.data_root,InpAiEnabled,InpAiMaxCallsPerDay);
   EEA_SetupReplayInit(g_setup_replay,g_config.data_root,InpSetupReplayEnabled && InpStrategyRuntimeEnabled &&
                       !InpS02UsePrototype,(long)InpSetupReplayFrom);
   EEA_BarExportInit(g_bar_export,g_config.data_root,InpResearchExportBars,(long)InpSetupReplayFrom,
                     (long)InpResearchExportFrom);
   if(g_runtime.initialized) EEA_SentimentUpdate(g_sentiment,g_config.data_root);
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

// G40: one small file with what the EA would do now (inputs, session, modes), so an operator or a
// script can audit live readiness without looking at the chart. Written at most every 30 seconds.
datetime g_live_status_written=0;
string EEA_LiveStatusPair(const string key,const string value,const bool quoted)
  {
   const string q="\"";
   return q+key+q+":"+(quoted ? q+EEA_JsonEscape(value)+q : value);
  }

void EEA_WriteLiveStatus()
  {
   const datetime now=TimeGMT();
   if(now-g_live_status_written<30) return;
   g_live_status_written=now;
   string session_reason;
   const string session=EEA_LiveSessionStateText(session_reason);
   const bool armed=g_live_config.enabled && g_live_config.armed;
   string modes="{"+EEA_LiveStatusPair("S02",EEA_SetupModeName((int)InpS02Mode),true)+","+
                EEA_LiveStatusPair("S04",EEA_SetupModeName((int)InpS04Mode),true)+","+
                EEA_LiveStatusPair("S06",EEA_SetupModeName((int)InpS06Mode),true)+","+
                EEA_LiveStatusPair("S06B",EEA_SetupModeName((int)InpS06BMode),true)+","+
                EEA_LiveStatusPair("SCALP_CAP",EEA_SetupModeName((int)InpScalpMode),true)+","+
                EEA_LiveStatusPair("T2",EEA_SetupModeName((int)InpT2Mode),true)+"}";
   string json="{"+EEA_LiveStatusPair("document_version","live-status-v1.0.0",true)+","+
      EEA_LiveStatusPair("written_at_utc",IntegerToString((long)now),false)+","+
      EEA_LiveStatusPair("execution_enabled",InpExecutionEnabled ? "true" : "false",false)+","+
      EEA_LiveStatusPair("observer_only",InpObserverOnly ? "true" : "false",false)+","+
      EEA_LiveStatusPair("live_trade_armed",InpLiveTradeArmed ? "true" : "false",false)+","+
      EEA_LiveStatusPair("live_path_armed",armed ? "true" : "false",false)+","+
      EEA_LiveStatusPair("session",session,true)+","+
      EEA_LiveStatusPair("operator_paused",EEA_RemoteEntriesPaused() ? "true" : "false",false)+","+
      EEA_LiveStatusPair("recovery_blocked",g_live_runtime.recovery_blocked ? "true" : "false",false)+","+
      EEA_LiveStatusPair("last_reason",g_live_runtime.last_reason,true)+","+
      EEA_LiveStatusPair("modes",modes,false)+","+
      EEA_LiveStatusPair("s06b_pyramid_live",g_s06b_pyramid_live ? "true" : "false",false)+","+
      EEA_LiveStatusPair("s06b_require_usd_flow",g_s06b_require_usd_flow ? "true" : "false",false)+"}";
   EEA_WriteAtomicText(g_config.data_root+"/current/live_status.json",json);
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
       if(g_runtime.initialized) EEA_SentimentUpdate(g_sentiment,g_config.data_root);
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
          EEA_CommandProcessNow();
          EEA_NewsReactionUpdate(g_news_reaction,g_audit,g_config.data_root,g_news,g_trade_manager,(long)InpNewsReplayFrom);
          EEA_NewsHealthUpdate();
          EEA_AiTimer();
          // G29: USD flow at the last closed H1 bar, for the S06B filter and every candidate log.
          EEA_UsdFlowUpdateFromObserver(g_usd_flow,g_runtime);
          // SHADOW setups record would-be trades; the replay measures S02/S04 on history.
          EEA_S04ShadowOnTimer(g_live_runtime,g_strategy_runtime,g_runtime,g_risk_ledger,g_news,g_sentiment,
                               g_trade_manager,g_pending_runtime,g_audit);
          EEA_SetupReplayUpdate(g_setup_replay,g_runtime.canonical_symbols,g_runtime.broker_symbols,g_runtime.symbol_count);
          // G11: the sentiment reference pairs are exported too (H1) for the per-news replay.
          string ref_canonical[], ref_broker[];
          ArrayResize(ref_canonical,g_sentiment.count); ArrayResize(ref_broker,g_sentiment.count);
          for(int r=0;r<g_sentiment.count;r++) { ref_canonical[r]=g_sentiment.pairs[r].canonical; ref_broker[r]=g_sentiment.brokers[r]; }
          EEA_BarExportUpdate(g_bar_export,g_runtime.canonical_symbols,g_runtime.broker_symbols,g_runtime.symbol_count,
                              ref_canonical,ref_broker,g_sentiment.count);
          EEA_RemoteModeTimer();
          EEA_WriteLiveStatus();
          if(g_live_config.enabled && g_live_config.armed && !g_live_runtime.recovery_blocked)
            {
             // REQ-019 / O-12: an operator pause blocks new entries only; management keeps running.
             if(EEA_RemoteEntriesPaused())
                g_live_runtime.last_reason="OPERATOR_PAUSED_ENTRIES";
             else
               {
                EEA_ControlledLiveOnTimer(g_live_runtime,g_live_config,g_strategy_runtime,g_runtime,
                                          g_controller,g_controller_allows_market,g_audit,g_risk_ledger,
                                          g_pending_runtime,g_live_session,g_trade_manager,g_news,g_sentiment);
                // G31: one add for a LIVE S06B trade at +1R (OFF unless InpS06BPyramidLive).
                if(!g_live_runtime.recovery_blocked)
                   EEA_S06BPyramidOnTimer(g_live_runtime,g_live_config,g_strategy_runtime,g_runtime,g_controller,
                                          g_controller_allows_market,g_audit,g_risk_ledger,g_pending_runtime,
                                          g_live_session,g_trade_manager,g_news);
               }
            }
          // G18: every candidate's final outcome (entered or why not) for the virtual-result report.
          EEA_CandidateLedgerUpdate(g_candidate_ledger,g_config.data_root,g_strategy_runtime,g_live_runtime,
                                    g_live_config.enabled && g_live_config.armed && !g_live_runtime.recovery_blocked,
                                    g_trade_manager,g_pending_runtime);
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
      // StringLen, not !="": an unset (NULL) string compares unequal to "" in MQL5.
      if(StringLen(g_panel_state.session_request)>0 || StringLen(g_panel_state.recovery_request)>0 ||
         StringLen(g_panel_state.ai_request)>0 || StringLen(g_panel_state.cmd_request_action)>0)
        {
         EEA_CommandHandlePanelRequest();
         EEA_AiHandlePanelRequest();
         EEA_LiveSessionHandlePanelRequest();
         EEA_RecoveryHandlePanelRequest();
         EEA_PublishPanelEngineView();
         EEA_SymbolPanelRefreshOpenOverlay(0,g_runtime);
         ChartRedraw(0);
        }
     }
  }

