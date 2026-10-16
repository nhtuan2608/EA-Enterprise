#ifndef ENTERPRISE_EA_BOT_XRT_MQH
#define ENTERPRISE_EA_BOT_XRT_MQH

// XauRegime (G96) inside EnterpriseEA (bots host). Port of XauRegimeTester.mq5 with the same trading rules:
//   regime   the closed D1 bar's close and the EMA(N) 10-day slope on the same side -> +1 / -1, else 0
//   plan     fixed at the day open: market (reference = the open price) or a limit zone; stop 3 ATR20 D1
//            from the fill; a delayed market entry never chases more than 0.5 ATR past the reference
//   exit     the regime leaves the direction (next day open) or a D1 close 3 ATR from the best close
//            (then no new entry on that side until the regime changes), or the broker stop
// Host changes: the tester's copies of the live EA gates are replaced by the live EA itself - EnterpriseEA
// News Guard (SWING block, break-even before HIGH USD events) and sentiment (SWING: x0.5 against, blocked
// when strongly against) through g_bot_guard; every new entry asks EEA_BotGuardCheck(); SHADOW keeps a
// virtual position; the trail anchor and the trail block are saved to current/bots/xrt_state.txt.

#include <Trade/Trade.mqh>
#include "../Tester/TesterPanel.mqh"
#include "PortfolioGuard.mqh"

#define XRB_D1_HISTORY 800
#define XRB_MAX_CHASE_ATR 0.5

enum XrtBotDirMode { XRB_LONG_ONLY=0, XRB_LONG_SHORT=1, XRB_SHORT_ONLY=2 };
enum XrtBotZone
  {
   XRB_MARKET=0, XRB_EMA21_D1=1, XRB_EMA50_D1=2, XRB_PREV_EXTREME=3, XRB_PREV_MID=4, XRB_CLOSE_05ATR=5,
   XRB_CLOSE_1ATR=6, XRB_SWING=7, XRB_EMA21_H4=8
  };

struct XrtBotParams
  {
   EEA_BotModeInput mode;
   double risk_percent;
   bool   block_opposite;
   bool   spread_filter;
   XrtBotDirMode dir_mode;
   int    ema_period, slope_days, atr_period;
   XrtBotZone buy_zone, sell_zone;
   double stop_atr;
   bool   trail;
   double trail_atr;
   bool   news_guard;
   bool   sentiment;
   double news_be_min_r;
   long   magic;
  };

void XrtBotParamsDefaults(XrtBotParams &p)
  {
   p.mode=BOT_SHADOW; p.risk_percent=1.5; p.block_opposite=true; p.spread_filter=false; p.dir_mode=XRB_LONG_ONLY;
   p.ema_period=50; p.slope_days=10; p.atr_period=20; p.buy_zone=XRB_MARKET; p.sell_zone=XRB_EMA21_D1;
   p.stop_atr=3.0; p.trail=true; p.trail_atr=3.0; p.news_guard=true; p.sentiment=true; p.news_be_min_r=0.3;
   p.magic=969696;
  }

struct XrtBotDay
  {
   bool   ok;
   int    state;
   double atr, close, high, low, ema21, ema50, swing_low, swing_high, ema, ema_prev;
  };

struct XrtBotPlan
  {
   bool     ok;
   int      dir;
   bool     market;
   double   ref, level, stop;
   datetime made;
   string   note;
  };

