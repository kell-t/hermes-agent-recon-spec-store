# Capability: skills-system

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27 + no-ref tail to the pin (pass-2 fold).

## Summary
Skills are Hermes' primary capability-extension edge ("extend before duplicating", root rubric): `skills/` holds built-ins loadable by default, `optional-skills/` ships heavier skills that are installed explicitly. The system covers SKILL.md frontmatter contracts, hardline authoring standards enforced by tests plus an advisory linter, the `skill_manage` tool with atomic multi-skill operations and write guards (content lock, ownership, pinned, user locks enforced on every write path), load-time injection into conversations, hub/catalog installs, and the curator that maintains learned skills with tar.gz snapshot rollback.

## Primary code locations
- `skills/`, `optional-skills/` — the two shipped surfaces (by category)
- `agent/skill_utils.py` — frontmatter parsing, platform gate, description budget, tiered search roots
- `agent/skill_commands.py` — slash-command injection as user messages
- `tools/skills_tool.py` — `skill_view`/`skills_list` and the skill catalog
- `tools/skill_manager_tool.py`, `tools/skill_manager_batch.py`, `tools/skill_manager_guards.py`, `tools/skill_lock.py` — the skill_manage tool and its guards
- `tools/skill_linter.py` — advisory authoring-standards linter attached to `skill_manage` results
- `tools/skills_guard.py` — trust-aware static scan + install policy with attestation cache
- `tools/skills_hub*.py` — hub adapters (official, clawhub, github, install)
- `agent/curator.py`, `agent/curator_backup.py`, `tools/skill_usage.py` — the skill curator, its snapshots, and usage telemetry
- `skills/AGENTS.md` — authoring law (enforced via `tests/skills/test_authoring_standards.py`)

## Requirements

### Requirement: Two shipped surfaces with explicit activation
`skills/` SHALL be built-in and loadable by default; heavier/niche skills SHALL ship in `optional-skills/` NOT active, installed explicitly (`hermes skills install official/<category>/<skill>`); reviewing a skill PR SHALL check the target directory for heavy-dep/niche placement.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Two surfaces; [commit 183b5ddd5fbc] — post-window practice of the placement rule ("move niche built-in skills to optional")
- Anchor: `tools/skills_hub_official.py:34` (`class OptionalSkillSource(SkillSource)`; `official/<category>/<skill>` identifier parsing at :58 and :99-101, `trust_level="builtin"` at :76); `skills/` and `optional-skills/` trees exist at the pin

### Requirement: SKILL.md frontmatter contract
A skill's frontmatter SHALL carry `name`, `description`, `version`, `author`, `license`, `platforms` (OS gate) and `metadata.hermes.*` (tags, category, related_skills, config); `metadata.hermes.config` declares config.yaml settings stored under `skills.config.<key>`, prompted during setup and injected at load; top-level `tags:`/`category:` are mirrored by the loader.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § SKILL.md frontmatter; doc: website/docs/developer-guide/creating-skills.md
- Anchor: `tests/skills/test_authoring_standards.py:81` (`test_required_frontmatter_fields` — the six fields; tags accepted from `metadata.hermes.tags` OR top-level `tags`); `agent/skill_utils.py:109` (`skill_matches_platform` — `platforms:` OS gate); `agent/skill_utils.py:746` (`extract_skill_config_vars` — `metadata.hermes.config` key/description/default/prompt), `agent/skill_utils.py:795` (`SKILL_CONFIG_PREFIX = "skills.config"`); `tools/skills_tool.py:661` (loader reads `metadata.hermes.*` first, falls back to top-level `tags:`/`related_skills:`)

### Requirement: 60-character description bound
Skill descriptions in the served index SHALL be cut to `SKILL_PROMPT_DESC_LIMIT = 60` at a word boundary, and `skill_manage` SHALL reject a new or changed description over the limit (one sentence, period-terminated, no marketing words, no name/category repetition).
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 1
- Anchor: `agent/skill_utils.py:846` (`SKILL_PROMPT_DESC_LIMIT = 60`), `agent/skill_utils.py:858` (`clip_skill_description` — word-boundary fit); `tools/skill_manager_tool.py:173` (`_description_budget_error` rejects a create or a *changed* over-limit description; an unchanged legacy one stays editable); `tests/skills/test_authoring_standards.py:103` (`test_description_hardline` — limit, period, marketing words)

