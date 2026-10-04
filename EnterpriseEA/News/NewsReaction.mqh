#ifndef ENTERPRISE_EA_NEWS_REACTION_MQH
#define ENTERPRISE_EA_NEWS_REACTION_MQH

// News Reaction Recorder, pure part (design 2026-10-04 news reaction recorder, R1-R6).
// Measures what a HIGH impact event did: surprise against forecast, the M1 price path
// around the event in units of the pre-event ATR, spread blow-out and recovery. It never
// produces a trading direction (master specification 7.3) and never invents a number:
// missing data leaves the field invalid and names the reason (TC-020).

#define EEA_NR_HORIZONS 5
#define EEA_NR_MIN_SURPRISE_HISTORY 8      // R4
#define EEA_NR_MIN_SAMPLES_FOR_SUGGESTION 6 // R6

int EEA_NewsReactionHorizonMin(const int i)
  {
   // R1: 1, 5, 15, 60 and 240 minutes after the event.
   if(i==0) return 1;
   if(i==1) return 5;
   if(i==2) return 15;
   if(i==3) return 60;
   if(i==4) return 240;
   return 0;
  }

struct EEA_ReactionBar      // one M1 bar, open time in UTC
  {
   long   t;
   double o;
   double h;
   double l;
   double c;
   long   volume;
   double spread;           // price units
  };

struct EEA_ReactionSpread
  {
   long   t;                // UTC seconds
   double spread;           // price units
  };

struct EEA_Reaction
  {
   string key;
   string source;           // LIVE | BACKFILL
   string symbol;
   string currency;
   string event_name;
   string impact;           // DIRECT (red: own currency) | INDIRECT (yellow: another currency's strength)
   long   event_utc;
   // surprise
   bool   has_actual;
   bool   has_forecast;
   bool   has_previous;
   double actual;
   double forecast;
   double previous;
   double surprise_raw;
   string surprise_side;    // ABOVE | INLINE | BELOW | ""
   bool   has_surprise_std;
   double surprise_std;
   string surprise_quality;
   // price path
   double atr_ref;
   double point;
   double p0;
   bool   move_ok[EEA_NR_HORIZONS];
   double move[EEA_NR_HORIZONS];          // price units
   double max_up_60;
   double max_down_60;
   int    bars_to_extreme_60;
   string first_direction;
   bool   reversal_60;
   bool   has_follow_through;
   double follow_through;
   int    vol_recovery_min;               // -1 = not within 240 minutes
   bool   has_volume_ratio;
   double tick_volume_ratio_15m;
   // spread
   string spread_source;                  // TICKS | M1
   double spread_pre;
   double spread_peak;
   double spread_peak_ratio;
   int    spread_recovery_min;            // -1 = not within 60 minutes
   // News Guard
   int    guard_normal_min;               // -1 = unknown
   bool   guard_timeout;
   // EA trades (LIVE only)
   int    positions_open;
   string positions_detail;
   int    exits_in_window;
   int    be_before_news;
   int    be_would_have_hit_sl;
   int    entries_blocked;
   int    pending_cancelled;
   string quality;                        // OK | INCOMPLETE_<reason>
  };

void EEA_ReactionDefaults(EEA_Reaction &r)
  {
   r.key=""; r.source=""; r.symbol=""; r.currency=""; r.event_name=""; r.impact=""; r.event_utc=0;
   r.has_actual=false; r.has_forecast=false; r.has_previous=false; r.actual=0.0; r.forecast=0.0; r.previous=0.0;
   r.surprise_raw=0.0; r.surprise_side=""; r.has_surprise_std=false; r.surprise_std=0.0; r.surprise_quality="";
   r.atr_ref=0.0; r.point=0.0; r.p0=0.0;
   for(int i=0;i<EEA_NR_HORIZONS;i++) { r.move_ok[i]=false; r.move[i]=0.0; }
   r.max_up_60=0.0; r.max_down_60=0.0; r.bars_to_extreme_60=-1; r.first_direction=""; r.reversal_60=false;
   r.has_follow_through=false; r.follow_through=0.0; r.vol_recovery_min=-1;
   r.has_volume_ratio=false; r.tick_volume_ratio_15m=0.0;
   r.spread_source=""; r.spread_pre=0.0; r.spread_peak=0.0; r.spread_peak_ratio=0.0; r.spread_recovery_min=-1;
   r.guard_normal_min=-1; r.guard_timeout=false;
   r.positions_open=0; r.positions_detail=""; r.exits_in_window=0; r.be_before_news=0; r.be_would_have_hit_sl=0;
   r.entries_blocked=0; r.pending_cancelled=0; r.quality="";
  }

