#ifndef ENTERPRISE_EA_POLICY_SETTINGS_STORE_MQH
#define ENTERPRISE_EA_POLICY_SETTINGS_STORE_MQH

#include "AtomicWriter.mqh"

struct EEA_PolicySettings
  {
   string config_version;
   string account_fingerprint;
   string broker_server;
   long revision;
   string proposed_policy;
   string committed_policy;
   bool committed_daily_continuation;
   bool committed_overall_continuation;
   long authorization_utc;
  };

void EEA_PolicySettingsDefaults(EEA_PolicySettings &s)
  {
   s.config_version=""; s.account_fingerprint=""; s.broker_server="";
   s.revision=0; s.proposed_policy="UNSELECTED"; s.committed_policy="UNSELECTED";
   s.committed_daily_continuation=true; s.committed_overall_continuation=true;
   s.authorization_utc=0;
  }

string EEA_PolicySettingsJsonEscape(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort ch=StringGetCharacter(value,i);
      if(ch==34) out+="\\\""; else if(ch==92) out+="\\\\";
      else out+=ShortToString(ch);
     }
   return out;
  }

string EEA_PolicySettingsToJson(const EEA_PolicySettings &s)
  {
   return "{\"schema_version\":\"policy-settings-v1.0.0\",\"config_version\":\""+
      EEA_PolicySettingsJsonEscape(s.config_version)+"\",\"account_fingerprint\":\""+
      EEA_PolicySettingsJsonEscape(s.account_fingerprint)+"\",\"broker_server\":\""+
      EEA_PolicySettingsJsonEscape(s.broker_server)+"\",\"revision\":"+IntegerToString(s.revision)+
      ",\"proposed_policy\":\""+EEA_PolicySettingsJsonEscape(s.proposed_policy)+
      "\",\"committed_policy\":\""+EEA_PolicySettingsJsonEscape(s.committed_policy)+
      "\",\"committed_daily_continuation\":"+(s.committed_daily_continuation ? "true" : "false")+
      ",\"committed_overall_continuation\":"+(s.committed_overall_continuation ? "true" : "false")+
      ",\"authorization_utc\":"+IntegerToString(s.authorization_utc)+"}";
  }

bool EEA_PolicySettingsReadFile(const string path,string &json)
  {
   json=""; int h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE) return false;
   ulong size=FileSize(h); if(size==0 || size>65536) { FileClose(h); return false; }
   uchar bytes[]; ArrayResize(bytes,(int)size); uint count=FileReadArray(h,bytes,0,(int)size); FileClose(h);
   if(count!=(uint)size) return false; json=CharArrayToString(bytes,0,(int)count,CP_UTF8); return true;
  }

string EEA_PolicySettingsField(const string json,const string name)
  {
   string key="\""+name+"\":"; int at=StringFind(json,key); if(at<0) return "";
   int start=at+StringLen(key); if(StringGetCharacter(json,start)==34) { start++; int end=StringFind(json,"\"",start); if(end<0) return ""; return StringSubstr(json,start,end-start); }
   int end=StringFind(json,",",start); if(end<0) end=StringFind(json,"}",start); if(end<0) return ""; return StringSubstr(json,start,end-start);
  }

bool EEA_PolicySettingsStoreLoad(const string path,const string config_version,const string account_fingerprint,
                                 const string broker_server,EEA_PolicySettings &s)
  {
   EEA_PolicySettingsDefaults(s); string json=""; if(!EEA_PolicySettingsReadFile(path,json)) return false;
   if(EEA_PolicySettingsField(json,"schema_version")!="policy-settings-v1.0.0" ||
      EEA_PolicySettingsField(json,"config_version")!=config_version ||
      EEA_PolicySettingsField(json,"account_fingerprint")!=account_fingerprint ||
      EEA_PolicySettingsField(json,"broker_server")!=broker_server) { EEA_PolicySettingsDefaults(s); return false; }
   s.config_version=config_version; s.account_fingerprint=account_fingerprint; s.broker_server=broker_server;
   s.revision=StringToInteger(EEA_PolicySettingsField(json,"revision"));
   s.proposed_policy=EEA_PolicySettingsField(json,"proposed_policy"); s.committed_policy=EEA_PolicySettingsField(json,"committed_policy");
   s.committed_daily_continuation=EEA_PolicySettingsField(json,"committed_daily_continuation")=="true";
   s.committed_overall_continuation=EEA_PolicySettingsField(json,"committed_overall_continuation")=="true";
   s.authorization_utc=StringToInteger(EEA_PolicySettingsField(json,"authorization_utc")); return s.revision>0;
  }

bool EEA_PolicySettingsStoreWrite(const string path,const EEA_PolicySettings &s)
  {
   if(s.config_version=="" || s.account_fingerprint=="" || s.broker_server=="" || s.revision<=0 ||
      s.committed_policy=="" || s.proposed_policy=="") return false;
   return EEA_WriteAtomicText(path,EEA_PolicySettingsToJson(s));
  }

#endif
