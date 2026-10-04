#ifndef ENTERPRISE_EA_AI_BRIDGE_CLIENT_MQH
#define ENTERPRISE_EA_AI_BRIDGE_CLIENT_MQH

// AI Bridge client (master specification section 8, design 2026-10-04, Level 0/1).
// The EA writes requests to <root>/ai/requests and reads validated answers from
// <root>/ai/responses; an external bridge (bridge/ai_bridge.py) calls the claude or
// codex CLI. The EA never waits for AI: polling happens on the timer, a request that is
// not answered by its deadline counts as a failure, and three failures in a row open a
// 30-minute circuit. Answers are re-validated here (request id, type, provider, TTL,
// action whitelist) and are only displayed, stored and audited: AI never touches orders,
// risk or inputs.

#include "../Core/Events.mqh"
#include "../Storage/AtomicWriter.mqh"
#include "../Storage/AuditLog.mqh"

#define EEA_AI_TYPES 4
#define EEA_AI_MAX_PENDING 4
#define EEA_AI_LINES 8
#define EEA_AI_DEADLINE_SECONDS 300
#define EEA_AI_CIRCUIT_FAILURES 3
#define EEA_AI_CIRCUIT_SECONDS 1800
#define EEA_AI_HEARTBEAT_STALE 120

string EEA_AiType(const int i)
  {
   if(i==0) return "NEWS_DATA_REVIEW";
   if(i==1) return "NEWS_EVENT_REVIEW";
   if(i==2) return "EA_DIAGNOSTICS";
   if(i==3) return "ASK_AI";
   return "";
  }

int EEA_AiTypeIndex(const string type)
  {
   for(int i=0;i<EEA_AI_TYPES;i++) if(EEA_AiType(i)==type) return i;
   return -1;
  }

struct EEA_AiReport
  {
   bool   present;
   string request_id;
   string provider;
   long   created_at_utc;
   long   valid_until_utc;
   string status;
   string error;
   int    line_count;
   string lines[EEA_AI_LINES];
  };

struct EEA_AiClient
  {
   bool   enabled;
   string root;
   int    max_calls_per_day;
   long   day_local;                  // yyyymmdd of the operator's local day
   int    calls_today;
   int    failures;
   long   circuit_until_utc;
   long   last_news_review_day;
   long   last_diag_day;
   int    pending_count;
   string pending_id[EEA_AI_MAX_PENDING];
   string pending_type[EEA_AI_MAX_PENDING];
   string pending_provider[EEA_AI_MAX_PENDING];
   string pending_actions[EEA_AI_MAX_PENDING];
   long   pending_deadline[EEA_AI_MAX_PENDING];
   EEA_AiReport reports[EEA_AI_TYPES];
   long   bridge_seen_utc;
   string bridge_version;
   string last_reason;
  };

string EEA_AiField(const string json,const string name)
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
   int brace=StringFind(json,"}",start);
   if(end<0 || (brace>=0 && brace<end)) end=brace;
   return end<0 ? "" : StringSubstr(json,start,end-start);
  }

// Items of a flat JSON string array: "name":["a","b"] (the bridge removes quotes from items).
int EEA_AiStringArray(const string json,const string name,string &items[],const int max_items)
  {
   ArrayResize(items,0);
   string key="\""+name+"\":[";
   int at=StringFind(json,key);
   if(at<0) return 0;
   int start=at+StringLen(key);
   int end=StringFind(json,"]",start);
   if(end<0) return 0;
   string body=StringSubstr(json,start,end-start);
   int n=0;
   int pos=0;
   while(n<max_items)
     {
      int q1=StringFind(body,"\"",pos);
      if(q1<0) break;
      int q2=StringFind(body,"\"",q1+1);
      if(q2<0) break;
      ArrayResize(items,n+1);
      items[n++]=StringSubstr(body,q1+1,q2-q1-1);
      pos=q2+1;
     }
   return n;
  }

