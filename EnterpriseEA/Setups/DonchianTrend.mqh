#ifndef ENTERPRISE_EA_T2_DONCHIAN_TREND_MQH
#define ENTERPRISE_EA_T2_DONCHIAN_TREND_MQH

#include "BreakRetest.mqh"

// G38 T2: H4 Donchian breakout on the D1 EMA200 side (research/long/discovery.py sig_t2, chosen on
// 2010-2016 only: channel 60 bars, stop 2 ATR, ATR trailing 3, no target). Pure closed-bar engine,
// POSITION profile. SHADOW only in this phase (InpT2Mode has no LIVE value): the Trade Manager has
// no POSITION profile with an ATR trail yet.
//
// A closed H4 bar triggers when its close is beyond the highest high (lowest low) of the
// EEA_T2_CHANNEL_BARS closed bars before it and the D1 side agrees (previous closed day's close
// above / below the EMA200 of daily closes). Every qualifying bar triggers, as in the research;
// one position per symbol is enforced downstream (live: one per symbol, side and profile; virtual
// results: the next trade starts after the previous one closed).
// Engine fields:
//   zone_low/zone_high   the channel (lowest low / highest high of the previous bars)
//   key_level            channel edge in the trade direction
//   retest_extreme       close - direction x EEA_T2_STOP_ATR x ATR (stop anchor at the signal close)
//   signal_atr           ATR14 of the signal bar (research: simple mean of the true ranges)

#define EEA_T2_CHANNEL_BARS 60
#define EEA_T2_STOP_ATR 2.0
#define EEA_T2_TRAIL_ATR 3.0
#define EEA_T2_EMA_DAYS 200
#define EEA_T2_TIMEOUT_BARS 180
#define EEA_T2_SHADOW_TARGET_R 10.0     // shadow risk path only (research has no target)

void EEA_T2V1Config(EEA_S02Config &c)
  {
   EEA_S02V1Config(c,"SWING");       // valid shared fields; T2 uses its own constants
   c.config_version="t2-v1-position-0.1.0";
   c.invalidation_buffer_atr=0.0;
   c.candidate_ttl_bars=1;           // enter at the signal close only
  }

bool EEA_T2IsConfig(const EEA_S02Config &c) { return StringFind(c.config_version,"t2-")==0; }

// +1 / -1 / 0 from daily closes in time order (oldest first), for the day after the last close:
// the last close against the EMA200 of all closes up to it (seeded with the first close).
int EEA_T2DailySide(const double &closes[],const int count)
  {
   if(count<EEA_T2_EMA_DAYS+1) return 0;
   const double k=2.0/(EEA_T2_EMA_DAYS+1);
   double e=closes[0];
   for(int i=1;i<count;i++) e=e+k*(closes[i]-e);
   if(closes[count-1]>e) return 1;
   if(closes[count-1]<e) return -1;
   return 0;
  }

void EEA_T2SetEvent(EEA_S02Event &ev,const EEA_S02Engine &e,const datetime at,
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

// Breakout direction of the bar: +1 above the channel with the D1 side up, -1 below with it down.
int EEA_T2Direction(const EEA_S02Bar &b,const double channel_low,const double channel_high,const int d1_side)
  {
   if(b.close>channel_high && d1_side==1) return 1;
   if(b.close<channel_low && d1_side==-1) return -1;
   return 0;
  }

bool EEA_T2ProcessClosedBar(EEA_S02Engine &e,const EEA_S02Bar &b,const double channel_low,const double channel_high,
                            const int d1_side,const EEA_S02Config &c,EEA_S02Event &ev)
  {
   EEA_T2SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_BREAKOUT");
   if(e.canonical_symbol=="" || e.timeframe=="" || e.config_version=="")
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="ENGINE_IDENTITY_REQUIRED"; return false; }
   if(c.config_version!=e.config_version)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="CONFIG_VERSION_MISMATCH"; return false; }
   if(!EEA_S02ConfigValid(c) || !EEA_T2IsConfig(c))
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_RESEARCH_CONFIG"; return false; }
   if(!EEA_S02ValidBar(b) || !MathIsValidNumber(channel_low) || !MathIsValidNumber(channel_high) ||
      channel_high<channel_low || b.atr<=0.0)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_CLOSED_BAR"; return false; }
   if(b.closed_at_utc==e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="DUPLICATE_CLOSED_BAR"; return true; }
   if(b.closed_at_utc<e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="OUT_OF_ORDER_CLOSED_BAR"; return true; }
   // A triggered candidate lives for its own bar only; this bar is scanned afresh.
   if(e.state!=EEA_S02_IDLE)
     {
      EEA_S02Reset(e);
      e.candidate.setup_id="T2";
     }
   e.last_processed_bar_utc=b.closed_at_utc;
   const int d=EEA_T2Direction(b,channel_low,channel_high,d1_side);
   if(d==0)
     {
      EEA_T2SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,
                     d1_side==0 ? "D1_SIDE_UNKNOWN" : "WAITING_FOR_BREAKOUT");
      return true;
     }
   const int before=e.state;
   e.direction=d;
   e.zone_low=channel_low;
   e.zone_high=channel_high;
   e.key_level=(d>0 ? channel_high : channel_low);
   e.signal_atr=b.atr;
   e.retest_extreme=b.close-d*EEA_T2_STOP_ATR*b.atr;
   e.invalidation_price=e.retest_extreme;
   e.breakout_bar_utc=b.closed_at_utc;
   e.state=EEA_S02_TRIGGERED;
   e.candidate.canonical_symbol=e.canonical_symbol;
   e.candidate.timeframe=e.timeframe;
   e.candidate.config_version=e.config_version;
   e.candidate.candidate_id=StringFormat("T2-%s-%s-%s-%I64d",e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
   e.candidate.setup_id="T2";
   e.candidate.direction=(d>0 ? "LONG" : "SHORT");
   e.candidate.state="TRIGGERED";
   e.candidate.key_level=e.key_level;
   e.candidate.zone_low=channel_low;
   e.candidate.zone_high=channel_high;
   e.candidate.retest_extreme=e.retest_extreme;
   e.candidate.invalidation_price=e.invalidation_price;
   e.candidate.detected_at_utc=b.closed_at_utc;
   e.candidate.triggered_at_utc=b.closed_at_utc;
   e.candidate.expires_after_bars=1;
   e.candidate.age_after_trigger_bars=0;
   e.candidate.reason_code=(d>0 ? "CLOSE_ABOVE_CHANNEL" : "CLOSE_BELOW_CHANNEL");
   EEA_T2SetEvent(ev,e,b.closed_at_utc,"CANDIDATE_TRIGGERED",before,e.candidate.reason_code);
   return true;
  }

#endif
