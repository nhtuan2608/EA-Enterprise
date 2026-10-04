#ifndef ENTERPRISE_EA_SETUP_REPLAY_MQH
#define ENTERPRISE_EA_SETUP_REPLAY_MQH

#include "StrategyCandidateRuntime.mqh"
#include "../News/NewsCalendar.mqh"
#include "../News/NewsReaction.mqh"
#include "../Storage/AtomicWriter.mqh"

// Historical replay of S02 and S04 (G9, D6). Measurement only: the same engines run over
// past closed entry bars with the confluence zones rebuilt from the level bars that were
// closed at that time. Each triggered candidate is evaluated as a market entry at the
// trigger close with the live stop/target rules, then followed forward bar by bar. No
// order is ever sent and nothing here feeds the live decision path.
// Outputs: logs/setup_replay.jsonl (one line per candidate) and current/setup_replay.json.

#define EEA_REPLAY_MAX_JOBS 128
#define EEA_REPLAY_SCALP_HORIZON 48     // M5 bars followed after the trigger (4 h)
#define EEA_REPLAY_SWING_HORIZON 72     // H1 bars followed after the trigger (3 days)
#define EEA_REPLAY_VERSION "setup-replay-v1"

struct EEA_ReplayStats
  {
   int candidates;      // triggered candidates
   int no_target;       // no structural target: live would skip
   int rr_low;          // target closer than the minimum RR: live would skip
   int taken;           // plan valid
   int tp_first;
   int sl_first;
   int open_end;        // neither hit within the horizon
   int reached_1r;
   double sum_bars_1r;
   double sum_mfe_r;
   double sum_mae_r;
   double sum_result_r; // TP = +RR, SL = -1, open = close at horizon in R
  };

struct EEA_ReplayJob
  {
   string canonical;
   string broker;
   string setup;
   string profile;
   bool done;
   string reason;
   EEA_ReplayStats stats;
  };

struct EEA_ReplayRuntime
  {
   bool enabled;
   bool loaded;
   bool complete;
   string root;
   long from_utc;
   long until_server;
   int count;
   int next;
   string reason;
   EEA_ReplayJob jobs[EEA_REPLAY_MAX_JOBS];
  };

struct EEA_ReplayOutcome
  {
   bool valid;
   string reason;
   double entry;
   double stop;
   double target;
   double rr;
   string result;     // TP | SL | OPEN
   double result_r;
   double mfe_r;
   double mae_r;
   int bars_1r;       // -1 when 1R was never reached
  };

void EEA_ReplayStatsReset(EEA_ReplayStats &s)
  {
   s.candidates=0; s.no_target=0; s.rr_low=0; s.taken=0; s.tp_first=0; s.sl_first=0; s.open_end=0;
   s.reached_1r=0; s.sum_bars_1r=0.0; s.sum_mfe_r=0.0; s.sum_mae_r=0.0; s.sum_result_r=0.0;
  }

void EEA_SetupReplayInit(EEA_ReplayRuntime &rt,const string root,const bool enabled,const long from_utc)
  {
   rt.enabled=enabled; rt.loaded=false; rt.complete=false; rt.root=root; rt.from_utc=from_utc;
   rt.until_server=0; rt.count=0; rt.next=0; rt.reason=enabled ? "REPLAY_WAITING" : "REPLAY_DISABLED";
  }

string EEA_SetupReplaySummaryPath(const string root) { return root+"/current/setup_replay.json"; }

