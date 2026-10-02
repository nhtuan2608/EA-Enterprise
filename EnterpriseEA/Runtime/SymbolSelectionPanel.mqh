#ifndef ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH
#define ENTERPRISE_EA_SYMBOL_SELECTION_PANEL_MQH

#include "ObserverRuntime.mqh"
#include "ObserverPanelModel.mqh"
#include "..\Market\SymbolRegistry.mqh"
#include "..\Storage\PolicySettingsStore.mqh"

#define EEA_PANEL_MAX_ROWS 32
#define EEA_PANEL_PREFIX "EEA_Panel_"
#define EEA_PANEL_MAIN_PREFIX "EEA_Panel_Main_"
#define EEA_PANEL_OVERLAY_PREFIX "EEA_Panel_Overlay_"
// EnterpriseEA — OBSERVER ONLY; explicit confirmation is required for proposals.
#define EEA_PANEL_POLICY_PROPOSAL_ONLY "POLICY_PROPOSAL_ONLY"

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
  };

static EEA_SymbolPanelState g_panel_state;

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

void EEA_SymbolPanelSetLabel(const long chart_id,const string name,const int x,const int y,
                             const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_LABEL,g_panel_state.sub_window,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,text);
  }

void EEA_SymbolPanelSetButton(const long chart_id,const string name,const int x,const int y,
                              const int width,const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_BUTTON,g_panel_state.sub_window,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,22);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,text);
  }

void EEA_SymbolPanelSetEdit(const long chart_id,const string name,const int x,const int y,
                            const int width,const string text)
  {
   if(ObjectFind(chart_id,name)<0) ObjectCreate(chart_id,name,OBJ_EDIT,g_panel_state.sub_window,0,0);
   ObjectSetInteger(chart_id,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(chart_id,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(chart_id,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,22);
   ObjectSetString(chart_id,name,OBJPROP_TEXT,text);
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
   return status_persisted;
  }

void EEA_SymbolPanelClearOverlay(const long chart_id)
  {
   ObjectsDeleteAll(chart_id,EEA_PANEL_OVERLAY_PREFIX,g_panel_state.sub_window);
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
                           "EnterpriseEA - OBSERVER ONLY");
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

EEA_ObserverPanelMarketRow EEA_ObserverPanelMarketRowFromRuntime(const EEA_ObserverRuntimeContext &ctx,const int index)
  {
   EEA_ObserverPanelMarketRow row;
   EEA_ObserverPanelMarketRowDefaults(row);
   if(index<0 || index>=ctx.symbol_count) return row;
   row.canonical=ctx.canonical_symbols[index];
   row.broker=ctx.broker_symbols[index];
   row.status=(row.broker=="" ? "UNRESOLVED" : "RESOLVED");
   row.context_only=EEA_SymbolPanelIsContextOnly(row.canonical,row.broker);
   row.digits=ctx.symbol_specs[index].digits;
   row.trade_mode=ctx.symbol_specs[index].trade_mode;
   row.freshness_text=EEA_SymbolPanelReadableUtc(ctx.reconciliation.valid_until_utc);
   return row;
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
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Telemetry",10,103,
                           "Last refresh: "+EEA_SymbolPanelReadableUtc(ctx.last_refresh_utc)+
                           " | Next refresh: "+EEA_SymbolPanelReadableUtc(ctx.last_refresh_utc+ctx.refresh_seconds)+
                           " | sequence="+IntegerToString(ctx.status.refresh_sequence)+
                           " | generation="+IntegerToString(ctx.status.refresh_generation)+
                           " | new_entries_blocked="+(ctx.status.new_entries_blocked ? "true" : "false"));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Counts",10,123,
                           "POSITIONS: "+IntegerToString(ctx.reconciliation.position_count)+
                           " | ORDERS: "+IntegerToString(ctx.reconciliation.order_count)+
                           " | DEALS: "+IntegerToString(ctx.reconciliation.deal_count)+
                           " | Selected symbols: "+IntegerToString(ctx.symbol_count));

   for(int i=0;i<EEA_PANEL_MAX_ROWS;i++) ObjectDelete(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(i));
   int line=0;
   for(int i=0;i<ctx.symbol_count && i<EEA_PANEL_MAX_ROWS;i++)
     {
      EEA_ObserverPanelMarketRow row=EEA_ObserverPanelMarketRowFromRuntime(ctx,i);
      EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(line),10,
                              165+line*20,row.canonical+" -> "+
                              (row.broker=="" ? "[UNRESOLVED]" : row.broker)+
                              " ("+row.status+", digits="+IntegerToString(row.digits)+
                              ", trade_mode="+row.trade_mode+")");
      line++;
     }
   string dxy_broker="";
   int total=SymbolsTotal(false);
   for(int n=0;n<total;n++)
     {
      string candidate=SymbolName(n,false);
      if(EEA_TrimUpper(candidate)=="USDX." || EEA_TrimUpper(candidate)=="USDX")
        { dxy_broker=candidate; break; }
     }
   if(dxy_broker!="" && line<EEA_PANEL_MAX_ROWS)
      EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Market_"+IntegerToString(line),10,
                              165+line*20,"DXY -> "+dxy_broker+" (CONTEXT ONLY)");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_MAIN_PREFIX+"Lbl_Market",10,145,
                           "Market rows (DXY/USDX: CONTEXT ONLY)");
   ChartRedraw(chart_id);
  }

