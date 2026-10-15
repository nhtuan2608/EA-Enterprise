#ifndef ENTERPRISE_EA_TESTER_PANEL_MQH
#define ENTERPRISE_EA_TESTER_PANEL_MQH

// On-chart analysis panel shared by the tester EAs (S07Tester, XauRegimeTester, CtxBoxTester, CtxLimitTester):
// how the bot reads the market right now, what it waits for, its open trades and why entries were blocked.
// Text labels on a dark box (top-left). Sections have a [+]/[-] button: a closed section shows only its one-line
// summary. Skipped in the non-visual Strategy Tester. The panel only displays: it never changes a decision.
// Saved as UTF-8 with BOM so the Vietnamese text compiles as Unicode.

#define PNL_PREFIX "TPNL_"
#define PNL_FONT "Consolas"
#define PNL_SIZE 9
#define PNL_LINE_H 15
#define PNL_BTN_W 18

color PnlTextColor   = C'215,215,215';
color PnlHeadColor   = C'255,200,60';
color PnlOkColor     = C'90,210,120';
color PnlWarnColor   = C'240,120,100';
color PnlBoxColor    = C'18,22,30';
color PnlSecColor    = C'130,180,255';

string g_pnl_lines[];
color  g_pnl_colors[];
string g_pnl_btn[];          // section id for a section header line, else ""
int    g_pnl_drawn=0;
string g_pnl_btn_drawn[];    // button ids drawn last time

string g_sec_ids[];          // section open / closed state (kept while the EA runs)
bool   g_sec_open[];

bool PnlActive()
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return false;
   return true;
  }

string PnlMark(const bool ok) { return ok ? "[v]" : "[x]"; }   // plain ASCII: every chart font has it
string PnlDir(const int d)    { return d==1 ? "MUA" : (d==-1 ? "BÁN" : "—"); }
string PnlPx(const double v)  { return DoubleToString(v,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS)); }
string PnlTime(const datetime t) { return TimeToString(t,TIME_DATE|TIME_MINUTES); }
string PnlHm(const datetime t)   { return TimeToString(t,TIME_MINUTES); }
string PnlR(const double r)      { return (r>=0.0 ? "+" : "")+DoubleToString(r,2)+"R"; }

void PnlBegin()
  {
   ArrayResize(g_pnl_lines,0);
   ArrayResize(g_pnl_colors,0);
   ArrayResize(g_pnl_btn,0);
  }

void PnlAddLine(const string text,const color c,const string btn)
  {
   const int n=ArraySize(g_pnl_lines);
   ArrayResize(g_pnl_lines,n+1);
   ArrayResize(g_pnl_colors,n+1);
   ArrayResize(g_pnl_btn,n+1);
   g_pnl_lines[n]=text;
   g_pnl_colors[n]=(c==clrNONE ? PnlTextColor : c);
   g_pnl_btn[n]=btn;
  }

void PnlAdd(const string text,const color c=clrNONE) { PnlAddLine(text,c,""); }
void PnlHead(const string text) { PnlAdd(text,PnlHeadColor); }
void PnlOk(const string text)   { PnlAdd(text,PnlOkColor); }
void PnlWarn(const string text) { PnlAdd(text,PnlWarnColor); }

bool PnlIsOpen(const string id,const bool default_open)
  {
   for(int i=0;i<ArraySize(g_sec_ids);i++) if(g_sec_ids[i]==id) return g_sec_open[i];
   const int n=ArraySize(g_sec_ids);
   ArrayResize(g_sec_ids,n+1); ArrayResize(g_sec_open,n+1);
   g_sec_ids[n]=id; g_sec_open[n]=default_open;
   return default_open;
  }

// Section header with a [+]/[-] button; returns true when the section is open (then add its detail lines).
bool PnlSection(const string id,const string summary,const bool default_open,const color c=clrNONE)
  {
   const bool open=PnlIsOpen(id,default_open);
   PnlAddLine(summary,c==clrNONE ? PnlSecColor : c,id);
   return open;
  }

