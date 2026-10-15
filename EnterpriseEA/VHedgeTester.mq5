#property strict
#property version   "2.000"
#property description "VHedge v2 (G119/G120): M5 EMA200 V candle, return into its range, hedge, add at the break, 5R target, BE +1R. Profiles G119 and BIGV side by side; optional partial / swing trail / time exit / M30 confirmation. SHADOW or LIVE."

// Rules = research/long/g116_v_hedge.py, g119_v_m5_native.py, g120_vhedge_v2.py (reports 2026-10-14/15):
//   V        an M5 bar whose body crosses the EMA200 (open on one side, close on the other)
//   return   within 6 bars after V, price closes outside the V high-low range, then a bar closes back inside it
//            (the first inside close after V decides; the earliest V claims a return bar)
//   profiles at V (each enabled profile opens its own group; ATR14 = Wilder):
//            G119  EMA21..200 spread <= 0.91 ATR AND (V volume >= 1.26x OR return volume >= 1.17x the 20-bar mean)
//                  stop (1.5 + 0.1) ATR
//            BIGV  V range >= 1.38 ATR AND EMA spread <= 0.91 ATR, stop (1.0 + 0.1) ATR
//            M30 confirmation (option): last closed M30 bar has EMA21/55/100 fanned against the V break, ADX14 < 25
//            and its EMA200 48-bar slope against the break (G120: no gain, off by default)
//   entry    at the open after the return bar: a BUY and a SELL with stops at the open -/+ the profile gap
//   resolve  the first leg stopped is lost; an ADD opens in the survivor's direction with the survivor's stop;
//            target = survivor entry + 5R; BE at +1R; everything closes after 288 bars (24 h)
//   exits    options (G120, off by default): close 50% at +2R | swing trail from +2R | close after 2 h without +1R
// SHADOW: virtual legs on bid/ask ticks, CSV log, panel. LIVE: real orders (hedging accounts only).

#include <Trade/Trade.mqh>
#include "Tester/TesterPanel.mqh"

enum VHT_Mode { VHT_SHADOW=0, VHT_LIVE=1 };
enum VHT_RiskBase { VHT_RISK_INITIAL=0, VHT_RISK_BALANCE=1 };

input VHT_Mode InpMode          = VHT_SHADOW; // SHADOW: virtual trades only (log + panel) | LIVE: real orders (hedging account)
input bool     InpProfG119      = true;  // Profile G119: bundled EMAs + volume, stop 1.5 ATR
input bool     InpProfBigV      = true;  // Profile BIGV: large V candle + bundled EMAs, stop 1.0 ATR
input bool     InpProfAll       = false; // Profile ALL: every V return, no filter (research baseline), stop 1.5 ATR
input double   InpStopG119      = 1.5;   // G119 stop, x ATR14 (+0.1 ATR)
input double   InpStopBigV      = 1.0;   // BIGV stop, x ATR14 (+0.1 ATR)
input double   InpEmaSpreadAtr  = 0.91;  // EMA21..200 spread limit (x ATR14)
input double   InpVVolRatio     = 1.26;  // G119: V-bar tick volume vs the 20 bars before
input double   InpRVolRatio     = 1.17;  // G119: return-bar tick volume vs its 20 bars before
input double   InpBigVSizeAtr   = 1.38;  // BIGV: V range limit (x ATR14)
input bool     InpM30Confirm    = false; // Also require the M30 context (G120: fewer trades, no gain)
input double   InpTargetR       = 5.0;   // Target, x the survivor's risk
input bool     InpBreakEven     = true;  // Stops to entry at +1R
input bool     InpPartial2R     = false; // Close 50% of every leg at +2R (G120: smoother, ~1/3 less profit)
input bool     InpSwingTrail    = false; // From +2R, stops follow the last confirmed M5 swing (G120: worse)
input bool     InpTimeExit      = false; // Close after 24 bars (2 h) from the resolution without +1R (G120: no effect)
input double   InpRiskPercent   = 0.5;   // LIVE: risk per leg, % (S07Tester uses 1.5 per trade; no protection limits: minimum volume if smaller)
input VHT_RiskBase InpRiskBase  = VHT_RISK_INITIAL; // as S07Tester: INITIAL = % of min(equity, initial deposit) | BALANCE = % of equity (compounding)
input int      InpMaxGroups     = 10;    // Open groups at once
input int      InpHistoryBars   = 3000;  // M5 bars for EMA / ATR
input bool     InpLogCsv        = true;  // Write groups to MQL5\Files\VHedge_<symbol>_<magic>.csv
input long     InpMagic         = 116119;
input bool     InpPanel         = true;
input bool     InpVerbose       = false;

