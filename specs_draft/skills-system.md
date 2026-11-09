# Capability: skills-system

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27 + no-ref tail to the pin (pass-2 fold). | Pass 2 (scenario grounding) applied 2026-11-08.

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

#### Scenario: Reviewing a skill PR's target directory
- **WHEN** a skill PR is reviewed and the skill is heavy-dep or niche
- **THEN** it belongs in `optional-skills/`, not the bundled tree — "Reviewing a skill PR: check the target directory — heavy-dep or niche skills go to `optional-skills/`."
- AND post-window practice confirms the rule: niche built-ins were moved out ("a fresh install ships 44 built-in skills instead of 58 ... 12 niche skills become optional installs")
- Source: doc: skills/AGENTS.md § Two surfaces "Reviewing a skill PR: check the target directory"; [relnote v0.23.0] "12 niche skills become optional installs"

#### Scenario: Installing an optional skill
- **WHEN** a user wants a heavier/niche skill that ships "shipped but NOT active"
- **THEN** it is installed explicitly with `hermes skills install official/<category>/<skill>` — "still one `hermes skills install` away, just not loaded by default"
- Source: doc: skills/AGENTS.md § Two surfaces "heavier/niche skills shipped but NOT active; installed via"; [relnote v0.16.0] "still one `hermes skills install` away, just not loaded by default"

### Requirement: SKILL.md frontmatter contract
A skill's frontmatter SHALL carry `name`, `description`, `version`, `author`, `license`, `platforms` (OS gate) and `metadata.hermes.*` (tags, category, related_skills, config); `metadata.hermes.config` declares config.yaml settings stored under `skills.config.<key>`, prompted during setup and injected at load; top-level `tags:`/`category:` are mirrored by the loader.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § SKILL.md frontmatter; doc: website/docs/developer-guide/creating-skills.md
- Anchor: `tests/skills/test_authoring_standards.py:81` (`test_required_frontmatter_fields` — the six fields; tags accepted from `metadata.hermes.tags` OR top-level `tags`); `agent/skill_utils.py:109` (`skill_matches_platform` — `platforms:` OS gate); `agent/skill_utils.py:746` (`extract_skill_config_vars` — `metadata.hermes.config` key/description/default/prompt), `agent/skill_utils.py:795` (`SKILL_CONFIG_PREFIX = "skills.config"`); `tools/skills_tool.py:661` (loader reads `metadata.hermes.*` first, falls back to top-level `tags:`/`related_skills:`)

#### Scenario: A skill declares config it needs
- **WHEN** a skill declares `metadata.hermes.config` settings
- **THEN** they are "stored under `skills.config.<key>`, prompted during setup, injected at load"
- Source: doc: skills/AGENTS.md § SKILL.md frontmatter "stored under `skills.config.<key>`, prompted during setup, injected at load"; [relnote v0.8.0] "skills can declare required config.yaml settings, prompted during setup, injected at load time"

#### Scenario: A skill uses top-level tags instead of metadata.hermes
- **WHEN** a SKILL.md carries top-level `tags:`/`category:` instead of `metadata.hermes.*`
- **THEN** they are "accepted and mirrored from `metadata.hermes.*` by the loader"
- AND the six required fields are checked by the standards test
- Source: doc: skills/AGENTS.md § SKILL.md frontmatter "are accepted and mirrored from `metadata.hermes.*` by the loader."; test: tests/skills/test_authoring_standards.py::test_required_frontmatter_fields

### Requirement: 60-character description bound
Skill descriptions in the served index SHALL be cut to `SKILL_PROMPT_DESC_LIMIT = 60` at a word boundary, and `skill_manage` SHALL reject a new or changed description over the limit (one sentence, period-terminated, no marketing words, no name/category repetition).
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 1
- Anchor: `agent/skill_utils.py:846` (`SKILL_PROMPT_DESC_LIMIT = 60`), `agent/skill_utils.py:858` (`clip_skill_description` — word-boundary fit); `tools/skill_manager_tool.py:173` (`_description_budget_error` rejects a create or a *changed* over-limit description; an unchanged legacy one stays editable); `tests/skills/test_authoring_standards.py:103` (`test_description_hardline` — limit, period, marketing words)

