# MT5 Runtime Evidence Adapter Implementation Plan

> **Kiểm tra ô tick (07/10/2026, bằng cách đối chiếu mã nguồn):** các ô `[x]` được tick sau khi grep mã nguồn và `Tests/` xác nhận tính năng tồn tại (RuntimeEvidence, ba adapter, RuntimeEvidenceStore, ObserverRuntime, `EnterpriseEA.mq5`), `runtime_evidence_tests` hiện đạt, và báo cáo `...-implementation-report.md` ghi bằng chứng RED/GREEN, compile, quan sát runtime. Các bước chạy lại (RED, quét API) tick theo bản ghi đó, không chạy lại. **Chưa xong, để trống:** Task 5 Bước 1 (chưa có test bắt buộc sáu nhãn trạng thái trong báo cáo; các nhãn có trong báo cáo nhưng không có test khoá) và Task 5 Bước 4 (không có bằng chứng về lần review độc lập). Ghi chú: Bước 1 Task 4 ghi snapshot trước khi chạy vào báo cáo thực hiện, không có `artifacts/mt5-runtime-verification.md`; Bước 6 Task 4 chạy trên tester không chứng minh checkpoint sống qua lần chạy, bằng chứng sau này là 3 lần nạp lại EA trên demo 05/10 (checkpoint COMPATIBLE); quét `OrderSend` ở Bước 8 đúng tại thời điểm đó, nay `ExecutionAdapter.mqh` có chủ ý chứa lệnh gửi.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only MT5 runtime evidence adapter that compiles and runs against VTMarkets-Demo, persists account/symbol/order/position/deal observations, reconciles safely after restart, and never enables or executes trading.

**Architecture:** Keep all existing pure/offline modules unchanged and add a narrow runtime boundary under `Runtime/`. MT5 adapters collect broker evidence, pure validation assigns `OBSERVING`/`DEGRADED`/`BLOCKED`, and a storage module writes deterministic JSON snapshots atomically. The EA shell coordinates initialization, timer refresh, and transaction-triggered invalidation while `EEA_StateCanAllowEntry` remains unconditionally false.

**Tech Stack:** MQL5 strict mode, MetaEditor build 6230, Python 3.11 standard-library `unittest`, JSON fixtures, MT5 Files sandbox.

**Spec:** `docs/superpowers/specs/2026-09-30-mt5-runtime-evidence-adapter-design.md`

## Global Constraints

- Observer-only: no `OrderSend`, `OrderSendAsync`, `CTrade`, order modification/deletion, position close, partial close, BE, or trailing operations.
- `InpObserverOnly=false` must refuse startup.
- Terminal/account trade permission never grants EA execution permission.
- `EEA_StateCanAllowEntry` remains false for every state.
- Missing, stale, conflicting, incomplete, or identity-mismatched evidence fails closed.
- Persist no raw account login, account-holder name, credentials, tokens, or provider secrets.
- Stored snapshots are not broker truth; startup always performs a fresh MT5 read.
- Writes use same-directory temporary replacement via `EEA_WriteAtomicText`.
- Telegram remains paused.
- Target compile/runtime environment is MetaTrader 5 build 6230 and VTMarkets-Demo.
- No Paper/Live readiness claim follows from this increment.
- The project directory is not a Git repository; replace each Commit step with recording changed files in the implementation report unless the user explicitly initializes Git.

## File structure

- `Runtime/RuntimeEvidence.mqh`: pure runtime evidence structures, defaults, validation, state transition, material symbol-spec comparison.
- `Runtime/AccountSnapshotAdapter.mqh`: read account/terminal identity into the pure account structure.
- `Runtime/SymbolSpecAdapter.mqh`: read explicit canonical/broker bindings and material broker specifications.
- `Runtime/BrokerReconciliationAdapter.mqh`: enumerate positions, active orders, and bounded deal history read-only.
- `Runtime/ObserverRuntime.mqh`: coordinate refresh, staleness, audit, timer behavior, and current status.
- `Storage/RuntimeEvidenceStore.mqh`: deterministic JSON serialization, atomic snapshot writes, narrow checkpoint compatibility check.
- `Tests/runtime_evidence_oracle.py`: Python reference validator/state reducer for test fixtures.
- `Tests/runtime_evidence_tests.py`: behavioral and static-boundary tests.
- `Tests/Fixtures/runtime-evidence-v0.1.0.json`: valid and invalid synthetic evidence.
- `EnterpriseEA.mq5`: include and delegate to observer runtime; install/remove timer; transaction invalidation.
- `README.md`, `OFFLINE_WORKFLOW.md`, `PHASE3_TRACEABILITY.md`, `PHASE4_TRACEABILITY.md`: evidence-status updates after verification.

