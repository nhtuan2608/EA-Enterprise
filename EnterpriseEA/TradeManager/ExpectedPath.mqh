#ifndef ENTERPRISE_EA_EXPECTED_PATH_MQH
#define ENTERPRISE_EA_EXPECTED_PATH_MQH

// Pure closed-bar observation after a caller-attested fill. No order or
// position operations. Thresholds are fixture/research inputs, not live policy.
struct EEA_PathProfile
  {
   string config_version;
   string setup_id;
   string trade_style; // SCALP | SWING
   int proving_bars;
   int working_bars;
   int horizon_bars;
   double minimum_mfe_at_proving_r;
   double runner_min_close_r;
  };

struct EEA_PathSeed
  {
   string trade_id;
   string setup_id;
   string config_version;
   string canonical_symbol;
   string direction; // LONG | SHORT
   datetime filled_at_utc;
   double filled_price;
   double invalidation_stop;
  };

struct EEA_PathBar
  {
   string trade_id;
   string config_version;
   long bar_sequence;
   string bar_fingerprint; // Caller-attested full bar content version
   datetime closed_at_utc;
   bool bar_closed_confirmed;
   string data_quality; // OK required
   double open;
   double high;
   double low;
   double close;
   string structure_state; // VALID | INVALID | UNKNOWN
   string volatility_state; // NORMAL | DECAY | UNKNOWN
   string session_state;
   string news_state;
  };

struct EEA_PathState
  {
   bool initialized;
   string status; // UNKNOWN | OBSERVING | INVALIDATED_REVIEW | STOP_TOUCHED_REVIEW
   string phase; // ENTERED | PROVING | WORKING | MATURE | TIMEOUT_REVIEW
   string reason_code;
   string trade_id;
   string setup_id;
   string config_version;
   string canonical_symbol;
   string direction;
   datetime filled_at_utc;
   double filled_price;
   double invalidation_stop;
   double initial_risk_points;
   long last_bar_sequence;
   string last_bar_fingerprint;
   datetime last_bar_closed_at_utc;
   int bars_held;
   double mfe_r;
   double mae_r;
   int bars_to_mfe;
   int bars_to_mae;
   int time_to_05r_bars;
   int time_to_1r_bars;
   int time_to_2r_bars;
  };

struct EEA_PathEvent
  {
   string trade_id;
   string state_before;
   string state_after;
   string phase_before;
   string phase_after;
   string reason_code;
   long bar_sequence;
   datetime closed_at_utc;
   double mfe_r;
   double mae_r;
   string structure_state;
   string volatility_state;
   string session_state;
   string news_state;
  };

bool EEA_PathProfileValid(const EEA_PathProfile &p)
  {
   return p.config_version!="" && p.setup_id!="" &&
          (p.trade_style=="SCALP" || p.trade_style=="SWING") &&
          p.proving_bars>0 && p.working_bars>p.proving_bars &&
          p.horizon_bars>p.working_bars &&
          MathIsValidNumber(p.minimum_mfe_at_proving_r) &&
          p.minimum_mfe_at_proving_r>=0.0 &&
          MathIsValidNumber(p.runner_min_close_r) && p.runner_min_close_r>=0.0;
  }

void EEA_PathDefaults(EEA_PathState &s)
  {
   s.initialized=false;
   s.status="UNKNOWN";
   s.phase="ENTERED";
   s.reason_code="ATTESTED_FILL_REQUIRED";
   s.trade_id="";
   s.setup_id="";
   s.config_version="";
   s.canonical_symbol="";
   s.direction="";
   s.filled_at_utc=0;
   s.filled_price=0.0;
   s.invalidation_stop=0.0;
   s.initial_risk_points=0.0;
   s.last_bar_sequence=0;
   s.last_bar_fingerprint="";
   s.last_bar_closed_at_utc=0;
   s.bars_held=0;
   s.mfe_r=0.0;
   s.mae_r=0.0;
   s.bars_to_mfe=0;
   s.bars_to_mae=0;
   s.time_to_05r_bars=0;
   s.time_to_1r_bars=0;
   s.time_to_2r_bars=0;
  }

