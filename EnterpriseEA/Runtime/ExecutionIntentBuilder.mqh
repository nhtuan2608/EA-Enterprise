#ifndef ENTERPRISE_EA_EXECUTION_INTENT_BUILDER_MQH
#define ENTERPRISE_EA_EXECUTION_INTENT_BUILDER_MQH

#include "ExecutionContracts.mqh"
#include "RiskDecisionBinding.mqh"
#include "RuntimeEvidence.mqh"
#include "..\Risk\RiskDecision.mqh"

struct EEA_MarketIntentParameters
  {
   string canonical_symbol;
   string setup_version;
   string risk_policy_snapshot_id;
   string intent_id;
   string correlation_id;
   string idempotency_key;
   double entry_reference;
   double price;
   double stop_loss;
   double take_profit;
   int order_type;
   int deviation;
   int filling_mode;
   long magic;
  };

void EEA_MarketIntentParametersDefaults(EEA_MarketIntentParameters &p)
  {
   p.setup_version="";
   p.canonical_symbol="";
   p.risk_policy_snapshot_id="";
   p.intent_id="";
   p.correlation_id="";
   p.idempotency_key="";
   p.entry_reference=0.0;
   p.price=0.0;
   p.stop_loss=0.0;
   p.take_profit=0.0;
   p.order_type=-1;
   p.deviation=20;
   p.filling_mode=0;
   p.magic=888888;
  }

bool EEA_BuildMarketExecutionIntent(const EEA_RiskDecision &decision,
                                    const EEA_RuntimeAccountSnapshot &account,
                                    const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                    const EEA_RuntimeSymbolSpec &symbol,
                                    const string config_version,
                                    const EEA_MarketIntentParameters &p,
                                    const datetime now_utc,
                                    EEA_ExecutionIntent &intent,
                                    string &reason)
  {
   EEA_ExecutionIntentDefaults(intent);
   reason="EXECUTION_INTENT_BUILDER_REJECTED";
   if(!EEA_RiskDecisionValidForRelease(decision,now_utc))
     { reason="RISK_RELEASE_INVALID_OR_EXPIRED"; return false; }
   if(p.canonical_symbol=="" || p.setup_version=="" || p.risk_policy_snapshot_id=="" ||
      p.intent_id=="" || p.correlation_id=="" || p.idempotency_key=="")
     { reason="EXECUTION_INTENT_IDENTITY_MISSING"; return false; }
   if(p.order_type<0 || p.order_type>1)
     { reason="EXECUTION_INTENT_BUILDER_PENDING_UNSUPPORTED"; return false; }
   if(!MathIsValidNumber(p.entry_reference) || p.entry_reference<=0.0 ||
      !MathIsValidNumber(p.stop_loss) || !MathIsValidNumber(p.take_profit) ||
      p.stop_loss<=0.0 || p.take_profit<=0.0 || p.deviation<0 || p.magic<=0)
     { reason="EXECUTION_INTENT_PRICE_OR_CONTROL_INVALID"; return false; }
   if(MathAbs(p.entry_reference-decision.entry_reference)>1.0e-8 ||
      MathAbs(p.stop_loss-decision.stop_loss)>1.0e-8 ||
      MathAbs(p.take_profit-decision.take_profit)>1.0e-8 ||
      ((decision.direction==1 && p.order_type!=0) ||
       (decision.direction==-1 && p.order_type!=1)))
     { reason="EXECUTION_INTENT_PRICE_OR_DIRECTION_MISMATCH"; return false; }
   if(account.config_version!=config_version || reconciliation.config_version!=config_version ||
      account.account_fingerprint=="" || account.broker_server=="" ||
      reconciliation.account_fingerprint!=account.account_fingerprint ||
      reconciliation.broker_server!=account.broker_server ||
      account.valid_until_utc<=now_utc || reconciliation.valid_until_utc<=now_utc)
     { reason="EXECUTION_INTENT_RUNTIME_IDENTITY_INVALID"; return false; }
   if(symbol.broker_symbol=="" || symbol.metadata_fingerprint=="" ||
      decision.symbol!=p.canonical_symbol)
     { reason="EXECUTION_INTENT_SYMBOL_METADATA_INVALID"; return false; }
   if(MathAbs(decision.final_volume)<=0.0 ||
      !MathIsValidNumber(decision.final_volume) ||
      !MathIsValidNumber(decision.risk_budget) ||
      !MathIsValidNumber(decision.projected_loss) ||
      decision.projected_loss>decision.risk_budget)
     { reason="EXECUTION_INTENT_RISK_VALUES_INVALID"; return false; }

   intent.config_version=config_version;
   intent.intent_id=p.intent_id;
   intent.correlation_id=p.correlation_id;
   intent.idempotency_key=p.idempotency_key;
   intent.risk_policy_id=decision.policy_id;
   intent.account_fingerprint=account.account_fingerprint;
   intent.broker_server=account.broker_server;
   intent.canonical_symbol=decision.symbol;
   intent.broker_symbol=symbol.broker_symbol;
   intent.symbol_fingerprint=symbol.metadata_fingerprint;
   intent.candidate_id=decision.candidate_id;
   intent.setup_id=decision.setup_id;
   intent.setup_version=p.setup_version;
   intent.risk_decision_id=decision.decision_id;
   intent.risk_decision_status=decision.decision_status;
   intent.risk_policy_snapshot_id=p.risk_policy_snapshot_id;
   intent.portfolio_snapshot_id=decision.portfolio_snapshot_id;
   intent.quote_snapshot_id=decision.quote_snapshot_id;
   intent.reconciliation_snapshot_id=decision.reconciliation_id;
   intent.entry_reference=DoubleToString(p.entry_reference,8);
   intent.risk_budget=decision.risk_budget;
   intent.projected_loss=decision.projected_loss;
   intent.net_reward_risk=decision.net_reward_risk;
   intent.reconciliation_observed_at_utc=reconciliation.observed_at_utc;
   intent.action=EEA_EXEC_ACTION_SUBMIT_MARKET;
   intent.order_type=p.order_type;
   intent.volume=decision.final_volume;
   intent.price=p.price;
   intent.sl=p.stop_loss;
   intent.tp=p.take_profit;
   intent.magic=p.magic;
   intent.deviation=p.deviation;
   intent.filling_mode=p.filling_mode;
   intent.intent_created_at_utc=now_utc;
   if(!EEA_RiskDecisionBindsExecutionIntent(decision,intent,now_utc))
     { EEA_ExecutionIntentDefaults(intent); reason="EXECUTION_INTENT_RISK_LINEAGE_MISMATCH"; return false; }
   reason="EXECUTION_INTENT_BUILT_MARKET_ONLY";
   return true;
  }

