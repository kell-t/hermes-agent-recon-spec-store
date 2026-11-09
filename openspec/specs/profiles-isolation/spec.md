# Capability: profiles-isolation

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
Profiles are deliberate islands: one Hermes process (gateway, cron, serve) serves many profiles, and every path, secret, log line, and routing decision must answer "which profile owns this" before acting. The capability covers profile-aware paths (`get_hermes_home()`), the secret-scope fail-closed guard, per-event identity canonicalization in the multiplexing gateway, and the lint ratchets (HX001/HX002) that keep the rules enforced. AGENTS.md warns the isolation itself is often the design — absences are load-bearing.

## Primary code locations
- `hermes_constants.py` — `get_hermes_home()` / `display_hermes_home()` / `hermes_home_key()`
- `agent/secret_scope.py` — scoped secret reads, multiplex activation, `UnscopedSecretError`
- `gateway/session_identity.py` — one-identity-per-event resolution (`RoutingIdentity`)
- `hermes_cli/profiles.py` — profiles root (`_get_profiles_root()`)
- `scripts/code_health/config.py` — HX rules enforcement
- `agent/delegation_context.py` — delegated-child env marker

## Requirements

### Requirement: Profile-aware home paths only
All code SHALL obtain the Hermes home through `get_hermes_home()` (paths) and `display_hermes_home()` (user-facing text); a hardcoded `~/.hermes` is a lint failure (HX001) waivable only by an inline `# health: allow HX001 -- <why>` comment.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § "Rules that apply everywhere" (HX001)
**Anchor**: `hermes_constants.py:194` (`get_hermes_home`), `hermes_constants.py:648` (`display_hermes_home`), `scripts/code_health/config.py:104` (Rule HX001 definition)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** All code SHALL obtain the Hermes home through `get_hermes_home()` (paths) and `display_hermes_home()` (user-facing text);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Profiles root is HOME-anchored on purpose
`_get_profiles_root()` SHALL stay anchored to the OS HOME, not the active Hermes home — profiles are siblings of the install's home, and this is intentional isolation, not a bug.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § Rules that apply everywhere ("`_get_profiles_root()` is HOME-anchored on purpose")
**Anchor**: `hermes_cli/profiles.py:287` (`_get_profiles_root`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `_get_profiles_root()` SHALL stay anchored to the OS HOME, not the active Hermes home — profiles are siblings of the install's home, and this is intentional isolation, not a bug.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Fail-closed scoped secrets once multiplex is active
Secret reads SHALL go through `get_secret()` in the caller's profile scope; after `set_multiplex_active(True)` an unscoped read SHALL raise `UnscopedSecretError` (fail closed), and every multi-home host (gateway, cron, migrate, serve) SHALL set the flag or the guard is silently off; a child's `UnscopedSecretError` is a spawn-site bug and never grounds an `os.getenv` fallthrough.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Memory, context engines, curator (secret-scope paragraph)
**Anchor**: `agent/secret_scope.py:39` (`set_multiplex_active`), `agent/secret_scope.py:126` (`class UnscopedSecretError`), `agent/secret_scope.py:230` (`get_secret`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Secret reads SHALL go through `get_secret()` in the caller's profile scope;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Out-of-turn code binds the owning profile explicitly
Code that runs outside a turn (boot probes, eviction, tickers, deferred callbacks, RPC methods, thread hops, child spawns) SHALL bind the owning profile's scope explicitly, because `os.environ`, module globals and import-time values hold the launch profile's — an unbound read is a silent default-profile leak.
**Status**: INFERRED
**Evidence**: doc: AGENTS.md (root) § Rules that apply everywhere (HX002/HX004/HX005/HX012, PS-P05/P06); [PR #125974](https://github.com/NousResearch/hermes-agent/pull/125974) — "log to the active profile home, not the import-time freeze"
**Anchor**: `scripts/code_health/config.py:110` (HX rule machinery) — the per-seam binding list lives in gateway/AGENTS.md § Profile scope


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Code that runs outside a turn (boot probes, eviction, tickers, deferred callbacks, RPC methods, thread hops, child spawns) SHALL bind the owning profile's scope explicitly, because `os.environ`, module globals and import-time values hold the launch profile's — an unbound read is a silent default-pro
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: One canonical identity per inbound event
The gateway SHALL resolve "which bot received it / who may admit it / where does it run" exactly once per inbound event (`resolve_identity`) and pin a frozen `RoutingIdentity` on the source; every ingress path canonicalizes before deriving any session/profile key, and code SHALL NOT derive a second answer next to the identity.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Profile scope ("One identity per inbound event, canonicalized FIRST")
**Anchor**: `gateway/session_identity.py:44` (`class RoutingIdentity`), `gateway/session_identity.py:201` (`resolve_identity`), `gateway/run.py:4197` (`_resolve_profile_home_for_source` reads the identity)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The gateway SHALL resolve "which bot received it / who may admit it / where does it run" exactly once per inbound event (`resolve_identity`) and pin a frozen `RoutingIdentity` on the source;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Unroutable events are dropped, never mis-keyed
Under multiplexing, an event whose identity resolves to an unserved profile SHALL be dropped with a single WARNING at the first seam and SHALL never be keyed into `agent:main`; a route to a parked profile SHALL tell the sender in-channel to resend, and unacknowledged transport dispatch SHALL answer a retryable 503 instead.
**Status**: INFERRED
**Evidence**: doc: gateway/AGENTS.md § Profile scope (`parked_route_refusal.drop_rejected_route`, `ParkedProfileRefusal`, `retryable_ingress()`)
**Anchor**: `gateway/session_identity.py` (refusal machinery — named in doc, lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Under multiplexing, an event whose identity resolves to an unserved profile SHALL be dropped with a single WARNING at the first seam and SHALL never be keyed into `agent:main`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Launch home .env stays loaded under multiplex routing
Multiplex routing SHALL still load the launch home's `.env` (host-level secrets remain available) while per-profile secrets route to the resolved profile.
**Status**: INFERRED
**Evidence**: [PR #125530](https://github.com/NousResearch/hermes-agent/pull/125530) — "still load the launch home's .env under multiplex routing"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Multiplex routing SHALL still load the launch home's `.env` (host-level secrets remain available) while per-profile secrets route to the resolved profile.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Serve profiles created after boot
A gateway that booted single-profile SHALL serve a newly created profile in place without a restart.
**Status**: INFERRED
**Evidence**: [PR #141623](https://github.com/NousResearch/hermes-agent/pull/141623) — "serve a profile created after a single-profile boot in place, without a restart"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A gateway that booted single-profile SHALL serve a newly created profile in place without a restart.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Delegated children carry a valued environment marker
A delegated child process SHALL carry the `HERMES_DELEGATED_CHILD_CONTEXT` marker valued as the fenced Kanban board root (not a bare flag), so spawn-site fencing is provable in the child environment.
**Status**: VERIFIED
**Evidence**: doc: agent/AGENTS.md § Memory/context/curator ("Delegated children carry delegation_context.py::DELEGATED_CHILD_ENV_MARKER valued as the fenced Kanban board root")
**Anchor**: `agent/delegation_context.py:20` (`DELEGATED_CHILD_ENV_MARKER = "HERMES_DELEGATED_CHILD_CONTEXT"`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A delegated child process SHALL carry the `HERMES_DELEGATED_CHILD_CONTEXT` marker valued as the fenced Kanban board root (not a bare flag), so spawn-site fencing is provable in the child environment.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: No new HERMES_* env vars for non-secret behavior
Behavioral settings SHALL NOT arrive as new `HERMES_*` environment variables (`.env` is secrets only; behavior lives in `config.yaml`), enforced by lint rule HX002.
**Status**: VERIFIED
**Evidence**: doc: AGENTS.md (root) § Contribution rubric ("Rejected even when well-built"); doc: AGENTS.md § Rules that apply everywhere
**Anchor**: `scripts/code_health/config.py:110` (Rule HX002 "new HERMES_* environment variable")


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Behavioral settings SHALL NOT arrive as new `HERMES_*` environment variables (`.env` is secrets only;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Process identity via designated predicates
Process identity SHALL never be inferred from argv substrings; code SHALL use the designated identity predicates (e.g. `gateway.status.looks_like_gateway_command_line`, `hermes_cli.update_cmd._hermes_holder_subcommand`) per lint rule HX003.
**Status**: INFERRED
**Evidence**: doc: AGENTS.md (root) § Rules that apply everywhere (HX003; details hermes_cli/AGENTS.md)
**Anchor**: not located (predicates in gateway/status.py / hermes_cli/update_cmd.py — not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Process identity SHALL never be inferred from argv substrings;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Legacy custom-home units are adopted
The gateway SHALL adopt a bare legacy user systemd unit that pins a custom `HERMES_HOME` into the profile-routed lifecycle rather than running it unmanaged.
**Status**: INFERRED
**Evidence**: [PR #109476](https://github.com/NousResearch/hermes-agent/pull/109476) — "adopt a bare legacy user unit that pins this custom HERMES_HOME"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The gateway SHALL adopt a bare legacy user systemd unit that pins a custom `HERMES_HOME` into the profile-routed lifecycle rather than running it unmanaged.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Terminal session isolation keys qualify by profile
Session-isolated container keys and cwd records SHALL be qualified under the routed profile scope so two profiles never share a container identity.
**Status**: INFERRED
**Evidence**: [PR #123989](https://github.com/NousResearch/hermes-agent/pull/123989) — "qualify session-isolated container keys and cwd records under a routed profile scope"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Session-isolated container keys and cwd records SHALL be qualified under the routed profile scope so two profiles never share a container identity.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- `transport_profile` ≠ `runtime_profile` (shared bot → routed satellite) is declared normal in gateway/AGENTS.md but the split's full contract is only partly drafted; needs a requirement once anchors are opened.
- Many bundle PRs for profile-scoped reads are desktop-UI (`#125969`, `#121966`, `#92569`, `#130714`) — excluded to deferred desktop-ui; the underlying "scope reads/writes to the viewed profile" rule may deserve a cross-cutting requirement in GROUNDWORK.
- PS-P05/P06 seam list (gateway/AGENTS.md § Profile scope) not enumerated into requirements — 10+ individual contracts; pass 2 candidate.
- `hermes_dir_acl` per-profile directory ACLs (imported by hermes_state) not drafted — UNVERIFIED.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
