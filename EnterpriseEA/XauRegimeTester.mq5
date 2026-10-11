#property strict
#property version   "1.000"
#property description "G96 gold trend-regime backtest EA for the MT5 Strategy Tester: D1 regime (EMA side + slope), market or limit-zone entries, trail; S07Tester risk, news and sentiment gates."

// G96 (docs/superpowers/plans/2026-10-11-g96-xau-regime.md, reports/2026-10-11-g96-xau-regime.md):
//   regime   R1: the closed D1 bar's close and the EMA's 10-day slope on the same side of EMA(N) -> +1 / -1, else 0
//   entry    each day in the regime without a position: a market order at the day open, or one limit order
//            at a zone (valid for the day; a level already through the price fills at market)
//   stop     fill -/+ InpStopAtr x ATR20 D1 at the broker
//   exit     the regime leaves the direction (next day open), a D1 close InpTrailAtr x ATR from the best close
//            since entry (next day open; no new entry until the regime changes), or the stop
// The gates are those of S07Tester.mq5 (G91): risk basis / compounding, no buy and sell at once, spread rule,
// the live EA's News Guard (SWING) and sentiment, from the same input files (research/long/g91_tester_inputs.py).

#property tester_file "S07Tester_news.csv"
#property tester_file "S07Tester_sentiment.csv"

#include <Trade/Trade.mqh>

enum XRT_RiskBase { XRT_RISK_INITIAL=0, XRT_RISK_BALANCE=1 };
enum XRT_Mode { XRT_LONG_ONLY=0, XRT_LONG_SHORT=1, XRT_SHORT_ONLY=2 };
enum XRT_Zone
  {
   XRT_MARKET=0,        // Z0 market at the day open
   XRT_EMA21_D1=1,      // Z1 EMA21 D1
   XRT_EMA50_D1=2,      // Z2 EMA50 D1
   XRT_PREV_EXTREME=3,  // Z3 prior day low (buy) / high (sell)
   XRT_PREV_MID=4,      // Z4 prior day middle
   XRT_CLOSE_05ATR=5,   // Z5 prior close -/+ 0.5 ATR
   XRT_CLOSE_1ATR=6,    // Z6 prior close -/+ 1 ATR
   XRT_SWING=7,         // Z7 last 5-bar fractal low (buy) / high (sell)
   XRT_EMA21_H4=8       // Z8 EMA21 H4 at the day open
  };

input double       InpRiskPercent   = 1.5;   // Risk per trade, % (sized on the broker stop)
input XRT_RiskBase InpRiskBase      = XRT_RISK_INITIAL; // INITIAL: % of min(equity, initial deposit) like the live EA; BALANCE: % of equity (compounding)
input bool         InpBlockOpposite = true;  // Like the live EA: no buy while a sell is open and the reverse
input bool         InpSpreadFilter  = true;  // Like the live EA: skip when spread > 2x the 288-bar M5 median or > 25% of the stop
input XRT_Mode     InpMode          = XRT_LONG_ONLY; // G96: buying only was the best; selling gold had no edge in any period
input int          InpEmaPeriod     = 50;    // Regime EMA on D1 (G96 cells: 50 / 100 / 200)
input int          InpSlopeDays     = 10;    // EMA slope over this many D1 bars
input int          InpAtrPeriod     = 20;    // ATR on D1 (simple mean of the true range)
input XRT_Zone     InpBuyZone       = XRT_MARKET;   // Buy entry: market or limit zone
input XRT_Zone     InpSellZone      = XRT_EMA21_D1; // Sell entry (G96: limits at EMA21/EMA50/swing took sells from -0.20R to break-even)
input double       InpStopAtr       = 3.0;   // Broker stop, ATR D1 from the fill (G96 part A ~ the 3 ATR trail; part B used 1.0)
input bool         InpTrail         = true;  // Exit on a D1 close InpTrailAtr x ATR from the best close since entry
input double       InpTrailAtr      = 3.0;
// G91: the live EA's News Guard (SWING profile) and sentiment, same files as S07Tester
input bool   InpNewsGuard               = true;   // News Guard: block new entries around HIGH events, break-even before USD events
input int    InpNewsSwingBlockBeforeMin = 180;    // News Guard: SWING blocks new entries this long before (live EA input)
input int    InpNewsPostMin             = 15;     // News Guard: POST_NEWS ends
input int    InpNewsMaxNormalizeMin     = 60;     // News Guard: longest wait for a stable market
input int    InpNewsBreakEvenBeforeMin  = 15;     // News Guard: break-even for profitable trades this long before
input double InpNewsBreakEvenMinR       = 0.3;    // News Guard: minimum profit (R) for that break-even
input string InpNewsIgnoreKeywords      = "Initial Jobless Claims,EIA Crude Oil,Lagarde Speech,CB Consumer Confidence,Durable Goods,Home Sales,S&P Global Services PMI,Note Auction,Money Stock"; // same default as the live EA
input bool   InpSentiment               = true;   // Sentiment: risk x0.5 when the flow is against the trade, no entry when strongly against
input long   InpMagic                   = 969696;
input bool   InpVerbose                 = false;

