#ifndef ENTERPRISE_EA_CALENDAR_EXPORT_MQH
#define ENTERPRISE_EA_CALENDAR_EXPORT_MQH

#include "../Storage/AtomicWriter.mqh"
#include "../News/NewsCalendar.mqh"
#include "../News/NewsReaction.mqh"
#include "../Storage/StrategyCandidateStore.mqh"
#include "BarExport.mqh"

// G53 research export: the MT5 economic calendar since 2010 (HIGH and MODERATE events of the tracked
// currencies) to research/calendar/calendar_<YEAR>.csv, so the News Guard rules can be measured on years of
// trades instead of the news log since 2026-01. Read-only calendar access, no trading effect. One year per
// timer pass, only once the bar export is idle. A past year is written once; the current year again when its
// file is older than the bar export's staleness rule (a week, or before the weekend). Ignored keywords are not
// applied here: the research applies them, so it can measure them too.
// time_utc uses the broker offset valid at the event (EEA_NewsServerOffsetAt, as the reaction recorder).

#define EEA_CALENDAR_EXPORT_FROM_YEAR 2010
#define EEA_CALENDAR_EXPORT_RECHECK_SECONDS 3600

struct EEA_CalendarExportRuntime
  {
   bool enabled;
   bool done;
   string root;
   int year;              // next year to look at
   int written;           // years written in this pass
   int events;            // rows written in this pass
   string reason;
   long next_check_utc;
  };

void EEA_CalendarExportInit(EEA_CalendarExportRuntime &rt,const string root,const bool enabled)
  {
   rt.enabled=enabled; rt.done=false; rt.root=root; rt.year=EEA_CALENDAR_EXPORT_FROM_YEAR;
   rt.written=0; rt.events=0; rt.reason=enabled ? "CALENDAR_EXPORT_WAITING" : "CALENDAR_EXPORT_DISABLED";
   rt.next_check_utc=0;
  }

int EEA_CalendarExportYearOf(const long utc)
  {
   MqlDateTime t;
   TimeToStruct((datetime)utc,t);
   return t.year;
  }

long EEA_CalendarExportYearStart(const int year)
  {
   MqlDateTime t;
   t.year=year; t.mon=1; t.day=1; t.hour=0; t.min=0; t.sec=0; t.day_of_week=0; t.day_of_year=0;
   return (long)StructToTime(t);
  }

string EEA_CalendarExportPath(const string root,const int year)
  { return root+"/research/calendar/calendar_"+IntegerToString(year)+".csv"; }

string EEA_CalendarExportMetaPath(const string root) { return root+"/research/calendar/calendar_meta.json"; }

// A field without the CSV separators (event names may hold commas or quotes).
string EEA_CalendarExportField(const string text)
  {
   string s=text;
   StringReplace(s,","," "); StringReplace(s,"\""," "); StringReplace(s,"\n"," "); StringReplace(s,"\r"," ");
   return s;
  }

// Is the file of this year due? Past years once; the current year by the bar export's staleness rule.
bool EEA_CalendarExportDue(const string root,const int year,const int current_year,const long now_utc)
  {
   if(!FileIsExist(EEA_CalendarExportPath(root,year),0)) return true;
   if(year<current_year) return false;
   string json;
   if(!EEA_StrategyCandidateStoreReadText(EEA_CalendarExportMetaPath(root),json)) return true;
   return EEA_BarExportStale(StringToInteger(EEA_StrategyCandidateStoreField(json,"exported_at_utc")),now_utc);
  }

