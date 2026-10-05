#ifndef ENTERPRISE_EA_S04_FAILED_BREAK_MQH
#define ENTERPRISE_EA_S04_FAILED_BREAK_MQH

#include "BreakRetest.mqh"

// Pure closed-bar S04 Failed Break engine (design 2026-10-04). It shares the S02 engine
// record, bar and config types so that checkpoints, the candidate store and the live
// risk path handle both setups the same way. S04 trades AGAINST the attempted break:
// engine.direction is the trade direction (-1 after a failed upside break).
//
// State mapping onto the shared enum:
//   DETECTED   = BREAK_ATTEMPT (closed beyond the zone, waiting for a close back inside)
//   RETESTING  = RETURNED      (closed back inside, waiting for the rejection trigger)
//   TRIGGERED, INVALIDATED, EXPIRED as in S02.
// Engine fields used by S04:
//   key_level        break edge (zone high after an upside break)
//   retest_extreme   extreme of the failed break (stop-loss anchor)
//   invalidation_price  retest_extreme + invalidation buffer
//   retest_close     extreme of the RETURNED bar on the trade side (trigger reference)
//   bars_since_break    bars after the break bar
//   bars_since_acceptance  consecutive closes beyond the break edge (2 = break accepted)
//   bars_since_retest   bars after the RETURNED bar
// Config fields used by S04:
//   break_buffer_atr, break_body_ratio     break attempt
//   max_bars_to_accept                     window for the close back inside (D2)
//   max_bars_for_reaction                  window for the trigger (D3)
//   trigger_body_ratio, trigger_progress_atr  trigger candle (D3)
//   invalidation_buffer_atr, candidate_ttl_bars

#define EEA_S04_ACCEPT_CLOSES 2

void EEA_S04V1Config(EEA_S02Config &c,const string profile)
  {
   EEA_S02ResearchSeedConfig(c);
   bool swing=(profile=="SWING");
   c.config_version=swing ? "s04-v1-swing-0.1.0" : "s04-v1-scalp-0.1.0";
   c.break_buffer_atr=0.10;
   c.acceptance_buffer_atr=0.0;
   c.retest_tolerance_atr=0.15;      // unused by S04, kept valid for the shared validator
   c.invalidation_buffer_atr=0.10;
   c.hold_buffer_atr=0.0;
   c.max_bars_to_accept=3;           // D2: close back inside within 3 bars
   c.max_bars_to_retest=3;           // unused by S04
   c.max_bars_for_reaction=3;        // D3: trigger within 3 bars of RETURNED
   c.candidate_ttl_bars=2;
   c.break_body_ratio=0.50;          // D1: same break as S02
   c.trigger_body_ratio=0.40;
   c.trigger_progress_atr=0.05;
   c.fail_on_close_inside_zone=false;
  }

bool EEA_S04IsConfig(const EEA_S02Config &c) { return StringFind(c.config_version,"s04-")==0; }

string EEA_S04StateName(const int state)
  {
   if(state==EEA_S02_DETECTED) return "BREAK_ATTEMPT";
   if(state==EEA_S02_RETESTING) return "RETURNED";
   return EEA_S02StateName(state);
  }

string EEA_SetupStateName(const string setup,const int state)
  {
   if(setup=="S06" || setup=="S06B") return state==EEA_S02_DETECTED ? "RELEASED" : EEA_S02StateName(state);   // CompressionExpansion.mqh
   return setup=="S04" ? EEA_S04StateName(state) : EEA_S02StateName(state);
  }

void EEA_S04SetEvent(EEA_S02Event &ev,const EEA_S02Engine &e,const datetime at,
                     const string event_type,const int before,const string reason)
  {
   ev.bar_time_utc=at;
   ev.event_type=event_type;
   ev.state_before=EEA_S04StateName(before);
   ev.state_after=EEA_S04StateName(e.state);
   ev.reason_code=reason;
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
  }

void EEA_S04Transition(EEA_S02Engine &e,EEA_S02Event &ev,const datetime at,
                       const int next_state,const string event_type,const string reason)
  {
   int before=e.state;
   e.state=next_state;
   e.candidate.state=EEA_S04StateName(next_state);
   e.candidate.reason_code=reason;
   EEA_S04SetEvent(ev,e,at,event_type,before,reason);
  }

