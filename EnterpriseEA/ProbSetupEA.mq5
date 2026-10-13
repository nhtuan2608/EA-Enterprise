#property strict
#property version   "1.000"
#property description "ProbSetupEA: G112 chase signals (C1 impulse, C2 day extreme) gated by the G114 calibrated probability / lower-bound EV. Shadow by default: it only trades when InpTradeEnabled = true."

// Research: G112 (signals, stop, X1 exit), G114 (naive-Bayes probability, isotonic calibration, Wilson 90 % lower
// bound, EV_lo = p_lo W - (1 - p_lo) L, take when EV_lo > 0, one trade at a time, 1/4 Kelly capped at 1 R).
// IMPORTANT: no family / model passed the G114 pre-registered criteria (docs/superpowers/reports/2026-10-14-g114-prob*.md);
// the frozen tables (ProbSetup/ProbTables.mqh, PS_PASSED = false) are for forward shadow evidence. The EA never
// trades unless InpTradeEnabled is switched on by the user.
// Restart-safe: no trade state in memory. The shadow ledger is rebuilt from the loaded bars on every new bar,
// an own position is found by magic and closed by time from POSITION_TIME; SL / TP sit at the broker.
// Distinct magic (141414) so it can share an account with S07Tester / CtxLimitTester / XauRegimeTester / CtxBoxTester.

#include <Trade/Trade.mqh>
#include "ProbSetup/ProbSignals.mqh"
#include "ProbSetup/ProbTables.mqh"
#include "Tester/TesterPanel.mqh"

enum PsRiskBase { PS_RISK_INITIAL=0, PS_RISK_BALANCE=1 };

input bool       InpTradeEnabled = false; // Send real orders (false = shadow only: panel + CSV)
input double     InpRiskPercent  = 0.5;   // Risk per trade, %
input PsRiskBase InpRiskBase     = PS_RISK_INITIAL; // INITIAL: % of min(equity, initial deposit); BALANCE: % of equity
input bool       InpUseKelly     = false; // Scale the risk by the 1/4 Kelly size (0..1 R); usually far below the minimum lot
input bool       InpC1           = true;  // C1 impulse chase
input bool       InpC2           = true;  // C2 day-extreme chase
input bool       InpBuy          = true;  // Buys
input bool       InpSell         = true;  // Sells
input int        InpNewsMinutes  = 0;     // Block a real entry within +/- N minutes of a HIGH USD event (0 = off, as researched)
input int        InpMaxLateSec   = 120;   // A real entry only within N seconds of the bar open (no late entries after a restart)
input int        InpHistoryBars  = 6000;  // Bars of the trading timeframe loaded (>= 2000: relative volume needs 20 days)
input bool       InpShadowCsv    = true;  // Write the shadow ledger to MQL5\Files\ProbSetupEA_shadow.csv
input long       InpMagic        = 141414;
input bool       InpPanel        = true;  // On-chart panel
input bool       InpVerbose      = false;

#define PS_CSV "ProbSetupEA_shadow.csv"

struct PsRow { PsSig s; PsDecision dec; bool taken; };

CTrade   g_trade;
double   g_initial_capital=0.0;
datetime g_last_bar=0;
PsRow    g_rows[];
int      g_nrows=0;
string   g_last_note="";
datetime g_last_note_time=0;
int      g_too_small=0;

ENUM_TIMEFRAMES PsTf() { return PS_TF_MIN==15 ? PERIOD_M15 : (PS_TF_MIN==30 ? PERIOD_M30 : PERIOD_M5); }

int FamIndex(const int fam)
  {
   for(int i=0;i<ArraySize(PS_FAMS);i++) if(PS_FAMS[i].id==fam) return i;
   return -1;
  }

bool FamEnabled(const int fam) { return (fam==1 && InpC1) || (fam==2 && InpC2); }
string FamName(const int fam)  { const int k=FamIndex(fam); return k>=0 ? PS_FAM_NAMES[k] : "?"; }

bool HasPosition(ulong &ticket)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic) { ticket=t; return true; }
     }
   return false;
  }

// time stop: 48 bars of the trading timeframe from the position open (bar-rounded), as X1
void ManagePosition()
  {
   ulong t=0;
   if(!HasPosition(t) || !PositionSelectByTicket(t)) return;
   const long sec=PS_TF_MIN*60;
   const long opened=(long)PositionGetInteger(POSITION_TIME)/sec*sec;
   const long now=(long)TimeCurrent()/sec*sec;
   if(now-opened>=PS_MAX_BARS*sec)
     {
      if(g_trade.PositionClose(t)) PrintFormat("ProbSetupEA: time stop after %d bars, ticket %I64u",PS_MAX_BARS,t);
     }
  }

