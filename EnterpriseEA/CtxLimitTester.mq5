#property strict
#property version   "1.000"
#property description "CtxLimitTester: the MKT04 gold context-forecast plan (limit or market) with the S07 gates, for the MT5 Strategy Tester."

// MKT04 (research/markets): 30 context features on every full-hour M30 close -> LightGBM forecast of the R of
//   plan L (limit 0.5 x ATR14 H4 from the close, 4 h to fill) or plan M (market at the next bar open),
//   SL 1.0 x ATR H4, TP 2.0 x ATR H4, closed after 96 M30 bars (48 h); one position at a time.
// S07 gates (descriptive follow-up mkt04_gold_s07_gates.py): trade only on the side of the last closed H4 EMA200;
//   sells also need the S07S location (high of the last 9 M30 bars >= H4 EMA200 - 0.5 x ATR M30);
//   weight 1.0 when EMA21/55/100 are ordered with the close beyond EMA21, else InpUnorderedWeight.
// The models (CtxLimit/CtxGoldModel.mqh) were trained on XAUUSD M30 07/2018 .. 09/2025: only bars from
// 10/2025 are out of sample. The features need ~200 days of M30 history before the test start (H4/D1 EMA200).
// Like S07Tester: one symbol, no files, sessions or registry. Distinct magic so both can run on one account.

#include <Trade/Trade.mqh>
#include "CtxLimit/CtxGoldModel.mqh"
#include "Tester/TesterPanel.mqh"

enum CtxPlan     { CTX_PLAN_LIMIT=0, CTX_PLAN_MARKET=1 };
enum CtxRiskBase { CTX_RISK_INITIAL=0, CTX_RISK_BALANCE=1 };

input CtxPlan     InpPlan            = CTX_PLAN_LIMIT;   // L: limit 0.5 ATR H4 from the close / M: market
input double      InpThreshold       = 0.0;   // Forecast threshold (R); <= 0 uses the MKT04 value (L 0.383, M 0.211)
input double      InpRiskPercent     = 0.5;   // Risk per trade, % (x weight)
input CtxRiskBase InpRiskBase        = CTX_RISK_INITIAL; // INITIAL: % of min(equity, initial deposit); BALANCE: % of equity (compounding)
input bool        InpBuy             = true;  // Buys
input bool        InpSell            = true;  // Sells
input bool        InpH4SideGate      = true;  // S07 gate: only on the side of the last closed H4 EMA200
input bool        InpSellLocation    = true;  // S07S gate for sells: 9-bar high within 0.5 ATR of the H4 EMA200
input double      InpUnorderedWeight = 0.67;  // Weight when EMA21/55/100 are not ordered (1.0 = no weighting)
input double      InpStopAtr         = 1.0;   // Stop, x ATR14 H4
input double      InpTargetAtr       = 2.0;   // Target, x ATR14 H4
input double      InpPullAtr         = 0.5;   // Limit distance from the decision close, x ATR14 H4 (plan L)
input int         InpLimitBars       = 8;     // M30 bars a limit stays (plan L)
input int         InpHoldBars        = 96;    // M30 bars a position is held at most
input int         InpMaxPending      = 8;     // Limits waiting at once (the first fill cancels the others)
input bool        InpParityFile      = false; // Write every decision (features + forecasts) to Common\Files\CtxLimitTester_parity.csv
input long        InpMagic           = 717171;
input bool        InpVerbose         = false;
input bool        InpPanel           = true;  // On-chart analysis panel (context, forecasts, orders)

#define CTX_SLOTS 48
#define CTX_VOLHIST 20

// ---------------------------------------------------------------------------
// incremental context (mirrors research/markets/ctx_incremental.py)
// ---------------------------------------------------------------------------
double CtxNan() { return MathArcsin(2.0); }
bool   CtxOk(const double v) { return MathIsValidNumber(v); }

struct CtxWilder
  {
   double n, v; bool ok;
   void   Init(const double period) { n=period; v=0.0; ok=false; }
   double Add(const double x) { v=(ok ? v+(x-v)/n : x); ok=true; return v; }
  };

struct CtxEma
  {
   double k, v; bool ok;
   void   Init(const double period) { k=2.0/(period+1.0); v=0.0; ok=false; }
   double Add(const double x) { v=(ok ? v+k*(x-v) : x); ok=true; return v; }
  };