// ---------------------------------------------------------------------------
// Surprise (7.3): raw delta, side, and a standardized value only with enough history.
// ---------------------------------------------------------------------------
void EEA_NewsSurprise(EEA_Reaction &r,const int digits,const double &history_diffs[],const int history_count)
  {
   r.surprise_side=""; r.has_surprise_std=false; r.surprise_std=0.0;
   if(!r.has_actual) { r.surprise_quality="NO_ACTUAL"; return; }
   if(!r.has_forecast) { r.surprise_quality="NO_FORECAST"; return; }
   r.surprise_raw=r.actual-r.forecast;
   double half_unit=0.5*MathPow(10.0,-MathMax(0,digits));
   r.surprise_side=MathAbs(r.surprise_raw)<=half_unit ? "INLINE" : (r.surprise_raw>0.0 ? "ABOVE" : "BELOW");
   if(history_count<EEA_NR_MIN_SURPRISE_HISTORY) { r.surprise_quality="SURPRISE_HISTORY_INSUFFICIENT"; return; }
   double mean=0.0;
   for(int i=0;i<history_count;i++) mean+=history_diffs[i];
   mean/=history_count;
   double var=0.0;
   for(int i=0;i<history_count;i++) var+=(history_diffs[i]-mean)*(history_diffs[i]-mean);
   double sigma=MathSqrt(var/(history_count-1));
   if(sigma<=0.0) { r.surprise_quality="SURPRISE_SIGMA_ZERO"; return; }
   r.surprise_std=r.surprise_raw/sigma;
   r.has_surprise_std=true;
   r.surprise_quality="OK";
  }

// ---------------------------------------------------------------------------
// Price path from M1 bars sorted by open time (UTC). P0 is the close of the bar that
// ends at the event; move k is the close as of T+k. ATR_ref is the pre-event M5 ATR.
// ---------------------------------------------------------------------------
int EEA_NewsBarClosingBy(const EEA_ReactionBar &bars[],const int n,const long time_utc)
  {
   int found=-1;
   for(int i=0;i<n;i++) { if(bars[i].t+60<=time_utc) found=i; else break; }
   return found;
  }

void EEA_NewsReactionPath(EEA_Reaction &r,const EEA_ReactionBar &bars[],const int n)
  {
   const long T=r.event_utc;
   const double atr=r.atr_ref;
   if(atr<=0.0) { r.quality="INCOMPLETE_NO_ATR"; return; }
   int i0=EEA_NewsBarClosingBy(bars,n,T);
   if(i0<0 || bars[i0].t<T-600) { r.quality="INCOMPLETE_NO_PRE_PRICE"; return; }
   r.p0=bars[i0].c;
   long last_close=n>0 ? bars[n-1].t+60 : 0;
   for(int h=0;h<EEA_NR_HORIZONS;h++)
     {
      long target=T+EEA_NewsReactionHorizonMin(h)*60;
      int k=EEA_NewsBarClosingBy(bars,n,target);
      r.move_ok[h]=(k>i0 && last_close>=target-120);
      if(r.move_ok[h]) r.move[h]=bars[k].c-r.p0;
     }
   double hi=r.p0, lo=r.p0, far=0.0;
   int bars_seen=0;
   for(int i=0;i<n;i++)
     {
      if(bars[i].t<T || bars[i].t>=T+3600) continue;
      bars_seen++;
      hi=MathMax(hi,bars[i].h); lo=MathMin(lo,bars[i].l);
      double dist=MathMax(bars[i].h-r.p0,r.p0-bars[i].l);
      if(dist>far) { far=dist; r.bars_to_extreme_60=bars_seen; }
     }
   r.max_up_60=hi-r.p0; r.max_down_60=r.p0-lo;
   if(r.move_ok[1])
      r.first_direction=MathAbs(r.move[1])<0.1*atr ? "FLAT" : (r.move[1]>0.0 ? "UP" : "DOWN");
   if(r.move_ok[1] && r.move_ok[3])
     {
      r.reversal_60=MathAbs(r.move[1])>=0.3*atr && MathAbs(r.move[3])>=0.3*atr && r.move[1]*r.move[3]<0.0;
      if(MathAbs(r.move[1])>=0.3*atr) { r.has_follow_through=true; r.follow_through=r.move[3]/r.move[1]; }
     }
   // First 5-minute window after T whose range is back within one ATR_ref.
   r.vol_recovery_min=-1;
   for(int j=0;j<48 && r.vol_recovery_min<0;j++)
     {
      long w0=T+j*300, w1=w0+300;
      double wh=-DBL_MAX, wl=DBL_MAX; int cnt=0;
      for(int i=0;i<n;i++)
         if(bars[i].t>=w0 && bars[i].t<w1) { wh=MathMax(wh,bars[i].h); wl=MathMin(wl,bars[i].l); cnt++; }
      if(cnt>0 && wh-wl<=atr) r.vol_recovery_min=(j+1)*5;
     }
   r.quality=r.move_ok[3] ? "OK" : "INCOMPLETE_NO_60M_PRICE";
  }

