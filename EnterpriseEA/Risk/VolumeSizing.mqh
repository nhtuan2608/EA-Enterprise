#ifndef ENTERPRISE_EA_VOLUME_SIZING_MQH
#define ENTERPRISE_EA_VOLUME_SIZING_MQH

// Pure sizing from caller-supplied broker-validated quotes. No symbol or trade APIs.
struct EEA_VolumeSizingInput
  {
   string config_version;
   string account_currency;
   double risk_budget;
   bool loss_quote_valid;
   string loss_quote_quality;       // OK required
   string loss_quote_version;
   string loss_quote_currency;
   double loss_per_lot_at_sl;       // Account-currency loss for 1.0 lot at selected structural SL
   double volume_min;
   double volume_max;
   double volume_step;
   bool final_loss_quote_valid;
   string final_loss_quote_quality; // OK required; calculated at selected SL for final rounded volume incl costs/slippage
   string final_loss_quote_version;
   string final_loss_quote_currency;
   double final_loss_quote_volume;
   double final_loss_at_sl;
   bool margin_quote_valid;
   string margin_quote_quality;     // OK required
   string margin_quote_version;
   string margin_quote_currency;
   double margin_quote_volume;      // Must match the final rounded volume; caller can retry otherwise
   double required_margin;
   double available_margin;
  };

struct EEA_VolumeSizingResult
  {
   bool valid;
   string sizing_status;            // SIZED | BLOCKED | INPUT_UNKNOWN
   string reason_code;
   double raw_volume;
   double volume;
   double projected_loss;
   double required_margin;
   double available_margin;
  };

void EEA_VolumeSizingDefaults(EEA_VolumeSizingResult &r)
  {
   r.valid=false;
   r.sizing_status="INPUT_UNKNOWN";
   r.reason_code="INPUT_UNKNOWN";
   r.raw_volume=0.0;
   r.volume=0.0;
   r.projected_loss=0.0;
   r.required_margin=0.0;
   r.available_margin=0.0;
  }

bool EEA_SizeVolume(const EEA_VolumeSizingInput &i,EEA_VolumeSizingResult &r)
  {
   EEA_VolumeSizingDefaults(r);
   if(i.config_version=="" || i.account_currency=="" ||
      !MathIsValidNumber(i.risk_budget) || i.risk_budget<=0.0 ||
      !i.loss_quote_valid || i.loss_quote_quality!="OK" ||
      i.loss_quote_version!=i.config_version || i.loss_quote_currency!=i.account_currency ||
      !MathIsValidNumber(i.loss_per_lot_at_sl) || i.loss_per_lot_at_sl<=0.0 ||
      !MathIsValidNumber(i.volume_min) || !MathIsValidNumber(i.volume_max) ||
      !MathIsValidNumber(i.volume_step) || i.volume_min<=0.0 ||
      i.volume_max<i.volume_min || i.volume_step<=0.0)
     { r.reason_code="LOSS_QUOTE_OR_VOLUME_SPEC_INVALID"; return false; }
   if(!i.margin_quote_valid || i.margin_quote_quality!="OK" ||
      i.margin_quote_version!=i.config_version || i.margin_quote_currency!=i.account_currency ||
      !MathIsValidNumber(i.margin_quote_volume) || !MathIsValidNumber(i.required_margin) ||
      !MathIsValidNumber(i.available_margin) || i.margin_quote_volume<=0.0 ||
      i.required_margin<0.0 || i.available_margin<0.0)
     { r.reason_code="MARGIN_QUOTE_MISSING_OR_INVALID"; return false; }

   r.raw_volume=i.risk_budget/i.loss_per_lot_at_sl;
   if(!MathIsValidNumber(r.raw_volume) || r.raw_volume<=0.0)
     { r.reason_code="CALCULATION_OVERFLOW_OR_INVALID_RESULT"; return false; }
   double capped=MathMin(r.raw_volume,i.volume_max);
   r.volume=MathFloor(capped/i.volume_step)*i.volume_step;
   if(!MathIsValidNumber(r.volume))
     { r.reason_code="CALCULATION_OVERFLOW_OR_INVALID_RESULT"; return false; }
   if(r.volume>i.volume_max)
     { r.reason_code="ROUNDED_VOLUME_EXCEEDS_MAXIMUM"; return false; }
   if(r.volume<i.volume_min)
     { r.sizing_status="BLOCKED"; r.reason_code="RISK_BUDGET_BELOW_MINIMUM_VOLUME"; return false; }

   if(!i.final_loss_quote_valid || i.final_loss_quote_quality!="OK" ||
      i.final_loss_quote_version!=i.config_version || i.final_loss_quote_currency!=i.account_currency ||
      !MathIsValidNumber(i.final_loss_quote_volume) ||
      MathAbs(i.final_loss_quote_volume-r.volume)>i.volume_step*1e-8 ||
      !MathIsValidNumber(i.final_loss_at_sl) || i.final_loss_at_sl<=0.0)
     { r.reason_code="FINAL_VOLUME_LOSS_QUOTE_MISSING_OR_MISMATCHED"; return false; }
   r.projected_loss=i.final_loss_at_sl;
   if(r.projected_loss>i.risk_budget)
     { r.sizing_status="BLOCKED"; r.reason_code="FINAL_VOLUME_LOSS_EXCEEDS_RISK_BUDGET"; return false; }
   r.required_margin=i.required_margin;
   r.available_margin=i.available_margin;
   if(MathAbs(i.margin_quote_volume-r.volume)>i.volume_step*1e-8)
     { r.reason_code="MARGIN_QUOTE_VOLUME_MISMATCH"; return false; }
   if(i.required_margin>i.available_margin)
     { r.sizing_status="BLOCKED"; r.reason_code="INSUFFICIENT_AVAILABLE_MARGIN"; return false; }

   r.valid=true;
   r.sizing_status="SIZED";
   r.reason_code="ROUNDED_VOLUME_WITHIN_RISK_AND_MARGIN_BUDGETS";
   return true;
  }

#endif
