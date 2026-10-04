#ifndef ENTERPRISE_EA_LIVE_SESSION_AUTHORIZATION_MQH
#define ENTERPRISE_EA_LIVE_SESSION_AUTHORIZATION_MQH

// Session authorization (REQ-LIVE-SESSION). The operator signs one time-boxed session
// from the control center instead of one document per trade. Inside the session every
// candidate that passes the Risk Kernel may be sent, bounded by the session limits:
// allowed broker symbols, risk per trade, entries per Prague day and daily loss.
// The session is bound to account, server, config, margin mode and the committed risk
// policy; any change invalidates it. Expiry, revocation or a breached limit fail closed.
// Nothing here sends an order: it only produces an EEA_LiveAuthorizationDecision that
// the execution adapter binds to one intent as before.

#include "../Core/Events.mqh"
#include "../Storage/AtomicWriter.mqh"
#include "../Storage/LiveAuthorizationStore.mqh"
#include "LiveAuthorizationGate.mqh"

#define EEA_LIVE_SESSION_SCHEMA "live-session-v1.0.0"
#define EEA_LIVE_SESSION_USAGE_SCHEMA "live-session-usage-v1.0.0"
#define EEA_LIVE_SESSION_MAX_SECONDS (7*86400)
#define EEA_LIVE_SESSION_SCOPE "MARKET_AND_PENDING_ENTRY"

struct EEA_LiveSession
  {
   string session_id;
   string status;              // ACTIVE | REVOKED
   string operator_id;
   string config_version;
   string account_fingerprint;
   string broker_server;
   string account_mode;
   string risk_policy_id;
   string build_hash;
   string allowed_symbols;     // comma separated broker symbols
   string scope;
   long signed_at_utc;
   long valid_from_utc;
   long valid_until_utc;
   long revoked_at_utc;
   double max_risk_per_trade_fraction;
   double max_daily_loss_fraction;
   int max_entries_per_day;
   bool real_account;
  };

struct EEA_LiveSessionUsage
  {
   string session_id;
   long day_reset_utc;
   int entries;
  };

struct EEA_LiveSessionRuntime
  {
   bool loaded;
   bool present;
   EEA_LiveSession session;
   EEA_LiveSessionUsage usage;
   bool usage_failed;          // a sent entry could not be counted durably: block further entries
   string reason;
   string last_action;
  };

void EEA_LiveSessionDefaults(EEA_LiveSession &s)
  {
   s.session_id=""; s.status=""; s.operator_id=""; s.config_version=""; s.account_fingerprint="";
   s.broker_server=""; s.account_mode=""; s.risk_policy_id=""; s.build_hash=""; s.allowed_symbols="";
   s.scope=""; s.signed_at_utc=0; s.valid_from_utc=0; s.valid_until_utc=0; s.revoked_at_utc=0;
   s.max_risk_per_trade_fraction=0.0; s.max_daily_loss_fraction=0.0; s.max_entries_per_day=0;
   s.real_account=false;
  }

void EEA_LiveSessionRuntimeDefaults(EEA_LiveSessionRuntime &r)
  {
   r.loaded=false; r.present=false; EEA_LiveSessionDefaults(r.session);
   r.usage.session_id=""; r.usage.day_reset_utc=0; r.usage.entries=0;
   r.usage_failed=false; r.reason="LIVE_SESSION_NONE"; r.last_action="";
  }

string EEA_LiveSessionPath(const string root) { return root+"/current/live_session.json"; }
string EEA_LiveSessionUsagePath(const string root) { return root+"/current/live_session_usage.json"; }

