#ifndef ENTERPRISE_EA_DXY_LABEL_MQH
#define ENTERPRISE_EA_DXY_LABEL_MQH

#include "SymbolRegistry.mqh"
#include "../Setups/DmiEmaCompression.mqh"

// G76/G77 F3 as a quality label (17/10/2026), never a filter. Research: a gold S07 signal
// whose bar closes within 2 hours after a DXY M30 S07 signal of the opposite direction (DXY
// expands down while gold buys) gave +1.09R per trade on M30 x M30, causal, but only ~10
// trades a year; G76/G77 left it for a separate plan. The EA records the label on every
// XAUUSD S07 / S07S base candidate so live and shadow results can be compared later.
// DXY signals use the S07 base rule on the broker's dollar index (USDX, USDInd) with its own
// H4 EMA200 side, exactly as research/long/g77_dxy_tf.py (g67 signals + block B6).
// Times are broker server times of bar opens; a bar closes at open + 1800.

#define EEA_DXY_TF_SECONDS 1800
#define EEA_DXY_F3_SECONDS 7200
#define EEA_DXY_MAX_SIGNALS 32
#define EEA_DXY_RESOLVE_SECONDS 3600
#define EEA_DXY_HISTORY_BARS 1500       // as the gold S07 scan: EMA200 / Wilder warm-up
#define EEA_DXY_MIN_BARS 400
#define EEA_DXY_H4_BARS 1200

struct EEA_DxyLabelState
  {
   string   broker;                       // "" until resolved
   long     resolved_at_utc;
   datetime last_bar;                     // open time of the last DXY M30 bar scanned
   int      count;
   long     signal_close[EEA_DXY_MAX_SIGNALS];   // server close time of each recent DXY signal
   int      signal_dir[EEA_DXY_MAX_SIGNALS];
   string   reason;
  };

EEA_DxyLabelState g_dxy_label;

void EEA_DxyLabelInit(EEA_DxyLabelState &s)
  {
   s.broker=""; s.resolved_at_utc=0; s.last_bar=0; s.count=0; s.reason="DXY_NOT_RESOLVED";
  }

// The broker's dollar index through the DXY aliases (USDX, USDInd); retried hourly when absent.
bool EEA_DxyLabelResolve(EEA_DxyLabelState &s)
  {
   if(s.broker!="") return true;
   const long now=(long)TimeGMT();
   if(s.resolved_at_utc>0 && now-s.resolved_at_utc<EEA_DXY_RESOLVE_SECONDS) return false;
   s.resolved_at_utc=now;
   const int total=SymbolsTotal(false);
   EEA_SymbolDiscoveryCandidate candidates[];
   ArrayResize(candidates,total);
   for(int i=0;i<total;i++)
     {
      candidates[i].name=SymbolName(i,false);
      candidates[i].tradeable=true;          // context only: a disabled index still has prices
      candidates[i].conversion_only=false;
     }
   string list[1]={"DXY"};
   EEA_SymbolDiscoveryResult results[];
   EEA_ResolveSymbolsBatch(list,candidates,results);
   if(ArraySize(results)<1 || !results[0].resolved) { s.reason="DXY_NOT_ON_BROKER"; return false; }
   s.broker=results[0].broker_symbol;
   SymbolSelect(s.broker,true);
   s.reason="DXY_RESOLVED";
   return true;
  }

// Rescans the DXY M30 bars once per new closed bar and keeps the signals of the last 8 hours.
bool EEA_DxyLabelRefresh(EEA_DxyLabelState &s)
  {
   if(!EEA_DxyLabelResolve(s)) return false;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   const int copied=CopyRates(s.broker,PERIOD_M30,1,EEA_DXY_HISTORY_BARS,rates);
   if(copied<EEA_DXY_MIN_BARS) { s.reason="DXY_BARS_UNAVAILABLE"; return false; }
   const int last=copied-1;
   if(rates[last].time<=s.last_bar) return true;
   MqlRates h4[];
   ArraySetAsSeries(h4,false);
   const int h4_count=CopyRates(s.broker,PERIOD_H4,1,EEA_DXY_H4_BARS,h4);
   if(h4_count<2*EEA_S07_H4_EMA) { s.reason="DXY_H4_BARS_UNAVAILABLE"; return false; }
   double h4_ema[],e21[],e55[],e100[],e200[],pdi[],mdi[],adx[],atr[];
   EEA_S07Ema(h4,h4_count,EEA_S07_H4_EMA,h4_ema);
   EEA_S07Ema(rates,copied,21,e21); EEA_S07Ema(rates,copied,55,e55);
   EEA_S07Ema(rates,copied,100,e100); EEA_S07Ema(rates,copied,200,e200);
   EEA_S07Dmi(rates,copied,pdi,mdi,adx,atr);
   const int window=EEA_S07WindowBars("M30");
   const long horizon=(long)rates[last].time+EEA_DXY_TF_SECONDS-4*EEA_DXY_F3_SECONDS;
   s.count=0;
   int h=0;
   for(int b=window+1;b<=last;b++)
     {
      const long close=(long)rates[b].time+EEA_DXY_TF_SECONDS;
      if(close<=horizon) continue;
      const long bucket=(long)rates[b].time-((long)rates[b].time%14400);
      while(h+1<h4_count && (long)h4[h+1].time<bucket) h++;
      const bool h4_ok=((long)h4[h].time<bucket && h>=EEA_S07_H4_EMA);
      const int h4_side=!h4_ok ? 0 : (h4[h].close>h4_ema[h] ? 1 : (h4[h].close<h4_ema[h] ? -1 : 0));
      const int d=EEA_S07SignalAt(rates,b,window,e21,e55,e100,e200,pdi,mdi,adx,h4_side);
      if(d==0 || s.count>=EEA_DXY_MAX_SIGNALS) continue;
      s.signal_close[s.count]=close; s.signal_dir[s.count]=d; s.count++;
     }
   s.last_bar=rates[last].time;
   s.reason="DXY_SCANNED";
   return true;
  }

// "YES": a DXY S07 signal opposite to `direction` closed in (gold close - 2h, gold close];
// "NO": none; "NA": not an XAUUSD S07 / S07S M30 base candidate; "UNKNOWN": DXY unavailable.
string EEA_DxyF3Label(EEA_DxyLabelState &s,const string canonical,const string setup,const string timeframe,
                      const int direction,const long gold_bar_open)
  {
   if(canonical!="XAUUSD" || (setup!="S07" && setup!="S07S") || timeframe!="M30" ||
      (direction!=1 && direction!=-1) || gold_bar_open<=0) return "NA";
   if(!EEA_DxyLabelRefresh(s)) return "UNKNOWN";
   const long tc=gold_bar_open+EEA_DXY_TF_SECONDS;
   if(tc>(long)s.last_bar+EEA_DXY_TF_SECONDS) return "UNKNOWN";   // DXY bar of that close not in yet
   for(int i=0;i<s.count;i++)
      if(s.signal_dir[i]==-direction && s.signal_close[i]>tc-EEA_DXY_F3_SECONDS && s.signal_close[i]<=tc)
         return "YES";
   return "NO";
  }

string EEA_DxyF3Json(EEA_DxyLabelState &s,const string canonical,const string setup,const string timeframe,
                     const int direction,const long gold_bar_open)
  {
   const string label=EEA_DxyF3Label(s,canonical,setup,timeframe,direction,gold_bar_open);
   return "\"dxy_f3\":\""+label+"\",\"dxy_symbol\":\""+EEA_JsonEscape(s.broker)+"\"";
  }

#endif