// Forward evaluation of one candidate (pure: bars, indices and levels are supplied).
// Within one bar a stop touch wins over a target touch (conservative).
bool EEA_SetupReplayEvaluate(const MqlRates &rates[],const int count,const int trigger,const int direction,
                             const double extreme,const double atr,const double spread_price,
                             const double far_edge,const bool s04,const EEA_LevelPoint &points[],
                             const int point_count,const double min_rr,const int horizon,EEA_ReplayOutcome &o)
  {
   o.valid=false; o.reason=""; o.entry=rates[trigger].close; o.stop=0.0; o.target=0.0; o.rr=0.0;
   o.result="NONE"; o.result_r=0.0; o.mfe_r=0.0; o.mae_r=0.0; o.bars_1r=-1;
   double buffer=MathMax(0.10*atr,1.5*spread_price);
   o.stop=(direction==1 ? extreme-buffer : extreme+buffer);
   double risk=direction*(o.entry-o.stop);
   if(extreme<=0.0 || risk<=0.0) { o.reason="STRUCTURE_INVALID"; return false; }
   double need=risk;
   if(s04) need=MathMax(risk,direction*(far_edge-o.entry));
   if(!EEA_S02V1StructuralTarget(points,point_count,direction,o.entry,need,o.target))
     { o.reason="NO_STRUCTURAL_TARGET"; return false; }
   o.rr=direction*(o.target-o.entry)/risk;
   if(o.rr<min_rr) { o.reason="RR_TOO_LOW"; return false; }
   o.valid=true;
   o.result="OPEN";
   int last=MathMin(count-1,trigger+horizon);
   for(int b=trigger+1;b<=last;b++)
     {
      double fav=direction*((direction==1 ? rates[b].high : rates[b].low)-o.entry)/risk;
      double adv=direction*(o.entry-(direction==1 ? rates[b].low : rates[b].high))/risk;
      o.mfe_r=MathMax(o.mfe_r,fav);
      o.mae_r=MathMax(o.mae_r,adv);
      if(o.bars_1r<0 && fav>=1.0 && adv<1.0) o.bars_1r=b-trigger;
      if(adv>=1.0) { o.result="SL"; o.result_r=-1.0; break; }
      if(fav>=o.rr) { o.result="TP"; o.result_r=o.rr; break; }
      if(b==last) o.result_r=direction*(rates[b].close-o.entry)/risk;
     }
   o.reason="EVALUATED";
   return true;
  }

void EEA_SetupReplayLoad(EEA_ReplayRuntime &rt,const string &canonical[],const string &broker[],const int count)
  {
   rt.loaded=true;
   string json;
   if(EEA_StrategyCandidateStoreReadText(EEA_SetupReplaySummaryPath(rt.root),json) &&
      EEA_StrategyCandidateStoreField(json,"version")==EEA_REPLAY_VERSION &&
      StringToInteger(EEA_StrategyCandidateStoreField(json,"from_utc"))==rt.from_utc &&
      EEA_StrategyCandidateStoreField(json,"complete")=="true")
     { rt.complete=true; rt.reason="REPLAY_COMPLETE"; return; }
   rt.count=0;
   for(int i=0;i<count;i++)
     {
      if(broker[i]=="") continue;
      for(int p=0;p<4 && rt.count<EEA_REPLAY_MAX_JOBS;p++)
        {
         EEA_ReplayJob j;
         j.canonical=canonical[i]; j.broker=broker[i];
         j.setup=(p<2 ? "S02" : "S04"); j.profile=(p%2==0 ? "SCALP" : "SWING");
         j.done=false; j.reason="PENDING";
         EEA_ReplayStatsReset(j.stats);
         rt.jobs[rt.count++]=j;
        }
     }
   // A fixed end (start of today, server time) keeps a rerun over the same data identical.
   rt.until_server=((long)TimeTradeServer()/86400)*86400;
   rt.next=0;
   FileDelete(rt.root+"/logs/setup_replay.jsonl",0);
   rt.reason=rt.count>0 ? "REPLAY_RUNNING" : "REPLAY_NO_SYMBOLS";
  }

void EEA_SetupReplayAddOutcome(EEA_ReplayStats &s,const EEA_ReplayOutcome &o)
  {
   s.candidates++;
   if(!o.valid)
     {
      if(o.reason=="RR_TOO_LOW") s.rr_low++; else s.no_target++;
      return;
     }
   s.taken++;
   if(o.result=="TP") s.tp_first++; else if(o.result=="SL") s.sl_first++; else s.open_end++;
   if(o.bars_1r>=0) { s.reached_1r++; s.sum_bars_1r+=o.bars_1r; }
   s.sum_mfe_r+=o.mfe_r; s.sum_mae_r+=o.mae_r; s.sum_result_r+=o.result_r;
  }

