#ifndef ENTERPRISE_EA_NEWS_CALENDAR_MQH
#define ENTERPRISE_EA_NEWS_CALENDAR_MQH

// News Guard runtime: reads HIGH impact events from the MT5 economic calendar (built
// into the terminal, no external feed, REQ-001), converts trade-server time to UTC and
// keeps one news state per selected symbol. A calendar that cannot be read, or whose
// last successful read is older than EEA_NEWS_STALE_SECONDS, makes every symbol UNKNOWN.
// The calendar does not exist in the Strategy Tester: the guard is then DISABLED.

#include "NewsState.mqh"
#include "../Core/Events.mqh"
#include "../Storage/AtomicWriter.mqh"
#include "../Storage/AuditLog.mqh"

#define EEA_NEWS_MAX_SYMBOLS 32
#define EEA_NEWS_REFRESH_SECONDS 900
#define EEA_NEWS_STALE_SECONDS 1800
#define EEA_NEWS_LOOKBACK_SECONDS (6*3600)
#define EEA_NEWS_LOOKAHEAD_SECONDS (7*86400)

struct EEA_NewsSymbol
  {
   string canonical;
   string broker;
   string currencies;
   string state;
   long   event_utc;
   string event_label;
   long   next_event_utc;
   string next_label;
   long   normalized_event_utc;
   long   normal_at_utc;          // last time the state returned to NORMAL (recorder timing)
   long   timeout_event_utc;      // event whose normalization timed out
   long   watch_event_utc;        // next indirect (yellow) event
   string watch_label;
   bool   indirect_swing_blocked; // yellow: SWING takes no new entry
   bool   indirect_scalp_reduced; // yellow: SCALP risk reduced
  };

// Recent News Guard effects (entry blocks, pending cancels) for the reaction recorder.
#define EEA_NEWS_MAX_EFFECTS 256
struct EEA_NewsEffect
  {
   long   t;
   string symbol;
   string kind;
  };

struct EEA_NewsRuntime
  {
   bool   initialized;
   bool   disabled;
   string config_version;
   EEA_NewsConfig cfg;
   EEA_NewsEvent events[EEA_NEWS_MAX_EVENTS];
   int    count;
   long   last_attempt_utc;
   long   last_success_utc;
   ulong  change_id;
   bool   calendar_ok;
   string reason;
   int    symbol_count;
   EEA_NewsSymbol symbols[EEA_NEWS_MAX_SYMBOLS];
   int    effect_count;
   int    effect_next;
   EEA_NewsEffect effects[EEA_NEWS_MAX_EFFECTS];
  };

void EEA_NewsNoteEffect(EEA_NewsRuntime &rt,const string symbol,const string kind)
  {
   rt.effects[rt.effect_next].t=(long)TimeGMT();
   rt.effects[rt.effect_next].symbol=symbol;
   rt.effects[rt.effect_next].kind=kind;
   rt.effect_next=(rt.effect_next+1)%EEA_NEWS_MAX_EFFECTS;
   rt.effect_count=MathMin(rt.effect_count+1,EEA_NEWS_MAX_EFFECTS);
  }

int EEA_NewsEffectCount(const EEA_NewsRuntime &rt,const string symbol,const string kind,const long from,const long to)
  {
   int n=0;
   for(int i=0;i<rt.effect_count;i++)
      if(rt.effects[i].symbol==symbol && rt.effects[i].kind==kind && rt.effects[i].t>=from && rt.effects[i].t<to) n++;
   return n;
  }

