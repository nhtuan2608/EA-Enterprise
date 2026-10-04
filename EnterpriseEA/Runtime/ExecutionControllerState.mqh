#ifndef ENTERPRISE_EA_EXECUTION_CONTROLLER_STATE_MQH
#define ENTERPRISE_EA_EXECUTION_CONTROLLER_STATE_MQH

// Pure controller contract. It carries no transport, storage, clock, or broker dependency.
// A caller must provide the current UTC timestamp and explicitly request a scope.
struct EEA_ExecutionControllerState
  {
   bool kill_active;
   long revision;
   string config_version;
   string account_fingerprint;
   string broker_server;
   string operator_id;
   string reference;
   datetime valid_from_utc;
   datetime valid_until_utc;
   string operation_scope;
  };

void EEA_ExecutionControllerStateDefaults(EEA_ExecutionControllerState &state)
  {
   state.kill_active=true;
   state.revision=0;
   state.config_version="";
   state.account_fingerprint="";
   state.broker_server="";
   state.operator_id="";
   state.reference="";
   state.valid_from_utc=0;
   state.valid_until_utc=0;
   state.operation_scope="";
  }

bool EEA_ExecutionControllerOpaqueIdentifierValid(const string value)
  {
   int length=StringLen(value);
   if(length<=0 || length>128)
      return false;
   for(int i=0;i<length;i++)
     {
      ushort ch=StringGetCharacter(value,i);
      bool alpha=(ch>='A' && ch<='Z') || (ch>='a' && ch<='z');
      bool digit=(ch>='0' && ch<='9');
      if(!alpha && !digit && ch!='_' && ch!='-' && ch!='.' && ch!=':' && ch!='/')
         return false;
     }
   return true;
  }

bool EEA_ExecutionControllerIdentityMatches(const EEA_ExecutionControllerState &state,
                                            const string expected_config_version,
                                            const string expected_account_fingerprint,
                                            const string expected_broker_server)
  {
   if(!EEA_ExecutionControllerOpaqueIdentifierValid(expected_config_version) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(expected_account_fingerprint) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(expected_broker_server))
      return false;
   return state.config_version==expected_config_version &&
          state.account_fingerprint==expected_account_fingerprint &&
          state.broker_server==expected_broker_server;
  }

bool EEA_ExecutionControllerStateValid(const EEA_ExecutionControllerState &state,
                                       const datetime now_utc)
  {
   if(now_utc<=0)
      return false;
   if(state.revision<=0 || state.operator_id=="" || state.reference=="")
      return false;
   if(!EEA_ExecutionControllerOpaqueIdentifierValid(state.config_version) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(state.account_fingerprint) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(state.broker_server) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(state.operator_id) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(state.reference) ||
      !EEA_ExecutionControllerOpaqueIdentifierValid(state.operation_scope))
      return false;
   if(state.valid_from_utc<=0 || state.valid_until_utc<=state.valid_from_utc)
      return false;
   if(now_utc<state.valid_from_utc || now_utc>=state.valid_until_utc)
      return false;
   if(state.operation_scope=="")
      return false;
   return true;
  }

// MARKET_AND_PENDING_ENTRY covers both entry scopes (REQ-021).
bool EEA_ExecutionControllerScopeCovers(const string granted_scope,const string requested_scope)
  {
   if(requested_scope=="") return false;
   if(granted_scope==requested_scope) return true;
   return granted_scope=="MARKET_AND_PENDING_ENTRY" &&
          (requested_scope=="MARKET_ENTRY" || requested_scope=="PENDING_ENTRY");
  }

bool EEA_ExecutionControllerAllowsNewRequest(const EEA_ExecutionControllerState &state,
                                              const string requested_scope,
                                              const datetime now_utc)
  {
   if(state.kill_active)
      return false;
   if(!EEA_ExecutionControllerStateValid(state,now_utc))
      return false;
   if(requested_scope=="")
      return false;
   if(requested_scope!=state.operation_scope &&
      !EEA_ExecutionControllerScopeCovers(state.operation_scope,requested_scope))
      return false;
   return true;
  }

#endif