double EEA_NewsMedian(double &values[],const int n)
  {
   if(n<=0) return 0.0;
   double copy[];
   ArrayResize(copy,n);
   for(int i=0;i<n;i++) copy[i]=values[i];
   ArraySort(copy);
   return (n%2==1) ? copy[n/2] : 0.5*(copy[n/2-1]+copy[n/2]);
  }

double EEA_NewsPercentile(double &values[],const int n,const double q)
  {
   if(n<=0) return 0.0;
   double copy[];
   ArrayResize(copy,n);
   for(int i=0;i<n;i++) copy[i]=values[i];
   ArraySort(copy);
   int idx=(int)MathCeil(q*n)-1;
   return copy[MathMax(0,MathMin(n-1,idx))];
  }

// Spread around the event: median in [T-30m, T-5m], peak in [T-1m, T+15m], minutes until
// it is back within 1.5x the pre-event median after the peak.
void EEA_NewsReactionSpread(EEA_Reaction &r,const EEA_ReactionSpread &samples[],const int n)
  {
   const long T=r.event_utc;
   double pre[];
   int pre_n=0;
   ArrayResize(pre,n);
   for(int i=0;i<n;i++) if(samples[i].t>=T-1800 && samples[i].t<=T-300) pre[pre_n++]=samples[i].spread;
   if(pre_n<3) return;
   r.spread_pre=EEA_NewsMedian(pre,pre_n);
   long peak_t=0;
   for(int i=0;i<n;i++)
      if(samples[i].t>=T-60 && samples[i].t<=T+900 && samples[i].spread>r.spread_peak)
        { r.spread_peak=samples[i].spread; peak_t=samples[i].t; }
   if(r.spread_pre>0.0) r.spread_peak_ratio=r.spread_peak/r.spread_pre;
   r.spread_recovery_min=-1;
   if(peak_t>0)
      for(int i=0;i<n;i++)
         if(samples[i].t>=peak_t && samples[i].t<=T+3600 && samples[i].spread<=1.5*r.spread_pre)
           { r.spread_recovery_min=(int)MathMax(0,MathCeil((double)(samples[i].t-T)/60.0)); break; }
  }

// ---------------------------------------------------------------------------
// Aggregation per (event, currency) x symbol and the suggested windows (R3: display only).
// ---------------------------------------------------------------------------
struct EEA_ReactionSummary
  {
   string group;            // currency + " " + event name + " x " + symbol
   double move15_atr;
   double move60_atr;
   double spread_ratio;
   double recovery_min;     // max(spread recovery, volatility recovery); 240 when never
   bool   reversal;
   bool   ok;
  };

struct EEA_ReactionStats
  {
   int    n;
   double median_move15_atr;
   double p80_move60_atr;
   double median_spread_ratio;
   double median_recovery_min;
   double reversal_rate;
   bool   has_suggestion;
   int    suggested_post_min;
   string suggested_pre;    // KEEP | REDUCE
  };

double EEA_NewsReactionRecoveryMin(const EEA_Reaction &r)
  {
   double a=r.spread_recovery_min<0 ? 240.0 : (double)r.spread_recovery_min;
   double b=r.vol_recovery_min<0 ? 240.0 : (double)r.vol_recovery_min;
   return MathMax(a,b);
  }

void EEA_NewsReactionStats(const EEA_ReactionSummary &rows[],const int count,const string group,EEA_ReactionStats &s)
  {
   s.n=0; s.median_move15_atr=0.0; s.p80_move60_atr=0.0; s.median_spread_ratio=0.0; s.median_recovery_min=0.0;
   s.reversal_rate=0.0; s.has_suggestion=false; s.suggested_post_min=0; s.suggested_pre="";
   double m15[],m60[],sp[],rec[];
   ArrayResize(m15,count); ArrayResize(m60,count); ArrayResize(sp,count); ArrayResize(rec,count);
   int reversals=0;
   for(int i=0;i<count;i++)
     {
      if(!rows[i].ok || rows[i].group!=group) continue;
      m15[s.n]=MathAbs(rows[i].move15_atr); m60[s.n]=MathAbs(rows[i].move60_atr);
      sp[s.n]=rows[i].spread_ratio; rec[s.n]=rows[i].recovery_min;
      if(rows[i].reversal) reversals++;
      s.n++;
     }
   if(s.n==0) return;
   s.median_move15_atr=EEA_NewsMedian(m15,s.n);
   s.p80_move60_atr=EEA_NewsPercentile(m60,s.n,0.8);
   s.median_spread_ratio=EEA_NewsMedian(sp,s.n);
   s.median_recovery_min=EEA_NewsMedian(rec,s.n);
   s.reversal_rate=(double)reversals/s.n;
   if(s.n>=EEA_NR_MIN_SAMPLES_FOR_SUGGESTION)
     {
      s.has_suggestion=true;
      s.suggested_post_min=(int)(MathCeil(EEA_NewsPercentile(rec,s.n,0.8)/5.0)*5.0);
      s.suggested_pre=s.p80_move60_atr<0.5 ? "REDUCE" : "KEEP";
     }
  }

#endif
