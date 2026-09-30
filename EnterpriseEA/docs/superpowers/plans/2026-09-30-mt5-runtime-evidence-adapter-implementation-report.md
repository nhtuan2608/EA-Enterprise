# MT5 Runtime Evidence Adapter Implementation Report

> **For agentic workers:** This report tracks the implementation of the MT5 runtime evidence adapter increment. Each task records created/modified files, test commands, and evidence. This is not a Git repository; exact file paths and test outputs replace commit references.

**Spec:** `docs/superpowers/specs/2026-09-30-mt5-runtime-evidence-adapter-design.md`  
**Plan:** `docs/superpowers/plans/2026-09-30-mt5-runtime-evidence-adapter.md`  
**Baseline:** 111 passing offline tests (pre-increment)

---

## Task 1: Pure runtime evidence contract

**Status:** ✅ COMPLETE  
**Date:** 2026-09-30

### Files created

- `Tests/Fixtures/runtime-evidence-v0.1.0.json` — synthetic valid and invalid evidence cases
- `Tests/runtime_evidence_oracle.py` — Python reference validator (evaluate, material_spec_equal)
- `Tests/runtime_evidence_tests.py` — behavioral and static-boundary tests (6 tests)
- `Runtime/RuntimeEvidence.mqh` — MQL5 pure contract (structures, defaults, validation, material-spec comparison)

### Test execution

#### RED phase (before implementation)

**Command:**
```powershell
cd Tests
python -m unittest runtime_evidence_tests -v
```

**Output:**
```
ERROR: runtime_evidence_tests (unittest.loader._FailedTest.runtime_evidence_tests)
----------------------------------------------------------------------
ImportError: Failed to import test module: runtime_evidence_tests
ModuleNotFoundError: No module named 'runtime_evidence_oracle'
```

**Reason:** Oracle module and MQL pure contract do not yet exist. This proves the new contract is absent.

#### GREEN phase (after implementation)

**Command:**
```powershell
cd Tests
python -m unittest runtime_evidence_tests -v
```

**Output:**
```
test_complete_empty_account_is_observing ... ok
test_identity_duplicates_and_watermark_regression_block ... ok
test_incomplete_sources_fail_closed ... ok
test_material_symbol_spec_comparison ... ok
test_mql_pure_contract_structure_and_purity ... ok
test_runtime_core_not_included_by_shell_yet ... ok
----------------------------------------------------------------------
Ran 6 tests in 0.001s
OK
```

#### Full suite verification

**Command:**
```powershell
cd Tests
python -m unittest discover -p '*_tests.py' -v
```

**Output (summary):**
```
Ran 117 tests in 0.043s
OK
```

**Evidence:** 111 baseline tests + 6 new runtime evidence tests = 117 total, zero failures.

### Contract summary

**Structures defined in `Runtime/RuntimeEvidence.mqh`:**
- `EEA_RuntimeAccountSnapshot`
- `EEA_RuntimeSymbolSpec`
- `EEA_RuntimePositionRow`
- `EEA_RuntimeOrderRow`
- `EEA_RuntimeDealRow`
- `EEA_RuntimeReconciliationSnapshot`
- `EEA_RuntimeStatus`

**Helpers:**
- `EEA_RuntimeDefaults` — sets BLOCKED / RUNTIME_RECONCILIATION_REQUIRED / new_entries_blocked=true
- `EEA_RuntimeValidate` — validation order matches oracle (schema → identity → freshness → watermark → duplicates → completeness → symbols → OBSERVING)
- `EEA_RuntimeMaterialSpecEqual` — compares 18 material symbol-spec fields
- `EEA_IsFiniteDouble` — wraps MQL5 `MathIsValidNumber` for finite-number checks

**Fixed capacities:**
- `EEA_RUNTIME_MAX_SYMBOLS = 32`
- `EEA_RUNTIME_MAX_POSITIONS = 256`
- `EEA_RUNTIME_MAX_ORDERS = 256`
- `EEA_RUNTIME_MAX_DEALS = 2048`

**Purity:** No MT5 account, symbol, position, order, history, file, or trade API appears in `RuntimeEvidence.mqh`. Forbidden tokens include `OrderSend`, `AccountInfo`, `PositionGet`, `FileOpen`, etc.

