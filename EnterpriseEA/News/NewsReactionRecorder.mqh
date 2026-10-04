#ifndef ENTERPRISE_EA_NEWS_REACTION_RECORDER_MQH
#define ENTERPRISE_EA_NEWS_REACTION_RECORDER_MQH

// News Reaction Recorder adapter (design 2026-10-04, R1-R6). Measurement only: it reads
// the MT5 calendar, M1 bars and ticks after the measurement window has passed
// (T + 4h05m) and appends one record per HIGH event x affected selected symbol to
// logs/news_reactions.jsonl, keyed by calendar value id + symbol (idempotent). Records of
// the last 48 hours are LIVE (with EA trade impact); 12 weeks before that are BACKFILL.
// It calls no order function and changes no parameter (R3: suggestions are display only).

#include "NewsReaction.mqh"
#include "NewsCalendar.mqh"
#include "../Runtime/TradeManagerRuntime.mqh"

#define EEA_NR_LIVE_LOOKBACK_SECONDS (48*3600)
#define EEA_NR_SETTLE_SECONDS (4*3600+300)
#define EEA_NR_BACKFILL_SECONDS (84*86400)          // R2: 12 weeks
#define EEA_NR_MAX_PER_TIMER 12
#define EEA_NR_MAX_MS_PER_TIMER 2500     // stop the batch after this much work in one timer
#define EEA_NR_LIVE_SCAN_SECONDS 300
#define EEA_NR_MAX_NOT_READY 5
#define EEA_NR_RECENT 3

struct EEA_NewsReactionRuntime
  {
   bool   loaded;
   int    key_count;
   string keys[];
   int    summary_count;
   EEA_ReactionSummary summaries[];
   long   backfill_cursor_utc;
   long   backfill_from_utc;               // P1: replay starts here (default 2026-01-01)
   bool   backfill_done;
   int    not_ready_attempts;
   long   last_live_scan_utc;
   string reason;
   int    recent_count;
   string recent[EEA_NR_RECENT];
  };

string EEA_NrField(const string json,const string name)
  {
   string key="\""+name+"\":";
   int at=StringFind(json,key);
   if(at<0) return "";
   int start=at+StringLen(key);
   if(start<StringLen(json) && StringGetCharacter(json,start)==34)
     {
      start++;
      int end=StringFind(json,"\"",start);
      return end<0 ? "" : StringSubstr(json,start,end-start);
     }
   int end=StringFind(json,",",start);
   if(end<0) end=StringFind(json,"}",start);
   return end<0 ? "" : StringSubstr(json,start,end-start);
  }

string EEA_NrGroup(const string currency,const string event_name,const string symbol)
  { return EEA_NewsReactionGroup(currency+" "+event_name,symbol); }

bool EEA_NrKnown(const EEA_NewsReactionRuntime &rt,const string key)
  {
   for(int i=rt.key_count-1;i>=0;i--) if(rt.keys[i]==key) return true;
   return false;
  }

void EEA_NrRemember(EEA_NewsReactionRuntime &rt,const string key,const EEA_ReactionSummary &summary,const string recent,
                    const bool add_summary=true)
  {
   ArrayResize(rt.keys,rt.key_count+1,256); rt.keys[rt.key_count]=key; rt.key_count++;
   if(add_summary)
     { ArrayResize(rt.summaries,rt.summary_count+1,256); rt.summaries[rt.summary_count]=summary; rt.summary_count++; }
   if(recent!="")
     {
      for(int i=EEA_NR_RECENT-1;i>0;i--) rt.recent[i]=rt.recent[i-1];
      rt.recent[0]=recent;
      rt.recent_count=MathMin(rt.recent_count+1,EEA_NR_RECENT);
     }
  }

string EEA_NrBackfillPath(const string root) { return root+"/current/news_reaction_backfill.json"; }
string EEA_NrLogPath(const string root) { return root+"/logs/news_reactions.jsonl"; }

