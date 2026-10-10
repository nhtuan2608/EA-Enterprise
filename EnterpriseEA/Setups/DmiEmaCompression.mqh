#ifndef ENTERPRISE_EA_S07_DMI_EMA_COMPRESSION_MQH
#define ENTERPRISE_EA_S07_DMI_EMA_COMPRESSION_MQH

#include "BreakRetest.mqh"

// G72 S07: compression -> expansion on DMI + the EMA ribbon (research G67-G71,
// research/long/g67_dmi_ema.py signals/walk; design specs/2026-10-09-s07-dmi-ema-design.md).
// Pure closed-bar functions; the runtime supplies bars oldest first with the indicator arrays.
//
// Signal at the close of bar i, direction d:
//   1. compression: the lowest ADX of the W bars before i is <= 20 and |+DI - -DI| <= 6 there;
//   2. ADX turns up: ADX[i] > ADX[i-1] and ADX[i] - that low <= 10;
//   3. DI with d and widening: d x (+DI - -DI) > 0 and larger than on bar i-1;
//   4. the close is beyond all four EMAs 21/55/100/200 on the side of d;
//   5. the last completed H4 bar closed on the side of d of the H4 EMA200.
// Stop anchor: the lowest low (d=+1) / highest high (d=-1) of bars i-W..i, ignoring the bars
// before a break longer than 6 hours (weekend). The plan adds 0.1 ATR and keeps the stop
// between 1 and 4 ATR (Wilder ATR14 of bar i).
// Setups: "S07" (buy, M30, the base trade), "S07A" (buy, M15/H1/H4, pyramiding sources only),
// "S07S" (sell, H1, SHADOW only, with the L2 location: the window high reached the H4 EMA200
// minus 0.5 ATR), "S07E" (G73 V1, SHADOW only: the M30 buy rule on the forming M30 bar at every
// closed M15 bar, EEA_S07ProvisionalSignal).
// Indicators follow TradingView / the research: EMA alpha 2/(n+1) and Wilder RMA (alpha 1/14)
// for TR, +DM, -DM and DX, each seeded with its first value.

#define EEA_S07_ADX_LOW 20.0
#define EEA_S07_DI_GAP 6.0
#define EEA_S07_ADX_RISE 10.0
#define EEA_S07_DMI_PERIOD 14
#define EEA_S07_STOP_BUFFER_ATR 0.10
#define EEA_S07_STOP_MIN_ATR 1.0
#define EEA_S07_STOP_MAX_ATR 4.0
#define EEA_S07_GAP_SECONDS 21600         // 6 hours
#define EEA_S07_TARGET_R 8.0
#define EEA_S07_TRAIL_SWITCH_R 3.0        // EMA55 -> EMA100 once the trade has run 3R
#define EEA_S07_L2_ATR 0.5
#define EEA_S07_MAX_ADDS 2
#define EEA_S07_MAX_OPEN_LEGS 3
#define EEA_S07_ADD_SPACING_SECONDS 3600
#define EEA_S07_H4_EMA 200

// Compression window, cool-down and maximum hold (bars of the entry timeframe), G69/G70 table.
int EEA_S07WindowBars(const string timeframe)
  { return timeframe=="M15" ? 16 : timeframe=="M30" ? 8 : timeframe=="H1" ? 4 : 8; }
int EEA_S07HoldBars(const string timeframe)
  { return timeframe=="M15" ? 480 : timeframe=="M30" ? 240 : timeframe=="H1" ? 120 : 240; }

void EEA_S07V1Config(EEA_S02Config &c,const string setup,const string timeframe)
  {
   EEA_S02V1Config(c,"SWING");       // valid shared fields; S07 uses its own constants
   string tf=timeframe; StringToLower(tf);
   string s=setup; StringToLower(s);
   c.config_version=s+"-v1-"+tf+"-0.1.0";
   c.invalidation_buffer_atr=0.0;
   c.candidate_ttl_bars=1;           // enter at the signal close only
  }

bool EEA_S07IsConfig(const EEA_S02Config &c) { return StringFind(c.config_version,"s07")==0; }

