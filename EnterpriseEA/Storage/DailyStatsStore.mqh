#ifndef ENTERPRISE_EA_DAILY_STATS_STORE_MQH
#define ENTERPRISE_EA_DAILY_STATS_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Core\Events.mqh"
#include "..\Runtime\RuntimeEvidence.mqh"

// Realized trading result per operator-local day (O-18), accumulated across sessions
// so the calendar keeps months beyond the broker history window. Days fully covered
// by the loaded history are recomputed from deals on every refresh; older days keep
// their stored values. Cash flows (deposits, withdrawals, credit) are excluded.
#define EEA_DAILY_STATS_MAX_DAYS 400
#define EEA_DAILY_STATS_DOCUMENT "daily-stats-v1.0.0"

struct EEA_DailyStatRow
  {
   long   day;          // local day index: (utc + offset) / 86400
   double net;
   int    trades;       // closing deals
   int    wins;
   int    losses;
   double gross_profit;
   double gross_loss;
  };

struct EEA_DailyStatsBook
  {
   int count;
   long offset_seconds;
   bool dirty;
   EEA_DailyStatRow rows[EEA_DAILY_STATS_MAX_DAYS];
  };

static EEA_DailyStatsBook g_daily_stats;

void EEA_DailyStatsReset(EEA_DailyStatsBook &book,const long offset_seconds)
  {
   book.count=0; book.offset_seconds=offset_seconds; book.dirty=false;
  }

int EEA_DailyStatsFind(const EEA_DailyStatsBook &book,const long day)
  {
   for(int i=0;i<book.count;i++) if(book.rows[i].day==day) return i;
   return -1;
  }

bool EEA_DailyStatsLookup(const long day,EEA_DailyStatRow &row)
  {
   int index=EEA_DailyStatsFind(g_daily_stats,day);
   if(index<0) return false;
   row=g_daily_stats.rows[index];
   return true;
  }

bool EEA_DailyStatsRowEqual(const EEA_DailyStatRow &a,const EEA_DailyStatRow &b)
  {
   return a.day==b.day && MathAbs(a.net-b.net)<1e-9 && a.trades==b.trades && a.wins==b.wins &&
          a.losses==b.losses && MathAbs(a.gross_profit-b.gross_profit)<1e-9 && MathAbs(a.gross_loss-b.gross_loss)<1e-9;
  }

// Keeps rows sorted by day and drops the oldest beyond the capacity.
void EEA_DailyStatsPut(EEA_DailyStatsBook &book,const EEA_DailyStatRow &row)
  {
   int index=EEA_DailyStatsFind(book,row.day);
   if(index>=0)
     {
      if(!EEA_DailyStatsRowEqual(book.rows[index],row)) { book.rows[index]=row; book.dirty=true; }
      return;
     }
   if(book.count>=EEA_DAILY_STATS_MAX_DAYS)
     {
      for(int i=1;i<book.count;i++) book.rows[i-1]=book.rows[i];
      book.count--;
     }
   int at=book.count;
   while(at>0 && book.rows[at-1].day>row.day) { book.rows[at]=book.rows[at-1]; at--; }
   book.rows[at]=row;
   book.count++;
   book.dirty=true;
  }

void EEA_DailyStatsRemove(EEA_DailyStatsBook &book,const long day)
  {
   int index=EEA_DailyStatsFind(book,day);
   if(index<0) return;
   for(int i=index+1;i<book.count;i++) book.rows[i-1]=book.rows[i];
   book.count--;
   book.dirty=true;
  }

// Recomputes every local day fully covered by the reconciled deal history.
bool EEA_DailyStatsMerge(EEA_DailyStatsBook &book,const EEA_RuntimeReconciliationSnapshot &snapshot,
                         const long offset_seconds,const long now_utc)
  {
   if(!snapshot.deals_complete || snapshot.history_from_utc<=0) return false;
   if(offset_seconds!=book.offset_seconds) EEA_DailyStatsReset(book,offset_seconds); // day boundaries moved
   long first_day=(snapshot.history_from_utc+offset_seconds+86399)/86400; // first fully covered day
   long today=(now_utc+offset_seconds)/86400;
   if(first_day>today) return true;
   int span=(int)(today-first_day+1);
   if(span>EEA_DAILY_STATS_MAX_DAYS) { first_day=today-EEA_DAILY_STATS_MAX_DAYS+1; span=EEA_DAILY_STATS_MAX_DAYS; }
   EEA_DailyStatRow fresh[];
   ArrayResize(fresh,span);
   for(int d=0;d<span;d++)
     {
      fresh[d].day=first_day+d; fresh[d].net=0.0; fresh[d].trades=0; fresh[d].wins=0; fresh[d].losses=0;
      fresh[d].gross_profit=0.0; fresh[d].gross_loss=0.0;
     }
   bool active[];
   ArrayResize(active,span);
   ArrayInitialize(active,false);
   for(int i=0;i<snapshot.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      if(snapshot.deals[i].type!="0" && snapshot.deals[i].type!="1") continue;
      long day=(snapshot.deals[i].time_utc+offset_seconds)/86400;
      if(day<first_day || day>today) continue;
      int d=(int)(day-first_day);
      double value=snapshot.deals[i].profit+snapshot.deals[i].commission+snapshot.deals[i].swap+snapshot.deals[i].fee;
      fresh[d].net+=value; active[d]=true;
      string entry=snapshot.deals[i].entry;
      if(entry=="1" || entry=="2" || entry=="3")
        {
         fresh[d].trades++;
         if(value>=0.0) { fresh[d].wins++; fresh[d].gross_profit+=value; }
         else { fresh[d].losses++; fresh[d].gross_loss+=value; }
        }
     }
   for(int d=0;d<span;d++)
     {
      if(active[d]) EEA_DailyStatsPut(book,fresh[d]);
      else EEA_DailyStatsRemove(book,fresh[d].day);
     }
   return true;
  }