string EEA_NrRecentText(const EEA_Reaction &r)
  {
   if(r.quality!="OK" || !r.cluster_lead) return "";
   double atr=r.atr_ref;
   return r.symbol+(r.impact=="INDIRECT" ? " (ind)" : "")+"  "+r.currency+" "+r.event_name+
          (r.cluster_size>1 ? " +"+IntegerToString(r.cluster_size-1) : "")+"  "+(r.surprise_side=="" ? "-" : r.surprise_side)+
          "  5m "+DoubleToString(r.move[1]/atr,1)+"A  60m "+DoubleToString(r.move[3]/atr,1)+"A"+
          (r.spread_peak_ratio>0.0 ? "  sp x"+DoubleToString(r.spread_peak_ratio,1) : "");
  }

// Restores keys, summaries and the backfill cursor so nothing is measured twice.
void EEA_NewsReactionLoad(EEA_NewsReactionRuntime &rt,const string root,const long backfill_from_utc)
  {
   rt.loaded=true; rt.key_count=0; rt.summary_count=0; rt.recent_count=0; rt.not_ready_attempts=0;
   rt.last_live_scan_utc=0; rt.reason="NEWS_REACTION_LOADED";
   ArrayResize(rt.keys,0); ArrayResize(rt.summaries,0);
   for(int i=0;i<EEA_NR_RECENT;i++) rt.recent[i]="";
   string path=EEA_NrLogPath(root);
   if(FileIsExist(path,0))
     {
      int h=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(h!=INVALID_HANDLE)
        {
         while(!FileIsEnding(h))
           {
            string line=FileReadString(h);
            string key=EEA_NrField(line,"key");
            // Lines written before clusters existed are re-measured with their cluster; the old
            // lines stay in the log but no longer count.
            if(key=="" || StringFind(line,"\"cluster_events\":")<0 || StringFind(line,"\"guard_block_end_min\":")<0) continue;
            EEA_ReactionSummary s;
            string group=EEA_NrField(line,"group");
            s.group=group!="" ? group : EEA_NrGroup(EEA_NrField(line,"currency"),EEA_NrField(line,"event"),EEA_NrField(line,"symbol"));
            s.ok=EEA_NrField(line,"quality")=="OK";
            s.move15_atr=StringToDouble(EEA_NrField(line,"move_15m_atr"));
            s.move60_atr=StringToDouble(EEA_NrField(line,"move_60m_atr"));
            s.spread_ratio=StringToDouble(EEA_NrField(line,"spread_peak_ratio"));
            s.recovery_min=StringToDouble(EEA_NrField(line,"recovery_min"));
            s.reversal=EEA_NrField(line,"reversal_60m")=="true";
            s.replay_ok=EEA_NrField(line,"replay_ok")=="true";
            s.covered=EEA_NrField(line,"guard_covered")=="true";
            s.residual_atr=StringToDouble(EEA_NrField(line,"residual_after_block_atr"));
            // Only the lead record of a cluster feeds the statistics (records before clusters count alone).
            EEA_NrRemember(rt,key,s,"",EEA_NrField(line,"cluster_lead")!="false");
           }
         FileClose(h);
        }
      else rt.reason="NEWS_REACTION_LOG_UNREADABLE";
     }
   string json;
   rt.backfill_from_utc=backfill_from_utc>0 ? backfill_from_utc :
                        (long)TimeGMT()-EEA_NR_BACKFILL_SECONDS-EEA_NR_LIVE_LOOKBACK_SECONDS;
   rt.backfill_cursor_utc=rt.backfill_from_utc;
   rt.backfill_done=false;
   // A backfill that started from another date (or before the replay fields) restarts.
   if(EEA_PendingReadText(EEA_NrBackfillPath(root),json) &&
      StringToInteger(EEA_NrField(json,"from_utc"))==rt.backfill_from_utc)
     {
      long cursor=StringToInteger(EEA_NrField(json,"cursor_utc"));
      if(cursor>0) rt.backfill_cursor_utc=cursor;
      rt.backfill_done=EEA_NrField(json,"done")=="true";
     }
  }