void EEA_NewsRuntimeInit(EEA_NewsRuntime &rt,const EEA_NewsConfig &cfg,const string config_version)
  {
   rt.initialized=true; rt.config_version=config_version; rt.cfg=cfg; rt.count=0; rt.last_attempt_utc=0; rt.last_success_utc=0;
   rt.change_id=0; rt.calendar_ok=false; rt.symbol_count=0; rt.effect_count=0; rt.effect_next=0;
   rt.disabled=!cfg.enabled || MQLInfoInteger(MQL_TESTER)!=0 || MQLInfoInteger(MQL_OPTIMIZATION)!=0;
   rt.reason=!cfg.enabled ? "NEWS_GUARD_DISABLED" :
             (rt.disabled ? "NEWS_GUARD_TESTER_DISABLED" : "NEWS_CALENDAR_PENDING");
   if(!EEA_NewsConfigValid(cfg)) { rt.disabled=false; rt.reason="NEWS_CONFIG_INVALID"; }
  }

long EEA_NewsServerOffsetSeconds()
  {
   return (long)MathRound(((double)TimeTradeServer()-(double)TimeGMT())/900.0)*900;
  }

string EEA_NewsValueText(const bool has,const double value)
  {
   return has ? DoubleToString(value,2) : "";
  }

// Reads [now-6h, now+7d] of HIGH impact events for the tracked currencies.
bool EEA_NewsRefreshCalendar(EEA_NewsRuntime &rt,const long now,string &reason)
  {
   rt.last_attempt_utc=now;
   const long offset=EEA_NewsServerOffsetSeconds();
   MqlCalendarValue values[];
   ResetLastError();
   if(!CalendarValueHistory(values,(datetime)(now-EEA_NEWS_LOOKBACK_SECONDS+offset),
                            (datetime)(now+EEA_NEWS_LOOKAHEAD_SECONDS+offset),NULL,NULL))
     { reason="NEWS_CALENDAR_READ_FAILED_"+IntegerToString(GetLastError()); return false; }
   int total=ArraySize(values);
   // A week without a single event of any importance means the calendar is not loaded.
   if(total<=0) { reason="NEWS_CALENDAR_EMPTY"; return false; }
   EEA_NewsEvent fresh[];
   ArrayResize(fresh,0,EEA_NEWS_MAX_EVENTS);
   int n=0;
   for(int i=0;i<total && n<EEA_NEWS_MAX_EVENTS;i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id,ev) || ev.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry country;
      if(!CalendarCountryById(ev.country_id,country) || !EEA_NewsCurrencyTracked(country.currency)) continue;
      if(EEA_NewsEventIgnored(ev.name,rt.cfg.ignore_keywords)) continue;
      ArrayResize(fresh,n+1);
      fresh[n].time_utc=(long)values[i].time-offset;
      fresh[n].currency=country.currency;
      fresh[n].name=ev.name;
      fresh[n].sector=(int)ev.sector;
      fresh[n].actual=EEA_NewsValueText(values[i].HasActualValue(),values[i].GetActualValue());
      fresh[n].forecast=EEA_NewsValueText(values[i].HasForecastValue(),values[i].GetForecastValue());
      fresh[n].previous=EEA_NewsValueText(values[i].HasPreviousValue(),values[i].GetPreviousValue());
      n++;
     }
   // Sort by time so the dashboard and the evaluation see events in order.
   for(int i=1;i<n;i++)
     {
      EEA_NewsEvent key=fresh[i];
      int j=i-1;
      while(j>=0 && fresh[j].time_utc>key.time_utc) { fresh[j+1]=fresh[j]; j--; }
      fresh[j+1]=key;
     }
   for(int i=0;i<n;i++) rt.events[i]=fresh[i];
   rt.count=n;
   rt.last_success_utc=now;
   MqlCalendarValue changes[];
   ulong change_id=0;
   CalendarValueLast(change_id,changes);   // current change id; later calls report updates
   rt.change_id=change_id;
   reason="NEWS_CALENDAR_REFRESHED";
   return true;
  }

bool EEA_NewsCalendarChanged(EEA_NewsRuntime &rt)
  {
   if(rt.change_id==0) return false;
   MqlCalendarValue changes[];
   ulong id=rt.change_id;
   int changed=CalendarValueLast(id,changes);
   return changed>0;
  }

