#property strict
#property version   "1.000"
#property description "S07 family backtest EA for the MT5 Strategy Tester: the S07 rules of EnterpriseEA on one symbol, no files, sessions or registry."

// G89: EnterpriseEA is built for live operation (symbol registry, state files, signed sessions,
// controller) and does not run in the Strategy Tester. This EA reuses the same S07 functions
// (Setups/DmiEmaCompression.mqh) on the chart symbol so the family can be tested in MT5:
//   base     S07 (buy) / S07S (sell, with the L2 location) on the M30 close
//   early    S07E / S07ES: the M30 rule on the forming M30 bar at every closed entry bar (M5)
//   re-entry S07R / S07RS: within 2 h after a base closed (not at target), price back beyond the four EMAs
//   adds     S07A / S07AS: the S07 rule on M15 / H1 / H4 while the base is in profit (max 2 adds, 3 legs)
// Exits: close beyond EMA55 (EMA100 once the leg ran 3R), ADX >= 50 turning down (base legs),
// time stop per timeframe, stop and 8R target at the broker.

#include <Trade/Trade.mqh>
#include "Setups/DmiEmaCompression.mqh"

enum S07T_EntryTf { S07T_ENTRY_M5=5, S07T_ENTRY_M15=15 };

input double InpRiskPercent       = 1.5;   // Risk per trade, % of balance
input bool   InpBuy               = true;  // Buy family (S07, S07E, S07R, S07A)
input bool   InpSell              = true;  // Sell family (S07S, S07ES, S07RS, S07AS)
input bool   InpEarly             = true;  // Early entries (S07E / S07ES)
input bool   InpReentry           = true;  // Re-entries (S07R / S07RS)
input bool   InpAdds              = true;  // Adds (S07A / S07AS)
input bool   InpSellLocation      = true;  // Sell bases need the L2 location (window high near the H4 EMA200)
input bool   InpAdxExit           = true;  // Base legs exit on ADX >= 50 turning down
input double InpUnorderedWeight   = 0.67;  // Base without EMA21>EMA55>EMA100 (mirrored for sells)
input double InpAddWeight         = 0.67;  // Adds
input S07T_EntryTf InpEntryTf     = S07T_ENTRY_M5; // Entry bars of the early / re-entry engines
input double InpMaxChaseAtr       = 0.5;   // Skip when price ran more than this many ATR past the signal close
input int    InpBaseCooldownBars  = 4;     // M30 bars without a new base after a base closed
input long   InpMagic             = 707070;
input bool   InpVerbose           = false;

#define S07T_HISTORY 1500
#define S07T_H4_HISTORY 1200
#define S07T_MAX_LEGS 16

struct S07TFrame
  {
   ENUM_TIMEFRAMES tf;
   string          name;
   datetime        last_time;
   int             n;
   MqlRates        r[];
   double          e21[],e55[],e100[],e200[],pdi[],mdi[],adx[],atr[];
  };

struct S07TLeg
  {
   ulong    ticket;
   string   setup;
   string   tfname;
   int      dir;
   bool     base;
   double   entry;
   double   risk;
   double   mfe_r;
   int      bars;
   datetime last_bar;
   datetime opened;
   int      adds;
   datetime last_leg;
   double   stop;
  };

struct S07TContext
  {
   bool     valid;
   datetime closed;
   double   stop_ref;
   bool     target_hit;
   bool     used;
  };

CTrade     g_trade;
S07TFrame  g_m30, g_m15, g_h1, g_h4f, g_h4;   // g_h4: H4 EMA200 side only; g_h4f: H4 adds
double     g_h4_ema[];
S07TLeg    g_legs[S07T_MAX_LEGS];
int        g_nlegs=0;
S07TContext g_ctx[2];                  // [0] buy, [1] sell
datetime   g_base_free[2];             // earliest time a new base may open per side
datetime   g_early_bucket[2];          // M30 bucket of the last early entry per side
datetime   g_last_entry_bar=0;

int Side(const int dir) { return dir==1 ? 0 : 1; }

void FrameInit(S07TFrame &f,const ENUM_TIMEFRAMES tf,const string name)
  { f.tf=tf; f.name=name; f.last_time=0; f.n=0; }

