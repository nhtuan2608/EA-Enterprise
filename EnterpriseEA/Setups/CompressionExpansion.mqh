#ifndef ENTERPRISE_EA_S06_COMPRESSION_EXPANSION_MQH
#define ENTERPRISE_EA_S06_COMPRESSION_EXPANSION_MQH

#include "BreakRetest.mqh"

// Pure closed-bar S06 Compression Expansion engine, SWING only (H1 entry, H4 HTF).
// Mirrors research/g10/setups.py s06 with the configuration chosen in the G10 long-history
// study (report 2026-10-05, part 3): box 12 bars, box <= 3 ATR, ATR <= 0.85 x ATR 48 bars
// earlier, entry on the confirmation bar, stop at the far edge of the box, fixed 3R target.
// It shares the S02 engine record so checkpoints, the candidate store and the live risk
// path handle it like S02 and S04.
//
// State mapping onto the shared enum:
//   IDLE       waiting for a release bar out of a compression box
//   DETECTED   = RELEASED (closed beyond the box; the next bar must confirm)
//   TRIGGERED  confirmation bar closed beyond the box edge: enter on this bar only
//   EXPIRED    no confirmation, or the triggered candidate was not taken in its bar
// Engine fields used by S06:
//   zone_low/zone_high   the compression box (the Trade Manager guards it like a zone)
//   key_level            box edge in the trade direction
//   retest_extreme       far edge of the box (stop-loss anchor, research sl='far')
//   invalidation_price   same as retest_extreme
//   signal_atr           ATR of the confirmation bar (stop buffer, entry chase limit)
// The caller supplies the box (the S06_BOX_BARS closed bars before this bar) and the
// ATR of the previous bar and of the bar S06_CONTRACTION_LOOKBACK bars earlier.
//
// S06B (G26, long-history study G23): same engine with a 24-bar box and entry on the release
// bar itself (no confirmation bar): TRIGGERED straight from IDLE, signal ATR = ATR of the bar
// before the release (research setups.s06 mode "immediate"). It is told apart by its config
// version (s06b-...), so checkpoints and candidates never mix with S06.

#define EEA_S06_BOX_BARS 12
#define EEA_S06_MAX_BOX_ATR 3.0
#define EEA_S06_CONTRACTION 0.85
#define EEA_S06_CONTRACTION_LOOKBACK 48
#define EEA_S06_RELEASE_BUFFER_ATR 0.10
#define EEA_S06_RELEASE_BODY_RATIO 0.50
#define EEA_S06_RELEASE_MIN_RANGE_ATR 1.0
#define EEA_S06_TARGET_R 3.0
#define EEA_S06B_BOX_BARS 24

void EEA_S06V1Config(EEA_S02Config &c)
  {
   EEA_S02V1Config(c,"SWING");       // valid shared fields; S06 uses its own constants
   c.config_version="s06-v1-swing-0.1.0";
   c.break_buffer_atr=EEA_S06_RELEASE_BUFFER_ATR;
   c.break_body_ratio=EEA_S06_RELEASE_BODY_RATIO;
   c.invalidation_buffer_atr=0.0;
   c.candidate_ttl_bars=1;           // research enters at the confirmation close only
  }

void EEA_S06BV1Config(EEA_S02Config &c)
  {
   EEA_S06V1Config(c);
   c.config_version="s06b-v1-swing-0.1.0";
  }

bool EEA_S06IsVariantB(const EEA_S02Config &c) { return StringFind(c.config_version,"s06b-")==0; }
bool EEA_S06IsConfig(const EEA_S02Config &c) { return StringFind(c.config_version,"s06-")==0 || EEA_S06IsVariantB(c); }
int EEA_S06BoxBars(const EEA_S02Config &c) { return EEA_S06IsVariantB(c) ? EEA_S06B_BOX_BARS : EEA_S06_BOX_BARS; }
string EEA_S06SetupId(const EEA_S02Config &c) { return EEA_S06IsVariantB(c) ? "S06B" : "S06"; }

