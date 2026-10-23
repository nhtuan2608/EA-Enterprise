#ifndef ENTERPRISE_EA_BOT_SHADOW_CANDIDATES_MQH
#define ENTERPRISE_EA_BOT_SHADOW_CANDIDATES_MQH

// G153 SHADOW forward (plan docs/superpowers/plans/2026-10-23-g153b-shadow-forward.md): two research candidates
// run as virtual trades only - no order, no Active flag, no risk. They write the bots journal under their own codes:
//   SQZ  Bollinger squeeze breakout M30 (g139_hybrid.csq): on the closed M30 bar i, hour not 23 / 0, the band width
//        (4 x stdev 20 closes) of bar i-1 in the lowest 20% of its last 120, close beyond the 20-bar high / low, a
//        candle of that colour, close beyond the M30 EMA200 and D1 SMA50 vs SMA200 on that side; cooldown 10 bars.
//        Entry at the next open, stop SMA20 -/+ 0.1 ATR14 (0.5..3 ATR), target 3R, out after 96 bars; one at a time.
//   W1   previous-week breakout (g149_repeating.w1, no target): Monday..Thursday, the first touch of last week's
//        high (ask) / low (bid) on each side, stop at the middle of last week's range, out Friday 21:30 server.
//        A week that opened beyond the level has no breakout on that side.
// The candidate is the G153 gate: only trades with the XauRegime R1 state of the last closed D1 bar on their side
// (close vs EMA50, EMA50 vs 10 days earlier). Trades against it are still followed, as the research did (SQZ: they
// also hold the one-at-a-time slot), and logged apart: ENTRY / EXIT = gated (counted as SHADOW R by the readers),
// SKIP / MANAGE = outside the gate ("r_ungated"). R uses ask for buys, bid for sells, no commission.

#include "BotJournal.mqh"
#include "../Tester/TesterPanel.mqh"

#define SHC_STATE_DOCUMENT "shadow-cand-v1"

struct ShadowCandParams
  {
   bool squeeze;
   bool weekly;
  };

struct ShadowCandTrade
  {
   bool     open;
   int      dir;
   bool     gated;
   double   entry, stop, target;
   datetime opened;          // M30 bar of the entry (SQZ) / entry time (W1)
  };

