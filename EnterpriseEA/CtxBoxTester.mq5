#property strict
#property version   "1.000"
#property description "G106 context-switch + BOX hold backtest EA for the MT5 Strategy Tester (XAUUSD): entry TF M5/M15/M30/H1, buy and sell; S07Tester risk, news and sentiment gates."

// G106 (research/long/g106_ctx_box.py, reports/2026-10-11-g106-ctx-box.md):
//   context  close beyond EMA21/55/100/200 of the entry TF AND the last closed higher-TF bar (before the bucket
//            of the entry bar) on the same side of its EMA200; higher TF: M5->M30, M15->H1, M30->H4, H1->H4
//   entry    at the entry-bar close where the context switches on (it was off on the bar before), at market
//   stop     the 16-bar entry-TF extreme -/+ 0.1 ATR14 (Wilder), at the broker
//   hold     from +1R (best price since entry): level = the far edge of the last higher-TF pause box (8 bars,
//            width <= 2.5 ATR14 of the higher TF) that price closed out of in the trade direction; exit on a
//            higher-TF close beyond level -/+ 0.25 ATR; broker stop at level -/+ 1.5 ATR, only tightening.
//            No take-profit. One position per direction.
// Gates as S07Tester.mq5 (G91): risk basis / compounding, no buy and sell at once (input), spread rule, the live
// EA's News Guard (SWING) and sentiment, from the same input files.

#property tester_file "S07Tester_news.csv"
#property tester_file "S07Tester_sentiment.csv"

#include <Trade/Trade.mqh>

enum CBT_RiskBase { CBT_RISK_INITIAL=0, CBT_RISK_BALANCE=1 };
enum CBT_EntryTf { CBT_M5=5, CBT_M15=15, CBT_M30=30, CBT_H1=60 };

input CBT_EntryTf  InpEntryTf       = CBT_M15; // Entry timeframe (higher TF: M5->M30, M15->H1, M30->H4, H1->H4)
input bool         InpBuy           = true;
input bool         InpSell          = true;
input double       InpRiskPercent   = 1.5;   // Risk per trade, % (sized on the broker stop)
input CBT_RiskBase InpRiskBase      = CBT_RISK_INITIAL; // INITIAL: % of min(equity, initial deposit) like the live EA; BALANCE: % of equity (compounding)
input bool         InpBlockOpposite = false; // true = like the live EA (no buy while a sell is open); research books each side apart
input bool         InpSpreadFilter  = true;  // Like the live EA: skip when spread > 2x the 288-bar M5 median or > 25% of the stop
input int          InpBoxBars       = 8;     // Pause box length (higher TF bars)
input double       InpBoxMaxAtr     = 2.5;   // Pause box width limit (x ATR of the higher TF)
input double       InpCloseBufAtr   = 0.25;  // Exit when a higher-TF close passes the level by this much ATR
input double       InpHardBufAtr    = 1.5;   // Broker stop distance beyond the level (ATR of the higher TF)
// G91: the live EA's News Guard (SWING profile) and sentiment, same files as S07Tester
input bool   InpNewsGuard               = true;   // News Guard: block new entries around HIGH events, break-even before USD events
input int    InpNewsSwingBlockBeforeMin = 180;    // News Guard: SWING blocks new entries this long before (live EA input)
input int    InpNewsPostMin             = 15;     // News Guard: POST_NEWS ends
input int    InpNewsMaxNormalizeMin     = 60;     // News Guard: longest wait for a stable market
input int    InpNewsBreakEvenBeforeMin  = 15;     // News Guard: break-even for profitable trades this long before
input double InpNewsBreakEvenMinR       = 0.3;    // News Guard: minimum profit (R) for that break-even
input string InpNewsIgnoreKeywords      = "Initial Jobless Claims,EIA Crude Oil,Lagarde Speech,CB Consumer Confidence,Durable Goods,Home Sales,S&P Global Services PMI,Note Auction,Money Stock"; // same default as the live EA
input bool   InpSentiment               = true;   // Sentiment: risk x0.5 when the flow is against the trade, no entry when strongly against
input long   InpMagic                   = 106106;
input bool   InpVerbose                 = false;