struct CtxHtf
  {
   long      sec;
   long      cur;
   bool      has_cur;
   double    h, l, c, prev_c;
   bool      has_prev;
   CtxEma    ema;
   CtxWilder atr;
   int       done;
   double    last_c, last_e, last_a;
   void Init(const long seconds)
     {
      sec=seconds; has_cur=false; has_prev=false; done=0; h=l=c=prev_c=0.0;
      ema.Init(200); atr.Init(14); last_c=last_e=last_a=CtxNan();
     }
   void Add(const long t,const double hi,const double lo,const double cl)
     {
      const long b=t/sec;
      if(has_cur && b!=cur)
        {
         const double pc=(has_prev ? prev_c : c);
         const double tr=MathMax(h,pc)-MathMin(l,pc);
         last_e=ema.Add(c); last_a=atr.Add(tr); last_c=c;
         prev_c=c; has_prev=true; done++; has_cur=false;
        }
      if(!has_cur) { cur=b; h=hi; l=lo; has_cur=true; }
      else { h=MathMax(h,hi); l=MathMin(l,lo); }
      c=cl;
     }
  };

struct CtxState
  {
   bool      started;
   double    prev_c, prev_h, prev_l;
   CtxWilder atr, atr100, pdm, mdm, dx, gain, loss;
   CtxEma    e21, e55, e100, e200;
   double    closes[97]; int nclose;   // ring, newest at (nclose-1)%97
   double    highs[16], lows[16]; int nhl;
   double    highs9[9]; int nh9;
   CtxHtf    h4, d1;
   long      day; bool has_day;
   double    dmax, dmin, pv, vv, pdh, pdl;
   double    vol[CTX_SLOTS][CTX_VOLHIST]; int vcount[CTX_SLOTS]; int vpos[CTX_SLOTS];
   // outputs of the last bar
   double    f[CTX_NFEAT];
   double    a14, A, c, top9, x21, x55, x100, h4ema;
  };

CtxState g;

void CtxInit()
  {
   g.started=false; g.prev_c=g.prev_h=g.prev_l=0.0;
   g.atr.Init(14); g.atr100.Init(100); g.pdm.Init(14); g.mdm.Init(14); g.dx.Init(14); g.gain.Init(14); g.loss.Init(14);
   g.e21.Init(21); g.e55.Init(55); g.e100.Init(100); g.e200.Init(200);
   g.nclose=0; g.nhl=0; g.nh9=0;
   g.h4.Init(14400); g.d1.Init(86400);
   g.has_day=false; g.day=0; g.dmax=g.dmin=g.pv=g.vv=0.0; g.pdh=g.pdl=CtxNan();
   for(int s=0;s<CTX_SLOTS;s++) { g.vcount[s]=0; g.vpos[s]=0; }
  }

double CtxBack(const int n,const double c,const double a)
  {
   if(g.nclose<=n) return CtxNan();
   return (c-g.closes[(g.nclose-1-n)%97])/a;
  }

