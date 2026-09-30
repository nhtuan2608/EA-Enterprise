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

#endif
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

int EEA_NormalizeCanonicalCsv(const string csv, string &out_canonicals[], const int max_symbols=32)
  {
   return 0; // Stub
  }

int EEA_RankSymbolCandidate(const string canonical, const EEA_SymbolDiscoveryCandidate &candidate, string &out_reason)
  {
   return 0; // Stub
  }

int EEA_ResolveSymbolsBatch(const string &canonicals[], const EEA_SymbolDiscoveryCandidate &available[], EEA_SymbolDiscoveryResult &results[])
  {
   return 0; // Stub
  }
