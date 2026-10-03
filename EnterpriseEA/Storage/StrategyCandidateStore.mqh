#ifndef ENTERPRISE_EA_STRATEGY_CANDIDATE_STORE_MQH
#define ENTERPRISE_EA_STRATEGY_CANDIDATE_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Core\Events.mqh"
#include "..\Setups\BreakRetest.mqh"

enum EEA_StrategyCandidateLoadStatus
  {
   EEA_CANDIDATE_CHECKPOINT_MISSING=0,
   EEA_CANDIDATE_CHECKPOINT_CORRUPT=1,
   EEA_CANDIDATE_CHECKPOINT_IDENTITY_MISMATCH=2,
   EEA_CANDIDATE_CHECKPOINT_STALE=3,
   EEA_CANDIDATE_CHECKPOINT_LOADED=4
  };

string EEA_StrategyCandidateStorePath(const string root,const string canonical)
  { return root+"/current/strategy_"+canonical+".json"; }

string EEA_StrategyCandidateStoreField(const string json,const string name)
  {
   string key="\""+name+"\":";
   int at=StringFind(json,key);
   if(at<0) return "";
   int start=at+StringLen(key);
   if(start<StringLen(json) && StringGetCharacter(json,start)==34)
     {
      start++;
      int end=StringFind(json,"\"",start);
      if(end<0) return "";
      return StringSubstr(json,start,end-start);
     }
   int end=StringFind(json,",",start);
   if(end<0) end=StringFind(json,"}",start);
   if(end<0) return "";
   return StringSubstr(json,start,end-start);
  }

bool EEA_StrategyCandidateStoreReadText(const string path,string &json)
  {
   json="";
   if(!FileIsExist(path,0)) return false;
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   ulong size=FileSize(handle);
   if(size==0 || size>131072) { FileClose(handle); return false; }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size) { FileClose(handle); return false; }
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return false;
   json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   return StringLen(json)>0;
  }

bool EEA_StrategyCandidateStoreWrite(const string path,
                                     const string config_version,
                                     const string account_fingerprint,
                                     const string broker_server,
                                     const EEA_S02Engine &engine,
                                     const bool has_candidate,
                                     const long observed_at_utc)
  {
   if(path=="" || config_version=="" || account_fingerprint=="" || broker_server=="" ||
      engine.canonical_symbol=="" || engine.timeframe=="" || engine.config_version!=config_version ||
      observed_at_utc<=0 || engine.last_processed_bar_utc<0)
      return false;
   string json="{\"schema_version\":\"s02-runtime-v0.1.0\",\"document_version\":\"strategy-candidate-v0.1.0\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+
      "\",\"broker_server\":\""+EEA_JsonEscape(broker_server)+"\",\"canonical_symbol\":\""+
      EEA_JsonEscape(engine.canonical_symbol)+"\",\"timeframe\":\""+EEA_JsonEscape(engine.timeframe)+
      "\",\"observed_at_utc\":"+IntegerToString(observed_at_utc)+",\"last_processed_bar_utc\":"+
      IntegerToString((long)engine.last_processed_bar_utc)+",\"state\":"+IntegerToString(engine.state)+
      ",\"direction\":"+IntegerToString(engine.direction)+",\"key_level\":"+DoubleToString(engine.key_level,16)+
      ",\"signal_atr\":"+DoubleToString(engine.signal_atr,16)+",\"invalidation_price\":"+
      DoubleToString(engine.invalidation_price,16)+",\"retest_close\":"+DoubleToString(engine.retest_close,16)+
      ",\"bars_since_break\":"+IntegerToString(engine.bars_since_break)+",\"bars_since_acceptance\":"+
      IntegerToString(engine.bars_since_acceptance)+",\"bars_since_retest\":"+IntegerToString(engine.bars_since_retest)+
      ",\"has_candidate\":"+(has_candidate ? "true" : "false")+",\"candidate_id\":\""+
      EEA_JsonEscape(engine.candidate.candidate_id)+"\",\"candidate_setup_id\":\""+
      EEA_JsonEscape(engine.candidate.setup_id)+"\",\"candidate_direction\":\""+
      EEA_JsonEscape(engine.candidate.direction)+"\",\"candidate_state\":\""+
      EEA_JsonEscape(engine.candidate.state)+"\",\"candidate_key_level\":"+
      DoubleToString(engine.candidate.key_level,16)+",\"candidate_invalidation_price\":"+
      DoubleToString(engine.candidate.invalidation_price,16)+",\"candidate_detected_at_utc\":"+
      IntegerToString((long)engine.candidate.detected_at_utc)+",\"candidate_triggered_at_utc\":"+
      IntegerToString((long)engine.candidate.triggered_at_utc)+",\"candidate_expires_after_bars\":"+
      IntegerToString(engine.candidate.expires_after_bars)+",\"candidate_age_after_trigger_bars\":"+
      IntegerToString(engine.candidate.age_after_trigger_bars)+",\"candidate_reason_code\":\""+
      EEA_JsonEscape(engine.candidate.reason_code)+"\"}";
   return EEA_WriteAtomicText(path,json);
  }

