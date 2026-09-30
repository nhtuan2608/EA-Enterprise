#ifndef ENTERPRISE_EA_RUNTIME_EVIDENCE_MQH
#define ENTERPRISE_EA_RUNTIME_EVIDENCE_MQH

#include "..\Core\Config.mqh"

// Fixed capacities for the observer increment (plan §Task 1 Step 5).
#define EEA_RUNTIME_MAX_SYMBOLS   32
#define EEA_RUNTIME_MAX_POSITIONS 256
#define EEA_RUNTIME_MAX_ORDERS    256
#define EEA_RUNTIME_MAX_DEALS     2048

// Pure finite-number helper using the built-in MQL5 MathIsValidNumber.
// Returns true only for finite numeric values (rejects NaN / Inf).
bool EEA_IsFiniteDouble(const double value)
  {
   return MathIsValidNumber(value);
  }

// ---------------------------------------------------------------------------
// Structures
// ---------------------------------------------------------------------------

struct EEA_RuntimeAccountSnapshot
  {
   string schema_version;
   string config_version;
   string snapshot_id;
   string account_fingerprint;
   string broker_server;
   string account_currency;
   string account_margin_mode;
   long   observed_at_utc;
   long   valid_until_utc;
  };

struct EEA_RuntimeSymbolSpec
  {
   string broker_symbol;
   int    digits;
   double point;
   double tick_size;
   double tick_value;
   double contract_size;
   double volume_min;
   double volume_max;
   double volume_step;
   int    stops_level_points;
   int    freeze_level_points;
   string trade_mode;
   string order_mode;
   string expiration_mode;
   string calculation_mode;
   string base_currency;
   string profit_currency;
   string margin_currency;
  };

struct EEA_RuntimePositionRow
  {
   long   ticket;
   string position_id;
   string symbol;
   string type;
   double volume;
   double price_open;
   double current_price;
   double profit;
   double swap;
   double commission;
   long   time_open_utc;
  };

struct EEA_RuntimeOrderRow
  {
   long   ticket;
   string order_id;
   string symbol;
   string type;
   double volume;
   double price;
   double sl;
   double tp;
   long   time_setup_utc;
   long   expiration_utc;
  };

struct EEA_RuntimeDealRow
  {
   long   deal_ticket;
   long   order_ticket;
   string position_id;
   string symbol;
   string type;
   string entry;
   double volume;
   double price;
   double profit;
   double commission;
   double swap;
   double fee;
   long   time_utc;
   long   time_msc;
  };

struct EEA_RuntimeReconciliationSnapshot
  {
   string schema_version;
   string config_version;
   string snapshot_id;
   string account_fingerprint;
   string broker_server;
   string account_currency;
   string account_margin_mode;
   long   observed_at_utc;
   long   valid_until_utc;
   long   history_lookback_days;
   long   history_from_utc;
   bool   positions_complete;
   bool   orders_complete;
   bool   deals_complete;
   long   deal_watermark;
   long   deal_watermark_time_msc;
   EEA_RuntimeSymbolSpec symbols[EEA_RUNTIME_MAX_SYMBOLS];
   int    symbol_count;
   EEA_RuntimePositionRow positions[EEA_RUNTIME_MAX_POSITIONS];
   int    position_count;
   EEA_RuntimeOrderRow orders[EEA_RUNTIME_MAX_ORDERS];
   int    order_count;
   EEA_RuntimeDealRow deals[EEA_RUNTIME_MAX_DEALS];
   int    deal_count;
  };

struct EEA_RuntimeStatus
  {
   string runtime_state;
   string reason_code;
   bool   new_entries_blocked;
   long   previous_deal_watermark;
   long   previous_deal_watermark_time;
  };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

void EEA_RuntimeDefaults(EEA_RuntimeStatus &s)
  {
   s.runtime_state              = "BLOCKED";
   s.reason_code                = "RUNTIME_RECONCILIATION_REQUIRED";
   s.new_entries_blocked        = true;
   s.previous_deal_watermark    = -1;
   s.previous_deal_watermark_time = -1;
  }

