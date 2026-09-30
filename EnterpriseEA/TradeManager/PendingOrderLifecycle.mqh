#ifndef ENTERPRISE_EA_PENDING_ORDER_LIFECYCLE_MQH
#define ENTERPRISE_EA_PENDING_ORDER_LIFECYCLE_MQH

// Pure, caller-attested lifecycle proposal. It never reads MT5 orders or sends
// trade requests. All UTC values, broker acceptance and fill/cancel events
// require a separate authoritative adapter before Paper or Live use.
struct EEA_PendingSeed
  {
   string intent_id;
   string candidate_id;
   string setup_id;
   string setup_version;
   string config_version;
   string instrument_version;
   string canonical_symbol;
   string account_currency;
   string broker_server;
   string account_fingerprint;
   string order_ticket;
   string trade_style; // SCALP | SWING
   string order_type; // BUY_LIMIT | SELL_LIMIT | BUY_STOP | SELL_STOP
   datetime candidate_triggered_at_utc;
   datetime submitted_at_utc;
   datetime broker_accepted_at_utc;
   datetime setup_valid_until_utc;
   datetime session_end_at_utc;
   datetime broker_expiration_at_utc;
   long placed_after_closed_bar_sequence;
   int max_wait_closed_bars;
   bool placement_validated;
   bool broker_expiration_attested;
   double requested_volume;
   double volume_step;
   double reserved_risk_per_lot_money;
   double max_committed_risk_money;
  };

struct EEA_PendingObservation
  {
   string intent_id;
   string config_version;
   string setup_snapshot_id;
   string bar_fingerprint;
   long closed_bar_sequence;
   datetime closed_at_utc;
   bool bar_closed_confirmed;
   bool setup_valid;
   bool session_open;
   bool risk_entry_allowed;
   bool news_entry_allowed;
   bool quote_premise_valid;
   bool config_spec_unchanged;
   string data_quality; // OK required
  };

struct EEA_PendingGuard
  {
   string intent_id;
   string config_version;
   string snapshot_id;
   string content_fingerprint;
   datetime observed_at_utc;
   bool setup_valid;
   bool session_open;
   bool risk_entry_allowed;
   bool news_entry_allowed;
   bool quote_premise_valid;
   bool config_spec_unchanged;
   string data_quality;
  };

struct EEA_PendingBrokerEvent
  {
   string event_id;
   long event_sequence;
   string content_fingerprint;
   string intent_id;
   string config_version;
   string instrument_version;
   string broker_server;
   string account_fingerprint;
   string order_ticket;
   datetime occurred_at_utc;
   string data_quality; // OK required
   string event_kind; // FILL | CANCEL_REQUESTED | CANCEL_CONFIRMED | EXPIRE_CONFIRMED
   string correlation_id; // Required for cancellation request/confirmation
   double fill_volume; // FILL only
   double filled_initial_risk_money; // FILL only, includes attested costs
   double confirmed_remaining_volume; // terminal confirmation only
  };

struct EEA_PendingState
  {
   bool initialized;
   string status; // UNKNOWN | WORKING | PARTIAL | CANCEL_REQUIRED | CANCEL_REQUESTED | FILLED | CANCELLED | EXPIRED | BREACH_REVIEW | PENDING_RACE_UNKNOWN
   string reason_code;
   string cancel_reason;
   string intent_id;
   string candidate_id;
   string setup_id;
   string setup_version;
   string config_version;
   string instrument_version;
   string canonical_symbol;
   string account_currency;
   string broker_server;
   string account_fingerprint;
   string order_ticket;
   string trade_style;
   string order_type;
   datetime broker_accepted_at_utc;
   datetime effective_expires_at_utc;
   datetime cancel_required_at_utc;
   datetime cancel_requested_at_utc;
   datetime broker_confirmed_at_utc;
   string cancel_correlation_id;
   long last_closed_bar_sequence;
   datetime last_bar_closed_at_utc;
   string last_bar_fingerprint;
   string last_setup_snapshot_id;
   string last_guard_snapshot_id;
   string last_guard_fingerprint;
   datetime last_guard_at_utc;
   int max_wait_closed_bars;
   int bars_waited;
   long last_event_sequence;
   datetime last_event_at_utc;
   string last_event_id;
   string last_event_fingerprint;
   double requested_volume;
   double filled_volume;
   double cancelled_volume;
   double remaining_volume;
   double volume_step;
   double reserved_risk_per_lot_money;
   double max_committed_risk_money;
   double filled_initial_risk_money;
   double remaining_risk_reservation_money;
   double total_committed_risk_money;
   bool new_entries_blocked;
  };

