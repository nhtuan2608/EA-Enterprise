#ifndef ENTERPRISE_EA_EXECUTION_CONTROLLER_STATE_MQH
#define ENTERPRISE_EA_EXECUTION_CONTROLLER_STATE_MQH

// Pure controller contract. It carries no transport, storage, clock, or broker dependency.
// A caller must provide the current UTC timestamp and explicitly request a scope.
struct EEA_ExecutionControllerState
  {
   bool kill_active;
   long revision;
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
   state.operator_id="";
   state.reference="";
   state.valid_from_utc=0;
   state.valid_until_utc=0;
   state.operation_scope="";
  }

bool EEA_ExecutionControllerStateValid(const EEA_ExecutionControllerState &state,
                                       const datetime now_utc)
  {
   if(now_utc<=0)
      return false;
   if(state.revision<=0 || state.operator_id=="" || state.reference=="")
      return false;
   if(state.valid_from_utc<=0 || state.valid_until_utc<=state.valid_from_utc)
      return false;
   if(now_utc<state.valid_from_utc || now_utc>=state.valid_until_utc)
      return false;
   if(state.operation_scope=="")
      return false;
   return true;
  }

bool EEA_ExecutionControllerAllowsNewRequest(const EEA_ExecutionControllerState &state,
                                              const string requested_scope,
                                              const datetime now_utc)
  {
   if(state.kill_active)
      return false;
   if(!EEA_ExecutionControllerStateValid(state,now_utc))
      return false;
   if(requested_scope=="" || requested_scope!=state.operation_scope)
      return false;
   return true;
  }

#endif