bool EEA_AiReadText(const string path,string &text)
  {
   text="";
   int h=FileOpen(path,FILE_READ|FILE_BIN|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) return false;
   ulong size=FileSize(h);
   if(size==0 || size>131072) { FileClose(h); return false; }
   uchar bytes[];
   ArrayResize(bytes,(int)size);
   uint read=FileReadArray(h,bytes,0,(int)size);
   FileClose(h);
   if(read!=(uint)size) return false;
   text=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   return true;
  }

string EEA_AiStatePath(const EEA_AiClient &c) { return c.root+"/ai/client_state.json"; }

void EEA_AiSaveState(const EEA_AiClient &c)
  {
   string json="{\"document_version\":\"ai-client-v1.0.0\",\"day_local\":"+IntegerToString(c.day_local)+
      ",\"calls_today\":"+IntegerToString(c.calls_today)+",\"failures\":"+IntegerToString(c.failures)+
      ",\"circuit_until_utc\":"+IntegerToString(c.circuit_until_utc)+
      ",\"last_news_review_day\":"+IntegerToString(c.last_news_review_day)+
      ",\"last_diag_day\":"+IntegerToString(c.last_diag_day)+"}";
   EEA_WriteAtomicText(EEA_AiStatePath(c),json);
  }

bool EEA_AiParseReport(const string json,EEA_AiReport &r)
  {
   r.present=true;
   r.request_id=EEA_AiField(json,"request_id");
   r.provider=EEA_AiField(json,"provider");
   r.created_at_utc=StringToInteger(EEA_AiField(json,"created_at_utc"));
   r.valid_until_utc=StringToInteger(EEA_AiField(json,"valid_until_utc"));
   r.status=EEA_AiField(json,"status");
   r.error=EEA_AiField(json,"error");
   string lines[];
   r.line_count=EEA_AiStringArray(json,"display_lines",lines,EEA_AI_LINES);
   for(int i=0;i<EEA_AI_LINES;i++) r.lines[i]=(i<r.line_count ? lines[i] : "");
   return r.request_id!="";
  }

// Restores counters and the latest report of each type after the EA is re-attached.
void EEA_AiClientInit(EEA_AiClient &c,const string root,const bool enabled,const int max_calls_per_day)
  {
   c.enabled=enabled; c.root=root; c.max_calls_per_day=max_calls_per_day; c.day_local=0; c.calls_today=0;
   c.failures=0; c.circuit_until_utc=0; c.last_news_review_day=0; c.last_diag_day=0; c.pending_count=0;
   c.bridge_seen_utc=0; c.bridge_version=""; c.last_reason=enabled ? "AI_CLIENT_READY" : "AI_DISABLED";
   string json;
   if(EEA_AiReadText(EEA_AiStatePath(c),json))
     {
      c.day_local=StringToInteger(EEA_AiField(json,"day_local"));
      c.calls_today=(int)StringToInteger(EEA_AiField(json,"calls_today"));
      c.failures=(int)StringToInteger(EEA_AiField(json,"failures"));
      c.circuit_until_utc=StringToInteger(EEA_AiField(json,"circuit_until_utc"));
      c.last_news_review_day=StringToInteger(EEA_AiField(json,"last_news_review_day"));
      c.last_diag_day=StringToInteger(EEA_AiField(json,"last_diag_day"));
     }
   for(int i=0;i<EEA_AI_TYPES;i++)
     {
      c.reports[i].present=false; c.reports[i].line_count=0;
      if(EEA_AiReadText(c.root+"/ai/reports/"+EEA_AiType(i)+".json",json)) EEA_AiParseReport(json,c.reports[i]);
     }
  }

bool EEA_AiAudit(CAuditLog &audit,const string event_type,const string request_id,const string request_type,
                 const string reason,const string quality)
  {
   EEAEvent event;
   EEAEvent_Init(event,event_type,TimeGMT(),"",request_id,"",request_type,quality);
   if(reason!="") EEAEvent_AddReason(event,reason);
   return audit.Append(event,"EA_AI_BRIDGE");
  }

bool EEA_AiCircuitOpen(const EEA_AiClient &c) { return c.circuit_until_utc>(long)TimeGMT(); }