CTrade   g_trade;
double   g_initial_capital=0.0;
int      g_block_opposite=0, g_block_spread=0, g_block_news=0, g_block_sent=0, g_sent_reduced=0, g_news_be=0;
int      g_entries=0, g_exit_level=0;
int      g_too_small=0;              // entries skipped: the risk budget is below the minimum volume

// --- News Guard and sentiment: the S07Tester (G91) implementation --------------------------------------------
long   g_news_t[];
string g_news_cur[];
int    g_news_sec[];
int    g_news_n=0;
bool   g_news_loaded=false;

bool NewsIgnored(const string name)
  {
   if(InpNewsIgnoreKeywords=="") return false;
   string lowered=name; StringToLower(lowered);
   string parts[];
   const int n=StringSplit(InpNewsIgnoreKeywords,',',parts);
   for(int i=0;i<n;i++)
     {
      string key=parts[i]; StringTrimLeft(key); StringTrimRight(key); StringToLower(key);
      if(key!="" && StringFind(lowered,key)>=0) return true;
     }
   return false;
  }

void LoadNews()
  {
   g_news_n=0; g_news_loaded=false;
   const int h=FileOpen("S07Tester_news.csv",FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { Print("CtxBoxTester: S07Tester_news.csv missing, News Guard off"); return; }
   bool header=true;
   while(!FileIsEnding(h))
     {
      string line=FileReadString(h);
      if(header) { header=false; continue; }
      string f[];
      if(StringSplit(line,';',f)<4 || NewsIgnored(f[3])) continue;
      ArrayResize(g_news_t,g_news_n+1,4096); ArrayResize(g_news_cur,g_news_n+1,4096); ArrayResize(g_news_sec,g_news_n+1,4096);
      g_news_t[g_news_n]=StringToInteger(f[0]); g_news_cur[g_news_n]=f[1]; g_news_sec[g_news_n]=(int)StringToInteger(f[2]);
      g_news_n++;
     }
   FileClose(h);
   g_news_loaded=(g_news_n>0);
   PrintFormat("CtxBoxTester: %d HIGH news events loaded",g_news_n);
  }

int NewsFirstFrom(const long t)
  {
   int lo=0, hi=g_news_n;
   while(lo<hi) { const int mid=(lo+hi)/2; if(g_news_t[mid]<t) lo=mid+1; else hi=mid; }
   return lo;
  }

bool StrengthSector(const int sector)
  {
   return sector==(int)CALENDAR_SECTOR_MONEY || sector==(int)CALENDAR_SECTOR_PRICES ||
          sector==(int)CALENDAR_SECTOR_JOBS || sector==(int)CALENDAR_SECTOR_GDP;
  }

bool MarketStable()
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,PERIOD_M5,1,288,r);
   if(n<20) return false;
   double sp[];
   ArrayResize(sp,n);
   for(int i=0;i<n;i++) sp[i]=(double)r[i].spread;
   ArraySort(sp);
   const double median=sp[n/2];
   const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   const double spread=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/point;
   double tr=0.0;
   for(int i=n-14;i<n;i++) tr+=MathMax(r[i].high,r[i-1].close)-MathMin(r[i].low,r[i-1].close);
   const double atr=tr/14.0;
   return median>0.0 && spread<=1.5*median && atr>0.0 && (r[n-1].high-r[n-1].low)<=2.0*atr;
  }

bool NewsBlocked(const long now)
  {
   if(!InpNewsGuard || !g_news_loaded) return false;
   const long from=now-(long)InpNewsMaxNormalizeMin*60;
   bool normalizing=false;
   for(int i=NewsFirstFrom(from);i<g_news_n && g_news_t[i]<=now+(long)InpNewsSwingBlockBeforeMin*60;i++)
     {
      const long t=g_news_t[i];
      const bool in_window=(now>=t-(long)InpNewsSwingBlockBeforeMin*60 && now<t+(long)InpNewsPostMin*60);
      if(g_news_cur[i]=="USD")
        {
         if(in_window) return true;
         if(now>=t+(long)InpNewsPostMin*60 && now<t+(long)InpNewsMaxNormalizeMin*60) normalizing=true;
        }
      else if(in_window && StrengthSector(g_news_sec[i])) return true;
     }
   return normalizing && !MarketStable();
  }

