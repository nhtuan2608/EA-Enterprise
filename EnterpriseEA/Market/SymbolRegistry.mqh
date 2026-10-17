#ifndef ENTERPRISE_EA_SYMBOL_REGISTRY_MQH
#define ENTERPRISE_EA_SYMBOL_REGISTRY_MQH

// Registry records follow symbol-registry.schema.json plus offline quality/version
// evidence carried by this pure resolver. Runtime metadata is supplied by the caller.
struct EEA_SymbolRegistryEntry
  {
   string canonical_symbol;
   string broker_symbol;
   string broker_server;
   string resolution_status;   // RESOLVED | UNRESOLVED | BLOCKED
   string metadata_quality;    // OK required
   string source_version;
   string metadata_version;
   string metadata_fingerprint;
  };

struct EEA_SymbolRuntimeEvidence
  {
   string configured_broker_server;
   string observed_broker_server;
   string observed_broker_symbol;
   bool broker_symbol_enabled;
   string metadata_quality;    // OK required
   string metadata_version;
   string metadata_fingerprint;
  };

struct EEA_SymbolResolution
  {
   bool resolved;
   string status;              // RESOLVED | UNRESOLVED | BLOCKED
   string reason_code;
   string canonical_symbol;
   string broker_symbol;
   string broker_server;
   string source_version;
   string metadata_version;
   string metadata_fingerprint;
  };

void EEA_SymbolResolutionDefaults(EEA_SymbolResolution &r,const string canonical)
  {
   r.resolved=false;
   r.status="UNRESOLVED";
   r.reason_code="NO_EXACT_MAPPING";
   r.canonical_symbol=canonical;
   r.broker_symbol="";
   r.broker_server="";
   r.source_version="";
   r.metadata_version="";
   r.metadata_fingerprint="";
  }

// Suggest exact canonical prefix/suffix variants for operator review only.
int EEA_SuggestBrokerSymbol(const string canonical,const string &available_symbols[],
                            string &suggested_symbol)
  {
   suggested_symbol="";
   if(canonical=="") return 0;
   int found=0;
   int canonical_len=StringLen(canonical);
   for(int n=0;n<ArraySize(available_symbols);n++)
     {
      string candidate=available_symbols[n];
      int candidate_len=StringLen(candidate);
      if(candidate=="" || candidate==canonical || candidate_len<=canonical_len) continue;
      bool prefix=(StringSubstr(candidate,0,canonical_len)==canonical);
      bool suffix=(StringSubstr(candidate,candidate_len-canonical_len,canonical_len)==canonical);
      if(!prefix && !suffix) continue;
      bool duplicate=false;
      for(int prior=0;prior<n;prior++)
         if(available_symbols[prior]==candidate) { duplicate=true; break; }
      if(duplicate) continue;
      found++;
      if(found==1) suggested_symbol=candidate;
      else suggested_symbol="";
     }
   return found;
  }

bool EEA_ResolveSymbol(const string canonical,const EEA_SymbolRegistryEntry &entries[],
                       const EEA_SymbolRuntimeEvidence &runtime,
                       EEA_SymbolResolution &result)
  {
   EEA_SymbolResolutionDefaults(result,canonical);
   if(canonical=="" || runtime.configured_broker_server=="" || runtime.observed_broker_server=="")
     { result.status="BLOCKED"; result.reason_code="BROKER_SERVER_IDENTITY_MISSING"; return false; }
   if(runtime.configured_broker_server!=runtime.observed_broker_server)
     { result.status="BLOCKED"; result.reason_code="BROKER_SERVER_IDENTITY_MISMATCH"; return false; }

   int match=-1;
   int matches=0;
   for(int n=0;n<ArraySize(entries);n++)
      if(entries[n].canonical_symbol==canonical && entries[n].broker_server==runtime.observed_broker_server)
        { match=n; matches++; }
   if(matches==0)
     { result.reason_code="NO_EXACT_SERVER_MAPPING"; return false; }
   if(matches!=1)
     { result.reason_code="AMBIGUOUS_EXACT_MAPPING"; return false; }

   EEA_SymbolRegistryEntry entry=entries[match];
   result.broker_server=entry.broker_server;
   result.broker_symbol=entry.broker_symbol;
   result.source_version=entry.source_version;
   result.metadata_version=entry.metadata_version;
   result.metadata_fingerprint=entry.metadata_fingerprint;
   if(entry.resolution_status=="BLOCKED")
     { result.status="BLOCKED"; result.reason_code="REGISTRY_ENTRY_BLOCKED"; return false; }
   if(entry.resolution_status!="RESOLVED" || entry.broker_symbol=="")
     { result.reason_code="REGISTRY_ENTRY_UNRESOLVED"; return false; }
   if(entry.metadata_quality!="OK" || entry.source_version=="" || entry.metadata_version=="" ||
      entry.metadata_fingerprint=="")
     { result.reason_code="REGISTRY_METADATA_INCOMPLETE"; return false; }
   if(!runtime.broker_symbol_enabled)
     { result.status="BLOCKED"; result.reason_code="BROKER_SYMBOL_DISABLED"; return false; }
   if(runtime.observed_broker_symbol!=entry.broker_symbol)
     { result.status="BLOCKED"; result.reason_code="BROKER_SYMBOL_IDENTITY_MISMATCH"; return false; }
   if(runtime.metadata_quality!="OK" || runtime.metadata_version=="" || runtime.metadata_fingerprint=="")
     { result.reason_code="RUNTIME_METADATA_INCOMPLETE"; return false; }
   if(runtime.metadata_version!=entry.metadata_version ||
      runtime.metadata_fingerprint!=entry.metadata_fingerprint)
     { result.status="BLOCKED"; result.reason_code="MATERIAL_SPEC_CHANGED"; return false; }

   result.resolved=true;
   result.status="RESOLVED";
   result.reason_code="EXACT_MAPPING_AND_METADATA_CONFIRMED";
   return true;
  }

