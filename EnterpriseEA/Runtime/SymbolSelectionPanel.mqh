#ifndef ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH
#define ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH

#include "ObserverRuntime.mqh"
#include "ObserverPanelModel.mqh"
#include "..\Market\SymbolRegistry.mqh"

#define EEA_PANEL_MAX_ROWS 32
#define EEA_PANEL_PREFIX "EEA_Panel_"
#define EEA_PANEL_MAIN_PREFIX "EEA_Panel_Main_"
#define EEA_PANEL_OVERLAY_PREFIX "EEA_Panel_Overlay_"

struct EEA_SymbolPanelRow
  {
   string canonical_symbol;
   string broker_symbol;
   string status;
   string description;
   bool checked;
   bool context_only;
  };

struct EEA_SymbolPanelState
  {
   long chart_id;
   int sub_window;
   int row_count;
   EEA_SymbolPanelRow rows[EEA_PANEL_MAX_ROWS];
   string status_message;
   bool overlay_open;
   string overlay_name;
   bool staged_initialized;
  };

static EEA_SymbolPanelState g_panel_state;

void EEA_SymbolPanelSetLabel(const long chart_id,const string name,const int x,const int y,
                             const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,text);
  }

void EEA_SymbolPanelSetButton(const long chart_id,const string name,const int x,const int y,
                              const int width,const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,22);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,text);
  }

void EEA_SymbolPanelClearOverlay(const long chart_id)
  {
   ObjectsDeleteAll(chart_id,EEA_PANEL_OVERLAY_PREFIX);
   g_panel_state.overlay_open=false;
   g_panel_state.overlay_name="";
  }

void EEA_SymbolPanelCloseOverlay(const long chart_id)
  {
   EEA_SymbolPanelClearOverlay(chart_id);
  }

void EEA_SymbolPanelCreateControls(const long chart_id,const int sub_window)
  {
   g_panel_state.chart_id=chart_id;
   g_panel_state.sub_window=sub_window;
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Header",10,8,
                           "EnterpriseEA - OBSERVER ONLY"); // EnterpriseEA — OBSERVER ONLY
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Settings",10,34,82,"Settings");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard",98,34,88,"Dashboard");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_MAIN_PREFIX+"Btn_Refresh",192,34,78,"Refresh");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Status",10,63,"Status: BLOCKED");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Account",10,83,"Account: unavailable");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Telemetry",10,103,"Refresh: not available");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Counts",10,123,
                           "POSITIONS: 0 | ORDERS: 0 | DEALS: 0 | Selected symbols: 0");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Market",10,145,"Market:");
   ChartRedraw(chart_id);
  }

void EEA_SymbolPanelRenderMainView(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   string formatted_status;
   EEA_ObserverPanelFormatStatus(ctx.status,formatted_status);
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Status",10,63,
                           "Status: "+formatted_status);
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Account",10,83,
                           "Server: "+ctx.account.broker_server+" | Currency: "+ctx.account.account_currency+
                           " | Margin: "+ctx.account.account_margin_mode+
                           " | Execution: EXECUTION_DISABLED | Live: NOT_AUTHORIZED");
   string last_refresh=(ctx.last_refresh_utc>0 ? IntegerToString(ctx.last_refresh_utc) : "UNAVAILABLE");
   string next_refresh=(ctx.last_refresh_utc>0 ? IntegerToString(ctx.last_refresh_utc+ctx.refresh_seconds) : "UNAVAILABLE");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Telemetry",10,103,
                           "Last refresh: "+last_refresh+" | Next refresh: "+next_refresh+
                           " | sequence="+IntegerToString(ctx.status.refresh_sequence)+
                           " | generation="+IntegerToString(ctx.status.refresh_generation)+
                           " | new_entries_blocked="+(ctx.status.new_entries_blocked ? "true" : "false"));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Counts",10,123,
                           "POSITIONS: "+IntegerToString(ctx.reconciliation.position_count)+
                           " | ORDERS: "+IntegerToString(ctx.reconciliation.order_count)+
                           " | DEALS: "+IntegerToString(ctx.reconciliation.deal_count)+
                           " | Selected symbols: "+IntegerToString(ctx.symbol_count));

   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++)
      ObjectDelete(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(i));
   int line=0;
   for(int i=0;i<ctx.symbol_count && line<EEA_PANEL_MAX_ROWS-1;i++)
     {
      string broker=ctx.broker_symbols[i];
      string row_status=(broker=="" ? "UNRESOLVED" : "RESOLVED");
      EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(line),10,
                              165+line*20,
                              ctx.canonical_symbols[i]+" -> "+(broker=="" ? "[UNRESOLVED]" : broker)+
                              " ("+row_status+")");
      line++;
     }
   // DXY is context-only. It is never copied into ctx.canonical_symbols or selection state.
   string dxy_broker="";
   int total=SymbolsTotal(false);
   for(int n=0;n<total;n++)
     {
      string candidate=SymbolName(n,false);
      if(EEA_TrimUpper(candidate)=="USDX." || EEA_TrimUpper(candidate)=="USDX")
        { dxy_broker=candidate; break; }
     }
   if(dxy_broker!="" && line<EEA_PANEL_MAX_ROWS)
     {
      EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(line),10,
                              165+line*20,"DXY -> "+dxy_broker+" (CONTEXT ONLY)");
      line++;
     }
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Market",10,145,
                           "Market rows (DXY/USDX: CONTEXT ONLY)");
   ChartRedraw(chart_id);
  }