int EEA_NewsSymbolIndex(const EEA_NewsRuntime &rt,const string canonical)
  {
   for(int i=0;i<rt.symbol_count;i++) if(rt.symbols[i].canonical==canonical) return i;
   return -1;
  }

// Market stable after an event: spread back near normal and the last closed M5 bar
// no longer extreme.
bool EEA_NewsMarketStable(const string broker_symbol)
  {
   MqlTick tick; ZeroMemory(tick);
   double point=SymbolInfoDouble(broker_symbol,SYMBOL_POINT);
   if(!SymbolInfoTick(broker_symbol,tick) || point<=0.0) return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(broker_symbol,PERIOD_M5,1,288,rates);
   if(copied<20) return false;
   double spreads[];
   ArrayResize(spreads,copied);
   for(int i=0;i<copied;i++) spreads[i]=(double)rates[i].spread;
   ArraySort(spreads);
   double median=spreads[copied/2];
   double spread=(tick.ask-tick.bid)/point;
   double tr=0.0;
   for(int i=copied-14;i<copied;i++)
      tr+=MathMax(rates[i].high,rates[i-1].close)-MathMin(rates[i].low,rates[i-1].close);
   double atr=tr/14.0;
   double last_range=rates[copied-1].high-rates[copied-1].low;
   return median>0.0 && spread<=1.5*median && atr>0.0 && last_range<=2.0*atr;
  }

bool EEA_NewsAudit(CAuditLog &audit,const string config_version,const string event_type,const string symbol,
                   const string before,const string after,const string details)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),symbol,"",before,after,"OK");
   event.config_version=config_version;
   event.details_json=details;
   return audit.Append(event,"EA_NEWS_GUARD");
  }

void EEA_NewsWriteState(const EEA_NewsRuntime &rt,const string root)
  {
   string json="{\"document_version\":\"news-state-v1.0.0\",\"reason\":\""+EEA_JsonEscape(rt.reason)+
      "\",\"last_success_utc\":"+IntegerToString(rt.last_success_utc)+",\"symbols\":[";
   for(int i=0;i<rt.symbol_count;i++)
      json+=(i>0 ? "," : "")+"{\"symbol\":\""+EEA_JsonEscape(rt.symbols[i].canonical)+"\",\"state\":\""+
            EEA_JsonEscape(rt.symbols[i].state)+"\",\"event\":\""+EEA_JsonEscape(rt.symbols[i].event_label)+
            "\",\"event_utc\":"+IntegerToString(rt.symbols[i].event_utc)+",\"next\":\""+
            EEA_JsonEscape(rt.symbols[i].next_label)+"\",\"next_utc\":"+IntegerToString(rt.symbols[i].next_event_utc)+"}";
   json+="],\"events\":[";
   int written=0;
   for(int i=0;i<rt.count && written<40;i++)
     {
      json+=(written>0 ? "," : "")+"{\"time_utc\":"+IntegerToString(rt.events[i].time_utc)+",\"currency\":\""+
            rt.events[i].currency+"\",\"name\":\""+EEA_JsonEscape(rt.events[i].name)+"\",\"actual\":\""+
            rt.events[i].actual+"\",\"forecast\":\""+rt.events[i].forecast+"\",\"previous\":\""+rt.events[i].previous+"\"}";
      written++;
     }
   json+="]}";
   EEA_WriteAtomicText(root+"/current/news_state.json",json);
  }