#### Scenario: A new or changed description exceeds the budget
- **WHEN** `skill_manage` creates a skill — or changes an existing description — with a description over the index width
- **THEN** it is rejected: "60 is the width the index shows (`SKILL_PROMPT_DESC_LIMIT`); `skill_manage` rejects a new or changed description over it."
- AND the bundled population is held to the hardline (limit, period, no marketing words) by the standards test
- Source: doc: skills/AGENTS.md § Authoring standards rule 1 "rejects a new or changed description over it"; test: tests/skills/test_authoring_standards.py::test_description_hardline

#### Scenario: The served index clips a long description
- **WHEN** the served skill index renders a description longer than the budget
- **THEN** it is clipped at a word boundary — never mid-word
- Source: test: tests/agent/test_skills_index_format.py::test_clip_cuts_at_any_whitespace_never_inside_a_word; tests/agent/test_skills_index_format.py::test_index_rows_carry_each_name_once_and_never_a_half_word

### Requirement: Prose names native tools, never wrapped shell utilities
Skill prose SHALL reference native Hermes tools (`terminal`, `read_file`, `patch`, `search_files`, ...) in backticks and never name shell utilities the agent has wrapped (`grep`→`search_files`, `cat`→`read_file`, `sed`/`awk`→`patch`); third-party CLIs belong in script files, not the headline surface.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 2 (enforced by `tests/skills/test_authoring_standards.py`)
- Anchor: `tools/skill_linter.py:22` (`_SHELL_UTIL_TO_TOOL` — banned token → native tool map, exactly the doc's `grep`/`cat`/`sed`/`find` substitutions), `tools/skill_linter.py:136` (`_check_body` flags backtick-wrapped shell utilities in prose, code fences stripped)
- Note: this check is an *advisory lint finding* attached to `skill_manage` results, not a blocking CI test — see Known gaps (enforcement-strength drift).

#### Scenario: Skill prose names a wrapped shell utility
- **WHEN** skill prose (outside code fences) names a shell utility the agent has wrapped — "`grep` →" `search_files`, `cat`/`head`/`tail` → `read_file`, `sed`/`awk` → `patch`
- **THEN** the attached linter flags it as a finding (advisory — see Known gaps; it does not block the write)
- Source: doc: skills/AGENTS.md § Authoring standards rule 2 "Never name shell utilities the agent has wrapped"; test: tests/tools/test_skill_linter.py::test_shell_utility_reference_in_prose_flagged

#### Scenario: The same utility appears inside a code block
- **WHEN** the shell utility appears inside a fenced code block rather than in prose
- **THEN** the linter does not flag it
- Source: test: tests/tools/test_skill_linter.py::test_shell_utility_inside_code_block_not_flagged

### Requirement: Platform gating audited against imports
`platforms:` frontmatter SHALL be audited against actual script imports: POSIX-only primitives require a platform declaration; cross-platform fixes are preferred, gating narrower only for genuinely platform-bound dependencies.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 3
- Anchor: `tools/skill_linter.py:31` (`_POSIX_PRIMITIVES` — `fcntl`, `termios`, `os.setsid`, `signal.SIGKILL`, `/proc/`, `osascript`, `apt-get`, `systemctl`), `tools/skill_linter.py:164` (`_check_files` — "scripts use POSIX-only primitives … but no 'platforms:' frontmatter")
- Note: advisory lint, not blocking CI — see Known gaps (enforcement-strength drift).

#### Scenario: A skill script uses a POSIX-only primitive
- **WHEN** a skill's scripts use POSIX-only primitives (`fcntl`, `termios`, `os.setsid`, `/proc`, `osascript`, `apt`, `systemctl`, bash heredocs, hardcoded `/tmp`)
- **THEN** they "require a platform declaration" in `platforms:` — and reviewers should "Fix cross-platform" first, gating "only when the dependency is genuinely platform-bound"
- Source: doc: skills/AGENTS.md § Authoring standards rule 3 "`platforms:` gating is audited against actual script imports" / "require a platform declaration"

### Requirement: Human-first author credit
A skill's `author` SHALL credit the human first (real name + handle), "Hermes Agent" second; a commit authored as "Hermes Agent" is replaced with the human's name.
- Status: INFERRED
- Evidence: doc: skills/AGENTS.md § Authoring standards rule 4
- Anchor: not located — no code enforces the human-first *ordering*; only a soft capitalization lint exists (`tools/skill_linter.py:113`, `author-caps`: an author loosely spelled "hermes agent" should be proper-cased "or a real contributor name"). Ordering stays with human review.

#### Scenario: A commit was authored as "Hermes Agent"
- **WHEN** a contributed skill's commit is authored as "Hermes Agent" (the contributor drafted with Hermes)
- **THEN** the author credit "is replaced" with the human's name — "credit the human, not the tool" — human first, "Hermes Agent" second
- Source: doc: skills/AGENTS.md § Authoring standards rule 4 "credit the human, not the tool."

### Requirement: No pagination on skill-loading tools
Skill-loading tools SHALL NOT expose `offset`/`limit`: the agent must read a skill fully (root rubric rejects pagination on instructional tools).
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § closing rule ("No offset/limit pagination on skill-loading tools — the agent must read a skill fully (root)"); doc: AGENTS.md (root) § Contribution rubric
- Anchor: `tools/skills_tool.py:733` (`SKILL_VIEW_SCHEMA` — parameters are exactly `name` + optional `file_path`, no `offset`/`limit`); `tools/skills_tool.py:613` (`skill_view()` signature — reads SKILL.md or one linked file whole); `tools/skills_tool.py:753` (`skills_list` registration — handler takes only `category`)

#### Scenario: A PR adds pagination to a skill-loading tool
- **WHEN** a PR adds `offset`/`limit` pagination to an instructional (skill-loading) tool
- **THEN** the contribution rubric rejects it even when well-built — "No `offset`/`limit` pagination on skill-loading tools — the agent must read a skill fully (root)."
- Source: doc: skills/AGENTS.md § closing rule "No `offset`/`limit` pagination on skill-loading tools — the agent must read a skill fully (root)."; doc: AGENTS.md (root) § Contribution rubric "`offset`/`limit` pagination on instructional tools"

### Requirement: Skill content injection rides user messages
Activating a skill slash command SHALL inject skill content as a user message (never the system prompt), with skill config injected at load.
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Message-flow invariants ("skill slash commands (agent/skill_commands.py) inject as a user message"); [PR #97918](https://github.com/NousResearch/hermes-agent/pull/97918) — skills prompt-section cleanup incl. gating the skill pointer on the skill actually being installed
- Anchor: `agent/skill_commands.py:843` (`build_skill_invocation_message` — "Build the user message for a skill slash command"), `agent/skill_commands.py:311` (`_inject_skill_config` — appends the `[Skill config: …]` block resolved from `metadata.hermes.config`)

#### Scenario: A skill slash command fires mid-conversation
- **WHEN** a skill slash command injects content into a running conversation
- **THEN** it "rides a **user message or tool result**, never the system prompt" — skill slash commands "inject as a user message" (prompt caching stays intact)
- AND the skill's declared config is injected with it ("prompted during setup, injected at load")
- Source: doc: agent/AGENTS.md § Message-flow invariants "rides a **user message or tool result**, never the system prompt" / "inject as a user message"; doc: skills/AGENTS.md § SKILL.md frontmatter "prompted during setup, injected at load"

### Requirement: skill_manage operations are one atomic call
`skill_manage` SHALL take an `operations[]` array as the call shape — each operation names its skill — applying atomically with cross-skill rollback on any failure.
- Status: VERIFIED
- Evidence: [PR #97295](https://github.com/NousResearch/hermes-agent/pull/97295) — "operations[] is the call — each op names its skill; atomic with cross-skill rollback"
- Anchor: `tools/skill_manager_batch.py:219` (`_skill_manage_batch` — "Apply operations atomically: every touched skill is snapshotted first and any failure rolls them back"; snapshot :137, restore :158, rollback :199); `tools/skill_manager_tool.py:886` (advertised schema — `operations` array is the required call shape), `tools/skill_manager_tool.py:790` (dispatch: `operations` overrides flat fields)

#### Scenario: A multi-operation call fails partway
- **WHEN** an `operations[]` call fails on a later operation (e.g. a `write_file` after a `patch`)
- **THEN** every touched skill is rolled back — the earlier patch is undone, and a skill created earlier in the same batch is removed
- Source: test: tests/tools/test_skill_manage_batch.py::TestSkillManageBatch::test_midbatch_failure_rolls_back_existing_skill; tests/tools/test_skill_manage_batch.py::TestSkillManageBatch::test_failed_create_batch_removes_partial_skill

#### Scenario: Operations span several skills and one fails late
- **WHEN** a batch targets different skills and a late operation fails
- **THEN** the rollback covers every touched skill (patch undone in one, batch-created skill deleted), while pre-existing directories and files the batch did not write survive
- Source: test: tests/tools/test_skill_manage_batch.py::TestSkillManageBatch::test_cross_skill_batch_and_rollback; tests/tools/test_skill_manage_batch.py::TestSkillManageBatch::test_create_plus_files_atomic

### Requirement: Content lock and ownership guard on mutating skill actions
Every mutating `skill_manage` action SHALL pass the per-skill content lock and the ownership delete guard.
- Status: VERIFIED
- Evidence: [PR #25083](https://github.com/NousResearch/hermes-agent/pull/25083) — "per-skill content lock against autonomous writes"
- Anchor: `tools/skill_manager_guards.py:256` (`_background_review_preflight` — "the content lock (every mutating action) and the ownership delete guard", run on the single-op AND batch paths); `tools/skill_manager_guards.py:143` (`_pinned_guard` — pinned skills refuse deletion only)

#### Scenario: An autonomous pass attempts a mutating action
- **WHEN** the agent (including background review) issues any mutating `skill_manage` action against a locked skill
- **THEN** the preflight refuses it — the content lock applies to every mutating action on both the single-op and batch paths
- Source: test: tests/tools/test_skill_manager_tool.py::TestLockedGuard::test_locked_skill_refuses_every_autonomous_mutation

#### Scenario: The agent tries to delete a pinned skill
- **WHEN** `skill_manage(action="delete")` targets a pinned skill
- **THEN** the delete is refused while "patch/edit/write_file/" "remove_file still work so the agent can keep improving them"
- Source: doc: skills/AGENTS.md § Curator Invariants "refuses pinned skills while patch/edit/write_file/"; test: tests/tools/test_skill_manager_tool.py::TestPinnedGuard::test_delete_refuses_pinned; tests/tools/test_skill_manager_tool.py::TestPinnedGuard::test_edit_allowed_when_pinned

### Requirement: User-locked skills are immutable through every agent write path
A skill the user locks SHALL be unchangeable by the agent through **any** write path — `skill_manage`, `write_file`/`patch`, `terminal` writes, and self-unlock — while the user's own edits stay ungated; the curator and background review honour locks by display name, and an unreadable lock sidecar fails closed for autonomous passes.
- Status: VERIFIED
- Evidence: [commit 91c51e04f457] — "a locked skill can't be changed by the agent through any write path"; [commit a639ed0ae491] — "close terminal lock bypasses; curator honours locks by display name"; [commit 557254faa24e] — lock guard resolves variables and relative inline code, lets reads through
- Anchor: `tools/skill_lock.py:1` (module contract: lock enforced on every agent write path; terminal write-target analysis — redirections, `tee`, `cp`/`mv`/`rm`, inline interpreter code); `tools/skill_manager_guards.py:224` (`_locked_guard` — refuses every mutating action, whoever asks, keyed so all name forms resolve, fail-closed for autonomous passes); `tools/file_tools_write_guards.py:174` (`path_refusal` on `write_file`/`patch` targets); `tools/terminal_tool_guards.py:375` (`command_refusal` on terminal commands); `agent/curator.py:228` (curator skip via `locked_skill_names`)

#### Scenario: A user locks a skill, the agent tries to change it
- **WHEN** the user has run `hermes curator lock <skill>` and the agent then attempts to change that skill
- **THEN** "the agent can't change that skill with `skill_manage`, file edits or terminal writes, even under `--yolo`, and the curator won't archive it"
- AND the lock resolves by every display-name form and still lets reads through
- Source: [relnote v0.23.0] "after `hermes curator lock <skill>`, the agent can't change that skill with `skill_manage`, file edits or terminal writes, even under `--yolo`, and the curator won't archive it."; test: tests/tools/test_skill_lock.py::test_lock_resolves_by_display_name_as_well_as_directory; tests/tools/test_skill_manager_tool.py::TestLockedGuard::test_locked_skill_refuses_every_autonomous_mutation

#### Scenario: A terminal command touches a locked skill
- **WHEN** a terminal command would write into a locked skill's directory
- **THEN** it is refused — but commands that only read the locked skill are allowed
- Source: test: tests/tools/test_skill_lock.py::test_terminal_refuses_writes_into_a_locked_skill_but_not_reads; tests/tools/test_skill_lock.py::test_file_tools_refuse_a_locked_skill_and_its_record

### Requirement: Curator rollback restores complete packages
The skill curator's ledger rollback SHALL restore complete skill packages (not individual files).
- Status: VERIFIED
- Evidence: [PR #96962](https://github.com/NousResearch/hermes-agent/pull/96962) — "restore complete skill packages on ledger rollback"
- Anchor: `agent/curator_backup.py:406` (`rollback()` — restores the whole-tree tar.gz, staging under `.rollback-staging-*` first); `agent/curator_backup.py:1` (module docstring: rollback restores the complete `~/.hermes/skills/` tree — skill dirs, `.usage.json`, `.archive/`, `.curator_state`, and captured `cron-jobs.json` — never individual files)

#### Scenario: Rolling back a delete or re-home from the ledger
- **WHEN** a ledger rollback targets a delete/re-home mutation whose entry is hollow (individual files only)
- **THEN** the rollback restores the complete skill package (backed by the full-package entry recorded at delete time), not just the touched files
- Source: test: tests/tools/test_skill_ledger.py::test_rollback_historical_hollow_entry_restores_full_package; tests/tools/test_skill_ledger.py::test_delete_after_rehome_ledgers_full_package_from_backup

### Requirement: Hub installs are bounded and degradable
Hub skill installs SHALL bound streamed ZIP downloads, SHALL fall through from a revoked/expired `GITHUB_TOKEN` to `gh` auth or anonymous (naming the fallback), SHALL fetch explicitly linked same-directory sibling files on install, and SHALL NOT serve a cached security scan whose source trust no longer matches (a trust-level change forces a re-scan).
- Status: VERIFIED
- Evidence: [PR #57571](https://github.com/NousResearch/hermes-agent/pull/57571) — bound streamed ClawHub ZIP downloads; [PR #98725](https://github.com/NousResearch/hermes-agent/pull/98725) — revoked GITHUB_TOKEN no longer blocks hub installs; [PR #96310](https://github.com/NousResearch/hermes-agent/pull/96310) — fetch explicitly linked same-directory siblings on install; [commit 29a61cb7ab50] — "a cached scan re-scans when the source's trust level changed"
- Anchor: `tools/skills_hub_clawhub.py:70` (`ZIP_DOWNLOAD_MAX_BYTES = 25 * 1024 * 1024`); `tools/skills_hub_github.py:75` (`GitHubAuth` — priority chain PAT → `gh auth token` → GitHub App → anonymous; `reject()` at :119 — a token GitHub 401s is skipped so the chain falls through, with human labels naming the fallback, cites #98725 at :83); `tools/skills_hub_models.py:260` (same-directory sibling-link contract, cites #96310); `tools/skills_guard.py:800` (`scan_skill_cached` — cache served only when `trust_level`/source match the resolved values, else re-scan)

#### Scenario: A source's trust level changes under a cached scan
- **WHEN** a skill's source joins or leaves the trusted repos and a cached security-scan verdict exists for unchanged content
- **THEN** the cache re-scans under the new trust level instead of serving the stale verdict (a stale *trusted* verdict would loosen install policy)
- Source: test: tests/tools/test_skills_guard.py::TestScanSkillCached::test_cached_trust_follows_current_trusted_repos; tests/tools/test_skills_guard.py::TestScanSkillCached::test_cached_verdict_served_when_scanner_version_unchanged (edge: unchanged trust/version serves the cache)

### Requirement: External skill mounts carry a provenance tier
Skills loaded from external mounts SHALL be tagged with an `external` provenance tier distinguishing them from bundled/official sources.
- Status: VERIFIED
- Evidence: [PR #108032](https://github.com/NousResearch/hermes-agent/pull/108032) — "external mounts get an 'external' provenance tier"
- Anchor: `tools/skill_usage.py:753` (`provenance()` — `'hub' | 'bundled' | 'external' | 'agent'`; the docstring names #108032 and defines `external` as mounted from `skills.external_dirs` and absent from the local store); `tools/skill_usage.py:453` (`telemetry_provenance` — `"external"` label at :466); `agent/skill_utils.py:405` (`TIER_EXTERNAL` in the shared tiered search roots, appended at :422 from `get_external_skills_dirs()` at :340)

### Requirement: Curator runs inactivity-triggered with prune always-on and LLM consolidation opt-in
The curator SHALL run as background maintenance with no cron daemon: `maybe_run_curator()` fires when the curator is enabled, not paused, the last run is older than `curator.interval_hours`, and the agent has been idle at least `curator.min_idle_hours`. The deterministic inactivity walk (active→stale→archived) always runs when the curator is enabled; the LLM consolidation fork is opt-in, default off.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator (skill lifecycle); [PR #47840](https://github.com/NousResearch/hermes-agent/pull/47840) — "make skill consolidation opt-in (prune stays default-on)"
- Anchor: `agent/curator.py:3` (module docstring — "Inactivity-triggered (no cron daemon)…"); `agent/curator.py:1200` (`maybe_run_curator` — idle gate `idle_for_seconds < get_min_idle_hours()*3600` at :1204); `agent/curator.py:160` (`should_run_now` gates: enabled, not paused, `last_run_at` older than `interval_hours`); `agent/curator.py:35` (`DEFAULT_CONSOLIDATE = False`; config key `curator.consolidate` resolved at :148); `agent/curator.py:40` (`_state_file` — `~/.hermes/skills/.curator_state`)

#### Scenario: Hermes checks whether the curator should run
- **WHEN** a session starts, gateway housekeeping ticks, or the `hermes serve` maintenance timer fires
- **THEN** "The curator is triggered by an inactivity check, not a cron job": it runs when "Enough time has passed since the last curator run (`interval_hours`, default **7 days**)," and "The agent has been idle long enough (`min_idle_hours`, default **2 hours**)."
- Source: doc: website/docs/user-guide/features/curator.md § How it runs "The curator is triggered by an inactivity check, not a cron job"

#### Scenario: A brand-new install gets a grace interval
- **WHEN** the curator is first observed on a brand-new install (or a pre-curator install after `hermes update`)
- **THEN** it "does not run immediately. The first observation seeds `last_run_at` to "now" and defers the first real pass by one full `interval_hours`."
- Source: doc: website/docs/user-guide/features/curator.md § How it runs "defers the first real pass by one full `interval_hours`"; test: tests/agent/test_curator.py::test_first_run_defers

#### Scenario: Prune runs always; consolidation stays opt-in
- **WHEN** the curator is enabled
- **THEN** the deterministic inactivity pass runs — "This is the always-on pruning behavior — it runs whenever the curator is enabled, with no aux-model cost."
- AND the LLM consolidation pass is "**OFF by default**. When `curator.consolidate: true`" it forks the aux-model review
- Source: doc: website/docs/user-guide/features/curator.md § A run has two phases "This is the always-on pruning behavior — it runs whenever the curator is enabled, with no aux-model cost."

### Requirement: Curator scope invariants — agent-created only, archive is the maximum
The curator SHALL touch only curator-managed skills (`created_by: "agent"`; bundled/hub-installed off-limits except the deterministic archive under `curator.prune_builtins`), SHALL NEVER delete — archiving is its maximum destructive action and is restorable — and SHALL exempt pinned and user-locked skills from every auto-transition and the LLM review.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator — "Invariants" paragraph; [commit a639ed0ae491] — curator honours locks by display name
- Anchor: `tools/skill_usage.py:290` (`_is_curator_managed_record` — `created_by == "agent"` opt-in flag; `curated_report()` is the managed subset, see :768 docstring); `agent/curator.py:851` (LLM candidates = curated_report minus bundled minus disabled); `agent/curator.py:232` (auto-transitions skip `pinned`, protected, and `is_locked_skill` names); `agent/curator.py:323` (review prompt — "archive … is the maximum destructive action"); `tools/skill_manager_guards.py:143` (`_pinned_guard` — delete refused while patch/edit stay allowed)

#### Scenario: A skill goes unused for weeks
- **WHEN** a curator-managed skill sits unused past its archive threshold — and it is neither pinned nor referenced by any cron job
- **THEN** it is moved to `~/.hermes/skills/.archive/` — the curator "also **never auto-deletes**", and archival is recoverable via `hermes curator restore <skill>` which will "move an archived skill back to active"
- Source: doc: website/docs/user-guide/features/curator.md § CLI "move an archived skill back to active"; doc: website/docs/user-guide/features/curator.md § Overview "also **never auto-deletes**"

#### Scenario: Hub-installed skills face the curator
- **WHEN** the curator surveys the library
- **THEN** "By default the curator manages only agent-created skills" and hub-installed skills are "always off-limits"
- AND bundled built-ins are offered to neither path unless `curator.prune_builtins: true` lets only the deterministic walk archive them, while the LLM candidate list still omits bundled and disabled skills
- Source: doc: website/docs/user-guide/features/curator.md § Overview "By default the curator manages only agent-created skills." / "always off-limits" / "With `curator.prune_builtins: true` it can also archive **unused bundled built-in skills**"; test: tests/agent/test_curator.py::test_prune_builtins_still_archives_bundled_via_deterministic_pass; tests/agent/test_curator.py::test_llm_candidate_list_omits_bundled_and_disabled_skills

#### Scenario: A locked or pinned skill hits its archive threshold
- **WHEN** auto-transitions reach a pinned skill or a user-locked skill during the inactivity sweep
- **THEN** both are skipped — pinned skills are "skipped entirely" and for a locked skill "the curator won't archive it"
- Source: doc: website/docs/user-guide/features/curator.md § A run has two phases "**Pinned skills** and **skills referenced by any cron job** (including paused/disabled jobs) are skipped entirely"; [relnote v0.23.0] "the curator won't archive it"; test: tests/agent/test_curator.py::test_pinned_skill_is_never_touched

### Requirement: Curator pre-run snapshots are tar.gz + manifest packages
Before any mutating curator pass the system SHALL snapshot the skills tree as `skills.tar.gz` plus a `manifest.json` under a timestamped `.curator_backups/` directory, covering the ledger files so rollback restores whole ledger state; rollback SHALL first snapshot the current tree, and old snapshots prune to a configured keep count with the rollback target protected.
- Status: VERIFIED
- Evidence: doc: skills/AGENTS.md § Curator ("`agent/curator_backup.py` (pre-run tar.gz snapshots)"; config `backup.*`; `rollback` subcommand)
- Anchor: `agent/curator_backup.py:1` (module docstring — snapshot/rollback contract incl. `.usage.json`, `.archive/`, `.curator_state`, `cron-jobs.json`); `agent/curator_backup.py:58` (`_ARCHIVE_NAME = "skills.tar.gz"`); `agent/curator_backup.py:153` (`snapshot_skills` — tar.gz + manifest, prune with `protect_ids`); `agent/curator_backup.py:406` (`rollback`)

#### Scenario: A consolidation pass is about to run
- **WHEN** the curator prepares to run (its state and cron store live outside the tree)
- **THEN** Hermes takes a `tar.gz` snapshot of the whole `~/.hermes/skills/` tree at `~/.hermes/skills/.curator_backups/<utc-iso>/skills.tar.gz` — one directory per run with the archive plus a manifest
- Source: doc: website/docs/user-guide/features/curator.md § Backups and rollback "Before a consolidation pass (`consolidate: true`, the only pass that rewrites skill content in place), Hermes takes a tar.gz snapshot"

#### Scenario: Snapshots pile up
- **WHEN** curator runs accumulate backups
- **THEN** they are "pruned to `curator.backup.keep` (default 2) on every pass to keep disk usage bounded", protecting the rollback target
- Source: doc: website/docs/user-guide/features/curator.md § Backups and rollback "pruned to `curator.backup.keep` (default 2) on every pass to keep disk usage bounded"; test: tests/agent/test_curator_backup.py::test_snapshot_prunes_to_keep_count; tests/agent/test_curator_backup.py::test_rollback_is_itself_undoable

## Scenario-ification notes
Pass 2 grounded 16 of 17 requirements with 28 scenarios (Tier B skills/AGENTS.md + website curator.md + agent/AGENTS.md; Tier C tests/skills, tests/agent, tests/tools; Tier A relnotes v0.7.0-v0.23.0). Left property-style:
- REQ "External skill mounts carry a provenance tier": no doc states a user-observable trigger→outcome pair for a mount (tests cover tagging mechanically); kept as a structural invariant.
- Hub-install degradation (revoked-token fallthrough, ZIP cap, sibling fetch): anchored code + PR evidence only — no Tier A/B trigger-outcome text located (`revoked` absent from all release bodies); kept property-style.
- "First-run surfaces" and "External-supervisor gateway restart" live in cli-surface.md, not this file.

## Known gaps / open questions
- **Enforcement-strength drift (doc-vs-code):** skills/AGENTS.md heads the authoring standards "HARDLINE — enforced by `tests/skills/test_authoring_standards.py`", but that file's docstring says it enforces only "the programmatically-checkable subset … prose quality stays with review". Rule 2 (native-tool prose) and rule 3 (platform-vs-imports audit) exist only as *advisory* findings in `tools/skill_linter.py` ("Findings never block by themselves"; attached to `skill_manage` results via `_attach_lint_findings`, `tools/skill_manager_tool.py:441`); rule 4 (human-first author credit) has no mechanical check at all (only the `author-caps` soft warning). Doc claims kept as requirements per DRAFT_TEMPLATE rule 6.
- Description bound nuance (not drift): `skill_manage` lets an *unchanged* legacy over-limit description stay editable — only a create or a changed description is rejected (`tools/skill_manager_tool.py:173-178`).
- `skills.config.<key>` setup-time prompting is only partially anchored: the declaration with `prompt` fields (`agent/skill_utils.py:746`) and load-time injection (`agent/skill_commands.py:311`) are verified; the exact setup-wizard entry point that prompts (vs. required-env prompting in `tools/skills_tool_setup.py:87`) was not located.
- Plugin-provided skills (#119644 "installed plugins' MCP tools and skills are live in every open chat") are a plugins×skills contract at the deferred plugins-mcp boundary — excluded here.
- Desktop skill pill behavior (#91626) and the Desktop lock switch UI (tail commit 722d4fac961f) excluded to desktop-ui; the lock *mechanism* is covered by "User-locked skills are immutable through every agent write path".
- Tail commits considered and rejected as out-of-capability: plugin-catalog items (6dcdb81f5e8b, 18d6877f4b00); website catalog/regen commits (888664fda483, 7c6fc00f8028, c2744d98bd63, 08a7c25eecb6, 0aab6dcf8b78, ad09ca5b4421); individual skill-content fixes/consolidations that change skill text, not the skills system (f282c57b7897, a53acf8d3a5d, b544b82db163, 395e89060fe3, c4f72bc69b57, cfabecfa797a, dc82bec3bd4d, d202ddfda225, 30a8c50a6ff1, 4a8c01790a03, b357ebbfc4dc; inventory churn 8112254f8a93/9347107cdbc0 — the active placement rule is already cited via 183b5ddd5fbc); cache-bounds LRU work (c9577b67224b — cache subsystem); test-infra pinning (a53912d2888f); webapp-access lock naming (5c668bbe4daa); 84a0301415ed ("background review never asks the user for a skill's API key") — the background-review guard family exists in `tools/skill_manager_guards.py` but this specific never-ask behavior was not anchored.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05; tail items are cited as `[commit <sha>]` per the G-01 fold.