bool EEA_PendingPositive(const double value)
  { return MathIsValidNumber(value) && value>0.0; }

bool EEA_PendingVolumeAligned(const double volume,const double step)
  {
   if(!EEA_PendingPositive(volume) || !EEA_PendingPositive(step)) return false;
   double units=volume/step;
   return MathAbs(units-MathRound(units))<=0.0000001;
  }

void EEA_PendingDefaults(EEA_PendingState &s)
  {
   s.initialized=false; s.status="UNKNOWN"; s.reason_code="ATTESTED_PENDING_SEED_REQUIRED";
   s.cancel_reason=""; s.intent_id=""; s.candidate_id=""; s.setup_id="";
   s.setup_version=""; s.config_version=""; s.instrument_version="";
   s.canonical_symbol=""; s.account_currency="";
   s.broker_server=""; s.account_fingerprint=""; s.order_ticket="";
   s.trade_style="";
   s.order_type=""; s.broker_accepted_at_utc=0; s.effective_expires_at_utc=0;
   s.cancel_required_at_utc=0; s.cancel_requested_at_utc=0;
   s.broker_confirmed_at_utc=0; s.cancel_correlation_id="";
   s.last_closed_bar_sequence=0; s.last_bar_closed_at_utc=0;
   s.last_bar_fingerprint=""; s.last_setup_snapshot_id="";
   s.last_guard_snapshot_id=""; s.last_guard_fingerprint="";
   s.last_guard_at_utc=0;
   s.max_wait_closed_bars=0; s.bars_waited=0;
   s.last_event_sequence=0; s.last_event_at_utc=0;
   s.last_event_id=""; s.last_event_fingerprint="";
   s.requested_volume=0.0; s.filled_volume=0.0; s.cancelled_volume=0.0;
   s.remaining_volume=0.0; s.volume_step=0.0;
   s.reserved_risk_per_lot_money=0.0; s.max_committed_risk_money=0.0;
   s.filled_initial_risk_money=0.0; s.remaining_risk_reservation_money=0.0;
   s.total_committed_risk_money=0.0; s.new_entries_blocked=true;
  }

bool EEA_PendingInit(const EEA_PendingSeed &seed,const datetime now_utc,
                     EEA_PendingState &s)
  {
   EEA_PendingDefaults(s);
   if(seed.intent_id=="" || seed.candidate_id=="" || seed.setup_id=="" ||
      seed.setup_version=="" || seed.config_version=="" ||
      seed.instrument_version=="" || seed.canonical_symbol=="" ||
      seed.account_currency=="" || seed.broker_server=="" ||
      seed.account_fingerprint=="" || seed.order_ticket=="" ||
      (seed.trade_style!="SCALP" && seed.trade_style!="SWING") ||
      (seed.order_type!="BUY_LIMIT" && seed.order_type!="SELL_LIMIT" &&
       seed.order_type!="BUY_STOP" && seed.order_type!="SELL_STOP") ||
      seed.candidate_triggered_at_utc<=0 ||
      seed.submitted_at_utc<seed.candidate_triggered_at_utc ||
      seed.broker_accepted_at_utc<seed.submitted_at_utc ||
      now_utc<seed.broker_accepted_at_utc ||
      seed.setup_valid_until_utc<=seed.broker_accepted_at_utc ||
      seed.session_end_at_utc<=seed.broker_accepted_at_utc ||
      seed.broker_expiration_at_utc<=seed.broker_accepted_at_utc ||
      seed.placed_after_closed_bar_sequence<0 ||
      seed.max_wait_closed_bars<=0 || !seed.placement_validated ||
      !seed.broker_expiration_attested ||
      !EEA_PendingVolumeAligned(seed.requested_volume,seed.volume_step) ||
      !EEA_PendingPositive(seed.reserved_risk_per_lot_money) ||
      !EEA_PendingPositive(seed.max_committed_risk_money))
     { s.reason_code="PENDING_SEED_OR_PROFILE_INVALID"; return false; }
   datetime expiry=seed.setup_valid_until_utc;
   if(seed.session_end_at_utc<expiry) expiry=seed.session_end_at_utc;
   if(seed.broker_expiration_at_utc<expiry) expiry=seed.broker_expiration_at_utc;
   double reserved=seed.requested_volume*seed.reserved_risk_per_lot_money;
   if(now_utc>=expiry || !MathIsValidNumber(reserved) ||
      reserved>seed.max_committed_risk_money+0.0000001)
     { s.reason_code="PENDING_EXPIRED_OR_RISK_BUDGET_EXCEEDED"; return false; }
   s.initialized=true; s.status="WORKING"; s.reason_code="PENDING_ACCEPTED_RESERVED";
   s.intent_id=seed.intent_id; s.candidate_id=seed.candidate_id;
   s.setup_id=seed.setup_id; s.setup_version=seed.setup_version;
   s.config_version=seed.config_version;
   s.instrument_version=seed.instrument_version;
   s.canonical_symbol=seed.canonical_symbol;
   s.account_currency=seed.account_currency;
   s.broker_server=seed.broker_server;
   s.account_fingerprint=seed.account_fingerprint;
   s.order_ticket=seed.order_ticket;
   s.trade_style=seed.trade_style; s.order_type=seed.order_type;
   s.broker_accepted_at_utc=seed.broker_accepted_at_utc;
   s.effective_expires_at_utc=expiry;
   s.last_closed_bar_sequence=seed.placed_after_closed_bar_sequence;
   s.max_wait_closed_bars=seed.max_wait_closed_bars;
   s.last_event_at_utc=seed.broker_accepted_at_utc;
   s.requested_volume=seed.requested_volume;
   s.remaining_volume=seed.requested_volume;
   s.volume_step=seed.volume_step;
   s.reserved_risk_per_lot_money=seed.reserved_risk_per_lot_money;
   s.max_committed_risk_money=seed.max_committed_risk_money;
   s.remaining_risk_reservation_money=reserved;
   s.total_committed_risk_money=reserved;
   s.new_entries_blocked=false;
   return true;
  }

