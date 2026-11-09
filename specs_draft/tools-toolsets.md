# Capability: tools-toolsets

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Summary
The model-tool surface: `tools/registry.py` (dependency-free registry with import-time self-registration and auto-discovery), `toolsets.py` (the TOOLSETS dict and `_HERMES_CORE_TOOLS` default bundle), and `model_tools.py` (schema collection, dispatch via `handle_function_call()`, per-session resolution). Governed by the project's "narrow waist" invariant: every model tool is sent on every API call, so new core tools face a high bar (Footprint Ladder).

## Primary code locations
- `tools/registry.py` — registry, discovery, check_fn cache, result normalization
- `toolsets.py` — `_HERMES_CORE_TOOLS` (line 11), toolset composition, session-disabled toolsets
- `model_tools.py` — orchestration, `handle_function_call()` (line 886), dynamic cross-references
- `tools/AGENTS.md` — normative rules for adding tools; long-form `website/docs/developer-guide/adding-tools.md`

## Requirements

### Requirement: Import-time registry self-registration with auto-discovery
Every `tools/*.py` with a top-level `registry.register()` SHALL be imported and registered automatically (no manual import list); package-style tools SHALL register from `tools/<pkg>/tool.py`, the only file scanned inside a package, and a package lacking `__init__.py` SHALL be skipped with a warning.
- Status: VERIFIED
- Evidence: doc: tools/AGENTS.md § Registry and discovery
- Anchor: `tools/registry.py:121` (`discover_builtin_tools`)

### Requirement: Toolset membership gates exposure
Registering a schema SHALL not expose a tool: a tool is model-visible only if a toolset names it; `_HERMES_CORE_TOOLS` is the default bundle every platform's base toolset inherits.
- Status: VERIFIED
- Evidence: doc: tools/AGENTS.md § "Adding a core tool" step 2 ("Required — a tool is only exposed if a toolset names it")
- Anchor: `toolsets.py:11` (`_HERMES_CORE_TOOLS = [`), `toolsets.py:54` (toolset = core + extras)

### Requirement: JSON-string handler contract with a single multimodal exception
All tool handlers SHALL return a JSON string, except a tool returning pixels, which MAY return the exact envelope `{"_multimodal": True, "content": [...], "text_summary": str}` accepted by the registry's result normalizer; the normalizer SHALL accept exactly that shape.
- Status: VERIFIED
- Evidence: doc: tools/AGENTS.md § Registry and discovery
- Anchor: `tools/registry.py:955` (`_normalize_handler_result`), `tools/registry.py:963` (`"_multimodal" is True` check)

### Requirement: check_fn answers reachability per profile, TTL-cached
`check_fn` SHALL answer reachability/opt-in for the profile it runs under — never surface — reading credentials through the scoped secret reader (never bare `os.getenv`), with results TTL-cached process-wide keyed by the hermes-home scope key.
- Status: VERIFIED
- Evidence: doc: tools/AGENTS.md § Rules for tool code (check_fn paragraph; `_check_fn_cache` keyed by `hermes_home_key()`)
- Anchor: `tools/registry.py:268` (`_check_fn_cache: dict[tuple[Callable, Optional[str]], ...]`), `tools/registry.py:23` (`hermes_home_key` import)

### Requirement: Schema descriptions stay toolset-agnostic
A tool's schema description SHALL NOT name tools from other toolsets (they may be unavailable, inducing hallucinated calls); cross-references SHALL be added dynamically at definition-build time.
- Status: INFERRED
- Evidence: doc: tools/AGENTS.md § Rules for tool code ("Cross-references are added dynamically in get_tool_definitions() in model_tools.py")
- Anchor: `model_tools.py` (get_tool_definitions post-processing blocks — lines not opened)

### Requirement: Core-tool bar (Footprint Ladder); custom tools go through plugins
A new core tool requires the highest ladder rung justification (fundamental, broadly useful, unreachable otherwise); custom/local tooling SHALL be added as a plugin calling `ctx.register_tool(...)` with automatically discovered plugin toolsets, not by editing `tools/` or `toolsets.py`.
- Status: VERIFIED
- Evidence: doc: AGENTS.md (root) § "The core is a narrow waist" + Footprint ladder; doc: tools/AGENTS.md § "Adding a core tool"
- Anchor: `hermes_cli/plugins.py:463` (`PluginContext.register_tool`)

