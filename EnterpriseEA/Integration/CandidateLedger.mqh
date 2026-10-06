#ifndef ENTERPRISE_EA_CANDIDATE_LEDGER_MQH
#define ENTERPRISE_EA_CANDIDATE_LEDGER_MQH

#include "ControlledLiveRuntime.mqh"

// G18 candidate ledger (design 2026-10-05-setup-arbitration-and-candidate-ledger, A5):
// every TRIGGERED candidate, and every S02 LIMIT that was placed, gets one line in
// logs/candidates.jsonl once its outcome is final: EXECUTED, or NOT_EXECUTED with the last
// reason the live path gave for that candidate. research/g10/candidates_eval.py turns the
// lines into virtual results. Open candidates live in memory only (a restart drops them).

#define EEA_LEDGER_MAX_OPEN 128
#define EEA_LEDGER_WRITTEN_RING 256

struct EEA_LedgerEntry
  {
   string candidate_id;
   string setup;
   string profile;
   string symbol;
   string timeframe;
   string mode;
   int    direction;
   long   bar_time;
   long   detected_at;
   double extreme;
   double zone_low;
   double zone_high;
   double signal_atr;
   double key_level;
   long   first_seen_utc;
   string reason;
   bool   seen;
   bool   executed;
   string entry_kind;
   string usd_json;     // G29: USD flow when the candidate was first seen
  };

struct EEA_CandidateLedger
  {
   int count;
   EEA_LedgerEntry items[EEA_LEDGER_MAX_OPEN];
   string written[EEA_LEDGER_WRITTEN_RING];
   int written_next;
   long lines_written;
  };

void EEA_CandidateLedgerInit(EEA_CandidateLedger &l)
  {
   l.count=0; l.written_next=0; l.lines_written=0;
   for(int i=0;i<EEA_LEDGER_WRITTEN_RING;i++) l.written[i]="";
  }

string EEA_CandidateLedgerPath(const string root) { return root+"/logs/candidates.jsonl"; }

bool EEA_CandidateLedgerWritten(const EEA_CandidateLedger &l,const string id)
  {
   for(int i=0;i<EEA_LEDGER_WRITTEN_RING;i++) if(l.written[i]==id) return true;
   return false;
  }

int EEA_CandidateLedgerFind(const EEA_CandidateLedger &l,const string id)
  {
   for(int i=0;i<l.count;i++) if(l.items[i].candidate_id==id) return i;
   return -1;
  }

// The reason a live candidate did not enter (yet), from its own evaluation in this slot.
string EEA_CandidateLedgerReason(const EEA_ControlledLiveRuntimeState &live,const int engine,const string id,
                                 const int mode,const bool live_armed)
  {
   if(mode==EEA_S04_MODE_SHADOW) return "SHADOW_MODE";
   if(!live_armed) return "LIVE_NOT_ARMED";
   if(live.reason_candidate[engine]==id && live.candidate_reason[engine]!="") return live.candidate_reason[engine];
   return "NOT_EVALUATED:"+live.last_reason;
  }

string EEA_CandidateLedgerLine(const EEA_LedgerEntry &e,const long closed_utc)
  {
   return "{\"candidate_id\":\""+EEA_JsonEscape(e.candidate_id)+"\",\"setup\":\""+e.setup+
      "\",\"profile\":\""+e.profile+"\",\"symbol\":\""+e.symbol+"\",\"timeframe\":\""+e.timeframe+
      "\",\"direction\":"+IntegerToString(e.direction)+",\"bar_time\":"+IntegerToString(e.bar_time)+
      ",\"detected_at\":"+IntegerToString(e.detected_at)+
      ",\"extreme\":"+DoubleToString(e.extreme,8)+",\"zone_low\":"+DoubleToString(e.zone_low,8)+
      ",\"zone_high\":"+DoubleToString(e.zone_high,8)+",\"signal_atr\":"+DoubleToString(e.signal_atr,8)+
      ",\"key_level\":"+DoubleToString(e.key_level,8)+",\"mode\":\""+e.mode+
      "\",\"disposition\":\""+(e.executed ? "EXECUTED" : "NOT_EXECUTED")+
      "\",\"reason\":\""+EEA_JsonEscape(e.executed ? "EXECUTED" : e.reason)+
      "\",\"entry_kind\":\""+e.entry_kind+"\","+e.usd_json+",\"first_seen_utc\":"+IntegerToString(e.first_seen_utc)+
      ",\"closed_utc\":"+IntegerToString(closed_utc)+"}";
  }