bool NewsBreakEvenDue(const long now)
  {
   if(!InpNewsGuard || !g_news_loaded) return false;
   for(int i=NewsFirstFrom(now-(long)InpNewsPostMin*60);i<g_news_n && g_news_t[i]<=now+(long)InpNewsBreakEvenBeforeMin*60;i++)
      if(g_news_cur[i]=="USD" && now>=g_news_t[i]-(long)InpNewsBreakEvenBeforeMin*60 && now<g_news_t[i]+(long)InpNewsPostMin*60)
         return true;
   return false;
  }

long   g_sent_t[];
double g_sent_v[][6];
bool   g_sent_ok[];
int    g_sent_n=0;

void LoadSentiment()
  {
   g_sent_n=0;
   const int h=FileOpen("S07Tester_sentiment.csv",FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { Print("CtxBoxTester: S07Tester_sentiment.csv missing, sentiment off"); return; }
   bool header=true;
   while(!FileIsEnding(h))
     {
      string line=FileReadString(h);
      if(header) { header=false; continue; }
      string f[];
      if(StringSplit(line,';',f)<8) continue;
      ArrayResize(g_sent_t,g_sent_n+1,4096); ArrayResize(g_sent_v,g_sent_n+1,4096); ArrayResize(g_sent_ok,g_sent_n+1,4096);
      g_sent_t[g_sent_n]=StringToInteger(f[0]); g_sent_ok[g_sent_n]=(f[1]=="1");
      for(int k=0;k<6;k++) g_sent_v[g_sent_n][k]=StringToDouble(f[k+2]);
      g_sent_n++;
     }
   FileClose(h);
   PrintFormat("CtxBoxTester: %d sentiment H1 bars loaded",g_sent_n);
  }

double SentimentFactor(const int dir,const long now)
  {
   if(!InpSentiment || g_sent_n==0) return 1.0;
   int lo=0, hi=g_sent_n;
   while(lo<hi) { const int mid=(lo+hi)/2; if(g_sent_t[mid]+3600<=now) lo=mid+1; else hi=mid; }
   const int k=lo-1;
   if(k<0 || !g_sent_ok[k] || now-g_sent_t[k]>6*3600) return 1.0;
   const double a4=dir*g_sent_v[k][0], a24=dir*g_sent_v[k][1];
   const double ag4=(dir==1 ? g_sent_v[k][2] : g_sent_v[k][4]), ag24=(dir==1 ? g_sent_v[k][3] : g_sent_v[k][5]);
   if(a4<=-0.8 && a24<=-0.8 && ag4>=0.7 && ag24>=0.7) return 0.0;
   if(a4<=-0.3 && a24<=-0.3) return 0.5;
   return 1.0;
  }

double MedianSpreadPoints()
  {
   MqlRates r[];
   const int n=CopyRates(_Symbol,PERIOD_M5,1,288,r);
   if(n<=0) return 0.0;
   double v[];
   ArrayResize(v,n);
   int used=0;
   for(int i=0;i<n;i++) if(r[i].spread>0) v[used++]=(double)r[i].spread;
   if(used==0) return 0.0;
   ArrayResize(v,used);
   ArraySort(v);
   return (used%2==1) ? v[used/2] : 0.5*(v[used/2-1]+v[used/2]);
  }
// --- context + BOX ------------------------------------------------------------------------------------------------
ENUM_TIMEFRAMES EntryTf()
  {
   switch(InpEntryTf) { case CBT_M5: return PERIOD_M5; case CBT_M30: return PERIOD_M30; case CBT_H1: return PERIOD_H1; }
   return PERIOD_M15;
  }

ENUM_TIMEFRAMES HigherTf()
  {
   switch(InpEntryTf) { case CBT_M5: return PERIOD_M30; case CBT_M15: return PERIOD_H1; }
   return PERIOD_H4;
  }

struct CBTLeg
  {
   bool   open;
   ulong  ticket;
   double entry, risk, best, level, hard;
   bool   has_box, be_done;
   double box_hi, box_lo;
  };

CBTLeg   g_leg[2];                  // [0] buy, [1] sell
datetime g_last_entry_bar=0, g_last_higher_bar=0;
int      g_prev_ctx[2]={0,0};       // context of the previous entry bar (-1 unknown)

int Side(const int dir) { return dir==1 ? 0 : 1; }

void EmaArr(const MqlRates &r[],const int n,const int period,double &out[])
  {
   ArrayResize(out,n);
   const double k=2.0/(period+1.0);
   out[0]=r[0].close;
   for(int i=1;i<n;i++) out[i]=r[i].close*k+out[i-1]*(1.0-k);
  }

// Wilder ATR14 (the research dmi(): ewm alpha 1/14 of the true range, seeded with the first range)
void AtrWilder(const MqlRates &r[],const int n,double &out[])
  {
   ArrayResize(out,n);
   out[0]=r[0].high-r[0].low;
   for(int i=1;i<n;i++)
     {
      const double tr=MathMax(r[i].high,r[i-1].close)-MathMin(r[i].low,r[i-1].close);
      out[i]=out[i-1]+(tr-out[i-1])/14.0;
     }
  }

// Side of the higher-TF EMA200 for the last higher bar opened before `bucket_start`.
int HigherSide(const MqlRates &h[],const double &he[],const int hn,const datetime bucket_start)
  {
   for(int k=hn-1;k>=200;k--)
      if(h[k].time<bucket_start) return h[k].close>he[k] ? 1 : (h[k].close<he[k] ? -1 : 0);
   return 0;
  }

double VolumeFor(const int dir,const double entry,const double stop,const double weight)
  {
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double basis=(InpRiskBase==CBT_RISK_BALANCE ? equity : MathMin(equity,g_initial_capital));
   const double money=basis*InpRiskPercent/100.0*MathMax(0.0,MathMin(1.0,weight));
   double loss=0.0;
   if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin)
     {
      // the risk budget buys less than the minimum volume (small deposit, wide stop, or the tester's
      // "profit in pips" mode, where OrderCalcProfit returns points instead of money)
      g_too_small++;
      if(g_too_small==1)
         PrintFormat("%s: risk %.2f buys %.4f lots < minimum %.2f (stop %.2f away, loss per lot %.2f). "
                     "Use money profit (not pips) in the tester, a larger deposit or a higher risk %%.",
                     "CtxBoxTester",money,money/(-loss),vmin,MathAbs(entry-stop),-loss);
      return 0.0;
     }
   return MathMin(v,vmax);
  }

