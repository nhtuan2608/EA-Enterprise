#ifndef ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH
#define ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH

#include "ObserverRuntime.mqh"
#include "ObserverPanelModel.mqh"
#include "..\Market\SymbolRegistry.mqh"
#include "..\Storage\PolicySettingsStore.mqh"

// Control center layout (spec 9.1): a persistent shell (header, view tabs, status
// bar) plus exactly one active view (Dashboard or Settings). Views never stack, so
// a click can only reach controls that are visible. All coordinates passed to the
// Set* helpers are relative to the panel origin.
#define EEA_PANEL_MAX_ROWS 32
#define EEA_PANEL_PREFIX "EEA_Panel_"
#define EEA_PANEL_MAIN_PREFIX "EEA_Panel_Main_"
#define EEA_PANEL_OVERLAY_PREFIX "EEA_Panel_Overlay_"
#define EEA_PANEL_BG_COLOR C'15,23,42'
#define EEA_PANEL_SURFACE_COLOR C'30,41,59'
#define EEA_PANEL_SURFACE_ALT_COLOR C'51,65,85'
#define EEA_PANEL_STRIPE_COLOR C'23,32,51'
#define EEA_PANEL_BORDER_COLOR C'51,65,85'
#define EEA_PANEL_TEXT_COLOR C'241,245,249'
#define EEA_PANEL_MUTED_COLOR C'148,163,184'
#define EEA_PANEL_FAINT_COLOR C'100,116,139'
#define EEA_PANEL_ACCENT_COLOR C'165,180,252'
#define EEA_PANEL_ACCENT_FILL_COLOR C'79,70,229'
#define EEA_PANEL_OK_COLOR C'74,222,128'
#define EEA_PANEL_ON_COLOR C'21,128,61'
#define EEA_PANEL_OFF_COLOR C'30,41,59'
#define EEA_PANEL_WARNING_COLOR C'251,191,36'
#define EEA_PANEL_WARNING_FILL_COLOR C'120,53,15'
#define EEA_PANEL_DANGER_COLOR C'248,113,113'
#define EEA_PANEL_DANGER_FILL_COLOR C'127,29,29'
#define EEA_PANEL_OK_FILL_COLOR C'20,83,45'
#define EEA_PANEL_FONT "Segoe UI"
#define EEA_PANEL_FONT_BOLD "Segoe UI Semibold"
#define EEA_PANEL_FONT_MONO "Consolas"
#define EEA_PANEL_X 10
#define EEA_PANEL_Y 28
#define EEA_PANEL_MARGIN_X 16
#define EEA_PANEL_MAIN_WIDTH 560
#define EEA_PANEL_INNER_WIDTH 536
#define EEA_PANEL_MAIN_HEIGHT 600
#define EEA_PANEL_SETTINGS_HEIGHT 600
#define EEA_PANEL_DASHBOARD_HEIGHT 600
#define EEA_PANEL_COLLAPSED_HEIGHT 48
#define EEA_PANEL_HEADER_HEIGHT 48
#define EEA_PANEL_TABBAR_HEIGHT 40
#define EEA_PANEL_VIEW_Y 96
#define EEA_PANEL_CONTENT_Y 128
#define EEA_PANEL_ROW_HEIGHT 29
#define EEA_PANEL_TABLE_ROW_HEIGHT 26
#define EEA_PANEL_TABLE_ROWS 13
#define EEA_PANEL_CONTROL_HEIGHT 30
#define EEA_PANEL_BODY_FONT_SIZE 9
#define EEA_PANEL_META_FONT_SIZE 8
#define EEA_PANEL_TITLE_FONT_SIZE 12
#define EEA_PANEL_VALUE_FONT_SIZE 13
#define EEA_PANEL_VISIBLE_ROWS 9
#define EEA_PANEL_MAX_LABEL_CHARS 84
#define EEA_PANEL_INNER_X 12
#define EEA_PANEL_CONTENT_X 24
#define EEA_PANEL_SETTINGS_ROWS_Y 166
#define EEA_PANEL_SETTINGS_SUMMARY_Y 432
#define EEA_PANEL_FOOTER_Y 456
#define EEA_PANEL_SETTINGS_SAFETY_Y 548
#define EEA_PANEL_STATUSBAR_Y 572
#define EEA_PANEL_CLICK_DEBOUNCE_MS 250
#define EEA_PANEL_MAX_HITS 160
#define EEA_PANEL_AUTO_REFRESH "AUTO_REFRESH"
// EnterpriseEA — OBSERVER ONLY; explicit confirmation is required for proposals.
#define EEA_PANEL_POLICY_PROPOSAL_ONLY "POLICY_PROPOSAL_ONLY"

enum EEA_SymbolPanelButtonVariant
  {
   EEA_PANEL_BUTTON_SECONDARY=0,
   EEA_PANEL_BUTTON_PRIMARY=1,
   EEA_PANEL_BUTTON_SELECTED=2,
   EEA_PANEL_BUTTON_ON=3,
   EEA_PANEL_BUTTON_OFF=4,
   EEA_PANEL_BUTTON_DISABLED=5,
   EEA_PANEL_BUTTON_TAB=6,
   EEA_PANEL_BUTTON_TAB_ACTIVE=7,
   EEA_PANEL_BUTTON_GHOST=8
  };

struct EEA_SymbolPanelRow
  {
   string canonical_symbol;
   string broker_symbol;
   string status;
   string description;
   bool checked;
   bool context_only;
   EEA_RuntimeSymbolSpec spec;
  };

struct EEA_SymbolPanelState
  {
   long chart_id;
   int sub_window;
   int row_count;
   int row_offset;
   EEA_SymbolPanelRow rows[EEA_PANEL_MAX_ROWS];
   string status_message;
   string apply_reason;
   string committed_policy;
   string staged_policy;
   bool committed_daily_continuation;
   bool staged_daily_continuation;
   bool committed_overall_continuation;
   bool staged_overall_continuation;
   bool policy_confirmed;
   bool overlay_open;
   string overlay_name;
   bool staged_initialized;
   long authorization_utc;
   string authorization_input_gmt7;
   string policy_store_path;
   string active_view;
   string dashboard_tab;
   string settings_tab;
   bool collapsed;
   string last_click_name;
   uint last_click_tick;
   string hover_name;
   bool chart_scroll_captured;
   bool chart_scroll_original;
   bool chart_mouse_move_original;
   int calendar_year;
   int calendar_month;
   int calendar_selected_day;
   string toast_text;
   color toast_color;
   datetime toast_until;
   string edit_rendered_value;
  };

static EEA_SymbolPanelState g_panel_state;

// Read-only engine facts published by the EA shell before each refresh. The panel
// renders them; it never derives execution or strategy state on its own.
struct EEA_SymbolPanelEngineView
  {
   bool published;
   bool observer_only;
   bool execution_enabled;
   bool live_armed;
   string controller_status;
   bool controller_kill_active;
   bool controller_allows_market;
   bool recovery_blocked;
   string live_reason;
   bool strategy_enabled;
   string strategy_reason;
   int setup_count;
   string setup_symbol[EEA_PANEL_MAX_ROWS];
   string setup_state[EEA_PANEL_MAX_ROWS];
   int universe_count;
   string universe[EEA_PANEL_MAX_ROWS];
  };

static EEA_SymbolPanelEngineView g_panel_engine;

struct EEA_SymbolPanelHit
  {
   string name;
   int x;
   int y;
   int w;
   int h;
   color base;
  };

static EEA_SymbolPanelHit g_panel_hits[EEA_PANEL_MAX_HITS];
static int g_panel_hit_count=0;

void EEA_SymbolPanelEngineViewDefaults(EEA_SymbolPanelEngineView &view)
  {
   view.published=false;
   view.observer_only=true;
   view.execution_enabled=false;
   view.live_armed=false;
   view.controller_status="MISSING";
   view.controller_kill_active=true;
   view.controller_allows_market=false;
   view.recovery_blocked=false;
   view.live_reason="";
   view.strategy_enabled=false;
   view.strategy_reason="";
   view.setup_count=0;
   view.universe_count=0;
   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++)
     { view.setup_symbol[i]=""; view.setup_state[i]=""; view.universe[i]=""; }
  }

void EEA_SymbolPanelSetEngineView(const EEA_SymbolPanelEngineView &view)
  {
   g_panel_engine=view;
   g_panel_engine.published=true;
  }

struct EEA_SymbolPanelPolicySnapshot
  {
   string committed_policy;
   bool committed_daily_continuation;
   bool committed_overall_continuation;
   string staged_policy;
   bool staged_daily_continuation;
   bool staged_overall_continuation;
   bool policy_confirmed;
   string authorization_input_gmt7;
   long authorization_utc;
   string status_message;
   string apply_reason;
  };

void EEA_SymbolPanelCapturePolicySnapshot(EEA_SymbolPanelPolicySnapshot &snapshot)
  {
   snapshot.committed_policy=g_panel_state.committed_policy;
   snapshot.committed_daily_continuation=g_panel_state.committed_daily_continuation;
   snapshot.committed_overall_continuation=g_panel_state.committed_overall_continuation;
   snapshot.staged_policy=g_panel_state.staged_policy;
   snapshot.staged_daily_continuation=g_panel_state.staged_daily_continuation;
   snapshot.staged_overall_continuation=g_panel_state.staged_overall_continuation;
   snapshot.policy_confirmed=g_panel_state.policy_confirmed;
   snapshot.authorization_input_gmt7=g_panel_state.authorization_input_gmt7;
   snapshot.authorization_utc=g_panel_state.authorization_utc;
   snapshot.status_message=g_panel_state.status_message;
   snapshot.apply_reason=g_panel_state.apply_reason;
  }

void EEA_SymbolPanelRestorePolicySnapshot(const EEA_SymbolPanelPolicySnapshot &snapshot)
  {
   g_panel_state.committed_policy=snapshot.committed_policy;
   g_panel_state.committed_daily_continuation=snapshot.committed_daily_continuation;
   g_panel_state.committed_overall_continuation=snapshot.committed_overall_continuation;
   g_panel_state.staged_policy=snapshot.staged_policy;
   g_panel_state.staged_daily_continuation=snapshot.staged_daily_continuation;
   g_panel_state.staged_overall_continuation=snapshot.staged_overall_continuation;
   g_panel_state.policy_confirmed=snapshot.policy_confirmed;
   g_panel_state.authorization_input_gmt7=snapshot.authorization_input_gmt7;
   g_panel_state.authorization_utc=snapshot.authorization_utc;
   g_panel_state.status_message=snapshot.status_message;
   g_panel_state.apply_reason=snapshot.apply_reason;
  }