#define VHT_RET_BARS 6
#define VHT_CAP_BARS 288
#define VHT_TIME_BARS 24
#define VHT_MAX 32
#define VHT_NPROF 3

string PROF_NAME[VHT_NPROF]={"G119","BIGV","ALL"};

struct VLeg
  {
   bool   open;
   int    dir;
   double entry, sl, lots, size;    // size: 1.0, 0.5 after the partial close (shadow accounting)
   ulong  ticket;
   double exit_px;
  };

struct VGroup
  {
   bool     active;
   int      id, prof;
   datetime v_time, sig_time, opened, resolved;
   int      phase;
   int      dir;
   double   atr, unit;
   double   surv_entry, surv_sl, R, tp;
   bool     be_done, partial_done;
   double   best;
   VLeg     leg[3];
   double   realized;
   string   note;
  };

CTrade   g_trade;
double   g_initial_capital=0.0;
VGroup   g_g[VHT_MAX];
int      g_next_id=1;
datetime g_last_bar=0;
int      g_csv=INVALID_HANDLE;
int      g_groups[VHT_NPROF], g_wins[VHT_NPROF], g_both=0, g_timeouts=0, g_filtered=0;
double   g_sumU[VHT_NPROF];
double   g_sw_lo=0.0, g_sw_hi=0.0;          // last confirmed M5 swing (2 bars each side)
string   g_pv_ctx="", g_pv_last="", g_pv_m30="", g_pv_pending[];

// ---------------------------------------------------------------------------------------------------------
double Pt(const double v) { return NormalizeDouble(v,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }

void EmaArr(const MqlRates &r[],const int n,const int p,double &out[])
  {
   ArrayResize(out,n);
   const double k=2.0/(p+1.0);
   out[0]=r[0].close;
   for(int i=1;i<n;i++) out[i]=r[i].close*k+out[i-1]*(1.0-k);
  }

// Wilder DMI as research g97_forming_bar.dmi(): rma = ewm(alpha 1/14) seeded with the first value
void Dmi(const MqlRates &r[],const int n,double &adx[],double &atr[])
  {
   ArrayResize(adx,n); ArrayResize(atr,n);
   double tr_s=0, p_s=0, m_s=0, dx_s=0;
   for(int i=0;i<n;i++)
     {
      const double pc=(i==0 ? r[0].close : r[i-1].close);
      const double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-pc),MathAbs(r[i].low-pc)));
      const double up=(i==0 ? 0.0 : r[i].high-r[i-1].high), dn=(i==0 ? 0.0 : r[i-1].low-r[i].low);
      const double pdm=(up>dn && up>0.0 ? up : 0.0), mdm=(dn>up && dn>0.0 ? dn : 0.0);
      if(i==0) { tr_s=tr; p_s=pdm; m_s=mdm; }
      else { tr_s+=(tr-tr_s)/14.0; p_s+=(pdm-p_s)/14.0; m_s+=(mdm-m_s)/14.0; }
      const double pdi=(tr_s>0 ? 100.0*p_s/tr_s : 0.0), mdi=(tr_s>0 ? 100.0*m_s/tr_s : 0.0);
      const double dx=100.0*MathAbs(pdi-mdi)/MathMax(pdi+mdi,1e-9);
      dx_s=(i==0 ? dx : dx_s+(dx-dx_s)/14.0);
      adx[i]=dx_s; atr[i]=tr_s;
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
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double basis=(InpRiskBase==VHT_RISK_BALANCE ? equity : MathMin(equity,g_initial_capital));
   const double money=basis*InpRiskPercent/100.0;
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double v=MathFloor(money/(-loss)/step+1e-9)*step;
   if(v<vmin) v=vmin;
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
   if(!exists) FileWriteString(g_csv,"mode;profile;group;v_time;signal_time;open_time;close_time;side;U;atr;buy_entry;sell_entry;buy_sl;sell_sl;add_entry;tp;result_price;result_U;note\r\n");
  }

