#ifndef ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH
#define ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH

// G94: the EnterpriseS07 edition (EEA_S07_EDITION) shows its own name, no AI tab and the S07 setup column.
#ifdef EEA_S07_EDITION
   #define EEA_PANEL_PRODUCT_NAME   "EnterpriseS07"
   #define EEA_PANEL_SETUP_COLUMN   "S07 setup"
   #define EEA_PANEL_STRATEGY_LABEL "Strategy runtime (S07 family)"
   #define EEA_PANEL_STRATEGY_STATUS "Strategy S07 / trade manager"
   #define EEA_PANEL_DASH_TABS      6
#else
   #define EEA_PANEL_PRODUCT_NAME   "EnterpriseEA"
   #define EEA_PANEL_SETUP_COLUMN   "S02 setup"
   #define EEA_PANEL_STRATEGY_LABEL "Strategy runtime (S02/S04/S06)"
   #define EEA_PANEL_STRATEGY_STATUS "Strategy S02/S04/S06 / trade manager"
   #define EEA_PANEL_DASH_TABS      7
#endif

#include "ObserverRuntime.mqh"
#include "ObserverPanelModel.mqh"
#include "..\Market\SymbolRegistry.mqh"
#include "..\Storage\PolicySettingsStore.mqh"
#include "..\Storage\DailyStatsStore.mqh"
#include "..\Storage\DailyFloatingStore.mqh"

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
#define EEA_AI_VIEW_SLOTS 6   // must equal EEA_AI_TYPES (AiBridgeClient.mqh); one report slot per request type
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
#define EEA_PANEL_NEWS_ROWS 10

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
   EEA_PANEL_BUTTON_GHOST=8,
   EEA_PANEL_BUTTON_DANGER=9,
   EEA_PANEL_BUTTON_WARNING=10
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
   int calendar_mode;             // REQ-010 cell value: 0 MONEY, 1 %, 2 R
   string toast_text;
   color toast_color;
   datetime toast_until;
   string edit_rendered_value;
   string session_request;        // consumed by the EA shell: SIGN_24H | SIGN_7D | REVOKE
   string recovery_request;       // consumed by the EA shell: RECHECK | RESOLVE
   string ai_request;             // consumed by the EA shell: ASK | REVIEW
   string trade_selected_kind;    // Trades tab (G8): POSITION | ORDER | ""
   long trade_selected_ticket;
   double trade_selected_volume;
   double trade_selected_sl;
   string trade_pending_action;   // action waiting for Confirm (15 seconds)
   uint trade_confirm_tick;
   double trade_partial_fraction;
   int trade_closeall_stage;      // 0 none, 1 first confirm, 2 second click (10 seconds)
   uint trade_closeall_tick;
   int trade_row_count;
   string trade_row_kind[12];
   long trade_row_ticket[12];
   string cmd_request_action;     // consumed by the EA shell
   string cmd_request_kind;
   long cmd_request_ticket;
   double cmd_request_volume;
   double cmd_request_sl;
   double cmd_request_fraction;
   uint ai_request_tick;          // one AI request per minute from the panel
   string bot_toggle_request;     // consumed by the EA shell: bot code to toggle (Settings > Bots)
   string bot_confirm_code;       // enabling needs a second click within 10 seconds
   uint bot_confirm_tick;
   uint recovery_confirm_tick;    // RESOLVE needs a second click within 10 seconds
   string session_confirm_action; // the first click arms a confirmation for 10 seconds
   uint session_confirm_tick;
  };

static EEA_SymbolPanelState g_panel_state;

// Bots host rows (published by the EA shell each timer): Settings > Bots and the collapsed panel.
struct EEA_PanelBotRow
  {
   string code;
   string title;
   string mode;
   bool   active;
   long   magic;
   int    open_count;
   double today;
   double floating;
   string status;
   double near_score;             // 0..1: how close the bot is to its next entry
   string near_text;              // what it waits for / what is still missing
  };

EEA_PanelBotRow g_panel_bots[4];
int    g_panel_bot_count=0;
string g_panel_bots_guard="";      // one line: armed / pause / open risk / daily loss / news
bool   g_panel_bots_enabled=false;
#define EEA_PANEL_MINI_LINE 16

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
   string setup_detail[EEA_PANEL_MAX_ROWS];
   int universe_count;
   string universe[EEA_PANEL_MAX_ROWS];
   string session_state;          // NONE | ACTIVE | EXPIRED | REVOKED | INVALID
   string session_id;
   long session_until_utc;
   string session_symbols;
   double session_risk_fraction;
   double session_daily_loss_fraction;
   int session_entries_today;        // SCALP
   int session_max_entries;
   int session_swing_entries_today;
   int session_max_swing_entries;
   string session_reason;
   string session_message;
   bool session_real_account;
   string trade_manager_reason;
   bool cmd_armed;                // manual actions need an armed EA (C3)
   string cmd_last;
   int ea_position_count;
   long ea_position_ticket[32];
   string ea_position_profile[32];
   int ea_order_count;
   long ea_order_ticket[16];
   string ai_status;              // AI Bridge: ONLINE | BRIDGE OFFLINE | CIRCUIT OPEN | DISABLED
   string ai_status_line;
   string ai_title[EEA_AI_VIEW_SLOTS];
   int ai_line_count[EEA_AI_VIEW_SLOTS];
   string ai_lines[EEA_AI_VIEW_SLOTS*8];
   bool sentiment_ok;             // market sentiment (cross-pair flow)
   string sentiment_reason;
   string sentiment_regime;
   long sentiment_bar_time;
   string sentiment_summary;
   bool operator_paused;          // G19: entries paused by the operator (Telegram)
   string operator_mode_reason;
   string sentiment_ccy[8];
   double sentiment_s4[8];
   double sentiment_s24[8];
   int sentiment_symbol_count;
   string sentiment_symbol[EEA_PANEL_MAX_ROWS];
   string sentiment_symbol_text[EEA_PANEL_MAX_ROWS];
   string news_reason;            // News Guard calendar status
   long news_last_success_utc;
   string news_policy;
   int news_symbol_count;
   string news_symbol[EEA_PANEL_MAX_ROWS];
   string news_state[EEA_PANEL_MAX_ROWS];
   string news_detail[EEA_PANEL_MAX_ROWS];
   int news_event_count;
   long news_event_utc[EEA_PANEL_NEWS_ROWS];
   string news_event_text[EEA_PANEL_NEWS_ROWS];
   string news_event_values[EEA_PANEL_NEWS_ROWS];
   string news_event_stats[EEA_PANEL_NEWS_ROWS];   // reaction history on the focus symbol
   string news_watch[EEA_PANEL_MAX_ROWS];          // indirect (yellow) event per symbol
   string news_focus;
   int news_recent_count;
   string news_recent[3];
   string news_reaction_reason;
   string news_health_line;
   int news_health_warn;
   string recovery_detail;        // the blocked entry: intent, ticket, retcode
   string recovery_message;       // last re-check / resolve outcome
   bool active_risk_valid;
   double active_risk_money;      // loss at SL of open positions and EA/broker pending orders
   double active_risk_capital;    // initial capital the percentage is measured against
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
   view.session_state="NONE"; view.session_id=""; view.session_until_utc=0; view.session_symbols="";
   view.session_risk_fraction=0.0; view.session_daily_loss_fraction=0.0; view.session_entries_today=0;
   view.session_max_entries=0; view.session_swing_entries_today=0; view.session_max_swing_entries=0; view.session_reason=""; view.session_message=""; view.session_real_account=false;
   view.trade_manager_reason="";
   view.recovery_detail=""; view.recovery_message="";
   view.cmd_armed=false; view.cmd_last=""; view.ea_position_count=0; view.ea_order_count=0;
   view.ai_status="DISABLED"; view.ai_status_line="";
   for(int i=0;i<EEA_AI_VIEW_SLOTS;i++) { view.ai_title[i]=""; view.ai_line_count[i]=0; }
   for(int i=0;i<EEA_AI_VIEW_SLOTS*8;i++) view.ai_lines[i]="";
   view.sentiment_ok=false; view.sentiment_reason="SENTIMENT_NOT_PUBLISHED"; view.sentiment_regime="UNKNOWN";
   view.sentiment_bar_time=0; view.sentiment_summary=""; view.sentiment_symbol_count=0;
   view.operator_paused=false; view.operator_mode_reason="";
   for(int i=0;i<8;i++) { view.sentiment_ccy[i]=""; view.sentiment_s4[i]=0.0; view.sentiment_s24[i]=0.0; }
   view.news_reason="NEWS_GUARD_NOT_PUBLISHED"; view.news_last_success_utc=0; view.news_policy="";
   view.news_symbol_count=0; view.news_event_count=0;
   view.news_focus=""; view.news_recent_count=0; view.news_reaction_reason="";
   view.news_health_line=""; view.news_health_warn=0;
   for(int i=0;i<3;i++) view.news_recent[i]="";
   for(int i=0;i<EEA_PANEL_NEWS_ROWS;i++) view.news_event_stats[i]="";
   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++) view.news_watch[i]="";
   view.active_risk_valid=false; view.active_risk_money=0.0; view.active_risk_capital=0.0;
   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++)
     { view.setup_symbol[i]=""; view.setup_state[i]=""; view.setup_detail[i]=""; view.universe[i]=""; }
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
   return c=="DXY" || c=="USDX" || b=="USDX" || b=="USDX." || b=="USDIND";
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
   else if(variant==EEA_PANEL_BUTTON_DANGER)
     { background=EEA_PANEL_DANGER_FILL_COLOR; border=EEA_PANEL_DANGER_COLOR; }
   else if(variant==EEA_PANEL_BUTTON_WARNING)
     { background=EEA_PANEL_WARNING_FILL_COLOR; border=EEA_PANEL_WARNING_COLOR; }
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

#define EEA_PANEL_MINI_FIRST 44    // characters on a bot's first line (next to its name)
#define EEA_PANEL_MINI_NEXT  64    // characters on its continuation lines (under the name)
#define EEA_PANEL_MINI_BEST  84    // characters per line of the "closest" summary
#define EEA_PANEL_MINI_MAX   4     // lines per bot at most

// Splits text into lines of at most first / next characters, at " | " first, then at spaces.
int EEA_SymbolPanelWrap(const string text,const int first,const int next,const int max_lines,string &out[])
  {
   ArrayResize(out,0);
   string segs[];
   int ns=StringSplit(text,'|',segs);
   if(ns<=0) { ns=1; ArrayResize(segs,1); segs[0]=text; }
   int n=0;
   string cur="";
   for(int i=0;i<ns;i++)
     {
      string seg=segs[i];
      StringTrimLeft(seg); StringTrimRight(seg);
      if(seg=="") continue;
      const int limit=(n==0 ? first : next);
      const string candidate=(cur=="" ? seg : cur+" | "+seg);
      if(StringLen(candidate)<=limit) { cur=candidate; continue; }
      if(cur!="") { ArrayResize(out,n+1); out[n++]=cur; cur=""; if(n>=max_lines) break; }
      // a segment longer than a line: cut it at spaces
      while(StringLen(seg)>(n==0 ? first : next) && n<max_lines)
        {
         const int lim=(n==0 ? first : next);
         int cut=lim;
         for(int k=lim;k>lim/2;k--) if(StringGetCharacter(seg,k)==' ') { cut=k; break; }
         ArrayResize(out,n+1); out[n++]=StringSubstr(seg,0,cut);
         seg=StringSubstr(seg,cut); StringTrimLeft(seg);
        }
      if(n>=max_lines) break;
      cur=seg;
     }
   if(cur!="" && n<max_lines) { ArrayResize(out,n+1); out[n++]=cur; }
   if(n==0) { ArrayResize(out,1); out[0]=""; n=1; }
   return n;
  }

string EEA_SymbolPanelMiniText(const int i)
  {
   return g_panel_bots[i].near_text!="" ? g_panel_bots[i].near_text : g_panel_bots[i].status;
  }

int EEA_SymbolPanelMiniBest()
  {
   int best=-1;
   for(int i=0;i<g_panel_bot_count && i<4;i++)
      if(g_panel_bots[i].active && g_panel_bots[i].mode!="OFF" &&
         (best<0 || g_panel_bots[i].near_score>g_panel_bots[best].near_score)) best=i;
   return best;
  }

string EEA_SymbolPanelMiniBestText()
  {
   const int best=EEA_SymbolPanelMiniBest();
   if(best<0) return "Gần khớp nhất: không có bot nào đang bật";
   return "Gần khớp nhất: "+g_panel_bots[best].title+" "+IntegerToString((int)MathRound(100.0*g_panel_bots[best].near_score))+
          "%  "+EEA_SymbolPanelGlyph(0x2192)+"  "+g_panel_bots[best].near_text;
  }

