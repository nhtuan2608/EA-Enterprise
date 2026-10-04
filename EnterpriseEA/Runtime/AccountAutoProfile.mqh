#ifndef ENTERPRISE_EA_ACCOUNT_AUTO_PROFILE_MQH
#define ENTERPRISE_EA_ACCOUNT_AUTO_PROFILE_MQH

#include "RuntimeEvidence.mqh"

// Plan step 4: account and instrument facts derived from the broker so the operator
// does not type lot sizes, pip values, reset balances or cost assumptions.
// Pure helpers take reconciled snapshots; the few broker reads are marked.

// ---------------------------------------------------------------------------
// Europe/Prague trading day (FTMO daily reset). EU rule: summer time runs from the
// last Sunday of March 01:00 UTC to the last Sunday of October 01:00 UTC.
// ---------------------------------------------------------------------------
long EEA_AutoCivilDays(int y,const int m,const int d)
  {
   y-=m<=2 ? 1 : 0;
   int era=(y>=0 ? y : y-399)/400;
   int yoe=y-era*400;
   int mp=m+(m>2 ? -3 : 9);
   int doy=(153*mp+2)/5+d-1;
   int doe=yoe*365+yoe/4-yoe/100+doy;
   return (long)era*146097+doe-719468;
  }

long EEA_AutoLastSundayUtc(const int year,const int month)
  {
   int next_year=month==12 ? year+1 : year, next_month=month==12 ? 1 : month+1;
   long last_day=EEA_AutoCivilDays(next_year,next_month,1)-1;
   long weekday=(last_day+4)%7; // 0 = Sunday; 1970-01-01 was a Thursday
   return (last_day-weekday)*86400;
  }

long EEA_PragueOffsetSeconds(const long utc)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)utc,dt);
   long start=EEA_AutoLastSundayUtc(dt.year,3)+3600;
   long end=EEA_AutoLastSundayUtc(dt.year,10)+3600;
   return (utc>=start && utc<end) ? 7200 : 3600;
  }

// UTC instant of the most recent 00:00 Europe/Prague at or before now_utc.
long EEA_PragueDailyResetUtc(const long now_utc)
  {
   long local=now_utc+EEA_PragueOffsetSeconds(now_utc);
   long local_midnight=(local/86400)*86400;
   long guess=local_midnight-EEA_PragueOffsetSeconds(now_utc);
   return local_midnight-EEA_PragueOffsetSeconds(guess);
  }

