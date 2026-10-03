#ifndef ENTERPRISE_EA_STRATEGY_CANDIDATE_RUNTIME_MQH
#define ENTERPRISE_EA_STRATEGY_CANDIDATE_RUNTIME_MQH

#include "../Setups/BreakRetest.mqh"
#include "../Storage/StrategyCandidateStore.mqh"

#define EEA_STRATEGY_RUNTIME_MAX_SYMBOLS 32
#define EEA_STRATEGY_RUNTIME_ATR_PERIOD 14
#define EEA_STRATEGY_RUNTIME_LOOKBACK_BARS 20

struct EEA_StrategyCandidateRuntime
  {
   bool enabled;
   bool initialized;
   string config_version;
   string timeframe;
   EEA_S02Config config;
   EEA_S02Engine engines[EEA_STRATEGY_RUNTIME_MAX_SYMBOLS];
   EEA_S02Candidate candidates[EEA_STRATEGY_RUNTIME_MAX_SYMBOLS];
   bool has_candidate[EEA_STRATEGY_RUNTIME_MAX_SYMBOLS];
   int symbol_count;
   long last_scan_utc;
   string reason_code;
   string persistence_root;
   string account_fingerprint;
   string broker_server;
  };

void EEA_StrategyCandidateRuntimeDefaults(EEA_StrategyCandidateRuntime &runtime)
  {
   runtime.enabled=false;
   runtime.initialized=false;
   runtime.config_version="";
   runtime.timeframe="M5";
   runtime.symbol_count=0;
   runtime.last_scan_utc=0;
   runtime.reason_code="EEA_STRATEGY_RUNTIME_DISABLED";
   runtime.persistence_root="";
   runtime.account_fingerprint="";
   runtime.broker_server="";
   EEA_S02ResearchSeedConfig(runtime.config);
   for(int i=0;i<EEA_STRATEGY_RUNTIME_MAX_SYMBOLS;i++)
     {
      EEA_S02Init(runtime.engines[i],"","M5","");
      EEA_S02ClearCandidate(runtime.candidates[i]);
      runtime.has_candidate[i]=false;
     }
  }

bool EEA_StrategyCandidateRuntimeInit(EEA_StrategyCandidateRuntime &runtime,
                                      const string &canonical[],const int count,
                                      const EEA_S02Config &config,const bool enabled)
  {
   EEA_StrategyCandidateRuntimeDefaults(runtime);
   runtime.enabled=enabled;
   runtime.config=config;
   runtime.config_version=config.config_version;
   runtime.symbol_count=count;
   if(!enabled)
     { runtime.initialized=true; runtime.reason_code="EEA_STRATEGY_RUNTIME_DISABLED"; return true; }
   // The offline research seed is never accepted as a live runtime config.
   if(config.config_version=="" || config.config_version=="s02-offline-research-v0.1.0" ||
      !EEA_S02ConfigValid(config) || count<1 || count>EEA_STRATEGY_RUNTIME_MAX_SYMBOLS)
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_CONFIG_INVALID"; return false; }
   for(int i=0;i<count;i++)
     {
      if(canonical[i]=="") { runtime.reason_code="EEA_STRATEGY_RUNTIME_SYMBOL_INVALID"; return false; }
      EEA_S02Init(runtime.engines[i],canonical[i],runtime.timeframe,config.config_version);
      EEA_S02ClearCandidate(runtime.candidates[i]);
      runtime.has_candidate[i]=false;
     }
   runtime.initialized=true;
   runtime.reason_code="EEA_STRATEGY_RUNTIME_READY";
   return true;
  }

void EEA_StrategyRuntimeConfigurePersistence(EEA_StrategyCandidateRuntime &runtime,
                                              const string root,const string account_fingerprint,
                                              const string broker_server)
  {
   runtime.persistence_root=root;
   runtime.account_fingerprint=account_fingerprint;
   runtime.broker_server=broker_server;
  }

