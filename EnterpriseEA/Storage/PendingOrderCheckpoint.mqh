#ifndef ENTERPRISE_EA_PENDING_ORDER_CHECKPOINT_MQH
#define ENTERPRISE_EA_PENDING_ORDER_CHECKPOINT_MQH

#include "PendingOrderAudit.mqh"

#define EEA_PENDING_CHECKPOINT_VERSION "pending-order-checkpoint-v1.1.0"

// In-memory contract only. A trusted serializer must calculate and verify
// fingerprint/recomputed_fingerprint over the full envelope except fingerprint
// fields, including schema, marker, sequence, capture time, max age and state.
// This module does no file or broker I/O.
struct EEA_PendingOrderCheckpoint
  {
   string schema_version;
   string integrity_marker;
   string fingerprint;
   string recomputed_fingerprint;
   long checkpoint_sequence;
   datetime captured_at_utc;
   int max_age_seconds;
   long audit_sequence;
   string audit_fingerprint;
   string audit_event_id;
   datetime audit_observed_at_utc;
   EEA_PendingState state;
  };

struct EEA_PendingCheckpointGuard
  {
   bool initialized;
   long last_sequence;
   string last_fingerprint;
   bool audit_tail_verified;
  };

void EEA_PendingCheckpointGuardDefaults(EEA_PendingCheckpointGuard &g)
  {
   g.initialized=false;
   g.last_sequence=0;
   g.last_fingerprint="";
   g.audit_tail_verified=false;
  }

void EEA_PendingCheckpointFailClosed(EEA_PendingState &s,
                                     const string reason)
  {
   if(!s.initialized)
      EEA_PendingDefaults(s);
   EEA_PendingMarkUnknown(s,reason);
  }

bool EEA_PendingCheckpointPayloadValid(const EEA_PendingState &p,
                                        const datetime captured_at_utc)
  {
   if(!p.initialized || p.intent_id=="" || p.candidate_id=="" ||
      p.setup_id=="" || p.setup_version=="" || p.config_version=="" ||
      p.instrument_version=="" || p.canonical_symbol=="" ||
      p.account_currency=="" || p.broker_server=="" ||
      p.account_fingerprint=="" || p.order_ticket=="" ||
      (p.trade_style!="SCALP" && p.trade_style!="SWING") ||
      (p.order_type!="BUY_LIMIT" && p.order_type!="SELL_LIMIT" &&
       p.order_type!="BUY_STOP" && p.order_type!="SELL_STOP") ||
      (p.status!="WORKING" && p.status!="PARTIAL" &&
       p.status!="CANCEL_REQUIRED" && p.status!="CANCEL_REQUESTED" &&
       p.status!="FILLED" && p.status!="CANCELLED" &&
       p.status!="EXPIRED" && p.status!="BREACH_REVIEW" &&
       p.status!="PENDING_RACE_UNKNOWN") ||
      p.broker_accepted_at_utc<=0 ||
      p.effective_expires_at_utc<=p.broker_accepted_at_utc ||
      captured_at_utc<p.broker_accepted_at_utc ||
      p.max_wait_closed_bars<=0 || p.bars_waited<0 ||
      p.last_closed_bar_sequence<p.bars_waited ||
      p.last_bar_closed_at_utc>captured_at_utc ||
      p.last_guard_at_utc>captured_at_utc ||
      p.last_event_at_utc<p.broker_accepted_at_utc ||
      p.last_event_at_utc>captured_at_utc ||
      p.cancel_required_at_utc>captured_at_utc ||
      p.cancel_requested_at_utc>captured_at_utc ||
      p.broker_confirmed_at_utc>captured_at_utc ||
      p.last_event_sequence<0 ||
      (p.last_event_sequence==0 &&
       (p.last_event_id!="" || p.last_event_fingerprint!="")) ||
      (p.last_event_sequence>0 &&
       (p.last_event_id=="" || p.last_event_fingerprint=="")) ||
      (p.bars_waited>0 &&
       (p.last_bar_closed_at_utc<=p.broker_accepted_at_utc ||
        p.last_bar_fingerprint=="" || p.last_setup_snapshot_id=="")) ||
      (p.last_guard_at_utc>0 &&
       (p.last_guard_snapshot_id=="" || p.last_guard_fingerprint=="")) ||
      !EEA_PendingVolumeAligned(p.requested_volume,p.volume_step) ||
      !EEA_PendingPositive(p.reserved_risk_per_lot_money) ||
      !EEA_PendingPositive(p.max_committed_risk_money) ||
      !MathIsValidNumber(p.filled_volume) || p.filled_volume<0.0 ||
      !MathIsValidNumber(p.cancelled_volume) || p.cancelled_volume<0.0 ||
      !MathIsValidNumber(p.remaining_volume) || p.remaining_volume<0.0 ||
      !MathIsValidNumber(p.filled_initial_risk_money) ||
      p.filled_initial_risk_money<0.0 ||
      !MathIsValidNumber(p.remaining_risk_reservation_money) ||
      p.remaining_risk_reservation_money<0.0 ||
      !MathIsValidNumber(p.total_committed_risk_money) ||
      p.total_committed_risk_money<0.0 ||
      MathAbs(p.requested_volume-p.filled_volume-p.cancelled_volume-
              p.remaining_volume)>0.0000001 ||
      MathAbs(p.remaining_risk_reservation_money-
              p.remaining_volume*p.reserved_risk_per_lot_money)>0.0000001 ||
      MathAbs(p.total_committed_risk_money-p.filled_initial_risk_money-
              p.remaining_risk_reservation_money)>0.0000001)
      return false;
   if((p.status=="WORKING" &&
       (p.filled_volume>0.0 || p.cancelled_volume>0.0 ||
        p.remaining_volume<=0.0)) ||
      (p.status=="PARTIAL" &&
       (p.filled_volume<=0.0 || p.remaining_volume<=0.0)) ||
      (p.status=="FILLED" &&
       (p.remaining_volume>0.0 || p.cancelled_volume>0.0)) ||
      ((p.status=="CANCELLED" || p.status=="EXPIRED") &&
       (p.remaining_volume>0.0 || p.cancelled_volume<=0.0 ||
        p.broker_confirmed_at_utc<=0)) ||
      ((p.status=="CANCEL_REQUIRED" || p.status=="CANCEL_REQUESTED") &&
       (p.remaining_volume<=0.0 || p.cancel_required_at_utc<=0)) ||
      (p.status=="CANCEL_REQUESTED" &&
       (p.cancel_requested_at_utc<=0 || p.cancel_correlation_id=="")))
      return false;
   return true;
  }

