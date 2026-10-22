#ifndef ENTERPRISE_EA_NEWS_STATE_MQH
#define ENTERPRISE_EA_NEWS_STATE_MQH

// News Guard state machine (master specification 7.4; design 2026-10-04 market
// information and News Guard, decisions D1-D5). Pure: the caller supplies the HIGH
// impact events in UTC, the symbol's currencies, the clock and whether the market has
// normalized after an event. No calendar, broker or file access here.
//
//   [T-swing_block, T-scalp_block)  PRE_NEWS        SWING blocked, SCALP allowed
//   [T-scalp_block, T)              PRE_NEWS_BLOCK  all new entries blocked
//   [T, T+active)                   ACTIVE          blocked
//   [T+active, T+post)              POST_NEWS       blocked
//   [T+post, T+max_normalize)       NORMALIZING     blocked until the market is stable
//   otherwise                       NORMAL
// A calendar that cannot be read is UNKNOWN, never NORMAL.

#define EEA_NEWS_MAX_EVENTS 256

struct EEA_NewsEvent
  {
   long   time_utc;
   string currency;
   string name;
   int    sector;                   // ENUM_CALENDAR_EVENT_SECTOR
   string actual;
   string forecast;
   string previous;
  };

struct EEA_NewsConfig
  {
   bool   enabled;
   int    scalp_block_before_min;   // D1: 60
   int    swing_block_before_min;   // D1: 180
   int    active_min;
   int    post_min;
   int    max_normalize_min;
   int    be_before_min;            // D2: 15
   double be_min_r;                 // D2: 0.3
   bool   allow_when_unknown;       // D3: false = block
   string ignore_keywords;          // comma list matched against event names; empty = keep every HIGH event
   double indirect_scalp_factor;    // yellow: SCALP risk multiplier (0.5)
  };

void EEA_NewsConfigDefaults(EEA_NewsConfig &c)
  {
   c.enabled=true; c.scalp_block_before_min=60; c.swing_block_before_min=180; c.active_min=5;
   c.post_min=15; c.max_normalize_min=60; c.be_before_min=15; c.be_min_r=0.3; c.allow_when_unknown=false;
   c.ignore_keywords="";
   c.indirect_scalp_factor=0.5;
  }

bool EEA_NewsConfigValid(const EEA_NewsConfig &c)
  {
   return c.scalp_block_before_min>=0 && c.swing_block_before_min>=c.scalp_block_before_min &&
          c.active_min>0 && c.post_min>=c.active_min && c.max_normalize_min>=c.post_min &&
          c.be_before_min>=0 && c.be_min_r>=0.0;
  }

// True when the event name contains one of the operator's ignore keywords (case-insensitive).
// The default list is empty: every HIGH impact event counts.
bool EEA_NewsEventIgnored(const string name,const string keywords)
  {
   if(keywords=="") return false;
   string lowered=name;
   StringToLower(lowered);
   string parts[];
   int n=StringSplit(keywords,',',parts);
   for(int i=0;i<n;i++)
     {
      string key=parts[i];
      StringTrimLeft(key); StringTrimRight(key); StringToLower(key);
      if(key!="" && StringFind(lowered,key)>=0) return true;
     }
   return false;
  }

// Indirect impact (yellow): a HIGH event of another major currency in a sector that moves
// that currency's strength (rates, inflation, labour, growth) still moves USD pairs and gold
// through the dollar. Direct impact (red) is the symbol's own currency.
bool EEA_NewsStrengthSector(const int sector)
  {
   return sector==CALENDAR_SECTOR_MONEY || sector==CALENDAR_SECTOR_PRICES ||
          sector==CALENDAR_SECTOR_JOBS || sector==CALENDAR_SECTOR_GDP;
  }

bool EEA_NewsIndirectAffects(const string currencies,const string event_currency,const int sector)
  {
   return currencies!="" && event_currency!="" && EEA_NewsCurrencyTracked(event_currency) &&
          !EEA_NewsAffects(currencies,event_currency) && EEA_NewsStrengthSector(sector);
  }

