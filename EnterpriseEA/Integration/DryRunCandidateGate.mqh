#ifndef ENTERPRISE_EA_DRY_RUN_CANDIDATE_GATE_MQH
#define ENTERPRISE_EA_DRY_RUN_CANDIDATE_GATE_MQH

#include "..\Setups\BreakRetest.mqh"
#include "..\Market\SymbolRegistry.mqh"
#include "..\Risk\StructuralLevels.mqh"
#include "..\Risk\TradeEconomics.mqh"
#include "..\Risk\FtmoHeadroom.mqh"
#include "..\Risk\PortfolioBudget.mqh"
#include "..\Risk\VolumeSizing.mqh"

#define EEA_DRYRUN_STAGE_COUNT 7
#define EEA_DRYRUN_MAX_REASONS 16

enum ENUM_EEA_DRYRUN_EVIDENCE_STAGE
  {
   EEA_DRYRUN_EVIDENCE_SYMBOL=0,
   EEA_DRYRUN_EVIDENCE_CANDIDATE=1,
   EEA_DRYRUN_EVIDENCE_LEVELS=2,
   EEA_DRYRUN_EVIDENCE_ECONOMICS=3,
   EEA_DRYRUN_EVIDENCE_FTMO=4,
   EEA_DRYRUN_EVIDENCE_PORTFOLIO=5,
   EEA_DRYRUN_EVIDENCE_VOLUME=6
  };

struct EEA_DryRunEvidence
  {
   int stage;
   string quality;               // OK required
   string config_version;        // Shared run/config bundle version
   string source_version;        // Component-specific version
   string account_currency;
   string canonical_symbol;
   string broker_symbol;
   string broker_server;
   string source_snapshot_id;    // Nonempty immutable source/event/snapshot identifier
   datetime captured_at_utc;
   int max_age_seconds;
  };

struct EEA_DryRunContext
  {
   string config_version;
   string setup_config_version;
   string account_currency;
   string canonical_symbol;
   string broker_symbol;
   string broker_server;
   string levels_snapshot_id;
   string portfolio_snapshot_id;
   string volume_quote_snapshot_id;
   datetime evaluated_at_utc;
   EEA_SymbolResolution symbol;
   EEA_S02Candidate candidate;
   EEA_StructuralLevels levels;
   EEA_TradeEconomicsInput economics_input;
   EEA_TradeEconomicsResult economics;
   EEA_FtmoHeadroom headroom;
   EEA_PortfolioBudgetInputs portfolio_input;
   EEA_PortfolioBudgetResult portfolio;
   EEA_VolumeSizingInput volume_input;
   EEA_VolumeSizingResult sizing;
  };

struct EEA_DryRunDecision
  {
   bool evaluated;
   string decision_status;       // UNKNOWN | BLOCKED | REJECTED | REVIEWABLE_CANDIDATE
   int reason_count;
   string reason_codes[EEA_DRYRUN_MAX_REASONS];
   string candidate_id;
   double final_volume;
   double projected_loss;
   double net_reward_risk;
  };

void EEA_DryRunDecisionDefaults(EEA_DryRunDecision &o)
  {
   o.evaluated=false;
   o.decision_status="UNKNOWN";
   o.reason_count=0;
   for(int n=0;n<EEA_DRYRUN_MAX_REASONS;n++) o.reason_codes[n]="";
   o.candidate_id="";
   o.final_volume=0.0;
   o.projected_loss=0.0;
   o.net_reward_risk=0.0;
  }

void EEA_DryRunAddReason(EEA_DryRunDecision &o,const string code)
  {
   if(o.reason_count<EEA_DRYRUN_MAX_REASONS)
     {
      o.reason_codes[o.reason_count]=code;
      o.reason_count++;
     }
  }