string EEA_S06StateName(const int state)
  {
   if(state==EEA_S02_DETECTED) return "RELEASED";
   return EEA_S02StateName(state);
  }

void EEA_S06SetEvent(EEA_S02Event &ev,const EEA_S02Engine &e,const datetime at,
                     const string event_type,const int before,const string reason)
  {
   ev.bar_time_utc=at;
   ev.event_type=event_type;
   ev.state_before=EEA_S06StateName(before);
   ev.state_after=EEA_S06StateName(e.state);
   ev.reason_code=reason;
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
  }

void EEA_S06Transition(EEA_S02Engine &e,EEA_S02Event &ev,const datetime at,
                       const int next_state,const string event_type,const string reason)
  {
   int before=e.state;
   e.state=next_state;
   e.candidate.state=EEA_S06StateName(next_state);
   e.candidate.reason_code=reason;
   EEA_S06SetEvent(ev,e,at,event_type,before,reason);
  }

// The box qualifies when it is narrow and volatility has contracted (research s06).
bool EEA_S06Compressed(const double box_low,const double box_high,const double ref_atr,const double old_atr)
  {
   if(ref_atr<=0.0 || old_atr<=0.0 || box_high<box_low) return false;
   return box_high-box_low<=EEA_S06_MAX_BOX_ATR*ref_atr && ref_atr<=EEA_S06_CONTRACTION*old_atr;
  }

// Release direction of a bar out of the box: +1, -1 or 0. Upside is checked first.
int EEA_S06ReleaseDirection(const EEA_S02Bar &b,const double box_low,const double box_high,const double ref_atr)
  {
   if(b.high-b.low<EEA_S06_RELEASE_MIN_RANGE_ATR*ref_atr) return 0;
   if(b.close-box_high>EEA_S06_RELEASE_BUFFER_ATR*ref_atr && EEA_S02BodyOk(b,1,EEA_S06_RELEASE_BODY_RATIO)) return 1;
   if(box_low-b.close>EEA_S06_RELEASE_BUFFER_ATR*ref_atr && EEA_S02BodyOk(b,-1,EEA_S06_RELEASE_BODY_RATIO)) return -1;
   return 0;
  }

