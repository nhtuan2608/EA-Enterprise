#ifndef ENTERPRISE_EA_DAILY_FLOATING_STORE_MQH
#define ENTERPRISE_EA_DAILY_FLOATING_STORE_MQH

#include "AtomicWriter.mqh"
#include "..\Core\Events.mqh"

// TC-029: floating P/L (equity - balance) per operator-local day. Every refresh overwrites the value of its
// day, so a past day keeps the value of its last refresh = the end-of-day snapshot. A day nobody observed has
// no entry and the calendar shows "unavailable" instead of guessing.
#define EEA_DAILY_FLOATING_MAX_DAYS 400
#define EEA_DAILY_FLOATING_DOCUMENT "daily-floating-v1.0.0"

struct EEA_DailyFloatingRow
  {
   long   day;          // local day index: (utc + offset) / 86400
   double value;
   long   at_utc;       // time of the last refresh of this day
  };

struct EEA_DailyFloatingBook
  {
   int count;
   long offset_seconds;
   bool dirty;
   EEA_DailyFloatingRow rows[EEA_DAILY_FLOATING_MAX_DAYS];
  };

static EEA_DailyFloatingBook g_daily_floating;

void EEA_DailyFloatingReset(EEA_DailyFloatingBook &book,const long offset_seconds)
  {
   book.count=0; book.offset_seconds=offset_seconds; book.dirty=false;
  }

int EEA_DailyFloatingFind(const EEA_DailyFloatingBook &book,const long day)
  {
   for(int i=0;i<book.count;i++) if(book.rows[i].day==day) return i;
   return -1;
  }

bool EEA_DailyFloatingLookup(const long day,double &value)
  {
   int index=EEA_DailyFloatingFind(g_daily_floating,day);
   if(index<0) return false;
   value=g_daily_floating.rows[index].value;
   return true;
  }

// Overwrites the value of `day`; keeps days sorted and drops the oldest beyond the capacity.
void EEA_DailyFloatingUpdate(EEA_DailyFloatingBook &book,const long day,const double value,const long at_utc)
  {
   int index=EEA_DailyFloatingFind(book,day);
   if(index>=0)
     {
      book.rows[index].value=value; book.rows[index].at_utc=at_utc; book.dirty=true;
      return;
     }
   if(book.count>=EEA_DAILY_FLOATING_MAX_DAYS)
     {
      for(int i=1;i<book.count;i++) book.rows[i-1]=book.rows[i];
      book.count--;
     }
   int at=book.count;
   while(at>0 && book.rows[at-1].day>day) { book.rows[at]=book.rows[at-1]; at--; }
   book.rows[at].day=day; book.rows[at].value=value; book.rows[at].at_utc=at_utc;
   book.count++;
   book.dirty=true;
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
            IntegerToString(book.rows[i].at_utc)+"]";
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
bool EEA_DailyFloatingLoad(const string root,EEA_DailyFloatingBook &book,const string config_version,
                           const string account_fingerprint,const long offset_seconds)
  {
   EEA_DailyFloatingReset(book,offset_seconds);
   string json;
   if(!EEA_DailyFloatingReadFile(EEA_DailyFloatingPath(root),json)) return false;
   if(StringFind(json,"\"document_version\":\""+EEA_DAILY_FLOATING_DOCUMENT+"\"")<0 ||
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
      if(StringSplit(StringSubstr(body,open+1,close-open-1),',',fields)!=3)
        { EEA_DailyFloatingReset(book,offset_seconds); return false; }
      long day=StringToInteger(fields[0]);
      double value=StringToDouble(fields[1]);
      if(day<=0 || !MathIsValidNumber(value)) { EEA_DailyFloatingReset(book,offset_seconds); return false; }
      EEA_DailyFloatingUpdate(book,day,value,StringToInteger(fields[2]));
      pos=close+1;
     }
   book.dirty=false;
   return true;
  }

#endif