#define XRT_D1_HISTORY 800

CTrade   g_trade;
double   g_initial_capital=0.0;
int      g_block_opposite=0, g_block_spread=0, g_block_news=0, g_block_sent=0, g_sent_reduced=0, g_news_be=0;
int      g_entries=0, g_exit_regime=0, g_exit_trail=0, g_limits_placed=0, g_limits_expired=0;

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
   if(h==INVALID_HANDLE) { Print("XauRegimeTester: S07Tester_news.csv missing, News Guard off"); return; }
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
   PrintFormat("XauRegimeTester: %d HIGH news events loaded",g_news_n);
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
   if(h==INVALID_HANDLE) { Print("XauRegimeTester: S07Tester_sentiment.csv missing, sentiment off"); return; }
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
   PrintFormat("XauRegimeTester: %d sentiment H1 bars loaded",g_sent_n);
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

// --- D1 regime ------------------------------------------------------------------------------------------------
struct XRTDay
  {
   bool     ok;
   int      state;       // regime of the last closed D1 bar
   double   atr, close, high, low, ema21, ema50, swing_low, swing_high;
  };

XRTDay   g_day;
datetime g_last_d1=0, g_last_m5=0;
int      g_dir=0;             // direction of the open position (0 = none)
ulong    g_ticket=0;
double   g_entry=0.0, g_risk=0.0, g_best=0.0;
bool     g_be_done=false;
int      g_blocked_dir=0;     // after a trail exit: no new entry this side until the regime changes
ulong    g_pending=0;         // today's limit order
int      g_pending_dir=0;
double   g_pending_level=0.0;
bool     g_want_entry=false;  // an entry for today still to be placed (news / spread can delay it)

void Ema(const MqlRates &r[],const int n,const int period,double &out[])
  {
   ArrayResize(out,n);
   const double k=2.0/(period+1.0);
   out[0]=r[0].close;
   for(int i=1;i<n;i++) out[i]=r[i].close*k+out[i-1]*(1.0-k);
  }

bool RefreshDay()
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,PERIOD_D1,1,XRT_D1_HISTORY,r);
   g_day.ok=false;
   if(n<MathMax(2*InpEmaPeriod,InpAtrPeriod+InpSlopeDays+5)) return false;
   double e[], e21[], e50[];
   Ema(r,n,InpEmaPeriod,e); Ema(r,n,21,e21); Ema(r,n,50,e50);
   const int i=n-1;
   double tr=0.0;
   for(int k=i-InpAtrPeriod+1;k<=i;k++) tr+=MathMax(r[k].high,r[k-1].close)-MathMin(r[k].low,r[k-1].close);
   g_day.atr=tr/InpAtrPeriod;
   const int side=(r[i].close>e[i] ? 1 : (r[i].close<e[i] ? -1 : 0));
   const int slope=(e[i]>e[i-InpSlopeDays] ? 1 : (e[i]<e[i-InpSlopeDays] ? -1 : 0));
   g_day.state=(side==slope ? side : 0);
   g_day.close=r[i].close; g_day.high=r[i].high; g_day.low=r[i].low; g_day.ema21=e21[i]; g_day.ema50=e50[i];
   g_day.swing_low=0.0; g_day.swing_high=0.0;
   for(int k=i-2;k>=2;k--)            // fractal confirmed two bars later
     {
      if(g_day.swing_low==0.0 && r[k].low<=MathMin(MathMin(r[k-2].low,r[k-1].low),MathMin(r[k+1].low,r[k+2].low))) g_day.swing_low=r[k].low;
      if(g_day.swing_high==0.0 && r[k].high>=MathMax(MathMax(r[k-2].high,r[k-1].high),MathMax(r[k+1].high,r[k+2].high))) g_day.swing_high=r[k].high;
      if(g_day.swing_low>0.0 && g_day.swing_high>0.0) break;
     }
   g_day.ok=(g_day.atr>0.0);
   return g_day.ok;
  }

double Ema21H4()
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,PERIOD_H4,1,300,r);
   if(n<100) return 0.0;
   double e[];
   Ema(r,n,21,e);
   return e[n-1];
  }

