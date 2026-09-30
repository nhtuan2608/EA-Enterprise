#ifndef ENTERPRISE_EA_SHARED_STATE_STORE_MQH
#define ENTERPRISE_EA_SHARED_STATE_STORE_MQH

enum EEAStateLoadResult
  {
   EEA_STATE_MISSING=0,
   EEA_STATE_COMPATIBLE=1,
   EEA_STATE_INCOMPATIBLE=2
  };

string EEA_StateToJson(const CSharedState &s)
  {
   string policy="null",policy_version="null",source_url="null",timezone="null",currency="null";
   string daily_policy_version="null";
   if(s.policy.status=="ACTIVE")
     {
      policy="\""+EEA_JsonEscape(s.policy.policy_id)+"\"";
      policy_version="\""+EEA_JsonEscape(s.policy.config_version)+"\"";
      source_url="\""+EEA_JsonEscape(s.policy.source_url)+"\"";
      timezone="\""+EEA_JsonEscape(s.policy.policy_timezone)+"\"";
      currency="\""+EEA_JsonEscape(s.policy.account_currency)+"\"";
      daily_policy_version="\""+EEA_JsonEscape(s.daily_snapshot.policy_version)+"\"";
     }
   string daily_floor="null",overall_floor="null",headroom="null";
   string daily_headroom="null",overall_headroom="null";
   return "{\"schema_version\":\""+EEA_SCHEMA_VERSION+"\",\"state_version\":\"core-state-v1.0.0\",\"updated_at_utc\":\""+
      EEA_IsoUtc(TimeGMT())+"\",\"config_version\":\""+EEA_JsonEscape(s.config_version)+"\",\"source\":\""+
      EEA_JsonEscape(s.source)+"\",\"data_quality\":\""+EEA_JsonEscape(s.data_quality)+"\",\"symbol_resolution\":\""+
      EEA_JsonEscape(s.symbol_resolution)+"\",\"policy_status\":\""+EEA_JsonEscape(s.policy_status)+"\",\"risk_status\":\""+
      EEA_JsonEscape(s.risk_status)+"\",\"symbols\":[],\"account_policy\":{\"policy_id\":"+policy+
      ",\"config_version\":"+policy_version+",\"source_url\":"+source_url+",\"policy_timezone\":"+timezone+
      ",\"account_currency\":"+currency+",\"initial_capital\":null,\"daily_reset_hour\":null,\"daily_reset_minute\":null,\"daily_loss_percent_of_initial\":null,\"overall_loss_percent_of_initial\":null,\"overall_floor_mode\":null,\"safety_buffer\":null,\"internal_daily_loss_limit\":null,\"internal_weekly_drawdown_limit\":null,\"status\":\""+
      EEA_JsonEscape(s.policy.status)+"\"},\"daily_snapshot\":{\"schema_version\":\""+EEA_SCHEMA_VERSION+"\",\"snapshot_id\":\""+
      EEA_JsonEscape(s.daily_snapshot.snapshot_id)+"\",\"reset_at_utc\":\""+EEA_IsoUtc(TimeGMT())+"\",\"balance_at_reset\":0,\"equity_at_reset\":0,\"floating_at_reset\":0,\"commission\":0,\"swap\":0,\"fee\":0,\"daily_floor\":"+daily_floor+",\"overall_floor\":"+overall_floor+",\"floor_headroom\":"+headroom+",\"policy_version\":"+daily_policy_version+",\"snapshot_source\":\"EA_CORE\",\"reason_code\":\"POLICY_DATA_UNKNOWN\",\"data_quality\":\"UNKNOWN\"},\"portfolio_snapshot\":{\"schema_version\":\""+
      EEA_SCHEMA_VERSION+"\",\"snapshot_id\":\""+EEA_JsonEscape(s.portfolio_snapshot.snapshot_id)+"\",\"as_of_utc\":\""+
      EEA_IsoUtc(TimeGMT())+"\",\"account_scope\":\"UNKNOWN\",\"equity\":0,\"realized_pnl\":0,\"floating_pnl\":0,\"commission\":0,\"swap\":0,\"fee\":0,\"initial_risk_money\":0,\"projected_loss_to_sl\":0,\"remaining_loss_to_sl\":0,\"locked_profit\":0,\"daily_floor_headroom\":"+daily_headroom+",\"overall_floor_headroom\":"+overall_headroom+",\"reconciliation_status\":\"UNKNOWN\",\"risk_status\":\""+
      EEA_JsonEscape(s.risk_status)+"\",\"data_quality\":\"UNKNOWN\"}}";
  }

EEAStateLoadResult EEA_StateCheckCheckpoint(const string path,const string config_version)
  {
   if(!FileIsExist(path,0)) return EEA_STATE_MISSING;
   int h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE) return EEA_STATE_INCOMPATIBLE;
   ulong size=FileSize(h);
   if(size==0 || size>1048576) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uchar bytes[];
   if(ArrayResize(bytes,(int)size)!=(int)size) { FileClose(h); return EEA_STATE_INCOMPATIBLE; }
   uint count=FileReadArray(h,bytes,0,(int)size);
   FileClose(h);
   if(count!=(uint)size) return EEA_STATE_INCOMPATIBLE;
   string json=CharArrayToString(bytes,0,(int)count,CP_UTF8);
   if(StringLen(json)<2 || StringGetCharacter(json,0)!=123 ||
      StringGetCharacter(json,StringLen(json)-1)!=125)
      return EEA_STATE_INCOMPATIBLE;
   string schema_token="\"schema_version\":\""+EEA_SCHEMA_VERSION+"\"";
   string config_token="\"config_version\":\""+EEA_JsonEscape(config_version)+"\"";
   string state_token="\"state_version\":\"core-state-v1.0.0\"";
   if(StringFind(json,schema_token)<0 || StringFind(json,config_token)<0 || StringFind(json,state_token)<0)
      return EEA_STATE_INCOMPATIBLE;
   // This phase only understands the unselected, empty boot snapshot. Unknown persisted state blocks use.
   if(StringFind(json,"\"policy_status\":\"UNSELECTED\"")<0 ||
      StringFind(json,"\"symbol_resolution\":\"UNRESOLVED\"")<0 ||
      StringFind(json,"\"risk_status\":\"POLICY_DATA_UNKNOWN\"")<0)
      return EEA_STATE_INCOMPATIBLE;
   return EEA_STATE_COMPATIBLE;
  }

bool EEA_StateSave(const string path,const CSharedState &s)
  {
   // This Phase 1 checkpoint is deliberately limited to the empty, unselected boot state.
   if(s.data_quality!="UNKNOWN" || s.symbol_resolution!="UNRESOLVED" ||
      s.policy_status!="UNSELECTED" || s.policy.status!="UNSELECTED" ||
      s.risk_status!="POLICY_DATA_UNKNOWN") return false;
   return EEA_WriteAtomicText(path,EEA_StateToJson(s));
  }

#endif