### Requirement: Prose names native tools, never wrapped shell utilities
Skill prose SHALL reference native Hermes tools (`terminal`, `read_file`, `patch`, `search_files`, ...) in backticks and never name shell utilities the agent has wrapped (`grep`→`search_files`, `cat`→`read_file`, `sed`/`awk`→`patch`); third-party CLIs belong in script files, not the headline surface.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 2 (enforced by `tests/skills/test_authoring_standards.py`)
- Anchor: `tools/skill_linter.py:22` (`_SHELL_UTIL_TO_TOOL` — banned token → native tool map, exactly the doc's `grep`/`cat`/`sed`/`find` substitutions), `tools/skill_linter.py:136` (`_check_body` flags backtick-wrapped shell utilities in prose, code fences stripped)
- Note: this check is an *advisory lint finding* attached to `skill_manage` results, not a blocking CI test — see Known gaps (enforcement-strength drift).

### Requirement: Platform gating audited against imports
`platforms:` frontmatter SHALL be audited against actual script imports: POSIX-only primitives require a platform declaration; cross-platform fixes are preferred, gating narrower only for genuinely platform-bound dependencies.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 3
- Anchor: `tools/skill_linter.py:31` (`_POSIX_PRIMITIVES` — `fcntl`, `termios`, `os.setsid`, `signal.SIGKILL`, `/proc/`, `osascript`, `apt-get`, `systemctl`), `tools/skill_linter.py:164` (`_check_files` — "scripts use POSIX-only primitives … but no 'platforms:' frontmatter")
- Note: advisory lint, not blocking CI — see Known gaps (enforcement-strength drift).

### Requirement: Human-first author credit
A skill's `author` SHALL credit the human first (real name + handle), "Hermes Agent" second; a commit authored as "Hermes Agent" is replaced with the human's name.
- Status: INFERRED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 4
- Anchor: not located — no code enforces the human-first *ordering*; only a soft capitalization lint exists (`tools/skill_linter.py:113`, `author-caps`: an author loosely spelled "hermes agent" should be proper-cased "or a real contributor name"). Ordering stays with human review.

### Requirement: No pagination on skill-loading tools
Skill-loading tools SHALL NOT expose `offset`/`limit`: the agent must read a skill fully (root rubric rejects pagination on instructional tools).
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § closing rule ("No offset/limit pagination on skill-loading tools — the agent must read a skill fully (root)"); doc: AGENTS.md (root) § Contribution rubric
- Anchor: `tools/skills_tool.py:733` (`SKILL_VIEW_SCHEMA` — parameters are exactly `name` + optional `file_path`, no `offset`/`limit`); `tools/skills_tool.py:613` (`skill_view()` signature — reads SKILL.md or one linked file whole); `tools/skills_tool.py:753` (`skills_list` registration — handler takes only `category`)

### Requirement: Skill content injection rides user messages
Activating a skill slash command SHALL inject skill content as a user message (never the system prompt), with skill config injected at load.
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Message-flow invariants ("skill slash commands (agent/skill_commands.py) inject as a user message"); [PR #97918](https://github.com/NousResearch/hermes-agent/pull/97918) — skills prompt-section cleanup incl. gating the skill pointer on the skill actually being installed
- Anchor: `agent/skill_commands.py:843` (`build_skill_invocation_message` — "Build the user message for a skill slash command"), `agent/skill_commands.py:311` (`_inject_skill_config` — appends the `[Skill config: …]` block resolved from `metadata.hermes.config`)

### Requirement: skill_manage operations are one atomic call
`skill_manage` SHALL take an `operations[]` array as the call shape — each operation names its skill — applying atomically with cross-skill rollback on any failure.
- Status: VERIFIED
- Evidence: [PR #97295](https://github.com/NousResearch/hermes-agent/pull/97295) — "operations[] is the call — each op names its skill; atomic with cross-skill rollback"
- Anchor: `tools/skill_manager_batch.py:219` (`_skill_manage_batch` — "Apply operations atomically: every touched skill is snapshotted first and any failure rolls them back"; snapshot :137, restore :158, rollback :199); `tools/skill_manager_tool.py:886` (advertised schema — `operations` array is the required call shape), `tools/skill_manager_tool.py:790` (dispatch: `operations` overrides flat fields)

### Requirement: Content lock and ownership guard on mutating skill actions
Every mutating `skill_manage` action SHALL pass the per-skill content lock and the ownership delete guard.
- Status: VERIFIED
- Evidence: [PR #25083](https://github.com/NousResearch/hermes-agent/pull/25083) — "per-skill content lock against autonomous writes"
- Anchor: `tools/skill_manager_guards.py:256` (`_background_review_preflight` — "the content lock (every mutating action) and the ownership delete guard", run on the single-op AND batch paths); `tools/skill_manager_guards.py:143` (`_pinned_guard` — pinned skills refuse deletion only)

### Requirement: User-locked skills are immutable through every agent write path
A skill the user locks (`hermes curator lock`, or the Desktop lock switch) SHALL be unchangeable by the agent through **any** write path — not just `skill_manage`: `skill_manage` refuses every mutating action, `write_file`/`patch` refuse any path inside the skill directory, `terminal` refuses commands that write there, and the agent cannot run `hermes curator unlock`; the user's own edits (CLI, editor) are NOT gated. The curator and background review honour locks by display name (bare, `category/name`, and frontmatter-name forms all resolve to the same record), and an unreadable lock sidecar fails closed for autonomous passes.
- Status: VERIFIED
- Evidence: [commit 91c51e04f457] — "a locked skill can't be changed by the agent through any write path"; [commit a639ed0ae491] — "close terminal lock bypasses; curator honours locks by display name"; [commit 557254faa24e] — lock guard resolves variables and relative inline code, lets reads through
- Anchor: `tools/skill_lock.py:1` (module contract: lock enforced on every agent write path; terminal write-target analysis — redirections, `tee`, `cp`/`mv`/`rm`, inline interpreter code); `tools/skill_manager_guards.py:224` (`_locked_guard` — refuses every mutating action, whoever asks, keyed so all name forms resolve, fail-closed for autonomous passes); `tools/file_tools_write_guards.py:174` (`path_refusal` on `write_file`/`patch` targets); `tools/terminal_tool_guards.py:375` (`command_refusal` on terminal commands); `agent/curator.py:228` (curator skip via `locked_skill_names`)

### Requirement: Curator rollback restores complete packages
The skill curator's ledger rollback SHALL restore complete skill packages (not individual files).
- Status: VERIFIED
- Evidence: [PR #96962](https://github.com/NousResearch/hermes-agent/pull/96962) — "restore complete skill packages on ledger rollback"
- Anchor: `agent/curator_backup.py:406` (`rollback()` — restores the whole-tree tar.gz, staging under `.rollback-staging-*` first); `agent/curator_backup.py:1` (module docstring: rollback restores the complete `~/.hermes/skills/` tree — skill dirs, `.usage.json`, `.archive/`, `.curator_state`, and captured `cron-jobs.json` — never individual files)

### Requirement: Hub installs are bounded and degradable
Hub skill installs SHALL bound streamed ZIP downloads, SHALL fall through from a revoked/expired `GITHUB_TOKEN` to `gh` auth or anonymous (naming the fallback), SHALL fetch explicitly linked same-directory sibling files on install, and SHALL NOT serve a cached security scan whose source trust no longer matches (a trust-level change forces a re-scan).
- Status: VERIFIED
- Evidence: [PR #57571](https://github.com/NousResearch/hermes-agent/pull/57571) — bound streamed ClawHub ZIP downloads; [PR #98725](https://github.com/NousResearch/hermes-agent/pull/98725) — revoked GITHUB_TOKEN no longer blocks hub installs; [PR #96310](https://github.com/NousResearch/hermes-agent/pull/96310) — fetch explicitly linked same-directory siblings on install; [commit 29a61cb7ab50] — "a cached scan re-scans when the source's trust level changed"
- Anchor: `tools/skills_hub_clawhub.py:70` (`ZIP_DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024`); `tools/skills_hub_github.py:75` (`GitHubAuth` — priority chain PAT → `gh auth token` → GitHub App → anonymous; `reject()` at :119 — a token GitHub 401s is skipped so the chain falls through, with human labels naming the fallback, cites #98725 at :83); `tools/skills_hub_models.py:260` (same-directory sibling-link contract, cites #96310); `tools/skills_guard.py:800` (`scan_skill_cached` — cache served only when `trust_level`/source match the resolved values, else re-scan)

### Requirement: External skill mounts carry a provenance tier
Skills loaded from external mounts SHALL be tagged with an `external` provenance tier distinguishing them from bundled/official sources.
- Status: VERIFIED
- Evidence: [PR #108032](https://github.com/NousResearch/hermes-agent/pull/108032) — "external mounts get an 'external' provenance tier"
- Anchor: `tools/skill_usage.py:753` (`provenance()` — `'hub' | 'bundled' | 'external' | 'agent'`; the docstring names #108032 and defines `external` as mounted from `skills.external_dirs` and absent from the local store); `tools/skill_usage.py:453` (`telemetry_provenance` — `"external"` label at :466); `agent/skill_utils.py:405` (`TIER_EXTERNAL` in the shared tiered search roots, appended at :422 from `get_external_skills_dirs()` at :340)

### Requirement: Curator runs inactivity-triggered with prune always-on and LLM consolidation opt-in
The curator SHALL run as background maintenance with no cron daemon: `maybe_run_curator()` fires when the curator is enabled, not paused, the last run is older than `curator.interval_hours`, and the agent has been idle at least `curator.min_idle_hours`. The deterministic inactivity walk (active→stale→archived by activity timestamps) always runs when the curator is enabled; the LLM consolidation/review fork is opt-in (`curator.consolidate`, default off). Scheduler state persists in `~/.hermes/skills/.curator_state`.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator (skill lifecycle); [PR #47840](https://github.com/NousResearch/hermes-agent/pull/47840) — "make skill consolidation opt-in (prune stays default-on)"
- Anchor: `agent/curator.py:3` (module docstring — "Inactivity-triggered (no cron daemon)…"); `agent/curator.py:1200` (`maybe_run_curator` — idle gate `idle_for_seconds < get_min_idle_hours()*3600` at :1204); `agent/curator.py:160` (`should_run_now` gates: enabled, not paused, `last_run_at` older than `interval_hours`); `agent/curator.py:35` (`DEFAULT_CONSOLIDATE = False`; config key `curator.consolidate` resolved at :148); `agent/curator.py:40` (`_state_file` — `~/.hermes/skills/.curator_state`)

### Requirement: Curator scope invariants — agent-created only, archive is the maximum
The curator SHALL touch only curator-managed skills (`created_by: "agent"` opt-in in `.usage.json`; bundled and hub-installed are off-limits unless `curator.prune_builtins` lets the deterministic walk — and only that walk — archive bundled skills; `skills.disabled` names are excluded from the LLM pass); SHALL NEVER delete — moving a skill to `~/.hermes/skills/.archive/` is its maximum destructive action, restorable via `hermes curator restore`; and pinned and user-locked skills SHALL be exempt from every auto-transition and the LLM review.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator — "Invariants" paragraph; [commit a639ed0ae491] — curator honours locks by display name
- Anchor: `tools/skill_usage.py:290` (`_is_curator_managed_record` — `created_by == "agent"` opt-in flag; `curated_report()` is the managed subset, see :768 docstring); `agent/curator.py:851` (LLM candidates = curated_report minus bundled minus disabled); `agent/curator.py:232` (auto-transitions skip `pinned`, protected, and `is_locked_skill` names); `agent/curator.py:323` (review prompt — "archive … is the maximum destructive action"); `tools/skill_manager_guards.py:143` (`_pinned_guard` — delete refused while patch/edit stay allowed)

### Requirement: Curator pre-run snapshots are tar.gz + manifest packages
Before any mutating curator pass the system SHALL snapshot `~/.hermes/skills/` as `skills.tar.gz` plus a `manifest.json` under `~/.hermes/skills/.curator_backups/<utc-iso>/`, including `.usage.json`, `.archive/`, `.curator_state` and captured `cron-jobs.json` so rollback restores the whole ledger state; rollback SHALL first snapshot the current tree; old snapshots prune to a configured `keep` count with the rollback target protected.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator ("`agent/curator_backup.py` (pre-run tar.gz snapshots)"; config `backup.*`; `rollback` subcommand)
- Anchor: `agent/curator_backup.py:1` (module docstring — snapshot/rollback contract incl. `.usage.json`, `.archive/`, `.curator_state`, `cron-jobs.json`); `agent/curator_backup.py:58` (`_ARCHIVE_NAME = "skills.tar.gz"`); `agent/curator_backup.py:153` (`snapshot_skills` — tar.gz + manifest, prune with `protect_ids`); `agent/curator_backup.py:406` (`rollback`)

## Known gaps / open questions
- **Enforcement-strength drift (doc-vs-code):** skills/AGENTS.md heads the authoring standards "HARDLINE — enforced by `tests/skills/test_authoring_standards.py`", but that file's docstring says it enforces only "the programmatically-checkable subset … prose quality stays with review". Rule 2 (native-tool prose) and rule 3 (platform-vs-imports audit) exist only as *advisory* findings in `tools/skill_linter.py` ("Findings never block by themselves"; attached to `skill_manage` results via `_attach_lint_findings`, `tools/skill_manager_tool.py:441`); rule 4 (human-first author credit) has no mechanical check at all (only the `author-caps` soft warning). Doc claims kept as requirements per DRAFT_TEMPLATE rule 6.
- Description bound nuance (not drift): `skill_manage` lets an *unchanged* legacy over-limit description stay editable — only a create or a changed description is rejected (`tools/skill_manager_tool.py:173-178`).
- `skills.config.<key>` setup-time prompting is only partially anchored: the declaration with `prompt` fields (`agent/skill_utils.py:746`) and load-time injection (`agent/skill_commands.py:311`) are verified; the exact setup-wizard entry point that prompts (vs. required-env prompting in `tools/skills_tool_setup.py:87`) was not located.
- Plugin-provided skills (#119644 "installed plugins' MCP tools and skills are live in every open chat") are a plugins×skills contract at the deferred plugins-mcp boundary — excluded here.
- Desktop skill pill behavior (#91626) and the Desktop lock switch UI (tail commit 722d4fac961f) excluded to desktop-ui; the lock *mechanism* is covered by "User-locked skills are immutable through every agent write path".
- Tail commits considered and rejected as out-of-capability: plugin-catalog items (6dcdb81f5e8b, 18d6877f4b00); website catalog/regen commits (888664fda483, 7c6fc00f8028, c2744d98bd63, 08a7c25eecb6, 0aab6dcf8b78, ad09ca5b4421); individual skill-content fixes/consolidations that change skill text, not the skills system (f282c57b7897, a53acf8d3a5d, b544b82db163, 395e89060fe3, c4f72bc69b57, cfabecfa797a, dc82bec3bd4d, d202ddfda225, 30a8c50a6ff1, 4a8c01790a03, b357ebbfc4dc; inventory churn 8112254f8a93/9347107cdbc0 — the active placement rule is already cited via 183b5ddd5fbc); cache-bounds LRU work (c9577b67224b — cache subsystem); test-infra pinning (a53912d2888f); webapp-access lock naming (5c668bbe4daa); 84a0301415ed ("background review never asks the user for a skill's API key") — the background-review guard family exists in `tools/skill_manager_guards.py` but this specific never-ask behavior was not anchored.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05; tail items are cited as `[commit <sha>]` per the G-01 fold.
