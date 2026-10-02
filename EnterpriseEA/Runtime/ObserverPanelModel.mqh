#ifndef ENTERPRISE_EA_OBSERVER_PANEL_MODEL_MQH
#define ENTERPRISE_EA_OBSERVER_PANEL_MODEL_MQH

#include "RuntimeEvidence.mqh"

// Runtime/RuntimeEvidence.mqh is the only input contract; this model is pure.
// Context-only rows are displayed with the literal status CONTEXT ONLY.
struct EEA_ObserverPanelMarketRow
  {
   string canonical;
   string broker;
   string status;
   bool   context_only;
   int    digits;
   string trade_mode;
   string freshness_text;
  };

struct EEA_ObserverPanelStatusDefaults
  {
   string runtime_state;
   string reason_code;
   bool   new_entries_blocked;
   string execution_status;
   string live_status;
  };

void EEA_ObserverPanelStatusDefaultsInit(EEA_ObserverPanelStatusDefaults &defaults)
  {
   defaults.runtime_state="BLOCKED";
   defaults.reason_code="RUNTIME_RECONCILIATION_REQUIRED";
   defaults.new_entries_blocked=true;
   defaults.execution_status="EXECUTION_DISABLED";
   defaults.live_status="NOT_AUTHORIZED";
  }

void EEA_ObserverPanelMarketRowDefaults(EEA_ObserverPanelMarketRow &row)
  {
   row.canonical="";
   row.broker="";
   row.status="CONTEXT ONLY";
   row.context_only=false;
   row.digits=0;
   row.trade_mode="UNKNOWN";
   row.freshness_text="UNAVAILABLE";
  }

void EEA_ObserverPanelFormatStatus(const EEA_RuntimeStatus &status,string &formatted)
  {
   string execution_status="EXECUTION_DISABLED";
   string live_status="NOT_AUTHORIZED";
   string blocked=status.new_entries_blocked ? "new_entries_blocked" : "new_entries_allowed";
   formatted=status.runtime_state + " / " + status.reason_code +
             " | " + execution_status + " | " + live_status +
             " | " + blocked +
             " | refresh_sequence=" + IntegerToString(status.refresh_sequence) +
             " | refresh_generation=" + IntegerToString(status.refresh_generation);
  }

#endif