// FNV-1a 32-bit hash helper used to build the opaque account fingerprint.
// The algorithm and prime/offset are fixed so the MQL implementation matches
// this Python oracle byte-for-byte.
string EEA_RuntimeFingerprint(const string server,const string account_id)
  {
   uint   h   = 0x811C9DC5;
   string raw = server + "|" + account_id;
   for(int i = 0; i < StringLen(raw); i++)
     {
      h = h ^ (uchar)StringGetCharacter(raw, i);
      h = h * 0x01000193;
     }
   return StringFormat("fnv1a32:%x", h);
  }

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

// Validate a runtime evidence snapshot.  The order of checks and the reason
// codes match the Python oracle in Tests/runtime_evidence_oracle.py.
void EEA_RuntimeValidate(const EEA_RuntimeReconciliationSnapshot &snapshot,
                          const long now_utc,
                          const long previous_watermark,
                          EEA_RuntimeStatus &status)
  {
   EEA_RuntimeDefaults(status);
   status.previous_deal_watermark = previous_watermark;

   // 1. Identity / version checks
   if(snapshot.schema_version != "runtime-evidence-v0.1.0")
     { status.reason_code = "RUNTIME_CHECKPOINT_INCOMPATIBLE"; return; }

   if(snapshot.account_fingerprint == "" || snapshot.broker_server == "" ||
       snapshot.account_currency == "" || snapshot.account_margin_mode == "")
     { status.reason_code = "ACCOUNT_IDENTITY_UNAVAILABLE"; return; }

   // 2. Freshness
   if(snapshot.valid_until_utc <= 0 || now_utc > snapshot.valid_until_utc)
     { status.reason_code = "RUNTIME_RECONCILIATION_REQUIRED"; return; }

   // 3. Watermark regression
   if(previous_watermark >= 0 && snapshot.deal_watermark < previous_watermark)
     { status.reason_code = "DEAL_WATERMARK_REGRESSED"; return; }

   // 4. Duplicate tickets and finite numeric validation (fail-closed → BLOCKED)
   // Position tickets and finite numeric fields
   for(int i = 0; i < snapshot.position_count; i++)
      {
       // Check duplicate tickets
       for(int j = i + 1; j < snapshot.position_count; j++)
          if(snapshot.positions[i].ticket == snapshot.positions[j].ticket)
             { status.reason_code = "POSITIONS_SOURCE_INCOMPLETE"; return; }
       // Check finite numeric fields
       if(!EEA_IsFiniteDouble(snapshot.positions[i].volume) || !EEA_IsFiniteDouble(snapshot.positions[i].price_open))
          { status.reason_code = "POSITIONS_SOURCE_INCOMPLETE"; return; }
      }

   // Order tickets and finite numeric fields
   for(int i = 0; i < snapshot.order_count; i++)
      {
       // Check duplicate tickets
       for(int j = i + 1; j < snapshot.order_count; j++)
          if(snapshot.orders[i].ticket == snapshot.orders[j].ticket)
             { status.reason_code = "ORDERS_SOURCE_INCOMPLETE"; return; }
       // Check finite numeric fields
       if(!EEA_IsFiniteDouble(snapshot.orders[i].volume) || !EEA_IsFiniteDouble(snapshot.orders[i].price))
          { status.reason_code = "ORDERS_SOURCE_INCOMPLETE"; return; }
      }

   // Deal tickets, finite numeric fields, and chronological ordering
   for(int i = 0; i < snapshot.deal_count; i++)
      {
       // Check duplicate tickets
       for(int j = i + 1; j < snapshot.deal_count; j++)
          if(snapshot.deals[i].deal_ticket == snapshot.deals[j].deal_ticket)
             { status.reason_code = "DEALS_SOURCE_INCOMPLETE"; return; }
       // Check finite numeric fields
       if(!EEA_IsFiniteDouble(snapshot.deals[i].volume) || !EEA_IsFiniteDouble(snapshot.deals[i].price))
          { status.reason_code = "DEALS_SOURCE_INCOMPLETE"; return; }
       
       // Check chronological ordering by (time_msc, ticket) for deals after first
       if(i > 0)
          {
           if(snapshot.deals[i].time_msc < snapshot.deals[i-1].time_msc)
              { status.reason_code = "DEALS_SOURCE_INCOMPLETE"; return; }
           if(snapshot.deals[i].deal_ticket < snapshot.deals[i-1].deal_ticket)
              { status.reason_code = "DEALS_SOURCE_INCOMPLETE"; return; }
          }
      }

   // 5. Source completeness (fail-closed → DEGRADED)
   if(!snapshot.positions_complete)
      { status.runtime_state = "DEGRADED"; status.reason_code = "POSITIONS_SOURCE_INCOMPLETE"; return; }
   if(!snapshot.orders_complete)
      { status.runtime_state = "DEGRADED"; status.reason_code = "ORDERS_SOURCE_INCOMPLETE"; return; }
   if(!snapshot.deals_complete)
      { status.runtime_state = "DEGRADED"; status.reason_code = "DEALS_SOURCE_INCOMPLETE"; return; }

   // 6. Symbol spec validation (finite/positive ranges/currencies)
   for(int i = 0; i < snapshot.symbol_count; i++)
      {
       // Check finite/positive numeric ranges
       if(snapshot.symbols[i].volume_min <= 0)
          { status.reason_code = "SYMBOL_SPEC_INCOMPLETE"; return; }
       if(snapshot.symbols[i].volume_max < snapshot.symbols[i].volume_min)
          { status.reason_code = "SYMBOL_SPEC_INCOMPLETE"; return; }
       if(snapshot.symbols[i].volume_step <= 0)
          { status.reason_code = "SYMBOL_SPEC_INCOMPLETE"; return; }
       if(snapshot.symbols[i].tick_size <= 0 || snapshot.symbols[i].point <= 0)
          { status.reason_code = "SYMBOL_SPEC_INCOMPLETE"; return; }
       
       // Check currency presence
       if(snapshot.symbols[i].base_currency == "" ||
          snapshot.symbols[i].profit_currency == "" ||
          snapshot.symbols[i].margin_currency == "")
          { status.reason_code = "SYMBOL_SPEC_INCOMPLETE"; return; }
      }

   // 7. All checks passed
   status.runtime_state = "OBSERVING";
   status.reason_code   = "RUNTIME_EVIDENCE_CURRENT";
  }