### Requirement: Session/platform toolset reduction honors config
Session- and platform-level toolset configuration (`agent.disabled_toolsets`, e.g. `[browser]` for headless/Docker) SHALL be honored across desktop/TUI gateway surfaces; subset toolsets SHALL not silently strip tools the session still resolved (e.g. web_search after Blank Slate).
- Status: INFERRED
- Evidence: [PR #44499](https://github.com/NousResearch/hermes-agent/pull/44499) — honor agent.disabled_toolsets in the desktop/TUI gateway; [PR #134593](https://github.com/NousResearch/hermes-agent/pull/134593) — stop subset toolset 'search' from stripping web_search after Blank Slate; doc: toolsets.py:106 comment
- Anchor: `toolsets.py:455` (`session_disabled_toolsets`) — behavior PRs cited, line opened for the helper only

### Requirement: Role-gated setup toolset
Setup profile sessions SHALL get the setup toolset by profile role, and no other configuration path SHALL be able to grant it.
- Status: INFERRED
- Evidence: [PR #119491](https://github.com/NousResearch/hermes-agent/pull/119491) — "setup profile sessions get the setup toolset by profile role; nothing else can grant it"
- Anchor: not located

### Requirement: Shared argument repair for inline tools
Inline agent tools (clarify, todo, memory, session_search) SHALL go through the same shared argument-repair path as registry tools.
- Status: INFERRED
- Evidence: [PR #127781](https://github.com/NousResearch/hermes-agent/pull/127781) — "Inline agent tools get the shared argument repair"
- Anchor: not located (boundary with agent-turn-loop's inline executor table)

### Requirement: Pruned spill archives read as expired
Reading a pruned tool-result spill archive SHALL report "expired", and spill pointers appearing inside structured content and Windows paths SHALL count as references (kept out of pruning).
- Status: INFERRED
- Evidence: [PR #126351](https://github.com/NousResearch/hermes-agent/pull/126351) — "read_file on a pruned spill archive says 'expired'"; "spill pointers in structured content and Windows paths count as references"
- Anchor: not located (`tools/tool_result_storage.py` implied by hermes_state_media.py import)

### Requirement: Tool-name resolution is process-global and fenced around children
`_last_resolved_tool_names` in `model_tools.py` is a process-global; subagent execution SHALL save/restore it so delegated children do not poison the parent's resolved surface (and readers may see temporarily stale values during child runs).
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Message-flow invariants (names `_run_single_child()` in `tools/delegate_tool.py`)
- Anchor: `model_tools.py:175` (`_last_resolved_tool_names: list[str] = []`)

### Requirement: Stable tool-row identity for display
Tool rows SHALL be keyed on stable tool identity rather than payload bytes for display identity, so providers reusing tool-call ids do not overwrite finished rows.
- Status: INFERRED
- Evidence: [PR #117750](https://github.com/NousResearch/hermes-agent/pull/117750) — "key display identity of tool rows on stable tool identity, not payload bytes"; related desktop-side #128009/#128003 (desktop capability excluded)
- Anchor: not located (state/display boundary)

## Known gaps / open questions
- `registry.register()` signature/behavior at line level not opened (grep showed `register_toolset_alias` at :595 and the class region only); VERIFIED claims lean on AGENTS.md + the opened cache/normalizer/discovery lines.
- MCP tool availability unification (#119644 "installed plugins' MCP tools ... live in every open chat", #119601 shared enabled-flag reader) is a plugins×tools contract owned by the deferred plugins-mcp capability — excluded here, boundary noted.
- Terminal/browser tool behavior contracts (`tools/environments/` backends) not drafted — sub-capability candidate for pass 2.
- Truncated/lost tool-call recovery contracts (#72770 max_tokens boost, #101899 arg fragments glued to bare tool name, #102766 clean-EOF retry) are agent-loop/tool-round hybrids — drafted under agent-turn-loop's recovery gap list instead; ownership TBD.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
