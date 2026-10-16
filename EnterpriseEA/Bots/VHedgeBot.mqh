#ifndef ENTERPRISE_EA_BOT_VHEDGE_MQH
#define ENTERPRISE_EA_BOT_VHEDGE_MQH

// VHedge G119/G120 inside EnterpriseEA (bots host). Port of VHedgeTester.mq5 v2 with the same rules:
//   V        an M5 bar whose body crosses the EMA200
//   return   within 6 bars after V, price closes outside the V range, then a bar closes back inside it
//   profiles G119 (EMA21..200 spread <= 0.91 ATR and V volume >= 1.26x or return volume >= 1.17x, stop 1.5 ATR)
//            BIGV (V range >= 1.38 ATR and spread <= 0.91 ATR, stop 1.0 ATR); optional M30 confirmation
//   entry    BUY and SELL at the open after the return, stops at the open -/+ (stop + 0.1) ATR
//   resolve  the first stopped leg is lost; an ADD opens in the survivor's direction with the survivor's stop;
//            target survivor entry + 5R, BE at +1R, everything closed after 288 M5 bars
// Host changes: every new group asks the Portfolio Guard; a group's add is a risk increase (no Active
// check, still armed / pause / daily loss / open risk); groups are saved to current/bots/vhedge_groups.txt
// and restored on restart (live legs re-bound by ticket); LIVE needs a hedging account, else SHADOW.

#include <Trade/Trade.mqh>
#include "../Tester/TesterPanel.mqh"
#include "PortfolioGuard.mqh"

#define VHB_RET_BARS 6
#define VHB_CAP_BARS 288
#define VHB_TIME_BARS 24
#define VHB_MAX 32
#define VHB_NPROF 3

struct VHedgeBotParams
  {
   EEA_BotModeInput mode;
   bool   prof_g119, prof_bigv, prof_all;
   double stop_g119, stop_bigv;
   double ema_spread_atr, v_vol_ratio, r_vol_ratio, bigv_size_atr;
   bool   m30_confirm;
   double target_r;
   bool   break_even, partial_2r, swing_trail, time_exit;
   double risk_percent;           // per leg, % of the guard capital (INITIAL)
   int    max_groups;
   int    history_bars;
   bool   log_csv;
   long   magic;
   bool   news_guard;
  };

void VHedgeBotParamsDefaults(VHedgeBotParams &p)
  {
   p.mode=BOT_SHADOW; p.prof_g119=true; p.prof_bigv=false; p.prof_all=false; p.stop_g119=1.5; p.stop_bigv=1.0;
   p.ema_spread_atr=0.91; p.v_vol_ratio=1.26; p.r_vol_ratio=1.17; p.bigv_size_atr=1.38; p.m30_confirm=false;
   p.target_r=5.0; p.break_even=true; p.partial_2r=false; p.swing_trail=false; p.time_exit=false;
   p.risk_percent=0.75; p.max_groups=10; p.history_bars=3000; p.log_csv=true; p.magic=116119; p.news_guard=false;
  }

struct VHBLeg
  {
   bool   open;
   int    dir;
   double entry, sl, lots, size;
   ulong  ticket;
   double exit_px;
  };

struct VHBGroup
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
   VHBLeg   leg[3];
   double   realized;
   bool     live;                 // legs are real orders
   string   note;
  };

