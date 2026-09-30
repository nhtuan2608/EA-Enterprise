# Dry-run candidate gate (offline)

`DryRunCandidateGate.mqh` composes existing pure modules. It is isolated from the EA shell and makes no terminal, broker, or order calls. It evaluates only a caller-supplied bundle; it does not calculate market data, risk policy, portfolio reconciliation, broker quotes, or instrument metadata itself.

## Evaluation order

1. Require exactly one fresh `OK` evidence record for each of SYMBOL, CANDIDATE, LEVELS, ECONOMICS, FTMO, PORTFOLIO and VOLUME. All seven records must share the same run `config_version`, account currency, canonical/broker symbol and server identity. Each has a source version, source snapshot ID, capture time and maximum age. Version, currency, symbol or server mismatch blocks; missing, stale or low-quality evidence returns UNKNOWN.
2. Confirm the explicit resolved symbol and bind its source version and metadata fingerprint to the symbol evidence.
3. Require a nonexpired S02 `TRIGGERED` candidate and bind its ID/config version to candidate evidence. Candidate direction must be exactly BUY/LONG or SELL/SHORT and match economics.
4. Require valid structural levels, exact stop/target agreement with economics inputs, and bind the levels evidence to its configured snapshot ID.
5. Require fresh net economics with target space and execution constraints confirmed. Recompute/check the reward-risk ratio and ensure its input quote volume, losses and gains agree with the cached result.
6. Require a valid FTMO calculation with `SUFFICIENT` headroom, and bind policy version and daily snapshot ID. The account currency is carried by the shared evidence envelope because the FTMO result type has no currency field.
7. Require account-wide portfolio evidence: reconciled account state, external orders included, account mode and limits confirmed, policy headroom linked to the same FTMO result, and positive budget.
8. Require a valid final volume/margin quote and sizing result. The final rounded volume must match economics, final loss quote and margin quote; projected loss must match economics and FTMO stress, stay within sizing/portfolio budgets, and fit after existing portfolio stress.

The ordered reason list stops at the first failing stage, except the initial evidence scan, which can report multiple issues in stage order. UNKNOWN means required evidence/calculation is absent or invalid; BLOCKED means identity/config/source bindings conflict; REJECTED means a present candidate fails a setup/economics/headroom/budget/sizing condition.

The only positive result is `REVIEWABLE_CANDIDATE`. Numeric outputs are populated only on that result; candidate ID is exposed after candidate identity/config have been checked. This status is not entry permission, an order intent, paper/live approval, or a Phase 3 completion claim.

## Evidence limits

The evidence envelope and snapshot IDs are caller attestations, not cryptographic proofs. The gate compares their values to component IDs where those exist and requires explicit expected IDs for levels, portfolio and volume quote bundles where existing component types have no ID field. It cannot establish that the account-wide ledger is truly complete or that a broker quote is current; trusted producers must do that. Any terminal integration must refresh/reconcile on startup, reconnect and before use, then invalidate candidates and recalculate all dependent values after material spec/config changes.

`Tests/Fixtures/dry-run-gate-v0.1.0.json` and `Tests/dry_run_gate_oracle.py` provide synthetic composition cases. The Python oracle does not execute the MQL5 gate. MetaEditor compilation, terminal behavior, account-wide reconciliation and broker-specific paper tests remain unverified.
