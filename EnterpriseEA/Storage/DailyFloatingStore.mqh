#ifndef ENTERPRISE_EA_DAILY_FLOATING_STORE_MQH
#define ENTERPRISE_EA_DAILY_FLOATING_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Core\Events.mqh"

// TC-029 / REQ-010: per operator-local day book. Every refresh overwrites the floating value of its day, so a
// past day keeps the value of its last refresh = the end-of-day snapshot. A day nobody observed has no entry and
// the calendar shows "unavailable" instead of guessing. v1.1.0 adds the day-detail fields: start balance/equity
// (first observation of the day, set once), the most negative floating seen (max floating drawdown, money) and
// the realized R of the trades that exited that local day. Each field has a "known" bit in the row flags so a
// v1.0.0 row (floating only) or an R-only row never invents the missing values.
#define EEA_DAILY_FLOATING_MAX_DAYS 400
#define EEA_DAILY_FLOATING_DOCUMENT "daily-floating-v1.1.0"
#define EEA_DAILY_FLOATING_DOCUMENT_V10 "daily-floating-v1.0.0"
#define EEA_DAILY_FLOATING_HAS_VALUE 1
#define EEA_DAILY_FLOATING_HAS_START 2
#define EEA_DAILY_FLOATING_HAS_MIN 4

struct EEA_DailyFloatingRow
  {
   long   day;          // local day index: (utc + offset) / 86400
   double value;
   long   at_utc;       // time of the last refresh of this day
   int    flags;        // EEA_DAILY_FLOATING_HAS_*
   double start_balance;
   double start_equity;
   double min_floating; // most negative floating seen (stays >= 0 when it never went negative)
   double r_sum;
   double r_best;
   double r_worst;
   int    r_count;
  };

struct EEA_DailyFloatingBook
  {
   int count;
   long offset_seconds;
   bool dirty;
   bool urgent;         // an R was added: write without waiting for the throttle
   bool loaded;         // set by the owner after EEA_DailyFloatingLoad; R is skipped until then
   EEA_DailyFloatingRow rows[EEA_DAILY_FLOATING_MAX_DAYS];
  };

static EEA_DailyFloatingBook g_daily_floating;

void EEA_DailyFloatingReset(EEA_DailyFloatingBook &book,const long offset_seconds)
  {
   book.count=0; book.offset_seconds=offset_seconds; book.dirty=false; book.urgent=false;
  }

int EEA_DailyFloatingFind(const EEA_DailyFloatingBook &book,const long day)
  {
   for(int i=0;i<book.count;i++) if(book.rows[i].day==day) return i;
   return -1;
  }

void EEA_DailyFloatingRowInit(EEA_DailyFloatingRow &row,const long day)
  {
   row.day=day; row.value=0.0; row.at_utc=0; row.flags=0; row.start_balance=0.0; row.start_equity=0.0;
   row.min_floating=0.0; row.r_sum=0.0; row.r_best=0.0; row.r_worst=0.0; row.r_count=0;
  }

// Index of the row of `day`; inserted (sorted, oldest dropped beyond the capacity) when missing.
int EEA_DailyFloatingEnsure(EEA_DailyFloatingBook &book,const long day)
  {
   int index=EEA_DailyFloatingFind(book,day);
   if(index>=0) return index;
   if(book.count>=EEA_DAILY_FLOATING_MAX_DAYS)
     {
      for(int i=1;i<book.count;i++) book.rows[i-1]=book.rows[i];
      book.count--;
     }
   int at=book.count;
   while(at>0 && book.rows[at-1].day>day) { book.rows[at]=book.rows[at-1]; at--; }
   EEA_DailyFloatingRowInit(book.rows[at],day);
   book.count++;
   return at;
  }

bool EEA_DailyFloatingGet(const long day,EEA_DailyFloatingRow &row)
  {
   int index=EEA_DailyFloatingFind(g_daily_floating,day);
   if(index<0) return false;
   row=g_daily_floating.rows[index];
   return true;
  }

bool EEA_DailyFloatingLookup(const long day,double &value)
  {
   int index=EEA_DailyFloatingFind(g_daily_floating,day);
   if(index<0 || (g_daily_floating.rows[index].flags & EEA_DAILY_FLOATING_HAS_VALUE)==0) return false;
   value=g_daily_floating.rows[index].value;
   return true;
  }

// One observation of the day: overwrites the floating value (= equity - balance), sets the start balance/equity
// once and keeps the most negative floating. `start_balance` is the real start of the day (current balance minus the
// realized net of the day so far, computed by the caller); `start_known` is false while the daily stats are not
// merged yet, in which case the start is left unset and taken on a later call. start_equity is the equity at the
// moment the start is set (first observation), used only for the floating DD percentage.
void EEA_DailyFloatingObserve(EEA_DailyFloatingBook &book,const long day,const double balance,const double equity,
                              const long at_utc,const double start_balance,const bool start_known)
  {
   int index=EEA_DailyFloatingEnsure(book,day);
   double floating=equity-balance;
   book.rows[index].value=floating; book.rows[index].at_utc=at_utc;
   if(start_known && (book.rows[index].flags & EEA_DAILY_FLOATING_HAS_START)==0)
     {
      book.rows[index].start_balance=start_balance; book.rows[index].start_equity=equity;
      book.rows[index].flags|=EEA_DAILY_FLOATING_HAS_START;
     }
   if((book.rows[index].flags & EEA_DAILY_FLOATING_HAS_MIN)==0 || floating<book.rows[index].min_floating)
     {
      book.rows[index].min_floating=floating;
      book.rows[index].flags|=EEA_DAILY_FLOATING_HAS_MIN;
     }
   book.rows[index].flags|=EEA_DAILY_FLOATING_HAS_VALUE;
   book.dirty=true;
  }

