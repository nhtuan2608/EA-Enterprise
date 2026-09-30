#ifndef ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH
#define ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH

#include "ObserverRuntime.mqh"
#include "..\Market\SymbolRegistry.mqh"

#define EEA_PANEL_MAX_ROWS 32
#define EEA_PANEL_PREFIX "EEA_Panel_"

struct EEA_SymbolPanelRow
  {
   string canonical_symbol;
   string broker_symbol;
   string status;
   string description;
   bool checked;
  };

struct EEA_SymbolPanelState
  {
   long chart_id;
   int sub_window;
   int row_count;
   EEA_SymbolPanelRow rows[EEA_PANEL_MAX_ROWS];
   string status_message;
  };

static EEA_SymbolPanelState g_panel_state;

void EEA_SymbolPanelCreateControls(const long chart_id, const int sub_window)
  {
   g_panel_state.chart_id = chart_id;
   g_panel_state.sub_window = sub_window;

   // Global Refresh Button
   string btn_refresh = EEA_PANEL_PREFIX + "Btn_Refresh";
   ObjectCreate(chart_id, btn_refresh, OBJ_BUTTON, sub_window, 0, 0);
   ObjectSetInteger(chart_id, btn_refresh, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(chart_id, btn_refresh, OBJPROP_YDISTANCE, 10);
   ObjectSetInteger(chart_id, btn_refresh, OBJPROP_XSIZE, 80);
   ObjectSetInteger(chart_id, btn_refresh, OBJPROP_YSIZE, 25);
   ObjectSetString(chart_id, btn_refresh, OBJPROP_TEXT, "Refresh");

   // Global Apply Button
   string btn_apply = EEA_PANEL_PREFIX + "Btn_Apply";
   ObjectCreate(chart_id, btn_apply, OBJ_BUTTON, sub_window, 0, 0);
   ObjectSetInteger(chart_id, btn_apply, OBJPROP_XDISTANCE, 100);
   ObjectSetInteger(chart_id, btn_apply, OBJPROP_YDISTANCE, 10);
   ObjectSetInteger(chart_id, btn_apply, OBJPROP_XSIZE, 80);
   ObjectSetInteger(chart_id, btn_apply, OBJPROP_YSIZE, 25);
   ObjectSetString(chart_id, btn_apply, OBJPROP_TEXT, "Apply");

   // Status Label
   string lbl_status = EEA_PANEL_PREFIX + "Lbl_Status";
   ObjectCreate(chart_id, lbl_status, OBJ_LABEL, sub_window, 0, 0);
   ObjectSetInteger(chart_id, lbl_status, OBJPROP_XDISTANCE, 190);
   ObjectSetInteger(chart_id, lbl_status, OBJPROP_YDISTANCE, 15);
   ObjectSetString(chart_id, lbl_status, OBJPROP_TEXT, "Ready");

   ChartRedraw(chart_id);
  }

bool EEA_SymbolPanelInit(const long chart_id, const int sub_window)
  {
   EEA_SymbolPanelCreateControls(chart_id, sub_window);
   return true;
  }

void EEA_SymbolPanelRefresh(const long chart_id, EEA_ObserverRuntimeContext &ctx)
  {
   // Determine which canonicals we should show.
   // We'll show all canonicals currently configured. In a real system, you'd allow adding canonicals.
   string req_canonicals[];
   int count = ctx.symbol_count;
   ArrayResize(req_canonicals, count);
   for(int i = 0; i < count; i++) req_canonicals[i] = ctx.canonical_symbols[i];

   string out_brk[], reason;
   bool ok = EEA_ObserverRuntimeAutoDiscover(req_canonicals, out_brk, count, ctx.account.broker_server, reason);

   g_panel_state.row_count = count;
   for(int i = 0; i < count && i < EEA_PANEL_MAX_ROWS; i++)
     {
      g_panel_state.rows[i].canonical_symbol = req_canonicals[i];
      g_panel_state.rows[i].broker_symbol = (ok ? out_brk[i] : ctx.broker_symbols[i]);
      g_panel_state.rows[i].status = (g_panel_state.rows[i].broker_symbol != "" ? "RESOLVED" : "UNRESOLVED");
      g_panel_state.rows[i].description = "Discovered observer symbol";
      // keep it checked if it was checked before, but for simplicity we default to true if it matches ctx
      g_panel_state.rows[i].checked = true;

      string row_prefix = EEA_PANEL_PREFIX + "Row_" + IntegerToString(i) + "_";

      // Checkbox
      string chk_name = row_prefix + "Chk";
      ObjectCreate(chart_id, chk_name, OBJ_BUTTON, g_panel_state.sub_window, 0, 0);
      ObjectSetInteger(chart_id, chk_name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(chart_id, chk_name, OBJPROP_YDISTANCE, 45 + i * 25);
      ObjectSetInteger(chart_id, chk_name, OBJPROP_XSIZE, 20);
      ObjectSetInteger(chart_id, chk_name, OBJPROP_YSIZE, 20);
      ObjectSetString(chart_id, chk_name, OBJPROP_TEXT, g_panel_state.rows[i].checked ? "[X]" : "[ ]");

      // Label
      string lbl_name = row_prefix + "Lbl";
      ObjectCreate(chart_id, lbl_name, OBJ_LABEL, g_panel_state.sub_window, 0, 0);
      ObjectSetInteger(chart_id, lbl_name, OBJPROP_XDISTANCE, 35);
      ObjectSetInteger(chart_id, lbl_name, OBJPROP_YDISTANCE, 48 + i * 25);
      string display_str = g_panel_state.rows[i].canonical_symbol +
                           (g_panel_state.rows[i].broker_symbol != "" ? " -> " + g_panel_state.rows[i].broker_symbol : " [UNRESOLVED]") +
                           " (" + g_panel_state.rows[i].status + ")";
      ObjectSetString(chart_id, lbl_name, OBJPROP_TEXT, display_str);
     }
   ChartRedraw(chart_id);
  }

void EEA_SymbolPanelHandleChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam, EEA_ObserverRuntimeContext &ctx, CAuditLog &audit)
  {
   if(id == CHARTEVENT_OBJECT_CLICK)
     {
      if(sparam == EEA_PANEL_PREFIX + "Btn_Refresh")
        {
         EEA_SymbolPanelRefresh(g_panel_state.chart_id, ctx);
         ObjectSetString(g_panel_state.chart_id, EEA_PANEL_PREFIX + "Lbl_Status", OBJPROP_TEXT, "Refreshed");
         ChartRedraw(g_panel_state.chart_id);
        }
      else if(sparam == EEA_PANEL_PREFIX + "Btn_Apply")
        {
         string selected_canonicals[];
         int count = 0;
         for(int i = 0; i < g_panel_state.row_count; i++)
           {
            if(g_panel_state.rows[i].checked)
              {
               ArrayResize(selected_canonicals, count + 1);
               selected_canonicals[count] = g_panel_state.rows[i].canonical_symbol;
               count++;
              }
           }
         if(count > 0)
           {
            bool ok = EEA_ObserverRuntimeApplySelection(ctx, audit, selected_canonicals, count);
            if(ok)
              {
               ObjectSetString(g_panel_state.chart_id, EEA_PANEL_PREFIX + "Lbl_Status", OBJPROP_TEXT, "Selection Applied");
              }
            else
              {
               ObjectSetString(g_panel_state.chart_id, EEA_PANEL_PREFIX + "Lbl_Status", OBJPROP_TEXT, "Apply Rejected");
              }
            EEA_SymbolPanelRefresh(g_panel_state.chart_id, ctx);
           }
         else
           {
            ObjectSetString(g_panel_state.chart_id, EEA_PANEL_PREFIX + "Lbl_Status", OBJPROP_TEXT, "No Selection");
            ChartRedraw(g_panel_state.chart_id);
           }
        }
      else if(StringFind(sparam, EEA_PANEL_PREFIX + "Row_") == 0)
        {
         for(int i = 0; i < g_panel_state.row_count; i++)
           {
            string chk_name = EEA_PANEL_PREFIX + "Row_" + IntegerToString(i) + "_Chk";
            if(sparam == chk_name)
              {
               g_panel_state.rows[i].checked = !g_panel_state.rows[i].checked;
               ObjectSetString(g_panel_state.chart_id, chk_name, OBJPROP_TEXT, g_panel_state.rows[i].checked ? "[X]" : "[ ]");
               ChartRedraw(g_panel_state.chart_id);
               break;
              }
           }
        }
     }
  }

void EEA_SymbolPanelDestroy(const long chart_id)
  {
   ObjectsDeleteAll(chart_id, EEA_PANEL_PREFIX);
   ChartRedraw(chart_id);
  }

#endif


