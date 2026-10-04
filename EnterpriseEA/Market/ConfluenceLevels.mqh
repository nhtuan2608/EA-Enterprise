#ifndef ENTERPRISE_EA_CONFLUENCE_LEVELS_MQH
#define ENTERPRISE_EA_CONFLUENCE_LEVELS_MQH

// S02 v1 Location (design 2026-10-03, sections 4.1-4.2). Pure functions over
// closed bars supplied oldest-first in broker server time; no market access.
// All level sources of one profile are extracted from the same bar resolution
// (H1 for SCALP, H4 for SWING), so two sources produced by the same bar share
// the same bar time and are not counted as independent confluence.

#define EEA_LEVEL_SOURCE_PREV_DAY  "PREV_DAY"
#define EEA_LEVEL_SOURCE_SESSION   "SESSION"
#define EEA_LEVEL_SOURCE_PREV_WEEK "PREV_WEEK"
#define EEA_LEVEL_SOURCE_SWING     "SWING"
#define EEA_LEVEL_MAX_POINTS 64
#define EEA_LEVEL_MAX_ZONES  32

struct EEA_LevelBar
  {
   long   time;   // bar open time, broker server time
   double open;
   double high;
   double low;
   double close;
  };

struct EEA_LevelPoint
  {
   string source;
   string side;      // HIGH or LOW
   double price;
   long   bar_time;  // open time of the bar that printed the extreme
  };

struct EEA_ConfluenceZone
  {
   double low;
   double high;
   int    member_count;
   int    independent_sources;
   string sources;   // e.g. PREV_DAY+SWING
   bool   qualified;
   string reason_code;
  };

bool EEA_LevelAppend(EEA_LevelPoint &points[],int &count,const string source,const string side,
                     const double price,const long bar_time)
  {
   if(count>=EEA_LEVEL_MAX_POINTS || !MathIsValidNumber(price) || price<=0.0 || bar_time<=0) return false;
   if(ArraySize(points)<count+1) ArrayResize(points,count+1);
   points[count].source=source;
   points[count].side=side;
   points[count].price=price;
   points[count].bar_time=bar_time;
   count++;
   return true;
  }

long EEA_LevelDayIndex(const long server_time) { return server_time/86400; }

// Monday 00:00 server time of the week containing server_time (1970-01-01 was a Thursday).
long EEA_LevelWeekStart(const long server_time)
  {
   long day=server_time/86400;
   long weekday=(day+3)%7;
   return (day-weekday)*86400;
  }

// Extreme high and low over bars whose open time lies in [from,to).
bool EEA_LevelRangeExtremes(const EEA_LevelBar &bars[],const int count,const long from,const long to,
                            double &high,long &high_time,double &low,long &low_time)
  {
   bool found=false;
   high=0.0; low=0.0; high_time=0; low_time=0;
   for(int i=0;i<count;i++)
     {
      if(bars[i].time<from || bars[i].time>=to) continue;
      if(!found || bars[i].high>high) { high=bars[i].high; high_time=bars[i].time; }
      if(!found || bars[i].low<low) { low=bars[i].low; low_time=bars[i].time; }
      found=true;
     }
   return found;
  }

// PDH/PDL: previous broker-server day relative to now_server.
int EEA_LevelsPreviousDay(const EEA_LevelBar &bars[],const int count,const long now_server,
                          EEA_LevelPoint &points[],int &point_count)
  {
   long today=EEA_LevelDayIndex(now_server)*86400;
   double high,low; long high_time,low_time;
   if(!EEA_LevelRangeExtremes(bars,count,today-86400,today,high,high_time,low,low_time)) return 0;
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_PREV_DAY,"HIGH",high,high_time);
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_PREV_DAY,"LOW",low,low_time);
   return 2;
  }