**Schema:** Consumes `EEA_SCHEMA_VERSION` from `Core/Config.mqh` (currently `"1.0.0"`). The runtime evidence schema version is `"runtime-evidence-v0.1.0"` (distinct from the global config schema).

### Validation order and reason codes

The oracle and MQL implementation validate in this order:

1. Schema version mismatch → `RUNTIME_CHECKPOINT_INCOMPATIBLE`
2. Missing identity (fingerprint, broker server, currency, margin mode) → `ACCOUNT_IDENTITY_UNAVAILABLE`
3. Expired evidence (`now_utc > valid_until_utc`) → `RUNTIME_RECONCILIATION_REQUIRED`
4. Watermark regression (`deal_watermark < previous_watermark`) → `DEAL_WATERMARK_REGRESSED`
5. Duplicate position ticket → `POSITIONS_SOURCE_INCOMPLETE`
6. Duplicate order ticket → `ORDERS_SOURCE_INCOMPLETE`
7. Duplicate deal ticket or descending deal order → `DEALS_SOURCE_INCOMPLETE`
8. Non-finite numeric input → `POSITIONS_SOURCE_INCOMPLETE` / `ORDERS_SOURCE_INCOMPLETE` / `DEALS_SOURCE_INCOMPLETE`
9. Incomplete source flag → `DEGRADED` + corresponding reason
10. Invalid symbol spec (volume_min <= 0, volume_max < volume_min, volume_step <= 0, tick_size <= 0, point <= 0, missing currencies) → `SYMBOL_SPEC_INCOMPLETE`
11. All checks pass → `OBSERVING` / `RUNTIME_EVIDENCE_CURRENT`

**New entries remain blocked** in every state (observer-only increment).

### Fixture coverage

The JSON fixture covers:

- **Base snapshot:** valid empty account with complete source flags, zero rows, nonnegative deal watermark, `observed_at_utc <= valid_until_utc`
- **Degraded cases:** incomplete positions/orders/deals flags
- **Blocked cases:**
  - Missing identity
  - Expired evidence
  - Duplicate position ticket
  - Duplicate order ticket
  - Duplicate deal ticket
  - Descending deal ticket/time
  - Deal watermark regression
  - Invalid symbol volume range (volume_min > volume_max)
  - Invalid symbol volume step (volume_step = 0)
  - Non-finite numeric input (represented as string `"NaN"` in JSON; oracle detects via `math.isfinite`)

### Final verification (after review fixes)

**Command:**
```powershell
python -m unittest discover -s Tests -p 'runtime_evidence_tests.py' -v
```

**Output:**
```
test_complete_empty_account_is_observing ... ok
test_fingerprint_is_32bit_fnv1a ... ok
test_identity_duplicates_and_watermark_regression_block ... ok
test_incomplete_sources_fail_closed ... ok
test_material_symbol_spec_comparison ... ok
test_mql_pure_contract_structure_and_purity ... ok
test_mql_validation_contains_duplicate_and_finite_checks ... ok
test_no_self_hash_comparison_remains ... ok
test_runtime_core_not_included_by_shell_yet ... ok
----------------------------------------------------------------------
Ran 9 tests in 0.002s
OK
```

**Full suite verification:**
```
Ran 120 tests in 0.113s
OK
```

**Evidence:** 120 total tests passing (117 pre-fix + 3 new regression tests for review findings).

### Concerns

- The MQL5 `EEA_RuntimeFingerprint` helper uses FNV-1a 32-bit hash. The oracle does not currently implement this hash; it only validates identity presence. The fingerprint algorithm will be exercised in Task 3 (persistence) when the account adapter serializes the opaque fingerprint.
- The MQL5 `EEA_RuntimeValidate` does not yet implement duplicate-ticket checks or non-finite numeric validation. These will be added when the adapter layer populates the structures. The current test only checks that the MQL file is pure and has the required structure names.

### Fix-round evidence (Task 1 review findings — 2026-09-30)

**Review findings addressed:**

