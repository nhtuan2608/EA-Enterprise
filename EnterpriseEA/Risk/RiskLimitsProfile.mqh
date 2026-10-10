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
   EEA_PolicyRules rules;
   if(!EEA_PolicyRulesResolve(policy_id,g_custom_policy_rules,rules))
     { reason="RISK_LIMITS_POLICY_UNSELECTED"; return false; }
   l.policy_id=policy_id;
   l.firm_daily_fraction=rules.daily_percent/100.0;
   l.firm_overall_fraction=rules.overall_percent/100.0;
   l.internal_daily_fraction=MathMin(0.4*l.firm_daily_fraction,0.02);
   l.per_trade_fraction=l.internal_daily_fraction/4.0;
   l.total_open_fraction=l.internal_daily_fraction;
   l.currency_exposure_fraction=2.5*l.per_trade_fraction;
   l.internal_weekly_fraction=MathMin(2.0*l.internal_daily_fraction,0.4*l.firm_overall_fraction);
   l.safety_buffer_fraction=l.per_trade_fraction;
   if(g_risk_per_trade_override>0.0)
     {
      // Evaluation phase (G42): the same ratios as the derived set (open 4x, day 4x, week 8x the risk of
      // one trade) around the requested risk, but never beyond 80% of the firm's daily / overall
      // allowance, and one trade never above half the internal daily limit.
      const double day_ceiling=0.8*l.firm_daily_fraction;
      const double p=MathMin(MathMin(g_risk_per_trade_override,EEA_RISK_OVERRIDE_CAP),0.5*day_ceiling);
      l.per_trade_fraction=p;
      l.internal_daily_fraction=MathMin(4.0*p,day_ceiling);
      l.total_open_fraction=l.internal_daily_fraction;
      l.currency_exposure_fraction=2.5*p;
      l.internal_weekly_fraction=MathMin(2.0*l.internal_daily_fraction,0.8*l.firm_overall_fraction);
      l.safety_buffer_fraction=p;
      reason="RISK_LIMITS_EVALUATION_OVERRIDE";
      return true;
     }
   reason="RISK_LIMITS_DERIVED";
   return true;
  }

// G43/G44: risk weight by setup (mean / variance of the research results, 2010-2016, scaled so the
// largest is 1). A weight only lowers the risk of one trade; 0 means the setup takes no live risk.
double g_risk_weight_s04=1.0;
double g_risk_weight_s06b=1.0;
double g_risk_weight_t2=1.0;
double g_risk_weight_s07a=1.0;          // G87: S07A adds (research G86: 1.0% of the 1.5% base risk)
double g_s07_unordered_weight=1.0;      // G87: S07 base without the ordered-ribbon label

double EEA_SetupRiskWeight(const string setup)
  {
   double w=1.0;
   if(setup=="S04") w=g_risk_weight_s04;
   else if(setup=="S06B") w=g_risk_weight_s06b;
   else if(setup=="T2") w=g_risk_weight_t2;
   else if(setup=="S07A") w=g_risk_weight_s07a;
   if(!MathIsValidNumber(w)) return 0.0;
   return MathMax(0.0,MathMin(1.0,w));
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
