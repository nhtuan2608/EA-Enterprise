#ifndef ENTERPRISE_EA_SYMBOL_SPEC_ADAPTER_MQH
#define ENTERPRISE_EA_SYMBOL_SPEC_ADAPTER_MQH

#include "RuntimeEvidence.mqh"

string EEA_RuntimeLongName(const long value) { return IntegerToString(value); }

// Resolution requires an explicit canonical/broker binding. Discovery never authorizes it.
bool EEA_ReadRuntimeSymbolSpec(const string canonical_symbol,
                               const string broker_symbol,
                               const string account_server,
                               EEA_RuntimeSymbolSpec &spec,
                               string &reason)
  {
   reason="";
   if(canonical_symbol=="" || broker_symbol=="" || account_server=="")
     { reason="SYMBOL_BINDING_MISSING"; return false; }
   if(!SymbolSelect(broker_symbol,true) || !SymbolInfoInteger(broker_symbol,SYMBOL_EXIST))
     { reason="SYMBOL_BINDING_MISSING"; return false; }

   spec.broker_symbol=broker_symbol;
   spec.digits=(int)SymbolInfoInteger(broker_symbol,SYMBOL_DIGITS);
   spec.point=SymbolInfoDouble(broker_symbol,SYMBOL_POINT);
   spec.tick_size=SymbolInfoDouble(broker_symbol,SYMBOL_TRADE_TICK_SIZE);
   spec.tick_value=SymbolInfoDouble(broker_symbol,SYMBOL_TRADE_TICK_VALUE);
   spec.contract_size=SymbolInfoDouble(broker_symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   spec.volume_min=SymbolInfoDouble(broker_symbol,SYMBOL_VOLUME_MIN);
   spec.volume_max=SymbolInfoDouble(broker_symbol,SYMBOL_VOLUME_MAX);
   spec.volume_step=SymbolInfoDouble(broker_symbol,SYMBOL_VOLUME_STEP);
   spec.stops_level_points=(int)SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_STOPS_LEVEL);
   spec.freeze_level_points=(int)SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   spec.trade_mode=EEA_RuntimeLongName(SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_MODE));
   spec.order_mode=EEA_RuntimeLongName(SymbolInfoInteger(broker_symbol,SYMBOL_ORDER_MODE));
   spec.expiration_mode=EEA_RuntimeLongName(SymbolInfoInteger(broker_symbol,SYMBOL_EXPIRATION_MODE));
   spec.calculation_mode=EEA_RuntimeLongName(SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_CALC_MODE));
   spec.base_currency=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_BASE);
   spec.profit_currency=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_PROFIT);
   spec.margin_currency=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_MARGIN);
   spec.metadata_fingerprint=EEA_RuntimeSymbolFingerprint(spec);
    spec.filling_mode_mask=SymbolInfoInteger(broker_symbol,SYMBOL_FILLING_MODE);

   if(!EEA_IsFiniteDouble(spec.point) || !EEA_IsFiniteDouble(spec.tick_size) ||
      !EEA_IsFiniteDouble(spec.tick_value) || !EEA_IsFiniteDouble(spec.contract_size) ||
      !EEA_IsFiniteDouble(spec.volume_min) || !EEA_IsFiniteDouble(spec.volume_max) ||
      !EEA_IsFiniteDouble(spec.volume_step) || spec.point<=0.0 || spec.tick_size<=0.0 ||
      spec.contract_size<=0.0 || spec.volume_min<=0.0 || spec.volume_max<spec.volume_min ||
      spec.volume_step<=0.0 || spec.stops_level_points<0 || spec.freeze_level_points<0 ||
      spec.base_currency=="" || spec.profit_currency=="" || spec.margin_currency=="")
     { reason="SYMBOL_SPEC_INCOMPLETE"; return false; }
   return true;
  }

#endif