bool EEA_PathInit(const EEA_PathSeed &seed,const EEA_PathProfile &p,
                  EEA_PathState &s)
  {
   EEA_PathDefaults(s);
   if(!EEA_PathProfileValid(p) || seed.trade_id=="" ||
      seed.setup_id!=p.setup_id || seed.config_version!=p.config_version ||
      seed.canonical_symbol=="" || seed.filled_at_utc<=0 ||
      !MathIsValidNumber(seed.filled_price) || seed.filled_price<=0.0 ||
      !MathIsValidNumber(seed.invalidation_stop) || seed.invalidation_stop<=0.0 ||
      !((seed.direction=="LONG" && seed.invalidation_stop<seed.filled_price) ||
        (seed.direction=="SHORT" && seed.invalidation_stop>seed.filled_price)))
     { s.reason_code="PATH_SEED_OR_PROFILE_INVALID"; return false; }
   s.initialized=true;
   s.status="OBSERVING";
   s.phase="ENTERED";
   s.reason_code="FILL_ATTESTED_WAITING_FOR_CLOSED_BAR";
   s.trade_id=seed.trade_id;
   s.setup_id=seed.setup_id;
   s.config_version=seed.config_version;
   s.canonical_symbol=seed.canonical_symbol;
   s.direction=seed.direction;
   s.filled_at_utc=seed.filled_at_utc;
   s.filled_price=seed.filled_price;
   s.invalidation_stop=seed.invalidation_stop;
   s.initial_risk_points=MathAbs(seed.filled_price-seed.invalidation_stop);
   return true;
  }

void EEA_PathEventFromState(const EEA_PathState &s,const EEA_PathBar &b,
                            EEA_PathEvent &e)
  {
   e.trade_id=s.trade_id;
   e.state_before=s.status;
   e.state_after=s.status;
   e.phase_before=s.phase;
   e.phase_after=s.phase;
   e.reason_code="";
   e.bar_sequence=b.bar_sequence;
   e.closed_at_utc=b.closed_at_utc;
   e.mfe_r=s.mfe_r;
   e.mae_r=s.mae_r;
   e.structure_state=b.structure_state;
   e.volatility_state=b.volatility_state;
   e.session_state=b.session_state;
   e.news_state=b.news_state;
  }