bool EEA_RestorePendingOrderCheckpoint(const EEA_PendingOrderCheckpoint &c,
                                        const string expected_intent_id,
                                        const string expected_config_version,
                                        const string expected_broker_server,
                                        const string expected_account_fingerprint,
                                        const string expected_order_ticket,
                                        const datetime now_utc,
                                        EEA_PendingCheckpointGuard &guard,
                                        EEA_PendingState &s,
                                        string &result)
  {
   if(c.schema_version!=EEA_PENDING_CHECKPOINT_VERSION ||
      c.integrity_marker!="CHECKPOINT_OK" ||
      c.fingerprint=="" || c.fingerprint!=c.recomputed_fingerprint ||
      c.checkpoint_sequence<=0 || c.captured_at_utc<=0 ||
      c.max_age_seconds<=0 || now_utc<c.captured_at_utc ||
      (now_utc-c.captured_at_utc)>c.max_age_seconds ||
      c.audit_sequence<=0 || c.audit_fingerprint=="" ||
      c.audit_event_id=="" ||
      c.audit_observed_at_utc<c.state.broker_accepted_at_utc ||
      c.audit_observed_at_utc>c.captured_at_utc ||
      expected_intent_id=="" || expected_config_version=="" ||
      expected_broker_server=="" || expected_account_fingerprint=="" ||
      expected_order_ticket=="" ||
      c.state.intent_id!=expected_intent_id ||
      c.state.config_version!=expected_config_version ||
      c.state.broker_server!=expected_broker_server ||
      c.state.account_fingerprint!=expected_account_fingerprint ||
      c.state.order_ticket!=expected_order_ticket ||
      !EEA_PendingCheckpointPayloadValid(c.state,c.captured_at_utc))
     {
      result="PENDING_CHECKPOINT_REJECTED";
      EEA_PendingCheckpointFailClosed(s,result);
      return false;
     }
   if(guard.initialized)
     {
      if(c.checkpoint_sequence==guard.last_sequence &&
         c.fingerprint==guard.last_fingerprint)
        { result="PENDING_CHECKPOINT_REPLAY_IGNORED"; return true; }
      if(c.checkpoint_sequence<=guard.last_sequence)
        {
         result="PENDING_CHECKPOINT_SEQUENCE_REGRESSION";
         EEA_PendingCheckpointFailClosed(s,result);
         return false;
        }
     }
   s=c.state;
   s.status="PENDING_RACE_UNKNOWN";
   s.reason_code="RESTORED_PENDING_BROKER_RECONCILIATION";
   s.new_entries_blocked=true;
   guard.initialized=true;
   guard.last_sequence=c.checkpoint_sequence;
   guard.last_fingerprint=c.fingerprint;
   guard.audit_tail_verified=false;
   result="PENDING_CHECKPOINT_RESTORED_RECONCILIATION_REQUIRED";
   return true;
  }