// Adds the realized R of one closed trade to `day`.
void EEA_DailyFloatingAddR(EEA_DailyFloatingBook &book,const long day,const double r)
  {
   if(!MathIsValidNumber(r)) return;
   int index=EEA_DailyFloatingEnsure(book,day);
   if(book.rows[index].r_count==0) { book.rows[index].r_best=r; book.rows[index].r_worst=r; }
   else
     {
      book.rows[index].r_best=MathMax(book.rows[index].r_best,r);
      book.rows[index].r_worst=MathMin(book.rows[index].r_worst,r);
     }
   book.rows[index].r_sum+=r; book.rows[index].r_count++;
   book.dirty=true; book.urgent=true;
  }

// Exit hook (Trade Manager): the R of a trade is added once, when its exit is recorded, to the local day of the exit
// time. Skipped while the book is not loaded yet (the maintenance loop loads it on its first pass); an exit recorded
// before that loses its R in the calendar only, logs/trades.jsonl keeps it.
bool EEA_DailyFloatingRecordExitR(const long exit_utc,const double r)
  {
   if(!g_daily_floating.loaded) return false;
   long utc=exit_utc>0 ? exit_utc : (long)TimeGMT();
   EEA_DailyFloatingAddR(g_daily_floating,(utc+g_daily_floating.offset_seconds)/86400,r);
   return true;
  }

string EEA_DailyFloatingPath(const string root) { return root+"/current/daily_floating.json"; }

bool EEA_DailyFloatingWrite(const string root,const EEA_DailyFloatingBook &book,const string config_version,
                            const string account_fingerprint)
  {
   if(root=="" || config_version=="" || account_fingerprint=="") return false;
   string days="";
   for(int i=0;i<book.count;i++)
     {
      if(i>0) days+=",";
      days+="["+IntegerToString(book.rows[i].day)+","+DoubleToString(book.rows[i].value,8)+","+
            IntegerToString(book.rows[i].at_utc)+","+DoubleToString(book.rows[i].start_balance,8)+","+
            DoubleToString(book.rows[i].start_equity,8)+","+DoubleToString(book.rows[i].min_floating,8)+","+
            DoubleToString(book.rows[i].r_sum,8)+","+DoubleToString(book.rows[i].r_best,8)+","+
            DoubleToString(book.rows[i].r_worst,8)+","+IntegerToString(book.rows[i].r_count)+","+
            IntegerToString(book.rows[i].flags)+"]";
     }
   string json="{\"document_version\":\""+EEA_DAILY_FLOATING_DOCUMENT+"\",\"config_version\":\""+
      EEA_JsonEscape(config_version)+"\",\"account_fingerprint\":\""+EEA_JsonEscape(account_fingerprint)+
      "\",\"utc_offset_seconds\":"+IntegerToString(book.offset_seconds)+",\"days\":["+days+"]}";
   return EEA_WriteAtomicText(EEA_DailyFloatingPath(root),json);
  }

bool EEA_DailyFloatingReadFile(const string path,string &json)
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

// A missing, foreign or malformed file leaves the book empty (days are then "unavailable").
// v1.0.0 files (3 fields per day) are still accepted; their day-detail fields stay unknown.
bool EEA_DailyFloatingLoad(const string root,EEA_DailyFloatingBook &book,const string config_version,
                           const string account_fingerprint,const long offset_seconds)
  {
   EEA_DailyFloatingReset(book,offset_seconds);
   string json;
   if(!EEA_DailyFloatingReadFile(EEA_DailyFloatingPath(root),json)) return false;
   if((StringFind(json,"\"document_version\":\""+EEA_DAILY_FLOATING_DOCUMENT+"\"")<0 &&
       StringFind(json,"\"document_version\":\""+EEA_DAILY_FLOATING_DOCUMENT_V10+"\"")<0) ||
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
      if(close<0) { EEA_DailyFloatingReset(book,offset_seconds); return false; }
      string fields[];
      int n=StringSplit(StringSubstr(body,open+1,close-open-1),',',fields);
      if(n!=3 && n!=11) { EEA_DailyFloatingReset(book,offset_seconds); return false; }
      long day=StringToInteger(fields[0]);
      double value=StringToDouble(fields[1]);
      if(day<=0 || !MathIsValidNumber(value)) { EEA_DailyFloatingReset(book,offset_seconds); return false; }
      int index=EEA_DailyFloatingEnsure(book,day);
      book.rows[index].value=value; book.rows[index].at_utc=StringToInteger(fields[2]);
      book.rows[index].flags=EEA_DAILY_FLOATING_HAS_VALUE;
      if(n==11)
        {
         book.rows[index].start_balance=StringToDouble(fields[3]); book.rows[index].start_equity=StringToDouble(fields[4]);
         book.rows[index].min_floating=StringToDouble(fields[5]); book.rows[index].r_sum=StringToDouble(fields[6]);
         book.rows[index].r_best=StringToDouble(fields[7]); book.rows[index].r_worst=StringToDouble(fields[8]);
         book.rows[index].r_count=(int)StringToInteger(fields[9]);
         book.rows[index].flags=(int)StringToInteger(fields[10]);
        }
      pos=close+1;
     }
   book.dirty=false;
   return true;
  }

#endif