string EEA_SymbolPanelUtcText(const long value)
  {
   if(value<=0) return "UNAVAILABLE";
   MqlDateTime dt;
   TimeToStruct((datetime)value,dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",dt.year,dt.mon,dt.day,dt.hour,dt.min,dt.sec);
  }

bool EEA_SymbolPanelIsContextOnly(const string canonical,const string broker)
  {
   string c=EEA_TrimUpper(canonical), b=EEA_TrimUpper(broker);
   return c=="DXY" || c=="USDX" || b=="USDX" || b=="USDX.";
  }

string EEA_SymbolPanelReadableUtc(const long value)
  {
   string text=EEA_SymbolPanelUtcText(value);
   return text=="UNAVAILABLE" ? text : text+" UTC";
  }

string EEA_SymbolPanelClipText(const string text,const int max_chars=EEA_PANEL_MAX_LABEL_CHARS)
  {
   if(max_chars<4 || StringLen(text)<=max_chars) return text;
   return StringSubstr(text,0,max_chars-3)+"...";
  }

color EEA_SymbolPanelStatusColor(const string runtime_state)
  {
   if(runtime_state=="READY" || runtime_state=="OBSERVING" || runtime_state=="RECONCILED")
      return EEA_PANEL_OK_COLOR;
   if(runtime_state=="DEGRADED" || runtime_state=="STALE" || runtime_state=="PENDING")
      return EEA_PANEL_WARNING_COLOR;
   return EEA_PANEL_DANGER_COLOR;
  }

string EEA_SymbolPanelGlyph(const int code)
  {
   return ShortToString((ushort)code);
  }

string EEA_SymbolPanelSep()
  {
   return "  "+EEA_SymbolPanelGlyph(0x00B7)+"  ";
  }

string EEA_SymbolPanelFormatNumber(const double value,const int digits)
  {
   if(!MathIsValidNumber(value)) return "--";
   string raw=DoubleToString(MathAbs(value),digits);
   int dot=StringFind(raw,".");
   string whole=dot>=0 ? StringSubstr(raw,0,dot) : raw;
   string fraction=dot>=0 ? StringSubstr(raw,dot) : "";
   string grouped="";
   int length=StringLen(whole);
   for(int i=0;i<length;i++)
     {
      if(i>0 && (length-i)%3==0) grouped+=",";
      grouped+=StringSubstr(whole,i,1);
     }
   return (value<0.0 && raw!=DoubleToString(0.0,digits) ? "-" : "")+grouped+fraction;
  }

string EEA_SymbolPanelSigned(const double value,const int digits=2)
  {
   string text=EEA_SymbolPanelFormatNumber(value,digits);
   return value>0.0 ? "+"+text : text;
  }

color EEA_SymbolPanelPnlColor(const double value)
  {
   if(value>0.0) return EEA_PANEL_OK_COLOR;
   if(value<0.0) return EEA_PANEL_DANGER_COLOR;
   return EEA_PANEL_TEXT_COLOR;
  }

string EEA_SymbolPanelClockUtc(const long value)
  {
   if(value<=0) return "--:--:--";
   MqlDateTime dt;
   TimeToStruct((datetime)value,dt);
   return StringFormat("%02d:%02d:%02dZ",dt.hour,dt.min,dt.sec);
  }

color EEA_SymbolPanelLighten(const color value,const int amount)
  {
   uint raw=(uint)value;
   int r=(int)(raw&0xFF)+amount;
   int g=(int)((raw>>8)&0xFF)+amount;
   int b=(int)((raw>>16)&0xFF)+amount;
   if(r>255) r=255;
   if(g>255) g=255;
   if(b>255) b=255;
   return (color)(r|(g<<8)|(b<<16));
  }

void EEA_SymbolPanelRegisterHit(const string name,const int x,const int y,const int width,
                                const int height,const color base)
  {
   int index=-1;
   for(int i=0;i<g_panel_hit_count;i++)
      if(g_panel_hits[i].name==name) { index=i; break; }
   if(index<0)
     {
      if(g_panel_hit_count>=EEA_PANEL_MAX_HITS) return;
      index=g_panel_hit_count;
      g_panel_hit_count++;
     }
   g_panel_hits[index].name=name;
   g_panel_hits[index].x=EEA_PANEL_X+x;
   g_panel_hits[index].y=EEA_PANEL_Y+y;
   g_panel_hits[index].w=width;
   g_panel_hits[index].h=height;
   g_panel_hits[index].base=base;
  }

void EEA_SymbolPanelUnregisterHit(const string name)
  {
   for(int i=0;i<g_panel_hit_count;i++)
      if(g_panel_hits[i].name==name)
        {
         for(int j=i+1;j<g_panel_hit_count;j++) g_panel_hits[j-1]=g_panel_hits[j];
         g_panel_hit_count--;
         break;
        }
   if(g_panel_state.hover_name==name) g_panel_state.hover_name="";
  }

void EEA_SymbolPanelPruneHits(const string prefix)
  {
   int kept=0;
   for(int i=0;i<g_panel_hit_count;i++)
     {
      if(StringFind(g_panel_hits[i].name,prefix)==0) continue;
      if(kept!=i) g_panel_hits[kept]=g_panel_hits[i];
      kept++;
     }
   g_panel_hit_count=kept;
   if(StringFind(g_panel_state.hover_name,prefix)==0) g_panel_state.hover_name="";
  }

void EEA_SymbolPanelStyleObject(const long chart_id,const string name,const color text_color,
                                const int font_size,const int zorder)
  {
   ObjectSetInteger(chart_id,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(chart_id,name,OBJPROP_COLOR,text_color);
   ObjectSetString(chart_id,name,OBJPROP_FONT,EEA_PANEL_FONT);
   ObjectSetInteger(chart_id,name,OBJPROP_FONTSIZE,font_size);
   // Panel objects are never selectable: a selectable control is picked up by a
   // double-click and can then be dragged, which made controls feel unresponsive.
   ObjectSetInteger(chart_id,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(chart_id,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(chart_id,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(chart_id,name,OBJPROP_ZORDER,zorder);
  }

void EEA_SymbolPanelSetSurface(const long chart_id,const string name,const int x,const int y,
                               const int width,const int height,const color background,
                               const color border=EEA_PANEL_BORDER_COLOR)
  {
   if(ObjectFind(chart_id,name)<0)
      ObjectCreate(chart_id,name,OBJ_RECTANGLE_LABEL,g_panel_state.sub_window,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,EEA_PANEL_X+x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,EEA_PANEL_Y+y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,height);
   ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,background);
   ObjectSetInteger(chart_id,name,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(chart_id,name,OBJPROP_COLOR,border);
   ObjectSetInteger(chart_id,name,OBJPROP_BORDER_COLOR,border);
   ObjectSetInteger(chart_id,name,OBJPROP_BACK,false);
   ObjectSetInteger(chart_id,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(chart_id,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(chart_id,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(chart_id,name,OBJPROP_ZORDER,0);
  }

// A surface that also reacts to hover and clicks (list rows, calendar cells).
void EEA_SymbolPanelSetHotSurface(const long chart_id,const string name,const int x,const int y,
                                  const int width,const int height,const color background,
                                  const color border)
  {
   EEA_SymbolPanelSetSurface(chart_id,name,x,y,width,height,background,border);
   ObjectSetInteger(chart_id,name,OBJPROP_ZORDER,5);
   EEA_SymbolPanelRegisterHit(name,x,y,width,height,background);
   if(g_panel_state.hover_name==name)
      ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,EEA_SymbolPanelLighten(background,14));
  }

void EEA_SymbolPanelSetLabel(const long chart_id,const string name,const int x,const int y,
                             const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_LABEL,g_panel_state.sub_window,0,0);
   EEA_SymbolPanelStyleObject(chart_id,name,EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE,10);
   ObjectSetInteger(chart_id,name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,EEA_PANEL_X+x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,EEA_PANEL_Y+y);
   // MT5 renders an empty label as the literal word "Label".
   string clipped=EEA_SymbolPanelClipText(text);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,clipped=="" ? " " : clipped);
  }

void EEA_SymbolPanelSetText(const long chart_id,const string name,const int x,const int y,
                            const string text,const color text_color,const int font_size,
                            const string font=EEA_PANEL_FONT,
                            const ENUM_ANCHOR_POINT anchor=ANCHOR_LEFT_UPPER,
                            const int max_chars=EEA_PANEL_MAX_LABEL_CHARS)
  {
   EEA_SymbolPanelSetLabel(chart_id,name,x,y,EEA_SymbolPanelClipText(text,max_chars));
   ObjectSetInteger(chart_id,name,OBJPROP_COLOR,text_color);
   ObjectSetInteger(chart_id,name,OBJPROP_FONTSIZE,font_size);
   ObjectSetString(chart_id,name,OBJPROP_FONT,font);
   ObjectSetInteger(chart_id,name,OBJPROP_ANCHOR,anchor);
  }

void EEA_SymbolPanelSetLabelColor(const long chart_id,const string name,const int x,const int y,
                                  const string text,const color text_color,
                                  const int font_size=EEA_PANEL_BODY_FONT_SIZE)
  {
   EEA_SymbolPanelSetText(chart_id,name,x,y,text,text_color,font_size);
  }

// Section caption: small, letter-spaced, muted accent.
void EEA_SymbolPanelSetCaption(const long chart_id,const string name,const int x,const int y,
                               const string text)
  {
   EEA_SymbolPanelSetText(chart_id,name,x,y,text,EEA_PANEL_ACCENT_COLOR,EEA_PANEL_META_FONT_SIZE,
                          EEA_PANEL_FONT_BOLD);
  }

void EEA_SymbolPanelButtonColors(const EEA_SymbolPanelButtonVariant variant,color &background,
                                 color &border,color &text_color)
  {
   background=EEA_PANEL_SURFACE_ALT_COLOR; border=EEA_PANEL_BORDER_COLOR; text_color=EEA_PANEL_TEXT_COLOR;
   if(variant==EEA_PANEL_BUTTON_PRIMARY)
     { background=EEA_PANEL_ACCENT_FILL_COLOR; border=EEA_PANEL_ACCENT_FILL_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_SELECTED)
     { background=EEA_PANEL_ACCENT_FILL_COLOR; border=EEA_PANEL_ACCENT_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_ON)
     { background=EEA_PANEL_ON_COLOR; border=EEA_PANEL_OK_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_OFF)
     { background=EEA_PANEL_OFF_COLOR; border=EEA_PANEL_BORDER_COLOR; text_color=EEA_PANEL_MUTED_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_DISABLED)
     { background=EEA_PANEL_SURFACE_COLOR; border=EEA_PANEL_SURFACE_COLOR; text_color=EEA_PANEL_FAINT_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_TAB)
     { background=EEA_PANEL_BG_COLOR; border=EEA_PANEL_BG_COLOR; text_color=EEA_PANEL_MUTED_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_TAB_ACTIVE)
     { background=EEA_PANEL_SURFACE_COLOR; border=EEA_PANEL_ACCENT_FILL_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_GHOST)
     { background=EEA_PANEL_SURFACE_COLOR; border=EEA_PANEL_BORDER_COLOR; text_color=EEA_PANEL_MUTED_COLOR; }
  }

void EEA_SymbolPanelSetButtonEx(const long chart_id,const string name,const int x,const int y,
                                const int width,const int height,const string text,
                                const EEA_SymbolPanelButtonVariant variant,
                                const int font_size=EEA_PANEL_BODY_FONT_SIZE)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_BUTTON,g_panel_state.sub_window,0,0);
   color background,border,text_color;
   EEA_SymbolPanelButtonColors(variant,background,border,text_color);
   EEA_SymbolPanelStyleObject(chart_id,name,text_color,font_size,20);
   ObjectSetString(chart_id,name,OBJPROP_FONT,EEA_PANEL_FONT_BOLD);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,EEA_PANEL_X+x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,EEA_PANEL_Y+y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,height);
   ObjectSetInteger(chart_id,name,OBJPROP_BORDER_COLOR,border);
   ObjectSetInteger(chart_id,name,OBJPROP_BACK,false);
   // Buttons are momentary: never leave one latched in the pressed state.
   ObjectSetInteger(chart_id,name,OBJPROP_STATE,false);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,EEA_SymbolPanelClipText(text,40));
   if(variant==EEA_PANEL_BUTTON_DISABLED) EEA_SymbolPanelUnregisterHit(name);
   else EEA_SymbolPanelRegisterHit(name,x,y,width,height,background);
   bool hovered=(g_panel_state.hover_name==name && variant!=EEA_PANEL_BUTTON_DISABLED);
   ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,hovered ? EEA_SymbolPanelLighten(background,18) : background);
  }

void EEA_SymbolPanelSetButton(const long chart_id,const string name,const int x,const int y,
                              const int width,const string text)
  {
   EEA_SymbolPanelSetButtonEx(chart_id,name,x,y,width,EEA_PANEL_CONTROL_HEIGHT,text,EEA_PANEL_BUTTON_SECONDARY);
  }

// Toggle with semantic colors: EEA_PANEL_ON_COLOR when on, EEA_PANEL_OFF_COLOR when off.
void EEA_SymbolPanelSetButtonState(const long chart_id,const string name,const int x,const int y,
                                   const int width,const string text,const bool enabled)
  {
   EEA_SymbolPanelSetButtonEx(chart_id,name,x,y,width,EEA_PANEL_CONTROL_HEIGHT-2,text,
                              enabled ? EEA_PANEL_BUTTON_ON : EEA_PANEL_BUTTON_OFF);
   ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,enabled ? EEA_PANEL_ON_COLOR : EEA_PANEL_OFF_COLOR);
   if(g_panel_state.hover_name==name)
      ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,
                       EEA_SymbolPanelLighten(enabled ? EEA_PANEL_ON_COLOR : EEA_PANEL_OFF_COLOR,18));
  }

void EEA_SymbolPanelSetEdit(const long chart_id,const string name,const int x,const int y,
                            const int width,const string text)
  {
   bool created=ObjectFind(chart_id,name)<0;
   if(created) ObjectCreate(chart_id,name,OBJ_EDIT,g_panel_state.sub_window,0,0);
   EEA_SymbolPanelStyleObject(chart_id,name,EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE+1,20);
   ObjectSetString(chart_id,name,OBJPROP_FONT,EEA_PANEL_FONT_MONO);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,EEA_PANEL_X+x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,EEA_PANEL_Y+y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,EEA_PANEL_CONTROL_HEIGHT);
   ObjectSetInteger(chart_id,name,OBJPROP_BGCOLOR,EEA_PANEL_BG_COLOR);
   ObjectSetInteger(chart_id,name,OBJPROP_BORDER_COLOR,EEA_PANEL_ACCENT_FILL_COLOR);
   ObjectSetInteger(chart_id,name,OBJPROP_ALIGN,ALIGN_LEFT);
   ObjectSetInteger(chart_id,name,OBJPROP_READONLY,false);
   ObjectSetInteger(chart_id,name,OBJPROP_BACK,false);
   // Timer refreshes must not wipe what the operator is typing: only push the
   // stored value when the field is new or the stored value itself changed.
   if(created || text!=g_panel_state.edit_rendered_value)
      ObjectSetString(chart_id,name,OBJPROP_TEXT,EEA_SymbolPanelClipText(text,32));
   g_panel_state.edit_rendered_value=text;
  }

// Key/value pair used by status grids: muted caption above a value.
void EEA_SymbolPanelSetField(const long chart_id,const string name,const int x,const int y,
                             const string caption,const string value,const color value_color,
                             const int max_chars=34)
  {
   EEA_SymbolPanelSetText(chart_id,name+"_K",x,y,caption,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,name+"_V",x,y+14,value,value_color,EEA_PANEL_BODY_FONT_SIZE,
                          EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,max_chars);
  }

// KPI tile: caption, large monospace value, optional footnote.
void EEA_SymbolPanelSetTile(const long chart_id,const string name,const int x,const int y,
                            const int width,const string caption,const string value,
                            const color value_color,const string note)
  {
   EEA_SymbolPanelSetSurface(chart_id,name,x,y,width,60,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetText(chart_id,name+"_K",x+10,y+7,caption,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                          EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,name+"_V",x+10,y+22,value,value_color,EEA_PANEL_VALUE_FONT_SIZE,
                          EEA_PANEL_FONT_MONO,ANCHOR_LEFT_UPPER,16);
   EEA_SymbolPanelSetText(chart_id,name+"_N",x+10,y+43,note,EEA_PANEL_FAINT_COLOR,7,
                          EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,24);
  }

// Small rounded-looking status chip (filled rectangle plus centred text).
void EEA_SymbolPanelSetPill(const long chart_id,const string name,const int x,const int y,
                            const int width,const string text,const color fill,const color text_color)
  {
   EEA_SymbolPanelSetSurface(chart_id,name,x,y,width,22,fill,fill);
   EEA_SymbolPanelSetText(chart_id,name+"_T",x+width/2,y+11,text,text_color,EEA_PANEL_META_FONT_SIZE,
                          EEA_PANEL_FONT_BOLD,ANCHOR_CENTER,22);
  }

void EEA_SymbolPanelStateFill(const string state,color &fill,color &text_color)
  {
   color semantic=EEA_SymbolPanelStatusColor(state);
   if(semantic==EEA_PANEL_OK_COLOR) { fill=EEA_PANEL_OK_FILL_COLOR; text_color=EEA_PANEL_OK_COLOR; }
   else if(semantic==EEA_PANEL_WARNING_COLOR) { fill=EEA_PANEL_WARNING_FILL_COLOR; text_color=EEA_PANEL_WARNING_COLOR; }
   else { fill=EEA_PANEL_DANGER_FILL_COLOR; text_color=EEA_PANEL_DANGER_COLOR; }
  }

void EEA_SymbolPanelToast(const string text,const color text_color)
  {
   g_panel_state.toast_text=text;
   g_panel_state.toast_color=text_color;
   g_panel_state.toast_until=TimeLocal()+10;
  }

long EEA_SymbolPanelDaysFromCivil(int y,int m,int d)
  {
   y-=m<=2 ? 1 : 0;
   int era=(y>=0 ? y : y-399)/400;
   int yoe=y-era*400;
   int mp=m+(m>2 ? -3 : 9);
   int doy=(153*mp+2)/5+d-1;
   int doe=yoe*365+yoe/4-yoe/100+doy;
   return (long)era*146097+doe-719468;
  }

bool EEA_SymbolPanelParseGmtPlus7(const string value,long &authorization_utc,string &reason)
  {
   authorization_utc=0; reason="GMT_PLUS_7_INVALID";
   if(StringLen(value)!=16 || StringGetCharacter(value,4)!=45 || StringGetCharacter(value,7)!=45 ||
      StringGetCharacter(value,10)!=32 || StringGetCharacter(value,13)!=58) return false;
   long y_value=StringToInteger(StringSubstr(value,0,4));
   long m_value=StringToInteger(StringSubstr(value,5,2));
   long d_value=StringToInteger(StringSubstr(value,8,2));
   long hh_value=StringToInteger(StringSubstr(value,11,2));
   long mm_value=StringToInteger(StringSubstr(value,14,2));
   int y=(int)y_value; int m=(int)m_value; int d=(int)d_value; int hh=(int)hh_value; int mm=(int)mm_value;
   if(y<1970 || m<1 || m>12 || d<1 || d>31 || hh<0 || hh>23 || mm<0 || mm>59) return false;
   int next_m=m==12 ? 1 : m+1; int next_y=m==12 ? y+1 : y;
   if(EEA_SymbolPanelDaysFromCivil(next_y,next_m,1)-EEA_SymbolPanelDaysFromCivil(y,m,1)<d) return false;
   authorization_utc=EEA_SymbolPanelDaysFromCivil(y,m,d)*86400+hh*3600+mm*60-7*60*60;
   if(authorization_utc<=0) { authorization_utc=0; return false; }
   reason="GMT_PLUS_7_VALIDATED"; return true;
  }

bool EEA_SymbolPanelAuditPolicy(CAuditLog &audit,const string event_type,const string reason,
                                const string policy,const long authorization_utc)
  {
   if(!audit.IsOpen()) return false;
   EEAEvent e; EEAEvent_Init(e,event_type,TimeGMT(),"","policy-settings","","OBSERVER_ONLY","DEGRADED");
   EEAEvent_AddReason(e,reason);
   e.details_json="{\"observer_only\":true,\"new_entries_blocked\":true,\"policy\":\""+
      EEA_JsonEscape(policy)+"\",\"authorization_utc\":\""+EEA_IsoUtc((datetime)authorization_utc)+"\"}";
   return audit.Append(e,"EA_POLICY_OBSERVER");
  }

bool EEA_SymbolPanelRequirePolicyAudit(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,
                                       const string event_type,const string reason,
                                       const string policy,const long authorization_utc)
  {
   if(EEA_SymbolPanelAuditPolicy(audit,event_type,reason,policy,authorization_utc)) return true;
   ctx.status.runtime_state="BLOCKED";
   ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
   ctx.status.new_entries_blocked=true;
   bool status_persisted=EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
      ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
   return false;
  }

void EEA_SymbolPanelClearOverlay(const long chart_id)
  {
   ObjectsDeleteAll(chart_id,EEA_PANEL_OVERLAY_PREFIX,g_panel_state.sub_window);
   EEA_SymbolPanelPruneHits(EEA_PANEL_OVERLAY_PREFIX);
   g_panel_state.overlay_open=false;
   g_panel_state.overlay_name="";
  }

bool EEA_SymbolPanelBeginOverlay(const long chart_id,const string view_name)
  {
   bool reuse=g_panel_state.overlay_open && g_panel_state.overlay_name==view_name &&
      ObjectFind(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Surface")>=0;
   if(!reuse) EEA_SymbolPanelClearOverlay(chart_id);
   g_panel_state.overlay_open=true;
   g_panel_state.overlay_name=view_name;
   return reuse;
  }

void EEA_SymbolPanelClearSettingsRows(const long chart_id)
  {
   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++)
     {
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Chk");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Lbl");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Bg");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Badge");
     }
   EEA_SymbolPanelPruneHits(EEA_PANEL_OVERLAY_PREFIX+"Row_");
  }

