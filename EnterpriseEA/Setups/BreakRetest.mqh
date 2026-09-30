#ifndef ENTERPRISE_EA_S02_BREAK_RETEST_MQH
#define ENTERPRISE_EA_S02_BREAK_RETEST_MQH

// Pure closed-bar S02 prototype. The caller supplies completed bars and a key level.
// Every numeric threshold in S02_ResearchSeedConfig is a research seed, not a live default.

enum ENUM_EEA_S02_STATE
  {
   EEA_S02_IDLE=0,
   EEA_S02_DETECTED=1,
   EEA_S02_ARMED=2,
   EEA_S02_RETESTING=3,
   EEA_S02_TRIGGERED=4,
   EEA_S02_INVALIDATED=5,
   EEA_S02_EXPIRED=6
  };

struct EEA_S02Bar
  {
   datetime closed_at_utc;
   double open;
   double high;
   double low;
   double close;
   double atr;
  };

struct EEA_S02Config
  {
   string config_version;
   double break_buffer_atr;           // research seed: 0.10
   double acceptance_buffer_atr;      // research seed: 0.00
   double retest_tolerance_atr;       // research seed: 0.15
   double invalidation_buffer_atr;    // research seed: 0.10
   double hold_buffer_atr;            // research seed: 0.05
   int max_bars_to_accept;            // research seed: 2
   int max_bars_to_retest;            // research seed: 3
   int max_bars_for_reaction;         // research seed: 2
   int candidate_ttl_bars;            // research seed: 3
  };

struct EEA_S02Candidate
  {
   string candidate_id;
   string setup_id;
   string direction;
   string state;
   double key_level;
   double invalidation_price;
   datetime detected_at_utc;
   datetime triggered_at_utc;
   int expires_after_bars;
   int age_after_trigger_bars;
   string canonical_symbol;
   string timeframe;
   string config_version;
   string reason_code;
  };

struct EEA_S02Event
  {
   datetime bar_time_utc;
   string event_type;
   string state_before;
   string state_after;
   string reason_code;
   string candidate_id;
   string canonical_symbol;
   string timeframe;
   string config_version;
  };

struct EEA_S02Engine
  {
   string canonical_symbol;
   string timeframe;
   string config_version;
   int state;
   int direction; // +1 long, -1 short, 0 none
   datetime last_processed_bar_utc;
   datetime breakout_bar_utc;
   double key_level;
   double signal_atr;
   double invalidation_price;
   double retest_close;
   int bars_since_break;
   int bars_since_acceptance;
   int bars_since_retest;
   EEA_S02Candidate candidate;
  };

void EEA_S02ResearchSeedConfig(EEA_S02Config &c)
  {
   c.config_version="s02-offline-research-v0.1.0";
   c.break_buffer_atr=0.10;
   c.acceptance_buffer_atr=0.00;
   c.retest_tolerance_atr=0.15;
   c.invalidation_buffer_atr=0.10;
   c.hold_buffer_atr=0.05;
   c.max_bars_to_accept=2;
   c.max_bars_to_retest=3;
   c.max_bars_for_reaction=2;
   c.candidate_ttl_bars=3;
  }

bool EEA_S02ConfigValid(const EEA_S02Config &c)
  {
   return c.config_version!="" && c.break_buffer_atr>=0.0 &&
          c.acceptance_buffer_atr>=0.0 && c.retest_tolerance_atr>0.0 &&
          c.invalidation_buffer_atr>=0.0 && c.hold_buffer_atr>=0.0 &&
          c.max_bars_to_accept>0 && c.max_bars_to_retest>0 &&
          c.max_bars_for_reaction>0 && c.candidate_ttl_bars>0;
  }

string EEA_S02StateName(const int state)
  {
   if(state==EEA_S02_DETECTED) return "DETECTED";
   if(state==EEA_S02_ARMED) return "ARMED";
   if(state==EEA_S02_RETESTING) return "RETESTING";
   if(state==EEA_S02_TRIGGERED) return "TRIGGERED";
   if(state==EEA_S02_INVALIDATED) return "INVALIDATED";
   if(state==EEA_S02_EXPIRED) return "EXPIRED";
   return "IDLE";
  }

bool EEA_S02IsTerminal(const int state)
  {
   return state==EEA_S02_INVALIDATED || state==EEA_S02_EXPIRED;
  }

void EEA_S02ClearCandidate(EEA_S02Candidate &c)
  {
   c.candidate_id="";
   c.setup_id="S02";
   c.direction="NONE";
   c.state="IDLE";
   c.key_level=0.0;
   c.invalidation_price=0.0;
   c.detected_at_utc=0;
   c.triggered_at_utc=0;
   c.expires_after_bars=0;
   c.age_after_trigger_bars=0;
   c.canonical_symbol="";
   c.timeframe="";
   c.config_version="";
   c.reason_code="";
  }