// Closed bars of a timeframe with the S07 indicators; true when a new bar closed since the last call.
bool FrameRefresh(S07TFrame &f)
  {
   datetime t=iTime(_Symbol,f.tf,1);
   if(t==0 || t==f.last_time) return false;
   ArraySetAsSeries(f.r,false);
   f.n=CopyRates(_Symbol,f.tf,1,S07T_HISTORY,f.r);
   if(f.n<400) { f.n=0; return false; }
   f.last_time=f.r[f.n-1].time;
   EEA_S07Ema(f.r,f.n,21,f.e21); EEA_S07Ema(f.r,f.n,55,f.e55);
   EEA_S07Ema(f.r,f.n,100,f.e100); EEA_S07Ema(f.r,f.n,200,f.e200);
   EEA_S07Dmi(f.r,f.n,f.pdi,f.mdi,f.adx,f.atr);
   return true;
  }

// Last completed H4 bar before the H4 bucket of `t` (server time): side of the H4 EMA200 and its value.
int H4Side(const datetime t,double &ema)
  {
   ema=0.0;
   if(g_h4.n<2*EEA_S07_H4_EMA) return 0;
   const long bucket=(long)t-(long)t%14400;
   int h=g_h4.n-1;
   while(h>=0 && (long)g_h4.r[h].time>=bucket) h--;
   if(h<EEA_S07_H4_EMA) return 0;
   ema=g_h4_ema[h];
   return g_h4.r[h].close>ema ? 1 : (g_h4.r[h].close<ema ? -1 : 0);
  }

bool RefreshH4()
  {
   datetime t=iTime(_Symbol,PERIOD_H4,1);
   if(t==0 || t==g_h4.last_time) return false;
   ArraySetAsSeries(g_h4.r,false);
   g_h4.n=CopyRates(_Symbol,PERIOD_H4,1,S07T_H4_HISTORY,g_h4.r);
   if(g_h4.n<2*EEA_S07_H4_EMA) { g_h4.n=0; return false; }
   g_h4.last_time=g_h4.r[g_h4.n-1].time;
   EEA_S07Ema(g_h4.r,g_h4.n,EEA_S07_H4_EMA,g_h4_ema);
   return true;
  }

bool Ordered(const int dir,const double c,const double x21,const double x55,const double x100)
  { return dir==1 ? (x21>x55 && x55>x100 && c>x21) : (x21<x55 && x55<x100 && c<x21); }

// ---------------------------------------------------------------------------
// legs
// ---------------------------------------------------------------------------
int BaseIndex(const int dir)
  {
   for(int i=0;i<g_nlegs;i++) if(g_legs[i].base && g_legs[i].dir==dir) return i;
   return -1;
  }

int LegsOpen(const int dir)
  {
   int n=0;
   for(int i=0;i<g_nlegs;i++) if(g_legs[i].dir==dir) n++;
   return n;
  }

void RemoveLeg(const int k)
  {
   for(int i=k;i<g_nlegs-1;i++) g_legs[i]=g_legs[i+1];
   g_nlegs--;
  }

void OnLegClosed(const int k)
  {
   const S07TLeg L=g_legs[k];
   if(L.base)
     {
      const int s=Side(L.dir);
      g_ctx[s].valid=true; g_ctx[s].closed=TimeCurrent(); g_ctx[s].stop_ref=L.stop;
      g_ctx[s].target_hit=(L.mfe_r>=EEA_S07_TARGET_R-0.05); g_ctx[s].used=false;
      g_base_free[s]=TimeCurrent()+InpBaseCooldownBars*PeriodSeconds(PERIOD_M30);
     }
   RemoveLeg(k);
  }

// Drop legs whose position is gone (stop or target at the broker).
void SyncLegs()
  {
   for(int i=g_nlegs-1;i>=0;i--)
      if(!PositionSelectByTicket(g_legs[i].ticket)) OnLegClosed(i);
  }

double VolumeFor(const int dir,const double entry,const double stop,const double weight)
  {
   const double money=AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPercent/100.0*MathMax(0.0,MathMin(1.0,weight));
   double loss=0.0;
   if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin) return 0.0;
   return MathMin(v,vmax);
  }

