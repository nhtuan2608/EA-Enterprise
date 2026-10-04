#ifndef ENTERPRISE_EA_SENTIMENT_RUNTIME_MQH
#define ENTERPRISE_EA_SENTIMENT_RUNTIME_MQH

// Sentiment runtime: resolves the read-only reference pairs on this broker, measures
// each one on closed H1 bars and recomputes the snapshot once per new H1 bar.

#include "Sentiment.mqh"
#include "SymbolRegistry.mqh"
#include "../Core/Events.mqh"
#include "../Storage/AtomicWriter.mqh"

struct EEA_SentimentRuntime
  {
   bool   resolved;
   long   last_resolve_utc;
   int    count;
   EEA_SentPair pairs[EEA_SENT_MAX_PAIRS];
   string brokers[EEA_SENT_MAX_PAIRS];
   EEA_SentConfig cfg;
   EEA_SentimentSnapshot snap;
  };

void EEA_SentimentRuntimeInit(EEA_SentimentRuntime &rt,const EEA_SentConfig &cfg)
  {
   rt.resolved=false; rt.last_resolve_utc=0; rt.count=0; rt.cfg=cfg;
   EEA_SentimentDefaults(rt.snap);
  }

void EEA_SentAddPair(EEA_SentimentRuntime &rt,const string canonical,const string base,const string quote,
                     const string kind,const string broker)
  {
   if(rt.count>=EEA_SENT_MAX_PAIRS || broker=="") return;
   int i=rt.count++;
   rt.pairs[i].canonical=canonical; rt.pairs[i].base=base; rt.pairs[i].quote=quote; rt.pairs[i].kind=kind;
   rt.pairs[i].ok=false; rt.pairs[i].z4=0.0; rt.pairs[i].z24=0.0;
   rt.brokers[i]=broker;
   SymbolSelect(broker,true);   // read-only reference: Market Watch needs it for history
  }

// M5: FX majors and crosses, gold, BTC and the first US equity index the broker has.
void EEA_SentimentResolve(EEA_SentimentRuntime &rt)
  {
   rt.count=0;
   rt.last_resolve_utc=(long)TimeGMT();
   string fx[11]={"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY"};
   string other[2]={"XAUUSD","BTCUSD"};
   string index[7]={"US500","SPX500","SP500","NAS100","USTEC","US30","DJ30"};
   string canonicals[20];
   int n=0;
   for(int i=0;i<11;i++) canonicals[n++]=fx[i];
   for(int i=0;i<2;i++) canonicals[n++]=other[i];
   for(int i=0;i<7;i++) canonicals[n++]=index[i];
   int total=SymbolsTotal(false);
   EEA_SymbolDiscoveryCandidate candidates[];
   ArrayResize(candidates,total);
   for(int i=0;i<total;i++)
     {
      string name=SymbolName(i,false);
      candidates[i].name=name;
      candidates[i].tradeable=(SymbolInfoInteger(name,SYMBOL_TRADE_MODE)!=SYMBOL_TRADE_MODE_DISABLED);
      candidates[i].conversion_only=false;
     }
   string list[];
   ArrayResize(list,n);
   for(int i=0;i<n;i++) list[i]=canonicals[i];
   EEA_SymbolDiscoveryResult results[];
   EEA_ResolveSymbolsBatch(list,candidates,results);
   for(int i=0;i<11;i++)
      if(results[i].resolved)
         EEA_SentAddPair(rt,fx[i],StringSubstr(fx[i],0,3),StringSubstr(fx[i],3,3),"FX",results[i].broker_symbol);
   if(results[11].resolved) EEA_SentAddPair(rt,"XAUUSD","XAU","USD","GOLD",results[11].broker_symbol);
   if(results[12].resolved) EEA_SentAddPair(rt,"BTCUSD","BTC","USD","BTC",results[12].broker_symbol);
   for(int i=13;i<n;i++)
      if(results[i].resolved) { EEA_SentAddPair(rt,canonicals[i],"","","INDEX",results[i].broker_symbol); break; }
   rt.resolved=true;
  }

