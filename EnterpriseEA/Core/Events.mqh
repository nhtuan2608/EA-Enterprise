#ifndef ENTERPRISE_EA_EVENTS_MQH
#define ENTERPRISE_EA_EVENTS_MQH

#define EEA_MAX_REASONS 8

struct EEAEvent
  {
   string schema_version;
   string event_id;
   string event_type;
   datetime occurred_at_utc;
   datetime observed_at_utc;
   string symbol;
   string entity_id;
   string state_before;
   string state_after;
   string reason_codes[EEA_MAX_REASONS];
   int reason_count;
   string config_version;
   string data_quality;
   string details_json;
  };

string EEA_NewId()
  {
   static uint sequence=0;
   sequence++;
   uint a=(uint)TimeGMT();
   uint b=(uint)GetTickCount();
   uint c=(uint)MathRand();
   return StringFormat("%08X-%04X-%04X-%04X-%08X%04X",a,(uint)(b&0xFFFF),
                       (uint)(c&0xFFFF),(uint)(sequence&0xFFFF),b,c);
  }

void EEAEvent_Init(EEAEvent &e,const string type,const datetime now,
                   const string symbol,const string entity,
                   const string before,const string after,const string quality)
  {
   e.schema_version=EEA_SCHEMA_VERSION;
   e.event_id=EEA_NewId();
   e.event_type=type;
   e.occurred_at_utc=now;
   e.observed_at_utc=TimeGMT();
   e.symbol=symbol;
   e.entity_id=entity;
   e.state_before=before;
   e.state_after=after;
   e.reason_count=0;
   e.config_version="";
   e.data_quality=quality;
   e.details_json="{}";
  }

void EEAEvent_AddReason(EEAEvent &e,const string reason)
  {
   if(reason=="" || e.reason_count>=EEA_MAX_REASONS) return;
   e.reason_codes[e.reason_count]=reason;
   e.reason_count++;
  }

string EEA_JsonEscape(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort ch=StringGetCharacter(value,i);
      if(ch==34) out+="\\\"";
      else if(ch==92) out+="\\\\";
      else if(ch==10) out+="\\n";
      else if(ch==13) out+="\\r";
      else if(ch==9) out+="\\t";
      else out+=ShortToString(ch);
     }
   return out;
  }

string EEA_IsoUtc(const datetime value)
  {
   MqlDateTime dt;
   TimeToStruct(value,dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",dt.year,dt.mon,dt.day,dt.hour,dt.min,dt.sec);
  }

string EEAEvent_ToJson(const EEAEvent &e,const string source)
  {
   string reasons="[";
   for(int i=0;i<e.reason_count;i++)
     {
      if(i>0) reasons+=",";
      reasons+="\""+EEA_JsonEscape(e.reason_codes[i])+"\"";
     }
   reasons+="]";
   return "{\"schema_version\":\""+EEA_JsonEscape(e.schema_version)+"\",\"event_id\":\""+
      EEA_JsonEscape(e.event_id)+"\",\"event_type\":\""+EEA_JsonEscape(e.event_type)+
      "\",\"occurred_at_utc\":\""+EEA_IsoUtc(e.occurred_at_utc)+"\",\"observed_at_utc\":\""+
      EEA_IsoUtc(e.observed_at_utc)+"\",\"symbol\":\""+EEA_JsonEscape(e.symbol)+
      "\",\"entity_id\":\""+EEA_JsonEscape(e.entity_id)+"\",\"state_before\":\""+
      EEA_JsonEscape(e.state_before)+"\",\"state_after\":\""+EEA_JsonEscape(e.state_after)+
      "\",\"reason_codes\":"+reasons+",\"config_version\":\""+EEA_JsonEscape(e.config_version)+
      "\",\"data_quality\":\""+EEA_JsonEscape(e.data_quality)+"\",\"source\":\""+
      EEA_JsonEscape(source)+"\",\"details\":"+e.details_json+"}";
  }

#endif