void SyncLegs()
  {
   for(int s=0;s<2;s++)
      if(g_leg[s].open && !PositionSelectByTicket(g_leg[s].ticket)) g_leg[s].open=false;
  }

void TryEnter(const int dir,const double stop_raw)
  {
   const int s=Side(dir);
   if(g_leg[s].open) return;
   if((dir==1 && !InpBuy) || (dir==-1 && !InpSell)) return;
   if(InpBlockOpposite && g_leg[1-s].open) { g_block_opposite++; return; }
   if(NewsBlocked((long)TimeCurrent())) { g_block_news++; return; }
   const double sent=SentimentFactor(dir,(long)TimeCurrent());
   if(sent<=0.0) { g_block_sent++; return; }
   const double price=(dir==1 ? SymbolInfoDouble(_Symbol,SYMBOL_ASK) : SymbolInfoDouble(_Symbol,SYMBOL_BID));
   const double dist=dir*(price-stop_raw);
   if(dist<=0.0) return;
   if(InpSpreadFilter)
     {
      const double spread=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
      const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
      const double median=MedianSpreadPoints();
      if(median>0.0 && point>0.0 && spread/point>2.0*median) { g_block_spread++; return; }
      if(spread>0.25*dist) { g_block_spread++; return; }
     }
   if(sent<1.0) g_sent_reduced++;
   const double vol=VolumeFor(dir,price,stop_raw,sent);
   if(vol<=0.0) return;
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   const bool ok=(dir==1 ? g_trade.Buy(vol,_Symbol,0.0,NormalizeDouble(stop_raw,digits),0.0,"CBT")
                         : g_trade.Sell(vol,_Symbol,0.0,NormalizeDouble(stop_raw,digits),0.0,"CBT"));
   if(!ok || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE) return;
   ulong ticket=0;
   const ulong deal=g_trade.ResultDeal();
   if(deal>0 && HistoryDealSelect(deal)) ticket=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   if(ticket==0) ticket=g_trade.ResultOrder();
   CBTLeg L;
   L.open=true; L.ticket=ticket; L.entry=g_trade.ResultPrice(); if(L.entry<=0.0) L.entry=price;
   L.risk=MathAbs(L.entry-stop_raw); L.best=L.entry; L.level=0.0; L.hard=stop_raw;
   L.has_box=false; L.be_done=false; L.box_hi=0.0; L.box_lo=0.0;
   g_leg[s]=L;
   g_entries++;
   if(InpVerbose) PrintFormat("CBT %s vol %.2f entry %.2f stop %.2f",dir==1 ? "BUY" : "SELL",vol,L.entry,stop_raw);
  }