---

### Task 1: Pure runtime evidence contract

**Files:**
- Create: `Tests/Fixtures/runtime-evidence-v0.1.0.json`
- Create: `Tests/runtime_evidence_oracle.py`
- Create: `Tests/runtime_evidence_tests.py`
- Create: `Runtime/RuntimeEvidence.mqh`

**Interfaces:**
- Consumes: `EEA_SCHEMA_VERSION` from `Core/Config.mqh`; finite-number behavior from MQL5 `MathIsValidNumber`.
- Produces: `EEA_RuntimeAccountSnapshot`, `EEA_RuntimeSymbolSpec`, `EEA_RuntimePositionRow`, `EEA_RuntimeOrderRow`, `EEA_RuntimeDealRow`, `EEA_RuntimeReconciliationSnapshot`, `EEA_RuntimeStatus`; `EEA_RuntimeDefaults`, `EEA_RuntimeValidate`, and `EEA_RuntimeMaterialSpecEqual`.

- [x] **Step 1: Create fixture with exact valid and invalid cases**

Create a JSON fixture whose base snapshot contains schema/config version, opaque account fingerprint, `VTMarkets-Demo`, USD currency, `HEDGING`, complete source flags, zero rows, a nonnegative deal watermark, and `observed_at_utc <= valid_until_utc`. Invalid cases must mutate exactly one of: missing identity, expired evidence, incomplete positions/orders/deals, duplicate position ticket, duplicate order ticket, duplicate or descending deal ticket/time, regressed deal watermark, invalid symbol volume range/step, and non-finite numeric input represented by an oracle override rather than invalid JSON.

- [x] **Step 2: Write failing pure-contract tests**

```python
class RuntimeEvidenceContractTests(unittest.TestCase):
    def test_complete_empty_account_is_observing(self):
        status = evaluate(FIXTURE["base_snapshot"], now_utc=FIXTURE["base_snapshot"]["observed_at_utc"])
        self.assertEqual(status["runtime_state"], "OBSERVING")
        self.assertEqual(status["reason_code"], "RUNTIME_EVIDENCE_CURRENT")
        self.assertTrue(status["new_entries_blocked"])

    def test_incomplete_sources_fail_closed(self):
        for field, reason in (
            ("positions_complete", "POSITIONS_SOURCE_INCOMPLETE"),
            ("orders_complete", "ORDERS_SOURCE_INCOMPLETE"),
            ("deals_complete", "DEALS_SOURCE_INCOMPLETE"),
        ):
            snapshot = deepcopy(FIXTURE["base_snapshot"])
            snapshot[field] = False
            status = evaluate(snapshot, now_utc=snapshot["observed_at_utc"])
            self.assertEqual(status["runtime_state"], "DEGRADED")
            self.assertEqual(status["reason_code"], reason)
            self.assertTrue(status["new_entries_blocked"])

    def test_identity_duplicates_and_watermark_regression_block(self):
        for case in FIXTURE["blocked_cases"]:
            with self.subTest(name=case["name"]):
                snapshot = deepcopy(FIXTURE["base_snapshot"])
                snapshot.update(case.get("snapshot_overrides", {}))
                snapshot["positions"] = case.get("positions", snapshot["positions"])
                snapshot["orders"] = case.get("orders", snapshot["orders"])
                snapshot["deals"] = case.get("deals", snapshot["deals"])
                status = evaluate(snapshot, now_utc=snapshot["observed_at_utc"],
                                  previous_watermark=case.get("previous_watermark", -1))
                self.assertEqual(status["runtime_state"], "BLOCKED")
                self.assertEqual(status["reason_code"], case["expected_reason"])
                self.assertTrue(status["new_entries_blocked"])

    def test_material_symbol_spec_comparison(self):
        self.assertTrue(material_spec_equal(FIXTURE["symbol_spec"], deepcopy(FIXTURE["symbol_spec"])))
        changed = deepcopy(FIXTURE["symbol_spec"])
        changed["volume_step"] = 0.1
        self.assertFalse(material_spec_equal(FIXTURE["symbol_spec"], changed))
```