void EEA_SymbolPanelClearDashboardRows(const long chart_id)
  {
   for(int i=0;i<EEA_PANEL_VISIBLE_ROWS;i++)
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(i));
   ObjectsDeleteAll(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_",g_panel_state.sub_window);
   EEA_SymbolPanelPruneHits(EEA_PANEL_OVERLAY_PREFIX+"Spec_");
  }

void EEA_SymbolPanelCloseOverlay(const long chart_id)
  {
   EEA_SymbolPanelClearOverlay(chart_id);
  }

int EEA_SymbolPanelHeight()
  {
   return g_panel_state.collapsed ? EEA_PANEL_COLLAPSED_HEIGHT : EEA_PANEL_MAIN_HEIGHT;
  }

bool EEA_SymbolPanelSelectionContains(const EEA_ObserverRuntimeContext &ctx,const string canonical)
  {
   for(int j=0;j<ctx.symbol_count;j++)
      if(ctx.canonical_symbols[j]==canonical) return true;
   return false;
  }

int EEA_SymbolPanelStagedSymbolCount()
  {
   int count=0;
   for(int i=0;i<g_panel_state.row_count;i++)
      if(g_panel_state.rows[i].checked && !g_panel_state.rows[i].context_only) count++;
   return count;
  }

// Number of staged differences from the committed runtime selection and policy.
int EEA_SymbolPanelPendingChanges(const EEA_ObserverRuntimeContext &ctx)
  {
   int pending=0;
   if(g_panel_state.staged_policy!=g_panel_state.committed_policy) pending++;
   if(g_panel_state.staged_daily_continuation!=g_panel_state.committed_daily_continuation) pending++;
   if(g_panel_state.staged_overall_continuation!=g_panel_state.committed_overall_continuation) pending++;
   for(int i=0;i<g_panel_state.row_count;i++)
     {
      if(g_panel_state.rows[i].context_only) continue;
      if(g_panel_state.rows[i].checked!=EEA_SymbolPanelSelectionContains(ctx,g_panel_state.rows[i].canonical_symbol))
         pending++;
     }
   return pending;
  }

string EEA_SymbolPanelSetupState(const string canonical)
  {
   for(int i=0;i<g_panel_engine.setup_count && i<EEA_PANEL_MAX_ROWS;i++)
      if(g_panel_engine.setup_symbol[i]==canonical) return g_panel_engine.setup_state[i];
   return g_panel_engine.strategy_enabled ? "IDLE" : "OFF";
  }

void EEA_SymbolPanelCreateControls(const long chart_id,const int sub_window)
  {
   g_panel_state.chart_id=chart_id;
   g_panel_state.sub_window=sub_window;
   ObjectsDeleteAll(chart_id,EEA_PANEL_PREFIX,g_panel_state.sub_window);
   g_panel_hit_count=0;
   g_panel_state.hover_name="";
   int height=EEA_SymbolPanelHeight();
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"Surface",0,0,
                             EEA_PANEL_MAIN_WIDTH,height,EEA_PANEL_BG_COLOR);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"HeaderSurface",0,0,
                             EEA_PANEL_MAIN_WIDTH,EEA_PANEL_HEADER_HEIGHT,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"Brand",0,0,4,EEA_PANEL_HEADER_HEIGHT,
                             EEA_PANEL_ACCENT_FILL_COLOR,EEA_PANEL_ACCENT_FILL_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Header",EEA_PANEL_MARGIN_X,7,
                          "EnterpriseEA",EEA_PANEL_TEXT_COLOR,EEA_PANEL_TITLE_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Subheader",EEA_PANEL_MARGIN_X,29,
                          "Control center",EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Collapse",EEA_PANEL_MAIN_WIDTH-40,12,28,24,
                              g_panel_state.collapsed ? "+" : EEA_SymbolPanelGlyph(0x2013),
                              EEA_PANEL_BUTTON_GHOST,10);
   ObjectSetString(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Collapse",OBJPROP_TOOLTIP,
                   g_panel_state.collapsed ? "Expand panel" : "Collapse panel");
   if(g_panel_state.collapsed) { ChartRedraw(chart_id); return; }
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"TabBar",0,EEA_PANEL_HEADER_HEIGHT,
                             EEA_PANEL_MAIN_WIDTH,EEA_PANEL_TABBAR_HEIGHT,EEA_PANEL_BG_COLOR,EEA_PANEL_BG_COLOR);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"TabRule",EEA_PANEL_INNER_X,
                             EEA_PANEL_HEADER_HEIGHT+EEA_PANEL_TABBAR_HEIGHT-1,EEA_PANEL_INNER_WIDTH,1,
                             EEA_PANEL_BORDER_COLOR,EEA_PANEL_BORDER_COLOR);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"StatusBar",0,EEA_PANEL_STATUSBAR_Y,
                             EEA_PANEL_MAIN_WIDTH,EEA_PANEL_MAIN_HEIGHT-EEA_PANEL_STATUSBAR_Y,EEA_PANEL_SURFACE_COLOR);
   ChartRedraw(chart_id);
  }

EEA_ObserverPanelMarketRow EEA_ObserverPanelMarketRowFromRuntime(const EEA_ObserverRuntimeContext &ctx,const int index)
  {
   EEA_ObserverPanelMarketRow row;
   EEA_ObserverPanelMarketRowDefaults(row);
   if(index<0 || index>=ctx.symbol_count) return row;
   row.canonical=ctx.canonical_symbols[index];
   row.broker=ctx.broker_symbols[index];
   row.status=(row.broker=="" ? "UNRESOLVED" : "RESOLVED");
   row.context_only=EEA_SymbolPanelIsContextOnly(row.canonical,row.broker);
   if(row.context_only) row.status="CONTEXT ONLY";
   row.digits=ctx.symbol_specs[index].digits;
   row.trade_mode=ctx.symbol_specs[index].trade_mode;
   row.freshness_text=EEA_SymbolPanelReadableUtc(ctx.reconciliation.valid_until_utc);
   return row;
  }

// Shell: header status pill, view tabs and status bar. Never touches the view.
void EEA_SymbolPanelRenderMainView(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   color pill_fill,pill_text;
   EEA_SymbolPanelStateFill(ctx.status.runtime_state,pill_fill,pill_text);
   EEA_SymbolPanelSetPill(chart_id,EEA_PANEL_MAIN_PREFIX+"Pill",EEA_PANEL_MAIN_WIDTH-178,13,128,
                          ctx.status.runtime_state,pill_fill,pill_text);
   string execution=g_panel_engine.execution_enabled ? "Execution ENABLED" : "EXECUTION_DISABLED";
   string live=(g_panel_engine.execution_enabled && g_panel_engine.live_armed) ? "Live ARMED (gated)" : "Live NOT_AUTHORIZED";
   string entries=ctx.status.new_entries_blocked ? "Entries BLOCKED" : "Entries REVIEW";
   string subheader=g_panel_state.collapsed ?
      "Equity "+EEA_SymbolPanelFormatNumber(ctx.account.equity,2)+" "+ctx.account.account_currency+
      EEA_SymbolPanelSep()+entries :
      execution+EEA_SymbolPanelSep()+live+EEA_SymbolPanelSep()+entries;
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Subheader",EEA_PANEL_MARGIN_X,29,subheader,
                          ctx.status.new_entries_blocked ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_WARNING_COLOR,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,60);
   if(g_panel_state.collapsed) { ChartRedraw(chart_id); return; }
   bool dashboard=(g_panel_state.active_view!="SETTINGS");
   int tab_y=EEA_PANEL_HEADER_HEIGHT+6;
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard",EEA_PANEL_INNER_X,tab_y,124,28,
                              "Dashboard",dashboard ? EEA_PANEL_BUTTON_TAB_ACTIVE : EEA_PANEL_BUTTON_TAB,10);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Settings",EEA_PANEL_INNER_X+130,tab_y,124,28,
                              "Settings",dashboard ? EEA_PANEL_BUTTON_TAB : EEA_PANEL_BUTTON_TAB_ACTIVE,10);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"TabIndicator",
                             EEA_PANEL_INNER_X+(dashboard ? 0 : 130),tab_y+28,124,3,
                             EEA_PANEL_ACCENT_FILL_COLOR,EEA_PANEL_ACCENT_FILL_COLOR);
   // AUTO_REFRESH: the view refreshes from the EA timer; there is no manual refresh button.
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_AutoRefresh",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_MARGIN_X,
                          tab_y+8,"Auto-refresh "+IntegerToString(ctx.refresh_seconds)+"s"+EEA_SymbolPanelSep()+
                          "last "+EEA_SymbolPanelClockUtc(ctx.last_refresh_utc),
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_RIGHT_UPPER);
   if(g_panel_state.toast_text!="" && TimeLocal()>=g_panel_state.toast_until) g_panel_state.toast_text="";
   string status_text=g_panel_state.toast_text!="" ? g_panel_state.toast_text :
      "Ready"+EEA_SymbolPanelSep()+ctx.status.reason_code;
   color status_color=g_panel_state.toast_text!="" ? g_panel_state.toast_color : EEA_PANEL_MUTED_COLOR;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"StatusDot",EEA_PANEL_MARGIN_X,EEA_PANEL_STATUSBAR_Y+11,6,6,
                             status_color,status_color);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Status",EEA_PANEL_MARGIN_X+14,EEA_PANEL_STATUSBAR_Y+6,
                          status_text,status_color,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,86);
   ChartRedraw(chart_id);
  }

bool EEA_SymbolPanelInit(const long chart_id,const int sub_window)
  {
   g_panel_state.row_count=0;
   g_panel_state.row_offset=0;
   g_panel_state.status_message="Ready";
   g_panel_state.apply_reason="";
   g_panel_state.committed_policy="UNSELECTED";
   g_panel_state.staged_policy="UNSELECTED";
   g_panel_state.committed_daily_continuation=true;
   g_panel_state.staged_daily_continuation=true;
   g_panel_state.committed_overall_continuation=true;
   g_panel_state.staged_overall_continuation=true;
   g_panel_state.policy_confirmed=false;
   g_panel_state.overlay_open=false;
   g_panel_state.overlay_name="";
   g_panel_state.staged_initialized=false;
   g_panel_state.authorization_utc=0;
   g_panel_state.authorization_input_gmt7="";
   g_panel_state.policy_store_path="EnterpriseEA/current/policy_settings.json";
   g_panel_state.active_view="DASHBOARD";
   g_panel_state.dashboard_tab="OVERVIEW";
   g_panel_state.settings_tab="RISK";
   g_panel_state.collapsed=false;
   g_panel_state.last_click_name="";
   g_panel_state.last_click_tick=0;
   g_panel_state.hover_name="";
   g_panel_state.chart_scroll_captured=false;
   g_panel_state.chart_scroll_original=(bool)ChartGetInteger(chart_id,CHART_MOUSE_SCROLL);
   g_panel_state.chart_mouse_move_original=(bool)ChartGetInteger(chart_id,CHART_EVENT_MOUSE_MOVE);
   g_panel_state.calendar_year=0;
   g_panel_state.calendar_month=0;
   g_panel_state.calendar_selected_day=0;
   g_panel_state.toast_text="";
   g_panel_state.toast_color=EEA_PANEL_MUTED_COLOR;
   g_panel_state.toast_until=0;
   g_panel_state.edit_rendered_value="";
   if(!g_panel_engine.published) EEA_SymbolPanelEngineViewDefaults(g_panel_engine);
   // Hover feedback and chart-scroll suppression need mouse-move events.
   ChartSetInteger(chart_id,CHART_EVENT_MOUSE_MOVE,true);
   EEA_SymbolPanelCreateControls(chart_id,sub_window);
   return true;
  }