string EEA_LiveSessionToJson(const EEA_LiveSession &s)
  {
   return "{\"schema_version\":\""+EEA_LIVE_SESSION_SCHEMA+"\",\"session_id\":\""+EEA_JsonEscape(s.session_id)+
      "\",\"status\":\""+EEA_JsonEscape(s.status)+"\",\"operator_id\":\""+EEA_JsonEscape(s.operator_id)+
      "\",\"config_version\":\""+EEA_JsonEscape(s.config_version)+
      "\",\"account_fingerprint\":\""+EEA_JsonEscape(s.account_fingerprint)+
      "\",\"broker_server\":\""+EEA_JsonEscape(s.broker_server)+"\",\"account_mode\":\""+EEA_JsonEscape(s.account_mode)+
      "\",\"risk_policy_id\":\""+EEA_JsonEscape(s.risk_policy_id)+"\",\"build_hash\":\""+EEA_JsonEscape(s.build_hash)+
      "\",\"allowed_symbols\":\""+EEA_JsonEscape(s.allowed_symbols)+"\",\"scope\":\""+EEA_JsonEscape(s.scope)+
      "\",\"signed_at_utc\":"+IntegerToString(s.signed_at_utc)+
      ",\"valid_from_utc\":"+IntegerToString(s.valid_from_utc)+
      ",\"valid_until_utc\":"+IntegerToString(s.valid_until_utc)+
      ",\"revoked_at_utc\":"+IntegerToString(s.revoked_at_utc)+
      ",\"max_risk_per_trade_fraction\":"+DoubleToString(s.max_risk_per_trade_fraction,6)+
      ",\"max_daily_loss_fraction\":"+DoubleToString(s.max_daily_loss_fraction,6)+
      ",\"max_entries_per_day\":"+IntegerToString(s.max_entries_per_day)+
      ",\"real_account\":"+(s.real_account ? "true" : "false")+"}";
  }

bool EEA_LiveSessionWrite(const string root,const EEA_LiveSession &s)
  { return EEA_WriteAtomicText(EEA_LiveSessionPath(root),EEA_LiveSessionToJson(s)); }

// Returns false only for an unreadable or malformed file; a missing file is "not present".
bool EEA_LiveSessionLoadPath(const string path,EEA_LiveSession &s,bool &present)
  {
   EEA_LiveSessionDefaults(s);
   present=FileIsExist(path,0);
   if(!present) return true;
   string json;
   if(!EEA_LiveAuthorizationStoreRead(path,json)) return false;
   if(EEA_LiveAuthorizationStoreField(json,"schema_version")!=EEA_LIVE_SESSION_SCHEMA) return false;
   s.session_id=EEA_LiveAuthorizationStoreField(json,"session_id");
   s.status=EEA_LiveAuthorizationStoreField(json,"status");
   s.operator_id=EEA_LiveAuthorizationStoreField(json,"operator_id");
   s.config_version=EEA_LiveAuthorizationStoreField(json,"config_version");
   s.account_fingerprint=EEA_LiveAuthorizationStoreField(json,"account_fingerprint");
   s.broker_server=EEA_LiveAuthorizationStoreField(json,"broker_server");
   s.account_mode=EEA_LiveAuthorizationStoreField(json,"account_mode");
   s.risk_policy_id=EEA_LiveAuthorizationStoreField(json,"risk_policy_id");
   s.build_hash=EEA_LiveAuthorizationStoreField(json,"build_hash");
   s.allowed_symbols=EEA_LiveAuthorizationStoreField(json,"allowed_symbols");
   s.scope=EEA_LiveAuthorizationStoreField(json,"scope");
   s.signed_at_utc=StringToInteger(EEA_LiveAuthorizationStoreField(json,"signed_at_utc"));
   s.valid_from_utc=StringToInteger(EEA_LiveAuthorizationStoreField(json,"valid_from_utc"));
   s.valid_until_utc=StringToInteger(EEA_LiveAuthorizationStoreField(json,"valid_until_utc"));
   s.revoked_at_utc=StringToInteger(EEA_LiveAuthorizationStoreField(json,"revoked_at_utc"));
   s.max_risk_per_trade_fraction=StringToDouble(EEA_LiveAuthorizationStoreField(json,"max_risk_per_trade_fraction"));
   s.max_daily_loss_fraction=StringToDouble(EEA_LiveAuthorizationStoreField(json,"max_daily_loss_fraction"));
   s.max_entries_per_day=(int)StringToInteger(EEA_LiveAuthorizationStoreField(json,"max_entries_per_day"));
   s.real_account=EEA_LiveAuthorizationStoreBool(json,"real_account");
   return s.session_id!="";
  }

bool EEA_LiveSessionLoad(const string root,EEA_LiveSession &s,bool &present)
  { return EEA_LiveSessionLoadPath(EEA_LiveSessionPath(root),s,present); }

bool EEA_LiveSessionUsageWrite(const string root,const EEA_LiveSessionUsage &u)
  {
   string json="{\"schema_version\":\""+EEA_LIVE_SESSION_USAGE_SCHEMA+"\",\"session_id\":\""+EEA_JsonEscape(u.session_id)+
      "\",\"day_reset_utc\":"+IntegerToString(u.day_reset_utc)+",\"entries\":"+IntegerToString(u.entries)+"}";
   return EEA_WriteAtomicText(EEA_LiveSessionUsagePath(root),json);
  }