// Chart click on a section button: toggle it. Returns true when the panel must be redrawn.
bool PnlOnClick(const string object_name)
  {
   const string head=PNL_PREFIX+"btn_";
   if(StringFind(object_name,head)!=0) return false;
   const string id=StringSubstr(object_name,StringLen(head));
   for(int i=0;i<ArraySize(g_sec_ids);i++)
      if(g_sec_ids[i]==id) { g_sec_open[i]=!g_sec_open[i]; break; }
   ObjectSetInteger(0,object_name,OBJPROP_STATE,false);
   return true;
  }

void PnlFlush()
  {
   if(!PnlActive()) return;
   const long cid=0;
   const int n=ArraySize(g_pnl_lines);
   int width=0;
   for(int i=0;i<n;i++) width=MathMax(width,StringLen(g_pnl_lines[i])+(g_pnl_btn[i]!="" ? 3 : 0));
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
   ObjectSetInteger(cid,box,OBJPROP_XSIZE,22+width*7);
   ObjectSetInteger(cid,box,OBJPROP_YSIZE,10+n*PNL_LINE_H);
   string drawn[];
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
      const int y=27+i*PNL_LINE_H;
      ObjectSetInteger(cid,name,OBJPROP_XDISTANCE,g_pnl_btn[i]!="" ? 14+PNL_BTN_W+4 : 14);
      ObjectSetInteger(cid,name,OBJPROP_YDISTANCE,y);
      ObjectSetInteger(cid,name,OBJPROP_COLOR,g_pnl_colors[i]);
      ObjectSetString(cid,name,OBJPROP_TEXT,g_pnl_lines[i]=="" ? " " : g_pnl_lines[i]);
      if(g_pnl_btn[i]!="")
        {
         const string b=PNL_PREFIX+"btn_"+g_pnl_btn[i];
         if(ObjectFind(cid,b)<0)
           {
            ObjectCreate(cid,b,OBJ_BUTTON,0,0,0);
            ObjectSetInteger(cid,b,OBJPROP_CORNER,CORNER_LEFT_UPPER);
            ObjectSetInteger(cid,b,OBJPROP_XSIZE,PNL_BTN_W);
            ObjectSetInteger(cid,b,OBJPROP_YSIZE,PNL_LINE_H-2);
            ObjectSetString(cid,b,OBJPROP_FONT,PNL_FONT);
            ObjectSetInteger(cid,b,OBJPROP_FONTSIZE,PNL_SIZE);
            ObjectSetInteger(cid,b,OBJPROP_BGCOLOR,C'40,50,70');
            ObjectSetInteger(cid,b,OBJPROP_COLOR,clrWhite);
            ObjectSetInteger(cid,b,OBJPROP_BORDER_COLOR,C'70,90,120');
            ObjectSetInteger(cid,b,OBJPROP_SELECTABLE,false);
            ObjectSetInteger(cid,b,OBJPROP_HIDDEN,true);
           }
         ObjectSetInteger(cid,b,OBJPROP_XDISTANCE,14);
         ObjectSetInteger(cid,b,OBJPROP_YDISTANCE,y);
         ObjectSetString(cid,b,OBJPROP_TEXT,PnlIsOpen(g_pnl_btn[i],false) ? "-" : "+");
         ObjectSetInteger(cid,b,OBJPROP_STATE,false);
         const int k=ArraySize(drawn); ArrayResize(drawn,k+1); drawn[k]=g_pnl_btn[i];
        }
     }
   for(int i=n;i<g_pnl_drawn;i++) ObjectDelete(cid,PNL_PREFIX+IntegerToString(i));
   for(int i=0;i<ArraySize(g_pnl_btn_drawn);i++)
     {
      bool keep=false;
      for(int k=0;k<ArraySize(drawn);k++) if(drawn[k]==g_pnl_btn_drawn[i]) { keep=true; break; }
      if(!keep) ObjectDelete(cid,PNL_PREFIX+"btn_"+g_pnl_btn_drawn[i]);
     }
   ArrayCopy(g_pnl_btn_drawn,drawn);
   ArrayResize(g_pnl_btn_drawn,ArraySize(drawn));
   g_pnl_drawn=n;
   ChartRedraw(cid);
  }