// Writes one year; false when the calendar could not be read (tried again on a later pass).
bool EEA_CalendarExportYear(EEA_CalendarExportRuntime &rt,const int year,int &rows)
  {
   rows=0;
   const long now=(long)TimeGMT();
   const long now_offset=EEA_NewsServerOffsetSeconds();
   const long from=EEA_CalendarExportYearStart(year);
   const long to=MathMin(EEA_CalendarExportYearStart(year+1),now+7*86400);
   MqlCalendarValue values[];
   ResetLastError();
   if(!CalendarValueHistory(values,(datetime)(from+EEA_NewsServerOffsetAt(from,now_offset,now)),
                            (datetime)(to+EEA_NewsServerOffsetAt(to,now_offset,now)),NULL,NULL))
     { rt.reason="CALENDAR_EXPORT_READ_FAILED_"+IntegerToString(GetLastError()); return false; }
   // No value at all in a year = the calendar is not loaded yet: never write an empty past year.
   if(ArraySize(values)<=0) { rt.reason="CALENDAR_EXPORT_EMPTY_"+IntegerToString(year); return false; }
   FolderCreate(rt.root+"/research",0);
   FolderCreate(rt.root+"/research/calendar",0);
   const string path=EEA_CalendarExportPath(rt.root,year);
   const string tmp=path+".tmp";
   int h=FileOpen(tmp,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { rt.reason="CALENDAR_EXPORT_WRITE_FAILED"; return false; }
   FileWriteString(h,"time_utc,time_server,currency,importance,sector,event_id,name,actual,forecast,previous\n");
   string chunk="";
   const int total=ArraySize(values);
   for(int i=0;i<total;i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id,ev)) continue;
      if(ev.importance!=CALENDAR_IMPORTANCE_HIGH && ev.importance!=CALENDAR_IMPORTANCE_MODERATE) continue;
      MqlCalendarCountry country;
      if(!CalendarCountryById(ev.country_id,country) || !EEA_NewsCurrencyTracked(country.currency)) continue;
      const long server=(long)values[i].time;
      const long utc=server-EEA_NewsServerOffsetAt(server-now_offset,now_offset,now);
      chunk+=IntegerToString(utc)+","+IntegerToString(server)+","+country.currency+","+
             (ev.importance==CALENDAR_IMPORTANCE_HIGH ? "HIGH" : "MODERATE")+","+IntegerToString((int)ev.sector)+","+
             IntegerToString((long)ev.id)+","+EEA_CalendarExportField(ev.name)+","+
             EEA_NewsValueText(values[i].HasActualValue(),values[i].GetActualValue())+","+
             EEA_NewsValueText(values[i].HasForecastValue(),values[i].GetForecastValue())+","+
             EEA_NewsValueText(values[i].HasPreviousValue(),values[i].GetPreviousValue())+"\n";
      rows++;
      if(rows%2000==0) { FileWriteString(h,chunk); chunk=""; }
     }
   if(chunk!="") FileWriteString(h,chunk);
   FileClose(h);
   if(!FileMove(tmp,0,path,FILE_REWRITE)) { rt.reason="CALENDAR_EXPORT_WRITE_FAILED"; return false; }
   return true;
  }

void EEA_CalendarExportWriteMeta(const EEA_CalendarExportRuntime &rt,const int last_year)
  {
   string json="{\"from_year\":"+IntegerToString(EEA_CALENDAR_EXPORT_FROM_YEAR)+",\"to_year\":"+IntegerToString(last_year)+
      ",\"exported_at_utc\":"+IntegerToString((long)TimeGMT())+",\"server_offset_now\":"+
      IntegerToString(EEA_NewsServerOffsetSeconds())+",\"importance\":[\"HIGH\",\"MODERATE\"]"+
      ",\"time_rule\":\"utc=server-EEA_NewsServerOffsetAt\"}";
   EEA_WriteAtomicText(EEA_CalendarExportMetaPath(rt.root),json);
  }

// One step per timer pass; `idle` is false while the bar export is still writing.
void EEA_CalendarExportUpdate(EEA_CalendarExportRuntime &rt,const bool idle)
  {
   if(!rt.enabled || !idle) return;
   const long now=(long)TimeGMT();
   if(rt.done)
     {
      if(now<rt.next_check_utc) return;
      rt.done=false; rt.year=EEA_CALENDAR_EXPORT_FROM_YEAR; rt.written=0; rt.events=0;
     }
   const int current=EEA_CalendarExportYearOf(now);
   // Skip the years already written (no calendar call), then write at most one year per pass.
   while(rt.year<=current && !EEA_CalendarExportDue(rt.root,rt.year,current,now)) rt.year++;
   if(rt.year<=current)
     {
      int rows=0;
      if(!EEA_CalendarExportYear(rt,rt.year,rows))
        { rt.done=true; rt.next_check_utc=now+EEA_CALENDAR_EXPORT_RECHECK_SECONDS; return; }
      rt.written++; rt.events+=rows; rt.year++;
      rt.reason="CALENDAR_EXPORT_RUNNING";
      return;
     }
   if(rt.written>0) EEA_CalendarExportWriteMeta(rt,current);
   rt.done=true; rt.next_check_utc=now+EEA_CALENDAR_EXPORT_RECHECK_SECONDS;
   rt.reason=rt.written>0 ? "CALENDAR_EXPORT_DONE" : "CALENDAR_EXPORT_CURRENT";
  }

#endif