double VolumeFor(const int dir,const double entry,const double stop,const double weight)
  {
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double basis=(InpRiskBase==PS_RISK_BALANCE ? equity : MathMin(equity,g_initial_capital));
   const double money=basis*InpRiskPercent/100.0*MathMax(0.0,MathMin(1.0,weight));
   double loss=0.0;
   if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   const double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   const double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin)
     {
      g_too_small++;
      if(g_too_small==1)
         PrintFormat("ProbSetupEA: risk %.2f buys %.4f lots < minimum %.2f (stop %.2f away). Raise the risk or the deposit.",
                     money,money/(-loss),vmin,MathAbs(entry-stop));
      return 0.0;
     }
   return MathMin(v,vmax);
  }

// HIGH-importance USD event within +/- InpNewsMinutes (calendar times are server times; empty in the tester)
bool NewsBlocked(const datetime now)
  {
   if(InpNewsMinutes<=0) return false;
   MqlCalendarValue v[];
   const datetime from=now-InpNewsMinutes*60, to=now+InpNewsMinutes*60;
   if(CalendarValueHistory(v,from,to,NULL,"USD")<=0) return false;
   for(int i=0;i<ArraySize(v);i++)
     {
      MqlCalendarEvent ev;
      if(CalendarEventById(v[i].event_id,ev) && ev.importance==CALENDAR_IMPORTANCE_HIGH) return true;
     }
   return false;
  }

void Note(const string s) { g_last_note=s; g_last_note_time=TimeCurrent(); if(InpVerbose) Print("ProbSetupEA: ",s); }

// one trade at a time over the shadow rows (research g114_prob.select): earliest entry, ties by the higher EV_lo;
// a trade blocks entries until its exit bar (a running trade blocks until the end)
void SelectShadow(const int n)
  {
   int order[]; ArrayResize(order,g_nrows);
   for(int i=0;i<g_nrows;i++) order[i]=i;
   for(int a=1;a<g_nrows;a++)                                   // stable insertion sort by (entry bar, -EV_lo)
     {
      const int x=order[a]; int b=a-1;
      while(b>=0 && (g_rows[order[b]].s.j>g_rows[x].s.j ||
            (g_rows[order[b]].s.j==g_rows[x].s.j && g_rows[order[b]].dec.ev_lo<g_rows[x].dec.ev_lo)))
        { order[b+1]=order[b]; b--; }
      order[b+1]=x;
     }
   int free=-1;
   for(int q=0;q<g_nrows;q++)
     {
      const int x=order[q];
      g_rows[x].taken=false;
      if(!g_rows[x].dec.ok || !FamEnabled(g_rows[x].s.fam) || (g_rows[x].s.d==1 && !InpBuy) || (g_rows[x].s.d==-1 && !InpSell)) continue;
      const int e=g_rows[x].s.j+1;
      if(e<free) continue;
      g_rows[x].taken=true;
      free=(g_rows[x].s.closed ? e+g_rows[x].s.bars : n+PS_MAX_BARS);
     }
  }

void WriteCsv(const MqlRates &rt[])
  {
   if(!InpShadowCsv) return;
   const int h=FileOpen(PS_CSV,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) return;
   FileWrite(h,"signal_time","family","dir","entry","stop","risk","side","sess","d1","h4","adx","vol","div","pos",
             "score","p","n","p_lo","ev_lo","kelly","taken","closed","R","bars","exit_time");
   for(int i=0;i<g_nrows;i++)
     {
      const PsRow r=g_rows[i];
      FileWrite(h,TimeToString(r.s.time,TIME_DATE|TIME_MINUTES),FamName(r.s.fam),r.s.d,
                DoubleToString(r.s.entry,_Digits),DoubleToString(r.s.stop,_Digits),DoubleToString(r.s.risk,_Digits),
                r.s.f[0],r.s.f[1],r.s.f[2],r.s.f[3],r.s.f[4],r.s.f[5],r.s.f[6],r.s.f[7],
                DoubleToString(r.dec.score,6),DoubleToString(r.dec.p,4),DoubleToString(r.dec.n,0),DoubleToString(r.dec.p_lo,4),
                DoubleToString(r.dec.ev_lo,4),DoubleToString(r.dec.size,4),(int)r.taken,(int)r.s.closed,DoubleToString(r.s.R,4),
                r.s.bars,(r.s.exit_j>=0 ? TimeToString(rt[r.s.exit_j].time,TIME_DATE|TIME_MINUTES) : ""));
     }
   FileClose(h);
  }