int EEA_SymbolPanelMiniLineCount()
  {
   string tmp[];
   int lines=0;
   for(int i=0;i<g_panel_bot_count && i<4;i++)
      lines+=EEA_SymbolPanelWrap(EEA_SymbolPanelMiniText(i),EEA_PANEL_MINI_FIRST,EEA_PANEL_MINI_NEXT,EEA_PANEL_MINI_MAX,tmp);
   lines+=EEA_SymbolPanelWrap(EEA_SymbolPanelMiniBestText(),EEA_PANEL_MINI_BEST,EEA_PANEL_MINI_BEST,3,tmp);
   return lines;
  }

int EEA_SymbolPanelHeight()
  {
   if(!g_panel_state.collapsed) return EEA_PANEL_MAIN_HEIGHT;
   // Collapsed with the bots layer: every bot's lines (wrapped, not cut) plus the "closest" lines.
   if(!g_panel_bots_enabled || g_panel_bot_count<=0) return EEA_PANEL_COLLAPSED_HEIGHT;
   return EEA_PANEL_COLLAPSED_HEIGHT+6+EEA_SymbolPanelMiniLineCount()*EEA_PANEL_MINI_LINE+14;
  }

string EEA_SymbolPanelMeter(const double score)
  {
   const int n=(int)MathRound(MathMax(0.0,MathMin(1.0,score))*5.0);
   string m="";
   for(int i=0;i<5;i++) m+=(i<n ? EEA_SymbolPanelGlyph(0x25A0) : EEA_SymbolPanelGlyph(0x25A1));
   return m;
  }

// Collapsed panel: what every bot is doing and how close it is to an entry; the closest one last.
// Long texts wrap onto more lines (the panel grows); every line carries the full text as a tooltip.
void EEA_SymbolPanelRenderMiniBots(const long chart_id)
  {
   const string pfx=EEA_PANEL_MAIN_PREFIX+"Mini_";
   ObjectsDeleteAll(chart_id,pfx,g_panel_state.sub_window);
   if(!g_panel_state.collapsed || !g_panel_bots_enabled || g_panel_bot_count<=0) return;
   int y=EEA_PANEL_COLLAPSED_HEIGHT+6;
   string lines[];
   for(int i=0;i<g_panel_bot_count && i<4;i++)
     {
      const EEA_PanelBotRow b=g_panel_bots[i];
      const string id=IntegerToString(i);
      const string full=EEA_SymbolPanelMiniText(i);
      const color c=(!b.active || b.mode=="OFF") ? EEA_PANEL_FAINT_COLOR :
                    (b.near_score>=0.8 ? EEA_PANEL_OK_COLOR : (b.near_score>=0.5 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR));
      EEA_SymbolPanelSetText(chart_id,pfx+"M"+id,EEA_PANEL_MARGIN_X,y,EEA_SymbolPanelMeter(b.near_score),c,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,10);
      EEA_SymbolPanelSetText(chart_id,pfx+"N"+id,EEA_PANEL_MARGIN_X+62,y,b.title+(b.active ? "" : " (OFF)"),
                             b.active ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,16);
      EEA_SymbolPanelSetText(chart_id,pfx+"D"+id,EEA_PANEL_MARGIN_X+150,y,
                             b.mode+(b.open_count>0 ? " "+IntegerToString(b.open_count)+" mở" : ""),
                             b.mode=="LIVE" ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,12);
      const int n=EEA_SymbolPanelWrap(full,EEA_PANEL_MINI_FIRST,EEA_PANEL_MINI_NEXT,EEA_PANEL_MINI_MAX,lines);
      for(int k=0;k<n;k++)
        {
         const string name=pfx+"T"+id+"_"+IntegerToString(k);
         EEA_SymbolPanelSetText(chart_id,name,k==0 ? EEA_PANEL_MARGIN_X+214 : EEA_PANEL_MARGIN_X+62,y,lines[k],
                                b.active ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,
                                EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,200);
         ObjectSetString(chart_id,name,OBJPROP_TOOLTIP,b.title+": "+full);
         y+=EEA_PANEL_MINI_LINE;
        }
     }
   const int best=EEA_SymbolPanelMiniBest();
   const string full=EEA_SymbolPanelMiniBestText();
   const int nb=EEA_SymbolPanelWrap(full,EEA_PANEL_MINI_BEST,EEA_PANEL_MINI_BEST,3,lines);
   y+=2;
   for(int k=0;k<nb;k++)
     {
      const string name=pfx+"Best_"+IntegerToString(k);
      EEA_SymbolPanelSetText(chart_id,name,k==0 ? EEA_PANEL_MARGIN_X : EEA_PANEL_MARGIN_X+16,y,lines[k],
                             best>=0 && g_panel_bots[best].near_score>=0.8 ? EEA_PANEL_OK_COLOR : EEA_PANEL_ACCENT_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,200);
      ObjectSetString(chart_id,name,OBJPROP_TOOLTIP,full);
      y+=EEA_PANEL_MINI_LINE;
     }
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

string EEA_SymbolPanelSetupDetail(const string canonical)
  {
   for(int i=0;i<g_panel_engine.setup_count && i<EEA_PANEL_MAX_ROWS;i++)
      if(g_panel_engine.setup_symbol[i]==canonical) return g_panel_engine.setup_detail[i];
   return "";
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
                          EEA_PANEL_PRODUCT_NAME,EEA_PANEL_TEXT_COLOR,EEA_PANEL_TITLE_FONT_SIZE,EEA_PANEL_FONT_BOLD);
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

// SYM-02 per-symbol state: UNRESOLVED (no unique broker mapping) or BLOCKED
// (mapping found but the specification could not be read).
string EEA_SymbolPanelSymbolStatus(const EEA_ObserverRuntimeContext &ctx,const int index)
  {
   if(EEA_SymbolPanelIsContextOnly(ctx.canonical_symbols[index],ctx.broker_symbols[index])) return "CONTEXT ONLY";
   if(ctx.broker_symbols[index]!="") return "RESOLVED";
   return StringFind(ctx.symbol_block_reason[index],"SPEC")>=0 ? "BLOCKED" : "UNRESOLVED";
  }

string EEA_SymbolPanelBlockReason(const EEA_ObserverRuntimeContext &ctx,const int index)
  {
   if(ctx.broker_symbols[index]!="") return "";
   return ctx.symbol_block_reason[index]=="" ? "SYMBOL_UNRESOLVED" : ctx.symbol_block_reason[index];
  }

EEA_ObserverPanelMarketRow EEA_ObserverPanelMarketRowFromRuntime(const EEA_ObserverRuntimeContext &ctx,const int index)
  {
   EEA_ObserverPanelMarketRow row;
   EEA_ObserverPanelMarketRowDefaults(row);
   if(index<0 || index>=ctx.symbol_count) return row;
   row.canonical=ctx.canonical_symbols[index];
   row.broker=ctx.broker_symbols[index];
   row.status=EEA_SymbolPanelSymbolStatus(ctx,index);
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
   string execution=g_panel_engine.execution_enabled ? "Exec ON" : "EXECUTION_DISABLED";
   string live=(g_panel_engine.execution_enabled && g_panel_engine.live_armed) ?
      (g_panel_engine.session_state=="ACTIVE" ? "Session ACTIVE" : "Armed, no session") : "Live NOT_AUTHORIZED";
   string entries=EEA_SymbolPanelLivePathOpen() ? "Entries LIVE" :
                  (ctx.status.new_entries_blocked ? "Entries BLOCKED" : "Entries REVIEW");
   string subheader=g_panel_state.collapsed ?
      "Equity "+EEA_SymbolPanelFormatNumber(ctx.account.equity,2)+" "+ctx.account.account_currency+
      EEA_SymbolPanelSep()+entries :
      execution+EEA_SymbolPanelSep()+live+EEA_SymbolPanelSep()+entries;
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Subheader",EEA_PANEL_MARGIN_X,29,subheader,
                          ctx.status.new_entries_blocked ? EEA_PANEL_MUTED_COLOR : EEA_PANEL_WARNING_COLOR,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,60);
   // The surface follows the collapsed height (the bot lines appear once the shell published them).
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_MAIN_PREFIX+"Surface",0,0,EEA_PANEL_MAIN_WIDTH,EEA_SymbolPanelHeight(),
                             EEA_PANEL_BG_COLOR);
   EEA_SymbolPanelRenderMiniBots(chart_id);
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
   // Requests to the EA shell start empty (an unset string is NULL, which is not "").
   g_panel_state.session_request=""; g_panel_state.session_confirm_action=""; g_panel_state.session_confirm_tick=0;
   g_panel_state.recovery_request=""; g_panel_state.recovery_confirm_tick=0;
   g_panel_state.ai_request=""; g_panel_state.ai_request_tick=0;
   g_panel_state.bot_toggle_request=""; g_panel_state.bot_confirm_code=""; g_panel_state.bot_confirm_tick=0;
   g_panel_state.cmd_request_action=""; g_panel_state.cmd_request_kind=""; g_panel_state.cmd_request_ticket=0;
   g_panel_state.cmd_request_volume=0.0; g_panel_state.cmd_request_sl=0.0; g_panel_state.cmd_request_fraction=0.0;
   g_panel_state.trade_selected_kind=""; g_panel_state.trade_selected_ticket=0; g_panel_state.trade_selected_volume=0.0;
   g_panel_state.trade_selected_sl=0.0; g_panel_state.trade_pending_action=""; g_panel_state.trade_confirm_tick=0;
   g_panel_state.trade_partial_fraction=0.5; g_panel_state.trade_closeall_stage=0; g_panel_state.trade_closeall_tick=0;
   g_panel_state.trade_row_count=0;
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
   g_panel_state.calendar_mode=0;
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

// Panel view preferences survive EA removal and re-attachment.
string EEA_SymbolPanelUiStatePath(const string data_root) { return data_root+"/current/ui_state.json"; }

void EEA_SymbolPanelSaveUiState(const string data_root)
  {
   if(data_root=="") return;
   string json="{\"document_version\":\"ui-state-v1.0.0\",\"active_view\":\""+g_panel_state.active_view+
      "\",\"dashboard_tab\":\""+g_panel_state.dashboard_tab+"\",\"settings_tab\":\""+g_panel_state.settings_tab+
      "\",\"collapsed\":"+(g_panel_state.collapsed ? "true" : "false")+"}";
   EEA_WriteAtomicText(EEA_SymbolPanelUiStatePath(data_root),json);
  }

string EEA_SymbolPanelUiField(const string json,const string name)
  {
   string key="\""+name+"\":\"";
   int at=StringFind(json,key);
   if(at<0) return "";
   int start=at+StringLen(key);
   int end=StringFind(json,"\"",start);
   return end<0 ? "" : StringSubstr(json,start,end-start);
  }