double ZoneLevel(const XRT_Zone z,const int dir)
  {
   switch(z)
     {
      case XRT_EMA21_D1:     return g_day.ema21;
      case XRT_EMA50_D1:     return g_day.ema50;
      case XRT_PREV_EXTREME: return dir==1 ? g_day.low : g_day.high;
      case XRT_PREV_MID:     return 0.5*(g_day.high+g_day.low);
      case XRT_CLOSE_05ATR:  return g_day.close-dir*0.5*g_day.atr;
      case XRT_CLOSE_1ATR:   return g_day.close-dir*1.0*g_day.atr;
      case XRT_SWING:        return dir==1 ? g_day.swing_low : g_day.swing_high;
      case XRT_EMA21_H4:     return Ema21H4();
      default:               return 0.0;
     }
  }

bool Allowed(const int dir)
  {
   if(InpMode==XRT_LONG_ONLY) return dir==1;
   if(InpMode==XRT_SHORT_ONLY) return dir==-1;
   return dir!=0;
  }

double VolumeFor(const int dir,const double entry,const double stop,const double weight)
  {
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double basis=(InpRiskBase==XRT_RISK_BALANCE ? equity : MathMin(equity,g_initial_capital));
   const double money=basis*InpRiskPercent/100.0*MathMax(0.0,MathMin(1.0,weight));
   double loss=0.0;
   if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin) return 0.0;
   return MathMin(v,vmax);
  }

// --- positions ------------------------------------------------------------------------------------------------
bool OwnPosition(int &dir)
  {
   dir=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong t=PositionGetTicket(i);
      if(t==0 || PositionGetInteger(POSITION_MAGIC)!=InpMagic || PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      dir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
      if(g_ticket!=t)                      // a limit order filled since the last check
        {
         g_ticket=t; g_entry=PositionGetDouble(POSITION_PRICE_OPEN);
         g_risk=MathAbs(g_entry-PositionGetDouble(POSITION_SL)); g_best=g_entry; g_be_done=false; g_entries++;
         g_pending=0; g_pending_dir=0; g_want_entry=false;
        }
      return true;
     }
   g_ticket=0;
   return false;
  }

void DeletePending()
  {
   if(g_pending!=0 && OrderSelect(g_pending)) g_trade.OrderDelete(g_pending);
   g_pending=0; g_pending_dir=0;
  }

// The gates of the live EA / S07Tester; returns the risk weight (0 = no entry now).
double EntryGate(const int dir,const double price,const double stop)
  {
   int open_dir=0;
   if(InpBlockOpposite && OwnPosition(open_dir) && open_dir==-dir) { g_block_opposite++; return 0.0; }
   if(NewsBlocked((long)TimeCurrent())) { g_block_news++; return 0.0; }
   const double sent=SentimentFactor(dir,(long)TimeCurrent());
   if(sent<=0.0) { g_block_sent++; return 0.0; }
   if(InpSpreadFilter)
     {
      const double spread=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
      const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
      const double median=MedianSpreadPoints();
      if(median>0.0 && point>0.0 && spread/point>2.0*median) { g_block_spread++; return 0.0; }
      if(spread>0.25*MathAbs(price-stop)) { g_block_spread++; return 0.0; }
     }
   if(sent<1.0) g_sent_reduced++;
   return sent;
  }

// Place today's entry (market or limit). Returns true when nothing is left to do today.
bool PlaceEntry()
  {
   const int dir=g_day.state;
   if(!Allowed(dir) || dir==g_blocked_dir) return true;
   const XRT_Zone zone=(dir==1 ? InpBuyZone : InpSellZone);
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const double market=(dir==1 ? ask : bid);
   double level=(zone==XRT_MARKET ? 0.0 : ZoneLevel(zone,dir));
   if(zone!=XRT_MARKET && level<=0.0) return true;
   const bool at_market=(zone==XRT_MARKET || dir*(market-level)<=0.0);   // a level already through the price
   const double price=(at_market ? market : level);
   const double stop=price-dir*InpStopAtr*g_day.atr;
   const double w=EntryGate(dir,price,stop);
   if(w<=0.0) return false;                                            // retry on a later M5 bar today
   const double vol=VolumeFor(dir,price,stop,w);
   if(vol<=0.0) return true;
   bool ok;
   if(at_market)
     {
      ok=(dir==1 ? g_trade.Buy(vol,_Symbol,0.0,NormalizeDouble(stop,digits),0.0,"XRT")
                 : g_trade.Sell(vol,_Symbol,0.0,NormalizeDouble(stop,digits),0.0,"XRT"));
      if(ok && g_trade.ResultRetcode()==TRADE_RETCODE_DONE) { int d; OwnPosition(d); }
     }
   else
     {
      const datetime expiry=(datetime)(iTime(_Symbol,PERIOD_D1,0)+86400-60);
      ok=(dir==1 ? g_trade.BuyLimit(vol,NormalizeDouble(level,digits),_Symbol,NormalizeDouble(stop,digits),0.0,ORDER_TIME_SPECIFIED,expiry,"XRT")
                 : g_trade.SellLimit(vol,NormalizeDouble(level,digits),_Symbol,NormalizeDouble(stop,digits),0.0,ORDER_TIME_SPECIFIED,expiry,"XRT"));
      if(ok) { g_pending=g_trade.ResultOrder(); g_pending_dir=dir; g_pending_level=level; g_limits_placed++; }
     }
   if(InpVerbose) PrintFormat("XRT %s %s level %.2f stop %.2f vol %.2f ok %d",dir==1 ? "BUY" : "SELL",
                              at_market ? "market" : "limit",price,stop,vol,ok);
   return true;
  }