void EEA_NrWriteBackfill(const EEA_NewsReactionRuntime &rt,const string root)
  {
   EEA_WriteAtomicText(EEA_NrBackfillPath(root),"{\"document_version\":\"news-reaction-backfill-v1.1.0\",\"from_utc\":"+
                       IntegerToString(rt.backfill_from_utc)+",\"cursor_utc\":"+
                       IntegerToString(rt.backfill_cursor_utc)+",\"done\":"+(rt.backfill_done ? "true" : "false")+"}");
  }

string EEA_NrNum(const string name,const bool ok,const double value,const int digits)
  { return ",\""+name+"\":"+(ok ? DoubleToString(value,digits) : "null"); }

string EEA_NrJson(const EEA_Reaction &r)
  {
   const double atr=r.atr_ref>0.0 ? r.atr_ref : 1.0;
   string json="{\"document_version\":\"news-reaction-v1.0.0\",\"key\":\""+EEA_JsonEscape(r.key)+
      "\",\"source\":\""+r.source+"\",\"symbol\":\""+r.symbol+"\",\"currency\":\""+r.currency+
      "\",\"event\":\""+EEA_JsonEscape(r.event_name)+"\",\"impact\":\""+r.impact+
      "\",\"group\":\""+EEA_JsonEscape(EEA_NewsReactionGroup(r.cluster_label,r.symbol))+
      "\",\"cluster_events\":\""+EEA_JsonEscape(r.cluster_label)+"\",\"cluster_size\":"+IntegerToString(r.cluster_size)+
      ",\"cluster_lead\":"+(r.cluster_lead ? "true" : "false")+
      ",\"event_utc\":"+IntegerToString(r.event_utc)+
      EEA_NrNum("actual",r.has_actual,r.actual,4)+EEA_NrNum("forecast",r.has_forecast,r.forecast,4)+
      EEA_NrNum("previous",r.has_previous,r.previous,4)+
      EEA_NrNum("surprise_raw",r.has_actual && r.has_forecast,r.surprise_raw,4)+
      ",\"surprise_side\":\""+r.surprise_side+"\""+EEA_NrNum("surprise_std",r.has_surprise_std,r.surprise_std,3)+
      ",\"surprise_quality\":\""+r.surprise_quality+"\""+
      EEA_NrNum("atr_ref",r.atr_ref>0.0,r.atr_ref,8)+EEA_NrNum("p0",r.p0>0.0,r.p0,8);
   string names[EEA_NR_HORIZONS]={"move_1m","move_5m","move_15m","move_60m","move_240m"};
   for(int h=0;h<EEA_NR_HORIZONS;h++)
     {
      json+=EEA_NrNum(names[h],r.move_ok[h],r.move[h],8);
      json+=EEA_NrNum(names[h]+"_atr",r.move_ok[h],r.move[h]/atr,3);
      json+=EEA_NrNum(names[h]+"_points",r.move_ok[h] && r.point>0.0,r.point>0.0 ? r.move[h]/r.point : 0.0,1);
     }
   json+=EEA_NrNum("max_up_60m_atr",r.p0>0.0,r.max_up_60/atr,3)+EEA_NrNum("max_down_60m_atr",r.p0>0.0,r.max_down_60/atr,3)+
      ",\"bars_to_extreme_60m\":"+IntegerToString(r.bars_to_extreme_60)+
      ",\"first_direction\":\""+r.first_direction+"\",\"reversal_60m\":"+(r.reversal_60 ? "true" : "false")+
      EEA_NrNum("follow_through",r.has_follow_through,r.follow_through,3)+
      ",\"vol_recovery_min\":"+IntegerToString(r.vol_recovery_min)+
      EEA_NrNum("tick_volume_ratio_15m",r.has_volume_ratio,r.tick_volume_ratio_15m,2)+
      ",\"spread_source\":\""+r.spread_source+"\""+EEA_NrNum("spread_pre",r.spread_pre>0.0,r.spread_pre,8)+
      EEA_NrNum("spread_peak",r.spread_peak>0.0,r.spread_peak,8)+
      EEA_NrNum("spread_peak_ratio",r.spread_peak_ratio>0.0,r.spread_peak_ratio,2)+
      ",\"spread_recovery_min\":"+IntegerToString(r.spread_recovery_min)+
      ",\"recovery_min\":"+DoubleToString(EEA_NewsReactionRecoveryMin(r),0)+
      ",\"guard_normal_min\":"+IntegerToString(r.guard_normal_min)+",\"guard_timeout\":"+(r.guard_timeout ? "true" : "false")+
      ",\"positions_open\":"+IntegerToString(r.positions_open)+",\"positions_detail\":\""+EEA_JsonEscape(r.positions_detail)+
      "\",\"exits_in_window\":"+IntegerToString(r.exits_in_window)+",\"be_before_news\":"+IntegerToString(r.be_before_news)+
      ",\"be_would_have_hit_sl\":"+IntegerToString(r.be_would_have_hit_sl)+
      ",\"entries_blocked\":"+IntegerToString(r.entries_blocked)+",\"pending_cancelled\":"+IntegerToString(r.pending_cancelled)+
      ",\"replay_ok\":"+(r.replay_ok ? "true" : "false")+",\"guard_block_end_min\":"+IntegerToString(r.guard_block_end_min)+
      ",\"guard_covered\":"+(r.guard_covered ? "true" : "false")+
      EEA_NrNum("residual_after_block_atr",r.replay_ok,r.residual_after_block_atr,3)+
      EEA_NrNum("pre_drift_scalp_atr",r.has_pre_drift,r.pre_drift_scalp_atr,3)+
      EEA_NrNum("pre_drift_swing_atr",r.has_pre_drift,r.pre_drift_swing_atr,3)+
      ",\"server_offset\":"+IntegerToString(r.server_offset)+
      ",\"quality\":\""+r.quality+"\",\"recorded_at_utc\":"+IntegerToString((long)TimeGMT())+"}";
   return json;
  }

