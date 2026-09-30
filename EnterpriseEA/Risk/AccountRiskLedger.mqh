#ifndef ENTERPRISE_EA_ACCOUNT_RISK_LEDGER_MQH
#define ENTERPRISE_EA_ACCOUNT_RISK_LEDGER_MQH

// Offline account-wide snapshot reducer. It consumes caller-reconciled rows only.
struct EEA_LedgerPosition
  {
   string position_id;
   string origin;                  // EA | MANUAL | OTHER_EA
   string canonical_symbol;
   string broker_symbol;
   string direction;               // LONG | SHORT
   string config_version;
   string account_currency;
   double volume;
   bool risk_lineage_valid;       // Caller attests original entry/intent values are unchanged
   double initial_risk_money;      // Frozen at entry; do not overwrite on SL changes
   double projected_loss_to_sl;    // Original projected loss from order intent
   double remaining_loss_to_sl;    // Current-price loss to current SL, net costs
   double floating_pnl_after_costs;
   double locked_profit_money;
  };

struct EEA_LedgerWorkingOrder
  {
   string order_id;
   string origin;                  // EA | MANUAL | OTHER_EA
   string canonical_symbol;
   string broker_symbol;
   string order_status;            // WORKING | PARTIAL
   string config_version;
   string account_currency;
   double remaining_volume;
   double projected_loss_to_sl;    // Order-intent projection for unfilled quantity
   double remaining_loss_to_sl;    // Current estimate for the working quantity
  };

struct EEA_LedgerDeal
  {
   string deal_id;
   string origin;                  // EA | MANUAL | OTHER_EA
   string deal_kind;               // TRADE | COMMISSION | SWAP | FEE | DEPOSIT | WITHDRAWAL
   string config_version;
   string account_currency;
   long sequence;
   double money;
  };

struct EEA_LedgerSnapshot
  {
   string config_version;
   string account_id;              // Opaque identifier; no secret/account login is needed
   string broker_server;
   string account_currency;
   string account_mode;            // HEDGING | NETTING, caller reconciled
   string data_quality;            // OK required
   string reconciliation_status;   // RECONCILED required
   string account_scope;           // ACCOUNT_WIDE required
   string event_id;
   string source_snapshot_id;
   string content_fingerprint;     // Caller-attested hash/version over all snapshot fields and rows
   string positions_snapshot_id;
   string orders_snapshot_id;
   string deals_snapshot_id;
   string policy_snapshot_id;
   datetime captured_at_utc;
   int max_age_seconds;
   long event_sequence;
   long deal_watermark;
   bool positions_complete;
   bool orders_complete;
   bool deals_complete;
   bool manual_activity_included;
   bool other_ea_activity_included;
   bool cash_flows_reconciled;
   bool costs_reconciled;
   bool account_mode_reconciled;
   bool policy_headroom_valid;
   string policy_config_version;
   string policy_currency;
   string policy_quality;          // OK required
   double equity_after_costs;
   double equity_floor_headroom_money; // Available policy headroom before current ledger stress
  };

struct EEA_AccountRiskLedger
  {
   bool initialized;
   bool reconciliation_valid;
   bool new_entries_blocked;
   bool protect_existing_positions;
   string ledger_status;           // POLICY_DATA_UNKNOWN | RECONCILED
   string last_transition;         // SNAPSHOT_APPLIED | DUPLICATE_IGNORED | REJECTED
   string reason_code;
   string config_version;
   string account_id;
   string broker_server;
   string account_currency;
   string account_mode;
   string last_event_id;
   string last_snapshot_id;
   string last_content_fingerprint;
   datetime last_captured_at_utc;
   long last_event_sequence;
   long last_deal_watermark;
   int position_count;
   int working_order_count;
   int deal_count;
   double initial_risk_money;
   double projected_loss_to_sl_money;
   double remaining_loss_to_sl_money;
   double floating_pnl_after_costs;
   double locked_profit_money;
   double equity_after_costs;
   double equity_floor_headroom_money;
   double floor_headroom_after_ledger_risk_money;
  };

