# Capability: cli-surface

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (scenario grounding + tail fold) applied 2026-11-08.

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

#### Scenario: A maintainer adds a command alias
- **WHEN** an alias is added to a `CommandDef`'s `aliases` tuple
- **THEN** "every surface updates automatically" — no per-surface edit is needed
- Source: doc: hermes_cli/AGENTS.md § Slash command registry "**Adding an alias** = add to `aliases`" ("surface updates automatically")

#### Scenario: A surface needs the command list
- **WHEN** CLI dispatch, gateway dispatch/`GATEWAY_KNOWN_COMMANDS`, `telegram_bot_commands()`, `slack_subcommand_map()`, autocomplete or categorized help needs the command set
- **THEN** it is derived: "`COMMAND_REGISTRY` (list of `CommandDef`) is the single source; everything derives from it"
- Source: doc: hermes_cli/AGENTS.md § Slash command registry "is the single source; everything derives from it"

### Requirement: Config-gated command visibility
A `cli_only` command with a truthy `gateway_config_gate` dotpath SHALL become gateway-dispatchable, and menus/help SHALL show gated commands only when their gate is open (dispatch always knows them).
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § Slash command registry (`gateway_config_gate` semantics)
**Anchor**: `hermes_cli/commands.py:211` (example gate `display.tool_progress_command`), `hermes_cli/commands.py:256` (gate `skills.write_approval`)

#### Scenario: A gated cli_only command becomes gateway-usable
- **WHEN** a `cli_only` command carries a `gateway_config_gate` config dotpath and that gate is truthy
- **THEN** the command is "gateway-available when truthy", and `GATEWAY_KNOWN_COMMANDS` "always includes gated commands so the" gateway can dispatch them
- AND help/menus "show them only when the gate is open"
- Source: doc: hermes_cli/AGENTS.md § Slash command registry "gateway-available when truthy" / "help/menus show them only when the gate is open"; test: tests/hermes_cli/test_commands.py::TestGatewayKnownCommands::test_includes_config_gated_cli_only; tests/hermes_cli/test_commands.py::TestGatewayHelpLines::test_excludes_cli_only_commands_without_config_gate

### Requirement: Table/naming-convention dispatch, no elif ladders
Slash dispatch SHALL resolve the canonical name then look up `_SLASH_DISPATCH` (`canonical -> (method name, pass_arg)`), falling back to a `_handle_<name>_command` method by naming convention; `elif` ladders for command dispatch are forbidden.
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture ("There is no elif ladder — do not add one")
**Anchor**: `cli.py:1119` (`_SLASH_DISPATCH: dict[str, tuple[str, bool]]`), `cli.py:1143` (entry lookup)

#### Scenario: A slash command is dispatched
- **WHEN** `process_command()` handles a slash command
- **THEN** it resolves the canonical name via `resolve_command()` and dispatches through `HermesCLI._SLASH_DISPATCH` (`canonical -> (method name, pass_arg)`), "falling back to a" `_handle_<name>_command` method by naming convention
- AND "There is no `elif` ladder — do not add one."
- Source: doc: hermes_cli/AGENTS.md § CLI architecture "There is no `elif` ladder — do not add one."

#### Scenario: An unknown command reaches the dispatch table
- **WHEN** the dispatched name is not in the table
- **THEN** dispatch falls through (no crash inside the table lookup)
- Source: test: tests/hermes_cli/test_slash_dispatch_table.py::test_unknown_command_falls_through

### Requirement: Behavior lives in mixins; late binding preserves patch seams
CLI behavior SHALL live in `cli_*_mixin.py` mixins on `HermesCLI`; moved bodies SHALL late-bind cli-level names via `from cli import ...` at call time so monkeypatching the `cli` facade intercepts them, while mutable module state stays in `cli.py`.
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (facade + siblings law)
**Anchor**: `cli.py:881` (`class HermesCLI(CLIBacktrackMixin, CLIInitMixin, ...)` — the mixin assembly itself)

