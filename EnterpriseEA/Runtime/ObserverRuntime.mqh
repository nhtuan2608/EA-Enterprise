#ifndef ENTERPRISE_EA_OBSERVER_RUNTIME_MQH
#define ENTERPRISE_EA_OBSERVER_RUNTIME_MQH

#include "AccountSnapshotAdapter.mqh"
#include "SymbolSpecAdapter.mqh"
#include "BrokerReconciliationAdapter.mqh"
#include "..\Storage\RuntimeEvidenceStore.mqh"
#include "..\Storage\AuditLog.mqh"
#include "..\Market\SymbolRegistry.mqh"

struct EEA_ObserverRuntimeContext
  {
   bool enabled;
   bool initialized;
   bool stale;
   string stale_reason;
   string root;
   string config_version;
   int refresh_seconds;
   int history_lookback_days;
   long last_refresh_utc;
   long previous_deal_watermark;
   string canonical_symbols[EEA_RUNTIME_MAX_SYMBOLS];
   string broker_symbols[EEA_RUNTIME_MAX_SYMBOLS];
   EEA_RuntimeSymbolSpec symbol_specs[EEA_RUNTIME_MAX_SYMBOLS];
   int symbol_count;
   EEA_RuntimeAccountSnapshot account;
   EEA_RuntimeReconciliationSnapshot reconciliation;
   EEA_RuntimeStatus status;
   string symbol_block_reason[EEA_RUNTIME_MAX_SYMBOLS];
   string unresolved_fingerprint;
  };

bool EEA_ObserverRuntimeAudit(CAuditLog &audit,const string config_version,
                              const string event_type,const EEA_RuntimeStatus &status)
  {
   if(!audit.IsOpen()) return false;
   EEAEvent e;
   EEAEvent_Init(e,event_type,TimeGMT(),"","runtime-evidence","",status.runtime_state,
                 status.runtime_state=="OBSERVING" ? "OK" : "DEGRADED");
   e.config_version=config_version;
   EEAEvent_AddReason(e,status.reason_code);
   e.details_json="{\"observer_only\":true,\"new_entries_blocked\":true," +
                  "\"runtime_instance_id\":" + IntegerToString(status.runtime_instance_id) + "," +
                  "\"refresh_sequence\":" + IntegerToString(status.refresh_sequence) + "," +
                  "\"refresh_generation\":" + IntegerToString(status.refresh_generation) + "," +
                  "\"selection_revision\":" + IntegerToString(status.selection_revision) + "}";
   return audit.Append(e,"EA_RUNTIME_OBSERVER");
  }

bool EEA_ObserverRuntimeAuditChecked(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                                     const string event_type,const EEA_RuntimeStatus &status);

bool EEA_ObserverRuntimeIsContextOnly(const string canonical,const string broker)
  {
   string c=EEA_TrimUpper(canonical), b=EEA_TrimUpper(broker);
   return c=="DXY" || c=="USDX" || b=="USDX" || b=="USDX.";
  }