void CsvGroup(const VGroup &g,const datetime closed)
  {
   if(g_csv==INVALID_HANDLE) return;
   FileWriteString(g_csv,StringFormat("%s;%s;%d;%s;%s;%s;%s;%s;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.4f;%s\r\n",
                   InpMode==VHT_LIVE ? "LIVE" : "SHADOW",PROF_NAME[g.prof],g.id,TimeToString(g.v_time),TimeToString(g.sig_time),
                   TimeToString(g.opened),TimeToString(closed),g.dir==1 ? "BUY" : (g.dir==-1 ? "SELL" : "NONE"),g.unit,g.atr,
                   g.leg[0].entry,g.leg[1].entry,g.leg[0].sl,g.leg[1].sl,g.leg[2].entry,g.tp,g.realized,
                   g.unit>0.0 ? g.realized/g.unit : 0.0,g.note));
   FileFlush(g_csv);
  }

// M30 context for a V break in direction vd closed at vclose (G120 M30C)
bool M30Context(const int vd,const datetime vclose,string &txt)
  {
   MqlRates h[];
   ArraySetAsSeries(h,false);
   const int n=CopyRates(_Symbol,PERIOD_M30,1,1500,h);
   txt="M30: chưa đủ nến";
   if(n<300) return false;
   int k=n-1;
   while(k>=0 && (long)h[k].time+1800>(long)vclose) k--;
   if(k<60) return false;
   double e21[],e55[],e100[],e200[],adx[],atr[];
   EmaArr(h,n,21,e21); EmaArr(h,n,55,e55); EmaArr(h,n,100,e100); EmaArr(h,n,200,e200); Dmi(h,n,adx,atr);
   const int fan=(e21[k]>e55[k] && e55[k]>e100[k]) ? 1 : ((e21[k]<e55[k] && e55[k]<e100[k]) ? -1 : 0);
   const double slope=(e200[k]-e200[k-48])/atr[k];
   const bool ok_fan=(fan==-vd), ok_adx=(adx[k]<25.0), ok_slope=((slope>0 ? 1 : (slope<0 ? -1 : 0))==-vd);
   txt=StringFormat("M30: EMA xòe ngược chiều phá %s | ADX %.1f < 25 %s | dốc EMA200 %.2f ngược chiều %s",PnlMark(ok_fan),adx[k],
                    PnlMark(ok_adx),slope,PnlMark(ok_slope));
   return ok_fan && ok_adx && ok_slope;
  }

