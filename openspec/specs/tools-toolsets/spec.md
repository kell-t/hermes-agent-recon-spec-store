# Capability: tools-toolsets

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 3 (scenario-ification) applied 2026-11-08

## Purpose
The model-tool surface: `tools/registry.py` (dependency-free registry with import-time self-registration and auto-discovery), `toolsets.py` (the TOOLSETS dict and `_HERMES_CORE_TOOLS` default bundle), and `model_tools.py` (schema collection, dispatch via `handle_function_call()`, per-session resolution). Governed by the project's "narrow waist" invariant: every model tool is sent on every API call, so new core tools face a high bar (Footprint Ladder).

## Primary code locations
- `tools/registry.py` — registry, discovery, check_fn cache, result normalization
- `toolsets.py` — `_HERMES_CORE_TOOLS` (line 11), toolset composition, session-disabled toolsets
- `model_tools.py` — orchestration, `handle_function_call()` (line 886), dynamic cross-references
- `tools/AGENTS.md` — normative rules for adding tools; long-form `website/docs/developer-guide/adding-tools.md`

## Requirements

### Requirement: Import-time registry self-registration with auto-discovery
Every `tools/*.py` with a top-level `registry.register()` SHALL be imported and registered automatically (no manual import list); package-style tools SHALL register from `tools/<pkg>/tool.py`, the only file scanned inside a package, and a package lacking `__init__.py` SHALL be skipped with a warning.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § Registry and discovery
**Anchor**: `tools/registry.py:121` (`discover_builtin_tools`)

#### Scenario: New tool file registers without an import list
- **WHEN** a `tools/*.py` file calls `registry.register()` at import time
- **THEN** it SHALL be imported and registered automatically
- Source: doc: tools/AGENTS.md § Registry and discovery "Any `tools/*.py` with a top-level `registry.register()` is imported automatically"

#### Scenario: Package tool without `__init__.py` is skipped
- **WHEN** a package-style tool (`tools/<pkg>/`) lacks an `__init__.py`
- **THEN** discovery SHALL skip the package with a warning
- **AND** only `tools/<pkg>/tool.py` is scanned inside a package (every sibling is a library by construction)
- Source: doc: tools/AGENTS.md § Registry and discovery "the package needs an `__init__.py` or discovery skips it with a"
- Source: doc: tools/AGENTS.md § Registry and discovery "the only file discovery scans inside a package"

### Requirement: Toolset membership gates exposure
Registering a schema SHALL not expose a tool: a tool is model-visible only if a toolset names it; `_HERMES_CORE_TOOLS` is the default bundle every platform's base toolset inherits.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § "Adding a core tool" step 2 ("Required — a tool is only exposed if a toolset names it")
**Anchor**: `toolsets.py:11` (`_HERMES_CORE_TOOLS = [`), `toolsets.py:54` (toolset = core + extras)

#### Scenario: Registration alone does not expose a tool
- **WHEN** a tool's schema has been discovered and registered, but no toolset names it
- **THEN** it SHALL NOT be model-visible — a tool is only exposed if a toolset names it
- **AND** `_HERMES_CORE_TOOLS` is the default bundle every platform's base toolset inherits
- Source: doc: tools/AGENTS.md § Adding a core tool, step 2 "discovery registers the schema, but a tool is only exposed if a toolset names it"
- Source: doc: tools/AGENTS.md § Adding a core tool, step 2 "`_HERMES_CORE_TOOLS` is the default bundle every platform's base toolset inherits"

### Requirement: JSON-string handler contract with a single multimodal exception
All tool handlers SHALL return a JSON string, except a tool returning pixels, which MAY return the exact envelope `{"_multimodal": True, "content": [...], "text_summary": str}` accepted by the registry's result normalizer; the normalizer SHALL accept exactly that shape.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § Registry and discovery
**Anchor**: `tools/registry.py:955` (`_normalize_handler_result`), `tools/registry.py:963` (`"_multimodal" is True` check)

