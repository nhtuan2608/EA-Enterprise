#ifndef ENTERPRISE_EA_LEDGER_CHECKPOINT_MQH
#define ENTERPRISE_EA_LEDGER_CHECKPOINT_MQH

#include "../Risk/DailyResetLedger.mqh"
#include "../Risk/AccountRiskLedger.mqh"

#define EEA_LEDGER_CHECKPOINT_VERSION "ledger-checkpoint-v1.0.0"

struct EEA_LedgerCheckpoint
  {
   string schema_version;
   string integrity_marker;
   string fingerprint;
   string recomputed_fingerprint; // Supplied by a trusted serializer/adapter
   string config_version;
   string account_epoch_id;
   string account_id;
   string broker_server;
   string account_currency;
   long checkpoint_sequence;
   datetime captured_at_utc;
   int max_age_seconds;
   string daily_snapshot_id;
   string risk_source_snapshot_id;
   string risk_content_fingerprint;
   // Daily reset ledger payload
   string policy_id;
   double initial_capital;
   string reset_status;
   string reset_reason_code;
   string prague_day_id;
   int day_index;
   datetime reset_at_utc;
   double balance_at_reset;
   double highest_reset_balance;
   double daily_floor;
   double overall_floor;
   // Account risk ledger aggregate payload
   string account_mode;
   bool reconciliation_valid;
   bool new_entries_blocked;
   bool protect_existing_positions;
   string risk_status;
   datetime risk_captured_at_utc;
   long risk_event_sequence;
   long deal_watermark;
   int position_count;
   int working_order_count;
   int deal_count;
   double initial_risk_money;
   double projected_loss_to_sl_money;
   double remaining_loss_to_sl_money;
   double floating_pnl_after_costs;
   double locked_profit_money;
   double equity_after_costs;
   double equity_floor_headroom_money;
   double floor_headroom_after_ledger_risk_money;
  };

struct EEA_CheckpointRestoreGuard
  {
   long last_sequence;
   string last_fingerprint;
   bool initialized;
  };

void EEA_CheckpointGuardDefaults(EEA_CheckpointRestoreGuard &g)
  {
   g.last_sequence=0;
   g.last_fingerprint="";
   g.initialized=false;
  }

void EEA_CheckpointFailClosed(EEA_DailyResetState &daily,
                              EEA_AccountRiskLedger &risk,
                              const string reason)
  {
   daily.status="UNKNOWN";
   daily.reason_code=reason;
   EEA_LedgerMarkUnknown(risk,reason,"CHECKPOINT_REJECTED");
  }

