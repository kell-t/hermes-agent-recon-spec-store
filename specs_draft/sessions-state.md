# Capability: sessions-state

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Summary
Session persistence for every Hermes surface: the `SessionDB` facade `hermes_state.py` plus ~60 `hermes_state_<topic>.py` siblings own session metadata, message history, model config, and FTS5 search in a single SQLite store. Contracts include WAL concurrency, compression session-split chains, live-turn mutation guards, prune/repair/reconcile behavior, and error taxonomy that remote surfaces map to HTTP statuses.

## Primary code locations
- `hermes_state.py` — SessionDB facade (module docstring states the core contract)
- `hermes_state_schema.py`, `hermes_state_wal.py`, `hermes_state_dbfile.py` — schema and file/locking layer
- `hermes_state_mutations.py` + `hermes_state_mutation_*.py` — guarded write paths
- `hermes_state_prune_rewrite.py`, `hermes_state_repair.py`, `hermes_state_reconcile.py`, `hermes_state_maintenance.py` — integrity paths
- `hermes_state_fts.py`, `hermes_state_search.py` — search; `hermes_state_session_list.py` — listings; `hermes_state_media.py` — tool-result spillover

## Requirements

### Requirement: SQLite store with WAL concurrency model
The state store SHALL be a SQLite database in WAL mode giving concurrent readers and a single writer, storing session metadata, message history and model config with FTS5 search; sessions SHALL be source-tagged by originating surface (`cli`, `telegram`, ...).
- Status: VERIFIED
- Evidence: doc: hermes_state.py module docstring (lines 1-5); doc: website/docs/developer-guide/ (session-storage long-form referenced by agent/AGENTS.md)
- Anchor: `hermes_state_wal.py:62` (`_on_disk_journal_mode`), `hermes_state_wal.py:58`

### Requirement: Compression splits sessions via parent chains
Compaction that rotates a session SHALL express the split as a `parent_session_id` chain rather than destroying history; delegated-child lineage rides `model_config.$._delegate_from` against the same chain.
- Status: VERIFIED
- Evidence: doc: hermes_state.py module docstring ("compression splits sessions via parent_session_id chains")
- Anchor: `hermes_state_schema.py:1066` (`'$._delegate_from', parent_session_id` migration/backfill)