void CtxAdd(const MqlRates &r)
  {
   const long   t=(long)r.time;
   const double o=r.open, h=r.high, l=r.low, c=r.close, v=(double)r.tick_volume;
   const double pc=(g.started ? g.prev_c : c);
   const double tr=MathMax(h,pc)-MathMin(l,pc);
   const double a=g.atr.Add(tr);
   const double a100=g.atr100.Add(tr);
   const double ph=(g.started ? g.prev_h : h), pl=(g.started ? g.prev_l : l);
   const double up=h-ph, dn=pl-l;
   const double pdm=((up>dn && up>0.0) ? up : 0.0);
   const double mdm=((dn>up && dn>0.0) ? dn : 0.0);
   const double pds=g.pdm.Add(pdm), mds=g.mdm.Add(mdm);
   const double pdi=100.0*pds/MathMax(a,1e-12), mdi=100.0*mds/MathMax(a,1e-12);
   const double adx=g.dx.Add(100.0*MathAbs(pdi-mdi)/MathMax(pdi+mdi,1e-9));
   const double ch=c-pc;
   const double gg=g.gain.Add(MathMax(ch,0.0)), ll=g.loss.Add(MathMax(-ch,0.0));
   const double rsi=100.0-100.0/(1.0+gg/MathMax(ll,1e-12));
   const double x21=g.e21.Add(c), x55=g.e55.Add(c), x100=g.e100.Add(c), x200=g.e200.Add(c);
   g.closes[g.nclose%97]=c; g.nclose++;
   g.highs[g.nhl%16]=h; g.lows[g.nhl%16]=l; g.nhl++;
   g.highs9[g.nh9%9]=h; g.nh9++;
   g.h4.Add(t,h,l,c);
   g.d1.Add(t,h,l,c);
   const long day=t/86400;
   if(!g.has_day || day!=g.day)
     {
      if(g.has_day) { g.pdh=g.dmax; g.pdl=g.dmin; }
      g.day=day; g.has_day=true; g.dmax=h; g.dmin=l; g.pv=0.0; g.vv=0.0;
     }
   else { g.dmax=MathMax(g.dmax,h); g.dmin=MathMin(g.dmin,l); }
   const double w=MathMax(v,1.0);
   g.pv+=w*(h+l+c)/3.0; g.vv+=w;
   const long sod=t%86400;
   const int slot=(int)(sod/1800)%CTX_SLOTS;
   double mean20=CtxNan();
   if(g.vcount[slot]>=10)
     {
      double s=0.0;
      for(int k=0;k<g.vcount[slot];k++) s+=g.vol[slot][k];
      mean20=s/g.vcount[slot];
     }
   g.vol[slot][g.vpos[slot]]=v; g.vpos[slot]=(g.vpos[slot]+1)%CTX_VOLHIST;
   if(g.vcount[slot]<CTX_VOLHIST) g.vcount[slot]++;

   // features, CTX_FEATURES order
   g.f[0]=CtxBack(1,c,a); g.f[1]=CtxBack(4,c,a); g.f[2]=CtxBack(16,c,a); g.f[3]=CtxBack(48,c,a);
   g.f[4]=(c-x21)/a; g.f[5]=(x21-x55)/a; g.f[6]=(x55-x200)/a;
   const bool h4ok=(g.h4.done>=201), d1ok=(g.d1.done>=201);
   g.f[7]=(h4ok ? (g.h4.last_c>g.h4.last_e ? 1.0 : (g.h4.last_c<g.h4.last_e ? -1.0 : 0.0)) : CtxNan());
   g.f[8]=(h4ok ? (c-g.h4.last_e)/a : CtxNan());
   g.f[9]=(d1ok ? (g.d1.last_c>g.d1.last_e ? 1.0 : (g.d1.last_c<g.d1.last_e ? -1.0 : 0.0)) : CtxNan());
   g.f[10]=(d1ok ? (c-g.d1.last_e)/a : CtxNan());
   g.f[11]=adx; g.f[12]=pdi-mdi; g.f[13]=rsi;
   g.f[14]=a/a100;
   if(g.nhl>=16)
     {
      double mx=g.highs[0], mn=g.lows[0];
      for(int k=1;k<16;k++) { mx=MathMax(mx,g.highs[k]); mn=MathMin(mn,g.lows[k]); }
      g.f[15]=(mx-mn)/a;
     }
   else g.f[15]=CtxNan();
   g.f[16]=(c-g.pdh)/a; g.f[17]=(c-g.pdl)/a;
   g.f[18]=(c-g.dmin)/MathMax(g.dmax-g.dmin,1e-12);
   g.f[19]=(c-g.pv/g.vv)/a;
   const double step=MathPow(10.0,MathFloor(MathLog10(c))-2.0);
   g.f[20]=MathMod(c,step)/step;
   g.f[21]=(double)((((sod/3600)-7)%24+24)%24);
   g.f[22]=(double)((((t-7*3600)/86400+3)%7+7)%7);
   g.f[23]=((sod>=16*3600+1800 && sod<=23*3600) ? (double)(sod-(16*3600+1800))/60.0 : -1.0);
   g.f[24]=(CtxOk(mean20) ? v/mean20 : CtxNan());
   g.f[25]=g.f[0]; g.f[26]=g.f[1];
   g.f[27]=CtxBack(96,c,a);
   const double A=(g.h4.done>=15 ? g.h4.last_a : CtxNan());
   g.f[28]=(CtxOk(A) ? a/A : CtxNan());
   g.f[29]=0.0;
   double top9=h;
   const int n9=MathMin(g.nh9,9);
   for(int k=0;k<n9;k++) top9=MathMax(top9,g.highs9[k]);
   g.a14=a; g.A=A; g.c=c; g.top9=(g.nh9>=9 ? top9 : CtxNan()); g.x21=x21; g.x55=x55; g.x100=x100;
   g.h4ema=(h4ok ? g.h4.last_e : CtxNan());
   g.prev_c=c; g.prev_h=h; g.prev_l=l; g.started=true;
  }