// Surprise history of the same event: actual - forecast of earlier releases (latest 24).
int EEA_NrSurpriseHistory(const ulong event_id,const datetime before_server,double &diffs[])
  {
   ArrayResize(diffs,0);
   MqlCalendarValue hist[];
   if(!CalendarValueHistoryByEvent(event_id,hist,(datetime)((long)before_server-6*365*86400),(datetime)((long)before_server-1)))
      return 0;
   int total=ArraySize(hist), n=0;
   for(int i=total-1;i>=0 && n<24;i--)
     {
      if(!hist[i].HasActualValue() || !hist[i].HasForecastValue()) continue;
      ArrayResize(diffs,n+1);
      diffs[n]=hist[i].GetActualValue()-hist[i].GetForecastValue();
      n++;
     }
   return n;
  }

// Pre-event ATR14 of M5 bars that closed by T-5m.
double EEA_NrAtrRef(const string broker,const long T,const long offset,int &copied)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   copied=CopyRates(broker,PERIOD_M5,(datetime)(T+offset-300-20*300),(datetime)(T+offset-600),rates);
   if(copied<15) return 0.0;
   double tr=0.0;
   for(int i=copied-14;i<copied;i++)
      tr+=MathMax(rates[i].high,rates[i-1].close)-MathMin(rates[i].low,rates[i-1].close);
   return tr/14.0;
  }