bool EEA_AiBridgeOnline(const EEA_AiClient &c)
  { return c.bridge_seen_utc>0 && (long)TimeGMT()-c.bridge_seen_utc<=EEA_AI_HEARTBEAT_STALE; }

bool EEA_AiHasPending(const EEA_AiClient &c,const string type)
  {
   for(int i=0;i<c.pending_count;i++) if(c.pending_type[i]==type) return true;
   return false;
  }

// Queues one request. Context must be a JSON object built only from allowlisted fields.
bool EEA_AiEnqueue(EEA_AiClient &c,CAuditLog &audit,const string type,const string provider,
                   const string allowed_actions_json,const string context_json,string &reason)
  {
   if(!c.enabled) { reason="AI_DISABLED"; return false; }
   if(EEA_AiTypeIndex(type)<0) { reason="AI_REQUEST_TYPE_INVALID"; return false; }
   if(EEA_AiCircuitOpen(c)) { reason="AI_CIRCUIT_OPEN"; return false; }
   if(c.calls_today>=c.max_calls_per_day) { reason="AI_DAILY_LIMIT_REACHED"; return false; }
   if(c.pending_count>=EEA_AI_MAX_PENDING || EEA_AiHasPending(c,type)) { reason="AI_REQUEST_ALREADY_PENDING"; return false; }
   if(StringLen(context_json)>45000) { reason="AI_CONTEXT_TOO_LARGE"; return false; }
   const long now=(long)TimeGMT();
   string id="eea-"+IntegerToString(EEA_AiTypeIndex(type))+"-"+IntegerToString(now)+"-"+IntegerToString(MathRand());
   string json="{\"schema_version\":\"1.0\",\"request_id\":\""+id+"\",\"request_type\":\""+type+
      "\",\"created_at_utc\":"+IntegerToString(now)+",\"deadline_utc\":"+IntegerToString(now+EEA_AI_DEADLINE_SECONDS)+
      ",\"provider\":\""+provider+"\",\"language\":\"vi\",\"allowed_actions\":"+allowed_actions_json+
      ",\"context\":"+context_json+"}";
   if(!EEA_WriteAtomicText(c.root+"/ai/requests/"+id+".json",json)) { reason="AI_REQUEST_WRITE_FAILED"; return false; }
   int k=c.pending_count++;
   c.pending_id[k]=id; c.pending_type[k]=type; c.pending_provider[k]=provider;
   c.pending_actions[k]=allowed_actions_json; c.pending_deadline[k]=now+EEA_AI_DEADLINE_SECONDS;
   c.calls_today++;
   EEA_AiSaveState(c);
   EEA_AiAudit(audit,"AI_REQUEST_QUEUED",id,type,"","OK");
   reason="AI_REQUEST_QUEUED";
   return true;
  }

void EEA_AiRemovePending(EEA_AiClient &c,const int k)
  {
   for(int i=k;i<c.pending_count-1;i++)
     {
      c.pending_id[i]=c.pending_id[i+1]; c.pending_type[i]=c.pending_type[i+1];
      c.pending_provider[i]=c.pending_provider[i+1]; c.pending_actions[i]=c.pending_actions[i+1];
      c.pending_deadline[i]=c.pending_deadline[i+1];
     }
   c.pending_count--;
  }

void EEA_AiFailure(EEA_AiClient &c,CAuditLog &audit,const string id,const string type,const string reason)
  {
   c.failures++;
   c.last_reason=reason;
   EEA_AiAudit(audit,"AI_RESPONSE_REJECTED",id,type,reason,"DEGRADED");
   if(c.failures>=EEA_AI_CIRCUIT_FAILURES)
     {
      c.circuit_until_utc=(long)TimeGMT()+EEA_AI_CIRCUIT_SECONDS;
      c.failures=0;
      EEA_AiAudit(audit,"AI_CIRCUIT_OPEN","","",reason,"DEGRADED");
     }
   EEA_AiSaveState(c);
  }

