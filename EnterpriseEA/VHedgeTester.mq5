#property strict
#property version   "1.000"
#property description "G119 V-hedge: M5 EMA200 V candle, return into its range, bundled EMAs + volume filter, hedge, add at the break, 5R target, break-even at +1R. SHADOW (virtual) or LIVE."

// Rules = research/long/g116_v_hedge.py + g119_v_m5_native.py (reports 2026-10-14-g116 / g119):
//   V        an M5 bar whose body crosses the EMA200 (open on one side, close on the other)
//   return   within 6 bars after V, price closes outside the V high-low range, then a bar closes back inside it
//            (the first inside close after V decides; one group per return bar, the earliest V claims it)
//   filter   at V: EMA21/55/100/200 spread <= InpEmaSpreadAtr x ATR14 AND (V tick volume >= InpVVolRatio x mean
//            of the 20 bars before, OR return-bar tick volume >= InpRVolRatio x its 20-bar mean)
//   entry    at the open after the return bar: a BUY and a SELL; stops at open -/+ (InpStopAtr + 0.1) x ATR14
//   resolve  the first leg stopped is lost; an ADD opens in the survivor's direction at that price with the
//            survivor's stop; target = survivor entry + InpTargetR x R (R = survivor entry to its stop);
//            at +1R both stops go to their entries (break-even); everything closes after 288 bars (24 h)
// SHADOW: virtual legs on bid/ask ticks, CSV log, panel. LIVE: real orders (hedging accounts only), same logic.
// ATR = Wilder ATR14, EMA = standard EMA, both over InpHistoryBars closed M5 bars (as the research).

#include <Trade/Trade.mqh>
#include "Tester/TesterPanel.mqh"

enum VHT_Mode { VHT_SHADOW=0, VHT_LIVE=1 };

input VHT_Mode InpMode          = VHT_SHADOW; // SHADOW: virtual trades only (log + panel) | LIVE: real orders (hedging account)
input double   InpStopAtr       = 1.5;   // Stop distance from the entry, x ATR14 M5 (+0.1 ATR buffer)
input double   InpTargetR       = 5.0;   // Target, x the survivor's risk
input bool     InpBreakEven     = true;  // Stops to entry at +1R
input bool     InpFilter        = true;  // G119 filter: bundled EMAs + volume (false = every V return, research baseline)
input double   InpEmaSpreadAtr  = 0.91;  // EMA21..200 spread limit (x ATR14)
input double   InpVVolRatio     = 1.26;  // V-bar tick volume vs the 20 bars before
input double   InpRVolRatio     = 1.17;  // Return-bar tick volume vs its 20 bars before
input double   InpRiskPercent   = 0.5;   // LIVE: risk per leg, % of balance (SHADOW logs the same notional)
input int      InpMaxGroups     = 10;    // Open groups at once (overlapping signals each get a group)
input int      InpHistoryBars   = 3000;  // M5 bars for EMA / ATR
input bool     InpLogCsv        = true;  // Write groups to MQL5\Files\VHedge_<symbol>_<magic>.csv
input long     InpMagic         = 116119;
input bool     InpPanel         = true;
input bool     InpVerbose       = false;

#define VHT_RET_BARS 6
#define VHT_CAP_BARS 288
#define VHT_MAX 32

struct VLeg
  {
   bool   open;
   int    dir;
   double entry, sl, lots;
   ulong  ticket;           // LIVE
   double exit_px;
  };

struct VGroup
  {
   bool     active;
   int      id;
   datetime v_time, sig_time, opened;
   int      phase;           // 1 hedge, 2 survivor (+ add)
   int      dir;             // survivor direction in phase 2
   double   atr, unit;       // ATR at the return bar, U = gap between the two stops
   double   surv_entry, surv_sl, R, tp;
   bool     be_done;
   double   best;
   VLeg     leg[3];          // 0 buy, 1 sell, 2 add
   double   realized;        // price units, sum over closed legs
   string   note;
  };

CTrade   g_trade;
VGroup   g_g[VHT_MAX];
int      g_next_id=1;
datetime g_last_bar=0;
int      g_csv=INVALID_HANDLE;
// stats
int      g_groups=0, g_wins=0, g_both=0, g_filtered=0, g_timeouts=0;
double   g_sumU=0.0;
// panel view
string   g_pv_ctx="", g_pv_last="", g_pv_pending[];

