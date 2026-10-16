#ifndef ENTERPRISE_EA_BOT_CTXLIMIT_MQH
#define ENTERPRISE_EA_BOT_CTXLIMIT_MQH

// CtxLimit (MKT04 gold context forecast) inside EnterpriseEA (bots host). Port of CtxLimitTester.mq5 with the
// same model, features and rules:
//   30 context features on every full-hour M30 close -> LightGBM forecast of plan L (limit 0.5 ATR14 H4 from
//   the close, 8 M30 bars to fill) or plan M (market); SL 1.0 ATR H4, TP 2.0 ATR H4, closed after 96 M30 bars;
//   one position at a time (a fill cancels the other limits); S07 gates: H4 EMA200 side, sell location (9-bar
//   high within 0.5 ATR M30 of the H4 EMA200), weight 0.67 without the ordered EMA21/55/100.
// Host changes: every new order asks EEA_BotGuardCheck(); SHADOW keeps virtual limits and a virtual position.
// The tester had no News Guard / sentiment and neither does this module. Positions and limits are found by
// magic, so a restart keeps managing them (the context is rebuilt from the M30 history).

#include <Trade/Trade.mqh>
#include "../CtxLimit/CtxGoldModel.mqh"
#include "../Tester/TesterPanel.mqh"
#include "PortfolioGuard.mqh"

#define CTXB_SLOTS 48
#define CTXB_VOLHIST 20
#define CTXB_MAXV 8
#define CTXB_MIN_BARS 9600            // ~200 trading days of M30: H4 / D1 EMA200 need it (CtxLimitTester note)

enum CtxBotPlan { CTXB_PLAN_LIMIT=0, CTXB_PLAN_MARKET=1 };

struct CtxLimitBotParams
  {
   EEA_BotModeInput mode;
   CtxBotPlan plan;
   double threshold;              // <= 0: the MKT04 value (L 0.383, M 0.211)
   double risk_percent;           // x weight
   bool   buy, sell, h4_side_gate, sell_location;
   double unordered_weight, stop_atr, target_atr, pull_atr;
   int    limit_bars, hold_bars, max_pending;
   long   magic;
  };

void CtxLimitBotParamsDefaults(CtxLimitBotParams &p)
  {
   p.mode=BOT_SHADOW; p.plan=CTXB_PLAN_LIMIT; p.threshold=0.0; p.risk_percent=0.5; p.buy=true; p.sell=true;
   p.h4_side_gate=true; p.sell_location=true; p.unordered_weight=0.67; p.stop_atr=1.0; p.target_atr=2.0; p.pull_atr=0.5;
   p.limit_bars=8; p.hold_bars=96; p.max_pending=8; p.magic=717171;
  }

double CtxbNan() { return MathArcsin(2.0); }
bool   CtxbOk(const double v) { return MathIsValidNumber(v); }

struct CtxbWilder
  {
   double n, v; bool ok;
   void   Init(const double period) { n=period; v=0.0; ok=false; }
   double Add(const double x) { v=(ok ? v+(x-v)/n : x); ok=true; return v; }
  };

struct CtxbEma
  {
   double k, v; bool ok;
   void   Init(const double period) { k=2.0/(period+1.0); v=0.0; ok=false; }
   double Add(const double x) { v=(ok ? v+k*(x-v) : x); ok=true; return v; }
  };