// Re-validates an answer against its pending request (TC-AI-02/04).
string EEA_AiValidate(const string json,const string id,const string type,const string provider,const string allowed_json)
  {
   if(EEA_AiField(json,"schema_version")!="1.0") return "AI_RESPONSE_SCHEMA_INVALID";
   if(EEA_AiField(json,"request_id")!=id) return "AI_RESPONSE_ID_MISMATCH";
   if(EEA_AiField(json,"request_type")!=type) return "AI_RESPONSE_TYPE_MISMATCH";
   if(EEA_AiField(json,"provider")!=provider) return "AI_PROVIDER_MISMATCH";
   string status=EEA_AiField(json,"status");
   if(status=="ERROR") { string e=EEA_AiField(json,"error"); return e=="" ? "AI_BRIDGE_ERROR" : e; }
   if(status!="OK") return "AI_RESPONSE_STATUS_INVALID";
   if(StringToInteger(EEA_AiField(json,"valid_until_utc"))<=(long)TimeGMT()) return "AI_RESPONSE_EXPIRED";
   string actions[];
   int n=EEA_AiStringArray(json,"actions",actions,16);
   for(int i=0;i<n;i++)
      if(StringFind(allowed_json,"\""+actions[i]+"\"")<0) return "AI_ACTION_NOT_ALLOWED";
   return "";
  }

// Timer: heartbeat, answers, deadlines. Never blocks: only reads files that already exist.
void EEA_AiPoll(EEA_AiClient &c,CAuditLog &audit)
  {
   if(!c.enabled) return;
   string json;
   if(EEA_AiReadText(c.root+"/ai/bridge_heartbeat.json",json))
     {
      c.bridge_seen_utc=StringToInteger(EEA_AiField(json,"at_utc"));
      c.bridge_version=EEA_AiField(json,"version");
     }
   const long now=(long)TimeGMT();
   for(int k=c.pending_count-1;k>=0;k--)
     {
      string id=c.pending_id[k], type=c.pending_type[k];
      string path=c.root+"/ai/responses/"+id+".json";
      if(FileIsExist(path,0) && EEA_AiReadText(path,json))
        {
         string reason=EEA_AiValidate(json,id,type,c.pending_provider[k],c.pending_actions[k]);
         int t=EEA_AiTypeIndex(type);
         if(reason=="")
           {
            EEA_WriteAtomicText(c.root+"/ai/reports/"+type+".json",json);
            EEA_WriteAtomicAppendText(c.root+"/logs/ai_recommendations.jsonl",json+"\r\n");   // REQ-012 record
            if(t>=0) EEA_AiParseReport(json,c.reports[t]);
            c.failures=0;
            c.last_reason="AI_RESPONSE_ACCEPTED";
            EEA_AiAudit(audit,"AI_RESPONSE_ACCEPTED",id,type,"","OK");
            EEA_AiSaveState(c);
           }
         else
           {
            if(t>=0)
              {
               c.reports[t].present=true; c.reports[t].request_id=id; c.reports[t].status="ERROR";
               c.reports[t].error=reason; c.reports[t].created_at_utc=now; c.reports[t].line_count=0;
              }
            EEA_AiFailure(c,audit,id,type,reason);
           }
         FileDelete(path);
         EEA_AiRemovePending(c,k);
         continue;
        }
      if(now>c.pending_deadline[k])
        {
         EEA_AiFailure(c,audit,id,type,EEA_AiBridgeOnline(c) ? "AI_REQUEST_TIMEOUT" : "AI_BRIDGE_OFFLINE");
         EEA_AiRemovePending(c,k);
        }
     }
  }

// Operator's local day as yyyymmdd and minutes since local midnight.
void EEA_AiLocalClock(const long local_offset_seconds,long &day,int &minute_of_day)
  {
   MqlDateTime d;
   TimeToStruct((datetime)((long)TimeGMT()+local_offset_seconds),d);
   day=(long)d.year*10000+d.mon*100+d.day;
   minute_of_day=d.hour*60+d.min;
  }

void EEA_AiRollDay(EEA_AiClient &c,const long day)
  {
   if(c.day_local==day) return;
   c.day_local=day; c.calls_today=0;
   EEA_AiSaveState(c);
  }

#endif
