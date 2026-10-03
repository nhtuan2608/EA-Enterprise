#ifndef ENTERPRISE_EA_RISK_DECISION_RELEASE_MQH
#define ENTERPRISE_EA_RISK_DECISION_RELEASE_MQH

#include "DryRunCandidateGate.mqh"
#include "..\Risk\RiskDecision.mqh"
#include "..\Runtime\RuntimeEvidence.mqh"

struct EEA_RiskReleaseRecheck
  {
   bool runtime_current;
   bool account_reconciled;
   bool quote_repriced;
   bool policy_rechecked;
   bool portfolio_reconciled;
   bool symbol_spec_unchanged;
   string account_id;
   string reconciliation_fingerprint;
   string quote_fingerprint;
   string portfolio_fingerprint;
   string release_reference;
   datetime checked_at_utc;
   datetime expires_at_utc;
  };

void EEA_RiskReleaseRecheckDefaults(EEA_RiskReleaseRecheck &r)
  {
   r.runtime_current=false;
   r.account_reconciled=false;
   r.quote_repriced=false;
   r.policy_rechecked=false;
   r.portfolio_reconciled=false;
   r.symbol_spec_unchanged=false;
   r.account_id="";
   r.reconciliation_fingerprint="";
   r.quote_fingerprint="";
   r.portfolio_fingerprint="";
   r.release_reference="";
   r.checked_at_utc=0;
   r.expires_at_utc=0;
  }

bool EEA_RiskDecisionReleaseFromReview(const EEA_DryRunContext &current,
                                       const EEA_DryRunDecision &review,
                                       const EEA_DryRunEvidence &evidence[],
                                       const EEA_RuntimeAccountSnapshot &account,
                                       const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                       const EEA_RiskReleaseRecheck &recheck,
                                       const datetime now_utc,
                                       EEA_RiskDecision &decision)
  {
   EEA_RiskDecisionDefaults(decision);
   decision.reason_code="RISK_RELEASE_RECHECK_REQUIRED";

   if(review.decision_status!="REVIEWABLE_CANDIDATE" || !review.evaluated ||
      review.candidate_id=="" || current.evaluated_at_utc<=0 ||
      current.evaluated_at_utc>now_utc || now_utc<=0)
      return false;

   // The release pass must re-run all seven gates against the fresh bundle.
   EEA_DryRunDecision fresh;
   if(!EEA_EvaluateDryRunCandidate(current,evidence,fresh) ||
      fresh.decision_status!="REVIEWABLE_CANDIDATE" ||
      fresh.candidate_id!=review.candidate_id)
      {
       decision.reason_code="RISK_RELEASE_FRESH_REVIEW_FAILED";
       return false;
      }

   EEA_RuntimeStatus runtime_status;
   EEA_RuntimeValidate(reconciliation,now_utc,-1,runtime_status);
   if(runtime_status.runtime_state!="OBSERVING" ||
      !recheck.runtime_current || !recheck.account_reconciled ||
      !recheck.quote_repriced || !recheck.policy_rechecked ||
      !recheck.portfolio_reconciled || !recheck.symbol_spec_unchanged)
      return false;

   if(account.snapshot_id=="" || account.account_fingerprint=="" ||
      account.broker_server!=current.broker_server ||
      account.config_version!=current.config_version ||
      account.valid_until_utc<=now_utc ||
      reconciliation.snapshot_id=="" ||
      reconciliation.account_fingerprint!=account.account_fingerprint ||
      reconciliation.broker_server!=account.broker_server ||
      reconciliation.config_version!=current.config_version)
      {
       decision.reason_code="RISK_RELEASE_RUNTIME_IDENTITY_MISMATCH";
       return false;
      }

   if(recheck.account_id=="" || recheck.reconciliation_fingerprint=="" ||
      recheck.quote_fingerprint=="" || recheck.portfolio_fingerprint=="" ||
      recheck.release_reference=="" || recheck.checked_at_utc<=0 ||
      recheck.checked_at_utc>now_utc || recheck.expires_at_utc<=now_utc ||
      recheck.expires_at_utc>account.valid_until_utc ||
      recheck.expires_at_utc>reconciliation.valid_until_utc)
      {
       decision.reason_code="RISK_RELEASE_LINEAGE_INCOMPLETE";
       return false;
      }

   decision.decision_status="RISK_APPROVED";
   decision.release_status="RELEASED";
   decision.decision_id="RISK-"+fresh.candidate_id+"-"+IntegerToString((long)recheck.checked_at_utc);
   decision.candidate_id=fresh.candidate_id;
   decision.setup_id=current.candidate.setup_id;
   decision.policy_id=current.headroom.policy_id;
   decision.policy_version=current.config_version;
   decision.account_id=recheck.account_id;
   decision.account_snapshot_id=account.snapshot_id;
   decision.account_fingerprint=account.account_fingerprint;
   decision.reconciliation_id=reconciliation.snapshot_id;
   decision.reconciliation_fingerprint=recheck.reconciliation_fingerprint;
   decision.symbol=current.canonical_symbol;
   decision.symbol_spec_fingerprint=current.symbol.metadata_fingerprint;
   decision.quote_id=current.economics_input.pricing_snapshot_id;
   decision.quote_snapshot_id=current.economics_input.pricing_snapshot_id;
   decision.quote_fingerprint=recheck.quote_fingerprint;
   decision.portfolio_snapshot_id=current.portfolio_snapshot_id;
   decision.portfolio_fingerprint=recheck.portfolio_fingerprint;
   decision.final_volume=fresh.final_volume;
   decision.risk_budget=current.volume_input.risk_budget;
   decision.projected_loss=fresh.projected_loss;
   decision.net_reward_risk=fresh.net_reward_risk;
   decision.available_headroom=current.headroom.available_headroom;
   decision.direction=current.economics_input.direction;
   decision.entry_reference=current.economics_input.entry_reference;
   decision.stop_loss=current.economics_input.stop_loss;
   decision.take_profit=current.economics_input.take_profit;
   decision.decided_at_utc=recheck.checked_at_utc;
   decision.expires_at_utc=recheck.expires_at_utc;
   decision.reason_code="RISK_RELEASE_RECHECKS_PASSED";
   decision.secondary_reason_code=recheck.release_reference;
   return EEA_RiskDecisionValidForRelease(decision,now_utc);
  }

#endif