// ---------------------------------------------------------------------------
// LightGBM trees (missing: 0 None -> NaN as 0, 1 Zero, 2 NaN)
// ---------------------------------------------------------------------------
double CtxPredict(const double &x[],const int &feat[],const double &thr[],const int &left[],const int &right[],
                  const char &dleft[],const char &miss[],const double &leaf[],const int &root[],const int &rootleaf[])
  {
   double s=0.0;
   const int trees=ArraySize(root);
   for(int t=0;t<trees;t++)
     {
      if(root[t]<0) { s+=leaf[rootleaf[t]]; continue; }
      int k=root[t];
      while(true)
        {
         double v=x[feat[k]];
         bool go_left;
         if(miss[k]==2 && !CtxOk(v)) go_left=(dleft[k]==1);
         else if(miss[k]==1 && (!CtxOk(v) || MathAbs(v)<=1e-35)) go_left=(dleft[k]==1);
         else
           {
            if(!CtxOk(v)) v=0.0;
            go_left=(v<=thr[k]);
           }
         const int nxt=(go_left ? left[k] : right[k]);
         if(nxt<0) { s+=leaf[-nxt-1]; break; }
         k=nxt;
        }
     }
   return s;
  }

double PredLL(const double &x[]) { return CtxPredict(x,CTX_LL_FEAT,CTX_LL_THR,CTX_LL_LEFT,CTX_LL_RIGHT,CTX_LL_DLEFT,CTX_LL_MISS,CTX_LL_LEAF,CTX_LL_ROOT,CTX_LL_ROOTLEAF); }
double PredLS(const double &x[]) { return CtxPredict(x,CTX_LS_FEAT,CTX_LS_THR,CTX_LS_LEFT,CTX_LS_RIGHT,CTX_LS_DLEFT,CTX_LS_MISS,CTX_LS_LEAF,CTX_LS_ROOT,CTX_LS_ROOTLEAF); }
double PredML(const double &x[]) { return CtxPredict(x,CTX_ML_FEAT,CTX_ML_THR,CTX_ML_LEFT,CTX_ML_RIGHT,CTX_ML_DLEFT,CTX_ML_MISS,CTX_ML_LEAF,CTX_ML_ROOT,CTX_ML_ROOTLEAF); }
double PredMS(const double &x[]) { return CtxPredict(x,CTX_MS_FEAT,CTX_MS_THR,CTX_MS_LEFT,CTX_MS_RIGHT,CTX_MS_DLEFT,CTX_MS_MISS,CTX_MS_LEAF,CTX_MS_ROOT,CTX_MS_ROOTLEAF); }

// ---------------------------------------------------------------------------
// trading
// ---------------------------------------------------------------------------
CTrade   g_trade;
double   g_initial_capital=0.0;
datetime g_last_bar=0;
bool     g_warm=false;
datetime g_dl_time=0;                // last decision (panel)
double   g_dl_buy=0.0, g_dl_sell=0.0;
string   g_dl_result="";
int      g_too_small=0;              // entries skipped: the risk budget is below the minimum volume
int      g_parity=INVALID_HANDLE;
int      g_decisions=0, g_signals=0, g_gated=0, g_orders=0, g_fills=0, g_expired=0, g_timeouts=0;

double Threshold()
  {
   if(InpThreshold>0.0) return InpThreshold;
   return (InpPlan==CTX_PLAN_LIMIT ? 0.3825820347356539 : 0.21075521107935286);
  }

bool HasPosition(ulong &ticket)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong tk=PositionGetTicket(i);
      if(tk>0 && PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
        { ticket=tk; return true; }
     }
   return false;
  }

int PendingCount()
  {
   int n=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong tk=OrderGetTicket(i);
      if(tk>0 && OrderGetString(ORDER_SYMBOL)==_Symbol && OrderGetInteger(ORDER_MAGIC)==InpMagic) n++;
     }
   return n;
  }