bool EEA_SymbolPanelInit(const long chart_id,const int sub_window)
  {
   g_panel_state.row_count=0;
   g_panel_state.status_message="Ready";
   g_panel_state.overlay_open=false;
   g_panel_state.overlay_name="";
   g_panel_state.staged_initialized=false;
   EEA_SymbolPanelCreateControls(chart_id,sub_window);
   return true;
  }

void EEA_SymbolPanelRefresh(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   g_panel_state.chart_id=chart_id;
   g_panel_state.row_count=ctx.symbol_count;
   for(int i=0;i<ctx.symbol_count && i<EEA_PANEL_MAX_ROWS;i++)
     {
      g_panel_state.rows[i].canonical_symbol=ctx.canonical_symbols[i];
      g_panel_state.rows[i].broker_symbol=ctx.broker_symbols[i];
      g_panel_state.rows[i].status=(ctx.broker_symbols[i]!="" ? "RESOLVED" : "UNRESOLVED");
      g_panel_state.rows[i].description="Observer symbol";
      g_panel_state.rows[i].context_only=false;
      if(!g_panel_state.staged_initialized) g_panel_state.rows[i].checked=true;
      string row_prefix=EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_";
      if(g_panel_state.overlay_name=="SETTINGS")
        {
         EEA_SymbolPanelSetButton(chart_id,row_prefix+"Chk",10,215+i*24,25,
                                  g_panel_state.rows[i].checked ? "[X]" : "[ ]");
         EEA_SymbolPanelSetLabel(chart_id,row_prefix+"Lbl",42,218+i*24,
                                 g_panel_state.rows[i].canonical_symbol+" -> "+
                                 (g_panel_state.rows[i].broker_symbol=="" ? "[UNRESOLVED]" : g_panel_state.rows[i].broker_symbol)+
                                 " ("+g_panel_state.rows[i].status+")");
        }
     }
   g_panel_state.staged_initialized=true;
   EEA_SymbolPanelRenderMainView(chart_id,ctx);
  }

void EEA_SymbolPanelRenderSettings(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelClearOverlay(chart_id);
   g_panel_state.overlay_open=true;
   g_panel_state.overlay_name="SETTINGS";
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Title",10,165,
                           "Settings - observer-only staged controls");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Close",10,188,64,"Close");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Apply",80,188,64,"Apply");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_ResetStaged",150,188,70,"Reset");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Policy",10,300,
                           "Risk Policy: UNSELECTED | continuation: ON | GMT+7 | UTC display");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Safety",10,320,
                           "Safety: EXECUTION_DISABLED | NOT_AUTHORIZED | new_entries_blocked");
   EEA_SymbolPanelRefresh(chart_id,ctx);
  }

