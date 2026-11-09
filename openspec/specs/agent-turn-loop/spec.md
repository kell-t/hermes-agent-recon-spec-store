# Capability: agent-turn-loop

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (scenario grounding) applied 2026-11-08.

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

#### Scenario: Budget exhaustion grants one grace call
- **WHEN** the agent's iteration budget is exhausted mid-conversation (`iteration_budget.remaining` reaches 0)
- **THEN** the loop grants a one-turn grace call instead of stopping mid-work
- Source: doc: agent/AGENTS.md § Agent loop — "Entirely synchronous, with interrupt checks, budget tracking, and a one-turn grace call"

#### Scenario: Interrupt breaks the loop immediately
- **WHEN** an interrupt is requested while the loop is iterating
- **THEN** the loop breaks before issuing another model call
- Source: doc: agent/AGENTS.md § Agent loop — loop shape shown as `if self._interrupt_requested: break`

### Requirement: Prompt cache stability is the governing invariant
The system SHALL keep the system prompt byte-stable for the life of a conversation and SHALL NOT alter past context, change toolsets, reload memories, or rebuild the system prompt mid-conversation; the only sanctioned context mutation is compression.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § "What Hermes Is" invariant 1; doc: agent/AGENTS.md § Message-flow invariants
**Anchor**: `agent/agent_runtime_helpers.py:2768` ("Shallow-copy so stored history / prompt caching stays byte-stable"), `agent/agent_runtime_helpers.py:2815`

#### Scenario: Surface switch keeps the cached prefix
- **WHEN** a conversation switches surface mid-session (Desktop ↔ TUI)
- **THEN** the system prompt is not rebuilt and the prompt cache is not busted
- Source: [relnote v2026.9.11] "Surface switch (Desktop↔TUI) no longer rebuilds the system prompt and busts the prompt cache"

#### Scenario: Tool list frozen for the session
- **WHEN** the session crosses TUI, `-q --resume` and gateway hops
- **THEN** the tool list stays frozen per session so the prompt cache holds all session
- Source: [relnote v0.22.0] "the tool list is frozen per session across TUI, `-q --resume` and gateway hops"

#### Scenario: System-prompt-changing commands defer (compression excepted)
- **WHEN** a slash command would change system-prompt state mid-conversation
- **THEN** it defers to the next session unless the user opts into `--now`, and big sessions confirm a cache-breaking `/model`
- **AND** the one sanctioned exception to byte-stability is context compression
- Source: doc: AGENTS.md (root) § two invariants — "Slash commands that change system-prompt state defer to the next session, with an opt-in `--now`"; "the ONE exception is context compression"; [relnote v0.22.0] "big sessions confirm a cache-breaking `/model`"

### Requirement: Mid-conversation injections ride user or tool-result messages
The system SHALL deliver anything that must inject content mid-conversation (skill slash commands, subdirectory AGENTS.md hints, `/steer`) via a user message or an appended tool result — never by mutating the system prompt.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants; PR #97899 — platform-hint diet compressed system prompt hint weight (−657 tok)
**Anchor**: `agent/skill_commands.py:311` (`_inject_skill_config`), `agent/subdirectory_hints.py:308` (hint appended to tool result with `queue_warning=False`)

#### Scenario: Plugin context rides a user message
- **WHEN** `pre_llm_call` plugin context must be injected mid-conversation
- **THEN** it is moved to a user message to preserve the prompt cache
- Source: [relnote v2026.4.8] "**pre_llm_call plugin context** moved to user message to preserve prompt cache"

#### Scenario: Skill commands and subdirectory hints ride user/tool-result rows
- **WHEN** skill slash commands or subdirectory `AGENTS.md` hints inject content mid-conversation
- **THEN** skill slash commands inject as a user message and subdirectory hints append to the tool result — never the system prompt
- Source: doc: agent/AGENTS.md § Message-flow invariants — "Anything that must inject content mid-conversation rides a **user message or tool result**, never the system prompt"

