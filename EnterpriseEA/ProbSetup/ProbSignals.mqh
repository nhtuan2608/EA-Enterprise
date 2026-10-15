#ifndef ENTERPRISE_EA_PROB_SIGNALS_MQH
#define ENTERPRISE_EA_PROB_SIGNALS_MQH

// G112 chase signals C1 / C2 on closed bars of the trading timeframe, their stop / filters, the X1 result and the
// G114 factors. Line-for-line the same rules as Tests/prob_setup_oracle.py (checked against the research tables
// research/long/data/g112_chase_XAUUSD_m15.pkl by Tests/prob_setup_oracle_tests.py):
//   C1 impulse      the last 6 bars moved >= 1.0 ATR14 M30 one way and the close makes a new 24-bar high / low
//   C2 day extreme  from 10:00 server, the close goes beyond the day's high / low so far
//   one signal per type, direction and 30-minute bucket; entry at the next bar open (ask for buys), same day,
//   entry hour 01:00-22:59; stop = latest confirmed fractal (2/2) swing on the other side -/+ spread, at least
//   0.5 ATR M30 away (else 0.5 ATR), skipped beyond 3 ATR, below 8 spreads, or when ATR14 of the bars < 3 spreads
//   X1: stop first, then 2R; at most 48 bars, then the close (ask for sells)
// All arrays are oldest first (index 0 = oldest closed bar).

#define PS_IMP_BARS 6
#define PS_IMP_ATR 1.0
#define PS_NEWX_BARS 24
#define PS_MAX_BARS 48
#define PS_MIN_STOP_ATR 0.5
#define PS_MAX_STOP_ATR 3.0
#define PS_MIN_STOP_SPREADS 8.0
#define PS_MIN_ATR_SPREADS 3.0
#define PS_VOL_DAYS 20
#define PS_VOL_MIN 10
#define PS_F_SIDE 0
#define PS_F_SESS 1
#define PS_F_D1 2
#define PS_F_H4 3
#define PS_F_ADX 4
#define PS_F_VOL 5
#define PS_F_DIV 6
#define PS_F_POS 7

struct PsSig
  {
   int      j;            // signal bar (closed)
   datetime time;         // its open time
   int      fam;          // 1 = C1, 2 = C2
   int      d;
   double   entry, stop, risk, a30;
   int      f[8];
   bool     closed;       // X1 finished within the loaded bars
   double   R;            // X1 result (or the running R at the last bar when not closed)
   int      bars;
   int      exit_j;
  };

double PsNan() { return MathArcsin(2.0); }
bool   PsOk(const double v) { return MathIsValidNumber(v); }
int    PsSign(const double v) { return (v>0.0) ? 1 : ((v<0.0) ? -1 : 0); }
int    PsSession(const int hour) { return hour<10 ? 0 : (hour<15 ? 1 : 2); }

int PsBand(const double x,const double lo,const double hi)
  {
   if(!PsOk(x)) return -1;
   return (x>=lo ? 1 : 0)+(x>=hi ? 1 : 0);
  }

void PsWilderTr(const double &h[],const double &l[],const double &c[],const int n,double &out[])
  {
   ArrayResize(out,n);
   double v=0.0;
   for(int i=0;i<n;i++)
     {
      const double pc=(i>0 ? c[i-1] : c[0]);
      const double tr=MathMax(h[i],pc)-MathMin(l[i],pc);
      v=(i==0 ? tr : v+(tr-v)/14.0);
      out[i]=v;
     }
  }

void PsEmaArr(const double &x[],const int n,const int p,double &out[])
  {
   ArrayResize(out,n);
   const double k=2.0/(p+1.0);
   double v=0.0;
   for(int i=0;i<n;i++) { v=(i==0 ? x[0] : v+k*(x[i]-v)); out[i]=v; }
  }

