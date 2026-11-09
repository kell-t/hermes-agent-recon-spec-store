# Capability: delegation-orchestration

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
Subagent orchestration via the `delegate_task` agent-level tool: parallel children with isolated context and their own terminal sessions, governed by concurrency/depth/iteration budgets (`delegation.*` config), completion queues back to the parent, and provider routing for child model calls. Implemented by `tools/delegate_tool.py` + siblings and `agent/delegation_*` modules; children inherit profile scope via contextvars.

## Primary code locations
- `tools/delegate_tool.py` (+ `delegate_tool_*.py`: dispatch, child_run, config, results, routes, tasks, tuning)
- `agent/delegation_backends.py`, `agent/delegation_provider.py`, `agent/delegation_registry.py`, `agent/delegation_context.py`
- `agent/inline_tool_executors.py` — `delegate_task` intercept entry
- `toolsets.py` — `delegation` toolset (`delegate_task`)

## Requirements

### Requirement: delegate_task as an agent-level inline tool
Subagent spawning SHALL go through `delegate_task`, intercepted as an agent-level tool (inline executor table, not a registry core tool), with a tasks-only call interface.
**Status**: VERIFIED
**Evidence**: [PR #96424](https://github.com/NousResearch/hermes-agent/pull/96424) — "tasks-only interface + depth-derived delegation (1,201 → 773 tok/call)"; doc: agent/AGENTS.md § Agent loop (inline intercept table)
**Anchor**: `agent/inline_tool_executors.py:303` (`"delegate_task": ... agent._dispatch_delegate_task`), `tools/delegate_tool.py:552` (`def delegate_task`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Subagent spawning SHALL go through `delegate_task`, intercepted as an agent-level tool (inline executor table, not a registry core tool), with a tasks-only call interface.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Bounded concurrency with an explicit default
Concurrent children SHALL be capped by `delegation.max_concurrent_children` (default raised 3 → 10 with config migration), with separate caps for async children (`_get_max_async_children`).
**Status**: VERIFIED
**Evidence**: [PR #86745](https://github.com/NousResearch/hermes-agent/pull/86745) — "raise max_concurrent_children default 3 -> 10 (+migration)"
**Anchor**: `tools/delegate_tool.py:602` (`max_children = _get_max_concurrent_children()`), `tools/delegate_tool_config.py` (config getters module)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Concurrent children SHALL be capped by `delegation.max_concurrent_children` (default raised 3 → 10 with config migration), with separate caps for async children (`_get_max_async_children`).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: One-shot sessions carry a finite delegation budget
A one-shot (unattended) session SHALL charge requested children against a total `delegation.oneshot_max_children` budget; when exhausted, the tool SHALL fail closed and instruct the parent to finish the remaining work itself.
**Status**: VERIFIED
**Evidence**: [PR #86745](https://github.com/NousResearch/hermes-agent/pull/86745) (budget knob family); behavior directly observed during this recon run (this session hit the exhausted budget and received the "do the remaining work yourself" message)
**Anchor**: `tools/delegate_tool.py:533` (charge against `delegation.oneshot_max_children`), `tools/delegate_tool.py:545` (fail-closed instruction text)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A one-shot (unattended) session SHALL charge requested children against a total `delegation.oneshot_max_children` budget;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Generous iteration cap for children, truncation marked for the parent
Subagent default iteration cap SHALL be 250 (raised from 50 with migration), and a child ending on `max_iterations` SHALL have its result marked as truncated for the parent's consumption.
**Status**: INFERRED
**Evidence**: [PR #86506](https://github.com/NousResearch/hermes-agent/pull/86506) — "raise subagent iteration cap default 50 -> 250 (+migration)"; [PR #86641](https://github.com/NousResearch/hermes-agent/pull/86641) — "mark max_iterations-truncated subagent results for the parent"
**Anchor**: not located (`tools/delegate_tool_tuning.py` per module naming)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Subagent default iteration cap SHALL be 250 (raised from 50 with migration), and a child ending on `max_iterations` SHALL have its result marked as truncated for the parent's consumption.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Spawn-depth bounding
Delegation SHALL enforce a maximum spawn depth (`_get_max_spawn_depth`), deriving child permissions from depth rather than per-call flags.
**Status**: VERIFIED
**Evidence**: [PR #96424](https://github.com/NousResearch/hermes-agent/pull/96424) — "depth-derived delegation"
**Anchor**: `tools/delegate_tool.py:33` (`_get_max_spawn_depth` import) — enforcement site not opened


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Delegation SHALL enforce a maximum spawn depth (`_get_max_spawn_depth`), deriving child permissions from depth rather than per-call flags.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Children get dedicated session storage
A subagent SHALL receive its own SessionDB rather than writing into the parent's.
**Status**: INFERRED
**Evidence**: [PR #81267](https://github.com/NousResearch/hermes-agent/pull/81267) — "subagents get a dedicated SessionDB, not the parent's"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A subagent SHALL receive its own SessionDB rather than writing into the parent's.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Child API calls run inline, not on a nested pool
Delegated-child API calls SHALL be routed inline to avoid nested-thread-pool wedge (observed failure mode).
**Status**: INFERRED
**Evidence**: [PR #60203](https://github.com/NousResearch/hermes-agent/pull/60203) — "route delegated-child API calls inline to avoid nested-pool wedge"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Delegated-child API calls SHALL be routed inline to avoid nested-thread-pool wedge (observed failure mode).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Subagents inherit profile scope and carry a child marker
Children SHALL inherit the parent's secret/profile scope via context copying and carry the valued delegated-child environment marker; a child raising an unscoped-secret error is a spawn-site bug.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Memory/context/curator ("children inherit via copy_context; a child's UnscopedSecretError is a spawn-site bug")
**Anchor**: `agent/delegation_context.py:20` (`DELEGATED_CHILD_ENV_MARKER`), `agent/secret_scope.py` (scope machinery — drafted under profiles-isolation)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Children SHALL inherit the parent's secret/profile scope via context copying and carry the valued delegated-child environment marker;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Parent tool-resolution state fenced around child runs
The process-global `_last_resolved_tool_names` SHALL be saved/restored around subagent execution so children cannot poison the parent's tool surface.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (names `_run_single_child()` in `tools/delegate_tool.py`)
**Anchor**: `tools/delegate_tool.py:363` (`def _run_single_child`), `model_tools.py:175` (the fenced global)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The process-global `_last_resolved_tool_names` SHALL be saved/restored around subagent execution so children cannot poison the parent's tool surface.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Gateway coalesces same-tick delegation completions
The gateway SHALL coalesce async-delegation completions arriving in the same tick into one parent turn rather than one turn per completion.
**Status**: INFERRED
**Evidence**: [PR #70300](https://github.com/NousResearch/hermes-agent/pull/70300) — "coalesce same-tick async-delegation completions into one turn"
**Anchor**: not located (gateway-side consumer)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The gateway SHALL coalesce async-delegation completions arriving in the same tick into one parent turn rather than one turn per completion.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Completion-queue consumers restore the ledger first
Consumers of the delegation completion queue SHALL restore the launch ledger before reading it (test-pinned ordering invariant).
**Status**: INFERRED
**Evidence**: [PR #123265](https://github.com/NousResearch/hermes-agent/pull/123265) — "consumers restore the ledger before reading the completion queue"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Consumers of the delegation completion queue SHALL restore the launch ledger before reading it (test-pinned ordering invariant).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Subagent transcripts are live-viewable
Subagent runs SHALL expose live-tailable transcripts to the parent/user while the child works.
**Status**: INFERRED
**Evidence**: [PR #67479](https://github.com/NousResearch/hermes-agent/pull/67479) — "live-viewable subagent transcripts — tail your subagents while they work"
**Anchor**: `tools/delegate_tool_progress.py` (module named for the feature; not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Subagent runs SHALL expose live-tailable transcripts to the parent/user while the child works.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Delegation providers carry request overrides
A delegation provider SHALL be configurable as `delegation.provider` alongside `base_url`, carrying request overrides (per-provider plugin contract documented at `website/docs/developer-guide/delegation-provider-plugin.md`).
**Status**: INFERRED
**Evidence**: [PR #65035](https://github.com/NousResearch/hermes-agent/pull/65035) — "delegation.provider alongside base_url carries request overrides"
**Anchor**: `agent/delegation_provider.py` (module exists; not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A delegation provider SHALL be configurable as `delegation.provider` alongside `base_url`, carrying request overrides (per-provider plugin contract documented at `website/docs/developer-guide/delegation-provider-plugin.md`).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Subagents may use execute_code
Subagents SHALL be allowed the `execute_code` tool (subject to the parent's toolset gating).
**Status**: INFERRED
**Evidence**: [PR #69325](https://github.com/NousResearch/hermes-agent/pull/69325) — "let subagents use execute_code"; `toolsets.py:24` lists `execute_code`, `delegate_task` together in a core grouping
**Anchor**: `toolsets.py:24`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Subagents SHALL be allowed the `execute_code` tool (subject to the parent's toolset gating).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- Kanban multi-agent queue vs delegate_task orchestration boundary: kanban dispatcher lives at the deferred plugins boundary (cron/AGENTS.md); its fencing root is the child env marker VALUE (agent/AGENTS.md) — cross-capability contract, needs one owner next pass.
- Worktree isolation knob (`_get_worktree_isolation`) seen in config imports — never drafted; UNVERIFIED contract.
- Fleet reconciliation of gateway processes (#103679, #93406 "fleet probe") is update/packaging scope (deferred) — the "fleet" keyword false-positives here; regex to tighten.
- Child timeout semantics (`_get_child_timeout`) and orchestrator enable flag (`_get_orchestrator_enabled`) not drafted.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05; bundle is thin (84 items) and older than other caps' newest evidence.
