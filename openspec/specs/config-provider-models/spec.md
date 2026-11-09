# Capability: config-provider-models

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
Configuration and model/provider resolution: `~/.hermes/config.yaml` holds behavior, `.env` holds secrets only; a shared runtime resolver (used identically by CLI, gateway, cron, ACP and auxiliary calls) turns provider ids into credentials, base URLs, API modes and fallback chains. Provider profiles are plugins under `providers/` + `plugins/model-providers/`. Auxiliary (side-LLM) work routes through its own resolver with per-task overrides.

## Primary code locations
- `hermes_cli/config.py`, `hermes_cli/config_defaults.py` — config system, `DEFAULT_CONFIG`, `OPTIONAL_ENV_VARS`
- `hermes_cli/runtime_provider.py`, `hermes_cli/auth.py`, `hermes_cli/model_switch.py` — resolution pipeline
- `providers/` — `ProviderProfile` ABC + registry (`register_provider`, `get_provider_profile`)
- `plugins/model-providers/<name>/` — per-provider plugins (bundled; user plugins override by name)
- `agent/auxiliary_client.py` — auxiliary routing (`_resolve_auto_route`)
- `website/docs/developer-guide/provider-runtime.md`, `adding-providers.md` — long-form contracts

## Requirements

### Requirement: Secrets live in .env, behavior lives in config.yaml
Non-secret behavioral settings SHALL NOT be introduced as new `HERMES_*` environment variables (`.env` is secrets only; behavior goes in `config.yaml`); new optional env vars are declared via `OPTIONAL_ENV_VARS` in the config defaults.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § Contribution rubric ("Rejected even when well-built"); lint HX002 (drafted under profiles-isolation)
**Anchor**: `hermes_cli/config_defaults.py:588` (`from hermes_cli.config_defaults import DEFAULT_CONFIG, OPTIONAL_ENV_VARS` — consumer at `hermes_cli/config.py:588`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Non-secret behavioral settings SHALL NOT be introduced as new `HERMES_*` environment variables (`.env` is secrets only;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Shared provider runtime resolver across all surfaces
One provider runtime resolver SHALL serve CLI, gateway, cron jobs, ACP and auxiliary model calls — credential resolution, custom-endpoint resolution, provider registry (`resolve_provider()`), and the shared `/model` switch pipeline — so surfaces cannot diverge on provider semantics.
**Status**: VERIFIED
**Evidence**: doc: website/docs/developer-guide/provider-runtime.md ("shared provider runtime resolver used across: CLI, gateway, cron jobs, ACP, auxiliary model calls")
**Anchor**: `hermes_cli/runtime_provider.py`, `hermes_cli/auth.py`, `hermes_cli/model_switch.py` (named implementation files, opened as tree entries)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** One provider runtime resolver SHALL serve CLI, gateway, cron jobs, ACP and auxiliary model calls — credential resolution, custom-endpoint resolution, provider registry (`resolve_provider()`), and the shared `/model` switch pipeline — so surfaces cannot diverge on provider semantics.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Providers are plugins; adding one needs no resolver branch
A provider SHALL be addable by dropping a plugin that calls `register_provider()` (bundled `plugins/model-providers/<name>/`, or user `plugins/model-providers/` under HERMES_HOME which overrides a bundled provider of the same name); the resolver SHALL pick it up with no new branch, reading canonical `base_url`, `env_vars` priority, `api_mode` and `fallback_models` from the `ProviderProfile`.
**Status**: VERIFIED
**Evidence**: doc: website/docs/developer-guide/provider-runtime.md (Primary implementation section, verbatim rule)
**Anchor**: `providers/` (`base.py`, registry entry points `register_provider`/`get_provider_profile` per doc; `plugins/model-providers/` ships dozens of provider dirs at the pin)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A provider SHALL be addable by dropping a plugin that calls `register_provider()` (bundled `plugins/model-providers/<name>/`, or user `plugins/model-providers/` under HERMES_HOME which overrides a bundled provider of the same name);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Config saves preserve user-authored content
Config writes SHALL write the user's own YAML (stripped of commented-out defaults where applicable) and SHALL NOT overwrite the file with `DEFAULT_CONFIG` verbatim (the gateway reads raw YAML — verbatim dumps clobber intent).
**Status**: VERIFIED
**Evidence**: doc: hermes_cli/config.py comment ("Never DEFAULT_CONFIG verbatim -- the gateway")
**Anchor**: `hermes_cli/config.py:513`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Config writes SHALL write the user's own YAML (stripped of commented-out defaults where applicable) and SHALL NOT overwrite the file with `DEFAULT_CONFIG` verbatim (the gateway reads raw YAML — verbatim dumps clobber intent).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Auxiliary work resolves per task with pinned overrides
Auxiliary (side-LLM) tasks — curator, vision, embedding, title generation, session_search, compression — SHALL resolve through `_resolve_auto_route`, with per-task `provider/model/base_url/reasoning_effort` overrides settable under `auxiliary:` in config.yaml.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Model and provider resolution
**Anchor**: `agent/auxiliary_client.py:4568` (`def _resolve_auto_route`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Auxiliary (side-LLM) tasks — curator, vision, embedding, title generation, session_search, compression — SHALL resolve through `_resolve_auto_route`, with per-task `provider/model/base_url/reasoning_effort` overrides settable under `auxiliary:` in config.yaml.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Credential pools and fallback models are first-class construction inputs
The agent SHALL accept a `fallback_model` and a `credential_pool` at construction, and fallback/credential resolution chains SHALL be covered by E2E tests with real imports against a temp `HERMES_HOME` (not mocks).
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Model and provider resolution ("Fallback models and credential pools are resolution-chain code: E2E them with real imports against a temp HERMES_HOME, not mocks")
**Anchor**: `run_agent.py:274` (`fallback_model: dict | None = None, credential_pool=None`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The agent SHALL accept a `fallback_model` and a `credential_pool` at construction, and fallback/credential resolution chains SHALL be covered by E2E tests with real imports against a temp `HERMES_HOME` (not mocks).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Rate-limit waiting distinguishes free tier from paid
Only free-tier accounts SHALL end a live turn on a long cooldown; paid providers SHALL wait out `Retry-After` rather than terminate the turn.
**Status**: INFERRED
**Evidence**: [PR #129410](https://github.com/NousResearch/hermes-agent/pull/129410) — "only the free tier ends a live turn on a long cooldown; paid providers wait out Retry-After again"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Only free-tier accounts SHALL end a live turn on a long cooldown;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Nous sign-in is a plain device login
Every Nous sign-in path SHALL use the plain device login flow, and a free-tier guest account SHALL be handed to the real account after sign-in (identity continuity).
**Status**: INFERRED
**Evidence**: [PR #143235](https://github.com/NousResearch/hermes-agent/pull/143235) — "every Nous sign-in is the plain device login"; [PR #143234](https://github.com/NousResearch/hermes-agent/pull/143234) — "hand the free-tier guest to the account after sign-in"
**Anchor**: not located (`hermes_cli/auth.py` is the registry owner per provider-runtime doc; flow lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Every Nous sign-in path SHALL use the plain device login flow, and a free-tier guest account SHALL be handed to the real account after sign-in (identity continuity).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: api_mode selects the wire per provider/model
Model calls SHALL carry an explicit `api_mode` (`"chat_completions" | "codex_responses" | ...`) resolved from the provider profile, and mis-routed families SHALL be corrected at the profile level (e.g. Claude models via a chat-completions-shaped gateway routed to the Messages wire).
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Shape (`api_mode` param of AIAgent); [PR #134848](https://github.com/NousResearch/hermes-agent/pull/134848) — route Claude models to the Messages wire (opencode-go)
**Anchor**: not located (profile `api_mode` fields inside `plugins/model-providers/*`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Model calls SHALL carry an explicit `api_mode` (`"chat_completions" | "codex_responses" | ...`) resolved from the provider profile, and mis-routed families SHALL be corrected at the profile level (e.g.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Model-visible capability claims match the active model
Capability notes injected to the model SHALL reflect the actually-resolved model (a text-only header must not tell vision-capable models they cannot see images; badges show the runtime model during fallback, not the config value).
**Status**: INFERRED
**Evidence**: [PR #131568](https://github.com/NousResearch/hermes-agent/pull/131568) — text-only header no longer tells vision models they cannot see images; [PR #54509](https://github.com/NousResearch/hermes-agent/pull/54509) — badge follows the PTY runtime model, not config, during fallback
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Capability notes injected to the model SHALL reflect the actually-resolved model (a text-only header must not tell vision-capable models they cannot see images;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Context lengths and model capabilities are centralized
Per-model context lengths and capabilities SHALL live in `agent/model_metadata.py` (single source for sizing decisions such as window-derived thresholds).
**Status**: INFERRED
**Evidence**: doc: agent/AGENTS.md § Model and provider resolution ("agent/model_metadata.py holds context lengths and capabilities")
**Anchor**: `agent/model_metadata.py` (module exists; not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Per-model context lengths and capabilities SHALL live in `agent/model_metadata.py` (single source for sizing decisions such as window-derived thresholds).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Setup-profile models reason at low effort
Setup/onboarding chat SHALL run at low reasoning effort on every provider (cost guard on the funnel).
**Status**: INFERRED
**Evidence**: [PR #129405](https://github.com/NousResearch/hermes-agent/pull/129405) — "the setup chat reasons at low effort on every provider"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Setup/onboarding chat SHALL run at low reasoning effort on every provider (cost guard on the funnel).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- Exact provider-profile schema (fields of `ProviderProfile`) not opened — `providers/base.py` next pass.
- Default-model policy (GLM-5.3 as "silent default", #144810) — where the default is pinned (catalog vs config default) not located; needs a requirement with anchor.
- Bedrock inference-profile routing and 1M-window sizing (#133573) — provider-specific contract, not drafted.
- Config-backend long-form (`website/docs/developer-guide/config-backend.md`) not read — may contain load-precedence requirements (managed scope / profile_routes seen in cron #121212).
- Deferred boundary: plugins/model-providers is a plugins-shaped tree; this spec owns the *resolution contract*, plugins-mcp (deferred) would own plugin lifecycle.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