void EEA_CandidateLedgerAdd(EEA_CandidateLedger &l,const EEA_StrategyCandidateRuntime &strategy,const int i,
                            const int mode,const long now)
  {
   if(l.count>=EEA_LEDGER_MAX_OPEN) return;
   const EEA_S02Engine e=strategy.engines[i];
   EEA_LedgerEntry x;
   x.candidate_id=e.candidate.candidate_id; x.setup=strategy.setup[i]; x.profile=strategy.profile[i];
   x.symbol=e.canonical_symbol; x.timeframe=e.timeframe; x.mode=EEA_SetupModeName(mode);
   x.direction=e.direction; x.bar_time=(long)e.candidate.triggered_at_utc; x.detected_at=(long)e.candidate.detected_at_utc;
   x.extreme=e.candidate.retest_extreme>0.0 ? e.candidate.retest_extreme : e.retest_extreme;
   x.zone_low=e.zone_low; x.zone_high=e.zone_high; x.signal_atr=e.signal_atr; x.key_level=e.key_level;
   x.first_seen_utc=now; x.reason=""; x.seen=false; x.executed=false; x.entry_kind="";
   x.usd_json=EEA_UsdFlowJson(g_usd_flow,e.canonical_symbol,e.direction);
   l.items[l.count++]=x;
  }

// One pass after the live entry pass. Returns false only when a line could not be written.
bool EEA_CandidateLedgerUpdate(EEA_CandidateLedger &l,const string root,const EEA_StrategyCandidateRuntime &strategy,
                               const EEA_ControlledLiveRuntimeState &live,const bool live_armed,
                               const EEA_TradeManagerRuntime &trades,const EEA_PendingRuntime &pending)
  {
   if(!strategy.enabled || !strategy.zone_mode) return true;
   const long now=(long)TimeGMT();
   for(int k=0;k<l.count;k++) l.items[k].seen=false;
   for(int i=0;i<strategy.symbol_count;i++)
     {
      const int mode=EEA_StrategyRuntimeEngineMode(strategy,i);
      if(mode==EEA_S04_MODE_OFF) continue;
      const string id=strategy.engines[i].candidate.candidate_id;
      if(id=="" || EEA_CandidateLedgerWritten(l,id)) continue;
      const bool in_trade=EEA_TradeManagerHasCandidate(trades,id);
      const bool in_pending=EEA_PendingRuntimeHasCandidate(pending,id);
      const bool triggered=(strategy.has_candidate[i] && strategy.engines[i].state==EEA_S02_TRIGGERED);
      if(!triggered && !in_trade && !in_pending) continue;
      int x=EEA_CandidateLedgerFind(l,id);
      if(x<0) { EEA_CandidateLedgerAdd(l,strategy,i,mode,now); x=EEA_CandidateLedgerFind(l,id); }
      if(x<0) continue;
      l.items[x].seen=true;
      if(in_trade || in_pending || (live.reason_candidate[i]==id && live.candidate_reason[i]=="EXECUTED"))
        {
         l.items[x].executed=true;
         l.items[x].entry_kind=in_pending ? "PENDING" : "MARKET";
        }
      else
         l.items[x].reason=EEA_CandidateLedgerReason(live,i,id,mode,live_armed);
     }
   bool ok=true;
   for(int k=l.count-1;k>=0;k--)
     {
      if(l.items[k].seen && !l.items[k].executed) continue;
      // Left TRIGGERED without an entry, or entered: the outcome is final.
      if(!l.items[k].executed && (EEA_TradeManagerHasCandidate(trades,l.items[k].candidate_id) ||
                                  EEA_PendingRuntimeHasCandidate(pending,l.items[k].candidate_id)))
         l.items[k].executed=true;
      if(l.items[k].reason=="" && !l.items[k].executed) l.items[k].reason="NOT_EVALUATED";
      if(!EEA_WriteAtomicAppendText(EEA_CandidateLedgerPath(root),EEA_CandidateLedgerLine(l.items[k],now)+"\r\n"))
        { ok=false; continue; }
      l.lines_written++;
      l.written[l.written_next]=l.items[k].candidate_id;
      l.written_next=(l.written_next+1)%EEA_LEDGER_WRITTEN_RING;
      l.items[k]=l.items[l.count-1];
      l.count--;
     }
   return ok;
  }

#endif
