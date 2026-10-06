#ifndef ENTERPRISE_EA_POLICY_RULES_MQH
#define ENTERPRISE_EA_POLICY_RULES_MQH

// One description of an account's loss rules. FTMO 1-Step, FTMO 2-Step and the balance-based
// variant are presets of it; CUSTOM takes the numbers from the operator (G34).
//   daily_percent    daily loss allowance, percent of the initial capital
//   overall_percent  overall loss allowance, percent of the initial capital
//   trailing         false: floor = initial capital - overall allowance (FIXED)
//                    true : floor = high-water balance - overall allowance (TRAILING)
//   daily_from_equity false: daily floor starts from the balance at the daily reset
//                    true : from the equity at the daily reset (floating result included)
struct EEA_PolicyRules
  {
   double daily_percent;
   double overall_percent;
   bool   trailing;
   bool   daily_from_equity;
  };

void EEA_PolicyRulesDefaults(EEA_PolicyRules &r)
  {
   r.daily_percent=0.0; r.overall_percent=0.0; r.trailing=false; r.daily_from_equity=false;
  }

// The operator's CUSTOM numbers (EA inputs), set once at start; the runtime copies it into the policy.
EEA_PolicyRules g_custom_policy_rules={0.0,0.0,false,false};

// G42: risk per trade the operator asks for during an evaluation phase (fraction of the initial
// capital, 0 = derive it from the policy). Capped, and every other internal limit follows it.
#define EEA_RISK_OVERRIDE_CAP 0.015
double g_risk_per_trade_override=0.0;

bool EEA_PolicyRulesValid(const EEA_PolicyRules &r)
  {
   return MathIsValidNumber(r.daily_percent) && MathIsValidNumber(r.overall_percent) &&
          r.daily_percent>0.0 && r.daily_percent<=r.overall_percent && r.overall_percent<=100.0;
  }

bool EEA_PolicyIsPreset(const string policy_id)
  {
   return policy_id=="FTMO_1_STEP" || policy_id=="FTMO_2_STEP" || policy_id=="BALANCE_BASED_FTMO_V1";
  }

// Resolves the rules of a policy id. Presets ignore `custom`; CUSTOM needs valid custom numbers.
bool EEA_PolicyRulesResolve(const string policy_id,const EEA_PolicyRules &custom,EEA_PolicyRules &r)
  {
   EEA_PolicyRulesDefaults(r);
   if(policy_id=="FTMO_1_STEP")
     { r.daily_percent=3.0; r.overall_percent=10.0; r.trailing=true; return true; }
   if(policy_id=="FTMO_2_STEP" || policy_id=="BALANCE_BASED_FTMO_V1")
     { r.daily_percent=5.0; r.overall_percent=10.0; return true; }
   if(policy_id=="CUSTOM")
     {
      if(!EEA_PolicyRulesValid(custom)) return false;
      r=custom;
      return true;
     }
   return false;
  }

// What a signed live session carries as its risk policy. Presets keep their plain id, so existing
// sessions stay valid; CUSTOM includes the numbers, so changing any of them voids the session.
string EEA_PolicySignedId(const string policy_id)
  {
   if(policy_id!="CUSTOM") return policy_id;
   return "CUSTOM:d="+DoubleToString(g_custom_policy_rules.daily_percent,4)+
          ";o="+DoubleToString(g_custom_policy_rules.overall_percent,4)+
          ";t="+(g_custom_policy_rules.trailing ? "1" : "0")+
          ";e="+(g_custom_policy_rules.daily_from_equity ? "1" : "0");
  }

#endif