void EEA_S07Ema(const MqlRates &rates[],const int n,const int period,double &out[])
  {
   ArrayResize(out,n);
   if(n<=0) return;
   const double k=2.0/(period+1);
   out[0]=rates[0].close;
   for(int i=1;i<n;i++) out[i]=out[i-1]+k*(rates[i].close-out[i-1]);
  }

// Wilder DMI and ATR over the whole array (research g67_dmi_ema.load).
void EEA_S07Dmi(const MqlRates &rates[],const int n,double &pdi[],double &mdi[],double &adx[],double &atr[])
  {
   ArrayResize(pdi,n); ArrayResize(mdi,n); ArrayResize(adx,n); ArrayResize(atr,n);
   if(n<=0) return;
   const double a=1.0/EEA_S07_DMI_PERIOD;
   double tr_s=0.0,pdm_s=0.0,mdm_s=0.0,adx_s=0.0;
   for(int i=0;i<n;i++)
     {
      const double pc=(i==0 ? rates[0].close : rates[i-1].close);
      const double tr=MathMax(rates[i].high-rates[i].low,MathMax(MathAbs(rates[i].high-pc),MathAbs(rates[i].low-pc)));
      const double up=(i==0 ? 0.0 : rates[i].high-rates[i-1].high);
      const double dn=(i==0 ? 0.0 : rates[i-1].low-rates[i].low);
      const double pdm=(up>dn && up>0.0) ? up : 0.0;
      const double mdm=(dn>up && dn>0.0) ? dn : 0.0;
      if(i==0) { tr_s=tr; pdm_s=pdm; mdm_s=mdm; }
      else { tr_s+=a*(tr-tr_s); pdm_s+=a*(pdm-pdm_s); mdm_s+=a*(mdm-mdm_s); }
      pdi[i]=(tr_s>0.0 ? 100.0*pdm_s/tr_s : 0.0);
      mdi[i]=(tr_s>0.0 ? 100.0*mdm_s/tr_s : 0.0);
      const double sum=pdi[i]+mdi[i];
      const double dx=(sum>1e-9 ? 100.0*MathAbs(pdi[i]-mdi[i])/sum : 0.0);
      adx_s=(i==0 ? dx : adx_s+a*(dx-adx_s));
      adx[i]=adx_s;
      atr[i]=tr_s;
     }
  }

// Direction of a signal at bar i (+1 / -1 / 0); h4_side is the last completed H4 bar against
// the H4 EMA200 (+1 above, -1 below, 0 unknown).
int EEA_S07SignalAt(const MqlRates &rates[],const int i,const int window,
                    const double &e21[],const double &e55[],const double &e100[],const double &e200[],
                    const double &pdi[],const double &mdi[],const double &adx[],const int h4_side)
  {
   if(i<window+1) return 0;
   int k=i-window;
   for(int j=i-window+1;j<i;j++) if(adx[j]<adx[k]) k=j;     // first lowest, like numpy argmin
   if(adx[k]>EEA_S07_ADX_LOW || MathAbs(pdi[k]-mdi[k])>EEA_S07_DI_GAP) return 0;
   if(!(adx[i]>adx[i-1] && adx[i]-adx[k]<=EEA_S07_ADX_RISE)) return 0;
   const double gap=pdi[i]-mdi[i], gap_prev=pdi[i-1]-mdi[i-1];
   const double hi=MathMax(MathMax(e21[i],e55[i]),MathMax(e100[i],e200[i]));
   const double lo=MathMin(MathMin(e21[i],e55[i]),MathMin(e100[i],e200[i]));
   int d=0;
   if(gap>0.0 && gap>gap_prev && rates[i].close>hi) d=1;
   else if(gap<0.0 && gap<gap_prev && rates[i].close<lo) d=-1;
   if(d==0 || h4_side!=d) return 0;
   return d;
  }

// Stop anchor (no buffer) of a signal at bar i: the window extreme after the last long break.
double EEA_S07StopAnchor(const MqlRates &rates[],const int i,const int window,const int d)
  {
   int a0=i-window;
   for(int k=i;k>i-window;k--)
      if((long)rates[k].time-(long)rates[k-1].time>EEA_S07_GAP_SECONDS) { a0=k; break; }
   double x=(d==1 ? rates[a0].low : rates[a0].high);
   for(int k=a0+1;k<=i;k++) x=(d==1 ? MathMin(x,rates[k].low) : MathMax(x,rates[k].high));
   return x;
  }

