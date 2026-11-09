# Capability: profiles-isolation

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 3 (scenario-ification) applied 2026-11-08

## Summary
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
- Status: VERIFIED
- Evidence: doc: AGENTS.md (root) § "Rules that apply everywhere" (HX001)
- Anchor: `hermes_constants.py:194` (`get_hermes_home`), `hermes_constants.py:648` (`display_hermes_home`), `scripts/code_health/config.py:104` (Rule HX001 definition)

#### Scenario: Home paths come from the profile-aware resolvers
- **WHEN** code needs the Hermes home for a path or for user-facing text
- **THEN** it SHALL use `get_hermes_home()` for paths and `display_hermes_home()` for text — never hardcode `~/.hermes` (HX001)
- **AND** the lint finding is waivable only by a health-allow comment (`# health: allow <RULE> -- <why>`; `# noqa` does not waive)
- Source: doc: AGENTS.md (root) § Rules that apply everywhere "Never hardcode `~/.hermes`"
- Source: doc: AGENTS.md (root) § Development Environment "`# health: allow <RULE> -- <why>` does"

### Requirement: Profiles root is HOME-anchored on purpose
`_get_profiles_root()` SHALL stay anchored to the OS HOME, not the active Hermes home — profiles are siblings of the install's home, and this is intentional isolation, not a bug.
- Status: VERIFIED
- Evidence: doc: AGENTS.md (root) § Rules that apply everywhere ("`_get_profiles_root()` is HOME-anchored on purpose")
- Anchor: `hermes_cli/profiles.py:287` (`_get_profiles_root`)

#### Scenario: Profile roots resolve beside HOME even when the active home moves
- **WHEN** profiles are enumerated while the active Hermes home is anywhere else
- **THEN** `_get_profiles_root()` SHALL still resolve from the OS HOME — profiles stay siblings of the install's home
- **AND** this is deliberate: profiles are islands on purpose, not a bug to re-anchor
- Source: doc: AGENTS.md (root) § Rules that apply everywhere "`_get_profiles_root()` is HOME-anchored on purpose."
- Source: doc: AGENTS.md (root) § Contribution rubric "profiles are islands on purpose"

### Requirement: Fail-closed scoped secrets once multiplex is active
Secret reads SHALL go through `get_secret()` in the caller's profile scope; after `set_multiplex_active(True)` an unscoped read SHALL raise `UnscopedSecretError` (fail closed), and every multi-home host (gateway, cron, migrate, serve) SHALL set the flag or the guard is silently off; a child's `UnscopedSecretError` is a spawn-site bug and never grounds an `os.getenv` fallthrough.
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Memory, context engines, curator (secret-scope paragraph)
- Anchor: `agent/secret_scope.py:39` (`set_multiplex_active`), `agent/secret_scope.py:126` (`class UnscopedSecretError`), `agent/secret_scope.py:230` (`get_secret`)

#### Scenario: An unscoped read fails closed once multiplex is active
- **WHEN** a secret is read unscoped after multiplex activation (`set_multiplex_active(True)`)
- **THEN** `get_secret` SHALL fail closed with `UnscopedSecretError`
- **AND** the multi-home hosts — the gateway, cron, migrate and `serve` — each set the flag
- Source: doc: agent/AGENTS.md § secret scope "fails closed (`UnscopedSecretError`) only after"
- Source: doc: agent/AGENTS.md § secret scope "the gateway, cron, migrate and `serve` set it"

#### Scenario: A child's UnscopedSecretError never licenses an os.getenv fallthrough
- **WHEN** a spawned child raises `UnscopedSecretError`
- **THEN** it SHALL be treated as a spawn-site bug, never grounds for an `os.getenv` fallthrough
- **AND** with scope installed and multiplex active, a scoped miss returns the default profile's value, never `os.environ`
- Source: doc: agent/AGENTS.md § secret scope "is a spawn-site bug, never grounds for an"
- Source: doc: gateway/AGENTS.md § Profile scope "a scoped miss returns the **default**, NEVER `os.environ`"