// One timer pass: refresh the calendar when due, then the state of every selected symbol.
void EEA_NewsUpdate(EEA_NewsRuntime &rt,CAuditLog &audit,const string root,
                    const string &canonicals[],const string &brokers[],const int symbol_count)
  {
   if(!rt.initialized) return;
   const long now=(long)TimeGMT();
   bool changed=false;
   if(!rt.disabled && rt.reason!="NEWS_CONFIG_INVALID")
     {
      if(rt.last_attempt_utc==0 || now-rt.last_attempt_utc>=EEA_NEWS_REFRESH_SECONDS || EEA_NewsCalendarChanged(rt))
        {
         string reason;
         bool ok=EEA_NewsRefreshCalendar(rt,now,reason);
         // Readers outside the EA (AI bridge, news health) judge freshness from
         // last_success_utc, so every successful refresh is written, not only state changes.
         if(ok) changed=true;
         if(ok!=rt.calendar_ok || rt.reason!=reason)
           {
            EEA_NewsAudit(audit,rt.config_version,ok ? "NEWS_CALENDAR_REFRESHED" : "NEWS_CALENDAR_UNAVAILABLE","","","",
                          "{\"reason\":\""+EEA_JsonEscape(reason)+"\",\"events\":"+IntegerToString(rt.count)+"}");
            changed=true;
           }
         rt.calendar_ok=ok; rt.reason=reason;
        }
     }
   const bool unknown=!rt.disabled && (rt.reason=="NEWS_CONFIG_INVALID" || rt.last_success_utc==0 ||
                                        now-rt.last_success_utc>EEA_NEWS_STALE_SECONDS);
   int n=MathMin(symbol_count,EEA_NEWS_MAX_SYMBOLS);
   EEA_NewsSymbol next[EEA_NEWS_MAX_SYMBOLS];
   for(int i=0;i<n;i++)
     {
      int prev=EEA_NewsSymbolIndex(rt,canonicals[i]);
      EEA_NewsSymbol s;
      s.canonical=canonicals[i]; s.broker=brokers[i];
      s.normalized_event_utc=prev>=0 ? rt.symbols[prev].normalized_event_utc : 0;
      s.normal_at_utc=prev>=0 ? rt.symbols[prev].normal_at_utc : 0;
      s.timeout_event_utc=prev>=0 ? rt.symbols[prev].timeout_event_utc : 0;
      s.watch_event_utc=0; s.watch_label="";
      s.indirect_swing_blocked=false; s.indirect_scalp_reduced=false;
      string before=prev>=0 ? rt.symbols[prev].state : "";
      s.currencies=brokers[i]=="" ? "" :
         EEA_NewsSymbolCurrencies(SymbolInfoString(brokers[i],SYMBOL_CURRENCY_BASE),
                                  SymbolInfoString(brokers[i],SYMBOL_CURRENCY_PROFIT));
      s.event_utc=0; s.event_label=""; s.next_event_utc=0; s.next_label="";
      if(rt.disabled) s.state="DISABLED";
      else if(unknown) s.state="UNKNOWN";
      else
        {
         EEA_NewsPhase phase;
         EEA_NewsEvaluate(rt.events,rt.count,s.currencies,now,rt.cfg,s.normalized_event_utc,phase);
         if(phase.state=="NORMALIZING" && s.broker!="" && EEA_NewsMarketStable(s.broker))
           {
            s.normalized_event_utc=phase.event_utc;
            EEA_NewsEvaluate(rt.events,rt.count,s.currencies,now,rt.cfg,s.normalized_event_utc,phase);
           }
         s.state=phase.state; s.event_utc=phase.event_utc; s.event_label=phase.event_label;
         s.next_event_utc=phase.next_event_utc; s.next_label=phase.next_label;
         string indirect_label;
         EEA_NewsIndirectWindow(rt.events,rt.count,s.currencies,now,rt.cfg,s.indirect_swing_blocked,
                                s.indirect_scalp_reduced,indirect_label);
         // Next indirect (yellow) event within the SWING window.
         for(int e=0;e<rt.count;e++)
            if(rt.events[e].time_utc>=now-rt.cfg.post_min*60 &&
               rt.events[e].time_utc<=now+rt.cfg.swing_block_before_min*60 &&
               EEA_NewsIndirectAffects(s.currencies,rt.events[e].currency,rt.events[e].sector))
              { s.watch_event_utc=rt.events[e].time_utc; s.watch_label=rt.events[e].currency+" "+rt.events[e].name; break; }
         if(before=="NORMALIZING" && s.state=="NORMAL" && prev>=0 &&
            s.normalized_event_utc<rt.symbols[prev].event_utc)
           {
            s.timeout_event_utc=rt.symbols[prev].event_utc;
            EEA_NewsAudit(audit,rt.config_version,"NEWS_NORMALIZE_TIMEOUT",s.canonical,"NORMALIZING","NORMAL",
                          "{\"event\":\""+EEA_JsonEscape(rt.symbols[prev].event_label)+"\"}");
           }
        }
      if(before!="" && before!="NORMAL" && s.state=="NORMAL") s.normal_at_utc=now;
      if(before!=s.state)
        {
         EEA_NewsAudit(audit,rt.config_version,"NEWS_STATE_CHANGED",s.canonical,before,s.state,
                       "{\"from\":\""+before+"\",\"to\":\""+s.state+"\",\"event\":\""+EEA_JsonEscape(s.event_label)+
                       "\",\"event_utc\":"+IntegerToString(s.event_utc)+"}");
         changed=true;
        }
      next[i]=s;
     }
   for(int i=0;i<n;i++) rt.symbols[i]=next[i];
   rt.symbol_count=n;
   if(changed) EEA_NewsWriteState(rt,root);
  }