// break_dir is the direction of the attempted break (+1 up); the trade goes the other way.
void EEA_S04StartAttempt(EEA_S02Engine &e,const EEA_S02Bar &b,const double zone_low,const double zone_high,
                         const int break_dir,const EEA_S02Config &c,EEA_S02Event &ev)
  {
   e.direction=-break_dir;
   e.key_level=(break_dir>0 ? zone_high : zone_low);
   e.zone_low=zone_low;
   e.zone_high=zone_high;
   e.signal_atr=b.atr;
   e.breakout_bar_utc=b.closed_at_utc;
   e.retest_extreme=(break_dir>0 ? b.high : b.low);
   e.invalidation_price=e.retest_extreme+break_dir*c.invalidation_buffer_atr*b.atr;
   e.retest_close=0.0;
   e.bars_since_break=0;
   e.bars_since_acceptance=0;
   e.bars_since_retest=0;
   e.candidate.canonical_symbol=e.canonical_symbol;
   e.candidate.timeframe=e.timeframe;
   e.candidate.config_version=e.config_version;
   e.candidate.candidate_id=StringFormat("S04-%s-%s-%s-%I64d",e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
   e.candidate.setup_id="S04";
   e.candidate.direction=(e.direction>0 ? "LONG" : "SHORT");
   e.candidate.key_level=e.key_level;
   e.candidate.zone_low=zone_low;
   e.candidate.zone_high=zone_high;
   e.candidate.invalidation_price=e.invalidation_price;
   e.candidate.detected_at_utc=b.closed_at_utc;
   e.candidate.expires_after_bars=c.candidate_ttl_bars;
   EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_DETECTED,"BREAK_ATTEMPT_DETECTED",
                     break_dir>0 ? "BREAK_ATTEMPT_ABOVE_ZONE" : "BREAK_ATTEMPT_BELOW_ZONE");
  }

