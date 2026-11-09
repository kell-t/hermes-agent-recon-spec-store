# Capability: skills-system

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
Skills are Hermes' primary capability-extension edge ("extend before duplicating", root rubric): `skills/` holds built-ins loadable by default, `optional-skills/` ships heavier skills that are installed explicitly. The system covers SKILL.md frontmatter contracts, hardline authoring standards enforced by tests, the `skill_manage` tool with atomic multi-skill operations and write guards, load-time injection into conversations, hub/catalog installs, and the curator that maintains learned skills with ledger rollback.

## Primary code locations
- `skills/`, `optional-skills/` — the two shipped surfaces (by category)
- `agent/skill_utils.py` — index/description machinery
- `agent/skill_commands.py` — slash-command injection as user messages
- `tools/skill_manager_tool.py`, `tools/skill_manager_batch.py`, `tools/skill_manager_guards.py` — the skill_manage tool
- `agent/curator.py`, `agent/curator_backup.py` — the skill curator
- `skills/AGENTS.md` — authoring law (enforced via `tests/skills/test_authoring_standards.py`)

## Requirements

### Requirement: Two shipped surfaces with explicit activation
`skills/` SHALL be built-in and loadable by default; heavier/niche skills SHALL ship in `optional-skills/` NOT active, installed explicitly (`hermes skills install official/<category>/<skill>`); reviewing a skill PR SHALL check the target directory for heavy-dep/niche placement.
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § Two surfaces
**Anchor**: `skills/` and `optional-skills/` directories exist at the pin (tree-verified; adapter `tools/skills_hub_official.py` named by doc, not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `skills/` SHALL be built-in and loadable by default;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: SKILL.md frontmatter contract
A skill's frontmatter SHALL carry `name`, `description`, `version`, `author`, `license`, `platforms` (OS gate) and `metadata.hermes.*` (tags, category, related_skills, config); `metadata.hermes.config` declares config.yaml settings stored under `skills.config.<key>`, prompted during setup and injected at load; top-level `tags:`/`category:` are mirrored by the loader.
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § SKILL.md frontmatter; doc: website/docs/developer-guide/creating-skills.md
**Anchor**: not located (loader mirror code not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A skill's frontmatter SHALL carry `name`, `description`, `version`, `author`, `license`, `platforms` (OS gate) and `metadata.hermes.*` (tags, category, related_skills, config);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: 60-character description bound
Skill descriptions in the served index SHALL be cut to `SKILL_PROMPT_DESC_LIMIT = 60` at a word boundary, and `skill_manage` SHALL reject a new or changed description over the limit (one sentence, period-terminated, no marketing words, no name/category repetition).
**Status**: VERIFIED
**Evidence**: doc: skills/AGENTS.md § Authoring standards rule 1
**Anchor**: `agent/skill_utils.py:846` (`SKILL_PROMPT_DESC_LIMIT = 60`), `agent/skill_utils.py:858` (word-boundary fit)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Skill descriptions in the served index SHALL be cut to `SKILL_PROMPT_DESC_LIMIT = 60` at a word boundary, and `skill_manage` SHALL reject a new or changed description over the limit (one sentence, period-terminated, no marketing words, no name/category repetition).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Prose names native tools, never wrapped shell utilities
Skill prose SHALL reference native Hermes tools (`terminal`, `read_file`, `patch`, `search_files`, ...) in backticks and never name shell utilities the agent has wrapped (`grep`→`search_files`, `cat`→`read_file`, `sed`/`awk`→`patch`); third-party CLIs belong in script files, not the headline surface.
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § Authoring standards rule 2 (enforced by `tests/skills/test_authoring_standards.py`)
**Anchor**: not located (test file not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Skill prose SHALL reference native Hermes tools (`terminal`, `read_file`, `patch`, `search_files`, ...) in backticks and never name shell utilities the agent has wrapped (`grep`→`search_files`, `cat`→`read_file`, `sed`/`awk`→`patch`);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Platform gating audited against imports
`platforms:` frontmatter SHALL be audited against actual script imports: POSIX-only primitives require a platform declaration; cross-platform fixes are preferred, gating narrower only for genuinely platform-bound dependencies.
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § Authoring standards rule 3
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `platforms:` frontmatter SHALL be audited against actual script imports: POSIX-only primitives require a platform declaration;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Human-first author credit
A skill's `author` SHALL credit the human first (real name + handle), "Hermes Agent" second; a commit authored as "Hermes Agent" is replaced with the human's name.
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § Authoring standards rule 4
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A skill's `author` SHALL credit the human first (real name + handle), "Hermes Agent" second;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: No pagination on skill-loading tools
Skill-loading tools SHALL NOT expose `offset`/`limit`: the agent must read a skill fully (root rubric rejects pagination on instructional tools).
**Status**: INFERRED
**Evidence**: doc: skills/AGENTS.md § closing rule ("No offset/limit pagination on skill-loading tools — the agent must read a skill fully (root)"); doc: AGENTS.md (root) § Contribution rubric
**Anchor**: not located (negative contract — absence verified only by inspection of `skill_view` schema; recorded as doc-grounded)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Skill-loading tools SHALL NOT expose `offset`/`limit`: the agent must read a skill fully (root rubric rejects pagination on instructional tools).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Skill content injection rides user messages
Activating a skill slash command SHALL inject skill content as a user message (never the system prompt), with skill config injected at load.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Message-flow invariants ("skill slash commands (agent/skill_commands.py) inject as a user message"); [PR #97918](https://github.com/NousResearch/hermes-agent/pull/97918) — skills prompt-section cleanup incl. gating the skill pointer on the skill actually being installed
**Anchor**: `agent/skill_commands.py:311` (`_inject_skill_config`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Activating a skill slash command SHALL inject skill content as a user message (never the system prompt), with skill config injected at load.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: skill_manage operations are one atomic call
`skill_manage` SHALL take an `operations[]` array as the call shape — each operation names its skill — applying atomically with cross-skill rollback on any failure.
**Status**: INFERRED
**Evidence**: [PR #97295](https://github.com/NousResearch/hermes-agent/pull/97295) — "operations[] is the call — each op names its skill; atomic with cross-skill rollback"
**Anchor**: `tools/skill_manager_batch.py` (batch module exists; atomicity lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `skill_manage` SHALL take an `operations[]` array as the call shape — each operation names its skill — applying atomically with cross-skill rollback on any failure.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Content lock and ownership guard on mutating skill actions
Every mutating `skill_manage` action SHALL pass the per-skill content lock and the ownership delete guard.
**Status**: VERIFIED
**Evidence**: [PR #25083](https://github.com/NousResearch/hermes-agent/pull/25083) — "per-skill content lock against autonomous writes"
**Anchor**: `tools/skill_manager_guards.py:256` ("the content lock (every mutating action) and the ownership delete guard")


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Every mutating `skill_manage` action SHALL pass the per-skill content lock and the ownership delete guard.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Curator rollback restores complete packages
The skill curator's ledger rollback SHALL restore complete skill packages (not individual files).
**Status**: INFERRED
**Evidence**: [PR #96962](https://github.com/NousResearch/hermes-agent/pull/96962) — "restore complete skill packages on ledger rollback"
**Anchor**: `agent/curator.py`, `agent/curator_backup.py` (modules exist; lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The skill curator's ledger rollback SHALL restore complete skill packages (not individual files).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Hub installs are bounded and degradable
Hub skill installs SHALL bound streamed ZIP downloads, SHALL fall through from a revoked/expired `GITHUB_TOKEN` to `gh` auth or anonymous (naming the fallback), and SHALL fetch explicitly linked same-directory sibling files on install.
**Status**: INFERRED
**Evidence**: [PR #57571](https://github.com/NousResearch/hermes-agent/pull/57571) — bound streamed ClawHub ZIP downloads; [PR #98725](https://github.com/NousResearch/hermes-agent/pull/98725) — revoked GITHUB_TOKEN no longer blocks hub installs; [PR #96310](https://github.com/NousResearch/hermes-agent/pull/96310) — fetch explicitly linked same-directory siblings on install
**Anchor**: not located (skills_hub adapter files not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Hub skill installs SHALL bound streamed ZIP downloads, SHALL fall through from a revoked/expired `GITHUB_TOKEN` to `gh` auth or anonymous (naming the fallback), and SHALL fetch explicitly linked same-directory sibling files on install.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: External skill mounts carry a provenance tier
Skills loaded from external mounts SHALL be tagged with an `external` provenance tier distinguishing them from bundled/official sources.
**Status**: INFERRED
**Evidence**: [PR #108032](https://github.com/NousResearch/hermes-agent/pull/108032) — "external mounts get an 'external' provenance tier"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Skills loaded from external mounts SHALL be tagged with an `external` provenance tier distinguishing them from bundled/official sources.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- Curator invariants (skills/AGENTS.md curator section — when it runs, what it may edit, backup ledger format) not read at the pin; UNVERIFIED sub-area, pass 2 target.
- Plugin-provided skills (#119644 "installed plugins' MCP tools and skills are live in every open chat") are a plugins×skills contract at the deferred plugins-mcp boundary — excluded here.
- Desktop skill pill behavior (#91626) excluded to desktop-ui.
- `skills.config.<key>` setup-prompt injection path not anchored.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
