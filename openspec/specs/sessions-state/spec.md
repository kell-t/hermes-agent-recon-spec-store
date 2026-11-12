# Capability: sessions-state

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (scenario grounding) applied 2026-11-08.

## Purpose
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
**Status**: VERIFIED
**Evidence**: doc: hermes_state.py module docstring (lines 1-5); doc: website/docs/developer-guide/ (session-storage long-form referenced by agent/AGENTS.md)
**Anchor**: `hermes_state_wal.py:62` (`_on_disk_journal_mode`), `hermes_state_wal.py:58`

#### Scenario: WAL store serves readers alongside one writer
- **WHEN** the state store is opened
- **THEN** it runs in WAL mode — concurrent readers and one writer — holding session metadata, message history and model config, with sessions source-tagged (`'cli'`, `'telegram'`, ...)
- Source: doc: hermes_state.py module docstring — "WAL mode (concurrent readers + one writer); compression splits sessions via parent_session_id chains; sessions are source-tagged ('cli', 'telegram', ...)"

#### Scenario: Invalid journal-mode config falls back to WAL
- **WHEN** the configured journal mode is invalid or the database config section is malformed
- **THEN** the store falls back to WAL instead of failing or silently using another mode
- Source: test: tests/hermes_state/test_journal_mode_config.py::test_invalid_config_value_falls_back_to_wal; ::test_apply_wal_with_fallback_defaults_to_wal

### Requirement: Compression splits sessions via parent chains
Compaction that rotates a session SHALL express the split as a `parent_session_id` chain rather than destroying history; delegated-child lineage rides `model_config.$._delegate_from` against the same chain.
**Status**: VERIFIED
**Evidence**: doc: hermes_state.py module docstring ("compression splits sessions via parent_session_id chains")
**Anchor**: `hermes_state_schema.py:1066` (`'$._delegate_from', parent_session_id` migration/backfill)

#### Scenario: Compression rotation splits via a parent chain
- **WHEN** compression rotates a session
- **THEN** the split is expressed as a `parent_session_id` chain rather than destroying history
- Source: doc: hermes_state.py module docstring — "compression splits sessions via parent_session_id chains"

#### Scenario: In-place compaction creates no chain
- **WHEN** compaction runs in place (the default)
- **THEN** there is no `parent_session_id` chain and no `name #N` renumbering — one conversation keeps one durable id
- Source: doc: website/docs/developer-guide/context-compression-and-caching.md — "There is no `parent_session_id` chain and no `name #N` renumbering; one conversation keeps one durable id for its whole life."

#### Scenario: Deleting a chain tip removes the whole chain
- **WHEN** the projected tip row of a compressed conversation is deleted
- **THEN** the whole chain is removed, so the deleted conversation does not reappear in the next listing
- Source: test: tests/hermes_state/test_delete_compression_chain.py::test_deleting_tip_removes_whole_chain (module docstring: deleting only the physical row "leaves the root behind, and the next list re-projects it onto the previous link")