1. **Account fingerprint self-hash removed.** The MQL validator previously called `EEA_RuntimeFingerprint(broker_server, account_fingerprint)` (hashing the fingerprint with itself), which is impossible for pure contracts without raw `account_id`. Fixed: removed self-hash comparison; identity check validates presence only (matching oracle behavior). Fingerprint format corrected to `fnv1a32:...` (not `fnv1a64`).
2. **Full MQL validation parity implemented.** `EEA_RuntimeValidate` now includes: duplicate position/order/deal ticket loops (`for ... j = i + 1`), finite numeric checks (`EEA_IsFiniteDouble` for volume/price fields), chronological deal ordering (`(time_msc, ticket)` tuple comparison), symbol spec finite/positive ranges (`volume_min > 0`, `volume_max >= min`, `volume_step > 0`, `tick_size > 0`, `point > 0`), and currency presence checks. Exact reason codes match oracle (`POSITIONS_SOURCE_INCOMPLETE`, `ORDERS_SOURCE_INCOMPLETE`, `DEALS_SOURCE_INCOMPLETE`, `SYMBOL_SPEC_INCOMPLETE`).
3. **Fixture deal key fixed.** Fixture `blocked_cases[].deals[].ticket` changed to `deal_ticket` (oracle reads `deal_ticket`). Fixture `base_snapshot.observed_at_utc` updated to realistic epoch (`1700000000`); `valid_until_utc` = observed + 7*86400; `history_from_utc` = observed - 7*86400 (`1699395200`).
4. **FNV label corrected to `fnv1a32`.** MQL `StringFormat` uses `fnv1a32:%x`. Python `fnv_oracle.py` added with exact `fnv1a32_hex()` helper and fixed test vector (`fnv1a32:a9a2fef8` for `VTMarkets-Demo|12345678`). Fixture fingerprint updated to `fnv1a32:b96fe430`.
5. **Regression tests strengthened.** Added 3 new regression assertions in `runtime_evidence_tests.py`: `test_mql_validation_contains_duplicate_and_finite_checks` (asserts loops/reason-codes in MQL source), `test_fingerprint_is_32bit_fnv1a`, `test_no_self_hash_comparison_remains`. All 9 runtime tests pass (6 original + 3 regression). Full suite remains at 117+ passing.
6. **Evidence updated.** Implementation report claims corrected: fingerprint validation order, validation completeness, and fixture accuracy documented.

### Resolved concerns

- The MQL validator now implements duplicate-ticket, finite numeric, chronological deal and symbol-spec checks; the earlier concern was resolved in Task 1 fix round.
- A Python FNV-1a 32-bit oracle and fixed vector now cover the fingerprint helper; adapter integration is covered in Task 2.

### Next task

Task 2: Read-only MT5 adapters (account, symbol, reconciliation)

---

## Task 2: Read-only MT5 adapters

**Status:** IMPLEMENTED OFFLINE; compiler/runtime integration remains Task 3/4  
**Date:** 2026-09-30

### Files created

- `Runtime/AccountSnapshotAdapter.mqh`
- `Runtime/SymbolSpecAdapter.mqh`
- `Runtime/BrokerReconciliationAdapter.mqh`

### RED evidence

Command: `python -m unittest Tests/runtime_evidence_tests.py -v`

Initial adapter tests failed because the adapter files were absent. A partial failed worker then left invalid draft sources; a fresh RED run failed `test_account_adapter_never_serializes_account_name` because the draft referenced the prohibited account-name property. The draft also used invalid string access for enum properties and was replaced.

### GREEN evidence

