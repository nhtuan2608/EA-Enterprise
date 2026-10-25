#ifndef ENTERPRISE_EA_COUNCIL_CONTEXT_MQH
#define ENTERPRISE_EA_COUNCIL_CONTEXT_MQH

// AI council step 3b-2 (plan docs/superpowers/plans/2026-10-25-council-3b.md): on every newly closed M30 bar of the bots
// symbol, write current/council/context.json with the last closed bars (1000 M30, 250 H4, 300 D1), bid / ask and the server
// offset. The council (bridge/council_market.py) builds its state card, named situations and anomaly checks from it.
// Read-only market data: nothing here touches orders or the bots.

#include "../Storage/AtomicWriter.mqh"

#define EEA_COUNCIL_CONTEXT_DOCUMENT "council-context-v1"
#define EEA_COUNCIL_M30_BARS 1000
#define EEA_COUNCIL_H4_BARS 250
#define EEA_COUNCIL_D1_BARS 300

bool     g_council_context_enabled=true;      // InpCouncilContext
datetime g_council_context_bar=0;              // M30 bar (closed) of the last write

string EEA_CouncilBars(const string sym,const ENUM_TIMEFRAMES tf,const int count,const bool with_volume,const int digits)
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(sym,tf,1,count,r);
   if(n<=0) return "[]";
   string s="[";
   for(int i=0;i<n;i++)
     {
      s+=(i>0 ? "," : "")+"["+IntegerToString((long)r[i].time)+","+DoubleToString(r[i].open,digits)+","+
         DoubleToString(r[i].high,digits)+","+DoubleToString(r[i].low,digits)+","+DoubleToString(r[i].close,digits);
      if(with_volume) s+=","+IntegerToString((long)r[i].tick_volume)+","+IntegerToString(r[i].spread);
      s+="]";
     }
   return s+"]";
  }

// Called from the timer; writes once per closed M30 bar. Returns true when a file was written.
bool EEA_CouncilContextTimer(const string root,const string symbol)
  {
   if(!g_council_context_enabled || root=="") return false;
   const string sym=(symbol=="" ? _Symbol : symbol);
   const datetime bar=iTime(sym,PERIOD_M30,1);
   if(bar==0 || bar==g_council_context_bar) return false;
   const int digits=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   const string json="{\"document_version\":\""+EEA_COUNCIL_CONTEXT_DOCUMENT+"\",\"symbol\":\""+sym+
      "\",\"written_at_utc\":"+IntegerToString((long)TimeGMT())+",\"server_offset\":"+
      IntegerToString((long)(TimeTradeServer()-TimeGMT()))+",\"point\":"+DoubleToString(SymbolInfoDouble(sym,SYMBOL_POINT),10)+
      ",\"digits\":"+IntegerToString(digits)+",\"bid\":"+DoubleToString(SymbolInfoDouble(sym,SYMBOL_BID),digits)+
      ",\"ask\":"+DoubleToString(SymbolInfoDouble(sym,SYMBOL_ASK),digits)+
      ",\"m30\":"+EEA_CouncilBars(sym,PERIOD_M30,EEA_COUNCIL_M30_BARS,true,digits)+
      ",\"h4\":"+EEA_CouncilBars(sym,PERIOD_H4,EEA_COUNCIL_H4_BARS,false,digits)+
      ",\"d1\":"+EEA_CouncilBars(sym,PERIOD_D1,EEA_COUNCIL_D1_BARS,false,digits)+"}";
   FolderCreate(root+"/current/council",0);
   if(!EEA_WriteAtomicText(root+"/current/council/context.json",json)) return false;
   g_council_context_bar=bar;
   return true;
  }

#endif