Replace the illustrative ellipsis before saving the test with a concrete loop over `FIXTURE["blocked_cases"]`; the committed test file must contain no placeholder.

- [x] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
```

Expected: import failure for `runtime_evidence_oracle` or missing `Runtime/RuntimeEvidence.mqh`, proving the new contract is absent.

- [x] **Step 4: Implement the Python oracle minimally**

Implement:

```python
def evaluate(snapshot: dict, now_utc: int, previous_watermark: int = -1) -> dict:
    result = {"runtime_state": "BLOCKED", "reason_code": "RUNTIME_RECONCILIATION_REQUIRED",
              "new_entries_blocked": True}
    # Validate identity/version first, then freshness, source flags, symbol specs,
    # unique position/order/deal identities, chronological deals, and watermark.
    # Return OBSERVING only when every declared source is complete and valid.
    return result


def material_spec_equal(left: dict, right: dict) -> bool:
    fields = ("broker_symbol", "digits", "point", "tick_size", "tick_value",
              "contract_size", "volume_min", "volume_max", "volume_step",
              "stops_level_points", "freeze_level_points", "trade_mode",
              "order_mode", "expiration_mode", "calculation_mode",
              "base_currency", "profit_currency", "margin_currency")
    return all(left.get(name) == right.get(name) for name in fields)
```

- [x] **Step 5: Implement the MQL pure contract**

Define fixed-capacity arrays sized for the observer increment (`EEA_RUNTIME_MAX_SYMBOLS=32`, `EEA_RUNTIME_MAX_POSITIONS=256`, `EEA_RUNTIME_MAX_ORDERS=256`, `EEA_RUNTIME_MAX_DEALS=2048`) and explicit counts. Validation order and reason codes must match the oracle. `EEA_RuntimeDefaults` sets `runtime_state="BLOCKED"`, `reason_code="RUNTIME_RECONCILIATION_REQUIRED"`, and `new_entries_blocked=true`. No MT5 account, symbol, position, order, history, file, or trade API appears in this file.

- [x] **Step 6: Run the targeted and full offline suites**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
python -m unittest discover -s Tests -p '*tests.py' -v
```

Expected: targeted tests pass; full count is greater than 111 with zero failures.

- [x] **Step 7: Record Task 1 changes**

Because Git is unavailable, append exact created paths and test commands/results to `docs/superpowers/plans/2026-09-30-mt5-runtime-evidence-adapter-implementation-report.md`.

---

### Task 2: Read-only MT5 adapters

**Files:**
- Create: `Runtime/AccountSnapshotAdapter.mqh`
- Create: `Runtime/SymbolSpecAdapter.mqh`
- Create: `Runtime/BrokerReconciliationAdapter.mqh`
- Modify: `Tests/runtime_evidence_tests.py`

**Interfaces:**
- Consumes: Task 1 structures and validation; MT5 `AccountInfo*`, `TerminalInfo*`, `SymbolInfo*`, `PositionsTotal`, `PositionGet*`, `OrdersTotal`, `OrderGet*`, `HistorySelect`, `HistoryDealsTotal`, and `HistoryDealGet*` read APIs.
- Produces: `EEA_ReadRuntimeAccount`, `EEA_ReadRuntimeSymbolSpec`, `EEA_ReadRuntimeReconciliation`; none can mutate broker state.

- [x] **Step 1: Add failing static-boundary tests**

```python
def test_runtime_adapters_are_read_only(self):
    allowed_reads = ("AccountInfo", "TerminalInfo", "SymbolInfo", "PositionGet",
                     "OrderGet", "HistorySelect", "HistoryDealGet")
    forbidden = ("OrderSend", "OrderSendAsync", "CTrade", ".Buy(", ".Sell(",
                 "PositionClose", "PositionModify", "OrderDelete")
    sources = [ROOT / "Runtime/AccountSnapshotAdapter.mqh",
               ROOT / "Runtime/SymbolSpecAdapter.mqh",
               ROOT / "Runtime/BrokerReconciliationAdapter.mqh"]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    self.assertTrue(any(token in combined for token in allowed_reads))
    for token in forbidden:
        self.assertNotIn(token, combined)
```

Add exact tests asserting the account adapter source never serializes `ACCOUNT_NAME` and that symbol resolution requires caller-provided canonical and broker symbols.