// expired limits (by their comment-free placement time) and, once a position exists, every pending order
void ManagePending(const bool position)
  {
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong tk=OrderGetTicket(i);
      if(tk==0 || OrderGetString(ORDER_SYMBOL)!=_Symbol || OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      const datetime placed=(datetime)OrderGetInteger(ORDER_TIME_SETUP);
      const bool expired=(TimeCurrent()-placed>=(long)InpLimitBars*1800);
      if(position || expired)
        {
         if(g_trade.OrderDelete(tk) && expired && !position) g_expired++;
        }
     }
  }

void ManagePosition()
  {
   ulong tk=0;
   if(!HasPosition(tk) || !PositionSelectByTicket(tk)) return;
   const datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
   const datetime bar0=(datetime)((long)opened-(long)opened%1800);
   if((long)(TimeCurrent()-bar0)>=(long)InpHoldBars*1800)
      if(g_trade.PositionClose(tk)) g_timeouts++;
  }

double VolumeFor(const int dir,const double entry,const double stop,const double weight)
  {
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double basis=(InpRiskBase==CTX_RISK_BALANCE ? equity : MathMin(equity,g_initial_capital));
   const double money=basis*InpRiskPercent/100.0*MathMax(0.0,MathMin(1.0,weight));
   double loss=0.0;
   if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin)
     {
      // the risk budget buys less than the minimum volume (small or cent deposit, wide stop, or the tester's
      // "profit in pips" mode, where OrderCalcProfit returns points instead of money)
      g_too_small++;
      if(g_too_small==1)
         PrintFormat("%s: risk %.2f buys %.4f lots < minimum %.2f (stop %.2f away, loss per lot %.2f). "
                     "Use a larger deposit, a higher risk %% or money profit (not pips) in the tester.",
                     "CtxLimitTester",money,money/(-loss),vmin,MathAbs(entry-stop),-loss);
      return 0.0;
     }
   return MathMin(v,vmax);
  }

void WriteParity(const datetime bar_time,const double pll,const double pls,const double pml,const double pms)
  {
   if(g_parity==INVALID_HANDLE) return;
   string line=TimeToString(bar_time,TIME_DATE|TIME_MINUTES)+","+IntegerToString((long)bar_time);
   for(int k=0;k<CTX_NFEAT;k++) line+=","+(CtxOk(g.f[k]) ? DoubleToString(g.f[k],10) : "nan");
   line+=StringFormat(",%.10f,%.10f,%.10f,%.10f",pll,pls,pml,pms);
   FileWriteString(g_parity,line+"\r\n");
  }

