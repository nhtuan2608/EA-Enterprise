#ifndef ENTERPRISE_EA_STRUCTURAL_LEVELS_MQH
#define ENTERPRISE_EA_STRUCTURAL_LEVELS_MQH

// Price geometry only. MarketState selects invalidation and target upstream.
// These proposed prices do not grant entry permission or satisfy broker checks.
struct EEA_StructuralLevels
  {
   bool valid;
   string reason_code;
   double stop_loss;
   double take_profit;
  };

double EEA_LevelFloorTick(const double price,const double tick_size)
  {
   return MathFloor(price/tick_size)*tick_size;
  }

double EEA_LevelCeilTick(const double price,const double tick_size)
  {
   return MathCeil(price/tick_size)*tick_size;
  }

bool EEA_ProposeStructuralLevels(const int direction,const double entry_reference,
                                 const double invalidation,const double target,
                                 const double stop_buffer,const double tick_size,
                                 EEA_StructuralLevels &result)
  {
   result.valid=false;
   result.reason_code="INVALID_LEVEL_INPUT";
   result.stop_loss=0.0;
   result.take_profit=0.0;
   if(direction!=1 && direction!=-1) return false;
   if(!MathIsValidNumber(entry_reference) || !MathIsValidNumber(invalidation) ||
      !MathIsValidNumber(target) || !MathIsValidNumber(stop_buffer) ||
      !MathIsValidNumber(tick_size)) return false;
   if(entry_reference<=0.0 || invalidation<=0.0 || target<=0.0 ||
      stop_buffer<=0.0 || tick_size<=0.0) return false;

   double raw_stop=(direction==1 ? invalidation-stop_buffer : invalidation+stop_buffer);
   if(!MathIsValidNumber(raw_stop) || !MathIsValidNumber(raw_stop/tick_size) ||
      !MathIsValidNumber(target/tick_size)) return false;

   if(direction==1)
     {
      if(invalidation>=entry_reference || target<=entry_reference)
        {
         result.reason_code="INVALID_LONG_GEOMETRY";
         return false;
        }
      result.stop_loss=EEA_LevelFloorTick(raw_stop,tick_size);
      result.take_profit=EEA_LevelFloorTick(target,tick_size);
      if(!MathIsValidNumber(result.stop_loss) || !MathIsValidNumber(result.take_profit) ||
         result.stop_loss<=0.0 || result.stop_loss>=invalidation ||
         result.take_profit<=entry_reference)
        {
         result.reason_code="LEVELS_COLLAPSED_AFTER_TICK_ROUNDING";
         return false;
        }
     }
   else
     {
      if(invalidation<=entry_reference || target>=entry_reference)
        {
         result.reason_code="INVALID_SHORT_GEOMETRY";
         return false;
        }
      result.stop_loss=EEA_LevelCeilTick(raw_stop,tick_size);
      result.take_profit=EEA_LevelCeilTick(target,tick_size);
      if(!MathIsValidNumber(result.stop_loss) || !MathIsValidNumber(result.take_profit) ||
         result.stop_loss<=invalidation || result.take_profit>=entry_reference)
        {
         result.reason_code="LEVELS_COLLAPSED_AFTER_TICK_ROUNDING";
         return false;
        }
     }
   result.valid=true;
   result.reason_code="PROPOSED_LEVELS_ONLY";
   return true;
  }

#endif