// Returns 1 recorded, 0 skipped, -1 history not ready yet (retry later).
int EEA_NrRecord(EEA_NewsReactionRuntime &rt,const string root,CAuditLog &audit,const MqlCalendarValue &value,
                 const MqlCalendarEvent &ev,const string currency,const string canonical,const string broker,
                 const string source,const string impact,const string cluster_label,const int cluster_size,
                 const bool cluster_lead,const EEA_NewsRuntime &news,const EEA_TradeManagerRuntime &trades)
  {
   const string key=IntegerToString((long)value.id)+"|"+canonical;
   if(EEA_NrKnown(rt,key)) return 0;
   const long now_offset=EEA_NewsServerOffsetSeconds();
   // Offset valid at the event (broker on New York close: one hour less in US winter time).
   const long offset=EEA_NewsServerOffsetAt((long)value.time-now_offset,now_offset,(long)TimeGMT());
   EEA_Reaction r;
   EEA_ReactionDefaults(r);
   r.key=key; r.source=source; r.symbol=canonical; r.currency=currency; r.event_name=ev.name; r.impact=impact;
   r.cluster_label=cluster_label!="" ? cluster_label : currency+" "+ev.name;
   r.cluster_size=MathMax(1,cluster_size); r.cluster_lead=cluster_lead;
   r.event_utc=(long)value.time-offset;
   r.server_offset=offset;
   const long T=r.event_utc;
   r.has_actual=value.HasActualValue(); if(r.has_actual) r.actual=value.GetActualValue();
   r.has_forecast=value.HasForecastValue(); if(r.has_forecast) r.forecast=value.GetForecastValue();
   r.has_previous=value.HasPreviousValue(); if(r.has_previous) r.previous=value.GetPreviousValue();
   double diffs[];
   int history=EEA_NrSurpriseHistory(ev.id,value.time,diffs);
   EEA_NewsSurprise(r,(int)ev.digits,diffs,history);
   r.point=SymbolInfoDouble(broker,SYMBOL_POINT);
   int atr_copied=0;
   r.atr_ref=EEA_NrAtrRef(broker,T,offset,atr_copied);
   MqlRates m1[];
   ArraySetAsSeries(m1,false);
   int copied=CopyRates(broker,PERIOD_M1,(datetime)(T+offset-news.cfg.swing_block_before_min*60-900),
                        (datetime)(T+offset+4*3600),m1);
   if(copied<0 || atr_copied<0) return -1;      // terminal still loading history
   EEA_ReactionBar bars[];
   ArrayResize(bars,MathMax(copied,0));
   for(int i=0;i<copied;i++)
     {
      bars[i].t=(long)m1[i].time-offset; bars[i].o=m1[i].open; bars[i].h=m1[i].high; bars[i].l=m1[i].low;
      bars[i].c=m1[i].close; bars[i].volume=m1[i].tick_volume; bars[i].spread=m1[i].spread*r.point;
     }
   EEA_NewsReactionPath(r,bars,copied);
   if(r.quality=="") r.quality="INCOMPLETE_NO_M1_HISTORY";
   // Spread: ticks when the broker still has them, otherwise the M1 bar spread.
   MqlTick ticks[];
   int tick_count=CopyTicksRange(broker,ticks,COPY_TICKS_INFO,(ulong)(T+offset-1800)*1000,(ulong)(T+offset+3600)*1000);
   EEA_ReactionSpread samples[];
   if(tick_count>100)
     {
      ArrayResize(samples,tick_count);
      for(int i=0;i<tick_count;i++)
        { samples[i].t=(long)(ticks[i].time_msc/1000)-offset; samples[i].spread=ticks[i].ask-ticks[i].bid; }
      r.spread_source="TICKS";
      EEA_NewsReactionSpread(r,samples,tick_count);
     }
   else
     {
      ArrayResize(samples,copied);
      for(int i=0;i<copied;i++) { samples[i].t=bars[i].t; samples[i].spread=bars[i].spread; }
      r.spread_source="M1";
      EEA_NewsReactionSpread(r,samples,copied);
     }
   // Tick volume in the 15 minutes after T against the same window of up to 7 prior days.
   long after=0;
   for(int i=0;i<copied;i++) if(bars[i].t>=T && bars[i].t<T+900) after+=bars[i].volume;
   double base_sum=0.0; int base_days=0;
   for(int d=1;d<=7;d++)
     {
      MqlRates prior[];
      int pc=CopyRates(broker,PERIOD_M1,(datetime)(T+offset-d*86400),(datetime)(T+offset-d*86400+840),prior);
      if(pc<=0) continue;
      long v=0; for(int i=0;i<pc;i++) v+=prior[i].tick_volume;
      if(v>0) { base_sum+=(double)v; base_days++; }
     }
   if(base_days>=3 && base_sum>0.0) { r.has_volume_ratio=true; r.tick_volume_ratio_15m=after/(base_sum/base_days); }
   EEA_NewsGuardReplay(r,bars,copied,news.cfg.scalp_block_before_min,news.cfg.swing_block_before_min,
                       news.cfg.post_min,news.cfg.max_normalize_min);
   // News Guard timing for this symbol.
   int si=EEA_NewsSymbolIndex(news,canonical);
   if(si>=0)
     {
      if(news.symbols[si].normal_at_utc>=T && news.symbols[si].normal_at_utc<T+4*3600)
         r.guard_normal_min=(int)((news.symbols[si].normal_at_utc-T)/60);
      r.guard_timeout=(news.symbols[si].timeout_event_utc==T);
     }
   // EA trades (LIVE only): positions open across the event, exits, break-even value.
   if(source=="LIVE")
     {
      for(int i=0;i<trades.count;i++)
        {
         const EEA_ManagedTrade t=trades.items[i];
         if(t.intent.canonical_symbol!=canonical || t.opened_at_utc<=0) continue;
         if(t.exited_at_utc>=T && t.exited_at_utc<T+3600) r.exits_in_window++;
         if(t.opened_at_utc>=T || (!t.active && t.exited_at_utc<T)) continue;
         r.positions_open++;
         double risk=MathAbs(t.entry_price-t.initial_sl);
         int k0=EEA_NewsBarClosingBy(bars,copied,T-900), k1=EEA_NewsBarClosingBy(bars,copied,T+3600);
         string r0=(k0>=0 && risk>0.0) ? DoubleToString(t.direction*(bars[k0].c-t.entry_price)/risk,2) : "-";
         string r1=(k1>=0 && risk>0.0) ? DoubleToString(t.direction*(bars[k1].c-t.entry_price)/risk,2) : "-";
         r.positions_detail+=(r.positions_detail=="" ? "" : "; ")+IntegerToString(t.entry_ticket)+" "+t.profile+
                             " R@T-15 "+r0+" R@T+60 "+r1+(t.be_done ? " BE" : "");
         if(t.be_done)
           {
            r.be_before_news++;
            for(int b=0;b<copied;b++)
               if(bars[b].t>=T && bars[b].t<T+3600 &&
                  ((t.direction==1 && bars[b].l<=t.initial_sl) || (t.direction==-1 && bars[b].h>=t.initial_sl)))
                 { r.be_would_have_hit_sl++; break; }
           }
        }
      r.entries_blocked=EEA_NewsEffectCount(news,canonical,"ENTRY_BLOCKED",T-4*3600,T+4*3600);
      r.pending_cancelled=EEA_NewsEffectCount(news,canonical,"PENDING_CANCEL",T-4*3600,T+4*3600);
     }
   if(!EEA_WriteAtomicAppendText(EEA_NrLogPath(root),EEA_NrJson(r)+"\r\n"))
     { rt.reason="NEWS_REACTION_PERSISTENCE_FAILED"; return 0; }
   EEAEvent event;
   EEAEvent_Init(event,r.quality=="OK" ? "NEWS_REACTION_RECORDED" : "NEWS_REACTION_INCOMPLETE",TimeGMT(),canonical,key,"",
                 r.quality,r.quality=="OK" ? "OK" : "DEGRADED");
   event.config_version=news.config_version;
   event.details_json="{\"event\":\""+EEA_JsonEscape(currency+" "+r.event_name)+"\",\"source\":\""+source+"\""+
      EEA_NrNum("move_15m_atr",r.move_ok[2],r.atr_ref>0.0 ? r.move[2]/r.atr_ref : 0.0,2)+
      EEA_NrNum("spread_peak_ratio",r.spread_peak_ratio>0.0,r.spread_peak_ratio,2)+"}";
   audit.Append(event,"EA_NEWS_REACTION");
   EEA_ReactionSummary s;
   s.group=EEA_NewsReactionGroup(r.cluster_label,canonical);
   s.ok=(r.quality=="OK");
   s.move15_atr=(r.move_ok[2] && r.atr_ref>0.0) ? r.move[2]/r.atr_ref : 0.0;
   s.move60_atr=(r.move_ok[3] && r.atr_ref>0.0) ? r.move[3]/r.atr_ref : 0.0;
   s.spread_ratio=r.spread_peak_ratio;
   s.recovery_min=EEA_NewsReactionRecoveryMin(r);
   s.reversal=r.reversal_60;
   s.replay_ok=r.replay_ok; s.covered=r.guard_covered; s.residual_atr=r.residual_after_block_atr;
   EEA_NrRemember(rt,key,s,EEA_NrRecentText(r),r.cluster_lead);
   return 1;
  }

