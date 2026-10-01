#ifndef ENTERPRISE_EA_BROKER_RECONCILIATION_ADAPTER_MQH
#define ENTERPRISE_EA_BROKER_RECONCILIATION_ADAPTER_MQH

#include "RuntimeEvidence.mqh"

void EEA_RuntimeSortDeals(EEA_RuntimeDealRow &rows[],const int count)
  {
   for(int i=1;i<count;i++)
     {
      EEA_RuntimeDealRow key=rows[i];
      int j=i-1;
      while(j>=0 && (rows[j].time_msc>key.time_msc ||
            (rows[j].time_msc==key.time_msc && rows[j].deal_ticket>key.deal_ticket)))
        { rows[j+1]=rows[j]; j--; }
      rows[j+1]=key;
     }
  }

bool EEA_ReadRuntimeReconciliation(const EEA_RuntimeAccountSnapshot &account,
                                   const string config_version,
                                   const int lookback_days,
                                   const int freshness_seconds,
                                   EEA_RuntimeReconciliationSnapshot &snapshot,
                                   string &reason)
  {
   reason="";
   snapshot.positions_complete=false;
   snapshot.orders_complete=false;
   snapshot.history_orders_complete=false;
   snapshot.deals_complete=false;
   snapshot.position_count=0;
   snapshot.order_count=0;
   snapshot.history_order_count=0;
   snapshot.deal_count=0;
   if(lookback_days<1 || lookback_days>90 || freshness_seconds<1)
     { reason="RUNTIME_CONFIGURATION_INVALID"; return false; }

   const long observed=(long)TimeGMT();
   snapshot.schema_version="runtime-evidence-v0.1.0";
   snapshot.config_version=config_version;
   snapshot.snapshot_id="reconciliation-"+IntegerToString(observed);
   snapshot.account_fingerprint=account.account_fingerprint;
   snapshot.broker_server=account.broker_server;
   snapshot.account_currency=account.account_currency;
   snapshot.account_margin_mode=account.account_margin_mode;
   snapshot.observed_at_utc=observed;
   snapshot.valid_until_utc=observed+freshness_seconds;
   snapshot.history_lookback_days=lookback_days;
   snapshot.history_from_utc=observed-(long)lookback_days*86400;

   const int position_total=PositionsTotal();
   if(position_total<0 || position_total>EEA_RUNTIME_MAX_POSITIONS)
     { reason="POSITIONS_SOURCE_INCOMPLETE"; return false; }
   for(int i=0;i<position_total;i++)
     {
      const ulong ticket=PositionGetTicket(i);
      if(ticket==0)
        { reason="POSITIONS_SOURCE_INCOMPLETE"; return false; }
      EEA_RuntimePositionRow row;
      row.ticket=(long)ticket;
      row.position_id=IntegerToString((long)PositionGetInteger(POSITION_IDENTIFIER));
      row.symbol=PositionGetString(POSITION_SYMBOL);
      row.type=IntegerToString(PositionGetInteger(POSITION_TYPE));
      row.volume=PositionGetDouble(POSITION_VOLUME);
      row.price_open=PositionGetDouble(POSITION_PRICE_OPEN);
      row.current_price=PositionGetDouble(POSITION_PRICE_CURRENT);
      row.profit=PositionGetDouble(POSITION_PROFIT);
      row.swap=PositionGetDouble(POSITION_SWAP);
      row.commission=0.0; // Position properties expose no authoritative commission total.
      row.time_open_utc=PositionGetInteger(POSITION_TIME);
      row.sl=PositionGetDouble(POSITION_SL);
      row.tp=PositionGetDouble(POSITION_TP);
      if(row.symbol=="" || !EEA_IsFiniteDouble(row.volume) || row.volume<=0.0 ||
         !EEA_IsFiniteDouble(row.price_open) || !EEA_IsFiniteDouble(row.current_price) ||
         !EEA_IsFiniteDouble(row.profit) || !EEA_IsFiniteDouble(row.swap) ||
         !EEA_IsFiniteDouble(row.sl) || !EEA_IsFiniteDouble(row.tp))
        { reason="POSITIONS_SOURCE_INCOMPLETE"; return false; }
      snapshot.positions[snapshot.position_count++]=row;
     }
   snapshot.positions_complete=true;

   const int order_total=OrdersTotal();
   if(order_total<0 || order_total>EEA_RUNTIME_MAX_ORDERS)
     { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
   for(int i=0;i<order_total;i++)
     {
      const ulong ticket=OrderGetTicket(i);
      if(ticket==0)
        { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
      EEA_RuntimeOrderRow row;
      row.ticket=(long)ticket;
      row.order_id=IntegerToString((long)ticket);
      row.symbol=OrderGetString(ORDER_SYMBOL);
      row.type=IntegerToString(OrderGetInteger(ORDER_TYPE));
      row.volume=OrderGetDouble(ORDER_VOLUME_CURRENT);
      row.price=OrderGetDouble(ORDER_PRICE_OPEN);
      row.sl=OrderGetDouble(ORDER_SL);
      row.tp=OrderGetDouble(ORDER_TP);
      row.time_setup_utc=OrderGetInteger(ORDER_TIME_SETUP);
      row.expiration_utc=OrderGetInteger(ORDER_TIME_EXPIRATION);
      if(row.symbol=="" || !EEA_IsFiniteDouble(row.volume) || row.volume<0.0 ||
         !EEA_IsFiniteDouble(row.price) || !EEA_IsFiniteDouble(row.sl) || !EEA_IsFiniteDouble(row.tp))
        { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
      snapshot.orders[snapshot.order_count++]=row;
     }
   snapshot.orders_complete=true;

   if(!HistorySelect((datetime)snapshot.history_from_utc,(datetime)observed))
     { reason="DEALS_SOURCE_INCOMPLETE"; return false; }

   snapshot.history_order_count=0;
   snapshot.history_orders_complete=false;
   const int history_order_total=HistoryOrdersTotal();
   if(history_order_total<0 || history_order_total>EEA_RUNTIME_MAX_ORDERS)
     { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
   for(int i=0;i<history_order_total;i++)
     {
      const ulong ticket=HistoryOrderGetTicket(i);
      if(ticket==0)
        { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
      EEA_RuntimeOrderRow row;
      row.ticket=(long)ticket;
      row.order_id=IntegerToString((long)ticket);
      row.symbol=HistoryOrderGetString(ticket,ORDER_SYMBOL);
      row.type=IntegerToString(HistoryOrderGetInteger(ticket,ORDER_TYPE));
      row.volume=HistoryOrderGetDouble(ticket,ORDER_VOLUME_CURRENT);
      row.price=HistoryOrderGetDouble(ticket,ORDER_PRICE_OPEN);
      row.sl=HistoryOrderGetDouble(ticket,ORDER_SL);
      row.tp=HistoryOrderGetDouble(ticket,ORDER_TP);
      row.time_setup_utc=HistoryOrderGetInteger(ticket,ORDER_TIME_SETUP);
      row.expiration_utc=HistoryOrderGetInteger(ticket,ORDER_TIME_EXPIRATION);
      if(!EEA_IsFiniteDouble(row.volume) || row.volume<0.0 ||
         !EEA_IsFiniteDouble(row.price) || !EEA_IsFiniteDouble(row.sl) || !EEA_IsFiniteDouble(row.tp))
        { reason="ORDERS_SOURCE_INCOMPLETE"; return false; }
      snapshot.history_orders[snapshot.history_order_count++]=row;
     }
   snapshot.history_orders_complete=true;
   const int deal_total=HistoryDealsTotal();
   if(deal_total<0 || deal_total>EEA_RUNTIME_MAX_DEALS)
     { reason="DEALS_SOURCE_INCOMPLETE"; return false; }
   for(int i=0;i<deal_total;i++)
     {
      const ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0)
        { reason="DEALS_SOURCE_INCOMPLETE"; return false; }
      EEA_RuntimeDealRow row;
      row.deal_ticket=(long)ticket;
      row.order_ticket=HistoryDealGetInteger(ticket,DEAL_ORDER);
      row.position_id=IntegerToString(HistoryDealGetInteger(ticket,DEAL_POSITION_ID));
      row.symbol=HistoryDealGetString(ticket,DEAL_SYMBOL);
      row.type=IntegerToString(HistoryDealGetInteger(ticket,DEAL_TYPE));
      row.entry=IntegerToString(HistoryDealGetInteger(ticket,DEAL_ENTRY));
      row.volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
      row.price=HistoryDealGetDouble(ticket,DEAL_PRICE);
      row.profit=HistoryDealGetDouble(ticket,DEAL_PROFIT);
      row.commission=HistoryDealGetDouble(ticket,DEAL_COMMISSION);
      row.swap=HistoryDealGetDouble(ticket,DEAL_SWAP);
      row.fee=HistoryDealGetDouble(ticket,DEAL_FEE);
      row.time_utc=HistoryDealGetInteger(ticket,DEAL_TIME);
      row.time_msc=HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
      if(!EEA_IsFiniteDouble(row.volume) || row.volume<0.0 || !EEA_IsFiniteDouble(row.price) ||
         !EEA_IsFiniteDouble(row.profit) || !EEA_IsFiniteDouble(row.commission) ||
         !EEA_IsFiniteDouble(row.swap) || !EEA_IsFiniteDouble(row.fee))
        { reason="DEALS_SOURCE_INCOMPLETE"; return false; }
      snapshot.deals[snapshot.deal_count++]=row;
     }
   EEA_RuntimeSortDeals(snapshot.deals,snapshot.deal_count);
   snapshot.deal_watermark=0;
   snapshot.deal_watermark_time_msc=0;
   for(int i=0;i<snapshot.deal_count;i++)
     {
      if(snapshot.deals[i].deal_ticket>snapshot.deal_watermark)
         snapshot.deal_watermark=snapshot.deals[i].deal_ticket;
      if(snapshot.deals[i].time_msc>snapshot.deal_watermark_time_msc)
         snapshot.deal_watermark_time_msc=snapshot.deals[i].time_msc;
     }
   snapshot.deals_complete=true;
   return true;
  }

#endif