void EEA_SymbolPanelLoadUiState(const string data_root)
  {
   string path=EEA_SymbolPanelUiStatePath(data_root);
   if(data_root=="" || !FileIsExist(path,0)) return;
   int handle=FileOpen(path,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return;
   ulong size=FileSize(handle);
   if(size==0 || size>4096) { FileClose(handle); return; }
   uchar bytes[];
   ArrayResize(bytes,(int)size);
   uint read=FileReadArray(handle,bytes,0,(int)size);
   FileClose(handle);
   if(read!=(uint)size) return;
   string json=CharArrayToString(bytes,0,(int)read,CP_UTF8);
   if(StringFind(json,"\"document_version\":\"ui-state-v1.0.0\"")<0) return;
   string view=EEA_SymbolPanelUiField(json,"active_view");
   string dash=EEA_SymbolPanelUiField(json,"dashboard_tab");
   string settings=EEA_SymbolPanelUiField(json,"settings_tab");
   if(view=="DASHBOARD" || view=="SETTINGS") g_panel_state.active_view=view;
   if(dash=="OVERVIEW" || dash=="MARKET" || dash=="TRADES" || dash=="RISK" || dash=="NEWS" || dash=="AI" || dash=="CALENDAR")
      g_panel_state.dashboard_tab=dash;
#ifdef EEA_S07_EDITION
   if(g_panel_state.dashboard_tab=="AI") g_panel_state.dashboard_tab="OVERVIEW";
#endif
   if(settings=="RISK" || settings=="SYMBOLS" || settings=="AUTHORIZATION" || settings=="SYSTEM" || settings=="BOTS")
      g_panel_state.settings_tab=settings;
   g_panel_state.collapsed=StringFind(json,"\"collapsed\":true")>=0;
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
      if(broker=="") broker=(g_panel_state.rows[row_index].status=="AVAILABLE" ? "resolves on Apply" :
                             (g_panel_state.rows[row_index].description=="" ? "[UNRESOLVED]" : g_panel_state.rows[row_index].description));
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
      g_panel_state.rows[count].status=EEA_SymbolPanelSymbolStatus(ctx,i);
      g_panel_state.rows[count].description=EEA_SymbolPanelBlockReason(ctx,i);
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
   if(!g_panel_state.staged_initialized)
     {
      bool was_collapsed=g_panel_state.collapsed;
      EEA_SymbolPanelLoadUiState(ctx.root);
      if(g_panel_state.collapsed!=was_collapsed) EEA_SymbolPanelCreateControls(chart_id,g_panel_state.sub_window);
     }
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

// ---------------------------------------------------------------------------------------------- Bots tab
// Bots host (design 2026-10-16): one row per strategy with its Active switch. The EA shell publishes
// g_panel_bots each timer; a click only sets g_panel_state.bot_toggle_request (the shell commits,
// audits and applies it). Turning a bot OFF is one click; turning it ON needs a second click (10 s).

bool EEA_SymbolPanelBotConfirming(const string code)
  {
   return g_panel_state.bot_confirm_code==code && g_panel_state.bot_confirm_tick>0 &&
          GetTickCount()-g_panel_state.bot_confirm_tick<10000;
  }

void EEA_SymbolPanelSettingsBots(const long chart_id)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Bots",EEA_PANEL_CONTENT_X,y,
                             "BOTS"+EEA_SymbolPanelSep()+"ONE PORTFOLIO"+EEA_SymbolPanelSep()+"ACTIVE GATES NEW ENTRIES ONLY");
   if(!g_panel_bots_enabled)
     {
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_BotsOff",EEA_PANEL_CONTENT_X,y+24,
                             "The bots layer is off (InpBotsEnabled=false).",EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
      return;
     }
   for(int i=0;i<g_panel_bot_count && i<4;i++)
     {
      const EEA_PanelBotRow b=g_panel_bots[i];
      const int ry=y+20+i*66;
      const string id=EEA_PANEL_OVERLAY_PREFIX+"Bot"+IntegerToString(i);
      EEA_SymbolPanelSetSurface(chart_id,id+"_Bg",EEA_PANEL_INNER_X,ry,EEA_PANEL_INNER_WIDTH,60,EEA_PANEL_SURFACE_COLOR,
                                b.active ? EEA_PANEL_OK_COLOR : EEA_PANEL_BORDER_COLOR);
      EEA_SymbolPanelSetText(chart_id,id+"_T",EEA_PANEL_CONTENT_X,ry+7,b.title,EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE+1,
                             EEA_PANEL_FONT_BOLD);
      color mode_fill=EEA_PANEL_SURFACE_ALT_COLOR, mode_text=EEA_PANEL_MUTED_COLOR;
      if(b.mode=="LIVE") { mode_fill=EEA_PANEL_WARNING_FILL_COLOR; mode_text=EEA_PANEL_WARNING_COLOR; }
      else if(b.mode=="SHADOW") { mode_fill=EEA_PANEL_ACCENT_FILL_COLOR; mode_text=EEA_PANEL_TEXT_COLOR; }
      EEA_SymbolPanelSetPill(chart_id,id+"_M",EEA_PANEL_CONTENT_X+130,ry+5,70,b.mode,mode_fill,mode_text);
      EEA_SymbolPanelSetText(chart_id,id+"_I",EEA_PANEL_CONTENT_X+210,ry+9,
                             "magic "+IntegerToString(b.magic)+EEA_SymbolPanelSep()+"open "+IntegerToString(b.open_count)+
                             EEA_SymbolPanelSep()+"today "+DoubleToString(b.today,2),EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_MONO,ANCHOR_LEFT_UPPER,40);
      EEA_SymbolPanelSetText(chart_id,id+"_S",EEA_PANEL_CONTENT_X,ry+34,b.status,
                             b.active ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,70);
      const bool confirming=EEA_SymbolPanelBotConfirming(b.code);
      const string label=b.active ? "ACTIVE" : (confirming ? "Confirm ON" : "INACTIVE");
      const EEA_SymbolPanelButtonVariant v=b.active ? EEA_PANEL_BUTTON_ON : (confirming ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_OFF);
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Bot_"+b.code,EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-104,
                                 ry+6,104,26,label,v,EEA_PANEL_META_FONT_SIZE);
     }
   const int gy=y+20+4*66+4;
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_BotsGuard",EEA_PANEL_CONTENT_X,gy,g_panel_bots_guard,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,90);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_BotsNote",EEA_PANEL_CONTENT_X,gy+16,
                          "OFF = no new entry; open trades keep their stops and exits. ON needs a second click. Telegram: /bots",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,100);
  }

void EEA_SymbolPanelRenderSettings(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelBeginOverlay(chart_id,"SETTINGS");
   EEA_SymbolPanelRenderViewBase(chart_id);
   string tabs[5]={"RISK","SYMBOLS","AUTHORIZATION","SYSTEM","BOTS"};
   string titles[5]={"Risk policy","Symbols","Authorization","System","Bots"};
   titles[1]="Symbols ("+IntegerToString(EEA_SymbolPanelStagedSymbolCount())+")";
   for(int t=0;t<5;t++)
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tab_"+tabs[t],EEA_PANEL_INNER_X+t*107,
                                 EEA_PANEL_VIEW_Y,104,24,titles[t],
                                 g_panel_state.settings_tab==tabs[t] ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,
                                 EEA_PANEL_META_FONT_SIZE);
   if(g_panel_state.settings_tab=="SYMBOLS") EEA_SymbolPanelSettingsSymbols(chart_id,ctx);
   else if(g_panel_state.settings_tab=="AUTHORIZATION") EEA_SymbolPanelSettingsAuthorization(chart_id,ctx);
   else if(g_panel_state.settings_tab=="SYSTEM") EEA_SymbolPanelSettingsSystem(chart_id,ctx);
   else if(g_panel_state.settings_tab=="BOTS") EEA_SymbolPanelSettingsBots(chart_id);
   else EEA_SymbolPanelSettingsRisk(chart_id,ctx);
   if(g_panel_state.settings_tab!="BOTS") EEA_SymbolPanelSettingsFooter(chart_id,ctx);
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
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_1_STEP",EEA_PANEL_CONTENT_X,y+46,124,30,
                              "FTMO 1-Step",g_panel_state.staged_policy=="FTMO_1_STEP" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_2_STEP",EEA_PANEL_CONTENT_X+129,y+46,124,30,
                              "FTMO 2-Step",g_panel_state.staged_policy=="FTMO_2_STEP" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_BALANCE_BASED_FTMO_V1",EEA_PANEL_CONTENT_X+258,y+46,124,30,
                              "Balance based",g_panel_state.staged_policy=="BALANCE_BASED_FTMO_V1" ?
                              EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_SECONDARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_CUSTOM",EEA_PANEL_CONTENT_X+387,y+46,123,30,
                              "Custom",g_panel_state.staged_policy=="CUSTOM" ?
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

// The observer evidence always blocks entries by design; only the identity-bound live
// path (inputs armed, session active, kill switch released) may send, per candidate.
bool EEA_SymbolPanelLivePathOpen()
  {
   return g_panel_engine.execution_enabled && g_panel_engine.live_armed &&
          g_panel_engine.session_state=="ACTIVE" && !g_panel_engine.controller_kill_active &&
          g_panel_engine.controller_allows_market && !g_panel_engine.recovery_blocked;
  }

string EEA_SymbolPanelPercent(const double fraction) { return DoubleToString(fraction*100.0,2)+"%"; }

string EEA_SymbolPanelDurationText(const long seconds)
  {
   if(seconds<=0) return "0m";
   long d=seconds/86400, h=(seconds%86400)/3600, m=(seconds%3600)/60;
   if(d>0) return IntegerToString(d)+"d "+IntegerToString(h)+"h";
   if(h>0) return IntegerToString(h)+"h "+IntegerToString(m)+"m";
   return IntegerToString(m)+"m";
  }

bool EEA_SymbolPanelSessionConfirming(const string action)
  {
   // A chosen duration stays selected for 60 s; Accept (or a second click on it) signs.
   return g_panel_state.session_confirm_action==action &&
          GetTickCount()-g_panel_state.session_confirm_tick<60000;
  }

// Session authorization: one signed, time-boxed permission for automatic entries.
// The panel only raises a request; the EA shell validates, writes and audits it.
void EEA_SymbolPanelSettingsSession(const long chart_id,const int y)
  {
   string state=g_panel_engine.session_state;
   bool active=(state=="ACTIVE");
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"SessionSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,192,EEA_PANEL_SURFACE_COLOR,
                             active ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_BORDER_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Session",EEA_PANEL_CONTENT_X,y+10,
                             "SESSION AUTHORIZATION"+EEA_SymbolPanelSep()+"AUTOMATIC ENTRIES");
   color fill=EEA_PANEL_SURFACE_ALT_COLOR, text_color=EEA_PANEL_MUTED_COLOR;
   if(active) { fill=EEA_PANEL_WARNING_FILL_COLOR; text_color=EEA_PANEL_WARNING_COLOR; }
   else if(state=="INVALID") { fill=EEA_PANEL_DANGER_FILL_COLOR; text_color=EEA_PANEL_DANGER_COLOR; }
   EEA_SymbolPanelSetPill(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Pill_Session",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-112,y+6,
                          112,state,fill,text_color);
   long now=(long)TimeGMT();
   string status_line=active ?
      "Active until "+EEA_SymbolPanelReadableUtc(g_panel_engine.session_until_utc)+"  ("+
      EEA_SymbolPanelDurationText(g_panel_engine.session_until_utc-now)+" left)" :
      (state=="NONE" ? "No session. The EA observes and never sends an order." :
       "Session "+state+(g_panel_engine.session_reason=="" ? "" : "  ("+g_panel_engine.session_reason+")"));
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionStatus",EEA_PANEL_CONTENT_X,y+34,status_line,
                          active ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionSymbols",EEA_PANEL_CONTENT_X,y+54,
                          "Symbols  "+(g_panel_engine.session_symbols=="" ? "--" : g_panel_engine.session_symbols),
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   string limits=g_panel_engine.session_max_entries>0 ?
      "Limits  "+EEA_SymbolPanelPercent(g_panel_engine.session_risk_fraction)+" per trade"+EEA_SymbolPanelSep()+
      EEA_SymbolPanelPercent(g_panel_engine.session_daily_loss_fraction)+" daily loss"+EEA_SymbolPanelSep()+
      "today scalp "+IntegerToString(g_panel_engine.session_entries_today)+"/"+IntegerToString(g_panel_engine.session_max_entries)+
      ", swing "+IntegerToString(g_panel_engine.session_swing_entries_today)+"/"+
      IntegerToString(g_panel_engine.session_max_swing_entries) :
      "Limits  taken from the committed risk policy (O-04) when you authorize";
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionLimits",EEA_PANEL_CONTENT_X,y+70,limits,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   string layers="Inputs "+((g_panel_engine.execution_enabled && g_panel_engine.live_armed) ? "ARMED" : "NOT ARMED (F7)")+
      EEA_SymbolPanelSep()+"Kill switch "+(g_panel_engine.controller_kill_active ? "ON" : "OFF")+
      EEA_SymbolPanelSep()+(g_panel_engine.session_real_account ? "REAL account" : "Demo account");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionLayers",EEA_PANEL_CONTENT_X,y+86,layers,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   bool c24=EEA_SymbolPanelSessionConfirming("SIGN_24H"), c7=EEA_SymbolPanelSessionConfirming("SIGN_7D");
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Session24h",EEA_PANEL_CONTENT_X,y+108,128,30,
                              c24 ? EEA_SymbolPanelGlyph(0x2713)+" 24h selected" : "Authorize 24h",
                              c24 ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_PRIMARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Session7d",EEA_PANEL_CONTENT_X+136,y+108,136,30,
                              c7 ? EEA_SymbolPanelGlyph(0x2713)+" 7 days selected" : "Authorize 7 days",
                              c7 ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_SECONDARY);
   // Accept signs the selected duration (disabled until one is chosen).
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_SessionAccept",EEA_PANEL_CONTENT_X+280,y+108,104,30,
                              "Accept",(c24 || c7) ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_DISABLED);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_SessionRevoke",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-120,
                              y+108,120,30,"Revoke now",
                              (active || !g_panel_engine.controller_kill_active) ? EEA_PANEL_BUTTON_DANGER : EEA_PANEL_BUTTON_DISABLED);
   string message=(c24 || c7) ? "Press Accept to sign "+(c24 ? "24h" : "7 days")+" (selection kept 60 s). Every candidate passing all risk checks may then be traded." :
                  g_panel_engine.session_message;
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionMessage",EEA_PANEL_CONTENT_X,y+146,
                          message=="" ? "Signing re-checks account, policy, ledger and broker state first." : message,
                          (c24 || c7) ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SessionNote",EEA_PANEL_CONTENT_X,y+166,
                          "Revoke stops new entries at once and cancels EA pending orders on the next closed bar.",
                          EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelSettingsAuthorization(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"AuthorizationSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,120,EEA_PANEL_SURFACE_COLOR);
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
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_TimeHint",EEA_PANEL_CONTENT_X,y+100,hint,hint_color,
                          EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSettingsSession(chart_id,y+128);
  }

bool EEA_SymbolPanelRecoveryConfirming()
  {
   return g_panel_state.recovery_confirm_tick>0 && GetTickCount()-g_panel_state.recovery_confirm_tick<10000;
  }