class CXrtBot
  {
public:
   XrtBotParams p;
   string   sym, root;
   CTrade   trade;
   XrtBotDay day;
   XrtBotPlan plan;
   datetime last_d1, last_m5;
   // live position (by magic) or the SHADOW virtual position
   ulong    ticket;
   int      pos_dir;
   double   entry, risk, best, stop;
   bool     be_done;
   int      blocked_dir;
   ulong    pending;
   double   pending_level;
   bool     want_entry;
   // SHADOW virtual orders
   bool     v_open, v_pending;
   double   v_entry, v_stop, v_level, v_realized_r;
   int      v_dir;
   string   last_note;
   int      entries, exits_regime, exits_trail, blocked_news, blocked_sent, blocked_guard;

                     CXrtBot() { ticket=0; pos_dir=0; last_d1=0; last_m5=0; }

   bool     IsLive() const { return p.mode==BOT_LIVE; }
   string   ModeText() const { return p.mode==BOT_OFF ? "OFF" : (IsLive() ? "LIVE" : "SHADOW"); }
   string   PxT(const double v) const { return DoubleToString(v,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS)); }
   int      Digits() const { return (int)SymbolInfoInteger(sym,SYMBOL_DIGITS); }

   void Init(const XrtBotParams &params,const string symbol,const string data_root)
     {
      p=params; sym=symbol; root=data_root;
      trade.SetExpertMagicNumber(p.magic);
      trade.SetTypeFillingBySymbol(sym);
      trade.SetDeviationInPoints(20);
      day.ok=false; plan.ok=false; plan.note=""; plan.made=0;
      ticket=0; pos_dir=0; entry=0; risk=0; best=0; stop=0; be_done=false; blocked_dir=0; pending=0; pending_level=0;
      want_entry=false; v_open=false; v_pending=false; v_entry=0; v_stop=0; v_level=0; v_dir=0; v_realized_r=0;
      last_note=""; entries=0; exits_regime=0; exits_trail=0; blocked_news=0; blocked_sent=0; blocked_guard=0;
      Load();
     }

   void Deinit() { Save(); }

   // ------------------------------------------------------------------------------------------------ persistence
   string StatePath() const { return root+"/current/bots/xrt_state.txt"; }

   void Save()
     {
      if(root=="") return;
      const string s=StringFormat("xrt-state-v1|%s|%I64d|%I64u|%.8f|%d|%d|%d|%.8f|%.8f|%.8f|%d|%.8f",sym,p.magic,ticket,best,
                                  be_done ? 1 : 0,blocked_dir,v_open ? 1 : 0,v_entry,v_stop,v_realized_r,v_dir,v_level);
      FolderCreate(root+"/current/bots",0);
      EEA_WriteAtomicText(StatePath(),s);
     }

   void Load()
     {
      string text;
      if(root=="" || !FileIsExist(StatePath(),0) || !EEA_PendingReadText(StatePath(),text)) return;
      StringTrimRight(text);
      string f[];
      if(StringSplit(text,'|',f)<13 || f[0]!="xrt-state-v1" || f[1]!=sym || StringToInteger(f[2])!=p.magic) return;
      ticket=(ulong)StringToInteger(f[3]); best=StringToDouble(f[4]); be_done=(f[5]=="1"); blocked_dir=(int)StringToInteger(f[6]);
      v_open=(f[7]=="1"); v_entry=StringToDouble(f[8]); v_stop=StringToDouble(f[9]); v_realized_r=StringToDouble(f[10]);
      v_dir=(int)StringToInteger(f[11]); v_level=StringToDouble(f[12]);
      if(ticket!=0 && PositionSelectByTicket(ticket))
        {
         pos_dir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
         entry=PositionGetDouble(POSITION_PRICE_OPEN); stop=PositionGetDouble(POSITION_SL); risk=MathAbs(entry-stop);
         if(best==0.0) best=entry;
        }
     }

   // ------------------------------------------------------------------------------------------------ D1
   static void Ema(const MqlRates &r[],const int n,const int period,double &out[])
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
      const int n=CopyRates(sym,PERIOD_D1,1,XRB_D1_HISTORY,r);
      day.ok=false;
      if(n<MathMax(2*p.ema_period,p.atr_period+p.slope_days+5)) return false;
      double e[], e21[], e50[];
      Ema(r,n,p.ema_period,e); Ema(r,n,21,e21); Ema(r,n,50,e50);
      const int i=n-1;
      double tr=0.0;
      for(int k=i-p.atr_period+1;k<=i;k++) tr+=MathMax(r[k].high,r[k-1].close)-MathMin(r[k].low,r[k-1].close);
      day.atr=tr/p.atr_period;
      const int side=(r[i].close>e[i] ? 1 : (r[i].close<e[i] ? -1 : 0));
      const int slope=(e[i]>e[i-p.slope_days] ? 1 : (e[i]<e[i-p.slope_days] ? -1 : 0));
      day.state=(side==slope ? side : 0);
      day.ema=e[i]; day.ema_prev=e[i-p.slope_days];
      day.close=r[i].close; day.high=r[i].high; day.low=r[i].low; day.ema21=e21[i]; day.ema50=e50[i];
      day.swing_low=0.0; day.swing_high=0.0;
      for(int k=i-2;k>=2;k--)
        {
         if(day.swing_low==0.0 && r[k].low<=MathMin(MathMin(r[k-2].low,r[k-1].low),MathMin(r[k+1].low,r[k+2].low))) day.swing_low=r[k].low;
         if(day.swing_high==0.0 && r[k].high>=MathMax(MathMax(r[k-2].high,r[k-1].high),MathMax(r[k+1].high,r[k+2].high))) day.swing_high=r[k].high;
         if(day.swing_low>0.0 && day.swing_high>0.0) break;
        }
      day.ok=(day.atr>0.0);
      return day.ok;
     }

   double Ema21H4()
     {
      MqlRates r[];
      ArraySetAsSeries(r,false);
      const int n=CopyRates(sym,PERIOD_H4,1,300,r);
      if(n<100) return 0.0;
      double e[];
      Ema(r,n,21,e);
      return e[n-1];
     }

   double ZoneLevel(const XrtBotZone z,const int dir)
     {
      switch(z)
        {
         case XRB_EMA21_D1:     return day.ema21;
         case XRB_EMA50_D1:     return day.ema50;
         case XRB_PREV_EXTREME: return dir==1 ? day.low : day.high;
         case XRB_PREV_MID:     return 0.5*(day.high+day.low);
         case XRB_CLOSE_05ATR:  return day.close-dir*0.5*day.atr;
         case XRB_CLOSE_1ATR:   return day.close-dir*1.0*day.atr;
         case XRB_SWING:        return dir==1 ? day.swing_low : day.swing_high;
         case XRB_EMA21_H4:     return Ema21H4();
         default:               return 0.0;
        }
     }

   bool Allowed(const int dir) const
     {
      if(p.dir_mode==XRB_LONG_ONLY) return dir==1;
      if(p.dir_mode==XRB_SHORT_ONLY) return dir==-1;
      return dir!=0;
     }

   // ------------------------------------------------------------------------------------------------ positions
   // The live position of this magic; a new ticket (a limit filled, or a restart) restarts its bookkeeping.
   bool OwnPosition(int &dir)
     {
      dir=0;
      if(!IsLive()) { if(v_open) dir=v_dir; return v_open; }
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         const ulong t=PositionGetTicket(i);
         if(t==0 || PositionGetInteger(POSITION_MAGIC)!=p.magic || PositionGetString(POSITION_SYMBOL)!=sym) continue;
         dir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
         if(ticket!=t)
           {
            ticket=t; entry=PositionGetDouble(POSITION_PRICE_OPEN); stop=PositionGetDouble(POSITION_SL);
            risk=MathAbs(entry-stop); best=entry; be_done=false; entries++;
            pending=0; want_entry=false;
            Save();
           }
         pos_dir=dir;
         return true;
        }
      ticket=0; pos_dir=0;
      return false;
     }

   void DeletePending()
     {
      if(IsLive()) { if(pending!=0 && OrderSelect(pending)) trade.OrderDelete(pending); }
      pending=0; v_pending=false;
     }

   void CloseOwn(const string why,const double px)
     {
      if(IsLive()) { if(ticket!=0) trade.PositionClose(ticket); ticket=0; }
      else if(v_open)
        {
         const double r=(MathAbs(v_entry-v_stop)>0.0 ? v_dir*(px-v_entry)/MathAbs(v_entry-v_stop) : 0.0);
         v_realized_r+=r; v_open=false;
        }
      last_note="đã thoát: "+why;
      Save();
     }

   // ------------------------------------------------------------------------------------------------ gates
   // Risk weight of a new entry (0 = not now): own opposite position, News Guard (SWING), sentiment (SWING),
   // optional spread rule, then the portfolio guard for LIVE.
   double EntryGate(const int dir,const double price,const double stop_px,const double risk_money,string &reason)
     {
      reason="";
      int open_dir=0;
      if(p.block_opposite && OwnPosition(open_dir) && open_dir==-dir) { reason="XRT_OPPOSITE_OPEN"; return 0.0; }
      if(p.news_guard && g_bot_guard.news_block_swing!="") { blocked_news++; reason=g_bot_guard.news_block_swing; return 0.0; }
      double sent=1.0;
      if(p.sentiment)
        {
         const int k=(dir==1 ? 0 : 1);
         if(g_bot_guard.sent_block[k]) { blocked_sent++; reason="SENTIMENT_STRONGLY_AGAINST"; return 0.0; }
         sent=MathMax(0.0,MathMin(1.0,g_bot_guard.sent_factor[k]));
        }
      if(p.spread_filter)
        {
         const double spread=SymbolInfoDouble(sym,SYMBOL_ASK)-SymbolInfoDouble(sym,SYMBOL_BID);
         if(spread>0.25*MathAbs(price-stop_px)) { reason="XRT_SPREAD_TOO_WIDE"; return 0.0; }
        }
      if(IsLive())
        {
         reason=EEA_BotGuardCheck(EEA_BOT_XRT,risk_money*sent,"SWING",true,false);
         if(reason!="") { blocked_guard++; return 0.0; }
        }
      else if(!EEA_BotActive(EEA_BOT_XRT)) { reason="BOT_INACTIVE"; return 0.0; }
      return sent;
     }

   double VolumeFor(const int dir,const double price,const double stop_px,const double weight,double &risk_money)
     {
      risk_money=0.0;
      const double capital=(g_bot_guard.capital>0.0 ? g_bot_guard.capital : AccountInfoDouble(ACCOUNT_BALANCE));
      const double money=MathMin(AccountInfoDouble(ACCOUNT_EQUITY),capital)*p.risk_percent/100.0*MathMax(0.0,MathMin(1.0,weight));
      double loss=0.0;
      if(!OrderCalcProfit(dir==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,1.0,price,stop_px,loss) || loss>=0.0) return 0.0;
      const double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
      const double vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
      double v=MathFloor(money/(-loss)/step+1e-9)*step;
      if(v<vmin) return 0.0;
      v=MathMin(v,vmax);
      risk_money=v*(-loss);
      return v;
     }

   // ------------------------------------------------------------------------------------------------ plan / entry
   void MakePlan()
     {
      plan.ok=false; plan.note="";
      const int dir=day.state;
      if(!Allowed(dir)) { plan.note="chế độ không cho phép vào hôm nay"; return; }
      if(dir==blocked_dir) { plan.note="vừa thoát bằng trail: chờ chế độ đổi"; return; }
      const XrtBotZone zone=(dir==1 ? p.buy_zone : p.sell_zone);
      const double market=(dir==1 ? SymbolInfoDouble(sym,SYMBOL_ASK) : SymbolInfoDouble(sym,SYMBOL_BID));
      plan.dir=dir; plan.made=TimeCurrent();
      plan.market=(zone==XRB_MARKET);
      plan.ref=market;
      plan.level=(plan.market ? 0.0 : ZoneLevel(zone,dir));
      if(!plan.market && plan.level<=0.0) { plan.note="không tính được vùng limit"; return; }
      if(!plan.market && dir*(market-plan.level)<=0.0) { plan.market=true; plan.level=0.0; }
      const double base=(plan.market ? plan.ref : plan.level);
      plan.stop=base-dir*p.stop_atr*day.atr;
      plan.ok=true;
     }

   bool PlaceEntry()
     {
      if(!plan.ok) return true;
      const int dir=plan.dir;
      const double market=(dir==1 ? SymbolInfoDouble(sym,SYMBOL_ASK) : SymbolInfoDouble(sym,SYMBOL_BID));
      const bool at_market=(plan.market || dir*(market-plan.level)<=0.0);
      if(at_market)
        {
         const double ref=(plan.market ? plan.ref : plan.level);
         if(dir*(market-ref)>XRB_MAX_CHASE_ATR*day.atr)
           { plan.ok=false; plan.note=StringFormat("bỏ hôm nay: giá đã chạy %.2f ATR qua giá kế hoạch",dir*(market-ref)/day.atr); return true; }
         if(dir*(market-plan.stop)<=0.0) { plan.ok=false; plan.note="bỏ hôm nay: giá đã qua stop kế hoạch"; return true; }
        }
      const double price=(at_market ? market : plan.level);
      double risk_money=0.0;
      const double vol0=VolumeFor(dir,price,plan.stop,1.0,risk_money);
      string reason="";
      const double w=EntryGate(dir,price,plan.stop,risk_money,reason);
      if(w<=0.0) { plan.note="đang chờ: "+reason+", thử lại ở nến M5 sau"; return false; }
      if(!IsLive())
        {
         if(at_market) { v_open=true; v_dir=dir; v_entry=market; v_stop=plan.stop; best=market; be_done=false; entries++; plan.note="đã vào (ảo) market"; }
         else { v_pending=true; v_dir=dir; v_level=plan.level; v_stop=plan.stop; plan.note="limit (ảo) đang chờ"; }
         Save();
         return true;
        }
      const double vol=(w<1.0 ? VolumeFor(dir,price,plan.stop,w,risk_money) : vol0);
      if(vol<=0.0) { plan.ok=false; plan.note="bỏ hôm nay: khối lượng dưới mức tối thiểu"; return true; }
      bool ok;
      if(at_market)
        {
         ok=(dir==1 ? trade.Buy(vol,sym,0.0,NormalizeDouble(plan.stop,Digits()),0.0,"XRT")
                    : trade.Sell(vol,sym,0.0,NormalizeDouble(plan.stop,Digits()),0.0,"XRT"));
         if(ok && trade.ResultRetcode()==TRADE_RETCODE_DONE) { int d; OwnPosition(d); plan.note="đã vào market"; }
         else plan.note=StringFormat("broker từ chối lệnh market (mã %u)",trade.ResultRetcode());
        }
      else
        {
         const bool dated=((SymbolInfoInteger(sym,SYMBOL_EXPIRATION_MODE)&SYMBOL_EXPIRATION_SPECIFIED)!=0);
         const ENUM_ORDER_TYPE_TIME tt=(dated ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC);
         const datetime expiry=(dated ? (datetime)(iTime(sym,PERIOD_D1,0)+86400-60) : 0);
         ok=(dir==1 ? trade.BuyLimit(vol,NormalizeDouble(plan.level,Digits()),sym,NormalizeDouble(plan.stop,Digits()),0.0,tt,expiry,"XRT")
                    : trade.SellLimit(vol,NormalizeDouble(plan.level,Digits()),sym,NormalizeDouble(plan.stop,Digits()),0.0,tt,expiry,"XRT"));
         if(ok) { pending=trade.ResultOrder(); pending_level=plan.level; plan.note="limit đang chờ"; }
         else plan.note=StringFormat("broker từ chối lệnh limit (mã %u)",trade.ResultRetcode());
        }
      return true;
     }

   void OnNewDay()
     {
      if(pending!=0 || v_pending) DeletePending();
      if(!RefreshDay()) return;
      int dir=0;
      if(OwnPosition(dir))
        {
         best=(dir==1 ? MathMax(best,day.close) : MathMin(best,day.close));
         const double px=(dir==1 ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK));
         if(day.state!=dir) { CloseOwn("chế độ đổi",px); exits_regime++; }
         else if(p.trail && dir*(day.close-best)<=-p.trail_atr*day.atr) { CloseOwn("trail",px); exits_trail++; blocked_dir=dir; }
        }
      if(blocked_dir!=0 && day.state!=blocked_dir) blocked_dir=0;
      want_entry=!OwnPosition(dir);
      plan.ok=false; plan.note="";
      if(want_entry && p.mode!=BOT_OFF) MakePlan();
      Save();
     }

   void NewsBreakEven()
     {
      if(!IsLive() || ticket==0 || be_done || risk<=0.0 || !p.news_guard || !g_bot_guard.news_be_due) return;
      if(!PositionSelectByTicket(ticket)) return;
      const int d=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1);
      const double now=(d==1 ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK));
      if(d*(now-entry)/risk<p.news_be_min_r) return;
      const double spread=SymbolInfoDouble(sym,SYMBOL_ASK)-SymbolInfoDouble(sym,SYMBOL_BID);
      const double be=NormalizeDouble(entry+d*spread,Digits());
      const double sl=PositionGetDouble(POSITION_SL);
      if(d*(be-sl)<=0.0) { be_done=true; return; }
      if(trade.PositionModify(ticket,be,0.0)) { be_done=true; Save(); }
     }

   // SHADOW: virtual limit fill and virtual stop.
   void ShadowTick()
     {
      if(IsLive()) return;
      const double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      if(v_pending && ((v_dir==1 && ask<=v_level) || (v_dir==-1 && bid>=v_level)))
        { v_pending=false; v_open=true; v_entry=v_level; best=v_level; be_done=false; entries++; plan.note="limit (ảo) đã khớp"; Save(); }
      if(v_open && ((v_dir==1 && bid<=v_stop) || (v_dir==-1 && ask>=v_stop)))
        { v_realized_r+=-1.0; v_open=false; last_note="dừng ở stop (ảo)"; Save(); }
     }

   void OnTick()
     {
      if(p.mode==BOT_OFF) return;
      ShadowTick();
      const datetime d1=iTime(sym,PERIOD_D1,0);
      const datetime m5=iTime(sym,PERIOD_M5,0);
      // A new D1 bar, or a D1 refresh that failed (history still loading after a start): retried each new M5 bar.
      if(d1!=0 && (d1!=last_d1 || (!day.ok && m5!=last_m5))) { last_d1=d1; OnNewDay(); }
      if(m5==last_m5) return;
      last_m5=m5;
      int dir=0;
      OwnPosition(dir);
      NewsBreakEven();
      if(IsLive() && pending!=0)
        {
         if(!OrderSelect(pending)) pending=0;
         else if(p.news_guard && g_bot_guard.news_block_swing!="") { DeletePending(); blocked_news++; want_entry=true; }
        }
      if(want_entry && pending==0 && !v_pending && !OwnPosition(dir) && day.ok && plan.ok)
         if(PlaceEntry()) want_entry=false;
     }

   int OpenLegs() { int d=0; return OwnPosition(d) ? 1 : 0; }

   string StatusText()
     {
      if(p.mode==BOT_OFF) return "OFF";
      if(!day.ok) return "chưa đủ nến D1";
      const string st=(day.state==1 ? "TĂNG" : (day.state==-1 ? "GIẢM" : "TRUNG TÍNH"));
      int dir=0;
      string s="chế độ D1 "+st+" | ";
      if(OwnPosition(dir))
        {
         const double px=(dir==1 ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK));
         const double e=(IsLive() ? entry : v_entry), sl=(IsLive() ? stop : v_stop);
         const double r=(MathAbs(e-sl)>0.0 ? dir*(px-e)/MathAbs(e-sl) : 0.0);
         s+=StringFormat("%s%s vào %s, %s",PnlDir(dir),IsLive() ? "" : " (ảo)",PxT(e),PnlR(r));
        }
      else s+=(plan.note!="" ? plan.note : (last_note!="" ? last_note : "đứng ngoài"));
      return s;
     }
  };

#endif