#### Scenario: Handlers return JSON strings
- **WHEN** any tool handler returns
- **THEN** it SHALL return a JSON string
- **AND** the one exception is a tool that hands the model pixels
- Source: doc: tools/AGENTS.md § Registry and discovery "All handlers return a JSON"
- Source: doc: tools/AGENTS.md § Registry and discovery "except a tool that hands the model pixels"

#### Scenario: The multimodal envelope is the one pixel exception
- **WHEN** a pixel-returning tool returns the multimodal envelope `{"_multimodal": True, "content": [...], "text_summary": str}`
- **THEN** the registry's result normalizer SHALL accept exactly that shape
- Source: doc: tools/AGENTS.md § Registry and discovery "it may return the multimodal envelope"
- Source: doc: tools/AGENTS.md § Registry and discovery "accepts exactly that shape"

### Requirement: check_fn answers reachability per profile, TTL-cached
`check_fn` SHALL answer reachability/opt-in for the profile it runs under — never surface — reading credentials through the scoped secret reader (never bare `os.getenv`), with results TTL-cached process-wide keyed by the hermes-home scope key.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § Rules for tool code (check_fn paragraph; `_check_fn_cache` keyed by `hermes_home_key()`)
**Anchor**: `tools/registry.py:268` (`_check_fn_cache: dict[tuple[Callable, Optional[str]], ...]`), `tools/registry.py:23` (`hermes_home_key` import)

#### Scenario: check_fn answers for its profile, never surface
- **WHEN** a `check_fn` probe evaluates tool availability under a served profile
- **THEN** it SHALL answer reachability/opt-in for the profile it runs under, never surface
- **AND** the probe SHALL read credentials through `agent.secret_scope.get_secret`, since one process serves many sessions and many profiles
- Source: doc: tools/AGENTS.md § Rules for tool code "answers reachability/opt-in for the profile it runs under, never surface."
- Source: doc: tools/AGENTS.md § Rules for tool code "serves many sessions AND many profiles"

#### Scenario: Probe verdicts are TTL-cached per hermes home
- **WHEN** tool availability is re-evaluated within the cache TTL
- **THEN** the result SHALL come from the process-wide TTL cache keyed by `hermes_home_key()`
- Source: doc: tools/AGENTS.md § Rules for tool code "TTL-cached in `registry.py::_check_fn_cache` keyed by `hermes_home_key()`"
- Source: [relnote 2026.4.30] "memoized `get_tool_definitions()` with TTL-cached `check_fn` results"

### Requirement: Schema descriptions stay toolset-agnostic
A tool's schema description SHALL NOT name tools from other toolsets (they may be unavailable, inducing hallucinated calls); cross-references SHALL be added dynamically at definition-build time.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § Rules for tool code ("Cross-references are added dynamically in get_tool_definitions() in model_tools.py") — code: the rewriter table and availability-gated injection live in model_tools.py's Dynamic-schema-rewrite section
**Anchor**: `model_tools.py:358-361` (Dynamic schema rewrites header) — the invariant comment: 'Cross-references must use that set so the model never hears of an absent tool.'; `model_tools.py:479` (`_DYNAMIC_SCHEMA_REWRITERS`) — per-tool rewriters (execute_code, browser_cdp, browser_exec, delegate_task, …) that inject cross-references only for tools in the availability set; `model_tools.py:490` (`_apply_dynamic_schemas`) — applied at definition-build time inside `_compute_tool_definitions` (called at `model_tools.py:521`)

#### Scenario: Cross-references are injected at definition-build time, not in the schema
- **WHEN** a tool's description would name a tool from another toolset (e.g. a browser tool saying prefer web_search)
- **THEN** the schema SHALL NOT contain that reference — those tools may be unavailable (missing key, disabled toolset) and the model hallucinates calls to them
- **AND** cross-references are instead added dynamically in `get_tool_definitions()`
- Source: doc: tools/AGENTS.md § Rules for tool code "Schema descriptions must not name tools from other toolsets"
- Source: doc: tools/AGENTS.md § Rules for tool code "may be unavailable (missing key, disabled toolset)"
- Source: doc: tools/AGENTS.md § Rules for tool code "Cross-references are added dynamically in `get_tool_definitions()`"