void EEA_AccountRiskLedgerDefaults(EEA_AccountRiskLedger &l)
  {
   l.initialized=false;
   l.reconciliation_valid=false;
   l.new_entries_blocked=true;
   l.protect_existing_positions=true;
   l.ledger_status="POLICY_DATA_UNKNOWN";
   l.last_transition="NONE";
   l.reason_code="ACCOUNT_WIDE_SNAPSHOT_REQUIRED";
   l.config_version="";
   l.account_id="";
   l.broker_server="";
   l.account_currency="";
   l.account_mode="";
   l.last_event_id="";
   l.last_snapshot_id="";
   l.last_content_fingerprint="";
   l.last_captured_at_utc=0;
   l.last_event_sequence=0;
   l.last_deal_watermark=0;
   l.position_count=0;
   l.working_order_count=0;
   l.deal_count=0;
   l.initial_risk_money=0.0;
   l.projected_loss_to_sl_money=0.0;
   l.remaining_loss_to_sl_money=0.0;
   l.floating_pnl_after_costs=0.0;
   l.locked_profit_money=0.0;
   l.equity_after_costs=0.0;
   l.equity_floor_headroom_money=0.0;
   l.floor_headroom_after_ledger_risk_money=0.0;
  }

bool EEA_LedgerValidOrigin(const string origin)
  {
   return origin=="EA" || origin=="MANUAL" || origin=="OTHER_EA";
  }

void EEA_LedgerMarkUnknown(EEA_AccountRiskLedger &l,const string reason,const string transition)
  {
   l.reconciliation_valid=false;
   l.new_entries_blocked=true;
   l.protect_existing_positions=true;
   l.ledger_status="POLICY_DATA_UNKNOWN";
   l.last_transition=transition;
   l.reason_code=reason;
  }