bool EEA_PathApplyClosedBar(EEA_PathState &s,const EEA_PathProfile &p,
                            const EEA_PathBar &b,EEA_PathEvent &e)
  {
   EEA_PathEventFromState(s,b,e);
   if(!s.initialized || s.status!="OBSERVING" || !EEA_PathProfileValid(p) ||
      p.config_version!=s.config_version || p.setup_id!=s.setup_id)
     { e.reason_code="PATH_STATE_OR_PROFILE_NOT_READY"; return false; }
   if(b.trade_id==s.trade_id && b.config_version==s.config_version &&
      b.bar_closed_confirmed && b.data_quality=="OK" &&
      b.bar_fingerprint!="" &&
      b.bar_sequence==s.last_bar_sequence && s.last_bar_sequence>0 &&
      b.closed_at_utc==s.last_bar_closed_at_utc &&
      b.bar_fingerprint==s.last_bar_fingerprint)
     { e.reason_code="DUPLICATE_CLOSED_BAR_IGNORED"; return true; }
   if(b.trade_id!=s.trade_id || b.config_version!=s.config_version ||
      b.bar_sequence!=s.last_bar_sequence+1 || b.bar_fingerprint=="" ||
      b.closed_at_utc<=s.filled_at_utc ||
      b.closed_at_utc<=s.last_bar_closed_at_utc ||
      !b.bar_closed_confirmed || b.data_quality!="OK" ||
      !MathIsValidNumber(b.open) || !MathIsValidNumber(b.high) ||
      !MathIsValidNumber(b.low) || !MathIsValidNumber(b.close) ||
      b.low<=0.0 || b.low>b.open || b.low>b.close ||
      b.high<b.open || b.high<b.close || b.high<b.low ||
      (b.structure_state!="VALID" && b.structure_state!="INVALID" &&
       b.structure_state!="UNKNOWN") ||
      (b.volatility_state!="NORMAL" && b.volatility_state!="DECAY" &&
       b.volatility_state!="UNKNOWN") ||
      b.session_state=="" || b.news_state=="")
     {
      s.status="UNKNOWN";
      s.reason_code="CLOSED_BAR_MISSING_CONFLICTING_OR_UNTRUSTED";
      e.state_after=s.status;
      e.reason_code=s.reason_code;
      return false;
     }
   s.last_bar_sequence=b.bar_sequence;
   s.last_bar_fingerprint=b.bar_fingerprint;
   s.last_bar_closed_at_utc=b.closed_at_utc;
   s.bars_held++;
   if((s.direction=="LONG" && b.low<=s.invalidation_stop) ||
      (s.direction=="SHORT" && b.high>=s.invalidation_stop))
     {
      // The bar alone cannot establish whether target or stop came first.
      // Preserve prior excursions rather than inventing an intrabar fill/path.
      s.status="STOP_TOUCHED_REVIEW";
      s.reason_code="INTRABAR_PATH_AMBIGUOUS_STOP_TOUCHED";
     }
   else
     {
      double favorable=(s.direction=="LONG" ? b.high-s.filled_price :
                        s.filled_price-b.low)/s.initial_risk_points;
      double adverse=(s.direction=="LONG" ? s.filled_price-b.low :
                      b.high-s.filled_price)/s.initial_risk_points;
      if(!MathIsValidNumber(favorable) || !MathIsValidNumber(adverse))
        {
         s.status="UNKNOWN";
         s.reason_code="PATH_EXCURSION_INVALID";
         e.state_after=s.status;
         e.reason_code=s.reason_code;
         return false;
        }
      if(favorable>s.mfe_r)
        { s.mfe_r=favorable; s.bars_to_mfe=s.bars_held; }
      if(adverse>s.mae_r)
        { s.mae_r=adverse; s.bars_to_mae=s.bars_held; }
      if(s.mfe_r>=0.5 && s.time_to_05r_bars==0) s.time_to_05r_bars=s.bars_held;
      if(s.mfe_r>=1.0 && s.time_to_1r_bars==0) s.time_to_1r_bars=s.bars_held;
      if(s.mfe_r>=2.0 && s.time_to_2r_bars==0) s.time_to_2r_bars=s.bars_held;

      if(b.structure_state=="INVALID")
        {
         s.status="INVALIDATED_REVIEW";
         s.reason_code="STRUCTURE_INVALIDATED_REVIEW";
        }
      else if(b.structure_state=="UNKNOWN" || b.volatility_state=="UNKNOWN")
        {
         s.status="UNKNOWN";
         s.reason_code="PATH_CONTEXT_UNKNOWN";
        }
      else if(s.bars_held>=p.horizon_bars)
        {
         s.phase="TIMEOUT_REVIEW";
         double close_r=(s.direction=="LONG" ? b.close-s.filled_price :
                         s.filled_price-b.close)/s.initial_risk_points;
         s.reason_code=(close_r>=p.runner_min_close_r &&
                        b.volatility_state=="NORMAL" ?
                        "RUNNER_REVIEW_AT_HORIZON" : "TIMEOUT_REVIEW_REQUIRED");
        }
      else if(s.bars_held>=p.proving_bars &&
              s.mfe_r<p.minimum_mfe_at_proving_r &&
              b.volatility_state=="DECAY")
        {
         s.phase=(s.bars_held<=p.working_bars ? "WORKING" : "MATURE");
         s.reason_code="UNDERPERFORMING_REVIEW_REQUIRED";
        }
      else
        {
         s.phase=(s.bars_held<=p.proving_bars ? "PROVING" :
                  (s.bars_held<=p.working_bars ? "WORKING" : "MATURE"));
         s.reason_code="PATH_PROGRESS_OBSERVED";
        }
     }
   e.state_after=s.status;
   e.phase_after=s.phase;
   e.reason_code=s.reason_code;
   e.mfe_r=s.mfe_r;
   e.mae_r=s.mae_r;
   return true;
  }

#endif
