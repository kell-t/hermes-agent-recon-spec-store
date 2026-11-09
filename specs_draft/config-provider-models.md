# Capability: config-provider-models

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (scenario grounding + tail fold) applied 2026-11-08.

## Summary
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
- Status: VERIFIED
- Evidence: doc: AGENTS.md (root) § Contribution rubric ("Rejected even when well-built"); lint HX002 (drafted under profiles-isolation)
- Anchor: `hermes_cli/config_defaults.py:588` (`from hermes_cli.config_defaults import DEFAULT_CONFIG, OPTIONAL_ENV_VARS` — consumer at `hermes_cli/config.py:588`)

#### Scenario: A PR introduces a HERMES_* env var for non-secret config
- **WHEN** a PR proposes a new `HERMES_*` environment variable for a non-secret setting
- **THEN** the contribution rubric rejects it: `.env` is secrets only, behaviour goes in `config.yaml`
- Source: doc: AGENTS.md (root) § Contribution rubric "(`.env` is secrets only, behaviour goes in `config.yaml`)"

#### Scenario: Internal code needs an env mirror of a config value
- **WHEN** internal code needs an environment mirror of a config setting
- **THEN** it is bridged in code (e.g. `terminal.cwd` → `TERMINAL_CWD`) rather than registering a new behavioural env var
- AND `.env` remains "SECRETS ONLY (keys, tokens, passwords)" — new secret vars are declared in `OPTIONAL_ENV_VARS`
- Source: doc: hermes_cli/AGENTS.md § Config system ".env = SECRETS ONLY" / "if internal code needs an env mirror, bridge it in code"

### Requirement: Shared provider runtime resolver across all surfaces
One provider runtime resolver SHALL serve CLI, gateway, cron jobs, ACP and auxiliary model calls — credential resolution, custom-endpoint resolution, provider registry (`resolve_provider()`), and the shared `/model` switch pipeline — so surfaces cannot diverge on provider semantics.
- Status: VERIFIED
- Evidence: doc: website/docs/developer-guide/provider-runtime.md ("shared provider runtime resolver used across: CLI, gateway, cron jobs, ACP, auxiliary model calls")
- Anchor: `hermes_cli/runtime_provider.py:1044` (`resolve_runtime_provider`), `hermes_cli/auth.py:919` (`is_runtime_provider_routable`), `hermes_cli/model_switch.py:1163` (model switch late-imports `resolve_runtime_provider`)

#### Scenario: Any surface resolves a provider
- **WHEN** one of the surfaces — "CLI, gateway, cron jobs, ACP, auxiliary model calls" — needs provider credentials or endpoint data
- **THEN** the shared provider runtime resolver resolves it "at resolution time to get the canonical `base_url`, `env_vars` priority list, `api_mode`, and `fallback_models` without needing to duplicate that data in multiple files"
- Source: doc: website/docs/developer-guide/provider-runtime.md § "Hermes has a shared provider runtime resolver used across" / "at resolution time to get the canonical `base_url`"

### Requirement: Providers are plugins; adding one needs no resolver branch
A provider SHALL be addable by dropping a plugin that calls `register_provider()` (bundled `plugins/model-providers/<name>/`, or user `plugins/model-providers/` under HERMES_HOME which overrides a bundled provider of the same name); the resolver SHALL pick it up with no new branch, reading canonical `base_url`, `env_vars` priority, `api_mode` and `fallback_models` from the `ProviderProfile`.
- Status: VERIFIED
- Evidence: doc: website/docs/developer-guide/provider-runtime.md (Primary implementation section, verbatim rule)
- Anchor: `providers/__init__.py:140` (`register_provider`), `providers/__init__.py:218` (`get_provider_profile`); `plugins/model-providers/` ships 40 provider dirs at the pin

#### Scenario: Add a provider plugin without touching the resolver
- **WHEN** a new plugin under `plugins/model-providers/<your-provider>/` (or `$HERMES_HOME/plugins/model-providers/<your-provider>/`) calls `register_provider()`
- **THEN** it "is enough for `runtime_provider.py` to pick it up — no branch needed in the resolver itself"
- Source: doc: website/docs/developer-guide/provider-runtime.md § Provider Runtime Resolution "no branch needed in the resolver itself"

#### Scenario: User plugin shadows a bundled provider profile
- **WHEN** a user plugin at `$HERMES_HOME/plugins/model-providers/<name>/` has the same name as a bundled provider
- **THEN** it overrides the bundled plugin (last-writer-wins in `register_provider()`) — third parties can replace any built-in profile without editing the repo
- Source: doc: website/docs/developer-guide/adding-providers.md "override bundled plugins of the same name (last-writer-wins in `register_provider()`)"