// ---------------------------------------------------------------------------------------------------------
double Pt(const double v) { return NormalizeDouble(v,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }

void EmaArr(const MqlRates &r[],const int n,const int p,double &out[])
  {
   ArrayResize(out,n);
   const double k=2.0/(p+1.0);
   out[0]=r[0].close;
   for(int i=1;i<n;i++) out[i]=r[i].close*k+out[i-1]*(1.0-k);
  }

void AtrWilder(const MqlRates &r[],const int n,double &out[])
  {
   ArrayResize(out,n);
   out[0]=r[0].high-r[0].low;
   for(int i=1;i<n;i++)
     {
      const double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-r[i-1].close),MathAbs(r[i].low-r[i-1].close)));
      out[i]=out[i-1]+(tr-out[i-1])/14.0;
     }
  }

double VolMean20(const MqlRates &r[],const int i)
  {
   if(i<20) return 0.0;
   double s=0.0;
   for(int k=i-20;k<i;k++) s+=(double)r[k].tick_volume;
   return s/20.0;
  }

bool BodyCross(const MqlRates &r[],const double &e[],const int i)
  { return (r[i].open<e[i] && r[i].close>e[i]) || (r[i].open>e[i] && r[i].close<e[i]); }

double LotsFor(const double dist)
  {
   if(dist<=0.0) return 0.0;
   double loss=0.0;
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(!OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,1.0,ask,ask-dist,loss) || loss>=0.0) return 0.0;
   const double money=AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPercent/100.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin) v=vmin;                                   // no protection limits by design (user): minimum volume
   return MathMin(v,vmax);
  }

void CsvOpen()
  {
   if(!InpLogCsv) return;
   const string name=StringFormat("VHedge_%s_%I64d.csv",_Symbol,InpMagic);
   const bool exists=FileIsExist(name);
   g_csv=FileOpen(name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(g_csv==INVALID_HANDLE) return;
   FileSeek(g_csv,0,SEEK_END);
   if(!exists) FileWriteString(g_csv,"mode;group;v_time;signal_time;open_time;close_time;side;U;atr;buy_entry;sell_entry;buy_sl;sell_sl;add_entry;tp;result_price;result_U;note\r\n");
  }

void CsvGroup(const VGroup &g,const datetime closed)
  {
   if(g_csv==INVALID_HANDLE) return;
   const string line=StringFormat("%s;%d;%s;%s;%s;%s;%s;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.4f;%s\r\n",
                                  InpMode==VHT_LIVE ? "LIVE" : "SHADOW",g.id,TimeToString(g.v_time),TimeToString(g.sig_time),
                                  TimeToString(g.opened),TimeToString(closed),g.dir==1 ? "BUY" : (g.dir==-1 ? "SELL" : "NONE"),
                                  g.unit,g.atr,g.leg[0].entry,g.leg[1].entry,g.leg[0].sl,g.leg[1].sl,g.leg[2].entry,g.tp,
                                  g.realized,g.unit>0.0 ? g.realized/g.unit : 0.0,g.note);
   FileWriteString(g_csv,line);
   FileFlush(g_csv);
  }

// ---------------------------------------------------------------------------------------------------------
// signal: called once per closed M5 bar
// ---------------------------------------------------------------------------------------------------------
void ScanSignal()
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,PERIOD_M5,1,InpHistoryBars,r);
   if(n<400) { g_pv_ctx="chưa đủ nến M5"; return; }
   double e21[],e55[],e100[],e200[],atr[];
   EmaArr(r,n,21,e21); EmaArr(r,n,55,e55); EmaArr(r,n,100,e100); EmaArr(r,n,200,e200); AtrWilder(r,n,atr);
   const int j=n-1;                                     // the bar that just closed
   const double sp_now=MathMax(e21[j],MathMax(e55[j],MathMax(e100[j],e200[j])))-MathMin(e21[j],MathMin(e55[j],MathMin(e100[j],e200[j])));
   g_pv_ctx=StringFormat("giá %s %s EMA200 %s | EMA21-200 bó %.2f ATR (lọc <= %.2f) %s | ATR14 %s",PnlPx(r[j].close),
                         r[j].close>e200[j] ? "TRÊN" : "DƯỚI",PnlPx(e200[j]),sp_now/atr[j],InpEmaSpreadAtr,PnlMark(sp_now/atr[j]<=InpEmaSpreadAtr),
                         PnlPx(atr[j]));
   // pending V candles (for the panel) and the return check for bar j
   ArrayResize(g_pv_pending,0);
   int found_v=-1;
   for(int v=MathMax(1,j-VHT_RET_BARS);v<j;v++)
     {
      if(!BodyCross(r,e200,v)) continue;
      bool left=false, decided=false, hit=false;
      for(int q=v+1;q<=j && !decided;q++)
        {
         const bool inside=(r[q].close>=r[v].low && r[q].close<=r[v].high);
         if(inside) { decided=true; hit=(left && q==j); }
         else left=true;
        }
      if(!decided)
        {
         const int k=ArraySize(g_pv_pending); ArrayResize(g_pv_pending,k+1);
         g_pv_pending[k]=StringFormat("V %s %s [%s - %s] | %s, còn %d nến",PnlHm(r[v].time),r[v].close>e200[v] ? "phá LÊN" : "phá XUỐNG",
                                      PnlPx(r[v].low),PnlPx(r[v].high),left ? "đã ra ngoài, chờ đóng lại bên trong" : "chưa ra khỏi vùng",
                                      VHT_RET_BARS-(j-v));
        }
      if(hit && found_v<0) found_v=v;
     }
   // one V before (j-6) can still have a hit at j only if it is within RET_BARS: covered by the loop bounds
   if(found_v<0) return;
   const int v=found_v;
   const double spread=(MathMax(e21[v],MathMax(e55[v],MathMax(e100[v],e200[v])))-MathMin(e21[v],MathMin(e55[v],MathMin(e100[v],e200[v]))))/atr[v];
   const double vm=VolMean20(r,v), jm=VolMean20(r,j);
   const double vv=(vm>0.0 ? r[v].tick_volume/vm : 0.0), rv=(jm>0.0 ? r[j].tick_volume/jm : 0.0);
   const bool f_ema=spread<=InpEmaSpreadAtr, f_vol=(vv>=InpVVolRatio || rv>=InpRVolRatio);
   const string desc=StringFormat("V %s, quay về %s | EMA bó %.2f %s | vol V %.2fx, vol quay về %.2fx %s",PnlHm(r[v].time),
                                  PnlHm(r[j].time),spread,PnlMark(f_ema),vv,rv,PnlMark(f_vol));
   if(InpFilter && !(f_ema && f_vol))
     {
      g_filtered++;
      g_pv_last="BỎ (không qua lọc): "+desc;
      return;
     }
   g_pv_last="VÀO HEDGE: "+desc;
   OpenGroup(r[v].time,r[j].time,atr[j]);
  }

