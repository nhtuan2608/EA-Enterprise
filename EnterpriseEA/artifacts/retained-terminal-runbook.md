# Retained Terminal Runbook: EnterpriseEA Observer

## Overview
This runbook defines the operational protocol for compiling, deploying, and running the `EnterpriseEA` observer in a connected MetaTrader 5 terminal sandbox without granting trade execution permissions.

## Environment & Prerequisites
- **Terminal:** MetaTrader 5 Build 6230 (64-bit)
- **Broker / Server:** VTMarkets-Demo
- **Account:** Demo (Login: 1223006, Currency: USD, Leverage: 500)
- **Compiler:** MetaEditor 64 (`metaeditor64.exe`)
- **Execution Mode:** Observer-Only (`InpObserverOnly = true`)

## Safety Invariants
1. `InpObserverOnly` must remain `true`. Startup aborts if `false`.
2. No trade execution APIs (`OrderSend`, `OrderSendAsync`, `CTrade`, `OrderDelete`, `PositionClose`, `PositionModify`) exist in any compiled source file.
3. `EEA_StateCanAllowEntry` remains `false` in all states.
4. No credentials, raw account logins, or account holder names are serialized into runtime artifacts.

## Compilation Protocol
1. Open `EnterpriseEA.mq5` in MetaEditor build 6230 or compile via command line:
   ```powershell
   & "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile:"EnterpriseEA.mq5" /log:"metaeditor-build.log"
   ```
2. Verify build log: requires `Result: 0 errors, 0 warnings`.

## Deployment Protocol
1. Copy compiled `EnterpriseEA.ex5` and all MQL5 source/header files (`Core/`, `Market/`, `Risk/`, `Runtime/`, `Storage/`, `Setups/`, `TradeManager/`, `Integration/`) into the terminal data path:
   `C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\EnterpriseEA\`
2. Open MetaTrader 5 terminal and verify EA visibility in Navigator.

## Attachment & Observation Protocol
1. Open a chart for a canonical symbol (e.g. `EURUSD`).
2. Drag `EnterpriseEA` onto the chart.
3. Configure Inputs:
   - `InpObserverOnly = true`
   - `InpCanonicalSymbols = "EURUSD,GBPUSD,XAUUSD,BTCUSD,USDJPY"`
   - `InpShowSymbolPanel = true`
   - `InpRefreshIntervalSeconds = 30`
   - `InpHistoryLookbackDays = 7`
4. Verify the chart selection panel renders discovered broker symbols (`EURUSD-VIP`, `XAUUSD-VIP`, etc.) with correct status (`RESOLVED`).
5. Click **Apply** to commit selection and initiate fresh reconciliation.

## Restart & Checkpoint Verification
1. Allow at least two timer refresh cycles to complete.
2. Inspect `MQL5\Files\EnterpriseEA\` for atomic JSON snapshots (`runtime_status.json`, `symbol_selection.json`, `audit.jsonl`).
3. Restart the terminal normally.
4. Verify checkpoint survival: prior checkpoint is read and checked as `COMPATIBLE` before a fresh broker reconciliation overwrites runtime evidence with a new instance ID and later observation timestamp.

## Limitations & Automation Status
- **Live GUI Attachment:** Automated attachment of EAs to interactive charts in a live running MT5 instance requires manual operator action or profile configuration; unattended GUI chart attachment is recorded as `PENDING`.
- **Timer Soak & External Transactions:** 60-minute soak and external transaction invalidation require active live session observation with external trade events; recorded as `RUNTIME_EVIDENCE_PENDING` without live external trigger.
