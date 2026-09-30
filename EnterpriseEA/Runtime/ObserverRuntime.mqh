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
  };

void EEA_ObserverRuntimeAudit(CAuditLog &audit,const string config_version,
                              const string event_type,const EEA_RuntimeStatus &status)
  {
   if(!audit.IsOpen()) return;
   EEAEvent e;
   EEAEvent_Init(e,event_type,TimeGMT(),"","runtime-evidence","",status.runtime_state,
                 status.runtime_state=="OBSERVING" ? "OK" : "DEGRADED");
   e.config_version=config_version;
   EEAEvent_AddReason(e,status.reason_code);
   e.details_json="{\"observer_only\":true,\"new_entries_blocked\":true}";
   audit.Append(e,"EA_RUNTIME_OBSERVER");
  }

bool EEA_ObserverRuntimeAutoDiscover(const string &canonicals[], string &brokers[], const int count, const string server, string &out_reason)
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
   for(int i = 0; i < count; i++)
     {
      if(!results[i].resolved)
        {
         out_reason = "SYMBOL_RESOLUTION_FAILED";
         return false;
        }
      brokers[i] = results[i].broker_symbol;
      
      EEA_RuntimeSymbolSpec spec;
      string spec_reason;
      if(!EEA_ReadRuntimeSymbolSpec(canonicals[i], brokers[i], server, spec, spec_reason))
        {
         out_reason = spec_reason;
         return false;
        }
     }
   return true;
  }