// S07S location L2: the window high reached the H4 EMA200 minus 0.5 ATR.
bool EEA_S07SellLocation(const MqlRates &rates[],const int i,const int window,const double h4_ema,const double atr)
  {
   if(h4_ema<=0.0 || atr<=0.0) return false;
   double top=rates[i-window].high;
   for(int k=i-window+1;k<=i;k++) top=MathMax(top,rates[k].high);
   return top>=h4_ema-EEA_S07_L2_ATR*atr;
  }

// G73 V1 (S07E): the rule on a forming bar. rates[0..q] are the closed bars of the entry timeframe
// (indicator arrays over them); the forming bar (time forming_time, open fo, high fh, low fl, price fc)
// gets provisional Wilder DMI / ATR and EMAs from bar q. The compression window is bars q-W+1..q
// (research g73_early.v1_trades). Returns the direction (0 = none) with the provisional ATR and the
// stop anchor (lowest low / highest high of bars q-W+1..q and the forming bar, after a break > 6 h).
int EEA_S07ProvisionalSignal(const MqlRates &rates[],const int q,const int window,
                             const double &e21[],const double &e55[],const double &e100[],const double &e200[],
                             const double &pdi[],const double &mdi[],const double &adx[],const double &atr[],
                             const long forming_time,const double fo,const double fh,const double fl,
                             const double fc,const int h4_side,double &atr_p,double &anchor)
  {
   atr_p=0.0; anchor=0.0;
   if(q<=window || h4_side==0 || atr[q]<=0.0) return 0;
   int k=q-window+1;
   for(int j=k+1;j<=q;j++) if(adx[j]<adx[k]) k=j;
   if(adx[k]>EEA_S07_ADX_LOW || MathAbs(pdi[k]-mdi[k])>EEA_S07_DI_GAP) return 0;
   const double a=1.0/EEA_S07_DMI_PERIOD;
   const double pc=rates[q].close;
   const double tr=MathMax(fh-fl,MathMax(MathAbs(fh-pc),MathAbs(fl-pc)));
   const double up=fh-rates[q].high, dn=rates[q].low-fl;
   const double pdm=(up>dn && up>0.0) ? up : 0.0;
   const double mdm=(dn>up && dn>0.0) ? dn : 0.0;
   const double pd0=pdi[q]*atr[q]/100.0, md0=mdi[q]*atr[q]/100.0;
   const double ts=atr[q]+a*(tr-atr[q]);
   if(ts<=0.0) return 0;
   const double p=100.0*(pd0+a*(pdm-pd0))/ts, m=100.0*(md0+a*(mdm-md0))/ts;
   const double sum=p+m;
   const double dx=(sum>1e-9 ? 100.0*MathAbs(p-m)/sum : 0.0);
   const double adx_p=adx[q]+a*(dx-adx[q]);
   if(!(adx_p>adx[q] && adx_p-adx[k]<=EEA_S07_ADX_RISE)) return 0;
   const double x21=e21[q]+2.0/22.0*(fc-e21[q]), x55=e55[q]+2.0/56.0*(fc-e55[q]);
   const double x100=e100[q]+2.0/101.0*(fc-e100[q]), x200=e200[q]+2.0/201.0*(fc-e200[q]);
   const double hi=MathMax(MathMax(x21,x55),MathMax(x100,x200));
   const double lo=MathMin(MathMin(x21,x55),MathMin(x100,x200));
   const double gap=p-m, gp=pdi[q]-mdi[q];
   int d=0;
   if(gap>0.0 && gap>gp && fc>hi) d=1;
   else if(gap<0.0 && gap<gp && fc<lo) d=-1;
   if(d==0 || d!=h4_side) return 0;
   int a0=q+1-window;
   if(forming_time-(long)rates[q].time>EEA_S07_GAP_SECONDS) a0=q+1;
   else
      for(int j=q;j>a0;j--) if((long)rates[j].time-(long)rates[j-1].time>EEA_S07_GAP_SECONDS) { a0=j; break; }
   double x=(d==1 ? fl : fh);
   for(int j=a0;j<=q;j++) x=(d==1 ? MathMin(x,rates[j].low) : MathMax(x,rates[j].high));
   atr_p=ts; anchor=x;
   return d;
  }