Commands:

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
python -m unittest discover -s Tests -p '*tests.py' -v
```

Results:

```text
Ran 15 tests ... OK
Ran 126 tests ... OK
```

### Implemented boundary

- Account adapter reads only server, opaque login input, currency, margin mode and terminal connectivity. It never reads or stores the account-holder name. Fingerprint input is `server|login|currency|margin_mode` and output is `fnv1a32`.
- Symbol adapter requires explicit canonical and broker symbol arguments and reads material broker properties. Prefix/suffix inference does not resolve a binding.
- Reconciliation adapter reads positions, active orders and a bounded 1–90 day deal window, validates capacity/finite values, sorts deals by `(time_msc, ticket)`, and marks each source complete only after its full read succeeds.
- No broker mutation API was added. Entry permission remains false.

### Remaining evidence

The bounded deal window is not full lifetime lineage and cannot close Phase 3/4 by itself.

---

## Task 3: Atomic persistence and observer coordinator

**Status:** OFFLINE_VERIFIED and MQL_COMPILED  
**Date:** 2026-09-30

### Files created or modified

- `Storage/RuntimeEvidenceStore.mqh`
- `Runtime/ObserverRuntime.mqh`
- `EnterpriseEA.mq5`
- `Tests/runtime_evidence_tests.py`

### TDD evidence

Before implementation, four integration tests produced two failures and one error because the store, coordinator include and transaction handler did not exist. After implementation, a regression test exposed that reconciliation JSON contained counts but not the actual position/order/deal rows. The serializer was extended to include deterministic `positions`, `orders`, and `deals` arrays.

Fresh offline result after the fix:

```text
Runtime evidence tests: 20 passed
Full offline suite: 131 passed
```

The shell now starts only in observer mode, parses explicit one-to-one canonical/broker bindings, refreshes on a timer, marks evidence stale on `OnTradeTransaction`, performs no runtime I/O in `OnTick`, writes four atomic current snapshots, and leaves `EEA_StateCanAllowEntry` false.

---

## Task 4: MT5 compiler and runtime evidence

### Compiler evidence

- Compiler: MetaEditor build 6230
- Output: `artifacts/metaeditor-enterpriseea-build.log`
- Result: `0 errors, 0 warnings`
- Deployed binary: terminal data path `MQL5/Experts/EnterpriseEA/EnterpriseEA.ex5`

Classification: **MQL_COMPILED**.

### Connected terminal evidence before runtime attempt

- Server: VTMarkets-Demo
- Currency: USD
- Account mode: demo, hedging (terminal log)
- Balance/equity: 10000/10000
- Positions: 0
- Pending orders: 0
- Explicit broker binding: `EURUSD -> EURUSD-VIP`; exact `EURUSD` exists but is disabled.

### Runtime observation and restart evidence

After explicit user approval, the normal terminal was closed safely after backing up chart profiles. The dedicated observer-only tester config at `artifacts/enterpriseea-observer-tester.ini` then ran `EnterpriseEA.ex5` on `EURUSD-VIP` M5. Tester build 6230 logged initialization with the exact observer-only inputs and the EA message `EnterpriseEA observer runtime initialized without execution authority.`

Generated evidence under the isolated tester agent:

- `MQL5/Files/EnterpriseEA_Test/current/account_snapshot.json`
- `MQL5/Files/EnterpriseEA_Test/current/symbol_registry.json`
- `MQL5/Files/EnterpriseEA_Test/current/broker_reconciliation.json`
- `MQL5/Files/EnterpriseEA_Test/current/runtime_status.json`
- `MQL5/Files/EnterpriseEA_Test/logs/audit.jsonl`

The runtime status is `OBSERVING/RUNTIME_EVIDENCE_CURRENT` with `new_entries_blocked=true`. The account snapshot records only opaque fingerprint, `VTMarkets-Demo`, USD and `RETAIL_HEDGING`. Symbol evidence matches the broker metadata for `EURUSD-VIP`: 5 digits, point/tick size 0.00001, tick value 1, contract size 100000, volume 0.01–100 step 0.01. Reconciliation is explicitly bounded to seven days and recorded zero positions, zero active orders and one tester deposit deal.

A second tester run succeeded again and performed a fresh refresh. Because the MT5 tester recreates its agent Files sandbox between runs, the runtime-status checkpoint was again reported missing; this proves clean startup/fresh broker reading but does not prove persistent checkpoint survival across separate tester runs. Persistent restart compatibility still requires attachment to a retained terminal Files sandbox.

The normal connected MT5 terminal was restored afterward. Account balance/equity remained 10000/10000, with zero positions and zero pending orders before and after.

### Current evidence classifications

- Existing pure Phase 1–4 prototype modules: **OFFLINE_VERIFIED**.
- Runtime evidence contract/adapters/store/coordinator: **OFFLINE_VERIFIED**, **MQL_COMPILED** (latest full suite: 132/132; latest compile: 0 errors/0 warnings).
- Observer EA in isolated MT5 tester: **RUNTIME_OBSERVED**.
- Seven-day tester account snapshot: **BROKER_RECONCILED_BOUNDED** for the declared tester scope only, not full live/demo account lineage.
- Virtual execution, Strategy Tester trading scenarios, Paper soak and Live: **PAPER_PENDING**.
- Pending order submission/cancellation, Dashboard, News Center, MCP AI runtime and Telegram gateway: **NOT_IMPLEMENTED**.