void Decide(const datetime bar_time)
  {
   g_decisions++;
   double x[CTX_NFEAT];
   for(int k=0;k<CTX_NFEAT;k++) x[k]=g.f[k];
   const double pll=PredLL(x), pls=PredLS(x), pml=PredML(x), pms=PredMS(x);
   WriteParity(bar_time,pll,pls,pml,pms);
   const double th=Threshold();
   const double p_buy=(InpPlan==CTX_PLAN_LIMIT ? pll : pml), p_sell=(InpPlan==CTX_PLAN_LIMIT ? pls : pms);
   g_dl_time=bar_time; g_dl_buy=p_buy; g_dl_sell=p_sell; g_dl_result="";
   ulong tk=0;
   if(HasPosition(tk)) { g_dl_result="bỏ qua — đang có lệnh mở (một lệnh mỗi lúc)"; return; }
   if(InpPlan==CTX_PLAN_LIMIT && PendingCount()>=InpMaxPending) { g_dl_result="bỏ qua — đã đủ limit chờ"; return; }
   string why="";
   int dir=0; double best=-1e9;
   for(int s=0;s<2;s++)
     {
      const int d=(s==0 ? 1 : -1);
      const double p=(d==1 ? p_buy : p_sell);
      if((d==1 && !InpBuy) || (d==-1 && !InpSell)) continue;
      if(!(p>th && p>0.0)) continue;
      g_signals++;
      if(InpH4SideGate && !(CtxOk(g.f[7]) && (int)g.f[7]==d)) { g_gated++; why+=(d==1 ? "MUA" : "BÁN")+string(" qua ngưỡng nhưng ngược phía EMA200 H4; "); continue; }
      if(d==-1 && InpSellLocation && !(CtxOk(g.h4ema) && CtxOk(g.top9) && g.top9>=g.h4ema-0.5*g.a14)) { g_gated++; why+="BÁN qua ngưỡng nhưng chưa đạt vị trí L2; "; continue; }
      if(p>best) { best=p; dir=d; }
     }
   if(dir==0 || !CtxOk(g.A) || g.A<=0.0) { g_dl_result=(why!="" ? "không vào — "+why : "không vào — chưa chiều nào qua ngưỡng"); return; }
   const bool ordered=(dir==1 ? (g.x21>g.x55 && g.x55>g.x100 && g.c>g.x21) : (g.x21<g.x55 && g.x55<g.x100 && g.c<g.x21));
   const double weight=(ordered ? 1.0 : InpUnorderedWeight);
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   bool market=(InpPlan==CTX_PLAN_MARKET);
   double entry=(dir==1 ? ask : bid);
   if(!market)
     {
      const double level=g.c-dir*InpPullAtr*g.A;
      if((dir==1 && ask<=level) || (dir==-1 && bid>=level)) market=true;   // already through the level: take the market
      else entry=level;
     }
   const double stop=entry-dir*InpStopAtr*g.A, target=entry+dir*InpTargetAtr*g.A;
   const double vol=VolumeFor(dir,entry,stop,weight);
   if(vol<=0.0) { g_dl_result="không vào — khối lượng dưới mức tối thiểu"; return; }
   const string tag=StringFormat("CTX%s %.2f%s",InpPlan==CTX_PLAN_LIMIT ? "L" : "M",best,ordered ? "" : " w");
   bool ok;
   if(market)
      ok=(dir==1 ? g_trade.Buy(vol,_Symbol,0.0,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),tag)
                 : g_trade.Sell(vol,_Symbol,0.0,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),tag));
   else
      ok=(dir==1 ? g_trade.BuyLimit(vol,NormalizeDouble(entry,digits),_Symbol,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),ORDER_TIME_GTC,0,tag)
                 : g_trade.SellLimit(vol,NormalizeDouble(entry,digits),_Symbol,NormalizeDouble(stop,digits),NormalizeDouble(target,digits),ORDER_TIME_GTC,0,tag));
   if(ok) g_orders++;
   g_dl_result=StringFormat("%s %s %s %.2f lot tại %s (SL %s, TP %s)%s",ok ? (market ? "VÀO" : "ĐẶT") : "LỖI gửi",market ? "market" : "limit",
                            dir==1 ? "MUA" : "BÁN",vol,PnlPx(entry),PnlPx(stop),PnlPx(target),ok ? "" : " — xem tab Experts/Journal");
   if(InpVerbose)
      PrintFormat("%s %s %s vol %.2f entry %.2f stop %.2f target %.2f forecast %.3f weight %.2f %s",TimeToString(bar_time),
                  dir==1 ? "BUY" : "SELL",market ? "MARKET" : "LIMIT",vol,entry,stop,target,best,weight,ok ? "" : "FAILED");
  }

// every closed M30 bar after the last processed one, in order; decisions only on live full-hour closes
void ProcessBars()
  {
   MqlRates r[];
   int n;
   if(g_last_bar==0)
     {
      const int total=Bars(_Symbol,PERIOD_M30);
      n=CopyRates(_Symbol,PERIOD_M30,1,MathMax(0,total-1),r);
     }
   else
      n=CopyRates(_Symbol,PERIOD_M30,g_last_bar+1,TimeCurrent(),r);
   if(n<=0) return;
   const datetime forming=iTime(_Symbol,PERIOD_M30,0);
   for(int i=0;i<n;i++)
     {
      if(r[i].time<=g_last_bar || r[i].time>=forming) continue;
      CtxAdd(r[i]);
      g_last_bar=r[i].time;
      const bool live=(i==n-1 || r[i+1].time>=forming);
      if(g_warm && live && ((long)r[i].time+1800)%3600==0) Decide(r[i].time);
     }
   g_warm=true;
  }