#### Scenario: Behavior moves out of cli.py
- **WHEN** a body is moved from `cli.py` into a mixin or topical sibling
- **THEN** it late-binds cli-level names "via `from cli import ...` at call time, so patch seams on the" `cli` facade still intercept them
- AND mutable module state and "every `global`-writing function stay in `cli.py`"
- Source: doc: hermes_cli/AGENTS.md § CLI architecture "via `from cli import ...` at call time" / "and every `global`-writing function stay in `cli.py`"

### Requirement: System-prompt-changing slash commands defer to the next session
Slash commands that change system-prompt state SHALL defer their effect to the next session by default (prompt-caching invariant), with an explicit opt-in `--now` variant (e.g. `/skills install --now`).
**Status**: INFERRED
**Evidence**: doc: AGENTS.md (root) § "What Hermes Is" ("Slash commands that change system-prompt state defer to the next session, with an opt-in --now (/skills install --now)")
**Anchor**: not located (`--now` parse site not found in agent/skill_commands.py or commands.py by grep)

#### Scenario: A slash command mutates system-prompt state
- **WHEN** a slash command changes system-prompt state
- **THEN** it "defer[s] to the next session" (prompt-caching invariant), "with an opt-in `--now` (`/skills install --now`)"
- Source: doc: AGENTS.md (root) § What Hermes Is "defer to the next session, with an opt-in `--now` (`/skills install --now`)"; doc: hermes_cli/AGENTS.md § Slash command registry "default to deferred" / "invalidation with `--now` opt-in (root invariant)"

#### Scenario: /delegation saves its choice for the next session
- **WHEN** the user runs `/delegation <mode>` mid-session
- **THEN** the choice "saves for the next session, and `--now` applies it immediately"
- Source: [relnote v0.23.0] "`/delegation <mode>` saves for the next session, and `--now` applies it immediately."

### Requirement: Non-interactive single-query mode
The CLI SHALL provide `-q` single-query execution (`hermes -q "..."`) with defined exit codes for scripted/headless use (`cli_single_query.py`).
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (`cli_single_query.py` (-q runner, exit codes, kanban loops))
**Anchor**: `hermes_cli/cli_single_query.py` (module exists; not opened)

#### Scenario: -q on a real TTY
- **WHEN** the user runs `hermes -q "..."` on a real TTY
- **THEN** the prompt "is submitted **literally** as the first turn of a normal interactive session (it is never parsed as a slash command or `!` shell escape) and the session stays open"
- Source: doc: website/docs/reference/cli-commands.md § top-level flags, `-q` row "is submitted **literally** as the first turn"

#### Scenario: -q for scripted/headless use
- **WHEN** `-q` is combined with `--oneshot`, `-Q`, or non-TTY stdio
- **THEN** the run "answers and exits" as a finite non-interactive `oneshot` session, hidden from the session pickers
- Source: doc: website/docs/reference/cli-commands.md § top-level flags, `-q` row "With `--oneshot`, `-Q`, or non-TTY stdio it answers and exits."; doc: website/docs/user-guide/sessions.md "Finite non-interactive runs"

### Requirement: Interactive pickers use curses; display code avoids erase-to-EOL
Interactive menu pickers SHALL use the curses UI helper, and spinner/display code SHALL NEVER emit `\033[K` (it leaks as literal `?[K` under prompt_toolkit `patch_stdout`) — space-padding instead.
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § Rules ("all interactive menu-pickers use curses"; no-`\033[K` rule)
**Anchor**: not located (`hermes_cli/curses_ui.py` named by doc)

#### Scenario: Display code clears a line under prompt_toolkit
- **WHEN** spinner/display code emits `\033[K` (ANSI erase-to-EOL)
- **THEN** it "leaks as literal `?[K` under prompt_toolkit's `patch_stdout`" — code must space-pad instead
- Source: doc: hermes_cli/AGENTS.md § Rules "it leaks as literal `?[K` under prompt_toolkit's `patch_stdout`; space-pad instead"