void EEA_SymbolPanelRenderSettingsRows(const long chart_id)
  {
   if(g_panel_state.overlay_name!="SETTINGS") return;
   if(g_panel_state.settings_tab!="SYMBOLS") return;
   EEA_SymbolPanelClearSettingsRows(chart_id);
   for(int i=0;i<EEA_PANEL_VISIBLE_ROWS;i++)
     {
      int row_index=g_panel_state.row_offset+i;
      if(row_index>=g_panel_state.row_count) continue;
      string prefix=EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(row_index)+"_";
      int y=EEA_PANEL_SETTINGS_ROWS_Y+i*EEA_PANEL_ROW_HEIGHT;
      bool context_only=g_panel_state.rows[row_index].context_only;
      bool checked=g_panel_state.rows[row_index].checked;
      color stripe=(i%2==0) ? EEA_PANEL_SURFACE_COLOR : EEA_PANEL_STRIPE_COLOR;
      if(context_only)
         EEA_SymbolPanelSetSurface(chart_id,prefix+"Bg",EEA_PANEL_INNER_X+4,y-2,EEA_PANEL_INNER_WIDTH-8,27,stripe,stripe);
      else
         EEA_SymbolPanelSetHotSurface(chart_id,prefix+"Bg",EEA_PANEL_INNER_X+4,y-2,EEA_PANEL_INNER_WIDTH-8,27,stripe,stripe);
      EEA_SymbolPanelSetButtonEx(chart_id,prefix+"Chk",EEA_PANEL_CONTENT_X,y+1,34,21,
                                 context_only ? "N/A" :
                                 (g_panel_state.rows[row_index].checked ? EEA_SymbolPanelGlyph(0x2713) : " "),
                                 context_only ? EEA_PANEL_BUTTON_DISABLED :
                                 (checked ? EEA_PANEL_BUTTON_ON : EEA_PANEL_BUTTON_OFF),EEA_PANEL_META_FONT_SIZE);
      string broker=g_panel_state.rows[row_index].broker_symbol;
      if(broker=="") broker=(g_panel_state.rows[row_index].status=="AVAILABLE" ? "resolves on Apply" : "[UNRESOLVED]");
      color row_color=context_only ? EEA_PANEL_MUTED_COLOR :
                      (checked ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR);
      EEA_SymbolPanelSetText(chart_id,prefix+"Lbl",EEA_PANEL_CONTENT_X+48,y+4,
                             g_panel_state.rows[row_index].canonical_symbol+"   "+EEA_SymbolPanelGlyph(0x2192)+"   "+broker,
                             row_color,EEA_PANEL_BODY_FONT_SIZE);
      ObjectSetInteger(chart_id,prefix+"Lbl",OBJPROP_ZORDER,15);
      string status=g_panel_state.rows[row_index].status;
      color badge_color=context_only ? EEA_PANEL_FAINT_COLOR :
                        status=="RESOLVED" ? EEA_PANEL_OK_COLOR :
                        status=="AVAILABLE" ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_WARNING_COLOR;
      EEA_SymbolPanelSetText(chart_id,prefix+"Badge",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X,y+5,status,badge_color,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_RIGHT_UPPER);
     }
   int first=g_panel_state.row_count==0 ? 0 : g_panel_state.row_offset+1;
   int last=g_panel_state.row_offset+EEA_PANEL_VISIBLE_ROWS<g_panel_state.row_count ?
            g_panel_state.row_offset+EEA_PANEL_VISIBLE_ROWS : g_panel_state.row_count;
   EEA_SymbolPanelSetLabelColor(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RowSummary",EEA_PANEL_CONTENT_X,
                                EEA_PANEL_SETTINGS_SUMMARY_Y,
                                "Showing "+IntegerToString(first)+"-"+IntegerToString(last)+" of "+
                                IntegerToString(g_panel_state.row_count)+" symbols"+EEA_SymbolPanelSep()+
                                "DXY / USDX are CONTEXT ONLY and never tradable",
                                EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelRefresh(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   g_panel_state.chart_id=chart_id;
   // Rows are the configured universe plus the live selection. Staged check marks
   // are carried by canonical name so a refresh never reshuffles operator input.
   EEA_SymbolPanelRow previous[EEA_PANEL_MAX_ROWS];
   int previous_count=g_panel_state.row_count;
   for(int i=0;i<previous_count && i<EEA_PANEL_MAX_ROWS;i++) previous[i]=g_panel_state.rows[i];
   int count=0;
   for(int i=0;i<ctx.symbol_count && i<EEA_PANEL_MAX_ROWS;i++)
     {
      g_panel_state.rows[count].canonical_symbol=ctx.canonical_symbols[i];
      g_panel_state.rows[count].broker_symbol=ctx.broker_symbols[i];
      g_panel_state.rows[count].status=(ctx.broker_symbols[i]!="" ? "RESOLVED" : "UNRESOLVED");
      g_panel_state.rows[count].description="Observer symbol";
      g_panel_state.rows[count].context_only=EEA_SymbolPanelIsContextOnly(g_panel_state.rows[count].canonical_symbol,
                                                                         g_panel_state.rows[count].broker_symbol);
      if(g_panel_state.rows[count].context_only) g_panel_state.rows[count].status="CONTEXT ONLY";
      g_panel_state.rows[count].spec=ctx.symbol_specs[i];
      g_panel_state.rows[count].checked=true;
      count++;
     }
   for(int u=0;u<g_panel_engine.universe_count && u<EEA_PANEL_MAX_ROWS && count<EEA_PANEL_MAX_ROWS;u++)
     {
      string canonical=g_panel_engine.universe[u];
      if(canonical=="" || EEA_SymbolPanelSelectionContains(ctx,canonical)) continue;
      bool duplicate=false;
      for(int k=0;k<count;k++) if(g_panel_state.rows[k].canonical_symbol==canonical) { duplicate=true; break; }
      if(duplicate) continue;
      g_panel_state.rows[count].canonical_symbol=canonical;
      g_panel_state.rows[count].broker_symbol="";
      g_panel_state.rows[count].context_only=EEA_SymbolPanelIsContextOnly(canonical,"");
      g_panel_state.rows[count].status=g_panel_state.rows[count].context_only ? "CONTEXT ONLY" : "AVAILABLE";
      g_panel_state.rows[count].description="Configured, not selected";
      g_panel_state.rows[count].checked=false;
      count++;
     }
   g_panel_state.row_count=count;
   if(g_panel_state.staged_initialized)
      for(int i=0;i<count;i++)
         for(int p=0;p<previous_count && p<EEA_PANEL_MAX_ROWS;p++)
            if(previous[p].canonical_symbol==g_panel_state.rows[i].canonical_symbol)
              { g_panel_state.rows[i].checked=previous[p].checked; break; }
   if(g_panel_state.row_count<=0) g_panel_state.row_offset=0;
   else if(g_panel_state.row_offset>=g_panel_state.row_count)
      g_panel_state.row_offset=((g_panel_state.row_count-1)/EEA_PANEL_VISIBLE_ROWS)*EEA_PANEL_VISIBLE_ROWS;
   if(!g_panel_state.staged_initialized)
      EEA_SymbolPanelLoadPolicy(ctx);
   g_panel_state.staged_initialized=true;
   EEA_SymbolPanelRenderMainView(chart_id,ctx);
   // The first refresh opens the active view; later timer ticks re-render it in
   // place through EEA_SymbolPanelRefreshOpenOverlay.
   if(!g_panel_state.collapsed && !g_panel_state.overlay_open)
     {
      if(g_panel_state.active_view=="SETTINGS") EEA_SymbolPanelRenderSettings(chart_id,ctx);
      else EEA_SymbolPanelRenderDashboard(chart_id,ctx);
     }
   EEA_SymbolPanelRenderSettingsRows(chart_id);
  }

void EEA_SymbolPanelRefreshOpenOverlay(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   if(!g_panel_state.overlay_open) return;
   if(g_panel_state.overlay_name=="DASHBOARD") EEA_SymbolPanelRenderDashboard(chart_id,ctx);
   else if(g_panel_state.overlay_name=="SETTINGS") EEA_SymbolPanelRenderSettings(chart_id,ctx);
  }

void EEA_SymbolPanelLoadPolicy(EEA_ObserverRuntimeContext &ctx)
  {
   EEA_PolicySettings stored;
   if(EEA_PolicySettingsStoreLoad(ctx.root+"/current/policy_settings.json",ctx.config_version,
                                  ctx.account.account_fingerprint,ctx.account.broker_server,stored))
     {
      g_panel_state.committed_policy=stored.committed_policy;
      g_panel_state.staged_policy=stored.proposed_policy;
      g_panel_state.committed_daily_continuation=stored.committed_daily_continuation;
      g_panel_state.staged_daily_continuation=stored.proposed_daily_continuation;
      g_panel_state.committed_overall_continuation=stored.committed_overall_continuation;
      g_panel_state.staged_overall_continuation=stored.proposed_overall_continuation;
      g_panel_state.policy_confirmed=stored.policy_confirmed;
       g_panel_state.authorization_input_gmt7=stored.authorization_input_gmt7;
       g_panel_state.policy_confirmed=stored.policy_confirmed;
       g_panel_state.authorization_input_gmt7=stored.authorization_input_gmt7;
       g_panel_state.authorization_utc=stored.authorization_utc;
     }
  }

bool EEA_SymbolPanelPersistPolicy(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,const bool applied,
                                   EEA_PolicySettings &written)
  {
   EEA_PolicySettings stored;
   EEA_PolicySettingsDefaults(stored);
   EEA_PolicySettings existing;
   bool existing_file=FileIsExist(ctx.root+"/current/policy_settings.json",0);
   bool existing_loaded=EEA_PolicySettingsStoreLoad(ctx.root+"/current/policy_settings.json",ctx.config_version,
      ctx.account.account_fingerprint,ctx.account.broker_server,existing);
   if(existing_file && !existing_loaded)
     {
      ctx.status.runtime_state="BLOCKED";
      ctx.status.reason_code="POLICY_SETTINGS_REVISION_UNAVAILABLE";
      ctx.status.new_entries_blocked=true;
      EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
         ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
      return false;
     }
   stored.config_version=ctx.config_version; stored.account_fingerprint=ctx.account.account_fingerprint;
   stored.broker_server=ctx.account.broker_server; stored.revision=existing_loaded ? existing.revision+1 : 1;
   stored.proposed_policy=g_panel_state.staged_policy; stored.committed_policy=g_panel_state.committed_policy;
    stored.proposed_daily_continuation=g_panel_state.staged_daily_continuation;
    stored.committed_daily_continuation=g_panel_state.committed_daily_continuation;
    stored.proposed_overall_continuation=g_panel_state.staged_overall_continuation;
    stored.committed_overall_continuation=g_panel_state.committed_overall_continuation;
   stored.policy_confirmed=g_panel_state.policy_confirmed;
    stored.authorization_input_gmt7=g_panel_state.authorization_input_gmt7;
    stored.authorization_utc=g_panel_state.authorization_utc;
   if(EEA_PolicySettingsStoreWrite(ctx.root+"/current/policy_settings.json",stored))
     {
      written=stored;
      if(!EEA_SymbolPanelRequirePolicyAudit(ctx,audit,applied ? "POLICY_APPLIED" : "POLICY_PROPOSED",
                                 applied ? "POLICY_APPLY_PERSISTED" : "POLICY_PROPOSAL_PERSISTED",
                                 applied ? stored.committed_policy : stored.proposed_policy,stored.authorization_utc)) return false;
      return true;
     }
   EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                              stored.proposed_policy,stored.authorization_utc);
   return false;
  }

bool EEA_SymbolPanelPersistPolicy(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit,const bool applied)
  {
   EEA_PolicySettings written;
   return EEA_SymbolPanelPersistPolicy(ctx,audit,applied,written);
  }

bool EEA_SymbolPanelVerifyPersistedPolicy(EEA_ObserverRuntimeContext &ctx,const EEA_PolicySettings &expected)
  {
   EEA_PolicySettings stored;
   // EEA_SymbolPanelVerifyPersistedPolicy(ctx,stored) is the persisted-policy verification contract.
   if(!EEA_PolicySettingsStoreLoad(ctx.root+"/current/policy_settings.json",ctx.config_version,
                                  ctx.account.account_fingerprint,ctx.account.broker_server,stored)) return false;
   return stored.revision>0 && (expected.revision<=0 || stored.revision==expected.revision) && stored.committed_policy==expected.committed_policy &&
      stored.proposed_policy==expected.proposed_policy && stored.policy_confirmed==expected.policy_confirmed &&
      stored.authorization_input_gmt7==expected.authorization_input_gmt7 && stored.authorization_utc==expected.authorization_utc &&
      stored.proposed_daily_continuation==expected.proposed_daily_continuation &&
      stored.committed_daily_continuation==expected.committed_daily_continuation &&
      stored.proposed_overall_continuation==expected.proposed_overall_continuation &&
      stored.committed_overall_continuation==expected.committed_overall_continuation;
  }

bool EEA_SymbolPanelRestorePolicyFile(const string path,const string contents,const bool existed)
  {
   if(existed) return EEA_WriteAtomicText(path,contents);
   if(!FileIsExist(path,0)) return true;
   return FileDelete(path,0);
  }

void EEA_SymbolPanelRenderViewBase(const long chart_id)
  {
   int top=EEA_PANEL_HEADER_HEIGHT+EEA_PANEL_TABBAR_HEIGHT;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Surface",0,top,EEA_PANEL_MAIN_WIDTH,
                             EEA_PANEL_STATUSBAR_Y-top,EEA_PANEL_BG_COLOR,EEA_PANEL_BG_COLOR);
  }

void EEA_SymbolPanelRenderSettings(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelBeginOverlay(chart_id,"SETTINGS");
   EEA_SymbolPanelRenderViewBase(chart_id);
   string tabs[4]={"RISK","SYMBOLS","AUTHORIZATION","SYSTEM"};
   string titles[4]={"Risk policy","Symbols","Authorization","System"};
   titles[1]="Symbols  ("+IntegerToString(EEA_SymbolPanelStagedSymbolCount())+")";
   for(int t=0;t<4;t++)
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tab_"+tabs[t],EEA_PANEL_INNER_X+t*134,
                                 EEA_PANEL_VIEW_Y,130,24,titles[t],
                                 g_panel_state.settings_tab==tabs[t] ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,
                                 EEA_PANEL_META_FONT_SIZE);
   if(g_panel_state.settings_tab=="SYMBOLS") EEA_SymbolPanelSettingsSymbols(chart_id,ctx);
   else if(g_panel_state.settings_tab=="AUTHORIZATION") EEA_SymbolPanelSettingsAuthorization(chart_id,ctx);
   else if(g_panel_state.settings_tab=="SYSTEM") EEA_SymbolPanelSettingsSystem(chart_id,ctx);
   else EEA_SymbolPanelSettingsRisk(chart_id,ctx);
   EEA_SymbolPanelSettingsFooter(chart_id,ctx);
   ChartRedraw(chart_id);
  }

void EEA_SymbolPanelSettingsRisk(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"PolicySurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,112,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Policy",EEA_PANEL_CONTENT_X,y+10,
                             "ACCOUNT RISK POLICY");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PolicyHelp",EEA_PANEL_CONTENT_X,y+26,
                          "Selects the equity floors used by the Risk Kernel. Changes stay staged until Apply.",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_1_STEP",EEA_PANEL_CONTENT_X,y+46,166,30,
                              "FTMO 1-Step",g_panel_state.staged_policy=="FTMO_1_STEP" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_2_STEP",EEA_PANEL_CONTENT_X+172,y+46,166,30,
                              "FTMO 2-Step",g_panel_state.staged_policy=="FTMO_2_STEP" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_BALANCE_BASED_FTMO_V1",EEA_PANEL_CONTENT_X+344,y+46,166,30,
                              "Balance based",g_panel_state.staged_policy=="BALANCE_BASED_FTMO_V1" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   bool policy_changed=(g_panel_state.staged_policy!=g_panel_state.committed_policy);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PolicyState",EEA_PANEL_CONTENT_X,y+88,
                          "Committed  "+g_panel_state.committed_policy+EEA_SymbolPanelSep()+
                          "Staged  "+g_panel_state.staged_policy+(policy_changed ? "  (unsaved)" : ""),
                          policy_changed ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);

   int y2=y+120;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"ContinuationSurface",EEA_PANEL_INNER_X,y2,
                             EEA_PANEL_INNER_WIDTH,104,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Continuation",EEA_PANEL_CONTENT_X,y2+10,
                             "PROFIT-TARGET CONTINUATION");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_DailyTitle",EEA_PANEL_CONTENT_X,y2+30,
                          "Daily profit target",EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_DailyHelp",EEA_PANEL_CONTENT_X,y2+46,
                          "Keep evaluating entries after the daily target is reached",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonState(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_DailyContinuation",
                                 EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-150,y2+30,150,
                                 g_panel_state.staged_daily_continuation ? "Daily target  ON" : "Daily target  OFF",
                                 g_panel_state.staged_daily_continuation);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_OverallTitle",EEA_PANEL_CONTENT_X,y2+66,
                          "Overall profit target",EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_OverallHelp",EEA_PANEL_CONTENT_X,y2+82,
                          "Keep evaluating entries after the overall target is reached",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonState(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_OverallContinuation",
                                 EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-150,y2+66,150,
                                 g_panel_state.staged_overall_continuation ? "Overall target  ON" : "Overall target  OFF",
                                 g_panel_state.staged_overall_continuation);

   int y3=y2+112;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"ConfirmSurface",EEA_PANEL_INNER_X,y3,
                             EEA_PANEL_INNER_WIDTH,88,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Confirm",EEA_PANEL_CONTENT_X,
                             y3+10,"EXPLICIT CONFIRMATION");
   EEA_SymbolPanelSetButtonState(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_ConfirmPolicy",EEA_PANEL_CONTENT_X,y3+28,140,
                                 g_panel_state.policy_confirmed ? "Confirmed" : "Confirm policy",
                                 g_panel_state.policy_confirmed);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ConfirmText",EEA_PANEL_CONTENT_X+152,y3+29,
                          "The staged policy matches this account's prop-firm terms.",
                          EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ConfirmServer",EEA_PANEL_CONTENT_X+152,y3+45,
                          "Server  "+ctx.account.broker_server+EEA_SymbolPanelSep()+ctx.account.account_currency+
                          EEA_SymbolPanelSep()+ctx.account.account_margin_mode,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,58);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ConfirmNote",EEA_PANEL_CONTENT_X,y3+66,
                          "Continuation never overrides loss floors, exposure, margin, kill switch or EXECUTION_UNKNOWN.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelSettingsSymbols(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"SelectionSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,EEA_PANEL_FOOTER_Y-y-8,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PersistenceStatus",EEA_PANEL_CONTENT_X,y+12,
                             "TRADING SYMBOLS"+EEA_SymbolPanelSep()+IntegerToString(EEA_SymbolPanelStagedSymbolCount())+
                             " selected");
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_SelectAll",300,y+6,56,24,"All",
                              EEA_PANEL_BUTTON_GHOST,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_SelectNone",362,y+6,56,24,"None",
                              EEA_PANEL_BUTTON_GHOST,EEA_PANEL_META_FONT_SIZE);
   bool can_previous=g_panel_state.row_offset>0;
   bool can_next=g_panel_state.row_offset+EEA_PANEL_VISIBLE_ROWS<g_panel_state.row_count;
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_PreviousRows",424,y+6,58,24,
                              EEA_SymbolPanelGlyph(0x2039)+" Prev",
                              can_previous ? EEA_PANEL_BUTTON_SECONDARY : EEA_PANEL_BUTTON_DISABLED,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_NextRows",488,y+6,58,24,
                              "Next "+EEA_SymbolPanelGlyph(0x203A),
                              can_next ? EEA_PANEL_BUTTON_SECONDARY : EEA_PANEL_BUTTON_DISABLED,EEA_PANEL_META_FONT_SIZE);
   if(g_panel_state.row_count==0)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NoSymbols",EEA_PANEL_CONTENT_X,
                             EEA_PANEL_SETTINGS_ROWS_Y+8,"No configured symbols. Set InpCanonicalSymbols in the EA inputs.",
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
   EEA_SymbolPanelRenderSettingsRows(chart_id);
  }