void EEA_S02Reset(EEA_S02Engine &e)
  {
   // Identity belongs to the per-symbol/timeframe engine and survives terminal-state resets.
   e.state=EEA_S02_IDLE;
   e.direction=0;
   e.last_processed_bar_utc=0;
   e.breakout_bar_utc=0;
   e.key_level=0.0;
   e.signal_atr=0.0;
   e.invalidation_price=0.0;
   e.retest_close=0.0;
   e.bars_since_break=0;
   e.bars_since_acceptance=0;
   e.bars_since_retest=0;
   EEA_S02ClearCandidate(e.candidate);
  }

void EEA_S02Init(EEA_S02Engine &e,const string canonical_symbol,const string timeframe,const string config_version)
  {
   e.canonical_symbol="";
   e.timeframe="";
   e.config_version="";
   EEA_S02Reset(e);
   e.canonical_symbol=canonical_symbol;
   e.timeframe=timeframe;
   e.config_version=config_version;
  }

bool EEA_S02ValidBar(const EEA_S02Bar &b)
  {
   if(b.closed_at_utc<=0 || !MathIsValidNumber(b.open) || !MathIsValidNumber(b.high) ||
      !MathIsValidNumber(b.low) || !MathIsValidNumber(b.close) || !MathIsValidNumber(b.atr)) return false;
   if(b.atr<=0.0 || b.high<b.low || b.high<MathMax(b.open,b.close) || b.low>MathMin(b.open,b.close)) return false;
   return true;
  }

void EEA_S02SetEvent(EEA_S02Event &ev,const EEA_S02Engine &e,const datetime at,
                     const string event_type,const int before,const string reason)
  {
   ev.bar_time_utc=at;
   ev.event_type=event_type;
   ev.state_before=EEA_S02StateName(before);
   ev.state_after=EEA_S02StateName(e.state);
   ev.reason_code=reason;
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
  }

void EEA_S02Transition(EEA_S02Engine &e,EEA_S02Event &ev,const datetime at,
                       const int next_state,const string event_type,const string reason)
  {
   int before=e.state;
   e.state=next_state;
   e.candidate.state=EEA_S02StateName(next_state);
   e.candidate.reason_code=reason;
   EEA_S02SetEvent(ev,e,at,event_type,before,reason);
  }