bool EEA_LedgerValidateSnapshot(const EEA_LedgerSnapshot &s,
                                const EEA_LedgerPosition &positions[],
                                const EEA_LedgerWorkingOrder &orders[],
                                const EEA_LedgerDeal &deals[],const datetime now_utc,
                                string &reason)
  {
   reason="ACCOUNT_WIDE_SNAPSHOT_INVALID";
   if(s.config_version=="" || s.account_id=="" || s.broker_server=="" || s.account_currency=="" ||
      (s.account_mode!="HEDGING" && s.account_mode!="NETTING") || s.event_id=="" ||
      s.source_snapshot_id=="" || s.positions_snapshot_id=="" || s.orders_snapshot_id=="" ||
      s.deals_snapshot_id=="" || s.policy_snapshot_id=="" || s.content_fingerprint=="" || s.event_sequence<=0 ||
      s.captured_at_utc<=0 || s.max_age_seconds<=0 || now_utc<s.captured_at_utc ||
      (now_utc-s.captured_at_utc)>s.max_age_seconds || s.data_quality!="OK" ||
      s.reconciliation_status!="RECONCILED" || s.account_scope!="ACCOUNT_WIDE" ||
      !s.positions_complete || !s.orders_complete || !s.deals_complete ||
      !s.manual_activity_included || !s.other_ea_activity_included ||
      !s.cash_flows_reconciled || !s.costs_reconciled || !s.account_mode_reconciled ||
      !s.policy_headroom_valid || s.policy_quality!="OK" ||
      s.policy_config_version!=s.config_version || s.policy_currency!=s.account_currency)
     { reason="ACCOUNT_WIDE_SNAPSHOT_OR_POLICY_EVIDENCE_MISSING"; return false; }
   if(!MathIsValidNumber(s.equity_after_costs) || s.equity_after_costs<=0.0 ||
      !MathIsValidNumber(s.equity_floor_headroom_money))
     { reason="ACCOUNT_EQUITY_OR_FLOOR_HEADROOM_INVALID"; return false; }

   double initial_risk=0.0,projected=0.0,remaining=0.0,floating=0.0,locked=0.0;
   for(int n=0;n<ArraySize(positions);n++)
     {
      EEA_LedgerPosition p=positions[n];
      if(p.position_id=="" || !EEA_LedgerValidOrigin(p.origin) || p.canonical_symbol=="" ||
         p.broker_symbol=="" || (p.direction!="LONG" && p.direction!="SHORT") ||
         p.config_version!=s.config_version || p.account_currency!=s.account_currency ||
         !p.risk_lineage_valid ||
         !MathIsValidNumber(p.volume) || p.volume<=0.0 ||
         !MathIsValidNumber(p.initial_risk_money) || p.initial_risk_money<=0.0 ||
         !MathIsValidNumber(p.projected_loss_to_sl) || p.projected_loss_to_sl<=0.0 ||
         !MathIsValidNumber(p.remaining_loss_to_sl) || p.remaining_loss_to_sl<0.0 ||
         !MathIsValidNumber(p.floating_pnl_after_costs) ||
         !MathIsValidNumber(p.locked_profit_money) || p.locked_profit_money<0.0)
        { reason="POSITION_ROW_INVALID"; return false; }
      for(int prior=0;prior<n;prior++)
        {
         if(positions[prior].position_id==p.position_id)
           { reason="DUPLICATE_POSITION_ID"; return false; }
         if(s.account_mode=="NETTING" && positions[prior].broker_symbol==p.broker_symbol)
           { reason="NETTING_DUPLICATE_SYMBOL_POSITION"; return false; }
        }
      initial_risk+=p.initial_risk_money;
      projected+=p.projected_loss_to_sl;
      remaining+=p.remaining_loss_to_sl;
      floating+=p.floating_pnl_after_costs;
      locked+=p.locked_profit_money;
     }

   for(int n=0;n<ArraySize(orders);n++)
     {
      EEA_LedgerWorkingOrder w=orders[n];
      if(w.order_id=="" || !EEA_LedgerValidOrigin(w.origin) || w.canonical_symbol=="" ||
         w.broker_symbol=="" || (w.order_status!="WORKING" && w.order_status!="PARTIAL") ||
         w.config_version!=s.config_version || w.account_currency!=s.account_currency ||
         !MathIsValidNumber(w.remaining_volume) || w.remaining_volume<=0.0 ||
         !MathIsValidNumber(w.projected_loss_to_sl) || w.projected_loss_to_sl<=0.0 ||
         !MathIsValidNumber(w.remaining_loss_to_sl) || w.remaining_loss_to_sl<0.0)
        { reason="WORKING_ORDER_ROW_INVALID"; return false; }
      for(int prior=0;prior<n;prior++)
         if(orders[prior].order_id==w.order_id)
           { reason="DUPLICATE_WORKING_ORDER_ID"; return false; }
      projected+=w.projected_loss_to_sl;
      remaining+=w.remaining_loss_to_sl;
     }

   long previous_deal_sequence=0;
   for(int n=0;n<ArraySize(deals);n++)
     {
      EEA_LedgerDeal d=deals[n];
      if(d.deal_id=="" || !EEA_LedgerValidOrigin(d.origin) || d.config_version!=s.config_version ||
         d.account_currency!=s.account_currency || d.sequence<=previous_deal_sequence ||
         d.sequence>s.deal_watermark || !MathIsValidNumber(d.money) ||
         (d.deal_kind!="TRADE" && d.deal_kind!="COMMISSION" && d.deal_kind!="SWAP" &&
          d.deal_kind!="FEE" && d.deal_kind!="DEPOSIT" && d.deal_kind!="WITHDRAWAL"))
        { reason="DEAL_HISTORY_INVALID_OR_OUT_OF_ORDER"; return false; }
      for(int prior=0;prior<n;prior++)
         if(deals[prior].deal_id==d.deal_id)
           { reason="DUPLICATE_DEAL_ID"; return false; }
      previous_deal_sequence=d.sequence;
     }

   if(s.deal_watermark<0 || s.deal_watermark<(ArraySize(deals)>0 ? deals[ArraySize(deals)-1].sequence : 0))
     { reason="DEAL_WATERMARK_INVALID"; return false; }
   if(!MathIsValidNumber(initial_risk) || !MathIsValidNumber(projected) ||
      !MathIsValidNumber(remaining) || !MathIsValidNumber(floating) || !MathIsValidNumber(locked))
     { reason="LEDGER_TOTAL_OVERFLOW"; return false; }
   reason="ACCOUNT_WIDE_SNAPSHOT_VALID";
   return true;
  }