void EEA_SymbolPanelRenderDashboard(const long chart_id,EEA_ObserverRuntimeContext &ctx)
  {
   EEA_SymbolPanelClearOverlay(chart_id);
   g_panel_state.overlay_open=true;
   g_panel_state.overlay_name="DASHBOARD";
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Title",10,165,
                           "Dashboard - read-only observer snapshot");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Close",10,188,64,"Close");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Financial",10,220,
                           "Balance: "+DoubleToString(ctx.account.balance,2)+
                           " | Equity: "+DoubleToString(ctx.account.equity,2)+
                           " | Margin: "+DoubleToString(ctx.account.margin,2)+
                           " | Free margin: "+DoubleToString(ctx.account.margin_free,2));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Counts",10,242,
                           "Positions: "+IntegerToString(ctx.reconciliation.position_count)+
                           " | Orders: "+IntegerToString(ctx.reconciliation.order_count)+
                           " | History orders: "+IntegerToString(ctx.reconciliation.history_order_count)+
                           " | Deals: "+IntegerToString(ctx.reconciliation.deal_count));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Health",10,264,
                           "Runtime: "+ctx.status.runtime_state+" / "+ctx.status.reason_code+
                           " | Audit health: observer evidence");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Live",10,286,
                           "Live status: NOT_AUTHORIZED | Blocking reason: "+ctx.status.reason_code);
   ChartRedraw(chart_id);
  }

void EEA_SymbolPanelResetStaged(EEA_ObserverRuntimeContext &ctx)
  {
   for(int i=0;i<g_panel_state.row_count;i++)
     {
      g_panel_state.rows[i].checked=false;
      for(int j=0;j<ctx.symbol_count;j++)
         if(g_panel_state.rows[i].canonical_symbol==ctx.canonical_symbols[j]) g_panel_state.rows[i].checked=true;
     }
   g_panel_state.status_message="Staged selection reset";
  }

void EEA_SymbolPanelApplyStaged(EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   string selected[];
   int count=0;
   for(int i=0;i<g_panel_state.row_count;i++)
      if(g_panel_state.rows[i].checked && !g_panel_state.rows[i].context_only)
        { ArrayResize(selected,count+1); selected[count]=g_panel_state.rows[i].canonical_symbol; count++; }
   if(count<1) { g_panel_state.status_message="Apply rejected: no selection"; return; }
   // This is read-only discovery/reconciliation; it never calls an execution adapter.
   g_panel_state.status_message=EEA_ObserverRuntimeApplySelection(ctx,audit,selected,count) ?
                                 "Selection applied; reconciliation required" :
                                 "Apply rejected; previous selection retained";
  }

void EEA_SymbolPanelHandleChartEvent(const int id,const long &lparam,const double &dparam,
                                     const string &sparam,EEA_ObserverRuntimeContext &ctx,CAuditLog &audit)
  {
   if(id!=CHARTEVENT_OBJECT_CLICK) return;
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Settings") { EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard") { EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Refresh")
     {
      EEA_ObserverRuntimeRefresh(ctx,audit);
      g_panel_state.status_message="Read-only refresh requested";
      EEA_SymbolPanelRefresh(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Close")
     {
      // Close only removes overlay objects; selection, policy, execution, and broker state remain unchanged.
      EEA_SymbolPanelCloseOverlay(g_panel_state.chart_id);
      EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ResetStaged")
     {
      EEA_SymbolPanelResetStaged(ctx);
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Apply")
     {
      EEA_SymbolPanelApplyStaged(ctx,audit);
      EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx);
      return;
     }
   for(int i=0;i<g_panel_state.row_count;i++)
     if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Chk")
       {
        g_panel_state.rows[i].checked=!g_panel_state.rows[i].checked;
        ObjectSetString(g_panel_state.chart_id,sparam,OBJPROP_TEXT,
                        g_panel_state.rows[i].checked ? "[X]" : "[ ]");
        ChartRedraw(g_panel_state.chart_id);
        return;
       }
  }

void EEA_SymbolPanelDestroy(const long chart_id)
  {
   ObjectsDeleteAll(chart_id,EEA_PANEL_PREFIX);
   ChartRedraw(chart_id);
  }

#endif