### Requirement: Live-turn mutation guard
The store SHALL refuse to delete or rewrite a session row whose lease a live turn still owns, and SHALL heal a session row deleted underneath a live agent.
**Status**: VERIFIED
**Evidence**: [PR #123583](https://github.com/NousResearch/hermes-agent/pull/123583) — "refuse to delete a session row a live turn still owns" and "heal a session row deleted under a live agent"
**Anchor**: `hermes_state_mutation_guards.py:6` (require_idle transcript-guard raises on live turn lease)

#### Scenario: Delete refused while a live turn owns the row
- **WHEN** `delete_session` runs while an active turn lease or compression lock protects the row
- **THEN** the delete is refused inside the transaction
- Source: test: tests/hermes_state/test_delete_session_write_guards.py::test_delete_session_refuses_when_write_guard_active (docstring: "refuses inside the transaction while an active turn lease or compression lock protects the row")

#### Scenario: Bulk delete skips guarded sessions
- **WHEN** a bulk delete selects sessions, some still under an active write guard
- **THEN** the guarded sessions are skipped and the rest are deleted
- Source: test: tests/hermes_state/test_delete_session_write_guards.py::test_delete_sessions_bulk_skips_active_write_guards

### Requirement: In-place prune rewrites only changed rows
Proactive pruning SHALL rewrite only the rows whose content actually changed, in place, holding live-owned rows out of the rewrite set.
**Status**: VERIFIED
**Evidence**: [PR #124273](https://github.com/NousResearch/hermes-agent/pull/124273) — "proactive prune rewrites only the changed rows, in place"
**Anchor**: `hermes_state_prune_rewrite.py:133` (`rewrite_pruned_rows`), `hermes_state_prune_rewrite.py:29` (`rewritten_held_row_ids`)

#### Scenario: In-place prune grows by changed rows only
- **WHEN** proactive tool-result pruning rewrites stored transcript rows
- **THEN** the rewrite happens in place and touches only the rows whose content actually changed
- Source: test: tests/agent/test_proactive_prune_restart_safety.py::test_in_place_prune_grows_by_changed_rows_only

#### Scenario: Prune skips rows another writer changed
- **WHEN** another writer has changed the stored body while a prune is planning its rewrite
- **THEN** the in-place prune skips rather than clobbering the newer content
- Source: test: tests/agent/test_proactive_prune_restart_safety.py::test_in_place_prune_skips_when_another_writer_changed_the_stored_body

### Requirement: Busy-vs-gone error taxonomy for remote surfaces
Store errors SHALL distinguish "BUSY, not gone" (retryable, mapped to HTTP 503) from hard failures (500) in one shared classifier so surfaces cannot drift apart in their mapping.
**Status**: VERIFIED
**Evidence**: [PR #140315](https://github.com/NousResearch/hermes-agent/pull/140315) — "catch a lagging state.db up once on browse instead of 503"
**Anchor**: `hermes_state_errors.py:30` ("Store BUSY, not gone — HTTP callers map these to 503"), `hermes_state_errors.py:67` (503-vs-500 split cannot drift apart), `hermes_state_reconcile.py:107` (oversized-store catch-up refused with retryable 503)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Store errors SHALL distinguish "BUSY, not gone" (retryable, mapped to HTTP 503) from hard failures (500) in one shared classifier so surfaces cannot drift apart in their mapping.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Locked-store resilience under gateway load
Lock contention SHALL NOT surface as crashes of `hermes sessions list` or dashboard 503s under a busy gateway (dedicated read pooling / lock guarding around the single-writer model).
**Status**: VERIFIED
**Evidence**: doc: hermes_state.py:197 comment ("database is locked ... under a busy gateway"); siblings `hermes_state_readpool.py`, `hermes_state_lockguard.py`, `hermes_state_lockowners.py` exist for this purpose (not opened) — implemented at pin: reader busy budget hermes_state.py:198 (applied :741), lock-patient open hermes_state.py:835, IOERR-retry on read-only opens hermes_state.py:739-763; tests/hermes_state/test_write_lock_patience.py present
**Anchor**: `hermes_state.py:198` (`_READ_BUSY_TIMEOUT_S = 5.0`) — 5 s SQLite busy-handler budget for read-only connections; the comment ending at :197 names the failure it prevents: "database is locked" (dashboard 503s, `hermes sessions list` crashes) under a busy gateway; `hermes_state.py:835` (`_connect_and_init_with_lock_patience`) — writable open waits out a sibling's write lock (VACUUM/checkpoint/FTS) with jittered patience instead of failing the entire open and disabling persistence; `hermes_state_readpool.py:1` (module docstring "Read-connection budgeting for SessionDB's WAL read path") — per-file/process-wide permit ceilings so pooled readers cannot hit EMFILE; used at `hermes_state.py:741` (`timeout=_READ_BUSY_TIMEOUT_S`)

#### Scenario: Writes survive multi-second lock holds
- **WHEN** sibling Hermes processes legitimately hold the shared `state.db` for multi-second stretches (VACUUM after auto-prune, checkpoint at close on a large WAL, a long FTS pass)
- **THEN** transcript appends and opens survive the wait on write-lock patience instead of erroring out
- Source: test: tests/hermes_state/test_write_lock_patience.py::TestTranscriptWritePatience::test_append_message_survives_multi_second_lock_hold (module docstring: "A shared state.db is legitimately held for multi-second stretches by sibling Hermes processes")

#### Scenario: Concurrent writers no longer poison the store
- **WHEN** a busy gateway drives second writers at `state.db`
- **THEN** writers no longer cancel each other's locks and healthy databases are not reported as corrupt
- Source: [relnote v2026.9.11] "second writers cancelling each other's locks, healthy databases reported as corrupt, one bad row killing `sessions list`. This release closes that class"

### Requirement: FTS5 search with retired-CJK-index cleanup
Message search SHALL be served by FTS5 (plain + trigram tables). A store still holding the `messages_fts_cjk` index an earlier release built SHALL have it dropped at the next read-write open — triggers first, then the source view, `fts_cjk_*` markers and the table — idempotently; CJK terms are served by the trigram and LIKE routes.
**Status**: VERIFIED
**Evidence**: [commit 0a0dab06867e] refactor(state)!: remove the CJK FTS5 tokenizer from core — no installer ever shipped `libfts5_cjk.so`, the loader returned False on every install and CJK queries already took the trigram and LIKE routes; `sessions.cjk_fts`, `HERMES_CJK_FTS` and `HERMES_FTS5_CJK_SO` no longer have an effect. (Rewritten at pin v0.23.1; superseded the pass-3 "CJK-aware tokenizer option" requirement — the tokenizer integration was deleted from core.)
**Anchor**: `hermes_state_fts.py:15` (`_FTS_DDL_TABLES` plain + trigram), `hermes_state_fts.py:165` (`_RETIRED_CJK_TRIGGERS`), `hermes_state_fts.py:178` (`drop_retired_cjk_index`), `hermes_state_schema.py:918` (drop at schema open), `hermes_state_repair.py:815` (drop at repair-probe start)

#### Scenario: A store built with the CJK index reopens without it
- **WHEN** a state.db still carries the `messages_fts_cjk` table, its three triggers and its `fts_cjk_*` markers from an earlier release, so outside writers fail with "no such tokenizer: cjk_unicode61"
- **THEN** the next SessionDB open drops them — "the index, its triggers and its markers are dropped, so writers that never load the tokenizer (the sqlite3 CLI) can write again" — leaving no `messages_fts_cjk` or `fts_cjk_*` residue and `PRAGMA integrity_check` ok
- Source: test: tests/hermes_state/test_fts_cjk_index_retirement.py::test_open_drops_the_cjk_index_and_restores_outside_writers

#### Scenario: Retirement is idempotent and search keeps working
- **WHEN** the store is opened again after its CJK index was retired
- **THEN** the second open finds nothing to drop (no repeated retirement warning), appends still work, and `search_messages` on a CJK term still returns the stored message
- Source: test: tests/hermes_state/test_fts_cjk_index_retirement.py::test_a_second_open_finds_nothing_to_drop

### Requirement: Tool-result spillover archives die with their session
Retiring/deleting sessions SHALL record and retire the tool-result spillover archives their messages point at (prefix `gateway.spillover.retired.v1.`), tying spillover lifetime to the owning session.
**Status**: VERIFIED
**Evidence**: [PR #126351](https://github.com/NousResearch/hermes-agent/pull/126351) — "tie spillover archive lifetime to the owning session"
**Anchor**: `hermes_state_media.py:8` (`SPILLOVER_PREFIX`), `hermes_state_media.py:21` (`retire_spillover`)

#### Scenario: Spill files leave with their session
- **WHEN** a session is deleted or pruned
- **THEN** the oversized-tool-result spill files its transcript pointed at are unlinked — the archive "leaves with its session"
- Source: doc: website/docs/user-guide/configuration.md § spillover — "A spill file is kept as long as any session's transcript still points at it, and leaves with its session when that session is deleted or pruned"; test: tests/test_session_spillover_cleanup.py::test_delete_session_unlinks_the_spill; ::test_prune_sessions_unlinks_the_spill_with_its_session

#### Scenario: Retained and shared spill files survive the age sweep
- **WHEN** the housekeeping age sweep runs while sessions still reference the spill
- **THEN** the referenced spill is kept — a shared pointer survives until the last session dies
- Source: doc: website/docs/user-guide/configuration.md § spillover — "kept as long as any session's transcript still points at it"; test: tests/test_session_spillover_cleanup.py::test_retained_sessions_spill_survives_the_age_sweep; ::test_shared_pointer_survives_until_the_last_session_dies

### Requirement: One preview-column builder for all session listings
Session listings SHALL share one preview-column builder so every surface shows identical previews, and listing subqueries SHALL stay on the messages-session index even under stale planner stats.
**Status**: VERIFIED
**Evidence**: [PR #119403](https://github.com/NousResearch/hermes-agent/pull/119403) — "one preview-column builder, pinned at every session listing"; "session-list subqueries stay on idx_messages_session under stale planner stats" — implemented at pin: builder _sql_preview_raw/_shape_preview live in hermes_state_common.py (:160/:149), imported by every listing sibling; tests/hermes_state/test_session_list_index_choice.py present
**Anchor**: `hermes_state_common.py:160` (`_sql_preview_raw`) — the single correlated `_preview_raw` builder; its docstring (:162-163) states INDEXED BY exists because with planner stats older than idx_messages_session_id SQLite would read and sort the whole session; `hermes_state_common.py:164` (`INDEXED BY idx_messages_session`) — the preview subquery pinned to the (session_id, timestamp) index; same pin in the last-active subquery at `hermes_state_common.py:265`; `hermes_state_sessions.py:1243` (`_sql_preview_raw('tip.id')`) — the one builder pinned at every listing; also called at hermes_state_sessions.py:1342, hermes_state_telegram.py:72, hermes_state_portability.py:85, shaped by `_shape_preview` (hermes_state_sessions.py:1290/1299)

#### Scenario: List subqueries stay on the timestamp index under stale stats
- **WHEN** session listings run against planner stats that predate `idx_messages_session_id`
- **THEN** message reads for the per-session last-active and preview subqueries go only through the (session_id, timestamp) index instead of scanning each session's full message rows
- Source: test: tests/hermes_state/test_session_list_index_choice.py::test_session_listings_search_messages_only_through_the_timestamp_index (module docstring: "Session-list reads stay on the (session_id, timestamp) index whatever the planner stats say (#119403)")

### Requirement: Rebuilt follow-up turns reproduce multimodal content
Follow-up turns reconstructed from the session DB SHALL reproduce attached media (a rebuilt turn must show the user's image again), i.e. persistence is lossless for model-visible content.
**Status**: VERIFIED
**Evidence**: [PR #136216](https://github.com/NousResearch/hermes-agent/pull/136216) — "follow-up turns rebuilt from the session DB see the user's image again" — implemented at pin — in agent/image_replay.py + agent/turn_context.py:1417, NOT in hermes_state_messages/media (draft's guessed location was wrong); tests/agent/test_image_replay.py present
**Anchor**: `agent/image_replay.py:105` (`replay_recent_images`) — puts the newest N retained images back as image_url parts on the wire copy of DB-rebuilt turns; module docstring (:1-20) states replay uses the same `_file_to_data_url` so the rebuilt row is byte-identical and the prompt-cache prefix holds; `agent/image_replay.py:86` (`hashlib.sha256(path.read_bytes()).hexdigest() != path.parent.name`) — only bytes whose content-addressed digest still matches are replayed, inside `_retained_data_url` (:75); `agent/turn_context.py:1417` (`replay_for_agent(agent, api_messages)`) — the rebuilt-turn call site that applies the replay

#### Scenario: Rebuilt follow-up turn re-sends the image byte-identically
- **WHEN** a follow-up turn is rebuilt from rows persisted in the session DB on a native multimodal route
- **THEN** the user's earlier image is replayed with the same wire bytes as the request that first sent it
- **AND** the prompt-cache prefix holds across the rebuild
- Source: test: tests/agent/test_image_replay.py::test_rebuilt_turn_resends_the_image_byte_identical_only_for_native_input (comment: "Same bytes as the request that first sent it: the prompt-cache prefix holds.")

### Requirement: Session-deleted hooks are process-local
`on_session_delete` hook delivery SHALL be documented as process-local, not cross-process.
**Status**: VERIFIED
**Evidence**: [PR #124988](https://github.com/NousResearch/hermes-agent/pull/124988) — "docs(hooks): note on_session_delete delivery is process-local, not cross-process" — doc claim verified verbatim at hooks.md:1113 (requirement is itself a documentation contract); post-commit firing corroborated in hermes_state_sessions.py:957
**Anchor**: `website/docs/user-guide/features/hooks.md:1113` (`Delivery scope`) — the normative text at the pin, verbatim: "Process-local — the callback runs only in the process that committed the delete. It is not a durable cross-process delivery channel, and it carries no exactly-once guarantee"; `hermes_state_sessions.py:957` (`set_session_archived` docstring) — "A real unarchived -> archived flip fires `on_session_delete` (`reason="archive"`) after commit", corroborating the post-commit in-process delivery the doc describes

#### Scenario: Delete hook fires post-commit on every surface
- **WHEN** a session delete or deliberate archive commits (single, bulk, empty-session sweep, retention prune, ghost-prune, profile repair)
- **THEN** `on_session_delete` fires once per operation after the transaction commits, on every surface (CLI, TUI, Desktop/dashboard, gateway API server)
- **AND** unknown ids, repeat archives and un-archives stay silent, and a failing callback is logged and skipped — never failing the delete
- Source: doc: website/docs/user-guide/features/hooks.md § `on_session_delete` — "Fires **once per operation, after the transaction commits**, when a session actually went away... A failing callback is logged and skipped like every other observer and never fails the delete."

#### Scenario: Delivery is process-local
- **WHEN** a session is deleted in a different process than the plugin host
- **THEN** the callback does not run there — it "runs only in the process that committed the delete", not as a durable cross-process delivery channel, with no exactly-once guarantee
- Source: doc: website/docs/user-guide/features/hooks.md § `on_session_delete` — "**Delivery scope:** Process-local — the callback runs only in the process that committed the delete. It is not a durable cross-process delivery channel"

### Requirement: Finalized sessions reopen only on a real turn
Mounting/attaching to a finalized session SHALL NOT reopen its row for display; the first real turn does. Resume-guard proofs rest on the history read, not the reopen.
**Status**: VERIFIED
**Evidence**: [PR #85303](https://github.com/NousResearch/hermes-agent/pull/85303) — "mounting a finalized session no longer reopens its row — the first real turn does"; "the resume guard fail-open proof is the history read, not the reopen" — implemented at pin: read-only mount in tui_gateway/methods_session.py:679, submit-path reopen _reopen_if_finalized (methods_prompt.py:607, invoked :645/:935, compute_host.py:270); tests/tui_gateway/test_resume_readonly_mount.py present
**Anchor**: `tui_gateway/methods_session.py:679` (`read_history` comment: "Read-only mount: an ended row stays ended") — resume must not clear ended_at/end_reason or DB-derived liveness re-lights a finalized session on open; states the first real turn (prompt.submit) reopens it; `tui_gateway/methods_prompt.py:607` (`_reopen_if_finalized`) — docstring "The first real turn is what reopens a finalized session"; called on the submit path at :645 before the turn's first transcript write (comment at :642: "an ended_at set at mount time is cleared HERE")

#### Scenario: Mounting a finalized session keeps it ended
- **WHEN** a finalized session is mounted (`session.resume`, its deferred hydration, or the lazy watch path)
- **THEN** the row's `ended_at`/`end_reason` are not cleared — mounting stays read-only, so DB-derived liveness cannot re-light a finished session just because someone opened it
- Source: test: tests/tui_gateway/test_resume_readonly_mount.py::test_resume_mount_keeps_finalized_row_ended (module docstring: "Mounting a finalized session is read-only (#85303)... only the first real turn (prompt.submit) reopens the row")

#### Scenario: First real turn reopens the row
- **WHEN** the first real turn (`prompt.submit`) arrives on a finalized session
- **THEN** the row is reopened
- Source: test: tests/tui_gateway/test_resume_readonly_mount.py::test_first_real_turn_reopens_a_finalized_row

### Requirement: One turn's rows bind to one session across rotation
Rows written during a single turn (submit row, model-switch markers, pivot rows) SHALL be addressed to the session the turn will write, surviving session rotation; superseded model-switch markers SHALL not replay.
**Status**: VERIFIED
**Evidence**: [PR #123545](https://github.com/NousResearch/hermes-agent/pull/123545) — "record the submit row's session, address every writer by it"; "pin one turn's rows to one session across a rotation"; "keep superseded model-switch markers from replaying" — implemented at pin: submit-row target/owner keys in tui_gateway/session_workdir.py:715/742/789, addressed by session.history (:1985), session.save (:2154/:2165) and the pivot writer (server.py:1201); marker dedupe server.py:1148-1168; tests/tui_gateway/test_submit_row_session_target.py present
**Anchor**: `tui_gateway/session_workdir.py:715` (`_submit_row_target_key`) — returns the live agent.session_id the turn will flush under; docstring records the split-turn failure mode (user row in parent, tool rows/text in child) and that the choice is made ONCE and recorded on the staged dict; `tui_gateway/session_workdir.py:789` (`staged[_SUBMIT_ROW_SESSION_KEY] = target`) — the owning session is recorded at write time so every later addresser (@-expansion rewrite, queue merge, drain deactivation) reads the same key even if a rotation lands mid-turn; `_submit_row_owner_key` (:745) reads it back; `tui_gateway/server.py:1148` (`_MODEL_SWITCH_MARKER_PREFIX`) — only the newest model-switch marker is meaningful; older ones are stale and would otherwise be re-sent every turn, and `_append_model_switch_marker` (server.py:1168) strips prior markers in place before appending (prompt_turn.py:290 comment)

#### Scenario: Submit row lands where the turn's tool rows land
- **WHEN** a turn writes its durable rows after the agent's session rotated (compression continuation, lease-wait re-resolve, adopted tip)
- **THEN** the turn's submit user row is addressed to the session the turn will write — landing where its tool rows land, so one chat shows the whole turn
- Source: test: tests/tui_gateway/test_submit_row_session_target.py::test_submit_user_row_lands_where_the_turns_tool_rows_land (module docstring: "#123545"; without the fix "the user row lands in the parent, every tool row and the final assistant text in the child")

#### Scenario: Model-switch markers land live and do not accumulate
- **WHEN** a model switch writes its marker, and later switches supersede it
- **THEN** the marker is addressed to the live session and superseded markers do not accumulate across switches
- Source: test: tests/tui_gateway/test_submit_row_session_target.py::test_model_switch_marker_lands_in_the_live_session; ::test_model_switch_markers_do_not_accumulate_across_switches

## Known gaps / open questions
- Read-pool / lock-guard implementation (`hermes_state_readpool.py`, `hermes_state_lockguard.py`) not opened — the exact reader-pool contract (pool size, staleness bound) is UNVERIFIED.
- `hermes_state_compression.py` / `hermes_state_compaction_display.py` boundary with agent-turn-loop capability: drafted the split-chain contract here, the compaction algorithm belongs to agent-turn-loop — ownership note for pass 2.
- Memory-system (cross-session memory, `plugins/memory/`) is deferred scope; several bundle PRs (memory provider session-end extraction) were rejected as misfiled here.
- Desktop-owned session behaviors (pin/unpin #142672, composer routing #141583) excluded — desktop-ui capability should own them.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05 (tail without refs).

## Scenario-ification notes
- REQ "Busy-vs-gone error taxonomy for remote surfaces": no doc-grounded trigger; kept as invariant. (The BUSY→503 / hard-failure→500 split is asserted only by code comments at `hermes_state_errors.py:30/:67`; no Tier A/B/C text names the mapping.)
- REQ "One preview-column builder for all session listings": scenario grounds the index-choice half only; the "one shared preview builder at every listing" contract has no Tier A/B/C trigger+outcome text.
- REQ "Live-turn mutation guard": the refuse-half is test-grounded; the "heal a session row deleted under a live agent" half had no Tier A/B/C text found.