### Requirement: Subdirectory hint size bound
Subdirectory context hints SHALL be head+tail truncated past a 32,000-character cap, with the truncation logged and never queued as a chat status warning.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (`_MAX_HINT_CHARS = 32_000`)
**Anchor**: `agent/subdirectory_hints.py:26` (`_MAX_HINT_CHARS = 32_000`)

#### Scenario: Oversized hint head+tail truncated, never announced
- **WHEN** a subdirectory `AGENTS.md` hint exceeds 32,000 characters
- **THEN** it is head+tail truncated and the truncation is logged, never queued as a chat status warning
- **AND** `context_file_max_chars` does not raise that cap
- Source: doc: agent/AGENTS.md § Message-flow invariants — "head+tail truncated past `_MAX_HINT_CHARS = 32_000`; the truncation is logged, never queued as a chat status warning — `context_file_max_chars` does not raise that cap"; test: tests/agent/test_subdirectory_hints.py::TestSubdirectoryHintTracker::test_truncation_of_large_hints

### Requirement: Strict role alternation with the /steer exception
The message flow SHALL never emit two same-role messages in a row and SHALL NOT inject synthetic user messages mid-loop; the single exception is `/steer`, delivered as a standalone user row after a tool result and never smeared onto the already-persisted tool row.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants ("Cron deliveries live in their own session for this reason")
**Anchor**: `agent/turn_facade_lease.py:129` ("Appends to the NEWEST role:\"tool\" message (cache-safe, like /steer)")

#### Scenario: /steer persists as its own user row
- **WHEN** `/steer` arrives mid-turn
- **THEN** it is persisted as its own user row delivered after a tool result, and the running agent sees it after its next tool call without the turn being interrupted
- **AND** it is never smeared onto the already-persisted tool row, and does not break the prompt cache
- Source: [relnote v2026.9.11] "a mid-turn `/steer` is persisted as its own user row"; [relnote v2026.4.23] "injects a note that the running agent sees after its next tool call, without interrupting the turn or breaking prompt cache"; doc: agent/AGENTS.md § Message-flow invariants — "never smeared onto the already-persisted tool row"

#### Scenario: Cron deliveries live in their own session
- **WHEN** a cron delivery must enter the message flow
- **THEN** it lives in its own session rather than being injected as a synthetic user message mid-loop
- Source: doc: agent/AGENTS.md § Message-flow invariants — "never a synthetic user message injected mid-loop... Cron deliveries live in their own session for this reason"

### Requirement: Durable session turn lease
Each conversation turn SHALL run under a durable cross-process session turn lease so concurrent drivers of the same session (CLI resume, gateway, background delivery) serialize; losing the lease SHALL interrupt the turn attributed to the lease, not the user.
**Status**: VERIFIED
**Evidence**: PR #112647 (referenced in-code: "attributes the stop to the lease, not the user"); doc: agent/AGENTS.md § Shape (turn lease taken before `run_conversation`)
**Anchor**: `agent/turn_facade_lease.py:1` (module docstring), `agent/turn_facade_lease.py:24` (`_REASON_LEASE_LOST`)

#### Scenario: One writer per session across surfaces
- **WHEN** multiple surfaces (classic CLI, TUI, Desktop, API server, ACP, bots, cron) drive the same chat
- **THEN** a single gateway owns it — one conversation, one queue, one writer — and each agent turn runs only after taking the session turn lease
- Source: [relnote v0.23.0] "A chat is one conversation with one queue and one writer"; doc: agent/AGENTS.md § Shape — "a turn is `agent/conversation_loop.py::run_conversation`, which `AIAgent.run_conversation` forwards to after taking the session turn lease (`turn_facade_lease.py`)"; test: tests/hermes_state/test_session_turn_lease.py::test_turn_lease_serializes_separate_session_db_instances