void EEA_PendingMarkUnknown(EEA_PendingState &s,const string reason)
  {
   s.status="PENDING_RACE_UNKNOWN"; s.reason_code=reason;
   s.new_entries_blocked=true;
  }

void EEA_PendingRequireCancel(EEA_PendingState &s,const datetime at_utc,
                              const string reason)
  {
   if(s.status!="WORKING" && s.status!="PARTIAL") return;
   if(s.remaining_volume<=0.0) return;
   s.status="CANCEL_REQUIRED"; s.reason_code="PENDING_CANCEL_REQUIRED";
   s.cancel_reason=reason; s.cancel_required_at_utc=at_utc;
   s.new_entries_blocked=true;
  }

bool EEA_PendingCheckDeadline(EEA_PendingState &s,const datetime now_utc)
  {
   if(!s.initialized || now_utc<s.broker_accepted_at_utc) return false;
   if(now_utc>=s.effective_expires_at_utc)
      EEA_PendingRequireCancel(s,now_utc,"UTC_DEADLINE_REACHED");
   return true;
  }

bool EEA_PendingObserve(EEA_PendingState &s,const EEA_PendingObservation &o)
  {
   if(!s.initialized || (s.status!="WORKING" && s.status!="PARTIAL" &&
                        s.status!="CANCEL_REQUIRED")) return false;
   if(o.closed_bar_sequence==s.last_closed_bar_sequence &&
      s.last_bar_fingerprint!="" && o.intent_id==s.intent_id &&
      o.config_version==s.config_version &&
      o.bar_fingerprint==s.last_bar_fingerprint &&
      o.setup_snapshot_id==s.last_setup_snapshot_id &&
      o.closed_at_utc==s.last_bar_closed_at_utc)
      return true;
   if(o.intent_id!=s.intent_id || o.config_version!=s.config_version ||
      o.setup_snapshot_id=="" || o.bar_fingerprint=="" ||
      o.closed_bar_sequence!=s.last_closed_bar_sequence+1 ||
      o.closed_at_utc<=s.broker_accepted_at_utc ||
      o.closed_at_utc<=s.last_bar_closed_at_utc ||
      !o.bar_closed_confirmed || o.data_quality!="OK")
     { EEA_PendingMarkUnknown(s,"PENDING_BAR_MISSING_CONFLICTING_OR_UNTRUSTED"); return false; }
   s.last_closed_bar_sequence=o.closed_bar_sequence;
   s.last_bar_closed_at_utc=o.closed_at_utc;
   s.last_bar_fingerprint=o.bar_fingerprint;
   s.last_setup_snapshot_id=o.setup_snapshot_id;
   s.bars_waited++;
   if(o.closed_at_utc>=s.effective_expires_at_utc)
      EEA_PendingRequireCancel(s,o.closed_at_utc,"UTC_DEADLINE_REACHED");
   else if(s.bars_waited>=s.max_wait_closed_bars)
      EEA_PendingRequireCancel(s,o.closed_at_utc,"MAX_WAIT_CLOSED_BARS_REACHED");
   else if(!o.setup_valid || !o.session_open || !o.risk_entry_allowed ||
           !o.news_entry_allowed || !o.quote_premise_valid ||
           !o.config_spec_unchanged)
      EEA_PendingRequireCancel(s,o.closed_at_utc,"SETUP_OR_POLICY_INVALIDATED");
   return true;
  }

