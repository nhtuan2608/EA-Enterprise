#ifndef ENTERPRISE_EA_FTMO_HEADROOM_MQH
#define ENTERPRISE_EA_FTMO_HEADROOM_MQH

// Pure arithmetic for policy-floor headroom. No terminal, broker, calendar, or order APIs.
// The default policy is unselected. This module is intentionally not included by the EA shell.

#include "PolicyRules.mqh"

struct EEA_FtmoPolicy
  {
   string policy_id;             // UNSELECTED | FTMO_1_STEP | FTMO_2_STEP | BALANCE_BASED_FTMO_V1 | CUSTOM
   string status;                // UNSELECTED | ACTIVE | POLICY_DATA_UNKNOWN
   string config_version;
   string source_version;
   string source_reference;
   string policy_timezone;
   string account_currency;
   double initial_capital;
   double safety_buffer_money;
   bool continue_after_daily_profit_target;
   bool continue_after_overall_profit_target;
   EEA_PolicyRules custom_rules;  // used only when policy_id is CUSTOM
  };

struct EEA_FtmoInputs
  {
   string daily_snapshot_config_version;
   string daily_snapshot_currency;
   string daily_snapshot_quality;  // OK required; STALE/DEGRADED/UNKNOWN fail closed
   string daily_snapshot_id;
   datetime daily_reset_at_utc;
   bool daily_snapshot_valid;
   bool reset_window_confirmed_by_caller;
   double balance_at_daily_reset;
   double equity_at_daily_reset;   // needed when the rules start the daily floor from equity (CUSTOM)
   double current_balance;
   double floating_pnl_after_costs;
   double proposed_stress_loss;
   string stress_loss_currency;
   bool high_water_snapshot_valid;
   string high_water_snapshot_quality;
   string high_water_config_version;
   datetime high_water_as_of_utc;
   double prior_overall_high_water_balance;
  };

struct EEA_FtmoHeadroom
  {
   bool calculation_valid;
   string calculation_status; // OK | POLICY_DATA_UNKNOWN
   string headroom_status;    // SUFFICIENT | REDUCE_OR_WAIT | BLOCK_NEW_ENTRY | POLICY_DATA_UNKNOWN
   string reason_code;
   string policy_id;
   string config_version;
   string source_version;
   string snapshot_id;
   datetime daily_reset_at_utc;
   double equity_after_costs;
   double daily_loss_amount;
   double daily_floor;
   double overall_floor;
   double overall_high_water_balance;
   double daily_floor_headroom;
   double overall_floor_headroom;
   double available_headroom;
   double proposed_stress_loss;
   double stress_equity;
   double post_stress_available_headroom;
  };

void EEA_FtmoPolicyDefaults(EEA_FtmoPolicy &p)
  {
   p.policy_id="UNSELECTED";
   p.status="UNSELECTED";
   p.config_version="";
   p.source_version="";
   p.source_reference="";
   p.policy_timezone="";
   p.account_currency="";
   p.initial_capital=0.0;
   p.safety_buffer_money=0.0;
   p.continue_after_daily_profit_target=true;
   p.continue_after_overall_profit_target=true;
   EEA_PolicyRulesDefaults(p.custom_rules);
  }

void EEA_FtmoInputDefaults(EEA_FtmoInputs &i)
  {
   i.daily_snapshot_config_version="";
   i.daily_snapshot_currency="";
   i.daily_snapshot_quality="UNKNOWN";
   i.daily_snapshot_id="";
   i.daily_reset_at_utc=0;
   i.daily_snapshot_valid=false;
   i.reset_window_confirmed_by_caller=false;
   i.balance_at_daily_reset=0.0;
   i.equity_at_daily_reset=0.0;
   i.current_balance=0.0;
   i.floating_pnl_after_costs=0.0;
   i.proposed_stress_loss=0.0;
   i.stress_loss_currency="";
   i.high_water_snapshot_valid=false;
   i.high_water_snapshot_quality="UNKNOWN";
   i.high_water_config_version="";
   i.high_water_as_of_utc=0;
   i.prior_overall_high_water_balance=0.0;
  }