- [x] **Step 2: Run targeted tests and verify RED**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
```

Expected: missing adapter files.

- [x] **Step 3: Implement account adapter**

`EEA_ReadRuntimeAccount(snapshot, reason)` reads server, currency, margin mode, terminal connected state, and trade-permission observations. Build an opaque local fingerprint with a deterministic FNV-1a-style hash over `server|login|currency|margin_mode`; only the hash is stored in the structure. Reject empty server/currency, nonpositive login, unsupported margin mode, or disconnected terminal with explicit reason. Do not read or persist `ACCOUNT_NAME`.

- [x] **Step 4: Implement symbol adapter**

`EEA_ReadRuntimeSymbolSpec(canonical, broker_symbol, account_server, spec, reason)` requires nonempty explicit names, selects/reads the broker symbol, and fills every material field named in the spec. Validate `volume_min > 0`, `volume_max >= volume_min`, `volume_step > 0`, `tick_size > 0`, `point > 0`, nonnegative stop/freeze levels, and nonempty currency identities. The function may report discovered prefix/suffix matches through a separate suggestion helper but may not mark them resolved.

- [x] **Step 5: Implement broker reconciliation adapter**

`EEA_ReadRuntimeReconciliation(account, lookback_days, snapshot, reason)`:

1. rejects lookback outside `1..90`;
2. captures `TimeGMT()` once as observation time;
3. enumerates all positions and active orders into fixed arrays, rejecting capacity overflow and unreadable rows;
4. selects history from `observed_at_utc - lookback_days*86400` through observation time;
5. enumerates deals, recording ticket, order ticket, position ID, event time, type, entry, symbol, volume, price, profit, commission, swap, fee;
6. sorts or validates deterministic ascending `(time_msc, ticket)` order;
7. sets each completeness flag only after its full loop succeeds;
8. records maximum deal ticket/time as bounded watermark evidence.

- [x] **Step 6: Run targeted and full suites**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
python -m unittest discover -s Tests -p '*tests.py' -v
```

Expected: all tests pass and forbidden API scan stays clean.

- [x] **Step 7: Record Task 2 changes**

Append paths and fresh test output summary to the implementation report.

---

### Task 3: Atomic runtime persistence and coordinator integration

**Files:**
- Create: `Storage/RuntimeEvidenceStore.mqh`
- Create: `Runtime/ObserverRuntime.mqh`
- Modify: `EnterpriseEA.mq5`
- Modify: `Tests/runtime_evidence_tests.py`

**Interfaces:**
- Consumes: Task 1 validation, Task 2 adapters, `EEA_WriteAtomicText`, `CAuditLog`, `EEAEvent`.
- Produces: `EEA_ObserverRuntimeInit`, `EEA_ObserverRuntimeRefresh`, `EEA_ObserverRuntimeMarkStale`, `EEA_ObserverRuntimeShutdown`, plus four current JSON documents.

- [x] **Step 1: Add failing persistence and shell-integration tests**

```python
def test_store_uses_atomic_writer_and_redacts_identity(self):
    source = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
    self.assertIn("EEA_WriteAtomicText", source)
    self.assertNotIn("ACCOUNT_LOGIN", source)
    self.assertNotIn("ACCOUNT_NAME", source)
    self.assertIn("account_fingerprint", source)


def test_shell_integrates_observer_without_execution(self):
    shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
    self.assertIn('Runtime/ObserverRuntime.mqh', shell)
    self.assertIn("EventSetTimer", shell)
    self.assertIn("OnTradeTransaction", shell)
    self.assertIn("EEA_ObserverRuntimeMarkStale", shell)
    self.assertIn("EEA_StateCanAllowEntry", (ROOT / "Core/State.mqh").read_text(encoding="utf-8"))
    for token in FORBIDDEN_EXECUTION_TOKENS:
        self.assertNotIn(token, all_project_mql_source())
```

Also assert `OnTick` contains no refresh/file/history call, and `OnDeinit` calls `EventKillTimer`.

