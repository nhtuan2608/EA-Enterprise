#ifndef ENTERPRISE_EA_PENDING_ORDER_AUDIT_MQH
#define ENTERPRISE_EA_PENDING_ORDER_AUDIT_MQH

#include "../TradeManager/PendingOrderLifecycle.mqh"

#define EEA_PENDING_AUDIT_VERSION "pending-order-audit-v1.0.0"

// Pure append contract. The caller builds a canonical fingerprint for the
// entire record except fingerprint fields and durably writes the accepted row.
// This module does not read orders/deals, write files, or grant entry.
struct EEA_PendingAuditRecord
  {
   string schema_version;
   long audit_sequence;
   string previous_fingerprint;
   string fingerprint;
   string recomputed_fingerprint;
   string event_id;
   string cause_kind; // SEED_ACCEPTED | BAR | GUARD | TIMER | BROKER_FILL | CANCEL_REQUEST | BROKER_TERMINAL | RESTORE | UNKNOWN | RECONCILE_EVIDENCE
   string source_fingerprint;
   string broker_snapshot_id;
   string order_history_fingerprint;
   string deal_set_fingerprint;
   datetime occurred_at_utc;
   datetime observed_at_utc;
   string data_quality; // OK | UNTRUSTED
   string intent_id;
   string candidate_id;
   string setup_id;
   string setup_version;
   string config_version;
   string instrument_version;
   string broker_server;
   string account_fingerprint;
   string order_ticket;
   string state_before;
   string state_after;
   string reason_code;
   datetime effective_expires_at_utc;
   int bars_waited_before;
   int bars_waited_after;
   long broker_event_sequence_before; // Caller-reconciled sequence, not OnTradeTransaction arrival order
   long broker_event_sequence_after;
   double filled_volume_before;
   double filled_volume_after;
   double cancelled_volume_before;
   double cancelled_volume_after;
   double remaining_volume_before;
   double remaining_volume_after;
   double filled_risk_before;
   double filled_risk_after;
   double remaining_reservation_before;
   double remaining_reservation_after;
  };

struct EEA_PendingAuditCursor
  {
   bool initialized;
   bool blocked;
   long last_sequence;
   string last_fingerprint;
   string last_event_id;
   datetime last_observed_at_utc;
  };

void EEA_PendingAuditCursorDefaults(EEA_PendingAuditCursor &cursor)
  {
   cursor.initialized=false;
   cursor.blocked=false;
   cursor.last_sequence=0;
   cursor.last_fingerprint="";
   cursor.last_event_id="";
   cursor.last_observed_at_utc=0;
  }

bool EEA_PendingAuditNear(const double a,const double b)
  { return MathIsValidNumber(a) && MathIsValidNumber(b) &&
           MathAbs(a-b)<=0.0000001; }

void EEA_PendingAuditReject(EEA_PendingState &after,
                            EEA_PendingAuditCursor &cursor)
  {
   cursor.blocked=true;
   EEA_PendingMarkUnknown(after,"PENDING_AUDIT_GAP_OR_CONFLICT");
  }