bool EEA_S02ProcessClosedBar(EEA_S02Engine &e,const EEA_S02Bar &b,
                             const double key_level,const EEA_S02Config &c,
                             EEA_S02Event &ev)
  {
   int before=e.state;
   ev.bar_time_utc=b.closed_at_utc;
   ev.event_type="NO_TRANSITION";
   ev.state_before=EEA_S02StateName(e.state);
   ev.state_after=EEA_S02StateName(e.state);
   ev.reason_code="WAITING_FOR_BREAK";
   ev.candidate_id=e.candidate.candidate_id;
   ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe;
   ev.config_version=e.config_version;
   if(e.canonical_symbol=="" || e.timeframe=="" || e.config_version=="")
     {
      ev.event_type="INPUT_REJECTED";
      ev.reason_code="ENGINE_IDENTITY_REQUIRED";
      return false;
     }
   if(c.config_version!=e.config_version)
     {
      ev.event_type="INPUT_REJECTED";
      ev.reason_code="CONFIG_VERSION_MISMATCH";
      return false;
     }
   if(!EEA_S02ConfigValid(c))
     {
      ev.event_type="INPUT_REJECTED";
      ev.reason_code="INVALID_RESEARCH_CONFIG";
      return false;
     }
   if(!EEA_S02ValidBar(b) || !MathIsValidNumber(key_level))
     {
      ev.event_type="INPUT_REJECTED";
      ev.reason_code="INVALID_CLOSED_BAR";
      return false;
     }
   if(b.closed_at_utc==e.last_processed_bar_utc)
     {
      ev.event_type="BAR_IGNORED";
      ev.reason_code="DUPLICATE_CLOSED_BAR";
      return true;
     }
   if(b.closed_at_utc<e.last_processed_bar_utc)
     {
      ev.event_type="BAR_IGNORED";
      ev.reason_code="OUT_OF_ORDER_CLOSED_BAR";
      return true;
     }
   if(EEA_S02IsTerminal(e.state))
     {
      datetime last=e.last_processed_bar_utc;
      EEA_S02Reset(e);
      e.last_processed_bar_utc=last;
      before=e.state;
      ev.state_before=EEA_S02StateName(e.state);
      ev.state_after=ev.state_before;
      ev.candidate_id="";
     }
   e.last_processed_bar_utc=b.closed_at_utc;

   if(e.state==EEA_S02_IDLE)
     {
      if(b.close>key_level+c.break_buffer_atr*b.atr)
        {
         e.direction=1;
         e.key_level=key_level;
         e.signal_atr=b.atr;
         e.breakout_bar_utc=b.closed_at_utc;
         e.invalidation_price=key_level-c.invalidation_buffer_atr*b.atr;
         e.candidate.canonical_symbol=e.canonical_symbol;
         e.candidate.timeframe=e.timeframe;
         e.candidate.config_version=e.config_version;
         e.candidate.candidate_id=StringFormat("S02-%s-%s-%s-%I64d",e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
         e.candidate.setup_id="S02";
         e.candidate.direction="LONG";
         e.candidate.key_level=key_level;
         e.candidate.invalidation_price=e.invalidation_price;
         e.candidate.detected_at_utc=b.closed_at_utc;
         e.candidate.expires_after_bars=c.candidate_ttl_bars;
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_DETECTED,"BREAK_DETECTED","BREAK_CLOSED_ABOVE_KEY");
        }
      else if(b.close<key_level-c.break_buffer_atr*b.atr)
        {
         e.direction=-1;
         e.key_level=key_level;
         e.signal_atr=b.atr;
         e.breakout_bar_utc=b.closed_at_utc;
         e.invalidation_price=key_level+c.invalidation_buffer_atr*b.atr;
         e.candidate.canonical_symbol=e.canonical_symbol;
         e.candidate.timeframe=e.timeframe;
         e.candidate.config_version=e.config_version;
         e.candidate.candidate_id=StringFormat("S02-%s-%s-%s-%I64d",e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
         e.candidate.setup_id="S02";
         e.candidate.direction="SHORT";
         e.candidate.key_level=key_level;
         e.candidate.invalidation_price=e.invalidation_price;
         e.candidate.detected_at_utc=b.closed_at_utc;
         e.candidate.expires_after_bars=c.candidate_ttl_bars;
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_DETECTED,"BREAK_DETECTED","BREAK_CLOSED_BELOW_KEY");
        }
      return true;
     }

   if(e.state==EEA_S02_DETECTED)
     {
      e.bars_since_break++;
      bool accepted=(e.direction>0 ? b.close>e.key_level+c.acceptance_buffer_atr*e.signal_atr :
                                      b.close<e.key_level-c.acceptance_buffer_atr*e.signal_atr);
      bool failed=(e.direction>0 ? b.close<e.invalidation_price : b.close>e.invalidation_price);
      if(failed)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"BREAK_INVALIDATED","BREAK_REJECTED_BACK_THROUGH_INVALIDATION");
      else if(accepted)
        {
         e.bars_since_acceptance=0;
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_ARMED,"BREAK_ACCEPTED","ACCEPTANCE_CLOSED_BEYOND_KEY");
        }
      else if(e.bars_since_break>=c.max_bars_to_accept)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","ACCEPTANCE_NOT_CONFIRMED");
      else
         EEA_S02SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_ACCEPTANCE");
      return true;
     }

   if(e.state==EEA_S02_ARMED)
     {
      e.bars_since_acceptance++;
      bool failed=(e.direction>0 ? b.close<e.invalidation_price : b.close>e.invalidation_price);
      if(failed)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"RETEST_INVALIDATED","LEVEL_LOST_BEFORE_RETEST");
      else
        {
         double tol=c.retest_tolerance_atr*e.signal_atr;
         bool touched=(e.direction>0 ? b.low<=e.key_level+tol && b.high>=e.key_level-tol :
                                       b.high>=e.key_level-tol && b.low<=e.key_level+tol);
         if(touched)
           {
            e.retest_close=b.close;
            e.bars_since_retest=0;
            EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_RETESTING,"RETEST_TOUCHED","RETEST_ZONE_TOUCHED");
           }
         else if(e.bars_since_acceptance>=c.max_bars_to_retest)
            EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","NO_RETEST_WITHIN_WINDOW");
         else
            EEA_S02SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_RETEST");
        }
      return true;
     }

   if(e.state==EEA_S02_RETESTING)
     {
      e.bars_since_retest++;
      bool failed=(e.direction>0 ? b.close<e.invalidation_price : b.close>e.invalidation_price);
      bool reaction=(e.direction>0 ? b.close>e.key_level+c.hold_buffer_atr*e.signal_atr &&
                                     b.close>b.open && b.close>e.retest_close :
                                     b.close<e.key_level-c.hold_buffer_atr*e.signal_atr &&
                                     b.close<b.open && b.close<e.retest_close);
      if(failed)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_INVALIDATED,"RETEST_INVALIDATED","RETEST_CLOSED_THROUGH_INVALIDATION");
      else if(reaction)
        {
         e.candidate.triggered_at_utc=b.closed_at_utc;
         e.candidate.age_after_trigger_bars=0;
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_TRIGGERED,"CANDIDATE_TRIGGERED","RETEST_HOLD_REACTION_CONFIRMED");
        }
      else if(e.bars_since_retest>=c.max_bars_for_reaction)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"SETUP_EXPIRED","HOLD_REACTION_TIMEOUT");
      else
         EEA_S02SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_HOLD_REACTION");
      return true;
     }

   if(e.state==EEA_S02_TRIGGERED)
     {
      e.candidate.age_after_trigger_bars++;
      if(e.candidate.age_after_trigger_bars>=e.candidate.expires_after_bars)
         EEA_S02Transition(e,ev,b.closed_at_utc,EEA_S02_EXPIRED,"CANDIDATE_EXPIRED","CANDIDATE_TTL_REACHED");
      else
         EEA_S02SetEvent(ev,e,b.closed_at_utc,"CANDIDATE_PENDING",before,"CANDIDATE_TTL_ACTIVE");
      return true;
     }
   return true;
  }

#endif