#### Scenario: A new interactive menu picker is added
- **WHEN** a CLI surface adds an interactive menu picker
- **THEN** it follows the rule "all interactive menu-pickers use curses (`hermes_cli/curses_ui.py`" — the shared curses helper
- Source: doc: hermes_cli/AGENTS.md § Rules "all interactive menu-pickers use curses"

### Requirement: Gateway process management via facade with platform backends
`hermes gateway` SHALL manage gateway processes through its facade — process discovery, PM-aware systemd unit generation/refresh, launchd (macOS) and Windows backends, supervised restart, migration, multiplex helpers — with siblings reading facade names late (`_gw()`).
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § CLI architecture (`hermes_cli/gateway.py` facade + named siblings); [PR #139041](https://github.com/NousResearch/hermes-agent/pull/139041) — `hermes update` drain stays reachable for a parked approval/clarify (update/gateway drain boundary, drafted there too)
**Anchor**: `hermes_cli/gateway.py` (facade exists; dispatch lines not opened)

#### Scenario: Restarting a gateway Hermes did not install
- **WHEN** `hermes gateway restart` targets a gateway Hermes did not install (custom launchd agent / unit running `gateway run --external-supervisor`)
- **THEN** the gateway's SELF-declared supervisor (control-socket `identify` or the argv marker) decides; Hermes must "hand back via SIGUSR1 and wait" for a fresh supervised PID
- AND never stop + foreground `run_gateway` — "that stamps the CLI's PID and wedges" every KeepAlive respawn
- Source: doc: hermes_cli/AGENTS.md § Profiles (service matrix) "hand back via SIGUSR1 and wait" / "that stamps the CLI's PID and wedges"

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

#### Scenario: A connector needs setup on the classic CLI
- **WHEN** a hosted app or local MCP server needs connect/setup
- **THEN** it shares "one setup card (desktop dialog, TUI callout or CLI panel)" — the card is not desktop-only — "and the agent can use new tools in the same turn"
- Source: [relnote v0.22.0] "Hosted apps and local MCP servers share one setup card (desktop dialog, TUI callout or CLI panel), and the agent can use new tools in the same turn."

### Requirement: Extension points over overrides
Wrapper CLIs SHALL extend the REPL through the protected hooks in `cli_tui_mixin.py` (per `website/docs/developer-guide/extending-the-cli.md`) rather than overriding `run()`.
**Status**: INFERRED
**Evidence**: doc: hermes_cli/AGENTS.md § Rules ("Wrapper CLIs extend via the protected hooks")
**Anchor**: `hermes_cli/cli_tui_mixin.py` (module exists; hooks not opened)

#### Scenario: A wrapper CLI adds widgets or keybindings
- **WHEN** a wrapper CLI wants to add widgets, keybindings, or layout customizations
- **THEN** it uses the protected extension hooks on `HermesCLI` "without overriding the `run()` method"
- AND this "keeps your extension decoupled from internal changes"
- Source: doc: website/docs/developer-guide/extending-the-cli.md § "Extending the CLI" "without overriding the `run()` method" / "This keeps your extension decoupled from internal changes."

### Requirement: Rewind edits or forks an earlier prompt
The classic CLI (and TUI) SHALL offer a backtrack picker — press Esc twice or `/rewind` — to edit and resend an earlier message or fork a new session from that point, leaving the original session unchanged.
**Status**: INFERRED
**Evidence**: [commit 1a71782f1795] — "backtrack picker — Esc Esc / /rewind to edit & resend or fork from an earlier prompt"; [relnote v0.23.0] "Press Esc twice or type `/rewind` in the TUI or classic CLI, pick an earlier message, then edit and resend it or fork a new session from that point. The original session stays exactly as it was."
**Anchor**: not located (backtrack picker implementation lines not opened)

#### Scenario: User rewinds to an earlier prompt
- **WHEN** the user presses Esc twice or types `/rewind` in the classic CLI (or TUI)
- **THEN** they can pick an earlier message and "edit and resend it or fork a new session from that point"
- AND "The original session stays exactly as it was."
- Source: [relnote v0.23.0] "Press Esc twice or type `/rewind` in the TUI or classic CLI"

### Requirement: Inline images in the classic CLI terminal
The classic CLI SHALL draw pasted/tool-produced images in the terminal (kitty/Ghostty; iTerm2, WezTerm and Konsole; full resolution in VS Code when its image support is on; colour blocks elsewhere) instead of only printing a file path.
**Status**: INFERRED
**Evidence**: [commit ab9dda55d610] — "draw images inline in the classic CLI scrollback"; [commit e0d6efd4dee1] — "full-resolution images in iTerm2, WezTerm and Konsole"; [commit be01eb2a9585] — "full-resolution images in VS Code when its image support is on"; [relnote v0.23.0] "the CLI and TUI now draw it right in the chat instead of printing a file path"
**Anchor**: not located (image-draw backends not opened)

#### Scenario: An image is pasted or captured in the terminal
- **WHEN** the user pastes an image, or a tool takes a screenshot
- **THEN** "the CLI and TUI now draw it right in the chat instead of printing a file path: real pixels in kitty and Ghostty (CLI and TUI) and in iTerm2, WezTerm and Konsole (CLI), coloured blocks everywhere else, and full resolution in VS Code's terminal when its image support is on"
- Source: [relnote v0.23.0] "Pictures in the terminal" — "draw it right in the chat instead of printing a file path"

### Requirement: /model reset returns a pinned session to the default
`/model reset` in the classic CLI SHALL take a session pinned via `/model` back to the configured default without losing the conversation.
**Status**: INFERRED
**Evidence**: [commit 66c48cb158de] — "/model reset in the classic CLI, help hint and queued-pick display (salvage #74899)"; [relnote v0.22.6] "`/model reset` to clear a session's model pin without losing history"; [relnote v0.23.0] "Takes a session pinned with `/model` back to your configured default without losing the conversation, in the CLI, TUI, Desktop and messaging."
**Anchor**: not located (command handler lines not opened)

#### Scenario: A pinned model is reset mid-conversation
- **WHEN** the user runs `/model reset` on a session pinned with `/model`
- **THEN** the session returns "to your configured default without losing the conversation"
- Source: [relnote v0.23.0] "back to your configured default without losing the conversation"

## Scenario-ification notes
- REQ "First-run surfaces reach their own setup": no doc-grounded trigger for the TUI blank-install case; PR #128663/#129200 quotes are bundle-only; the v0.22.0 onboarding note covers the desktop app ("Open the desktop app on a computer where you have never used Hermes and it starts a short setup chat instead of a settings screen"), a different surface — kept as invariant.
- Tail-fold rejections (out of capability/deferrable): `--cpu-profile` launch-path fixes (695d9a641d42, ce154453eb76); image-probe timing fixes (ed1afb082eb3, 5ce017578436); oversized-PNG decode guard (55bc503305fe); scrollback replay hygiene (fcfd416dcdee); docs/inline-image naming (025e1febe99b); reasoning-footer tests (7cce4ab92069, aa28a71341ff); gateway-socket closed/refusal-pair (7303b01fd6ad, d72b65595e42, f398ff59b8e7, ac7e758c3d1b) — CLI↔gateway transport, deferred to the gateway/messaging capability.

## Known gaps / open questions
- `--now` deferral opt-in: root doc asserts it; implementation site not located — UNVERIFIED exact semantics (which commands, how state is staged).
- Updater (`hermes update`) contracts (autostash preservation #124641, drain reachability #139041) sit at the deferred update-packaging boundary — deliberately not drafted here.
- `hermes pm` / dependency-manager CLI: deferred packaging scope.
- CLI bundle is noisy: top hits were desktop/telegram fixes (keyword false positives) — only genuine CLI items drafted; cluster regex needs tightening for pass 2 (`\bcli\b` over-matches).
- `hermes_cli/web_routers/` + dashboard SPA excluded (tui-web deferred).
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
