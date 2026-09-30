# Remote mode command gate (offline)

`RemoteModeGate.mqh` is an isolated, pure MQL5 prototype for `PAUSE_ENTRIES`, `REQUEST_RESUME`, and `CONFIRM_RESUME`. It does not connect to Telegram, call an AI provider, access MT5 trading APIs, persist a file, or alter the observer-only EA shell. The corresponding fixture and Python oracle check the proposed state transitions and reason codes; they do not execute this MQL5 source.

## Contract and trust boundary

The input is a **trusted internal command**, produced only after the future Telegram gateway has independently verified a private chat, both `chat_id` and `from.id`, the operator allowlist, the bot update, and the bridge-to-EA channel. The boolean attestation fields in the struct and JSON schema are data carried from that trusted adapter; setting them to `true` in an untrusted file is not authentication. Production needs a concrete authenticated IPC protocol and key/storage handling before any command is accepted. The gateway must also persist processed Telegram `update_id` values and its monotonic `gateway_sequence`; Telegram update IDs alone are not a durable local sequence or a complete replay ledger.

The module requires a previously initialized, durable remote-mode state bound to the exact account and config version. Startup with missing or invalid remote-mode persistence must keep entries paused. The module does **not** bootstrap or persist that state. The caller supplies an attested UTC time and fresh safety evidence; the module cannot prove the broker, news, risk or MT5 trade-permission facts itself.

`EEA_EvaluateRemoteModeCommand` copies the current state into `next` and returns `VALIDATED_PENDING_COMMIT` for a valid mutating command. The caller must atomically persist `next`, adopt it, then send an `EA_APPLIED` reply. A failed write means the old state remains authoritative and the reply must say `EA_REJECTED` or `COMMIT_FAILED`. A Telegram gateway ACK must never be labeled applied. An exact replay of the most recently committed command returns `DUPLICATE_IGNORED`; an older gateway sequence, reused last ID, or wrong state version is rejected. Full replay resistance beyond the last command belongs to the durable gateway/EA command journal.

`PAUSE_ENTRIES` sets the operator pause latch and clears any pending resume challenge. It never closes or changes an existing position. `REQUEST_RESUME` keeps entries paused and stores a caller-generated one-time nonce with a maximum 120-second TTL, bound to the private chat and user. `CONFIRM_RESUME` requires that nonce, matching chat/user, unexpired challenge, exact state version, and all seven fresh safety flags. It only proposes clearing the operator pause latch. Even after durable commit, the EA's Risk Kernel, FTMO, news, broker and account-wide gates must still decide whether a new entry is eligible; the terminal's global AutoTrading switch is never changed.

`schemas/remote-command.schema.json` specifies the internal command envelope. `schemas/telegram-ai-request.schema.json` and `schemas/telegram-ai-reply.schema.json` specify the read-only `/ask` transport contract. The Python reply oracle binds request ID, chat, context snapshot, deadline and evidence references. Neither the schema nor the oracle sends a Telegram message. Any AI prose or JSON asking to resume or trade stays a reply and cannot call this remote-mode gate.

## Evidence and remaining work

`Tests/Fixtures/remote-control-v1.0.0.json` is synthetic. `Tests/remote_control_tests.py` covers valid pause, duplicate handling, unauthorized/private-chat failures, stale command and state versions, nonce/user/chat mismatches, safety-gate refusal, and AI reply binding. The checks are offline only.

Before a Paper gate: build and test the authenticated Telegram gateway, allowlist and secret storage, durable update/command journal, nonce generator, atomic remote-mode state store, AI context allowlist, real Telegram delivery/retry, EA adapter, and MT5 permission/reconciliation adapters. Re-run all failure/restart cases on the approved MT5 host. No local MetaEditor compile or broker runtime evidence is available on this machine.
