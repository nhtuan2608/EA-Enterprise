// Live sources for the G91 News Guard and sentiment arrays of the including tester EA (S07Tester, XauRegimeTester,
// CtxBoxTester). In the Strategy Tester the EA keeps its CSV files (S07Tester_news.csv / S07Tester_sentiment.csv);
// on a live chart the files stop at the day they were made, so:
//   news      : HIGH events of the tracked currencies from the MT5 economic calendar, re-read every 15 minutes
//               (calendar times are trade-server times, like TimeCurrent and the CSV);
//   sentiment : one row per closed H1 bar from the broker's own pairs, the formula of research/long/g91_tester_inputs.py
//               (Market/Sentiment.mqh for gold, SWING): USD strength over the FX pairs, the JPY/CHF/gold/S&P risk blend,
//               and the share of USD pairs moving against a buy / a sell.
// Needs, declared before the include: InpNewsIgnoreKeywords, InpSentimentNewsHours, NewsIgnored(), the g_news_* and
// g_sent_* arrays. Saved as UTF-8 with BOM so the Vietnamese text compiles as Unicode.

#define LF_NEWS_REFRESH 900

string g_lf_news_src="file CSV";      // panel: where the news list comes from
string g_lf_sent_src="file CSV";      // panel: where the sentiment rows come from
long   g_lf_news_last=0;
long   g_lf_sent_bar=0;
string g_lf_fx[11]={"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY"};
string g_lf_fx_broker[11];
string g_lf_index="";
bool   g_lf_resolved=false;

bool LfLive() { return !MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION); }

// Sentiment acts only within InpSentimentNewsHours of a HIGH event of the news list (before or after it).
bool LfNearHighNews(const long now)
  {
   const long w=(long)InpSentimentNewsHours*3600;
   int lo=0, hi=g_news_n;
   while(lo<hi) { const int mid=(lo+hi)/2; if(g_news_t[mid]<now-w) lo=mid+1; else hi=mid; }
   return lo<g_news_n && g_news_t[lo]<=now+w;
  }

bool LfTracked(const string c)
  { return c=="USD" || c=="EUR" || c=="GBP" || c=="JPY" || c=="AUD" || c=="NZD" || c=="CAD" || c=="CHF" || c=="CNY"; }

