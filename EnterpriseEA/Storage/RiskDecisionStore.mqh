#ifndef ENTERPRISE_EA_RISK_DECISION_STORE_MQH
#define ENTERPRISE_EA_RISK_DECISION_STORE_MQH

#include "AtomicWriter.mqh"
#include "../Risk/RiskDecision.mqh"

string EEA_RiskDecisionStoreJson(const EEA_RiskDecision &d)
  {
   return "{\"schema_version\":\"risk-decision-v0.1.0\",\"decision_status\":\""+
      EEA_JsonEscape(d.decision_status)+"\",\"release_status\":\""+
      EEA_JsonEscape(d.release_status)+"\",\"decision_id\":\""+
      EEA_JsonEscape(d.decision_id)+"\",\"candidate_id\":\""+
      EEA_JsonEscape(d.candidate_id)+"\",\"setup_id\":\""+EEA_JsonEscape(d.setup_id)+
      "\",\"policy_id\":\""+EEA_JsonEscape(d.policy_id)+"\",\"policy_version\":\""+
      EEA_JsonEscape(d.policy_version)+"\",\"account_id\":\""+EEA_JsonEscape(d.account_id)+
      "\",\"account_snapshot_id\":\""+EEA_JsonEscape(d.account_snapshot_id)+
      "\",\"account_fingerprint\":\""+EEA_JsonEscape(d.account_fingerprint)+
      "\",\"reconciliation_id\":\""+EEA_JsonEscape(d.reconciliation_id)+
      "\",\"reconciliation_fingerprint\":\""+EEA_JsonEscape(d.reconciliation_fingerprint)+
      "\",\"symbol\":\""+EEA_JsonEscape(d.symbol)+"\",\"symbol_spec_fingerprint\":\""+
      EEA_JsonEscape(d.symbol_spec_fingerprint)+"\",\"quote_id\":\""+EEA_JsonEscape(d.quote_id)+
      "\",\"quote_snapshot_id\":\""+EEA_JsonEscape(d.quote_snapshot_id)+
      "\",\"quote_fingerprint\":\""+EEA_JsonEscape(d.quote_fingerprint)+
      "\",\"portfolio_snapshot_id\":\""+EEA_JsonEscape(d.portfolio_snapshot_id)+
      "\",\"portfolio_fingerprint\":\""+EEA_JsonEscape(d.portfolio_fingerprint)+
      "\",\"final_volume\":"+DoubleToString(d.final_volume,16)+
      ",\"risk_budget\":"+DoubleToString(d.risk_budget,16)+
      ",\"projected_loss\":"+DoubleToString(d.projected_loss,16)+
      ",\"net_reward_risk\":"+DoubleToString(d.net_reward_risk,16)+
      ",\"available_headroom\":"+DoubleToString(d.available_headroom,16)+
      ",\"direction\":"+IntegerToString(d.direction)+
      ",\"entry_reference\":"+DoubleToString(d.entry_reference,16)+
      ",\"stop_loss\":"+DoubleToString(d.stop_loss,16)+
      ",\"take_profit\":"+DoubleToString(d.take_profit,16)+
      ",\"decided_at_utc\":"+IntegerToString((long)d.decided_at_utc)+
      ",\"expires_at_utc\":"+IntegerToString((long)d.expires_at_utc)+
      ",\"reason_code\":\""+EEA_JsonEscape(d.reason_code)+
      "\",\"secondary_reason_code\":\""+EEA_JsonEscape(d.secondary_reason_code)+"\"}";
  }

bool EEA_RiskDecisionStoreWrite(const string root,const EEA_RiskDecision &decision)
  {
   if(root=="" || !EEA_RiskDecisionValidForRelease(decision,TimeGMT())) return false;
   string json=EEA_RiskDecisionStoreJson(decision);
   return EEA_WriteAtomicText(root+"/current/risk_decision.json",json) &&
          EEA_WriteAtomicAppendText(root+"/logs/risk_decisions.jsonl",json+"\r\n");
  }

#endif