bool EEA_SentMeasure(const string broker,double &z4,double &z24,long &last_bar)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(broker,PERIOD_H1,1,40,rates);
   if(copied<40) return false;
   double tr=0.0;
   for(int i=copied-14;i<copied;i++)
      tr+=MathMax(rates[i].high,rates[i-1].close)-MathMin(rates[i].low,rates[i-1].close);
   double atr=tr/14.0;
   if(atr<=0.0) return false;
   double c0=rates[copied-1].close;
   z4=(c0-rates[copied-5].close)/(atr*2.0);
   z24=(c0-rates[copied-25].close)/(atr*MathSqrt(24.0));
   last_bar=(long)rates[copied-1].time;
   return true;
  }

// Recomputes when a new H1 bar has closed (or when nothing is measured yet).
void EEA_SentimentUpdate(EEA_SentimentRuntime &rt,const string root)
  {
   if(!rt.cfg.enabled) { rt.snap.ok=false; rt.snap.reason="SENTIMENT_DISABLED"; return; }
   if(!rt.resolved || (long)TimeGMT()-rt.last_resolve_utc>6*3600) EEA_SentimentResolve(rt);
   if(rt.count==0) { rt.snap.ok=false; rt.snap.reason="SENTIMENT_NO_REFERENCE_PAIRS"; return; }
   MqlRates probe[];
   if(CopyRates(rt.brokers[0],PERIOD_H1,1,1,probe)==1 && (long)probe[0].time==rt.snap.bar_time && rt.snap.ok) return;
   long newest=0;
   for(int i=0;i<rt.count;i++)
     {
      long bar=0;
      rt.pairs[i].ok=EEA_SentMeasure(rt.brokers[i],rt.pairs[i].z4,rt.pairs[i].z24,bar);
      newest=MathMax(newest,bar);
     }
   rt.snap.bar_time=newest;
   EEA_SentimentCompute(rt.pairs,rt.count,rt.cfg,rt.snap);
   string json="{\"document_version\":\"sentiment-v1.0.0\",\"ok\":"+(rt.snap.ok ? "true" : "false")+
      ",\"reason\":\""+rt.snap.reason+"\",\"bar_time\":"+IntegerToString(rt.snap.bar_time)+
      ",\"regime\":\""+rt.snap.regime+"\",\"regime4\":"+DoubleToString(rt.snap.regime4,3)+
      ",\"regime24\":"+DoubleToString(rt.snap.regime24,3)+",\"strength\":{";
   for(int c=0;c<EEA_SENT_CCY;c++)
      json+=(c>0 ? "," : "")+"\""+EEA_SentCurrency(c)+"\":{\"h4\":"+DoubleToString(rt.snap.s4[c],3)+
            ",\"h24\":"+DoubleToString(rt.snap.s24[c],3)+",\"pairs\":"+IntegerToString(rt.snap.n[c])+"}";
   json+="},\"pairs\":[";
   for(int i=0;i<rt.count;i++)
      json+=(i>0 ? "," : "")+"{\"symbol\":\""+rt.pairs[i].canonical+"\",\"broker\":\""+rt.brokers[i]+"\",\"ok\":"+
            (rt.pairs[i].ok ? "true" : "false")+",\"z4\":"+DoubleToString(rt.pairs[i].z4,3)+
            ",\"z24\":"+DoubleToString(rt.pairs[i].z24,3)+"}";
   json+="]}";
   EEA_WriteAtomicText(root+"/current/sentiment.json",json);
  }

// Base, quote and kind of a traded canonical symbol for the alignment score.
void EEA_SentSymbolShape(const string canonical,string &base,string &quote,string &kind)
  {
   base=StringSubstr(canonical,0,3); quote=StringSubstr(canonical,3,3);
   kind=(base=="XAU" ? "GOLD" : (base=="BTC" ? "BTC" : "FX"));
  }

void EEA_SentimentAlignFor(const EEA_SentimentRuntime &rt,const string canonical,const int direction,
                           const string profile,EEA_SentAlignment &a)
  {
   string base,quote,kind;
   EEA_SentSymbolShape(canonical,base,quote,kind);
   EEA_SentAlign(rt.snap,rt.pairs,rt.count,rt.cfg,canonical,base,quote,kind,direction,profile,a);
  }

#endif