struct EEA_SymbolDiscoveryCandidate
  {
   string name;
   bool   tradeable;
   bool   conversion_only;
  };

struct EEA_SymbolDiscoveryResult
  {
   bool   resolved;
   string status;
   string reason_code;
   string canonical_symbol;
   string broker_symbol;
  };

string EEA_TrimUpper(const string in_str)
  {
   string s = in_str;
   StringTrimLeft(s);
   StringTrimRight(s);
   int len = StringLen(s);
   while(len > 0)
     {
      ushort ch = StringGetCharacter(s, 0);
      if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n')
        {
         s = StringSubstr(s, 1);
         len = StringLen(s);
        }
      else break;
     }
   while(len > 0)
     {
      ushort ch = StringGetCharacter(s, len - 1);
      if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n')
        {
         s = StringSubstr(s, 0, len - 1);
         len = StringLen(s);
        }
      else break;
     }
   StringToUpper(s);
   return s;
  }

int EEA_NormalizeCanonicalCsv(const string csv, string &out_canonicals[], const int max_symbols=32)
  {
   ArrayResize(out_canonicals, 0);
   if(csv == "") return 0;
   
   string temp_csv = csv;
   StringTrimLeft(temp_csv);
   StringTrimRight(temp_csv);
   if(temp_csv == "") return 0;

   string raw_tokens[];
   ushort u_sep = StringGetCharacter(",", 0);
   int raw_count = StringSplit(temp_csv, u_sep, raw_tokens);
   if(raw_count <= 0) return 0;

   int count = 0;
   for(int i = 0; i < raw_count; i++)
     {
      string token = EEA_TrimUpper(raw_tokens[i]);
      if(token == "") continue;
      
      bool duplicate = false;
      for(int j = 0; j < count; j++)
        {
         if(out_canonicals[j] == token)
           {
            duplicate = true;
            break;
           }
        }
      if(duplicate) continue;
      
      count++;
      ArrayResize(out_canonicals, count);
      out_canonicals[count - 1] = token;
     }

   if(count == 0 || count > max_symbols)
     {
      ArrayResize(out_canonicals, 0);
      return 0;
     }

   return count;
  }

// Other broker names for the same instrument, tried after exact, suffix and prefix matches (rank 4).
// 17/10/2026: WTI crude (Lirunex USOIL.r), the S&P 500 index (Lirunex SPCUSD.r), the dollar index (Lirunex USDInd).
int EEA_SymbolAliases(const string canonical, string &aliases[])
  {
   ArrayResize(aliases, 0);
   if(canonical == "DXY")
     { ArrayResize(aliases, 2); aliases[0] = "USDX"; aliases[1] = "USDIND"; }
   else if(canonical == "USOUSD")
     { ArrayResize(aliases, 3); aliases[0] = "USOIL"; aliases[1] = "XTIUSD"; aliases[2] = "WTI"; }
   else if(canonical == "US500")
     { ArrayResize(aliases, 4); aliases[0] = "SPCUSD"; aliases[1] = "SPX500"; aliases[2] = "SP500"; aliases[3] = "USA500"; }
   return ArraySize(aliases);
  }