- [x] **Step 2: Run targeted tests and verify RED**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
```

Expected: missing store/coordinator and missing shell integration.

- [x] **Step 3: Implement deterministic serializers and checkpoint check**

`RuntimeEvidenceStore.mqh` serializes account, symbol registry, reconciliation, and status documents with JSON escaping through `EEA_JsonEscape` and UTC formatting through `EEA_IsoUtc`. Implement:

```mql5
bool EEA_RuntimeStoreWriteAccount(const string root,const EEA_RuntimeAccountSnapshot &account);
bool EEA_RuntimeStoreWriteSymbols(const string root,const EEA_RuntimeSymbolSpec &symbols[],const int count);
bool EEA_RuntimeStoreWriteReconciliation(const string root,const EEA_RuntimeReconciliationSnapshot &snapshot);
bool EEA_RuntimeStoreWriteStatus(const string root,const EEA_RuntimeStatus &status);
EEAStateLoadResult EEA_RuntimeStoreCheckStatus(const string path,const string config_version,
                                               const string account_fingerprint);
```

The compatibility check requires document version, config version, and account fingerprint markers but never promotes stored evidence to current.

- [x] **Step 4: Implement observer coordinator**

Define `EEA_ObserverRuntimeContext` containing current account, symbol array/count, reconciliation snapshot, status, stale flag, refresh interval, history lookback, root, and config version. Initialization receives explicit canonical/broker arrays parsed by the shell, performs a fresh refresh regardless of checkpoint result, persists all documents, and audits the checkpoint result. Refresh failure persists/audits `DEGRADED` or `BLOCKED` if possible. A persistence failure sets `BLOCKED/RUNTIME_PERSISTENCE_FAILED`.

- [x] **Step 5: Integrate the EA shell**

Add inputs:

```mql5
input bool   InpRuntimeEvidenceEnabled = true;
input int    InpRuntimeRefreshSeconds  = 30;
input int    InpHistoryLookbackDays    = 7;
input string InpCanonicalSymbols       = "EURUSD";
input string InpBrokerSymbols          = "EURUSD";
```

Parse one-to-one comma-separated bindings, reject empty/mismatched arrays, initialize observer runtime after audit opens, and call `EventSetTimer`. `OnTimer` invokes refresh only when due/stale. Add the exact MQL event signature:

```mql5
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   EEA_ObserverRuntimeMarkStale(g_runtime,"BROKER_TRANSACTION_OBSERVED");
  }
```

The handler ignores request/result content and performs no broker mutation. `OnDeinit` kills the timer and shuts down runtime before closing audit. `OnTick` remains empty of scanning/history/file writes.

- [x] **Step 6: Run targeted and full offline tests**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
python -m unittest discover -s Tests -p '*tests.py' -v
```

Expected: all tests pass and count remains above 111.

- [x] **Step 7: Record Task 3 changes**

Append paths and test evidence to the implementation report.

---

### Task 4: Compile, deploy, and verify MT5 observer runtime

**Files:**
- Create/update outside source tree only as deployment copies: terminal data path `MQL5/Experts/EnterpriseEA/**`
- Create: `artifacts/metaeditor-enterpriseea-build.log`
- Create: `artifacts/mt5-runtime-verification.md`
- Modify: implementation report

**Interfaces:**
- Consumes: completed source tree and installed MetaEditor/MT5.
- Produces: compiler log, deployed EX5, runtime JSON/audit evidence, before/after account/order/position comparison.

- [x] **Step 1: Capture the pre-run broker snapshot**

Use the MT5 status/account/positions/pending-order tools and record timestamp, account server/currency/mode, balance/equity, position tickets/count, and pending order tickets/count in `artifacts/mt5-runtime-verification.md`. Do not place or cancel anything.

- [x] **Step 2: Deploy source tree to the terminal data path**

Copy `EnterpriseEA.mq5` and its required `Core`, `Storage`, and `Runtime` include files into:

```text
C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\EnterpriseEA\
```

Keep the project source authoritative; deployment is a reproducible copy.

- [x] **Step 3: Compile with MetaEditor build 6230**

Run:

```powershell
& 'C:\Program Files\MetaTrader 5\metaeditor64.exe' `
  /compile:'<terminal-data-path>\MQL5\Experts\EnterpriseEA\EnterpriseEA.mq5' `
  /log:'D:\Work\Private\Trading\ea\ea\EnterpriseEA\artifacts\metaeditor-enterpriseea-build.log'
```

Inspect the log. Required: `0 errors`. Review every warning; fix and recompile any unsafe warning.

- [x] **Step 4: Run the observer EA without trading side effects**

