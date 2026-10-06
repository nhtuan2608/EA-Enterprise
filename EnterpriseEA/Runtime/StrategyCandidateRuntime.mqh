#ifndef ENTERPRISE_EA_STRATEGY_CANDIDATE_RUNTIME_MQH
#define ENTERPRISE_EA_STRATEGY_CANDIDATE_RUNTIME_MQH

#include "../Setups/BreakRetest.mqh"
#include "../Setups/FailedBreak.mqh"
#include "../Setups/CompressionExpansion.mqh"
#include "../Setups/DonchianTrend.mqh"
#include "../Storage/StrategyCandidateStore.mqh"
#include "../Market/ConfluenceLevels.mqh"

#define EEA_STRATEGY_RUNTIME_MAX_SYMBOLS 32
// S02 v1 runs a SCALP and a SWING engine per symbol; S04 (G9) adds two more and S06
// (G12) one SWING engine.
#define EEA_STRATEGY_RUNTIME_MAX_ENGINES 128
#define EEA_S04_MODE_OFF 0
#define EEA_S04_MODE_SHADOW 1      // detect and record the would-be trade, never submit
#define EEA_S04_MODE_LIVE 2
#define EEA_S02_SCALP_LEVEL_BARS 200        // H1: previous day, sessions, 5 days of swings
#define EEA_S02_SWING_LEVEL_BARS 320        // H4: previous week and about 8 weeks of swings
#define EEA_S02_MIN_LEVEL_BARS 48
#define EEA_S02_SWING_WING 3
#define EEA_S02_SCALP_SWING_LOOKBACK 120     // H1 bars
#define EEA_S02_SWING_SWING_LOOKBACK 240     // H4 bars
#define EEA_S02_HTF_COUNTER_TREND_MODIFIER 0.5
#define EEA_S02_SCALP_CATCHUP_BARS 288      // M5 bars replayed after a restart (24 h)
#define EEA_S02_SWING_CATCHUP_BARS 120      // H1 bars replayed after a restart (5 days)
#define EEA_T2_CATCHUP_BARS 30              // G38 T2: H4 bars replayed after a restart (5 days)
#define EEA_T2_DAILY_BARS 1000              // D1 closes for the EMA200 side (about 4 years to settle)
#define EEA_STRATEGY_CHECKPOINT_MAX_AGE_SECONDS 604800 // 7 days; older checkpoints restart IDLE
#define EEA_STRATEGY_RUNTIME_ATR_PERIOD 14
#define EEA_STRATEGY_RUNTIME_LOOKBACK_BARS 20

