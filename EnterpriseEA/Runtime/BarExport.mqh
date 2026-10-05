#ifndef ENTERPRISE_EA_BAR_EXPORT_MQH
#define ENTERPRISE_EA_BAR_EXPORT_MQH

#include "../Storage/AtomicWriter.mqh"
#include "../News/NewsCalendar.mqh"
#include "../Storage/StrategyCandidateStore.mqh"

// G10 research export: closed M5/H1/H4 bars of the selected symbols to
// research/bars_<SYMBOL>_<TF>.csv so that the setup parameters can be studied offline.
// Read-only market access; one symbol/timeframe per timer pass. Runs again when the
// start date changed, the last export is older than a week, or (G18) on the weekend when
// the last export predates that Saturday, so the weekly review has the whole week's bars.
// A finished export re-checks once an hour.
// G11: the sentiment reference pairs that are not selected symbols are exported on H1 only
// (from the replay start), so the sentiment at each news event can be rebuilt offline.
// The meta file carries the job signature: a different job list exports again.

#define EEA_BAR_EXPORT_MAX_JOBS 96
#define EEA_BAR_EXPORT_LEAD_DAYS 120   // level bars before the replay start (H4 swings, previous week)
#define EEA_BAR_EXPORT_MAX_AGE 604800
#define EEA_BAR_EXPORT_RECHECK_SECONDS 3600

struct EEA_BarExportRuntime
  {
   bool enabled;
   bool loaded;
   bool done;
   string root;
   long from_utc;
   long swing_from_utc;   // H1/H4 start (longer history for SWING research)
   int count;
   int next;
   int retries;           // history still loading from the server: try the job again later
   string canonical[EEA_BAR_EXPORT_MAX_JOBS];
   string broker[EEA_BAR_EXPORT_MAX_JOBS];
   int tf[EEA_BAR_EXPORT_MAX_JOBS];
   bool reference[EEA_BAR_EXPORT_MAX_JOBS];   // H1 of a sentiment reference pair (G11)
   string reason;
   long next_check_utc;   // a finished export re-checks staleness from this time
  };

void EEA_BarExportInit(EEA_BarExportRuntime &rt,const string root,const bool enabled,const long from_utc,
                       const long swing_from_utc=0)
  {
   rt.enabled=enabled; rt.loaded=false; rt.done=false; rt.root=root; rt.from_utc=from_utc;
   rt.swing_from_utc=(swing_from_utc>0 && swing_from_utc<from_utc) ? swing_from_utc : from_utc;
   rt.count=0; rt.next=0; rt.retries=0; rt.reason=enabled ? "EXPORT_WAITING" : "EXPORT_DISABLED";
   rt.next_check_utc=0;
  }

// 00:00 UTC of the Saturday of the current weekend, or 0 on a weekday.
long EEA_BarExportWeekendStart(const long now_utc)
  {
   const long day=now_utc/86400;
   const long weekday=(day+4)%7;   // 0 = Sunday (1970-01-01 was a Thursday)
   if(weekday==6) return day*86400;
   if(weekday==0) return (day-1)*86400;
   return 0;
  }

bool EEA_BarExportStale(const long exported_at_utc,const long now_utc)
  {
   if(now_utc-exported_at_utc>=EEA_BAR_EXPORT_MAX_AGE) return true;
   const long weekend=EEA_BarExportWeekendStart(now_utc);
   return weekend>0 && exported_at_utc<weekend;
  }

string EEA_BarExportTfName(const int tf) { return tf==PERIOD_M5 ? "M5" : tf==PERIOD_H1 ? "H1" : "H4"; }

string EEA_BarExportMetaPath(const string root) { return root+"/research/bars_meta.json"; }
string EEA_BarExportProgressPath(const string root) { return root+"/research/bars_progress.json"; }

string EEA_BarExportSignature(const EEA_BarExportRuntime &rt)
  {
   string sig=IntegerToString(rt.from_utc)+"|"+IntegerToString(rt.swing_from_utc);
   for(int j=0;j<rt.count;j++) sig+="|"+rt.canonical[j]+EEA_BarExportTfName(rt.tf[j])+(rt.reference[j] ? "R" : "");
   return sig;
  }

