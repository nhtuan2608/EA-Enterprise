#property strict
#property version   "1.000"
#property script_show_inputs
#property description "Exports the account's deal history (with magic, comment and the opening order's stop/target) and the chart symbol's M5/M15/M30/H1/H4 bars to MQL5\\Files\\EEA_export\\ for Tests/live_vs_research.py. Read-only: places no orders."

input int  InpDays      = 60;    // Deal history: days back
input int  InpM5Bars    = 30000; // M5 bars to export
input int  InpM15Bars   = 40000; // M15 bars
input int  InpM30Bars   = 16000; // M30 bars (>= ~250 trading days for the D1 EMA200 of the CtxLimit features)
input int  InpH1Bars    = 9000;  // H1 bars
input int  InpH4Bars    = 3000;  // H4 bars

string Dir() { return "EEA_export\\"; }

bool ExportBars(const ENUM_TIMEFRAMES tf,const string name,const int count)
  {
   MqlRates r[];
   ArraySetAsSeries(r,false);
   const int n=CopyRates(_Symbol,tf,1,count,r);
   if(n<=0) { PrintFormat("EEA_ExportDeals: no %s bars (%d)",name,GetLastError()); return false; }
   const int h=FileOpen(Dir()+StringFormat("bars_%s.csv",name),FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return false;
   FileWriteString(h,"time,open,high,low,close,tickvol,spread\r\n");
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   for(int i=0;i<n;i++)
      FileWriteString(h,StringFormat("%I64d,%s,%s,%s,%s,%I64d,%d\r\n",(long)r[i].time,DoubleToString(r[i].open,digits),
                      DoubleToString(r[i].high,digits),DoubleToString(r[i].low,digits),DoubleToString(r[i].close,digits),
                      r[i].tick_volume,r[i].spread));
   FileClose(h);
   PrintFormat("EEA_ExportDeals: %s %d bars",name,n);
   return true;
  }

void OnStart()
  {
   const datetime to=TimeCurrent()+86400, from=TimeCurrent()-(datetime)InpDays*86400;
   if(!HistorySelect(from,to)) { Print("EEA_ExportDeals: HistorySelect failed"); return; }
   const int h=FileOpen(Dir()+"deals.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) { PrintFormat("EEA_ExportDeals: cannot write (%d)",GetLastError()); return; }
   FileWriteString(h,"deal,time,time_msc,position,order,magic,symbol,type,entry,volume,price,profit,commission,swap,fee,"
                     "comment,order_type,order_price,order_sl,order_tp,order_setup\r\n");
   const int n=HistoryDealsTotal();
   for(int i=0;i<n;i++)
     {
      const ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      const ulong ord=(ulong)HistoryDealGetInteger(d,DEAL_ORDER);
      long otype=-1; double oprice=0.0, osl=0.0, otp=0.0; long osetup=0;
      if(ord>0 && HistoryOrderSelect(ord))
        {
         otype=HistoryOrderGetInteger(ord,ORDER_TYPE);
         oprice=HistoryOrderGetDouble(ord,ORDER_PRICE_OPEN);
         osl=HistoryOrderGetDouble(ord,ORDER_SL);
         otp=HistoryOrderGetDouble(ord,ORDER_TP);
         osetup=HistoryOrderGetInteger(ord,ORDER_TIME_SETUP);
        }
      string cm=HistoryDealGetString(d,DEAL_COMMENT);
      StringReplace(cm,",",";");
      FileWriteString(h,StringFormat("%I64u,%I64d,%I64d,%I64d,%I64u,%I64d,%s,%I64d,%I64d,%.2f,%.5f,%.2f,%.2f,%.2f,%.2f,%s,%I64d,%.5f,%.5f,%.5f,%I64d\r\n",
                      d,HistoryDealGetInteger(d,DEAL_TIME),HistoryDealGetInteger(d,DEAL_TIME_MSC),HistoryDealGetInteger(d,DEAL_POSITION_ID),
                      ord,HistoryDealGetInteger(d,DEAL_MAGIC),HistoryDealGetString(d,DEAL_SYMBOL),HistoryDealGetInteger(d,DEAL_TYPE),
                      HistoryDealGetInteger(d,DEAL_ENTRY),HistoryDealGetDouble(d,DEAL_VOLUME),HistoryDealGetDouble(d,DEAL_PRICE),
                      HistoryDealGetDouble(d,DEAL_PROFIT),HistoryDealGetDouble(d,DEAL_COMMISSION),HistoryDealGetDouble(d,DEAL_SWAP),
                      HistoryDealGetDouble(d,DEAL_FEE),cm,otype,oprice,osl,otp,osetup));
     }
   FileClose(h);
   PrintFormat("EEA_ExportDeals: %d deals since %s",n,TimeToString(from));
   ExportBars(PERIOD_M5,"M5",InpM5Bars);
   ExportBars(PERIOD_M15,"M15",InpM15Bars);
   ExportBars(PERIOD_M30,"M30",InpM30Bars);
   ExportBars(PERIOD_H1,"H1",InpH1Bars);
   ExportBars(PERIOD_H4,"H4",InpH4Bars);
   const int m=FileOpen(Dir()+"meta.json",FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(m!=INVALID_HANDLE)
     {
      FileWriteString(m,StringFormat("{\"symbol\":\"%s\",\"point\":%.10f,\"digits\":%d,\"login\":%I64d,\"server\":\"%s\",\"exported_server_time\":%I64d,\"exported_gmt\":%I64d}\r\n",
                      _Symbol,SymbolInfoDouble(_Symbol,SYMBOL_POINT),(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS),
                      AccountInfoInteger(ACCOUNT_LOGIN),AccountInfoString(ACCOUNT_SERVER),(long)TimeCurrent(),(long)TimeGMT()));
      FileClose(m);
     }
   Print("EEA_ExportDeals: done -> MQL5\\Files\\EEA_export\\");
  }