bool EEA_LiveSessionUsageLoad(const string root,EEA_LiveSessionUsage &u)
  {
   u.session_id=""; u.day_reset_utc=0; u.entries=0;
   string path=EEA_LiveSessionUsagePath(root);
   if(!FileIsExist(path,0)) return true;
   string json;
   if(!EEA_LiveAuthorizationStoreRead(path,json)) return false;
   if(EEA_LiveAuthorizationStoreField(json,"schema_version")!=EEA_LIVE_SESSION_USAGE_SCHEMA) return false;
   u.session_id=EEA_LiveAuthorizationStoreField(json,"session_id");
   u.day_reset_utc=StringToInteger(EEA_LiveAuthorizationStoreField(json,"day_reset_utc"));
   u.entries=(int)StringToInteger(EEA_LiveAuthorizationStoreField(json,"entries"));
   return u.entries>=0;
  }

// Entries sent on the current Prague day across all sessions: re-signing a session
// must not reset the daily cap. Another day counts zero.
int EEA_LiveSessionEntriesToday(const EEA_LiveSessionRuntime &r,const long day_reset_utc)
  {
   if(r.usage.day_reset_utc!=day_reset_utc) return 0;
   return r.usage.entries;
  }

bool EEA_LiveSessionSymbolAllowed(const EEA_LiveSession &s,const string broker_symbol)
  {
   if(broker_symbol=="") return false;
   string parts[];
   int n=StringSplit(s.allowed_symbols,',',parts);
   for(int i=0;i<n;i++) if(parts[i]==broker_symbol) return true;
   return false;
  }

// Structural validity at time now: status, window, scope and limits.
bool EEA_LiveSessionActive(const EEA_LiveSession &s,const long now_utc,string &reason)
  {
   if(s.session_id=="") { reason="LIVE_SESSION_NONE"; return false; }
   if(s.status=="REVOKED") { reason="LIVE_SESSION_REVOKED"; return false; }
   if(s.status!="ACTIVE") { reason="LIVE_SESSION_STATUS_INVALID"; return false; }
   if(s.valid_from_utc<=0 || s.valid_until_utc<=s.valid_from_utc ||
      s.valid_until_utc-s.valid_from_utc>EEA_LIVE_SESSION_MAX_SECONDS)
     { reason="LIVE_SESSION_WINDOW_INVALID"; return false; }
   if(now_utc<s.valid_from_utc) { reason="LIVE_SESSION_NOT_STARTED"; return false; }
   if(now_utc>=s.valid_until_utc) { reason="LIVE_SESSION_EXPIRED"; return false; }
   if(s.scope!=EEA_LIVE_SESSION_SCOPE) { reason="LIVE_SESSION_SCOPE_INVALID"; return false; }
   if(s.max_risk_per_trade_fraction<=0.0 || s.max_risk_per_trade_fraction>0.02 ||
      s.max_daily_loss_fraction<=0.0 || s.max_daily_loss_fraction>0.05 ||
      s.max_entries_per_day<1 || s.max_entries_per_day>50)
     { reason="LIVE_SESSION_LIMITS_INVALID"; return false; }
   if(s.allowed_symbols=="") { reason="LIVE_SESSION_SYMBOLS_EMPTY"; return false; }
   reason="LIVE_SESSION_ACTIVE";
   return true;
  }