bool EEA_ApplyLedgerSnapshot(EEA_AccountRiskLedger &l,const EEA_LedgerSnapshot &s,
                             const EEA_LedgerPosition &positions[],
                             const EEA_LedgerWorkingOrder &orders[],
                             const EEA_LedgerDeal &deals[],const datetime now_utc)
  {
   string reason="";
   if(!EEA_LedgerValidateSnapshot(s,positions,orders,deals,now_utc,reason))
     {
      EEA_LedgerMarkUnknown(l,reason,"REJECTED");
      return false;
     }
   if(l.initialized)
     {
      if(s.event_id==l.last_event_id && s.source_snapshot_id==l.last_snapshot_id &&
         s.event_sequence==l.last_event_sequence)
        {
         if(s.content_fingerprint!=l.last_content_fingerprint)
           {
            EEA_LedgerMarkUnknown(l,"SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT","REJECTED");
            return false;
           }
         if(!l.reconciliation_valid)
           {
            l.last_transition="DUPLICATE_IGNORED";
            l.reason_code="DUPLICATE_SNAPSHOT_WHILE_LEDGER_UNKNOWN";
            return false;
           }
         l.last_transition="DUPLICATE_IGNORED";
         l.reason_code="DUPLICATE_SNAPSHOT_NO_STATE_CHANGE";
         return true;
        }
      if(s.event_id==l.last_event_id || s.source_snapshot_id==l.last_snapshot_id)
        {
         EEA_LedgerMarkUnknown(l,"SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT","REJECTED");
         return false;
        }
      if(s.config_version!=l.config_version || s.account_id!=l.account_id ||
         s.broker_server!=l.broker_server || s.account_currency!=l.account_currency ||
         s.account_mode!=l.account_mode)
        {
         EEA_LedgerMarkUnknown(l,"ACCOUNT_IDENTITY_OR_MODE_CHANGED","REJECTED");
         return false;
        }
      if(s.event_sequence<=l.last_event_sequence || s.captured_at_utc<=l.last_captured_at_utc ||
         s.deal_watermark<l.last_deal_watermark)
        {
         EEA_LedgerMarkUnknown(l,"OUT_OF_ORDER_ACCOUNT_SNAPSHOT","REJECTED");
         return false;
        }
     }

   double initial_risk=0.0,projected=0.0,remaining=0.0,floating=0.0,locked=0.0;
   for(int n=0;n<ArraySize(positions);n++)
     {
      initial_risk+=positions[n].initial_risk_money;
      projected+=positions[n].projected_loss_to_sl;
      remaining+=positions[n].remaining_loss_to_sl;
      floating+=positions[n].floating_pnl_after_costs;
      locked+=positions[n].locked_profit_money;
     }
   for(int n=0;n<ArraySize(orders);n++)
     {
      projected+=orders[n].projected_loss_to_sl;
      remaining+=orders[n].remaining_loss_to_sl;
     }
   double headroom_after_ledger=s.equity_floor_headroom_money-remaining;
   if(!MathIsValidNumber(initial_risk) || !MathIsValidNumber(projected) ||
      !MathIsValidNumber(remaining) || !MathIsValidNumber(floating) ||
      !MathIsValidNumber(locked) || !MathIsValidNumber(headroom_after_ledger))
     {
      EEA_LedgerMarkUnknown(l,"LEDGER_TOTAL_OVERFLOW","REJECTED");
      return false;
     }

   l.initialized=true;
   l.reconciliation_valid=true;
   l.ledger_status="RECONCILED";
   l.last_transition="SNAPSHOT_APPLIED";
   l.reason_code="ACCOUNT_WIDE_SNAPSHOT_RECONCILED";
   l.config_version=s.config_version;
   l.account_id=s.account_id;
   l.broker_server=s.broker_server;
   l.account_currency=s.account_currency;
   l.account_mode=s.account_mode;
   l.last_event_id=s.event_id;
   l.last_snapshot_id=s.source_snapshot_id;
   l.last_content_fingerprint=s.content_fingerprint;
   l.last_captured_at_utc=s.captured_at_utc;
   l.last_event_sequence=s.event_sequence;
   l.last_deal_watermark=s.deal_watermark;
   l.position_count=ArraySize(positions);
   l.working_order_count=ArraySize(orders);
   l.deal_count=ArraySize(deals);
   l.initial_risk_money=initial_risk;
   l.projected_loss_to_sl_money=projected;
   l.remaining_loss_to_sl_money=remaining;
   l.floating_pnl_after_costs=floating;
   l.locked_profit_money=locked;
   l.equity_after_costs=s.equity_after_costs;
   l.equity_floor_headroom_money=s.equity_floor_headroom_money;
   l.floor_headroom_after_ledger_risk_money=headroom_after_ledger;
   l.new_entries_blocked=(l.floor_headroom_after_ledger_risk_money<=0.0);
   l.protect_existing_positions=true;
   if(l.new_entries_blocked) l.reason_code="RECONCILED_BUT_FLOOR_HEADROOM_EXHAUSTED";
   return true;
  }

#endif