// --- on-chart analysis panel (Tester/TesterPanel.mqh) ----------------------------------------------------------
void CtxPanel()
  {
   if(!PnlActive()) return;
   PnlBegin();
   const double th=Threshold();
   PnlHead(StringFormat("CtxLimitTester  %s  %s (giờ server)  | kế hoạch %s, ngưỡng dự báo %.3fR | rủi ro %.2f%%",_Symbol,
                        PnlTime(TimeCurrent()),InpPlan==CTX_PLAN_LIMIT ? "LIMIT" : "MARKET",th,InpRiskPercent));
   if(!g_warm || !CtxOk(g.A))
     { PnlWarn("Ngữ cảnh   : đang nạp lịch sử M30 (cần ~200 ngày để EMA200 H4/D1 ổn định)"); PnlFlush(); return; }
   // context of the last closed M30 bar: one summary line, the values behind the button
   const int h4side=(CtxOk(g.f[7]) ? (int)g.f[7] : 0);
   const bool ord_b=(g.x21>g.x55 && g.x55>g.x100 && g.c>g.x21), ord_s=(g.x21<g.x55 && g.x55<g.x100 && g.c<g.x21);
   const string ord=(ord_b ? "TĂNG đủ thứ tự" : (ord_s ? "GIẢM đủ thứ tự" : "chưa xếp thứ tự"));
   if(PnlSection("ctx",StringFormat("Ngữ cảnh   : giá %s | lọc H4 chỉ cho %s%s | EMA %s",PnlPx(g.c),PnlDir(h4side),
                                    InpH4SideGate ? "" : " (TẮT)",ord),false,
                 h4side==1 ? PnlOkColor : (h4side==-1 ? PnlWarnColor : clrNONE)))
     {
      PnlAdd(StringFormat("     M30 đã đóng giá %s | ATR14 H4 %s | EMA21 %s, 55 %s, 100 %s",PnlPx(g.c),PnlPx(g.A),PnlPx(g.x21),
                          PnlPx(g.x55),PnlPx(g.x100)));
      PnlAdd(StringFormat("     EMA200 H4 %s | trọng số %s",CtxOk(g.h4ema) ? PnlPx(g.h4ema) : "—",
                          (ord_b || ord_s) ? "1.0" : DoubleToString(InpUnorderedWeight,2)));
      if(InpSell && InpSellLocation && CtxOk(g.h4ema) && CtxOk(g.top9))
         PnlAdd(StringFormat("     vị trí bán %s: đỉnh 9 nến M30 %s ≥ EMA200 H4 - 0.5 ATR (%s)",PnlMark(g.top9>=g.h4ema-0.5*g.a14),
                             PnlPx(g.top9),PnlPx(g.h4ema-0.5*g.a14)));
     }
   // the decision (the base order): open by default
   const datetime nextdec=(datetime)(((long)TimeCurrent()/3600+1)*3600);
   if(g_dl_time==0)
      PnlAdd("Quyết định : chưa có (bot chỉ xét ở nến M30 đóng đúng giờ tròn) | xét tiếp lúc "+PnlHm(nextdec));
   else
     {
      const bool placed=(StringFind(g_dl_result,"ĐẶT")==0 || StringFind(g_dl_result,"VÀO")==0);
      if(PnlSection("dec","Quyết định "+PnlHm(g_dl_time+1800)+": "+g_dl_result,true,placed ? PnlOkColor : clrNONE))
        {
         PnlAdd(StringFormat("     dự báo MUA %+.3fR %s | BÁN %+.3fR %s (ngưỡng %.3f)",g_dl_buy,PnlMark(g_dl_buy>th),
                             g_dl_sell,PnlMark(g_dl_sell>th),th));
         PnlAdd("     xét tiếp lúc "+PnlHm(nextdec)+" (nến M30 đóng giờ tròn); quyết định đã chốt không tính lại theo giá");
        }
     }
   ulong tk=0;
   if(HasPosition(tk) && PositionSelectByTicket(tk))
     {
      const int d=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
      const double op=PositionGetDouble(POSITION_PRICE_OPEN), sl=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
      const double cur=PositionGetDouble(POSITION_PRICE_CURRENT);
      const double r=(MathAbs(op-sl)>0.0 ? d*(cur-op)/MathAbs(op-sl) : 0.0);
      const datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      PnlAdd(StringFormat("Lệnh %s    : vào %s, SL %s, TP %s, đang %s; tự đóng lúc %s (48 giờ)",PnlDir(d),PnlPx(op),PnlPx(sl),PnlPx(tp),
                          PnlR(r),PnlTime((datetime)((long)opened-(long)opened%1800+(long)InpHoldBars*1800))),r>=0.0 ? PnlOkColor : PnlWarnColor);
     }
   else
      PnlAdd("Lệnh mở    : không có");
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong o=OrderGetTicket(i);
      if(o==0 || OrderGetString(ORDER_SYMBOL)!=_Symbol || OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      const bool buy=(OrderGetInteger(ORDER_TYPE)==ORDER_TYPE_BUY_LIMIT);
      const datetime placed=(datetime)OrderGetInteger(ORDER_TIME_SETUP);
      PnlAdd(StringFormat("Limit %s   : tại %s, SL %s, TP %s, hủy lúc %s",buy ? "MUA" : "BÁN",PnlPx(OrderGetDouble(ORDER_PRICE_OPEN)),
                          PnlPx(OrderGetDouble(ORDER_SL)),PnlPx(OrderGetDouble(ORDER_TP)),PnlHm((datetime)((long)placed+(long)InpLimitBars*1800))));
     }
   if(PnlSection("cnt",StringFormat("Đã đếm     : lệnh %d | khớp %d%s",g_orders,g_fills,
                                    g_too_small>0 ? StringFormat(" | khối lượng < tối thiểu %d",g_too_small) : ""),false,
                 g_too_small>0 ? PnlWarnColor : clrNONE))
     {
      PnlAdd(StringFormat("     xét %d | qua ngưỡng %d | bị lọc S07 %d | lệnh %d | khớp %d | limit hết hạn %d | đóng 48h %d",
                          g_decisions,g_signals,g_gated,g_orders,g_fills,g_expired,g_timeouts));
      if(g_too_small>0) PnlAdd(StringFormat("     khối lượng < tối thiểu %d lần (xem tab Experts)",g_too_small));
      PnlAdd("     không có News Guard / sentiment trong bot này");
     }
   PnlFlush();
  }

