#ifndef ENTERPRISE_EA_ACCOUNT_SNAPSHOT_ADAPTER_MQH
#define ENTERPRISE_EA_ACCOUNT_SNAPSHOT_ADAPTER_MQH

#include "RuntimeEvidence.mqh"

string EEA_RuntimeMarginModeName(const ENUM_ACCOUNT_MARGIN_MODE mode)
  {
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_NETTING) return "RETAIL_NETTING";
   if(mode==ACCOUNT_MARGIN_MODE_EXCHANGE) return "EXCHANGE";
   if(mode==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "RETAIL_HEDGING";
   return "";
  }

// Read account identity only. Trading permission is deliberately not entry permission.
bool EEA_ReadRuntimeAccount(const string config_version,
                            const int freshness_seconds,
                            EEA_RuntimeAccountSnapshot &snapshot,
                            string &reason)
  {
   reason="";
   if(config_version=="" || freshness_seconds<1)
     { reason="RUNTIME_CONFIGURATION_INVALID"; return false; }
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     { reason="ACCOUNT_IDENTITY_UNAVAILABLE"; return false; }

   const string server=AccountInfoString(ACCOUNT_SERVER);
   const long login=AccountInfoInteger(ACCOUNT_LOGIN);
   const string currency=AccountInfoString(ACCOUNT_CURRENCY);
   const ENUM_ACCOUNT_MARGIN_MODE mode=(ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   const string margin_mode=EEA_RuntimeMarginModeName(mode);
   const double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   const double margin=AccountInfoDouble(ACCOUNT_MARGIN);
   const double margin_free=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(server=="" || login<=0 || currency=="" || margin_mode=="")
     { reason="ACCOUNT_IDENTITY_UNAVAILABLE"; return false; }
   if(!EEA_IsFiniteDouble(balance) || !EEA_IsFiniteDouble(equity) ||
      !EEA_IsFiniteDouble(margin) || !EEA_IsFiniteDouble(margin_free))
     { reason="ACCOUNT_FINANCIAL_STATE_UNAVAILABLE"; return false; }

   const long observed=(long)TimeGMT();
   const string opaque_id=IntegerToString(login)+"|"+currency+"|"+margin_mode;
   snapshot.schema_version="runtime-evidence-v0.1.0";
   snapshot.config_version=config_version;
   snapshot.snapshot_id="account-"+IntegerToString(observed);
   snapshot.account_fingerprint=EEA_RuntimeFingerprint(server,opaque_id);
   snapshot.broker_server=server;
   snapshot.account_currency=currency;
   snapshot.account_margin_mode=margin_mode;
   snapshot.balance=balance;
   snapshot.equity=equity;
   snapshot.margin=margin;
   snapshot.margin_free=margin_free;
   snapshot.observed_at_utc=observed;
   snapshot.valid_until_utc=observed+freshness_seconds;
   return true;
  }

#endif
