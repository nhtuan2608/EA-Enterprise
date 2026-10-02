#ifndef ENTERPRISE_EA_TRADE_QUOTE_ADAPTER_MQH
#define ENTERPRISE_EA_TRADE_QUOTE_ADAPTER_MQH

#include "RuntimeEvidence.mqh"

struct EEA_RuntimeTradeQuote
  {
   string schema_version;
   string snapshot_id;
   string account_snapshot_id;
   string account_fingerprint;
   string broker_symbol;
   string symbol_fingerprint;
   int    order_type;
   double bid;
   double ask;
   double spread_points;
   double entry_price;
   double stop_loss;
   double take_profit;
   double volume;
   double projected_loss;
   double required_margin;
   double available_margin;
   int    stops_level_points;
   int    freeze_level_points;
   long   observed_at_utc;
   long   valid_until_utc;
  };

void EEA_RuntimeTradeQuoteDefaults(EEA_RuntimeTradeQuote &quote)
  {
   quote.schema_version="runtime-evidence-v0.1.0";
   quote.snapshot_id="";
   quote.account_snapshot_id="";
   quote.account_fingerprint="";
   quote.broker_symbol="";
   quote.symbol_fingerprint="";
   quote.order_type=-1;
   quote.bid=0.0;
   quote.ask=0.0;
   quote.spread_points=0.0;
   quote.entry_price=0.0;
   quote.stop_loss=0.0;
   quote.take_profit=0.0;
   quote.volume=0.0;
   quote.projected_loss=0.0;
   quote.required_margin=0.0;
   quote.available_margin=0.0;
   quote.stops_level_points=0;
   quote.freeze_level_points=0;
   quote.observed_at_utc=0;
   quote.valid_until_utc=0;
  }

bool EEA_ReadRuntimeTradeQuote(const EEA_RuntimeAccountSnapshot &account,
                               const EEA_RuntimeSymbolSpec &symbol,
                               const int order_type,
                               const double entry,
                               const double stop_loss,
                               const double take_profit,
                               const double volume,
                               const int freshness_seconds,
                               EEA_RuntimeTradeQuote &quote,
                               string &reason)
  {
   EEA_RuntimeTradeQuoteDefaults(quote);
   reason="";
   if(account.snapshot_id=="" || account.account_fingerprint=="" ||
      account.valid_until_utc<=TimeGMT() || symbol.broker_symbol=="" ||
      symbol.metadata_fingerprint=="" || freshness_seconds<1 || freshness_seconds>3600)
     { reason="TRADE_QUOTE_CONTEXT_INVALID"; return false; }
   if(order_type<ORDER_TYPE_BUY || order_type>ORDER_TYPE_SELL ||
      !EEA_IsFiniteDouble(entry) || !EEA_IsFiniteDouble(stop_loss) ||
      !EEA_IsFiniteDouble(take_profit) || !EEA_IsFiniteDouble(volume) ||
      volume<=0.0 || symbol.point<=0.0 || symbol.tick_size<=0.0)
     { reason="TRADE_QUOTE_INPUT_INVALID"; return false; }

   MqlTick tick;
   ZeroMemory(tick);
   if(!SymbolInfoTick(symbol.broker_symbol,tick) || tick.bid<=0.0 || tick.ask<=0.0 ||
      !EEA_IsFiniteDouble(tick.bid) || !EEA_IsFiniteDouble(tick.ask))
     { reason="TRADE_QUOTE_UNAVAILABLE"; return false; }

   const double effective_entry=(entry>0.0) ? entry :
      (order_type==ORDER_TYPE_BUY ? tick.ask : tick.bid);
   if(!EEA_IsFiniteDouble(effective_entry) || effective_entry<=0.0)
     { reason="TRADE_QUOTE_INPUT_INVALID"; return false; }
   if(order_type==ORDER_TYPE_BUY && (stop_loss>=effective_entry || take_profit<=effective_entry))
     { reason="PRICE_GEOMETRY_INVALID"; return false; }
   if(order_type==ORDER_TYPE_SELL && (stop_loss<=effective_entry || take_profit>=effective_entry))
     { reason="PRICE_GEOMETRY_INVALID"; return false; }

   const double stop_distance_points=MathAbs(effective_entry-stop_loss)/symbol.point;
   if(stop_distance_points<symbol.stops_level_points)
     { reason="STOP_DISTANCE_INVALID"; return false; }

   double loss_at_stop=0.0;
   if(!OrderCalcProfit((ENUM_ORDER_TYPE)order_type,symbol.broker_symbol,volume,
                       effective_entry,stop_loss,loss_at_stop) ||
      !EEA_IsFiniteDouble(loss_at_stop) || loss_at_stop>=0.0)
     { reason="LOSS_CALCULATION_INVALID"; return false; }

   double required_margin=0.0;
   if(!OrderCalcMargin((ENUM_ORDER_TYPE)order_type,symbol.broker_symbol,volume,
                       effective_entry,required_margin) ||
      !EEA_IsFiniteDouble(required_margin) || required_margin<0.0)
     { reason="MARGIN_CALCULATION_INVALID"; return false; }

   const long observed=(long)TimeGMT();
   quote.snapshot_id="quote-"+IntegerToString(observed)+"-"+IntegerToString(GetTickCount());
   quote.account_snapshot_id=account.snapshot_id;
   quote.account_fingerprint=account.account_fingerprint;
   quote.broker_symbol=symbol.broker_symbol;
   quote.symbol_fingerprint=symbol.metadata_fingerprint;
   quote.order_type=order_type;
   quote.bid=tick.bid;
   quote.ask=tick.ask;
   quote.spread_points=(tick.ask-tick.bid)/symbol.point;
   quote.entry_price=effective_entry;
   quote.stop_loss=stop_loss;
   quote.take_profit=take_profit;
   quote.volume=volume;
   quote.projected_loss=-loss_at_stop;
   quote.required_margin=required_margin;
   quote.available_margin=account.margin_free;
   quote.stops_level_points=symbol.stops_level_points;
   quote.freeze_level_points=symbol.freeze_level_points;
   quote.observed_at_utc=observed;
   quote.valid_until_utc=observed+freshness_seconds;
   return true;
  }

#endif