// SYM-02: every symbol resolves on its own. A symbol that cannot be mapped, or
// whose specification cannot be read, keeps an empty broker symbol plus a
// per-symbol reason and is blocked alone; the other symbols keep running.
// Discovery fails only when no tradable symbol resolves at all.
bool EEA_ObserverRuntimeAutoDiscover(const string &canonicals[], string &brokers[], string &reasons[],
                                     const int count, const string server, string &out_reason)
  {
   out_reason = "";
   if(count < 1 || count > EEA_RUNTIME_MAX_SYMBOLS)
     { out_reason="RUNTIME_CONFIGURATION_INVALID"; return false; }
   int total = SymbolsTotal(false);
   EEA_SymbolDiscoveryCandidate candidates[];
   ArrayResize(candidates, total);
   for(int i = 0; i < total; i++)
     {
      string name = SymbolName(i, false);
      candidates[i].name = name;
      candidates[i].tradeable = (SymbolInfoInteger(name, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_DISABLED);
      candidates[i].conversion_only = false;
     }
   EEA_SymbolDiscoveryResult results[];
   EEA_ResolveSymbolsBatch(canonicals, candidates, results);
   ArrayResize(brokers, count);
   ArrayResize(reasons, count);
   for(int i = 0; i < count; i++) { brokers[i]=""; reasons[i]=""; }
   int tradable=0, resolved=0;
   for(int i = 0; i < count; i++)
     {
      if(!results[i].resolved)
        {
         if(EEA_ObserverRuntimeIsContextOnly(canonicals[i],"")) continue;
         tradable++;
         reasons[i]=(results[i].reason_code=="" ? "SYMBOL_UNRESOLVED" : results[i].reason_code);
         continue;
        }
      brokers[i] = results[i].broker_symbol;
      if(EEA_ObserverRuntimeIsContextOnly(canonicals[i],brokers[i])) continue;
      tradable++;
      EEA_RuntimeSymbolSpec spec;
      string spec_reason;
      if(!EEA_ReadRuntimeSymbolSpec(canonicals[i], brokers[i], server, spec, spec_reason))
        {
         brokers[i]="";
         reasons[i]=(spec_reason=="" ? "SYMBOL_SPEC_UNAVAILABLE" : spec_reason);
         continue;
        }
      resolved++;
     }
   if(tradable>0 && resolved==0)
     { out_reason = "SYMBOL_RESOLUTION_FAILED"; return false; }
   if(resolved<tradable) out_reason = "SYMBOL_RESOLUTION_PARTIAL";
   return true;
  }

int EEA_ObserverRuntimeIndexOf(const EEA_ObserverRuntimeContext &ctx,const string canonical)
  {
   for(int i=0;i<ctx.symbol_count;i++)
      if(ctx.canonical_symbols[i]==canonical) return i;
   return -1;
  }

bool EEA_ObserverRuntimeRefresh(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(ctx.status.refresh_in_progress) return false;
   ctx.status.refresh_in_progress = true;
   ctx.status.refresh_attempt_count++;
   ctx.status.refresh_sequence++;
   ctx.status.refresh_generation++;
   ulong start_tick = GetTickCount64();
    string account_refresh_reason="";
    if(!EEA_ReadRuntimeAccount(ctx.config_version,ctx.refresh_seconds*2,ctx.account,account_refresh_reason))
      {
       ctx.status.refresh_in_progress=false;
       ctx.status.refresh_failure_count++;
       ctx.status.consecutive_refresh_failures++;
       ctx.status.runtime_state="DEGRADED";
       ctx.status.reason_code=account_refresh_reason;
       ctx.status.pending_refresh=true;
       ctx.status.new_entries_blocked=true;
       ctx.stale=true;
       ctx.stale_reason=account_refresh_reason;
       EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_ACCOUNT_REFRESH_FAILED",ctx.status);
       return false;
      }
   string reason="";
   EEA_RuntimeStatus prior=ctx.status;
   ctx.status.runtime_state="BLOCKED";
   ctx.status.reason_code="RUNTIME_RECONCILIATION_REQUIRED";
   ctx.status.new_entries_blocked=true;
   bool missing_broker_mapping=false;
   for(int i=0;i<ctx.symbol_count;i++)
      if(!EEA_ObserverRuntimeIsContextOnly(ctx.canonical_symbols[i],ctx.broker_symbols[i]) && ctx.broker_symbols[i]=="") missing_broker_mapping=true;
   if(missing_broker_mapping)
     {
      string rediscover_reason=""; string rediscovered[]; string rediscovered_reasons[];
      if(EEA_ObserverRuntimeAutoDiscover(ctx.canonical_symbols,rediscovered,rediscovered_reasons,ctx.symbol_count,ctx.account.broker_server,rediscover_reason))
         for(int i=0;i<ctx.symbol_count;i++) { ctx.broker_symbols[i]=rediscovered[i]; ctx.symbol_block_reason[i]=rediscovered_reasons[i]; }
      else { ctx.stale=true; ctx.stale_reason="RUNTIME_SYMBOL_DISCOVERY_DEGRADED"; ctx.status.pending_refresh=true; ctx.status.refresh_in_progress=false; ctx.status.refresh_failure_count++; ctx.status.consecutive_refresh_failures++; ctx.status.runtime_state="DEGRADED"; ctx.status.reason_code="RUNTIME_SYMBOL_DISCOVERY_DEGRADED"; ctx.status.new_entries_blocked=true; EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_REFRESH_DEGRADED",ctx.status); return false; }
     }
   int tradable_count=0, resolved_count=0;
   for(int i=0;i<ctx.symbol_count;i++)
     {
      if(EEA_ObserverRuntimeIsContextOnly(ctx.canonical_symbols[i],ctx.broker_symbols[i])) continue;
      tradable_count++;
      if(ctx.broker_symbols[i]=="") continue;
      if(!EEA_ReadRuntimeSymbolSpec(ctx.canonical_symbols[i],ctx.broker_symbols[i],
                                    ctx.account.broker_server,ctx.symbol_specs[i],reason))
        {
         // SYM-02: a missing or unreadable specification blocks this symbol only.
         ctx.symbol_block_reason[i]=(reason=="" ? "SYMBOL_SPEC_UNAVAILABLE" : reason);
         ctx.broker_symbols[i]="";
         ctx.symbol_specs[i].broker_symbol="";
         ctx.symbol_specs[i].trade_mode="BLOCKED";
         continue;
        }
      ctx.symbol_block_reason[i]="";
      resolved_count++;
     }
   if(tradable_count>0 && resolved_count==0)
     {
      ctx.status.refresh_in_progress = false;
      ctx.status.refresh_failure_count++;
      ctx.status.consecutive_refresh_failures++;
      ctx.status.reason_code=(reason=="" ? "SYMBOL_RESOLUTION_FAILED" : reason);
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_REFRESH_FAILED",ctx.status);
      return false;
     }
   if(!EEA_ReadRuntimeReconciliation(ctx.account,ctx.config_version,ctx.history_lookback_days,
                                      ctx.refresh_seconds*2,ctx.reconciliation,reason))
     {
      ctx.status.refresh_in_progress = false;
      ctx.status.refresh_failure_count++;
      ctx.status.consecutive_refresh_failures++;
      ctx.status.reason_code=reason;
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_REFRESH_FAILED",ctx.status);
      return false;
     }
   // Only resolved, tradable symbols carry a validated specification.
   int spec_count=0;
   for(int i=0;i<ctx.symbol_count;i++)
      if(ctx.broker_symbols[i]!="" && !EEA_ObserverRuntimeIsContextOnly(ctx.canonical_symbols[i],ctx.broker_symbols[i]))
        { ctx.reconciliation.symbols[spec_count]=ctx.symbol_specs[i]; spec_count++; }
   ctx.reconciliation.symbol_count=spec_count;
   ctx.status.selected_symbols_fingerprint=EEA_RuntimeSelectedSymbolsFingerprint(
      ctx.canonical_symbols,ctx.broker_symbols,ctx.symbol_count);
   EEA_RuntimeStatus val_status;
   EEA_RuntimeValidate(ctx.reconciliation,(long)TimeGMT(),ctx.previous_deal_watermark,val_status);
   val_status.runtime_instance_id = ctx.status.runtime_instance_id;
   val_status.refresh_sequence = ctx.status.refresh_sequence;
   val_status.refresh_generation = ctx.status.refresh_generation;
   val_status.selection_revision = ctx.status.selection_revision;
   val_status.checkpoint_written_at_utc = ctx.status.checkpoint_written_at_utc;
   val_status.broker_observed_at_utc = ctx.status.broker_observed_at_utc;
   val_status.selected_symbols_fingerprint = ctx.status.selected_symbols_fingerprint;
   val_status.timer_tick_count = ctx.status.timer_tick_count;
   val_status.refresh_attempt_count = ctx.status.refresh_attempt_count;
   val_status.refresh_success_count = ctx.status.refresh_success_count;
   val_status.refresh_failure_count = ctx.status.refresh_failure_count;
   val_status.last_timer_at_utc = ctx.status.last_timer_at_utc;
   val_status.last_refresh_duration_ms = ctx.status.last_refresh_duration_ms;
   val_status.max_refresh_duration_ms = ctx.status.max_refresh_duration_ms;
   val_status.consecutive_refresh_failures = ctx.status.consecutive_refresh_failures;
   val_status.transaction_callback_count = ctx.status.transaction_callback_count;
   val_status.transaction_invalidation_generation = ctx.status.transaction_invalidation_generation;
   val_status.pending_refresh = ctx.status.pending_refresh;
   val_status.refresh_in_progress = ctx.status.refresh_in_progress;
   ctx.status = val_status;
   ulong duration_ms = GetTickCount64() - start_tick;
   ctx.status.last_refresh_duration_ms = (long)duration_ms;
   if((long)duration_ms > ctx.status.max_refresh_duration_ms)
      ctx.status.max_refresh_duration_ms = (long)duration_ms;
   ctx.status.broker_observed_at_utc = ctx.reconciliation.observed_at_utc;
   ctx.status.checkpoint_written_at_utc = (long)TimeGMT();
   ctx.previous_deal_watermark=ctx.reconciliation.deal_watermark;
   ctx.last_refresh_utc=(long)TimeGMT();
   ctx.stale=false;
   ctx.stale_reason="";
   ctx.status.refresh_success_count++;
   ctx.status.consecutive_refresh_failures=0;
   ctx.status.refresh_in_progress=false;
   ctx.status.pending_refresh=false;
   bool persisted=EEA_RuntimeStoreWriteAccount(ctx.root,ctx.account) &&
      EEA_RuntimeStoreWriteSymbols(ctx.root,ctx.canonical_symbols,ctx.symbol_specs,ctx.symbol_count,
                                   ctx.config_version,ctx.account.account_fingerprint) &&
      EEA_RuntimeStoreWriteReconciliation(ctx.root,ctx.reconciliation) &&
      EEA_RuntimeStoreWriteSymbolSelection(ctx.root,ctx.config_version,ctx.account.account_fingerprint,
                                            ctx.account.broker_server,ctx.status.selection_revision,
                                            ctx.canonical_symbols,ctx.broker_symbols,ctx.symbol_count) &&
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                                  ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
   if(!persisted)
     {
      ctx.status.refresh_in_progress = false;
      ctx.status.refresh_failure_count++;
      ctx.status.consecutive_refresh_failures++;
      ctx.status.runtime_state="BLOCKED"; ctx.status.reason_code="RUNTIME_PERSISTENCE_FAILED";
      ctx.status.new_entries_blocked=true;
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_PERSISTENCE_FAILED",ctx.status);
      return false;
     }
   if(!EEA_ObserverRuntimeAuditSymbolResolution(ctx,audit)) return false;
   EEA_ObserverRuntimeAuditChecked(ctx,audit,prior.runtime_state=="" ? "RUNTIME_INITIALIZED" : "RUNTIME_REFRESHED",ctx.status);
   return ctx.status.runtime_state=="OBSERVING";
  }

// Records a change in the set of blocked symbols; an audit failure blocks the runtime.
bool EEA_ObserverRuntimeAuditSymbolResolution(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   string blocked="";
   string json="[";
   for(int i=0;i<ctx.symbol_count;i++)
     {
      if(EEA_ObserverRuntimeIsContextOnly(ctx.canonical_symbols[i],ctx.broker_symbols[i]) ||
         ctx.broker_symbols[i]!="") continue;
      string reason=(ctx.symbol_block_reason[i]=="" ? "SYMBOL_UNRESOLVED" : ctx.symbol_block_reason[i]);
      if(blocked!="") { blocked+=","; json+=","; }
      blocked+=ctx.canonical_symbols[i]+":"+reason;
      json+="{\"canonical_symbol\":\""+EEA_JsonEscape(ctx.canonical_symbols[i])+
            "\",\"reason\":\""+EEA_JsonEscape(reason)+"\"}";
     }
   json+="]";
   if(blocked==ctx.unresolved_fingerprint) return true;
   if(audit.IsOpen())
     {
      EEAEvent e;
      EEAEvent_Init(e,blocked=="" ? "SYMBOL_RESOLUTION_RESTORED" : "SYMBOL_RESOLUTION_PARTIAL",TimeGMT(),"",
                    "runtime-evidence","",ctx.status.runtime_state,blocked=="" ? "OK" : "DEGRADED");
      e.config_version=ctx.config_version;
      EEAEvent_AddReason(e,blocked=="" ? "SYMBOL_RESOLUTION_COMPLETE" : "SYMBOL_BLOCKED_INDIVIDUALLY");
      e.details_json="{\"observer_only\":true,\"blocked_symbols\":"+json+"}";
      if(audit.Append(e,"EA_RUNTIME_OBSERVER"))
        {
         ctx.unresolved_fingerprint=blocked;
         return true;
        }
     }
   ctx.status.runtime_state="BLOCKED";
   ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
   ctx.status.new_entries_blocked=true;
   EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
      ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
   return false;
  }

bool EEA_ObserverRuntimeAuditChecked(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                                     const string event_type,const EEA_RuntimeStatus &status)
  {
   if(EEA_ObserverRuntimeAudit(audit,ctx.config_version,event_type,status)) return true;
   ctx.status.runtime_state="BLOCKED";
   ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
   ctx.status.new_entries_blocked=true;
   bool status_persisted=EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                                      ctx.account.account_fingerprint,
                                      ctx.reconciliation.observed_at_utc);
   bool status_validated=status_persisted &&
      EEA_RuntimeStoreCheckBlockedAuditStatus(ctx.root+"/current/runtime_status.json",ctx.config_version,
                                              ctx.account.account_fingerprint);
   if(!status_validated)
     {
      ctx.status.runtime_state="BLOCKED";
      ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
      ctx.status.new_entries_blocked=true;
     }
   return false;
  }

bool EEA_ObserverRuntimeInit(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                             const string root,const string config_version,
                             const int refresh_seconds,const int history_lookback_days,
                             const string &canonical[],const int count)
  {
   EEA_RuntimeDefaults(ctx.status);
   ctx.status.runtime_instance_id = (long)GetTickCount64() + (long)TimeGMT();
   long persisted_selection_revision=0;
   // Start from an invalid sentinel; a valid persisted revision is mandatory for recovery.
   ctx.status.selection_revision = 0;
   for(int i=0;i<count && i<EEA_RUNTIME_MAX_SYMBOLS;i++)
     {
      ctx.canonical_symbols[i]=canonical[i];
      ctx.broker_symbols[i]="";
      ctx.symbol_block_reason[i]="";
     }
   ctx.unresolved_fingerprint="";
   ctx.enabled=true; ctx.initialized=false; ctx.stale=true; ctx.stale_reason="STARTUP";
   ctx.root=root; ctx.config_version=config_version; ctx.refresh_seconds=refresh_seconds;
   ctx.history_lookback_days=history_lookback_days; ctx.last_refresh_utc=0;
   ctx.previous_deal_watermark=-1; ctx.symbol_count=count;
   if(refresh_seconds<1 || history_lookback_days<1 || history_lookback_days>90 || count<1 || count>EEA_RUNTIME_MAX_SYMBOLS)
     { ctx.status.reason_code="RUNTIME_CONFIGURATION_INVALID"; return false; }
   string account_reason="";
    if(!EEA_ReadRuntimeAccount(ctx.config_version,ctx.refresh_seconds*2,ctx.account,account_reason))
      {
       ctx.status.runtime_state="DEGRADED";
       ctx.status.reason_code="RUNTIME_ACCOUNT_INIT_DEGRADED";
       ctx.status.new_entries_blocked=true;
       ctx.stale=true;
       ctx.stale_reason=account_reason;
       ctx.status.pending_refresh=true;
       ctx.initialized=true;
       EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_ACCOUNT_INIT_DEGRADED",ctx.status);
       return false;
      }
    string brokers[];
   string discover_reasons[];
   string discover_reason;
   if(!EEA_ObserverRuntimeAutoDiscover(canonical, brokers, discover_reasons, count, ctx.account.broker_server, discover_reason))
     {
      ctx.status.runtime_state="DEGRADED";
      ctx.status.reason_code=discover_reason;
      ctx.status.new_entries_blocked=true;
      ctx.stale=true;
      ctx.stale_reason=discover_reason;
      ctx.status.pending_refresh=true;
      ctx.initialized=true;
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_INIT_DEGRADED",ctx.status);
      return false;
     }
   for(int i=0;i<count;i++)
     {
      ctx.canonical_symbols[i]=canonical[i];
      ctx.broker_symbols[i]=brokers[i];
      ctx.symbol_block_reason[i]=discover_reasons[i];
     }
   EEAStateLoadResult checkpoint=EEA_RuntimeStoreCheckStatus(
      ctx.root+"/current/runtime_status.json",ctx.config_version,ctx.account.account_fingerprint);
   EEAStateLoadResult selection_check=EEA_RuntimeStoreCheckSymbolSelection(
      ctx.root+"/current/symbol_selection.json",ctx.config_version,ctx.account.account_fingerprint);
   if(selection_check==EEA_STATE_COMPATIBLE &&
      EEA_RuntimeStoreLoadSymbolSelectionRevision(ctx.root+"/current/symbol_selection.json",
         ctx.config_version,ctx.account.account_fingerprint,persisted_selection_revision))
      ctx.status.selection_revision=persisted_selection_revision;
   else if(selection_check==EEA_STATE_INCOMPATIBLE)
      { ctx.status.reason_code="RUNTIME_SELECTION_INCOMPATIBLE"; ctx.status.selection_revision=1; }
   else if(selection_check==EEA_STATE_MISSING)
      ctx.status.selection_revision=1;
   EEA_RuntimeStatus checkpoint_status;
   EEA_RuntimeDefaults(checkpoint_status);
   checkpoint_status.reason_code=(checkpoint==EEA_STATE_MISSING ? "RUNTIME_CHECKPOINT_MISSING" :
                                  checkpoint==EEA_STATE_INCOMPATIBLE ? "RUNTIME_CHECKPOINT_INCOMPATIBLE" :
                                  selection_check==EEA_STATE_INCOMPATIBLE ? "RUNTIME_SELECTION_INCOMPATIBLE" :
                                  "RUNTIME_RECONCILIATION_REQUIRED");
   if(!EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_CHECKPOINT_OBSERVED",checkpoint_status))
     {
      ctx.status.runtime_state="BLOCKED";
      ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
      ctx.status.new_entries_blocked=true;
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
         ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
      ctx.initialized=true;
      return false;
     }
   ctx.initialized=true;
   return EEA_ObserverRuntimeRefresh(ctx,audit);
  }

void EEA_ObserverRuntimeMarkStale(EEA_ObserverRuntimeContext &ctx,const string reason,CAuditLog &audit)
  {
   ctx.status.transaction_callback_count++;
   if(!ctx.stale)
     {
      ctx.status.transaction_invalidation_generation++;
      ctx.stale=true;
      ctx.stale_reason=reason;
      ctx.status.runtime_state="DEGRADED";
      ctx.status.reason_code="RUNTIME_RECONCILIATION_REQUIRED";
      ctx.status.new_entries_blocked=true;
      ctx.status.pending_refresh=true;
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"BROKER_TRANSACTION_OBSERVED",ctx.status);
     }
   else
     {
      ctx.stale_reason=reason;
      ctx.status.pending_refresh=true;
     }
  }

void EEA_ObserverRuntimeOnTimer(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(!ctx.initialized) return;
   ctx.status.timer_tick_count++;
   ctx.status.last_timer_at_utc = (long)TimeGMT();
   if(ctx.stale || ctx.status.pending_refresh || (long)TimeGMT()-ctx.last_refresh_utc>=ctx.refresh_seconds)
     {
      if(ctx.status.refresh_in_progress)
        { ctx.status.pending_refresh = true; return; }
      EEA_ObserverRuntimeRefresh(ctx,audit);
     }
  }

void EEA_ObserverRuntimeShutdown(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(!ctx.initialized) return;
   EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
      ctx.account.account_fingerprint,(long)TimeGMT());
   EEA_ObserverRuntimeAuditChecked(ctx,audit,"RUNTIME_STOPPED",ctx.status);
   ctx.initialized=false;
  }