// A restart (chart timeframe change, re-attach) resumes after the jobs already written
// by the same export within the last day instead of starting over.
void EEA_BarExportWriteProgress(const EEA_BarExportRuntime &rt)
  {
   EEA_WriteAtomicText(EEA_BarExportProgressPath(rt.root),"{\"signature\":\""+EEA_BarExportSignature(rt)+
      "\",\"next\":"+IntegerToString(rt.next)+",\"written_at_utc\":"+IntegerToString((long)TimeGMT())+"}");
  }

void EEA_BarExportLoad(EEA_BarExportRuntime &rt,const string &canonical[],const string &broker[],const int count,
                       const string &ref_canonical[],const string &ref_broker[],const int ref_count)
  {
   rt.loaded=true;
   // The job list first: its signature decides whether the last export is still current.
   rt.count=0;
   int tfs[3]={PERIOD_M5,PERIOD_H1,PERIOD_H4};
   for(int i=0;i<count;i++)
      for(int k=0;k<3 && broker[i]!="" && rt.count<EEA_BAR_EXPORT_MAX_JOBS;k++)
        {
         rt.canonical[rt.count]=canonical[i]; rt.broker[rt.count]=broker[i]; rt.tf[rt.count]=tfs[k];
         rt.reference[rt.count]=false; rt.count++;
        }
   for(int r=0;r<ref_count && rt.count<EEA_BAR_EXPORT_MAX_JOBS;r++)
     {
      if(ref_broker[r]=="" || ref_canonical[r]=="") continue;
      bool selected=false;
      for(int i=0;i<count && !selected;i++) if(canonical[i]==ref_canonical[r] && broker[i]!="") selected=true;
      if(selected) continue;
      rt.canonical[rt.count]=ref_canonical[r]; rt.broker[rt.count]=ref_broker[r]; rt.tf[rt.count]=PERIOD_H1;
      rt.reference[rt.count]=true; rt.count++;
     }
   string json;
   if(EEA_StrategyCandidateStoreReadText(EEA_BarExportMetaPath(rt.root),json) &&
      StringToInteger(EEA_StrategyCandidateStoreField(json,"from_utc"))==rt.from_utc &&
      StringToInteger(EEA_StrategyCandidateStoreField(json,"swing_from_utc"))==rt.swing_from_utc &&
      EEA_StrategyCandidateStoreField(json,"signature")==EEA_BarExportSignature(rt) &&
      !EEA_BarExportStale(StringToInteger(EEA_StrategyCandidateStoreField(json,"exported_at_utc")),(long)TimeGMT()))
     { rt.done=true; rt.reason="EXPORT_CURRENT"; return; }
   FolderCreate(rt.root+"/research",0);
   rt.next=0;
   string progress;
   if(EEA_StrategyCandidateStoreReadText(EEA_BarExportProgressPath(rt.root),progress) &&
      EEA_StrategyCandidateStoreField(progress,"signature")==EEA_BarExportSignature(rt) &&
      (long)TimeGMT()-StringToInteger(EEA_StrategyCandidateStoreField(progress,"written_at_utc"))<86400)
      rt.next=(int)MathMax(0,MathMin(rt.count,StringToInteger(EEA_StrategyCandidateStoreField(progress,"next"))));
   rt.reason="EXPORT_RUNNING";
  }