void EEA_FtmoHeadroomDefaults(EEA_FtmoHeadroom &o)
  {
   o.calculation_valid=false;
   o.calculation_status="POLICY_DATA_UNKNOWN";
   o.headroom_status="POLICY_DATA_UNKNOWN";
   o.reason_code="POLICY_DATA_UNKNOWN";
   o.policy_id="UNSELECTED";
   o.config_version="";
   o.source_version="";
   o.snapshot_id="";
   o.daily_reset_at_utc=0;
   o.equity_after_costs=0.0;
   o.daily_loss_amount=0.0;
   o.daily_floor=0.0;
   o.overall_floor=0.0;
   o.overall_high_water_balance=0.0;
   o.daily_floor_headroom=0.0;
   o.overall_floor_headroom=0.0;
   o.available_headroom=0.0;
   o.proposed_stress_loss=0.0;
   o.stress_equity=0.0;
   o.post_stress_available_headroom=0.0;
  }

bool EEA_FtmoPolicyRates(const string policy_id,double &daily_percent,double &overall_percent)
  {
   EEA_PolicyRules none,r;
   EEA_PolicyRulesDefaults(none);
   daily_percent=0.0;
   overall_percent=0.0;
   if(!EEA_PolicyIsPreset(policy_id) || !EEA_PolicyRulesResolve(policy_id,none,r)) return false;
   daily_percent=r.daily_percent;
   overall_percent=r.overall_percent;
   return true;
  }

