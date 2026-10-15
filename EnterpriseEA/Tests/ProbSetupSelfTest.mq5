#property script_show_inputs
#property strict
#property description "ProbSetupEA self-test: unit checks of the G114 decision math, then the C1 / C2 signals, factors, X1 results and decisions on the terminal's closed bars, written to MQL5\\Files\\ProbSetupSelfTest.csv for Tests/prob_setup_parity.py. Sends no orders."

#include "../ProbSetup/ProbSignals.mqh"
#include "../ProbSetup/ProbTables.mqh"

input int InpBars = 6000;   // closed bars of the trading timeframe

int g_fail=0;

void Check(const bool ok,const string what)
  {
   if(!ok) { g_fail++; Print("SELFTEST FAIL: ",what); }
  }

void UnitChecks()
  {
   Check(MathAbs(PsWilsonLower(0.5,100)-0.41888)<1e-4,"wilson(0.5,100)");
   Check(PsWilsonLower(0.4,0)==0.0,"wilson n=0");
   Check(PsWilsonLower(0.5,20)<PsWilsonLower(0.5,200),"wilson shrinks with n");
   Check(MathAbs(PsEvLower(0.4,2.0,1.0)-0.2)<1e-12,"ev");
   Check(PsKelly(-0.1,2.0)==0.0,"kelly negative");
   Check(MathAbs(PsKelly(0.2,2.0)-0.025)<1e-12,"kelly");
   Check(PsKelly(50.0,1.0)==1.0,"kelly cap");
   PsBlock b[3];
   b[0].fam=9; b[0].lo=1.0; b[0].p=0.0; b[0].n=1;
   b[1].fam=9; b[1].lo=2.0; b[1].p=0.5; b[1].n=2;
   b[2].fam=9; b[2].lo=4.0; b[2].p=1.0; b[2].n=3;
   double p=0,n=0;
   Check(PsCalibrate(9,b,0.0,p,n) && p==0.0 && n==1,"calibrate below the first block");
   Check(PsCalibrate(9,b,2.5,p,n) && p==0.5 && n==2,"calibrate inside");
   Check(PsCalibrate(9,b,4.0,p,n) && p==1.0 && n==3,"calibrate on a block start");
   Check(!PsCalibrate(7,b,1.0,p,n),"calibrate unknown family");
   Check(PsBand(25.0,20.0,30.0)==1 && PsBand(30.0,20.0,30.0)==2 && PsBand(PsNan(),20.0,30.0)==-1,"band");
  }

void OnStart()
  {
   UnitChecks();
   const ENUM_TIMEFRAMES tf=(PS_TF_MIN==15 ? PERIOD_M15 : (PS_TF_MIN==30 ? PERIOD_M30 : PERIOD_M5));
   MqlRates rt[], h1[], h4[], d1[];
   ArraySetAsSeries(rt,false); ArraySetAsSeries(h1,false); ArraySetAsSeries(h4,false); ArraySetAsSeries(d1,false);
   const int n=CopyRates(_Symbol,tf,1,InpBars,rt);
   const int n1=CopyRates(_Symbol,PERIOD_H1,1,3000,h1);
   const int n4=CopyRates(_Symbol,PERIOD_H4,1,1500,h4);
   const int nd=CopyRates(_Symbol,PERIOD_D1,1,400,d1);
   if(n<1000 || n1<200 || n4<400 || nd<60) { Print("SELFTEST: not enough history"); return; }
   PsSig sig[];
   const int ns=PsSignals(rt,n,h1,n1,h4,n4,d1,nd,PS_TF_MIN*60,0,_Point,sig);
   const int h=FileOpen("ProbSetupSelfTest.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) { Print("SELFTEST: cannot write the csv"); return; }
   FileWrite(h,"#window",_Symbol,(long)rt[0].time,(long)rt[n-1].time,(long)h1[0].time,(long)h1[n1-1].time,
             (long)h4[0].time,(long)h4[n4-1].time,(long)d1[0].time,(long)d1[nd-1].time,_Point,g_fail);
   FileWrite(h,"j","time","fam","d","entry","stop","risk","a30","side","sess","d1","h4","adx","vol","div","pos",
             "closed","R","bars","score","p","n","p_lo","ev_lo","kelly","ok");
   int lv[8];
   for(int i=0;i<ns;i++)
     {
      for(int k=0;k<8;k++) lv[k]=sig[i].f[k];
      PsDecision dec; dec.ok=false; dec.score=0; dec.p=0; dec.n=0; dec.p_lo=0; dec.ev_lo=0; dec.size=0;
      for(int q=0;q<ArraySize(PS_FAMS);q++) if(PS_FAMS[q].id==sig[i].fam) dec=PsDecide(PS_FAMS[q],PS_LR,PS_BLOCKS,lv,PS_NFACTORS);
      FileWrite(h,sig[i].j,(long)sig[i].time,sig[i].fam,sig[i].d,DoubleToString(sig[i].entry,8),DoubleToString(sig[i].stop,8),
                DoubleToString(sig[i].risk,8),DoubleToString(sig[i].a30,8),
                sig[i].f[0],sig[i].f[1],sig[i].f[2],sig[i].f[3],sig[i].f[4],sig[i].f[5],sig[i].f[6],sig[i].f[7],
                (int)sig[i].closed,DoubleToString(sig[i].R,8),sig[i].bars,DoubleToString(dec.score,10),DoubleToString(dec.p,10),
                DoubleToString(dec.n,1),DoubleToString(dec.p_lo,10),DoubleToString(dec.ev_lo,10),DoubleToString(dec.size,10),(int)dec.ok);
     }
   FileClose(h);
   PrintFormat("SELFTEST %s: %d unit failures, %d signals -> MQL5\\Files\\ProbSetupSelfTest.csv",g_fail==0 ? "OK" : "FAILED",g_fail,ns);
  }