### Requirement: Out-of-turn code binds the owning profile explicitly
Code that runs outside a turn (boot probes, eviction, tickers, deferred callbacks, RPC methods, thread hops, child spawns) SHALL bind the owning profile's scope explicitly, because `os.environ`, module globals and import-time values hold the launch profile's — an unbound read is a silent default-profile leak.
- Status: INFERRED
- Evidence: doc: AGENTS.md (root) § Rules that apply everywhere (HX002/HX004/HX005/HX012, PS-P05/P06); [PR #125974](https://github.com/NousResearch/hermes-agent/pull/125974) — "log to the active profile home, not the import-time freeze"
- Anchor: `scripts/code_health/config.py:110` (HX rule machinery) — the per-seam binding list lives in gateway/AGENTS.md § Profile scope

#### Scenario: Out-of-turn code binds the owning scope explicitly
- **WHEN** code runs outside a turn (boot probes, eviction, tickers, deferred callbacks, RPC methods, thread hops, child spawns)
- **THEN** it SHALL bind the owning profile scope explicitly
- **AND** an unbound read is a silent default-profile leak, because `os.environ`, module globals and import-time values hold the launch profile's
- Source: doc: AGENTS.md (root) § Rules that apply everywhere "binds the owning profile scope"
- Source: doc: AGENTS.md (root) § Rules that apply everywhere "unbound read is a silent default-profile leak."

#### Scenario: Eviction must flush under the OWNING profile's scope
- **WHEN** session release/eviction or shutdown finalization runs with no turn on the stack
- **THEN** it SHALL re-enter the owning profile's scope (TTL, LRU and memory-pressure eviction all route through `_run_release_in_profile_scope`)
- **AND** the guarded incident: eviction that flushed under the launch scope wrote a secondary profile's memories into the default profile's store, silently
- Source: doc: gateway/AGENTS.md § Profile scope "touches a session's home, secrets or terminal scope with no turn on the stack"
- Source: doc: gateway/AGENTS.md § Profile scope "wrote a secondary profile's memories into the default profile's store"

### Requirement: One canonical identity per inbound event
The gateway SHALL resolve "which bot received it / who may admit it / where does it run" exactly once per inbound event (`resolve_identity`) and pin a frozen `RoutingIdentity` on the source; every ingress path canonicalizes before deriving any session/profile key, and code SHALL NOT derive a second answer next to the identity.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Profile scope ("One identity per inbound event, canonicalized FIRST")
- Anchor: `gateway/session_identity.py:44` (`class RoutingIdentity`), `gateway/session_identity.py:201` (`resolve_identity`), `gateway/run.py:4197` (`_resolve_profile_home_for_source` reads the identity)

#### Scenario: Identity is canonicalized before any key derivation
- **WHEN** an inbound event reaches any ingress path (adapter or runner side)
- **THEN** `resolve_identity` SHALL answer "which bot received it / who may admit it / where does it run" exactly once and pin a frozen `RoutingIdentity` on the source
- **AND** no key derivation happens before it, and code never derives a second answer next to the identity
- Source: doc: gateway/AGENTS.md § Profile scope 'answers "which bot received it / who may admit it / where does it run" ONCE per event and pins a'
- Source: doc: gateway/AGENTS.md § Profile scope "frozen `RoutingIdentity` on the source"
- Source: doc: gateway/AGENTS.md § Profile scope "Never derive a second answer"

### Requirement: Unroutable events are dropped, never mis-keyed
Under multiplexing, an event whose identity resolves to an unserved profile SHALL be dropped with a single WARNING at the first seam and SHALL never be keyed into `agent:main`; a route to a parked profile SHALL tell the sender in-channel to resend, and unacknowledged transport dispatch SHALL answer a retryable 503 instead.
- Status: INFERRED
- Evidence: doc: gateway/AGENTS.md § Profile scope (`parked_route_refusal.drop_rejected_route`, `ParkedProfileRefusal`, `retryable_ingress()`)
- Anchor: `gateway/session_identity.py` (refusal machinery — named in doc, lines not opened)

#### Scenario: A route to an unserved profile is dropped, never mis-keyed
- **WHEN** an unresolved identity under multiplexing routes to an unserved profile
- **THEN** the event SHALL be dropped with one WARNING at the first seam it reaches, never keyed into `agent:main`
- **AND** a route to a parked profile also tells the sender in-channel to resend (a direct bot's update is already confirmed and never redelivered)
- **AND** a dispatch whose transport has not acknowledged yet (e.g. Google Chat HTTP events) runs in `retryable_ingress()` and answers `ParkedRouteRefused` (503) instead
- Source: doc: gateway/AGENTS.md § Profile scope "with one WARNING at the first seam it reaches, never keyed into `agent:main`"
- Source: doc: gateway/AGENTS.md § Profile scope "also tells the sender"
- Source: doc: gateway/AGENTS.md § Profile scope "in-channel to resend"
- Source: doc: gateway/AGENTS.md § Profile scope "answers `ParkedRouteRefused` (503) instead"

### Requirement: Launch home .env stays loaded under multiplex routing
Multiplex routing SHALL still load the launch home's `.env` (host-level secrets remain available) while per-profile secrets route to the resolved profile.
- Status: INFERRED
- Evidence: [PR #125530](https://github.com/NousResearch/hermes-agent/pull/125530) — "still load the launch home's .env under multiplex routing"
- Anchor: not located

### Requirement: Serve profiles created after boot
A gateway that booted single-profile SHALL serve a newly created profile in place without a restart.
- Status: INFERRED
- Evidence: [PR #141623](https://github.com/NousResearch/hermes-agent/pull/141623) — "serve a profile created after a single-profile boot in place, without a restart"
- Anchor: not located

### Requirement: Delegated children carry a valued environment marker
A delegated child process SHALL carry the `HERMES_DELEGATED_CHILD_CONTEXT` marker valued as the fenced Kanban board root (not a bare flag), so spawn-site fencing is provable in the child environment.
- Status: VERIFIED
- Evidence: doc: agent/AGENTS.md § Memory/context/curator ("Delegated children carry delegation_context.py::DELEGATED_CHILD_ENV_MARKER valued as the fenced Kanban board root")
- Anchor: `agent/delegation_context.py:20` (`DELEGATED_CHILD_ENV_MARKER = "HERMES_DELEGATED_CHILD_CONTEXT"`)

#### Scenario: The child marker carries a board root, not a flag
- **WHEN** a delegated child is spawned
- **THEN** it SHALL carry `DELEGATED_CHILD_ENV_MARKER` valued as the fenced Kanban board root, not a bare flag
- Source: doc: agent/AGENTS.md § secret scope "valued as the fenced Kanban board root, not a bare flag"

#### Scenario: The fence denies only mutations on the fenced paths
- **WHEN** a delegated child writes Kanban paths inside its fenced context
- **THEN** `kanban_path_is_fenced(path)` SHALL deny mutations only on the dispatcher-pinned `HERMES_KANBAN_DB` or under the fenced root
- **AND** a child working against a scratch `HERMES_HOME` keeps a writable board
- Source: doc: cron/AGENTS.md § Kanban "so a child working against a scratch `HERMES_HOME` keeps a writable board"

### Requirement: No new HERMES_* env vars for non-secret behavior
Behavioral settings SHALL NOT arrive as new `HERMES_*` environment variables (`.env` is secrets only; behavior lives in `config.yaml`), enforced by lint rule HX002.
- Status: VERIFIED
- Evidence: doc: AGENTS.md (root) § Contribution rubric ("Rejected even when well-built"); doc: AGENTS.md § Rules that apply everywhere
- Anchor: `scripts/code_health/config.py:110` (Rule HX002 "new HERMES_* environment variable")

#### Scenario: A new HERMES_* env var for behavior is rejected
- **WHEN** a contribution introduces a new `HERMES_*` environment variable for non-secret config
- **THEN** it is rejected even when well-built — `.env` is secrets only, behaviour goes in `config.yaml`
- Source: doc: AGENTS.md (root) § Contribution rubric "Rejected even when well-built"
- Source: doc: AGENTS.md (root) § Contribution rubric "(`.env` is secrets only, behaviour goes in `config.yaml`)"

### Requirement: Process identity via designated predicates
Process identity SHALL never be inferred from argv substrings; code SHALL use the designated identity predicates (e.g. `gateway.status.looks_like_gateway_command_line`, `hermes_cli.update_cmd._hermes_holder_subcommand`) per lint rule HX003.
- Status: INFERRED
- Evidence: doc: AGENTS.md (root) § Rules that apply everywhere (HX003; details hermes_cli/AGENTS.md)
- Anchor: not located (predicates in gateway/status.py / hermes_cli/update_cmd.py — not opened)

#### Scenario: Process identity comes from predicates, never argv text
- **WHEN** code must decide what kind of process it is looking at (e.g. is this a gateway command line)
- **THEN** it SHALL use the designated identity predicates (`gateway.status.looks_like_gateway_command_line`, `hermes_cli.update_cmd._hermes_holder_subcommand`) — never infer process identity from argv substrings (HX003)
- **AND** the trap is real: `kanban --preserve-cache` contains "serve"
- Source: doc: AGENTS.md (root) § Rules that apply everywhere "Never infer process identity from argv substrings"
- Source: doc: cron/AGENTS.md § Kanban "`kanban --preserve-cache` contains"
- Source: doc: cron/AGENTS.md § Kanban "never classify processes by argv"

### Requirement: Legacy custom-home units are adopted
The gateway SHALL adopt a bare legacy user systemd unit that pins a custom `HERMES_HOME` into the profile-routed lifecycle rather than running it unmanaged.
- Status: INFERRED
- Evidence: [PR #109476](https://github.com/NousResearch/hermes-agent/pull/109476) — "adopt a bare legacy user unit that pins this custom HERMES_HOME"
- Anchor: not located

### Requirement: Terminal session isolation keys qualify by profile
Session-isolated container keys and cwd records SHALL be qualified under the routed profile scope so two profiles never share a container identity.
- Status: INFERRED
- Evidence: [PR #123989](https://github.com/NousResearch/hermes-agent/pull/123989) — "qualify session-isolated container keys and cwd records under a routed profile scope"
- Anchor: not located

## Sub-area: Tail fold (commits after 2026-10-27)

### Requirement: Force-install swap dirs stay out of skill discovery
When a profile distribution force-install stages a swap, the staged/locked old-tree swap directories SHALL NOT be visible to skill discovery, and a copy or swap that fails part-way SHALL keep the old tree in place.
- Status: INFERRED
- Evidence: [commit f6e40b0105ff] — keep force-install swap dirs out of skill discovery; [commit b04acfce7f29] — keep the force-install swap inside `_replace_entry`
- Anchor: not located (hermes_cli profile-distribution swap path)

#### Scenario: A locked old tree left by a force install is not a second profile copy
- **WHEN** a force install swaps in a new tree and leaves the locked old tree staged
- **THEN** skill discovery SHALL not pick the staged swap dir up as content
- **AND** a copy or swap that fails part-way keeps the existing tree (or restores it)
- Source: test: tests/hermes_cli/test_profile_distribution_swap.py::test_force_install_locked_old_tree_is_not_discovered
- Source: test: tests/hermes_cli/test_profile_distribution_swap.py::test_force_install_restores_existing_dir_when_staged_swap_fails

### Requirement: Same-named MCP stdio servers get one connection/child per profile
Under multiplex, an MCP server defined in two profiles with different credentials/secret-source values SHALL get its own connection (and its own stdio child) per profile — a same-named server never shares one process across profiles.
- Status: INFERRED
- Evidence: [commit 8819d8830861] — a same-named stdio server gets its own child per profile; [commit ca14c438e486] — an unscoped multiplex load keeps plugin servers after a ${VAR}-templated one
- Anchor: not located (MCP connection-key path)

#### Scenario: Different credentials, separate connection
- **WHEN** two profiles run a same-named MCP server with other credentials (or another secret-source-resolved value)
- **THEN** each profile SHALL hold a separate connection — and its own stdio child
- Source: test: tests/tools/test_mcp_multiplex_connection_keys.py::test_same_named_server_with_other_credentials_is_a_separate_connection
- Source: test: tests/tools/test_mcp_shared_connection_resolved_identity.py::test_profile_with_other_secret_source_value_gets_its_own_stdio_connection

### Requirement: An older shared login never replaces a newer profile login
A profile SHALL NOT adopt another account's newer shared Nous login: the profile keeps its own refresh token while the shared store keeps the other account's.
- Status: INFERRED
- Evidence: [commit b29bf60b3a32] — an older shared login never replaces a newer profile login
- Anchor: not located (auth_nous shared-store merge path)

#### Scenario: Profiles are islands across the shared OAuth store
- **WHEN** the shared store holds a newer login for a different account than the profile's
- **THEN** the profile SHALL keep its own refresh token (account B's shared login is not account A's next refresh token)
- **AND** the shared store keeps account B's token untouched
- Source: test: tests/hermes_cli/test_nous_shared_store_freshness.py::test_a_profile_never_adopts_another_accounts_newer_shared_login

## Known gaps / open questions
- `transport_profile` ≠ `runtime_profile` (shared bot → routed satellite) is declared normal in gateway/AGENTS.md but the split's full contract is only partly drafted; needs a requirement once anchors are opened.
- Many bundle PRs for profile-scoped reads are desktop-UI (`#125969`, `#121966`, `#92569`, `#130714`) — excluded to deferred desktop-ui; the underlying "scope reads/writes to the viewed profile" rule may deserve a cross-cutting requirement in GROUNDWORK.
- PS-P05/P06 seam list (gateway/AGENTS.md § Profile scope) not enumerated into requirements — 10+ individual contracts; pass 2 candidate.
- `hermes_dir_acl` per-profile directory ACLs (imported by hermes_state) not drafted — UNVERIFIED.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.

## Scenario-ification notes
- REQ "Launch home .env stays loaded under multiplex routing": no doc-grounded trigger; kept as invariant. (#125530's wording exists only as a bundle commit title; no release-note/doc/test pair found. Adjacent gateway/AGENTS.md text covers `.env`-over-frozen-env for the standalone path — a different contract.)
- REQ "Serve profiles created after boot": no doc-grounded trigger; kept as invariant. (#141623 not in any release-note body; the nearest documented re-enumeration is the cron ticker supervision rule, not gateway serving.)
- REQ "Legacy custom-home units are adopted": no doc-grounded trigger; kept as invariant. (commit-title-only evidence; the 0.22.2 boot-guard bullet is a different pidfile-misread story.)
- REQ "Terminal session isolation keys qualify by profile": no doc-grounded trigger; kept as invariant. (#123989 commit-title-only.)
- Tail items rejected (out of capability ownership): ~25 desktop per-gateway/remote-profile commits (2026-11-01 cluster, 7019faa6c470, ae95c1caffae, fcdca2dbd4d8, 5f60d72b65dd, ...), webapp voice-relay/profile-serving (1e81ee57e326), docker s6 supervision (c08c48530595, infrastructure), checkpoints snapshot scope (201326cf5894, area boundary), memory-provider lifecycle seams (e090092285fa, memory capability), plugins per-profile Update-all wording (d063eefc6797), update holder-flag listing (6b2895cacb85), test-fixture chores (6112c2adb9e1, 3e0985d01719, b5182f334298).
- Doc-vs-code surprise (flagged, not fixed): gateway/AGENTS.md § Profile scope documents `transport_profile` ≠ `runtime_profile` as normal routing, while several bundle PRs treat cross-profile leaks of the same values as bugs — the boundary between "legitimate split" and "leak" is prose-only and needs an anchored contract (already noted in Known gaps).