// ---------------------------------------------------------------------------------------------------------
// groups
// ---------------------------------------------------------------------------------------------------------
int ActiveCount() { int c=0; for(int i=0;i<VHT_MAX;i++) if(g_g[i].active) c++; return c; }

bool LiveOpen(const int dir,const double lots,const double sl,const double tp,const string tag,ulong &ticket)
  {
   const bool ok=(dir==1 ? g_trade.Buy(lots,_Symbol,0.0,Pt(sl),tp>0.0 ? Pt(tp) : 0.0,tag)
                         : g_trade.Sell(lots,_Symbol,0.0,Pt(sl),tp>0.0 ? Pt(tp) : 0.0,tag));
   if(!ok || (g_trade.ResultRetcode()!=TRADE_RETCODE_DONE && g_trade.ResultRetcode()!=TRADE_RETCODE_PLACED))
     {
      PrintFormat("VHedge: %s order failed (%u %s)",dir==1 ? "BUY" : "SELL",g_trade.ResultRetcode(),g_trade.ResultRetcodeDescription());
      return false;
     }
   ticket=0;
   const ulong deal=g_trade.ResultDeal();
   if(deal>0 && HistoryDealSelect(deal)) ticket=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   if(ticket==0) ticket=g_trade.ResultOrder();
   return true;
  }