void PnlClear()
  {
   ObjectsDeleteAll(0,PNL_PREFIX);
   g_pnl_drawn=0;
   ArrayResize(g_pnl_btn_drawn,0);
   ChartRedraw(0);
  }

#ifdef PNL_NEWS
// News Guard, sentiment and block counters (G91 arrays/functions of the including EA, live sources of
// Tester/LiveFeeds.mqh), as one collapsible section: the header is the one-line summary.
void PnlNewsSection(const string blocks)
  {
   const long now=(long)TimeCurrent();
   string news_s, news_d;
   bool warn=false;
   if(!InpNewsGuard) { news_s="tin: TẮT"; news_d="News Guard TẮT"; }
   else if(!g_news_loaded) { news_s="tin: KHÔNG có dữ liệu"; news_d="không có danh sách tin → không lọc tin"; warn=true; }
   else
     {
      const bool blocked=NewsBlocked(now);
      int next=-1;
      for(int i=NewsFirstFrom(now);i<g_news_n;i++) { next=i; break; }
      if(next<0 && !LfLive()) warn=true;
      news_s="tin: "+(blocked ? "ĐANG CHẶN" : "không chặn");
      news_d=(next>=0 ? StringFormat("tin HIGH kế tiếp %s %s (còn %.1f giờ)",g_news_cur[next],PnlTime((datetime)g_news_t[next]),
                                     (g_news_t[next]-now)/3600.0)
                      : (LfLive() ? "không có tin HIGH trong 7 ngày tới" : "file tin chỉ có tới ngày tạo → tin mới KHÔNG được lọc"));
     }
   string sent_s="sentiment: TẮT", sent_d="";
   bool stale=false;
   if(InpSentiment)
     {
      stale=!(g_sent_n>0 && now-g_sent_t[g_sent_n-1]<=6*3600);
      const bool active=(!InpSentimentNewsOnly || LfNearHighNews(now));
      if(!active)
         sent_s=StringFormat("sentiment: MỞ (không có tin HIGH trong ±%d giờ)",InpSentimentNewsHours);
      else
        {
         const double b=SentimentFactor(1,now), s=SentimentFactor(-1,now);
         sent_s="sentiment MUA "+(b<=0.0 ? "CHẶN" : "x"+DoubleToString(b,1))+", BÁN "+(s<=0.0 ? "CHẶN" : "x"+DoubleToString(s,1))+
                (InpSentimentNewsOnly ? " (đang gần tin HIGH)" : "")+(stale ? " (HẾT dữ liệu)" : "");
         if(stale) warn=true;
        }
      if(g_sent_n>0 && g_sent_ok[g_sent_n-1])
         sent_d=StringFormat("dòng tiền cho MUA vàng: 4h %+.2f, 24h %+.2f | cặp USD ngược MUA %.0f%%, ngược BÁN %.0f%%",
                             g_sent_v[g_sent_n-1][0],g_sent_v[g_sent_n-1][1],100.0*g_sent_v[g_sent_n-1][2],100.0*g_sent_v[g_sent_n-1][4]);
     }
   if(PnlSection("news","Tin tức & chặn : "+news_s+" | "+sent_s,false,warn ? PnlWarnColor : clrNONE))
     {
      PnlAdd("   "+news_d);
      PnlAdd("   nguồn tin: "+g_lf_news_src);
      if(InpSentiment)
        {
         PnlAdd("   sentiment: "+(InpSentimentNewsOnly ? StringFormat("chỉ chặn / giảm lot trong ±%d giờ quanh tin HIGH",InpSentimentNewsHours)
                                                       : "luôn áp dụng")+" | nguồn: "+g_lf_sent_src);
         if(sent_d!="") PnlAdd("   "+sent_d);
        }
      PnlAdd("   spread: "+(InpSpreadFilter ? "lọc BẬT" : "lọc TẮT")+" | Đã chặn: "+blocks);
     }
  }
#endif

#endif
