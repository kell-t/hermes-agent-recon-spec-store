# Capability: delegation-orchestration

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (anchor verification + scenario grounding + tail fold) applied 2026-11-08

## Purpose
Subagent orchestration via the `delegate_task` agent-level tool: parallel children with isolated context and their own terminal sessions, governed by concurrency/depth/iteration budgets (`delegation.*` config), completion queues back to the parent, and provider routing for child model calls. Implemented by `tools/delegate_tool.py` + siblings and `agent/delegation_*` modules; children inherit profile scope via contextvars.

## Primary code locations
- `tools/delegate_tool.py` (+ `delegate_tool_*.py`: dispatch, child_run, config, results, routes, tasks, tuning, prefix_gate)
- `agent/delegation_backends.py`, `agent/delegation_provider.py`, `agent/delegation_registry.py`, `agent/delegation_context.py`
- `agent/inline_tool_executors.py` — `delegate_task` intercept entry
- `tools/async_delegation.py`, `tools/process_registry.py` — completion queue, durable ledger, orphan sweep
- `toolsets.py` — `delegation` toolset (`delegate_task`)

## Requirements

### Requirement: delegate_task as an agent-level inline tool
Subagent spawning SHALL go through `delegate_task`, intercepted as an agent-level tool (inline executor table, not a registry core tool), with a tasks-only call interface.
**Status**: VERIFIED
**Evidence**: [PR #96424](https://github.com/NousResearch/hermes-agent/pull/96424) — "tasks-only interface + depth-derived delegation (1,201 → 773 tok/call)"; doc: agent/AGENTS.md § Agent loop (inline intercept table)
**Anchor**: `agent/inline_tool_executors.py:303` (`"delegate_task": ... agent._dispatch_delegate_task`), `tools/delegate_tool.py:552` (`def delegate_task`)

#### Scenario: Dispatch shape and completion path
- **WHEN** the parent calls `delegate_task` — "single (`goal` + optional `context`, `toolsets`) or batch (`tasks: [...]`)"
- **THEN** it "spawns a subagent with isolated context + terminal session; the parent waits for the summary unless `background=true`, which returns a delegation id and re-enters the result via the async-delegation completion queue"
- Source: doc: tools/AGENTS.md § Delegation (`tools/delegate_tool.py`)

### Requirement: Bounded concurrency with an explicit default
Concurrent children SHALL be capped by `delegation.max_concurrent_children` (default raised 3 → 10 with config migration), with separate caps for async children (`_get_max_async_children`).
**Status**: VERIFIED
**Evidence**: [PR #86745](https://github.com/NousResearch/hermes-agent/pull/86745) — "raise max_concurrent_children default 3 -> 10 (+migration)"
**Anchor**: `tools/delegate_tool.py:602` (`max_children = _get_max_concurrent_children()`), `tools/delegate_tool_config.py:19` (`_DEFAULT_MAX_CONCURRENT_CHILDREN = 10`)

#### Scenario: Default concurrency ceiling
- **WHEN** a batch of subagents is dispatched
- **THEN** there are "up to 10 concurrent subagents by default (configurable, no hard ceiling)" via `delegation.max_concurrent_children`
- Source: doc: website/docs/user-guide/features/delegation.md § Batch Mode Details ("Maximum concurrency: 10 tasks by default ... floor of 1, no hard ceiling")

#### Scenario: Oversized batch is refused, not truncated
- **WHEN** a batch is larger than the configured concurrency limit
- **THEN** "batches larger than the limit return a tool error rather than being silently truncated"
- Source: doc: website/docs/user-guide/features/delegation.md § Batch Mode Details

### Requirement: One-shot sessions carry a finite delegation budget
A one-shot (unattended) session SHALL charge requested children against a total `delegation.oneshot_max_children` budget; when exhausted, the tool SHALL fail closed and instruct the parent to finish the remaining work itself.
**Status**: VERIFIED
**Evidence**: [PR #86745](https://github.com/NousResearch/hermes-agent/pull/86745) (budget knob family); behavior directly observed during this recon run (this session hit the exhausted budget and received the "do the remaining work yourself" message)
**Anchor**: `tools/delegate_tool.py:532` (`_oneshot_spawn_budget` — "Charge *requested* children against the finite one-shot session's total (delegation.oneshot_max_children)" at :533), `tools/delegate_tool.py:545` (fail-closed instruction "Do the remaining work yourself in this session"), `tools/delegate_tool_config.py:87` (`_get_oneshot_max_children`, default 2, 0 = unlimited)

#### Scenario: One-shot spawn budget exhausted
- **WHEN** a `hermes chat -q` / `--oneshot` session requests more subagents than `delegation.oneshot_max_children` ("at most ... in total (default 2, 0 = unlimited)")
- **THEN** the spawn is refused — "a one-shot run has no later turn to receive results" — and "interactive and gateway sessions are unaffected"
- Source: doc: website/docs/user-guide/features/delegation.md ("One-shot runs are capped separately")

### Requirement: Generous iteration cap for children, truncation marked for the parent
Subagent default iteration cap SHALL be 250 (raised from 50 with migration), and a child ending on `max_iterations` SHALL have its result marked as truncated for the parent's consumption.
**Status**: VERIFIED
**Evidence**: [PR #86506](https://github.com/NousResearch/hermes-agent/pull/86506) — "raise subagent iteration cap default 50 -> 250 (+migration)"; [PR #86641](https://github.com/NousResearch/hermes-agent/pull/86641) — "mark max_iterations-truncated subagent results for the parent"
**Anchor**: `tools/delegate_tool.py:106` (`DEFAULT_MAX_ITERATIONS = 250`), `tools/delegate_tool_child_run.py:667` (`"truncated": exit_reason == "max_iterations"`), `tools/delegate_tool.py:376` (`truncated == (exit_reason == "max_iterations")` in the `_run_single_child` contract)

#### Scenario: Budget stop is distinguishable from completion
- **WHEN** a child exhausts its iteration budget (default 250 tool-calling turns)
- **THEN** it "returns with `exit_reason: max_iterations` and `truncated: true`, so the parent can tell a budget stop from a completed task"
- Source: doc: website/docs/user-guide/features/delegation.md ("Each subagent has an iteration limit (default: 250)"; "A child that exhausts its budget returns with exit_reason: max_iterations and truncated: true")

### Requirement: Spawn-depth bounding
Delegation SHALL enforce a maximum spawn depth (`_get_max_spawn_depth`), deriving child permissions from depth rather than per-call flags.
**Status**: VERIFIED
**Evidence**: [PR #96424](https://github.com/NousResearch/hermes-agent/pull/96424) — "depth-derived delegation"
**Anchor**: `tools/delegate_tool.py:585` (`max_spawn = _get_max_spawn_depth()`), `tools/delegate_tool.py:674` (`orchestration_available = _get_max_spawn_depth() >= 2 and _get_orchestrator_enabled()`), `tools/delegate_tool_toolsets.py:116` (orchestrator role re-grants `delegation` only for `role == "orchestrator"`)

#### Scenario: Flat by default
- **WHEN** a parent (depth 0) spawns children (depth 1) at default config
- **THEN** delegation is flat and "those children cannot delegate further. This prevents runaway recursive delegation"
- **AND** "raise `max_spawn_depth` to 2 to allow orchestrator children to spawn leaf grandchildren; 3+ for deeper trees" (orchestrator role only)
- Source: doc: website/docs/user-guide/features/delegation.md § Depth Limit and Nested Orchestration

### Requirement: Children get dedicated session storage
A subagent SHALL receive its own SessionDB rather than writing into the parent's.
**Status**: VERIFIED
**Evidence**: [PR #81267](https://github.com/NousResearch/hermes-agent/pull/81267) — "subagents get a dedicated SessionDB, not the parent's"
**Anchor**: `tools/delegate_tool.py:124` (`_open_child_session_db` — "DEDICATED SessionDB handle for the child, or None: the parent's handle can be closed by its own lifecycle"), `tools/delegate_tool.py:146` (`reserve_child_store(parent_session_db)`)

#### Scenario: Child never shares the parent's SessionDB handle
- **WHEN** a background delegation child flushes transcript rows while the parent's owner closes its per-job SessionDB
- **THEN** "children must not share the parent's SessionDB object" — each child owns a dedicated connection no other lifecycle can close
- Source: test: tests/tools/test_delegate.py::TestDelegateTask::test_child_gets_dedicated_session_db_not_parents_handle (#81267); ::test_child_dedicated_db_follows_parents_db_path

### Requirement: Child API calls run inline, not on a nested pool
Delegated-child API calls SHALL be routed inline to avoid nested-thread-pool wedge (observed failure mode).
**Status**: VERIFIED
**Evidence**: [PR #60203](https://github.com/NousResearch/hermes-agent/pull/60203) — "route delegated-child API calls inline to avoid nested-pool wedge"
**Anchor**: `agent/chat_completion_helpers.py:797` (`should_use_direct_api_call` — "delegated children (#60203) run inside nested thread pools that wedge before the socket opens ... Running inline drops the deepest layer"), `agent/chat_completion_helpers.py:825` (`if is_delegated_child_context(): return True`)

#### Scenario: Subagent turns stream on the calling thread
- **WHEN** a `subagent`-platform agent makes an OpenAI-wire (`chat_completions`) request
- **THEN** `should_use_direct_api_call` returns True and the request runs "on the wire and on the calling thread" — never put on another worker thread, "that is the nested-pool deadlock this path exists to avoid (#60203)"
- **AND** an interactive platform "still uses the worker thread"
- Source: test: tests/agent/test_direct_contexts_stream_inline.py::test_direct_contexts_stream_on_the_wire_and_on_the_calling_thread (parametrized `platform=["subagent", "cron"]`) and ::test_interactive_platform_still_uses_the_worker_thread

### Requirement: Subagents inherit profile scope and carry a child marker
Children SHALL inherit the parent's secret/profile scope via context copying and carry the valued delegated-child environment marker; a child raising an unscoped-secret error is a spawn-site bug.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Memory/context/curator ("children inherit via copy_context; a child's UnscopedSecretError is a spawn-site bug")
**Anchor**: `agent/delegation_context.py:20` (`DELEGATED_CHILD_ENV_MARKER`), `agent/secret_scope.py` (scope machinery — drafted under profiles-isolation)

#### Scenario: Child secret reads ride the inherited scope
- **WHEN** a delegated child resolves a secret
- **THEN** scope isolation is "BETWEEN profiles; children inherit via `copy_context`", and "a child's `UnscopedSecretError` is a spawn-site bug, never grounds for an `os.getenv` fallthrough"
- **AND** "delegated children carry `delegation_context.py::DELEGATED_CHILD_ENV_MARKER` valued as the fenced Kanban board root, not a bare flag"
- Source: doc: agent/AGENTS.md § Memory/context/curator

### Requirement: Parent tool-resolution state fenced around child runs
The process-global `_last_resolved_tool_names` SHALL be saved/restored around subagent execution so children cannot poison the parent's tool surface.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (names `_run_single_child()` in `tools/delegate_tool.py`)
**Anchor**: `tools/delegate_tool.py:363` (`def _run_single_child`), `model_tools.py:175` (the fenced global)

#### Scenario: Child run leaves the parent's tool surface intact
- **WHEN** a subagent executes (its own tool resolution overwrites the process-global)
- **THEN** "`_run_single_child()` in `tools/delegate_tool.py` saves/restores it around subagent execution"
- Source: doc: agent/AGENTS.md § Message-flow invariants ("`_last_resolved_tool_names` is a process-global in `model_tools.py`")

### Requirement: Gateway coalesces same-tick delegation completions
The gateway SHALL coalesce async-delegation completions arriving in the same tick into one parent turn rather than one turn per completion.
**Status**: VERIFIED
**Evidence**: [PR #70300](https://github.com/NousResearch/hermes-agent/pull/70300) — "coalesce same-tick async-delegation completions into one turn"
**Anchor**: `gateway/run_notifications.py:1688-1693` ("A fan-out finishing together yields N completions for one session; group by full route + parent session so each group becomes ONE consolidated turn. ... Events for different sessions never coalesce. See #70300."; `groups` dict at :1693)

#### Scenario: Fan-out finishing together yields one turn
- **WHEN** a same-tick completion drain carries N async-delegation completions for the same originating session
- **THEN** each route+session group "becomes ONE consolidated turn" and all rows are acked
- **AND** "events for different sessions never coalesce"
- Source: test: tests/gateway/test_completion_delivery.py::test_same_tick_async_batch_coalesces_into_one_turn_and_acks_all_rows and ::test_same_tick_async_events_for_different_sessions_do_not_coalesce (#70300)

### Requirement: Completion-queue consumers restore the ledger first
Consumers of the delegation completion queue SHALL restore the launch ledger before reading it (test-pinned ordering invariant).
**Status**: VERIFIED
**Evidence**: [PR #123265](https://github.com/NousResearch/hermes-agent/pull/123265) — "consumers restore the ledger before reading the completion queue"
**Anchor**: `tools/process_registry.py:1803` (`restore_completions` — "Rehydrate durable delegation completions from the LAUNCH profile's ledger, once per process. Called by the first consumer that drains the queue (CLI/TUI drain, gateway boot, TUI poller) ... (#123265)"), `tools/async_delegation.py:343` (`restore_undelivered_completions`), `gateway/run_notifications.py:1621` (`_restore_secondary_completion_ledgers`)

#### Scenario: First drain replays the launch ledger
- **WHEN** a consumer first drains the completion queue (a mere `import model_tools` must never touch state.db)
- **THEN** the launch ledger is replayed into the queue exactly once per process — even when the first drain call arrives under a secondary profile's scope
- Source: test: tests/tools/test_process_registry_lazy_restore.py::test_restore_runs_once_on_first_drain, ::test_first_drain_under_secondary_scope_replays_the_launch_ledger, ::test_model_tools_import_creates_no_state_db

### Requirement: Subagents transcripts are live-viewable
Subagent runs SHALL expose live-tailable transcripts to the parent/user while the child works.
**Status**: VERIFIED
**Evidence**: [PR #67479](https://github.com/NousResearch/hermes-agent/pull/67479) — "live-viewable subagent transcripts — tail your subagents while they work"
**Anchor**: `tools/delegation_live_log.py:91` (`LiveTranscriptWriter`), `tools/delegation_live_log.py:235` (`create_live_transcripts`), `tools/delegate_tool.py:659` (`create_live_transcripts` call — transcripts pre-created at dispatch), `website/docs/user-guide/features/delegation.md` § Live Transcripts

#### Scenario: Tail a running subagent immediately
- **WHEN** a `delegate_task` dispatch starts
- **THEN** it "creates one append-only, human-readable log per task" under `<hermes_home>/cache/delegation/live/<delegation_id>/task-<n>.log`, and "the files are pre-created at dispatch time", so `tail -f ~/.hermes/cache/delegation/live/deleg_ab12cd34/task-0.log` "works immediately"
- **AND** "the dispatch response includes the paths as `live_transcripts`"
- Source: doc: website/docs/user-guide/features/delegation.md § Live Transcripts; test: tests/tools/test_delegation_live_log.py::test_writer_precreates_file_with_header

### Requirement: Delegation providers carry request overrides
A delegation provider SHALL be configurable as `delegation.provider` alongside `base_url`, carrying request overrides (per-provider plugin contract documented at `website/docs/developer-guide/delegation-provider-plugin.md`).
**Status**: VERIFIED
**Evidence**: [PR #65035](https://github.com/NousResearch/hermes-agent/pull/65035) — "delegation.provider alongside base_url carries request overrides"; doc: website/docs/developer-guide/delegation-provider-plugin.md
**Anchor**: `tools/delegate_tool_config.py:433` (`"""delegation.provider branch: full bundle via the runtime provider system."""`), `tools/delegate_tool_config.py:349` (`_merge_request_overrides` — "Merge explicit delegation.request_overrides OVER runtime-derived ones"), `agent/delegation_provider.py:52` (route keys include `request_overrides`)

#### Scenario: Explicit overrides merge over runtime-derived ones
- **WHEN** `delegation.provider` is set alongside `delegation.base_url` and explicit `delegation.request_overrides` exist
- **THEN** explicit keys "merge ... OVER runtime-derived ones" and ride the child's request
- Source: test: tests/tools/test_delegate_request_overrides.py::test_explicit_merges_over_runtime_on_provider_alongside_base_url (#65035)

#### Scenario: A provider answers only the route question
- **WHEN** a plugin registers a delegation provider (`ctx.register_delegation_provider()`)
- **THEN** "a delegation provider decides how each `delegate_task` task becomes a child run: which model, provider, endpoint and reasoning effort the subagent uses, or which Hermes profile it runs as" — core keeps dispatch, validation and progress; the active provider is `delegation.backend`, whose default strategy follows the `delegation` section (`delegation.provider`, `delegation.model`, `delegation.base_url`, ...)
- Source: doc: website/docs/developer-guide/delegation-provider-plugin.md

### Requirement: Subagents may use execute_code
Subagents SHALL be allowed the `execute_code` tool (subject to the parent's toolset gating).
**Status**: VERIFIED
**Evidence**: [PR #69325](https://github.com/NousResearch/hermes-agent/pull/69325) — "let subagents use execute_code"; `toolsets.py:24` lists `execute_code`, `delegate_task` together in a core grouping
**Anchor**: `tools/delegate_tool_toolsets.py:14` (`DELEGATE_BLOCKED_TOOLS` — blocks `delegate_task`, `clarify`, `memory`, `send_message`, `cronjob_manage`; `execute_code` is not blocked)

#### Scenario: Both child roles keep execute_code
- **WHEN** a child is spawned in either role — `leaf` (default) or `orchestrator`
- **THEN** "both roles retain `execute_code` (programmatic tool calling) so children can batch mechanical work", while leaf children lose `delegate_task`, `clarify`, `memory`, `send_message`, `cronjob`
- Source: doc: website/docs/user-guide/features/delegation.md ("Both roles retain execute_code..."); doc: tools/AGENTS.md § Delegation ("leaf (default; no delegate_task, clarify, memory, send_message, cronjob; keeps execute_code)")

**Sub-area: Tail fold (commits after 2026-10-27, bundle TAIL APPEND G-01)**

### Requirement: Opt-in prompt-cache warm-up gate staggers batch siblings behind a leader
With `delegation.prefix_stagger_seconds` set, cache-sharing batch siblings SHALL wait for the leader's first response to begin before starting, bounded by the configured cap as a warm-up wait (not a fixed stagger); a stopped leader or non-streamed first response SHALL release siblings before the cap, and background siblings SHALL ignore a parent stop while waiting.
**Status**: VERIFIED
**Evidence**: [commit 6d0686ba3c47] "feat(delegation): opt-in prompt-cache warm-up gate for batch subagents"; [commit c58e6de692f1] "docs(delegation): prefix_stagger_seconds is a cap on the warm-up wait, not a stagger"; [commit fbec17e9e22e] "background siblings outlive a parent stop; a gate-skipped child is released"; [commit 17a8d1e201c2] "pin the gate's non-streamed and failed-leader releases, queued-child teardown and the config read"
**Anchor**: `tools/delegate_tool_prefix_gate.py:1` (module docstring — "Prompt-cache warm-up gate for batch subagents (delegation.prefix_stagger_seconds)"), `:50` (`PrefixCacheGate.for_children`), `:73` (`_wait`) — anchors verified live at pin, pass 4

#### Scenario: Siblings start after the leader's first response begins
- **WHEN** a batch dispatches cache-sharing siblings with the warm-up gate enabled
- **THEN** siblings "start only after the leader's first response begins" — the gate is off by default and bounded by the configured cap
- **AND** "a non-streamed first response or a failed leader releases siblings before the cap"
- Source: test: tests/tools/test_delegate_prefix_cache_gate.py::test_cache_sharing_siblings_start_only_after_the_leaders_first_response_begins, ::test_gate_is_off_by_default_bounded_by_the_cap_and_a_stopped_sibling_never_starts, ::test_a_non_streamed_first_response_or_a_failed_leader_releases_siblings_before_the_cap (#G-01 tail, 17a8d1e201c2)

#### Scenario: A parent stop does not strand queued siblings
- **WHEN** the parent stops while siblings are waiting on the gate or already backgrounded
- **THEN** "background siblings ignore a parent stop and a sibling stopped while waiting is released" — never left half-spawned
- Source: test: tests/tools/test_delegate_prefix_cache_gate.py::test_background_siblings_ignore_a_parent_stop_and_a_sibling_stopped_while_waiting_is_released (#G-01 tail, fbec17e9e22e); ::test_queued_children_cancelled_by_a_parent_stop_are_detached_and_closed

### Requirement: Child session ids are published only after their transcripts are reserved
The parent SHALL reserve a child's transcript row and execution under its own owner before publishing the child's session id, so a consumer that opens the published id never builds against an unpersisted child; a failed reservation closes the unpublished child and a later build may retry.
**Status**: VERIFIED
**Evidence**: [commit 13e0ce980129] "reserve child transcripts before publishing session IDs"; [commit 6059d35108af] "preserve initialization after transcript reservation"
**Anchor**: `tools/delegate_tool.py:124` (`_open_child_session_db` — reservation path via `reserve_child_store`, "the owner reserves the child's row and execution under the parent's own"), `agent/runtime_session_child.py:44` (`reserve_child_store`) — anchors verified live at pin, pass 4

#### Scenario: Published children are openable before any child starts
- **WHEN** a dispatch publishes children's session ids
- **THEN** the reserved transcripts are already open — "published children open before any child starts"
- **AND** "a failed reservation closes the unpublished child and a later build can retry"
- Source: test: tests/tools/test_delegate_transcript_readiness.py::test_published_children_open_before_any_child_starts, ::test_failed_reservation_closes_unpublished_child_and_a_later_build_can_retry (#G-01 tail, 13e0ce980129)

### Requirement: A pending completion is re-offered only when its copy is provably lost
The completion sweep SHALL re-offer a delegation completion into the queue only when the owning process proves its in-memory copy was lost, each re-offer taking its own lease, and replay plus sweep SHALL never offer the same row twice.
**Status**: VERIFIED
**Evidence**: [commit 8a10a3cbef53] "re-offer a pending completion only when its copy is provably lost"; [commit b84774186502] "give each lost-copy re-offer its own lease and count held copies as live"
**Anchor**: `tools/async_delegation.py:472` (`_note_reoffers` — "Start each lost copy's re-offer lease"; module map "when the sweep last re-offered a lost copy" at :78) — anchors verified live at pin, pass 4

#### Scenario: Live copy is never re-offered; lost copy returns after a lease
- **WHEN** the orphan sweep inspects a completion whose owner is live
- **THEN** a "row owned by a live process is never swept" — only "a live owner row whose queue copy was lost is re-offered after a lease"
- **AND** "restart replay and sweep never offer the same row twice"
- Source: test: tests/tools/test_async_delegation_orphan_sweep.py::test_row_owned_by_a_live_process_is_never_swept, ::test_live_owner_row_whose_queue_copy_was_lost_is_re_offered_after_a_lease, ::test_restart_replay_and_sweep_never_offer_the_same_row_twice (#G-01 tail, 8a10a3cbef53 / b84774186502)

## Known gaps / open questions
- Kanban multi-agent queue vs delegate_task orchestration boundary: kanban dispatcher lives at the deferred plugins boundary (cron/AGENTS.md); its fencing root is the child env marker VALUE (agent/AGENTS.md) — cross-capability contract, needs one owner next pass.
- Worktree isolation knob (`_get_worktree_isolation`) seen in config imports — never drafted; UNVERIFIED contract.
- Fleet reconciliation of gateway processes (#103679, #93406 "fleet probe") is update/packaging scope (deferred) — the "fleet" keyword false-positives here; regex to tighten.
- Child timeout semantics (`_get_child_timeout`) and orchestrator enable flag (`_get_orchestrator_enabled`) not drafted.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05; bundle is thin (84 items) and older than other caps' newest evidence.
- DOC-vs-DOC (pass 2, flagged not fixed): tools/AGENTS.md § Delegation says concurrency "default 3" — stale against `tools/delegate_tool_config.py:19` (`_DEFAULT_MAX_CONCURRENT_CHILDREN = 10`) and website/docs/user-guide/features/delegation.md ("Up to 10 concurrent subagents by default"). Requirement kept at the code/drift-correct value (10) per PR #86745.
- DOC-vs-DOC (pass 2, flagged not fixed): "tasks-only call interface" (PR #96424) vs tools/AGENTS.md § Delegation "Shapes: single (`goal` + ...) or batch (`tasks: [...]`)" — the internal dispatch still accepts both shapes; the tasks-only claim describes the model-facing schema. Requirement wording left as drafted.
- Provider-selection naming (pass 2, flagged not fixed): the per-provider plugin is selected by `delegation.backend` (website/docs/developer-guide/delegation-provider-plugin.md:17), while `delegation.provider` is the model-provider pin inside the `delegation` section (tools/delegate_tool_config.py:433). The requirement's "`delegation.provider` alongside `base_url`" matches the credential-route branch, not the plugin selector.

## Scenario-ification notes
- All 14 drafted requirements now carry at least one grounded scenario (Tier B docs: delegation.md / tools/AGENTS.md / agent/AGENTS.md / delegation-provider-plugin.md; Tier C: pinned test names cited inline).
- Tail folds: 3 requirements added from TAIL APPEND G-01 (max 3 allowed): prompt-cache warm-up gate (4 tail commits, module + tests opened), transcript-reservation-before-publish (2 commits, test opened), lost-copy re-offer lease (2 commits, sweep anchor + tests opened). Deferred tail candidates: TUI parked-delegation cluster (f702e968d829, b87a9a360998, cbd71f33b1b8 — TUI surface, belongs with a deferred desktop/TUI capability), async-record Context-pinning fix (e48531be2982; tests/tools/test_async_delegation_record_retention.py), `/bg` entry-point join fix (2d0bf91f111a), desktop running-highlight rows (e032b8a26425, cc9dbb0583fc — desktop scope). Fleet reconciliation stays excluded per the Known-gaps line above (update-packaging, deferred).