// Produces the per-intent authorization for one candidate inside an active session.
// The intent id is derived from session and candidate, so the adapter still binds the
// authorization to exactly one intent, account, symbol, config and policy.
bool EEA_LiveSessionAuthorize(const EEA_LiveSessionRuntime &r,
                              const string config_version,const string account_fingerprint,
                              const string broker_server,const string account_mode,
                              const string risk_policy_id,const string broker_symbol,
                              const string candidate_id,const bool real_account,
                              const long now_utc,const long day_reset_utc,
                              const double initial_capital,const double reset_balance,const double equity,
                              EEA_LiveAuthorizationDecision &d,string &reason)
  {
   EEA_LiveAuthorizationDecisionDefaults(d);
   const EEA_LiveSession s=r.session;
   if(!r.present) { reason="LIVE_SESSION_NONE"; return false; }
   if(r.usage_failed) { reason="LIVE_SESSION_USAGE_PERSISTENCE_FAILED"; return false; }
   if(!EEA_LiveSessionActive(s,now_utc,reason)) return false;
   if(s.config_version!=config_version || s.account_fingerprint!=account_fingerprint ||
      s.broker_server!=broker_server || s.account_mode!=account_mode)
     { reason="LIVE_SESSION_IDENTITY_MISMATCH"; return false; }
   if(s.risk_policy_id!=risk_policy_id) { reason="LIVE_SESSION_POLICY_CHANGED"; return false; }
   if(s.real_account!=real_account) { reason="LIVE_SESSION_ACCOUNT_TYPE_CHANGED"; return false; }
   if(!EEA_LiveSessionSymbolAllowed(s,broker_symbol)) { reason="LIVE_SESSION_SYMBOL_NOT_ALLOWED"; return false; }
   if(candidate_id=="") { reason="LIVE_CANDIDATE_ID_MISSING"; return false; }
   if(EEA_LiveSessionEntriesToday(r,day_reset_utc)>=s.max_entries_per_day)
     { reason="LIVE_SESSION_DAILY_ENTRIES_REACHED"; return false; }
   if(initial_capital<=0.0 || reset_balance<=0.0) { reason="LIVE_SESSION_LOSS_BASIS_UNKNOWN"; return false; }
   if(reset_balance-equity>=s.max_daily_loss_fraction*initial_capital)
     { reason="LIVE_SESSION_DAILY_LOSS_REACHED"; return false; }
   d.authorized=true;
   d.status="AUTHORIZED_CONTROLLED_LIVE";
   d.reason_code="LIVE_SESSION_AUTHORIZED";
   d.authorization_id=s.session_id;
   d.build_hash=s.build_hash;
   d.account_fingerprint=s.account_fingerprint;
   d.candidate_id=candidate_id;
   d.intent_id=s.session_id+"-"+candidate_id;
   d.risk_policy_id=s.risk_policy_id;
   d.config_version=s.config_version;
   d.broker_server=s.broker_server;
   d.account_mode=s.account_mode;
   d.broker_symbol=broker_symbol;
   d.authorization_valid_until_utc=s.valid_until_utc;
   reason="LIVE_SESSION_AUTHORIZED";
   return true;
  }

// Cancelling an EA pending order only removes exposure, so it stays possible after the
// session expired or was revoked. It is still bound to the session that placed the order
// (intent id prefix) and to the order's account, server, config, symbol and policy.
bool EEA_LiveSessionCancelAuthorization(const string path,const string intent_id,const string candidate_id,
                                        const string config_version,const string account_fingerprint,
                                        const string broker_server,const string account_mode,
                                        const string broker_symbol,const string risk_policy_id,
                                        EEA_LiveAuthorizationDecision &d,string &reason)
  {
   EEA_LiveAuthorizationDecisionDefaults(d);
   EEA_LiveSession s; bool present=false;
   if(!EEA_LiveSessionLoadPath(path,s,present) || !present) { reason="LIVE_SESSION_FILE_UNAVAILABLE"; return false; }
   if(StringFind(intent_id,s.session_id+"-")!=0 || candidate_id=="")
     { reason="LIVE_SESSION_CANCEL_NOT_OWNED"; return false; }
   if(s.config_version!=config_version || s.account_fingerprint!=account_fingerprint ||
      s.broker_server!=broker_server || s.account_mode!=account_mode)
     { reason="LIVE_SESSION_IDENTITY_MISMATCH"; return false; }
   d.authorized=true; d.status="AUTHORIZED_CONTROLLED_LIVE"; d.reason_code="LIVE_SESSION_CANCEL_AUTHORIZED";
   d.authorization_id=s.session_id; d.build_hash=s.build_hash; d.account_fingerprint=s.account_fingerprint;
   d.candidate_id=candidate_id; d.intent_id=intent_id; d.risk_policy_id=risk_policy_id;
   d.config_version=s.config_version; d.broker_server=s.broker_server; d.account_mode=s.account_mode;
   d.broker_symbol=broker_symbol; d.authorization_valid_until_utc=(long)TimeGMT()+60;
   reason="LIVE_SESSION_CANCEL_AUTHORIZED";
   return true;
  }

// Counts one sent entry; persisted so the daily cap survives EA removal and re-attach.
bool EEA_LiveSessionRecordEntry(EEA_LiveSessionRuntime &r,const string root,const long day_reset_utc)
  {
   if(r.usage.day_reset_utc!=day_reset_utc) { r.usage.day_reset_utc=day_reset_utc; r.usage.entries=0; }
   r.usage.session_id=r.session.session_id;
   r.usage.entries++;
   if(!EEA_LiveSessionUsageWrite(root,r.usage)) { r.usage_failed=true; return false; }
   return true;
  }

#endif