// REQ-021: a pending LIMIT or STOP intent carries the same released risk lineage as a
// market intent; only the action, order type, price and broker expiration differ.
bool EEA_BuildPendingExecutionIntent(const EEA_RiskDecision &decision,
                                     const EEA_RuntimeAccountSnapshot &account,
                                     const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                     const EEA_RuntimeSymbolSpec &symbol,
                                     const string config_version,
                                     const EEA_MarketIntentParameters &p,
                                     const int pending_order_type,
                                     const datetime expiration_utc,
                                     const datetime now_utc,
                                     EEA_ExecutionIntent &intent,
                                     string &reason)
  {
   if(pending_order_type<2 || pending_order_type>5 ||
      EEA_OrderTypeDirection(pending_order_type)!=decision.direction)
     { EEA_ExecutionIntentDefaults(intent); reason="EXECUTION_INTENT_PENDING_TYPE_INVALID"; return false; }
   if(expiration_utc<=now_utc)
     { EEA_ExecutionIntentDefaults(intent); reason="EXECUTION_INTENT_PENDING_EXPIRATION_INVALID"; return false; }
   if(!EEA_BuildMarketExecutionIntent(decision,account,reconciliation,symbol,config_version,p,now_utc,intent,reason))
      return false;
   intent.action=EEA_EXEC_ACTION_SUBMIT_PENDING;
   intent.order_type=pending_order_type;
   intent.price=p.entry_reference;
   intent.expiration=expiration_utc;
   if(!EEA_RiskDecisionBindsExecutionIntent(decision,intent,now_utc))
     { EEA_ExecutionIntentDefaults(intent); reason="EXECUTION_INTENT_RISK_LINEAGE_MISMATCH"; return false; }
   reason="EXECUTION_INTENT_BUILT_PENDING";
   return true;
  }

#endif