void LfNewsRefresh(const bool force)
  {
   const long now=(long)TimeCurrent();
   if(!force && now-g_lf_news_last<LF_NEWS_REFRESH) return;
   g_lf_news_last=now;
   MqlCalendarValue v[];
   ResetLastError();
   const int n=CalendarValueHistory(v,(datetime)(now-86400),(datetime)(now+7*86400));
   if(n<0) { g_lf_news_src=StringFormat("lịch MT5 LỖI %d (giữ danh sách cũ)",GetLastError()); return; }
   long t[]; string cur[]; int sec[];
   int k=0;
   for(int i=0;i<n;i++)
     {
      MqlCalendarEvent e;
      if(!CalendarEventById(v[i].event_id,e) || e.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry c;
      if(!CalendarCountryById(e.country_id,c) || !LfTracked(c.currency) || NewsIgnored(e.name)) continue;
      ArrayResize(t,k+1,64); ArrayResize(cur,k+1,64); ArrayResize(sec,k+1,64);
      t[k]=(long)v[i].time; cur[k]=c.currency; sec[k]=(int)e.sector;
      for(int j=k;j>0 && t[j]<t[j-1];j--)          // keep the list sorted by time
        {
         const long tt=t[j]; t[j]=t[j-1]; t[j-1]=tt;
         const string cc=cur[j]; cur[j]=cur[j-1]; cur[j-1]=cc;
         const int ss=sec[j]; sec[j]=sec[j-1]; sec[j-1]=ss;
        }
      k++;
     }
   ArrayResize(g_news_t,k); ArrayResize(g_news_cur,k); ArrayResize(g_news_sec,k);
   for(int i=0;i<k;i++) { g_news_t[i]=t[i]; g_news_cur[i]=cur[i]; g_news_sec[i]=sec[i]; }
   g_news_n=k;
   g_news_loaded=true;
   g_lf_news_src=StringFormat("lịch MT5, %d tin HIGH từ hôm qua tới 7 ngày tới, đọc lúc %s",k,TimeToString((datetime)now,TIME_MINUTES));
  }

// Broker name of a canonical symbol: the exact name, else canonical + a short suffix (prefer the traded one's suffix).
string LfResolve(const string canonical)
  {
   if(SymbolInfoInteger(canonical,SYMBOL_EXIST)) return canonical;
   const string suffix=(StringFind(_Symbol,"XAUUSD")==0 ? StringSubstr(_Symbol,6) : "");
   if(suffix!="" && SymbolInfoInteger(canonical+suffix,SYMBOL_EXIST)) return canonical+suffix;
   const int total=SymbolsTotal(false);
   for(int i=0;i<total;i++)
     {
      const string s=SymbolName(i,false);
      if(StringFind(s,canonical)==0 && StringLen(s)<=StringLen(canonical)+5) return s;
     }
   return "";
  }

void LfResolveAll()
  {
   for(int i=0;i<11;i++) { g_lf_fx_broker[i]=LfResolve(g_lf_fx[i]); if(g_lf_fx_broker[i]!="") SymbolSelect(g_lf_fx_broker[i],true); }
   string idx[3]={"US500","SPX500","SP500"};
   g_lf_index="";
   for(int i=0;i<3 && g_lf_index=="";i++) g_lf_index=LfResolve(idx[i]);
   if(g_lf_index!="") SymbolSelect(g_lf_index,true);
   g_lf_resolved=true;
  }

// EEA_SentMeasure: moves over 4 and 24 closed H1 bars in ATR14 units; false when missing or older than 6 h vs `at`.
bool LfMeasure(const string sym,const long at,double &z4,double &z24)
  {
   if(sym=="") return false;
   MqlRates r[];
   ArraySetAsSeries(r,false);
   if(CopyRates(sym,PERIOD_H1,1,40,r)<40) return false;
   if(at-(long)r[39].time>6*3600) return false;
   double tr=0.0;
   for(int i=26;i<40;i++) tr+=MathMax(r[i].high,r[i-1].close)-MathMin(r[i].low,r[i-1].close);
   const double atr=tr/14.0;
   if(atr<=0.0) return false;
   z4=(r[39].close-r[35].close)/(atr*2.0);
   z24=(r[39].close-r[15].close)/(atr*MathSqrt(24.0));
   return true;
  }

int LfCcy(const string c)
  {
   string all[8]={"USD","EUR","GBP","JPY","AUD","CAD","CHF","NZD"};
   for(int i=0;i<8;i++) if(all[i]==c) return i;
   return -1;
  }

// One sentiment row for the last closed H1 bar of the chart symbol (gold), appended to g_sent_*.
void LfSentimentRefresh()
  {
   const long at=(long)iTime(_Symbol,PERIOD_H1,1);
   if(at==0 || at==g_lf_sent_bar) return;
   if(!g_lf_resolved) LfResolveAll();
   double s4[8], s24[8]; int n[8];
   ArrayInitialize(s4,0.0); ArrayInitialize(s24,0.0); ArrayInitialize(n,0);
   double z4[11], z24[11]; bool ok[11];
   int fx=0;
   for(int i=0;i<11;i++)
     {
      ok[i]=LfMeasure(g_lf_fx_broker[i],at,z4[i],z24[i]);
      if(!ok[i]) continue;
      const int b=LfCcy(StringSubstr(g_lf_fx[i],0,3)), q=LfCcy(StringSubstr(g_lf_fx[i],3,3));
      s4[b]+=z4[i]; s24[b]+=z24[i]; n[b]++;
      s4[q]-=z4[i]; s24[q]-=z24[i]; n[q]++;
      fx++;
     }
   const int k=g_sent_n;
   ArrayResize(g_sent_t,k+1,256); ArrayResize(g_sent_v,k+1,256); ArrayResize(g_sent_ok,k+1,256);
   g_sent_t[k]=at; g_sent_ok[k]=false;
   for(int j=0;j<6;j++) g_sent_v[k][j]=0.0;
   g_sent_n=k+1;
   g_lf_sent_bar=at;
   if(fx<4 || n[0]<3)
     { g_lf_sent_src=StringFormat("tính trực tiếp: chỉ đọc được %d/11 cặp FX → coi như trung tính",fx); return; }
   for(int c=0;c<8;c++) if(n[c]>0) { s4[c]/=n[c]; s24[c]/=n[c]; }
   double r4=s4[3]+s4[6], r24=s24[3]+s24[6];
   int parts=2;
   double g4, g24, i4, i24;
   if(LfMeasure(_Symbol,at,g4,g24)) { r4+=g4; r24+=g24; parts++; }
   if(LfMeasure(g_lf_index,at,i4,i24)) { r4-=i4; r24-=i24; parts++; }
   g_sent_v[k][0]=-s4[0]+0.5*r4/parts;           // a4 for a gold buy (a sell is the negative)
   g_sent_v[k][1]=-s24[0]+0.5*r24/parts;
   for(int s=0;s<2;s++)
     {
      const int d=(s==0 ? 1 : -1);
      for(int h=0;h<2;h++)
        {
         int total=0, against=0;
         for(int i=0;i<11;i++)
           {
            if(!ok[i] || StringFind(g_lf_fx[i],"USD")<0) continue;
            const double zz=(h==1 ? z24[i] : z4[i]);
            const double support=(StringSubstr(g_lf_fx[i],0,3)=="USD" ? -d*zz : d*zz);
            total++;
            if(support<0.0) against++;
           }
         g_sent_v[k][2+2*s+h]=(total>0 ? (double)against/total : 0.0);
        }
     }
   g_sent_ok[k]=true;
   g_lf_sent_src=StringFormat("tính trực tiếp từ %d/11 cặp FX%s, nến H1 %s",fx,g_lf_index!="" ? " + "+g_lf_index : "",
                              TimeToString((datetime)at,TIME_MINUTES));
  }

// OnInit: on a live chart, replace the CSV contents with the live sources.
void LfInit()
  {
   if(!LfLive()) return;
   g_news_n=0; g_news_loaded=false; g_sent_n=0;
   ArrayResize(g_news_t,0); ArrayResize(g_news_cur,0); ArrayResize(g_news_sec,0);
   ArrayResize(g_sent_t,0); ArrayResize(g_sent_v,0); ArrayResize(g_sent_ok,0);
   g_lf_resolved=false; g_lf_sent_bar=0;
   LfNewsRefresh(true);
   LfSentimentRefresh();
   PrintFormat("%s live sources: news = %s | sentiment = %s",MQLInfoString(MQL_PROGRAM_NAME),g_lf_news_src,g_lf_sent_src);
  }

// OnTick: cheap when nothing is due.
void LfRefresh()
  {
   if(!LfLive()) return;
   LfNewsRefresh(false);
   LfSentimentRefresh();
  }