int OnInit()
  {
   if(ArraySize(CTX_FEATURES)!=CTX_NFEAT || CTX_FEATURES[0]!="r1" || CTX_FEATURES[28]!="atr_vs_h4")
     { Print("CtxLimitTester: model feature order mismatch"); return INIT_FAILED; }
   CtxInit();
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFillingBySymbol(_Symbol);    // FOK / IOC / RETURN as the broker allows (cent accounts often refuse FOK)
   g_trade.SetDeviationInPoints(20);
   g_initial_capital=AccountInfoDouble(ACCOUNT_BALANCE);
   g_last_bar=0; g_warm=false;
   if(InpParityFile)
     {
      g_parity=FileOpen("CtxLimitTester_parity.csv",FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
      if(g_parity!=INVALID_HANDLE)
        {
         string head="date,time";
         for(int k=0;k<CTX_NFEAT;k++) head+=","+CTX_FEATURES[k];
         FileWriteString(g_parity,head+",P_L_p,P_L_n,P_M_p,P_M_n\r\n");
        }
     }
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   const datetime bar=iTime(_Symbol,PERIOD_M30,0);
   static datetime seen=0;
   ulong tk=0;
   const bool pos=HasPosition(tk);
   if(pos) ManagePending(true);
   if(bar==seen) return;
   seen=bar;
   ManagePosition();
   ManagePending(HasPosition(tk));
   ProcessBars();
   if(InpPanel) CtxPanel();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD && HistoryDealSelect(trans.deal) &&
      HistoryDealGetInteger(trans.deal,DEAL_MAGIC)==InpMagic && HistoryDealGetInteger(trans.deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
      g_fills++;
  }

void OnDeinit(const int reason)
  {
   PnlClear();
   if(g_too_small>0) PrintFormat("CtxLimitTester: %d entries skipped, volume below the minimum (see the first message)",g_too_small);
   if(g_parity!=INVALID_HANDLE) FileClose(g_parity);
   PrintFormat("CtxLimitTester: decisions %d, signals above threshold %d, gated by S07 %d, orders %d, fills %d, expired limits %d, 48h time stops %d",
               g_decisions,g_signals,g_gated,g_orders,g_fills,g_expired,g_timeouts);
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && PnlOnClick(sparam) && InpPanel) CtxPanel();
  }