// Records every HIGH event of [from, to] for the affected selected symbols, within budget.
// Returns the time of the last fully processed event (or `to` when all were processed),
// or -1 when history was not ready.
long EEA_NrProcessWindow(EEA_NewsReactionRuntime &rt,const string root,CAuditLog &audit,const long from,const long to,
                         const string source,const EEA_NewsRuntime &news,const EEA_TradeManagerRuntime &trades,
                         int &budget)
  {
   const long now_offset=EEA_NewsServerOffsetSeconds();
   const long now=(long)TimeGMT();
   const uint started=GetTickCount();
   MqlCalendarValue values[];
   if(!CalendarValueHistory(values,(datetime)(from+EEA_NewsServerOffsetAt(from,now_offset,now)),
                            (datetime)(to+EEA_NewsServerOffsetAt(to,now_offset,now)),NULL,NULL)) return -1;
   long done_until=to;
   int total=ArraySize(values);
   for(int i=0;i<total;i++)
     {
      long T=(long)values[i].time-EEA_NewsServerOffsetAt((long)values[i].time-now_offset,now_offset,now);
      if(T<=from) continue;
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id,ev) || ev.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry country;
      if(!CalendarCountryById(ev.country_id,country) || !EEA_NewsCurrencyTracked(country.currency)) continue;
      if(EEA_NewsEventIgnored(ev.name,news.cfg.ignore_keywords)) continue;
      for(int s=0;s<news.symbol_count;s++)
        {
         if(news.symbols[s].broker=="") continue;
         // Red (own currency) and yellow (another major currency's rates/inflation/labour/growth).
         string impact=EEA_NewsAffects(news.symbols[s].currencies,country.currency) ? "DIRECT" :
                       (EEA_NewsIndirectAffects(news.symbols[s].currencies,country.currency,(int)ev.sector) ? "INDIRECT" : "");
         if(impact=="") continue;
         // Every HIGH event released at the same time that also reaches this symbol.
         string labels[]; int label_count=0;
         for(int j=0;j<total;j++)
           {
            if(values[j].time!=values[i].time) continue;
            MqlCalendarEvent other;
            if(!CalendarEventById(values[j].event_id,other) || other.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
            MqlCalendarCountry other_country;
            if(!CalendarCountryById(other.country_id,other_country) || !EEA_NewsCurrencyTracked(other_country.currency)) continue;
            if(EEA_NewsEventIgnored(other.name,news.cfg.ignore_keywords)) continue;
            if(!EEA_NewsAffects(news.symbols[s].currencies,other_country.currency) &&
               !EEA_NewsIndirectAffects(news.symbols[s].currencies,other_country.currency,(int)other.sector)) continue;
            ArrayResize(labels,label_count+1); labels[label_count++]=other_country.currency+" "+other.name;
           }
         string cluster=EEA_NewsClusterLabel(labels,label_count);
         bool lead=(label_count<=1 || labels[0]==country.currency+" "+ev.name);
         if(EEA_NrKnown(rt,IntegerToString((long)values[i].id)+"|"+news.symbols[s].canonical)) continue;
         if(budget<=0 || GetTickCount()-started>EEA_NR_MAX_MS_PER_TIMER) return T-1;
         int status=EEA_NrRecord(rt,root,audit,values[i],ev,country.currency,news.symbols[s].canonical,
                                 news.symbols[s].broker,source,impact,cluster,label_count,lead,news,trades);
         if(status<0) return -1;
         if(status>0) budget--;
        }
     }
   return done_until;
  }