struct EEA_StrategyCandidateRuntime
  {
   bool enabled;
   bool initialized;
   string config_version;
   string timeframe;
   EEA_S02Config config;
   EEA_S02Engine engines[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   EEA_S02Candidate candidates[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   bool has_candidate[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   int symbol_count;   // number of engines (prototype: one per symbol; v1: two per symbol)
   bool zone_mode;     // S02 v1 confluence-zone engines
   EEA_S02Config profile_config[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string profile[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string zone_text[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string htf_structure[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   double htf_risk_modifier[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string scan_reason[EEA_STRATEGY_RUNTIME_MAX_ENGINES];
   string setup[EEA_STRATEGY_RUNTIME_MAX_ENGINES];   // S02, S04, S06, S06B or T2
   int s04_mode;       // EEA_S04_MODE_*
   int s06_mode;       // same values: OFF, SHADOW or LIVE
   int s06b_mode;      // S06B (24-bar box, entry on the release bar), same values
   int scalp_mode;     // G26: cap for every SCALP engine (OFF, SHADOW or LIVE)
   int s02_mode;       // same values: OFF, SHADOW or LIVE
   int t2_mode;        // G38/G40: T2 (H4 Donchian, POSITION profile), OFF, SHADOW or LIVE
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
   runtime.zone_mode=false;
   runtime.s04_mode=EEA_S04_MODE_OFF;
   runtime.s06_mode=EEA_S04_MODE_OFF;
   runtime.s06b_mode=EEA_S04_MODE_OFF;
   runtime.scalp_mode=EEA_S04_MODE_LIVE;
   runtime.s02_mode=EEA_S04_MODE_LIVE;
   runtime.t2_mode=EEA_S04_MODE_OFF;
   EEA_S02ResearchSeedConfig(runtime.config);
   for(int i=0;i<EEA_STRATEGY_RUNTIME_MAX_ENGINES;i++)
     {
      EEA_S02Init(runtime.engines[i],"","M5","");
      EEA_S02ResearchSeedConfig(runtime.profile_config[i]);
      runtime.profile[i]="PROTOTYPE";
      runtime.zone_text[i]="";
      runtime.htf_structure[i]="NEUTRAL";
      runtime.htf_risk_modifier[i]=1.0;
      runtime.scan_reason[i]="";
      runtime.setup[i]="S02";
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
      runtime.profile_config[i]=config;
     }
   runtime.initialized=true;
   runtime.reason_code="EEA_STRATEGY_RUNTIME_READY";
   return true;
  }

// Entry mode of a setup: OFF, SHADOW (record only) or LIVE.
int EEA_StrategyRuntimeSetupMode(const EEA_StrategyCandidateRuntime &runtime,const string setup)
  { return setup=="S04" ? runtime.s04_mode : setup=="S06" ? runtime.s06_mode : setup=="S06B" ? runtime.s06b_mode :
           setup=="T2" ? runtime.t2_mode : runtime.s02_mode; }

// G26: the mode an engine actually runs in: its setup's mode, capped by the SCALP mode for
// SCALP engines (OFF < SHADOW < LIVE). Every entry, shadow and ledger decision uses this.
int EEA_StrategyRuntimeEngineMode(const EEA_StrategyCandidateRuntime &runtime,const int index)
  {
   const int mode=EEA_StrategyRuntimeSetupMode(runtime,runtime.setup[index]);
   return runtime.profile[index]=="SCALP" ? MathMin(mode,runtime.scalp_mode) : mode;
  }

string EEA_SetupModeName(const int mode)
  { return mode==EEA_S04_MODE_LIVE ? "LIVE" : mode==EEA_S04_MODE_SHADOW ? "SHADOW" : "OFF"; }

// Engines per symbol: S02 SCALP, S02 SWING, then S04 SCALP, S04 SWING unless S04 is OFF,
// then S06 SWING unless S06 is OFF, then S06B SWING unless S06B is OFF, then T2 POSITION (H4)
// unless T2 is OFF.
int EEA_StrategyRuntimeStride(const EEA_StrategyCandidateRuntime &runtime)
  {
   return 2+(runtime.s04_mode==EEA_S04_MODE_OFF ? 0 : 2)+(runtime.s06_mode==EEA_S04_MODE_OFF ? 0 : 1)+
          (runtime.s06b_mode==EEA_S04_MODE_OFF ? 0 : 1)+(runtime.t2_mode==EEA_S04_MODE_OFF ? 0 : 1);
  }

// Slot p of a symbol: setup, profile, entry timeframe and the v1 seed config of that slot.
void EEA_StrategyRuntimeSlot(const EEA_StrategyCandidateRuntime &runtime,const int p,string &setup,
                             string &profile,string &timeframe,EEA_S02Config &config)
  {
   const int base=2+(runtime.s04_mode==EEA_S04_MODE_OFF ? 0 : 2);
   const int s06_slots=(runtime.s06_mode==EEA_S04_MODE_OFF ? 0 : 1)+(runtime.s06b_mode==EEA_S04_MODE_OFF ? 0 : 1);
   if(runtime.t2_mode!=EEA_S04_MODE_OFF && p==base+s06_slots)
     {
      setup="T2"; profile="POSITION"; timeframe="H4"; EEA_T2V1Config(config);
      return;
     }
   if(p>=base)
     {
      profile="SWING"; timeframe="H1";
      if(p==base && runtime.s06_mode!=EEA_S04_MODE_OFF) { setup="S06"; EEA_S06V1Config(config); }
      else { setup="S06B"; EEA_S06BV1Config(config); }
      return;
     }
   setup=(p<2 ? "S02" : "S04");
   profile=(p%2==0 ? "SCALP" : "SWING");
   timeframe=(p%2==0 ? "M5" : "H1");
   if(setup=="S04") EEA_S04V1Config(config,profile);
   else EEA_S02V1Config(config,profile);
  }

// S02 v1: a SCALP (M5) and a SWING (H1) engine per symbol with the v1 seed configs.
bool EEA_StrategyCandidateRuntimeInitV1(EEA_StrategyCandidateRuntime &runtime,
                                        const string &canonical[],const int count,const bool enabled,
                                        const int s04_mode=EEA_S04_MODE_OFF,
                                        const int s02_mode=EEA_S04_MODE_LIVE,
                                        const int s06_mode=EEA_S04_MODE_OFF,
                                        const int s06b_mode=EEA_S04_MODE_OFF,
                                        const int scalp_mode=EEA_S04_MODE_LIVE,
                                        const int t2_mode=EEA_S04_MODE_OFF)
  {
   EEA_StrategyCandidateRuntimeDefaults(runtime);
   runtime.enabled=enabled;
   runtime.zone_mode=true;
   runtime.t2_mode=t2_mode;
   runtime.s04_mode=s04_mode;
   runtime.s06_mode=s06_mode;
   runtime.s06b_mode=s06b_mode;
   runtime.scalp_mode=scalp_mode;
   runtime.s02_mode=s02_mode;
   EEA_S02V1Config(runtime.config,"SCALP");
   runtime.config_version="s02-v1";
   if(!enabled)
     { runtime.initialized=true; runtime.reason_code="EEA_STRATEGY_RUNTIME_DISABLED"; return true; }
   const int stride=EEA_StrategyRuntimeStride(runtime);
   if(count<1 || count*stride>EEA_STRATEGY_RUNTIME_MAX_ENGINES)
     { runtime.reason_code="EEA_STRATEGY_RUNTIME_CONFIG_INVALID"; return false; }
   int engine_count=0;
   for(int i=0;i<count;i++)
     {
      if(canonical[i]=="") { runtime.reason_code="EEA_STRATEGY_RUNTIME_SYMBOL_INVALID"; return false; }
      for(int p=0;p<stride;p++)
        {
         string setup,profile,timeframe;
         EEA_StrategyRuntimeSlot(runtime,p,setup,profile,timeframe,runtime.profile_config[engine_count]);
         if(!EEA_S02ConfigValid(runtime.profile_config[engine_count]))
           { runtime.reason_code="EEA_STRATEGY_RUNTIME_CONFIG_INVALID"; return false; }
         runtime.profile[engine_count]=profile;
         runtime.setup[engine_count]=setup;
         EEA_S02Init(runtime.engines[engine_count],canonical[i],timeframe,
                     runtime.profile_config[engine_count].config_version);
         EEA_S02ClearCandidate(runtime.candidates[engine_count]);
         runtime.has_candidate[engine_count]=false;
         engine_count++;
        }
     }
   runtime.symbol_count=engine_count;
   runtime.initialized=true;
   runtime.reason_code="EEA_STRATEGY_RUNTIME_READY";
   return true;
  }

string EEA_StrategyRuntimeCheckpointPath(const EEA_StrategyCandidateRuntime &runtime,const int index)
  {
   if(!runtime.zone_mode)
      return EEA_StrategyCandidateStorePath(runtime.persistence_root,runtime.engines[index].canonical_symbol);
   return runtime.persistence_root+"/current/strategy_"+runtime.engines[index].canonical_symbol+"_"+
          runtime.engines[index].timeframe+(runtime.setup[index]=="S04" ? "_s04" :
                                            runtime.setup[index]=="S06" ? "_s06" :
                                            runtime.setup[index]=="S06B" ? "_s06b" :
                                            runtime.setup[index]=="T2" ? "_t2" : "")+".json";
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
      if(!EEA_StrategyRuntimeLoadEngine(runtime,i,now_utc,max_age_seconds))
        { runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINT_CORRUPT"; return false; }
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
            EEA_StrategyRuntimeCheckpointPath(runtime,i),
            runtime.engines[i].config_version,runtime.account_fingerprint,runtime.broker_server,
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

// Simple-average true range over `period` bars ending at `last` (oldest-first rates),
// matching MT5 iATR without depending on an indicator handle being ready.
double EEA_StrategyRuntimeAtrFromRates(const MqlRates &rates[],const int last,const int period)
  {
   if(period<1 || last<period) return 0.0;
   double sum=0.0;
   for(int i=last-period+1;i<=last;i++)
     {
      double prev_close=rates[i-1].close;
      double tr=MathMax(rates[i].high,prev_close)-MathMin(rates[i].low,prev_close);
      sum+=tr;
     }
   double atr=sum/period;
   return MathIsValidNumber(atr) && atr>0.0 ? atr : 0.0;
  }

// Level points, context ATR and level bars for one profile, taken from the profile's
// level timeframe (H1 for SCALP, H4 for SWING). Shared by zone building and by the
// structural take-profit selection so both use the same levels.
bool EEA_StrategyRuntimeCollectLevels(const string broker_symbol,const bool swing,
                                      EEA_LevelPoint &points[],int &point_count,
                                      EEA_LevelBar &bars[],int &level_count,
                                      double &context_atr,string &reason)
  {
   point_count=0; level_count=0; context_atr=0.0;
   ENUM_TIMEFRAMES level_tf=swing ? PERIOD_H4 : PERIOD_H1;
   int level_wanted=swing ? EEA_S02_SWING_LEVEL_BARS : EEA_S02_SCALP_LEVEL_BARS;
   MqlRates level_rates[];
   ArraySetAsSeries(level_rates,false);
   level_count=CopyRates(broker_symbol,level_tf,1,level_wanted,level_rates);
   if(level_count<EEA_S02_MIN_LEVEL_BARS)
     { reason="EEA_STRATEGY_RUNTIME_LEVEL_BARS_UNAVAILABLE"; return false; }
   context_atr=EEA_StrategyRuntimeAtrFromRates(level_rates,level_count-1,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
   if(context_atr<=0.0) { reason="EEA_STRATEGY_RUNTIME_CONTEXT_ATR_INVALID"; return false; }
   ArrayResize(bars,level_count);
   for(int i=0;i<level_count;i++)
     {
      bars[i].time=(long)level_rates[i].time; bars[i].open=level_rates[i].open;
      bars[i].high=level_rates[i].high; bars[i].low=level_rates[i].low; bars[i].close=level_rates[i].close;
     }
   long now_server=(long)TimeTradeServer();
   long offset=(long)MathRound(((double)now_server-(double)TimeGMT())/900.0)*900;
   EEA_StrategyRuntimeLevelsFromBars(bars,level_count,swing,now_server,offset,points,point_count);
   reason="LEVELS_COLLECTED";
   return true;
  }

// Pure level extraction for one profile as seen at now_server (also used by the replay).
void EEA_StrategyRuntimeLevelsFromBars(const EEA_LevelBar &bars[],const int level_count,const bool swing,
                                       const long now_server,const long offset,
                                       EEA_LevelPoint &points[],int &point_count)
  {
   point_count=0;
   EEA_LevelsPreviousDay(bars,level_count,now_server,points,point_count);
   if(swing)
     {
      EEA_LevelsPreviousWeek(bars,level_count,now_server,points,point_count);
      EEA_LevelsSwings(bars,level_count,EEA_S02_SWING_WING,EEA_S02_SWING_SWING_LOOKBACK,points,point_count);
     }
   else
     {
      EEA_LevelsSession(bars,level_count,now_server,offset,0,7,points,point_count);   // Asia
      EEA_LevelsSession(bars,level_count,now_server,offset,7,12,points,point_count);  // London
      EEA_LevelsSession(bars,level_count,now_server,offset,12,21,points,point_count); // New York
      EEA_LevelsSwings(bars,level_count,EEA_S02_SWING_WING,EEA_S02_SCALP_SWING_LOOKBACK,points,point_count);
     }
  }

// Nearest structural level in the trade direction at least min_distance beyond entry
// (design section 8). Any single source counts as a target.
bool EEA_S02V1StructuralTarget(const EEA_LevelPoint &points[],const int point_count,const int direction,
                               const double entry,const double min_distance,double &target)
  {
   target=0.0;
   double best=0.0;
   for(int i=0;i<point_count;i++)
     {
      double distance=direction*(points[i].price-entry);
      if(distance<min_distance) continue;
      if(target<=0.0 || distance<best) { best=distance; target=points[i].price; }
     }
   return target>0.0;
  }

// Zones and HTF structure for one engine.
bool EEA_StrategyRuntimeBuildZones(EEA_StrategyCandidateRuntime &runtime,const int index,
                                   const string broker_symbol,const bool swing,
                                   EEA_ConfluenceZone &zones[],int &zone_count,string &structure)
  {
   EEA_LevelPoint points[];
   EEA_LevelBar bars[];
   int point_count=0, level_count=0;
   double context_atr=0.0;
   string reason;
   if(!EEA_StrategyRuntimeCollectLevels(broker_symbol,swing,points,point_count,bars,level_count,context_atr,reason))
     { runtime.scan_reason[index]=reason; return false; }
   zone_count=EEA_BuildConfluenceZones(points,point_count,0.25*context_atr,0.5*context_atr,2,zones);
   structure=EEA_HtfStructure(bars,level_count,EEA_S02_SWING_WING);
   runtime.htf_structure[index]=structure;
   return true;
  }

// One closed entry bar through the zone engine.
bool EEA_StrategyRuntimeZoneStep(EEA_StrategyCandidateRuntime &runtime,const int index,
                                 EEA_S02Engine &engine,const EEA_S02Bar &bar,
                                 const EEA_ConfluenceZone &zones[],const int zone_count,
                                 const int digits,EEA_S02Event &event)
  {
   EEA_S02Config config=runtime.profile_config[index];
   if(engine.state==EEA_S02_IDLE || EEA_S02IsTerminal(engine.state))
     {
      // Only a qualified confluence zone crossed by this closed bar can start a setup.
      int pick=-1;
      for(int z=0;z<zone_count && pick<0;z++)
        {
         if(!zones[z].qualified) continue;
         if(bar.open<=zones[z].high && bar.close>zones[z].high) pick=z;
         else if(bar.open>=zones[z].low && bar.close<zones[z].low) pick=z;
        }
      int qualified=0, nearest=-1; double nearest_distance=0.0;
      for(int z=0;z<zone_count;z++)
        {
         if(!zones[z].qualified) continue;
         qualified++;
         double distance=MathMin(MathAbs(bar.close-zones[z].low),MathAbs(bar.close-zones[z].high));
         if(nearest<0 || distance<nearest_distance) { nearest=z; nearest_distance=distance; }
        }
      runtime.zone_text[index]=nearest<0 ? "no qualified zone" :
         DoubleToString(zones[nearest].low,digits)+"-"+DoubleToString(zones[nearest].high,digits)+" "+
         zones[nearest].sources+" ("+IntegerToString(qualified)+" zones)";
      if(pick<0)
        {
         if(!EEA_StrategyRuntimeNoTransition(engine,event,bar,"WAITING_FOR_CONFLUENCE_BREAK")) return false;
         runtime.scan_reason[index]="WAITING_FOR_CONFLUENCE_BREAK";
         return true;
        }
      bool stepped=(runtime.setup[index]=="S04") ?
         EEA_S04ProcessClosedBarZone(engine,bar,zones[pick].low,zones[pick].high,config,event) :
         EEA_S02ProcessClosedBarZone(engine,bar,zones[pick].low,zones[pick].high,config,event);
      if(!stepped) { runtime.scan_reason[index]=event.reason_code; return false; }
      if(engine.state!=EEA_S02_IDLE)
         runtime.zone_text[index]=DoubleToString(engine.zone_low,digits)+"-"+
            DoubleToString(engine.zone_high,digits)+" "+zones[pick].sources;
     }
   else if(runtime.setup[index]=="S04" ?
           !EEA_S04ProcessClosedBarZone(engine,bar,engine.zone_low,engine.zone_high,config,event) :
           !EEA_S02ProcessClosedBarZone(engine,bar,engine.zone_low,engine.zone_high,config,event))
     { runtime.scan_reason[index]=event.reason_code; return false; }
   runtime.scan_reason[index]=event.reason_code;
   if(engine.state==EEA_S02_TRIGGERED)
     {
      runtime.candidates[index]=engine.candidate;
      runtime.has_candidate[index]=true;
     }
   else if(EEA_S02IsTerminal(engine.state))
      runtime.has_candidate[index]=false;
   return true;
  }

// One closed H1 bar through the S06 engine. The box is the EEA_S06_BOX_BARS closed bars
// before bar b; the ATRs are those of bars b-1 and b-EEA_S06_CONTRACTION_LOOKBACK
// (research: bars[i-1].atr and bars[i-48].atr). The caller guarantees the warm-up.
bool EEA_StrategyRuntimeS06Step(EEA_StrategyCandidateRuntime &runtime,const int index,
                                EEA_S02Engine &engine,const MqlRates &rates[],const int b,
                                const EEA_S02Bar &bar,const int digits,EEA_S02Event &event)
  {
   const int box_bars=EEA_S06BoxBars(runtime.profile_config[index]);
   double box_high=rates[b-box_bars].high, box_low=rates[b-box_bars].low;
   for(int k=b-box_bars+1;k<b;k++)
     { box_high=MathMax(box_high,rates[k].high); box_low=MathMin(box_low,rates[k].low); }
   const double ref_atr=EEA_StrategyRuntimeAtrFromRates(rates,b-1,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
   const double old_atr=EEA_StrategyRuntimeAtrFromRates(rates,b-EEA_S06_CONTRACTION_LOOKBACK,
                                                        EEA_STRATEGY_RUNTIME_ATR_PERIOD);
   if(!EEA_S06ProcessClosedBar(engine,bar,box_low,box_high,ref_atr,old_atr,runtime.profile_config[index],event))
     { runtime.scan_reason[index]=event.reason_code; return false; }
   runtime.scan_reason[index]=event.reason_code;
   const double show_low=engine.state!=EEA_S02_IDLE ? engine.zone_low : box_low;
   const double show_high=engine.state!=EEA_S02_IDLE ? engine.zone_high : box_high;
   runtime.zone_text[index]="box "+DoubleToString(show_low,digits)+"-"+DoubleToString(show_high,digits)+
      (EEA_S06Compressed(box_low,box_high,ref_atr,old_atr) ? " compressed" : "");
   if(engine.state==EEA_S02_TRIGGERED)
     {
      runtime.candidates[index]=engine.candidate;
      runtime.has_candidate[index]=true;
     }
   else
      runtime.has_candidate[index]=false;
   return true;
  }

// G38 T2: D1 side for every closed H4 bar of a scan: the previous closed day's close against
// the EMA200 of daily closes (research discovery.d1_side). Daily bars come in time order.
int EEA_StrategyRuntimeT2SideAt(const MqlRates &daily[],const double &ema[],const int daily_count,const datetime bar_time)
  {
   const long day_start=(long)bar_time-((long)bar_time%86400);
   int count=0;
   while(count<daily_count && (long)daily[count].time<day_start) count++;
   if(count<EEA_T2_EMA_DAYS) return 0;
   const double c=daily[count-1].close, e=ema[count-1];
   return c>e ? 1 : (c<e ? -1 : 0);
  }

// G38 T2: closed H4 bars through the Donchian engine, with the restart catch-up and the gap
// reset of the zone engines. The channel is the EEA_T2_CHANNEL_BARS closed bars before each bar.
bool EEA_StrategyRuntimeScanT2Engine(EEA_StrategyCandidateRuntime &runtime,const int index,const string broker_symbol)
  {
   const int warm=EEA_T2_CHANNEL_BARS+EEA_STRATEGY_RUNTIME_ATR_PERIOD+1;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   const int copied=CopyRates(broker_symbol,PERIOD_H4,1,EEA_T2_CATCHUP_BARS+warm+1,rates);
   if(copied<warm+1) { runtime.scan_reason[index]="EEA_STRATEGY_RUNTIME_BARS_UNAVAILABLE"; return false; }
   const int last=copied-1;
   EEA_S02Engine engine=runtime.engines[index];
   if((datetime)rates[last].time<=engine.last_processed_bar_utc) return true;
   int first=last;
   if(engine.last_processed_bar_utc>0)
     {
      first=warm;
      while(first<last && (datetime)rates[first].time<=engine.last_processed_bar_utc) first++;
      if((datetime)rates[warm].time>engine.last_processed_bar_utc && (datetime)rates[warm-1].time>engine.last_processed_bar_utc)
        {
         string canonical=engine.canonical_symbol, timeframe=engine.timeframe, version=engine.config_version;
         EEA_S02Init(engine,canonical,timeframe,version);
         runtime.has_candidate[index]=false;
         runtime.scan_reason[index]="CHECKPOINT_GAP_RESET";
         first=last;
        }
     }
   MqlRates daily[];
   ArraySetAsSeries(daily,false);
   const int daily_count=CopyRates(broker_symbol,PERIOD_D1,0,EEA_T2_DAILY_BARS,daily);
   if(daily_count<EEA_T2_EMA_DAYS+1) { runtime.scan_reason[index]="T2_DAILY_BARS_UNAVAILABLE"; runtime.engines[index]=engine; return false; }
   double ema[];
   ArrayResize(ema,daily_count);
   const double k=2.0/(EEA_T2_EMA_DAYS+1);
   for(int i=0;i<daily_count;i++) ema[i]=(i==0 ? daily[0].close : ema[i-1]+k*(daily[i].close-ema[i-1]));
   const int digits=(int)SymbolInfoInteger(broker_symbol,SYMBOL_DIGITS);
   bool ok=true;
   for(int b=first;b<=last;b++)
     {
      double hi=rates[b-EEA_T2_CHANNEL_BARS].high, lo=rates[b-EEA_T2_CHANNEL_BARS].low;
      for(int j=b-EEA_T2_CHANNEL_BARS+1;j<b;j++) { hi=MathMax(hi,rates[j].high); lo=MathMin(lo,rates[j].low); }
      EEA_S02Bar bar;
      bar.closed_at_utc=rates[b].time;
      bar.open=rates[b].open; bar.high=rates[b].high; bar.low=rates[b].low; bar.close=rates[b].close;
      bar.atr=EEA_StrategyRuntimeAtrFromRates(rates,b,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
      const int side=EEA_StrategyRuntimeT2SideAt(daily,ema,daily_count,rates[b].time);
      EEA_S02Event event;
      if(!EEA_T2ProcessClosedBar(engine,bar,lo,hi,side,runtime.profile_config[index],event))
        { runtime.scan_reason[index]=event.reason_code; ok=false; break; }
      runtime.scan_reason[index]=event.reason_code;
      runtime.zone_text[index]="channel "+DoubleToString(lo,digits)+"-"+DoubleToString(hi,digits)+
                               " D1 "+(side>0 ? "up" : (side<0 ? "down" : "?"));
      if(engine.state==EEA_S02_TRIGGERED) { runtime.candidates[index]=engine.candidate; runtime.has_candidate[index]=true; }
      else runtime.has_candidate[index]=false;
     }
   runtime.engines[index]=engine;
   runtime.htf_risk_modifier[index]=1.0;
   if(ok) runtime.reason_code="EEA_STRATEGY_RUNTIME_SCANNED";
   return ok;
  }

// S02 v1: one engine per (symbol, profile) on closed entry bars (M5 for SCALP, H1 for
// SWING). After a restart the engine replays the entry bars it missed, up to a cap per
// profile; a longer gap resets it to IDLE because its windows have long expired.
// Replayed bars are evaluated against the current zone set (documented approximation).
bool EEA_StrategyRuntimeScanZoneEngine(EEA_StrategyCandidateRuntime &runtime,
                                       const int index,const string broker_symbol)
  {
   if(!runtime.enabled || !runtime.initialized || index<0 || index>=runtime.symbol_count ||
      broker_symbol=="") return false;
   if(runtime.setup[index]=="T2") return EEA_StrategyRuntimeScanT2Engine(runtime,index,broker_symbol);
   bool swing=(runtime.profile[index]=="SWING");
   ENUM_TIMEFRAMES entry_tf=swing ? PERIOD_H1 : PERIOD_M5;
   int catch_up=swing ? EEA_S02_SWING_CATCHUP_BARS : EEA_S02_SCALP_CATCHUP_BARS;
   // S06 compares the ATR with the ATR 48 bars earlier, which needs its own warm-up.
   const bool s06=(runtime.setup[index]=="S06" || runtime.setup[index]=="S06B");
   const int warm=EEA_STRATEGY_RUNTIME_ATR_PERIOD+(s06 ? EEA_S06_CONTRACTION_LOOKBACK : 0);

   MqlRates entry_rates[];
   ArraySetAsSeries(entry_rates,false);
   int entry_copied=CopyRates(broker_symbol,entry_tf,1,catch_up+warm+1,entry_rates);
   if(entry_copied<warm+1)
     { runtime.scan_reason[index]="EEA_STRATEGY_RUNTIME_BARS_UNAVAILABLE"; return false; }
   int last=entry_copied-1;
   EEA_S02Engine engine=runtime.engines[index];
   // Nothing new to evaluate until the next entry bar closes.
   if((datetime)entry_rates[last].time<=engine.last_processed_bar_utc) return true;

   int first=last;
   if(engine.last_processed_bar_utc>0)
     {
      first=warm;
      while(first<last && (datetime)entry_rates[first].time<=engine.last_processed_bar_utc) first++;
      bool gap_too_large=((datetime)entry_rates[warm].time>engine.last_processed_bar_utc &&
                          (datetime)entry_rates[warm-1].time>engine.last_processed_bar_utc);
      if(gap_too_large)
        {
         string canonical=engine.canonical_symbol, timeframe=engine.timeframe, version=engine.config_version;
         EEA_S02Init(engine,canonical,timeframe,version);
         runtime.has_candidate[index]=false;
         runtime.scan_reason[index]="CHECKPOINT_GAP_RESET";
         first=last;
        }
     }

   EEA_ConfluenceZone zones[];
   int zone_count=0;
   string structure="NEUTRAL";
   if(!EEA_StrategyRuntimeBuildZones(runtime,index,broker_symbol,swing,zones,zone_count,structure))
     { runtime.engines[index]=engine; return false; }
   int digits=(int)SymbolInfoInteger(broker_symbol,SYMBOL_DIGITS);
   bool ok=true;
   for(int b=first;b<=last;b++)
     {
      double atr=EEA_StrategyRuntimeAtrFromRates(entry_rates,b,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
      if(atr<=0.0) { runtime.scan_reason[index]="EEA_STRATEGY_RUNTIME_ATR_INVALID"; ok=false; break; }
      EEA_S02Bar bar;
      bar.closed_at_utc=entry_rates[b].time;
      bar.open=entry_rates[b].open; bar.high=entry_rates[b].high;
      bar.low=entry_rates[b].low; bar.close=entry_rates[b].close;
      bar.atr=atr;
      EEA_S02Event event;
      if(s06)
        {
         if(!EEA_StrategyRuntimeS06Step(runtime,index,engine,entry_rates,b,bar,digits,event)) { ok=false; break; }
         continue;
        }
      if(!EEA_StrategyRuntimeZoneStep(runtime,index,engine,bar,zones,zone_count,digits,event)) { ok=false; break; }
     }
   runtime.engines[index]=engine;
   runtime.htf_risk_modifier[index]=engine.direction!=0 ?
      EEA_HtfRiskModifier(structure,engine.direction,EEA_S02_HTF_COUNTER_TREND_MODIFIER) : 1.0;
   if(ok) runtime.reason_code="EEA_STRATEGY_RUNTIME_SCANNED";
   return ok;
  }

// Loads one engine's checkpoint. Missing, stale or foreign checkpoints start the
// engine fresh; a corrupt checkpoint is reported so the caller fails closed.
bool EEA_StrategyRuntimeLoadEngine(EEA_StrategyCandidateRuntime &runtime,const int i,
                                   const long now_utc,const long max_age_seconds)
  {
   bool has=false;
   string path=EEA_StrategyRuntimeCheckpointPath(runtime,i);
   string canonical=runtime.engines[i].canonical_symbol;
   string timeframe=runtime.engines[i].timeframe;
   string version=runtime.engines[i].config_version;
   EEA_StrategyCandidateLoadStatus status=EEA_StrategyCandidateStoreLoad(
      path,version,runtime.account_fingerprint,runtime.broker_server,
      canonical,timeframe,now_utc,max_age_seconds,runtime.engines[i],has);
   if(status==EEA_CANDIDATE_CHECKPOINT_LOADED)
     {
      runtime.has_candidate[i]=has;
      runtime.candidates[i]=runtime.engines[i].candidate;
      if(runtime.zone_mode && runtime.engines[i].state!=EEA_S02_IDLE)
         runtime.zone_text[i]="restored "+DoubleToString(runtime.engines[i].zone_low,8)+"-"+
                              DoubleToString(runtime.engines[i].zone_high,8);
      return true;
     }
   runtime.has_candidate[i]=false;
   EEA_S02Init(runtime.engines[i],canonical,timeframe,version);
   return status==EEA_CANDIDATE_CHECKPOINT_MISSING || status==EEA_CANDIDATE_CHECKPOINT_STALE ||
          status==EEA_CANDIDATE_CHECKPOINT_IDENTITY_MISMATCH;
  }

// Keeps the v1 engine list aligned with the live symbol selection (restored at
// start-up or changed in Settings). Running engines are kept by identity; engines
// for new symbols load their own checkpoint when persistence is configured.
bool EEA_StrategyRuntimeSyncSymbols(EEA_StrategyCandidateRuntime &runtime,const string &canonical[],
                                    const int count,const long now_utc,const long max_age_seconds)
  {
   if(!runtime.enabled || !runtime.zone_mode) return true;
   const int stride=EEA_StrategyRuntimeStride(runtime);
   if(count<1 || count*stride>EEA_STRATEGY_RUNTIME_MAX_ENGINES) return false;
   bool same=(runtime.symbol_count==count*stride);
   for(int i=0;i<count && same;i++)
      if(runtime.engines[stride*i].canonical_symbol!=canonical[i]) same=false;
   if(same) return true;
   EEA_StrategyCandidateRuntime next=runtime;
   bool persistence=(runtime.persistence_root!="" && runtime.account_fingerprint!="" && runtime.broker_server!="");
   bool ok=true;
   int e=0;
   for(int i=0;i<count;i++)
     {
      if(canonical[i]=="") return false;
      for(int p=0;p<stride;p++)
        {
         string setup,profile,timeframe;
         EEA_S02Config slot_config;
         EEA_StrategyRuntimeSlot(runtime,p,setup,profile,timeframe,slot_config);
         int old=-1;
         for(int j=0;j<runtime.symbol_count;j++)
            if(runtime.engines[j].canonical_symbol==canonical[i] && runtime.engines[j].timeframe==timeframe &&
               runtime.setup[j]==setup) { old=j; break; }
         if(old>=0)
           {
            next.engines[e]=runtime.engines[old]; next.candidates[e]=runtime.candidates[old];
            next.has_candidate[e]=runtime.has_candidate[old]; next.profile_config[e]=runtime.profile_config[old];
            next.profile[e]=runtime.profile[old]; next.zone_text[e]=runtime.zone_text[old];
            next.htf_structure[e]=runtime.htf_structure[old]; next.htf_risk_modifier[e]=runtime.htf_risk_modifier[old];
            next.scan_reason[e]=runtime.scan_reason[old]; next.setup[e]=runtime.setup[old];
           }
         else
           {
            next.profile_config[e]=slot_config;
            next.profile[e]=profile;
            next.setup[e]=setup;
            EEA_S02Init(next.engines[e],canonical[i],timeframe,next.profile_config[e].config_version);
            EEA_S02ClearCandidate(next.candidates[e]);
            next.has_candidate[e]=false; next.zone_text[e]=""; next.htf_structure[e]="NEUTRAL";
            next.htf_risk_modifier[e]=1.0; next.scan_reason[e]="";
           }
         e++;
        }
     }
   next.symbol_count=e;
   for(int k=0;k<e && persistence;k++)
     {
      bool fresh=true;
      for(int j=0;j<runtime.symbol_count;j++)
         if(runtime.engines[j].canonical_symbol==next.engines[k].canonical_symbol &&
            runtime.engines[j].timeframe==next.engines[k].timeframe && runtime.setup[j]==next.setup[k]) { fresh=false; break; }
      if(fresh && !EEA_StrategyRuntimeLoadEngine(next,k,now_utc,max_age_seconds)) ok=false;
     }
   runtime=next;
   if(!ok) runtime.reason_code="EEA_STRATEGY_RUNTIME_CHECKPOINT_CORRUPT";
   return ok;
  }

bool EEA_StrategyRuntimeOnTimer(EEA_StrategyCandidateRuntime &runtime,
                                const string &canonical[],const string &broker[],const int count)
  {
   if(!runtime.enabled) return true;
   if(!runtime.initialized) return false;
   // Engines are matched to the live selection by canonical name, never by row
   // index. A symbol that is not selected or is UNRESOLVED (SYM-02) is skipped
   // on its own; a scan failure on one symbol does not stop the others.
   bool all_scanned=true;
   for(int e=0;e<runtime.symbol_count;e++)
     {
      int row=-1;
      for(int k=0;k<count;k++)
         if(canonical[k]==runtime.engines[e].canonical_symbol) { row=k; break; }
      if(row<0 || broker[row]=="") continue;
      bool scanned=runtime.zone_mode ? EEA_StrategyRuntimeScanZoneEngine(runtime,e,broker[row]) :
                                      EEA_StrategyRuntimeScanSymbol(runtime,e,broker[row]);
      if(!scanned) all_scanned=false;
     }
   runtime.last_scan_utc=(long)TimeGMT();
   return all_scanned;
  }

#endif