// One entry through the S07 gates. anchor = window extreme (no buffer); atr = signal ATR; sig_close = signal close.
bool TryEnter(const string setup,const string tfname,const int dir,const bool base,const double anchor,const double atr,
              const double sig_close,const bool ordered)
  {
   if(atr<=0.0 || anchor<=0.0) return false;
   const int s=Side(dir);
   if(LegsOpen(dir)>=EEA_S07_MAX_OPEN_LEGS) return false;
   const int b=BaseIndex(dir);
   if(base)
     {
      if(b>=0) return false;
      if(setup!="S07R" && setup!="S07RS" && TimeCurrent()<g_base_free[s]) return false;
     }
   else
     {
      if(b<0) return false;
      if(g_legs[b].adds>=EEA_S07_MAX_ADDS) return false;
      if((long)(TimeCurrent()-g_legs[b].last_leg)<EEA_S07_ADD_SPACING_SECONDS) return false;
      const double now=(dir==1 ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK));
      if(dir*(now-g_legs[b].entry)<=0.0) return false;
     }
   const double price=(dir==1 ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID));
   if(dir*(price-sig_close)>InpMaxChaseAtr*atr) return false;
   double stop=anchor-dir*EEA_S07_STOP_BUFFER_ATR*atr;
   double dist=dir*(price-stop);
   if(dist<=0.0 || dist>EEA_S07_STOP_MAX_ATR*atr) return false;
   if(dist<EEA_S07_STOP_MIN_ATR*atr) { dist=EEA_S07_STOP_MIN_ATR*atr; stop=price-dir*dist; }
   const double target=price+dir*EEA_S07_TARGET_R*dist;
   double weight=(base ? (ordered ? 1.0 : InpUnorderedWeight) : InpAddWeight);
   const double vol=VolumeFor(dir,price,stop,weight);
   if(vol<=0.0 || g_nlegs>=S07T_MAX_LEGS) return false;
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   bool ok=(dir==1 ? g_trade.Buy(vol,_Symbol,0.0,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),setup)
                   : g_trade.Sell(vol,_Symbol,0.0,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),setup));
   if(!ok || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE) return false;
   ulong ticket=0;
   const ulong deal=g_trade.ResultDeal();
   if(deal>0 && HistoryDealSelect(deal)) ticket=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   if(ticket==0) ticket=g_trade.ResultOrder();
   S07TLeg L;
   L.ticket=ticket; L.setup=setup; L.tfname=tfname; L.dir=dir; L.base=base; L.entry=g_trade.ResultPrice();
   if(L.entry<=0.0) L.entry=price;
   L.risk=MathAbs(L.entry-stop); L.mfe_r=0.0; L.bars=0; L.last_bar=0; L.opened=TimeCurrent();
   L.adds=0; L.last_leg=TimeCurrent(); L.stop=stop;
   g_legs[g_nlegs++]=L;
   if(!base) { g_legs[b].adds++; g_legs[b].last_leg=TimeCurrent(); }
   if(base && (setup=="S07E" || setup=="S07ES")) g_early_bucket[s]=(datetime)((long)TimeCurrent()-(long)TimeCurrent()%1800);
   if(InpVerbose) PrintFormat("%s %s %s vol %.2f entry %.2f stop %.2f target %.2f%s",setup,tfname,dir==1 ? "BUY" : "SELL",
                              vol,L.entry,stop,target,ordered ? " RB3" : "");
   return true;
  }

// ---------------------------------------------------------------------------
// exits on the closed bars of each leg's timeframe
// ---------------------------------------------------------------------------
void ManageLegs(S07TFrame &f)
  {
   if(f.n==0) return;
   for(int i=g_nlegs-1;i>=0;i--)
     {
      if(g_legs[i].tfname!=f.name) continue;
      if(!PositionSelectByTicket(g_legs[i].ticket)) { OnLegClosed(i); continue; }
      string reason="";
      for(int b=1;b<f.n;b++)
        {
         if(f.r[b].time<=g_legs[i].last_bar) continue;
         if((long)f.r[b].time+PeriodSeconds(f.tf)<=(long)g_legs[i].opened) continue;
         g_legs[i].last_bar=f.r[b].time;
         g_legs[i].bars++;
         const int d=g_legs[i].dir;
         const double fav=(d==1 ? f.r[b].high-g_legs[i].entry : g_legs[i].entry-f.r[b].low);
         if(g_legs[i].risk>0.0) g_legs[i].mfe_r=MathMax(g_legs[i].mfe_r,fav/g_legs[i].risk);
         const bool wide=(g_legs[i].mfe_r>=EEA_S07_TRAIL_SWITCH_R);
         const double ema=(wide ? f.e100[b] : f.e55[b]);
         if(reason=="" && d*(f.r[b].close-ema)<0.0) reason=(wide ? "EMA100" : "EMA55");
         if(reason=="" && InpAdxExit && g_legs[i].base && f.adx[b-1]>=EEA_S07_ADX_EXHAUSTION && f.adx[b]<f.adx[b-1]) reason="ADX";
         if(reason=="" && g_legs[i].bars>=EEA_S07HoldBars(f.name)) reason="TIME";
        }
      if(reason!="")
        {
         if(InpVerbose) PrintFormat("exit %s %s: %s",g_legs[i].setup,f.name,reason);
         if(g_trade.PositionClose(g_legs[i].ticket)) OnLegClosed(i);
        }
     }
  }