bool EEA_RestoreLedgerCheckpoint(const EEA_LedgerCheckpoint &c,
                                 const string expected_config_version,
                                 const string expected_account_epoch_id,
                                 const string expected_account_id,
                                 const string expected_broker_server,
                                 const string expected_currency,
                                 const datetime now_utc,
                                 EEA_CheckpointRestoreGuard &guard,
                                 EEA_DailyResetState &daily,
                                 EEA_AccountRiskLedger &risk,
                                 string &result)
  {
   result="CHECKPOINT_INCOMPATIBLE";
   if(c.schema_version!=EEA_LEDGER_CHECKPOINT_VERSION || c.integrity_marker!="CHECKPOINT_OK" ||
      c.fingerprint=="" || c.fingerprint!=c.recomputed_fingerprint ||
      c.config_version=="" || c.config_version!=expected_config_version ||
      c.account_epoch_id=="" || c.account_epoch_id!=expected_account_epoch_id ||
      c.account_id=="" || c.account_id!=expected_account_id ||
      c.broker_server=="" || c.broker_server!=expected_broker_server ||
      c.account_currency=="" || c.account_currency!=expected_currency ||
      c.checkpoint_sequence<=0 || c.captured_at_utc<=0 || c.max_age_seconds<=0 ||
      now_utc<c.captured_at_utc || (now_utc-c.captured_at_utc)>c.max_age_seconds ||
      c.daily_snapshot_id=="" || c.risk_source_snapshot_id=="" ||
      c.risk_content_fingerprint=="" || c.policy_id=="" ||
      c.reset_status!="OK" || c.day_index<0 || c.prague_day_id=="" || c.reset_at_utc<=0 ||
      c.reset_at_utc>c.captured_at_utc ||
      (c.policy_id!="FTMO_1_STEP" && c.policy_id!="FTMO_2_STEP" && c.policy_id!="CUSTOM") ||
      !MathIsValidNumber(c.initial_capital) || c.initial_capital<=0.0 ||
      !MathIsValidNumber(c.balance_at_reset) || !MathIsValidNumber(c.highest_reset_balance) ||
      !MathIsValidNumber(c.daily_floor) || !MathIsValidNumber(c.overall_floor) ||
      (c.account_mode!="HEDGING" && c.account_mode!="NETTING") ||
      !c.reconciliation_valid || c.new_entries_blocked!=(c.floor_headroom_after_ledger_risk_money<=0.0) ||
      !c.protect_existing_positions || c.risk_status!="RECONCILED" ||
      c.risk_captured_at_utc<=0 || c.risk_captured_at_utc>c.captured_at_utc ||
      c.risk_event_sequence<=0 || c.deal_watermark<0 || c.position_count<0 ||
      c.working_order_count<0 || c.deal_count<0 ||
      !MathIsValidNumber(c.initial_risk_money) || c.initial_risk_money<0.0 ||
      !MathIsValidNumber(c.projected_loss_to_sl_money) || c.projected_loss_to_sl_money<0.0 ||
      !MathIsValidNumber(c.remaining_loss_to_sl_money) || c.remaining_loss_to_sl_money<0.0 ||
      !MathIsValidNumber(c.floating_pnl_after_costs) || !MathIsValidNumber(c.locked_profit_money) ||
      c.locked_profit_money<0.0 || !MathIsValidNumber(c.equity_after_costs) || c.equity_after_costs<=0.0 ||
      !MathIsValidNumber(c.equity_floor_headroom_money) ||
      !MathIsValidNumber(c.floor_headroom_after_ledger_risk_money) ||
      MathAbs((c.equity_floor_headroom_money-c.remaining_loss_to_sl_money)-
              c.floor_headroom_after_ledger_risk_money)>0.0000001)
     {
      result="CHECKPOINT_MISSING_TORN_STALE_OR_INCOMPATIBLE";
      EEA_CheckpointFailClosed(daily,risk,result);
      return false;
     }

   if(guard.initialized)
     {
      if(c.checkpoint_sequence==guard.last_sequence && c.fingerprint==guard.last_fingerprint)
        { result="CHECKPOINT_REPLAY_IGNORED"; return true; }
      if(c.checkpoint_sequence<=guard.last_sequence)
        {
         result="CHECKPOINT_REPLAY_OR_SEQUENCE_REGRESSION";
         EEA_CheckpointFailClosed(daily,risk,result);
         return false;
        }
     }

   daily.policy_id=c.policy_id;
   daily.config_version=c.config_version;
   daily.account_epoch_id=c.account_epoch_id;
   daily.account_currency=c.account_currency;
   daily.initial_capital=c.initial_capital;
   daily.status="UNKNOWN";
   daily.reason_code="CURRENT_PRAGUE_RESET_ATTESTATION_REQUIRED_AFTER_RESTART";
   daily.snapshot_id=c.daily_snapshot_id;
   daily.prague_day_id=c.prague_day_id;
   daily.day_index=c.day_index;
   daily.reset_at_utc=c.reset_at_utc;
   daily.balance_at_reset=c.balance_at_reset;
   daily.highest_reset_balance=c.highest_reset_balance;
   daily.daily_floor=c.daily_floor;
   daily.overall_floor=c.overall_floor;

   risk.initialized=true;
   risk.reconciliation_valid=false;
   risk.new_entries_blocked=true;
   risk.protect_existing_positions=true;
   risk.ledger_status="POLICY_DATA_UNKNOWN";
   risk.last_transition="RESTORED_PENDING_RECONCILIATION";
   risk.reason_code="CURRENT_RESET_AND_BROKER_RECONCILIATION_REQUIRED_AFTER_RESTART";
   risk.config_version=c.config_version;
   risk.account_id=c.account_id;
   risk.broker_server=c.broker_server;
   risk.account_currency=c.account_currency;
   risk.account_mode=c.account_mode;
   risk.last_event_id="RESTORED";
   risk.last_snapshot_id=c.risk_source_snapshot_id;
   risk.last_content_fingerprint=c.risk_content_fingerprint;
   risk.last_captured_at_utc=c.risk_captured_at_utc;
   risk.last_event_sequence=c.risk_event_sequence;
   risk.last_deal_watermark=c.deal_watermark;
   risk.position_count=c.position_count;
   risk.working_order_count=c.working_order_count;
   risk.deal_count=c.deal_count;
   risk.initial_risk_money=c.initial_risk_money;
   risk.projected_loss_to_sl_money=c.projected_loss_to_sl_money;
   risk.remaining_loss_to_sl_money=c.remaining_loss_to_sl_money;
   risk.floating_pnl_after_costs=c.floating_pnl_after_costs;
   risk.locked_profit_money=c.locked_profit_money;
   risk.equity_after_costs=c.equity_after_costs;
   risk.equity_floor_headroom_money=c.equity_floor_headroom_money;
   risk.floor_headroom_after_ledger_risk_money=c.floor_headroom_after_ledger_risk_money;
   guard.initialized=true;
   guard.last_sequence=c.checkpoint_sequence;
   guard.last_fingerprint=c.fingerprint;
   result="CHECKPOINT_RESTORED_PENDING_RESET_AND_BROKER_RECONCILIATION";
   return true;
  }

// Caller must independently attest the current Prague day and re-read the
// reset source. A persisted snapshot alone cannot satisfy this check.
bool EEA_ReattestRestoredDailyReset(EEA_DailyResetState &daily,
                                    const EEA_DailyResetInput &fresh,
                                    const string current_prague_day_id)
  {
   if(daily.status!="UNKNOWN" ||
      (daily.reason_code!="CURRENT_PRAGUE_RESET_ATTESTATION_REQUIRED_AFTER_RESTART" &&
       daily.reason_code!="CURRENT_PRAGUE_RESET_REATTESTATION_FAILED"))
      return false;
   if(current_prague_day_id=="" || fresh.prague_day_id!=current_prague_day_id ||
      fresh.config_version!=daily.config_version ||
      fresh.account_epoch_id!=daily.account_epoch_id ||
      fresh.account_currency!=daily.account_currency ||
      fresh.snapshot_id!=daily.snapshot_id || fresh.day_index!=daily.day_index ||
      fresh.reset_at_utc!=daily.reset_at_utc ||
      fresh.balance_at_reset!=daily.balance_at_reset ||
      !fresh.prague_midnight_confirmed || fresh.data_quality!="OK")
     {
      daily.status="UNKNOWN";
      daily.reason_code="CURRENT_PRAGUE_RESET_REATTESTATION_FAILED";
      return false;
     }
   daily.status="OK";
   daily.reason_code="CURRENT_PRAGUE_RESET_REATTESTED";
   return true;
  }

#endif