### Requirement: Core-tool bar (Footprint Ladder); custom tools go through plugins
A new core tool requires the highest ladder rung justification (fundamental, broadly useful, unreachable otherwise); custom/local tooling SHALL be added as a plugin calling `ctx.register_tool(...)` with automatically discovered plugin toolsets, not by editing `tools/` or `toolsets.py`.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § "The core is a narrow waist" + Footprint ladder; doc: tools/AGENTS.md § "Adding a core tool"
**Anchor**: `hermes_cli/plugins.py:463` (`PluginContext.register_tool`)

#### Scenario: A new core tool must clear the highest rung
- **WHEN** a contributor proposes a new core tool
- **THEN** the bar is high, because every model tool is sent on every API call — a core tool must be fundamental, broadly useful, unreachable otherwise (top Footprint Ladder rung)
- Source: doc: AGENTS.md (root) § What Hermes Is "so the bar for a new *core* tool is high."
- Source: doc: AGENTS.md (root) § Contribution rubric "take the highest rung that solves it"

#### Scenario: Custom/local tooling goes through a plugin
- **WHEN** custom or local-only tooling is added
- **THEN** it SHALL NOT edit core: create a plugin and call `ctx.register_tool(...)`
- **AND** plugin toolsets are discovered automatically and toggled without touching `tools/` or `toolsets.py`
- Source: doc: tools/AGENTS.md § Adding a core tool "For custom/local-only tools do NOT edit core"
- Source: doc: tools/AGENTS.md § Adding a core tool "plugin toolsets are discovered automatically and"