// ---------------------------------------------------------------------------
// signals
// ---------------------------------------------------------------------------
void BaseOnClose()
  {
   const int i=g_m30.n-1;
   const int window=EEA_S07WindowBars("M30");
   double h4e=0.0;
   const int side=H4Side(g_m30.r[i].time,h4e);
   const int d=EEA_S07SignalAt(g_m30.r,i,window,g_m30.e21,g_m30.e55,g_m30.e100,g_m30.e200,g_m30.pdi,g_m30.mdi,g_m30.adx,side);
   if(d==0) return;
   const long bucket=(long)g_m30.r[i].time;
   if(g_early_bucket[Side(d)]==(datetime)bucket) return;          // the early engine already entered this bar
   const bool ord=Ordered(d,g_m30.r[i].close,g_m30.e21[i],g_m30.e55[i],g_m30.e100[i]);
   const double anchor=EEA_S07StopAnchor(g_m30.r,i,window,d);
   if(d==1 && InpBuy) TryEnter("S07","M30",1,true,anchor,g_m30.atr[i],g_m30.r[i].close,ord);
   if(d==-1 && InpSell && (!InpSellLocation || EEA_S07SellLocation(g_m30.r,i,window,h4e,g_m30.atr[i])))
      TryEnter("S07S","M30",-1,true,anchor,g_m30.atr[i],g_m30.r[i].close,ord);
  }

void AddsOnClose(S07TFrame &f)
  {
   if(!InpAdds || f.n==0) return;
   const int i=f.n-1;
   const int window=EEA_S07WindowBars(f.name);
   double h4e=0.0;
   const int side=H4Side(f.r[i].time,h4e);
   const int d=EEA_S07SignalAt(f.r,i,window,f.e21,f.e55,f.e100,f.e200,f.pdi,f.mdi,f.adx,side);
   if(d==1 && InpBuy) TryEnter("S07A",f.name,1,false,EEA_S07StopAnchor(f.r,i,window,1),f.atr[i],f.r[i].close,false);
   if(d==-1 && InpSell) TryEnter("S07AS",f.name,-1,false,EEA_S07StopAnchor(f.r,i,window,-1),f.atr[i],f.r[i].close,false);
  }