void PsAdx(const MqlRates &r[],const int n,double &out[])
  {
   ArrayResize(out,n);
   const double a=1.0/14.0;
   double ts=0,ps=0,ms=0,ad=0;
   for(int i=0;i<n;i++)
     {
      const double pc=(i>0 ? r[i-1].close : r[0].close);
      const double tr=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-pc),MathAbs(r[i].low-pc)));
      const double up=(i>0 ? r[i].high-r[i-1].high : 0.0);
      const double dn=(i>0 ? r[i-1].low-r[i].low : 0.0);
      const double pdm=((up>dn && up>0.0) ? up : 0.0);
      const double mdm=((dn>up && dn>0.0) ? dn : 0.0);
      if(i==0) { ts=tr; ps=pdm; ms=mdm; }
      else { ts+=a*(tr-ts); ps+=a*(pdm-ps); ms+=a*(mdm-ms); }
      const double P=(ts>0 ? 100.0*ps/ts : 0.0), M=(ts>0 ? 100.0*ms/ts : 0.0);
      const double dx=(P+M>1e-9 ? 100.0*MathAbs(P-M)/(P+M) : 0.0);
      ad=(i==0 ? dx : ad+a*(dx-ad));
      out[i]=ad;
     }
  }

// index of the last bar with time + sec <= at (-1 if none)
int PsLastClosed(const MqlRates &r[],const int n,const long sec,const long at)
  {
   int lo=0, hi=n;
   while(lo<hi) { const int m=(lo+hi)/2; if((long)r[m].time+sec<=at) lo=m+1; else hi=m; }
   return lo-1;
  }

// tick volume / median of the same time of day over the previous 20 occurrences (at least 10), else NaN
void PsRelVolume(const MqlRates &r[],const int n,double &rv[])
  {
   ArrayResize(rv,n);
   long   keys[]; ArrayResize(keys,0);
   double hist[][PS_VOL_DAYS]; ArrayResize(hist,0);
   int    cnt[];  ArrayResize(cnt,0);
   for(int i=0;i<n;i++)
     {
      const long key=(long)r[i].time%86400;
      int s=-1;
      for(int q=0;q<ArraySize(keys);q++) if(keys[q]==key) { s=q; break; }
      if(s<0)
        {
         s=ArraySize(keys);
         ArrayResize(keys,s+1); ArrayResize(hist,s+1); ArrayResize(cnt,s+1);
         keys[s]=key; cnt[s]=0;
        }
      const int m=MathMin(cnt[s],PS_VOL_DAYS);
      if(m>=PS_VOL_MIN)
        {
         double tmp[]; ArrayResize(tmp,m);
         for(int q=0;q<m;q++) tmp[q]=hist[s][q];
         ArraySort(tmp);
         const double med=(m%2==1 ? tmp[m/2] : 0.5*(tmp[m/2-1]+tmp[m/2]));
         rv[i]=(med>0.0 ? (double)r[i].tick_volume/med : PsNan());
        }
      else rv[i]=PsNan();
      // ring of the last 20 values (order does not matter for the median)
      hist[s][cnt[s]%PS_VOL_DAYS]=(double)r[i].tick_volume;
      cnt[s]++;
     }
  }

// latest swing low / high confirmed by each bar (fractal 2/2: strict on the left, weak on the right)
void PsSwings(const MqlRates &r[],const int n,double &lo_at[],double &hi_at[])
  {
   ArrayResize(lo_at,n); ArrayResize(hi_at,n);
   double cl=PsNan(), ch=PsNan();
   for(int i=0;i<n;i++)
     {
      const int j=i-2;
      if(j>=2)
        {
         if(r[j].low<r[j-1].low && r[j].low<r[j-2].low && r[j].low<=r[j+1].low && r[j].low<=r[j+2].low) cl=r[j].low;
         if(r[j].high>r[j-1].high && r[j].high>r[j-2].high && r[j].high>=r[j+1].high && r[j].high>=r[j+2].high) ch=r[j].high;
        }
      lo_at[i]=cl; hi_at[i]=ch;
     }
  }

double PsSp(const MqlRates &x,const double point) { return x.spread*point; }

// X1 from the entry bar e; closed=false when the 48 bars are not all loaded yet (R = at the last loaded close)
void PsSimulateX1(PsSig &s,const MqlRates &r[],const int n,const int e,const double point)
  {
   const double tgt=s.entry+s.d*2.0*s.risk;
   const int last=MathMin(n,e+PS_MAX_BARS)-1;
   for(int k=e;k<=last;k++)
     {
      const double sp=PsSp(r[k],point);
      if((s.d==1 && r[k].low<=s.stop) || (s.d==-1 && r[k].high+sp>=s.stop))
        { s.R=s.d*(s.stop-s.entry)/s.risk; s.bars=k-e+1; s.exit_j=k; s.closed=true; return; }
      if((s.d==1 && r[k].high>=tgt) || (s.d==-1 && r[k].low+sp<=tgt))
        { s.R=2.0; s.bars=k-e+1; s.exit_j=k; s.closed=true; return; }
     }
   const double px=(s.d==1 ? r[last].close : r[last].close+PsSp(r[last],point));
   s.R=s.d*(px-s.entry)/s.risk; s.bars=last-e+1; s.exit_j=last;
   s.closed=(e+PS_MAX_BARS-1<=n-1);
  }