// ---------------------------------------------------------------------------
// Balance at a past instant from reconciled deal history: every deal at or after
// `at_utc` (trades and cash flows alike) is unwound from the current balance.
// Fails closed when the loaded history does not reach back to `at_utc`.
// ---------------------------------------------------------------------------
bool EEA_BalanceAtUtc(const EEA_RuntimeReconciliationSnapshot &snapshot,const double current_balance,
                      const long at_utc,double &balance,string &reason)
  {
   balance=0.0;
   if(!snapshot.deals_complete || snapshot.history_from_utc<=0 || snapshot.history_from_utc>at_utc)
     { reason="BALANCE_HISTORY_INCOMPLETE"; return false; }
   double after=0.0;
   for(int i=0;i<snapshot.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
      if(snapshot.deals[i].time_utc>=at_utc)
         after+=snapshot.deals[i].profit+snapshot.deals[i].commission+snapshot.deals[i].swap+snapshot.deals[i].fee;
   balance=current_balance-after;
   if(!MathIsValidNumber(balance) || balance<=0.0) { reason="BALANCE_RECONSTRUCTION_INVALID"; return false; }
   reason="BALANCE_RECONSTRUCTED";
   return true;
  }

// Broker read: the first positive balance deposit of the whole account history is
// the prop-firm initial capital. Returns 0 when the history has none.
double EEA_InitialCapitalFromHistory()
  {
   if(!HistorySelect(0,TimeCurrent())) return 0.0;
   int total=HistoryDealsTotal();
   long first_time=0; double amount=0.0;
   for(int i=0;i<total;i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      if(HistoryDealGetInteger(ticket,DEAL_TYPE)!=DEAL_TYPE_BALANCE) continue;
      double profit=HistoryDealGetDouble(ticket,DEAL_PROFIT);
      long time=HistoryDealGetInteger(ticket,DEAL_TIME);
      if(profit<=0.0) continue;
      if(first_time==0 || time<first_time) { first_time=time; amount=profit; }
     }
   return amount;
  }

// ---------------------------------------------------------------------------
// Costs
// ---------------------------------------------------------------------------
// Average commission per lot per side learned from this symbol's recent deals.
// `learned` is false when there is no deal yet; the caller then uses the account
// cost profile (0 for "no commission" account types) and flags COST_ESTIMATED.
double EEA_CommissionPerLotPerSide(const EEA_RuntimeReconciliationSnapshot &snapshot,
                                   const string broker_symbol,bool &learned)
  {
   double total=0.0, volume=0.0;
   for(int i=0;i<snapshot.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      if(snapshot.deals[i].symbol!=broker_symbol) continue;
      if(snapshot.deals[i].type!="0" && snapshot.deals[i].type!="1") continue;
      if(snapshot.deals[i].volume<=0.0) continue;
      total+=MathAbs(snapshot.deals[i].commission);
      volume+=snapshot.deals[i].volume;
     }
   learned=volume>0.0;
   return learned ? total/volume : 0.0;
  }

double EEA_MedianDouble(double &values[],const int count)
  {
   if(count<=0) return 0.0;
   ArraySort(values);
   if(count%2==1) return values[count/2];
   return 0.5*(values[count/2-1]+values[count/2]);
  }

// Broker read: median spread (points) of the last `bars` closed M5 bars.
double EEA_MedianSpreadPoints(const string broker_symbol,const int bars)
  {
   MqlRates rates[];
   int copied=CopyRates(broker_symbol,PERIOD_M5,1,bars,rates);
   if(copied<=0) return 0.0;
   double spreads[];
   ArrayResize(spreads,copied);
   int used=0;
   for(int i=0;i<copied;i++) if(rates[i].spread>0) { spreads[used]=(double)rates[i].spread; used++; }
   return EEA_MedianDouble(spreads,used);
  }

// Broker read: swap per lot per night in account currency for the given direction.
// `known` is false for swap modes this helper does not convert.
double EEA_SwapMoneyPerLotPerNight(const EEA_RuntimeSymbolSpec &spec,const int direction,bool &known)
  {
   known=false;
   long mode=SymbolInfoInteger(spec.broker_symbol,SYMBOL_SWAP_MODE);
   double rate=SymbolInfoDouble(spec.broker_symbol,direction>0 ? SYMBOL_SWAP_LONG : SYMBOL_SWAP_SHORT);
   if(!MathIsValidNumber(rate)) return 0.0;
   if(mode==SYMBOL_SWAP_MODE_DISABLED) { known=true; return 0.0; }
   if(mode==SYMBOL_SWAP_MODE_POINTS && spec.tick_size>0.0)
     { known=true; return rate*spec.point/spec.tick_size*spec.tick_value; }
   if(mode==SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT) { known=true; return rate; }
   return 0.0;
  }

long EEA_AccountLeverage() { return AccountInfoInteger(ACCOUNT_LEVERAGE); }

// ---------------------------------------------------------------------------
// Currency exposure (spec 5.5): open risk attributed to the two currencies of each
// instrument. A long EURUSD position at risk R adds +R to EUR and -R to USD.
// ---------------------------------------------------------------------------
#define EEA_EXPOSURE_MAX_CURRENCIES 32

struct EEA_CurrencyExposure
  {
   int count;
   string currency[EEA_EXPOSURE_MAX_CURRENCIES];
   double risk[EEA_EXPOSURE_MAX_CURRENCIES];     // signed risk money
   int contributors[EEA_EXPOSURE_MAX_CURRENCIES]; // positions adding risk in the same direction
  };

void EEA_CurrencyExposureReset(EEA_CurrencyExposure &e)
  {
   e.count=0;
   for(int i=0;i<EEA_EXPOSURE_MAX_CURRENCIES;i++) { e.currency[i]=""; e.risk[i]=0.0; e.contributors[i]=0; }
  }

bool EEA_CurrencyExposureAdd(EEA_CurrencyExposure &e,const string currency,const double signed_risk)
  {
   if(currency=="" || !MathIsValidNumber(signed_risk)) return false;
   int index=-1;
   for(int i=0;i<e.count;i++) if(e.currency[i]==currency) { index=i; break; }
   if(index<0)
     {
      if(e.count>=EEA_EXPOSURE_MAX_CURRENCIES) return false;
      index=e.count; e.count++; e.currency[index]=currency; e.risk[index]=0.0; e.contributors[index]=0;
     }
   if(e.risk[index]==0.0 || (e.risk[index]>0.0)==(signed_risk>0.0)) e.contributors[index]++;
   e.risk[index]+=signed_risk;
   return true;
  }

bool EEA_CurrencyExposureAddPosition(EEA_CurrencyExposure &e,const string base,const string quote,
                                     const int direction,const double risk_money)
  {
   if((direction!=1 && direction!=-1) || risk_money<0.0) return false;
   if(base==quote) return EEA_CurrencyExposureAdd(e,base,direction*risk_money);
   return EEA_CurrencyExposureAdd(e,base,direction*risk_money) &&
          EEA_CurrencyExposureAdd(e,quote,-direction*risk_money);
  }

// Blocks when adding the candidate pushes any currency beyond the cap or when the
// candidate would be at least the max_correlated-th same-direction contributor.
bool EEA_CurrencyExposureAllows(const EEA_CurrencyExposure &existing,const string base,const string quote,
                                const int direction,const double risk_money,const double cap_money,
                                const int max_correlated,string &reason)
  {
   EEA_CurrencyExposure after=existing;
   if(!EEA_CurrencyExposureAddPosition(after,base,quote,direction,risk_money))
     { reason="CURRENCY_EXPOSURE_INVALID"; return false; }
   for(int i=0;i<after.count;i++)
     {
      if(after.currency[i]!=base && after.currency[i]!=quote) continue;
      if(MathAbs(after.risk[i])>cap_money+1e-9) { reason="CURRENCY_EXPOSURE_CAP_"+after.currency[i]; return false; }
      if(after.contributors[i]>max_correlated) { reason="CORRELATED_TRADES_LIMIT_"+after.currency[i]; return false; }
     }
   reason="CURRENCY_EXPOSURE_OK";
   return true;
  }

#endif