bool EEA_PendingObserveGuard(EEA_PendingState &s,const EEA_PendingGuard &g)
  {
   if(!s.initialized || (s.status!="WORKING" && s.status!="PARTIAL" &&
                        s.status!="CANCEL_REQUIRED")) return false;
   if(g.intent_id==s.intent_id && g.config_version==s.config_version &&
      g.snapshot_id!="" && g.snapshot_id==s.last_guard_snapshot_id &&
      g.content_fingerprint==s.last_guard_fingerprint &&
      g.observed_at_utc==s.last_guard_at_utc)
      return true;
   if(g.intent_id!=s.intent_id || g.config_version!=s.config_version ||
      g.snapshot_id=="" || g.content_fingerprint=="" ||
      g.observed_at_utc<=s.broker_accepted_at_utc ||
      g.observed_at_utc<=s.last_guard_at_utc || g.data_quality!="OK")
     { EEA_PendingMarkUnknown(s,"PENDING_GUARD_MISSING_CONFLICTING_OR_UNTRUSTED"); return false; }
   s.last_guard_snapshot_id=g.snapshot_id;
   s.last_guard_fingerprint=g.content_fingerprint;
   s.last_guard_at_utc=g.observed_at_utc;
   if(g.observed_at_utc>=s.effective_expires_at_utc)
      EEA_PendingRequireCancel(s,g.observed_at_utc,"UTC_DEADLINE_REACHED");
   else if(!g.setup_valid || !g.session_open || !g.risk_entry_allowed ||
           !g.news_entry_allowed || !g.quote_premise_valid ||
           !g.config_spec_unchanged)
      EEA_PendingRequireCancel(s,g.observed_at_utc,"SETUP_OR_POLICY_INVALIDATED");
   return true;
  }

bool EEA_PendingReplay(const EEA_PendingState &s,const EEA_PendingBrokerEvent &e)
  {
   return e.event_sequence>0 && e.event_sequence==s.last_event_sequence &&
          e.event_id==s.last_event_id &&
          e.content_fingerprint==s.last_event_fingerprint;
  }

