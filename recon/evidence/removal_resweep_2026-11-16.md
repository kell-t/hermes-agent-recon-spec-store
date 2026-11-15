# D-05 removal-resweep 2026-11-16 (pass: v0.23.1 evidence re-mine)

Window: 2bd378ed..3b4215785882 (v0.23.0 -> v0.23.1). PR-cited requirements: 61; unique PR cites: 73.

- ancestry-proven via re-mined pr_index (commits live in pin history): 72
- covered by verified_numbers.json allowlist: [99558]
- UNCOVERED cites: []


## Removal-keyword commits in window touching PR-cited requirement anchor files

### agent-turn-loop / Two-layer compaction thresholds
- `agent/context_compressor.py` [936f3465f828] refactor(cli): remove the unused one-shot agent that ran outside the gateway

### cli-surface / Connection cards render on the classic CLI
- `cli.py` [a7b7ac654676] fix(cli): drop a dead config fallback and an import of a name that never existed

### cli-surface / Gateway process management via facade with platform backends
- `hermes_cli/gateway.py` [5a583fb3338f] chore: delete five functions that have no caller

### delegation-orchestration / Child API calls run inline, not on a nested pool
- `agent/chat_completion_helpers.py` [a76df9a17b38] refactor(wire): drop the never-read legacy chat-completions kwargs

### gateway-messaging / Multiplexed gateways serve profiles created after boot
- `gateway/run_turn_prepare.py` [e5ecded22ada] fix(gateway): drop a Telegram topic binding whose target row is gone

### gateway-messaging / Telegram topic and edit routing fidelity
- `plugins/platforms/telegram/telegram_topic_routing.py` [d2011903ccf4] fix(telegram): log when allowed_topics drops a forum topic
- `plugins/platforms/telegram/adapter.py` [007d7e8b50a6] fix(telegram): retired adapters edit and delete through their same-profile replacement (#98228, #143364)
- `plugins/platforms/telegram/adapter.py` [6c93005fe7f8] fix(telegram): replacement adapter resolves inside its own profile
- `plugins/platforms/telegram/adapter.py` [d2011903ccf4] fix(telegram): log when allowed_topics drops a forum topic
- `plugins/platforms/telegram/adapter.py` [7222595b82e0] fix(telegram): streaming drafts and deletes stay out of a chat's flood window
- `plugins/platforms/telegram/adapter.py` [82bdce51ad7b] fix(telegram): /stop and /new drop buffered photos through base's own debounce discard
- `plugins/platforms/telegram/adapter.py` [d742bfddc6e0] fix(telegram): contact cards reach the agent, /stop drops buffered photos, SDK import failures name their cause
- `plugins/platforms/telegram/adapter.py` [713e2274cf26] fix(telegram): a text reply whose anchor answers "reply message not found" drops only the anchor
- `plugins/platforms/telegram/adapter.py` [80903cc65f61] fix(telegram): keep an item's caption when a note replaces its media
- `plugins/platforms/telegram/adapter.py` [6e452f4c1273] fix(gateway): accept HEIC/HEIF/AVIF image documents instead of dropping them
- `plugins/platforms/telegram/adapter.py` [6e554301f70a] refactor(telegram): drop the always-true authorized guard at intake

### profiles-isolation / Legacy custom-home units are adopted
- `hermes_cli/gateway.py` [5a583fb3338f] chore: delete five functions that have no caller

### profiles-isolation / Out-of-turn code binds the owning profile explicitly
- `gateway/run_shutdown.py` [583558a7dc82] refactor(gateway): drop eight unused legacy session dict views

### sessions-state / Finalized sessions reopen only on a real turn
- `tui_gateway/methods_session.py` [9fc5a33631f0] refactor(gateway): llm.oneshot drops schema, redact and parsed again

### sessions-state / One preview-column builder for all session listings
- `hermes_state_common.py` [0a0dab06867e] refactor(state)!: remove the CJK FTS5 tokenizer from core
- `hermes_state_sessions.py` [68dd869df996] fix(state): Desktop Archive retires Bot Chat, reaped rows included

### sessions-state / Session-deleted hooks are process-local
- `hermes_state_sessions.py` [68dd869df996] fix(state): Desktop Archive retires Bot Chat, reaped rows included


Triage candidates with hits: 11 of 61 PR-cited requirements.