// One job: every closed entry bar from from_utc to until_server through a fresh engine.
bool EEA_SetupReplayRunJob(EEA_ReplayRuntime &rt,EEA_ReplayJob &job)
  {
   const bool swing=(job.profile=="SWING");
   const bool s04=(job.setup=="S04");
   const ENUM_TIMEFRAMES entry_tf=swing ? PERIOD_H1 : PERIOD_M5;
   const ENUM_TIMEFRAMES level_tf=swing ? PERIOD_H4 : PERIOD_H1;
   const long entry_seconds=PeriodSeconds(entry_tf), level_seconds=PeriodSeconds(level_tf);
   const int level_wanted=swing ? EEA_S02_SWING_LEVEL_BARS : EEA_S02_SCALP_LEVEL_BARS;
   const long now_offset=EEA_NewsServerOffsetSeconds();
   const long now_utc=(long)TimeGMT();
   const long from_server=rt.from_utc+EEA_NewsServerOffsetAt(rt.from_utc,now_offset,now_utc);
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int n=CopyRates(job.broker,entry_tf,(datetime)(from_server-EEA_STRATEGY_RUNTIME_ATR_PERIOD*2*entry_seconds),
                   (datetime)rt.until_server,rates);
   if(n<EEA_STRATEGY_RUNTIME_ATR_PERIOD+10) { job.reason="ENTRY_BARS_UNAVAILABLE"; return false; }
   MqlRates level_rates[];
   ArraySetAsSeries(level_rates,false);
   int ln=CopyRates(job.broker,level_tf,(datetime)(from_server-(level_wanted+10)*level_seconds),
                    (datetime)rt.until_server,level_rates);
   if(ln<EEA_S02_MIN_LEVEL_BARS) { job.reason="LEVEL_BARS_UNAVAILABLE"; return false; }
   EEA_LevelBar all[];
   ArrayResize(all,ln);
   for(int i=0;i<ln;i++)
     {
      all[i].time=(long)level_rates[i].time; all[i].open=level_rates[i].open; all[i].high=level_rates[i].high;
      all[i].low=level_rates[i].low; all[i].close=level_rates[i].close;
     }
   EEA_S02Config config;
   if(s04) EEA_S04V1Config(config,job.profile); else EEA_S02V1Config(config,job.profile);
   EEA_S02Engine engine;
   EEA_S02Init(engine,job.canonical,swing ? "H1" : "M5",config.config_version);
   const double point=SymbolInfoDouble(job.broker,SYMBOL_POINT);
   const int digits=(int)SymbolInfoInteger(job.broker,SYMBOL_DIGITS);
   const double min_rr=swing ? 2.0 : 1.5;
   const int horizon=swing ? EEA_REPLAY_SWING_HORIZON : EEA_REPLAY_SCALP_HORIZON;
   EEA_ConfluenceZone zones[];
   EEA_LevelPoint points[];
   EEA_LevelBar window[];
   int zone_count=0, point_count=0, built_for=-1;
   string structure="NEUTRAL";
   int level_index=-1;
   string lines="";
   for(int b=EEA_STRATEGY_RUNTIME_ATR_PERIOD;b<n;b++)
     {
      if((long)rates[b].time<from_server) continue;
      const long asof=(long)rates[b].time+entry_seconds;           // the entry bar has closed
      while(level_index+1<ln && all[level_index+1].time+level_seconds<=asof) level_index++;
      if(level_index+1<EEA_S02_MIN_LEVEL_BARS) continue;
      if(level_index!=built_for)
        {
         int start=MathMax(0,level_index+1-level_wanted);
         int wn=level_index+1-start;
         ArrayResize(window,wn);
         for(int k=0;k<wn;k++) window[k]=all[start+k];
         double context_atr=EEA_StrategyRuntimeAtrFromRates(level_rates,level_index,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
         long offset=EEA_NewsServerOffsetAt(asof-now_offset,now_offset,now_utc);
         EEA_StrategyRuntimeLevelsFromBars(window,wn,swing,asof,offset,points,point_count);
         zone_count=context_atr>0.0 ? EEA_BuildConfluenceZones(points,point_count,0.25*context_atr,0.5*context_atr,2,zones) : 0;
         structure=EEA_HtfStructure(window,wn,EEA_S02_SWING_WING);
         built_for=level_index;
        }
      double atr=EEA_StrategyRuntimeAtrFromRates(rates,b,EEA_STRATEGY_RUNTIME_ATR_PERIOD);
      if(atr<=0.0) continue;
      EEA_S02Bar bar;
      bar.closed_at_utc=rates[b].time; bar.open=rates[b].open; bar.high=rates[b].high;
      bar.low=rates[b].low; bar.close=rates[b].close; bar.atr=atr;
      EEA_S02Event event;
      const int before=engine.state;
      if(engine.state==EEA_S02_IDLE || EEA_S02IsTerminal(engine.state))
        {
         int pick=-1;
         for(int z=0;z<zone_count && pick<0;z++)
           {
            if(!zones[z].qualified) continue;
            if(bar.open<=zones[z].high && bar.close>zones[z].high) pick=z;
            else if(bar.open>=zones[z].low && bar.close<zones[z].low) pick=z;
           }
         if(pick<0) { engine.last_processed_bar_utc=bar.closed_at_utc; continue; }
         if(s04) EEA_S04ProcessClosedBarZone(engine,bar,zones[pick].low,zones[pick].high,config,event);
         else EEA_S02ProcessClosedBarZone(engine,bar,zones[pick].low,zones[pick].high,config,event);
        }
      else if(s04) EEA_S04ProcessClosedBarZone(engine,bar,engine.zone_low,engine.zone_high,config,event);
      else EEA_S02ProcessClosedBarZone(engine,bar,engine.zone_low,engine.zone_high,config,event);
      if(engine.state!=EEA_S02_TRIGGERED || before==EEA_S02_TRIGGERED) continue;
      EEA_ReplayOutcome o;
      const double far_edge=(engine.direction==1 ? engine.zone_high : engine.zone_low);
      EEA_SetupReplayEvaluate(rates,n,b,engine.direction,engine.candidate.retest_extreme,engine.signal_atr,
                              rates[b].spread*point,far_edge,s04,points,point_count,min_rr,horizon,o);
      EEA_SetupReplayAddOutcome(job.stats,o);
      const double htf=EEA_HtfRiskModifier(structure,engine.direction,EEA_S02_HTF_COUNTER_TREND_MODIFIER);
      lines+="{\"setup\":\""+job.setup+"\",\"profile\":\""+job.profile+"\",\"symbol\":\""+job.canonical+
         "\",\"bar_time\":"+IntegerToString((long)rates[b].time)+",\"direction\":"+IntegerToString(engine.direction)+
         ",\"zone_low\":"+DoubleToString(engine.zone_low,digits)+",\"zone_high\":"+DoubleToString(engine.zone_high,digits)+
         ",\"entry\":"+DoubleToString(o.entry,digits)+",\"sl\":"+DoubleToString(o.stop,digits)+
         ",\"tp\":"+DoubleToString(o.target,digits)+",\"rr\":"+DoubleToString(o.rr,2)+
         ",\"htf_modifier\":"+DoubleToString(htf,2)+",\"status\":\""+o.reason+"\",\"result\":\""+o.result+
         "\",\"result_r\":"+DoubleToString(o.result_r,2)+",\"mfe_r\":"+DoubleToString(o.mfe_r,2)+
         ",\"mae_r\":"+DoubleToString(o.mae_r,2)+",\"bars_1r\":"+IntegerToString(o.bars_1r)+"}\r\n";
     }
   if(lines!="") EEA_WriteAtomicAppendText(rt.root+"/logs/setup_replay.jsonl",lines);
   job.reason="DONE";
   return true;
  }

string EEA_SetupReplayStatsJson(const EEA_ReplayStats &s)
  {
   double taken=MathMax(1,s.taken);
   return "{\"candidates\":"+IntegerToString(s.candidates)+",\"taken\":"+IntegerToString(s.taken)+
      ",\"no_target\":"+IntegerToString(s.no_target)+",\"rr_low\":"+IntegerToString(s.rr_low)+
      ",\"tp_first\":"+IntegerToString(s.tp_first)+",\"sl_first\":"+IntegerToString(s.sl_first)+
      ",\"open_end\":"+IntegerToString(s.open_end)+",\"reached_1r\":"+IntegerToString(s.reached_1r)+
      ",\"avg_bars_1r\":"+DoubleToString(s.reached_1r>0 ? s.sum_bars_1r/s.reached_1r : 0.0,1)+
      ",\"avg_mfe_r\":"+DoubleToString(s.sum_mfe_r/taken,2)+",\"avg_mae_r\":"+DoubleToString(s.sum_mae_r/taken,2)+
      ",\"expectancy_r\":"+DoubleToString(s.sum_result_r/taken,3)+"}";
  }

void EEA_SetupReplayWriteSummary(const EEA_ReplayRuntime &rt)
  {
   string json="{\"version\":\""+EEA_REPLAY_VERSION+"\",\"from_utc\":"+IntegerToString(rt.from_utc)+
      ",\"until_server\":"+IntegerToString(rt.until_server)+",\"complete\":"+(rt.complete ? "true" : "false")+
      ",\"jobs_done\":"+IntegerToString(rt.next)+",\"jobs\":"+IntegerToString(rt.count)+",\"totals\":{";
   string keys[4]={"S02_SCALP","S02_SWING","S04_SCALP","S04_SWING"};
   for(int k=0;k<4;k++)
     {
      EEA_ReplayStats sum; EEA_ReplayStatsReset(sum);
      for(int i=0;i<rt.count;i++)
        {
         if(rt.jobs[i].setup+"_"+rt.jobs[i].profile!=keys[k]) continue;
         EEA_ReplayStats s=rt.jobs[i].stats;
         sum.candidates+=s.candidates; sum.no_target+=s.no_target; sum.rr_low+=s.rr_low; sum.taken+=s.taken;
         sum.tp_first+=s.tp_first; sum.sl_first+=s.sl_first; sum.open_end+=s.open_end; sum.reached_1r+=s.reached_1r;
         sum.sum_bars_1r+=s.sum_bars_1r; sum.sum_mfe_r+=s.sum_mfe_r; sum.sum_mae_r+=s.sum_mae_r; sum.sum_result_r+=s.sum_result_r;
        }
      json+=(k>0 ? "," : "")+"\""+keys[k]+"\":"+EEA_SetupReplayStatsJson(sum);
     }
   json+="},\"by_job\":[";
   for(int i=0;i<rt.count;i++)
      json+=(i>0 ? "," : "")+"{\"symbol\":\""+rt.jobs[i].canonical+"\",\"setup\":\""+rt.jobs[i].setup+
         "\",\"profile\":\""+rt.jobs[i].profile+"\",\"reason\":\""+rt.jobs[i].reason+"\",\"stats\":"+
         EEA_SetupReplayStatsJson(rt.jobs[i].stats)+"}";
   json+="]}";
   EEA_WriteAtomicText(EEA_SetupReplaySummaryPath(rt.root),json);
  }

// One job per timer pass so the terminal stays responsive.
void EEA_SetupReplayUpdate(EEA_ReplayRuntime &rt,const string &canonical[],const string &broker[],const int count)
  {
   if(!rt.enabled || rt.complete) return;
   if(!rt.loaded) { EEA_SetupReplayLoad(rt,canonical,broker,count); return; }
   if(rt.next>=rt.count) return;
   EEA_SetupReplayRunJob(rt,rt.jobs[rt.next]);
   rt.next++;
   rt.complete=(rt.next>=rt.count);
   rt.reason=rt.complete ? "REPLAY_COMPLETE" : "REPLAY_RUNNING";
   EEA_SetupReplayWriteSummary(rt);
  }

string EEA_SetupReplayStatus(const EEA_ReplayRuntime &rt)
  {
   if(!rt.enabled) return "replay off";
   if(rt.complete) return "replay done";
   return "replay "+IntegerToString(rt.next)+"/"+IntegerToString(rt.count);
  }

#endif
