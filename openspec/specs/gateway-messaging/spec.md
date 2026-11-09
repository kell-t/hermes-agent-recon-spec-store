# Capability: gateway-messaging

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
The messaging gateway runs the same agent core on ~20 chat platforms (Telegram, Discord, Slack, WhatsApp, Signal, relay, api_server, ...). It owns platform adapters over a shared base, two-stage inbound message guards, streaming delivery contracts, background-process completion notifications, authorization, and the multiplexer that serves many profiles from one process. Code lives behind the `gateway/run.py` facade with `run_*.py` phases, `session*.py`, and `platforms/<name>.py` adapters over `platforms/base.py`.

## Primary code locations
- `gateway/run.py` + `gateway/run_*.py` — facade and phases (startup, inbound, busy, notifications, shutdown)
- `gateway/platforms/base.py` — adapter base (queueing, streaming contract, access policy mixins)
- `gateway/platforms/ADDING_A_PLATFORM.md` — adapter authoring contract
- `gateway/run_busy.py` — mid-run command guards and handler table
- `gateway/run_notifications.py` — background process watchers / internal event admission
- `gateway/session*.py`, `gateway/authz_mixin.py`, `gateway/config_loader.py`

## Requirements

### Requirement: Two sequential inbound guards with approval-command bypass
While an agent turn is running, inbound messages SHALL pass two guards — the base adapter queues them into `_pending_messages` per session key, then the runner intercepts control commands (`/stop`, `/new`, `/queue`, `/status`, `/approve`, `/deny`) — and any command that must reach the runner while the agent is blocked SHALL bypass both guards and dispatch inline, never via the background processing path that races session lifecycle.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § "The gateway has TWO message guards"; merge behavior visible in queueing code
**Anchor**: `gateway/platforms/base.py:1882` (`_pending_messages` dict), `gateway/platforms/base.py:3747` (merge_pending_message_event), `gateway/run_busy.py:1049` (`_PLAIN_COMMANDS`), `gateway/run_busy.py:1055` (`_IDLE_COMMANDS`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** While an agent turn is running, inbound messages SHALL pass two guards — the base adapter queues them into `_pending_messages` per session key, then the runner intercepts control commands (`/stop`, `/new`, `/queue`, `/status`, `/approve`, `/deny`) — and any command that must reach the runner while t
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Table-driven slash dispatch
Slash command handlers SHALL be looked up by name through a command handler table distinguishing mid-run (plain) and idle command sets; conditional `if canonical == ...` chains SHALL NOT be used.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Shape
**Anchor**: `gateway/run_busy.py:1063` (`_command_handler_table`), `gateway/run_busy.py:1073,1093`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Slash command handlers SHALL be looked up by name through a command handler table distinguishing mid-run (plain) and idle command sets;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Prefix-stable draft streaming frames
For stream-is-the-message adapters (`draft_stream_is_message = True`), draft frames SHALL be prefix-stable (frame N a string prefix of frame N+1); per-tick mutation of drafts (fence-closing, cursor suffixes, segment resets, markdown conversion) SHALL NOT occur, because a non-prefix frame forces whole-snapshot re-append and recreates duplicate finals.
**Status**: INFERRED
**Evidence**: doc: gateway/AGENTS.md § Streaming delivery contract (four invariants, each from a live duplicate-final incident); contract tests `tests/gateway/test_stream_final_contract.py`; [PR #141014](https://github.com/NousResearch/hermes-agent/pull/141014) — keep two invariants for the hosted prompt digest (test)
**Anchor**: not located (attribute `draft_stream_is_message` present in `gateway/platforms/` and `gateway/relay/adapter.py` per grep, line not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** For stream-is-the-message adapters (`draft_stream_is_message = True`), draft frames SHALL be prefix-stable (frame N a string prefix of frame N+1);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Consumer declares the final, adapter never guesses
The streaming finish path SHALL carry the completed `final_response` in `finish(final_text)`; post-stream augmentation MUST ride this payload, and mutating `final_response` after the seal SHALL trigger corrective reconcile rather than silent divergence.
**Status**: INFERRED
**Evidence**: doc: gateway/AGENTS.md § Streaming delivery contract invariant 2 (`delivered_final_matches` mismatch → corrective duplicate send)
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The streaming finish path SHALL carry the completed `final_response` in `finish(final_text)`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Interim sends marked, seal interception at every egress door
Any adapter send that is not the turn-final SHALL set `metadata["_interim_send"] = True`; seal-interception SHALL exist at both egress doors (`send()` and `send_for_platform()`), and a new egress door SHALL add the same checks.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Streaming delivery contract invariant 3
**Anchor**: `gateway/stream_consumer_fallback.py`, `gateway/relay/adapter.py`, `gateway/run.py` (grep hits for `_interim_send`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Any adapter send that is not the turn-final SHALL set `metadata["_interim_send"] = True`;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Reconcile by edit, never by plain send
A lane delivering a final beside a sealed native stream SHALL first try `edit_message` on the consumer's message id and SHALL fall back to plain `send()` only when no editable message exists.
**Status**: INFERRED
**Evidence**: doc: gateway/AGENTS.md § Streaming delivery contract invariant 4 ("live-verified" chat.update)
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A lane delivering a final beside a sealed native stream SHALL first try `edit_message` on the consumer's message id and SHALL fall back to plain `send()` only when no editable message exists.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Background process completion starts a turn via admitted internal events
A backgrounded terminal process armed with completion notification SHALL have its watcher admitted on the gateway loop only through an `admit_internal_event` receipt (a handler returning None is not acceptance), and refused admission SHALL refund claimed batch siblings without spending an attempt.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Background process notifications
**Anchor**: `gateway/run_notifications.py:1828` (`arm_process_watcher`), `gateway/run_notifications.py:1017` (`await admit_internal_event(...)`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A backgrounded terminal process armed with completion notification SHALL have its watcher admitted on the gateway loop only through an `admit_internal_event` receipt (a handler returning None is not acceptance), and refused admission SHALL refund claimed batch siblings without spending an attempt.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Platform adapters follow a documented contract over a shared base
New platform adapters SHALL implement the step-by-step adapter contract against `platforms/base.py` (access policy, exec approval, log safety, post-delivery, streaming TTS mixins), and each adapter SHALL pick a base toolset (Telegram → `"messaging"`).
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Shape; doc: gateway/platforms/ADDING_A_PLATFORM.md
**Anchor**: `gateway/platforms/ADDING_A_PLATFORM.md`, `gateway/platforms/base.py` (mixin files: `base_exec_approval.py`, `access_policy_mixin.py`, `base_log_safety.py`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** New platform adapters SHALL implement the step-by-step adapter contract against `platforms/base.py` (access policy, exec approval, log safety, post-delivery, streaming TTS mixins), and each adapter SHALL pick a base toolset (Telegram → `"messaging"`).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Gateway reads user YAML raw
The gateway SHALL read user YAML configuration directly (not through CLI defaults merging), so gateway-visible keys are governed by the gateway loader.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § Shape ("a key the CLI sees but the gateway doesn't means you're on the wrong loader")
**Anchor**: `gateway/config_loader.py:220` (per-platform key list incl. `dm_policy`, `allow_from`, `allow_admin_from`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The gateway SHALL read user YAML configuration directly (not through CLI defaults merging), so gateway-visible keys are governed by the gateway loader.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Admin gating opt-in per platform
Per-platform slash access control SHALL be active only when the operator set `allow_admin_from`, and in-flight agents SHALL not bypass admin gating.
**Status**: VERIFIED
**Evidence**: doc: gateway/AGENTS.md § `/login` ("shared gateways must set allow_admin_from")
**Anchor**: `gateway/run_inbound.py:839`, `gateway/run_busy.py:1387`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Per-platform slash access control SHALL be active only when the operator set `allow_admin_from`, and in-flight agents SHALL not bypass admin gating.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Multiplexed gateways serve profiles created after boot
Under multiplexing, the gateway SHALL serve a profile created after a single-profile boot in place without restart, SHALL still load the launch home's `.env` under multiplex routing, and SHALL store per-conversation offers in the routed profile.
**Status**: INFERRED
**Evidence**: [PR #141623](https://github.com/NousResearch/hermes-agent/pull/141623) — serve a profile created after a single-profile boot in place, without a restart; [PR #125530](https://github.com/NousResearch/hermes-agent/pull/125530) — still load the launch home's .env under multiplex routing; [PR #127818](https://github.com/NousResearch/hermes-agent/pull/127818) — first-contact note only in DMs, offer flag saved in the routed profile
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Under multiplexing, the gateway SHALL serve a profile created after a single-profile boot in place without restart, SHALL still load the launch home's `.env` under multiplex routing, and SHALL store per-conversation offers in the routed profile.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Multi-tenant gateway isolation
A second tenant's host gateway SHALL never be attached to, refused as, or reported as ours.
**Status**: INFERRED
**Evidence**: [PR #121352](https://github.com/NousResearch/hermes-agent/pull/121352) — "a second tenant's host gateway never attaches, refuses, or reports as ours"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A second tenant's host gateway SHALL never be attached to, refused as, or reported as ours.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Telegram topic and edit routing fidelity
Telegram routing SHALL follow a new DM topic by time rather than message-id adjacency, SHALL keep an edit of an older lobby message in its room, and an edit of an already-sent message SHALL NOT be rejected with an admission conflict.
**Status**: INFERRED
**Evidence**: [PR #136567](https://github.com/NousResearch/hermes-agent/pull/136567) — follow a new DM topic by time, not message-id adjacency; edit of older lobby message keeps its room; [PR #140845](https://github.com/NousResearch/hermes-agent/pull/140845) — editing a sent message no longer replies admission_conflict; [PR #139611](https://github.com/NousResearch/hermes-agent/pull/139611) — send unanchored when a reply anchor is not a message id
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Telegram routing SHALL follow a new DM topic by time rather than message-id adjacency, SHALL keep an edit of an older lobby message in its room, and an edit of an already-sent message SHALL NOT be rejected with an admission conflict.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Turn executor reuses parked threads
The gateway turn executor SHALL hand work to parked threads instead of starting a new thread on the event loop per turn.
**Status**: INFERRED
**Evidence**: [PR #142061](https://github.com/NousResearch/hermes-agent/pull/142061) — "the turn executor hands work to parked threads instead of starting one on the loop"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The gateway turn executor SHALL hand work to parked threads instead of starting a new thread on the event loop per turn.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- Streaming contract invariants 2/4 are documented with incident lineage but their enforcement anchors (`delivered_final_matches`, reconcile-by-edit call sites) were not opened at the pin — locate next pass.
- Gateway lifecycle vs Desktop app section of gateway/AGENTS.md not drafted (ownership boundary with deferred desktop-ui capability).
- `builtin_hooks/` extension point ("none shipped") — contract for always-registered gateway hooks undocumented beyond its existence; UNVERIFIED.
- Post-admission consuming gateway plugin extension (#129958, profile-scoped) is a plugin×gateway contract — boundary with plugins capability (deferred); excluded here.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05: tail lacks refs (bundle newest is #142439 2026-10-21).
- `/login` single-worker `_login_executor`, one-attempt-per-process, and `nous/welcome` eviction semantics (gateway/AGENTS.md) — no PR-ref evidence sampled; UNVERIFIED.
