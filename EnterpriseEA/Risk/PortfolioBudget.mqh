#ifndef ENTERPRISE_EA_PORTFOLIO_BUDGET_MQH
#define ENTERPRISE_EA_PORTFOLIO_BUDGET_MQH

// Account-wide pre-sizing budget only. Inputs are supplied by a trusted reconciler.
// BUDGET_AVAILABLE is never an order or entry permission.
struct EEA_PortfolioBudgetInputs
  {
   string config_version;
   string account_currency;
   string data_quality;             // OK required
   string account_scope;            // ACCOUNT_WIDE required
   string reconciliation_status;    // RECONCILED required
   bool policy_floor_calculation_valid;
   string policy_headroom_quality;  // OK required
   string policy_config_version;
   string policy_headroom_currency;
   bool external_orders_included;
   bool account_mode_reconciled;
   bool portfolio_limits_confirmed;
   double equity_after_costs;
   double base_risk_fraction;
   double per_trade_cap_money;
   double portfolio_remaining_money;
   double policy_headroom_after_buffer_money;
   double existing_stress_loss_money;
  };

struct EEA_PortfolioBudgetResult
  {
   bool valid;
   string budget_status;  // UNKNOWN | BLOCK | BUDGET_AVAILABLE
   string reason_code;
   double base_risk_money;
   double floor_remaining_money;
   double budget_money;
  };

void EEA_PortfolioBudgetDefaults(EEA_PortfolioBudgetResult &o)
  {
   o.valid=false;
   o.budget_status="UNKNOWN";
   o.reason_code="PORTFOLIO_DATA_UNKNOWN";
   o.base_risk_money=0.0;
   o.floor_remaining_money=0.0;
   o.budget_money=0.0;
  }

bool EEA_CalculatePortfolioBudget(const EEA_PortfolioBudgetInputs &i,EEA_PortfolioBudgetResult &o)
  {
   EEA_PortfolioBudgetDefaults(o);
   if(i.config_version=="" || i.account_currency=="" || i.data_quality!="OK" ||
      i.account_scope!="ACCOUNT_WIDE" || i.reconciliation_status!="RECONCILED" ||
      !i.policy_floor_calculation_valid || i.policy_headroom_quality!="OK" ||
      i.policy_config_version!=i.config_version ||
      i.policy_headroom_currency!=i.account_currency || !i.external_orders_included ||
      !i.account_mode_reconciled || !i.portfolio_limits_confirmed)
     { o.reason_code="ACCOUNT_WIDE_EVIDENCE_INCOMPLETE"; return false; }
   if(!MathIsValidNumber(i.equity_after_costs) || i.equity_after_costs<=0.0 ||
      !MathIsValidNumber(i.base_risk_fraction) || i.base_risk_fraction<=0.0 ||
      i.base_risk_fraction>1.0 || !MathIsValidNumber(i.per_trade_cap_money) ||
      i.per_trade_cap_money<0.0 || !MathIsValidNumber(i.portfolio_remaining_money) ||
      i.portfolio_remaining_money<0.0 ||
      !MathIsValidNumber(i.policy_headroom_after_buffer_money) ||
      i.policy_headroom_after_buffer_money<0.0 ||
      !MathIsValidNumber(i.existing_stress_loss_money) ||
      i.existing_stress_loss_money<0.0)
     { o.reason_code="INVALID_BUDGET_INPUT"; return false; }

   o.base_risk_money=i.equity_after_costs*i.base_risk_fraction;
   o.floor_remaining_money=i.policy_headroom_after_buffer_money-i.existing_stress_loss_money;
   o.budget_money=MathMax(0.0,MathMin(MathMin(o.base_risk_money,i.per_trade_cap_money),
                                      MathMin(i.portfolio_remaining_money,o.floor_remaining_money)));
   if(!MathIsValidNumber(o.base_risk_money) || !MathIsValidNumber(o.floor_remaining_money) ||
      !MathIsValidNumber(o.budget_money))
     {
      EEA_PortfolioBudgetDefaults(o);
      o.reason_code="BUDGET_CALCULATION_INVALID";
      return false;
     }
   o.valid=true;
   if(o.budget_money<=0.0)
     { o.budget_status="BLOCK"; o.reason_code="NO_REMAINING_RISK_BUDGET"; return true; }
   o.budget_status="BUDGET_AVAILABLE";
   o.reason_code="PRE_SIZING_BUDGET_CALCULATED";
   return true;
  }

#endif
