#ifndef ENTERPRISE_EA_STATE_MQH
#define ENTERPRISE_EA_STATE_MQH

struct CSymbolRegistryEntry
  {
   string canonical_symbol;
   string broker_symbol;
   string broker_server;
   string asset_class;
   string base_currency;
   string quote_currency;
   string profit_currency;
   double contract_size;
   double tick_size;
   double tick_value;
   int digits;
   double volume_min;
   double volume_max;
   double volume_step;
   int stops_level_points;
   int freeze_level_points;
   string margin_mode;
   string sessions;
   string timezone;
   double spread_guard_points;
   string setup_whitelist;
   string timeframe_whitelist;
   string resolution_status;
   string source_version;
  };

struct CAccountPolicy
  {
   string policy_id;          // FTMO_1_STEP | FTMO_2_STEP | CUSTOM; empty until confirmed
   string config_version;
   string source_url;
   string policy_timezone;
   int daily_reset_hour;
   int daily_reset_minute;
   string account_currency;
   double initial_capital;
   double daily_loss_amount;
   double overall_loss_amount;
   double daily_loss_percent_of_initial;
   double overall_loss_percent_of_initial;
   string overall_floor_mode;
   double safety_buffer;
   double internal_daily_loss_limit;
   double internal_weekly_drawdown_limit;
   string status;             // UNSELECTED | ACTIVE | POLICY_DATA_UNKNOWN
  };

struct CDailySnapshot
  {
   string snapshot_id;
   string reset_at_utc;
   double balance_at_reset;
   double equity_at_reset;
   double floating_at_reset;
   double daily_floor;
   double overall_floor;
   double floor_headroom;
   double commission;
   double swap;
   double fee;
   string snapshot_source;
   string reason_code;
   string policy_version;
   string data_quality;
  };

struct CPortfolioRiskSnapshot
  {
   string snapshot_id;
   string as_of_utc;
   double equity;
   double floating_pnl;
   double initial_risk_money;
   double projected_loss_to_sl;
   double remaining_loss_to_sl;
   double locked_profit;
   double realized_pnl;
   double commission;
   double swap;
   double fee;
   double daily_floor_headroom;
   double overall_floor_headroom;
   string account_scope;
   string reconciliation_status;
   string risk_status;
   string data_quality;
  };

struct CSharedState
  {
   string schema_version;
   string config_version;
   string source;
   string data_quality;
   string symbol_resolution;
   string policy_status;
   string risk_status;
   CAccountPolicy policy;
   CDailySnapshot daily_snapshot;
   CPortfolioRiskSnapshot portfolio_snapshot;
  };

bool EEA_StateCanAllowEntry(const CSharedState &state)
  {
   // Phase 1 cannot grant entry. Later phases must replace this explicit fail-closed gate.
   return false;
  }

#endif
