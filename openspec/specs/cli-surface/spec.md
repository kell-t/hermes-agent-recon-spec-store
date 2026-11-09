# Capability: cli-surface

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
The classic CLI and its command system: `cli.py` hosts `HermesCLI` (REPL loop, config merge, slash dispatch) assembled from ~18 `hermes_cli/cli_*_mixin.py` behavior mixins plus topical siblings; one slash-command registry (`hermes_cli/commands.py`) is the single source of truth for CLI dispatch, gateway dispatch, platform command menus, and help. `hermes` subcommands (gateway, skills, cron, pm, ...) live in `hermes_cli/`. The `hermes gateway` facade owns process discovery and service unit generation.

## Primary code locations
- `cli.py` — HermesCLI (line 881), `_SLASH_DISPATCH` (line 1119), `load_cli_config()`
- `hermes_cli/commands.py` — `CommandDef`/registry, `resolve_command()`, `GATEWAY_KNOWN_COMMANDS`
- `hermes_cli/cli_*_mixin.py` — behavior mixins; siblings late-bind via `from cli import ...`
- `hermes_cli/cli_single_query.py` — `-q` non-interactive runner
- `hermes_cli/gateway.py` + `gateway_*.py` — `hermes gateway` facade
- `hermes_cli/AGENTS.md` — area law; long-form `website/docs/developer-guide/cli-internals.md`

## Requirements

