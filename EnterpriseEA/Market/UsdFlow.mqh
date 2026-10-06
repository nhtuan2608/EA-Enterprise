#ifndef ENTERPRISE_EA_USD_FLOW_MQH
#define ENTERPRISE_EA_USD_FLOW_MQH

#include "../Runtime/ObserverRuntime.mqh"

// G29 (research G27, research/long/filters.py usd_index): USD flow at the last closed H1 bar.
// The index is the mean of -ln EURUSD, -ln GBPUSD and +ln USDJPY closes, on the bars present in
// all three, against its EMA50: +1 USD stronger than its average, -1 weaker, 0 unknown.
// S06B with the USD flow kept +0.32/+0.30/+0.39 R per trade (2010-16/17-20/21-25) against
// +0.24/+0.31/+0.29 without it. The EA logs the flag on every candidate; S06B LIVE requires it
// (InpS06BRequireUsdFlow).

#define EEA_USD_FLOW_EMA 50
#define EEA_USD_FLOW_BARS 400

struct EEA_UsdFlowState
  {
   datetime bar_time;   // H1 bar (server time) the flow belongs to
   int      flow;       // +1, -1, 0 unknown
   double   value;
   double   ema;
   string   reason;
  };

EEA_UsdFlowState g_usd_flow;
bool g_s06b_require_usd_flow=true;

void EEA_UsdFlowInit(EEA_UsdFlowState &s)
  {
   s.bar_time=0; s.flow=0; s.value=0.0; s.ema=0.0; s.reason="NOT_COMPUTED";
  }

// +1 when a long position buys the USD (USDJPY), -1 when it sells it, 0 when not a USD pair.
int EEA_UsdFlowSymbolSign(const string canonical)
  {
   if(canonical=="USDJPY") return 1;
   if(canonical=="EURUSD" || canonical=="GBPUSD" || canonical=="XAUUSD" || canonical=="BTCUSD") return -1;
   return 0;
  }

// +1 the trade goes with the USD flow, -1 against it, 0 unknown.
int EEA_UsdFlowAlignment(const EEA_UsdFlowState &s,const string canonical,const int direction)
  {
   const int sign=EEA_UsdFlowSymbolSign(canonical);
   if(s.flow==0 || sign==0 || direction==0) return 0;
   return (direction*sign==s.flow) ? 1 : -1;
  }

string EEA_UsdFlowAlignmentName(const int alignment)
  {
   return alignment>0 ? "ALIGNED" : (alignment<0 ? "COUNTER" : "UNKNOWN");
  }

bool EEA_UsdFlowFail(EEA_UsdFlowState &s,const string reason)
  {
   s.flow=0; s.reason=reason;
   return false;
  }

bool EEA_UsdFlowUpdate(EEA_UsdFlowState &s,const string eur,const string gbp,const string jpy)
  {
   if(eur=="" || gbp=="" || jpy=="") return EEA_UsdFlowFail(s,"USD_FLOW_SYMBOLS_MISSING");
   const datetime last=iTime(eur,PERIOD_H1,1);
   if(last<=0) return EEA_UsdFlowFail(s,"USD_FLOW_HISTORY_UNAVAILABLE");
   if(last==s.bar_time && s.flow!=0) return true;
   MqlRates a[], b[], c[];
   const int na=CopyRates(eur,PERIOD_H1,1,EEA_USD_FLOW_BARS,a);
   const int nb=CopyRates(gbp,PERIOD_H1,1,EEA_USD_FLOW_BARS,b);
   const int nc=CopyRates(jpy,PERIOD_H1,1,EEA_USD_FLOW_BARS,c);
   if(na<=0 || nb<=0 || nc<=0) return EEA_UsdFlowFail(s,"USD_FLOW_HISTORY_UNAVAILABLE");
   const double k=2.0/(EEA_USD_FLOW_EMA+1);
   double ema=0.0, v=0.0;
   datetime t=0;
   int used=0, jb=0, jc=0;
   for(int ia=0;ia<na;ia++)
     {
      const datetime ta=a[ia].time;
      while(jb<nb && b[jb].time<ta) jb++;
      while(jc<nc && c[jc].time<ta) jc++;
      if(jb>=nb || jc>=nc) break;
      if(b[jb].time!=ta || c[jc].time!=ta) continue;
      if(a[ia].close<=0.0 || b[jb].close<=0.0 || c[jc].close<=0.0) continue;
      v=(-MathLog(a[ia].close)-MathLog(b[jb].close)+MathLog(c[jc].close))/3.0;
      ema=(used==0 ? v : ema+k*(v-ema));
      t=ta;
      used++;
     }
   if(used<2*EEA_USD_FLOW_EMA) return EEA_UsdFlowFail(s,"USD_FLOW_HISTORY_SHORT");
   s.bar_time=t; s.value=v; s.ema=ema; s.flow=(v>ema ? 1 : -1); s.reason="OK";
   return true;
  }

bool EEA_UsdFlowUpdateFromObserver(EEA_UsdFlowState &s,const EEA_ObserverRuntimeContext &observer)
  {
   string names[3]={"EURUSD","GBPUSD","USDJPY"};
   string brokers[3];
   for(int i=0;i<3;i++)
     {
      const int row=EEA_ObserverRuntimeIndexOf(observer,names[i]);
      brokers[i]=(row>=0 && row<ArraySize(observer.broker_symbols)) ? observer.broker_symbols[row] : "";
     }
   return EEA_UsdFlowUpdate(s,brokers[0],brokers[1],brokers[2]);
  }

// Fields for the shadow log and the candidate ledger.
string EEA_UsdFlowJson(const EEA_UsdFlowState &s,const string canonical,const int direction)
  {
   return "\"usd_flow\":"+IntegerToString(s.flow)+",\"usd_bar\":"+IntegerToString((long)s.bar_time)+
          ",\"usd_alignment\":\""+EEA_UsdFlowAlignmentName(EEA_UsdFlowAlignment(s,canonical,direction))+"\"";
  }

#endif