#### Scenario: Expired lease is reclaimed
- **WHEN** a turn lease's holder dies or lets it expire
- **THEN** the next driver reclaims the lease instead of being blocked forever
- Source: test: tests/hermes_state/test_session_turn_lease.py::test_expired_turn_lease_is_reclaimed

### Requirement: Two-layer compaction thresholds
Context management SHALL use two layers — gateway session hygiene (85%) and the agent `ContextCompressor` (default 50%, configurable, per-model overrides) — and in-place compaction SHALL follow `compression.threshold` without a hidden default token cap.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression (two layers, thresholds); [PR #126064](https://github.com/NousResearch/hermes-agent/pull/126064) — "Compaction follows compression.threshold again: no default 256K token cap (#117915, #125235)"
**Anchor**: `agent/context_compressor.py` (threshold math; e.g. `agent/context_compressor.py:2776`) — 85% gateway figure not located at anchor

#### Scenario: Two layers, two thresholds
- **WHEN** a session's context grows toward its limits
- **THEN** two layers apply: gateway session hygiene at an 85% threshold and the agent `ContextCompressor` at 50% (configurable; per-model overrides; failure cooldown after provider-proven overflow)
- Source: doc: agent/AGENTS.md § Compression — "Two layers: gateway session hygiene (85% threshold) and the agent `ContextCompressor` (50%, configurable; per-model overrides; failure cooldown after provider-proven overflow)"

#### Scenario: Thresholds configurable per model and in absolute tokens
- **WHEN** a deployment needs different compaction points per model
- **THEN** thresholds are configurable per-model and in absolute tokens
- Source: [relnote v2026.8.3] "Thresholds are now configurable per-model and in absolute tokens."

### Requirement: Prune-then-summarize compression algorithm
Compression SHALL first prune old tool results without an LLM call, then select boundaries, then generate a structured summary using the auxiliary compression model.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression; doc: website/docs/developer-guide/context-compression-and-caching.md
**Anchor**: not separately located (compression siblings under `agent/`)

#### Scenario: Prune first, then boundaries, then summarize
- **WHEN** compression runs on a conversation
- **THEN** it prunes old tool results first (no LLM call), then picks boundaries, then generates a structured summary with the `auxiliary` compression model
- Source: doc: agent/AGENTS.md § Compression — "The algorithm prunes old tool results first (no LLM call), then picks boundaries, then generates a structured summary with the `auxiliary` compression model."; [relnote v2026.8.3] "proactive tool-result pruning for large-window models"

### Requirement: System prompt rebuild at the compaction commit boundary
The system SHALL rebuild the system prompt at each compaction commit boundary so config updates finally reach long-lived sessions, while remaining stable between boundaries.
**Status**: VERIFIED
**Evidence**: [PR #98426](https://github.com/NousResearch/hermes-agent/pull/98426) — "system prompt always rebuilds at the commit boundary — updates finally reach long-lived sessions"
**Anchor**: `agent/system_prompt.py:189` (comment cites maintainer-directed #98426)

#### Scenario: System prompt rebuilt at the compaction commit
- **WHEN** a compaction commits (in-place mode, the default)
- **THEN** the system prompt is rebuilt as the live message list is rewritten on the same session id, so config updates reach long-lived sessions at the commit boundary
- Source: doc: website/docs/developer-guide/context-compression-and-caching.md — "a compaction **rewrites the live message list on the same session id**: the system prompt is rebuilt, the summarized middle is swapped in"

### Requirement: Stall-resilient summary generation
A stalled compression summary stream SHALL retry once on `auxiliary.compression.fallback_chain`; a repeated stall SHALL end with a deterministic fallback summary through the same pipeline, and the system SHALL never commit a prune outside the lease/fence.
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Compression; [PR #99692](https://github.com/NousResearch/hermes-agent/pull/99692) — stop Codex/Anthropic aux summary streams at the host deadline; [PR #124077](https://github.com/NousResearch/hermes-agent/pull/124077) — classify stream-guard stall as timeout, not terminal failure
**Anchor**: not located

#### Scenario: Stalled summary retries once on the fallback chain
- **WHEN** a compression summary stream stalls
- **THEN** it retries once on `auxiliary.compression.fallback_chain`
- Source: doc: agent/AGENTS.md § Compression — "A stalled summary stream retries once on `auxiliary.compression.fallback_chain`"

#### Scenario: Repeated stall ends in the deterministic fallback, inside the fence
- **WHEN** the stall repeats (a stall-class failure already on the cooldown ladder)
- **THEN** compression ends with the deterministic fallback summary through the same pipeline
- **AND** a prune is never committed outside the lease/fence
- Source: doc: agent/AGENTS.md § Compression — "a repeated stall (a stall-class failure already on the cooldown ladder) ends with the deterministic fallback summary through the same pipeline — never a prune committed outside the lease/fence"

### Requirement: In-place compaction keeps the session identity and rolls back on commit failure
In-place compaction SHALL keep a single stable session id, SHALL roll the live transcript back when a commit fails, and SHALL not hide the newest summarized turn from turn-start in-place compaction.
**Status**: INFERRED
**Evidence**: [PR #99477](https://github.com/NousResearch/hermes-agent/pull/99477) — roll back live transcript when in-place compaction commit fails; [PR #120187](https://github.com/NousResearch/hermes-agent/pull/120187) — turn-start in-place compaction no longer hides newest summarized turn; doc: agent/AGENTS.md ("In-place compaction keeps a single stable session id")
**Anchor**: not located

#### Scenario: In-place compaction keeps the durable session id
- **WHEN** in-place compaction runs (the default)
- **THEN** it rewrites the live message list on the same session id and soft-archives the pre-compaction turns — still searchable and recoverable, never deleted
- Source: doc: website/docs/developer-guide/context-compression-and-caching.md — "one conversation keeps one durable id for its whole life"; [relnote v2026.7.1] "In-place compaction option (single session id)"

#### Scenario: Failed compaction rolls the transcript back
- **WHEN** a compaction's child create/publish fails
- **THEN** the live transcript rolls back to the parent with the original content intact
- Source: test: tests/agent/test_compression_rotation_state.py::TestOrphanRollbackOnCreateFailure::test_rolls_back_to_parent_when_child_create_fails

### Requirement: post_compaction plugin hook
A committed compaction record SHALL fire a `post_compaction` plugin hook, gated on listener presence, with callbacks isolated by the dispatcher and never raising into compaction.
**Status**: VERIFIED
**Evidence**: [PR #118382](https://github.com/NousResearch/hermes-agent/pull/118382) — add post_compaction hook; doc: agent/compaction_events.py module docstring
**Anchor**: `agent/compaction_events.py:239` (`fire_post_compaction`), `agent/compaction_events.py:246` (listener gate)

#### Scenario: post_compaction fires once per committed compaction
- **WHEN** a compaction commits — automatic or manual, on any surface
- **THEN** the `post_compaction` plugin hook fires once per committed compaction, on every path
- Source: doc: website/docs/user-guide/features/hooks.md § hook table — "`post_compaction` ... Once per committed compaction, on every path"; [relnote v0.23.0] "New hooks: `post_compaction` and `on_session_delete`"

#### Scenario: No-op attempts stay silent; raising callbacks are isolated
- **WHEN** a compaction attempt changed nothing (aborted, blocked, refused)
- **THEN** `post_compaction` does not fire
- **AND** a raising plugin never changes what the compaction returns
- Source: doc: website/docs/user-guide/features/hooks.md § hook table — "Not fired for attempts that changed nothing (aborted, blocked, refused)"; test: tests/agent/test_post_compaction_hook.py::test_post_compaction_fires_once_per_committed_compaction

### Requirement: Agent-level tools via intercept table
Agent-level tools (todo, memory, ...) SHALL be intercepted through the `INLINE_TOOL_EXECUTORS` table before `handle_function_call()`; new ones SHALL register in the table rather than adding conditional chains.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Agent loop ("Adding one: register in that table (no `if name == ...` chain)")
**Anchor**: `agent/inline_tool_executors.py:313` (`INLINE_TOOL_EXECUTORS` dict)

#### Scenario: New agent-level tools register in the intercept table
- **WHEN** a new agent-level tool (like `todo`, `memory`) is added
- **THEN** it registers in the `INLINE_TOOL_EXECUTORS` table rather than a `if name == ...` chain, and is intercepted there before `handle_function_call()`
- Source: doc: agent/AGENTS.md § Agent loop — "Agent-level tools (`todo`, `memory`, ...) are intercepted by `agent/tool_executor.py` through the `INLINE_TOOL_EXECUTORS` table in `agent/inline_tool_executors.py` before `handle_function_call()`. Adding one: register in that table (no `if name == ...` chain)"

### Requirement: Context-file load caps and install-tree exclusion
Context files (AGENTS.md-style) SHALL load from the CWD only at startup and SHALL be capped (`CONTEXT_FILE_MAX_CHARS = 20_000`, dynamic cap from the context window, configurable `context_file_max_chars`); install-tree AGENTS.md SHALL never load as project context.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (cites PR #64611 for install-tree exclusion); bundle PR window contains related prompt work
**Anchor**: `agent/prompt_builder.py:1033` (`CONTEXT_FILE_MAX_CHARS = 20_000`), `agent/prompt_builder.py:1048` (dynamic ceiling clamp)

#### Scenario: Context files load at startup, capped
- **WHEN** Hermes starts a session
- **THEN** context files load from the CWD only, capped by `CONTEXT_FILE_MAX_CHARS` / a dynamic cap from the context window / `context_file_max_chars`
- Source: doc: agent/AGENTS.md § Message-flow invariants — "Context files (`agent/prompt_builder.py`) load from the CWD only at startup and are capped (`CONTEXT_FILE_MAX_CHARS` / dynamic cap from the context window / `context_file_max_chars`)"

#### Scenario: Install-tree AGENTS.md never loads as project context
- **WHEN** the project-context fallback scan encounters Hermes' own install tree
- **THEN** its `AGENTS.md` is skipped and never loaded as project context
- Source: doc: agent/AGENTS.md § Message-flow invariants — "Never load an install-tree `AGENTS.md` as project context (PR #64611)"; test: tests/agent/test_prompt_builder.py::TestBuildContextFilesPrompt::test_skips_agents_md_in_install_tree_on_fallback

### Requirement: Compaction summaries label uncertain claims UNVERIFIED
The system SHALL carry uncertain claims through compaction as explicitly labelled hypotheses rather than restating them as facts.
**Status**: VERIFIED
**Evidence**: [relnote v0.23.0] "Summaries list uncertain claims on `UNVERIFIED:` lines, so a guess does not come back as a fact."; [commit 73bfb9ce7e40] "feat(compression): keep uncertain claims labelled UNVERIFIED through compaction"
**Anchor**: `agent/context_compressor_prompt_rules.py:11` (`UNVERIFIED_SECTION_HEADING`), `agent/context_compressor_prompt_rules.py:14` (`EPISTEMIC_STANCE_RULE`)

#### Scenario: Guesses stay labelled through compaction
- **WHEN** a compaction summary is generated for a conversation containing uncertain claims (suspicions, hypotheses, unverified inferences)
- **THEN** each is listed under "## Unverified / Working Hypotheses" as "UNVERIFIED: <claim> — <basis>" instead of being restated as fact
- Source: [relnote v0.23.0] "Summaries list uncertain claims on `UNVERIFIED:` lines, so a guess does not come back as a fact."

### Requirement: Opt-in prepared compaction ahead of the trigger
With `compression.prepare_ahead`, the system SHALL write the next compaction summary in a background pass before the trigger fires so committing compaction does not pause the turn.
**Status**: VERIFIED
**Evidence**: [relnote v0.23.0] "With `compression.prepare_ahead: true`, the next summary is written in the background as a session nears the trigger, so compaction no longer pauses the turn while the summary is written."; doc: website/docs/developer-guide/context-compression-and-caching.md (prepared-compaction section)
**Anchor**: `agent/prepared_compaction.py:56` (`PREPARE_BAND_RATIO = 0.12`)

#### Scenario: Background summary prepared near the trigger
- **WHEN** `compression.prepare_ahead: true` and the provider-reported prompt count comes within 12% of the compaction trigger
- **THEN** one background pass writes the next summary so compaction no longer pauses the turn
- **AND** the live transcript, the system prompt and the prompt cache are untouched until compaction
- Source: [relnote v0.23.0] "the next summary is written in the background as a session nears the trigger, so compaction no longer pauses the turn while the summary is written"; doc: website/docs/developer-guide/context-compression-and-caching.md — "the live transcript, the system prompt and the prompt cache are untouched until compaction"; `agent/prepared_compaction.py:56` sets `PREPARE_BAND_RATIO = 0.12`

#### Scenario: Late-arriving messages stay in the tail
- **WHEN** messages arrive between the prepared pass and the committing compaction
- **THEN** the prepared summary is used when it still covers the same messages, and every later message is kept as tail word for word
- Source: [relnote v0.23.0] "Messages that arrive in the meantime stay in the tail word for word."

### Requirement: Refused compression summary aborts with the transcript intact
A compression summary request refused by provider safety filtering SHALL abort the compaction as a refusal instead of committing the lossy deterministic fallback; the abort is scoped to Gemini prompt-block refusals.
**Status**: INFERRED
**Evidence**: [commit 9c1799ed1af4] "fix(compression): a safety-blocked summary request aborts with the transcript intact"; [commit be765e31d810] "fix(compression): scope the summary-abort to Gemini prompt blocks only"; test: tests/agent/test_compressor_truncated_summary_guard.py::TestGenerateSummaryTruncationGuard::test_gemini_safety_blocked_summary_request_aborts_and_preserves
**Anchor**: not located (line-level; the refusal surfaces via `agent/gemini_native_adapter.py` into `agent/context_compressor.py`)

#### Scenario: Gemini safety block of the summary aborts, not lossy fallback
- **WHEN** Gemini blocks the compression summary request (HTTP 200 with `promptFeedback.blockReason`)
- **THEN** compression treats it as a refusal and aborts with the transcript intact, never committing the lossy fallback
- Source: test: tests/agent/test_compressor_truncated_summary_guard.py::TestGenerateSummaryTruncationGuard::test_gemini_safety_blocked_summary_request_aborts_and_preserves — "Gemini's safety block of the summary request is a refusal: abort, never the lossy fallback."

## Known gaps / open questions
- The 85% gateway session-hygiene threshold is documented in agent/AGENTS.md but its code constant was not located under `gateway/session*.py` at the pin — confirm owner file (compression vs. gateway) next pass.
- `turn_recovery_autorecover` post-exhaustion wait-and-retry ladder (agent/AGENTS.md) has no drafted requirement: no PR-ref evidence sampled.
- `/compress` manual parser semantics (`here [N]`, focus, `--preview`, `--aggressive` — `agent/conversation_compression_manual.py:69`) are a behavior contract worth a requirement; bundle PR refs for the parser itself were not found.
- PR-ref window ends 2026-10-27 while the pin is 2026-11-05: tail commits (incl. recent compression-chain work dated after #131412 on 2026-10-02 in-bundle) lack refs — re-extract without the `(#NNNN)` filter for pass 2.
- Compression "idle fence" semantics (#114938 dispatch alone must not reset the summary idle fence) referenced in bundle; underlying fence implementation not opened — UNVERIFIED contract.
