# Capability: agent-turn-loop

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
The core agent loop that every Hermes surface (CLI, gateway, TUI, desktop, ACP) drives. It owns the turn iteration with budget/interrupt handling, the per-conversation prompt-caching invariant (the project's "sacred" invariant), context compaction/compression, session turn leasing, and agent-level inline tools. It lives behind the `run_agent.py` facade, assembled from `agent/` mixins; the turn loop is `agent/conversation_loop.py` plus per-phase `agent/turn_*.py` siblings.

## Primary code locations
- `run_agent.py` — public AIAgent facade
- `agent/conversation_loop.py` — turn loop body
- `agent/turn_*.py` — one sibling per turn phase (preflight, request assembly, api call, tool round, overflow, compaction, recovery, finalizer...)
- `agent/turn_facade_lease.py` — durable cross-process session turn lease
- `agent/context_compressor.py`, `agent/compression_facade.py`, `agent/conversation_compression*.py`, `agent/turn_context_compaction.py` — compaction/compression layers
- `agent/system_prompt.py`, `agent/prompt_builder.py`, `agent/subdirectory_hints.py`, `agent/skill_commands.py` — prompt assembly and injection seams
- `agent/inline_tool_executors.py` — agent-level tool intercept table
- `agent/compaction_events.py` — post_compaction hook firing

## Requirements

### Requirement: Budgeted turn iteration
The agent SHALL iterate model calls while `api_call_count < max_iterations` and the iteration budget has remaining, granting exactly one grace call beyond exhaustion, and SHALL break immediately on an interrupt request.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Agent loop (loop shape and one-turn grace call); `max_iterations` default 500 shared with subagents (agent/AGENTS.md § Shape)
**Anchor**: `agent/conversation_loop.py:1746` (`(s.api_call_count < agent.max_iterations and agent.iteration_budget.remaining > 0) or agent._budget_grace_call`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The agent SHALL iterate model calls while `api_call_count < max_iterations` and the iteration budget has remaining, granting exactly one grace call beyond exhaustion, and SHALL break immediately on an interrupt request.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Prompt cache stability is the governing invariant
The system SHALL keep the system prompt byte-stable for the life of a conversation and SHALL NOT alter past context, change toolsets, reload memories, or rebuild the system prompt mid-conversation; the only sanctioned context mutation is compression.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § "What Hermes Is" invariant 1; doc: agent/AGENTS.md § Message-flow invariants
**Anchor**: `agent/agent_runtime_helpers.py:2768` ("Shallow-copy so stored history / prompt caching stays byte-stable"), `agent/agent_runtime_helpers.py:2815`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The system SHALL keep the system prompt byte-stable for the life of a conversation and SHALL NOT alter past context, change toolsets, reload memories, or rebuild the system prompt mid-conversation;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Mid-conversation injections ride user or tool-result messages
The system SHALL deliver anything that must inject content mid-conversation (skill slash commands, subdirectory AGENTS.md hints, `/steer`) via a user message or an appended tool result — never by mutating the system prompt.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants; PR #97899 — platform-hint diet compressed system prompt hint weight (−657 tok)
**Anchor**: `agent/skill_commands.py:311` (`_inject_skill_config`), `agent/subdirectory_hints.py:308` (hint appended to tool result with `queue_warning=False`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The system SHALL deliver anything that must inject content mid-conversation (skill slash commands, subdirectory AGENTS.md hints, `/steer`) via a user message or an appended tool result — never by mutating the system prompt.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Subdirectory hint size bound
Subdirectory context hints SHALL be head+tail truncated past a 32,000-character cap, with the truncation logged and never queued as a chat status warning.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (`_MAX_HINT_CHARS = 32_000`)
**Anchor**: `agent/subdirectory_hints.py:26` (`_MAX_HINT_CHARS = 32_000`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Subdirectory context hints SHALL be head+tail truncated past a 32,000-character cap, with the truncation logged and never queued as a chat status warning.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Strict role alternation with the /steer exception
The message flow SHALL never emit two same-role messages in a row and SHALL NOT inject synthetic user messages mid-loop; the single exception is `/steer`, delivered as a standalone user row after a tool result and never smeared onto the already-persisted tool row.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants ("Cron deliveries live in their own session for this reason")
**Anchor**: `agent/turn_facade_lease.py:129` ("Appends to the NEWEST role:\"tool\" message (cache-safe, like /steer)")


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The message flow SHALL never emit two same-role messages in a row and SHALL NOT inject synthetic user messages mid-loop;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Durable session turn lease
Each conversation turn SHALL run under a durable cross-process session turn lease so concurrent drivers of the same session (CLI resume, gateway, background delivery) serialize; losing the lease SHALL interrupt the turn attributed to the lease, not the user.
**Status**: VERIFIED
**Evidence**: PR #112647 (referenced in-code: "attributes the stop to the lease, not the user"); doc: agent/AGENTS.md § Shape (turn lease taken before `run_conversation`)
**Anchor**: `agent/turn_facade_lease.py:1` (module docstring), `agent/turn_facade_lease.py:24` (`_REASON_LEASE_LOST`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Each conversation turn SHALL run under a durable cross-process session turn lease so concurrent drivers of the same session (CLI resume, gateway, background delivery) serialize;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Two-layer compaction thresholds
Context management SHALL use two layers — gateway session hygiene (85%) and the agent `ContextCompressor` (default 50%, configurable, per-model overrides) — and in-place compaction SHALL follow `compression.threshold` without a hidden default token cap.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression (two layers, thresholds); [PR #126064](https://github.com/NousResearch/hermes-agent/pull/126064) — "Compaction follows compression.threshold again: no default 256K token cap (#117915, #125235)"
**Anchor**: `agent/context_compressor.py` (threshold math; e.g. `agent/context_compressor.py:2776`) — 85% gateway figure not located at anchor


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Context management SHALL use two layers — gateway session hygiene (85%) and the agent `ContextCompressor` (default 50%, configurable, per-model overrides) — and in-place compaction SHALL follow `compression.threshold` without a hidden default token cap.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Prune-then-summarize compression algorithm
Compression SHALL first prune old tool results without an LLM call, then select boundaries, then generate a structured summary using the auxiliary compression model.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression; doc: website/docs/developer-guide/context-compression-and-caching.md
**Anchor**: not separately located (compression siblings under `agent/`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Compression SHALL first prune old tool results without an LLM call, then select boundaries, then generate a structured summary using the auxiliary compression model.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: System prompt rebuild at the compaction commit boundary
The system SHALL rebuild the system prompt at each compaction commit boundary so config updates finally reach long-lived sessions, while remaining stable between boundaries.
**Status**: VERIFIED
**Evidence**: [PR #98426](https://github.com/NousResearch/hermes-agent/pull/98426) — "system prompt always rebuilds at the commit boundary — updates finally reach long-lived sessions"
**Anchor**: `agent/system_prompt.py:189` (comment cites maintainer-directed #98426)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The system SHALL rebuild the system prompt at each compaction commit boundary so config updates finally reach long-lived sessions, while remaining stable between boundaries.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Stall-resilient summary generation
A stalled compression summary stream SHALL retry once on `auxiliary.compression.fallback_chain`; a repeated stall SHALL end with a deterministic fallback summary through the same pipeline, and the system SHALL never commit a prune outside the lease/fence.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression; [PR #99692](https://github.com/NousResearch/hermes-agent/pull/99692) — stop Codex/Anthropic aux summary streams at the host deadline; [PR #124077](https://github.com/NousResearch/hermes-agent/pull/124077) — classify stream-guard stall as timeout, not terminal failure
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A stalled compression summary stream SHALL retry once on `auxiliary.compression.fallback_chain`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: In-place compaction keeps the session identity and rolls back on commit failure
In-place compaction SHALL keep a single stable session id, SHALL roll the live transcript back when a commit fails, and SHALL not hide the newest summarized turn from turn-start in-place compaction.
**Status**: INFERRED
**Evidence**: [PR #99477](https://github.com/NousResearch/hermes-agent/pull/99477) — roll back live transcript when in-place compaction commit fails; [PR #120187](https://github.com/NousResearch/hermes-agent/pull/120187) — turn-start in-place compaction no longer hides newest summarized turn; doc: agent/AGENTS.md ("In-place compaction keeps a single stable session id")
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** In-place compaction SHALL keep a single stable session id, SHALL roll the live transcript back when a commit fails, and SHALL not hide the newest summarized turn from turn-start in-place compaction.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: post_compaction plugin hook
A committed compaction record SHALL fire a `post_compaction` plugin hook, gated on listener presence, with callbacks isolated by the dispatcher and never raising into compaction.
**Status**: VERIFIED
**Evidence**: [PR #118382](https://github.com/NousResearch/hermes-agent/pull/118382) — add post_compaction hook; doc: agent/compaction_events.py module docstring
**Anchor**: `agent/compaction_events.py:239` (`fire_post_compaction`), `agent/compaction_events.py:246` (listener gate)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A committed compaction record SHALL fire a `post_compaction` plugin hook, gated on listener presence, with callbacks isolated by the dispatcher and never raising into compaction.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Agent-level tools via intercept table
Agent-level tools (todo, memory, ...) SHALL be intercepted through the `INLINE_TOOL_EXECUTORS` table before `handle_function_call()`; new ones SHALL register in the table rather than adding conditional chains.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Agent loop ("Adding one: register in that table (no `if name == ...` chain)")
**Anchor**: `agent/inline_tool_executors.py:313` (`INLINE_TOOL_EXECUTORS` dict)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Agent-level tools (todo, memory, ...) SHALL be intercepted through the `INLINE_TOOL_EXECUTORS` table before `handle_function_call()`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Context-file load caps and install-tree exclusion
Context files (AGENTS.md-style) SHALL load from the CWD only at startup and SHALL be capped (`CONTEXT_FILE_MAX_CHARS = 20_000`, dynamic cap from the context window, configurable `context_file_max_chars`); install-tree AGENTS.md SHALL never load as project context.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (cites PR #64611 for install-tree exclusion); bundle PR window contains related prompt work
**Anchor**: `agent/prompt_builder.py:1033` (`CONTEXT_FILE_MAX_CHARS = 20_000`), `agent/prompt_builder.py:1048` (dynamic ceiling clamp)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Context files (AGENTS.md-style) SHALL load from the CWD only at startup and SHALL be capped (`CONTEXT_FILE_MAX_CHARS = 20_000`, dynamic cap from the context window, configurable `context_file_max_chars`);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- The 85% gateway session-hygiene threshold is documented in agent/AGENTS.md but its code constant was not located under `gateway/session*.py` at the pin — confirm owner file (compression vs. gateway) next pass.
- `turn_recovery_autorecover` post-exhaustion wait-and-retry ladder (agent/AGENTS.md) has no drafted requirement: no PR-ref evidence sampled.
- `/compress` manual parser semantics (`here [N]`, focus, `--preview`, `--aggressive` — `agent/conversation_compression_manual.py:69`) are a behavior contract worth a requirement; bundle PR refs for the parser itself were not found.
- PR-ref window ends 2026-10-27 while the pin is 2026-11-05: tail commits (incl. recent compression-chain work dated after #131412 on 2026-10-02 in-bundle) lack refs — re-extract without the `(#NNNN)` filter for pass 2.
- Compression "idle fence" semantics (#114938 dispatch alone must not reset the summary idle fence) referenced in bundle; underlying fence implementation not opened — UNVERIFIED contract.