string EEA_NewsStateFor(const EEA_NewsRuntime &rt,const string canonical)
  {
   if(!rt.initialized) return "UNKNOWN";
   int i=EEA_NewsSymbolIndex(rt,canonical);
   if(i<0) return rt.disabled ? "DISABLED" : "UNKNOWN";
   return rt.symbols[i].state;
  }

// Red only: used for working pending orders (yellow never cancels them).
string EEA_NewsDirectBlockFor(const EEA_NewsRuntime &rt,const string canonical,const string profile)
  {
   if(!rt.initialized) return "NEWS_GUARD_NOT_READY";
   return EEA_NewsEntryBlock(EEA_NewsStateFor(rt,canonical),profile,rt.cfg);
  }

// New entries: red first, then yellow (SWING blocked around an indirect event).
string EEA_NewsEntryBlockFor(const EEA_NewsRuntime &rt,const string canonical,const string profile)
  {
   string red=EEA_NewsDirectBlockFor(rt,canonical,profile);
   if(red!="") return red;
   int i=EEA_NewsSymbolIndex(rt,canonical);
   if(i<0 || rt.disabled || !rt.cfg.enabled) return "";
   if(profile=="SWING" && rt.symbols[i].indirect_swing_blocked) return "NEWS_INDIRECT_SWING";
   return "";
  }

// Yellow: SCALP risk multiplier around an indirect event (1.0 otherwise).
double EEA_NewsRiskFactorFor(const EEA_NewsRuntime &rt,const string canonical,const string profile)
  {
   int i=EEA_NewsSymbolIndex(rt,canonical);
   if(i<0 || rt.disabled || !rt.cfg.enabled || profile=="SWING") return 1.0;
   return rt.symbols[i].indirect_scalp_reduced ? rt.cfg.indirect_scalp_factor : 1.0;
  }

long EEA_NewsBlockStartFor(const EEA_NewsRuntime &rt,const string canonical,const string profile)
  {
   int i=EEA_NewsSymbolIndex(rt,canonical);
   if(i<0 || rt.disabled) return 0;
   return EEA_NewsBlockStart(rt.symbols[i].next_event_utc,profile,rt.cfg);
  }

bool EEA_NewsBreakEvenDueFor(const EEA_NewsRuntime &rt,const string canonical)
  {
   int i=EEA_NewsSymbolIndex(rt,canonical);
   if(i<0 || rt.disabled || !rt.initialized) return false;
   return EEA_NewsBreakEvenDue(rt.events,rt.count,rt.symbols[i].currencies,(long)TimeGMT(),rt.cfg);
  }

#endif