// ---------------------------------------------------------------------------------------------------------
// signal: once per closed M5 bar
// ---------------------------------------------------------------------------------------------------------
void ScanSignal()
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,PERIOD_M5,1,InpHistoryBars,r);
   if(n<400) { g_pv_ctx="chưa đủ nến M5"; return; }
   double e21[],e55[],e100[],e200[],adx[],atr[];
   EmaArr(r,n,21,e21); EmaArr(r,n,55,e55); EmaArr(r,n,100,e100); EmaArr(r,n,200,e200); Dmi(r,n,adx,atr);
   const int j=n-1;
   // last confirmed swings (for the swing trail)
   for(int k=j-2;k>=2;k--)
      if(r[k].low<=MathMin(MathMin(r[k-2].low,r[k-1].low),MathMin(r[k+1].low,r[k+2].low))) { g_sw_lo=r[k].low; break; }
   for(int k=j-2;k>=2;k--)
      if(r[k].high>=MathMax(MathMax(r[k-2].high,r[k-1].high),MathMax(r[k+1].high,r[k+2].high))) { g_sw_hi=r[k].high; break; }
   const double spj=MathMax(e21[j],MathMax(e55[j],MathMax(e100[j],e200[j])))-MathMin(e21[j],MathMin(e55[j],MathMin(e100[j],e200[j])));
   g_pv_ctx=StringFormat("giá %s %s EMA200 %s | EMA bó %.2f ATR (<= %.2f) %s | ATR14 %s",PnlPx(r[j].close),
                         r[j].close>e200[j] ? "TRÊN" : "DƯỚI",PnlPx(e200[j]),spj/atr[j],InpEmaSpreadAtr,PnlMark(spj/atr[j]<=InpEmaSpreadAtr),
                         PnlPx(atr[j]));
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
         g_pv_pending[k]=StringFormat("V %s %s [%s - %s] %.2f ATR | %s, còn %d nến",PnlHm(r[v].time),r[v].close>e200[v] ? "phá LÊN" : "phá XUỐNG",
                                      PnlPx(r[v].low),PnlPx(r[v].high),(r[v].high-r[v].low)/atr[v],
                                      left ? "đã ra ngoài, chờ đóng lại bên trong" : "chưa ra khỏi vùng",VHT_RET_BARS-(j-v));
        }
      if(hit && found_v<0) found_v=v;
     }
   if(found_v<0) return;
   const int v=found_v;
   const int vd=(r[v].close>e200[v] ? 1 : -1);
   const double spread=(MathMax(e21[v],MathMax(e55[v],MathMax(e100[v],e200[v])))-MathMin(e21[v],MathMin(e55[v],MathMin(e100[v],e200[v]))))/atr[v];
   const double vm=VolMean20(r,v), jm=VolMean20(r,j);
   const double vv=(vm>0.0 ? r[v].tick_volume/vm : 0.0), rv=(jm>0.0 ? r[j].tick_volume/jm : 0.0);
   const double vsize=(r[v].high-r[v].low)/atr[v];
   const bool f_ema=(spread<=InpEmaSpreadAtr), f_vol=(vv>=InpVVolRatio || rv>=InpRVolRatio), f_big=(vsize>=InpBigVSizeAtr);
   bool m30=true;
   if(InpM30Confirm) m30=M30Context(vd,(datetime)((long)r[v].time+300),g_pv_m30);
   const bool p_g119=(InpProfG119 && f_ema && f_vol && m30), p_bigv=(InpProfBigV && f_ema && f_big && m30), p_all=InpProfAll;
   const string desc=StringFormat("V %s, quay về %s | EMA bó %.2f %s | vol V %.2fx / quay về %.2fx %s | V %.2f ATR %s%s",
                                  PnlHm(r[v].time),PnlHm(r[j].time),spread,PnlMark(f_ema),vv,rv,PnlMark(f_vol),vsize,PnlMark(f_big),
                                  InpM30Confirm ? " | M30 "+PnlMark(m30) : "");
   if(!p_g119 && !p_bigv && !p_all) { g_filtered++; g_pv_last="BỎ (không hồ sơ nào đạt): "+desc; return; }
   string who="";
   if(p_g119) { OpenGroup(0,r[v].time,r[j].time,atr[j],InpStopG119); who+="G119 "; }
   if(p_bigv) { OpenGroup(1,r[v].time,r[j].time,atr[j],InpStopBigV); who+="BIGV "; }
   if(p_all)  { OpenGroup(2,r[v].time,r[j].time,atr[j],InpStopG119); who+="ALL "; }
   g_pv_last="VÀO HEDGE ("+who+"): "+desc;
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

void OpenGroup(const int prof,const datetime vt,const datetime st,const double atr,const double stop_atr)
  {
   if(ActiveCount()>=InpMaxGroups) { g_pv_last+=" — đã đủ nhóm mở"; return; }
   int s=-1;
   for(int i=0;i<VHT_MAX;i++) if(!g_g[i].active) { s=i; break; }
   if(s<0) return;
   const double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   const double gap=(stop_atr+0.1)*atr;
   VGroup G;
   G.active=true; G.id=g_next_id++; G.prof=prof; G.v_time=vt; G.sig_time=st; G.opened=TimeCurrent(); G.resolved=0;
   G.phase=1; G.dir=0; G.atr=atr; G.unit=2.0*gap; G.surv_entry=0; G.surv_sl=0; G.R=0; G.tp=0;
   G.be_done=false; G.partial_done=false; G.best=0; G.realized=0; G.note="";
   for(int k=0;k<3;k++) { G.leg[k].open=false; G.leg[k].ticket=0; G.leg[k].exit_px=0; G.leg[k].lots=0; G.leg[k].size=1.0;
                          G.leg[k].entry=0; G.leg[k].sl=0; G.leg[k].dir=0; }
   G.leg[0].dir=1;  G.leg[0].entry=ask; G.leg[0].sl=bid-gap;
   G.leg[1].dir=-1; G.leg[1].entry=bid; G.leg[1].sl=bid+gap;
   const double lots=LotsFor(gap);
   G.leg[0].lots=lots; G.leg[1].lots=lots;
   if(InpMode==VHT_LIVE)
     {
      ulong tb=0, ts=0;
      if(!LiveOpen(1,lots,G.leg[0].sl,0.0,StringFormat("VH%d %s B",G.id,PROF_NAME[prof]),tb)) return;
      if(!LiveOpen(-1,lots,G.leg[1].sl,0.0,StringFormat("VH%d %s S",G.id,PROF_NAME[prof]),ts)) { g_trade.PositionClose(tb); return; }
      G.leg[0].ticket=tb; G.leg[1].ticket=ts;
      if(PositionSelectByTicket(tb)) G.leg[0].entry=PositionGetDouble(POSITION_PRICE_OPEN);
      if(PositionSelectByTicket(ts)) G.leg[1].entry=PositionGetDouble(POSITION_PRICE_OPEN);
     }
   G.leg[0].open=true; G.leg[1].open=true;
   g_g[s]=G;
   g_groups[prof]++;
   if(InpVerbose) PrintFormat("VHedge %s group %d: buy %.2f sl %.2f | sell %.2f sl %.2f",PROF_NAME[prof],G.id,G.leg[0].entry,
                              G.leg[0].sl,G.leg[1].entry,G.leg[1].sl);
  }