int EEA_RankSymbolCandidate(const string canonical, const EEA_SymbolDiscoveryCandidate &candidate, string &out_reason)
  {
   out_reason = "";
   string c_upper = EEA_TrimUpper(canonical);
   string c_name  = EEA_TrimUpper(candidate.name);
   if(c_upper == "" || c_name == "") return 0;

   string aliases[];
   const int alias_count = EEA_SymbolAliases(c_upper, aliases);

   bool tradeable = candidate.tradeable;
   bool conversion_only = candidate.conversion_only;
   int rank_value = (!tradeable || conversion_only) ? 5 : 0;

   int canonical_len = StringLen(c_upper);
   int name_len = StringLen(c_name);

   if(c_name == c_upper)
     {
      if(rank_value == 5)
        {
         out_reason = conversion_only ? "CONVERSION_ONLY" : "DISABLED";
         return 5;
        }
      out_reason = "EXACT_TRADEABLE";
      return 1;
     }

   if(canonical_len > 0 && name_len > canonical_len && StringSubstr(c_name, 0, canonical_len) == c_upper)
     {
      if(rank_value == 5)
        {
         out_reason = conversion_only ? "CONVERSION_ONLY" : "DISABLED";
         return 5;
        }
      out_reason = "SUFFIX_TRADEABLE";
      return 2;
     }

   if(canonical_len > 0 && name_len > canonical_len && StringSubstr(c_name, name_len - canonical_len, canonical_len) == c_upper)
     {
      if(rank_value == 5)
        {
         out_reason = conversion_only ? "CONVERSION_ONLY" : "DISABLED";
         return 5;
        }
      out_reason = "PREFIX_TRADEABLE";
      return 2;
     }

   for(int a = 0; a < alias_count; a++)
     {
      string alias_target = aliases[a];
      int alias_len = StringLen(alias_target);
      bool alias_match = false;
      if(c_name == alias_target) alias_match = true;
      else if(name_len > alias_len && StringSubstr(c_name, 0, alias_len) == alias_target) alias_match = true;
      else if(name_len > alias_len && StringSubstr(c_name, name_len - alias_len, alias_len) == alias_target) alias_match = true;

      if(alias_match)
        {
         if(rank_value == 5)
           {
            out_reason = conversion_only ? "CONVERSION_ONLY" : "DISABLED";
            return 5;
           }
         out_reason = "ALIAS_TRADEABLE";
         return 4;
        }
     }

   return 0;
  }

int EEA_ResolveSymbolsBatch(const string &canonicals[], const EEA_SymbolDiscoveryCandidate &available[], EEA_SymbolDiscoveryResult &results[])
  {
   int canonical_count = ArraySize(canonicals);
   ArrayResize(results, canonical_count);
   int available_count = ArraySize(available);

   int resolved_count = 0;

   for(int i = 0; i < canonical_count; i++)
     {
      string canonical = canonicals[i];
      int best_rank = 999;
      
      int best_count = 0;
      int best_indices[];
      string best_reasons[];

      for(int j = 0; j < available_count; j++)
        {
         string reason = "";
         int rank_score = EEA_RankSymbolCandidate(canonical, available[j], reason);
         if(rank_score > 0)
           {
            if(rank_score < best_rank)
              {
               best_rank = rank_score;
               best_count = 1;
               ArrayResize(best_indices, 1);
               ArrayResize(best_reasons, 1);
               best_indices[0] = j;
               best_reasons[0] = reason;
              }
            else if(rank_score == best_rank)
              {
               best_count++;
               ArrayResize(best_indices, best_count);
               ArrayResize(best_reasons, best_count);
               best_indices[best_count - 1] = j;
               best_reasons[best_count - 1] = reason;
              }
           }
        }

      results[i].canonical_symbol = canonical;
      results[i].broker_symbol    = "";
      results[i].status           = "MISSING";
      results[i].reason_code      = "NO_MATCHING_CANDIDATE";
      results[i].resolved         = false;

      if(best_count == 0)
        {
        }
      else if(best_rank >= 5)
        {
         results[i].status = "DISABLED";
         if(best_reasons[0] == "CONVERSION_ONLY")
            results[i].reason_code = "CONVERSION_ONLY_SYMBOL";
         else
            results[i].reason_code = "BROKER_SYMBOL_DISABLED";
        }
      else if(best_count > 1)
        {
         results[i].status = "AMBIGUOUS";
         results[i].reason_code = "AMBIGUOUS_BEST_RANK_MATCH";
        }
      else
        {
         int cand_idx = best_indices[0];
         string reason = best_reasons[0];
         results[i].broker_symbol = available[cand_idx].name;
         results[i].status = "RESOLVED";
         results[i].resolved = true;
         resolved_count++;

         if(reason == "EXACT_TRADEABLE")
            results[i].reason_code = "UNIQUE_EXACT_MATCH";
         else if(reason == "SUFFIX_TRADEABLE")
            results[i].reason_code = "UNIQUE_SUFFIX_ROOT_MATCH";
         else if(reason == "PREFIX_TRADEABLE")
            results[i].reason_code = "UNIQUE_PREFIX_ROOT_MATCH";
         else if(reason == "ALIAS_TRADEABLE")
            results[i].reason_code = "UNIQUE_ALIAS_ROOT_MATCH";
        }
     }

   return canonical_count;
  }

#endif

