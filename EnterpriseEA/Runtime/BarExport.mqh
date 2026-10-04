#ifndef ENTERPRISE_EA_BAR_EXPORT_MQH
#define ENTERPRISE_EA_BAR_EXPORT_MQH

#include "../Storage/AtomicWriter.mqh"
#include "../News/NewsCalendar.mqh"
#include "../Storage/StrategyCandidateStore.mqh"

// G10 research export: closed M5/H1/H4 bars of the selected symbols to
// research/bars_<SYMBOL>_<TF>.csv so that the setup parameters can be studied offline.
// Read-only market access; one symbol/timeframe per timer pass. Runs again only when
// the last export is older than a week or the start date changed.

#define EEA_BAR_EXPORT_MAX_JOBS 96
#define EEA_BAR_EXPORT_LEAD_DAYS 120   // level bars before the replay start (H4 swings, previous week)
#define EEA_BAR_EXPORT_MAX_AGE 604800

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
   string reason;
  };

void EEA_BarExportInit(EEA_BarExportRuntime &rt,const string root,const bool enabled,const long from_utc,
                       const long swing_from_utc=0)
  {
   rt.enabled=enabled; rt.loaded=false; rt.done=false; rt.root=root; rt.from_utc=from_utc;
   rt.swing_from_utc=(swing_from_utc>0 && swing_from_utc<from_utc) ? swing_from_utc : from_utc;
   rt.count=0; rt.next=0; rt.retries=0; rt.reason=enabled ? "EXPORT_WAITING" : "EXPORT_DISABLED";
  }

string EEA_BarExportTfName(const int tf) { return tf==PERIOD_M5 ? "M5" : tf==PERIOD_H1 ? "H1" : "H4"; }

string EEA_BarExportMetaPath(const string root) { return root+"/research/bars_meta.json"; }

void EEA_BarExportLoad(EEA_BarExportRuntime &rt,const string &canonical[],const string &broker[],const int count)
  {
   rt.loaded=true;
   string json;
   if(EEA_StrategyCandidateStoreReadText(EEA_BarExportMetaPath(rt.root),json) &&
      StringToInteger(EEA_StrategyCandidateStoreField(json,"from_utc"))==rt.from_utc &&
      StringToInteger(EEA_StrategyCandidateStoreField(json,"swing_from_utc"))==rt.swing_from_utc &&
      (long)TimeGMT()-StringToInteger(EEA_StrategyCandidateStoreField(json,"exported_at_utc"))<EEA_BAR_EXPORT_MAX_AGE)
     { rt.done=true; rt.reason="EXPORT_CURRENT"; return; }
   FolderCreate(rt.root+"/research",0);
   rt.count=0;
   int tfs[3]={PERIOD_M5,PERIOD_H1,PERIOD_H4};
   for(int i=0;i<count;i++)
      for(int k=0;k<3 && broker[i]!="" && rt.count<EEA_BAR_EXPORT_MAX_JOBS;k++)
        { rt.canonical[rt.count]=canonical[i]; rt.broker[rt.count]=broker[i]; rt.tf[rt.count]=tfs[k]; rt.count++; }
   rt.next=0;
   rt.reason="EXPORT_RUNNING";
  }

bool EEA_BarExportJob(EEA_BarExportRuntime &rt,const int j,const bool final)
  {
   const long offset=EEA_NewsServerOffsetSeconds();
   const long start=(rt.tf[j]==PERIOD_M5 ? rt.from_utc : rt.swing_from_utc);
   const long from_server=start+offset-EEA_BAR_EXPORT_LEAD_DAYS*86400;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   // Bar 1 onwards: the forming bar is never exported.
   int n=CopyRates(rt.broker[j],(ENUM_TIMEFRAMES)rt.tf[j],(datetime)from_server,
                   (datetime)((long)TimeTradeServer()-PeriodSeconds((ENUM_TIMEFRAMES)rt.tf[j])),rates);
   if(n<=0) return false;
   // The terminal downloads older history on demand; wait until it covers the start.
   if(!final && (long)rates[0].time>from_server+7*86400) return false;
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
      ",\"server_offset_now\":"+IntegerToString(EEA_NewsServerOffsetSeconds())+",\"symbols\":[";
   int w=0;
   for(int j=0;j<rt.count;j++)
     {
      if(rt.tf[j]!=PERIOD_M5) continue;
      json+=(w++>0 ? "," : "")+"{\"symbol\":\""+rt.canonical[j]+"\",\"broker\":\""+rt.broker[j]+
         "\",\"point\":"+DoubleToString(SymbolInfoDouble(rt.broker[j],SYMBOL_POINT),10)+
         ",\"digits\":"+IntegerToString(SymbolInfoInteger(rt.broker[j],SYMBOL_DIGITS))+"}";
     }
   json+="]}";
   EEA_WriteAtomicText(EEA_BarExportMetaPath(rt.root),json);
  }

void EEA_BarExportUpdate(EEA_BarExportRuntime &rt,const string &canonical[],const string &broker[],const int count)
  {
   if(!rt.enabled || rt.done) return;
   if(!rt.loaded) { EEA_BarExportLoad(rt,canonical,broker,count); return; }
   if(rt.next<rt.count)
     {
      if(EEA_BarExportJob(rt,rt.next,rt.retries>=10) || rt.retries>=10) { rt.next++; rt.retries=0; }
      else rt.retries++;
     }
   if(rt.next>=rt.count) { EEA_BarExportWriteMeta(rt); rt.done=true; rt.reason="EXPORT_DONE"; }
  }

#endif