bool EEA_BarExportJob(EEA_BarExportRuntime &rt,const int j,const bool last_try)
  {
   const long offset=EEA_NewsServerOffsetSeconds();
   const long start=(rt.tf[j]==PERIOD_M5 || rt.reference[j] ? rt.from_utc : rt.swing_from_utc);
   const long from_server=start+offset-EEA_BAR_EXPORT_LEAD_DAYS*86400;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   // Bar 1 onwards: the forming bar is never exported.
   int n=CopyRates(rt.broker[j],(ENUM_TIMEFRAMES)rt.tf[j],(datetime)from_server,
                   (datetime)((long)TimeTradeServer()-PeriodSeconds((ENUM_TIMEFRAMES)rt.tf[j])),rates);
   if(n<=0) return false;
   // The terminal downloads older history on demand; wait until it covers the start.
   if(!last_try && (long)rates[0].time>from_server+7*86400) return false;
   const int digits=(int)SymbolInfoInteger(rt.broker[j],SYMBOL_DIGITS);
   string path=rt.root+"/research/bars_"+rt.canonical[j]+"_"+EEA_BarExportTfName(rt.tf[j])+".csv";
   int h=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return false;
   FileWriteString(h,"time,open,high,low,close,spread\n");
   string chunk="";
   for(int i=0;i<n;i++)
     {
      chunk+=IntegerToString((long)rates[i].time)+","+DoubleToString(rates[i].open,digits)+","+
             DoubleToString(rates[i].high,digits)+","+DoubleToString(rates[i].low,digits)+","+
             DoubleToString(rates[i].close,digits)+","+IntegerToString(rates[i].spread)+"\n";
      if((i+1)%2000==0) { FileWriteString(h,chunk); chunk=""; }
     }
   if(chunk!="") FileWriteString(h,chunk);
   FileClose(h);
   return true;
  }

void EEA_BarExportWriteMeta(const EEA_BarExportRuntime &rt)
  {
   string json="{\"from_utc\":"+IntegerToString(rt.from_utc)+",\"swing_from_utc\":"+IntegerToString(rt.swing_from_utc)+",\"exported_at_utc\":"+IntegerToString((long)TimeGMT())+
      ",\"server_offset_now\":"+IntegerToString(EEA_NewsServerOffsetSeconds())+
      ",\"signature\":\""+EEA_BarExportSignature(rt)+"\",\"symbols\":[";
   int w=0;
   for(int j=0;j<rt.count;j++)
     {
      if(rt.tf[j]!=PERIOD_M5) continue;
      json+=(w++>0 ? "," : "")+"{\"symbol\":\""+rt.canonical[j]+"\",\"broker\":\""+rt.broker[j]+
         "\",\"point\":"+DoubleToString(SymbolInfoDouble(rt.broker[j],SYMBOL_POINT),10)+
         ",\"digits\":"+IntegerToString(SymbolInfoInteger(rt.broker[j],SYMBOL_DIGITS))+"}";
     }
   json+="],\"reference_h1\":[";
   w=0;
   for(int j=0;j<rt.count;j++)
      if(rt.reference[j]) json+=(w++>0 ? "," : "")+"\""+rt.canonical[j]+"\"";
   json+="]}";
   EEA_WriteAtomicText(EEA_BarExportMetaPath(rt.root),json);
  }

void EEA_BarExportUpdate(EEA_BarExportRuntime &rt,const string &canonical[],const string &broker[],const int count,
                         const string &ref_canonical[],const string &ref_broker[],const int ref_count)
  {
   if(!rt.enabled) return;
   if(rt.done)
     {
      const long now=(long)TimeGMT();
      if(now<rt.next_check_utc) return;
      rt.next_check_utc=now+EEA_BAR_EXPORT_RECHECK_SECONDS;
      rt.loaded=false; rt.done=false;   // EEA_BarExportLoad marks it current again if nothing is due
     }
   if(!rt.loaded) { EEA_BarExportLoad(rt,canonical,broker,count,ref_canonical,ref_broker,ref_count); return; }
   if(rt.next<rt.count)
     {
      if(EEA_BarExportJob(rt,rt.next,rt.retries>=10) || rt.retries>=10)
        { rt.next++; rt.retries=0; EEA_BarExportWriteProgress(rt); }
      else rt.retries++;
     }
   if(rt.next>=rt.count) { EEA_BarExportWriteMeta(rt); rt.done=true; rt.reason="EXPORT_DONE"; }
  }

#endif