Attach/run the compiled EA on a VTMarkets-Demo chart with `InpObserverOnly=true`, runtime evidence enabled, a 30-second refresh, 7-day history, and an explicit broker symbol that exists. If GUI attachment cannot be automated safely, use the existing terminal configuration/profile mechanism only if it does not alter unrelated charts; otherwise record runtime attachment as pending rather than claiming it.

- [x] **Step 5: Inspect runtime files**

Verify the four `current/*.json` files and `logs/audit.jsonl` parse, carry current schema/config/account fingerprint, declare the bounded history window, and contain no raw login/name. Check that runtime state and reason accurately reflect evidence completeness.

- [x] **Step 6: Verify restart behavior**

Restart/reinitialize the EA once in observer mode. Confirm a fresh broker observation timestamp and audit event, compatible checkpoint handling, unchanged account/order/position state, and no duplicate side effect.

- [x] **Step 7: Capture the post-run broker snapshot**

Repeat MT5 account/positions/pending-order reads. Compare ticket sets/counts and balance. Required: the observer created, modified, or cancelled no order/position and caused no balance change.

- [x] **Step 8: Run final verification commands**

```powershell
python -m unittest discover -s Tests -p '*tests.py' -v
Select-String -Path (Get-ChildItem -Recurse -Include *.mq5,*.mqh).FullName `
  -Pattern 'OrderSend|OrderSendAsync|CTrade|PositionClose|PositionModify|OrderDelete'
```

Expected: all tests pass; forbidden execution search returns no executable integration path (comments/test literals must be reviewed explicitly).

- [x] **Step 9: Record Task 4 evidence**

Update the implementation report with compiler result, runtime artifact paths, exact before/after comparison, constraints encountered, and classification achieved.

---

### Task 5: Update traceability and perform final review

**Files:**
- Modify: `README.md`
- Modify: `OFFLINE_WORKFLOW.md`
- Modify: `PHASE3_TRACEABILITY.md`
- Modify: `PHASE4_TRACEABILITY.md`
- Modify: `docs/superpowers/plans/2026-09-30-mt5-runtime-evidence-adapter-implementation-report.md`

**Interfaces:**
- Consumes: verified test, compile, and runtime evidence from Tasks 1–4.
- Produces: an accurate evidence matrix with no inflated Phase-completion claim.

- [ ] **Step 1: Add a failing documentation-status test**

Add a test to `Tests/runtime_evidence_tests.py` requiring each of the six exact labels to appear in the implementation report:

```python
for label in ("OFFLINE_VERIFIED", "MQL_COMPILED", "RUNTIME_OBSERVED",
              "BROKER_RECONCILED_BOUNDED", "PAPER_EXCLUDED_PERMANENTLY", "NOT_IMPLEMENTED"):
    self.assertIn(label, report)
```

Run the targeted test and verify it fails before documentation is updated.

- [x] **Step 2: Update project documentation from actual evidence only**

Record:

- which pre-existing modules remain `OFFLINE_VERIFIED` only;
- which files were included in a successful compile;
- whether runtime attachment and artifacts prove `RUNTIME_OBSERVED`;
- that the bounded history snapshot is not complete lifetime lineage;
- that pending execution/cancellation, Strategy Tester trading, Paper soak, dashboard, news, MCP AI runtime, and Telegram gateway remain pending/not implemented.

Do not mark Phase 3 or Phase 4 complete unless every existing gate in their traceability tables has evidence.

- [x] **Step 3: Run targeted and full tests**

```powershell
python -m unittest Tests/runtime_evidence_tests.py -v
python -m unittest discover -s Tests -p '*tests.py' -v
```

Expected: all tests pass.

- [ ] **Step 4: Request an independent code review**

Provide the reviewer the spec, this plan, implementation report, complete changed-file list, compiler log, runtime verification artifact, and full test output. Require separate verdicts for spec compliance, safety boundary, code quality, test quality, and accuracy of evidence claims. Fix all Critical/Important findings and re-run affected verification.

- [x] **Step 5: Run final fresh verification**

Re-run the full Python suite, MetaEditor compile, forbidden execution scan, JSON parse checks, and MT5 before/after position/order/account checks. Record exact outputs in the implementation report.

- [x] **Step 6: Record final status**

List all changed source/document paths, evidence achieved, remaining gaps, and any rulings. Because no Git repository exists, do not claim a commit, branch, merge, or clean working tree.
