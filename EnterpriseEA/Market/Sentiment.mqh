#ifndef ENTERPRISE_EA_SENTIMENT_MQH
#define ENTERPRISE_EA_SENTIMENT_MQH

// Market sentiment from price and cross pairs (design 2026-10-04, decisions M1-M6).
// Pure: the caller supplies ATR-normalised moves of each reference pair over 4 and 24
// closed H1 bars. Currency strength is the mean signed move over every FX pair holding
// the currency; the risk regime blends JPY, CHF, gold and an equity index. A trade is
// scored by how the flow agrees with its direction. Sentiment only reduces risk or blocks
// a SWING entry, never raises risk; missing data is neutral (SENTIMENT_UNAVAILABLE).

#define EEA_SENT_CCY 8
#define EEA_SENT_MAX_PAIRS 20

string EEA_SentCurrency(const int i)
  {
   if(i==0) return "USD"; if(i==1) return "EUR"; if(i==2) return "GBP"; if(i==3) return "JPY";
   if(i==4) return "AUD"; if(i==5) return "CAD"; if(i==6) return "CHF"; if(i==7) return "NZD";
   return "";
  }

int EEA_SentCurrencyIndex(const string c)
  {
   for(int i=0;i<EEA_SENT_CCY;i++) if(EEA_SentCurrency(i)==c) return i;
   return -1;
  }

struct EEA_SentPair
  {
   string canonical;
   string base;
   string quote;
   string kind;      // FX | GOLD | BTC | INDEX
   bool   ok;
   double z4;        // move over 4 closed H1 bars / (ATR14(H1) * sqrt(4))
   double z24;       // move over 24 closed H1 bars / (ATR14(H1) * sqrt(24))
  };

struct EEA_SentConfig
  {
   bool   enabled;
   double against_threshold;     // M3: -0.3
   double strong_threshold;      // M3: -0.8
   double strong_consensus;      // M3: 0.70 of the related pairs against
   double against_factor;        // M4: 0.5
   double min_combined_factor;   // M6: 0.25
   double regime_threshold;      // 0.3
  };

void EEA_SentConfigDefaults(EEA_SentConfig &c)
  {
   c.enabled=true; c.against_threshold=-0.3; c.strong_threshold=-0.8; c.strong_consensus=0.7;
   c.against_factor=0.5; c.min_combined_factor=0.25; c.regime_threshold=0.3;
  }

struct EEA_SentimentSnapshot
  {
   bool   ok;
   string reason;
   long   bar_time;               // last closed H1 bar used
   double s4[EEA_SENT_CCY];
   double s24[EEA_SENT_CCY];
   int    n[EEA_SENT_CCY];
   double regime4;
   double regime24;
   string regime;                 // RISK_ON | NEUTRAL | RISK_OFF | UNKNOWN
   int    fx_pairs;
  };

void EEA_SentimentDefaults(EEA_SentimentSnapshot &s)
  {
   s.ok=false; s.reason="SENTIMENT_UNAVAILABLE"; s.bar_time=0; s.regime4=0.0; s.regime24=0.0;
   s.regime="UNKNOWN"; s.fx_pairs=0;
   for(int i=0;i<EEA_SENT_CCY;i++) { s.s4[i]=0.0; s.s24[i]=0.0; s.n[i]=0; }
  }

void EEA_SentimentCompute(const EEA_SentPair &pairs[],const int count,const EEA_SentConfig &cfg,
                          EEA_SentimentSnapshot &s)
  {
   long bar_time=s.bar_time;
   EEA_SentimentDefaults(s);
   s.bar_time=bar_time;
   double gold4=0.0, gold24=0.0, index4=0.0, index24=0.0;
   bool gold=false, index=false;
   for(int p=0;p<count;p++)
     {
      if(!pairs[p].ok) continue;
      if(pairs[p].kind=="GOLD") { gold=true; gold4=pairs[p].z4; gold24=pairs[p].z24; continue; }
      if(pairs[p].kind=="INDEX") { if(!index) { index=true; index4=pairs[p].z4; index24=pairs[p].z24; } continue; }
      if(pairs[p].kind!="FX") continue;
      int b=EEA_SentCurrencyIndex(pairs[p].base), q=EEA_SentCurrencyIndex(pairs[p].quote);
      if(b<0 || q<0) continue;
      s.s4[b]+=pairs[p].z4; s.s24[b]+=pairs[p].z24; s.n[b]++;
      s.s4[q]-=pairs[p].z4; s.s24[q]-=pairs[p].z24; s.n[q]++;
      s.fx_pairs++;
     }
   for(int i=0;i<EEA_SENT_CCY;i++)
      if(s.n[i]>0) { s.s4[i]/=s.n[i]; s.s24[i]/=s.n[i]; }
   if(s.fx_pairs<4 || s.n[0]<3) { s.reason="SENTIMENT_TOO_FEW_PAIRS"; return; }
   // Risk-off: JPY and CHF strong, gold up, equities down.
   double r4=s.s4[3]+s.s4[6], r24=s.s24[3]+s.s24[6]; int parts=2;
   if(gold) { r4+=gold4; r24+=gold24; parts++; }
   if(index) { r4-=index4; r24-=index24; parts++; }
   s.regime4=r4/parts; s.regime24=r24/parts;
   s.regime=s.regime4>=cfg.regime_threshold ? "RISK_OFF" : (s.regime4<=-cfg.regime_threshold ? "RISK_ON" : "NEUTRAL");
   s.ok=true;
   s.reason="SENTIMENT_READY";
  }

