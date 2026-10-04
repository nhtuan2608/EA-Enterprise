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

struct EEA_ReactionBar      // one M1 bar (M5 when M1 history is out of reach), open time in UTC
  {
   long   t;
   int    seconds;          // bar length: 60 (M1) or 300 (M5)
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
   string cluster_label;    // all HIGH events at the same time for this symbol, sorted, " + " joined
   int    cluster_size;
   bool   cluster_lead;     // the first event of the cluster carries the cluster into the statistics
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
   // News Guard replay (P1): what the guard would have done around this event
   long   server_offset;                  // trade-server offset used for this event
   string price_resolution;               // M1, or M5 when M1 history is beyond the terminal limit
   bool   replay_ok;
   int    guard_block_end_min;            // minutes after T when new entries would resume
   bool   guard_covered;                  // volatility and spread were back to normal by then
   double residual_after_block_atr;       // largest move in the 60 minutes after the block, in ATR
   bool   has_pre_drift;
   double pre_drift_scalp_atr;            // move during the SCALP pre-block window (T-60 .. T)
   double pre_drift_swing_atr;            // move during the SWING pre-block window (T-180 .. T)
  };

void EEA_ReactionDefaults(EEA_Reaction &r)
  {
   r.key=""; r.source=""; r.symbol=""; r.currency=""; r.event_name=""; r.impact=""; r.event_utc=0;
   r.cluster_label=""; r.cluster_size=1; r.cluster_lead=true;
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
   r.server_offset=0; r.price_resolution=""; r.replay_ok=false; r.guard_block_end_min=-1; r.guard_covered=false; r.residual_after_block_atr=0.0;
   r.has_pre_drift=false; r.pre_drift_scalp_atr=0.0; r.pre_drift_swing_atr=0.0;
  }

// Recovery minutes used by the replay: -1 when either recovery never happened in its window.
double EEA_NewsReactionRecoveryMinRaw(const int spread_recovery_min,const int vol_recovery_min)
  {
   if(vol_recovery_min<0) return -1.0;
   return MathMax((double)vol_recovery_min,(double)MathMax(0,spread_recovery_min));
  }

// ---------------------------------------------------------------------------
// Cluster: HIGH events released at the same time move the price together, so their
// statistics are counted once per cluster. Labels are "CUR Event name"; the cluster
// label is the sorted list joined by " + ", the lead is the first label.
// ---------------------------------------------------------------------------
string EEA_NewsClusterLabel(string &labels[],const int n)
  {
   for(int i=1;i<n;i++)
     {
      string key=labels[i];
      int j=i-1;
      while(j>=0 && StringCompare(labels[j],key)>0) { labels[j+1]=labels[j]; j--; }
      labels[j+1]=key;
     }
   string out="";
   for(int i=0;i<n;i++)
     {
      bool duplicate=(i>0 && labels[i]==labels[i-1]);
      if(!duplicate) out+=(out=="" ? "" : " + ")+labels[i];
     }
   return out;
  }

string EEA_NewsReactionGroup(const string cluster_label,const string symbol)
  { return cluster_label+" x "+symbol; }

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
   for(int i=0;i<n;i++) { if(bars[i].t+bars[i].seconds<=time_utc) found=i; else break; }
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
   long last_close=n>0 ? bars[n-1].t+bars[n-1].seconds : 0;
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