string EEA_DryRunEvidenceMissingCode(const int stage)
  {
   if(stage==EEA_DRYRUN_EVIDENCE_SYMBOL) return "SYMBOL_EVIDENCE_MISSING_OR_DUPLICATE";
   if(stage==EEA_DRYRUN_EVIDENCE_CANDIDATE) return "CANDIDATE_EVIDENCE_MISSING_OR_DUPLICATE";
   if(stage==EEA_DRYRUN_EVIDENCE_LEVELS) return "LEVELS_EVIDENCE_MISSING_OR_DUPLICATE";
   if(stage==EEA_DRYRUN_EVIDENCE_ECONOMICS) return "ECONOMICS_EVIDENCE_MISSING_OR_DUPLICATE";
   if(stage==EEA_DRYRUN_EVIDENCE_FTMO) return "FTMO_EVIDENCE_MISSING_OR_DUPLICATE";
   if(stage==EEA_DRYRUN_EVIDENCE_PORTFOLIO) return "PORTFOLIO_EVIDENCE_MISSING_OR_DUPLICATE";
   return "VOLUME_EVIDENCE_MISSING_OR_DUPLICATE";
  }

int EEA_DryRunFindEvidence(const int stage,const EEA_DryRunEvidence &evidence[],int &matches)
  {
   int found=-1;
   matches=0;
   for(int n=0;n<ArraySize(evidence);n++)
      if(evidence[n].stage==stage) { found=n; matches++; }
   return found;
  }

bool EEA_DryRunNearlyEqual(const double a,const double b)
  {
   if(!MathIsValidNumber(a) || !MathIsValidNumber(b)) return false;
   double scale=MathMax(1.0,MathMax(MathAbs(a),MathAbs(b)));
   return MathAbs(a-b)<=scale*1e-9;
  }