// Entry-TF bar closed: context switch -> entry.
void OnEntryBar()
  {
   const ENUM_TIMEFRAMES etf=EntryTf(), htf=HigherTf();
   MqlRates r[], h[];
   ArraySetAsSeries(r,false); ArraySetAsSeries(h,false);
   const int n=CopyRates(_Symbol,etf,1,700,r);
   const int hn=CopyRates(_Symbol,htf,1,700,h);
   if(n<420 || hn<220) return;
   double e21[],e55[],e100[],e200[],atr[],he[];
   EmaArr(r,n,21,e21); EmaArr(r,n,55,e55); EmaArr(r,n,100,e100); EmaArr(r,n,200,e200); AtrWilder(r,n,atr);
   EmaArr(h,hn,200,he);
   const long hsec=PeriodSeconds(htf);
   for(int pass=0;pass<2;pass++)
     {
      const int i=n-1-pass;                       // pass 0: this bar, pass 1: the bar before
      const datetime bucket=(datetime)((long)r[i].time-(long)r[i].time%hsec);
      const int hs=HigherSide(h,he,hn,bucket);
      const double lo=MathMin(MathMin(e21[i],e55[i]),MathMin(e100[i],e200[i]));
      const double hi=MathMax(MathMax(e21[i],e55[i]),MathMax(e100[i],e200[i]));
      const int ctx=(r[i].close>hi && hs==1) ? 1 : ((r[i].close<lo && hs==-1) ? -1 : 0);
      if(pass==0) g_prev_ctx[0]=ctx; else g_prev_ctx[1]=ctx;
     }
   const int now=g_prev_ctx[0], before=g_prev_ctx[1];
   if(now==0 || now==before) return;
   const int i=n-1;
   double ext=(now==1 ? r[i].low : r[i].high);
   for(int k=i-15;k<=i;k++) ext=(now==1 ? MathMin(ext,r[k].low) : MathMax(ext,r[k].high));
   TryEnter(now,ext-now*0.1*atr[i]);
  }