// ---------------------------------------------------------------------------
// News Guard replay. Red: entries resume after POST_NEWS once volatility and spread are
// back (recovery), bounded by [post, max_normalize]. Yellow: SWING resumes at T+post.
// Covered = both recoveries happened by the block end. Residual = largest excursion in
// the 60 minutes after the block end. Pre drift = move inside the pre-block windows.
// ---------------------------------------------------------------------------
void EEA_NewsGuardReplay(EEA_Reaction &r,const EEA_ReactionBar &bars[],const int n,const int scalp_before_min,
                         const int swing_before_min,const int post_min,const int max_normalize_min)
  {
   r.replay_ok=false;
   const long T=r.event_utc;
   const double atr=r.atr_ref;
   if(atr<=0.0 || r.p0<=0.0) return;
   int recovery=(int)EEA_NewsReactionRecoveryMinRaw(r.spread_recovery_min,r.vol_recovery_min);
   if(r.impact=="INDIRECT") r.guard_block_end_min=post_min;
   else r.guard_block_end_min=recovery<0 ? max_normalize_min : MathMax(post_min,MathMin(max_normalize_min,recovery));
   r.guard_covered=(r.vol_recovery_min>=0 && r.vol_recovery_min<=r.guard_block_end_min &&
                    (r.spread_recovery_min<0 ? r.spread_source=="" : r.spread_recovery_min<=r.guard_block_end_min));
   const long block_end=T+r.guard_block_end_min*60;
   int k=EEA_NewsBarClosingBy(bars,n,block_end);
   if(k<0) return;
   double ref=bars[k].c, far=0.0;
   for(int i=k+1;i<n && bars[i].t<block_end+3600;i++)
      far=MathMax(far,MathMax(bars[i].h-ref,ref-bars[i].l));
   r.residual_after_block_atr=far/atr;
   int s60=EEA_NewsBarClosingBy(bars,n,T-scalp_before_min*60);
   int s180=EEA_NewsBarClosingBy(bars,n,T-swing_before_min*60);
   if(s60>=0 && s180>=0 && bars[s180].t>=T-swing_before_min*60-600)
     {
      r.has_pre_drift=true;
      r.pre_drift_scalp_atr=(r.p0-bars[s60].c)/atr;
      r.pre_drift_swing_atr=(r.p0-bars[s180].c)/atr;
     }
   r.replay_ok=true;
  }

// US daylight saving: second Sunday of March 07:00 UTC to first Sunday of November 06:00 UTC.
long EEA_NewsNthSundayUtc(const int year,const int month,const int nth)
  {
   MqlDateTime d; ZeroMemory(d); d.year=year; d.mon=month; d.day=1;
   long first=(long)StructToTime(d);
   MqlDateTime w; TimeToStruct((datetime)first,w);
   int offset=(7-w.day_of_week)%7;
   return first+(offset+(nth-1)*7)*86400;
  }

bool EEA_NewsUsDstAt(const long utc)
  {
   MqlDateTime d; TimeToStruct((datetime)utc,d);
   long start=EEA_NewsNthSundayUtc(d.year,3,2)+7*3600;
   long end=EEA_NewsNthSundayUtc(d.year,11,1)+6*3600;
   return utc>=start && utc<end;
  }

// Trade-server offset at a past instant for a broker on New York close time (summer
// offset now = winter offset + 1 hour). current_offset is the offset observed now.
long EEA_NewsServerOffsetAt(const long utc,const long current_offset,const long now_utc)
  {
   long winter=current_offset-(EEA_NewsUsDstAt(now_utc) ? 3600 : 0);
   return winter+(EEA_NewsUsDstAt(utc) ? 3600 : 0);
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
   bool   replay_ok;
   bool   covered;
   double residual_atr;
  };

struct EEA_ReactionStats
  {
   int    n;
   double median_move15_atr;
   double p80_move60_atr;
   double median_spread_ratio;
   double median_recovery_min;
   double reversal_rate;
   int    replay_n;
   double covered_rate;
   double median_residual_atr;
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
   s.reversal_rate=0.0; s.replay_n=0; s.covered_rate=0.0; s.median_residual_atr=0.0; s.has_suggestion=false; s.suggested_post_min=0; s.suggested_pre="";
   double m15[],m60[],sp[],rec[];
   ArrayResize(m15,count); ArrayResize(m60,count); ArrayResize(sp,count); ArrayResize(rec,count);
   int reversals=0, covered=0;
   double residual[];
   ArrayResize(residual,count);
   for(int i=0;i<count;i++)
     {
      if(!rows[i].ok || rows[i].group!=group) continue;
      if(rows[i].replay_ok) { residual[s.replay_n]=rows[i].residual_atr; if(rows[i].covered) covered++; s.replay_n++; }
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
   if(s.replay_n>0)
     { s.covered_rate=(double)covered/s.replay_n; s.median_residual_atr=EEA_NewsMedian(residual,s.replay_n); }
   if(s.n>=EEA_NR_MIN_SAMPLES_FOR_SUGGESTION)
     {
      s.has_suggestion=true;
      s.suggested_post_min=(int)(MathCeil(EEA_NewsPercentile(rec,s.n,0.8)/5.0)*5.0);
      s.suggested_pre=s.p80_move60_atr<0.5 ? "REDUCE" : "KEEP";
     }
  }

#endif
