#ifndef ENTERPRISE_EA_RISK_LIMITS_PROFILE_MQH
#define ENTERPRISE_EA_RISK_LIMITS_PROFILE_MQH

#include "FtmoHeadroom.mqh"

// O-04 internal risk limits, derived from the selected prop-firm policy so the
// internal stops always sit well inside the firm's loss floors:
//   internal_daily  = min(0.4 x firm daily loss, 2%)
//   per_trade       = internal_daily / 4      (four full losses reach the internal daily stop)
//   total_open      = internal_daily          (all open stops hit together stay within the day)
//   currency        = 2.5 x per_trade         (net exposure to one currency)
//   internal_weekly = min(2 x internal_daily, 0.4 x firm overall loss)
//   safety_buffer   = per_trade               (kept free above the FTMO floors)
// Every factor applied to a trade can only reduce risk; nothing raises it above per_trade.
#define EEA_RISK_LIMITS_VERSION "risk-limits-v1.0.0"

struct EEA_RiskLimits
  {
   string version;
   string policy_id;
   double firm_daily_fraction;
   double firm_overall_fraction;
   double internal_daily_fraction;
   double internal_weekly_fraction;
   double per_trade_fraction;
   double total_open_fraction;
   double currency_exposure_fraction;
   double safety_buffer_fraction;
   double htf_counter_trend_modifier;
   double min_margin_level_percent;
   int    max_correlated_trades;
  };

void EEA_RiskLimitsDefaults(EEA_RiskLimits &l)
  {
   l.version=EEA_RISK_LIMITS_VERSION; l.policy_id="";
   l.firm_daily_fraction=0.0; l.firm_overall_fraction=0.0;
   l.internal_daily_fraction=0.0; l.internal_weekly_fraction=0.0;
   l.per_trade_fraction=0.0; l.total_open_fraction=0.0;
   l.currency_exposure_fraction=0.0; l.safety_buffer_fraction=0.0;
   l.htf_counter_trend_modifier=0.5; l.min_margin_level_percent=300.0;
   l.max_correlated_trades=2;
  }

bool EEA_RiskLimitsForPolicy(const string policy_id,EEA_RiskLimits &l,string &reason)
  {
   EEA_RiskLimitsDefaults(l);
   double daily_percent=0.0,overall_percent=0.0;
   if(!EEA_FtmoPolicyRates(policy_id,daily_percent,overall_percent))
     { reason="RISK_LIMITS_POLICY_UNSELECTED"; return false; }
   l.policy_id=policy_id;
   l.firm_daily_fraction=daily_percent/100.0;
   l.firm_overall_fraction=overall_percent/100.0;
   l.internal_daily_fraction=MathMin(0.4*l.firm_daily_fraction,0.02);
   l.per_trade_fraction=l.internal_daily_fraction/4.0;
   l.total_open_fraction=l.internal_daily_fraction;
   l.currency_exposure_fraction=2.5*l.per_trade_fraction;
   l.internal_weekly_fraction=MathMin(2.0*l.internal_daily_fraction,0.4*l.firm_overall_fraction);
   l.safety_buffer_fraction=l.per_trade_fraction;
   reason="RISK_LIMITS_DERIVED";
   return true;
  }

// Risk money for one trade: equity-based, capped by the initial-capital cap, then
// reduced by the product of the trade's modifiers (each clamped to [0,1]).
double EEA_RiskLimitsTradeRiskMoney(const EEA_RiskLimits &l,const double equity,
                                    const double initial_capital,const double modifier)
  {
   if(!MathIsValidNumber(equity) || !MathIsValidNumber(initial_capital) || !MathIsValidNumber(modifier) ||
      equity<=0.0 || initial_capital<=0.0 || l.per_trade_fraction<=0.0) return 0.0;
   double bounded=MathMax(0.0,MathMin(1.0,modifier));
   return MathMin(l.per_trade_fraction*equity,l.per_trade_fraction*initial_capital)*bounded;
  }

#endif