### Requirement: Live-turn mutation guard
The store SHALL refuse to delete or rewrite a session row whose lease a live turn still owns, and SHALL heal a session row deleted underneath a live agent.
- Status: VERIFIED
- Evidence: [PR #123583](https://github.com/NousResearch/hermes-agent/pull/123583) — "refuse to delete a session row a live turn still owns" and "heal a session row deleted under a live agent"
- Anchor: `hermes_state_mutation_guards.py:6` (require_idle transcript-guard raises on live turn lease)

### Requirement: In-place prune rewrites only changed rows
Proactive pruning SHALL rewrite only the rows whose content actually changed, in place, holding live-owned rows out of the rewrite set.
- Status: VERIFIED
- Evidence: [PR #124273](https://github.com/NousResearch/hermes-agent/pull/124273) — "proactive prune rewrites only the changed rows, in place"
- Anchor: `hermes_state_prune_rewrite.py:133` (`rewrite_pruned_rows`), `hermes_state_prune_rewrite.py:29` (`rewritten_held_row_ids`)

### Requirement: Busy-vs-gone error taxonomy for remote surfaces
Store errors SHALL distinguish "BUSY, not gone" (retryable, mapped to HTTP 503) from hard failures (500) in one shared classifier so surfaces cannot drift apart in their mapping.
- Status: VERIFIED
- Evidence: [PR #140315](https://github.com/NousResearch/hermes-agent/pull/140315) — "catch a lagging state.db up once on browse instead of 503"
- Anchor: `hermes_state_errors.py:30` ("Store BUSY, not gone — HTTP callers map these to 503"), `hermes_state_errors.py:67` (503-vs-500 split cannot drift apart), `hermes_state_reconcile.py:107` (oversized-store catch-up refused with retryable 503)

### Requirement: Locked-store resilience under gateway load
Lock contention SHALL NOT surface as crashes of `hermes sessions list` or dashboard 503s under a busy gateway (dedicated read pooling / lock guarding around the single-writer model).
- Status: INFERRED
- Evidence: doc: hermes_state.py:197 comment ("database is locked ... under a busy gateway"); siblings `hermes_state_readpool.py`, `hermes_state_lockguard.py`, `hermes_state_lockowners.py` exist for this purpose (not opened)
- Anchor: not located (line-level)

### Requirement: FTS5 search with CJK-aware tokenizer option
Message search SHALL be served by FTS5; a loadable CJK tokenizer (`cjk_unicode61`) re-emitting CJK runs MAY be installed, and the search layer SHALL cope with the table existing only sometimes.
- Status: VERIFIED
- Evidence: doc: hermes_state_fts.py header comments; PR-ref evidence not needed — in-repo doc is the normative source here
- Anchor: `hermes_state_fts.py:23` (cjk_unicode61 note), `hermes_state_fts.py:26` (table exists ONLY when ...)

### Requirement: Tool-result spillover archives die with their session
Retiring/deleting sessions SHALL record and retire the tool-result spillover archives their messages point at (prefix `gateway.spillover.retired.v1.`), tying spillover lifetime to the owning session.
- Status: VERIFIED
- Evidence: [PR #126351](https://github.com/NousResearch/hermes-agent/pull/126351) — "tie spillover archive lifetime to the owning session"
- Anchor: `hermes_state_media.py:8` (`SPILLOVER_PREFIX`), `hermes_state_media.py:21` (`retire_spillover`)

### Requirement: One preview-column builder for all session listings
Session listings SHALL share one preview-column builder so every surface shows identical previews, and listing subqueries SHALL stay on the messages-session index even under stale planner stats.
- Status: INFERRED
- Evidence: [PR #119403](https://github.com/NousResearch/hermes-agent/pull/119403) — "one preview-column builder, pinned at every session listing"; "session-list subqueries stay on idx_messages_session under stale planner stats"
- Anchor: `hermes_state_session_list.py` (file exists; specific lines not opened)

### Requirement: Rebuilt follow-up turns reproduce multimodal content
Follow-up turns reconstructed from the session DB SHALL reproduce attached media (a rebuilt turn must show the user's image again), i.e. persistence is lossless for model-visible content.
- Status: INFERRED
- Evidence: [PR #136216](https://github.com/NousResearch/hermes-agent/pull/136216) — "follow-up turns rebuilt from the session DB see the user's image again"
- Anchor: not located (`hermes_state_messages.py`/`hermes_state_media.py` likely)

### Requirement: Session-deleted hooks are process-local
`on_session_delete` hook delivery SHALL be documented as process-local, not cross-process.
- Status: INFERRED
- Evidence: [PR #124988](https://github.com/NousResearch/hermes-agent/pull/124988) — "docs(hooks): note on_session_delete delivery is process-local, not cross-process"
- Anchor: not located

### Requirement: Finalized sessions reopen only on a real turn
Mounting/attaching to a finalized session SHALL NOT reopen its row for display; the first real turn does. Resume-guard proofs rest on the history read, not the reopen.
- Status: INFERRED
- Evidence: [PR #85303](https://github.com/NousResearch/hermes-agent/pull/85303) — "mounting a finalized session no longer reopens its row — the first real turn does"; "the resume guard fail-open proof is the history read, not the reopen"
- Anchor: not located (`tui_gateway` boundary — drafted here because the contract is a state-row lifecycle rule)

### Requirement: One turn's rows bind to one session across rotation
Rows written during a single turn (submit row, model-switch markers, pivot rows) SHALL be addressed to the session the turn will write, surviving session rotation; superseded model-switch markers SHALL not replay.
- Status: INFERRED
- Evidence: [PR #123545](https://github.com/NousResearch/hermes-agent/pull/123545) — "record the submit row's session, address every writer by it"; "pin one turn's rows to one session across a rotation"; "keep superseded model-switch markers from replaying"
- Anchor: not located

## Known gaps / open questions
- Read-pool / lock-guard implementation (`hermes_state_readpool.py`, `hermes_state_lockguard.py`) not opened — the exact reader-pool contract (pool size, staleness bound) is UNVERIFIED.
- `hermes_state_compression.py` / `hermes_state_compaction_display.py` boundary with agent-turn-loop capability: drafted the split-chain contract here, the compaction algorithm belongs to agent-turn-loop — ownership note for pass 2.
- Memory-system (cross-session memory, `plugins/memory/`) is deferred scope; several bundle PRs (memory provider session-end extraction) were rejected as misfiled here.
- Desktop-owned session behaviors (pin/unpin #142672, composer routing #141583) excluded — desktop-ui capability should own them.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05 (tail without refs).