void EEA_S07SetEvent(EEA_S02Event &ev,const EEA_S02Engine &e,const datetime at,const string event_type,
                     const int before,const string reason)
  {
   ev.bar_time_utc=at; ev.event_type=event_type;
   ev.state_before=EEA_S02StateName(before); ev.state_after=EEA_S02StateName(e.state);
   ev.reason_code=reason; ev.candidate_id=e.candidate.candidate_id; ev.canonical_symbol=e.canonical_symbol;
   ev.timeframe=e.timeframe; ev.config_version=e.config_version;
  }

// One closed bar. `d` is the signal of that bar (EEA_S07SignalAt plus the setup's own side and
// location rules, 0 = none). A triggered candidate lives for its own bar only.
bool EEA_S07ProcessClosedBar(EEA_S02Engine &e,const string setup,const EEA_S02Bar &b,const int d,
                             const double anchor,const EEA_S02Config &c,EEA_S02Event &ev)
  {
   EEA_S07SetEvent(ev,e,b.closed_at_utc,"NO_TRANSITION",e.state,"WAITING_FOR_COMPRESSION_BREAK");
   if(e.canonical_symbol=="" || e.timeframe=="" || e.config_version=="")
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="ENGINE_IDENTITY_REQUIRED"; return false; }
   if(c.config_version!=e.config_version || !EEA_S02ConfigValid(c) || !EEA_S07IsConfig(c))
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="CONFIG_VERSION_MISMATCH"; return false; }
   if(!EEA_S02ValidBar(b) || b.atr<=0.0)
     { ev.event_type="INPUT_REJECTED"; ev.reason_code="INVALID_CLOSED_BAR"; return false; }
   if(b.closed_at_utc<=e.last_processed_bar_utc)
     { ev.event_type="BAR_IGNORED"; ev.reason_code="DUPLICATE_OR_OLD_CLOSED_BAR"; return true; }
   if(e.state!=EEA_S02_IDLE) { EEA_S02Reset(e); }
   e.candidate.setup_id=setup;
   e.last_processed_bar_utc=b.closed_at_utc;
   if(d==0 || anchor<=0.0) return true;
   const int before=e.state;
   e.direction=d;
   e.zone_low=0.0; e.zone_high=0.0;            // no structure exit for S07 (Trade Manager)
   e.key_level=b.close;
   e.signal_atr=b.atr;
   e.retest_extreme=anchor;
   e.invalidation_price=anchor;
   e.breakout_bar_utc=b.closed_at_utc;
   e.state=EEA_S02_TRIGGERED;
   e.candidate.canonical_symbol=e.canonical_symbol;
   e.candidate.timeframe=e.timeframe;
   e.candidate.config_version=e.config_version;
   e.candidate.candidate_id=StringFormat("%s-%s-%s-%s-%I64d",setup,e.canonical_symbol,e.timeframe,e.config_version,(long)b.closed_at_utc);
   e.candidate.direction=(d>0 ? "LONG" : "SHORT");
   e.candidate.state="TRIGGERED";
   e.candidate.key_level=b.close;
   e.candidate.zone_low=0.0; e.candidate.zone_high=0.0;
   e.candidate.retest_extreme=anchor;
   e.candidate.invalidation_price=anchor;
   e.candidate.detected_at_utc=b.closed_at_utc;
   e.candidate.triggered_at_utc=b.closed_at_utc;
   e.candidate.expires_after_bars=1;
   e.candidate.age_after_trigger_bars=0;
   e.candidate.reason_code=(d>0 ? "S07_COMPRESSION_BREAK_UP" : "S07_COMPRESSION_BREAK_DOWN");
   EEA_S07SetEvent(ev,e,b.closed_at_utc,"CANDIDATE_TRIGGERED",before,e.candidate.reason_code);
   return true;
  }

#endif