void EEA_S06StartRelease(EEA_S02Engine &e,const EEA_S02Bar &b,const double box_low,const double box_high,
                         const int d,const double ref_atr,const EEA_S02Config &c,EEA_S02Event &ev)
  {
   const string setup=EEA_S06SetupId(c);
   e.direction=d;
   e.zone_low=box_low;
   e.zone_high=box_high;
   e.key_level=(d>0 ? box_high : box_low);
   e.retest_extreme=(d>0 ? box_low : box_high);
   e.invalidation_price=e.retest_extreme;
   e.signal_atr=ref_atr;
   e.breakout_bar_utc=b.closed_at_utc;
   e.bars_since_break=0;
   e.bars_since_acceptance=0;
   e.bars_since_retest=0;
   e.candidate.canonical_symbol=e.canonical_symbol;
   e.candidate.timeframe=e.timeframe;
   e.candidate.config_version=e.config_version;
   e.candidate.candidate_id=StringFormat("%s-%s-%s-%s-%I64d",setup,e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
   e.candidate.setup_id=setup;
   e.candidate.direction=(d>0 ? "LONG" : "SHORT");
   e.candidate.key_level=e.key_level;
   e.candidate.zone_low=box_low;
   e.candidate.zone_high=box_high;
   e.candidate.invalidation_price=e.invalidation_price;
   e.candidate.detected_at_utc=b.closed_at_utc;
   e.candidate.expires_after_bars=1;
   if(EEA_S06IsVariantB(c))
     {
      // S06B enters on the release bar: the candidate is ready at once.
      e.candidate.triggered_at_utc=b.closed_at_utc;
      e.candidate.retest_extreme=e.retest_extreme;
      e.candidate.invalidation_price=e.invalidation_price;
      e.candidate.age_after_trigger_bars=0;
      EEA_S06Transition(e,ev,b.closed_at_utc,EEA_S02_TRIGGERED,"CANDIDATE_TRIGGERED",
                        d>0 ? "RELEASE_ABOVE_BOX" : "RELEASE_BELOW_BOX");
      return;
     }
   EEA_S06Transition(e,ev,b.closed_at_utc,EEA_S02_DETECTED,"COMPRESSION_RELEASED",
                     d>0 ? "RELEASE_ABOVE_BOX" : "RELEASE_BELOW_BOX");
  }

bool EEA_S06ProcessClosedBar(EEA_S02Engine &e,const EEA_S02Bar &b,const double box_low,const double box_high,
                             const double ref_atr,const double old_atr,const EEA_S02Config &c,EEA_S02Event &ev)
  {
   ev.bar_time_utc=b.closed_at_utc;
   ev.event_type="NO_TRANSITION";
   ev.state_before=EEA_S06StateName(e.state);
   ev.state_after=EEA_S06StateName(e.state);
   ev.reason_code="WAITING_FOR_COMPRESSION";
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
   if(e.canonical_symbol=="" || e.timeframe=="" || e.config_version=="")
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="ENGINE_IDENTITY_REQUIRED"; return false; }
   if(c.config_version!=e.config_version)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="CONFIG_VERSION_MISMATCH"; return false; }
   if(!EEA_S02ConfigValid(c) || !EEA_S06IsConfig(c))
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_RESEARCH_CONFIG"; return false; }
   if(!EEA_S02ValidBar(b) || !MathIsValidNumber(box_low) || !MathIsValidNumber(box_high) ||
      !MathIsValidNumber(ref_atr) || !MathIsValidNumber(old_atr))
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_CLOSED_BAR"; return false; }
   if(b.closed_at_utc==e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="DUPLICATE_CLOSED_BAR"; return true; }
   if(b.closed_at_utc<e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="OUT_OF_ORDER_CLOSED_BAR"; return true; }

   // A triggered candidate lives for its own bar only; this bar is scanned afresh.
   if(e.state==EEA_S02_TRIGGERED || EEA_S02IsTerminal(e.state))
     {
      datetime last=e.last_processed_bar_utc;
      EEA_S02Reset(e);
      e.candidate.setup_id=EEA_S06SetupId(c);
      e.last_processed_bar_utc=last;
      ev.state_before=EEA_S06StateName(e.state);
      ev.state_after=ev.state_before;
      ev.candidate_id="";
     }
   e.last_processed_bar_utc=b.closed_at_utc;

   if(e.state==EEA_S02_DETECTED)
     {
      // The bar after the release confirms or ends it; it never starts a new release.
      if(e.direction*(b.close-e.key_level)>0.0)
        {
         e.signal_atr=b.atr;
         e.candidate.triggered_at_utc=b.closed_at_utc;
         e.candidate.retest_extreme=e.retest_extreme;
         e.candidate.invalidation_price=e.invalidation_price;
         e.candidate.age_after_trigger_bars=0;
         EEA_S06Transition(e,ev,b.closed_at_utc,EEA_S02_TRIGGERED,"CANDIDATE_TRIGGERED","EXPANSION_CONFIRMED");
        }
      else
         EEA_S06Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","EXPANSION_NOT_CONFIRMED");
      return true;
     }

   if(!EEA_S06Compressed(box_low,box_high,ref_atr,old_atr))
     {
      EEA_S06SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_COMPRESSION");
      return true;
     }
   const int d=EEA_S06ReleaseDirection(b,box_low,box_high,ref_atr);
   if(d==0)
     {
      EEA_S06SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_RELEASE");
      return true;
     }
   EEA_S06StartRelease(e,b,box_low,box_high,d,ref_atr,c,ev);
   return true;
  }

#endif
