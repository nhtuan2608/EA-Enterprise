#ifndef ENTERPRISE_EA_BOT_JOURNAL_MQH
#define ENTERPRISE_EA_BOT_JOURNAL_MQH

// Bots host journal: one JSON line per bot event in <data root>/logs/bots-YYYYMM.jsonl (UTC month),
// appended and flushed, read by the Telegram gateway, the AI bridge and the MCP server.
//   {"at_utc":..., "server":"2026.10.16 21:00", "bot":"VHEDGE", "event":"ENTRY", "mode":"LIVE",
//    "text":"...", "data":{...}}
// Events: START (EA start), SWITCH (on/off), DECISION (XRT daily plan, CtxLimit hourly forecast), ENTRY / ORDER
// (bot entry or limit placed, SHADOW included), MANAGE (VHedge leg resolved), EXIT (bot exit, SHADOW in R),
// BLOCKED, SKIP, ERROR, NEAR (each bot on every closed M30 bar), FILL / CLOSE (broker deals of a bot magic, money).
// BLOCKED is written only when the reason changes (a waiting entry is retried every bar).
// Summaries (per day, per bot) are computed by the readers from these lines.

#include "../Storage/AtomicWriter.mqh"
#include "../Core/Events.mqh"
#include "BotState.mqh"

string g_bot_journal_root="";
string g_bot_journal_block[EEA_BOT_COUNT];

string EEA_BotJournalPath(const datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc,t);
   return g_bot_journal_root+"/logs/"+StringFormat("bots-%04d%02d.jsonl",t.year,t.mon);
  }

// extra_json: the inside of the "data" object, e.g. "\"entry\":4100.5,\"sl\":4090.1" ("" = empty).
void EEA_BotLog(const int bot,const string event,const string mode,const string text,const string extra_json="")
  {
   if(g_bot_journal_root=="") return;
   const datetime now=TimeGMT();
   const string line="{\"at_utc\":"+IntegerToString((long)now)+",\"server\":\""+TimeToString(TimeTradeServer(),TIME_DATE|TIME_MINUTES)+
      "\",\"bot\":\""+(bot>=0 ? EEA_BotCode(bot) : "HOST")+"\",\"event\":\""+event+"\",\"mode\":\""+EEA_JsonEscape(mode)+
      "\",\"text\":\""+EEA_JsonEscape(text)+"\",\"data\":{"+extra_json+"}}";
   EEA_WriteAtomicAppendText(EEA_BotJournalPath(now),line+"\n");
  }

// A blocked entry: one line per new reason; the same reason again is not repeated.
void EEA_BotLogBlock(const int bot,const string mode,const string reason,const string text,const string extra_json="")
  {
   if(bot<0 || bot>=EEA_BOT_COUNT) return;
   if(g_bot_journal_block[bot]==reason) return;
   g_bot_journal_block[bot]=reason;
   EEA_BotLog(bot,"BLOCKED",mode,reason+(text!="" ? ": "+text : ""),"\"reason\":\""+EEA_JsonEscape(reason)+"\""+
              (extra_json!="" ? ","+extra_json : ""));
  }

// After an entry (or when nothing waits any more) the next block is news again.
void EEA_BotLogClearBlock(const int bot)
  {
   if(bot>=0 && bot<EEA_BOT_COUNT) g_bot_journal_block[bot]="";
  }

string EEA_BotJsonNum(const string key,const double v,const int digits=5)
  {
   return "\""+key+"\":"+(MathIsValidNumber(v) ? DoubleToString(v,digits) : "null");
  }

#endif