bool EEA_SymbolPanelInit(const long chart_id,const int sub_window)
  {
   g_panel_state.row_count=0;
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
   EEA_SymbolPanelCreateControls(chart_id,sub_window);
   return true;
  }

void EEA_SymbolPanelRenderSettingsRows(const long chart_id)
  {
   if(g_panel_state.overlay_name!="SETTINGS") return;
   for(int i=0;i<g_panel_state.row_count && i<EEA_PANEL_MAX_ROWS;i++)
     {
      string prefix=EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_";
      EEA_SymbolPanelSetButton(chart_id,prefix+"Chk",10,426+i*24,25,
                               g_panel_state.rows[i].context_only ? "N/A" :
                               (g_panel_state.rows[i].checked ? "[X]" : "[ ]"));
      ObjectSetInteger(chart_id,prefix+"Chk",OBJPROP_STATE,false);
      EEA_SymbolPanelSetLabel(chart_id,prefix+"Lbl",42,429+i*24,
                              g_panel_state.rows[i].canonical_symbol+" -> "+
                              (g_panel_state.rows[i].broker_symbol=="" ? "[UNRESOLVED]" : g_panel_state.rows[i].broker_symbol)+
                              " ("+g_panel_state.rows[i].status+")");
     }
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
      g_panel_state.rows[i].context_only=EEA_SymbolPanelIsContextOnly(g_panel_state.rows[i].canonical_symbol,
                                                                  g_panel_state.rows[i].broker_symbol);
      g_panel_state.rows[i].spec=ctx.symbol_specs[i];
      if(!g_panel_state.staged_initialized) g_panel_state.rows[i].checked=true;
     }
   if(!g_panel_state.staged_initialized)
      EEA_SymbolPanelLoadPolicy(ctx);
   g_panel_state.staged_initialized=true;
   EEA_SymbolPanelRenderMainView(chart_id,ctx);
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
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Policy",10,216,
                           "Risk Policy (staged): "+g_panel_state.staged_policy);
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_1_STEP",10,240,120,"FTMO_1_STEP");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_2_STEP",135,240,120,"FTMO_2_STEP");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_BALANCE_BASED_FTMO_V1",260,240,180,"BALANCE_BASED_FTMO_V1");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_DailyContinuation",10,266,150,
                            g_panel_state.staged_daily_continuation ? "Daily target: ON" : "Daily target: OFF");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_OverallContinuation",165,266,170,
                            g_panel_state.staged_overall_continuation ? "Overall target: ON" : "Overall target: OFF");
   EEA_SymbolPanelSetButton(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Btn_ConfirmPolicy",340,266,100,
                            g_panel_state.policy_confirmed ? "Confirmed" : "Confirm");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Time",10,292,
                           "Authorization input: GMT+7 (YYYY-MM-DD HH:MM)");
   EEA_SymbolPanelSetEdit(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Edit_AuthorizationGmt7",10,316,170,
                          g_panel_state.authorization_input_gmt7);
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Utc",190,319,
                           "UTC display: "+EEA_SymbolPanelReadableUtc(g_panel_state.authorization_utc));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_ApplyStatus",10,350,
                           "Apply status: "+(g_panel_state.status_message=="" ? "READY" : g_panel_state.status_message)+
                           " | reason: "+(g_panel_state.apply_reason=="" ? "NONE" : g_panel_state.apply_reason));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_PersistenceStatus",10,374,
                           "Persistence: durable proposal/apply audit; observer-only");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Safety",10,398,
                           "Safety: EXECUTION_DISABLED | NOT_AUTHORIZED | "+EEA_PANEL_POLICY_PROPOSAL_ONLY+"; proposal only; no execution");
   EEA_SymbolPanelRenderSettingsRows(chart_id);
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
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Watermark",10,264,
                           "Deal watermark: "+IntegerToString(ctx.reconciliation.deal_watermark)+
                           " | Watermark time: "+IntegerToString(ctx.reconciliation.deal_watermark_time_msc));
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Risk",10,286,
                           "Risk policy: "+g_panel_state.committed_policy+
                           " | Headroom: unavailable (policy evidence required)");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Freshness",10,308,
                           "Evidence freshness: observed="+EEA_SymbolPanelReadableUtc(ctx.reconciliation.observed_at_utc)+
                           " | valid_until_utc="+EEA_SymbolPanelReadableUtc(ctx.reconciliation.valid_until_utc));
   for(int i=0;i<ctx.symbol_count && i<EEA_PANEL_MAX_ROWS;i++)
     {
      EEA_ObserverPanelMarketRow row=EEA_ObserverPanelMarketRowFromRuntime(ctx,i);
      EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(i),10,
                              332+i*20,row.canonical+" / "+row.broker+
                              " | Digits: "+IntegerToString(row.digits)+" | Trade mode: "+row.trade_mode+
                              " | Freshness: "+row.freshness_text);
     }
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Health",10,350+ctx.symbol_count*20,
                           "Runtime: "+ctx.status.runtime_state+" / "+ctx.status.reason_code+
                           " | Audit health: observer evidence");
   EEA_SymbolPanelSetLabel(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Lbl_Live",10,372+ctx.symbol_count*20,
                           "Live status: NOT_AUTHORIZED | Blocking reason: "+ctx.status.reason_code);
   ChartRedraw(chart_id);
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
             EEA_ObserverRuntimeAudit(audit,ctx.config_version,"POLICY_ROLLBACK_FAILED",ctx.status);
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
            EEA_ObserverRuntimeAudit(audit,ctx.config_version,"POLICY_ROLLBACK_FAILED",ctx.status);
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
          EEA_ObserverRuntimeAudit(audit,ctx.config_version,"POLICY_ROLLBACK_FAILED",ctx.status);
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
   if(id!=CHARTEVENT_OBJECT_CLICK && id!=CHARTEVENT_OBJECT_ENDEDIT) return;
   if(id==CHARTEVENT_OBJECT_ENDEDIT && sparam!=EEA_PANEL_OVERLAY_PREFIX+"Edit_AuthorizationGmt7") return;
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Settings") { EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard") { EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx); return; }
   if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Refresh")
     {
      EEA_ObserverRuntimeRefresh(ctx,audit);
      g_panel_state.status_message="Read-only refresh requested";
      EEA_SymbolPanelRefresh(g_panel_state.chart_id,ctx);
      if(g_panel_state.overlay_name=="DASHBOARD") EEA_SymbolPanelRenderDashboard(g_panel_state.chart_id,ctx);
      return;
     }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Close")
     { EEA_SymbolPanelCloseOverlay(g_panel_state.chart_id); EEA_SymbolPanelRenderMainView(g_panel_state.chart_id,ctx); return; }
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ResetStaged")
     { EEA_SymbolPanelResetStaged(ctx); EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return; }
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
     { EEA_SymbolPanelApplyStaged(ctx,audit); EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return; }
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
   if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ConfirmPolicy") { g_panel_state.policy_confirmed=true; EEA_SymbolPanelRenderSettings(g_panel_state.chart_id,ctx); return; }
   for(int i=0;i<g_panel_state.row_count;i++)
     if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Chk")
       {
        if(g_panel_state.rows[i].context_only) return;
        if(!g_panel_state.rows[i].context_only)
           g_panel_state.rows[i].checked=!g_panel_state.rows[i].checked;
        ObjectSetString(g_panel_state.chart_id,sparam,OBJPROP_TEXT,g_panel_state.rows[i].checked ? "[X]" : "[ ]");
        ChartRedraw(g_panel_state.chart_id); return;
       }
  }

void EEA_SymbolPanelDestroy(const long chart_id)
  {
   ObjectsDeleteAll(chart_id,EEA_PANEL_PREFIX,g_panel_state.sub_window);
   ChartRedraw(chart_id);
  }

#endif