// Higher-TF bar closed: BOX hold for each open leg.
void OnHigherBar()
  {
   const ENUM_TIMEFRAMES htf=HigherTf();
   MqlRates h[];
   ArraySetAsSeries(h,false);
   const int hn=CopyRates(_Symbol,htf,1,InpBoxBars+40,h);
   if(hn<InpBoxBars+20) return;
   double atr[];
   ArrayResize(atr,hn);
   for(int k=0;k<hn;k++) atr[k]=0.0;
   for(int k=14;k<hn;k++)                         // simple mean of 14 true ranges (research box ATR)
     {
      double s=0.0;
      for(int q=k-13;q<=k;q++) s+=MathMax(h[q].high,h[q-1].close)-MathMin(h[q].low,h[q-1].close);
      atr[k]=s/14.0;
     }
   const int k=hn-1, b=hn-2;                      // k just closed; the box ends at k-1
   double bh=h[b].high, bl=h[b].low;
   for(int q=b-InpBoxBars+1;q<=b;q++) { bh=MathMax(bh,h[q].high); bl=MathMin(bl,h[q].low); }
   const bool box_ok=(bh-bl)<=InpBoxMaxAtr*atr[b];
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   for(int s=0;s<2;s++)
     {
      if(!g_leg[s].open) continue;
      if(!PositionSelectByTicket(g_leg[s].ticket)) { g_leg[s].open=false; continue; }
      const int d=(s==0 ? 1 : -1);
      const double hc=h[k].close, at=atr[k];
      if(box_ok && d*(hc-(d==-1 ? bl : bh))>0) { g_leg[s].has_box=true; g_leg[s].box_hi=bh; g_leg[s].box_lo=bl; }
      if(g_leg[s].has_box && g_leg[s].risk>0.0 && d*(g_leg[s].best-g_leg[s].entry)/g_leg[s].risk>=1.0)
        {
         const double nl=(d==-1 ? g_leg[s].box_hi : g_leg[s].box_lo);
         if(g_leg[s].level==0.0 || d*(nl-g_leg[s].level)>0.0)
           {
            g_leg[s].level=nl;
            const double cand=nl-d*InpHardBufAtr*at;
            if(d*(cand-g_leg[s].hard)>0.0 && g_trade.PositionModify(g_leg[s].ticket,NormalizeDouble(cand,digits),0.0))
               g_leg[s].hard=cand;
           }
        }
      if(g_leg[s].level!=0.0 && d*(hc-(g_leg[s].level-d*InpCloseBufAtr*at))<0.0)
        {
         if(g_trade.PositionClose(g_leg[s].ticket)) { g_leg[s].open=false; g_exit_level++; }
         if(InpVerbose) PrintFormat("CBT exit %s at level %.2f",d==1 ? "BUY" : "SELL",g_leg[s].level);
        }
     }
  }

void TrackBest()
  {
   const double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(g_leg[0].open) g_leg[0].best=MathMax(g_leg[0].best,bid);
   if(g_leg[1].open) g_leg[1].best=MathMin(g_leg[1].best,ask);
  }

void NewsBreakEven()
  {
   if(!NewsBreakEvenDue((long)TimeCurrent())) return;
   const double spread=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   for(int s=0;s<2;s++)
     {
      if(!g_leg[s].open || g_leg[s].be_done || g_leg[s].risk<=0.0 || !PositionSelectByTicket(g_leg[s].ticket)) continue;
      const int d=(s==0 ? 1 : -1);
      const double now=(d==1 ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK));
      if(d*(now-g_leg[s].entry)/g_leg[s].risk<InpNewsBreakEvenMinR) continue;
      const double be=NormalizeDouble(g_leg[s].entry+d*spread,digits);
      const double sl=PositionGetDouble(POSITION_SL);
      if(d*(be-sl)<=0.0) { g_leg[s].be_done=true; continue; }
      if(g_trade.PositionModify(g_leg[s].ticket,be,0.0)) { g_leg[s].be_done=true; g_leg[s].hard=be; g_news_be++; }
     }
  }

int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   g_initial_capital=AccountInfoDouble(ACCOUNT_BALANCE);
   for(int s=0;s<2;s++) g_leg[s].open=false;
   LoadNews();
   LoadSentiment();
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   SyncLegs();
   TrackBest();
   const datetime hb=iTime(_Symbol,HigherTf(),1);
   if(hb!=0 && hb!=g_last_higher_bar) { g_last_higher_bar=hb; OnHigherBar(); }
   const datetime eb=iTime(_Symbol,EntryTf(),1);
   if(eb!=0 && eb!=g_last_entry_bar)
     {
      g_last_entry_bar=eb;
      NewsBreakEven();
      OnEntryBar();
     }
  }

void OnDeinit(const int reason)
  {
   if(g_too_small>0) PrintFormat("CtxBoxTester: %d entries skipped, volume below the minimum (see the first message)",g_too_small);
   PrintFormat("CtxBoxTester %s: entries %d, level exits %d; blocked by opposite %d, spread %d, news %d, sentiment %d; sentiment-reduced %d; news break-evens %d",
               EnumToString(EntryTf()),g_entries,g_exit_level,g_block_opposite,g_block_spread,g_block_news,g_block_sent,
               g_sent_reduced,g_news_be);
  }
