#ifndef ENTERPRISE_EA_DAILY_RESET_LEDGER_MQH
#define ENTERPRISE_EA_DAILY_RESET_LEDGER_MQH

// Pure policy reset ledger. Caller verifies Europe/Prague midnight and DST.
// No clock, broker, history, file or order APIs are used here.
struct EEA_DailyResetPolicy
  {
   string policy_id;       // FTMO_1_STEP | FTMO_2_STEP
   string config_version;
   string account_epoch_id;
   string account_currency;
   double initial_capital;
  };

struct EEA_DailyResetInput
  {
   string config_version;
   string account_epoch_id;
   string account_currency;
   string snapshot_id;
   string prague_day_id;   // local YYYY-MM-DD, caller-attested
   int day_index;          // 0 on confirmed first day, then contiguous +1
   datetime reset_at_utc;
   bool prague_midnight_confirmed;
   string data_quality;    // OK required
   double balance_at_reset;
  };

struct EEA_DailyResetState
  {
   string policy_id;
   string config_version;
   string account_epoch_id;
   string account_currency;
   double initial_capital;
   string status;          // UNKNOWN | OK
   string reason_code;
   string snapshot_id;
   string prague_day_id;
   int day_index;
   datetime reset_at_utc;
   double balance_at_reset;
   double highest_reset_balance;
   double daily_floor;
   double overall_floor;
  };

bool EEA_DailyResetInit(const EEA_DailyResetPolicy &p,EEA_DailyResetState &s)
  {
   s.policy_id=p.policy_id;
   s.config_version=p.config_version;
   s.account_epoch_id=p.account_epoch_id;
   s.account_currency=p.account_currency;
   s.initial_capital=p.initial_capital;
   s.status="UNKNOWN";
   s.reason_code="FIRST_RESET_SNAPSHOT_REQUIRED";
   s.snapshot_id="";
   s.prague_day_id="";
   s.day_index=-1;
   s.reset_at_utc=0;
   s.balance_at_reset=0.0;
   s.highest_reset_balance=0.0;
   s.daily_floor=0.0;
   s.overall_floor=0.0;
   return (p.policy_id=="FTMO_1_STEP" || p.policy_id=="FTMO_2_STEP") &&
          p.config_version!="" && p.account_epoch_id!="" &&
          p.account_currency!="" && MathIsValidNumber(p.initial_capital) &&
          p.initial_capital>0.0;
  }

bool EEA_DailyResetApply(EEA_DailyResetState &s,const EEA_DailyResetInput &i)
  {
   if((s.policy_id!="FTMO_1_STEP" && s.policy_id!="FTMO_2_STEP") ||
      s.config_version=="" || s.account_epoch_id=="" || s.account_currency=="" ||
      !MathIsValidNumber(s.initial_capital) || s.initial_capital<=0.0 ||
      i.config_version!=s.config_version || i.account_epoch_id!=s.account_epoch_id ||
      i.account_currency!=s.account_currency)
     { s.status="UNKNOWN"; s.reason_code="RESET_POLICY_OR_EPOCH_MISMATCH"; return false; }
   if(i.snapshot_id=="" || i.prague_day_id=="" || i.day_index<0 || i.reset_at_utc<=0 ||
      !i.prague_midnight_confirmed || i.data_quality!="OK" ||
      !MathIsValidNumber(i.balance_at_reset))
     { s.status="UNKNOWN"; s.reason_code="RESET_SNAPSHOT_MISSING_OR_UNTRUSTED"; return false; }
   if(s.day_index==i.day_index)
     {
      if(s.snapshot_id==i.snapshot_id && s.prague_day_id==i.prague_day_id &&
         s.reset_at_utc==i.reset_at_utc && s.balance_at_reset==i.balance_at_reset)
        { s.reason_code="DUPLICATE_RESET_IGNORED"; return s.status=="OK"; }
      s.status="UNKNOWN"; s.reason_code="CONFLICTING_RESET_SNAPSHOT"; return false;
     }
   if(i.day_index!=s.day_index+1 ||
      (s.day_index>=0 && (i.reset_at_utc<=s.reset_at_utc ||
                          i.prague_day_id<=s.prague_day_id)))
     { s.status="UNKNOWN"; s.reason_code="RESET_SEQUENCE_GAP_OR_OUT_OF_ORDER"; return false; }
   if(s.day_index==-1 && i.balance_at_reset!=s.initial_capital)
     { s.status="UNKNOWN"; s.reason_code="FIRST_DAY_BALANCE_NOT_INITIAL"; return false; }

   double high=(s.day_index==-1 ? s.initial_capital : s.highest_reset_balance);
   if(s.policy_id=="FTMO_1_STEP") high=MathMax(high,i.balance_at_reset);
   double daily_percent=(s.policy_id=="FTMO_1_STEP" ? 3.0 : 5.0);
   double daily_floor=i.balance_at_reset-s.initial_capital*daily_percent/100.0;
   double overall_floor=(s.policy_id=="FTMO_1_STEP" ? high : s.initial_capital)-
                        s.initial_capital*0.10;
   if(!MathIsValidNumber(high) || !MathIsValidNumber(daily_floor) ||
      !MathIsValidNumber(overall_floor))
     { s.status="UNKNOWN"; s.reason_code="RESET_FLOOR_CALCULATION_INVALID"; return false; }
   s.snapshot_id=i.snapshot_id;
   s.prague_day_id=i.prague_day_id;
   s.day_index=i.day_index;
   s.reset_at_utc=i.reset_at_utc;
   s.balance_at_reset=i.balance_at_reset;
   s.highest_reset_balance=high;
   s.daily_floor=daily_floor;
   s.overall_floor=overall_floor;
   s.status="OK";
   s.reason_code="RESET_FLOORS_CALCULATED";
   return true;
  }

#endif
