# Symbol registry resolver (offline)

`SymbolRegistry.mqh` resolves only an explicit canonical symbol mapping for the exact observed broker server. It consumes a registry record and runtime evidence supplied by its caller; it makes no MT5 calls and is not included by the EA shell.

The resolver requires one exact `(canonical_symbol, broker_server)` record, `RESOLVED` status, nonempty source and metadata versions, `OK` metadata quality, an enabled mapped broker symbol, and matching runtime metadata version/fingerprint. Duplicate exact mappings, missing identity/metadata, disabled symbols, or material spec changes fail closed as unresolved/blocked. The current broker server must match the configured server. After material spec changes, the caller must refresh the registry and invalidate candidates/recompute sizing before attempting resolution again.

`EEA_SuggestBrokerSymbol` can report prefix/suffix variants such as `EURUSD.a` or `mEURUSD`, but it is advisory only. Suggestions never enter `EEA_ResolveSymbol` as accepted mappings. An operator must persist one explicit mapping before the resolver can return `RESOLVED`.

The base persisted record fields follow `schemas/symbol-registry.schema.json`. The pure module carries additional sidecar evidence (`metadata_quality`, `metadata_version`, `metadata_fingerprint`) because the schema's `source_version` alone does not prove runtime spec identity. The caller computes the fingerprint over the material instrument fields and supplies current broker/server/symbol-enabled state. Fixtures are synthetic. Python oracle tests are not MQL5 compiler/runtime or broker validation.