bool EEA_ObserverRuntimeRestoreSelectionSnapshot(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                                                 const string &old_canons[],
                                                 const string &old_broker_symbols[],
                                                 const EEA_RuntimeSymbolSpec &old_symbol_specs[],
                                                 const int old_count,
                                                 const EEA_RuntimeAccountSnapshot &old_account,
                                                 const EEA_RuntimeReconciliationSnapshot &old_reconciliation,
                                                 const EEA_RuntimeStatus &old_status,
                                                 const bool old_stale,
                                                 const string old_stale_reason,
                                                 const long old_last_refresh_utc,
                                                 const long old_previous_deal_watermark,
                                                 const long old_previous_deal_watermark_time=0)
  {
   for(int i=0;i<old_count;i++)
     {
      ctx.canonical_symbols[i] = old_canons[i];
      ctx.broker_symbols[i]=old_broker_symbols[i];
      ctx.symbol_specs[i]=old_symbol_specs[i];
     }
   ctx.symbol_count=old_count;
   ctx.account=old_account;
   ctx.reconciliation=old_reconciliation;
   ctx.status=old_status;
   ctx.status = old_status;
   long old_revision=old_status.selection_revision;
   ctx.stale=old_stale;
   ctx.stale_reason=old_stale_reason;
   ctx.last_refresh_utc=old_last_refresh_utc;
   ctx.previous_deal_watermark=old_previous_deal_watermark;
   ctx.status.previous_deal_watermark_time=old_previous_deal_watermark_time;
   return EEA_RuntimeStoreWriteAccount(ctx.root,ctx.account) &&
      EEA_RuntimeStoreWriteSymbols(ctx.root,ctx.canonical_symbols,ctx.symbol_specs,ctx.symbol_count,
                                       ctx.config_version,ctx.account.account_fingerprint) &&
      EEA_RuntimeStoreWriteReconciliation(ctx.root,ctx.reconciliation) &&
      EEA_RuntimeStoreWriteSymbolSelection(ctx.root,ctx.config_version,ctx.account.account_fingerprint,
                                           ctx.account.broker_server,ctx.status.selection_revision,
                                           ctx.canonical_symbols,ctx.broker_symbols,ctx.symbol_count) &&
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                                  ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
  }

