# Control center UI redesign (Dashboard and Settings)

Source: master specification v1.4, section 9 and appendix D.5. Implementation: `Runtime/SymbolSelectionPanel.mqh`; read-only engine facts are published by `EEA_PublishPanelEngineView()` in `EnterpriseEA.mq5`.

## Defects in the previous panel

| Symptom | Root cause | Fix |
| --- | --- | --- |
| A click needed a second click or opened the wrong view | Settings/Dashboard were overlays drawn over the main view; overlay Close/Apply sat on the exact coordinates of the hidden main Settings/Dashboard buttons with the same z-order | One shell plus exactly one view; switching or changing sub-tab deletes the previous view and its hover targets |
| Buttons stayed pressed | `OBJ_BUTTON` latches `OBJPROP_STATE`; only checkboxes were released | Every click releases the button; every render sets the state to false |
| Double-click selected and dragged a control | Buttons and the edit field were selectable | No panel object is selectable |
| Double-click toggled a setting on and back off | Both clicks of a double-click were handled | The repeat click on the same object within 250 ms is ignored |
| Symbol rows appeared over an open Settings/Dashboard view every 30 s | The timer deleted and recreated main-view rows, which drew on top | The shell never draws view content; the timer updates the active view in place |
| Typed GMT+7 time disappeared | Every timer render rewrote the edit text | The text is written only when the field is new or the stored value changed |
| Settings did not visibly react | Settings render had no `ChartRedraw` | Both views redraw at the end of render |
| A removed symbol could not be added back | Rows contained only the live selection | Rows are the configured universe (`InpCanonicalSymbols`) plus the live selection; check marks are kept by canonical name |
| Dragging on the panel panned the chart | Chart mouse scroll stayed active | Chart scrolling is suspended while the pointer is over the panel and restored on leave and on removal |

## Layout

- Shell: header with runtime status chip, execution/live/entries summary and a collapse button; Dashboard and Settings tabs with an active indicator; status bar for action results, which clear after about 10 seconds.
- Dashboard tabs (spec 9.1): Overview (equity, balance, floating, free margin, realized UTC-day P/L, active-risk placeholder, positions/orders, symbols, system status grid, evidence freshness), Market (selected symbols, broker mapping, digits, trade mode, S02 state), Trades (positions, read-only), Risk (committed policy, account figures, why kernel values are unavailable), News and AI (labelled not built; NEWS_UNKNOWN and OFFLINE), Calendar (month grid of realized P/L per UTC day with cash flows excluded, day detail, monthly summary).
- Settings tabs: Risk policy (segmented policy choice, continuation toggles, explicit confirmation), Symbols (paged rows, whole-row toggle, All/None, context-only rows disabled), Authorization (GMT+7 input with UTC preview and validation hint), System (read-only inputs). A shared footer shows pending changes, Discard and Apply. Apply is enabled only with staged changes, at least one tradable symbol and a confirmed policy. The persist, verify, rollback and audit path is unchanged.

## Boundaries

- The panel never sends, modifies or closes orders. Trade actions remain unavailable until the spec 9.2 command queue exists.
- Active risk, FTMO floors and headroom are shown as unavailable until the Risk Kernel publishes them; the panel does not recompute them (TC-026).
- Calendar money mode only; percent and R wait for daily snapshots and the trading-day decision (O-03/O-18).
- The panel is disabled in Strategy Tester and optimization, so its visual check must run on an attached terminal.

## Evidence

- Offline suite: 307 tests, including `ControlCenterInteractionTests`.
- Isolated MetaEditor build of the full EA: 0 errors, 0 warnings (`artifacts/ui-redesign-v2-metaeditor-build.log`).
- Pending: visual check on the attached terminal after deployment with `tools/deploy_target.ps1 -RequireBinaryChanged` and an EA reload; hover hit-testing should be checked on a display with DPI scaling.