void OpenGroup(const datetime vt,const datetime st,const double atr)
  {
   if(ActiveCount()>=InpMaxGroups) { g_pv_last+=" — đã đủ nhóm mở"; return; }
   int s=-1;
   for(int i=0;i<VHT_MAX;i++) if(!g_g[i].active) { s=i; break; }
   if(s<0) return;
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const double mid=bid;                                  // research: the open (bid) of the bar after the return
   const double gap=(InpStopAtr+0.1)*atr;
   VGroup G;
   G.active=true; G.id=g_next_id++; G.v_time=vt; G.sig_time=st; G.opened=TimeCurrent(); G.phase=1; G.dir=0;
   G.atr=atr; G.unit=2.0*gap; G.surv_entry=0; G.surv_sl=0; G.R=0; G.tp=0; G.be_done=false; G.best=0; G.realized=0; G.note="";
   for(int k=0;k<3;k++) { G.leg[k].open=false; G.leg[k].ticket=0; G.leg[k].exit_px=0; G.leg[k].lots=0; G.leg[k].entry=0; G.leg[k].sl=0; G.leg[k].dir=0; }
   G.leg[0].dir=1;  G.leg[0].entry=ask; G.leg[0].sl=mid-gap;
   G.leg[1].dir=-1; G.leg[1].entry=bid; G.leg[1].sl=mid+gap;
   const double lots=LotsFor(gap);
   G.leg[0].lots=lots; G.leg[1].lots=lots;
   if(InpMode==VHT_LIVE)
     {
      ulong tb=0, ts=0;
      if(!LiveOpen(1,lots,G.leg[0].sl,0.0,StringFormat("VH%d B",G.id),tb)) return;
      if(!LiveOpen(-1,lots,G.leg[1].sl,0.0,StringFormat("VH%d S",G.id),ts)) { g_trade.PositionClose(tb); return; }
      G.leg[0].ticket=tb; G.leg[1].ticket=ts;
      if(PositionSelectByTicket(tb)) G.leg[0].entry=PositionGetDouble(POSITION_PRICE_OPEN);
      if(PositionSelectByTicket(ts)) G.leg[1].entry=PositionGetDouble(POSITION_PRICE_OPEN);
     }
   G.leg[0].open=true; G.leg[1].open=true;
   g_g[s]=G;
   g_groups++;
   if(InpVerbose) PrintFormat("VHedge group %d opened: buy %.2f sl %.2f | sell %.2f sl %.2f",G.id,G.leg[0].entry,G.leg[0].sl,G.leg[1].entry,G.leg[1].sl);
  }

void CloseLeg(VGroup &G,const int k,const double px,const bool at_broker)
  {
   if(!G.leg[k].open) return;
   if(InpMode==VHT_LIVE && !at_broker && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
      g_trade.PositionClose(G.leg[k].ticket);
   G.leg[k].open=false;
   G.leg[k].exit_px=px;
   G.realized+=G.leg[k].dir*(px-G.leg[k].entry);
  }

void FinishGroup(VGroup &G,const string note)
  {
   if(note!="") G.note=note;
   CsvGroup(G,TimeCurrent());
   g_sumU+=(G.unit>0.0 ? G.realized/G.unit : 0.0);
   if(G.realized>0.0) g_wins++;
   G.active=false;
  }

// LIVE: was this leg closed at the broker? returns its close price
bool LiveClosed(const VLeg &L,double &px)
  {
   if(L.ticket==0) return false;
   if(PositionSelectByTicket(L.ticket)) return false;
   px=L.sl;
   if(HistorySelectByPosition(L.ticket))
      for(int i=HistoryDealsTotal()-1;i>=0;i--)
        {
         const ulong d=HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_OUT) { px=HistoryDealGetDouble(d,DEAL_PRICE); break; }
        }
   return true;
  }