bool EEA_FtmoCalculate(const EEA_FtmoPolicy &p,const EEA_FtmoInputs &i,EEA_FtmoHeadroom &o)
  {
   EEA_FtmoHeadroomDefaults(o);
   o.policy_id=p.policy_id;
   o.config_version=p.config_version;
   o.source_version=p.source_version;
   o.snapshot_id=i.daily_snapshot_id;
   o.daily_reset_at_utc=i.daily_reset_at_utc;

   if(p.status!="ACTIVE" || (!EEA_PolicyIsPreset(p.policy_id) && p.policy_id!="CUSTOM"))
     { o.reason_code="POLICY_NOT_SELECTED_OR_UNSUPPORTED"; return false; }
   if(p.config_version=="" || p.source_version=="" || p.source_reference=="" ||
      p.policy_timezone!="Europe/Prague" || p.account_currency=="" ||
      !MathIsValidNumber(p.initial_capital) || p.initial_capital<=0.0 ||
      !MathIsValidNumber(p.safety_buffer_money) || p.safety_buffer_money<0.0)
     { o.reason_code="POLICY_CONFIGURATION_INCOMPLETE"; return false; }
   if(!i.daily_snapshot_valid || i.daily_snapshot_quality!="OK" || !i.reset_window_confirmed_by_caller ||
      i.daily_reset_at_utc<=0 || i.daily_snapshot_id=="" ||
      i.daily_snapshot_config_version!=p.config_version ||
      i.daily_snapshot_currency!=p.account_currency ||
      !MathIsValidNumber(i.balance_at_daily_reset))
     { o.reason_code="DAILY_RESET_SNAPSHOT_MISSING_OR_MISMATCHED"; return false; }
   if(i.daily_reset_at_utc<=0 || !MathIsValidNumber(i.current_balance) ||
      !MathIsValidNumber(i.floating_pnl_after_costs) ||
      !MathIsValidNumber(i.proposed_stress_loss) || i.proposed_stress_loss<=0.0 ||
      i.stress_loss_currency!=p.account_currency)
     { o.reason_code="CURRENT_EQUITY_OR_STRESS_INPUT_INVALID"; return false; }

   EEA_PolicyRules rules;
   if(!EEA_PolicyRulesResolve(p.policy_id,p.custom_rules,rules))
     { o.reason_code="POLICY_RULESET_UNSUPPORTED"; return false; }
   double daily_reference=i.balance_at_daily_reset;
   if(rules.daily_from_equity)
     {
      if(!MathIsValidNumber(i.equity_at_daily_reset) || i.equity_at_daily_reset<=0.0)
        { o.reason_code="DAILY_RESET_EQUITY_MISSING"; return false; }
      daily_reference=i.equity_at_daily_reset;
     }
   double high_water=p.initial_capital;
   if(rules.trailing)
     {
      if(!i.high_water_snapshot_valid || i.high_water_snapshot_quality!="OK" ||
         i.high_water_config_version!=p.config_version ||
         i.high_water_as_of_utc<=0 || i.high_water_as_of_utc>i.daily_reset_at_utc ||
         !MathIsValidNumber(i.prior_overall_high_water_balance) ||
         i.prior_overall_high_water_balance<p.initial_capital)
        { o.reason_code="TRAILING_HIGH_WATER_SNAPSHOT_MISSING_OR_INVALID"; return false; }
      high_water=MathMax(p.initial_capital,MathMax(i.prior_overall_high_water_balance,i.balance_at_daily_reset));
     }

   o.equity_after_costs=i.current_balance+i.floating_pnl_after_costs;
   o.daily_loss_amount=p.initial_capital*rules.daily_percent/100.0;
   o.daily_floor=daily_reference-o.daily_loss_amount;
   o.overall_high_water_balance=high_water;
   o.overall_floor=(rules.trailing ? high_water : p.initial_capital)-
                   p.initial_capital*rules.overall_percent/100.0;
   o.daily_floor_headroom=o.equity_after_costs-o.daily_floor;
   o.overall_floor_headroom=o.equity_after_costs-o.overall_floor;
   o.available_headroom=MathMin(o.daily_floor_headroom,o.overall_floor_headroom)-p.safety_buffer_money;
   o.proposed_stress_loss=i.proposed_stress_loss;
   o.stress_equity=o.equity_after_costs-i.proposed_stress_loss;
   o.post_stress_available_headroom=o.available_headroom-i.proposed_stress_loss;

   if(!MathIsValidNumber(o.equity_after_costs) || !MathIsValidNumber(o.daily_loss_amount) ||
      !MathIsValidNumber(o.daily_floor) || !MathIsValidNumber(o.overall_floor) ||
      !MathIsValidNumber(o.overall_high_water_balance) || !MathIsValidNumber(o.daily_floor_headroom) ||
      !MathIsValidNumber(o.overall_floor_headroom) || !MathIsValidNumber(o.available_headroom) ||
      !MathIsValidNumber(o.stress_equity) || !MathIsValidNumber(o.post_stress_available_headroom))
     {
      o.reason_code="CALCULATION_OVERFLOW_OR_INVALID_RESULT";
      return false;
     }
   o.calculation_valid=true;
   o.calculation_status="OK";
   o.reason_code="POLICY_FLOORS_AND_HEADROOM_CALCULATED";

   if(o.daily_floor_headroom<=0.0 || o.overall_floor_headroom<=0.0 || o.available_headroom<=0.0)
     { o.headroom_status="BLOCK_NEW_ENTRY"; o.reason_code="FLOOR_OR_SAFETY_BUFFER_EXHAUSTED"; }
   else if(o.proposed_stress_loss>=o.available_headroom)
     { o.headroom_status="REDUCE_OR_WAIT"; o.reason_code=(o.proposed_stress_loss==o.available_headroom ?
        "STRESS_LOSS_CONSUMES_AVAILABLE_HEADROOM" : "STRESS_LOSS_EXCEEDS_AVAILABLE_HEADROOM"); }
   else
     { o.headroom_status="SUFFICIENT"; o.reason_code="STRESS_LOSS_WITHIN_AVAILABLE_HEADROOM"; }
   return true;
  }

#endif
