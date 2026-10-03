#ifndef ENTERPRISE_EA_CONFIG_MQH
#define ENTERPRISE_EA_CONFIG_MQH

#define EEA_SCHEMA_VERSION "1.0.0"

struct CEAConfig
  {
   string config_version;
   string source;
   string data_root;
   bool observer_only;
   string account_policy;
   string account_currency;
   double initial_capital;
   string policy_timezone;
   int daily_reset_hour;
   int daily_reset_minute;
   double safety_buffer;
   bool continue_after_daily_profit_target;
   bool continue_after_overall_profit_target;
  };

bool EAConfig_LoadDefaults(CEAConfig &c)
  {
   c.config_version="observer-v1.0.0";
   c.source="EA_CORE";
   c.data_root="EnterpriseEA";
   c.observer_only=true;
   c.account_policy="UNSELECTED";
   c.account_currency="";
   c.initial_capital=0.0;
   c.policy_timezone="";
   c.daily_reset_hour=-1;
   c.daily_reset_minute=-1;
   c.safety_buffer=0.0;
   c.continue_after_daily_profit_target=true;
   c.continue_after_overall_profit_target=true;
   return true;
  }

bool EAConfig_Validate(const CEAConfig &c)
  {
   if(c.config_version=="" || c.source=="" || c.data_root=="") return false;
   // Execution mode is validated by the EA shell's explicit live-profile
   // guard. This config validator must not make the non-observer profile
   // structurally impossible to start.
   if(c.account_policy!="UNSELECTED" && c.account_policy!="FTMO_1_STEP" &&
      c.account_policy!="FTMO_2_STEP" && c.account_policy!="BALANCE_BASED_FTMO_V1" &&
      c.account_policy!="CUSTOM") return false;
   if(c.initial_capital<0.0 || c.safety_buffer<0.0) return false;
   if(c.daily_reset_hour < -1 || c.daily_reset_hour > 23) return false;
   if(c.daily_reset_minute < -1 || c.daily_reset_minute > 59) return false;
   return true;
  }

#endif