void ManageGroup(VGroup &G)
  {
   const double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   const bool cap=((long)(TimeCurrent()-G.opened)>=(long)VHT_CAP_BARS*300);
   if(G.phase==1)
     {
      bool bs=false, ss=false; double bpx=G.leg[0].sl, spx=G.leg[1].sl;
      if(InpMode==VHT_LIVE) { bs=LiveClosed(G.leg[0],bpx); ss=LiveClosed(G.leg[1],spx); }
      else { bs=(bid<=G.leg[0].sl); ss=(ask>=G.leg[1].sl); }
      if(bs && ss)
        {
         CloseLeg(G,0,bpx,true); CloseLeg(G,1,spx,true); g_both++;
         FinishGroup(G,"cả hai chân bị cắt");
         return;
        }
      if(bs || ss)
        {
         const int d=(bs ? -1 : 1);
         const int lost=(bs ? 0 : 1), surv=(bs ? 1 : 0);
         CloseLeg(G,lost,bs ? bpx : spx,true);
         G.phase=2; G.dir=d;
         G.surv_entry=G.leg[surv].entry; G.surv_sl=G.leg[surv].sl;
         G.R=d*(G.surv_entry-G.surv_sl);
         G.tp=G.surv_entry+d*InpTargetR*G.R;
         G.best=(d==1 ? bid : ask);
         // add at the break, survivor's stop
         VLeg A; A.open=false; A.ticket=0; A.exit_px=0; A.dir=d; A.sl=G.surv_sl; A.lots=G.leg[surv].lots;
         A.entry=(d==1 ? ask : bid);
         if(d*(A.entry-A.sl)>0.0)
           {
            if(InpMode==VHT_LIVE)
              {
               ulong t=0;
               if(LiveOpen(d,A.lots,A.sl,G.tp,StringFormat("VH%d A",G.id),t))
                 { A.ticket=t; if(PositionSelectByTicket(t)) A.entry=PositionGetDouble(POSITION_PRICE_OPEN); A.open=true; }
               if(G.leg[surv].ticket!=0 && PositionSelectByTicket(G.leg[surv].ticket))
                  g_trade.PositionModify(G.leg[surv].ticket,Pt(G.leg[surv].sl),Pt(G.tp));
              }
            else A.open=true;
           }
         G.leg[2]=A;
         return;
        }
      if(cap)
        {
         CloseLeg(G,0,bid,false); CloseLeg(G,1,ask,false); g_timeouts++;
         FinishGroup(G,"hết 24 giờ, chưa phân định");
        }
      return;
     }
   // phase 2: survivor (+ add)
   const int d=G.dir;
   const double fav=(d==1 ? bid : ask);
   for(int k=0;k<3;k++)
     {
      if(!G.leg[k].open) continue;
      double px=G.leg[k].sl;
      bool hit=false;
      if(InpMode==VHT_LIVE) hit=LiveClosed(G.leg[k],px);
      else hit=(d==1 ? bid<=G.leg[k].sl : ask>=G.leg[k].sl);
      if(hit) CloseLeg(G,k,px,true);
     }
   bool any=false;
   for(int k=0;k<3;k++) if(G.leg[k].open) any=true;
   if(!any) { FinishGroup(G,"dừng ở stop"); return; }
   if((d==1 && bid>=G.tp) || (d==-1 && ask<=G.tp))
     {
      for(int k=0;k<3;k++) CloseLeg(G,k,G.tp,false);   // LIVE: the broker TP usually closed them already
      FinishGroup(G,StringFormat("chạm TP %.1fR",InpTargetR));
      return;
     }
   G.best=(d==1 ? MathMax(G.best,fav) : MathMin(G.best,fav));
   if(InpBreakEven && !G.be_done && d*(G.best-G.surv_entry)>=G.R)
     {
      G.be_done=true;
      for(int k=0;k<3;k++)
        {
         if(!G.leg[k].open || d*(G.leg[k].entry-G.leg[k].sl)<=0.0) continue;
         G.leg[k].sl=G.leg[k].entry;
         if(InpMode==VHT_LIVE && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
            g_trade.PositionModify(G.leg[k].ticket,Pt(G.leg[k].sl),Pt(G.tp));
        }
     }
   if(cap)
     {
      for(int k=0;k<3;k++) CloseLeg(G,k,d==1 ? bid : ask,false);
      g_timeouts++;
      FinishGroup(G,"hết 24 giờ");
     }
  }

// ---------------------------------------------------------------------------------------------------------
// panel
// ---------------------------------------------------------------------------------------------------------
void VPanel()
  {
   if(!InpPanel || !PnlActive()) return;
   PnlBegin();
   PnlAdd(StringFormat("VHedgeTester  %s  %s | %s | stop %.1f ATR, TP %.0fR%s | lọc %s",_Symbol,PnlTime(TimeCurrent()),
                        InpMode==VHT_LIVE ? "LIVE (lệnh thật)" : "SHADOW (lệnh ảo)",InpStopAtr,InpTargetR,InpBreakEven ? ", BE +1R" : "",
                        InpFilter ? "BẬT" : "TẮT"),InpMode==VHT_LIVE ? PnlWarnColor : PnlHeadColor);
   if(PnlSection("ctx","Bối cảnh M5 : "+g_pv_ctx,true))
     {
      PnlAdd(StringFormat("   lọc: EMA21-200 bó <= %.2f ATR và (vol nến V >= %.2fx hoặc vol nến quay về >= %.2fx TB 20 nến)",
                          InpEmaSpreadAtr,InpVVolRatio,InpRVolRatio));
     }
   const int np=ArraySize(g_pv_pending);
   if(PnlSection("pend",StringFormat("Nến V chờ quay về: %d",np),true))
      for(int i=0;i<np;i++) PnlAdd("   "+g_pv_pending[i]);
   if(g_pv_last!="") PnlAdd("Tín hiệu gần nhất: "+g_pv_last,StringFind(g_pv_last,"VÀO")==0 ? PnlOkColor : clrNONE);
   const double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   int shown=0;
   for(int i=0;i<VHT_MAX;i++)
     {
      if(!g_g[i].active) continue;
      shown++;
      VGroup G=g_g[i];
      string head;
      if(G.phase==1)
         head=StringFormat("Nhóm %d (hedge, chờ phân định) | MUA %s SL %s | BÁN %s SL %s",G.id,PnlPx(G.leg[0].entry),PnlPx(G.leg[0].sl),
                           PnlPx(G.leg[1].entry),PnlPx(G.leg[1].sl));
      else
        {
         const double px=(G.dir==1 ? bid : ask);
         const double r=(G.R>0.0 ? G.dir*(px-G.surv_entry)/G.R : 0.0);
         head=StringFormat("Nhóm %d %s | đang %s | TP %s%s",G.id,PnlDir(G.dir),PnlR(r),PnlPx(G.tp),G.be_done ? " | đã BE" : "");
        }
      if(PnlSection("g"+IntegerToString(G.id),head,false))
        {
         for(int k=0;k<3;k++)
           {
            if(G.leg[k].entry==0.0) continue;
            PnlAdd(StringFormat("   %s %s vào %s SL %s %s",k==2 ? "BỒI" : (k==0 ? "MUA " : "BÁN "),PnlDir(G.leg[k].dir),PnlPx(G.leg[k].entry),
                                PnlPx(G.leg[k].sl),G.leg[k].open ? "đang mở" : "đã đóng "+PnlPx(G.leg[k].exit_px)));
           }
         PnlAdd(StringFormat("   V %s, tín hiệu %s, mở %s, ATR %s",PnlHm(G.v_time),PnlHm(G.sig_time),PnlHm(G.opened),PnlPx(G.atr)));
        }
     }
   if(shown==0) PnlAdd("Nhóm đang mở: không có");
   PnlAdd(StringFormat("Thống kê    : %d nhóm | thắng %d | cả hai chân bị cắt %d | hết giờ %d | tổng %+.2fU | bỏ vì lọc %d",
                       g_groups,g_wins,g_both,g_timeouts,g_sumU,g_filtered));
   if(InpMode==VHT_SHADOW) PnlAdd("SHADOW: không gửi lệnh. Nhật ký nhóm trong MQL5\\Files\\VHedge_<symbol>_<magic>.csv");
   PnlFlush();
  }

// ---------------------------------------------------------------------------------------------------------
int OnInit()
  {
   if(_Period!=PERIOD_M5) Print("VHedgeTester: rules use M5 bars whatever the chart period");
   if(InpMode==VHT_LIVE && (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("VHedgeTester: LIVE needs a hedging account (buy and sell at once). Use SHADOW on this account.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(30);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   for(int i=0;i<VHT_MAX;i++) g_g[i].active=false;
   if(InpMode==VHT_LIVE)
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         const ulong t=PositionGetTicket(i);
         if(t>0 && PositionGetInteger(POSITION_MAGIC)==InpMagic)
            PrintFormat("VHedgeTester: position %I64u from a previous run keeps its broker SL/TP; it is not managed again (no add / break-even)",t);
        }
   CsvOpen();
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   for(int i=0;i<VHT_MAX;i++) if(g_g[i].active) ManageGroup(g_g[i]);
   const datetime b=iTime(_Symbol,PERIOD_M5,0);
   if(b!=0 && b!=g_last_bar)
     {
      const bool first=(g_last_bar==0);
      g_last_bar=b;
      if(first) Print("VHedgeTester: started; a signal on the last closed bar opens on this tick");
      ScanSignal();
      VPanel();
     }
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && PnlOnClick(sparam)) VPanel();
  }

void OnDeinit(const int reason)
  {
   PnlClear();
   if(g_csv!=INVALID_HANDLE) FileClose(g_csv);
   PrintFormat("VHedgeTester: groups %d, wins %d, both legs stopped %d, time-outs %d, total %+.2f U, filtered %d",
               g_groups,g_wins,g_both,g_timeouts,g_sumU,g_filtered);
  }