bool EEA_PendingApplyBrokerEvent(EEA_PendingState &s,
                                  const EEA_PendingBrokerEvent &e)
  {
   if(!s.initialized) return false;
   if(EEA_PendingReplay(s,e)) return true;
   if(e.event_id=="" || e.content_fingerprint=="" ||
      e.event_sequence!=s.last_event_sequence+1 ||
      e.intent_id!=s.intent_id || e.config_version!=s.config_version ||
      e.instrument_version!=s.instrument_version ||
      e.broker_server!=s.broker_server ||
      e.account_fingerprint!=s.account_fingerprint ||
      e.order_ticket!=s.order_ticket ||
      e.occurred_at_utc<s.last_event_at_utc || e.data_quality!="OK")
     { EEA_PendingMarkUnknown(s,"PENDING_BROKER_EVENT_MISSING_OR_CONFLICTING"); return false; }
   if(e.event_kind=="FILL")
     {
      if(s.status!="WORKING" && s.status!="PARTIAL" &&
         s.status!="CANCEL_REQUIRED" && s.status!="CANCEL_REQUESTED" &&
         s.status!="BREACH_REVIEW")
        { EEA_PendingMarkUnknown(s,"FILL_AFTER_TERMINAL_OR_UNKNOWN_STATE"); return false; }
      if(!EEA_PendingVolumeAligned(e.fill_volume,s.volume_step) ||
         e.fill_volume>s.remaining_volume+0.0000001 ||
         !EEA_PendingPositive(e.filled_initial_risk_money))
        { EEA_PendingMarkUnknown(s,"PENDING_FILL_VOLUME_OR_RISK_INVALID"); return false; }
      bool late=(e.occurred_at_utc>=s.effective_expires_at_utc ||
                 s.status=="CANCEL_REQUIRED" || s.status=="CANCEL_REQUESTED" ||
                 s.status=="BREACH_REVIEW");
      s.filled_volume+=e.fill_volume;
      s.remaining_volume-=e.fill_volume;
      if(MathAbs(s.remaining_volume)<0.0000001) s.remaining_volume=0.0;
      s.filled_initial_risk_money+=e.filled_initial_risk_money;
      s.remaining_risk_reservation_money=
         s.remaining_volume*s.reserved_risk_per_lot_money;
      s.total_committed_risk_money=s.filled_initial_risk_money+
                                   s.remaining_risk_reservation_money;
      if(late || s.total_committed_risk_money>
                 s.max_committed_risk_money+0.0000001)
        {
         s.status="BREACH_REVIEW";
         s.reason_code=(late ? "FILL_DURING_CANCEL_OR_AFTER_DEADLINE" :
                                "FILLED_RISK_EXCEEDS_BUDGET");
         s.new_entries_blocked=true;
        }
      else
        {
         s.status=(s.remaining_volume==0.0 ? "FILLED" : "PARTIAL");
         s.reason_code=(s.remaining_volume==0.0 ? "PENDING_FULLY_FILLED" :
                                                  "PENDING_PARTIALLY_FILLED");
        }
     }
   else if(e.event_kind=="CANCEL_REQUESTED")
     {
      if(s.status!="CANCEL_REQUIRED" && s.status!="BREACH_REVIEW") return false;
      if(e.correlation_id=="" || s.remaining_volume<=0.0 ||
         s.cancel_requested_at_utc>0)
        { EEA_PendingMarkUnknown(s,"CANCEL_REQUEST_INVALID"); return false; }
      s.status="CANCEL_REQUESTED";
      s.cancel_correlation_id=e.correlation_id;
      s.cancel_requested_at_utc=e.occurred_at_utc;
      s.reason_code="CANCEL_SENT_AWAITING_BROKER_CONFIRMATION";
      s.new_entries_blocked=true;
     }
   else if(e.event_kind=="CANCEL_CONFIRMED" ||
           e.event_kind=="EXPIRE_CONFIRMED")
     {
      if(s.status!="WORKING" && s.status!="PARTIAL" &&
         s.status!="CANCEL_REQUESTED" && s.status!="CANCEL_REQUIRED" &&
         s.status!="BREACH_REVIEW") return false;
      if(s.remaining_volume<=0.0 ||
         (e.event_kind=="CANCEL_CONFIRMED" &&
          s.cancel_requested_at_utc>0 &&
          (e.correlation_id=="" || e.correlation_id!=s.cancel_correlation_id)) ||
         !MathIsValidNumber(e.confirmed_remaining_volume) ||
         MathAbs(e.confirmed_remaining_volume-s.remaining_volume)>0.0000001)
        { EEA_PendingMarkUnknown(s,"CANCEL_CONFIRM_VOLUME_OR_ID_MISMATCH"); return false; }
      bool was_breach=(s.status=="BREACH_REVIEW");
      s.cancelled_volume+=s.remaining_volume;
      s.remaining_volume=0.0;
      s.remaining_risk_reservation_money=0.0;
      s.total_committed_risk_money=s.filled_initial_risk_money;
      s.broker_confirmed_at_utc=e.occurred_at_utc;
      s.status=(was_breach ? "BREACH_REVIEW" :
                (e.event_kind=="CANCEL_CONFIRMED" ? "CANCELLED" : "EXPIRED"));
      s.reason_code=(was_breach ? "REMAINDER_INACTIVE_AFTER_BREACH" :
                     "PENDING_REMAINDER_BROKER_CONFIRMED_INACTIVE");
      s.new_entries_blocked=true; // Fresh account-wide reconcile is still required.
     }
   else
     { EEA_PendingMarkUnknown(s,"PENDING_BROKER_EVENT_KIND_UNKNOWN"); return false; }
   if(!MathIsValidNumber(s.total_committed_risk_money) ||
      MathAbs(s.requested_volume-s.filled_volume-s.cancelled_volume-
              s.remaining_volume)>0.0000001)
     { EEA_PendingMarkUnknown(s,"PENDING_VOLUME_OR_RISK_INVARIANT_BROKEN"); return false; }
   s.last_event_sequence=e.event_sequence;
   s.last_event_at_utc=e.occurred_at_utc;
   s.last_event_id=e.event_id;
   s.last_event_fingerprint=e.content_fingerprint;
   return true;
  }

#endif