struct CtxbHtf
  {
   long       sec;
   long       cur;
   bool       has_cur;
   double     h, l, c, prev_c;
   bool       has_prev;
   CtxbEma    ema;
   CtxbWilder atr;
   int        done;
   double     last_c, last_e, last_a;
   void Init(const long seconds)
     {
      sec=seconds; has_cur=false; has_prev=false; done=0; h=l=c=prev_c=0.0;
      ema.Init(200); atr.Init(14); last_c=last_e=last_a=CtxbNan();
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

struct CtxbState
  {
   bool       started;
   double     prev_c, prev_h, prev_l;
   CtxbWilder atr, atr100, pdm, mdm, dx, gain, loss;
   CtxbEma    e21, e55, e100, e200;
   double     closes[97]; int nclose;
   double     highs[16], lows[16]; int nhl;
   double     highs9[9]; int nh9;
   CtxbHtf    h4, d1;
   long       day; bool has_day;
   double     dmax, dmin, pv, vv, pdh, pdl;
   double     vol[CTXB_SLOTS][CTXB_VOLHIST]; int vcount[CTXB_SLOTS]; int vpos[CTXB_SLOTS];
   double     f[CTX_NFEAT];
   double     a14, A, c, top9, x21, x55, x100, h4ema;
  };

struct CtxbVirtual
  {
   bool     used;
   int      dir;
   double   entry, stop, target;
   datetime at;                   // placed (limit) / opened (position)
  };

class CCtxLimitBot
  {
public:
   CtxLimitBotParams p;
   string   sym, root;
   CTrade   trade;
   CtxbState g;
   datetime last_bar, seen_bar;
   bool     warm;
   datetime dl_time;
   double   dl_buy, dl_sell;
   string   dl_result;
   int      decisions, signals, gated, orders, blocked_guard;
   CtxbVirtual v_pos;
   CtxbVirtual v_pend[CTXB_MAXV];
   double   v_realized_r;
   bool     model_ok;

                     CCtxLimitBot() { last_bar=0; seen_bar=0; warm=false; }

   bool     IsLive() const { return p.mode==BOT_LIVE; }
   string   ModeText() const { return p.mode==BOT_OFF ? "OFF" : (IsLive() ? "LIVE" : "SHADOW"); }
   int      Digits() const { return (int)SymbolInfoInteger(sym,SYMBOL_DIGITS); }
   string   PxT(const double v) const { return DoubleToString(v,Digits()); }
   double   Threshold() const { return p.threshold>0.0 ? p.threshold : (p.plan==CTXB_PLAN_LIMIT ? 0.3825820347356539 : 0.21075521107935286); }

   void Init(const CtxLimitBotParams &params,const string symbol,const string data_root)
     {
      p=params; sym=symbol; root=data_root;
      model_ok=(ArraySize(CTX_FEATURES)==CTX_NFEAT && CTX_FEATURES[0]=="r1" && CTX_FEATURES[28]=="atr_vs_h4");
      if(!model_ok) Print("CtxLimitBot: model feature order mismatch, the bot stays idle");
      CtxInit();
      trade.SetExpertMagicNumber(p.magic);
      trade.SetTypeFillingBySymbol(sym);
      trade.SetDeviationInPoints(20);
      last_bar=0; seen_bar=0; warm=false; dl_time=0; dl_buy=0; dl_sell=0; dl_result="";
      decisions=0; signals=0; gated=0; orders=0; blocked_guard=0; v_realized_r=0.0;
      v_pos.used=false;
      for(int i=0;i<CTXB_MAXV;i++) v_pend[i].used=false;
     }

   void Deinit() {}

   // ------------------------------------------------------------------------------------------------ context
   void CtxInit()
     {
      g.started=false; g.prev_c=g.prev_h=g.prev_l=0.0;
      g.atr.Init(14); g.atr100.Init(100); g.pdm.Init(14); g.mdm.Init(14); g.dx.Init(14); g.gain.Init(14); g.loss.Init(14);
      g.e21.Init(21); g.e55.Init(55); g.e100.Init(100); g.e200.Init(200);
      g.nclose=0; g.nhl=0; g.nh9=0;
      g.h4.Init(14400); g.d1.Init(86400);
      g.has_day=false; g.day=0; g.dmax=g.dmin=g.pv=g.vv=0.0; g.pdh=g.pdl=CtxbNan();
      for(int s=0;s<CTXB_SLOTS;s++) { g.vcount[s]=0; g.vpos[s]=0; }
     }

   double CtxBack(const int n,const double c,const double a) const
     {
      if(g.nclose<=n) return CtxbNan();
      return (c-g.closes[(g.nclose-1-n)%97])/a;
     }

   void CtxAdd(const MqlRates &r)
     {
      const long   t=(long)r.time;
      const double h=r.high, l=r.low, c=r.close, v=(double)r.tick_volume;
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
      const long dday=t/86400;
      if(!g.has_day || dday!=g.day)
        {
         if(g.has_day) { g.pdh=g.dmax; g.pdl=g.dmin; }
         g.day=dday; g.has_day=true; g.dmax=h; g.dmin=l; g.pv=0.0; g.vv=0.0;
        }
      else { g.dmax=MathMax(g.dmax,h); g.dmin=MathMin(g.dmin,l); }
      const double w=MathMax(v,1.0);
      g.pv+=w*(h+l+c)/3.0; g.vv+=w;
      const long sod=t%86400;
      const int slot=(int)(sod/1800)%CTXB_SLOTS;
      double mean20=CtxbNan();
      if(g.vcount[slot]>=10)
        {
         double s=0.0;
         for(int k=0;k<g.vcount[slot];k++) s+=g.vol[slot][k];
         mean20=s/g.vcount[slot];
        }
      g.vol[slot][g.vpos[slot]]=v; g.vpos[slot]=(g.vpos[slot]+1)%CTXB_VOLHIST;
      if(g.vcount[slot]<CTXB_VOLHIST) g.vcount[slot]++;
      g.f[0]=CtxBack(1,c,a); g.f[1]=CtxBack(4,c,a); g.f[2]=CtxBack(16,c,a); g.f[3]=CtxBack(48,c,a);
      g.f[4]=(c-x21)/a; g.f[5]=(x21-x55)/a; g.f[6]=(x55-x200)/a;
      const bool h4ok=(g.h4.done>=201), d1ok=(g.d1.done>=201);
      g.f[7]=(h4ok ? (g.h4.last_c>g.h4.last_e ? 1.0 : (g.h4.last_c<g.h4.last_e ? -1.0 : 0.0)) : CtxbNan());
      g.f[8]=(h4ok ? (c-g.h4.last_e)/a : CtxbNan());
      g.f[9]=(d1ok ? (g.d1.last_c>g.d1.last_e ? 1.0 : (g.d1.last_c<g.d1.last_e ? -1.0 : 0.0)) : CtxbNan());
      g.f[10]=(d1ok ? (c-g.d1.last_e)/a : CtxbNan());
      g.f[11]=adx; g.f[12]=pdi-mdi; g.f[13]=rsi;
      g.f[14]=a/a100;
      if(g.nhl>=16)
        {
         double mx=g.highs[0], mn=g.lows[0];
         for(int k=1;k<16;k++) { mx=MathMax(mx,g.highs[k]); mn=MathMin(mn,g.lows[k]); }
         g.f[15]=(mx-mn)/a;
        }
      else g.f[15]=CtxbNan();
      g.f[16]=(c-g.pdh)/a; g.f[17]=(c-g.pdl)/a;
      g.f[18]=(c-g.dmin)/MathMax(g.dmax-g.dmin,1e-12);
      g.f[19]=(c-g.pv/g.vv)/a;
      const double step=MathPow(10.0,MathFloor(MathLog10(c))-2.0);
      g.f[20]=MathMod(c,step)/step;
      g.f[21]=(double)((((sod/3600)-7)%24+24)%24);
      g.f[22]=(double)((((t-7*3600)/86400+3)%7+7)%7);
      g.f[23]=((sod>=16*3600+1800 && sod<=23*3600) ? (double)(sod-(16*3600+1800))/60.0 : -1.0);
      g.f[24]=(CtxbOk(mean20) ? v/mean20 : CtxbNan());
      g.f[25]=g.f[0]; g.f[26]=g.f[1];
      g.f[27]=CtxBack(96,c,a);
      const double A=(g.h4.done>=15 ? g.h4.last_a : CtxbNan());
      g.f[28]=(CtxbOk(A) ? a/A : CtxbNan());
      g.f[29]=0.0;
      double top9=h;
      const int n9=MathMin(g.nh9,9);
      for(int k=0;k<n9;k++) top9=MathMax(top9,g.highs9[k]);
      g.a14=a; g.A=A; g.c=c; g.top9=(g.nh9>=9 ? top9 : CtxbNan()); g.x21=x21; g.x55=x55; g.x100=x100;
      g.h4ema=(h4ok ? g.h4.last_e : CtxbNan());
      g.prev_c=c; g.prev_h=h; g.prev_l=l; g.started=true;
     }

   static double Predict(const double &x[],const int &feat[],const double &thr[],const int &left[],const int &right[],
                         const char &dleft[],const char &miss[],const double &leaf[],const int &root_[],const int &rootleaf[])
     {
      double s=0.0;
      const int trees=ArraySize(root_);
      for(int t=0;t<trees;t++)
        {
         if(root_[t]<0) { s+=leaf[rootleaf[t]]; continue; }
         int k=root_[t];
         while(true)
           {
            double v=x[feat[k]];
            bool go_left;
            if(miss[k]==2 && !CtxbOk(v)) go_left=(dleft[k]==1);
            else if(miss[k]==1 && (!CtxbOk(v) || MathAbs(v)<=1e-35)) go_left=(dleft[k]==1);
            else
              {
               if(!CtxbOk(v)) v=0.0;
               go_left=(v<=thr[k]);
              }
            const int nxt=(go_left ? left[k] : right[k]);
            if(nxt<0) { s+=leaf[-nxt-1]; break; }
            k=nxt;
           }
        }
      return s;
     }

   // ------------------------------------------------------------------------------------------------ orders
   bool HasPosition(ulong &ticket) const
     {
      if(!IsLive()) return v_pos.used;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         const ulong tk=PositionGetTicket(i);
         if(tk>0 && PositionGetString(POSITION_SYMBOL)==sym && PositionGetInteger(POSITION_MAGIC)==p.magic) { ticket=tk; return true; }
        }
      return false;
     }

   int PendingCount() const
     {
      int n=0;
      if(!IsLive()) { for(int i=0;i<CTXB_MAXV;i++) if(v_pend[i].used) n++; return n; }
      for(int i=OrdersTotal()-1;i>=0;i--)
        {
         const ulong tk=OrderGetTicket(i);
         if(tk>0 && OrderGetString(ORDER_SYMBOL)==sym && OrderGetInteger(ORDER_MAGIC)==p.magic) n++;
        }
      return n;
     }

   void ManagePending(const bool position)
     {
      if(!IsLive())
        {
         for(int i=0;i<CTXB_MAXV;i++)
            if(v_pend[i].used && (position || TimeCurrent()-v_pend[i].at>=(long)p.limit_bars*1800)) v_pend[i].used=false;
         return;
        }
      for(int i=OrdersTotal()-1;i>=0;i--)
        {
         const ulong tk=OrderGetTicket(i);
         if(tk==0 || OrderGetString(ORDER_SYMBOL)!=sym || OrderGetInteger(ORDER_MAGIC)!=p.magic) continue;
         const datetime placed=(datetime)OrderGetInteger(ORDER_TIME_SETUP);
         if(position || TimeCurrent()-placed>=(long)p.limit_bars*1800) trade.OrderDelete(tk);
        }
     }

   void ManagePosition()
     {
      if(!IsLive())
        {
         if(v_pos.used)
           {
            const datetime bar0=(datetime)((long)v_pos.at-(long)v_pos.at%1800);
            if((long)(TimeCurrent()-bar0)>=(long)p.hold_bars*1800) CloseVirtual("48 giờ");
           }
         return;
        }
      ulong tk=0;
      if(!HasPosition(tk) || !PositionSelectByTicket(tk)) return;
      const datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      const datetime bar0=(datetime)((long)opened-(long)opened%1800);
      if((long)(TimeCurrent()-bar0)>=(long)p.hold_bars*1800) trade.PositionClose(tk);
     }

   void CloseVirtual(const string why)
     {
      const double px=(v_pos.dir==1 ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK));
      const double R=MathAbs(v_pos.entry-v_pos.stop);
      v_realized_r+=(R>0.0 ? v_pos.dir*(px-v_pos.entry)/R : 0.0);
      v_pos.used=false;
      dl_result="lệnh ảo đóng: "+why;
     }

   // SHADOW: virtual limit fills (the first cancels the others), virtual SL / TP.
   void ShadowTick()
     {
      if(IsLive()) return;
      const double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      if(!v_pos.used)
         for(int i=0;i<CTXB_MAXV;i++)
            if(v_pend[i].used && ((v_pend[i].dir==1 && ask<=v_pend[i].entry) || (v_pend[i].dir==-1 && bid>=v_pend[i].entry)))
              {
               v_pos=v_pend[i]; v_pos.at=TimeCurrent();
               for(int k=0;k<CTXB_MAXV;k++) v_pend[k].used=false;
               break;
              }
      if(v_pos.used)
        {
         const int d=v_pos.dir;
         if((d==1 && bid<=v_pos.stop) || (d==-1 && ask>=v_pos.stop)) { v_realized_r+=-1.0; v_pos.used=false; dl_result="lệnh ảo: dừng ở SL"; }
         else if((d==1 && bid>=v_pos.target) || (d==-1 && ask<=v_pos.target))
           { v_realized_r+=p.target_atr/p.stop_atr; v_pos.used=false; dl_result="lệnh ảo: chạm TP"; }
        }
     }

   double VolumeFor(const int dir,const double entry,const double stop,const double weight,double &risk_money) const
     {
      risk_money=0.0;
      const double capital=(g_bot_guard.capital>0.0 ? g_bot_guard.capital : AccountInfoDouble(ACCOUNT_BALANCE));
      const double money=MathMin(AccountInfoDouble(ACCOUNT_EQUITY),capital)*p.risk_percent/100.0*MathMax(0.0,MathMin(1.0,weight));
      double loss=0.0;
      if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,1.0,entry,stop,loss) || loss>=0.0) return 0.0;
      const double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
      const double vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
      double v=MathFloor(money/(-loss)/step+1e-9)*step;
      if(v<vmin) return 0.0;
      v=MathMin(v,vmax);
      risk_money=v*(-loss);
      return v;
     }

   void Decide(const datetime bar_time)
     {
      decisions++;
      double x[CTX_NFEAT];
      for(int k=0;k<CTX_NFEAT;k++) x[k]=g.f[k];
      const double pll=Predict(x,CTX_LL_FEAT,CTX_LL_THR,CTX_LL_LEFT,CTX_LL_RIGHT,CTX_LL_DLEFT,CTX_LL_MISS,CTX_LL_LEAF,CTX_LL_ROOT,CTX_LL_ROOTLEAF);
      const double pls=Predict(x,CTX_LS_FEAT,CTX_LS_THR,CTX_LS_LEFT,CTX_LS_RIGHT,CTX_LS_DLEFT,CTX_LS_MISS,CTX_LS_LEAF,CTX_LS_ROOT,CTX_LS_ROOTLEAF);
      const double pml=Predict(x,CTX_ML_FEAT,CTX_ML_THR,CTX_ML_LEFT,CTX_ML_RIGHT,CTX_ML_DLEFT,CTX_ML_MISS,CTX_ML_LEAF,CTX_ML_ROOT,CTX_ML_ROOTLEAF);
      const double pms=Predict(x,CTX_MS_FEAT,CTX_MS_THR,CTX_MS_LEFT,CTX_MS_RIGHT,CTX_MS_DLEFT,CTX_MS_MISS,CTX_MS_LEAF,CTX_MS_ROOT,CTX_MS_ROOTLEAF);
      const double th=Threshold();
      const double p_buy=(p.plan==CTXB_PLAN_LIMIT ? pll : pml), p_sell=(p.plan==CTXB_PLAN_LIMIT ? pls : pms);
      dl_time=bar_time; dl_buy=p_buy; dl_sell=p_sell; dl_result="";
      ulong tk=0;
      if(HasPosition(tk)) { dl_result="bỏ qua — đang có lệnh mở (một lệnh mỗi lúc)"; return; }
      if(p.plan==CTXB_PLAN_LIMIT && PendingCount()>=p.max_pending) { dl_result="bỏ qua — đã đủ limit chờ"; return; }
      string why="";
      int dir=0; double best=-1e9;
      for(int s=0;s<2;s++)
        {
         const int d=(s==0 ? 1 : -1);
         const double pr=(d==1 ? p_buy : p_sell);
         if((d==1 && !p.buy) || (d==-1 && !p.sell)) continue;
         if(!(pr>th && pr>0.0)) continue;
         signals++;
         if(p.h4_side_gate && !(CtxbOk(g.f[7]) && (int)g.f[7]==d)) { gated++; why+=(d==1 ? "MUA" : "BÁN")+string(" qua ngưỡng nhưng ngược phía EMA200 H4; "); continue; }
         if(d==-1 && p.sell_location && !(CtxbOk(g.h4ema) && CtxbOk(g.top9) && g.top9>=g.h4ema-0.5*g.a14)) { gated++; why+="BÁN qua ngưỡng nhưng chưa đạt vị trí L2; "; continue; }
         if(pr>best) { best=pr; dir=d; }
        }
      if(dir==0 || !CtxbOk(g.A) || g.A<=0.0) { dl_result=(why!="" ? "không vào — "+why : "không vào — chưa chiều nào qua ngưỡng"); return; }
      if(!EEA_BotActive(EEA_BOT_CTXLIMIT)) { dl_result="không vào — bot INACTIVE"; return; }
      const bool ordered=(dir==1 ? (g.x21>g.x55 && g.x55>g.x100 && g.c>g.x21) : (g.x21<g.x55 && g.x55<g.x100 && g.c<g.x21));
      const double weight=(ordered ? 1.0 : p.unordered_weight);
      const double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      bool market=(p.plan==CTXB_PLAN_MARKET);
      double entry=(dir==1 ? ask : bid);
      if(!market)
        {
         const double level=g.c-dir*p.pull_atr*g.A;
         if((dir==1 && ask<=level) || (dir==-1 && bid>=level)) market=true;
         else entry=level;
        }
      const double stop=entry-dir*p.stop_atr*g.A, target=entry+dir*p.target_atr*g.A;
      double risk_money=0.0;
      const double vol=VolumeFor(dir,entry,stop,weight,risk_money);
      if(!IsLive())
        {
         CtxbVirtual o; o.used=true; o.dir=dir; o.entry=entry; o.stop=stop; o.target=target; o.at=TimeCurrent();
         if(market) v_pos=o;
         else for(int i=0;i<CTXB_MAXV;i++) if(!v_pend[i].used) { v_pend[i]=o; break; }
         orders++;
         dl_result=StringFormat("%s (ảo) %s %s tại %s (SL %s, TP %s)",market ? "VÀO" : "ĐẶT",market ? "market" : "limit",
                                dir==1 ? "MUA" : "BÁN",PxT(entry),PxT(stop),PxT(target));
         return;
        }
      if(vol<=0.0) { dl_result="không vào — khối lượng dưới mức tối thiểu"; return; }
      const string reason=EEA_BotGuardCheck(EEA_BOT_CTXLIMIT,risk_money,"SWING",true,false);
      if(reason!="") { blocked_guard++; dl_result="không vào — Portfolio Guard: "+reason; return; }
      const string tag=StringFormat("CTX%s %.2f%s",p.plan==CTXB_PLAN_LIMIT ? "L" : "M",best,ordered ? "" : " w");
      bool ok;
      if(market)
         ok=(dir==1 ? trade.Buy(vol,sym,0.0,NormalizeDouble(stop,Digits()),NormalizeDouble(target,Digits()),tag)
                    : trade.Sell(vol,sym,0.0,NormalizeDouble(stop,Digits()),NormalizeDouble(target,Digits()),tag));
      else
         ok=(dir==1 ? trade.BuyLimit(vol,NormalizeDouble(entry,Digits()),sym,NormalizeDouble(stop,Digits()),NormalizeDouble(target,Digits()),ORDER_TIME_GTC,0,tag)
                    : trade.SellLimit(vol,NormalizeDouble(entry,Digits()),sym,NormalizeDouble(stop,Digits()),NormalizeDouble(target,Digits()),ORDER_TIME_GTC,0,tag));
      if(ok) orders++;
      dl_result=StringFormat("%s %s %s %.2f lot tại %s (SL %s, TP %s)",ok ? (market ? "VÀO" : "ĐẶT") : "LỖI gửi",market ? "market" : "limit",
                             dir==1 ? "MUA" : "BÁN",vol,PxT(entry),PxT(stop),PxT(target));
     }

   // every closed M30 bar after the last processed one, in order; decisions only on live full-hour closes
   void ProcessBars()
     {
      MqlRates r[];
      int n;
      if(last_bar==0)
        {
         const int total=Bars(sym,PERIOD_M30);
         if(total<CTXB_MIN_BARS) return;                 // history still loading: not warm, tried again next tick
         n=CopyRates(sym,PERIOD_M30,1,MathMax(0,total-1),r);
         if(n<CTXB_MIN_BARS-1) return;
        }
      else
         n=CopyRates(sym,PERIOD_M30,last_bar+1,TimeCurrent(),r);
      if(n<=0) return;
      const datetime forming=iTime(sym,PERIOD_M30,0);
      for(int i=0;i<n;i++)
        {
         if(r[i].time<=last_bar || r[i].time>=forming) continue;
         CtxAdd(r[i]);
         last_bar=r[i].time;
         const bool live=(i==n-1 || r[i+1].time>=forming);
         if(warm && live && ((long)r[i].time+1800)%3600==0) Decide(r[i].time);
        }
      warm=true;
     }

   void OnTick()
     {
      if(p.mode==BOT_OFF || !model_ok) return;
      ShadowTick();
      const datetime bar=iTime(sym,PERIOD_M30,0);
      ulong tk=0;
      const bool pos=HasPosition(tk);
      if(pos) ManagePending(true);
      if(bar==seen_bar && warm) return;
      if(bar!=seen_bar)
        {
         ManagePosition();
         ManagePending(HasPosition(tk));
        }
      seen_bar=bar;
      ProcessBars();
     }

   int OpenLegs() const { ulong tk=0; return (HasPosition(tk) ? 1 : 0)+PendingCount(); }

   string StatusText() const
     {
      if(p.mode==BOT_OFF) return "OFF";
      if(!model_ok) return "mô hình không khớp thứ tự đặc trưng";
      if(!warm || !CtxbOk(g.A)) return StringFormat("đang nạp lịch sử M30 (%d / %d nến)",Bars(sym,PERIOD_M30),CTXB_MIN_BARS);
      if(dl_time==0) return "chờ nến M30 đóng đúng giờ tròn";
      return StringFormat("%s: MUA %+.2fR / BÁN %+.2fR (ngưỡng %.2f) — %s",PnlHm(dl_time+1800),dl_buy,dl_sell,Threshold(),dl_result);
     }
  };

#endif
