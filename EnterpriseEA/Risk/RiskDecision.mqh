#ifndef ENTERPRISE_EA_RISK_DECISION_MQH
#define ENTERPRISE_EA_RISK_DECISION_MQH

// Pure risk-release contract. No broker, terminal, storage, or execution APIs.
// REVIEWABLE_CANDIDATE is review output only; it is never a release approval.
struct EEA_RiskDecision
  {
   string decision_status;          // UNKNOWN | REVIEWABLE_CANDIDATE | RISK_APPROVED
   string release_status;           // BLOCKED | RELEASED

   string decision_id;
   string candidate_id;
   string setup_id;

   string policy_id;
   string policy_version;

   string account_id;
   string account_snapshot_id;
   string account_fingerprint;

   string reconciliation_id;
   string reconciliation_fingerprint;

   string symbol;
   string symbol_spec_fingerprint;

   string quote_id;
   string quote_snapshot_id;
   string quote_fingerprint;

   string portfolio_snapshot_id;
   string portfolio_fingerprint;

   double final_volume;
   double risk_budget;
   double projected_loss;
   double net_reward_risk;
   double available_headroom;
   int direction;
   double entry_reference;
   double stop_loss;
   double take_profit;

   datetime decided_at_utc;
   datetime expires_at_utc;

   string reason_code;
   string secondary_reason_code;
  };

void EEA_RiskDecisionDefaults(EEA_RiskDecision &decision)
  {
   decision.decision_status="UNKNOWN";
   decision.release_status="BLOCKED";

   decision.decision_id="";
   decision.candidate_id="";
   decision.setup_id="";

   decision.policy_id="";
   decision.policy_version="";

   decision.account_id="";
   decision.account_snapshot_id="";
   decision.account_fingerprint="";

   decision.reconciliation_id="";
   decision.reconciliation_fingerprint="";

   decision.symbol="";
   decision.symbol_spec_fingerprint="";

   decision.quote_id="";
   decision.quote_snapshot_id="";
   decision.quote_fingerprint="";

   decision.portfolio_snapshot_id="";
   decision.portfolio_fingerprint="";

   decision.final_volume=0.0;
   decision.risk_budget=0.0;
   decision.projected_loss=0.0;
   decision.net_reward_risk=0.0;
   decision.available_headroom=0.0;
   decision.direction=0;
   decision.entry_reference=0.0;
   decision.stop_loss=0.0;
   decision.take_profit=0.0;

   decision.decided_at_utc=0;
   decision.expires_at_utc=0;

   decision.reason_code="UNKNOWN";
   decision.secondary_reason_code="";
  }

bool EEA_RiskDecisionValidForRelease(const EEA_RiskDecision &decision,const datetime now_utc)
  {
   if(decision.decision_status=="REVIEWABLE_CANDIDATE" ||
      decision.decision_status!="RISK_APPROVED" || decision.release_status!="RELEASED")
     return false;

   if(decision.decision_id=="" || decision.candidate_id=="" || decision.setup_id=="" ||
      decision.policy_id=="" || decision.policy_version=="" ||
      decision.account_id=="" || decision.account_snapshot_id=="" ||
      decision.account_fingerprint=="" || decision.reconciliation_id=="" ||
      decision.reconciliation_fingerprint=="" || decision.symbol=="" ||
      decision.symbol_spec_fingerprint=="" || decision.quote_id=="" ||
      decision.quote_snapshot_id=="" || decision.quote_fingerprint=="" ||
      decision.portfolio_snapshot_id=="" || decision.portfolio_fingerprint=="" ||
      decision.reason_code=="")
     return false;

   if(!MathIsValidNumber(decision.final_volume) || decision.final_volume<=0.0 ||
      !MathIsValidNumber(decision.risk_budget) || decision.risk_budget<=0.0 ||
      !MathIsValidNumber(decision.projected_loss) || decision.projected_loss<=0.0 ||
      decision.projected_loss>decision.risk_budget ||
      !MathIsValidNumber(decision.net_reward_risk) || decision.net_reward_risk<=0.0 ||
      !MathIsValidNumber(decision.available_headroom) || decision.available_headroom<0.0 ||
      (decision.direction!=1 && decision.direction!=-1) ||
      !MathIsValidNumber(decision.entry_reference) || decision.entry_reference<=0.0 ||
      !MathIsValidNumber(decision.stop_loss) || decision.stop_loss<=0.0 ||
      !MathIsValidNumber(decision.take_profit) || decision.take_profit<=0.0 ||
      (decision.direction==1 && !(decision.stop_loss<decision.entry_reference &&
                                  decision.entry_reference<decision.take_profit)) ||
      (decision.direction==-1 && !(decision.take_profit<decision.entry_reference &&
                                   decision.entry_reference<decision.stop_loss)))
     return false;

   if(now_utc<=0 || decision.decided_at_utc<=0 ||
      decision.expires_at_utc<=decision.decided_at_utc ||
      decision.decided_at_utc>now_utc || decision.expires_at_utc<=now_utc)
     return false;

   return true;
  }

#endif
