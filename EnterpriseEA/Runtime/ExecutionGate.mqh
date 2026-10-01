#ifndef ENTERPRISE_EA_EXECUTION_GATE_MQH
#define ENTERPRISE_EA_EXECUTION_GATE_MQH

#include "ExecutionContracts.mqh"
#include "RuntimeEvidence.mqh"
#include "..\Market\SymbolRegistry.mqh"

bool EEA_ExecutionAligned(const double value,const double origin,const double step)
  {
   if(!EEA_IsFiniteDouble(value) || !EEA_IsFiniteDouble(origin) ||
      !EEA_IsFiniteDouble(step) || step<=0.0)
      return false;
   const double units=(value-origin)/step;
   const double rounded=MathRound(units);
   const double error=MathAbs((value-origin)-rounded*step);
   return error<=MathMax(step*1.0e-8,1.0e-12);
  }

bool EEA_ExecutionPriceAligned(const double price,const double tick_size)
  {
   if(price==0.0) return true; // Zero means "let the broker use market price".
   return EEA_ExecutionAligned(price,0.0,tick_size);
  }

bool EEA_ExecutionSymbolSnapshotMatches(const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                        const EEA_RuntimeSymbolSpec &symbol)
  {
   if(reconciliation.symbol_count<=0 || reconciliation.symbol_count>EEA_RUNTIME_MAX_SYMBOLS)
      return false;
   for(int i=0;i<reconciliation.symbol_count;i++)
      if(reconciliation.symbols[i].broker_symbol==symbol.broker_symbol &&
         EEA_RuntimeMaterialSpecEqual(reconciliation.symbols[i],symbol) &&
         reconciliation.symbols[i].filling_mode_mask==symbol.filling_mode_mask)
         return true;
   return false;
  }