// Signals with j >= start whose entry bar j + 1 is loaded (live: pass the bar that just opened as the last row,
// it is only used for the entry price). Returns the count.
int PsSignals(const MqlRates &r[],const int n,const MqlRates &h1[],const int n1,const MqlRates &h4[],const int n4,
              const MqlRates &d1[],const int nd,const long tf_sec,const int start,const double point,PsSig &out[])
  {
   ArrayResize(out,0);
   if(n<PS_NEWX_BARS+42) return 0;
   double h[], l[], c[];
   ArrayResize(h,n); ArrayResize(l,n); ArrayResize(c,n);
   for(int i=0;i<n;i++) { h[i]=r[i].high; l[i]=r[i].low; c[i]=r[i].close; }
   double atr_tf[]; PsWilderTr(h,l,c,n,atr_tf);
   // M30 buckets of the trading-timeframe bars
   MqlRates m30[]; ArrayResize(m30,0); int n30=0;
   for(int i=0;i<n;i++)
     {
      const datetime b=(datetime)((long)r[i].time/1800*1800);
      if(n30>0 && m30[n30-1].time==b)
        { m30[n30-1].high=MathMax(m30[n30-1].high,h[i]); m30[n30-1].low=MathMin(m30[n30-1].low,l[i]); m30[n30-1].close=c[i]; }
      else
        { ArrayResize(m30,n30+1); m30[n30].time=b; m30[n30].open=r[i].open; m30[n30].high=h[i]; m30[n30].low=l[i]; m30[n30].close=c[i]; n30++; }
     }
   double mh[], ml[], mc[]; ArrayResize(mh,n30); ArrayResize(ml,n30); ArrayResize(mc,n30);
   for(int i=0;i<n30;i++) { mh[i]=m30[i].high; ml[i]=m30[i].low; mc[i]=m30[i].close; }
   double atr30[]; PsWilderTr(mh,ml,mc,n30,atr30);
   double a_h1[]; PsAdx(h1,n1,a_h1);
   double c4[]; ArrayResize(c4,n4); for(int i=0;i<n4;i++) c4[i]=h4[i].close;
   double e4[]; PsEmaArr(c4,n4,200,e4);
   double cd[]; ArrayResize(cd,nd); for(int i=0;i<nd;i++) cd[i]=d1[i].close;
   double e50[]; PsEmaArr(cd,nd,50,e50);
   double rv[]; PsRelVolume(r,n,rv);
   double clv[]; ArrayResize(clv,n);
   for(int i=0;i<n;i++) clv[i]=(h[i]>l[i] ? ((c[i]-l[i])-(h[i]-c[i]))/(h[i]-l[i]) : 0.0);
   double sw_lo[], sw_hi[]; PsSwings(r,n,sw_lo,sw_hi);
   // first bar of each day
   int first[]; ArrayResize(first,n);
   for(int i=0;i<n;i++) first[i]=(i>0 && (long)r[i].time/86400==(long)r[i-1].time/86400) ? first[i-1] : i;
   long seen[]; ArrayResize(seen,0);
   int cnt=0;
   for(int j=MathMax(start,PS_NEWX_BARS+40);j<n-1;j++)
     {
      const int e=j+1;
      const long dj=(long)r[j].time/86400;
      const int he=(int)(((long)r[e].time%86400)/3600), hj=(int)(((long)r[j].time%86400)/3600);
      if((long)r[e].time/86400!=dj || he>=23 || he<1) continue;
      const int k30=PsLastClosed(m30,n30,1800,(long)r[j].time+tf_sec);
      if(k30<0) continue;
      const double a30=atr30[k30];
      const int a=first[j];
      int ctyp[2], cdir[2], nc=0;
      const double mv=c[j]-c[j-PS_IMP_BARS];
      if(MathAbs(mv)>=PS_IMP_ATR*a30)
        {
         const int s=(mv>0 ? 1 : -1);
         double ext=(s==1 ? h[j-PS_NEWX_BARS] : l[j-PS_NEWX_BARS]);
         for(int q=j-PS_NEWX_BARS;q<j;q++) ext=(s==1 ? MathMax(ext,h[q]) : MathMin(ext,l[q]));
         if((s==1 && c[j]>ext) || (s==-1 && c[j]<ext)) { ctyp[nc]=1; cdir[nc]=s; nc++; }
        }
      if(hj>=10 && j>a)
        {
         double dh=h[a], dl=l[a];
         for(int q=a;q<j;q++) { dh=MathMax(dh,h[q]); dl=MathMin(dl,l[q]); }
         if(c[j]>dh) { ctyp[nc]=2; cdir[nc]=1; nc++; }
         else if(c[j]<dl) { ctyp[nc]=2; cdir[nc]=-1; nc++; }
        }
      for(int q=0;q<nc;q++)
        {
         const int s=cdir[q];
         const long key=((long)r[j].time/1800)*8+ctyp[q]*2+(s==1 ? 1 : 0);
         bool dup=false;
         for(int z=0;z<ArraySize(seen);z++) if(seen[z]==key) { dup=true; break; }
         if(dup) continue;
         const int ns=ArraySize(seen); ArrayResize(seen,ns+1); seen[ns]=key;
         const double spj=PsSp(r[j],point), spe=PsSp(r[e],point);
         const double entry=r[e].open+(s==1 ? spe : 0.0);
         const double sw=(s==1 ? sw_lo[j] : sw_hi[j]);
         double stop=(s==1 ? sw-spj : sw+spj);
         if(!PsOk(sw) || s*(entry-stop)<PS_MIN_STOP_ATR*a30) stop=entry-s*PS_MIN_STOP_ATR*a30;
         const double risk=s*(entry-stop);
         if(risk>PS_MAX_STOP_ATR*a30 || risk<PS_MIN_STOP_SPREADS*spe || atr_tf[j]<PS_MIN_ATR_SPREADS*spe) continue;
         // factors (bars <= j)
         const int k1=PsLastClosed(h1,n1,3600,(long)r[j].time+tf_sec);
         const int k4=PsLastClosed(h4,n4,14400,(long)r[j].time+tf_sec);
         const int kd=PsLastClosed(d1,nd,86400,(long)r[a].time);
         int reg=0;
         if(kd>=10)
           {
            const int sd=PsSign(d1[kd].close-e50[kd]), sl=PsSign(e50[kd]-e50[kd-10]);
            reg=(sd==sl ? sd : 0);
           }
         const int h4s=(k4<0 ? 0 : PsSign(c[j]-e4[k4]));
         double rsum=0; int rn=0;
         for(int z=j-5;z<=j;z++) if(PsOk(rv[z])) { rsum+=rv[z]; rn++; }
         double num=0, den=0;
         for(int z=j-11;z<=j;z++) { const double w=(PsOk(rv[z]) ? rv[z] : 0.0); num+=clv[z]*w; den+=w; }
         int div=-1;
         if(den>0) div=(PsSign((c[j]-c[j-12])*s)!=PsSign(num/den*s)) ? 1 : 0;
         double dh=h[a], dl=l[a];
         for(int z=a;z<=j;z++) { dh=MathMax(dh,h[z]); dl=MathMin(dl,l[z]); }
         const double pos=(c[j]-dl)/MathMax(dh-dl,1e-12);
         PsSig sg;
         sg.j=j; sg.time=r[j].time; sg.fam=ctyp[q]; sg.d=s; sg.entry=entry; sg.stop=stop; sg.risk=risk; sg.a30=a30;
         sg.f[PS_F_SIDE]=s; sg.f[PS_F_SESS]=PsSession(hj); sg.f[PS_F_D1]=s*reg; sg.f[PS_F_H4]=s*h4s;
         sg.f[PS_F_ADX]=PsBand(k1>=0 ? a_h1[k1] : PsNan(),20.0,30.0);
         sg.f[PS_F_VOL]=PsBand(rn>0 ? rsum/rn : PsNan(),0.9,1.3);
         sg.f[PS_F_DIV]=div; sg.f[PS_F_POS]=PsBand(pos,0.33,0.67);
         sg.closed=false; sg.R=0; sg.bars=0; sg.exit_j=-1;
         PsSimulateX1(sg,r,n,e,point);
         ArrayResize(out,cnt+1); out[cnt]=sg; cnt++;
        }
     }
   return cnt;
  }

#endif