### Requirement: Session/platform toolset reduction honors config
Session- and platform-level toolset configuration (`agent.disabled_toolsets`, e.g. `[browser]` for headless/Docker) SHALL be honored across desktop/TUI gateway surfaces; subset toolsets SHALL not silently strip tools the session still resolved (e.g. web_search after Blank Slate).
**Status**: VERIFIED
**Evidence**: [PR #44499](https://github.com/NousResearch/hermes-agent/pull/44499) — honor agent.disabled_toolsets in the desktop/TUI gateway; [PR #134593](https://github.com/NousResearch/hermes-agent/pull/134593) — stop subset toolset 'search' from stripping web_search after Blank Slate; doc: toolsets.py:106 comment — code: agent_factory forwards agent.disabled_toolsets on the TUI/desktop gateway; selection subtracts disabled last; tools_config clears covered subset entries
**Anchor**: `tui_gateway/agent_factory.py:446-454` (`_load_disabled_toolsets`) — reads `agent.disabled_toolsets`; docstring names #44499 ('the desktop/TUI gateway historically dropped it… disabled_toolsets: [browser] silently had no effect on Desktop') and it is forwarded at :670; `model_tools.py:349-354` (`_select_tool_names`) — 'Disabled toolsets are always subtracted LAST… any tools belonging to a disabled toolset are strictly stripped out' (#17309); `hermes_cli/tools_config.py:826-832` (`_covered`) — the #134593 subset-cleanup: a disabled entry whose tools are fully covered by a newly enabled toolset (Blank Slate's `search` after enabling `web`) is cleared so `web_search` is not left stripped

#### Scenario: Disabling one platform bundle spares the others
- **WHEN** `disabled_toolsets` names a platform bundle (e.g. `hermes-yuanbao`) while another bundle (e.g. `hermes-telegram`) stays enabled
- **THEN** the enabled bundle's tool surface SHALL be unchanged — disabling a different platform bundle must not remove any tools
- Source: test: tests/tools/test_model_tools.py::TestDisabledToolsetsPlatformBundle::test_disabling_platform_bundle_preserves_core_tools

#### Scenario: Disabling `browser` keeps `web_search`
- **WHEN** `disabled_toolsets: [browser]` is set (natural in headless/Docker with no Chromium) and the session still resolves `web`/`search`
- **THEN** `web_search` SHALL NOT be stripped — it must not be a member of the `browser` toolset, since `disabled_toolsets` is a strict subtraction
- Source: test: tests/tools/test_model_tools.py::TestDisabledToolsetsPlatformBundle::test_disabling_browser_keeps_web_search_when_web_enabled

### Requirement: Session-platform-gated toolsets
A toolset SHALL declare the session platforms it exists for (`platforms=` in its spec → `TOOLSET_SESSION_PLATFORMS`), and a session on any other platform SHALL have those tools dropped via `session_platform_tool_drops()` — surface availability is a property of the session, not of the process env.
**Status**: VERIFIED
**Evidence**: doc: tools/AGENTS.md § "Surface capability is a property of the SESSION, never of the process env"; supersedes the removed role grant (see Known gaps drift note, #119491)
**Anchor**: `toolsets.py:143` (`onboarding` toolset, `platforms=frozenset({"desktop"})`), `toolsets.py:244` (`TOOLSET_SESSION_PLATFORMS` derived from specs), `toolsets.py:449` (`session_platform_tool_drops`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A toolset SHALL declare the session platforms it exists for (`platforms=` in its spec → `TOOLSET_SESSION_PLATFORMS`), and a session on any other platform SHALL have those tools dropped via `session_platform_tool_drops()` — surface availability is a property of the session, not of the process env.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Shared argument repair for inline tools
Inline agent tools (clarify, todo, memory, session_search) SHALL go through the same shared argument-repair path as registry tools.
**Status**: VERIFIED
**Evidence**: [PR #127781](https://github.com/NousResearch/hermes-agent/pull/127781) — "Inline agent tools get the shared argument repair" — code: INLINE_TOOL_EXECUTORS wraps every entry in coerce_tool_args, the same call handle_function_call makes (a2840f954b, #127781)
**Anchor**: `agent/inline_tool_executors.py:307-315` (`_coerced` / `INLINE_TOOL_EXECUTORS`) — every inline executor (todo_list, memory, session_search, clarify, …) is wrapped so `coerce_tool_args(name, args)` runs before it; `model_tools.py:902` (`handle_function_call`) — the registry dispatch path applies the same `coerce_tool_args(function_name, function_args)`; `tools/arg_coercion.py:21` (`coerce_tool_args`) — the single shared repair/coercion implementation (imported at `agent/inline_tool_executors.py:17`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Inline agent tools (clarify, todo, memory, session_search) SHALL go through the same shared argument-repair path as registry tools.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Pruned spill archives read as expired
Reading a pruned tool-result spill archive SHALL report "expired", and spill pointers appearing inside structured content and Windows paths SHALL count as references (kept out of pruning).
**Status**: VERIFIED
**Evidence**: [PR #126351](https://github.com/NousResearch/hermes-agent/pull/126351) — "read_file on a pruned spill archive says 'expired'"; "spill pointers in structured content and Windows paths count as references" — code: expired_archive_fields merged into read_file misses; backslash separators + instr() scan make structured/Windows pointers owned
**Anchor**: `tools/tool_result_storage.py:80-89` (`expired_archive_fields`) — an archive-shaped path returns `{"expired": True, "hint": …}` 'instead of a generic miss' (#126351); plain misses get {} (no expired flag); `tools/file_tools.py:691-692` — read_file's not-found branch merges `expired_archive_fields(path)` into the result; `tools/tool_result_storage.py:71-74` (`_SPILLOVER_NAME_RE`, `SPILLOVER_SQL_FILTER`) — pointer regex accepts backslashed (Windows) separators and the SQL filter uses instr() so structured content behind the NUL sentinel still counts as a reference

#### Scenario: A pruned spill archive reads as expired
- **WHEN** `read_file` targets a spill archive that has been pruned
- **THEN** the result SHALL report expired (`expired: true` with an expired hint) rather than a generic file miss
- **AND** a plain missing file still reads as a plain miss
- Source: test: tests/tools/test_tool_result_storage.py::TestSpillover::test_read_file_on_pruned_archive_says_expired

#### Scenario: Structured and Windows-path spill pointers count as references
- **WHEN** a retained session references a spill archive from structured content or a backslashed (Windows) path
- **THEN** the age sweep SHALL never delete a referenced archive
- Source: test: tests/test_session_spillover_cleanup.py::test_structured_and_backslashed_pointers_are_owned

### Requirement: Tool-name resolution is process-global and fenced around children
`_last_resolved_tool_names` in `model_tools.py` is a process-global; subagent execution SHALL save/restore it so delegated children do not poison the parent's resolved surface (and readers may see temporarily stale values during child runs).
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants (names `_run_single_child()` in `tools/delegate_tool.py`)
**Anchor**: `model_tools.py:175` (`_last_resolved_tool_names: list[str] = []`)

#### Scenario: Delegation children restore the parent's resolved surface
- **WHEN** a delegated child runs (`_run_single_child()`)
- **THEN** it SHALL save/restore the process-global `_last_resolved_tool_names` around child runs, so children do not poison the parent's resolved surface
- **AND** readers may see it stale mid-delegation
- Source: doc: tools/AGENTS.md § Rules for tool code "is a process-global in `model_tools.py`"
- Source: doc: tools/AGENTS.md § Rules for tool code "saves/restores it around child runs"
- Source: doc: tools/AGENTS.md § Rules for tool code "readers may see it stale mid-delegation."

### Requirement: Stable tool-row identity for display
Tool rows SHALL be keyed on stable tool identity rather than payload bytes for display identity, so providers reusing tool-call ids do not overwrite finished rows.
**Status**: VERIFIED
**Evidence**: [PR #117750](https://github.com/NousResearch/hermes-agent/pull/117750) — "key display identity of tool rows on stable tool identity, not payload bytes"; related desktop-side #128009/#128003 (desktop capability excluded) — code: _stable_tool_key keys display dedupe on tool_call ids; payload-content key only as the id-less fallback
**Anchor**: `hermes_state_identity.py:99-111` (`_stable_tool_key`) — display-dedupe key of a tool-calling assistant row built from stable call ids 'instead of the arguments a prune rewrites' (#117750); None when the id set is incomplete; `hermes_state_messages.py:1106-1117` (`_display_dedupe_key`) — `return _stable_tool_key(row) or (role, dedupe_content, …)`: identity rows never fall back to payload bytes; id-less rows keep the full content key so distinct calls never merge

#### Scenario: A pruned copy is displayed next to its original
- **WHEN** the display layer dedupes a pruned carried-forward tool row against its durable original
- **THEN** the key is built "from its stable call ids instead of the arguments a prune rewrites", so the pair collapses (#117750)
- Source: doc: hermes_state_identity.py:100 (`_stable_tool_key` docstring) — "instead of the arguments a prune rewrites"
**Sub-area: Tail fold (commits after 2026-10-27)**

### Requirement: The live session's tool surface stays frozen; the definitions memo expires with its verdicts
The tool list presented to a session SHALL stay frozen for that session even when a `check_fn` verdict flips back or a pin is restored; the memoized tool-definitions cache SHALL expire with its `check_fn` verdicts (and a grace/reuse window for a verdict starts when the probe returns).
**Status**: VERIFIED
**Evidence**: [commit 7aca8caeafb1] — keep a live session's tools[] frozen when a check_fn flips back; [commit 9b839d815eb1] — expire the tool-definitions memo with its check_fn verdicts; [commit b9e983665c7a] — key the tools[] freeze on generation and selection, hold flips on pin restore; [commit c49a94bee193] — keep a pinned Tool Search bridge on a same-process pin restore; [commit c2dac477f58e] — start the check_fn grace reuse window when the probe returns — code: freeze keyed on built-generation + selection in mcp_tool_agent; memo deadline = earliest verdict expiry; grace window stamped at probe return
**Anchor**: `tools/mcp_tool_agent.py:100-107` (`_publish_tool_snapshot`) — freeze keyed on generation and selection: 'neither the registry … nor the toolset selection moved … a name can only be new because a check_fn flipped, and tools[] stays frozen' (#101367); pin table at :19-24; `model_tools.py:219-224,252-264` (`_live_tool_defs_entry`, `get_tool_definitions`) — the memo expires at the earliest check_fn verdict deadline (`_tool_defs_expiry[cache_key] = verdict_expiry[0]` from `check_fn_verdict_window()`); `tools/registry.py:402-408,416` (`_check_fn_cached`) — 'Stamped at completion': the grace/reuse timestamps (`_check_fn_last_good`, `_CHECK_FN_GRACE_REUSE_SECONDS`) are taken when the probe returns, not when it starts

#### Scenario: Resume and hops keep the same tool list
- **WHEN** a session resumes (`-q --resume`) or hops between TUI and gateway
- **THEN** the tool list SHALL remain frozen for that session
- **AND** swapping toolsets mid-conversation is forbidden because it breaks the cached prefix
- Source: [relnote 0.22.0] "the tool list is frozen per session across TUI, `-q --resume` and gateway hops."
- Source: doc: AGENTS.md (root) § What Hermes Is "Mutating past context, swapping toolsets,"
- Source: doc: AGENTS.md (root) § What Hermes Is "breaks the cached prefix"

### Requirement: browser_exec binds its daemon socket to a kernel-acceptable path under a deep HOME
`browser_exec` SHALL bind its harness daemon socket under a short private dir when the Hermes home is too deep for the socket path limit, claiming an existing short dir only when it is private and real.
**Status**: VERIFIED
**Evidence**: [commit 92e8a6398d8c] — browser_exec binds its daemon socket under a deep HOME — code: fit_default_socket_dir re-homes the daemon socket to a claimed 0700 short dir when the budget is exceeded
**Anchor**: `tools/browser_harness_dirs.py:98-117` (`fit_default_socket_dir`) — under a deep HOME the default `<home>/runtime/bu-<BU_NAME>.sock` overflows sun_path, so the call's runtime dir moves to a private short dir; called from browser_exec's env build at `tools/browser_use_cli.py:809`; `tools/browser_harness_dirs.py:170-186` (`claim_private_dir`) — an existing dir is accepted only as a real (non-symlink) directory owned by this uid with no group/other access (0700); `tools/browser_harness_dirs.py:25-26,46-53` (`_LINUX_SOCKET_DIR_BUDGET`, `socket_dir_budget`) — the kernel sun_path budgets (Linux 108 / macOS 104 incl. NUL) minus the bu-<64-char>.sock suffix

#### Scenario: Deep HOME still gets a working daemon socket
- **WHEN** the Hermes home is deep enough that the default socket path exceeds the kernel limit
- **THEN** the harness SHALL use a daemon socket path the kernel accepts
- **AND** a pre-existing short dir is claimed only when it is private and real
- Source: test: tests/tools/test_browser_harness_default_socket.py::test_a_deep_home_gets_a_daemon_socket_the_kernel_accepts
- Source: test: tests/tools/test_browser_harness_default_socket.py::test_an_existing_short_dir_is_claimed_only_when_private_and_real

### Requirement: A too-deeply nested tool result still completes the tool event
A tool result nested beyond the normal depth SHALL still deliver its `tool.complete` event instead of being dropped.
**Status**: VERIFIED
**Evidence**: [commit 9aea04c329fd] — a too-deeply nested tool result no longer drops tool.complete — code: safe_json_loads now swallows RecursionError, fixing every tool-event parse caller
**Anchor**: `utils.py:679-684` (`safe_json_loads`) — catches RecursionError alongside JSONDecodeError/TypeError/ValueError, docstring: 'returning *default* on any parse error (a too-deeply nested body included)' (9aea04c329fd); `agent/terminal_image.py:374-377` (`tool_image_path`) — a tool event's result-parse site routes through safe_json_loads, so a deep-nest result degrades to no-image instead of raising out of the tool.complete handler

#### Scenario: A pathologically nested result reaches a display parser
- **WHEN** a tool-event parse site feeds `safe_json_loads` a body nested too deeply for the JSON parser
- **THEN** it returns the default ("a too-deeply nested body included") — RecursionError is caught — so the tool event completes degraded instead of raising
- Source: doc: utils.py:680 (`safe_json_loads` docstring) — "returning *default* on any parse error (a too-deeply nested body included)"
## Known gaps / open questions
- `registry.register()` signature/behavior at line level not opened (grep showed `register_toolset_alias` at :595 and the class region only); VERIFIED claims lean on AGENTS.md + the opened cache/normalizer/discovery lines.
- MCP tool availability unification (#119644 "installed plugins' MCP tools ... live in every open chat", #119601 shared enabled-flag reader) is a plugins×tools contract owned by the deferred plugins-mcp capability — excluded here, boundary noted.
- Terminal/browser tool behavior contracts (`tools/environments/` backends) not drafted — sub-capability candidate for pass 2.
- Truncated/lost tool-call recovery contracts (#72770 max_tokens boost, #101899 arg fragments glued to bare tool name, #102766 clean-EOF retry) are agent-loop/tool-round hybrids — drafted under agent-turn-loop's recovery gap list instead; ownership TBD.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.

## Scenario-ification notes
- REQ "Role-gated setup toolset": no doc-grounded trigger; kept as invariant. (#119491's wording exists only as a bundle commit title; no release note, in-repo doc, or test names the role grant.)
- REQ "Shared argument repair for inline tools": no doc-grounded trigger; kept as invariant. (tests/agent/test_repair_tool_call_arguments.py pins the shared repair path itself, not the inline-tool membership claim; PR #127781 is not in any release-note body.)
- REQ "Stable tool-row identity for display": no doc-grounded trigger; kept as invariant. (#117750 absent from release-note bodies; the adjacent reused-tool-call-ids bullets (#128003/#131758, relnote 0.22.0) are desktop-side and excluded by ownership.)
- Tail req "A too-deeply nested tool result still completes the tool event": commit-only evidence; no Tier A/B/C trigger+outcome pair found.
- Tail items rejected (out of capability ownership): desktop tool-row/reasoning-render items (#128009, #128003, #126479, #107386, #118271), TUI/terminal inline-image rendering tail commits (2026-11-04 cluster: kitty image ids, half-block painter, iTerm2 sizing, inline image cache — display/TUI surface), terminal-backend PATH/login-shell tail commits (29fef14fbf35, 6fa171ce5423, 35c2783b6ab7 — tools/environments backends sub-capability), Sprites backend docs (docs/website), plugin-catalog re-pins (a6cdad3e9fb6, fa830bef1db1), browser CDP URL-scan/interception details (09d2e686f9b8, e20007e4e7c0, 1c11a23f0f61 — browser sub-capability), test-infra chores.
- Doc-vs-code surprise (flagged, not fixed): 2026-3.23 release note reports disabled toolsets re-enabling themselves after `hermes tools` (#2268) — a historical violation of the session/platform reduction invariant; current behavior is pinned only at the toolset-resolution layer by tests, not by user docs.
- Drift (pass 3): the role-based setup toolset grant (#119491, a pass-2 requirement) does NOT exist at the pin — c3f85bc54f "delete profile role; the setup profile is a marked, plain profile" (2026-09-29), then b120ac575d (2026-10-13) removed the setup-profile machinery. Surviving mechanism is session-platform-gated toolsets (`toolsets.py` `TOOLSET_SESSION_PLATFORMS`); requirement rewritten to that.
