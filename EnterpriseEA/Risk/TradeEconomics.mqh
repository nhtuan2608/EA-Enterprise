#ifndef ENTERPRISE_EA_TRADE_ECONOMICS_MQH
#define ENTERPRISE_EA_TRADE_ECONOMICS_MQH

// Net reward/risk gate for a priced candidate. It never grants entry permission.
struct EEA_TradeEconomicsInput
  {
   string config_version;
   string account_currency;
   string quote_config_version;
   string quote_currency;
   string quote_quality;        // OK required
   string pricing_snapshot_id;
   bool loss_quote_valid;
   bool reward_quote_valid;
   bool target_space_confirmed;
   bool execution_constraints_confirmed; // caller checked spread, stops/freeze and quote age
   int direction;              // +1 BUY, -1 SELL
   double entry_reference;
   double stop_loss;
   double take_profit;
   double final_volume;
   double quote_volume;
   double net_loss_at_sl_money; // positive; includes costs/slippage allowance
   double net_gain_at_tp_money; // positive; after fees, swap estimate and target costs
   double minimum_net_rr;      // setup/profile threshold, no default
  };

struct EEA_TradeEconomicsResult
  {
   bool valid;
   string economics_status;    // UNKNOWN | REJECTED | ECONOMICS_ACCEPTABLE
   string reason_code;
   double net_reward_risk;
   double net_loss_at_sl_money;
   double net_gain_at_tp_money;
  };

void EEA_TradeEconomicsDefaults(EEA_TradeEconomicsResult &o)
  {
   o.valid=false;
   o.economics_status="UNKNOWN";
   o.reason_code="ECONOMICS_INPUT_UNKNOWN";
   o.net_reward_risk=0.0;
   o.net_loss_at_sl_money=0.0;
   o.net_gain_at_tp_money=0.0;
  }

bool EEA_CheckTradeEconomics(const EEA_TradeEconomicsInput &i,EEA_TradeEconomicsResult &o)
  {
   EEA_TradeEconomicsDefaults(o);
   if(i.config_version=="" || i.account_currency=="" ||
      i.quote_config_version!=i.config_version || i.quote_currency!=i.account_currency ||
      i.quote_quality!="OK" || i.pricing_snapshot_id=="" ||
      !i.loss_quote_valid || !i.reward_quote_valid ||
      !i.execution_constraints_confirmed)
     { o.reason_code="PRICING_OR_EXECUTION_EVIDENCE_MISSING"; return false; }
   if(i.direction!=1 && i.direction!=-1)
     { o.reason_code="INVALID_DIRECTION"; return false; }
   if(!MathIsValidNumber(i.entry_reference) || !MathIsValidNumber(i.stop_loss) ||
      !MathIsValidNumber(i.take_profit) || !MathIsValidNumber(i.final_volume) ||
      !MathIsValidNumber(i.quote_volume) || !MathIsValidNumber(i.net_loss_at_sl_money) ||
      !MathIsValidNumber(i.net_gain_at_tp_money) || !MathIsValidNumber(i.minimum_net_rr) ||
      i.entry_reference<=0.0 || i.stop_loss<=0.0 || i.take_profit<=0.0 ||
      i.final_volume<=0.0 || i.quote_volume!=i.final_volume ||
      i.net_loss_at_sl_money<=0.0 ||
      i.minimum_net_rr<=0.0)
     { o.reason_code="INVALID_ECONOMICS_INPUT"; return false; }
   if((i.direction==1 && !(i.stop_loss<i.entry_reference && i.entry_reference<i.take_profit)) ||
      (i.direction==-1 && !(i.take_profit<i.entry_reference && i.entry_reference<i.stop_loss)))
     { o.reason_code="INVALID_PRICE_GEOMETRY"; return false; }
   o.valid=true;
   o.net_loss_at_sl_money=i.net_loss_at_sl_money;
   o.net_gain_at_tp_money=i.net_gain_at_tp_money;
   o.net_reward_risk=i.net_gain_at_tp_money/i.net_loss_at_sl_money;
   if(!MathIsValidNumber(o.net_reward_risk))
     {
      EEA_TradeEconomicsDefaults(o);
      o.reason_code="ECONOMICS_CALCULATION_INVALID";
      return false;
     }
   if(!i.target_space_confirmed)
     { o.economics_status="REJECTED"; o.reason_code="TARGET_SPACE_INSUFFICIENT"; return true; }
   if(o.net_gain_at_tp_money<=0.0)
     { o.economics_status="REJECTED"; o.reason_code="NONPOSITIVE_NET_REWARD"; return true; }
   if(o.net_reward_risk<i.minimum_net_rr)
     { o.economics_status="REJECTED"; o.reason_code="NET_REWARD_RISK_BELOW_PROFILE_MINIMUM"; return true; }
   o.economics_status="ECONOMICS_ACCEPTABLE";
   o.reason_code="NET_REWARD_RISK_AND_TARGET_SPACE_ACCEPTABLE";
   return true;
  }

#endif
