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
input bool   InpStrategyRuntimeEnabled=false;
input bool   InpS02UsePrototype        = false; // false: S02 v1 confluence zones (SCALP M5 + SWING H1)
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
   string recovery_reason="";
   if(!EEA_ControlledLiveLoadRecovery(g_live_runtime,g_config.data_root,recovery_reason))
      Print("Execution recovery is fail-closed: ",recovery_reason);
   if(InpStrategyRuntimeEnabled && g_runtime.status.runtime_state=="OBSERVING")
     {
      EEA_StrategyRuntimeConfigurePersistence(g_strategy_runtime,g_config.data_root,
         g_runtime.account.account_fingerprint,g_runtime.account.broker_server);
      g_strategy_checkpoints_loaded=EEA_StrategyRuntimeLoadCheckpoints(g_strategy_runtime,TimeGMT(),3600);
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
       if(g_runtime.initialized)
          EEA_ControlledLiveReconcileRecovery(g_live_runtime,g_config.data_root,
                                              g_runtime.reconciliation,g_audit);
       if(InpStrategyRuntimeEnabled && g_runtime.status.runtime_state=="OBSERVING" &&
          g_strategy_runtime.enabled)
         {
          EEA_StrategyRuntimeConfigurePersistence(g_strategy_runtime,g_config.data_root,
             g_runtime.account.account_fingerprint,g_runtime.account.broker_server);
          if(!g_strategy_checkpoints_loaded)
             g_strategy_checkpoints_loaded=EEA_StrategyRuntimeLoadCheckpoints(g_strategy_runtime,TimeGMT(),3600);
          else
            {
             EEA_StrategyRuntimeOnTimer(g_strategy_runtime,g_runtime.canonical_symbols,
                                        g_runtime.broker_symbols,g_runtime.symbol_count);
             EEA_StrategyRuntimeWriteCheckpoints(g_strategy_runtime,TimeGMT());
            }
          if(g_live_config.enabled && g_live_config.armed && !g_live_runtime.recovery_blocked)
             EEA_ControlledLiveOnTimer(g_live_runtime,g_live_config,g_strategy_runtime,g_runtime,
                                       g_controller,g_controller_allows_market,g_audit);
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
     }
  }

