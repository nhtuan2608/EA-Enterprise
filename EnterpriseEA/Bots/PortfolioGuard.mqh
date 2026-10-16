#ifndef ENTERPRISE_EA_BOT_PORTFOLIO_GUARD_MQH
#define ENTERPRISE_EA_BOT_PORTFOLIO_GUARD_MQH

// Bots host: one account-wide guard in front of every bot entry or risk increase. The EA shell
// fills g_bot_guard each timer (and the host refreshes the equity part each tick); a bot asks
// EEA_BotGuardCheck() before it sends an order. Reasons are stable codes for the panel and logs.
//   1 the bot is Active (new entries only; an add of an open group is management)
//   2 the EA execution path is armed (InpExecutionEnabled, InpLiveTradeArmed, not observer-only, no recovery block)
//   3 no operator /pause
//   4 the day's loss (equity vs the server-day start) is below InpBotsDailyLossPct of the capital
//   5 account-wide open risk (every position and pending order, every magic) + this order <= InpBotsMaxOpenRiskPct
//   6 no HIGH-impact news block for the symbol (EnterpriseEA News Guard), when the bot uses it (use_news)

#include "BotState.mqh"
#include "BotJournal.mqh"

struct EEA_BotGuardContext
  {
   bool   ready;
   bool   execution_live;
   bool   operator_paused;
   double capital;                // risk basis (initial capital, INITIAL as S07)
   double daily_loss_pct;
   double max_open_risk_pct;
   bool   news_guard;             // InpBotsNewsGuard: the VHedge module's News Guard switch
   string news_block_scalp;       // "" = no block (EnterpriseEA News Guard, SCALP profile)
   string news_block_swing;       // (SWING profile)
   bool   news_be_due;            // break-even before a HIGH USD event is due (EnterpriseEA News Guard)
   double sent_factor[2];         // EnterpriseEA sentiment, SWING profile: [0] buy, [1] sell (1 = neutral)
   bool   sent_block[2];          // strongly against: no SWING entry
   int    day_key;                // server day of the equity anchor
   double day_start_equity;
  };

EEA_BotGuardContext g_bot_guard;

void EEA_BotGuardDefaults(EEA_BotGuardContext &g)
  {
   g.ready=false; g.execution_live=false; g.operator_paused=true; g.capital=0.0; g.daily_loss_pct=0.0;
   g.max_open_risk_pct=0.0; g.news_guard=true; g.news_block_scalp="NEWS_GUARD_NOT_READY";
   g.news_block_swing="NEWS_GUARD_NOT_READY"; g.day_key=0; g.day_start_equity=0.0; g.news_be_due=false;
   g.sent_factor[0]=1.0; g.sent_factor[1]=1.0; g.sent_block[0]=false; g.sent_block[1]=false;
  }

// The server day anchors the daily loss; the first call of a new day takes the equity then.
void EEA_BotGuardRollDay(EEA_BotGuardContext &g)
  {
   const int day=(int)(TimeTradeServer()/86400);
   if(day!=g.day_key || g.day_start_equity<=0.0)
     { g.day_key=day; g.day_start_equity=AccountInfoDouble(ACCOUNT_EQUITY); }
  }

// Money lost if every stop on the account is hit, from the current price for positions and from the
// order price for pending orders. A position or order without a stop fails closed.
bool EEA_BotsAccountOpenRisk(double &risk,string &reason)
  {
   risk=0.0; reason="";
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong t=PositionGetTicket(i);
      if(t==0 || !PositionSelectByTicket(t)) continue;
      const string sym=PositionGetString(POSITION_SYMBOL);
      const double sl=PositionGetDouble(POSITION_SL), vol=PositionGetDouble(POSITION_VOLUME);
      const bool buy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      if(sl<=0.0) { reason="BOTS_POSITION_WITHOUT_STOP"; return false; }
      const double from=(buy ? SymbolInfoDouble(sym,SYMBOL_BID) : SymbolInfoDouble(sym,SYMBOL_ASK));
      if((buy && sl>=from) || (!buy && sl<=from)) continue;              // stop already in profit
      double pnl=0.0;
      if(!OrderCalcProfit(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,vol,from,sl,pnl)) { reason="BOTS_RISK_CALC_FAILED"; return false; }
      if(pnl<0.0) risk+=-pnl;
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong t=OrderGetTicket(i);
      if(t==0 || !OrderSelect(t)) continue;
      const ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type!=ORDER_TYPE_BUY_LIMIT && type!=ORDER_TYPE_SELL_LIMIT && type!=ORDER_TYPE_BUY_STOP &&
         type!=ORDER_TYPE_SELL_STOP && type!=ORDER_TYPE_BUY_STOP_LIMIT && type!=ORDER_TYPE_SELL_STOP_LIMIT) continue;
      const string sym=OrderGetString(ORDER_SYMBOL);
      const double sl=OrderGetDouble(ORDER_SL), price=OrderGetDouble(ORDER_PRICE_OPEN);
      const double vol=OrderGetDouble(ORDER_VOLUME_CURRENT);
      const bool buy=(type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT);
      if(sl<=0.0) { reason="BOTS_ORDER_WITHOUT_STOP"; return false; }
      double pnl=0.0;
      if(!OrderCalcProfit(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,vol,price,sl,pnl)) { reason="BOTS_RISK_CALC_FAILED"; return false; }
      if(pnl<0.0) risk+=-pnl;
     }
   return true;
  }

// new_risk_money: the money lost at the stop of the order being considered.
// require_active=false for a risk increase inside an open group (management of an Inactive bot).
string EEA_BotGuardCheck(const int bot,const double new_risk_money,const string profile,const bool require_active,
                         const bool use_news)
  {
   const EEA_BotGuardContext g=g_bot_guard;
   if(!g.ready) return "BOTS_GUARD_NOT_READY";
   if(require_active && !EEA_BotActive(bot)) return "BOT_INACTIVE";
   if(!g.execution_live) return "EA_EXECUTION_NOT_ARMED";
   if(g.operator_paused) return "OPERATOR_PAUSED_ENTRIES";
   if(g.capital<=0.0) return "BOTS_CAPITAL_UNKNOWN";
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(g.daily_loss_pct>0.0 && g.day_start_equity>0.0 && g.day_start_equity-equity>=g.daily_loss_pct/100.0*g.capital)
      return "BOTS_DAILY_LOSS_LIMIT";
   double open_risk=0.0; string reason="";
   if(!EEA_BotsAccountOpenRisk(open_risk,reason)) return reason;
   if(g.max_open_risk_pct>0.0 && open_risk+MathMax(new_risk_money,0.0)>g.max_open_risk_pct/100.0*g.capital)
      return "BOTS_OPEN_RISK_CAP";
   if(use_news)
     {
      const string block=(profile=="SWING" ? g.news_block_swing : g.news_block_scalp);
      if(block!="") return block;
     }
   return "";
  }

#endif