### Requirement: One slash-command registry drives every surface
`COMMAND_REGISTRY` of `CommandDef` SHALL be the single source for CLI dispatch (`resolve_command()`), gateway `GATEWAY_KNOWN_COMMANDS` and dispatch, `telegram_bot_commands()`, `slack_subcommand_map()`, autocomplete and categorized help; fields SHALL include `name`, `description`, `category`, `aliases`, `args_hint`, `cli_only`, `gateway_only`, `gateway_config_gate`.
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § Slash command registry
**Anchor**: `hermes_cli/commands.py:45` (`class CommandDef`), `hermes_cli/commands.py:55` (`gateway_config_gate` field), `hermes_cli/commands.py:402` (`resolve_command`), `hermes_cli/commands.py:465` (`GATEWAY_KNOWN_COMMANDS`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `COMMAND_REGISTRY` of `CommandDef` SHALL be the single source for CLI dispatch (`resolve_command()`), gateway `GATEWAY_KNOWN_COMMANDS` and dispatch, `telegram_bot_commands()`, `slack_subcommand_map()`, autocomplete and categorized help;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Config-gated command visibility
A `cli_only` command with a truthy `gateway_config_gate` dotpath SHALL become gateway-dispatchable, and menus/help SHALL show gated commands only when their gate is open (dispatch always knows them).
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § Slash command registry (`gateway_config_gate` semantics)
**Anchor**: `hermes_cli/commands.py:211` (example gate `display.tool_progress_command`), `hermes_cli/commands.py:256` (gate `skills.write_approval`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A `cli_only` command with a truthy `gateway_config_gate` dotpath SHALL become gateway-dispatchable, and menus/help SHALL show gated commands only when their gate is open (dispatch always knows them).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Table/naming-convention dispatch, no elif ladders
Slash dispatch SHALL resolve the canonical name then look up `_SLASH_DISPATCH` (`canonical -> (method name, pass_arg)`), falling back to a `_handle_<name>_command` method by naming convention; `elif` ladders for command dispatch are forbidden.
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture ("There is no elif ladder — do not add one")
**Anchor**: `cli.py:1119` (`_SLASH_DISPATCH: dict[str, tuple[str, bool]]`), `cli.py:1143` (entry lookup)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Slash dispatch SHALL resolve the canonical name then look up `_SLASH_DISPATCH` (`canonical -> (method name, pass_arg)`), falling back to a `_handle_<name>_command` method by naming convention;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Behavior lives in mixins; late binding preserves patch seams
CLI behavior SHALL live in `cli_*_mixin.py` mixins on `HermesCLI`; moved bodies SHALL late-bind cli-level names via `from cli import ...` at call time so monkeypatching the `cli` facade intercepts them, while mutable module state stays in `cli.py`.
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (facade + siblings law)
**Anchor**: `cli.py:881` (`class HermesCLI(CLIBacktrackMixin, CLIInitMixin, ...)` — the mixin assembly itself)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** CLI behavior SHALL live in `cli_*_mixin.py` mixins on `HermesCLI`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: System-prompt-changing slash commands defer to the next session
Slash commands that change system-prompt state SHALL defer their effect to the next session by default (prompt-caching invariant), with an explicit opt-in `--now` variant (e.g. `/skills install --now`).
**Status**: INFERRED
**Evidence**: doc: AGENTS.md (root) § "What Hermes Is" ("Slash commands that change system-prompt state defer to the next session, with an opt-in --now (/skills install --now)")
**Anchor**: not located (`--now` parse site not found in agent/skill_commands.py or commands.py by grep)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Slash commands that change system-prompt state SHALL defer their effect to the next session by default (prompt-caching invariant), with an explicit opt-in `--now` variant (e.g.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Non-interactive single-query mode
The CLI SHALL provide `-q` single-query execution (`hermes -q "..."`) with defined exit codes for scripted/headless use (`cli_single_query.py`).
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (`cli_single_query.py` (-q runner, exit codes, kanban loops))
**Anchor**: `hermes_cli/cli_single_query.py` (module exists; not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The CLI SHALL provide `-q` single-query execution (`hermes -q "..."`) with defined exit codes for scripted/headless use (`cli_single_query.py`).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Interactive pickers use curses; display code avoids erase-to-EOL
Interactive menu pickers SHALL use the curses UI helper, and spinner/display code SHALL NEVER emit `\033[K` (it leaks as literal `?[K` under prompt_toolkit `patch_stdout`) — space-padding instead.
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § Rules ("all interactive menu-pickers use curses"; no-`\033[K` rule)
**Anchor**: not located (`hermes_cli/curses_ui.py` named by doc)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Interactive menu pickers SHALL use the curses UI helper, and spinner/display code SHALL NEVER emit `\033[K` (it leaks as literal `?[K` under prompt_toolkit `patch_stdout`) — space-padding instead.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Gateway process management via facade with platform backends
`hermes gateway` SHALL manage gateway processes through its facade — process discovery, PM-aware systemd unit generation/refresh, launchd (macOS) and Windows backends, supervised restart, migration, multiplex helpers — with siblings reading facade names late (`_gw()`).
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (`hermes_cli/gateway.py` facade + named siblings); [PR #139041](https://github.com/NousResearch/hermes-agent/pull/139041) — `hermes update` drain stays reachable for a parked approval/clarify (update/gateway drain boundary, drafted there too)
**Anchor**: `hermes_cli/gateway.py` (facade exists; dispatch lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `hermes gateway` SHALL manage gateway processes through its facade — process discovery, PM-aware systemd unit generation/refresh, launchd (macOS) and Windows backends, supervised restart, migration, multiplex helpers — with siblings reading facade names late (`_gw()`).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: First-run surfaces reach their own setup
A blank install on any interactive surface (e.g. TUI) SHALL reach its own setup screen rather than dead-ending (onboarding reachability).
**Status**: INFERRED
**Evidence**: [PR #128663](https://github.com/NousResearch/hermes-agent/pull/128663) — "blank-install TUI reaches its own setup screen"; [PR #129200](https://github.com/NousResearch/hermes-agent/pull/129200) — quick tour covers the model picker
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A blank install on any interactive surface (e.g.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Connection cards render on the classic CLI
Connection/approval cards (e.g. `manage_connections`) SHALL be available on the classic CLI, not only desktop.
**Status**: INFERRED
**Evidence**: [PR #142039](https://github.com/NousResearch/hermes-agent/pull/142039) — "bring the manage_connections card back to the classic CLI"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Connection/approval cards (e.g.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Extension points over overrides
Wrapper CLIs SHALL extend the REPL through the protected hooks in `cli_tui_mixin.py` (per `website/docs/developer-guide/extending-the-cli.md`) rather than overriding `run()`.
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § Rules ("Wrapper CLIs extend via the protected hooks")
**Anchor**: `hermes_cli/cli_tui_mixin.py` (module exists; hooks not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Wrapper CLIs SHALL extend the REPL through the protected hooks in `cli_tui_mixin.py` (per `website/docs/developer-guide/extending-the-cli.md`) rather than overriding `run()`.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- `--now` deferral opt-in: root doc asserts it; implementation site not located — UNVERIFIED exact semantics (which commands, how state is staged).
- Updater (`hermes update`) contracts (autostash preservation #124641, drain reachability #139041) sit at the deferred update-packaging boundary — deliberately not drafted here.
- `hermes pm` / dependency-manager CLI: deferred packaging scope.
- CLI bundle is noisy: top hits were desktop/telegram fixes (keyword false positives) — only genuine CLI items drafted; cluster regex needs tightening for pass 2 (`\bcli\b` over-matches).
- `hermes_cli/web_routers/` + dashboard SPA excluded (tui-web deferred).
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