// Execution recovery: shown only while an entry's outcome is unknown and entries are
// blocked. Re-check asks the broker again; Mark resolved is the operator's attestation
// after checking the MT5 Trade and History tabs (two clicks).
void EEA_SymbolPanelSettingsRecovery(const long chart_id,const int y)
  {
   if(!g_panel_engine.recovery_blocked)
     {
      EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"RecoverySurface",EEA_PANEL_INNER_X,y,
                                EEA_PANEL_INNER_WIDTH,40,EEA_PANEL_SURFACE_COLOR);
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Recovery",EEA_PANEL_CONTENT_X,y+13,
                             EEA_SymbolPanelGlyph(0x2713)+"  Execution recovery clear: no entry with an unknown outcome.",
                             EEA_PANEL_OK_COLOR,EEA_PANEL_META_FONT_SIZE);
      EEA_SymbolPanelUnregisterHit(EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryRecheck");
      EEA_SymbolPanelUnregisterHit(EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryResolve");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryRecheck");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryResolve");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RecoveryDetail");
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RecoveryMessage");
      return;
     }
   bool confirming=EEA_SymbolPanelRecoveryConfirming();
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"RecoverySurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,96,EEA_PANEL_SURFACE_COLOR,EEA_PANEL_DANGER_COLOR);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Recovery",EEA_PANEL_CONTENT_X,y+10,
                          "ENTRIES BLOCKED: an order outcome is unknown",EEA_PANEL_DANGER_COLOR,EEA_PANEL_BODY_FONT_SIZE,
                          EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RecoveryDetail",EEA_PANEL_CONTENT_X,y+28,
                          g_panel_engine.recovery_detail,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryRecheck",EEA_PANEL_CONTENT_X,y+44,
                              150,28,"Re-check broker",EEA_PANEL_BUTTON_PRIMARY);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryResolve",EEA_PANEL_CONTENT_X+158,y+44,
                              190,28,confirming ? "Confirm: checked in MT5" : "Mark resolved",
                              confirming ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_DANGER);
   string message=confirming ? "Only confirm after checking the MT5 Trade and History tabs for this ticket." :
                  (g_panel_engine.recovery_message=="" ? "Re-check first; mark resolved only when the broker shows nothing." :
                   g_panel_engine.recovery_message);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_RecoveryMessage",EEA_PANEL_CONTENT_X,y+76,message,
                          confirming ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE);
  }

void EEA_SymbolPanelSettingsSystem(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"SystemSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,220,EEA_PANEL_SURFACE_COLOR);
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
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_Strategy",left,y+140,EEA_PANEL_STRATEGY_LABEL,
                           g_panel_engine.strategy_enabled ? "ENABLED" : "DISABLED",
                           g_panel_engine.strategy_enabled ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Sys_StrategyReason",right,y+140,"Strategy reason",
                           g_panel_engine.strategy_reason=="" ? "--" : g_panel_engine.strategy_reason,EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSettingsRecovery(chart_id,y+228);
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
                          EEA_SymbolPanelLivePathOpen() ?
                          "Safety  LIVE SESSION ACTIVE  |  settings here change policy and symbols, never send orders" :
                          "Safety  NOT_AUTHORIZED  |  "+EEA_PANEL_POLICY_PROPOSAL_ONLY+"  |  proposal only; no execution",
                          EEA_PANEL_WARNING_COLOR,7);
  }

void EEA_SymbolPanelRenderDashboard(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelBeginOverlay(chart_id,"DASHBOARD");
   EEA_SymbolPanelRenderViewBase(chart_id);
#ifdef EEA_S07_EDITION
   string tabs[EEA_PANEL_DASH_TABS]={"OVERVIEW","MARKET","TRADES","RISK","NEWS","CALENDAR"};
   string titles[EEA_PANEL_DASH_TABS]={"Overview","Market","Trades","Risk","News","Calendar"};
#else
   string tabs[EEA_PANEL_DASH_TABS]={"OVERVIEW","MARKET","TRADES","RISK","NEWS","AI","CALENDAR"};
   string titles[EEA_PANEL_DASH_TABS]={"Overview","Market","Trades","Risk","News","AI","Calendar"};
#endif
   for(int t=0;t<EEA_PANEL_DASH_TABS;t++)
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tab_"+tabs[t],EEA_PANEL_INNER_X+t*77,
                                 EEA_PANEL_VIEW_Y,73,24,titles[t],
                                 g_panel_state.dashboard_tab==tabs[t] ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,
                                 EEA_PANEL_META_FONT_SIZE);
   if(g_panel_state.dashboard_tab=="MARKET") EEA_SymbolPanelDashMarket(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="TRADES") EEA_SymbolPanelDashTrades(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="RISK") EEA_SymbolPanelDashRisk(chart_id,ctx);
   else if(g_panel_state.dashboard_tab=="NEWS") EEA_SymbolPanelDashNews(chart_id,ctx);
#ifndef EEA_S07_EDITION
   else if(g_panel_state.dashboard_tab=="AI") EEA_SymbolPanelDashAi(chart_id,ctx);
#endif
   else if(g_panel_state.dashboard_tab=="CALENDAR") EEA_SymbolPanelDashCalendar(chart_id,ctx);
   else EEA_SymbolPanelDashOverview(chart_id,ctx);
   ChartRedraw(chart_id);
  }

// O-18: Calendar and daily P/L use the operator's local day (terminal clock).
// FTMO floors and daily reset stay on Europe/Prague in the Risk Kernel.
long EEA_SymbolPanelLocalOffsetSeconds()
  {
   long offset=(long)(TimeLocal()-TimeGMT());
   long rounded=(offset>=0 ? offset+30 : offset-30)/60;
   return rounded*60;
  }

string EEA_SymbolPanelLocalZoneLabel()
  {
   long offset=EEA_SymbolPanelLocalOffsetSeconds();
   long minutes=MathAbs(offset)/60;
   string text="GMT"+(offset<0 ? "-" : "+")+IntegerToString(minutes/60);
   if(minutes%60!=0) text+=StringFormat(":%02d",(int)(minutes%60));
   return text;
  }

long EEA_SymbolPanelLocalDayIndex(const long utc_seconds)
  {
   return (utc_seconds+EEA_SymbolPanelLocalOffsetSeconds())/86400;
  }

double EEA_SymbolPanelRealizedForDay(const EEA_ObserverRuntimeContext &ctx,const long day_index)
  {
   double total=0.0;
   for(int i=0;i<ctx.reconciliation.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      // Only buy/sell deals are trading P/L; balance, credit and other cash flows are excluded.
      if(ctx.reconciliation.deals[i].type!="0" && ctx.reconciliation.deals[i].type!="1") continue;
      if(EEA_SymbolPanelLocalDayIndex(ctx.reconciliation.deals[i].time_utc)!=day_index) continue;
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
   double today=EEA_SymbolPanelRealizedForDay(ctx,EEA_SymbolPanelLocalDayIndex((long)TimeGMT()));
   int resolved=0;
   for(int i=0;i<ctx.symbol_count;i++) if(ctx.broker_symbols[i]!="") resolved++;
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_Today",EEA_PANEL_INNER_X,y+68,128,"TODAY P/L",
                          EEA_SymbolPanelSigned(today,2),EEA_SymbolPanelPnlColor(today),"local day "+EEA_SymbolPanelLocalZoneLabel()+", realized");
   string risk_value="--", risk_note="open SL risk unavailable";
   color risk_color=EEA_PANEL_MUTED_COLOR;
   if(g_panel_engine.active_risk_valid)
     {
      risk_value=EEA_SymbolPanelFormatNumber(g_panel_engine.active_risk_money,2);
      risk_note=g_panel_engine.active_risk_capital>0.0 ?
         EEA_SymbolPanelPercent(g_panel_engine.active_risk_money/g_panel_engine.active_risk_capital)+" of capital at SL" :
         "loss at SL";
      risk_color=g_panel_engine.active_risk_money>0.0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR;
     }
   EEA_SymbolPanelSetTile(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tile_ActiveRisk",EEA_PANEL_INNER_X+136,y+68,128,"ACTIVE RISK",
                          risk_value,risk_color,risk_note);
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
   bool live_open=EEA_SymbolPanelLivePathOpen();
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Entries",left,s+60,"New entries",
                           live_open && g_panel_engine.operator_paused ? "PAUSED by operator (Telegram)" :
                           live_open ? "LIVE - each candidate risk-gated" :
                           (ctx.status.new_entries_blocked ? "BLOCKED (observer only)" : "REVIEW"),
                           live_open && g_panel_engine.operator_paused ? EEA_PANEL_DANGER_COLOR :
                           live_open ? EEA_PANEL_WARNING_COLOR :
                           (ctx.status.new_entries_blocked ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_WARNING_COLOR));
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Execution",right,s+60,"Execution",
                           g_panel_engine.execution_enabled ? (g_panel_engine.live_armed ? "ENABLED / ARMED" : "ENABLED") :
                           "EXECUTION_DISABLED",
                           g_panel_engine.execution_enabled ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_TEXT_COLOR);
   bool live_gated=g_panel_engine.execution_enabled && g_panel_engine.live_armed &&
                   g_panel_engine.controller_allows_market && !g_panel_engine.recovery_blocked;
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Live",left,s+92,"Live authorization",
                           live_gated ? (g_panel_engine.session_state=="ACTIVE" ? "SESSION ACTIVE" : "NO SESSION") :
                           "NOT_AUTHORIZED",
                           live_gated ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_DANGER_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Kill",right,s+92,"Kill switch / controller",
                           (g_panel_engine.controller_kill_active ? "ACTIVE" : "RELEASED")+
                           "  ("+g_panel_engine.controller_status+")"+
                           (g_panel_engine.recovery_blocked ? "  RECOVERY BLOCKED" : ""),
                           g_panel_engine.controller_kill_active || g_panel_engine.recovery_blocked ?
                           EEA_PANEL_DANGER_COLOR : EEA_PANEL_WARNING_COLOR,40);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_Strategy",left,s+124,EEA_PANEL_STRATEGY_STATUS,
                           (g_panel_engine.strategy_enabled ? "ENABLED" : "DISABLED")+
                           (g_panel_engine.trade_manager_reason=="" ? "" :
                            "  "+StringSubstr(g_panel_engine.trade_manager_reason,StringLen("TRADE_MANAGER_"))),
                           g_panel_engine.strategy_enabled ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR);
   EEA_SymbolPanelSetField(chart_id,EEA_PANEL_OVERLAY_PREFIX+"St_External",right,s+124,"Live engine - last decision",
                           g_panel_engine.live_reason=="" ? "--" : g_panel_engine.live_reason,
                           EEA_PANEL_MUTED_COLOR,40);

   int e=s+172;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"EvidenceSurface",EEA_PANEL_INNER_X,e,
                             EEA_PANEL_INNER_WIDTH,96,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_EvidenceTitle",EEA_PANEL_CONTENT_X,e+10,
                             "EVIDENCE"+EEA_SymbolPanelSep()+"Evidence freshness:");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Freshness",EEA_PANEL_CONTENT_X,e+28,
                          "observed  "+EEA_SymbolPanelReadableUtc(ctx.reconciliation.observed_at_utc)+
                          "   valid until  "+EEA_SymbolPanelClockUtc(ctx.reconciliation.valid_until_utc),
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

   // G11: one-line market sentiment (details on the Market tab). Reduce-only, never adds risk.
   int m=e+104;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"SentimentSurface",EEA_PANEL_INNER_X,m,
                             EEA_PANEL_INNER_WIDTH,44,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SentimentTitle",EEA_PANEL_CONTENT_X,m+8,
                             "MARKET SENTIMENT"+EEA_SymbolPanelSep()+"reduce-only");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_SentimentSummary",EEA_PANEL_CONTENT_X,m+26,
                          g_panel_engine.sentiment_ok ? g_panel_engine.sentiment_summary :
                          "unavailable: neutral, no effect on entries ("+g_panel_engine.sentiment_reason+")",
                          g_panel_engine.sentiment_ok ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR,
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
   string labels[6]={"Symbol","Broker","Status","Digits","Trade mode",EEA_PANEL_SETUP_COLUMN};
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
      EEA_SymbolPanelSetText(chart_id,n+"_b",104,ry+6,row.broker=="" ? EEA_SymbolPanelBlockReason(ctx,i) : row.broker,
                             row.broker=="" ? EEA_PANEL_WARNING_COLOR : text_color,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_LEFT_UPPER,16);
      EEA_SymbolPanelSetText(chart_id,n+"_s",214,ry+6,row.status,status_color,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_d",330,ry+6,IntegerToString(row.digits),text_color,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_m",352,ry+6,row.trade_mode,EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,16);
      string setup=row.context_only ? "--" : EEA_SymbolPanelSetupState(row.canonical);
      bool setup_idle=(setup=="OFF" || setup=="--" || setup=="IDLE" || setup=="SC:IDLE SW:IDLE");
      EEA_SymbolPanelSetText(chart_id,n+"_u",452,ry+7,setup,
                             setup_idle ? EEA_PANEL_FAINT_COLOR : EEA_PANEL_ACCENT_COLOR,
                             7,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,22);
      // Hover shows the confluence zone, sources and HTF structure behind the state.
      string detail=row.context_only ? "" : EEA_SymbolPanelSetupDetail(row.canonical);
      ObjectSetString(chart_id,n+"_u",OBJPROP_TOOLTIP,detail=="" ? "\n" : detail);
      line++;
     }
   string dxy_broker="";
   int total=SymbolsTotal(false);
   for(int k=0;k<total;k++)
     {
      string candidate=SymbolName(k,false);
      if(EEA_TrimUpper(candidate)=="USDX." || EEA_TrimUpper(candidate)=="USDX" || EEA_TrimUpper(candidate)=="USDIND")
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
   EEA_SymbolPanelSentiment(chart_id,y+46+MathMax(line,1)*EEA_PANEL_TABLE_ROW_HEIGHT+10);
  }