// ---------------------------------------------------------------------------
// Material symbol-spec comparison
// ---------------------------------------------------------------------------

bool EEA_RuntimeMaterialSpecEqual(const EEA_RuntimeSymbolSpec &left,
                                  const EEA_RuntimeSymbolSpec &right)
  {
   if(left.broker_symbol       != right.broker_symbol)       return false;
   if(left.digits              != right.digits)              return false;
   if(left.point               != right.point)               return false;
   if(left.tick_size           != right.tick_size)           return false;
   if(left.tick_value          != right.tick_value)          return false;
   if(left.contract_size       != right.contract_size)       return false;
   if(left.volume_min          != right.volume_min)          return false;
   if(left.volume_max          != right.volume_max)          return false;
   if(left.volume_step         != right.volume_step)         return false;
   if(left.stops_level_points  != right.stops_level_points)  return false;
   if(left.freeze_level_points != right.freeze_level_points) return false;
   if(left.trade_mode          != right.trade_mode)          return false;
   if(left.order_mode          != right.order_mode)          return false;
   if(left.expiration_mode     != right.expiration_mode)     return false;
   if(left.calculation_mode    != right.calculation_mode)    return false;
   if(left.base_currency       != right.base_currency)       return false;
   if(left.profit_currency     != right.profit_currency)     return false;
   if(left.margin_currency     != right.margin_currency)     return false;
   return true;
  }

#endif