bool EEA_ExecutionGateCheck(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
                            const EEA_RuntimeStatus &status,
                            const bool execution_enabled,
                            EEA_ExecutionResult &result)
  {
   EEA_ExecutionResultDefaults(result);
   result.intent_id=intent.intent_id;
   result.correlation_id=intent.correlation_id;
   result.idempotency_key=intent.idempotency_key;
   result.observed_at_utc=TimeGMT();

   if(!execution_enabled)
     {
      EEA_ExecutionResultReject(result,"EXECUTION_DISABLED");
      return false;
     }

   if(status.runtime_state!="OBSERVING")
     {
      EEA_ExecutionResultReject(result,"EXECUTION_STATE_INVALID");
      return false;
     }
   if((intent.action==EEA_EXEC_ACTION_SUBMIT_MARKET ||
       intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING) && status.new_entries_blocked)
     {
      EEA_ExecutionResultReject(result,"EXECUTION_STATE_INVALID");
      return false;
     }

   if(intent.intent_id=="")
     {
      EEA_ExecutionResultReject(result,"INTENT_ID_MISSING");
      return false;
     }
   if(intent.correlation_id=="")
     {
      EEA_ExecutionResultReject(result,"CORRELATION_ID_MISSING");
      return false;
     }
   if(intent.idempotency_key=="")
     {
      EEA_ExecutionResultReject(result,"IDEMPOTENCY_KEY_MISSING");
      return false;
     }
   if(!EEA_ExecutionIntentIdentifiersPresent(intent))
     {
      EEA_ExecutionResultReject(result,"EXECUTION_IDENTITY_MISSING");
      return false;
     }

   if(intent.schema_version!="0.1.0")
     {
      EEA_ExecutionResultReject(result,"INTENT_SCHEMA_INVALID");
      return false;
     }
   if(intent.config_version=="" || account.config_version=="" ||
      reconciliation.config_version=="")
     {
      EEA_ExecutionResultReject(result,"CONFIG_VERSION_MISSING");
      return false;
     }
   if(intent.risk_policy_id=="")
     {
      EEA_ExecutionResultReject(result,"RISK_POLICY_ID_MISSING");
      return false;
     }
   if(intent.risk_decision_status!="RISK_APPROVED" ||
      intent.candidate_id=="" || intent.setup_id=="" || intent.setup_version=="" ||
      intent.risk_decision_id=="" || intent.risk_policy_snapshot_id=="" ||
      intent.portfolio_snapshot_id=="" || intent.quote_snapshot_id=="" ||
      intent.reconciliation_snapshot_id=="" || intent.entry_reference=="" ||
      intent.reconciliation_observed_at_utc<=0 ||
      !EEA_IsFiniteDouble(intent.risk_budget) || intent.risk_budget<=0.0 ||
      !EEA_IsFiniteDouble(intent.projected_loss) || intent.projected_loss<=0.0 ||
      !EEA_IsFiniteDouble(intent.net_reward_risk))
     {
      EEA_ExecutionResultReject(result,"RISK_DECISION_LINEAGE_MISSING");
      return false;
     }
   if(intent.config_version!=account.config_version ||
      intent.config_version!=reconciliation.config_version)
     {
      EEA_ExecutionResultReject(result,"CONFIG_VERSION_MISMATCH");
      return false;
     }

   const long now=(long)TimeGMT();
   if(account.schema_version!="runtime-evidence-v0.1.0" ||
      account.snapshot_id=="" || account.observed_at_utc<=0 ||
      account.valid_until_utc<=now || account.observed_at_utc>now)
     {
      EEA_ExecutionResultReject(result,"ACCOUNT_SNAPSHOT_INVALID");
      return false;
     }
   if(!EEA_IsFiniteDouble(account.balance) || !EEA_IsFiniteDouble(account.equity) ||
      !EEA_IsFiniteDouble(account.margin) || !EEA_IsFiniteDouble(account.margin_free))
     {
      EEA_ExecutionResultReject(result,"ACCOUNT_FINANCIAL_STATE_INVALID");
      return false;
     }
   if(reconciliation.schema_version!="runtime-evidence-v0.1.0" ||
      reconciliation.snapshot_id=="" || reconciliation.observed_at_utc<=0 ||
      reconciliation.valid_until_utc<=now || reconciliation.observed_at_utc>now)
     {
      EEA_ExecutionResultReject(result,"RECONCILIATION_STALE");
      return false;
     }
   if(!reconciliation.positions_complete || !reconciliation.orders_complete ||
      !reconciliation.deals_complete || !reconciliation.history_orders_complete)
     {
      EEA_ExecutionResultReject(result,"RECONCILIATION_STALE");
      return false;
     }

   if(intent.account_fingerprint=="" || intent.broker_server=="" ||
      account.account_fingerprint=="" || account.broker_server=="" ||
      reconciliation.account_fingerprint=="" || reconciliation.broker_server=="")
     {
      EEA_ExecutionResultReject(result,"ACCOUNT_IDENTITY_MISSING");
      return false;
     }
   if(intent.account_fingerprint!=account.account_fingerprint ||
      intent.broker_server!=account.broker_server ||
      reconciliation.account_fingerprint!=account.account_fingerprint ||
      reconciliation.broker_server!=account.broker_server)
     {
      EEA_ExecutionResultReject(result,"ACCOUNT_IDENTITY_MISMATCH");
      return false;
     }

   if(intent.canonical_symbol=="" || intent.broker_symbol=="" ||
      symbol.broker_symbol=="")
     {
      EEA_ExecutionResultReject(result,"SYMBOL_BINDING_MISSING");
      return false;
     }
   if(intent.symbol_fingerprint=="" || symbol.metadata_fingerprint=="")
     {
      EEA_ExecutionResultReject(result,"SYMBOL_FINGERPRINT_MISSING");
      return false;
     }
   if(intent.broker_symbol!=symbol.broker_symbol ||
      intent.symbol_fingerprint!=symbol.metadata_fingerprint ||
      !EEA_ExecutionSymbolSnapshotMatches(reconciliation,symbol))
     {
      EEA_ExecutionResultReject(result,
         intent.symbol_fingerprint!=symbol.metadata_fingerprint ?
         "SYMBOL_FINGERPRINT_MISMATCH" : "BROKER_SYMBOL_MISMATCH");
      return false;
     }

   if(symbol.trade_mode=="DISABLED" || symbol.trade_mode=="CLOSE_ONLY" ||
      symbol.trade_mode=="0" || symbol.trade_mode=="3" ||
      !EEA_IsFiniteDouble(symbol.point) || !EEA_IsFiniteDouble(symbol.tick_size) ||
      !EEA_IsFiniteDouble(symbol.tick_value) || !EEA_IsFiniteDouble(symbol.contract_size) ||
      !EEA_IsFiniteDouble(symbol.volume_min) || !EEA_IsFiniteDouble(symbol.volume_max) ||
      !EEA_IsFiniteDouble(symbol.volume_step) || symbol.digits<0 ||
      symbol.point<=0.0 || symbol.tick_size<=0.0 || symbol.tick_value<=0.0 ||
      symbol.contract_size<=0.0 ||
      symbol.volume_min<=0.0 || symbol.volume_max<symbol.volume_min ||
      symbol.volume_step<=0.0 || symbol.stops_level_points<0 ||
      symbol.freeze_level_points<0 || symbol.base_currency=="" ||
      symbol.profit_currency=="" || symbol.margin_currency=="")
     {
      EEA_ExecutionResultReject(result,"SYMBOL_SPEC_INVALID");
      return false;
     }
   if(intent.filling_mode<0 || intent.filling_mode>2)
     {
      EEA_ExecutionResultReject(result,"SYMBOL_FILLING_UNSUPPORTED");
      return false;
     }
   if(symbol.filling_mode_mask>0)
     {
      const long filling_bit=(long)1 << intent.filling_mode;
      if((symbol.filling_mode_mask & filling_bit)==0)
        {
         EEA_ExecutionResultReject(result,"SYMBOL_FILLING_UNSUPPORTED");
         return false;
        }
     }

   if(intent.action<EEA_EXEC_ACTION_SUBMIT_MARKET ||
      intent.action>EEA_EXEC_ACTION_CANCEL_PENDING || intent.order_type<0 ||
      intent.order_type>7 || !EEA_IsFiniteDouble(intent.volume) ||
      !EEA_IsFiniteDouble(intent.price) || !EEA_IsFiniteDouble(intent.sl) ||
      !EEA_IsFiniteDouble(intent.tp))
     {
      EEA_ExecutionResultReject(result,"EXECUTION_CONTRACT_INVALID");
      return false;
     }
   if(intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING ||
      intent.action==EEA_EXEC_ACTION_CANCEL_PENDING ||
      (intent.action==EEA_EXEC_ACTION_MODIFY_PROTECTIVE && intent.position_ticket<=0))
     {
      EEA_ExecutionResultReject(result,"PENDING_RUNTIME_NOT_IMPLEMENTED");
      return false;
     }
   if(intent.action==EEA_EXEC_ACTION_SUBMIT_MARKET && intent.order_type>1)
     {
      EEA_ExecutionResultReject(result,"MARKET_ORDER_TYPE_UNSUPPORTED");
      return false;
     }
   if(intent.action==EEA_EXEC_ACTION_SUBMIT_MARKET ||
      intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING)
     {
      if(intent.volume<symbol.volume_min || intent.volume>symbol.volume_max)
        {
         EEA_ExecutionResultReject(result,"SYMBOL_SPEC_INVALID");
         return false;
        }
      if(!EEA_ExecutionAligned(intent.volume,symbol.volume_min,symbol.volume_step))
        {
         EEA_ExecutionResultReject(result,"VOLUME_STEP_INVALID");
         return false;
        }
      if(intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING && intent.price<=0.0)
        {
         EEA_ExecutionResultReject(result,"PRICE_GEOMETRY_INVALID");
         return false;
        }
     }
   if(!EEA_ExecutionPriceAligned(intent.price,symbol.tick_size) ||
      !EEA_ExecutionPriceAligned(intent.sl,symbol.tick_size) ||
      !EEA_ExecutionPriceAligned(intent.tp,symbol.tick_size))
     {
      EEA_ExecutionResultReject(result,"PRICE_GEOMETRY_INVALID");
      return false;
     }

   EEA_ExecutionResultAccept(result);
   return true;
  }

#endif