bool EEA_ObserverRuntimeRefresh(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   string reason="";
   EEA_RuntimeStatus prior=ctx.status;
   EEA_RuntimeDefaults(ctx.status);
   if(!EEA_ReadRuntimeAccount(ctx.config_version,ctx.refresh_seconds*2,ctx.account,reason))
     { ctx.status.reason_code=reason; EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_REFRESH_FAILED",ctx.status); return false; }

   for(int i=0;i<ctx.symbol_count;i++)
     if(!EEA_ReadRuntimeSymbolSpec(ctx.canonical_symbols[i],ctx.broker_symbols[i],
                                   ctx.account.broker_server,ctx.symbol_specs[i],reason))
       { ctx.status.reason_code=reason; EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_REFRESH_FAILED",ctx.status); return false; }

   if(!EEA_ReadRuntimeReconciliation(ctx.account,ctx.config_version,ctx.history_lookback_days,
                                      ctx.refresh_seconds*2,ctx.reconciliation,reason))
     { ctx.status.reason_code=reason; EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_REFRESH_FAILED",ctx.status); return false; }
   ctx.reconciliation.symbol_count=ctx.symbol_count;
   for(int i=0;i<ctx.symbol_count;i++) ctx.reconciliation.symbols[i]=ctx.symbol_specs[i];
   EEA_RuntimeValidate(ctx.reconciliation,(long)TimeGMT(),ctx.previous_deal_watermark,ctx.status);

   bool persisted=EEA_RuntimeStoreWriteAccount(ctx.root,ctx.account) &&
      EEA_RuntimeStoreWriteSymbols(ctx.root,ctx.canonical_symbols,ctx.symbol_specs,ctx.symbol_count,
                                   ctx.config_version,ctx.account.account_fingerprint) &&
      EEA_RuntimeStoreWriteReconciliation(ctx.root,ctx.reconciliation) &&
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                                  ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
   if(!persisted)
     { ctx.status.runtime_state="BLOCKED"; ctx.status.reason_code="RUNTIME_PERSISTENCE_FAILED";
       ctx.status.new_entries_blocked=true; EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_PERSISTENCE_FAILED",ctx.status); return false; }
   ctx.previous_deal_watermark=ctx.reconciliation.deal_watermark;
   ctx.last_refresh_utc=(long)TimeGMT();
   ctx.stale=false;
   ctx.stale_reason="";
   EEA_ObserverRuntimeAudit(audit,ctx.config_version,prior.runtime_state=="" ? "RUNTIME_INITIALIZED" : "RUNTIME_REFRESHED",ctx.status);
   return ctx.status.runtime_state=="OBSERVING";
  }

bool EEA_ObserverRuntimeInit(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                             const string root,const string config_version,
                             const int refresh_seconds,const int history_lookback_days,
                             const string &canonical[],const int count)
  {
   EEA_RuntimeDefaults(ctx.status);
   ctx.enabled=true; ctx.initialized=false; ctx.stale=true; ctx.stale_reason="STARTUP";
   ctx.root=root; ctx.config_version=config_version; ctx.refresh_seconds=refresh_seconds;
   ctx.history_lookback_days=history_lookback_days; ctx.last_refresh_utc=0;
   ctx.previous_deal_watermark=-1; ctx.symbol_count=count;
   if(refresh_seconds<1 || history_lookback_days<1 || history_lookback_days>90 || count<1 || count>EEA_RUNTIME_MAX_SYMBOLS)
     { ctx.status.reason_code="RUNTIME_CONFIGURATION_INVALID"; return false; }

   string account_reason="";
   if(!EEA_ReadRuntimeAccount(ctx.config_version,ctx.refresh_seconds*2,ctx.account,account_reason))
     { ctx.status.reason_code=account_reason; return false; }

   string brokers[];
   string discover_reason;
   if(!EEA_ObserverRuntimeAutoDiscover(canonical, brokers, count, ctx.account.broker_server, discover_reason))
     { ctx.status.reason_code=discover_reason; return false; }

   for(int i=0;i<count;i++)
     {
      ctx.canonical_symbols[i]=canonical[i];
      ctx.broker_symbols[i]=brokers[i];
     }

   EEAStateLoadResult checkpoint=EEA_RuntimeStoreCheckStatus(
      ctx.root+"/current/runtime_status.json",ctx.config_version,ctx.account.account_fingerprint);
   EEA_RuntimeStatus checkpoint_status;
   EEA_RuntimeDefaults(checkpoint_status);
   checkpoint_status.reason_code=(checkpoint==EEA_STATE_MISSING ? "RUNTIME_CHECKPOINT_MISSING" :
                                  checkpoint==EEA_STATE_INCOMPATIBLE ? "RUNTIME_CHECKPOINT_INCOMPATIBLE" :
                                  "RUNTIME_RECONCILIATION_REQUIRED");
   EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_CHECKPOINT_OBSERVED",checkpoint_status);
   ctx.initialized=true;
   return EEA_ObserverRuntimeRefresh(ctx,audit);
  }

void EEA_ObserverRuntimeMarkStale(EEA_ObserverRuntimeContext &ctx,const string reason)
  { ctx.stale=true; ctx.stale_reason=reason; ctx.status.runtime_state="DEGRADED";
    ctx.status.reason_code="RUNTIME_RECONCILIATION_REQUIRED"; ctx.status.new_entries_blocked=true; }

void EEA_ObserverRuntimeOnTimer(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(!ctx.initialized) return;
   if(ctx.stale || (long)TimeGMT()-ctx.last_refresh_utc>=ctx.refresh_seconds)
      EEA_ObserverRuntimeRefresh(ctx,audit);
  }

void EEA_ObserverRuntimeShutdown(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(!ctx.initialized) return;
   EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
      ctx.account.account_fingerprint,(long)TimeGMT());
   EEA_ObserverRuntimeAudit(audit,ctx.config_version,"RUNTIME_STOPPED",ctx.status);
   ctx.initialized=false;
  }

bool EEA_ObserverRuntimeApplySelection(EEA_ObserverRuntimeContext &ctx, CAuditLog &audit, const string &canonical[], const int count)
  {
   if(count < 1 || count > EEA_RUNTIME_MAX_SYMBOLS) return false;
   
   string brokers[];
   string discover_reason;
   if(!EEA_ObserverRuntimeAutoDiscover(canonical, brokers, count, ctx.account.broker_server, discover_reason))
     { return false; }

   string old_canons[EEA_RUNTIME_MAX_SYMBOLS];
   string old_brokers[EEA_RUNTIME_MAX_SYMBOLS];
   int old_count = ctx.symbol_count;
   for(int i=0; i<old_count; i++)
     {
      old_canons[i] = ctx.canonical_symbols[i];
      old_brokers[i] = ctx.broker_symbols[i];
     }
     
   for(int i=0; i<count; i++)
     {
      ctx.canonical_symbols[i] = canonical[i];
      ctx.broker_symbols[i] = brokers[i];
     }
   ctx.symbol_count = count;
   
   EEA_ObserverRuntimeMarkStale(ctx, "SELECTION_CHANGED");
   
   if(EEA_ObserverRuntimeRefresh(ctx, audit))
     {
      return true;
     }
   else
     {
      for(int i=0; i<old_count; i++)
        {
         ctx.canonical_symbols[i] = old_canons[i];
         ctx.broker_symbols[i] = old_brokers[i];
        }
      ctx.symbol_count = old_count;
      return false;
     }
  }

#endif