bool EEA_ObserverRuntimeApplySelection(EEA_ObserverRuntimeContext &ctx, CAuditLog &audit, const string &canonical[], const int count)
  {
   if(count < 1 || count > EEA_RUNTIME_MAX_SYMBOLS) return false;
   string brokers[];
   string discover_reasons[];
   string discover_reason;
   if(!EEA_ObserverRuntimeAutoDiscover(canonical, brokers, discover_reasons, count, ctx.account.broker_server, discover_reason))
     { return false; }
   string old_canons[EEA_RUNTIME_MAX_SYMBOLS];
   string old_brokers[EEA_RUNTIME_MAX_SYMBOLS];
   EEA_RuntimeSymbolSpec old_specs[EEA_RUNTIME_MAX_SYMBOLS];
   EEA_RuntimeAccountSnapshot old_account=ctx.account;
   EEA_RuntimeReconciliationSnapshot old_reconciliation=ctx.reconciliation;
   EEA_RuntimeStatus old_status=ctx.status;
   bool old_stale=ctx.stale;
   string old_stale_reason=ctx.stale_reason;
   long old_last_refresh_utc=ctx.last_refresh_utc;
   long old_previous_deal_watermark=ctx.previous_deal_watermark;
   long old_previous_deal_watermark_time=ctx.status.previous_deal_watermark_time;
   int old_count = ctx.symbol_count;
   for(int i=0;i<old_count;i++)
     {
      old_canons[i] = ctx.canonical_symbols[i];
      old_brokers[i] = ctx.broker_symbols[i];
      old_specs[i] = ctx.symbol_specs[i];
     }
   for(int i=0;i<count;i++)
     {
      ctx.canonical_symbols[i] = canonical[i];
      ctx.broker_symbols[i] = brokers[i];
      ctx.symbol_block_reason[i] = discover_reasons[i];
     }
   ctx.symbol_count = count;
   ctx.status.selection_revision++;
   EEA_ObserverRuntimeMarkStale(ctx, "SELECTION_CHANGED", audit);
   if(EEA_ObserverRuntimeRefresh(ctx, audit)) return true;
   bool rollback_persisted=EEA_ObserverRuntimeRestoreSelectionSnapshot(ctx,audit,old_canons,old_brokers,
      old_specs,old_count,old_account,old_reconciliation,old_status,old_stale,old_stale_reason,old_last_refresh_utc,
      old_previous_deal_watermark,old_previous_deal_watermark_time);
   if(!rollback_persisted)
     {
      ctx.status.runtime_state="BLOCKED";
      ctx.status.reason_code="POLICY/SELECTION_ROLLBACK_PERSISTENCE_FAILED";
      ctx.status.new_entries_blocked=true;
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
         ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
      EEA_ObserverRuntimeAuditChecked(ctx,audit,"SELECTION_ROLLBACK_PERSISTENCE_FAILED",ctx.status);
     }
   else if(!audit.IsOpen() || !EEA_ObserverRuntimeAuditChecked(ctx,audit,"SELECTION_APPLY_ROLLBACK_PERSISTED",ctx.status))
     {
      ctx.status.runtime_state="BLOCKED";
      ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
      ctx.status.new_entries_blocked=true;
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
         ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
     }
   return false;
  }

#endif