// Market sentiment: currency strength (4h / 24h, ATR-normalised), risk regime and how the
// flow agrees with a buy or a sell on each selected symbol. Reduce-only filter.
void EEA_SymbolPanelSentiment(const long chart_id,const int y)
  {
   string p=EEA_PANEL_OVERLAY_PREFIX+"Sent_";
   EEA_SymbolPanelSetCaption(chart_id,p+"Title",EEA_PANEL_CONTENT_X,y,
                             "MARKET SENTIMENT"+EEA_SymbolPanelSep()+"CURRENCY STRENGTH 4H / 24H"+EEA_SymbolPanelSep()+
                             (g_panel_engine.sentiment_ok ? g_panel_engine.sentiment_regime : g_panel_engine.sentiment_reason));
   if(!g_panel_engine.sentiment_ok)
     {
      EEA_SymbolPanelSetText(chart_id,p+"Off",EEA_PANEL_CONTENT_X,y+20,
                             "Sentiment unavailable: neutral, no effect on entries ("+g_panel_engine.sentiment_reason+").",
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
      return;
     }
   ObjectDelete(chart_id,p+"Off");
   for(int c=0;c<8;c++)
     {
      int col=c%4, row=c/4;
      int x=EEA_PANEL_CONTENT_X+col*130, ry=y+20+row*20;
      double v=g_panel_engine.sentiment_s4[c];
      color tone=v>=0.3 ? EEA_PANEL_OK_COLOR : (v<=-0.3 ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_MUTED_COLOR);
      EEA_SymbolPanelSetText(chart_id,p+"Ccy_"+IntegerToString(c),x,ry,
                             g_panel_engine.sentiment_ccy[c]+"  "+DoubleToString(v,2)+" / "+
                             DoubleToString(g_panel_engine.sentiment_s24[c],2),tone,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
     }
   int sy=y+64;
   for(int i=0;i<6;i++)
     {
      string n=p+"Sym_"+IntegerToString(i);
      if(i>=g_panel_engine.sentiment_symbol_count) { ObjectDelete(chart_id,n); continue; }
      EEA_SymbolPanelSetText(chart_id,n,EEA_PANEL_CONTENT_X,sy+i*16,
                             g_panel_engine.sentiment_symbol[i]+"   "+g_panel_engine.sentiment_symbol_text[i],
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_LEFT_UPPER,90);
     }
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
                             EEA_SymbolPanelSep()+"PENDING ORDERS  ("+IntegerToString(ctx.reconciliation.order_count)+")"+
                             EEA_SymbolPanelSep()+"click an EA symbol to act");
   string labels[8]={"Symbol","Side","Volume","Open","Current","SL","TP","P/L"};
   int xs[8]={24,112,206,284,360,424,486,540};
   bool right[8]={false,false,true,true,true,true,true,true};
   EEA_SymbolPanelTableHeader(chart_id,y+20,labels,xs,right,8);
   EEA_SymbolPanelClearDashboardRows(chart_id);
   EEA_SymbolPanelPruneHits(EEA_PANEL_OVERLAY_PREFIX+"Tr_Sel");
   for(int k=0;k<20;k++) ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tr_Sel_"+IntegerToString(k));
   double floating=0.0;
   int shown=0;
   bool selection_alive=false;
   for(int i=0;i<ctx.reconciliation.position_count && i<EEA_RUNTIME_MAX_POSITIONS;i++)
     {
      double pnl=ctx.reconciliation.positions[i].profit+ctx.reconciliation.positions[i].swap;
      floating+=pnl;
      if(shown>=9) continue;
      int ry=y+46+shown*EEA_PANEL_TABLE_ROW_HEIGHT;
      string n=EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(shown);
      int digits=EEA_SymbolPanelDigitsForBroker(ctx,ctx.reconciliation.positions[i].symbol);
      bool buy=ctx.reconciliation.positions[i].type=="0";
      long ticket=ctx.reconciliation.positions[i].ticket;
      string profile=EEA_SymbolPanelEaProfile(ticket);
      bool selected=(g_panel_state.trade_selected_kind=="POSITION" && g_panel_state.trade_selected_ticket==ticket);
      if(selected) selection_alive=true;
      EEA_SymbolPanelTableRowBase(chart_id,shown,ry);
      if(profile!="")
         EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tr_Sel_"+IntegerToString(shown),16,ry+3,90,20,
                                    ctx.reconciliation.positions[i].symbol,
                                    selected ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,EEA_PANEL_META_FONT_SIZE);
      else
         EEA_SymbolPanelSetText(chart_id,n,24,ry+6,ctx.reconciliation.positions[i].symbol+"  ext",EEA_PANEL_MUTED_COLOR,
                                EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,13);
      g_panel_state.trade_row_kind[shown]="POSITION"; g_panel_state.trade_row_ticket[shown]=ticket;
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
   // EA pending orders (REQ-021) below the positions.
   for(int i=0;i<ctx.reconciliation.order_count && shown<11;i++)
     {
      long ticket=ctx.reconciliation.orders[i].ticket;
      if(!EEA_SymbolPanelIsEaOrder(ticket)) continue;
      int ry=y+46+shown*EEA_PANEL_TABLE_ROW_HEIGHT;
      string n=EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(shown);
      int digits=EEA_SymbolPanelDigitsForBroker(ctx,ctx.reconciliation.orders[i].symbol);
      int type=(int)StringToInteger(ctx.reconciliation.orders[i].type);
      string type_name=type==ORDER_TYPE_BUY_LIMIT ? "BUY LMT" : type==ORDER_TYPE_SELL_LIMIT ? "SELL LMT" :
                       type==ORDER_TYPE_BUY_STOP ? "BUY STP" : type==ORDER_TYPE_SELL_STOP ? "SELL STP" : "ORDER";
      bool selected=(g_panel_state.trade_selected_kind=="ORDER" && g_panel_state.trade_selected_ticket==ticket);
      if(selected) selection_alive=true;
      EEA_SymbolPanelTableRowBase(chart_id,shown,ry);
      EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Tr_Sel_"+IntegerToString(shown),16,ry+3,90,20,
                                 ctx.reconciliation.orders[i].symbol,
                                 selected ? EEA_PANEL_BUTTON_SELECTED : EEA_PANEL_BUTTON_GHOST,EEA_PANEL_META_FONT_SIZE);
      g_panel_state.trade_row_kind[shown]="ORDER"; g_panel_state.trade_row_ticket[shown]=ticket;
      EEA_SymbolPanelSetText(chart_id,n+"_side",112,ry+6,type_name,EEA_PANEL_ACCENT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetText(chart_id,n+"_vol",206,ry+6,DoubleToString(ctx.reconciliation.orders[i].volume,2),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_open",284,ry+6,DoubleToString(ctx.reconciliation.orders[i].price,digits),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_sl",424,ry+6,DoubleToString(ctx.reconciliation.orders[i].sl,digits),
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_tp",486,ry+6,DoubleToString(ctx.reconciliation.orders[i].tp,digits),
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER);
      EEA_SymbolPanelSetText(chart_id,n+"_pnl",540,ry+6,"pending",EEA_PANEL_FAINT_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_RIGHT_UPPER);
      shown++;
     }
   g_panel_state.trade_row_count=shown;
   if(!selection_alive) { g_panel_state.trade_selected_kind=""; g_panel_state.trade_selected_ticket=0; }
   int after=y+46+(shown>0 ? shown : 1)*EEA_PANEL_TABLE_ROW_HEIGHT+8;
   if(shown==0)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_Empty",EEA_PANEL_CONTENT_X,y+52,
                             "No open positions on this account.",EEA_PANEL_MUTED_COLOR,EEA_PANEL_BODY_FONT_SIZE);
   else
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_Total",540,after,
                             "Floating (profit + swap)  "+EEA_SymbolPanelSigned(floating,2)+" "+ctx.account.account_currency,
                             EEA_SymbolPanelPnlColor(floating),EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_RIGHT_UPPER);
   EEA_SymbolPanelTradeActions(chart_id,ctx);
  }

string EEA_SymbolPanelEaProfile(const long position_ticket)
  {
   for(int i=0;i<g_panel_engine.ea_position_count;i++)
      if(g_panel_engine.ea_position_ticket[i]==position_ticket) return g_panel_engine.ea_position_profile[i];
   return "";
  }

bool EEA_SymbolPanelIsEaOrder(const long ticket)
  {
   for(int i=0;i<g_panel_engine.ea_order_count;i++) if(g_panel_engine.ea_order_ticket[i]==ticket) return true;
   return false;
  }

bool EEA_SymbolPanelTradeConfirming()
  {
   return g_panel_state.trade_pending_action!="" && GetTickCount()-g_panel_state.trade_confirm_tick<15000;   // C5
  }