bool EEA_S04ProcessClosedBarZone(EEA_S02Engine &e,const EEA_S02Bar &b,
                                 const double zone_low,const double zone_high,const EEA_S02Config &c,
                                 EEA_S02Event &ev)
  {
   int before=e.state;
   ev.bar_time_utc=b.closed_at_utc;
   ev.event_type="NO_TRANSITION";
   ev.state_before=EEA_S04StateName(e.state);
   ev.state_after=EEA_S04StateName(e.state);
   ev.reason_code="WAITING_FOR_BREAK_ATTEMPT";
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
   if(e.canonical_symbol=="" || e.timeframe=="" || e.config_version=="")
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="ENGINE_IDENTITY_REQUIRED"; return false; }
   if(c.config_version!=e.config_version)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="CONFIG_VERSION_MISMATCH"; return false; }
   if(!EEA_S02ConfigValid(c) || !EEA_S04IsConfig(c))
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_RESEARCH_CONFIG"; return false; }
   if(!EEA_S02ValidBar(b) || !MathIsValidNumber(zone_low) || !MathIsValidNumber(zone_high) || zone_low>zone_high)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_CLOSED_BAR"; return false; }
   if(b.closed_at_utc==e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="DUPLICATE_CLOSED_BAR"; return true; }
   if(b.closed_at_utc<e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="OUT_OF_ORDER_CLOSED_BAR"; return true; }
   if(EEA_S02IsTerminal(e.state))
     {
      datetime last=e.last_processed_bar_utc;
      EEA_S02Reset(e);
      EEA_S02ClearCandidate(e.candidate);
      e.candidate.setup_id="S04";
      e.last_processed_bar_utc=last;
      before=e.state;
      ev.state_before=EEA_S04StateName(e.state);
      ev.state_after=ev.state_before;
      ev.candidate_id="";
     }
   e.last_processed_bar_utc=b.closed_at_utc;

   if(e.state==EEA_S02_IDLE)
     {
      // TC-005: only a CLOSE beyond the zone starts an attempt; a wick alone never does.
      if(b.close>zone_high+c.break_buffer_atr*b.atr && EEA_S02BodyOk(b,1,c.break_body_ratio))
         EEA_S04StartAttempt(e,b,zone_low,zone_high,1,c,ev);
      else if(b.close<zone_low-c.break_buffer_atr*b.atr && EEA_S02BodyOk(b,-1,c.break_body_ratio))
         EEA_S04StartAttempt(e,b,zone_low,zone_high,-1,c,ev);
      return true;
     }

   const int break_dir=-e.direction;
   // A close beyond the failed-break extreme (plus buffer) ends the thesis. The
   // extreme is the one known before this bar, so the bar's own wick cannot hide it.
   const bool thesis_lost=(break_dir>0 ? b.close>e.invalidation_price : b.close<e.invalidation_price);
   const bool beyond_edge=(break_dir>0 ? b.close>e.key_level : b.close<e.key_level);
   if(e.state==EEA_S02_DETECTED || e.state==EEA_S02_RETESTING)
     {
      e.retest_extreme=(break_dir>0 ? MathMax(e.retest_extreme,b.high) : MathMin(e.retest_extreme,b.low));
      e.bars_since_acceptance=beyond_edge ? e.bars_since_acceptance+1 : 0;
     }

   if(e.state==EEA_S02_DETECTED)
     {
      e.bars_since_break++;
      if(thesis_lost)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"FAILED_BREAK_INVALIDATED","THESIS_INVALIDATED");
      else if(!beyond_edge)
        {
         e.retest_close=(break_dir>0 ? b.low : b.high);
         e.bars_since_retest=0;
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_RETESTING,"RETURNED_INSIDE","CLOSED_BACK_INSIDE_ZONE");
        }
      else if(e.bars_since_acceptance>=EEA_S04_ACCEPT_CLOSES)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"FAILED_BREAK_INVALIDATED","BREAK_ACCEPTED");
      else if(e.bars_since_break>=c.max_bars_to_accept)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","NO_RETURN_INSIDE");
      else
         EEA_S04SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_RETURN_INSIDE");
      if(e.state==EEA_S02_DETECTED || e.state==EEA_S02_RETESTING)
         e.invalidation_price=e.retest_extreme+break_dir*c.invalidation_buffer_atr*e.signal_atr;
      return true;
     }

   if(e.state==EEA_S02_RETESTING)
     {
      e.bars_since_retest++;
      const int d=e.direction;
      bool trigger=(d<0 ? b.close<b.open && b.close<e.retest_close-c.trigger_progress_atr*e.signal_atr :
                          b.close>b.open && b.close>e.retest_close+c.trigger_progress_atr*e.signal_atr) &&
                   EEA_S02BodyOk(b,d,c.trigger_body_ratio);
      if(thesis_lost)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"FAILED_BREAK_INVALIDATED","THESIS_INVALIDATED");
      else if(e.bars_since_acceptance>=EEA_S04_ACCEPT_CLOSES)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"FAILED_BREAK_INVALIDATED","BREAK_ACCEPTED");
      else if(trigger)
        {
         e.candidate.triggered_at_utc=b.closed_at_utc;
         e.candidate.retest_extreme=e.retest_extreme;
         e.candidate.invalidation_price=e.invalidation_price;
         e.candidate.age_after_trigger_bars=0;
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_TRIGGERED,"CANDIDATE_TRIGGERED","FAILED_BREAK_REJECTION_CONFIRMED");
        }
      else if(e.bars_since_retest>=c.max_bars_for_reaction)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","TRIGGER_EXPIRED");
      else
         EEA_S04SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_REJECTION");
      if(e.state==EEA_S02_RETESTING)
         e.invalidation_price=e.retest_extreme+break_dir*c.invalidation_buffer_atr*e.signal_atr;
      return true;
     }

   if(e.state==EEA_S02_TRIGGERED)
     {
      e.candidate.age_after_trigger_bars++;
      if(e.candidate.age_after_trigger_bars>=e.candidate.expires_after_bars)
         EEA_S04Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"CANDIDATE_EXPIRED","CANDIDATE_TTL_REACHED");
      else
         EEA_S04SetEvent(ev,e,b.closed_at_utc,"CANDIDATE_PENDING",before,"CANDIDATE_TTL_ACTIVE");
      return true;
     }
   return true;
  }

#endif