### Requirement: Config saves preserve user-authored content
Config writes SHALL write the user's own YAML (stripped of commented-out defaults where applicable) and SHALL NOT overwrite the file with `DEFAULT_CONFIG` verbatim (the gateway reads raw YAML — verbatim dumps clobber intent).
- Status: VERIFIED
- Evidence: doc: hermes_cli/config.py comment ("Never DEFAULT_CONFIG verbatim -- the gateway")
- Anchor: `hermes_cli/config.py:513`

#### Scenario: Saving config.yaml keeps the user's own content
- **WHEN** any `config.yaml` (main or profile) is written
- **THEN** it goes through the atomic writer seam (`atomic_config_write`, which "refuses deletion by omission"), "formatting survives, and the fail-closed unreadable-file guard runs first"
- Source: doc: hermes_cli/AGENTS.md § Config system "refuses deletion by omission" / "formatting survives, and the fail-closed unreadable-file guard runs first"

#### Scenario: Commented boilerplate only appears on a new file
- **WHEN** an existing `config.yaml` is saved
- **THEN** "The commented example blocks are appended only when the file is created" — they are never re-injected over user content
- Source: doc: hermes_cli/AGENTS.md § Config system "The commented example blocks are appended only when the file is created."; test: tests/hermes_cli/test_config_yaml_comment_preservation.py::TestEveryWriterPreservesComments::test_boilerplate_only_on_create

### Requirement: Auxiliary work resolves per task with pinned overrides
Auxiliary (side-LLM) tasks — curator, vision, embedding, title generation, session_search, compression — SHALL resolve through `_resolve_auto_route`, with per-task `provider/model/base_url/reasoning_effort` overrides settable under `auxiliary:` in config.yaml.
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Model and provider resolution
- Anchor: `agent/auxiliary_client.py:4568` (`def _resolve_auto_route`)

#### Scenario: A task pins its own side-LLM route
- **WHEN** auxiliary work (curator, vision, embedding, title generation, session_search, compression) needs a side-LLM call
- **THEN** it "resolves through `agent/auxiliary_client.py::_resolve_auto_route`; each task can pin" "its own `provider/model/base_url/reasoning_effort` under `auxiliary:` in config.yaml"
- Source: doc: agent/AGENTS.md § Model and provider resolution "its own `provider/model/base_url/reasoning_effort` under `auxiliary:` in config.yaml"

### Requirement: Credential pools and fallback models are first-class construction inputs
The agent SHALL accept a `fallback_model` and a `credential_pool` at construction, and fallback/credential resolution chains SHALL be covered by E2E tests with real imports against a temp `HERMES_HOME` (not mocks).
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Model and provider resolution ("Fallback models and credential pools are resolution-chain code: E2E them with real imports against a temp HERMES_HOME, not mocks")
- Anchor: `run_agent.py:274` (`fallback_model: dict | None = None, credential_pool=None`)

#### Scenario: A pooled credential hits a rate limit or 401
- **WHEN** one pooled key "hits a rate limit or billing quota" or returns an auth-expired 401
- **THEN** Hermes "automatically rotates to the next healthy key — keeping your session alive without switching providers"
- Source: doc: website/docs/user-guide/features/credential-pools.md "Hermes automatically rotates to the next healthy key"; [relnote v0.7.0] "401 failures trigger automatic rotation to the next credential"

#### Scenario: The primary provider fails or is unreachable
- **WHEN** the primary provider "returns errors or is unreachable"
- **THEN** "Hermes automatically tries the next provider in the chain" (configured via `fallback_providers`)
- Source: [relnote v2026.3.30 (v0.6.0)] "When your primary provider returns errors or is unreachable, Hermes automatically tries the next provider in the chain."