void EEA_SymbolPanelSettingsAuthorization(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"AuthorizationSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,180,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Time",EEA_PANEL_CONTENT_X,y+10,
                             "AUTHORIZATION WINDOW"+EEA_SymbolPanelSep()+"GMT+7");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TimeHelp",EEA_PANEL_CONTENT_X,y+26,
                          "Enter the operator's local GMT+7 start time. The EA stores and compares UTC only.",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TimeField",EEA_PANEL_CONTENT_X,y+52,
                          "Start time  (YYYY-MM-DD HH:MM)",EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetEdit(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Edit_AuthorizationGmt7",EEA_PANEL_CONTENT_X,y+70,220,
                          g_panel_state.authorization_input_gmt7);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Utc",EEA_PANEL_CONTENT_X+236,y+77,
                          EEA_SymbolPanelGlyph(0x2192)+"  UTC  "+EEA_SymbolPanelReadableUtc(g_panel_state.authorization_utc),
                          g_panel_state.authorization_utc>0 ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR,
                          EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_MONO);
   string hint="Type a time, then press Enter to validate.";
   color hint_color=EEA_PANEL_MUTED_COLOR;
   if(g_panel_state.apply_reason=="INVALID_GMT_PLUS_7_DATETIME")
     { hint="Invalid time. Use YYYY-MM-DD HH:MM, for example 2026-10-03 14:30."; hint_color=EEA_PANEL_DANGER_COLOR; }
   else if(g_panel_state.authorization_utc>0)
     { hint=EEA_SymbolPanelGlyph(0x2713)+"  Validated and stored as a proposal."; hint_color=EEA_PANEL_OK_COLOR; }
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TimeHint",EEA_PANEL_CONTENT_X,y+110,hint,hint_color,
                          EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TimeNote",EEA_PANEL_CONTENT_X,y+140,
                          "This time feeds the live authorization document as a proposal; it never authorizes execution.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelSettingsSystem(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"SystemSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,236,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_System",EEA_PANEL_CONTENT_X,y+10,
                             "RUNTIME CONFIGURATION"+EEA_SymbolPanelSep()+"READ-ONLY");
   int left=EEA_PANEL_CONTENT_X, right=EEA_PANEL_CONTENT_X+264;
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Root",left,y+32,"Data root",ctx.root,EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Config",right,y+32,"Config version",ctx.config_version,
                           EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Refresh",left,y+68,"Refresh interval",
                           IntegerToString(ctx.refresh_seconds)+" s",EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Lookback",right,y+68,"History lookback",
                           IntegerToString(ctx.history_lookback_days)+" days",EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Observer",left,y+104,"Observer only",
                           g_panel_engine.observer_only ? "YES" : "NO",
                           g_panel_engine.observer_only ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Execution",right,y+104,"Execution / armed",
                           (g_panel_engine.execution_enabled ? "ENABLED" : "EXECUTION_DISABLED")+
                           (g_panel_engine.live_armed ? " / ARMED" : " / not armed"),
                           g_panel_engine.execution_enabled ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Strategy",left,y+140,"Strategy runtime (S02)",
                           g_panel_engine.strategy_enabled ? "ENABLED" : "DISABLED",
                           g_panel_engine.strategy_enabled ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_StrategyReason",right,y+140,"Strategy reason",
                           g_panel_engine.strategy_reason=="" ? "--" : g_panel_engine.strategy_reason,EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SystemNote",EEA_PANEL_CONTENT_X,y+186,
                          "Change these through the EA Inputs dialog (F7). Reloading re-runs every startup gate.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SystemNote2",EEA_PANEL_CONTENT_X,y+202,
                          "Panel: click once to act; double-clicks are ignored; chart scrolling pauses over the panel.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelSettingsFooter(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_FOOTER_Y;
   int pending=EEA_SymbolPanelPendingChanges(ctx);
   int selected=EEA_SymbolPanelStagedSymbolCount();
   bool needs_confirmation=(g_panel_state.staged_policy!="UNSELECTED" && !g_panel_state.policy_confirmed);
   bool ready=(pending>0 && selected>0 && !needs_confirmation);
   string hint=pending==0 ? "Changes stay staged here until you apply or discard them." :
               selected==0 ? "Select at least one tradable symbol before applying." :
               needs_confirmation ? "Confirm the staged policy on the Risk policy tab to enable Apply." :
               "Apply re-reconciles the account, then persists and audits the proposal.";
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"FooterSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,86,EEA_PANEL_SURFACE_COLOR,
                             pending>0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_BORDER_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Pending",EEA_PANEL_CONTENT_X,y+14,
                          pending>0 ? IntegerToString(pending)+(pending==1 ? " unsaved change" : " unsaved changes") :
                          "No unsaved changes",pending>0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,
                          EEA_PANEL_BODY_FONT_SIZE+1,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_ResetStaged",296,y+10,104,30,"Discard",
                              pending>0 ? EEA_PANEL_BUTTON_SECONDARY : EEA_PANEL_BUTTON_DISABLED);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Apply",408,y+10,128,30,"Apply changes",
                              ready ? EEA_PANEL_BUTTON_PRIMARY : EEA_PANEL_BUTTON_DISABLED);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ApplyHint",EEA_PANEL_CONTENT_X,y+46,hint,
                          needs_confirmation && pending>0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,
                          EEA_PANEL_META_FONT_SIZE);
   bool failed=StringFind(g_panel_state.status_message,"FAILED")==0;
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ApplyStatus",EEA_PANEL_CONTENT_X,y+64,
                          "Apply status  "+(g_panel_state.status_message=="" ? "READY" : g_panel_state.status_message),
                          failed ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,
                          EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,44);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ApplyReason",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X,y+64,
                          "Reason  "+(g_panel_state.apply_reason=="" ? "NONE" : g_panel_state.apply_reason),
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_RIGHT_UPPER,46);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Safety",EEA_PANEL_CONTENT_X,EEA_PANEL_SETTINGS_SAFETY_Y,
                          "Safety  EXECUTION_DISABLED  |  NOT_AUTHORIZED  |  "+EEA_PANEL_POLICY_PROPOSAL_ONLY+
                          "  |  proposal only; no execution",
                          EEA_PANEL_WARNING_COLOR,7);
  }

void EEA_SymbolPanelRenderDashboard(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelBeginOverlay(chart_id,"DASHBOARD");
   EEA_SymbolPanelRenderViewBase(chart_id);
   string tabs[7]={"OVERVIEW","MARKET","TRADES","RISK","NEWS","AI","CALENDAR"};
   string titles[7]={"Overview","Market","Trades","Risk","News","AI","Calendar"};
   for(int t=0;t<7;t++)
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tab_"+tabs[t],EEA_PANEL_INNER_X+t*77,
                                 EEA_PANEL_VIEW_Y,73,24,titles[t],
                                 g_panel_state.dashboard_tab==tabs[t] ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,
                                 EEA_PANEL_META_FONT_SIZE);
   if(g_panel_state.dashboard_tab=="MARKET") EEA_SymbolPanelDashMarket(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="TRADES") EEA_SymbolPanelDashTrades(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="RISK") EEA_SymbolPanelDashRisk(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="NEWS")
      EEA_SymbolPanelDashPlaceholder(chart_id,"NEWS CENTER","NEWS_UNKNOWN","Not built yet  "+EEA_SymbolPanelGlyph(0x00B7)+"  spec section 7, Phase 6",
         "No calendar feed is connected, so news state is UNKNOWN and is never treated as NORMAL.",
         "Planned: PRE NEWS / NEWS ACTIVE / POST NEWS countdown, impact, actual vs forecast,",
         "affected symbols and the entry policy applied to each setup.");
   else if(g_panel_state.dashboard_tab=="AI")
      EEA_SymbolPanelDashPlaceholder(chart_id,"MCP AI BRIDGE","OFFLINE","Not built yet  "+EEA_SymbolPanelGlyph(0x00B7)+"  spec section 8, Phase 7",
         "Deterministic EA logic runs without AI; nothing waits on a provider.",
         "Planned: provider, last review, warnings with TTL, ASK AI / REFRESH / DETAIL.",
         "AI may report, warn or recommend reducing risk only. It never sends orders.");
   else if(g_panel_state.dashboard_tab=="CALENDAR") EEA_SymbolPanelDashCalendar(chart_id,ctx);
   else EEA_SymbolPanelDashOverview(chart_id,ctx);
   ChartRedraw(chart_id);
  }

double EEA_SymbolPanelRealizedForDay(const EEA_ObserverRuntimeContext &ctx,const long day_index)
  {
   double total=0.0;
   for(int i=0;i<ctx.reconciliation.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      // Only buy/sell deals are trading P/L; balance, credit and other cash flows are excluded.
      if(ctx.reconciliation.deals[i].type!="0" && ctx.reconciliation.deals[i].type!="1") continue;
      if(ctx.reconciliation.deals[i].time_utc/86400!=day_index) continue;
      total+=ctx.reconciliation.deals[i].profit+ctx.reconciliation.deals[i].commission+
             ctx.reconciliation.deals[i].swap+ctx.reconciliation.deals[i].fee;
     }
   return total;
  }

void EEA_SymbolPanelDashOverview(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   string ccy=ctx.account.account_currency;
   double floating=ctx.account.equity-ctx.account.balance;
   double margin_level=ctx.account.margin>0.0 ? ctx.account.equity/ctx.account.margin*100.0 : 0.0;
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Equity",EEA_PANEL_INNER_X,y,128,"EQUITY",
                          EEA_SymbolPanelFormatNumber(ctx.account.equity,2),EEA_PANEL_TEXT_COLOR,ccy);
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Balance",EEA_PANEL_INNER_X+136,y,128,"BALANCE",
                          EEA_SymbolPanelFormatNumber(ctx.account.balance,2),EEA_PANEL_TEXT_COLOR,ccy);
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Floating",EEA_PANEL_INNER_X+272,y,128,"FLOATING P/L",
                          EEA_SymbolPanelSigned(floating,2),EEA_SymbolPanelPnlColor(floating),"equity - balance");
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_FreeMargin",EEA_PANEL_INNER_X+408,y,128,"FREE MARGIN",
                          EEA_SymbolPanelFormatNumber(ctx.account.margin_free,2),EEA_PANEL_TEXT_COLOR,
                          margin_level>0.0 ? "margin level "+DoubleToString(margin_level,0)+"%" : "no margin used");
   double today=EEA_SymbolPanelRealizedForDay(ctx,(long)TimeGMT()/86400);
   int resolved=0;
   for(int i=0;i<ctx.symbol_count;i++) if(ctx.broker_symbols[i]!="") resolved++;
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Today",EEA_PANEL_INNER_X,y+68,128,"TODAY P/L",
                          EEA_SymbolPanelSigned(today,2),EEA_SymbolPanelPnlColor(today),"UTC day, realized");
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_ActiveRisk",EEA_PANEL_INNER_X+136,y+68,128,"ACTIVE RISK",
                          "--",EEA_PANEL_MUTED_COLOR,"Risk Kernel not wired");
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Book",EEA_PANEL_INNER_X+272,y+68,128,"POSITIONS / ORDERS",
                          IntegerToString(ctx.reconciliation.position_count)+" / "+IntegerToString(ctx.reconciliation.order_count),
                          EEA_PANEL_TEXT_COLOR,IntegerToString(ctx.reconciliation.deal_count)+" deals loaded");
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Symbols",EEA_PANEL_INNER_X+408,y+68,128,"SYMBOLS",
                          IntegerToString(ctx.symbol_count),EEA_PANEL_TEXT_COLOR,IntegerToString(resolved)+" resolved");

   int s=y+136;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"StatusSurface",EEA_PANEL_INNER_X,s,
                             EEA_PANEL_INNER_WIDTH,164,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_StatusTitle",EEA_PANEL_CONTENT_X,s+10,"SYSTEM STATUS");
   int left=EEA_PANEL_CONTENT_X, right=EEA_PANEL_CONTENT_X+264;
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Runtime",left,s+28,"Runtime",
                           ctx.status.runtime_state,EEA_SymbolPanelStatusColor(ctx.status.runtime_state));
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Reason",right,s+28,"Reason",
                           ctx.status.reason_code,EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Entries",left,s+60,"New entries (new_entries_blocked)",
                           ctx.status.new_entries_blocked ? "BLOCKED" : "REVIEW",
                           ctx.status.new_entries_blocked ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_WARNING_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Execution",right,s+60,"Execution",
                           g_panel_engine.execution_enabled ? (g_panel_engine.live_armed ? "ENABLED / ARMED" : "ENABLED") :
                           "EXECUTION_DISABLED",
                           g_panel_engine.execution_enabled ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR);
   bool live_gated=g_panel_engine.execution_enabled && g_panel_engine.live_armed &&
                   g_panel_engine.controller_allows_market && !g_panel_engine.recovery_blocked;
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Live",left,s+92,"Live authorization",
                           live_gated ? "GATED (per-intent check)" : "NOT_AUTHORIZED",
                           live_gated ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_DANGER_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Kill",right,s+92,"Kill switch / controller",
                           (g_panel_engine.controller_kill_active ? "ACTIVE" : "RELEASED")+
                           "  ("+g_panel_engine.controller_status+")"+
                           (g_panel_engine.recovery_blocked ? "  RECOVERY BLOCKED" : ""),
                           g_panel_engine.controller_kill_active || g_panel_engine.recovery_blocked ?
                           EEA_PANEL_DANGER_COLOR : EEA_PANEL_WARNING_COLOR,40);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Strategy",left,s+124,"Strategy S02",
                           g_panel_engine.strategy_enabled ? "ENABLED" : "DISABLED",
                           g_panel_engine.strategy_enabled ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_External",right,s+124,"AI bridge / News center",
                           "OFFLINE / UNKNOWN  (not built)",EEA_PANEL_MUTED_COLOR);

   int e=s+172;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"EvidenceSurface",EEA_PANEL_INNER_X,e,
                             EEA_PANEL_INNER_WIDTH,96,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_EvidenceTitle",EEA_PANEL_CONTENT_X,e+10,
                             "EVIDENCE"+EEA_SymbolPanelSep()+"Evidence freshness:");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Freshness",EEA_PANEL_CONTENT_X,e+28,
                          "observed_at_utc  "+EEA_SymbolPanelReadableUtc(ctx.reconciliation.observed_at_utc)+
                          "     valid_until_utc  "+EEA_SymbolPanelReadableUtc(ctx.reconciliation.valid_until_utc),
                          EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Watermark",EEA_PANEL_CONTENT_X,e+44,
                          "Deal watermark:  "+IntegerToString(ctx.reconciliation.deal_watermark)+EEA_SymbolPanelSep()+
                          "Watermark time:  "+IntegerToString(ctx.reconciliation.deal_watermark_time_msc),
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Counts",EEA_PANEL_CONTENT_X,e+60,
                          "POSITIONS "+IntegerToString(ctx.reconciliation.position_count)+EEA_SymbolPanelSep()+
                          "ORDERS "+IntegerToString(ctx.reconciliation.order_count)+EEA_SymbolPanelSep()+
                          "DEALS "+IntegerToString(ctx.reconciliation.deal_count)+EEA_SymbolPanelSep()+
                          "history "+IntegerToString(ctx.history_lookback_days)+"d",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RefreshMeta",EEA_PANEL_CONTENT_X,e+76,
                          "Refresh seq "+IntegerToString(ctx.status.refresh_sequence)+EEA_SymbolPanelSep()+
                          "ok "+IntegerToString(ctx.status.refresh_success_count)+EEA_SymbolPanelSep()+
                          "fail "+IntegerToString(ctx.status.refresh_failure_count)+EEA_SymbolPanelSep()+
                          "last "+IntegerToString(ctx.status.last_refresh_duration_ms)+" ms"+EEA_SymbolPanelSep()+
                          "max "+IntegerToString(ctx.status.max_refresh_duration_ms)+" ms",
                          ctx.status.refresh_failure_count>0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
  }