class CVHedgeBot
  {
public:
   VHedgeBotParams p;
   string   sym;
   string   root;
   bool     live_ok;              // LIVE allowed on this account (hedging)
   string   mode_reason;
   CTrade   trade;
   VHBGroup g[VHB_MAX];
   int      next_id;
   datetime last_bar;
   int      csv;
   int      groups[VHB_NPROF], wins[VHB_NPROF], both, timeouts, filtered;
   double   sumU[VHB_NPROF];
   double   sw_lo, sw_hi;
   string   pv_ctx, pv_last, pv_m30, pv_block;
   string   pv_pending[];
   string   prof_name[VHB_NPROF];
   int      day_key;
   double   day_realized_money;
   bool     dirty;

                     CVHedgeBot() { next_id=1; last_bar=0; csv=INVALID_HANDLE; dirty=false; }

   bool     IsLive() const { return p.mode==BOT_LIVE && live_ok; }
   string   ModeText() const { return p.mode==BOT_OFF ? "OFF" : (IsLive() ? "LIVE" : "SHADOW"); }
   double   Px(const double v) const { return NormalizeDouble(v,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS)); }
   string   PxT(const double v) const { return DoubleToString(v,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS)); }

   // ------------------------------------------------------------------------------------------------
   void Init(const VHedgeBotParams &params,const string symbol,const string data_root)
     {
      p=params; sym=symbol; root=data_root;
      prof_name[0]="G119"; prof_name[1]="BIGV"; prof_name[2]="ALL";
      live_ok=true; mode_reason="";
      if(p.mode==BOT_LIVE &&
         (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
        { live_ok=false; mode_reason="VHEDGE_LIVE_NEEDS_HEDGING_ACCOUNT"; }
      trade.SetExpertMagicNumber(p.magic);
      trade.SetDeviationInPoints(30);
      trade.SetTypeFillingBySymbol(sym);
      for(int i=0;i<VHB_MAX;i++) g[i].active=false;
      for(int k=0;k<VHB_NPROF;k++) { groups[k]=0; wins[k]=0; sumU[k]=0.0; }
      both=0; timeouts=0; filtered=0; sw_lo=0.0; sw_hi=0.0;
      pv_ctx=""; pv_last=""; pv_m30=""; pv_block=""; ArrayResize(pv_pending,0);
      day_key=(int)(TimeTradeServer()/86400); day_realized_money=0.0;
      Load();
      CsvOpen();
     }

   void Deinit()
     {
      Save();
      if(csv!=INVALID_HANDLE) { FileClose(csv); csv=INVALID_HANDLE; }
     }

   // ------------------------------------------------------------------------------------------------ indicators
   static void EmaArr(const MqlRates &r[],const int n,const int per,double &out[])
     {
      ArrayResize(out,n);
      const double k=2.0/(per+1.0);
      out[0]=r[0].close;
      for(int i=1;i<n;i++) out[i]=r[i].close*k+out[i-1]*(1.0-k);
     }

   static void Dmi(const MqlRates &r[],const int n,double &adx[],double &atr[])
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

   static double VolMean20(const MqlRates &r[],const int i)
     {
      if(i<20) return 0.0;
      double s=0.0;
      for(int k=i-20;k<i;k++) s+=(double)r[k].tick_volume;
      return s/20.0;
     }

   static bool BodyCross(const MqlRates &r[],const double &e[],const int i)
     { return (r[i].open<e[i] && r[i].close>e[i]) || (r[i].open>e[i] && r[i].close<e[i]); }

   // Volume for a stop distance and the money lost at that stop.
   double LotsFor(const double dist,double &risk_money)
     {
      risk_money=0.0;
      if(dist<=0.0) return 0.0;
      double loss=0.0;
      const double ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      if(!OrderCalcProfit(ORDER_TYPE_BUY,sym,1.0,ask,ask-dist,loss) || loss>=0.0) return 0.0;
      const double capital=(g_bot_guard.capital>0.0 ? g_bot_guard.capital : AccountInfoDouble(ACCOUNT_BALANCE));
      const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      const double money=MathMin(equity,capital)*p.risk_percent/100.0;
      const double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
      const double vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
      double v=MathFloor(money/(-loss)/step+1e-9)*step;
      if(v<vmin) v=vmin;
      v=MathMin(v,vmax);
      risk_money=v*(-loss);
      return v;
     }

   // ------------------------------------------------------------------------------------------------ csv log
   void CsvOpen()
     {
      if(!p.log_csv || csv!=INVALID_HANDLE) return;
      const string name=StringFormat("VHedge_%s_%I64d.csv",sym,p.magic);
      const bool exists=FileIsExist(name);
      csv=FileOpen(name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      if(csv==INVALID_HANDLE) return;
      FileSeek(csv,0,SEEK_END);
      if(!exists)
         FileWriteString(csv,"mode;profile;group;v_time;signal_time;open_time;close_time;side;U;atr;buy_entry;sell_entry;buy_sl;sell_sl;add_entry;tp;result_price;result_U;note\r\n");
     }

   void CsvGroup(const VHBGroup &G,const datetime closed)
     {
      if(csv==INVALID_HANDLE) return;
      FileWriteString(csv,StringFormat("%s;%s;%d;%s;%s;%s;%s;%s;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.5f;%.4f;%s\r\n",
                      G.live ? "LIVE" : "SHADOW",prof_name[G.prof],G.id,TimeToString(G.v_time),TimeToString(G.sig_time),
                      TimeToString(G.opened),TimeToString(closed),G.dir==1 ? "BUY" : (G.dir==-1 ? "SELL" : "NONE"),G.unit,G.atr,
                      G.leg[0].entry,G.leg[1].entry,G.leg[0].sl,G.leg[1].sl,G.leg[2].entry,G.tp,G.realized,
                      G.unit>0.0 ? G.realized/G.unit : 0.0,G.note));
      FileFlush(csv);
     }

   // ------------------------------------------------------------------------------------------------ persistence
   string StatePath() const { return root+"/current/bots/vhedge_groups.txt"; }

   void Save()
     {
      if(root=="") return;
      string s="vhedge-groups-v1|"+IntegerToString(next_id)+"|"+sym+"|"+IntegerToString(p.magic)+"\r\n";
      for(int i=0;i<VHB_MAX;i++)
        {
         if(!g[i].active) continue;
         const VHBGroup G=g[i];
         string note=G.note; StringReplace(note,"|","/");
         s+=StringFormat("G|%d|%d|%I64d|%I64d|%I64d|%I64d|%d|%d|%.8f|%.8f|%.8f|%.8f|%.8f|%.8f|%d|%d|%.8f|%.8f|%d|%s",
                         G.id,G.prof,(long)G.v_time,(long)G.sig_time,(long)G.opened,(long)G.resolved,G.phase,G.dir,G.atr,G.unit,
                         G.surv_entry,G.surv_sl,G.R,G.tp,G.be_done ? 1 : 0,G.partial_done ? 1 : 0,G.best,G.realized,
                         G.live ? 1 : 0,note);
         for(int k=0;k<3;k++)
            s+=StringFormat("|%d|%d|%.8f|%.8f|%.8f|%.8f|%I64u|%.8f",G.leg[k].open ? 1 : 0,G.leg[k].dir,G.leg[k].entry,
                            G.leg[k].sl,G.leg[k].lots,G.leg[k].size,G.leg[k].ticket,G.leg[k].exit_px);
         s+="\r\n";
        }
      FolderCreate(root+"/current/bots",0);
      EEA_WriteAtomicText(StatePath(),s);
      dirty=false;
     }

   void Load()
     {
      string text;
      if(root=="" || !FileIsExist(StatePath(),0) || !EEA_PendingReadText(StatePath(),text)) return;
      string lines[];
      const int n=StringSplit(text,'\n',lines);
      if(n<1) return;
      string head[];
      StringTrimRight(lines[0]);
      if(StringSplit(lines[0],'|',head)<4 || head[0]!="vhedge-groups-v1" || head[2]!=sym || StringToInteger(head[3])!=p.magic)
        { PrintFormat("VHedgeBot: saved groups ignored (other symbol/magic or format)"); return; }
      next_id=(int)StringToInteger(head[1]);
      int slot=0;
      for(int l=1;l<n && slot<VHB_MAX;l++)
        {
         string line=lines[l];
         StringTrimRight(line);
         string f[];
         if(StringSplit(line,'|',f)<45 || f[0]!="G") continue;
         VHBGroup G;
         G.active=true; G.id=(int)StringToInteger(f[1]); G.prof=(int)StringToInteger(f[2]);
         G.v_time=(datetime)StringToInteger(f[3]); G.sig_time=(datetime)StringToInteger(f[4]);
         G.opened=(datetime)StringToInteger(f[5]); G.resolved=(datetime)StringToInteger(f[6]);
         G.phase=(int)StringToInteger(f[7]); G.dir=(int)StringToInteger(f[8]); G.atr=StringToDouble(f[9]);
         G.unit=StringToDouble(f[10]); G.surv_entry=StringToDouble(f[11]); G.surv_sl=StringToDouble(f[12]);
         G.R=StringToDouble(f[13]); G.tp=StringToDouble(f[14]); G.be_done=(f[15]=="1"); G.partial_done=(f[16]=="1");
         G.best=StringToDouble(f[17]); G.realized=StringToDouble(f[18]); G.live=(f[19]=="1"); G.note=f[20];
         for(int k=0;k<3;k++)
           {
            const int b=21+8*k;
            G.leg[k].open=(f[b]=="1"); G.leg[k].dir=(int)StringToInteger(f[b+1]); G.leg[k].entry=StringToDouble(f[b+2]);
            G.leg[k].sl=StringToDouble(f[b+3]); G.leg[k].lots=StringToDouble(f[b+4]); G.leg[k].size=StringToDouble(f[b+5]);
            G.leg[k].ticket=(ulong)StringToInteger(f[b+6]); G.leg[k].exit_px=StringToDouble(f[b+7]);
           }
         if(G.prof<0 || G.prof>=VHB_NPROF) continue;
         g[slot++]=G;
        }
      PrintFormat("VHedgeBot: %d open group(s) restored from %s",slot,StatePath());
     }

   // ------------------------------------------------------------------------------------------------ M30 option
   bool M30Context(const int vd,const datetime vclose,string &txt)
     {
      MqlRates h[];
      ArraySetAsSeries(h,false);
      const int n=CopyRates(sym,PERIOD_M30,1,1500,h);
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

   // ------------------------------------------------------------------------------------------------ signal
   void ScanSignal()
     {
      MqlRates r[];
      ArraySetAsSeries(r,false);
      const int n=CopyRates(sym,PERIOD_M5,1,p.history_bars,r);
      if(n<400) { pv_ctx="chưa đủ nến M5"; return; }
      double e21[],e55[],e100[],e200[],adx[],atr[];
      EmaArr(r,n,21,e21); EmaArr(r,n,55,e55); EmaArr(r,n,100,e100); EmaArr(r,n,200,e200); Dmi(r,n,adx,atr);
      const int j=n-1;
      for(int k=j-2;k>=2;k--)
         if(r[k].low<=MathMin(MathMin(r[k-2].low,r[k-1].low),MathMin(r[k+1].low,r[k+2].low))) { sw_lo=r[k].low; break; }
      for(int k=j-2;k>=2;k--)
         if(r[k].high>=MathMax(MathMax(r[k-2].high,r[k-1].high),MathMax(r[k+1].high,r[k+2].high))) { sw_hi=r[k].high; break; }
      const double spj=MathMax(e21[j],MathMax(e55[j],MathMax(e100[j],e200[j])))-MathMin(e21[j],MathMin(e55[j],MathMin(e100[j],e200[j])));
      pv_ctx=StringFormat("giá %s %s EMA200 %s | EMA bó %.2f ATR (<= %.2f) %s | ATR14 %s",PxT(r[j].close),
                          r[j].close>e200[j] ? "TRÊN" : "DƯỚI",PxT(e200[j]),spj/atr[j],p.ema_spread_atr,
                          PnlMark(spj/atr[j]<=p.ema_spread_atr),PxT(atr[j]));
      ArrayResize(pv_pending,0);
      int found_v=-1;
      for(int v=MathMax(1,j-VHB_RET_BARS);v<j;v++)
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
            const int k=ArraySize(pv_pending); ArrayResize(pv_pending,k+1);
            pv_pending[k]=StringFormat("V %s %s [%s - %s] %.2f ATR | %s, còn %d nến",PnlHm(r[v].time),
                                       r[v].close>e200[v] ? "phá LÊN" : "phá XUỐNG",PxT(r[v].low),PxT(r[v].high),
                                       (r[v].high-r[v].low)/atr[v],left ? "đã ra ngoài, chờ đóng lại bên trong" : "chưa ra khỏi vùng",
                                       VHB_RET_BARS-(j-v));
           }
         if(hit && found_v<0) found_v=v;
        }
      if(found_v<0) return;
      const int v=found_v;
      const int vd=(r[v].close>e200[v] ? 1 : -1);
      const double spread=(MathMax(e21[v],MathMax(e55[v],MathMax(e100[v],e200[v])))-
                           MathMin(e21[v],MathMin(e55[v],MathMin(e100[v],e200[v]))))/atr[v];
      const double vm=VolMean20(r,v), jm=VolMean20(r,j);
      const double vv=(vm>0.0 ? r[v].tick_volume/vm : 0.0), rv=(jm>0.0 ? r[j].tick_volume/jm : 0.0);
      const double vsize=(r[v].high-r[v].low)/atr[v];
      const bool f_ema=(spread<=p.ema_spread_atr), f_vol=(vv>=p.v_vol_ratio || rv>=p.r_vol_ratio), f_big=(vsize>=p.bigv_size_atr);
      bool m30=true;
      if(p.m30_confirm) m30=M30Context(vd,(datetime)((long)r[v].time+300),pv_m30);
      const bool p_g119=(p.prof_g119 && f_ema && f_vol && m30), p_bigv=(p.prof_bigv && f_ema && f_big && m30), p_all=p.prof_all;
      const string desc=StringFormat("V %s, quay về %s | EMA bó %.2f %s | vol V %.2fx / quay về %.2fx %s | V %.2f ATR %s%s",
                                     PnlHm(r[v].time),PnlHm(r[j].time),spread,PnlMark(f_ema),vv,rv,PnlMark(f_vol),vsize,
                                     PnlMark(f_big),p.m30_confirm ? " | M30 "+PnlMark(m30) : "");
      if(!p_g119 && !p_bigv && !p_all) { filtered++; pv_last="BỎ (không hồ sơ nào đạt): "+desc; return; }
      string who="";
      if(p_g119 && OpenGroup(0,r[v].time,r[j].time,atr[j],p.stop_g119)) who+="G119 ";
      if(p_bigv && OpenGroup(1,r[v].time,r[j].time,atr[j],p.stop_bigv)) who+="BIGV ";
      if(p_all && OpenGroup(2,r[v].time,r[j].time,atr[j],p.stop_g119)) who+="ALL ";
      pv_last=(who!="" ? "VÀO HEDGE ("+who+"): " : "KHÔNG VÀO ("+pv_block+"): ")+desc;
     }

   // ------------------------------------------------------------------------------------------------ groups
   int ActiveCount() const { int c=0; for(int i=0;i<VHB_MAX;i++) if(g[i].active) c++; return c; }

   bool LiveOpen(const int dir,const double lots,const double sl,const double tp,const string tag,ulong &ticket)
     {
      const bool ok=(dir==1 ? trade.Buy(lots,sym,0.0,Px(sl),tp>0.0 ? Px(tp) : 0.0,tag)
                            : trade.Sell(lots,sym,0.0,Px(sl),tp>0.0 ? Px(tp) : 0.0,tag));
      if(!ok || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_PLACED))
        {
         PrintFormat("VHedgeBot: %s order failed (%u %s)",dir==1 ? "BUY" : "SELL",trade.ResultRetcode(),trade.ResultRetcodeDescription());
         return false;
        }
      ticket=0;
      const ulong deal=trade.ResultDeal();
      if(deal>0 && HistoryDealSelect(deal)) ticket=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      if(ticket==0) ticket=trade.ResultOrder();
      return true;
     }

   bool OpenGroup(const int prof,const datetime vt,const datetime st,const double atr,const double stop_atr)
     {
      pv_block="";
      if(p.mode==BOT_OFF) { pv_block="BOT_OFF"; return false; }
      if(!EEA_BotActive(EEA_BOT_VHEDGE)) { pv_block="BOT_INACTIVE"; return false; }
      if(ActiveCount()>=p.max_groups) { pv_block="đã đủ nhóm mở"; return false; }
      int s=-1;
      for(int i=0;i<VHB_MAX;i++) if(!g[i].active) { s=i; break; }
      if(s<0) { pv_block="hết chỗ nhóm"; return false; }
      const double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      const double gap=(stop_atr+0.1)*atr;
      double leg_risk=0.0;
      const double lots=LotsFor(gap,leg_risk);
      const bool live=IsLive();
      if(live)
        {
         const string reason=EEA_BotGuardCheck(EEA_BOT_VHEDGE,2.0*leg_risk,"SCALP",true,p.news_guard);
         if(reason!="") { pv_block=reason; return false; }
         if(lots<=0.0) { pv_block="VHEDGE_VOLUME_UNAVAILABLE"; return false; }
        }
      VHBGroup G;
      G.active=true; G.id=next_id++; G.prof=prof; G.v_time=vt; G.sig_time=st; G.opened=TimeCurrent(); G.resolved=0;
      G.phase=1; G.dir=0; G.atr=atr; G.unit=2.0*gap; G.surv_entry=0; G.surv_sl=0; G.R=0; G.tp=0;
      G.be_done=false; G.partial_done=false; G.best=0; G.realized=0; G.note=""; G.live=live;
      for(int k=0;k<3;k++) { G.leg[k].open=false; G.leg[k].ticket=0; G.leg[k].exit_px=0; G.leg[k].lots=0; G.leg[k].size=1.0;
                             G.leg[k].entry=0; G.leg[k].sl=0; G.leg[k].dir=0; }
      G.leg[0].dir=1;  G.leg[0].entry=ask; G.leg[0].sl=bid-gap;
      G.leg[1].dir=-1; G.leg[1].entry=bid; G.leg[1].sl=bid+gap;
      G.leg[0].lots=lots; G.leg[1].lots=lots;
      if(live)
        {
         ulong tb=0, ts=0;
         if(!LiveOpen(1,lots,G.leg[0].sl,0.0,StringFormat("VH%d %s B",G.id,prof_name[prof]),tb)) { pv_block="VHEDGE_ORDER_FAILED"; return false; }
         if(!LiveOpen(-1,lots,G.leg[1].sl,0.0,StringFormat("VH%d %s S",G.id,prof_name[prof]),ts))
           { trade.PositionClose(tb); pv_block="VHEDGE_ORDER_FAILED"; return false; }
         G.leg[0].ticket=tb; G.leg[1].ticket=ts;
         if(PositionSelectByTicket(tb)) G.leg[0].entry=PositionGetDouble(POSITION_PRICE_OPEN);
         if(PositionSelectByTicket(ts)) G.leg[1].entry=PositionGetDouble(POSITION_PRICE_OPEN);
        }
      G.leg[0].open=true; G.leg[1].open=true;
      g[s]=G;
      groups[prof]++;
      dirty=true;
      return true;
     }

   void CloseLeg(VHBGroup &G,const int k,const double px,const bool at_broker)
     {
      if(!G.leg[k].open) return;
      if(G.live && !at_broker && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
         trade.PositionClose(G.leg[k].ticket);
      G.leg[k].open=false;
      G.leg[k].exit_px=px;
      const double pnl=G.leg[k].size*G.leg[k].dir*(px-G.leg[k].entry);
      G.realized+=pnl;
      dirty=true;
     }

   void FinishGroup(VHBGroup &G,const string note)
     {
      if(note!="") G.note=note;
      CsvGroup(G,TimeCurrent());
      sumU[G.prof]+=(G.unit>0.0 ? G.realized/G.unit : 0.0);
      if(G.realized>0.0) wins[G.prof]++;
      G.active=false;
      dirty=true;
     }

   bool LiveClosed(const VHBLeg &L,double &px)
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

   void SetStop(VHBGroup &G,const int k,const double sl)
     {
      G.leg[k].sl=sl;
      if(G.live && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
         trade.PositionModify(G.leg[k].ticket,Px(sl),G.tp>0.0 ? Px(G.tp) : 0.0);
      dirty=true;
     }

   void ManageGroup(VHBGroup &G)
     {
      const double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      const bool cap=((long)(TimeCurrent()-G.opened)>=(long)VHB_CAP_BARS*300);
      if(G.phase==1)
        {
         bool bs=false, ss=false; double bpx=G.leg[0].sl, spx=G.leg[1].sl;
         if(G.live) { bs=LiveClosed(G.leg[0],bpx); ss=LiveClosed(G.leg[1],spx); }
         else { bs=(bid<=G.leg[0].sl); ss=(ask>=G.leg[1].sl); }
         if(bs && ss) { CloseLeg(G,0,bpx,true); CloseLeg(G,1,spx,true); both++; FinishGroup(G,"cả hai chân bị cắt"); return; }
         if(bs || ss)
           {
            const int d=(bs ? -1 : 1);
            const int lost=(bs ? 0 : 1), surv=(bs ? 1 : 0);
            CloseLeg(G,lost,bs ? bpx : spx,true);
            G.phase=2; G.dir=d; G.resolved=TimeCurrent();
            G.surv_entry=G.leg[surv].entry; G.surv_sl=G.leg[surv].sl;
            G.R=d*(G.surv_entry-G.surv_sl);
            G.tp=G.surv_entry+d*p.target_r*G.R;
            G.best=(d==1 ? bid : ask);
            VHBLeg A; A.open=false; A.ticket=0; A.exit_px=0; A.dir=d; A.sl=G.surv_sl; A.lots=G.leg[surv].lots; A.size=1.0;
            A.entry=(d==1 ? ask : bid);
            if(d*(A.entry-A.sl)>0.0)
              {
               if(G.live)
                 {
                  // The add is a risk increase of an open group: armed / pause / daily loss / open risk, no Active check.
                  double add_risk=0.0;
                  string reason="";
                  if(!OrderCalcProfit(d==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,A.lots,A.entry,A.sl,add_risk))
                     reason="BOTS_RISK_CALC_FAILED";
                  else reason=EEA_BotGuardCheck(EEA_BOT_VHEDGE,-add_risk,"SCALP",false,false);
                  ulong t=0;
                  if(reason!="") G.note="bồi bị chặn: "+reason;
                  else if(LiveOpen(d,A.lots,A.sl,G.tp,StringFormat("VH%d %s A",G.id,prof_name[G.prof]),t))
                    { A.ticket=t; if(PositionSelectByTicket(t)) A.entry=PositionGetDouble(POSITION_PRICE_OPEN); A.open=true; }
                  if(G.leg[surv].ticket!=0 && PositionSelectByTicket(G.leg[surv].ticket))
                     trade.PositionModify(G.leg[surv].ticket,Px(G.leg[surv].sl),Px(G.tp));
                 }
               else A.open=true;
              }
            G.leg[2]=A;
            dirty=true;
            return;
           }
         if(cap) { CloseLeg(G,0,bid,false); CloseLeg(G,1,ask,false); timeouts++; FinishGroup(G,"hết 24 giờ, chưa phân định"); }
         return;
        }
      const int d=G.dir;
      const double fav=(d==1 ? bid : ask);
      for(int k=0;k<3;k++)
        {
         if(!G.leg[k].open) continue;
         double px=G.leg[k].sl;
         bool hit=(G.live ? LiveClosed(G.leg[k],px) : (d==1 ? bid<=G.leg[k].sl : ask>=G.leg[k].sl));
         if(hit) CloseLeg(G,k,px,true);
        }
      bool any=false;
      for(int k=0;k<3;k++) if(G.leg[k].open) any=true;
      if(!any) { FinishGroup(G,"dừng ở stop"); return; }
      if((d==1 && bid>=G.tp) || (d==-1 && ask<=G.tp))
        {
         for(int k=0;k<3;k++) CloseLeg(G,k,G.tp,false);
         FinishGroup(G,StringFormat("chạm TP %.1fR",p.target_r));
         return;
        }
      G.best=(d==1 ? MathMax(G.best,fav) : MathMin(G.best,fav));
      const double rb=(G.R>0.0 ? d*(G.best-G.surv_entry)/G.R : 0.0);
      if(p.partial_2r && !G.partial_done && rb>=2.0)
        {
         G.partial_done=true;
         const double lvl=G.surv_entry+d*2.0*G.R;
         for(int k=0;k<3;k++)
           {
            if(!G.leg[k].open) continue;
            G.realized+=0.5*G.leg[k].size*d*(lvl-G.leg[k].entry);
            G.leg[k].size*=0.5;
            if(G.live && G.leg[k].ticket!=0 && PositionSelectByTicket(G.leg[k].ticket))
              {
               const double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
               const double half=MathFloor(G.leg[k].lots*0.5/step+1e-9)*step;
               if(half>=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN) && trade.PositionClosePartial(G.leg[k].ticket,half))
                  G.leg[k].lots-=half;
              }
           }
         dirty=true;
        }
      if(p.break_even && !G.be_done && rb>=1.0)
        {
         G.be_done=true;
         for(int k=0;k<3;k++) if(G.leg[k].open && d*(G.leg[k].entry-G.leg[k].sl)>0.0) SetStop(G,k,G.leg[k].entry);
        }
      if(p.swing_trail && rb>=2.0)
        {
         const double sw=(d==1 ? sw_lo : sw_hi);
         if(sw>0.0 && d*(sw-G.surv_entry)>0.0)
            for(int k=0;k<3;k++) if(G.leg[k].open && d*(sw-G.leg[k].sl)>0.0) SetStop(G,k,sw);
        }
      if(p.time_exit && rb<1.0 && (long)(TimeCurrent()-G.resolved)>=(long)VHB_TIME_BARS*300)
        {
         for(int k=0;k<3;k++) CloseLeg(G,k,d==1 ? bid : ask,false);
         FinishGroup(G,"2 giờ chưa đạt +1R");
         return;
        }
      if(cap) { for(int k=0;k<3;k++) CloseLeg(G,k,d==1 ? bid : ask,false); timeouts++; FinishGroup(G,"hết 24 giờ"); }
     }

   // ------------------------------------------------------------------------------------------------ host calls
   void OnTick()
     {
      if(p.mode==BOT_OFF) return;
      for(int i=0;i<VHB_MAX;i++) if(g[i].active) ManageGroup(g[i]);
      const datetime b=iTime(sym,PERIOD_M5,0);
      if(b!=0 && b!=last_bar)
        {
         last_bar=b;
         ScanSignal();
        }
      if(dirty) Save();
     }

   // Open groups, their open legs, and the bot's money at risk (live legs only).
   int OpenGroups() const { return ActiveCount(); }

   int OpenLegs() const
     {
      int c=0;
      for(int i=0;i<VHB_MAX;i++) if(g[i].active) for(int k=0;k<3;k++) if(g[i].leg[k].open) c++;
      return c;
     }

   // Status line and detail lines for the panel / Telegram.
   string StatusText() const
     {
      if(p.mode==BOT_OFF) return "OFF";
      string s=pv_last;
      if(s=="") s="chờ nến V quay về";
      if(mode_reason!="") s=mode_reason+" | "+s;
      return s;
     }

   void Lines(string &out[]) const
     {
      ArrayResize(out,0);
      int n=0;
      ArrayResize(out,n+1); out[n++]="Bối cảnh M5: "+pv_ctx;
      for(int i=0;i<ArraySize(pv_pending);i++) { ArrayResize(out,n+1); out[n++]="  "+pv_pending[i]; }
      const double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      for(int i=0;i<VHB_MAX;i++)
        {
         if(!g[i].active) continue;
         const VHBGroup G=g[i];
         string line;
         if(G.phase==1)
            line=StringFormat("Nhóm %d %s%s hedge | MUA %s SL %s | BÁN %s SL %s",G.id,prof_name[G.prof],G.live ? "" : " (ảo)",
                              PxT(G.leg[0].entry),PxT(G.leg[0].sl),PxT(G.leg[1].entry),PxT(G.leg[1].sl));
         else
           {
            const double px=(G.dir==1 ? bid : ask);
            const double r=(G.R>0.0 ? G.dir*(px-G.surv_entry)/G.R : 0.0);
            line=StringFormat("Nhóm %d %s%s %s | %s | TP %s%s",G.id,prof_name[G.prof],G.live ? "" : " (ảo)",PnlDir(G.dir),PnlR(r),
                              PxT(G.tp),G.be_done ? " | đã BE" : "");
           }
         ArrayResize(out,n+1); out[n++]=line;
        }
      for(int k=0;k<VHB_NPROF;k++)
         if(groups[k]>0)
           { ArrayResize(out,n+1); out[n++]=StringFormat("%s: %d nhóm, thắng %d, tổng %+.2fU (từ lúc chạy)",prof_name[k],groups[k],wins[k],sumU[k]); }
     }
  };

#endif