### Requirement: Rate-limit waiting distinguishes free tier from paid
Only free-tier accounts SHALL end a live turn on a long cooldown; paid providers SHALL wait out `Retry-After` rather than terminate the turn.
- Status: VERIFIED
- Evidence: [PR #129410](https://github.com/NousResearch/hermes-agent/pull/129410) — "only the free tier ends a live turn on a long cooldown; paid providers wait out Retry-After again" — implementation at `agent/turn_recovery.py::free_tier_cooldown_ends_turn`; the same resolver honors Retry-After (capped at RETRY_AFTER_CAP_S) for every retryable provider error
- Anchor: `agent/turn_recovery.py:1519` (`free_tier_cooldown_ends_turn`) — returns True only when `on_free_model(agent, base_url) and is_attended(agent)` (line 1529) and the cooldown exceeds `LIVE_RETRY_WAIT_CAP_S` (1531-1532); `agent/turn_recovery.py:1524` (`free_tier_cooldown_ends_turn` docstring) — "Every other provider, and every unattended run (cron, messaging, `hermes chat -q`), waits out its `Retry-After`: a paid bucket reopens on time"

### Requirement: Nous sign-in is a plain device login
Every Nous sign-in path SHALL use the plain device login flow, and a free-tier guest account SHALL be handed to the real account after sign-in (identity continuity).
- Status: VERIFIED
- Evidence: [PR #143235](https://github.com/NousResearch/hermes-agent/pull/143235) — "every Nous sign-in is the plain device login"; [PR #143234](https://github.com/NousResearch/hermes-agent/pull/143234) — "hand the free-tier guest to the account after sign-in" — every Nous login path funnels through `_nous_device_code_login` (auth_commands.py:351, auth_nous.py:1567/1723, nous_subscription.py:700); guest→account handoff is `hermes_cli/guest_handoff.py` drained after each save
- Anchor: `hermes_cli/auth_nous.py:1460` (`_nous_device_code_login`) — the single Nous sign-in mechanic: "Run the Nous device-code flow and return full OAuth state without persisting"; no PKCE/browser-flow branch exists in the module (grep empty); `hermes_cli/auth_nous.py:1710` (`_login_nous`) — "Nous Portal device authorization flow." — the login entry point calls `_nous_device_code_login` (imported 1713); other callers `hermes_cli/auth_commands.py:351` and `hermes_cli/nous_subscription.py:700` go through the same flow; `hermes_cli/guest_handoff.py:1` (module docstring) — "after a Nous account replaces the free tier, move the free tier's apps into it ... the result (the account email, what moved, what needs reconnecting) is shown afterwards"; drain+settle wired into the save at `hermes_cli/auth_commands.py:321-322`

#### Scenario: A user signs in to Nous
- **WHEN** a user signs in to Nous on any path — "every sign-in"
- **THEN** the plain device login flow runs, and "the free-tier guest hands over to your account, the result shows who signed in"
- AND connectors "offer sign-in instead of opening a guest"
- Source: [relnote v0.22.5] "Nous sign-in reworked (every sign-in is the plain device login, the free-tier guest hands over to your account, the result shows who signed in, connectors offer sign-in instead of opening a guest)"

### Requirement: api_mode selects the wire per provider/model
Model calls SHALL carry an explicit `api_mode` (`"chat_completions" | "codex_responses" | ...`) resolved from the provider profile, and mis-routed families SHALL be corrected at the profile level (e.g. Claude models via a chat-completions-shaped gateway routed to the Messages wire).
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Shape (`api_mode` param of AIAgent); [PR #134848](https://github.com/NousResearch/hermes-agent/pull/134848) — route Claude models to the Messages wire (opencode-go) — at the pin no bundled plugin overrides `api_mode_for_model`; OpenCode Zen/Go route api_mode per model in core (plugins/model-providers/opencode-zen/__init__.py:3; `opencode_model_api_mode` serves the anthropic_messages wire for Claude families at agent/chat_completion_helpers.py:1853-1856)
- Anchor: `providers/base.py:449` (`ProviderProfile.api_mode_for_model`) — "Wire (`api_mode`) this provider serves *model* on, or None to keep the static `api_mode`" (static field `api_mode: str = "chat_completions"` at providers/base.py:147; per-provider values e.g. plugins/model-providers/anthropic/__init__.py:50 `anthropic_messages`, openai-codex/__init__.py:7 `codex_responses`, bedrock/__init__.py:12 `bedrock_converse`); `hermes_cli/runtime_provider.py:274` (`_profile_runtime_api_mode`) — resolves the wire per model from the profile; a stale persisted `codex_responses` is overridden when the profile serves the target model on chat completions (288-290), and the comment at 281-282 names the Claude-slot-misrouted-on-Responses failure; `agent/provider_route_hooks.py:140` (`model_api_mode`) — the single guarded call of `profile.api_mode_for_model` for resolution, `/model`, resume and the agent (146), falling back to the declared `api_mode`

#### Scenario: Switching providers clears the stale wire
- **WHEN** the user switches providers via `hermes model`
- **THEN** Hermes "correctly clears stale `api_mode` instead of hardcoding `chat_completions`", fixing 404s for providers with Anthropic-compatible endpoints
- Source: [relnote v2026.3.30 (v0.6.0)] "switching providers via `hermes model` now correctly clears stale `api_mode` instead of hardcoding `chat_completions`, fixing 404s for providers with Anthropic-compatible endpoints"

### Requirement: Model-visible capability claims match the active model
Capability notes injected to the model SHALL reflect the actually-resolved model (a text-only header must not tell vision-capable models they cannot see images; badges show the runtime model during fallback, not the config value).
- Status: VERIFIED
- Evidence: [PR #131568](https://github.com/NousResearch/hermes-agent/pull/131568) — text-only header no longer tells vision models they cannot see images; [PR #54509](https://github.com/NousResearch/hermes-agent/pull/54509) — badge follows the PTY runtime model, not config, during fallback
- Anchor: `tools/browser_use_cli.py:925-928` (`SCREENSHOTS_DETACHED` comment) — the non-native header "states a transport fact ... never a verdict on the model's own vision: models quote 'your model cannot view images' against themselves and skip user images (#131568)"; `tools/browser_use_cli.py:961` (`_description_header`) — picks `_HEADER_VISION` vs `_HEADER_TEXT_ONLY` (933) based on whether the active route attaches screenshots natively, not on a config guess; `web/src/components/ChatSidebar.tsx:161-167` (`runtimeModel`) — badge model identity comes from the PTY session's `session.info`: "when a provider fallback replaces the configured primary mid-turn (#54509) ... the badge must follow it"; config is only the fallback source (gateway persists the runtime model + `fallback_active` at gateway/run_turn_prepare.py:275)

### Requirement: Context lengths and model capabilities are centralized
Per-model context lengths and capabilities SHALL live in `agent/model_metadata.py` (single source for sizing decisions such as window-derived thresholds).
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Model and provider resolution ("agent/model_metadata.py holds context lengths and capabilities") — module read at the pin: DEFAULT_CONTEXT_LENGTHS family table, MINIMUM_CONTEXT_LENGTH threshold and probe/cache plumbing all in this one module
- Anchor: `agent/model_metadata.py:1` (module docstring) — "Model metadata, context lengths, and token estimation utilities."; `agent/model_metadata.py:295` (`DEFAULT_CONTEXT_LENGTHS`) — the central per-model/family window table, commented at 292 "Family-pattern fallbacks, used only when provider-aware sources all miss"; `agent/model_metadata.py:277` (`MINIMUM_CONTEXT_LENGTH`) — the window-derived sizing threshold; Ollama vision-capability resolution also lives here (:1448)

### Requirement: Bedrock sizes context windows from catalog family fallback
Bedrock model calls SHALL size context windows by falling through to the catalog family window for models without their own entry (Anthropic, OpenAI, xAI families), and SHALL size listed third-party models from their AWS cards.
- Status: VERIFIED
- Evidence: [commit 9625c34f5258] — "fall through to the catalog family window for Anthropic, OpenAI and xAI"; [commit 4b3fba6942d5] — "size GPT-6.1 Terra, GPT-5.4 and third-party models from their AWS cards"
- Anchor: `agent/bedrock_adapter.py:1537` (`_CATALOG_FAMILY_ID_RE`) — `r"(?:^|[./])(?:anthropic|openai|xai)\.([a-z0-9][a-z0-9.:-]*)$"` — exactly the Anthropic/OpenAI/xAI issuers whose catalog family rows match Bedrock cards (issuer comment 1531-1536); `agent/bedrock_adapter.py:1575` (`bedrock_static_context_length`) — static table row first, else falls through to the catalog family window via `_longest_key_match(DEFAULT_CONTEXT_LENGTHS, family.group(1))` (1585-1590); `get_bedrock_context_length` (1593-1594) documents "live probe → static table → catalog family → default"; `agent/bedrock_adapter.py:1507` (BEDROCK_CONTEXT_LENGTHS comment) — third-party rows are "the 'Context window' field of each AWS card (docs.aws.amazon.com/bedrock/latest/userguide/model-card-<vendor>-<model>.html ...)"

### Requirement: Mandatory-thinking Anthropic families keep thinking on the wire
Provider handling SHALL treat mandatory-thinking Claude families (including Claude Mythos) as requiring thinking, so requests for those models are shaped accordingly.
- Status: VERIFIED
- Evidence: [commit ad25cdd478ed] — "treat Claude Mythos as mandatory-thinking"; [commit b27f6ee57c8f] — "name every mandatory-thinking family in the module docstring"
- Anchor: `agent/anthropic_adapter.py:103` (`_MANDATORY_THINKING_CLAUDE_SUBSTRINGS`) — `("claude-fable", "claude-mythos", "claude-opus-5-5", "claude-opus-5.5")`, commented 100-102: thinking is mandatory, `thinking: {"type": "disabled"}` answers HTTP 400, "when in doubt, add the family"; `agent/anthropic_adapter.py:187` (`_accepts_thinking_disable`) — returns False for mandatory-thinking families: they "400 on it and keep the omit behavior" (line 196 excludes them via `_model_matches`); `agent/voice_turn_route.py:94` — "Mandatory-thinking Claude omits the disable and thinks at its default effort" (routes them to the reasoning floor instead of a disable)

### Requirement: Same-issued-second token rotations order by obtained_at
When two credential rotations share one issued-at (`iat`) second, ordering SHALL use `obtained_at`, never expiry, so rotation order stays deterministic.
- Status: VERIFIED
- Evidence: [commit b5bce5c622c5] — "two rotations in one iat second order by obtained_at, never expiry"
- Anchor: `hermes_cli/auth_oauth_grants.py:434` (`oauth_pair_order`) — docstring 437-440: "ISSUE time decides ... Equal whole-second `iat` claims (two rotations in one second) fall to the sub-second local issue stamp" and expiry "only orders pairs lacking an issue stamp"; `hermes_cli/auth_oauth_grants.py:444` — `_sign(ia, ib) or _sign(la, lb) or 0`: iat first, then the local `obtained_at` stamp; expiry is consulted only at 445-449 when neither side carries an issue stamp; `hermes_cli/auth_oauth_grants.py:417` (`_oauth_stamps`) — the local issue stamp is `last_refresh`/`obtained_at` (425); consumed by `hermes_cli/auth_nous.py:417` (`_nous_state_order`) for shared-store merge ordering

## Scenario-ification notes
- REQ "Rate-limit waiting distinguishes free tier from paid": no doc-grounded trigger; kept as invariant. PR #129410 quote is bundle-only; no release-note/doc text covers free-tier-vs-paid cooldown.
- REQ "Model-visible capability claims match the active model": no doc-grounded trigger; PR #131568/#54509 quotes are bundle-only; the v0.23.0 "text-only" note ("Text-only vLLM servers that reject images recover") is a different behavior and was not used.
- REQ "Context lengths and model capabilities are centralized": declaration-only doc sentence ("`agent/model_metadata.py` holds context lengths and capabilities"); no trigger/outcome pair in Tier A/B.
- REQ "Setup-profile models reason at low effort": no Tier A/B text found ("low effort" appears in no release note body); kept as invariant.
- Tail-fold rejections (out of capability): plugin-catalog provider additions (a2d566c6ba52, 002c20612a9b, a44e24065a6a, 9e8eddb4309c, c2ef9764d054, 23fcab925e9b, bd375d9a1587, 36bf5fb3e24a, 45ad6ede6be8, 60f502939461, a0a6a070928d) and catalog bumps/disclosures (f135a9ede721, 5a1b40862233, a31d7a2ef34c, 75d8914a2dc0, c60840e64e90); desktop/test/docs-only commits (48438d0b5cd1, 56601f7c9a92, fd267bb3242a, 446a54d539c9, 21aa2ac26f5c, e7ba4fe1ddf9, 40ca63428b27, 75eef50b8601, b411560709ca); memory-provider config seams (e090092285fa — memory boundary); stt docs (ff09cead02e9, c10474fbb630 — STT capability); 84a0301415ed (background review never asks for a skill's API key — skills capability, already rejected there); a285c4f4ba72 + cf07d2a100b7 (removal of the dead `auxiliary.skills_hub` task — cleanup of an existing requirement's surface, no new contract).

## Known gaps / open questions
- Exact provider-profile schema (fields of `ProviderProfile`) not opened — `providers/base.py` next pass.
- Default-model policy (GLM-5.3 as "silent default", #144810) — where the default is pinned (catalog vs config default) not located; needs a requirement with anchor.
- Bedrock inference-profile routing and 1M-window sizing (#133573) — provider-specific contract, not drafted.
- Config-backend long-form (`website/docs/developer-guide/config-backend.md`) not read — may contain load-precedence requirements (managed scope / profile_routes seen in cron #121212).
- Deferred boundary: plugins/model-providers is a plugins-shaped tree; this spec owns the *resolution contract*, plugins-mcp (deferred) would own plugin lifecycle.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
- Drift (pass 3): the setup-chat low reasoning effort (#129405, added by df150ec10d1e) was removed pre-pin when b120ac575d deleted `hermes_cli/setup_profile.py` (file absent at the pin; no successor forcing low effort found in hermes_cli/, agent/, tui_gateway/). Pass-2 requirement deleted from the set — the spec models merged reality at the pin.