void EEA_SymbolPanelTableHeader(const long chart_id,const int y,const string &labels[],const int &xs[],
                                const bool &right_aligned[],const int count)
  {
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"TableHead",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,24,EEA_PANEL_SURFACE_ALT_COLOR,EEA_PANEL_SURFACE_ALT_COLOR);
   for(int c=0;c<count;c++)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"TableHead_"+IntegerToString(c),xs[c],y+6,labels[c],
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,
                             right_aligned[c] ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
  }

void EEA_SymbolPanelTableRowBase(const long chart_id,const int index,const int y)
  {
   color stripe=(index%2==0) ? EEA_PANEL_SURFACE_COLOR : EEA_PANEL_STRIPE_COLOR;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(index)+"_Bg",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,EEA_PANEL_TABLE_ROW_HEIGHT,stripe,stripe);
  }

void EEA_SymbolPanelDashMarket(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SymbolTitle",EEA_PANEL_CONTENT_X,y,
                             "SELECTED SYMBOLS"+EEA_SymbolPanelSep()+"Digits: price precision"+EEA_SymbolPanelSep()+
                             "Trade mode: broker capability");
   string labels[6]={"Symbol","Broker","Status","Digits","Trade mode","S02 setup"};
   int xs[6]={24,104,214,330,352,452};
   bool right[6]={false,false,false,true,false,false};
   EEA_SymbolPanelTableHeader(chart_id,y+20,labels,xs,right,6);
   EEA_SymbolPanelClearDashboardRows(chart_id);
   int line=0;
   for(int i=0;i<ctx.symbol_count && line<EEA_PANEL_TABLE_ROWS;i++)
     {
      EEA_ObserverPanelMarketRow row=EEA_ObserverPanelMarketRowFromRuntime(ctx,i);
      int ry=y+46+line*EEA_PANEL_TABLE_ROW_HEIGHT;
      string n=EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(line);
      EEA_SymbolPanelTableRowBase(chart_id,line,ry);
      color text_color=row.context_only ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_TEXT_COLOR;
      color status_color=row.context_only ? EEA_PANEL_FAINT_COLOR :
                         row.status=="RESOLVED" ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR;
      EEA_SymbolPanelSetText(chart_id,n,24,ry+6,row.canonical,text_color,EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_b",104,ry+6,row.broker=="" ? "--" : row.broker,text_color,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_LEFT_UPPER,16);
      EEA_SymbolPanelSetText(chart_id,n+"_s",214,ry+6,row.status,status_color,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_d",330,ry+6,IntegerToString(row.digits),text_color,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_m",352,ry+6,row.trade_mode,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,16);
      string setup=row.context_only ? "--" : EEA_SymbolPanelSetupState(row.canonical);
      EEA_SymbolPanelSetText(chart_id,n+"_u",452,ry+6,setup,
                             setup=="OFF" || setup=="--" || setup=="IDLE" ? EEA_PANEL_FAINT_COLOR : EEA_PANEL_ACCENT_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,16);
      line++;
     }
   string dxy_broker="";
   int total=SymbolsTotal(false);
   for(int k=0;k<total;k++)
     {
      string candidate=SymbolName(k,false);
      if(EEA_TrimUpper(candidate)=="USDX." || EEA_TrimUpper(candidate)=="USDX")
        { dxy_broker=candidate; break; }
     }
   if(dxy_broker!="" && line<EEA_PANEL_TABLE_ROWS)
     {
      int ry=y+46+line*EEA_PANEL_TABLE_ROW_HEIGHT;
      string n=EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(line);
      EEA_SymbolPanelTableRowBase(chart_id,line,ry);
      EEA_SymbolPanelSetText(chart_id,n,24,ry+6,"DXY",EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_b",104,ry+6,dxy_broker,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_MONO);
      EEA_SymbolPanelSetText(chart_id,n+"_s",214,ry+6,"CONTEXT ONLY",EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_BOLD);
      line++;
     }
   if(line==0)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_Empty",EEA_PANEL_CONTENT_X,y+56,
                             "No symbols selected. Choose them in Settings "+EEA_SymbolPanelGlyph(0x203A)+" Symbols.",
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
  }

int EEA_SymbolPanelDigitsForBroker(const EEA_ObserverRuntimeContext &ctx,const string broker)
  {
   for(int i=0;i<ctx.symbol_count;i++)
      if(ctx.broker_symbols[i]==broker && ctx.symbol_specs[i].digits>0) return ctx.symbol_specs[i].digits;
   return 5;
  }

void EEA_SymbolPanelDashTrades(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TradesTitle",EEA_PANEL_CONTENT_X,y,
                             "OPEN POSITIONS  ("+IntegerToString(ctx.reconciliation.position_count)+")"+
                             EEA_SymbolPanelSep()+"PENDING ORDERS  ("+IntegerToString(ctx.reconciliation.order_count)+")");
   string labels[8]={"Symbol","Side","Volume","Open","Current","SL","TP","P/L"};
   int xs[8]={24,112,206,284,360,424,486,540};
   bool right[8]={false,false,true,true,true,true,true,true};
   EEA_SymbolPanelTableHeader(chart_id,y+20,labels,xs,right,8);
   EEA_SymbolPanelClearDashboardRows(chart_id);
   double floating=0.0;
   int shown=0;
   for(int i=0;i<ctx.reconciliation.position_count && i<EEA_RUNTIME_MAX_POSITIONS;i++)
     {
      double pnl=ctx.reconciliation.positions[i].profit+ctx.reconciliation.positions[i].swap;
      floating+=pnl;
      if(shown>=11) continue;
      int ry=y+46+shown*EEA_PANEL_TABLE_ROW_HEIGHT;
      string n=EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(shown);
      int digits=EEA_SymbolPanelDigitsForBroker(ctx,ctx.reconciliation.positions[i].symbol);
      bool buy=ctx.reconciliation.positions[i].type=="0";
      EEA_SymbolPanelTableRowBase(chart_id,shown,ry);
      EEA_SymbolPanelSetText(chart_id,n,24,ry+6,ctx.reconciliation.positions[i].symbol,EEA_PANEL_TEXT_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,13);
      EEA_SymbolPanelSetText(chart_id,n+"_side",112,ry+6,buy ? "BUY" : "SELL",
                             buy ? EEA_PANEL_OK_COLOR : EEA_PANEL_DANGER_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_vol",206,ry+6,DoubleToString(ctx.reconciliation.positions[i].volume,2),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_open",284,ry+6,DoubleToString(ctx.reconciliation.positions[i].price_open,digits),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_cur",360,ry+6,DoubleToString(ctx.reconciliation.positions[i].current_price,digits),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      double sl=ctx.reconciliation.positions[i].sl, tp=ctx.reconciliation.positions[i].tp;
      EEA_SymbolPanelSetText(chart_id,n+"_sl",424,ry+6,sl>0.0 ? DoubleToString(sl,digits) : "none",
                             sl>0.0 ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_WARNING_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_tp",486,ry+6,tp>0.0 ? DoubleToString(tp,digits) : "none",EEA_PANEL_MUTED_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_pnl",540,ry+6,EEA_SymbolPanelSigned(pnl,2),EEA_SymbolPanelPnlColor(pnl),
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      shown++;
     }
   int after=y+46+(shown>0 ? shown : 1)*EEA_PANEL_TABLE_ROW_HEIGHT+8;
   if(shown==0)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_Empty",EEA_PANEL_CONTENT_X,y+52,
                             "No open positions on this account.",EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
   else
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_Total",540,after,
                             "Floating (profit + swap)  "+EEA_SymbolPanelSigned(floating,2)+" "+ctx.account.account_currency+
                             (ctx.reconciliation.position_count>shown ? "   "+EEA_SymbolPanelGlyph(0x00B7)+"   +"+
                             IntegerToString(ctx.reconciliation.position_count-shown)+" more" : ""),
                             EEA_SymbolPanelPnlColor(floating),EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_RIGHT_UPPER);
   int note=EEA_PANEL_STATUSBAR_Y-74;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"ActionsSurface",EEA_PANEL_INNER_X,note,
                             EEA_PANEL_INNER_WIDTH,64,EEA_PANEL_SURFACE_COLOR,EEA_PANEL_WARNING_FILL_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ActionsTitle",EEA_PANEL_CONTENT_X,note+10,
                             "MANUAL ACTIONS  "+EEA_SymbolPanelGlyph(0x00B7)+"  CLOSE / PARTIAL / BE / TRAIL");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ActionsText",EEA_PANEL_CONTENT_X,note+28,
                          "Spec 9.2 requires confirm "+EEA_SymbolPanelGlyph(0x2192)+" command queue "+EEA_SymbolPanelGlyph(0x2192)+
                          " engine validation "+EEA_SymbolPanelGlyph(0x2192)+" broker result for every action.",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ActionsText2",EEA_PANEL_CONTENT_X,note+44,
                          "That queue is not built yet, so this view is read-only by design.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelDashRisk(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"RiskSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,140,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RiskTitle",EEA_PANEL_CONTENT_X,y+10,"RISK POLICY");
   int left=EEA_PANEL_CONTENT_X, right=EEA_PANEL_CONTENT_X+264;
   bool selected=g_panel_state.committed_policy!="UNSELECTED";
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Policy",left,y+30,"Risk policy:",
                           g_panel_state.committed_policy+(selected && g_panel_state.policy_confirmed ? "  (confirmed)" : ""),
                           selected ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_WARNING_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Headroom",right,y+30,"Headroom:",
                           "unavailable",EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Daily",left,y+64,"Daily target continuation",
                           g_panel_state.committed_daily_continuation ? "ON" : "OFF",EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Overall",right,y+64,"Overall target continuation",
                           g_panel_state.committed_overall_continuation ? "ON" : "OFF",EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Active",left,y+98,"Active risk / open risk",
                           "unavailable",EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Floors",right,y+98,"Daily / overall equity floor",
                           "unavailable",EEA_PANEL_MUTED_COLOR);

   int a=y+148;
   double floating=ctx.account.equity-ctx.account.balance;
   double margin_level=ctx.account.margin>0.0 ? ctx.account.equity/ctx.account.margin*100.0 : 0.0;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"ExposureSurface",EEA_PANEL_INNER_X,a,
                             EEA_PANEL_INNER_WIDTH,108,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ExposureTitle",EEA_PANEL_CONTENT_X,a+10,
                             "ACCOUNT"+EEA_SymbolPanelSep()+"broker-reported");
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Margin",left,a+30,"Margin used",
                           EEA_SymbolPanelFormatNumber(ctx.account.margin,2)+" "+ctx.account.account_currency,EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Level",right,a+30,"Margin level",
                           margin_level>0.0 ? DoubleToString(margin_level,1)+"%" : "no margin used",EEA_PANEL_TEXT_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Floating",left,a+64,"Floating P/L",
                           EEA_SymbolPanelSigned(floating,2),EEA_SymbolPanelPnlColor(floating));
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Rk_Mode",right,a+64,"Margin mode",
                           ctx.account.account_margin_mode,EEA_PANEL_TEXT_COLOR);

   int w=a+116;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"WhySurface",EEA_PANEL_INNER_X,w,
                             EEA_PANEL_INNER_WIDTH,EEA_PANEL_STATUSBAR_Y-w-10,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_WhyTitle",EEA_PANEL_CONTENT_X,w+10,
                             "WHY SOME VALUES ARE UNAVAILABLE");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Why1",EEA_PANEL_CONTENT_X,w+28,
                          "Active risk, FTMO floors and headroom come only from the Risk Kernel (spec 5, appendix B).",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Why2",EEA_PANEL_CONTENT_X,w+44,
                          "They appear once a policy is committed and daily reset snapshots exist; the dashboard",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Why3",EEA_PANEL_CONTENT_X,w+60,
                          "never recomputes them itself, so it cannot disagree with the kernel (TC-026).",
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelDashPlaceholder(const long chart_id,const string title,const string state,const string subtitle,
                                    const string line1,const string line2,const string line3)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"PlaceholderSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,176,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PlaceholderTitle",EEA_PANEL_CONTENT_X,y+14,title,
                          EEA_PANEL_TEXT_COLOR,EEA_PANEL_TITLE_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetPill(chart_id,EEA_PANEL_OVERLAY_PREFIX+"PlaceholderPill",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-128,y+14,
                          128,state,EEA_PANEL_WARNING_FILL_COLOR,EEA_PANEL_WARNING_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PlaceholderSub",EEA_PANEL_CONTENT_X,y+40,subtitle,
                          EEA_PANEL_ACCENT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Placeholder1",EEA_PANEL_CONTENT_X,y+72,line1,
                          EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Placeholder2",EEA_PANEL_CONTENT_X,y+100,line2,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Placeholder3",EEA_PANEL_CONTENT_X,y+116,line3,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

string EEA_SymbolPanelMonthName(const int month)
  {
   string names[12]={"January","February","March","April","May","June","July","August",
                     "September","October","November","December"};
   return month>=1 && month<=12 ? names[month-1] : "";
  }

void EEA_SymbolPanelDashCalendar(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   MqlDateTime now;
   TimeToStruct(TimeGMT(),now);
   if(g_panel_state.calendar_year<=0) { g_panel_state.calendar_year=now.year; g_panel_state.calendar_month=now.mon; }
   int year=g_panel_state.calendar_year, month=g_panel_state.calendar_month;
   int next_year=month==12 ? year+1 : year, next_month=month==12 ? 1 : month+1;
   long first_day=EEA_SymbolPanelDaysFromCivil(year,month,1);
   int days_in_month=(int)(EEA_SymbolPanelDaysFromCivil(next_year,next_month,1)-first_day);
   int first_weekday=(int)((first_day+3)%7); // Monday = 0; 1970-01-01 was a Thursday.
   long today=(long)TimeGMT()/86400;
   long loaded_from=ctx.reconciliation.history_from_utc>0 ? ctx.reconciliation.history_from_utc/86400 : today;

   double net[32]; int trades[32]; int wins[32]; int losses[32]; double gross_profit[32]; double gross_loss[32]; bool active[32];
   for(int d=0;d<32;d++) { net[d]=0.0; trades[d]=0; wins[d]=0; losses[d]=0; gross_profit[d]=0.0; gross_loss[d]=0.0; active[d]=false; }
   for(int i=0;i<ctx.reconciliation.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      if(ctx.reconciliation.deals[i].type!="0" && ctx.reconciliation.deals[i].type!="1") continue;
      long day_index=ctx.reconciliation.deals[i].time_utc/86400;
      if(day_index<first_day || day_index>=first_day+days_in_month) continue;
      int d=(int)(day_index-first_day)+1;
      double value=ctx.reconciliation.deals[i].profit+ctx.reconciliation.deals[i].commission+
                   ctx.reconciliation.deals[i].swap+ctx.reconciliation.deals[i].fee;
      net[d]+=value; active[d]=true;
      string entry=ctx.reconciliation.deals[i].entry;
      if(entry=="1" || entry=="2" || entry=="3")
        {
         trades[d]++;
         if(value>=0.0) { wins[d]++; gross_profit[d]+=value; }
         else { losses[d]++; gross_loss[d]+=value; }
        }
     }

   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_CalPrev",EEA_PANEL_INNER_X,y,32,24,
                              EEA_SymbolPanelGlyph(0x2039),EEA_PANEL_BUTTON_SECONDARY,11);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalMonth",EEA_PANEL_MAIN_WIDTH/2,y+3,
                          EEA_SymbolPanelMonthName(month)+" "+IntegerToString(year),EEA_PANEL_TEXT_COLOR,
                          EEA_PANEL_TITLE_FONT_SIZE-1,EEA_PANEL_FONT_BOLD,ANCHOR_UPPER);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_CalNext",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_INNER_X-32,y,32,24,
                              EEA_SymbolPanelGlyph(0x203A),EEA_PANEL_BUTTON_SECONDARY,11);
   string weekdays[7]={"Mon","Tue","Wed","Thu","Fri","Sat","Sun"};
   for(int c=0;c<7;c++)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalWd"+IntegerToString(c),EEA_PANEL_INNER_X+c*76+37,y+32,
                             weekdays[c],EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_UPPER);
   int grid_y=y+50;
   double month_net=0.0; int month_trades=0, green=0, red=0, trading_days=0;
   for(int cell=0;cell<42;cell++)
     {
      int day=cell-first_weekday+1;
      int cx=EEA_PANEL_INNER_X+(cell%7)*76, cy=grid_y+(cell/7)*42;
      if(day<1 || day>days_in_month)
        {
         EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Cal_X"+IntegerToString(cell),cx,cy,74,40,
                                   EEA_PANEL_BG_COLOR,EEA_PANEL_STRIPE_COLOR);
         continue;
        }
      long day_index=first_day+day-1;
      bool loaded=(day_index>=loaded_from && day_index<=today);
      bool selected=(day==g_panel_state.calendar_selected_day);
      color fill=EEA_PANEL_SURFACE_COLOR;
      if(!loaded) fill=EEA_PANEL_STRIPE_COLOR;
      else if(active[day] && net[day]>0.0) fill=EEA_PANEL_OK_FILL_COLOR;
      else if(active[day] && net[day]<0.0) fill=EEA_PANEL_DANGER_FILL_COLOR;
      color border=selected ? EEA_PANEL_ACCENT_COLOR : (day_index==today ? EEA_PANEL_ACCENT_FILL_COLOR : fill);
      string base=EEA_PANEL_OVERLAY_PREFIX+"Cal_D"+IntegerToString(day)+"_";
      EEA_SymbolPanelSetHotSurface(chart_id,base+"Bg",cx,cy,74,40,fill,border);
      EEA_SymbolPanelSetText(chart_id,base+"Day",cx+6,cy+4,IntegerToString(day),
                             day_index==today ? EEA_PANEL_ACCENT_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_BOLD);
      string value=!loaded ? "" : (active[day] ? EEA_SymbolPanelSigned(net[day],MathAbs(net[day])>=1000.0 ? 0 : 2) : "0");
      EEA_SymbolPanelSetText(chart_id,base+"Val",cx+68,cy+22,value,
                             active[day] ? EEA_SymbolPanelPnlColor(net[day]) : EEA_PANEL_FAINT_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER,12);
      ObjectSetInteger(chart_id,base+"Day",OBJPROP_ZORDER,15);
      ObjectSetInteger(chart_id,base+"Val",OBJPROP_ZORDER,15);
      if(active[day])
        {
         month_net+=net[day]; month_trades+=trades[day]; trading_days++;
         if(net[day]>0.0) green++; else if(net[day]<0.0) red++;
        }
     }
   int detail_y=grid_y+6*42+4;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"CalDetailSurface",EEA_PANEL_INNER_X,detail_y,
                             EEA_PANEL_INNER_WIDTH,48,EEA_PANEL_SURFACE_COLOR);
   int sd=g_panel_state.calendar_selected_day;
   string detail="Click a day to see its realized result.";
   color detail_color=EEA_PANEL_MUTED_COLOR;
   if(sd>=1 && sd<=days_in_month)
     {
      detail=StringFormat("%04d-%02d-%02d",year,month,sd)+EEA_SymbolPanelSep()+"net "+EEA_SymbolPanelSigned(net[sd],2)+
             EEA_SymbolPanelSep()+"trades "+IntegerToString(trades[sd])+" ("+IntegerToString(wins[sd])+"W / "+
             IntegerToString(losses[sd])+"L)"+EEA_SymbolPanelSep()+"gross "+EEA_SymbolPanelSigned(gross_profit[sd],2)+
             " / "+EEA_SymbolPanelSigned(gross_loss[sd],2);
      detail_color=active[sd] ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR;
     }
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetailTitle",EEA_PANEL_CONTENT_X,detail_y+8,"DAY DETAIL");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetail",EEA_PANEL_CONTENT_X,detail_y+26,detail,detail_color,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalSummary",EEA_PANEL_CONTENT_X,detail_y+56,
                          "Month  net "+EEA_SymbolPanelSigned(month_net,2)+EEA_SymbolPanelSep()+"trading days "+
                          IntegerToString(trading_days)+EEA_SymbolPanelSep()+"green "+IntegerToString(green)+" / red "+
                          IntegerToString(red)+EEA_SymbolPanelSep()+"closed trades "+IntegerToString(month_trades),
                          EEA_SymbolPanelPnlColor(month_net),EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalNote",EEA_PANEL_CONTENT_X,detail_y+74,
                          "Realized P/L by UTC day from loaded history ("+IntegerToString(ctx.history_lookback_days)+
                          " days); cash flows excluded. % and R need daily snapshots (O-03).",
                          EEA_PANEL_FAINT_COLOR,7);
  }

