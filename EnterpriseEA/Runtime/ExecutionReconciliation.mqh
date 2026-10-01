#ifndef ENTERPRISE_EA_EXECUTION_RECONCILIATION_MQH
#define ENTERPRISE_EA_EXECUTION_RECONCILIATION_MQH

#include "ExecutionContracts.mqh"
#include "RuntimeEvidence.mqh"

bool EEA_ExecutionReconcileResult(EEA_ExecutionResult &result,
                                   const EEA_RuntimeReconciliationSnapshot &reconciliation,
                                   const long request_ticket,
                                   const string request_action,
                                   const double expected_sl=0.0,
                                   const double expected_tp=0.0)
  {
   if(result.confirmation_state=="CONFIRMED") return true;

   bool found=false;
   if(request_action=="SUBMIT_MARKET" || request_action=="SUBMIT_PENDING")
     {
      for(int i=0; i<reconciliation.deal_count; i++)
        {
         if(reconciliation.deals[i].order_ticket==request_ticket) { found=true; break; }
        }
      if(!found)
        {
         for(int i=0; i<reconciliation.order_count; i++)
           {
            if(reconciliation.orders[i].ticket==request_ticket) { found=true; break; }
           }
        }
      if(!found)
        {
         for(int i=0; i<reconciliation.position_count; i++)
           {
            if(reconciliation.positions[i].ticket==request_ticket) { found=true; break; }
           }
        }

      if(found)
        {
         result.confirmation_state="CONFIRMED";
         result.reason_code="OK";
         return true;
        }
     }
   else if(request_action=="CANCEL_PENDING")
     {
      bool active_found=false;
      for(int i=0; i<reconciliation.order_count; i++)
        {
         if(reconciliation.orders[i].ticket==request_ticket) { active_found=true; break; }
        }
      bool history_order_found=false;
      for(int i=0; i<reconciliation.history_order_count; i++)
        {
         if(reconciliation.history_orders[i].ticket==request_ticket) { history_order_found=true; break; }
        }
      bool terminal_in_history=false;
      for(int i=0; i<reconciliation.deal_count; i++)
        {
         if(reconciliation.deals[i].order_ticket==request_ticket) { terminal_in_history=true; break; }
        }

      if(!active_found && (history_order_found || terminal_in_history))
        {
         result.confirmation_state="CONFIRMED";
         result.reason_code="OK";
         return true;
        }
     }
   else if(request_action=="MODIFY_PROTECTIVE")
     {
      bool matched=false;
      for(int i=0; i<reconciliation.order_count; i++)
        {
         if(reconciliation.orders[i].ticket==request_ticket)
           {
            if(MathAbs(reconciliation.orders[i].sl - expected_sl) < 1e-9 &&
               MathAbs(reconciliation.orders[i].tp - expected_tp) < 1e-9)
              { matched=true; break; }
           }
        }
      if(!matched)
        {
         for(int i=0; i<reconciliation.position_count; i++)
           {
            if(reconciliation.positions[i].ticket==request_ticket)
              {
               if(MathAbs(reconciliation.positions[i].sl - expected_sl) < 1e-9 &&
                  MathAbs(reconciliation.positions[i].tp - expected_tp) < 1e-9)
                 { matched=true; break; }
              }
           }
        }
      if(matched)
        {
         result.confirmation_state="CONFIRMED";
         result.reason_code="OK";
         return true;
        }
     }

   result.confirmation_state="EXECUTION_UNKNOWN";
   result.reason_code="RECONCILIATION_PENDING_OR_MISSING";
   return false;
  }

#endif