// Previous broker-server week (Monday to Monday).
int EEA_LevelsPreviousWeek(const EEA_LevelBar &bars[],const int count,const long now_server,
                           EEA_LevelPoint &points[],int &point_count)
  {
   long week=EEA_LevelWeekStart(now_server);
   double high,low; long high_time,low_time;
   if(!EEA_LevelRangeExtremes(bars,count,week-7*86400,week,high,high_time,low,low_time)) return 0;
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_PREV_WEEK,"HIGH",high,high_time);
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_PREV_WEEK,"LOW",low,low_time);
   return 2;
  }

// Most recent completed occurrence of one UTC session window [start_hour,end_hour).
int EEA_LevelsSession(const EEA_LevelBar &bars[],const int count,const long now_server,
                      const long server_offset_seconds,const int start_hour_utc,const int end_hour_utc,
                      EEA_LevelPoint &points[],int &point_count)
  {
   if(start_hour_utc<0 || end_hour_utc>24 || start_hour_utc>=end_hour_utc) return 0;
   long now_utc=now_server-server_offset_seconds;
   long day_utc=(now_utc/86400)*86400;
   long end_utc=day_utc+end_hour_utc*3600;
   if(end_utc>now_utc) { day_utc-=86400; end_utc-=86400; }
   long start_utc=day_utc+start_hour_utc*3600;
   double high,low; long high_time,low_time;
   if(!EEA_LevelRangeExtremes(bars,count,start_utc+server_offset_seconds,end_utc+server_offset_seconds,
                              high,high_time,low,low_time)) return 0;
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_SESSION,"HIGH",high,high_time);
   EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_SESSION,"LOW",low,low_time);
   return 2;
  }

bool EEA_LevelIsFractalHigh(const EEA_LevelBar &bars[],const int count,const int index,const int wing)
  {
   if(index-wing<0 || index+wing>=count) return false;
   for(int k=1;k<=wing;k++)
      if(bars[index-k].high>=bars[index].high || bars[index+k].high>bars[index].high) return false;
   return true;
  }

bool EEA_LevelIsFractalLow(const EEA_LevelBar &bars[],const int count,const int index,const int wing)
  {
   if(index-wing<0 || index+wing>=count) return false;
   for(int k=1;k<=wing;k++)
      if(bars[index-k].low<=bars[index].low || bars[index+k].low<bars[index].low) return false;
   return true;
  }

// Confirmed fractal swings within the last lookback_bars that no later close has broken.
int EEA_LevelsSwings(const EEA_LevelBar &bars[],const int count,const int wing,const int lookback_bars,
                     EEA_LevelPoint &points[],int &point_count)
  {
   int added=0;
   int first=MathMax(wing,count-lookback_bars);
   for(int i=first;i<count-wing;i++)
     {
      if(EEA_LevelIsFractalHigh(bars,count,i,wing))
        {
         bool broken=false;
         for(int j=i+1;j<count;j++) if(bars[j].close>bars[i].high) { broken=true; break; }
         if(!broken && EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_SWING,"HIGH",bars[i].high,bars[i].time)) added++;
        }
      if(EEA_LevelIsFractalLow(bars,count,i,wing))
        {
         bool broken=false;
         for(int j=i+1;j<count;j++) if(bars[j].close<bars[i].low) { broken=true; break; }
         if(!broken && EEA_LevelAppend(points,point_count,EEA_LEVEL_SOURCE_SWING,"LOW",bars[i].low,bars[i].time)) added++;
        }
     }
   return added;
  }