bool EEA_StrategyRuntimeLoadCheckpoints(EEA_StrategyCandidateRuntime &runtime,
                                        const long now_utc,const long max_age_seconds)
  {
   if(!runtime.enabled) return true;
   if(runtime.persistence_root=="" || runtime.account_fingerprint=="" || runtime.broker_server=="")
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_PERSISTENCE_IDENTITY_MISSING"; return false; }
   for(int i=0;i<runtime.symbol_count;i++)
     {
      bool has=false;
      EEA_StrategyCandidateLoadStatus status=EEA_StrategyCandidateStoreLoad(
         EEA_StrategyCandidateStorePath(runtime.persistence_root,runtime.engines[i].canonical_symbol),
         runtime.config_version,runtime.account_fingerprint,runtime.broker_server,
         runtime.engines[i].canonical_symbol,runtime.timeframe,now_utc,max_age_seconds,
         runtime.engines[i],has);
      if(status==EEA_CANDIDATE_CHECKPOINT_LOADED)
        {
         runtime.has_candidate[i]=has;
         runtime.candidates[i]=runtime.engines[i].candidate;
        }
      else if(status==EEA_CANDIDATE_CHECKPOINT_MISSING || status==EEA_CANDIDATE_CHECKPOINT_STALE ||
              status==EEA_CANDIDATE_CHECKPOINT_IDENTITY_MISMATCH)
        {
         runtime.has_candidate[i]=false;
         EEA_S02Init(runtime.engines[i],runtime.engines[i].canonical_symbol,runtime.timeframe,runtime.config_version);
        }
      else
        { runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINT_CORRUPT"; return false; }
     }
   runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINTS_LOADED";
   return true;
  }

bool EEA_StrategyRuntimeWriteCheckpoints(const EEA_StrategyCandidateRuntime &runtime,
                                         const long observed_at_utc)
  {
   if(!runtime.enabled) return true;
   if(runtime.persistence_root=="" || runtime.account_fingerprint=="" || runtime.broker_server=="") return false;
   for(int i=0;i<runtime.symbol_count;i++)
      if(!EEA_StrategyCandidateStoreWrite(
            EEA_StrategyCandidateStorePath(runtime.persistence_root,runtime.engines[i].canonical_symbol),
            runtime.config_version,runtime.account_fingerprint,runtime.broker_server,
            runtime.engines[i],runtime.has_candidate[i],observed_at_utc)) return false;
   return true;
  }

bool EEA_StrategyRuntimeNoTransition(EEA_S02Engine &engine,EEA_S02Event &event,
                                     const EEA_S02Bar &bar,const string reason)
  {
   if(bar.closed_at_utc<=engine.last_processed_bar_utc) return false;
   engine.last_processed_bar_utc=bar.closed_at_utc;
   event.bar_time_utc=bar.closed_at_utc;
   event.event_type="NO_TRANSITION";
   event.state_before=EEA_S02StateName(engine.state);
   event.state_after=EEA_S02StateName(engine.state);
   event.reason_code=reason;
   event.candidate_id=engine.candidate.candidate_id;
   event.canonical_symbol=engine.canonical_symbol;
   event.timeframe=engine.timeframe;
   event.config_version=engine.config_version;
   return true;
  }

bool EEA_StrategyRuntimeScanSymbol(EEA_StrategyCandidateRuntime &runtime,
                                   const int index,const string broker_symbol)
  {
   if(!runtime.enabled || !runtime.initialized || index<0 || index>=runtime.symbol_count ||
      broker_symbol=="") return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   int copied=CopyRates(broker_symbol,PERIOD_M5,1,EEA_STRATEGY_RUNTIME_LOOKBACK_BARS+1,rates);
   if(copied<EEA_STRATEGY_RUNTIME_LOOKBACK_BARS+1)
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_BARS_UNAVAILABLE"; return false; }
   int atr_handle=iATR(broker_symbol,PERIOD_M5,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
   if(atr_handle==INVALID_HANDLE)
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_ATR_UNAVAILABLE"; return false; }
   double atr_values[];
   ArraySetAsSeries(atr_values,true);
   int atr_copied=CopyBuffer(atr_handle,0,1,1,atr_values);
   IndicatorRelease(atr_handle);
   if(atr_copied!=1 || !MathIsValidNumber(atr_values[0]) || atr_values[0]<=0.0)
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_ATR_INVALID"; return false; }

   EEA_S02Bar bar;
   bar.closed_at_utc=rates[0].time;
   bar.open=rates[0].open;
   bar.high=rates[0].high;
   bar.low=rates[0].low;
   bar.close=rates[0].close;
   bar.atr=atr_values[0];
   EEA_S02Engine engine=runtime.engines[index];
   EEA_S02Event event;
   double range_high=rates[1].high;
   double range_low=rates[1].low;
   for(int i=2;i<copied;i++)
     { range_high=MathMax(range_high,rates[i].high); range_low=MathMin(range_low,rates[i].low); }

   // The closed bar is allowed to create a setup only when it breaks the
   // explicit lookback range. Before that, advance time without letting the
   // generic S02 engine infer the opposite direction from a range level.
   if(engine.state==EEA_S02_IDLE)
     {
      bool breaks_long=bar.close>range_high+runtime.config.break_buffer_atr*bar.atr;
      bool breaks_short=bar.close<range_low-runtime.config.break_buffer_atr*bar.atr;
      if(!breaks_long && !breaks_short)
        {
         bool advanced=EEA_StrategyRuntimeNoTransition(engine,event,bar,"WAITING_FOR_LOOKBACK_BREAK");
         runtime.engines[index]=engine;
         return advanced;
        }
      double key_level=(breaks_long ? range_high : range_low);
      if(!EEA_S02ProcessClosedBar(engine,bar,key_level,runtime.config,event))
        { runtime.engines[index]=engine; return false; }
     }
   else
     {
      if(!EEA_S02ProcessClosedBar(engine,bar,engine.key_level,runtime.config,event))
        { runtime.engines[index]=engine; return false; }
     }
   runtime.engines[index]=engine;
   if(engine.state==EEA_S02_TRIGGERED)
     {
      runtime.candidates[index]=engine.candidate;
      runtime.candidates[index].state=engine.candidate.state;
      runtime.has_candidate[index]=true;
     }
   else if(EEA_S02IsTerminal(engine.state))
      runtime.has_candidate[index]=false;
   runtime.reason_code="EEA_STRATEGY_RUNTIME_SCANNED";
   return true;
  }

bool EEA_StrategyRuntimeOnTimer(EEA_StrategyCandidateRuntime &runtime,
                                const string &canonical[],const string &broker[],const int count)
  {
   if(!runtime.enabled) return true;
   if(!runtime.initialized || count!=runtime.symbol_count) return false;
   for(int i=0;i<count;i++)
      if(!EEA_StrategyRuntimeScanSymbol(runtime,i,broker[i])) return false;
   runtime.last_scan_utc=(long)TimeGMT();
   return true;
  }

#endif