void EEA_SymbolPanelRenderActiveView(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   if(g_panel_state.collapsed) return;
   if(g_panel_state.active_view=="SETTINGS") EEA_SymbolPanelRenderSettings(chart_id,ctx);
   if(g_panel_state.active_view!="SETTINGS") EEA_SymbolPanelRenderDashboard(chart_id,ctx);
  }

// Suspend chart drag/wheel scrolling while the pointer is over the panel so a
// click or drag on a control never pans the chart underneath it.
void EEA_SymbolPanelCaptureChartMouse(const bool inside)
  {
   if(inside && !g_panel_state.chart_scroll_captured)
     {
      g_panel_state.chart_scroll_original=(bool)ChartGetInteger(g_panel_state.chart_id,CHART_MOUSE_SCROLL);
      ChartSetInteger(g_panel_state.chart_id,CHART_MOUSE_SCROLL,false);
      g_panel_state.chart_scroll_captured=true;
     }
   if(!inside && g_panel_state.chart_scroll_captured)
     {
      ChartSetInteger(g_panel_state.chart_id,CHART_MOUSE_SCROLL,g_panel_state.chart_scroll_original);
      g_panel_state.chart_scroll_captured=false;
     }
  }

void EEA_SymbolPanelSetCollapsed(const bool collapsed,EEA_ObserverRuntimeContext &ctx)
  {
   g_panel_state.collapsed=collapsed;
   g_panel_state.overlay_open=false;
   g_panel_state.overlay_name="";
   EEA_SymbolPanelCaptureChartMouse(false);
   EEA_SymbolPanelCreateControls(g_panel_state.chart_id,g_panel_state.sub_window);
   EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx);
   EEA_SymbolPanelRenderActiveView(g_panel_state.chart_id,ctx);
   ChartRedraw(g_panel_state.chart_id);
  }

// OBJ_BUTTON latches its pressed state on click; release it immediately so every
// control behaves as a momentary push button.
void EEA_SymbolPanelReleaseButton(const long chart_id,const string name)
  {
   if(ObjectFind(chart_id,name)<0) return;
   if(ObjectGetInteger(chart_id,name,OBJPROP_TYPE)==OBJ_BUTTON)
      ObjectSetInteger(chart_id,name,OBJPROP_STATE,false);
  }

// The second click of a double-click on the same control is ignored, so a
// double-click can no longer toggle a setting on and straight back off.
bool EEA_SymbolPanelIsRepeatClick(const string name)
  {
   uint now=GetTickCount();
   bool repeat=(name==g_panel_state.last_click_name &&
                now-g_panel_state.last_click_tick<(uint)EEA_PANEL_CLICK_DEBOUNCE_MS);
   g_panel_state.last_click_name=name;
   g_panel_state.last_click_tick=now;
   return repeat;
  }

void EEA_SymbolPanelOnMouseMove(const long x_value,const double y_value)
  {
   if(g_panel_state.sub_window!=0) return;
   int x=(int)x_value, y=(int)y_value;
   bool inside=(x>=EEA_PANEL_X && x<EEA_PANEL_X+EEA_PANEL_MAIN_WIDTH &&
                y>=EEA_PANEL_Y && y<EEA_PANEL_Y+EEA_SymbolPanelHeight());
   EEA_SymbolPanelCaptureChartMouse(inside);
   long chart_id=g_panel_state.chart_id;
   string hit="";
   color base=EEA_PANEL_SURFACE_COLOR;
   if(inside)
      for(int i=g_panel_hit_count-1;i>=0;i--) // later registrations are drawn on top
        {
         if(x<g_panel_hits[i].x || x>=g_panel_hits[i].x+g_panel_hits[i].w ||
            y<g_panel_hits[i].y || y>=g_panel_hits[i].y+g_panel_hits[i].h) continue;
         if(ObjectFind(chart_id,g_panel_hits[i].name)<0) continue;
         hit=g_panel_hits[i].name;
         base=g_panel_hits[i].base;
         break;
        }
   if(hit==g_panel_state.hover_name) return;
   if(g_panel_state.hover_name!="" && ObjectFind(chart_id,g_panel_state.hover_name)>=0)
      for(int i=0;i<g_panel_hit_count;i++)
         if(g_panel_hits[i].name==g_panel_state.hover_name)
           {
            ObjectSetInteger(chart_id,g_panel_state.hover_name,OBJPROP_BGCOLOR,g_panel_hits[i].base);
            break;
           }
   g_panel_state.hover_name=hit;
   if(hit!="") ObjectSetInteger(chart_id,hit,OBJPROP_BGCOLOR,EEA_SymbolPanelLighten(base,18));
   ChartRedraw(chart_id);
  }

void EEA_SymbolPanelToastFromStatus()
  {
   bool failed=StringFind(g_panel_state.status_message,"FAILED")==0;
   string reason=g_panel_state.apply_reason=="" ? "" : "  ("+g_panel_state.apply_reason+")";
   EEA_SymbolPanelToast("Apply: "+g_panel_state.status_message+reason,
                        failed ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_OK_COLOR);
  }

void EEA_SymbolPanelResetStaged(EEA_ObserverRuntimeContext &ctx)
  {
   g_panel_state.staged_policy=g_panel_state.committed_policy;
   g_panel_state.staged_daily_continuation=g_panel_state.committed_daily_continuation;
   g_panel_state.staged_overall_continuation=g_panel_state.committed_overall_continuation;
   g_panel_state.policy_confirmed=false;
   for(int i=0;i<g_panel_state.row_count;i++)
     {
      g_panel_state.rows[i].checked=false;
      for(int j=0;j<ctx.symbol_count;j++)
         if(!g_panel_state.rows[i].context_only &&
            g_panel_state.rows[i].canonical_symbol==ctx.canonical_symbols[j]) g_panel_state.rows[i].checked=true;
     }
   g_panel_state.status_message="Staged settings reset";
   g_panel_state.apply_reason="NONE";
  }