bool EEA_EvaluateDryRunCandidate(const EEA_DryRunContext &i,
                                 const EEA_DryRunEvidence &evidence[],
                                 EEA_DryRunDecision &o)
  {
   EEA_DryRunDecisionDefaults(o);

   if(i.config_version=="" || i.setup_config_version=="" || i.account_currency=="" ||
      i.canonical_symbol=="" || i.broker_symbol=="" || i.broker_server=="" ||
      i.levels_snapshot_id=="" || i.portfolio_snapshot_id=="" || i.volume_quote_snapshot_id=="" ||
      i.evaluated_at_utc<=0)
     {
      EEA_DryRunAddReason(o,"DRY_RUN_CONTEXT_INCOMPLETE");
      o.decision_status="UNKNOWN";
      o.evaluated=true;
      return false;
     }

   // 1. Evidence/freshness and common identity checks in fixed stage order.
   if(ArraySize(evidence)!=EEA_DRYRUN_STAGE_COUNT)
     {
      EEA_DryRunAddReason(o,"EVIDENCE_STAGE_SET_INVALID");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   for(int n=0;n<ArraySize(evidence);n++)
      if(evidence[n].stage<EEA_DRYRUN_EVIDENCE_SYMBOL || evidence[n].stage>EEA_DRYRUN_EVIDENCE_VOLUME)
        {
         EEA_DryRunAddReason(o,"EVIDENCE_STAGE_SET_INVALID");
         o.decision_status="UNKNOWN"; o.evaluated=true; return false;
        }
   int stage_failures=0;
   int blocked_failures=0;
   for(int stage=0;stage<EEA_DRYRUN_STAGE_COUNT;stage++)
     {
      int matches=0;
      int index=EEA_DryRunFindEvidence(stage,evidence,matches);
      if(matches!=1)
        {
         EEA_DryRunAddReason(o,EEA_DryRunEvidenceMissingCode(stage));
         stage_failures++;
         continue;
        }
      EEA_DryRunEvidence ev=evidence[index];
      if(ev.quality!="OK" || ev.source_version=="" || ev.source_snapshot_id=="" ||
         ev.captured_at_utc<=0 || ev.max_age_seconds<=0 ||
         (i.evaluated_at_utc-ev.captured_at_utc)<0 ||
         (i.evaluated_at_utc-ev.captured_at_utc)>ev.max_age_seconds)
        {
         EEA_DryRunAddReason(o,"EVIDENCE_STALE_OR_INCOMPLETE");
         stage_failures++;
         continue;
        }
      if(ev.config_version!=i.config_version || ev.account_currency!=i.account_currency ||
         ev.canonical_symbol!=i.canonical_symbol || ev.broker_symbol!=i.broker_symbol ||
         ev.broker_server!=i.broker_server)
        {
         EEA_DryRunAddReason(o,"EVIDENCE_BINDING_MISMATCH");
         stage_failures++;
         blocked_failures++;
        }
     }
   if(stage_failures>0)
     {
      o.decision_status=(blocked_failures>0 ? "BLOCKED" : "UNKNOWN");
      o.evaluated=true;
      return false;
     }

   // 2. Explicit symbol mapping and current broker/server metadata.
   if(!i.symbol.resolved || i.symbol.status!="RESOLVED" ||
      i.symbol.canonical_symbol!=i.canonical_symbol || i.symbol.broker_symbol!=i.broker_symbol ||
      i.symbol.broker_server!=i.broker_server || i.symbol.source_version=="" ||
      i.symbol.metadata_version=="" || i.symbol.metadata_fingerprint=="")
     {
      EEA_DryRunAddReason(o,"SYMBOL_MAPPING_NOT_RESOLVED_OR_STALE");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   int ev_matches=0;
   int ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_SYMBOL,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.symbol.source_version ||
      evidence[ev_index].source_snapshot_id!=i.symbol.metadata_fingerprint)
     {
      EEA_DryRunAddReason(o,"SYMBOL_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 3. S02 candidate must still be a fresh triggered candidate for this identity/config.
   if(i.candidate.canonical_symbol!=i.canonical_symbol ||
      i.candidate.config_version!=i.setup_config_version)
     {
      EEA_DryRunAddReason(o,"CANDIDATE_IDENTITY_OR_CONFIG_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   o.candidate_id=i.candidate.candidate_id;
   if(i.candidate.state!="TRIGGERED" || (i.candidate.setup_id!="S02" && i.candidate.setup_id!="S04" && i.candidate.setup_id!="S06") ||
      i.candidate.candidate_id=="" || i.candidate.timeframe=="" ||
      i.candidate.expires_after_bars<=0 || i.candidate.age_after_trigger_bars<0 ||
      i.candidate.age_after_trigger_bars>=i.candidate.expires_after_bars ||
      (i.candidate.direction!="LONG" && i.candidate.direction!="SHORT"))
     {
      EEA_DryRunAddReason(o,"CANDIDATE_NOT_FRESH_TRIGGERED_S02");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_CANDIDATE,evidence,ev_matches);
   if(evidence[ev_index].captured_at_utc<i.candidate.triggered_at_utc)
     {
      EEA_DryRunAddReason(o,"CANDIDATE_EVIDENCE_PREDATES_TRIGGER");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   if(evidence[ev_index].source_version!=i.candidate.config_version ||
      evidence[ev_index].source_snapshot_id!=i.candidate.candidate_id)
     {
      EEA_DryRunAddReason(o,"CANDIDATE_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   if(i.candidate.triggered_at_utc<=0 || i.candidate.triggered_at_utc>i.evaluated_at_utc ||
      (i.evaluated_at_utc-i.candidate.triggered_at_utc)>evidence[ev_index].max_age_seconds)
     {
      EEA_DryRunAddReason(o,"CANDIDATE_TRIGGER_STALE_OR_INVALID");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   if((i.economics_input.direction!=1 && i.economics_input.direction!=-1) ||
      i.candidate.direction!= (i.economics_input.direction==1 ? "LONG" : "SHORT"))
     {
      EEA_DryRunAddReason(o,"CANDIDATE_DIRECTION_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 4. Structural levels are a valid proposal and must match the priced economics input.
   if(!i.levels.valid || i.levels.stop_loss<=0.0 || i.levels.take_profit<=0.0 ||
      !EEA_DryRunNearlyEqual(i.levels.stop_loss,i.economics_input.stop_loss) ||
      !EEA_DryRunNearlyEqual(i.levels.take_profit,i.economics_input.take_profit))
     {
      EEA_DryRunAddReason(o,"STRUCTURAL_LEVELS_INVALID_OR_MISMATCHED");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_LEVELS,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.setup_config_version ||
      evidence[ev_index].source_snapshot_id!=i.levels_snapshot_id)
     {
      EEA_DryRunAddReason(o,"LEVELS_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 5. Net economics and execution constraints must have passed.
   if(i.economics_input.config_version!=i.config_version ||
      i.economics_input.account_currency!=i.account_currency ||
      i.economics_input.quote_config_version!=i.config_version ||
      i.economics_input.quote_currency!=i.account_currency || i.economics_input.pricing_snapshot_id=="" ||
      i.economics_input.quote_quality!="OK" || !i.economics_input.target_space_confirmed ||
      !i.economics_input.execution_constraints_confirmed)
     {
      EEA_DryRunAddReason(o,"ECONOMICS_CONFIG_CURRENCY_OR_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED";
      o.evaluated=true; return false;
     }
   if(!i.economics.valid || i.economics.economics_status=="UNKNOWN")
     {
      EEA_DryRunAddReason(o,"TRADE_ECONOMICS_UNKNOWN");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   if(!MathIsValidNumber(i.economics_input.final_volume) || i.economics_input.final_volume<=0.0 ||
      !MathIsValidNumber(i.economics_input.net_loss_at_sl_money) ||
      i.economics_input.net_loss_at_sl_money<=0.0 ||
      !MathIsValidNumber(i.economics_input.net_gain_at_tp_money) ||
      i.economics_input.net_gain_at_tp_money<=0.0 ||
      !MathIsValidNumber(i.economics_input.minimum_net_rr) ||
      i.economics_input.minimum_net_rr<=0.0 ||
      !MathIsValidNumber(i.economics.net_reward_risk) ||
      !MathIsValidNumber(i.economics.net_loss_at_sl_money) || i.economics.net_loss_at_sl_money<=0.0 ||
      !MathIsValidNumber(i.economics.net_gain_at_tp_money) || i.economics.net_gain_at_tp_money<=0.0)
     {
      EEA_DryRunAddReason(o,"ECONOMICS_FINAL_VOLUME_OR_LOSS_INVALID");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   if(!EEA_DryRunNearlyEqual(i.economics_input.quote_volume,i.economics_input.final_volume) ||
      !EEA_DryRunNearlyEqual(i.economics.net_reward_risk,
         i.economics_input.net_gain_at_tp_money/i.economics_input.net_loss_at_sl_money) ||
      !EEA_DryRunNearlyEqual(i.economics.net_loss_at_sl_money,i.economics_input.net_loss_at_sl_money) ||
      !EEA_DryRunNearlyEqual(i.economics.net_gain_at_tp_money,i.economics_input.net_gain_at_tp_money) ||
      (i.economics.economics_status=="ECONOMICS_ACCEPTABLE" &&
       i.economics.net_reward_risk<i.economics_input.minimum_net_rr))
     {
      EEA_DryRunAddReason(o,"ECONOMICS_RESULT_INPUT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   if(i.economics.economics_status!="ECONOMICS_ACCEPTABLE")
     {
      EEA_DryRunAddReason(o,"TRADE_ECONOMICS_REJECTED");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_ECONOMICS,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.economics_input.quote_config_version ||
      evidence[ev_index].source_snapshot_id!=i.economics_input.pricing_snapshot_id)
     {
      EEA_DryRunAddReason(o,"ECONOMICS_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 6. Policy floor calculation is a necessary local check, never final permission.
   if(i.headroom.config_version!=i.config_version || i.headroom.snapshot_id=="")
     {
      EEA_DryRunAddReason(o,"FTMO_CONFIG_OR_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED";
      o.evaluated=true; return false;
     }
   if(!i.headroom.calculation_valid || i.headroom.calculation_status!="OK" ||
      i.headroom.headroom_status=="POLICY_DATA_UNKNOWN" ||
      !MathIsValidNumber(i.headroom.proposed_stress_loss) || i.headroom.proposed_stress_loss<=0.0 ||
      !MathIsValidNumber(i.headroom.available_headroom) || i.headroom.available_headroom<=0.0)
     {
      EEA_DryRunAddReason(o,"FTMO_HEADROOM_UNKNOWN");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   if(i.headroom.headroom_status!="SUFFICIENT")
     {
      EEA_DryRunAddReason(o,"FTMO_HEADROOM_INSUFFICIENT");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_FTMO,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.headroom.source_version ||
      evidence[ev_index].source_snapshot_id!=i.headroom.snapshot_id)
     {
      EEA_DryRunAddReason(o,"FTMO_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 7. Account-wide reconciliation/budget evidence must pass before final sizing review.
   if(i.portfolio_input.config_version!=i.config_version ||
      i.portfolio_input.account_currency!=i.account_currency ||
      i.portfolio_input.policy_config_version!=i.config_version ||
      i.portfolio_input.policy_headroom_currency!=i.account_currency ||
      !EEA_DryRunNearlyEqual(i.portfolio_input.policy_headroom_after_buffer_money,
                             i.headroom.available_headroom))
     {
      EEA_DryRunAddReason(o,"PORTFOLIO_CONFIG_CURRENCY_OR_HEADROOM_MISMATCH");
      o.decision_status="BLOCKED";
      o.evaluated=true; return false;
     }
   if(!i.portfolio.valid || i.portfolio.budget_status=="UNKNOWN" ||
      !MathIsValidNumber(i.portfolio.budget_money) || i.portfolio.budget_money<=0.0 ||
      i.portfolio_input.data_quality!="OK" || i.portfolio_input.account_scope!="ACCOUNT_WIDE" ||
      i.portfolio_input.reconciliation_status!="RECONCILED" ||
      !i.portfolio_input.external_orders_included || !i.portfolio_input.account_mode_reconciled ||
      !i.portfolio_input.portfolio_limits_confirmed ||
      !i.portfolio_input.policy_floor_calculation_valid ||
      i.portfolio_input.policy_headroom_quality!="OK" ||
      !MathIsValidNumber(i.portfolio_input.existing_stress_loss_money) ||
      i.portfolio_input.existing_stress_loss_money<0.0)
     {
      EEA_DryRunAddReason(o,"ACCOUNT_WIDE_RECONCILIATION_EVIDENCE_UNKNOWN");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   if(i.portfolio.budget_status!="BUDGET_AVAILABLE" || i.portfolio.budget_money<=0.0)
     {
      EEA_DryRunAddReason(o,"ACCOUNT_WIDE_BUDGET_REJECTED");
      o.decision_status="REJECTED"; o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_PORTFOLIO,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.portfolio_input.config_version ||
      evidence[ev_index].source_snapshot_id!=i.portfolio_snapshot_id)
     {
      EEA_DryRunAddReason(o,"PORTFOLIO_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   // 8. Final rounded volume/loss/margin quotes must align across all calculations.
   if(i.volume_input.config_version!=i.config_version ||
      i.volume_input.account_currency!=i.account_currency)
     {
      EEA_DryRunAddReason(o,"VOLUME_CONFIG_OR_CURRENCY_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }
   if(!i.sizing.valid || i.sizing.sizing_status!="SIZED")
     {
      EEA_DryRunAddReason(o,"VOLUME_SIZING_UNKNOWN_OR_REJECTED");
      o.decision_status=(i.sizing.sizing_status=="BLOCKED" ? "REJECTED" : "UNKNOWN");
      o.evaluated=true; return false;
     }
   if(!i.volume_input.loss_quote_valid || i.volume_input.loss_quote_quality!="OK" ||
      i.volume_input.loss_quote_version!=i.config_version ||
      i.volume_input.loss_quote_currency!=i.account_currency ||
      !i.volume_input.final_loss_quote_valid || i.volume_input.final_loss_quote_quality!="OK" ||
      i.volume_input.final_loss_quote_version!=i.config_version ||
      i.volume_input.final_loss_quote_currency!=i.account_currency ||
      !i.volume_input.margin_quote_valid || i.volume_input.margin_quote_quality!="OK" ||
      i.volume_input.margin_quote_version!=i.config_version ||
      i.volume_input.margin_quote_currency!=i.account_currency ||
      !MathIsValidNumber(i.sizing.required_margin) || !MathIsValidNumber(i.sizing.available_margin) ||
      i.sizing.required_margin>i.sizing.available_margin)
     {
      EEA_DryRunAddReason(o,"VOLUME_OR_MARGIN_QUOTE_EVIDENCE_INVALID");
      o.decision_status="UNKNOWN"; o.evaluated=true; return false;
     }
   if(!MathIsValidNumber(i.sizing.volume) || i.sizing.volume<=0.0 ||
      !MathIsValidNumber(i.sizing.projected_loss) || i.sizing.projected_loss<=0.0 ||
      i.volume_input.risk_budget<=0.0 || i.volume_input.risk_budget>i.portfolio.budget_money ||
      !EEA_DryRunNearlyEqual(i.economics_input.final_volume,i.sizing.volume) ||
      !EEA_DryRunNearlyEqual(i.sizing.volume,i.volume_input.final_loss_quote_volume) ||
      !EEA_DryRunNearlyEqual(i.sizing.volume,i.volume_input.margin_quote_volume) ||
      !EEA_DryRunNearlyEqual(i.sizing.projected_loss,i.economics_input.net_loss_at_sl_money) ||
      !EEA_DryRunNearlyEqual(i.sizing.projected_loss,i.headroom.proposed_stress_loss) ||
      i.sizing.projected_loss>i.volume_input.risk_budget ||
      i.sizing.projected_loss>i.portfolio.budget_money ||
      i.portfolio_input.existing_stress_loss_money+i.sizing.projected_loss>
      i.headroom.available_headroom)
     {
      EEA_DryRunAddReason(o,"FINAL_VOLUME_LOSS_BUDGET_OR_STRESS_MISMATCH");
      o.decision_status=(i.sizing.valid ? "BLOCKED" : "UNKNOWN");
      o.evaluated=true; return false;
     }
   ev_index=EEA_DryRunFindEvidence(EEA_DRYRUN_EVIDENCE_VOLUME,evidence,ev_matches);
   if(evidence[ev_index].source_version!=i.volume_input.config_version ||
      evidence[ev_index].source_snapshot_id!=i.volume_quote_snapshot_id)
     {
      EEA_DryRunAddReason(o,"VOLUME_SOURCE_SNAPSHOT_MISMATCH");
      o.decision_status="BLOCKED"; o.evaluated=true; return false;
     }

   o.decision_status="REVIEWABLE_CANDIDATE";
   o.final_volume=i.sizing.volume;
   o.projected_loss=i.sizing.projected_loss;
   o.net_reward_risk=i.economics.net_reward_risk;
   EEA_DryRunAddReason(o,"ALL_OFFLINE_GATES_PASSED_FOR_REVIEW_ONLY");
   o.evaluated=true;
   return true;
  }

#endif