string EEA_DailyStatsPath(const string root) { return root+"/current/daily_stats.json"; }

bool EEA_DailyStatsWrite(const string root,const EEA_DailyStatsBook &book,const string config_version,
                         const string account_fingerprint)
  {
   if(root=="" || config_version=="" || account_fingerprint=="") return false;
   string days="";
   for(int i=0;i<book.count;i++)
     {
      if(i>0) days+=",";
      days+="["+IntegerToString(book.rows[i].day)+","+DoubleToString(book.rows[i].net,8)+","+
            IntegerToString(book.rows[i].trades)+","+IntegerToString(book.rows[i].wins)+","+
            IntegerToString(book.rows[i].losses)+","+DoubleToString(book.rows[i].gross_profit,8)+","+
            DoubleToString(book.rows[i].gross_loss,8)+"]";
     }
   string json="{\"document_version\":\""+EEA_DAILY_STATS_DOCUMENT+"\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+
      "\",\"utc_offset_seconds\":"+IntegerToString(book.offset_seconds)+",\"days\":["+days+"]}";
   return EEA_WriteAtomicText(EEA_DailyStatsPath(root),json);
  }

bool EEA_DailyStatsReadFile(const string path,string &json)
  {
   json="";
   if(!FileIsExist(path,0)) return false;
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   ulong size=FileSize(handle);
   if(size==0 || size>1048576) { FileClose(handle); return false; }
   uchar bytes[];
   ArrayResize(bytes,(int)size);
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return false;
   json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   return true;
  }

// A missing, foreign or malformed file leaves the book empty; history refills it.
bool EEA_DailyStatsLoad(const string root,EEA_DailyStatsBook &book,const string config_version,
                        const string account_fingerprint,const long offset_seconds)
  {
   EEA_DailyStatsReset(book,offset_seconds);
   string json;
   if(!EEA_DailyStatsReadFile(EEA_DailyStatsPath(root),json)) return false;
   if(StringFind(json,"\"document_version\":\""+EEA_DAILY_STATS_DOCUMENT+"\"")<0 ||
      StringFind(json,"\"config_version\":\""+EEA_JsonEscape(config_version)+"\"")<0 ||
      StringFind(json,"\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+"\"")<0 ||
      StringFind(json,"\"utc_offset_seconds\":"+IntegerToString(offset_seconds)+",")<0) return false;
   int start=StringFind(json,"\"days\":[");
   if(start<0) return false;
   start+=StringLen("\"days\":[");
   int end=StringFind(json,"]}",start);
   if(end<start) return false;
   string body=StringSubstr(json,start,end-start);
   int pos=0;
   while(pos<StringLen(body))
     {
      int open=StringFind(body,"[",pos);
      if(open<0) break;
      int close=StringFind(body,"]",open);
      if(close<0) { EEA_DailyStatsReset(book,offset_seconds); return false; }
      string fields[];
      if(StringSplit(StringSubstr(body,open+1,close-open-1),',',fields)!=7)
        { EEA_DailyStatsReset(book,offset_seconds); return false; }
      EEA_DailyStatRow row;
      row.day=StringToInteger(fields[0]); row.net=StringToDouble(fields[1]);
      row.trades=(int)StringToInteger(fields[2]); row.wins=(int)StringToInteger(fields[3]);
      row.losses=(int)StringToInteger(fields[4]); row.gross_profit=StringToDouble(fields[5]);
      row.gross_loss=StringToDouble(fields[6]);
      if(row.day<=0 || !MathIsValidNumber(row.net)) { EEA_DailyStatsReset(book,offset_seconds); return false; }
      EEA_DailyStatsPut(book,row);
      pos=close+1;
     }
   book.dirty=false;
   return true;
  }

#endif