// a real entry on the signal of the bar that just closed (j = n - 2, entry bar = the bar that just opened)
void TryTrade(const MqlRates &rt[],const int n)
  {
   if(!InpTradeEnabled) return;
   ulong tk=0;
   if(HasPosition(tk)) return;
   if((long)TimeCurrent()-(long)rt[n-1].time>InpMaxLateSec) { Note("bỏ: vào trễ sau khởi động lại"); return; }
   int best=-1;
   for(int i=0;i<g_nrows;i++)
      if(g_rows[i].s.j==n-2 && g_rows[i].taken && (best<0 || g_rows[i].dec.ev_lo>g_rows[best].dec.ev_lo)) best=i;
   if(best<0) return;
   const PsRow r=g_rows[best];
   if(NewsBlocked(TimeCurrent())) { Note("bỏ: gần tin HIGH USD"); return; }
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;
   const double px=(r.s.d==1 ? tick.ask : tick.bid);
   const double risk=r.s.d*(px-r.s.stop);
   if(risk<=0.0 || risk>PS_MAX_STOP_ATR*r.s.a30) { Note("bỏ: giá đã đi quá stop / quá 3 ATR"); return; }
   const double tp=px+r.s.d*2.0*risk;
   const double weight=(InpUseKelly ? r.dec.size : 1.0);
   const double vol=VolumeFor(r.s.d,px,r.s.stop,weight);
   if(vol<=0.0) { Note("bỏ: khối lượng dưới mức tối thiểu"); return; }
   const string cmt=StringFormat("PS %s %s",FamName(r.s.fam),TimeToString(r.s.time,TIME_DATE|TIME_MINUTES));
   const bool ok=(r.s.d==1 ? g_trade.Buy(vol,_Symbol,0.0,r.s.stop,tp,cmt) : g_trade.Sell(vol,_Symbol,0.0,r.s.stop,tp,cmt));
   Note(ok ? StringFormat("VÀO %s %s %.2f lot, SL %s TP %s, EV_lo %+.3f",PnlDir(r.s.d),FamName(r.s.fam),vol,PnlPx(r.s.stop),PnlPx(tp),r.dec.ev_lo)
           : StringFormat("broker từ chối (%u)",g_trade.ResultRetcode()));
  }

bool Refresh()
  {
   const ENUM_TIMEFRAMES tf=PsTf();
   MqlRates rt[], h1[], h4[], d1[];
   ArraySetAsSeries(rt,false); ArraySetAsSeries(h1,false); ArraySetAsSeries(h4,false); ArraySetAsSeries(d1,false);
   const int n=CopyRates(_Symbol,tf,0,InpHistoryBars,rt);            // the last row is the bar that just opened
   const int n1=CopyRates(_Symbol,PERIOD_H1,1,3000,h1);
   const int n4=CopyRates(_Symbol,PERIOD_H4,1,1500,h4);
   const int nd=CopyRates(_Symbol,PERIOD_D1,1,400,d1);
   if(n<PS_NEWX_BARS+100 || n1<200 || n4<400 || nd<60) { Note("chờ đủ lịch sử nến"); return false; }
   PsSig sig[];
   const int ns=PsSignals(rt,n,h1,n1,h4,n4,d1,nd,PS_TF_MIN*60,0,_Point,sig);
   ArrayResize(g_rows,ns); g_nrows=ns;
   int lv[8];
   for(int i=0;i<ns;i++)
     {
      g_rows[i].s=sig[i];
      for(int k=0;k<8;k++) lv[k]=sig[i].f[k];
      const int fi=FamIndex(sig[i].fam);
      g_rows[i].dec.ok=false; g_rows[i].dec.ev_lo=-1e9; g_rows[i].dec.size=0; g_rows[i].dec.p=0; g_rows[i].dec.n=0; g_rows[i].dec.p_lo=0; g_rows[i].dec.score=0;
      if(fi>=0) g_rows[i].dec=PsDecide(PS_FAMS[fi],PS_LR,PS_BLOCKS,lv,PS_NFACTORS);
     }
   SelectShadow(n);
   WriteCsv(rt);
   TryTrade(rt,n);
   return true;
  }