// Early and re-entry engines on the closed entry bar inside the forming M30 bar.
void EntryBarEngines()
  {
   if(g_m30.n<400) return;
   const ENUM_TIMEFRAMES etf=(InpEntryTf==S07T_ENTRY_M15 ? PERIOD_M15 : PERIOD_M5);
   const long esec=PeriodSeconds(etf);
   MqlRates sub[];
   ArraySetAsSeries(sub,false);
   const int ns=CopyRates(_Symbol,etf,1,(int)(1800/esec)+1,sub);
   if(ns<1) return;
   const int s=ns-1;
   const long t=(long)sub[s].time;
   const long bucket=t-t%1800;
   if(t+esec>=bucket+1800) return;                       // the M30 bar closed: the base engine handles it
   const int q=g_m30.n-1;
   if((long)g_m30.r[q].time>=bucket || q<=EEA_S07WindowBars("M30")) return;
   int u=s;
   while(u>0 && (long)sub[u-1].time>=bucket) u--;
   double fh=sub[u].high, fl=sub[u].low;
   for(int k=u+1;k<=s;k++) { fh=MathMax(fh,sub[k].high); fl=MathMin(fl,sub[k].low); }
   const double fc=sub[s].close;
   double h4e=0.0;
   const int side=H4Side((datetime)bucket,h4e);
   const int window=EEA_S07WindowBars("M30");
   double pp,mm,ts,x21,x55,x100,x200;
   const bool state=EEA_S07ProvisionalState(g_m30.r,q,g_m30.e21,g_m30.e55,g_m30.e100,g_m30.e200,g_m30.pdi,g_m30.mdi,g_m30.atr,
                                            fh,fl,fc,pp,mm,ts,x21,x55,x100,x200);
   // early
   if(InpEarly)
     {
      double atr_p=0.0, anchor=0.0;
      const int d=EEA_S07ProvisionalSignal(g_m30.r,q,window,g_m30.e21,g_m30.e55,g_m30.e100,g_m30.e200,g_m30.pdi,g_m30.mdi,
                                           g_m30.adx,g_m30.atr,bucket,sub[u].open,fh,fl,fc,side,atr_p,anchor);
      if(d!=0 && g_early_bucket[Side(d)]!=(datetime)bucket)
        {
         bool loc=true;
         if(d==-1 && InpSellLocation)
           {
            double top=fh;
            for(int k=q-window+1;k<=q;k++) top=MathMax(top,g_m30.r[k].high);
            loc=(h4e>0.0 && top>=h4e-EEA_S07_L2_ATR*atr_p);
           }
         const bool ord=state && Ordered(d,fc,x21,x55,x100);
         if(d==1 && InpBuy) TryEnter("S07E","M30",1,true,anchor,atr_p,fc,ord);
         if(d==-1 && InpSell && loc) TryEnter("S07ES","M30",-1,true,anchor,atr_p,fc,ord);
        }
     }
   // re-entry
   if(InpReentry && state)
      for(int sd=0;sd<2;sd++)
        {
         const int dir=(sd==0 ? 1 : -1);
         if((dir==1 && !InpBuy) || (dir==-1 && !InpSell)) continue;
         S07TContext c=g_ctx[sd];
         if(!c.valid || c.used || c.target_hit) continue;
         if((long)TimeCurrent()-(long)c.closed>EEA_S07_REENTRY_SECONDS) continue;
         const double hi=MathMax(MathMax(x21,x55),MathMax(x100,x200)), lo=MathMin(MathMin(x21,x55),MathMin(x100,x200));
         const bool in_setup=(dir==1 ? (fc>hi && pp>mm) : (fc<lo && mm>pp)) && side==dir;
         if(!in_setup) continue;
         double ext=c.stop_ref;
         for(int k=0;k<=s;k++) ext=(dir==1 ? MathMin(ext,sub[k].low) : MathMax(ext,sub[k].high));
         if(TryEnter(dir==1 ? "S07R" : "S07RS","M30",dir,true,ext,ts,fc,Ordered(dir,fc,x21,x55,x100)))
            g_ctx[sd].used=true;
        }
  }

// ---------------------------------------------------------------------------
int OnInit()
  {
   FrameInit(g_m30,PERIOD_M30,"M30"); FrameInit(g_m15,PERIOD_M15,"M15");
   FrameInit(g_h1,PERIOD_H1,"H1"); FrameInit(g_h4f,PERIOD_H4,"H4"); FrameInit(g_h4,PERIOD_H4,"H4");
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   for(int s=0;s<2;s++) { g_ctx[s].valid=false; g_base_free[s]=0; g_early_bucket[s]=0; }
   g_nlegs=0;
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   const ENUM_TIMEFRAMES etf=(InpEntryTf==S07T_ENTRY_M15 ? PERIOD_M15 : PERIOD_M5);
   const datetime eb=iTime(_Symbol,etf,1);
   if(eb==0 || eb==g_last_entry_bar) return;
   g_last_entry_bar=eb;
   SyncLegs();
   RefreshH4();
   if(FrameRefresh(g_m30)) { ManageLegs(g_m30); BaseOnClose(); }
   if(FrameRefresh(g_m15)) { ManageLegs(g_m15); AddsOnClose(g_m15); }
   if(FrameRefresh(g_h1))  { ManageLegs(g_h1);  AddsOnClose(g_h1); }
   if(FrameRefresh(g_h4f)) { ManageLegs(g_h4f); AddsOnClose(g_h4f); }
   EntryBarEngines();
  }
