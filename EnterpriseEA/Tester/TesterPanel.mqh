#ifndef ENTERPRISE_EA_TESTER_PANEL_MQH
#define ENTERPRISE_EA_TESTER_PANEL_MQH

// On-chart analysis panel shared by the tester EAs (S07Tester, XauRegimeTester, CtxBoxTester, CtxLimitTester):
// how the bot reads the market right now, what it waits for, its open trades and why entries were blocked.
// Text labels on a dark box (top-left), one label per line. Skipped in the non-visual Strategy Tester.
// Saved as UTF-8 with BOM so the Vietnamese text compiles as Unicode.

#define PNL_PREFIX "TPNL_"
#define PNL_FONT "Consolas"
#define PNL_SIZE 9
#define PNL_LINE_H 15

color PnlTextColor   = C'215,215,215';
color PnlHeadColor   = C'255,200,60';
color PnlOkColor     = C'90,210,120';
color PnlWarnColor   = C'240,120,100';
color PnlBoxColor    = C'18,22,30';

string g_pnl_lines[];
color  g_pnl_colors[];
int    g_pnl_drawn=0;

bool PnlActive()
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return false;
   return true;
  }

string PnlMark(const bool ok) { return ok ? "✓" : "✗"; }
string PnlDir(const int d)    { return d==1 ? "MUA" : (d==-1 ? "BÁN" : "—"); }
string PnlPx(const double v)  { return DoubleToString(v,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }
string PnlTime(const datetime t) { return TimeToString(t,TIME_DATE|TIME_MINUTES); }
string PnlHm(const datetime t)   { return TimeToString(t,TIME_MINUTES); }
string PnlR(const double r)      { return (r>=0.0 ? "+" : "")+DoubleToString(r,2)+"R"; }

void PnlBegin()
  {
   ArrayResize(g_pnl_lines,0);
   ArrayResize(g_pnl_colors,0);
  }

void PnlAdd(const string text,const color c=clrNONE)
  {
   const int n=ArraySize(g_pnl_lines);
   ArrayResize(g_pnl_lines,n+1);
   ArrayResize(g_pnl_colors,n+1);
   g_pnl_lines[n]=text;
   g_pnl_colors[n]=(c==clrNONE ? PnlTextColor : c);
  }

void PnlHead(const string text) { PnlAdd(text,PnlHeadColor); }
void PnlOk(const string text)   { PnlAdd(text,PnlOkColor); }
void PnlWarn(const string text) { PnlAdd(text,PnlWarnColor); }

void PnlFlush()
  {
   if(!PnlActive()) return;
   const long cid=0;
   const int n=ArraySize(g_pnl_lines);
   int width=0;
   for(int i=0;i<n;i++) width=MathMax(width,StringLen(g_pnl_lines[i]));
   const string box=PNL_PREFIX+"box";
   if(ObjectFind(cid,box)<0)
     {
      ObjectCreate(cid,box,OBJ_RECTANGLE_LABEL,0,0,0);
      ObjectSetInteger(cid,box,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(cid,box,OBJPROP_BGCOLOR,PnlBoxColor);
      ObjectSetInteger(cid,box,OBJPROP_BORDER_TYPE,BORDER_FLAT);
      ObjectSetInteger(cid,box,OBJPROP_COLOR,C'60,70,90');
      ObjectSetInteger(cid,box,OBJPROP_BACK,false);
      ObjectSetInteger(cid,box,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(cid,box,OBJPROP_HIDDEN,true);
     }
   ObjectSetInteger(cid,box,OBJPROP_XDISTANCE,6);
   ObjectSetInteger(cid,box,OBJPROP_YDISTANCE,22);
   ObjectSetInteger(cid,box,OBJPROP_XSIZE,16+width*7);
   ObjectSetInteger(cid,box,OBJPROP_YSIZE,10+n*PNL_LINE_H);
   for(int i=0;i<n;i++)
     {
      const string name=PNL_PREFIX+IntegerToString(i);
      if(ObjectFind(cid,name)<0)
        {
         ObjectCreate(cid,name,OBJ_LABEL,0,0,0);
         ObjectSetInteger(cid,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
         ObjectSetString(cid,name,OBJPROP_FONT,PNL_FONT);
         ObjectSetInteger(cid,name,OBJPROP_FONTSIZE,PNL_SIZE);
         ObjectSetInteger(cid,name,OBJPROP_SELECTABLE,false);
         ObjectSetInteger(cid,name,OBJPROP_HIDDEN,true);
        }
      ObjectSetInteger(cid,name,OBJPROP_XDISTANCE,14);
      ObjectSetInteger(cid,name,OBJPROP_YDISTANCE,27+i*PNL_LINE_H);
      ObjectSetInteger(cid,name,OBJPROP_COLOR,g_pnl_colors[i]);
      ObjectSetString(cid,name,OBJPROP_TEXT,g_pnl_lines[i]=="" ? " " : g_pnl_lines[i]);
     }
   for(int i=n;i<g_pnl_drawn;i++) ObjectDelete(cid,PNL_PREFIX+IntegerToString(i));
   g_pnl_drawn=n;
   ChartRedraw(cid);
  }

void PnlClear()
  {
   ObjectsDeleteAll(0,PNL_PREFIX);
   g_pnl_drawn=0;
   ChartRedraw(0);
  }

#ifdef PNL_NEWS
// News Guard and sentiment state, from the S07Tester (G91) arrays and functions of the including EA.
void PnlNewsLines()
  {
   const long now=(long)TimeCurrent();
   if(!InpNewsGuard)
      PnlAdd("Tin tức     : News Guard TẮT");
   else if(!g_news_loaded)
      PnlWarn("Tin tức     : không đọc được S07Tester_news.csv → không lọc tin");
   else
     {
      const bool blocked=NewsBlocked(now);
      int next=-1;
      for(int i=NewsFirstFrom(now);i<g_news_n;i++) { next=i; break; }
      string nx=(next>=0 ? StringFormat("tin HIGH kế tiếp %s %s (còn %.1f giờ)",g_news_cur[next],
                                         PnlTime((datetime)g_news_t[next]),(g_news_t[next]-now)/3600.0)
                         : "hết dữ liệu tin (file chỉ có tới ngày tạo) → tin mới KHÔNG được lọc");
      if(blocked) PnlWarn("Tin tức     : ĐANG CHẶN vào lệnh mới | "+nx);
      else        PnlAdd ("Tin tức     : không chặn | "+nx,next>=0 ? clrNONE : PnlWarnColor);
     }
   if(!InpSentiment)
      PnlAdd("Sentiment   : TẮT");
   else
     {
      const double b=SentimentFactor(1,now), s=SentimentFactor(-1,now);
      string f="";
      f+="MUA "+(b<=0.0 ? "CHẶN" : "x"+DoubleToString(b,1))+" | BÁN "+(s<=0.0 ? "CHẶN" : "x"+DoubleToString(s,1));
      bool stale=true;
      if(g_sent_n>0 && now-g_sent_t[g_sent_n-1]<=6*3600) stale=false;
      if(stale) f+="  (hết dữ liệu sentiment → coi như trung tính)";
      PnlAdd("Sentiment   : "+f,stale ? PnlWarnColor : clrNONE);
     }
  }
#endif

#endif