// Manual actions through the command queue (spec 9.2, G8): select, act, confirm.
void EEA_SymbolPanelTradeActions(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   string p=EEA_PANEL_OVERLAY_PREFIX+"Tr_";
   int bar=EEA_PANEL_STATUSBAR_Y-84;
   if(!EEA_SymbolPanelTradeConfirming()) { g_panel_state.trade_pending_action=""; }
   if(g_panel_state.trade_closeall_stage>0 && GetTickCount()-g_panel_state.trade_closeall_tick>=10000)
      g_panel_state.trade_closeall_stage=0;
   string objects[11]={"Close","Partial","Be","Trail","Cancel","Confirm","Abort","CloseAll","Line1","Line2","Last"};
   for(int i=0;i<11;i++) ObjectDelete(chart_id,p+objects[i]);
   EEA_SymbolPanelPruneHits(p);
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"ActionsSurface",EEA_PANEL_INNER_X,bar,
                             EEA_PANEL_INNER_WIDTH,74,EEA_PANEL_SURFACE_COLOR,
                             g_panel_state.trade_pending_action!="" || g_panel_state.trade_closeall_stage>0 ?
                             EEA_PANEL_WARNING_COLOR : EEA_PANEL_BORDER_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ActionsTitle",EEA_PANEL_CONTENT_X,bar+8,
                             "MANUAL ACTIONS"+EEA_SymbolPanelSep()+"command queue"+EEA_SymbolPanelSep()+
                             "close / partial / BE / trail / cancel");
   EEA_SymbolPanelSetText(chart_id,p+"Last",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X,bar+8,
                          g_panel_engine.cmd_last=="" ? "" : "Last: "+g_panel_engine.cmd_last,EEA_PANEL_MUTED_COLOR,7,
                          EEA_PANEL_FONT,ANCHOR_RIGHT_UPPER,52);
   if(!g_panel_engine.cmd_armed)
     {
      EEA_SymbolPanelSetText(chart_id,p+"Line1",EEA_PANEL_CONTENT_X,bar+30,
                             "EA not armed: manual actions are locked. Use MT5 directly.",EEA_PANEL_WARNING_COLOR,
                             EEA_PANEL_META_FONT_SIZE);
      return;
     }
   int ea_items=g_panel_engine.ea_position_count+g_panel_engine.ea_order_count;
   if(g_panel_state.trade_closeall_stage>0)
     {
      EEA_SymbolPanelSetText(chart_id,p+"Line1",EEA_PANEL_CONTENT_X,bar+26,
                             "Close ALL EA positions ("+IntegerToString(g_panel_engine.ea_position_count)+") and cancel EA pending orders ("+
                             IntegerToString(g_panel_engine.ea_order_count)+")?",EEA_PANEL_WARNING_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Confirm",EEA_PANEL_CONTENT_X,bar+44,220,24,
                                 g_panel_state.trade_closeall_stage==1 ? "Confirm close all" :
                                 "Click again: close all ("+IntegerToString(ea_items)+")",
                                 g_panel_state.trade_closeall_stage==1 ? EEA_PANEL_BUTTON_WARNING : EEA_PANEL_BUTTON_DANGER);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Abort",EEA_PANEL_CONTENT_X+228,bar+44,90,24,"Cancel",EEA_PANEL_BUTTON_SECONDARY);
      return;
     }
   if(ea_items>0)
      EEA_SymbolPanelSetButtonEx(chart_id,p+"CloseAll",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-110,bar+44,110,24,"Close all EA",
                                 EEA_PANEL_BUTTON_DANGER);
   if(g_panel_state.trade_selected_kind=="")
     {
      EEA_SymbolPanelSetText(chart_id,p+"Line1",EEA_PANEL_CONTENT_X,bar+30,
                             ea_items>0 ? "Click the symbol of an EA position or pending order to act on it." :
                             "No EA position or pending order. Positions marked 'ext' are managed outside the EA.",
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
      return;
     }
   // Selected row summary.
   string summary="";
   double volume=0.0, sl=0.0;
   for(int i=0;i<ctx.reconciliation.position_count;i++)
      if(g_panel_state.trade_selected_kind=="POSITION" && ctx.reconciliation.positions[i].ticket==g_panel_state.trade_selected_ticket)
        {
         volume=ctx.reconciliation.positions[i].volume; sl=ctx.reconciliation.positions[i].sl;
         summary=ctx.reconciliation.positions[i].symbol+" #"+IntegerToString(g_panel_state.trade_selected_ticket)+"  "+
                 (ctx.reconciliation.positions[i].type=="0" ? "BUY" : "SELL")+" "+DoubleToString(volume,2)+" lot  P/L "+
                 EEA_SymbolPanelSigned(ctx.reconciliation.positions[i].profit+ctx.reconciliation.positions[i].swap,2)+
                 "  SL "+(sl>0.0 ? DoubleToString(sl,EEA_SymbolPanelDigitsForBroker(ctx,ctx.reconciliation.positions[i].symbol)) : "none")+
                 "  "+EEA_SymbolPanelEaProfile(g_panel_state.trade_selected_ticket);
        }
   for(int i=0;i<ctx.reconciliation.order_count;i++)
      if(g_panel_state.trade_selected_kind=="ORDER" && ctx.reconciliation.orders[i].ticket==g_panel_state.trade_selected_ticket)
        {
         volume=ctx.reconciliation.orders[i].volume;
         summary=ctx.reconciliation.orders[i].symbol+" #"+IntegerToString(g_panel_state.trade_selected_ticket)+"  pending "+
                 DoubleToString(volume,2)+" lot";
        }
   g_panel_state.trade_selected_volume=volume; g_panel_state.trade_selected_sl=sl;
   if(g_panel_state.trade_pending_action!="")
     {
      string act=g_panel_state.trade_pending_action;
      string label=act=="PARTIAL" ? "Close "+DoubleToString(g_panel_state.trade_partial_fraction*100.0,0)+"% of" :
                   act=="BE" ? "Move SL to break-even on" : act=="TRAIL" ? "Start trailing on" :
                   act=="CANCEL" ? "Cancel pending order" : "Close";
      EEA_SymbolPanelSetText(chart_id,p+"Line1",EEA_PANEL_CONTENT_X,bar+26,label+"  "+summary,EEA_PANEL_WARNING_COLOR,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,92);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Confirm",EEA_PANEL_CONTENT_X,bar+44,110,24,"Confirm",EEA_PANEL_BUTTON_WARNING);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Abort",EEA_PANEL_CONTENT_X+118,bar+44,80,24,"Cancel",EEA_PANEL_BUTTON_SECONDARY);
      if(act=="PARTIAL")
         EEA_SymbolPanelSetButtonEx(chart_id,p+"Partial",EEA_PANEL_CONTENT_X+206,bar+44,90,24,
                                    "Size "+DoubleToString(g_panel_state.trade_partial_fraction*100.0,0)+"%",EEA_PANEL_BUTTON_GHOST);
      return;
     }
   EEA_SymbolPanelSetText(chart_id,p+"Line1",EEA_PANEL_CONTENT_X,bar+26,summary,EEA_PANEL_TEXT_COLOR,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD,ANCHOR_LEFT_UPPER,92);
   if(g_panel_state.trade_selected_kind=="ORDER")
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Cancel",EEA_PANEL_CONTENT_X,bar+44,100,24,"Cancel order",EEA_PANEL_BUTTON_SECONDARY);
   else
     {
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Close",EEA_PANEL_CONTENT_X,bar+44,70,24,"Close",EEA_PANEL_BUTTON_SECONDARY);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Partial",EEA_PANEL_CONTENT_X+76,bar+44,50,24,"½",EEA_PANEL_BUTTON_SECONDARY);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Be",EEA_PANEL_CONTENT_X+132,bar+44,50,24,"BE",EEA_PANEL_BUTTON_SECONDARY);
      EEA_SymbolPanelSetButtonEx(chart_id,p+"Trail",EEA_PANEL_CONTENT_X+188,bar+44,60,24,"Trail",EEA_PANEL_BUTTON_SECONDARY);
     }
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

void EEA_SymbolPanelNewsStateColors(const string state,color &fill,color &text_color)
  {
   fill=EEA_PANEL_SURFACE_ALT_COLOR; text_color=EEA_PANEL_MUTED_COLOR;
   if(state=="NORMAL") { fill=EEA_PANEL_OK_FILL_COLOR; text_color=EEA_PANEL_OK_COLOR; }
   else if(state=="PRE_NEWS" || state=="NORMALIZING") { fill=EEA_PANEL_WARNING_FILL_COLOR; text_color=EEA_PANEL_WARNING_COLOR; }
   else if(state=="PRE_NEWS_BLOCK" || state=="ACTIVE" || state=="POST_NEWS" || state=="UNKNOWN")
     { fill=EEA_PANEL_DANGER_FILL_COLOR; text_color=EEA_PANEL_DANGER_COLOR; }
  }

// News Guard (REQ-007 subset): calendar status, per-symbol state and upcoming HIGH events.
// A calendar that cannot be read shows NEWS_UNKNOWN and is never treated as NORMAL.
void EEA_SymbolPanelDashNews(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   bool unknown=(StringFind(g_panel_engine.news_reason,"REFRESHED")<0 && g_panel_engine.news_reason!="NEWS_GUARD_DISABLED");
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"NewsSurface",EEA_PANEL_INNER_X,y,
                             EEA_PANEL_INNER_WIDTH,62,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_News",EEA_PANEL_CONTENT_X,y+8,
                             "NEWS GUARD"+EEA_SymbolPanelSep()+"MT5 ECONOMIC CALENDAR"+EEA_SymbolPanelSep()+"HIGH ONLY");
   EEA_SymbolPanelSetPill(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Pill_News",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-150,y+5,150,
                          unknown ? "NEWS_UNKNOWN" : (g_panel_engine.news_reason=="NEWS_GUARD_DISABLED" ? "DISABLED" : "CALENDAR OK"),
                          unknown ? EEA_PANEL_DANGER_FILL_COLOR : EEA_PANEL_OK_FILL_COLOR,
                          unknown ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_OK_COLOR);
   long offset=EEA_SymbolPanelLocalOffsetSeconds();
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsStatus",EEA_PANEL_CONTENT_X,y+28,
                          "Last read  "+(g_panel_engine.news_last_success_utc>0 ?
                          TimeToString((datetime)(g_panel_engine.news_last_success_utc+offset),TIME_DATE|TIME_MINUTES) : "never")+
                          EEA_SymbolPanelSep()+g_panel_engine.news_reason,
                          unknown ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsPolicy",EEA_PANEL_CONTENT_X,y+44,
                          g_panel_engine.news_health_line!="" ? g_panel_engine.news_health_line : g_panel_engine.news_policy,
                          g_panel_engine.news_health_warn>0 ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_FAINT_COLOR,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,100);
   ObjectSetString(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsPolicy",OBJPROP_TOOLTIP,
                   g_panel_engine.news_policy=="" ? "\n" : g_panel_engine.news_policy);
   int sy=y+70;
   for(int i=0;i<8;i++)
     {
      string row=EEA_PANEL_OVERLAY_PREFIX+"NewsSym_"+IntegerToString(i);
      if(i>=g_panel_engine.news_symbol_count)
        { ObjectDelete(chart_id,row+"_Name"); ObjectDelete(chart_id,row+"_Pill"); ObjectDelete(chart_id,row+"_Detail"); continue; }
      color fill,text_color;
      EEA_SymbolPanelNewsStateColors(g_panel_engine.news_state[i],fill,text_color);
      EEA_SymbolPanelSetText(chart_id,row+"_Name",EEA_PANEL_CONTENT_X,sy+i*24+4,g_panel_engine.news_symbol[i],
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_BODY_FONT_SIZE,EEA_PANEL_FONT_BOLD);
      EEA_SymbolPanelSetPill(chart_id,row+"_Pill",EEA_PANEL_CONTENT_X+76,sy+i*24,124,g_panel_engine.news_state[i],fill,text_color);
      bool watch=(g_panel_engine.news_state[i]=="NORMAL" && g_panel_engine.news_watch[i]!="");
      if(watch)
         EEA_SymbolPanelSetPill(chart_id,row+"_Pill",EEA_PANEL_CONTENT_X+76,sy+i*24,124,"WATCH (indirect)",
                                EEA_PANEL_WARNING_FILL_COLOR,EEA_PANEL_WARNING_COLOR);
      EEA_SymbolPanelSetText(chart_id,row+"_Detail",EEA_PANEL_CONTENT_X+210,sy+i*24+5,
                             watch ? g_panel_engine.news_watch[i] : g_panel_engine.news_detail[i],
                             watch ? EEA_PANEL_WARNING_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,
                             EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,52);
     }
   int ey=sy+MathMin(g_panel_engine.news_symbol_count,8)*24+8;
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsEvents",EEA_PANEL_CONTENT_X,ey,
                             "UPCOMING HIGH IMPACT"+EEA_SymbolPanelSep()+EEA_SymbolPanelLocalZoneLabel());
   int recent_rows=g_panel_engine.news_recent_count;
   int recent_h=recent_rows>0 ? 22+recent_rows*16 : 0;
   int max_rows=MathMax(0,MathMin(EEA_PANEL_NEWS_ROWS,(EEA_PANEL_STATUSBAR_Y-ey-24-recent_h)/26));
   for(int i=0;i<EEA_PANEL_NEWS_ROWS;i++)
     {
      string row=EEA_PANEL_OVERLAY_PREFIX+"NewsEvt_"+IntegerToString(i);
      if(i>=g_panel_engine.news_event_count || i>=max_rows)
        { ObjectDelete(chart_id,row+"_Time"); ObjectDelete(chart_id,row+"_Name"); ObjectDelete(chart_id,row+"_Val");
          ObjectDelete(chart_id,row+"_Stats"); continue; }
      int ry=ey+18+i*26;
      EEA_SymbolPanelSetText(chart_id,row+"_Time",EEA_PANEL_CONTENT_X,ry,
                             TimeToString((datetime)(g_panel_engine.news_event_utc[i]+offset),TIME_DATE|TIME_MINUTES),
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
      EEA_SymbolPanelSetText(chart_id,row+"_Name",EEA_PANEL_CONTENT_X+120,ry,g_panel_engine.news_event_text[i],
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,40);
      EEA_SymbolPanelSetText(chart_id,row+"_Val",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X,ry,g_panel_engine.news_event_values[i],
                             EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER,30);
      EEA_SymbolPanelSetText(chart_id,row+"_Stats",EEA_PANEL_CONTENT_X+120,ry+12,
                             g_panel_engine.news_event_stats[i]=="" ? "no reaction history yet" : g_panel_engine.news_event_stats[i],
                             EEA_PANEL_FAINT_COLOR,7,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,90);
     }
   if(g_panel_engine.news_event_count==0)
      EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"NewsEvt_None",EEA_PANEL_CONTENT_X,ey+20,
                             unknown ? "Calendar unavailable: news state is NEWS_UNKNOWN, never NORMAL." :
                             "No HIGH impact event in the next 7 days for the selected symbols.",
                             unknown ? EEA_PANEL_DANGER_COLOR : EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE);
   else
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"NewsEvt_None");
   // Latest recorded reactions (measurement only).
   int ry0=ey+18+MathMin(max_rows,g_panel_engine.news_event_count)*26+6;
   if(g_panel_engine.news_event_count==0) ry0=ey+42;
   if(recent_rows>0)
      EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsRecent",EEA_PANEL_CONTENT_X,ry0,
                                "RECENT REACTIONS"+EEA_SymbolPanelSep()+g_panel_engine.news_reaction_reason);
   else
      ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_NewsRecent");
   for(int i=0;i<3;i++)
     {
      string name=EEA_PANEL_OVERLAY_PREFIX+"NewsRecent_"+IntegerToString(i);
      if(i>=recent_rows) { ObjectDelete(chart_id,name); continue; }
      EEA_SymbolPanelSetText(chart_id,name,EEA_PANEL_CONTENT_X,ry0+18+i*16,g_panel_engine.news_recent[i],
                             EEA_PANEL_TEXT_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,96);
     }
  }

