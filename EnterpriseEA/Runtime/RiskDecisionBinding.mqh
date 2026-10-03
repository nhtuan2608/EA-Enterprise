#ifndef ENTERPRISE_EA_RISK_DECISION_BINDING_MQH
#define ENTERPRISE_EA_RISK_DECISION_BINDING_MQH

#include "ExecutionContracts.mqh"
#include "..\Risk\RiskDecision.mqh"

// Binds an executable intent to the immutable risk release that produced it.
// The intent's status string is not evidence of a release by itself.
bool EEA_RiskDecisionBindsExecutionIntent(const EEA_RiskDecision &decision,
                                          const EEA_ExecutionIntent &intent,
                                          const datetime now_utc)
  {
   if(!EEA_RiskDecisionValidForRelease(decision,now_utc)) return false;
   if(intent.risk_decision_status!="RISK_APPROVED" ||
      intent.risk_decision_id!=decision.decision_id ||
      intent.candidate_id!=decision.candidate_id ||
      intent.setup_id!=decision.setup_id ||
      intent.risk_policy_id!=decision.policy_id ||
      intent.account_fingerprint!=decision.account_fingerprint ||
      intent.canonical_symbol!=decision.symbol ||
      intent.symbol_fingerprint!=decision.symbol_spec_fingerprint ||
      intent.quote_snapshot_id!=decision.quote_snapshot_id ||
      intent.portfolio_snapshot_id!=decision.portfolio_snapshot_id ||
      intent.reconciliation_snapshot_id!=decision.reconciliation_id)
      return false;
   if(!MathIsValidNumber(intent.volume) || !MathIsValidNumber(intent.projected_loss) ||
      MathAbs(intent.volume-decision.final_volume)>1.0e-12 ||
      MathAbs(intent.risk_budget-decision.risk_budget)>1.0e-8 ||
      MathAbs(intent.net_reward_risk-decision.net_reward_risk)>1.0e-8 ||
      MathAbs(intent.projected_loss-decision.projected_loss)>1.0e-8 ||
      MathAbs(StringToDouble(intent.entry_reference)-decision.entry_reference)>1.0e-8 ||
      MathAbs(intent.sl-decision.stop_loss)>1.0e-8 ||
      MathAbs(intent.tp-decision.take_profit)>1.0e-8 ||
      EEA_OrderTypeDirection(intent.order_type)!=decision.direction ||
      (intent.action==EEA_EXEC_ACTION_SUBMIT_MARKET && intent.order_type>1) ||
      (intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING && (intent.order_type<2 || intent.order_type>5)))
      return false;
   return true;
  }

#endif