struct EEA_SentAlignment
  {
   bool   ok;
   double a4;
   double a24;
   double against4;     // share of related pairs moving against the trade
   double against24;
   string verdict;      // ALIGNED | NEUTRAL | AGAINST | STRONGLY_AGAINST | UNAVAILABLE
   double factor;       // risk multiplier, <= 1
   bool   block;        // SWING only, strongly against
   string reason;
  };

double EEA_SentStrength(const EEA_SentimentSnapshot &s,const string c,const bool h24)
  {
   int i=EEA_SentCurrencyIndex(c);
   if(i<0 || s.n[i]==0) return 0.0;
   return h24 ? s.s24[i] : s.s4[i];
  }

// Share of related FX pairs (holding one of `currencies`, excluding the traded symbol) whose
// move goes against the trade. `sign_base`/`sign_quote`: +1 when that currency strengthening
// supports the trade.
double EEA_SentAgainstShare(const EEA_SentPair &pairs[],const int count,const string exclude,const string c1,
                            const int sign1,const string c2,const int sign2,const bool h24)
  {
   int total=0, against=0;
   for(int p=0;p<count;p++)
     {
      if(!pairs[p].ok || pairs[p].kind!="FX" || pairs[p].canonical==exclude) continue;
      double z=h24 ? pairs[p].z24 : pairs[p].z4;
      double support=0.0;
      if(c1!="" && pairs[p].base==c1) support+=sign1*z;
      if(c1!="" && pairs[p].quote==c1) support-=sign1*z;
      if(c2!="" && pairs[p].base==c2) support+=sign2*z;
      if(c2!="" && pairs[p].quote==c2) support-=sign2*z;
      if((c1=="" || (pairs[p].base!=c1 && pairs[p].quote!=c1)) && (c2=="" || (pairs[p].base!=c2 && pairs[p].quote!=c2))) continue;
      total++;
      if(support<0.0) against++;
     }
   return total>0 ? (double)against/total : 0.0;
  }

// Scores a trade on `symbol` (base/quote/kind) in `direction` (+1 buy, -1 sell) and applies
// the reduce-only policy (M2: both windows must be against; M4: strong -> SWING blocked).
void EEA_SentAlign(const EEA_SentimentSnapshot &s,const EEA_SentPair &pairs[],const int count,const EEA_SentConfig &cfg,
                   const string symbol,const string base,const string quote,const string kind,const int direction,
                   const string profile,EEA_SentAlignment &a)
  {
   a.ok=false; a.a4=0.0; a.a24=0.0; a.against4=0.0; a.against24=0.0; a.verdict="UNAVAILABLE";
   a.factor=1.0; a.block=false; a.reason=s.reason;
   if(!cfg.enabled) { a.reason="SENTIMENT_DISABLED"; return; }
   if(!s.ok || (direction!=1 && direction!=-1)) return;
   if(kind=="GOLD" || kind=="BTC")
     {
      double tilt=(kind=="GOLD" ? 0.5 : -0.5);
      a.a4=direction*(-EEA_SentStrength(s,"USD",false)+tilt*s.regime4);
      a.a24=direction*(-EEA_SentStrength(s,"USD",true)+tilt*s.regime24);
      a.against4=EEA_SentAgainstShare(pairs,count,symbol,"USD",-direction,"",0,false);
      a.against24=EEA_SentAgainstShare(pairs,count,symbol,"USD",-direction,"",0,true);
     }
   else
     {
      a.a4=direction*(EEA_SentStrength(s,base,false)-EEA_SentStrength(s,quote,false));
      a.a24=direction*(EEA_SentStrength(s,base,true)-EEA_SentStrength(s,quote,true));
      a.against4=EEA_SentAgainstShare(pairs,count,symbol,base,direction,quote,-direction,false);
      a.against24=EEA_SentAgainstShare(pairs,count,symbol,base,direction,quote,-direction,true);
     }
   a.ok=true;
   bool against=(a.a4<=cfg.against_threshold && a.a24<=cfg.against_threshold);
   bool strong=(a.a4<=cfg.strong_threshold && a.a24<=cfg.strong_threshold &&
                a.against4>=cfg.strong_consensus && a.against24>=cfg.strong_consensus);
   if(strong)
     {
      a.verdict="STRONGLY_AGAINST";
      a.factor=cfg.against_factor;
      a.block=(profile=="SWING");
      a.reason=a.block ? "SENTIMENT_STRONGLY_AGAINST" : "SENTIMENT_AGAINST_REDUCED";
     }
   else if(against)
     { a.verdict="AGAINST"; a.factor=cfg.against_factor; a.reason="SENTIMENT_AGAINST_REDUCED"; }
   else
     {
      a.verdict=(a.a4>=-cfg.against_threshold && a.a24>=-cfg.against_threshold) ? "ALIGNED" : "NEUTRAL";
      a.reason="SENTIMENT_OK";
     }
  }

#endif