void Panel()
  {
   if(!InpPanel || !PnlActive()) return;
   PnlBegin();
   PnlHead(StringFormat("ProbSetupEA  %s M%d  magic %I64d",_Symbol,PS_TF_MIN,InpMagic));
   if(InpTradeEnabled) PnlWarn("CHẾ ĐỘ: VÀO LỆNH THẬT (rủi ro "+DoubleToString(InpRiskPercent,2)+"%)");
   else                PnlOk("CHẾ ĐỘ: BÓNG (chỉ ghi, không đặt lệnh)");
   if(!PS_PASSED) PnlWarn("Bảng G114: CHƯA đạt tiêu chí kiểm định (chỉ để thu bằng chứng)");
   int taken=0, closed=0; double sum=0, all_sum=0; int all_n=0;
   for(int i=0;i<g_nrows;i++)
     {
      if(g_rows[i].s.closed) { all_sum+=g_rows[i].s.R; all_n++; }
      if(g_rows[i].taken) { taken++; if(g_rows[i].s.closed) { closed++; sum+=g_rows[i].s.R; } }
     }
   if(PnlSection("sum",StringFormat("Bóng trong %d nến: chọn %d (xong %d, %s/lệnh) | mọi tín hiệu %d (%s/lệnh)",
                 InpHistoryBars,taken,closed,PnlR(closed>0 ? sum/closed : 0.0),all_n,PnlR(all_n>0 ? all_sum/all_n : 0.0)),true))
     {
      PnlAdd("Chọn = EV_lo > 0 và mỗi lúc một lệnh (như G114). R tính theo X1: stop, 2R, tối đa 48 nến.");
     }
   if(PnlSection("last","Tín hiệu gần nhất",true))
     {
      int shown=0;
      for(int i=g_nrows-1;i>=0 && shown<8;i--,shown++)
        {
         const PsRow r=g_rows[i];
         const string st=(r.s.closed ? PnlR(r.s.R) : "đang chạy "+PnlR(r.s.R));
         const string line=StringFormat("%s %s %s  p %.2f (n %.0f, thấp %.2f)  EV_lo %+.3f  %s  %s",
                                        PnlTime(r.s.time),FamName(r.s.fam),PnlDir(r.s.d),r.dec.p,r.dec.n,r.dec.p_lo,r.dec.ev_lo,
                                        r.taken ? "[chọn]" : "[bỏ]",st);
         if(r.taken) PnlOk(line); else PnlAdd(line);
        }
      if(g_nrows==0) PnlAdd("chưa có tín hiệu trong lịch sử đã nạp");
     }
   ulong tk=0;
   if(PnlSection("pos",HasPosition(tk) ? "Lệnh thật: ĐANG MỞ" : "Lệnh thật: không có",false))
     {
      if(tk>0 && PositionSelectByTicket(tk))
         PnlAdd(StringFormat("%s %.2f lot, giá %s, SL %s, TP %s, %s",PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? "MUA" : "BÁN",
                PositionGetDouble(POSITION_VOLUME),PnlPx(PositionGetDouble(POSITION_PRICE_OPEN)),PnlPx(PositionGetDouble(POSITION_SL)),
                PnlPx(PositionGetDouble(POSITION_TP)),PositionGetString(POSITION_COMMENT)));
     }
   if(g_last_note!="") PnlAdd(PnlHm(g_last_note_time)+" "+g_last_note);
   PnlFlush();
  }

int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetDeviationInPoints(20);
   g_initial_capital=AccountInfoDouble(ACCOUNT_BALANCE);
   g_last_bar=0;
   if(InpHistoryBars<2000) Print("ProbSetupEA: InpHistoryBars < 2000, relative volume may stay empty");
   if(InpTradeEnabled) PrintFormat("ProbSetupEA: REAL ORDERS ON (risk %.2f%%). G114 tables passed=%s.",InpRiskPercent,PS_PASSED ? "true" : "false");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { PnlClear(); }

void OnTick()
  {
   ManagePosition();
   const datetime bt=iTime(_Symbol,PsTf(),0);
   if(bt!=0 && bt!=g_last_bar)
     {
      if(Refresh()) g_last_bar=bt;
     }
   Panel();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && PnlOnClick(sparam)) Panel();
  }