EEA_StrategyCandidateLoadStatus EEA_StrategyCandidateStoreLoad(const string path,
                                                                const string config_version,
                                                                const string account_fingerprint,
                                                                const string broker_server,
                                                                const string canonical,
                                                                const string timeframe,
                                                                const long now_utc,
                                                                const long max_age_seconds,
                                                                EEA_S02Engine &engine,
                                                                bool &has_candidate)
  {
   EEA_S02Init(engine,canonical,timeframe,config_version);
   has_candidate=false;
   string json;
   if(!EEA_StrategyCandidateStoreReadText(path,json))
      return FileIsExist(path,0) ? EEA_CANDIDATE_CHECKPOINT_CORRUPT : EEA_CANDIDATE_CHECKPOINT_MISSING;
   if(EEA_StrategyCandidateStoreField(json,"document_version")!="strategy-candidate-v0.1.0" ||
      EEA_StrategyCandidateStoreField(json,"config_version")!=config_version ||
      EEA_StrategyCandidateStoreField(json,"account_fingerprint")!=account_fingerprint ||
      EEA_StrategyCandidateStoreField(json,"broker_server")!=broker_server ||
      EEA_StrategyCandidateStoreField(json,"canonical_symbol")!=canonical ||
      EEA_StrategyCandidateStoreField(json,"timeframe")!=timeframe)
      return EEA_CANDIDATE_CHECKPOINT_IDENTITY_MISMATCH;
   long observed=StringToInteger(EEA_StrategyCandidateStoreField(json,"observed_at_utc"));
   if(now_utc<=0 || max_age_seconds<=0 || observed<=0 || observed>now_utc || now_utc-observed>max_age_seconds)
      return EEA_CANDIDATE_CHECKPOINT_STALE;
   int state=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"state"));
   int direction=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"direction"));
   long last_bar=StringToInteger(EEA_StrategyCandidateStoreField(json,"last_processed_bar_utc"));
   if(state<EEA_S02_IDLE || state>EEA_S02_EXPIRED || (direction<-1 || direction>1) || last_bar<=0)
      return EEA_CANDIDATE_CHECKPOINT_CORRUPT;
   engine.state=state;
   engine.direction=direction;
   engine.last_processed_bar_utc=(datetime)last_bar;
   engine.key_level=StringToDouble(EEA_StrategyCandidateStoreField(json,"key_level"));
   engine.signal_atr=StringToDouble(EEA_StrategyCandidateStoreField(json,"signal_atr"));
   engine.invalidation_price=StringToDouble(EEA_StrategyCandidateStoreField(json,"invalidation_price"));
   engine.retest_close=StringToDouble(EEA_StrategyCandidateStoreField(json,"retest_close"));
   engine.bars_since_break=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"bars_since_break"));
   engine.bars_since_acceptance=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"bars_since_acceptance"));
   engine.bars_since_retest=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"bars_since_retest"));
   engine.candidate.candidate_id=EEA_StrategyCandidateStoreField(json,"candidate_id");
   engine.candidate.setup_id=EEA_StrategyCandidateStoreField(json,"candidate_setup_id");
   engine.candidate.direction=EEA_StrategyCandidateStoreField(json,"candidate_direction");
   engine.candidate.state=EEA_StrategyCandidateStoreField(json,"candidate_state");
   engine.candidate.key_level=StringToDouble(EEA_StrategyCandidateStoreField(json,"candidate_key_level"));
   engine.candidate.invalidation_price=StringToDouble(EEA_StrategyCandidateStoreField(json,"candidate_invalidation_price"));
   engine.candidate.detected_at_utc=(datetime)StringToInteger(EEA_StrategyCandidateStoreField(json,"candidate_detected_at_utc"));
   engine.candidate.triggered_at_utc=(datetime)StringToInteger(EEA_StrategyCandidateStoreField(json,"candidate_triggered_at_utc"));
   engine.candidate.expires_after_bars=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"candidate_expires_after_bars"));
   engine.candidate.age_after_trigger_bars=(int)StringToInteger(EEA_StrategyCandidateStoreField(json,"candidate_age_after_trigger_bars"));
   engine.candidate.canonical_symbol=canonical;
   engine.candidate.timeframe=timeframe;
   engine.candidate.config_version=config_version;
   engine.candidate.reason_code=EEA_StrategyCandidateStoreField(json,"candidate_reason_code");
   has_candidate=EEA_StrategyCandidateStoreField(json,"has_candidate")=="true";
   return EEA_CANDIDATE_CHECKPOINT_LOADED;
  }

#endif