class CShadowCandidates
  {
public:
   ShadowCandParams p;
   string   sym, root;
   datetime last_m30;
   // SQZ
   ShadowCandTrade sq;
   datetime sq_last_signal;   // M30 bar of the last signal (cooldown)
   // W1
   ShadowCandTrade wk[2];     // [0] buy, [1] sell
   datetime wk_week;          // Monday 00:00 server of the week the levels belong to
   double   wk_high, wk_low;
   bool     wk_done[2];
   bool     wk_scanned;        // this run already looked at the week's first open and closed bars (not saved)
   // results (gated trades only)
   int      n[2];
   double   sum_r[2];

                     CShadowCandidates() { last_m30=0; }

   string   PxT(const double v) const { return DoubleToString(v,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS)); }
   static string Code(const int k) { return k==0 ? "SQZ" : "W1"; }

   void ResetTrade(ShadowCandTrade &t) { t.open=false; t.dir=0; t.gated=false; t.entry=0; t.stop=0; t.target=0; t.opened=0; }

   void Init(const ShadowCandParams &params,const string symbol,const string data_root)
     {
      p=params; sym=symbol; root=data_root; last_m30=0;
      ResetTrade(sq); ResetTrade(wk[0]); ResetTrade(wk[1]);
      sq_last_signal=0; wk_week=0; wk_scanned=false; wk_high=0; wk_low=0; wk_done[0]=false; wk_done[1]=false;
      for(int k=0;k<2;k++) { n[k]=0; sum_r[k]=0.0; }
      Load();
     }

   void Deinit() { Save(); }

   bool Enabled() const { return p.squeeze || p.weekly; }

   // ------------------------------------------------------------------------------------------------ persistence
   string StatePath() const { return root+"/current/bots/shadow_candidates.txt"; }

   string TradeText(const ShadowCandTrade &t) const
     {
      return StringFormat("%d|%d|%d|%.8f|%.8f|%.8f|%I64d",t.open ? 1 : 0,t.dir,t.gated ? 1 : 0,t.entry,t.stop,t.target,(long)t.opened);
     }

   int TradeParse(const string &f[],const int at,ShadowCandTrade &t)
     {
      t.open=(f[at]=="1"); t.dir=(int)StringToInteger(f[at+1]); t.gated=(f[at+2]=="1");
      t.entry=StringToDouble(f[at+3]); t.stop=StringToDouble(f[at+4]); t.target=StringToDouble(f[at+5]);
      t.opened=(datetime)StringToInteger(f[at+6]);
      return at+7;
     }

   void Save()
     {
      if(root=="") return;
      const string s=SHC_STATE_DOCUMENT+"|"+sym+"|"+TradeText(sq)+"|"+IntegerToString((long)sq_last_signal)+"|"+
                     TradeText(wk[0])+"|"+TradeText(wk[1])+"|"+IntegerToString((long)wk_week)+"|"+
                     StringFormat("%.8f|%.8f|%d|%d|%d|%.8f|%d|%.8f",wk_high,wk_low,wk_done[0] ? 1 : 0,wk_done[1] ? 1 : 0,
                                  n[0],sum_r[0],n[1],sum_r[1]);
      FolderCreate(root+"/current/bots",0);
      EEA_WriteAtomicText(StatePath(),s);
     }

   void Load()
     {
      string text;
      if(root=="" || !FileIsExist(StatePath(),0) || !EEA_PendingReadText(StatePath(),text)) return;
      StringTrimRight(text);
      string f[];
      if(StringSplit(text,'|',f)<33 || f[0]!=SHC_STATE_DOCUMENT || f[1]!=sym) return;
      int k=TradeParse(f,2,sq);
      sq_last_signal=(datetime)StringToInteger(f[k++]);
      k=TradeParse(f,k,wk[0]);
      k=TradeParse(f,k,wk[1]);
      wk_week=(datetime)StringToInteger(f[k++]);
      wk_high=StringToDouble(f[k++]); wk_low=StringToDouble(f[k++]);
      wk_done[0]=(f[k++]=="1"); wk_done[1]=(f[k++]=="1");
      n[0]=(int)StringToInteger(f[k++]); sum_r[0]=StringToDouble(f[k++]);
      n[1]=(int)StringToInteger(f[k++]); sum_r[1]=StringToDouble(f[k++]);
     }

   // ------------------------------------------------------------------------------------------------ indicators
   static void Ema(const double &x[],const int cnt,const int period,double &out[])
     {
      ArrayResize(out,cnt);
      const double a=2.0/(period+1.0);
      out[0]=x[0];
      for(int i=1;i<cnt;i++) out[i]=out[i-1]+a*(x[i]-out[i-1]);
     }

   // XauRegime R1 and the D1 SMA50 / SMA200 side, both of the last closed D1 bar.
   bool DayStates(int &regime,int &sma_side)
     {
      regime=0; sma_side=0;
      MqlRates r[];
      ArraySetAsSeries(r,false);
      const int cnt=CopyRates(sym,PERIOD_D1,1,800,r);
      if(cnt<260) return false;
      double c[];
      ArrayResize(c,cnt);
      for(int i=0;i<cnt;i++) c[i]=r[i].close;
      double e[];
      Ema(c,cnt,50,e);
      const int i=cnt-1;
      if(c[i]>e[i] && e[i]>e[i-10]) regime=1;
      else if(c[i]<e[i] && e[i]<e[i-10]) regime=-1;
      double s50=0.0, s200=0.0;
      for(int k=0;k<200;k++) { s200+=c[i-k]; if(k<50) s50+=c[i-k]; }
      s50/=50.0; s200/=200.0;
      sma_side=(s50>s200 ? 1 : (s50<s200 ? -1 : 0));
      return true;
     }

   // ------------------------------------------------------------------------------------------------ shared exits
   void Close(const int k,ShadowCandTrade &t,const double px,const string why)
     {
      if(!t.open) return;
      const double dist=t.dir*(t.entry-t.stop);
      const double r=(dist>0.0 ? t.dir*(px-t.entry)/dist : 0.0);
      const string side=PnlDir(t.dir);
      if(t.gated)
        {
         n[k]++; sum_r[k]+=r;
         EEA_BotLogCode(Code(k),"EXIT","SHADOW",StringFormat("thoát (ảo) %s: %s tại %s, %+.2fR | cộng dồn %d lệnh %+.2fR",
                        side,why,PxT(px),r,n[k],sum_r[k]),
                        EEA_BotJsonNum("r",r,3)+",\"dir\":"+IntegerToString(t.dir)+",\"why\":\""+EEA_JsonEscape(why)+"\","+EEA_BotJsonNum("price",px,2));
        }
      else
         EEA_BotLogCode(Code(k),"MANAGE","SHADOW",StringFormat("lệnh ngoài cổng chế độ %s: %s tại %s, %+.2fR (không tính)",
                        side,why,PxT(px),r),
                        EEA_BotJsonNum("r_ungated",r,3)+",\"dir\":"+IntegerToString(t.dir)+",\"why\":\""+EEA_JsonEscape(why)+"\"");
      ResetTrade(t);
      Save();
     }

   // Stop first when both are touched (as gp.run_trade). Tick prices, then the extremes of the closed M30 bar as
   // a backstop for a gap or an EA restart.
   bool StopOrTarget(const int k,ShadowCandTrade &t,const double bid,const double ask,const double bar_hi,const double bar_lo,
                     const double spread)
     {
      if(!t.open) return false;
      const bool has_tp=(t.target>0.0);
      if(t.dir==1)
        {
         if(bid<=t.stop || (bar_lo>0.0 && bar_lo<=t.stop)) { Close(k,t,MathMin(t.stop,bid),"stop"); return true; }
         if(has_tp && (bid>=t.target || (bar_hi>0.0 && bar_hi>=t.target))) { Close(k,t,t.target,"target 3R"); return true; }
        }
      else
        {
         if(ask>=t.stop || (bar_hi>0.0 && bar_hi+spread>=t.stop)) { Close(k,t,MathMax(t.stop,ask),"stop"); return true; }
         if(has_tp && (ask<=t.target || (bar_lo>0.0 && bar_lo+spread<=t.target))) { Close(k,t,t.target,"target 3R"); return true; }
        }
      return false;
     }

   // ------------------------------------------------------------------------------------------------ SQZ
   void SqueezeBar(const double bid,const double ask)
     {
      MqlRates r[];
      ArraySetAsSeries(r,false);
      const int cnt=CopyRates(sym,PERIOD_M30,1,1500,r);     // r[cnt-1] = the bar that just closed (i)
      if(cnt<400) return;
      const int i=cnt-1;
      const double spread=ask-bid;
      // open trade: backstop on the closed bar, then the 96-bar time exit
      if(sq.open && r[i].time>=sq.opened)
        {
         if(!StopOrTarget(0,sq,bid,ask,r[i].high,r[i].low,spread))
           {
            const int held=iBarShift(sym,PERIOD_M30,sq.opened,false);   // bars from the entry bar to the forming bar
            if(held>=96) Close(0,sq,sq.dir==1 ? bid : ask,"96 nến");
           }
        }
      double c[];
      ArrayResize(c,cnt);
      for(int k=0;k<cnt;k++) c[k]=r[k].close;
      double e200[];
      Ema(c,cnt,200,e200);
      // ATR14 (Wilder) of bar i
      double atr=r[0].high-r[0].low;
      for(int k=1;k<cnt;k++)
        {
         const double tr=MathMax(r[k].high-r[k].low,MathMax(MathAbs(r[k].high-r[k-1].close),MathAbs(r[k].low-r[k-1].close)));
         atr+=(tr-atr)/14.0;
        }
      // band width 4 x stdev(20) and its rank among the last 120 (bar i-1)
      double bw[];
      ArrayResize(bw,cnt);
      for(int k=19;k<cnt;k++)
        {
         double m=0.0, v=0.0;
         for(int j=k-19;j<=k;j++) m+=c[j];
         m/=20.0;
         for(int j=k-19;j<=k;j++) v+=(c[j]-m)*(c[j]-m);
         bw[k]=4.0*MathSqrt(v/20.0);
        }
      const int q=i-1;
      int below=0;
      for(int j=q-119;j<=q;j++) if(bw[j]<=bw[q]) below++;
      const double rank=below/120.0;
      double sma=0.0;
      for(int j=i-19;j<=i;j++) sma+=c[j];
      sma/=20.0;
      double hh=r[i-20].high, ll=r[i-20].low;
      for(int j=i-19;j<i;j++) { hh=MathMax(hh,r[j].high); ll=MathMin(ll,r[j].low); }
      MqlDateTime tm;
      TimeToStruct(r[i].time,tm);
      if(tm.hour==23 || tm.hour==0) return;
      if(sq_last_signal>0 && iBarShift(sym,PERIOD_M30,sq_last_signal,false)<=11) return;   // i <= cool (signal + 10)
      if(!(rank<=0.2)) return;
      int regime=0, sma_side=0;
      if(!DayStates(regime,sma_side)) return;
      int d=0;
      if(c[i]>hh && c[i]>r[i].open && c[i]>e200[i] && sma_side==1) d=1;
      else if(c[i]<ll && c[i]<r[i].open && c[i]<e200[i] && sma_side==-1) d=-1;
      if(d==0) return;
      sq_last_signal=r[i].time;
      Save();
      if(sq.open)
        {
         EEA_BotLogCode("SQZ","SKIP","SHADOW",StringFormat("tín hiệu %s bỏ qua: lệnh trước còn mở",PnlDir(d)));
         return;
        }
      const double entry=(d==1 ? ask : bid);
      const double stop=sma-d*0.1*atr;
      const double dist=d*(entry-stop);
      if(!(0.5*atr<=dist && dist<=3.0*atr))
        {
         EEA_BotLogCode("SQZ","SKIP","SHADOW",StringFormat("tín hiệu %s bỏ qua: stop %.2f ATR ngoài 0,5..3",PnlDir(d),dist/atr));
         return;
        }
      sq.open=true; sq.dir=d; sq.gated=(regime==d); sq.entry=entry; sq.stop=stop; sq.target=entry+d*3.0*dist;
      sq.opened=iTime(sym,PERIOD_M30,0);
      const string base=StringFormat("%s tại %s, SL %s, TP %s (rank BW %.2f, ATR %s)",PnlDir(d),PxT(entry),PxT(stop),
                                     PxT(sq.target),rank,PxT(atr));
      const string data=EEA_BotJsonNum("price",entry,2)+","+EEA_BotJsonNum("sl",stop,2)+","+EEA_BotJsonNum("tp",sq.target,2)+
                        ",\"dir\":"+IntegerToString(d)+",\"regime\":"+IntegerToString(regime)+",\"gated\":"+(sq.gated ? "true" : "false");
      if(sq.gated) EEA_BotLogCode("SQZ","ENTRY","SHADOW","vào (ảo) "+base+", chế độ D1 cùng chiều",data);
      else EEA_BotLogCode("SQZ","SKIP","SHADOW","ngoài cổng chế độ D1 (theo dõi, không tính): "+base,data);
      Save();
     }

   // ------------------------------------------------------------------------------------------------ W1
   static datetime MondayOf(const datetime t)
     {
      MqlDateTime m;
      TimeToStruct(t,m);
      const int back=(m.day_of_week+6)%7;                     // Monday = 0
      return (datetime)((long)(t/86400)*86400-(long)back*86400);
     }

   // New server week: the levels of last week (its D1 bars); an open trade of the old week is closed.
   void WeekStart(const datetime monday)
     {
      for(int s=0;s<2;s++) if(wk[s].open) Close(1,wk[s],s==0 ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK),"tuần mới");
      wk_week=monday; wk_done[0]=false; wk_done[1]=false; wk_high=0.0; wk_low=0.0;
      MqlRates d[];
      ArraySetAsSeries(d,false);
      const int cnt=CopyRates(sym,PERIOD_D1,monday-7*86400,monday-1,d);
      if(cnt<=0) { wk_week=0; return; }
      wk_high=d[0].high; wk_low=d[0].low;
      for(int k=1;k<cnt;k++) { wk_high=MathMax(wk_high,d[k].high); wk_low=MathMin(wk_low,d[k].low); }
      wk_scanned=false;
      int regime=0, sma_side=0;
      DayStates(regime,sma_side);
      EEA_BotLogCode("W1","DECISION","SHADOW",StringFormat("tuần mới: đỉnh tuần trước %s, đáy %s, SL ở giữa %s | chế độ D1 %s",
                     PxT(wk_high),PxT(wk_low),PxT(0.5*(wk_high+wk_low)),regime==1 ? "TĂNG" : (regime==-1 ? "GIẢM" : "TRUNG TÍNH")),
                     EEA_BotJsonNum("pwh",wk_high,2)+","+EEA_BotJsonNum("pwl",wk_low,2)+",\"regime\":"+IntegerToString(regime));
      Save();
     }

   // Once per run and per week, from the first bar of the week on: a week that opened beyond a level has no
   // breakout on that side, and a touch in a closed bar this run did not see (EA off) uses that side up.
   void WeekScan()
     {
      const datetime cur=iTime(sym,PERIOD_M30,0);
      if(cur<wk_week) return;
      MqlRates m[];
      ArraySetAsSeries(m,false);
      const int mc=CopyRates(sym,PERIOD_M30,wk_week,TimeTradeServer(),m);
      if(mc<=0) return;
      const bool before0=wk_done[0], before1=wk_done[1];
      if(m[0].open>wk_high) wk_done[0]=true;
      if(m[0].open<wk_low) wk_done[1]=true;
      for(int k=0;k<mc;k++)
        {
         if(m[k].time>=cur) break;
         const double sp=m[k].spread*SymbolInfoDouble(sym,SYMBOL_POINT);
         if(m[k].high+sp>=wk_high) wk_done[0]=true;
         if(m[k].low<=wk_low) wk_done[1]=true;
        }
      wk_scanned=true;
      for(int s=0;s<2;s++)
         if(wk_done[s] && !(s==0 ? before0 : before1) && !wk[s].open)
            EEA_BotLogCode("W1","SKIP","SHADOW",StringFormat("phía %s tuần này bỏ: mở cửa vượt mức hoặc đã chạm khi EA không chạy",
                           s==0 ? "mua" : "bán"));
      Save();
     }

   void WeeklyTick(const double bid,const double ask,const bool new_bar)
     {
      const datetime now=TimeTradeServer();
      MqlDateTime tm;
      TimeToStruct(now,tm);
      const datetime monday=MondayOf(now);
      if(monday!=wk_week) WeekStart(monday);
      if(wk_week==0 || wk_high<=0.0) return;
      if(!wk_scanned) WeekScan();
      const bool friday_out=(tm.day_of_week==5 && tm.hour*60+tm.min>=21*60+30) || tm.day_of_week==6 || tm.day_of_week==0;
      double bh=0.0, bl=0.0;
      if(new_bar) { bh=iHigh(sym,PERIOD_M30,1); bl=iLow(sym,PERIOD_M30,1); }
      for(int s=0;s<2;s++)
        {
         if(!wk[s].open) continue;
         const bool just=(new_bar && iTime(sym,PERIOD_M30,1)<wk[s].opened);
         if(StopOrTarget(1,wk[s],bid,ask,just ? 0.0 : bh,just ? 0.0 : bl,ask-bid)) continue;
         if(friday_out) Close(1,wk[s],s==0 ? bid : ask,"thứ Sáu 21:30");
        }
      if(!wk_scanned || tm.day_of_week<1 || tm.day_of_week>4) return;   // entries Monday..Thursday, after the scan
      for(int s=0;s<2;s++)
        {
         if(wk_done[s]) continue;
         const int d=(s==0 ? 1 : -1);
         const bool hit=(d==1 ? ask>=wk_high : bid<=wk_low);
         if(!hit) continue;
         wk_done[s]=true;
         int regime=0, sma_side=0;
         DayStates(regime,sma_side);
         const double entry=(d==1 ? ask : bid);
         const double stop=0.5*(wk_high+wk_low);
         ShadowCandTrade t;
         ResetTrade(t);
         t.open=true; t.dir=d; t.gated=(regime==d); t.entry=entry; t.stop=stop; t.target=0.0; t.opened=now;
         wk[s]=t;
         const string base=StringFormat("%s phá %s tuần trước tại %s, SL %s, thoát thứ Sáu 21:30",PnlDir(d),d==1 ? "đỉnh" : "đáy",
                                        PxT(entry),PxT(stop));
         const string data=EEA_BotJsonNum("price",entry,2)+","+EEA_BotJsonNum("sl",stop,2)+",\"dir\":"+IntegerToString(d)+
                           ",\"regime\":"+IntegerToString(regime)+",\"gated\":"+(t.gated ? "true" : "false");
         if(t.gated) EEA_BotLogCode("W1","ENTRY","SHADOW","vào (ảo) "+base+", chế độ D1 cùng chiều",data);
         else EEA_BotLogCode("W1","SKIP","SHADOW","ngoài cổng chế độ D1 (theo dõi, không tính): "+base,data);
         Save();
        }
     }

   // ------------------------------------------------------------------------------------------------ tick
   void OnTick()
     {
      if(!Enabled()) return;
      const double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      if(bid<=0.0 || ask<=0.0) return;
      const datetime m30=iTime(sym,PERIOD_M30,0);
      const bool new_bar=(m30!=0 && m30!=last_m30);
      if(p.squeeze && !new_bar) StopOrTarget(0,sq,bid,ask,0.0,0.0,ask-bid);
      if(new_bar)
        {
         const bool first=(last_m30==0);
         last_m30=m30;
         if(p.squeeze && !first) SqueezeBar(bid,ask);       // the bar seen at the start may still be loading
        }
      if(p.weekly) WeeklyTick(bid,ask,new_bar);
     }

   string StatusJson()
     {
      string s="";
      for(int k=0;k<2;k++)
        {
         const bool on=(k==0 ? p.squeeze : p.weekly);
         int open_count=0;
         if(k==0) open_count=(sq.open ? 1 : 0); else open_count=(wk[0].open ? 1 : 0)+(wk[1].open ? 1 : 0);
         s+=(k>0 ? "," : "")+"{\"code\":\""+Code(k)+"\",\"enabled\":"+(on ? "true" : "false")+",\"gated_trades\":"+
            IntegerToString(n[k])+","+EEA_BotJsonNum("gated_r",sum_r[k],2)+",\"open\":"+IntegerToString(open_count)+"}";
        }
      return "["+s+"]";
     }
  };

#endif
