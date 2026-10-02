#property strict
#property version   "1.000"
#property description "Observer-only core foundation; execution adapter is compile-covered, disabled, and never invoked by lifecycle events."

#include "Core/Config.mqh"
#include "Core/State.mqh"
#include "Core/Events.mqh"
#include "Storage/AtomicWriter.mqh"
#include "Storage/AuditLog.mqh"
#include "Storage/SharedStateStore.mqh"
#include "Storage/PolicySettingsStore.mqh"
#include "Runtime/ObserverRuntime.mqh"
#include "Runtime/ExecutionAdapter.mqh"
#include "Runtime/ExecutionControllerState.mqh"
#include "Runtime/LiveAuthorizationGate.mqh"
#include "Runtime/TradeQuoteAdapter.mqh"
#include "Runtime/SymbolSelectionPanel.mqh"
#include "Risk/RiskDecision.mqh"

input bool   InpObserverOnly           = true;
input bool   InpExecutionEnabled       = false;
input string InpDataRoot               = "EnterpriseEA";
input bool   InpRuntimeEvidenceEnabled = true;
input int    InpRuntimeRefreshSeconds  = 30;
input int    InpHistoryLookbackDays    = 7;
input string InpCanonicalSymbols       = "EURUSD,GBPUSD,XAUUSD";
input bool   InpShowSymbolPanel        = true;
input int    InpPanelSubWindow         = 0; // OBJPROP_SUBWINDOW is represented by ObjectCreate sub_window.

CEAConfig g_config;
CSharedState g_state;
CAuditLog g_audit;
bool g_state_checkpoint_writable=true;
EEA_ObserverRuntimeContext g_runtime;

int OnInit()
  {
   if(!EAConfig_LoadDefaults(g_config))
      return INIT_FAILED;
   g_config.observer_only=InpObserverOnly;
   if(InpObserverOnly==false)
     {
      Print("Execution mode is not implemented in Phase 1; refusing startup.");
      return INIT_FAILED;
     }
   g_config.data_root=InpDataRoot;
   if(!EAConfig_Validate(g_config))
      return INIT_PARAMETERS_INCORRECT;
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
      if(count <= 0) return INIT_PARAMETERS_INCORRECT;

      if(!EEA_ObserverRuntimeInit(g_runtime,g_audit,g_config.data_root,g_config.config_version,
                                  InpRuntimeRefreshSeconds,InpHistoryLookbackDays,
                                  canonical,count))
         {
          g_runtime.initialized=true;
          g_runtime.status.runtime_state="DEGRADED";
          g_runtime.status.reason_code="RUNTIME_INIT_DEGRADED";
          g_runtime.status.new_entries_blocked=true;
          EEA_ObserverRuntimeAudit(g_audit,g_config.config_version,"RUNTIME_INIT_DEGRADED",g_runtime.status);
         }
       if(!EventSetTimer(InpRuntimeRefreshSeconds)) return INIT_FAILED;
     }
   if(InpShowSymbolPanel)
     {
      EEA_SymbolPanelInit(0, InpPanelSubWindow);
      if(InpRuntimeEvidenceEnabled) EEA_SymbolPanelRefresh(0, g_runtime);
     }
   Print("EnterpriseEA observer runtime initialized without execution authority.");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(InpShowSymbolPanel)
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
   // Phase 1 deliberately has no market scan, order API, or per-tick file writes.
  }

void OnTimer()
  {
   if(InpRuntimeEvidenceEnabled)
      {
       EEA_ObserverRuntimeOnTimer(g_runtime,g_audit);
       if(InpShowSymbolPanel)
         {
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
   if(InpShowSymbolPanel)
     {
      EEA_SymbolPanelHandleChartEvent(id, lparam, dparam, sparam, g_runtime, g_audit);
     }
  }