void EEA_SymbolPanelApplyStaged(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   string selected[];
   int count=0;
   for(int i=0;i<g_panel_state.row_count;i++)
      if(g_panel_state.rows[i].checked && !g_panel_state.rows[i].context_only)
        { ArrayResize(selected,count+1); selected[count]=g_panel_state.rows[i].canonical_symbol; count++; }
   if(count<1)
     { g_panel_state.status_message="FAILED"; g_panel_state.apply_reason="NO_SYMBOL_SELECTION"; return; }
   if(g_panel_state.staged_policy!="UNSELECTED" && !g_panel_state.policy_confirmed) // confirmation gate
     { g_panel_state.status_message="FAILED"; g_panel_state.apply_reason="EXPLICIT_CONFIRMATION_REQUIRED"; return; }
   string old_committed_policy=g_panel_state.committed_policy;
   EEA_SymbolPanelPolicySnapshot old_policy;
       EEA_SymbolPanelCapturePolicySnapshot(old_policy);
   bool old_committed_daily=g_panel_state.committed_daily_continuation;
   bool old_staged_daily=g_panel_state.staged_daily_continuation;
   bool old_committed_overall=g_panel_state.committed_overall_continuation;
   bool old_staged_overall=g_panel_state.staged_overall_continuation;
   bool old_policy_confirmed=g_panel_state.policy_confirmed;
   string old_authorization_input_gmt7=g_panel_state.authorization_input_gmt7;
   long old_authorization_utc=g_panel_state.authorization_utc;
   EEA_RuntimeAccountSnapshot old_account=ctx.account;
   string old_canonical_symbols[EEA_RUNTIME_MAX_SYMBOLS];
   string old_broker_symbols[EEA_RUNTIME_MAX_SYMBOLS];
   EEA_RuntimeSymbolSpec old_symbol_specs[EEA_RUNTIME_MAX_SYMBOLS];
   EEA_RuntimeReconciliationSnapshot old_reconciliation=ctx.reconciliation;
   EEA_RuntimeStatus old_status=ctx.status;
   bool old_stale=ctx.stale;
   string old_stale_reason=ctx.stale_reason;
   long old_last_refresh_utc=ctx.last_refresh_utc;
   long old_previous_deal_watermark=ctx.previous_deal_watermark;
   long old_previous_deal_watermark_time=ctx.status.previous_deal_watermark_time;
   int old_symbol_count=ctx.symbol_count;
   bool old_row_checked[EEA_PANEL_MAX_ROWS];
   for(int i=0;i<g_panel_state.row_count && i<EEA_PANEL_MAX_ROWS;i++)
      old_row_checked[i]=g_panel_state.rows[i].checked;
   string old_policy_file_contents="";
   EEA_PolicySettings old_policy_file;
   bool old_policy_file_exists=FileIsExist(ctx.root+"/current/policy_settings.json",0);
   bool old_policy_file_loaded=EEA_PolicySettingsStoreLoad(ctx.root+"/current/policy_settings.json",ctx.config_version,
      ctx.account.account_fingerprint,ctx.account.broker_server,old_policy_file);
   EEA_PolicySettingsReadFile(ctx.root+"/current/policy_settings.json",old_policy_file_contents);
   long old_policy_revision=old_policy_file_loaded ? old_policy_file.revision : 0;
   string old_status_message=g_panel_state.status_message;
   string old_apply_reason=g_panel_state.apply_reason;
   for(int i=0;i<old_symbol_count;i++)
     {
      old_canonical_symbols[i]=ctx.canonical_symbols[i];
      old_broker_symbols[i]=ctx.broker_symbols[i];
      old_symbol_specs[i]=ctx.symbol_specs[i];
     }
   if(EEA_ObserverRuntimeApplySelection(ctx,audit,selected,count))
     {
      g_panel_state.committed_policy=g_panel_state.staged_policy;
      g_panel_state.committed_daily_continuation=g_panel_state.staged_daily_continuation;
      g_panel_state.committed_overall_continuation=g_panel_state.staged_overall_continuation;
      g_panel_state.status_message="APPLIED (DISPLAY/CONTROLLER PROPOSAL ONLY)";
      g_panel_state.apply_reason="FRESH_RECONCILIATION_COMPLETE";
      EEA_PolicySettings persisted_policy;
       if(!EEA_SymbolPanelPersistPolicy(ctx,audit,true,persisted_policy))
        {
         bool rollback_persisted=EEA_ObserverRuntimeRestoreSelectionSnapshot(ctx,audit,old_canonical_symbols,
            old_broker_symbols,old_symbol_specs,old_symbol_count,old_account,old_reconciliation,old_status,
            old_stale,old_stale_reason,old_last_refresh_utc,old_previous_deal_watermark,
            old_previous_deal_watermark_time);
         bool policy_file_restored=EEA_SymbolPanelRestorePolicyFile(ctx.root+"/current/policy_settings.json",old_policy_file_contents,old_policy_file_exists);
         g_panel_state.committed_policy=old_committed_policy;
         g_panel_state.staged_policy=old_policy.staged_policy;
         g_panel_state.committed_daily_continuation=old_committed_daily;
         g_panel_state.staged_daily_continuation=old_staged_daily;
         g_panel_state.committed_overall_continuation=old_committed_overall;
         g_panel_state.staged_overall_continuation=old_staged_overall;
         g_panel_state.policy_confirmed=old_policy_confirmed;
         g_panel_state.authorization_input_gmt7=old_authorization_input_gmt7;
         g_panel_state.authorization_utc=old_authorization_utc;
         for(int i=0;i<g_panel_state.row_count && i<EEA_PANEL_MAX_ROWS;i++)
            g_panel_state.rows[i].checked=old_row_checked[i];
         g_panel_state.status_message=old_status_message;
         g_panel_state.apply_reason=old_apply_reason;
         EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                                    old_committed_policy,g_panel_state.authorization_utc);
          if(!rollback_persisted || !policy_file_restored)
            {
             ctx.status.runtime_state="BLOCKED";
             ctx.status.reason_code="POLICY_ROLLBACK_FAILED";
             ctx.status.new_entries_blocked=true;
             g_panel_state.status_message="FAILED; rollback persistence failed";
             g_panel_state.apply_reason="POLICY_ROLLBACK_PERSISTENCE_FAILED";
             bool rollback_status_persisted=EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
             if(!EEA_ObserverRuntimeAuditChecked(ctx,audit,"POLICY_ROLLBACK_FAILED",ctx.status))
               {
                ctx.status.runtime_state="BLOCKED";
                ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
                ctx.status.new_entries_blocked=true;
                EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                   ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
               }
             EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED",rollback_status_persisted ?
                                        "POLICY_ROLLBACK_PERSISTENCE_FAILED" :
                                        "POLICY_ROLLBACK_STATUS_PERSISTENCE_FAILED",
                                        old_committed_policy,g_panel_state.authorization_utc);
            }

         return;
        }

       if(!EEA_SymbolPanelVerifyPersistedPolicy(ctx,persisted_policy))
       {
         bool runtime_rollback_persisted=EEA_ObserverRuntimeRestoreSelectionSnapshot(ctx,audit,old_canonical_symbols,old_broker_symbols,
             old_symbol_specs,old_symbol_count,old_account,old_reconciliation,old_status,old_stale,
             old_stale_reason,old_last_refresh_utc,old_previous_deal_watermark,old_previous_deal_watermark_time);
         bool policy_file_restored=EEA_SymbolPanelRestorePolicyFile(ctx.root+"/current/policy_settings.json",old_policy_file_contents,old_policy_file_exists);
         EEA_SymbolPanelRestorePolicySnapshot(old_policy);
         for(int i=0;i<g_panel_state.row_count && i<EEA_PANEL_MAX_ROWS;i++)
            g_panel_state.rows[i].checked=old_row_checked[i];
         if(!runtime_rollback_persisted || !policy_file_restored)
           {
            ctx.status.runtime_state="BLOCKED";
            ctx.status.reason_code="POLICY_ROLLBACK_FAILED";
            ctx.status.new_entries_blocked=true;
            g_panel_state.status_message="FAILED; rollback persistence failed";
            g_panel_state.apply_reason="POLICY_ROLLBACK_PERSISTENCE_FAILED";
            bool rollback_status_persisted=EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
               ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
            if(!EEA_ObserverRuntimeAuditChecked(ctx,audit,"POLICY_ROLLBACK_FAILED",ctx.status))
             {
              ctx.status.runtime_state="BLOCKED";
              ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
              ctx.status.new_entries_blocked=true;
              EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                 ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
             }
            EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED",rollback_status_persisted ?
                                       "POLICY_ROLLBACK_PERSISTENCE_FAILED" :
                                       "POLICY_ROLLBACK_STATUS_PERSISTENCE_FAILED",
                                       old_policy.committed_policy,g_panel_state.authorization_utc);
           }
         else
           {
            g_panel_state.status_message="FAILED; policy persistence rolled back";
            g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED";
            EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                                       old_policy.committed_policy,g_panel_state.authorization_utc);
           }
        }
     }
   else
     {
      bool policy_file_restored=EEA_SymbolPanelRestorePolicyFile(ctx.root+"/current/policy_settings.json",old_policy_file_contents,old_policy_file_exists);
       if(!policy_file_restored)
         {
          ctx.status.runtime_state="BLOCKED";
          ctx.status.reason_code="POLICY_ROLLBACK_FAILED";
          ctx.status.new_entries_blocked=true;
          EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
             ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
          if(!EEA_ObserverRuntimeAuditChecked(ctx,audit,"POLICY_ROLLBACK_FAILED",ctx.status))
             {
              ctx.status.runtime_state="BLOCKED";
              ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED";
              ctx.status.new_entries_blocked=true;
              EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status,ctx.config_version,
                 ctx.account.account_fingerprint,ctx.reconciliation.observed_at_utc);
             }
          EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_ROLLBACK_PERSISTENCE_FAILED",
                                     old_committed_policy,g_panel_state.authorization_utc);
         }
       for(int i=0;i<g_panel_state.row_count && i<EEA_PANEL_MAX_ROWS;i++)
          g_panel_state.rows[i].checked=old_row_checked[i];
       g_panel_state.status_message="FAILED; previous committed state retained";
      g_panel_state.apply_reason="RUNTIME_RECONCILIATION_OR_PERSISTENCE_FAILED";
      g_panel_state.staged_policy=g_panel_state.committed_policy;
      g_panel_state.staged_daily_continuation=g_panel_state.committed_daily_continuation;
      g_panel_state.staged_overall_continuation=g_panel_state.committed_overall_continuation;
      g_panel_state.policy_confirmed=false;
     }
  }

void EEA_SymbolPanelHandleChartEvent(const int id,const long &lparam,const double &dparam,
                                     const string &sparam,EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   bool policy_persisted=false;
   bool old_staged_daily=g_panel_state.staged_daily_continuation;
   bool old_staged_overall=g_panel_state.staged_overall_continuation;
   bool old_policy_confirmed=g_panel_state.policy_confirmed;
   string old_status_message=g_panel_state.status_message;
   string old_apply_reason=g_panel_state.apply_reason;
   if(id==CHARTEVENT_MOUSE_MOVE) { EEA_SymbolPanelOnMouseMove(lparam,dparam); return; }
   if(id!=CHARTEVENT_OBJECT_CLICK && id!=CHARTEVENT_OBJECT_ENDEDIT) return;
   if(StringFind(sparam,EEA_PANEL_PREFIX)!=0) return;
   if(id==CHARTEVENT_OBJECT_ENDEDIT && sparam!=EEA_PANEL_OVERLAY_PREFIX+"Edit_AuthorizationGmt7") return;
   if(id==CHARTEVENT_OBJECT_CLICK)
     {
      EEA_SymbolPanelReleaseButton(g_panel_state.chart_id,sparam);
      if(EEA_SymbolPanelIsRepeatClick(sparam)) { ChartRedraw(g_panel_state.chart_id); return; }
     }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Collapse")
     { EEA_SymbolPanelSetCollapsed(!g_panel_state.collapsed,ctx); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Settings") { g_panel_state.active_view="SETTINGS"; EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx); EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); ChartRedraw(g_panel_state.chart_id); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard") { g_panel_state.active_view="DASHBOARD"; EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx); EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx); ChartRedraw(g_panel_state.chart_id); return; }
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Tab_")==0)
     {
      string tab=StringSubstr(sparam,StringLen(EEA_PANEL_OVERLAY_PREFIX+"Tab_"));
      if(g_panel_state.overlay_name=="SETTINGS") g_panel_state.settings_tab=tab;
      if(g_panel_state.overlay_name=="DASHBOARD") g_panel_state.dashboard_tab=tab;
      // A different sub-view has different controls: rebuild it from scratch.
      EEA_SymbolPanelClearOverlay(g_panel_state.chart_id);
      EEA_SymbolPanelRenderActiveView(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalPrev" || sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalNext")
     {
      int step=(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalNext") ? 1 : -1;
      int month_index=g_panel_state.calendar_year*12+(g_panel_state.calendar_month-1)+step;
      g_panel_state.calendar_year=month_index/12;
      g_panel_state.calendar_month=month_index%12+1;
      g_panel_state.calendar_selected_day=0;
      EEA_SymbolPanelClearOverlay(g_panel_state.chart_id);
      EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx);
      return;
     }
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Cal_D")==0)
     {
      string rest=StringSubstr(sparam,StringLen(EEA_PANEL_OVERLAY_PREFIX+"Cal_D"));
      int separator=StringFind(rest,"_");
      int day=(int)StringToInteger(separator>0 ? StringSubstr(rest,0,separator) : rest);
      g_panel_state.calendar_selected_day=(g_panel_state.calendar_selected_day==day) ? 0 : day;
      EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ResetStaged")
     {
      bool has_changes=EEA_SymbolPanelPendingChanges(ctx)>0;
      if(has_changes) EEA_SymbolPanelResetStaged(ctx);
      EEA_SymbolPanelToast(has_changes ? "Staged changes discarded" : "Nothing to discard",EEA_PANEL_MUTED_COLOR);
      EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx);
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_PreviousRows")
     {
      g_panel_state.row_offset-=EEA_PANEL_VISIBLE_ROWS;
      if(g_panel_state.row_offset<0) g_panel_state.row_offset=0;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_NextRows")
     {
      if(g_panel_state.row_offset+EEA_PANEL_VISIBLE_ROWS<g_panel_state.row_count)
         g_panel_state.row_offset+=EEA_PANEL_VISIBLE_ROWS;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SelectAll" || sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SelectNone")
     {
      bool select_all=(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SelectAll");
      for(int i=0;i<g_panel_state.row_count;i++)
         if(!g_panel_state.rows[i].context_only) g_panel_state.rows[i].checked=select_all;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(id==CHARTEVENT_OBJECT_ENDEDIT && sparam==EEA_PANEL_OVERLAY_PREFIX+"Edit_AuthorizationGmt7")
     {
      string entered_value=ObjectGetString(g_panel_state.chart_id,sparam,OBJPROP_TEXT);
      long parsed=0; string reason="";
       string old_authorization_input_gmt7=g_panel_state.authorization_input_gmt7;
       long old_authorization_utc=g_panel_state.authorization_utc;
       string old_status_message=g_panel_state.status_message;
      if(EEA_SymbolPanelParseGmtPlus7(entered_value,parsed,reason))
        { g_panel_state.authorization_input_gmt7=entered_value; g_panel_state.authorization_utc=parsed; g_panel_state.status_message="GMT+7 authorization validated"; g_panel_state.apply_reason=reason; }
      else { g_panel_state.status_message="FAILED"; g_panel_state.apply_reason="INVALID_GMT_PLUS_7_DATETIME"; }
      if(!EEA_SymbolPanelPersistPolicy(ctx,audit,false))
         { g_panel_state.authorization_input_gmt7=old_authorization_input_gmt7; g_panel_state.authorization_utc=old_authorization_utc; g_panel_state.status_message=old_status_message; g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED"; }
       EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Apply")
     {
      bool has_changes=EEA_SymbolPanelPendingChanges(ctx)>0;
      if(has_changes) EEA_SymbolPanelApplyStaged(ctx,audit);
      if(has_changes) EEA_SymbolPanelToastFromStatus();
      if(!has_changes) EEA_SymbolPanelToast("No staged changes to apply",EEA_PANEL_MUTED_COLOR);
      EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx);
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_1_STEP")
     {
      EEA_SymbolPanelPolicySnapshot old_policy;
       EEA_SymbolPanelCapturePolicySnapshot(old_policy);
       bool old_policy_confirmed=g_panel_state.policy_confirmed;
       bool old_staged_daily=g_panel_state.staged_daily_continuation;
       bool old_staged_overall=g_panel_state.staged_overall_continuation;
       string old_status_message=g_panel_state.status_message;
       string old_apply_reason=g_panel_state.apply_reason;
      g_panel_state.staged_policy="FTMO_1_STEP"; g_panel_state.policy_confirmed=false;
       bool policy_persisted=EEA_SymbolPanelPersistPolicy(ctx,audit,false);
       if(!policy_persisted)
          {
           EEA_SymbolPanelRestorePolicySnapshot(old_policy);
           g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED";
           EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                                      old_policy.staged_policy,old_policy.authorization_utc);
          }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_2_STEP")
     {
      EEA_SymbolPanelPolicySnapshot old_policy;
       EEA_SymbolPanelCapturePolicySnapshot(old_policy);
      g_panel_state.staged_policy="FTMO_2_STEP"; g_panel_state.policy_confirmed=false;
      bool policy_persisted=EEA_SymbolPanelPersistPolicy(ctx,audit,false);
       if(!policy_persisted)
         {
          EEA_SymbolPanelRestorePolicySnapshot(old_policy);
          g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED";
          EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                                     old_policy.staged_policy,old_policy.authorization_utc);
         }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_BALANCE_BASED_FTMO_V1")
     {
      EEA_SymbolPanelPolicySnapshot old_policy;
       EEA_SymbolPanelCapturePolicySnapshot(old_policy);
      g_panel_state.staged_policy="BALANCE_BASED_FTMO_V1"; g_panel_state.policy_confirmed=false;
      bool policy_persisted=EEA_SymbolPanelPersistPolicy(ctx,audit,false);
       if(!policy_persisted)
         {
          EEA_SymbolPanelRestorePolicySnapshot(old_policy);
          g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED";
          EEA_SymbolPanelRequirePolicyAudit(ctx,audit,"POLICY_APPLY_REJECTED","POLICY_SETTINGS_PERSISTENCE_FAILED",
                                     old_policy.staged_policy,old_policy.authorization_utc);
         }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_DailyContinuation")
     {
      g_panel_state.staged_daily_continuation=!g_panel_state.staged_daily_continuation;
      if(!EEA_SymbolPanelPersistPolicy(ctx,audit,false))
        { g_panel_state.staged_daily_continuation=g_panel_state.committed_daily_continuation; }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_OverallContinuation")
     {
      g_panel_state.staged_overall_continuation=!g_panel_state.staged_overall_continuation;
      if(!EEA_SymbolPanelPersistPolicy(ctx,audit,false))
        { g_panel_state.staged_overall_continuation=g_panel_state.committed_overall_continuation; }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ConfirmPolicy")
     {
      g_panel_state.policy_confirmed=!g_panel_state.policy_confirmed;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   for(int i=0;i<g_panel_state.row_count;i++)
     {
      string row_prefix=EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_";
      if(sparam!=row_prefix+"Chk" && sparam!=row_prefix+"Lbl" && sparam!=row_prefix+"Bg" && sparam!=row_prefix+"Badge")
         continue;
      if(g_panel_state.rows[i].context_only)
        {
         EEA_SymbolPanelToast(g_panel_state.rows[i].canonical_symbol+" is CONTEXT ONLY and cannot be selected",
                              EEA_PANEL_WARNING_COLOR);
         EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx);
        }
      if(g_panel_state.rows[i].context_only) return;
      if(!g_panel_state.rows[i].context_only)
         g_panel_state.rows[i].checked=!g_panel_state.rows[i].checked;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
  }

void EEA_SymbolPanelDestroy(const long chart_id)
  {
   EEA_SymbolPanelCaptureChartMouse(false);
   ChartSetInteger(chart_id,CHART_EVENT_MOUSE_MOVE,g_panel_state.chart_mouse_move_original);
   ObjectsDeleteAll(chart_id,EEA_PANEL_PREFIX,g_panel_state.sub_window);
   g_panel_hit_count=0;
   ChartRedraw(chart_id);
  }

#endif