// Caller must first replay and verify the complete durable audit chain.
// This only binds its final accepted record to the checkpoint envelope.
// Passing does not unblock entries or reconcile broker orders/deals.
bool EEA_VerifyPendingCheckpointAuditTail(const EEA_PendingOrderCheckpoint &c,
                                           const EEA_PendingAuditRecord &tail,
                                           EEA_PendingCheckpointGuard &guard,
                                           EEA_PendingState &s,
                                           string &result)
  {
   if(!guard.initialized || c.checkpoint_sequence!=guard.last_sequence ||
      c.fingerprint!=guard.last_fingerprint ||
      c.fingerprint=="" || c.fingerprint!=c.recomputed_fingerprint ||
      tail.schema_version!=EEA_PENDING_AUDIT_VERSION ||
      tail.audit_sequence!=c.audit_sequence ||
      tail.fingerprint=="" || tail.fingerprint!=tail.recomputed_fingerprint ||
      tail.fingerprint!=c.audit_fingerprint ||
      tail.event_id!=c.audit_event_id ||
      tail.observed_at_utc!=c.audit_observed_at_utc ||
      tail.intent_id!=c.state.intent_id ||
      tail.candidate_id!=c.state.candidate_id ||
      tail.setup_id!=c.state.setup_id ||
      tail.setup_version!=c.state.setup_version ||
      tail.config_version!=c.state.config_version ||
      tail.instrument_version!=c.state.instrument_version ||
      tail.broker_server!=c.state.broker_server ||
      tail.account_fingerprint!=c.state.account_fingerprint ||
      tail.order_ticket!=c.state.order_ticket ||
      tail.state_after!=c.state.status ||
      tail.reason_code!=c.state.reason_code ||
      tail.effective_expires_at_utc!=c.state.effective_expires_at_utc ||
      tail.bars_waited_after!=c.state.bars_waited ||
      tail.broker_event_sequence_after!=c.state.last_event_sequence ||
      !EEA_PendingAuditNear(tail.filled_volume_after,c.state.filled_volume) ||
      !EEA_PendingAuditNear(tail.cancelled_volume_after,c.state.cancelled_volume) ||
      !EEA_PendingAuditNear(tail.remaining_volume_after,c.state.remaining_volume) ||
      !EEA_PendingAuditNear(tail.filled_risk_after,
                            c.state.filled_initial_risk_money) ||
      !EEA_PendingAuditNear(tail.remaining_reservation_after,
                            c.state.remaining_risk_reservation_money) ||
      s.status!="PENDING_RACE_UNKNOWN" ||
      !EEA_PendingAuditNear(s.remaining_volume,c.state.remaining_volume) ||
      !EEA_PendingAuditNear(s.total_committed_risk_money,
                            c.state.total_committed_risk_money))
     {
      guard.audit_tail_verified=false;
      result="PENDING_CHECKPOINT_AUDIT_TAIL_MISMATCH";
      EEA_PendingCheckpointFailClosed(s,result);
      return false;
     }
   guard.audit_tail_verified=true;
   s.new_entries_blocked=true;
   result="PENDING_CHECKPOINT_AUDIT_TAIL_MATCHED_BROKER_RECONCILIATION_REQUIRED";
   return true;
  }

#endif