void CloseOwn(const string why)
  {
   if(g_ticket!=0 && g_trade.PositionClose(g_ticket))
     {
      if(InpVerbose) PrintFormat("XRT exit: %s",why);
      g_ticket=0;
     }
  }

// At a new D1 bar: exits on the closed bar, then today's entry.
void OnNewDay()
  {
   if(g_pending!=0) { if(OrderSelect(g_pending)) g_limits_expired++; DeletePending(); }
   if(!RefreshDay()) return;
   int dir=0;
   if(OwnPosition(dir))
     {
      g_best=(dir==1 ? MathMax(g_best,g_day.close) : MathMin(g_best,g_day.close));
      if(g_day.state!=dir) { CloseOwn("regime"); g_exit_regime++; }
      else if(InpTrail && dir*(g_day.close-g_best)<=-InpTrailAtr*g_day.atr)
        { CloseOwn("trail"); g_exit_trail++; g_blocked_dir=dir; }
     }
   if(g_blocked_dir!=0 && g_day.state!=g_blocked_dir) g_blocked_dir=0;
   g_want_entry=!OwnPosition(dir);
  }

void NewsBreakEven()
  {
   if(g_ticket==0 || g_be_done || g_risk<=0.0 || !NewsBreakEvenDue((long)TimeCurrent())) return;
   if(!PositionSelectByTicket(g_ticket)) return;
   const int d=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
   const double now=(d==1 ? SymbolInfoDouble(_Symbol,SYMBOL_BID) : SymbolInfoDouble(_Symbol,SYMBOL_ASK));
   if(d*(now-g_entry)/g_risk<InpNewsBreakEvenMinR) return;
   const double spread=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   const double be=NormalizeDouble(g_entry+d*spread,digits);
   const double sl=PositionGetDouble(POSITION_SL);
   if(d*(be-sl)<=0.0) { g_be_done=true; return; }
   if(g_trade.PositionModify(g_ticket,be,0.0)) { g_be_done=true; g_news_be++; }
  }

int OnInit()
  {
   if(InpStopAtr<=0.0 || InpEmaPeriod<2 || InpSlopeDays<1 || InpAtrPeriod<2) return INIT_PARAMETERS_INCORRECT;
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   g_initial_capital=AccountInfoDouble(ACCOUNT_BALANCE);
   LoadNews();
   LoadSentiment();
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   const datetime d1=iTime(_Symbol,PERIOD_D1,0);
   if(d1!=0 && d1!=g_last_d1) { g_last_d1=d1; OnNewDay(); }
   const datetime m5=iTime(_Symbol,PERIOD_M5,0);
   if(m5==g_last_m5) return;
   g_last_m5=m5;
   int dir=0;
   OwnPosition(dir);
   NewsBreakEven();
   // News Guard on a waiting limit: pull it while new entries are blocked, place it again afterwards.
   if(g_pending!=0)
     {
      if(!OrderSelect(g_pending)) { g_pending=0; g_pending_dir=0; }
      else if(NewsBlocked((long)TimeCurrent())) { DeletePending(); g_block_news++; g_want_entry=true; }
     }
   if(g_want_entry && g_pending==0 && g_ticket==0 && g_day.ok)
      if(PlaceEntry()) g_want_entry=false;
  }

void OnDeinit(const int reason)
  {
   PrintFormat("XauRegimeTester: entries %d, limits placed %d (expired %d), exits regime %d trail %d; blocked by opposite %d, spread %d, news %d, sentiment %d; sentiment-reduced %d; news break-evens %d",
               g_entries,g_limits_placed,g_limits_expired,g_exit_regime,g_exit_trail,g_block_opposite,g_block_spread,
               g_block_news,g_block_sent,g_sent_reduced,g_news_be);
  }