bool EEA_PendingAuditAccept(const EEA_PendingState &before,
                            EEA_PendingState &after,
                            const EEA_PendingAuditRecord &r,
                            EEA_PendingAuditCursor &cursor)
  {
   bool seed_record=(r.cause_kind=="SEED_ACCEPTED");
   if(cursor.blocked || !after.initialized ||
      (seed_record && before.initialized) ||
      (!seed_record && !before.initialized) ||
      r.schema_version!=EEA_PENDING_AUDIT_VERSION ||
      r.fingerprint=="" || r.fingerprint!=r.recomputed_fingerprint ||
      r.event_id=="" || r.source_fingerprint=="" ||
      r.occurred_at_utc<=0 || r.observed_at_utc<r.occurred_at_utc ||
      (r.data_quality!="OK" && r.data_quality!="UNTRUSTED") ||
      (r.data_quality=="UNTRUSTED" &&
       after.status!="PENDING_RACE_UNKNOWN") ||
      (!seed_record && r.intent_id!=before.intent_id) ||
      r.intent_id!=after.intent_id ||
      (!seed_record && r.candidate_id!=before.candidate_id) ||
      r.candidate_id!=after.candidate_id ||
      (!seed_record && r.setup_id!=before.setup_id) ||
      r.setup_id!=after.setup_id ||
      (!seed_record && r.setup_version!=before.setup_version) ||
      r.setup_version!=after.setup_version ||
      (!seed_record && r.config_version!=before.config_version) ||
      r.config_version!=after.config_version ||
      (!seed_record && r.instrument_version!=before.instrument_version) ||
      r.instrument_version!=after.instrument_version ||
      (!seed_record && r.broker_server!=before.broker_server) ||
      r.broker_server!=after.broker_server ||
      (!seed_record && r.account_fingerprint!=before.account_fingerprint) ||
      r.account_fingerprint!=after.account_fingerprint ||
      (!seed_record && r.order_ticket!=before.order_ticket) ||
      r.order_ticket!=after.order_ticket ||
      r.state_before!=before.status || r.state_after!=after.status ||
      r.reason_code!=after.reason_code ||
      (!seed_record &&
       r.effective_expires_at_utc!=before.effective_expires_at_utc) ||
      r.effective_expires_at_utc!=after.effective_expires_at_utc ||
      r.bars_waited_before!=before.bars_waited ||
      r.bars_waited_after!=after.bars_waited ||
      r.broker_event_sequence_before!=before.last_event_sequence ||
      r.broker_event_sequence_after!=after.last_event_sequence ||
      !EEA_PendingAuditNear(r.filled_volume_before,before.filled_volume) ||
      !EEA_PendingAuditNear(r.filled_volume_after,after.filled_volume) ||
      !EEA_PendingAuditNear(r.cancelled_volume_before,before.cancelled_volume) ||
      !EEA_PendingAuditNear(r.cancelled_volume_after,after.cancelled_volume) ||
      !EEA_PendingAuditNear(r.remaining_volume_before,before.remaining_volume) ||
      !EEA_PendingAuditNear(r.remaining_volume_after,after.remaining_volume) ||
      !EEA_PendingAuditNear(r.filled_risk_before,before.filled_initial_risk_money) ||
      !EEA_PendingAuditNear(r.filled_risk_after,after.filled_initial_risk_money) ||
      !EEA_PendingAuditNear(r.remaining_reservation_before,
                            before.remaining_risk_reservation_money) ||
      !EEA_PendingAuditNear(r.remaining_reservation_after,
                            after.remaining_risk_reservation_money) ||
      (!seed_record &&
       !EEA_PendingAuditNear(before.requested_volume,
                             after.requested_volume)) ||
      !EEA_PendingAuditNear(after.requested_volume,
                            after.filled_volume+after.cancelled_volume+
                            after.remaining_volume))
     { EEA_PendingAuditReject(after,cursor); return false; }

   // Identical record replay is harmless only while the caller retains the
   // matching before/after snapshots. A changed fingerprint at one sequence
   // is a conflict, never a replacement.
   if(cursor.initialized && r.audit_sequence==cursor.last_sequence &&
      r.fingerprint==cursor.last_fingerprint &&
      r.event_id==cursor.last_event_id)
      return true;
   if(r.audit_sequence<=0 ||
      (cursor.initialized &&
       (r.audit_sequence!=cursor.last_sequence+1 ||
        r.previous_fingerprint!=cursor.last_fingerprint ||
        r.observed_at_utc<cursor.last_observed_at_utc ||
        r.event_id==cursor.last_event_id)) ||
      (!cursor.initialized &&
       (r.audit_sequence!=1 || r.previous_fingerprint!="" ||
        !seed_record)))
     { EEA_PendingAuditReject(after,cursor); return false; }

   bool volumes_unchanged=
      EEA_PendingAuditNear(before.filled_volume,after.filled_volume) &&
      EEA_PendingAuditNear(before.cancelled_volume,after.cancelled_volume) &&
      EEA_PendingAuditNear(before.remaining_volume,after.remaining_volume) &&
      EEA_PendingAuditNear(before.filled_initial_risk_money,
                           after.filled_initial_risk_money) &&
      EEA_PendingAuditNear(before.remaining_risk_reservation_money,
                           after.remaining_risk_reservation_money);
   if(r.cause_kind=="SEED_ACCEPTED")
     {
      if(cursor.initialized || after.status!="WORKING" ||
         after.bars_waited!=0 || after.last_event_sequence!=0 ||
         !EEA_PendingAuditNear(before.requested_volume,0.0) ||
         !EEA_PendingAuditNear(after.filled_volume,0.0) ||
         !EEA_PendingAuditNear(after.cancelled_volume,0.0) ||
         !EEA_PendingAuditNear(after.remaining_volume,
                               after.requested_volume) ||
         !EEA_PendingAuditNear(after.remaining_risk_reservation_money,
                               after.total_committed_risk_money))
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else if(r.cause_kind=="BAR")
     {
      if(!volumes_unchanged || after.bars_waited!=before.bars_waited+1 ||
         after.last_event_sequence!=before.last_event_sequence ||
         (after.status!=before.status && after.status!="CANCEL_REQUIRED" &&
          after.status!="PENDING_RACE_UNKNOWN"))
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else if(r.cause_kind=="GUARD" || r.cause_kind=="TIMER" ||
           r.cause_kind=="RESTORE" || r.cause_kind=="UNKNOWN" ||
           r.cause_kind=="RECONCILE_EVIDENCE")
     {
      if(!volumes_unchanged || after.bars_waited!=before.bars_waited ||
         after.last_event_sequence!=before.last_event_sequence ||
         ((r.cause_kind=="GUARD" || r.cause_kind=="TIMER") &&
          after.status!=before.status && after.status!="CANCEL_REQUIRED" &&
          after.status!="PENDING_RACE_UNKNOWN") ||
         (r.cause_kind=="RESTORE" &&
          (after.status!="PENDING_RACE_UNKNOWN" ||
           !after.new_entries_blocked)) ||
         (r.cause_kind=="UNKNOWN" &&
          (after.status!="PENDING_RACE_UNKNOWN" ||
           !after.new_entries_blocked)) ||
         (r.cause_kind=="RECONCILE_EVIDENCE" &&
          (before.status!="PENDING_RACE_UNKNOWN" ||
           r.broker_snapshot_id=="" || r.order_history_fingerprint=="" ||
           r.deal_set_fingerprint=="" ||
           after.status!="PENDING_RACE_UNKNOWN" ||
           !after.new_entries_blocked)))
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else if(r.cause_kind=="BROKER_FILL")
     {
      if(after.last_event_sequence!=before.last_event_sequence+1 ||
         after.filled_volume<=before.filled_volume ||
         after.remaining_volume>=before.remaining_volume ||
         after.filled_initial_risk_money<=before.filled_initial_risk_money ||
         after.remaining_risk_reservation_money>=
            before.remaining_risk_reservation_money ||
         !EEA_PendingAuditNear(after.cancelled_volume,before.cancelled_volume) ||
         (after.status!="PARTIAL" && after.status!="FILLED" &&
          after.status!="BREACH_REVIEW"))
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else if(r.cause_kind=="CANCEL_REQUEST")
     {
      if(!volumes_unchanged ||
         after.last_event_sequence!=before.last_event_sequence+1 ||
         after.status!="CANCEL_REQUESTED")
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else if(r.cause_kind=="BROKER_TERMINAL")
     {
      if(after.last_event_sequence!=before.last_event_sequence+1 ||
         !EEA_PendingAuditNear(after.remaining_volume,0.0) ||
         after.cancelled_volume<=before.cancelled_volume ||
         !EEA_PendingAuditNear(after.cancelled_volume-before.cancelled_volume,
                               before.remaining_volume) ||
         !EEA_PendingAuditNear(after.filled_volume,before.filled_volume) ||
         !EEA_PendingAuditNear(after.filled_initial_risk_money,
                               before.filled_initial_risk_money) ||
         !EEA_PendingAuditNear(after.remaining_risk_reservation_money,0.0) ||
         (after.status!="CANCELLED" && after.status!="EXPIRED" &&
          after.status!="BREACH_REVIEW"))
        { EEA_PendingAuditReject(after,cursor); return false; }
     }
   else
     { EEA_PendingAuditReject(after,cursor); return false; }

   cursor.initialized=true;
   cursor.last_sequence=r.audit_sequence;
   cursor.last_fingerprint=r.fingerprint;
   cursor.last_event_id=r.event_id;
   cursor.last_observed_at_utc=r.observed_at_utc;
   return true;
  }

#endif