// AI Bridge v1 (Level 0/1): bridge status, buttons and the latest report of each type.
// AI only reports and recommends; the EA never acts on it.
void EEA_SymbolPanelDashAi(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   int y=EEA_PANEL_CONTENT_Y;
   string p=EEA_PANEL_OVERLAY_PREFIX+"Ai_";
   bool online=(g_panel_engine.ai_status=="ONLINE");
   EEA_SymbolPanelSetSurface(chart_id,p+"Surface",EEA_PANEL_INNER_X,y,EEA_PANEL_INNER_WIDTH,62,EEA_PANEL_SURFACE_COLOR);
   EEA_SymbolPanelSetCaption(chart_id,p+"Title",EEA_PANEL_CONTENT_X,y+8,
                             "AI BRIDGE"+EEA_SymbolPanelSep()+"LEVEL 0/1: REPORTS ONLY, NEVER TRADES");
   EEA_SymbolPanelSetPill(chart_id,p+"Pill",EEA_PANEL_MAIN_WIDTH-EEA_PANEL_CONTENT_X-150,y+5,150,g_panel_engine.ai_status,
                          online ? EEA_PANEL_OK_FILL_COLOR : EEA_PANEL_WARNING_FILL_COLOR,
                          online ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
   EEA_SymbolPanelSetText(chart_id,p+"Status",EEA_PANEL_CONTENT_X,y+28,g_panel_engine.ai_status_line,
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,ANCHOR_LEFT_UPPER,100);
   EEA_SymbolPanelSetButtonEx(chart_id,p+"BtnAsk",EEA_PANEL_CONTENT_X,y+68,150,26,"Ask AI (status)",EEA_PANEL_BUTTON_PRIMARY);
   EEA_SymbolPanelSetButtonEx(chart_id,p+"BtnReview",EEA_PANEL_CONTENT_X+158,y+68,170,26,"Review news data now",
                              EEA_PANEL_BUTTON_SECONDARY);
   int ry=y+104;
   for(int t=0;t<EEA_AI_VIEW_SLOTS;t++)
     {
      EEA_SymbolPanelSetCaption(chart_id,p+"RT_"+IntegerToString(t),EEA_PANEL_CONTENT_X,ry,g_panel_engine.ai_title[t]);
      ry+=15;   // 6 slots must fit above the status bar (y 572): tighter header/line/gap pitch
      int shown=MathMin(g_panel_engine.ai_line_count[t],t==0 ? 5 : 2);
      for(int i=0;i<5;i++)
        {
         string n=p+"RL_"+IntegerToString(t)+"_"+IntegerToString(i);
         if(i>=shown) { ObjectDelete(chart_id,n); continue; }
         string line=g_panel_engine.ai_lines[t*8+i];
         color tone=StringFind(line,"[WARN]")==0 ? EEA_PANEL_WARNING_COLOR : (StringFind(line,">")==0 ? EEA_PANEL_ACCENT_COLOR :
                    EEA_PANEL_TEXT_COLOR);
         EEA_SymbolPanelSetText(chart_id,n,EEA_PANEL_CONTENT_X+8,ry,line,tone,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT,
                                ANCHOR_LEFT_UPPER,96);
         ObjectSetString(chart_id,n,OBJPROP_TOOLTIP,line);
         ry+=13;
        }
      ry+=4;
     }
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

string EEA_SymbolPanelCalendarModeLabel(const int mode)
  {
   return mode==1 ? "%" : (mode==2 ? "R" : "MONEY");
  }

string EEA_SymbolPanelSignedPercent(const double value)
  {
   return EEA_SymbolPanelSigned(value,2)+"%";
  }

// REQ-010 calendar cell: MONEY = realized net, % = net / start balance, R = sum of the realized R of the day.
string EEA_SymbolPanelCalendarCell(const int mode,const bool active,const double net,const bool has_start,
                                   const double start_balance,const int r_count,const double r_sum)
  {
   if(mode==1)
     {
      if(!has_start || start_balance<=0.0) return "n/a";
      return active ? EEA_SymbolPanelSignedPercent(net/start_balance*100.0) : "0%";
     }
   if(mode==2) return r_count>0 ? EEA_SymbolPanelSigned(r_sum,2)+"R" : "-";
   return active ? EEA_SymbolPanelSigned(net,MathAbs(net)>=1000.0 ? 0 : 2) : "0";
  }

void EEA_SymbolPanelDashCalendar(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   MqlDateTime now;
   TimeToStruct((datetime)((long)TimeGMT()+EEA_SymbolPanelLocalOffsetSeconds()),now);
   if(g_panel_state.calendar_year<=0) { g_panel_state.calendar_year=now.year; g_panel_state.calendar_month=now.mon; }
   int year=g_panel_state.calendar_year, month=g_panel_state.calendar_month;
   int next_year=month==12 ? year+1 : year, next_month=month==12 ? 1 : month+1;
   long first_day=EEA_SymbolPanelDaysFromCivil(year,month,1);
   int days_in_month=(int)(EEA_SymbolPanelDaysFromCivil(next_year,next_month,1)-first_day);
   int first_weekday=(int)((first_day+3)%7); // Monday = 0; 1970-01-01 was a Thursday.
   long today=EEA_SymbolPanelLocalDayIndex((long)TimeGMT());
   long loaded_from=ctx.reconciliation.history_from_utc>0 ? EEA_SymbolPanelLocalDayIndex(ctx.reconciliation.history_from_utc) : today;

   double net[32]; int trades[32]; int wins[32]; int losses[32]; double gross_profit[32]; double gross_loss[32]; bool active[32];
   for(int d=0;d<32;d++) { net[d]=0.0; trades[d]=0; wins[d]=0; losses[d]=0; gross_profit[d]=0.0; gross_loss[d]=0.0; active[d]=false; }
   for(int i=0;i<ctx.reconciliation.deal_count && i<EEA_RUNTIME_MAX_DEALS;i++)
     {
      if(ctx.reconciliation.deals[i].type!="0" && ctx.reconciliation.deals[i].type!="1") continue;
      long day_index=EEA_SymbolPanelLocalDayIndex(ctx.reconciliation.deals[i].time_utc);
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

   // Days before the loaded broker history come from the persisted daily stats.
   bool stored[32];
   for(int d=0;d<32;d++) stored[d]=false;
   for(int d=1;d<=days_in_month;d++)
     {
      long day_index=first_day+d-1;
      if(day_index>=loaded_from) continue;
      EEA_DailyStatRow row;
      if(!EEA_DailyStatsLookup(day_index,row)) continue;
      net[d]=row.net; trades[d]=row.trades; wins[d]=row.wins; losses[d]=row.losses;
      gross_profit[d]=row.gross_profit; gross_loss[d]=row.gross_loss; active[d]=true; stored[d]=true;
     }
   // REQ-010 day book (start balance, max floating DD, R); unknown fields stay flagged unknown.
   EEA_DailyFloatingRow book_row[32]; bool has_book[32];
   for(int d=0;d<32;d++) has_book[d]=false;
   for(int d=1;d<=days_in_month;d++) has_book[d]=EEA_DailyFloatingGet(first_day+d-1,book_row[d]);
   int y=EEA_PANEL_CONTENT_Y;
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_CalPrev",EEA_PANEL_INNER_X,y,32,24,
                              EEA_SymbolPanelGlyph(0x2039),EEA_PANEL_BUTTON_SECONDARY,11);
   EEA_SymbolPanelSetButtonEx(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_CalMode",EEA_PANEL_MAIN_WIDTH/2+84,y,72,24,
                              EEA_SymbolPanelCalendarModeLabel(g_panel_state.calendar_mode),EEA_PANEL_BUTTON_SECONDARY,9);
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
   double month_r=0.0; int month_r_count=0;
   double month_first_start=0.0; bool month_has_start=false;
   double month_cum=0.0, month_peak=0.0, month_max_dd=0.0; // cumulative realized net in date order, peak-to-trough
   for(int d=1;d<=days_in_month;d++)
     {
      if(!has_book[d]) continue;
      if(!month_has_start && (book_row[d].flags & EEA_DAILY_FLOATING_HAS_START)!=0 && book_row[d].start_balance>0.0)
        { month_has_start=true; month_first_start=book_row[d].start_balance; }
      if(book_row[d].r_count>0) { month_r+=book_row[d].r_sum; month_r_count+=book_row[d].r_count; }
     }
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
      bool loaded=(day_index>=loaded_from && day_index<=today) || stored[day];
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
      bool cell_start=has_book[day] && (book_row[day].flags & EEA_DAILY_FLOATING_HAS_START)!=0;
      int cell_r_count=has_book[day] ? book_row[day].r_count : 0;
      double cell_r=has_book[day] ? book_row[day].r_sum : 0.0;
      string value=!loaded ? "" : EEA_SymbolPanelCalendarCell(g_panel_state.calendar_mode,active[day],net[day],cell_start,
                                                              cell_start ? book_row[day].start_balance : 0.0,cell_r_count,cell_r);
      color value_color=active[day] ? EEA_SymbolPanelPnlColor(net[day]) : EEA_PANEL_FAINT_COLOR;
      if(g_panel_state.calendar_mode==2) value_color=cell_r_count>0 ? EEA_SymbolPanelPnlColor(cell_r) : EEA_PANEL_FAINT_COLOR;
      EEA_SymbolPanelSetText(chart_id,base+"Val",cx+68,cy+22,value,value_color,
                             EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO,ANCHOR_RIGHT_UPPER,12);
      ObjectSetInteger(chart_id,base+"Day",OBJPROP_ZORDER,15);
      ObjectSetInteger(chart_id,base+"Val",OBJPROP_ZORDER,15);
      if(active[day])
        {
         month_net+=net[day]; month_trades+=trades[day]; trading_days++;
         month_cum+=net[day]; month_peak=MathMax(month_peak,month_cum); month_max_dd=MathMax(month_max_dd,month_peak-month_cum);
         if(net[day]>0.0) green++; else if(net[day]<0.0) red++;
        }
     }
   int detail_y=grid_y+6*42+4;
   EEA_SymbolPanelSetSurface(chart_id,EEA_PANEL_OVERLAY_PREFIX+"CalDetailSurface",EEA_PANEL_INNER_X,detail_y,
                             EEA_PANEL_INNER_WIDTH,70,EEA_PANEL_SURFACE_COLOR);
   // Layout (REQ-010): detail surface 70 high (was 48) with three mono lines at +26/+40/+54, month summary at
   // +78 and +92 (was +56), note at +108 (was +74); ends near y 554, above the status bar (572).
   int sd=g_panel_state.calendar_selected_day;
   string detail="Click a day to see its realized result.";
   string detail2="", detail3="";
   color detail_color=EEA_PANEL_MUTED_COLOR;
   if(sd>=1 && sd<=days_in_month)
     {
      bool sd_start=has_book[sd] && (book_row[sd].flags & EEA_DAILY_FLOATING_HAS_START)!=0 && book_row[sd].start_balance>0.0;
      bool sd_min=has_book[sd] && (book_row[sd].flags & EEA_DAILY_FLOATING_HAS_MIN)!=0;
      int sd_r_count=has_book[sd] ? book_row[sd].r_count : 0;
      string start_text=sd_start ? EEA_SymbolPanelFormatNumber(book_row[sd].start_balance,2) : "n/a";
      string return_text=sd_start ? EEA_SymbolPanelSignedPercent(net[sd]/book_row[sd].start_balance*100.0) : "n/a";
      detail=StringFormat("%04d-%02d-%02d",year,month,sd)+EEA_SymbolPanelSep()+"start "+start_text+
             EEA_SymbolPanelSep()+"realized "+EEA_SymbolPanelSigned(net[sd],2)+EEA_SymbolPanelSep()+"return "+return_text;
      detail2="trades "+IntegerToString(trades[sd])+" ("+IntegerToString(wins[sd])+"W / "+IntegerToString(losses[sd])+
              "L)"+EEA_SymbolPanelSep()+"gross "+EEA_SymbolPanelSigned(gross_profit[sd],2)+" / "+
              EEA_SymbolPanelSigned(gross_loss[sd],2);
      string dd_text="n/a";
      if(sd_min)
        {
         double dd=MathMin(book_row[sd].min_floating,0.0);
         dd_text=EEA_SymbolPanelSigned(dd,2);
         if((book_row[sd].flags & EEA_DAILY_FLOATING_HAS_START)!=0 && book_row[sd].start_equity>0.0)
            dd_text+=" ("+EEA_SymbolPanelSignedPercent(dd/book_row[sd].start_equity*100.0)+" of start equity)";
        }
      detail3="max floating DD "+dd_text+EEA_SymbolPanelSep()+
              (sd_r_count>0 ? "best R "+EEA_SymbolPanelSigned(book_row[sd].r_best,2)+" / worst R "+
                              EEA_SymbolPanelSigned(book_row[sd].r_worst,2)+" ("+IntegerToString(sd_r_count)+")"
                            : "best/worst R n/a");
      detail_color=active[sd] ? EEA_PANEL_TEXT_COLOR : EEA_PANEL_MUTED_COLOR;
     }
   // TC-029: floating P/L of the selected day (end-of-day snapshot; today = live) goes on the title line.
   string detail_title="DAY DETAIL";
   if(sd>=1 && sd<=days_in_month)
     {
      double floating_value=0.0;
      if(!EEA_DailyFloatingLookup(first_day+sd-1,floating_value)) detail_title+=EEA_SymbolPanelSep()+"floating EOD unavailable";
      else if(first_day+sd-1==today) detail_title+=EEA_SymbolPanelSep()+"floating now "+EEA_SymbolPanelSigned(floating_value,2);
      else detail_title+=EEA_SymbolPanelSep()+"floating EOD "+EEA_SymbolPanelSigned(floating_value,2);
     }
   EEA_SymbolPanelSetCaption(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetailTitle",EEA_PANEL_CONTENT_X,detail_y+8,detail_title);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetail",EEA_PANEL_CONTENT_X,detail_y+26,detail,detail_color,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetail2",EEA_PANEL_CONTENT_X,detail_y+40,detail2,detail_color,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalDetail3",EEA_PANEL_CONTENT_X,detail_y+54,detail3,detail_color,
                          EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_MONO);
   // Month summary (CHK-CAL-02): net, return, trading days, green/red, trades; average day, max DD, R sum.
   bool month_pct=month_has_start && month_first_start>0.0;
   double avg_day=trading_days>0 ? month_net/trading_days : 0.0;
   string avg_text="n/a";
   if(trading_days>0)
      avg_text=EEA_SymbolPanelSigned(avg_day,2)+(month_pct ? " ("+EEA_SymbolPanelSignedPercent(avg_day/month_first_start*100.0)+")" : "");
   string dd_month_text=EEA_SymbolPanelSigned(-month_max_dd,2)+
                        (month_pct ? " ("+EEA_SymbolPanelSignedPercent(-month_max_dd/month_first_start*100.0)+")" : "");
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalSummary",EEA_PANEL_CONTENT_X,detail_y+78,
                          "Month  net "+EEA_SymbolPanelSigned(month_net,2)+EEA_SymbolPanelSep()+"return "+
                          (month_pct ? EEA_SymbolPanelSignedPercent(month_net/month_first_start*100.0) : "n/a")+EEA_SymbolPanelSep()+
                          "trading days "+IntegerToString(trading_days)+EEA_SymbolPanelSep()+"green "+IntegerToString(green)+
                          " / red "+IntegerToString(red)+EEA_SymbolPanelSep()+"trades "+IntegerToString(month_trades),
                          EEA_SymbolPanelPnlColor(month_net),EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalSummary2",EEA_PANEL_CONTENT_X,detail_y+92,
                          "Month  avg day "+avg_text+EEA_SymbolPanelSep()+"max DD "+dd_month_text+EEA_SymbolPanelSep()+"R "+
                          (month_r_count>0 ? EEA_SymbolPanelSigned(month_r,2) : "n/a"),
                          EEA_PANEL_MUTED_COLOR,EEA_PANEL_META_FONT_SIZE,EEA_PANEL_FONT_BOLD);
   EEA_SymbolPanelSetText(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_CalNote",EEA_PANEL_CONTENT_X,detail_y+108,
                          "Realized P/L by local day ("+EEA_SymbolPanelLocalZoneLabel()+"), last "+IntegerToString(ctx.history_lookback_days)+
                          " days loaded; cash flows excluded. FTMO limits still use Prague days.",
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

// Trades tab clicks: select a row, choose an action, confirm (C2, C4, C5).
void EEA_SymbolPanelHandleTradeClick(const string sparam)
  {
   string p=EEA_PANEL_OVERLAY_PREFIX+"Tr_";
   if(StringFind(sparam,p+"Sel_")==0)
     {
      int row=(int)StringToInteger(StringSubstr(sparam,StringLen(p+"Sel_")));
      if(row<0 || row>=g_panel_state.trade_row_count) return;
      g_panel_state.trade_selected_kind=g_panel_state.trade_row_kind[row];
      g_panel_state.trade_selected_ticket=g_panel_state.trade_row_ticket[row];
      g_panel_state.trade_pending_action=""; g_panel_state.trade_closeall_stage=0;
      return;
     }
   if(sparam==p+"Abort") { g_panel_state.trade_pending_action=""; g_panel_state.trade_closeall_stage=0; return; }
   if(sparam==p+"CloseAll")
     { g_panel_state.trade_closeall_stage=1; g_panel_state.trade_closeall_tick=GetTickCount(); g_panel_state.trade_pending_action=""; return; }
   if(sparam==p+"Confirm" && g_panel_state.trade_closeall_stage==1)
     { g_panel_state.trade_closeall_stage=2; g_panel_state.trade_closeall_tick=GetTickCount(); return; }
   if(sparam==p+"Confirm" && g_panel_state.trade_closeall_stage==2)
     {
      g_panel_state.cmd_request_action="CLOSE_ALL_EA"; g_panel_state.cmd_request_kind="ALL"; g_panel_state.cmd_request_ticket=0;
      g_panel_state.cmd_request_volume=0.0; g_panel_state.cmd_request_sl=0.0; g_panel_state.cmd_request_fraction=0.0;
      g_panel_state.trade_closeall_stage=0;
      return;
     }
   if(sparam==p+"Confirm" && EEA_SymbolPanelTradeConfirming())
     {
      g_panel_state.cmd_request_action=g_panel_state.trade_pending_action;
      g_panel_state.cmd_request_kind=g_panel_state.trade_selected_kind;
      g_panel_state.cmd_request_ticket=g_panel_state.trade_selected_ticket;
      g_panel_state.cmd_request_volume=g_panel_state.trade_selected_volume;
      g_panel_state.cmd_request_sl=g_panel_state.trade_selected_sl;
      g_panel_state.cmd_request_fraction=g_panel_state.trade_partial_fraction;
      g_panel_state.trade_pending_action="";
      return;
     }
   string action="";
   if(sparam==p+"Close") action="CLOSE";
   else if(sparam==p+"Be") action="BE";
   else if(sparam==p+"Trail") action="TRAIL";
   else if(sparam==p+"Cancel") action="CANCEL";
   else if(sparam==p+"Partial")
     {
      // C4: 50% first; while confirming, each click cycles 25% -> 50% -> 75%.
      if(g_panel_state.trade_pending_action=="PARTIAL" && EEA_SymbolPanelTradeConfirming())
        {
         double f=g_panel_state.trade_partial_fraction;
         g_panel_state.trade_partial_fraction=(f<0.3 ? 0.5 : (f<0.6 ? 0.75 : 0.25));
         g_panel_state.trade_confirm_tick=GetTickCount();
         return;
        }
      action="PARTIAL";
      g_panel_state.trade_partial_fraction=0.5;
     }
   if(action=="" || g_panel_state.trade_selected_kind=="") return;
   g_panel_state.trade_pending_action=action;
   g_panel_state.trade_confirm_tick=GetTickCount();
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
     { EEA_SymbolPanelSetCollapsed(!g_panel_state.collapsed,ctx); EEA_SymbolPanelSaveUiState(ctx.root); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Settings") { g_panel_state.active_view="SETTINGS"; EEA_SymbolPanelSaveUiState(ctx.root); EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx); EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); ChartRedraw(g_panel_state.chart_id); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard") { g_panel_state.active_view="DASHBOARD"; EEA_SymbolPanelSaveUiState(ctx.root); EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx); EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx); ChartRedraw(g_panel_state.chart_id); return; }
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Tab_")==0)
     {
      string tab=StringSubstr(sparam,StringLen(EEA_PANEL_OVERLAY_PREFIX+"Tab_"));
      if(g_panel_state.overlay_name=="SETTINGS") g_panel_state.settings_tab=tab;
      if(g_panel_state.overlay_name=="DASHBOARD") g_panel_state.dashboard_tab=tab;
      EEA_SymbolPanelSaveUiState(ctx.root);
      // A different sub-view has different controls: rebuild it from scratch.
      EEA_SymbolPanelClearOverlay(g_panel_state.chart_id);
      EEA_SymbolPanelRenderActiveView(g_panel_state.chart_id,ctx);
      return;
     }
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Btn_Bot_")==0)
     {
      const string code=StringSubstr(sparam,StringLen(EEA_PANEL_OVERLAY_PREFIX+"Btn_Bot_"));
      bool active=false;
      for(int i=0;i<g_panel_bot_count;i++) if(g_panel_bots[i].code==code) active=g_panel_bots[i].active;
      if(active || EEA_SymbolPanelBotConfirming(code))
        { g_panel_state.bot_toggle_request=code; g_panel_state.bot_confirm_code=""; g_panel_state.bot_confirm_tick=0; }
      else
        { g_panel_state.bot_confirm_code=code; g_panel_state.bot_confirm_tick=GetTickCount(); }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalMode")
     {
      g_panel_state.calendar_mode=(g_panel_state.calendar_mode+1)%3; // MONEY -> % -> R -> MONEY
      EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalPrev" ||sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_CalNext")
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
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Session24h" || sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Session7d")
     {
      string action=(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Session24h") ? "SIGN_24H" : "SIGN_7D";
      if(EEA_SymbolPanelSessionConfirming(action))
        { g_panel_state.session_request=action; g_panel_state.session_confirm_action=""; }
      else
        { g_panel_state.session_confirm_action=action; g_panel_state.session_confirm_tick=GetTickCount(); }
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Tr_")==0)
     {
      EEA_SymbolPanelHandleTradeClick(sparam);
      EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Ai_BtnAsk" || sparam==EEA_PANEL_OVERLAY_PREFIX+"Ai_BtnReview")
     {
      if(g_panel_state.ai_request_tick>0 && GetTickCount()-g_panel_state.ai_request_tick<60000)
        { EEA_SymbolPanelToast("AI: one request per minute",EEA_PANEL_WARNING_COLOR); return; }
      g_panel_state.ai_request_tick=GetTickCount();
      g_panel_state.ai_request=(sparam==EEA_PANEL_OVERLAY_PREFIX+"Ai_BtnAsk") ? "ASK" : "REVIEW";
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryRecheck")
     {
      g_panel_state.recovery_request="RECHECK"; g_panel_state.recovery_confirm_tick=0;
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_RecoveryResolve")
     {
      if(EEA_SymbolPanelRecoveryConfirming())
        { g_panel_state.recovery_request="RESOLVE"; g_panel_state.recovery_confirm_tick=0; }
      else
         g_panel_state.recovery_confirm_tick=GetTickCount();
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SessionAccept")
     {
      string chosen=EEA_SymbolPanelSessionConfirming("SIGN_24H") ? "SIGN_24H" :
                    EEA_SymbolPanelSessionConfirming("SIGN_7D") ? "SIGN_7D" : "";
      if(chosen!="") { g_panel_state.session_request=chosen; g_panel_state.session_confirm_action=""; }
      else EEA_SymbolPanelToast("Choose 24h or 7 days first",EEA_PANEL_WARNING_COLOR);
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SessionRevoke")
     {
      g_panel_state.session_request="REVOKE"; g_panel_state.session_confirm_action="";
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
   // Clicking the policy already in force changes nothing (it used to stage it again and clear the
   // confirmation, which then blocked the live session with LIVE_POLICY_NOT_CONFIRMED).
   if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_")==0)
     {
      const string pick=StringSubstr(sparam,StringLen(EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_"));
      if(pick==g_panel_state.staged_policy && pick==g_panel_state.committed_policy)
        {
         EEA_SymbolPanelToast("Policy "+pick+" is already in force"+(g_panel_state.policy_confirmed ? " and confirmed" :
                              ": press Confirm policy"),g_panel_state.policy_confirmed ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
         EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return;
        }
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
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_CUSTOM")
     {
      EEA_SymbolPanelPolicySnapshot old_policy;
       EEA_SymbolPanelCapturePolicySnapshot(old_policy);
      g_panel_state.staged_policy="CUSTOM"; g_panel_state.policy_confirmed=false;
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
      // Confirming (or un-confirming) the policy already in force is not a staged change, so Apply never
      // saved it and a live session could not be signed again (LIVE_POLICY_NOT_CONFIRMED). Persist it at
      // once, audited; a different staged policy still needs Apply (its confirmation is saved with it).
      if(g_panel_state.staged_policy==g_panel_state.committed_policy && g_panel_state.committed_policy!="UNSELECTED")
        {
         if(EEA_SymbolPanelPersistPolicy(ctx,audit,false))
            EEA_SymbolPanelToast(g_panel_state.policy_confirmed ? "Policy "+g_panel_state.committed_policy+" confirmed and saved" :
                                 "Policy confirmation removed",
                                 g_panel_state.policy_confirmed ? EEA_PANEL_OK_COLOR : EEA_PANEL_WARNING_COLOR);
         else
           {
            g_panel_state.policy_confirmed=!g_panel_state.policy_confirmed;
            g_panel_state.apply_reason="POLICY_SETTINGS_PERSISTENCE_FAILED";
           }
        }
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
