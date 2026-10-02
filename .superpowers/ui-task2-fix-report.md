# Observer Panel UI — Important Fix Report

## Scope
Implemented the Important UI corrections against UI commit `248b258`:

- Added actual staged policy selector controls for `FTMO_1_STEP`, `FTMO_2_STEP`, and `BALANCE_BASED_FTMO_V1`.
- Added staged daily/overall continuation ON/OFF controls, GMT+7 input labeling with readable UTC display, and explicit confirmation state.
- Kept Apply display/controller-proposal-only; no UI execution adapter or broker order calls were added.
- Expanded Dashboard with selected-symbol specs (digits/trade mode/freshness), watermarks, risk/headroom summary, live blocking reason, and evidence freshness.
- Main market rows now consume `EEA_ObserverPanelMarketRow` fields and iterate all selected rows without silently dropping the last row; DXY remains context-only.
- Apply status/reason is visible. Selection apply rollback now restores canonical/broker selection, symbol specs, reconciliation snapshot, and selection revision when fresh reconciliation/persistence fails.
- Chart objects are created in the requested `sub_window`; disabled runtime evidence no longer triggers panel refresh with an uninitialized context.

## TDD evidence

1. Added focused static tests for policy controls, dashboard evidence, model-backed market rows, sub-window wiring, and disabled-evidence guards.
2. RED run: focused suite failed with four expected missing-contract failures before implementation.
3. GREEN run: focused `runtime_evidence_tests.py` passed: **44 tests, 0 failures**.
4. Full suite: `python -m unittest discover -s EnterpriseEA/Tests -p '*tests.py' -v` passed: **214 tests, 0 failures**.

## Compile evidence

MetaEditor 64-bit build invocation:

```text
C:\Program Files\MetaTrader 5\metaeditor64.exe /compile:EnterpriseEA\\EnterpriseEA.mq5 /log
```

Compiler log result: **0 errors, 0 warnings**.

## Safety / concerns

- No Paper ledger or Paper/execution calls were added.
- Existing execution adapter remains compile-covered but outside the observer panel event path and disabled by default.
- No retained-terminal GUI/soak/external activity was performed in this fix pass.
- Runtime policy/headroom remains a display/controller proposal; it does not authorize trading.