void CloseLeg(VGroup &G,const int k,const double px,const bool at_broker)
  {
   if(!G.leg[k].open) return;
   if(InpMode==VHT_LIVE && !at_broker && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
      g_trade.PositionClose(G.leg[k].ticket);
   G.leg[k].open=false;
   G.leg[k].exit_px=px;
   G.realized+=G.leg[k].size*G.leg[k].dir*(px-G.leg[k].entry);
  }

void FinishGroup(VGroup &G,const string note)
  {
   if(note!="") G.note=note;
   CsvGroup(G,TimeCurrent());
   g_sumU[G.prof]+=(G.unit>0.0 ? G.realized/G.unit : 0.0);
   if(G.realized>0.0) g_wins[G.prof]++;
   G.active=false;
  }

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

void SetStop(VGroup &G,const int k,const double sl)
  {
   G.leg[k].sl=sl;
   if(InpMode==VHT_LIVE && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
      g_trade.PositionModify(G.leg[k].ticket,Pt(sl),G.tp>0.0 ? Pt(G.tp) : 0.0);
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
      if(bs && ss) { CloseLeg(G,0,bpx,true); CloseLeg(G,1,spx,true); g_both++; FinishGroup(G,"cả hai chân bị cắt"); return; }
      if(bs || ss)
        {
         const int d=(bs ? -1 : 1);
         const int lost=(bs ? 0 : 1), surv=(bs ? 1 : 0);
         CloseLeg(G,lost,bs ? bpx : spx,true);
         G.phase=2; G.dir=d; G.resolved=TimeCurrent();
         G.surv_entry=G.leg[surv].entry; G.surv_sl=G.leg[surv].sl;
         G.R=d*(G.surv_entry-G.surv_sl);
         G.tp=G.surv_entry+d*InpTargetR*G.R;
         G.best=(d==1 ? bid : ask);
         VLeg A; A.open=false; A.ticket=0; A.exit_px=0; A.dir=d; A.sl=G.surv_sl; A.lots=G.leg[surv].lots; A.size=1.0;
         A.entry=(d==1 ? ask : bid);
         if(d*(A.entry-A.sl)>0.0)
           {
            if(InpMode==VHT_LIVE)
              {
               ulong t=0;
               if(LiveOpen(d,A.lots,A.sl,G.tp,StringFormat("VH%d %s A",G.id,PROF_NAME[G.prof]),t))
                 { A.ticket=t; if(PositionSelectByTicket(t)) A.entry=PositionGetDouble(POSITION_PRICE_OPEN); A.open=true; }
               if(G.leg[surv].ticket!=0 && PositionSelectByTicket(G.leg[surv].ticket))
                  g_trade.PositionModify(G.leg[surv].ticket,Pt(G.leg[surv].sl),Pt(G.tp));
              }
            else A.open=true;
           }
         G.leg[2]=A;
         return;
        }
      if(cap) { CloseLeg(G,0,bid,false); CloseLeg(G,1,ask,false); g_timeouts++; FinishGroup(G,"hết 24 giờ, chưa phân định"); }
      return;
     }
   const int d=G.dir;
   const double fav=(d==1 ? bid : ask);
   for(int k=0;k<3;k++)
     {
      if(!G.leg[k].open) continue;
      double px=G.leg[k].sl;
      bool hit=(InpMode==VHT_LIVE ? LiveClosed(G.leg[k],px) : (d==1 ? bid<=G.leg[k].sl : ask>=G.leg[k].sl));
      if(hit) CloseLeg(G,k,px,true);
     }
   bool any=false;
   for(int k=0;k<3;k++) if(G.leg[k].open) any=true;
   if(!any) { FinishGroup(G,"dừng ở stop"); return; }
   if((d==1 && bid>=G.tp) || (d==-1 && ask<=G.tp))
     {
      for(int k=0;k<3;k++) CloseLeg(G,k,G.tp,false);
      FinishGroup(G,StringFormat("chạm TP %.1fR",InpTargetR));
      return;
     }
   G.best=(d==1 ? MathMax(G.best,fav) : MathMin(G.best,fav));
   const double rb=(G.R>0.0 ? d*(G.best-G.surv_entry)/G.R : 0.0);
   if(InpPartial2R && !G.partial_done && rb>=2.0)
     {
      G.partial_done=true;
      const double lvl=G.surv_entry+d*2.0*G.R;
      for(int k=0;k<3;k++)
        {
         if(!G.leg[k].open) continue;
         G.realized+=0.5*G.leg[k].size*d*(lvl-G.leg[k].entry);
         G.leg[k].size*=0.5;
         if(InpMode==VHT_LIVE && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
           {
            const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
            const double half=MathFloor(G.leg[k].lots*0.5/step+1e-9)*step;
            if(half>=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN) && g_trade.PositionClosePartial(G.leg[k].ticket,half))
               G.leg[k].lots-=half;
           }
        }
     }
   if(InpBreakEven && !G.be_done && rb>=1.0)
     {
      G.be_done=true;
      for(int k=0;k<3;k++) if(G.leg[k].open && d*(G.leg[k].entry-G.leg[k].sl)>0.0) SetStop(G,k,G.leg[k].entry);
     }
   if(InpSwingTrail && rb>=2.0)
     {
      const double sw=(d==1 ? g_sw_lo : g_sw_hi);
      if(sw>0.0 && d*(sw-G.surv_entry)>0.0)
         for(int k=0;k<3;k++) if(G.leg[k].open && d*(sw-G.leg[k].sl)>0.0) SetStop(G,k,sw);
     }
   if(InpTimeExit && rb<1.0 && (long)(TimeCurrent()-G.resolved)>=(long)VHT_TIME_BARS*300)
     {
      for(int k=0;k<3;k++) CloseLeg(G,k,d==1 ? bid : ask,false);
      FinishGroup(G,"2 giờ chưa đạt +1R");
      return;
     }
   if(cap) { for(int k=0;k<3;k++) CloseLeg(G,k,d==1 ? bid : ask,false); g_timeouts++; FinishGroup(G,"hết 24 giờ"); }
  }

// ---------------------------------------------------------------------------------------------------------
// panel
// ---------------------------------------------------------------------------------------------------------
void VPanel()
  {
   if(!InpPanel || !PnlActive()) return;
   PnlBegin();
   string profs="";
   if(InpProfG119) profs+="G119 ";
   if(InpProfBigV) profs+="BIGV ";
   if(InpProfAll) profs+="ALL ";
   string exits=StringFormat("TP %.0fR",InpTargetR);
   if(InpBreakEven) exits+=", BE +1R";
   if(InpPartial2R) exits+=", chốt 50% @2R";
   if(InpSwingTrail) exits+=", trail swing";
   if(InpTimeExit) exits+=", 2h";
   PnlAdd(StringFormat("VHedgeTester v2  %s  %s | %s | hồ sơ: %s| %s%s",_Symbol,PnlTime(TimeCurrent()),
                       InpMode==VHT_LIVE ? "LIVE (lệnh thật)" : "SHADOW (lệnh ảo)",profs,exits,InpM30Confirm ? " | xác nhận M30" : ""),
          InpMode==VHT_LIVE ? PnlWarnColor : PnlHeadColor);
   if(PnlSection("ctx","Bối cảnh M5 : "+g_pv_ctx,true))
     {
      PnlAdd(StringFormat("   G119: EMA bó <= %.2f ATR và (vol V >= %.2fx hoặc vol quay về >= %.2fx), stop %.1f ATR",InpEmaSpreadAtr,
                          InpVVolRatio,InpRVolRatio,InpStopG119));
      PnlAdd(StringFormat("   BIGV: EMA bó <= %.2f ATR và nến V >= %.2f ATR, stop %.1f ATR",InpEmaSpreadAtr,InpBigVSizeAtr,InpStopBigV));
      if(InpM30Confirm && g_pv_m30!="") PnlAdd("   "+g_pv_m30);
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
         head=StringFormat("Nhóm %d %s (hedge, chờ phân định) | MUA %s SL %s | BÁN %s SL %s",G.id,PROF_NAME[G.prof],
                           PnlPx(G.leg[0].entry),PnlPx(G.leg[0].sl),PnlPx(G.leg[1].entry),PnlPx(G.leg[1].sl));
      else
        {
         const double px=(G.dir==1 ? bid : ask);
         const double r=(G.R>0.0 ? G.dir*(px-G.surv_entry)/G.R : 0.0);
         head=StringFormat("Nhóm %d %s %s | đang %s | TP %s%s%s",G.id,PROF_NAME[G.prof],PnlDir(G.dir),PnlR(r),PnlPx(G.tp),
                           G.be_done ? " | đã BE" : "",G.partial_done ? " | đã chốt 50%" : "");
        }
      if(PnlSection("g"+IntegerToString(G.id),head,false))
        {
         for(int k=0;k<3;k++)
           {
            if(G.leg[k].entry==0.0) continue;
            PnlAdd(StringFormat("   %s vào %s SL %s %s",k==2 ? "BỒI " : (k==0 ? "MUA " : "BÁN "),PnlPx(G.leg[k].entry),
                                PnlPx(G.leg[k].sl),G.leg[k].open ? "đang mở" : "đã đóng "+PnlPx(G.leg[k].exit_px)));
           }
         PnlAdd(StringFormat("   V %s, tín hiệu %s, mở %s, ATR %s",PnlHm(G.v_time),PnlHm(G.sig_time),PnlHm(G.opened),PnlPx(G.atr)));
        }
     }
   if(shown==0) PnlAdd("Nhóm đang mở: không có");
   for(int p=0;p<VHT_NPROF;p++)
      if(g_groups[p]>0)
         PnlAdd(StringFormat("Thống kê %-4s: %d nhóm | thắng %d | tổng %+.2fU",PROF_NAME[p],g_groups[p],g_wins[p],g_sumU[p]));
   PnlAdd(StringFormat("Chung       : cả hai chân bị cắt %d | hết giờ %d | V quay về bị bỏ %d",g_both,g_timeouts,g_filtered));
   if(InpMode==VHT_SHADOW) PnlAdd("SHADOW: không gửi lệnh. Nhật ký trong MQL5\\Files\\VHedge_<symbol>_<magic>.csv");
   PnlFlush();
  }

// ---------------------------------------------------------------------------------------------------------
int OnInit()
  {
   if(InpMode==VHT_LIVE && (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      Print("VHedgeTester: LIVE needs a hedging account (buy and sell at once). Use SHADOW on this account.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_initial_capital=AccountInfoDouble(ACCOUNT_BALANCE);
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(30);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   for(int i=0;i<VHT_MAX;i++) g_g[i].active=false;
   for(int p=0;p<VHT_NPROF;p++) { g_groups[p]=0; g_wins[p]=0; g_sumU[p]=0.0; }
   if(InpMode==VHT_LIVE)
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         const ulong t=PositionGetTicket(i);
         if(t>0 && PositionGetInteger(POSITION_MAGIC)==InpMagic)
            PrintFormat("VHedgeTester: position %I64u from a previous run keeps its broker SL/TP; it is not managed again",t);
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
      g_last_bar=b;
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
   for(int p=0;p<VHT_NPROF;p++)
      if(g_groups[p]>0) PrintFormat("VHedgeTester %s: groups %d, wins %d, total %+.2f U",PROF_NAME[p],g_groups[p],g_wins[p],g_sumU[p]);
   PrintFormat("VHedgeTester: both legs stopped %d, time-outs %d, V returns skipped %d",g_both,g_timeouts,g_filtered);
  }