// Yellow policy (user decision 04/10/2026): around an indirect event SWING takes no new
// entry from T-swing_block until T+post, SCALP enters with risk x indirect_scalp_factor from
// T-scalp_block until T+post. Pending orders are not cancelled and no break-even is forced.
void EEA_NewsIndirectWindow(const EEA_NewsEvent &events[],const int count,const string currencies,const long now,
                            const EEA_NewsConfig &c,bool &swing_blocked,bool &scalp_reduced,string &label)
  {
   swing_blocked=false; scalp_reduced=false; label="";
   if(!c.enabled) return;
   for(int i=0;i<count;i++)
     {
      if(!EEA_NewsIndirectAffects(currencies,events[i].currency,events[i].sector)) continue;
      const long t=events[i].time_utc;
      bool swing=(now>=t-c.swing_block_before_min*60 && now<t+c.post_min*60);
      bool scalp=(now>=t-c.scalp_block_before_min*60 && now<t+c.post_min*60);
      if(swing && label=="") label=events[i].currency+" "+events[i].name;
      swing_blocked=swing_blocked || swing;
      scalp_reduced=scalp_reduced || scalp;
     }
  }

// Currencies published by the MT5 economic calendar that the guard follows.
bool EEA_NewsCurrencyTracked(const string currency)
  {
   return currency=="USD" || currency=="EUR" || currency=="GBP" || currency=="JPY" || currency=="AUD" ||
          currency=="NZD" || currency=="CAD" || currency=="CHF" || currency=="CNY";
  }

// "EUR,USD" for EURUSD; "USD" for XAUUSD and BTCUSD (metal and crypto have no calendar).
string EEA_NewsSymbolCurrencies(const string base,const string profit)
  {
   string out="";
   if(EEA_NewsCurrencyTracked(base)) out=base;
   if(EEA_NewsCurrencyTracked(profit) && profit!=base) out+=(out=="" ? "" : ",")+profit;
   return out;
  }

bool EEA_NewsAffects(const string currencies,const string currency)
  {
   if(currencies=="" || currency=="") return false;
   string parts[];
   int n=StringSplit(currencies,',',parts);
   for(int i=0;i<n;i++) if(parts[i]==currency) return true;
   return false;
  }

int EEA_NewsStateRank(const string state)
  {
   if(state=="ACTIVE") return 5;
   if(state=="POST_NEWS") return 4;
   if(state=="PRE_NEWS_BLOCK") return 3;
   if(state=="NORMALIZING") return 2;
   if(state=="PRE_NEWS") return 1;
   return 0;
  }

// State of one event for a symbol at `now`. `normalized` means the market was seen
// stable after this event, which ends NORMALIZING early.
string EEA_NewsEventState(const long t,const long now,const EEA_NewsConfig &c,const bool normalized)
  {
   if(now>=t && now<t+c.active_min*60) return "ACTIVE";
   if(now>=t+c.active_min*60 && now<t+c.post_min*60) return "POST_NEWS";
   if(now>=t-c.scalp_block_before_min*60 && now<t) return "PRE_NEWS_BLOCK";
   if(now>=t+c.post_min*60 && now<t+c.max_normalize_min*60 && !normalized) return "NORMALIZING";
   if(now>=t-c.swing_block_before_min*60 && now<t-c.scalp_block_before_min*60) return "PRE_NEWS";
   return "NORMAL";
  }

struct EEA_NewsPhase
  {
   string state;
   long   event_utc;       // event that drives the state (0 when NORMAL)
   string event_label;
   long   next_event_utc;  // first event at or after now (0 when none)
   string next_label;
  };

