#ifndef ENTERPRISE_EA_RISK_LEDGER_STORE_MQH
#define ENTERPRISE_EA_RISK_LEDGER_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Core\Events.mqh"
#include "..\Runtime\AccountAutoProfile.mqh"

// Durable FTMO policy facts that cannot be re-read from the terminal at any moment:
// the initial capital, the balance at the latest Europe/Prague daily reset and the
// highest such balance (1-Step trailing overall floor). Restored on every attach.
#define EEA_RISK_LEDGER_DOCUMENT "risk-ledger-v1.0.0"

struct EEA_RiskLedger
  {
   string config_version;
   string account_fingerprint;
   string broker_server;
   double initial_capital;
   string initial_capital_source;   // INPUT | HISTORY_FIRST_DEPOSIT
   double high_water_balance;
   long   last_reset_utc;
   double last_reset_balance;
   long   revision;
  };

void EEA_RiskLedgerDefaults(EEA_RiskLedger &l)
  {
   l.config_version=""; l.account_fingerprint=""; l.broker_server="";
   l.initial_capital=0.0; l.initial_capital_source="";
   l.high_water_balance=0.0; l.last_reset_utc=0; l.last_reset_balance=0.0; l.revision=0;
  }

string EEA_RiskLedgerPath(const string root) { return root+"/current/risk_ledger.json"; }

string EEA_RiskLedgerField(const string json,const string name)
  {
   string key="\""+name+"\":";
   int at=StringFind(json,key);
   if(at<0) return "";
   int start=at+StringLen(key);
   if(start<StringLen(json) && StringGetCharacter(json,start)==34)
     {
      int end=StringFind(json,"\"",start+1);
      return end<0 ? "" : StringSubstr(json,start+1,end-start-1);
     }
   int end=StringFind(json,",",start);
   if(end<0) end=StringFind(json,"}",start);
   return end<0 ? "" : StringSubstr(json,start,end-start);
  }

bool EEA_RiskLedgerWrite(const string root,const EEA_RiskLedger &l)
  {
   if(root=="" || l.account_fingerprint=="" || l.initial_capital<=0.0) return false;
   string json="{\"document_version\":\""+EEA_RISK_LEDGER_DOCUMENT+"\",\"config_version\":\""+
      EEA_JsonEscape(l.config_version)+"\",\"account_fingerprint\":\""+EEA_JsonEscape(l.account_fingerprint)+
      "\",\"broker_server\":\""+EEA_JsonEscape(l.broker_server)+"\",\"initial_capital\":"+
      DoubleToString(l.initial_capital,8)+",\"initial_capital_source\":\""+EEA_JsonEscape(l.initial_capital_source)+
      "\",\"high_water_balance\":"+DoubleToString(l.high_water_balance,8)+",\"last_reset_utc\":"+
      IntegerToString(l.last_reset_utc)+",\"last_reset_balance\":"+DoubleToString(l.last_reset_balance,8)+
      ",\"revision\":"+IntegerToString(l.revision)+"}";
   return EEA_WriteAtomicText(EEA_RiskLedgerPath(root),json);
  }

bool EEA_RiskLedgerLoad(const string root,const string config_version,const string account_fingerprint,
                        const string broker_server,EEA_RiskLedger &l)
  {
   EEA_RiskLedgerDefaults(l);
   string path=EEA_RiskLedgerPath(root);
   if(!FileIsExist(path,0)) return false;
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   ulong size=FileSize(handle);
   if(size==0 || size>65536) { FileClose(handle); return false; }
   uchar bytes[];
   ArrayResize(bytes,(int)size);
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return false;
   string json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   if(EEA_RiskLedgerField(json,"document_version")!=EEA_RISK_LEDGER_DOCUMENT ||
      EEA_RiskLedgerField(json,"config_version")!=config_version ||
      EEA_RiskLedgerField(json,"account_fingerprint")!=account_fingerprint ||
      EEA_RiskLedgerField(json,"broker_server")!=broker_server) return false;
   l.config_version=config_version; l.account_fingerprint=account_fingerprint; l.broker_server=broker_server;
   l.initial_capital=StringToDouble(EEA_RiskLedgerField(json,"initial_capital"));
   l.initial_capital_source=EEA_RiskLedgerField(json,"initial_capital_source");
   l.high_water_balance=StringToDouble(EEA_RiskLedgerField(json,"high_water_balance"));
   l.last_reset_utc=StringToInteger(EEA_RiskLedgerField(json,"last_reset_utc"));
   l.last_reset_balance=StringToDouble(EEA_RiskLedgerField(json,"last_reset_balance"));
   l.revision=StringToInteger(EEA_RiskLedgerField(json,"revision"));
   if(l.initial_capital<=0.0 || l.high_water_balance<l.initial_capital || l.revision<=0)
     { EEA_RiskLedgerDefaults(l); return false; }
   return true;
  }

// Brings the ledger up to the latest Prague reset. Every reset inside the loaded
// history raises the high-water mark when its balance is higher; the high-water mark
// never falls. Returns true when anything changed.
bool EEA_RiskLedgerAdvance(EEA_RiskLedger &l,const EEA_RuntimeReconciliationSnapshot &snapshot,
                           const double current_balance,const long now_utc,string &reason)
  {
   reason="";
   if(l.initial_capital<=0.0) { reason="INITIAL_CAPITAL_UNKNOWN"; return false; }
   long latest=EEA_PragueDailyResetUtc(now_utc);
   if(latest==l.last_reset_utc) { reason="RISK_LEDGER_CURRENT"; return false; }
   double hw=MathMax(l.high_water_balance,l.initial_capital);
   // Walk Prague resets from the oldest covered by history up to the latest.
   long reset=latest;
   long resets[];
   int n=0;
   while(reset>snapshot.history_from_utc && n<120)
     {
      ArrayResize(resets,n+1); resets[n]=reset; n++;
      reset=EEA_PragueDailyResetUtc(reset-1);
     }
   double latest_balance=0.0;
   for(int k=n-1;k>=0;k--)
     {
      if(resets[k]<=l.last_reset_utc) continue;
      double balance; string balance_reason;
      if(!EEA_BalanceAtUtc(snapshot,current_balance,resets[k],balance,balance_reason)) continue;
      if(balance>hw) hw=balance;
      if(k==0) latest_balance=balance;
     }
   if(latest_balance<=0.0) { reason="DAILY_RESET_BALANCE_UNAVAILABLE"; return false; }
   l.high_water_balance=hw;
   l.last_reset_utc=latest; l.last_reset_balance=latest_balance; l.revision++;
   reason="RISK_LEDGER_ADVANCED";
   return true;
  }

#endif