// Timer entry point: LIVE records for the last 48 hours once settled, then BACKFILL.
void EEA_NewsReactionUpdate(EEA_NewsReactionRuntime &rt,CAuditLog &audit,const string root,
                            const EEA_NewsRuntime &news,const EEA_TradeManagerRuntime &trades,
                            const long backfill_from_utc)
  {
   if(!news.initialized || news.disabled || news.symbol_count==0) { rt.reason="NEWS_REACTION_WAIT_GUARD"; return; }
   if(!rt.loaded) EEA_NewsReactionLoad(rt,root,backfill_from_utc);
   const long now=(long)TimeGMT();
   int budget=EEA_NR_MAX_PER_TIMER;
   if(now-rt.last_live_scan_utc>=EEA_NR_LIVE_SCAN_SECONDS)
     {
      long result=EEA_NrProcessWindow(rt,root,audit,now-EEA_NR_LIVE_LOOKBACK_SECONDS,now-EEA_NR_SETTLE_SECONDS,
                                      "LIVE",news,trades,budget);
      if(result>=now-EEA_NR_SETTLE_SECONDS) rt.last_live_scan_utc=now;
      rt.reason=result<0 ? "NEWS_REACTION_HISTORY_LOADING" : "NEWS_REACTION_LIVE_SCANNED";
     }
   if(rt.backfill_done || budget<=0) return;
   const long backfill_end=now-EEA_NR_LIVE_LOOKBACK_SECONDS;
   long window_end=MathMin(rt.backfill_cursor_utc+7*86400,backfill_end);
   long result=EEA_NrProcessWindow(rt,root,audit,rt.backfill_cursor_utc,window_end,"BACKFILL",news,trades,budget);
   if(result<0)
     {
      // History not ready: retry; after several attempts skip a day so the backfill moves on.
      rt.not_ready_attempts++;
      if(rt.not_ready_attempts>=EEA_NR_MAX_NOT_READY)
        { rt.backfill_cursor_utc+=86400; rt.not_ready_attempts=0; EEA_NrWriteBackfill(rt,root); }
      rt.reason="NEWS_REACTION_BACKFILL_WAITING_HISTORY";
      return;
     }
   rt.not_ready_attempts=0;
   rt.backfill_cursor_utc=result;
   if(rt.backfill_cursor_utc>=backfill_end) { rt.backfill_done=true; rt.reason="NEWS_REACTION_BACKFILL_DONE"; }
   else rt.reason="NEWS_REACTION_BACKFILL_RUNNING";
   EEA_NrWriteBackfill(rt,root);
  }

bool EEA_NewsReactionStatsFor(const EEA_NewsReactionRuntime &rt,const string currency,const string event_name,
                              const string symbol,EEA_ReactionStats &stats)
  {
   EEA_NewsReactionStats(rt.summaries,rt.summary_count,EEA_NrGroup(currency,event_name,symbol),stats);
   return stats.n>0;
  }

bool EEA_NewsReactionStatsForCluster(const EEA_NewsReactionRuntime &rt,const string cluster_label,
                                     const string symbol,EEA_ReactionStats &stats)
  {
   EEA_NewsReactionStats(rt.summaries,rt.summary_count,EEA_NewsReactionGroup(cluster_label,symbol),stats);
   return stats.n>0;
  }

#endif