// Groups levels whose consecutive distance is <= tolerance. A zone qualifies when
// at least min_sources different source types can each be represented by a member
// printed on a different bar, and the zone is no wider than max_width.
int EEA_BuildConfluenceZones(const EEA_LevelPoint &points[],const int count,const double tolerance,
                             const double max_width,const int min_sources,EEA_ConfluenceZone &zones[])
  {
   ArrayResize(zones,0);
   if(count<=0 || !MathIsValidNumber(tolerance) || tolerance<=0.0 || max_width<=0.0) return 0;
   int order[];
   ArrayResize(order,count);
   for(int i=0;i<count;i++) order[i]=i;
   for(int i=1;i<count;i++)
     {
      int key=order[i]; int j=i-1;
      while(j>=0 && points[order[j]].price>points[key].price) { order[j+1]=order[j]; j--; }
      order[j+1]=key;
     }
   int zone_count=0;
   int start=0;
   while(start<count && zone_count<EEA_LEVEL_MAX_ZONES)
     {
      int end=start;
      while(end+1<count && points[order[end+1]].price-points[order[end]].price<=tolerance) end++;
      ArrayResize(zones,zone_count+1);
      zones[zone_count].low=points[order[start]].price;
      zones[zone_count].high=points[order[end]].price;
      zones[zone_count].member_count=end-start+1;
      // Greedy independence: one member per source type, each from a distinct bar.
      string used_sources[]; long used_times[]; int used=0;
      for(int m=start;m<=end;m++)
        {
         string source=points[order[m]].source;
         bool source_taken=false;
         for(int u=0;u<used;u++) if(used_sources[u]==source) { source_taken=true; break; }
         if(source_taken) continue;
         int pick=-1;
         for(int n=start;n<=end && pick<0;n++)
           {
            if(points[order[n]].source!=source) continue;
            bool time_taken=false;
            for(int u=0;u<used;u++) if(used_times[u]==points[order[n]].bar_time) { time_taken=true; break; }
            if(!time_taken) pick=n;
           }
         if(pick<0) continue;
         ArrayResize(used_sources,used+1); ArrayResize(used_times,used+1);
         used_sources[used]=source; used_times[used]=points[order[pick]].bar_time; used++;
        }
      zones[zone_count].independent_sources=used;
      string joined="";
      for(int u=0;u<used;u++) joined+=(u>0 ? "+" : "")+used_sources[u];
      zones[zone_count].sources=joined;
      double width=zones[zone_count].high-zones[zone_count].low;
      if(used<min_sources) { zones[zone_count].qualified=false; zones[zone_count].reason_code="CONFLUENCE_INSUFFICIENT"; }
      else if(width>max_width) { zones[zone_count].qualified=false; zones[zone_count].reason_code="ZONE_TOO_WIDE"; }
      else { zones[zone_count].qualified=true; zones[zone_count].reason_code="CONFLUENCE_ZONE"; }
      zone_count++;
      start=end+1;
     }
   return zone_count;
  }

// HTF structure from the last two confirmed swing highs and lows.
string EEA_HtfStructure(const EEA_LevelBar &bars[],const int count,const int wing)
  {
   double highs[2]; double lows[2]; int found_highs=0,found_lows=0;
   for(int i=count-1-wing;i>=wing && (found_highs<2 || found_lows<2);i--)
     {
      if(found_highs<2 && EEA_LevelIsFractalHigh(bars,count,i,wing)) { highs[found_highs]=bars[i].high; found_highs++; }
      if(found_lows<2 && EEA_LevelIsFractalLow(bars,count,i,wing)) { lows[found_lows]=bars[i].low; found_lows++; }
     }
   if(found_highs<2 || found_lows<2) return "NEUTRAL";
   // index 0 is the most recent swing
   if(highs[0]>highs[1] && lows[0]>lows[1]) return "UP";
   if(highs[0]<highs[1] && lows[0]<lows[1]) return "DOWN";
   return "NEUTRAL";
  }

// direction: +1 long, -1 short. Counter-trend only reduces risk (S02-D6).
double EEA_HtfRiskModifier(const string structure,const int direction,const double counter_trend_modifier)
  {
   if((structure=="UP" && direction<0) || (structure=="DOWN" && direction>0))
      return MathMax(0.0,MathMin(1.0,counter_trend_modifier));
   return 1.0;
  }

#endif