// Combined state over every event that affects the symbol: the strictest state wins,
// so close events merge into one continuous window. `normalized_event_utc` is the last
// event after which the market was seen stable.
void EEA_NewsEvaluate(const EEA_NewsEvent &events[],const int count,const string currencies,const long now,
                      const EEA_NewsConfig &c,const long normalized_event_utc,EEA_NewsPhase &phase)
  {
   phase.state="NORMAL"; phase.event_utc=0; phase.event_label="";
   phase.next_event_utc=0; phase.next_label="";
   int best=0;
   for(int i=0;i<count;i++)
     {
      if(!EEA_NewsAffects(currencies,events[i].currency)) continue;
      const long t=events[i].time_utc;
      const string label=events[i].currency+" "+events[i].name;
      if(t>=now && (phase.next_event_utc==0 || t<phase.next_event_utc))
        { phase.next_event_utc=t; phase.next_label=label; }
      string state=EEA_NewsEventState(t,now,c,normalized_event_utc>=t);
      int rank=EEA_NewsStateRank(state);
      if(rank>best || (rank==best && rank>0 && t<phase.event_utc))
        { best=rank; phase.state=state; phase.event_utc=t; phase.event_label=label; }
     }
  }

// Entry decision per profile. Empty string = allowed; otherwise the block reason.
string EEA_NewsEntryBlock(const string state,const string profile,const EEA_NewsConfig &c)
  {
   if(!c.enabled || state=="DISABLED") return "";
   if(state=="UNKNOWN") return c.allow_when_unknown ? "" : "NEWS_UNKNOWN";
   if(state=="PRE_NEWS") return profile=="SWING" ? "NEWS_PRE_BLOCK_SWING" : "";
   if(state=="PRE_NEWS_BLOCK") return profile=="SWING" ? "NEWS_PRE_BLOCK_SWING" : "NEWS_PRE_BLOCK_SCALP";
   if(state=="ACTIVE") return "NEWS_ACTIVE";
   if(state=="POST_NEWS") return "NEWS_POST";
   if(state=="NORMALIZING") return "NEWS_NORMALIZING";
   return "";
  }

// Start of the profile's block window for the next event (0 when no event is ahead).
long EEA_NewsBlockStart(const long next_event_utc,const string profile,const EEA_NewsConfig &c)
  {
   if(next_event_utc<=0) return 0;
   return next_event_utc-(profile=="SWING" ? c.swing_block_before_min : c.scalp_block_before_min)*60;
  }

// G152: the top-tier USD releases (NFP, CPI lines, Core PCE, the Fed rate decision and the FOMC press conference).
bool EEA_NewsTopTier(const string name)
  {
   string n=name;
   StringToLower(n);
   return StringFind(n,"nonfarm payrolls")>=0 || StringFind(n,"cpi")>=0 || StringFind(n,"core pce")>=0 ||
          StringFind(n,"fed interest rate decision")>=0 || StringFind(n,"fomc press conference")>=0;
  }

// D2 restricted to the top-tier releases (G152 "V2").
bool EEA_NewsBreakEvenDueTopTier(const EEA_NewsEvent &events[],const int count,const string currencies,
                                 const long now,const EEA_NewsConfig &c)
  {
   if(!c.enabled) return false;
   for(int i=0;i<count;i++)
     {
      if(!EEA_NewsAffects(currencies,events[i].currency) || !EEA_NewsTopTier(events[i].name)) continue;
      const long t=events[i].time_utc;
      if(now>=t-c.be_before_min*60 && now<t+c.post_min*60) return true;
     }
   return false;
  }

// D2: a profitable position is moved to break-even from T-be_before until the event
// has passed its POST_NEWS window.
bool EEA_NewsBreakEvenDue(const EEA_NewsEvent &events[],const int count,const string currencies,
                          const long now,const EEA_NewsConfig &c)
  {
   if(!c.enabled) return false;
   for(int i=0;i<count;i++)
     {
      if(!EEA_NewsAffects(currencies,events[i].currency)) continue;
      const long t=events[i].time_utc;
      if(now>=t-c.be_before_min*60 && now<t+c.post_min*60) return true;
     }
   return false;
  }

#endif
