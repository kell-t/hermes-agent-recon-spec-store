# Capability: gateway-messaging

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 2 (scenario grounding) applied 2026-11-08 | Pass 2b (anchor verification) applied 2026-11-08

## Summary
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
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § "The gateway has TWO message guards"; merge behavior visible in queueing code
- Anchor: `gateway/platforms/base.py:1882` (`_pending_messages` dict), `gateway/platforms/base.py:3747` (merge_pending_message_event), `gateway/run_busy.py:1049` (`_PLAIN_COMMANDS`), `gateway/run_busy.py:1055` (`_IDLE_COMMANDS`)

#### Scenario: Inbound message while an agent turn is running
- **WHEN** an agent is running and an inbound message arrives
- **THEN** it passes two sequential guards — the base adapter "queues it in `_pending_messages` when `session_key in self._active_sessions`", then the runner "intercepts `/stop`, `/new`, `/queue`, `/status`, `/approve`, `/deny` before they reach `running_agent.interrupt()`"
- Source: doc: gateway/AGENTS.md § "The gateway has TWO message guards — both must bypass approval/control commands" ("an inbound message passes two sequential guards")

#### Scenario: Control command reaches a blocked runner
- **WHEN** a command "must reach the runner while the agent is blocked (approval prompts)"
- **THEN** it bypasses BOTH guards and is dispatched inline — "never via `_process_message_background()`, which races session lifecycle"
- Source: doc: gateway/AGENTS.md § TWO message guards; [relnote v2026.4.8] "**Active-session guard bypass** for /approve, /deny, /stop, /new"

### Requirement: Table-driven slash dispatch
Slash command handlers SHALL be looked up by name through a command handler table distinguishing mid-run (plain) and idle command sets; conditional `if canonical == ...` chains SHALL NOT be used.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Shape
- Anchor: `gateway/run_busy.py:1063` (`_command_handler_table`), `gateway/run_busy.py:1073,1093`

#### Scenario: Slash command dispatch is a table lookup
- **WHEN** a slash command arrives at the busy/idle dispatcher
- **THEN** its handler is "looked up by name through `_command_handler_table`" and "a command is listed in `_IDLE_COMMANDS` or `_PLAIN_COMMANDS` (works mid-run) in `run_busy.py`"
- **AND** no `if canonical == ...` chains are used
- Source: doc: gateway/AGENTS.md § Shape

### Requirement: Prefix-stable draft streaming frames
For stream-is-the-message adapters (`draft_stream_is_message = True`), draft frames SHALL be prefix-stable (frame N a string prefix of frame N+1); per-tick mutation of drafts (fence-closing, cursor suffixes, segment resets, markdown conversion) SHALL NOT occur, because a non-prefix frame forces whole-snapshot re-append and recreates duplicate finals.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Streaming delivery contract (four invariants, each from a live duplicate-final incident); contract tests `tests/gateway/test_stream_final_contract.py`; [PR #141014](https://github.com/NousResearch/hermes-agent/pull/141014) — keep two invariants for the hosted prompt digest (test)
- Anchor: `gateway/stream_consumer_transport.py:319-321` ("Stream-is-the-message draft frames must stay prefix-stable: a closing ``` on a mid-code-block frame makes frame N not a prefix of N+1 and the connector re-appends the whole snapshot"), `:438-439` ("'...text▉' is never a prefix of '...text more▉', which forces the connector's whole-text re-append on EVERY tick (stacked copies)"), `gateway/stream_consumer.py:240` (consumer reads `adapter.draft_stream_is_message`), `gateway/relay/adapter.py:188` (set True for the relay Slack descriptor)

#### Scenario: Successive draft frames only grow
- **WHEN** a `draft_stream_is_message = True` adapter emits successive draft frames of one turn
- **THEN** "Frame N must be a string prefix of frame N+1" and the adapter never mutates drafts per tick — "no fence-closing (`ensure_closed_code_fences`), cursor suffix, segment-state resets at tool boundaries, or mrkdwn conversion"
- **AND** only "the finalize path may still transform the real final"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 1

#### Scenario: Non-prefix frame recreates duplicates
- **WHEN** a draft frame is emitted that is not a string prefix of its predecessor
- **THEN** it "forces a whole-snapshot re-append (\"stacked copies\")" — the live duplicate-final incident class the invariant exists to prevent
- **AND** each of the four streaming invariants is documented as coming "from a live duplicate-final incident"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract (invariant 1 and preamble)

### Requirement: Consumer declares the final, adapter never guesses
The streaming finish path SHALL carry the completed `final_response` in `finish(final_text)`; post-stream augmentation MUST ride this payload, and mutating `final_response` after the seal SHALL trigger corrective reconcile rather than silent divergence.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Streaming delivery contract invariant 2 (`delivered_final_matches` mismatch → corrective duplicate send)
- Anchor: `gateway/stream_consumer.py:547-549` (`def finish(self, final_text=None)` — "final_text is the AUTHORITATIVE completed final_response (incl. post-stream augmentation the accumulator never saw); the drain loop adopts it as the finalize payload"), `gateway/stream_consumer.py:335` (`delivered_final_matches` tri-state reconcile), `gateway/run_turn.py:1298` (runner consults `delivered_final_matches`; demonstrable False overrides the confirmed-delivery flag)

#### Scenario: Finish carries the completed final
- **WHEN** a native stream finishes
- **THEN** "`finish(final_text)` carries the completed `final_response` (verifier footer, completion explainer included)" and "new post-stream augmentation MUST ride this payload"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 2; test: tests/gateway/test_stream_final_contract.py::test_finish_final_text_rides_the_final_send

#### Scenario: Mutating the final after the seal re-opens the mismatch
- **WHEN** `final_response` is mutated after the seal
- **THEN** it "re-opens the `delivered_final_matches` mismatch → corrective duplicate send" (silent divergence is caught, not swallowed)
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 2; [relnote v0.22.0] "Slack native streaming stops posting answers twice."

### Requirement: Interim sends marked, seal interception at every egress door
Any adapter send that is not the turn-final SHALL set `metadata["_interim_send"] = True`; seal-interception SHALL exist at both egress doors (`send()` and `send_for_platform()`), and a new egress door SHALL add the same checks.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Streaming delivery contract invariant 3
- Anchor: `gateway/stream_consumer_fallback.py:329` and `:356` (`_md["_interim_send"] = True` marking at egress), grep hits also in `gateway/relay/adapter.py`, `gateway/run.py`

#### Scenario: Commentary is marked interim
- **WHEN** a consumer-side `adapter.send()` is not the turn-final (commentary, segment-tail flushes)
- **THEN** it must set `metadata["_interim_send"] = True` — otherwise "seal-interception seals the live stream with interim text"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 3; test: tests/gateway/test_stream_final_contract.py::test_commentary_is_marked_interim

#### Scenario: Both egress doors intercept the seal
- **WHEN** an interim send exits through either egress door
- **THEN** "Seal-interception exists at BOTH egress doors (`send()` and `send_for_platform()`)" and an interim send through either does not seal the stream
- **AND** "a new egress door needs the same two checks"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 3; test: tests/gateway/test_stream_final_contract.py::test_send_for_platform_interim_does_not_seal

### Requirement: Reconcile by edit, never by plain send
A lane delivering a final beside a sealed native stream SHALL first try `edit_message` on the consumer's message id and SHALL fall back to plain `send()` only when no editable message exists.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Streaming delivery contract invariant 4 ("live-verified" chat.update)
- Anchor: `gateway/run_notifications.py:312` (`_deliver_queued_first_response`), `:334-335` ("Reconcile-by-edit first: a stream-sealed message already carries most of the answer; a plain send here would duplicate it"), `:344` (`await adapter.edit_message(chat_id=..., message_id=_sc_msg_id, content=..., finalize=True)` — plain send only when no editable message id exists)

#### Scenario: Final beside a sealed stream edits in place
- **WHEN** "a lane delivering a final beside a sealed stream (queued follow-ups, media-accompanied finals)"
- **THEN** it "first tries `edit_message` on the consumer's `message_id`" — "a sealed native stream is a regular message — `chat.update` works (live-verified)"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 4; test: tests/gateway/test_stream_final_contract.py::test_queued_first_response_edits_in_place

#### Scenario: Plain send only with nothing editable
- **WHEN** no editable message exists for the lane's final
- **THEN** it falls back to "plain `send()` only when no editable message exists"
- Source: doc: gateway/AGENTS.md § Streaming delivery contract, invariant 4; test: tests/gateway/test_stream_final_contract.py::test_queued_first_response_falls_back_without_message

### Requirement: Background process completion starts a turn via admitted internal events
A backgrounded terminal process armed with completion notification SHALL have its watcher admitted on the gateway loop only through an `admit_internal_event` receipt (a handler returning None is not acceptance), and refused admission SHALL refund claimed batch siblings without spending an attempt.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Background process notifications
- Anchor: `gateway/run_notifications.py:1828` (`arm_process_watcher`), `gateway/run_notifications.py:1017` (`await admit_internal_event(...)`)

#### Scenario: Watcher starts a turn on process exit
- **WHEN** a `terminal(background=true, notify_on_complete=true)` process finishes
- **THEN** the watcher armed on the gateway loop (`run_notifications.py::arm_process_watcher`) "starts a new turn on completion"
- Source: doc: gateway/AGENTS.md § Background process notifications

#### Scenario: Completion reaches the agent, batched when busy
- **WHEN** a tracked background process exits (instead of the agent polling a quiet process)
- **THEN** "the agent is notified when it exits", and "jobs that finish during a busy turn come back as one turn"
- **AND** on messaging platforms completions "reach the agent instead of requeueing forever"
- Source: [relnote v0.23.0] "**Smarter background processes** — ... Instead of polling a quiet process, the agent is notified when it exits."; [relnote v0.23.0] "Background completions on Discord and Telegram reach the agent instead of requeueing forever."

#### Scenario: Refused admission refunds the batch
- **WHEN** a completion event is injected — "injection requires the `admit_internal_event` receipt (a handler returning None is not acceptance)" — and admission is refused
- **THEN** "refused admission refunds every claimed batch sibling without spending an attempt"
- Source: doc: gateway/AGENTS.md § Background process notifications

### Requirement: Platform adapters follow a documented contract over a shared base
New platform adapters SHALL implement the step-by-step adapter contract against `platforms/base.py` (access policy, exec approval, log safety, post-delivery, streaming TTS mixins), and each adapter SHALL pick a base toolset (Telegram → `"messaging"`).
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Shape; doc: gateway/platforms/ADDING_A_PLATFORM.md
- Anchor: `gateway/platforms/ADDING_A_PLATFORM.md:102` (§ Core Adapter — required methods at :106, optional default stubs at :118), `gateway/platforms/base.py` (mixin files: `base_exec_approval.py`, `access_policy_mixin.py`, `base_log_safety.py`)

#### Scenario: Adding a new platform adapter
- **WHEN** a new platform adapter is added
- **THEN** it follows the adapter contract — "New platform adapter: follow `gateway/platforms/ADDING_A_PLATFORM.md` step by step" — with the adapter "inherit[ing] from `BasePlatformAdapter`" over `platforms/base.py`
- **AND** "each adapter picks a base toolset (Telegram → `\"messaging\"`)"
- Source: doc: gateway/AGENTS.md § Shape; doc: gateway/platforms/ADDING_A_PLATFORM.md § Plugin Path ("The adapter inherits from `BasePlatformAdapter` and registers via `ctx.register_platform()`")

### Requirement: Gateway reads user YAML raw
The gateway SHALL read user YAML configuration directly (not through CLI defaults merging), so gateway-visible keys are governed by the gateway loader.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § Shape ("a key the CLI sees but the gateway doesn't means you're on the wrong loader")
- Anchor: `gateway/config_loader.py:220` (per-platform key list incl. `dm_policy`, `allow_from`, `allow_admin_from`)

#### Scenario: Gateway-visible config keys ride the gateway loader
- **WHEN** the gateway reads user configuration
- **THEN** it reads user YAML "**raw** (`run.py` + `config.py`), not through `DEFAULT_CONFIG`"
- **AND** "a key the CLI sees but the gateway doesn't means you're on the wrong loader"
- Source: doc: gateway/AGENTS.md § Shape

### Requirement: Admin gating opt-in per platform
Per-platform slash access control SHALL be active only when the operator set `allow_admin_from`, and in-flight agents SHALL not bypass admin gating.
- Status: VERIFIED
- Evidence: doc: gateway/AGENTS.md § `/login` ("shared gateways must set allow_admin_from")
- Anchor: `gateway/run_inbound.py:839`, `gateway/run_busy.py:1387`

#### Scenario: Operator opts into the admin/user tier split
- **WHEN** the operator adds `allow_admin_from` (and `user_allowed_commands`) to a platform's `extra` block for a scope
- **THEN** "a user listed in `allow_admin_from` for a scope (DM or group) can run **every** registered slash command — built-in commands AND plugin-registered ones", while "a user in `allow_from` but **not** in `allow_admin_from` can only run commands listed in `user_allowed_commands`, plus the always-allowed floor: `/help` and `/whoami`"
- Source: doc: website/docs/user-guide/messaging/telegram.md § Slash Command Access Control

#### Scenario: Gating stays off until opted in
- **WHEN** `allow_admin_from` is not set for a scope
- **THEN** "the tier split is disabled for that scope and every allowed user has full access. Existing installs keep working with no changes — opt in when you want the distinction."
- Source: doc: website/docs/user-guide/messaging/index.md § slash-command gating ("Backward compat"); doc: website/docs/user-guide/messaging/telegram.md § Slash Command Access Control

#### Scenario: A busy session does not bypass sender gating
- **WHEN** a session is mid-turn (busy path) and another user sends into the shared thread
- **THEN** the authorization check still runs — "an unauthorized user's message must be silently dropped, not queued"
- Source: test: tests/gateway/test_busy_session_auth_bypass.py::TestBusySessionAuthBypass::test_unauthorized_user_dropped_in_busy_path ("#17775: unauthorized users must be blocked in the busy-session path")

### Requirement: Multiplexed gateways serve profiles created after boot
Under multiplexing, the gateway SHALL serve a profile created after a single-profile boot in place without restart, SHALL still load the launch home's `.env` under multiplex routing, and SHALL store per-conversation offers in the routed profile.
- Status: INFERRED
- Evidence: [PR #141623](https://github.com/NousResearch/hermes-agent/pull/141623) — serve a profile created after a single-profile boot in place, without a restart; [PR #125530](https://github.com/NousResearch/hermes-agent/pull/125530) — still load the launch home's .env under multiplex routing; [PR #127818](https://github.com/NousResearch/hermes-agent/pull/127818) — first-contact note only in DMs, offer flag saved in the routed profile
- Anchor: `gateway/run_bootstrap.py:357` (control-socket verb table: `"rescan-profiles": _rescan_profiles_handler`), `gateway/control_socket.py:534` (`rescan_gateway_profiles` — creator signals the host; "callers then rely on the periodic rescan"), `gateway/host_attach.py:252-256` (rescan-then-attach), `gateway/run.py:1575-1577` (launch home's `.env` loaded unconditionally at boot) and `gateway/run.py:1580-1586` (`_reload_runtime_env_preserving_config_authority` — "Multiplex never reloads .env globally"); third clause (offer flag in the routed profile, #127818) anchor not opened

#### Scenario: Profile created after a single-profile boot is served in place
- **WHEN** a profile is created after a single-profile boot (Desktop's New Agent, `hermes profile create`) — previously "every ticket the Desktop minted for it through the host's control socket was refused"
- **THEN** "the creator's `rescan-profiles` signal (and the 30 s watcher) must start serving it from the SAME process: no restart, no drain"
- Source: test: tests/gateway/test_single_profile_host_serves_new_profile.py::test_profile_created_after_a_single_profile_boot_is_served_without_a_restart (module docstring, #141623)

#### Scenario: Launch home's .env still loads under multiplex routing
- **WHEN** multiplex routing is active and the launch home's `.env` is loaded
- **THEN** "the multiplex guard skips only FOREIGN (routed) home loads" — a skipped launch-home load had "hid the launch home's `.env` (a fallback_providers key) from the process env"
- **AND** "a routed profile's `.env` is still never copied into `os.environ`"
- Source: test: tests/gateway/test_multiplex_credential_isolation.py::test_launch_home_dotenv_still_loads_under_multiplex (#125530)

### Requirement: Multi-tenant gateway isolation
A second tenant's host gateway SHALL never be attached to, refused as, or reported as ours.
- Status: VERIFIED
- Evidence: [PR #121352](https://github.com/NousResearch/hermes-agent/pull/121352) — "a second tenant's host gateway never attaches, refuses, or reports as ours"
- Anchor: `gateway/host_attach.py:118-123` (`launched_by_other_tenant` — "two tenants (separate HERMES_HOME roots) each expose a profile named default: tenant A's multiplexer 'serving default' is a name collision for tenant B, never coverage, so it is not this tenant's host gateway (#121352)"), applied at `gateway/host_attach.py:374` (attach guard) and `gateway/host_topology.py:74`

### Requirement: Telegram topic and edit routing fidelity
Telegram routing SHALL follow a new DM topic by time rather than message-id adjacency, SHALL keep an edit of an older lobby message in its room, and an edit of an already-sent message SHALL NOT be rejected with an admission conflict.
- Status: VERIFIED
- Evidence: [PR #136567](https://github.com/NousResearch/hermes-agent/pull/136567) — follow a new DM topic by time, not message-id adjacency; edit of older lobby message keeps its room; [PR #140845](https://github.com/NousResearch/hermes-agent/pull/140845) — editing a sent message no longer replies admission_conflict; [PR #139611](https://github.com/NousResearch/hermes-agent/pull/139611) — send unanchored when a reply anchor is not a message id
- Anchor: `plugins/platforms/telegram/telegram_topic_routing.py:31` (`_NEW_TOPIC_FOLLOW_SECONDS = 5.0`) and `:79,:97` ("ends the follow; each adoption extends it" — adoption by `sent_at - last_sent_at`, i.e. by time), `plugins/platforms/telegram/adapter.py:7154` (`_edit_revision` — an edit carries its own revision, `:7151`), `plugins/platforms/telegram/adapter.py:1039-1045` (`_reply_to_message_id_for_send` — a non-message-id anchor parses to None and the send goes unanchored or on the DM topic's own anchor). The lobby-edit-keeps-its-room clause rides the same routing mixin per its pinned tests (test_telegram_new_topic_opener.py) — that exact branch not read line-by-line.

#### Scenario: Thread-less opener adopts a newly created DM topic by time
- **WHEN** Telegram for Android "sends the opener of a topic created from 'All messages' without `message_thread_id`", and only the preceding `forum_topic_created` service message names the topic
- **THEN** thread-less messages after the creation land in the new topic — followed within the routing mixin's `_NEW_TOPIC_FOLLOW_SECONDS` window (by time, not message-id adjacency)
- **AND** "an edit of a lobby message sent before the creation stays where that message lived", and the creation "is not adopted late or by others"
- Source: test: tests/gateway/test_telegram_new_topic_opener.py::test_thread_less_messages_after_creation_land_in_the_new_topic and ::test_creation_is_not_adopted_late_or_by_others (#136567)

#### Scenario: Root-DM message without a thread recovers to the active topic
- **WHEN** a message typed in the root DM arrives without a `message_thread_id`
- **THEN** "by default Hermes treats such a message as a continuation and answers it in your **most recently active topic** (lobby recovery)" — "the turn and its reply go to the last bound topic"
- **AND** with opt-in `dm_topic_auto_transfer`, "a plain message in the root DM makes Hermes create a new topic ... and post the reply inside that topic"
- Source: doc: website/docs/user-guide/messaging/telegram.md § DM topics ("lobby recovery"); [relnote v0.23.0] "New opt-in `dm_topic_auto_transfer` opens a fresh topic for root-DM messages."; test: tests/gateway/test_telegram_dm_topic_auto_transfer.py::test_default_root_dm_keeps_lobby_recovery_to_last_bound_topic

#### Scenario: Editing an already-sent message is its own admission
- **WHEN** a user edits an already-sent message (same message id, new text)
- **THEN** "native admission takes it as its own input, never as a changed replay of the original send" — no `admission_conflict` rejection
- Source: test: tests/gateway/test_native_admission_edit.py::test_edit_of_an_admitted_message_is_its_own_admission (#140845)

#### Scenario: Non-message-id reply anchor sends unanchored
- **WHEN** the reply anchor handed to `send()` is not a message id (e.g. an internal wake's producer identity)
- **THEN** "the reply goes out unanchored (or on the DM topic's own anchor) instead of failing on `int()`"
- Source: test: tests/gateway/test_telegram_reply_mode.py::TestSyntheticReplyAnchor::test_synthetic_anchor_sends_unanchored and tests/gateway/test_busy_reply_internal_anchor.py::test_busy_reply_to_an_internal_wake_is_unanchored (#139611)

### Requirement: Turn executor reuses parked threads
The gateway turn executor SHALL hand work to parked threads instead of starting a new thread on the event loop per turn.
- Status: VERIFIED
- Evidence: [PR #142061](https://github.com/NousResearch/hermes-agent/pull/142061) — "the turn executor hands work to parked threads instead of starting one on the loop"
- Anchor: `gateway/turn_executor.py:29-33` (docstring — "An item goes to a parked (idle) worker when one exists, otherwise to a new thread. ... Handing an item to a parked worker is a queue put. A worker parked for ``idle_timeout`` exits."), `:53` (`def submit`), `:35-38` (reuse hygiene — "A reused thread must look fresh to its next item")

#### Scenario: Submitting a turn hands work to a parked worker
- **WHEN** turn work is `submit`ted on the gateway event loop — where "starting a thread there waits until the new thread gets the GIL, which froze the loop on every submit while many turns ran"
- **THEN** "a parked worker takes the item with a queue put instead" — no new thread starts on the loop, and shutdown releases the parked worker
- Source: test: tests/gateway/test_turn_executor_reuse.py::test_submit_to_a_parked_worker_starts_no_thread_and_shutdown_releases_it (module docstring, #142061)

#### Scenario: A reused worker carries nothing from its last turn
- **WHEN** a parked worker is reused for a new turn
- **THEN** turn 1's thread-keyed state "is gone in turn 2" — interrupt bit, per-turn thread-locals, the thread-scoped sudo cache, context variables — and it does not log as the previous turn's session
- Source: test: tests/gateway/test_turn_executor_reuse.py::test_a_reused_worker_sees_none_of_the_previous_turns_thread_state and ::test_a_reused_worker_does_not_log_as_the_previous_turns_session

## Sub-area: Tail fold (commits after 2026-10-27, bundle TAIL APPEND G-01)

### Requirement: Turns reload the routed profile's current .env
A turn SHALL reload the serving profile's current `.env` on every execution path — messaging turns, local turns, and bypass sessions alike — so `${VAR}` references resolve against the profile's live values rather than values frozen at boot.
- Status: VERIFIED
- Evidence: [commit 8bc8980657bd] "a local turn reloads the profile's .env, as a messaging turn does"; [commit 6e7567be260b] "a bypass session's turn never reloads the profile's .env"; [commit 9bbe8e880f44] "a resume expands ${VAR} from the profile's current .env"
- Anchor: `gateway/run_turn_runner.py:1275-1279` ("Rotated .env keys reach this turn's config reads (side tasks read config.yaml), as on the messaging path ... A bypass session never reads the profile." → `if not policy.ignore_user_config: _reload_runtime_env_preserving_config_authority()`), `gateway/run.py:1580-1586` (`_reload_runtime_env_preserving_config_authority` — "Reload .env per turn for rotated keys while config.yaml stays authoritative for budgets ... Multiplex never reloads .env globally")

### Requirement: Side tasks resolve the profile's config with built-in defaults
A gateway side task SHALL read the routed profile's `config.yaml` like every other side-task reader, and a bypass session SHALL keep the built-in side-task defaults rather than overriding them.
- Status: VERIFIED
- Evidence: [commit 2afffc46ba15] "side tasks read the profile's config.yaml, like every other side-task reader"; [commit 7c00c01c9852] "bypass sessions keep the built-in side-task defaults"
- Anchor: `gateway/session_policy.py:20-21` ("Sections a ``follow_profile_config`` session re-reads from the owning profile's CURRENT config each turn"), `agent/auxiliary_task_config.py:17-20` (`_SESSION_AUXILIARY` — a bypass session's own saved `auxiliary:` section, "code defaults only", "set by its ``policy_scope`` so its side tasks never read the profile"), `agent/auxiliary_task_config.py:45-47` ("declared defaults layered under user config (user wins); built-in defaults live in DEFAULT_CONFIG")

### Requirement: Bot Mode roster carries every bot's saved description
In Bot Mode, the teammate roster SHALL list every bot's saved description, not just the main bot's, so each bot's role is visible wherever the roster is composed.
- Status: VERIFIED
- Evidence: [commit e27c38006a67] "Bot Mode shows every bot's saved description, not just the main bot's"; doc: website/docs/user-guide/bot-mode.md § Direct messages
- Anchor: `gateway/session_group_controls.py:457` (`entry['description'] = str(meta.get('description') or '').strip()` — every discovered profile's saved description rides `profiles.list`, not just the configured/main bot's; roster composition at `:74` `_roster_siblings`)

#### Scenario: Roster composes from each profile's title/description
- **WHEN** a Bot Chat's system prompt is composed
- **THEN** "the teammate roster — names **and roles** from each profile's title/description — is part of every Bot Chat's system prompt, so Bots know who does what before choosing a recipient"
- Source: doc: website/docs/user-guide/bot-mode.md § Direct messages

## Known gaps / open questions
- Streaming contract invariants 2/4: RESOLVED at pass 2b — enforcement anchors opened and set (`gateway/stream_consumer.py:335/:547`, `gateway/run_turn.py:1298`, `gateway/run_notifications.py:334-344`); requirement statuses upgraded to VERIFIED.
- DOC-vs-CODE (pass 2b, flagged not fixed): tail-folded "Turns reload ... .env" wording says "bypass sessions alike", but the pinned code deliberately NEVER reloads the profile `.env` for a bypass session (`gateway/run_turn_runner.py:1278-1279` — `if not policy.ignore_user_config:`, comment "A bypass session never reads the profile"), consistent with cited commit 6e7567be260b. The requirement text overstates the bypass clause.
- D-01 (ledger drift register): CLOSED at pass 2b — the 85% gateway-hygiene constant claimed by agent/AGENTS.md ("gateway session hygiene (85% threshold)") exists at the pin: `gateway/run_turn_hygiene.py:102` (`threshold_pct=0.85`; :97 "deliberately HIGHER than the agent's compressor (0.50)"). Pass 1 searched `gateway/session*.py` only; the constant lives in `run_turn_hygiene.py`. (No requirement in this file carries the hygiene claim — recorded for the agent-turn-loop owner / ledger.)
- Gateway lifecycle vs Desktop app section of gateway/AGENTS.md not drafted (ownership boundary with deferred desktop-ui capability).
- `builtin_hooks/` extension point ("none shipped") — contract for always-registered gateway hooks undocumented beyond its existence; UNVERIFIED.
- Post-admission consuming gateway plugin extension (#129958, profile-scoped) is a plugin×gateway contract — boundary with plugins capability (deferred); excluded here.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05: tail lacks refs (bundle newest is #142439 2026-10-21).
- `/login` single-worker `_login_executor`, one-attempt-per-process, and `nous/welcome` eviction semantics (gateway/AGENTS.md) — no PR-ref evidence sampled; UNVERIFIED.

## Scenario-ification notes
- REQ "Multi-tenant gateway isolation": no doc-grounded trigger; kept as invariant. (Only evidence is PR #121352's phrasing — echoed verbatim in the requirement itself; no Tier A release note, no Tier B doc section, and no test asserts "never attaches/refuses/reports as ours". Anchor located at pass 2b — `gateway/host_attach.py:118` docstring — but that is implementation comment, not a Tier A/B trigger+outcome doc, so no scenario added.)
- REQ "Multiplexed gateways serve profiles created after boot": the third clause (per-conversation offer flag saved in the routed profile, #127818) has no Tier A/B/C grounding found — scenario-ified for the first two clauses only.
- REQ "Admin gating opt-in per platform": "in-flight agents SHALL not bypass admin gating" is scenario-ified from the busy-path authorization test (#17775), which covers inbound sender gating while a session runs — it does not test an in-flight agent circumventing `allow_admin_from`. The requirement's wording may overstate what the evidence shows.
- Tail folds: 3 requirements added (max 3 allowed). Deferred tail candidates: stale approval-card binding cluster (5ab58da1f63a, 79f28901db7f, 8ebc4ef6ccab, 7ab170ea6d36 — strong Tier B/C grounding, better folded with the approvals capability); bot-to-bot loop-cap cluster (4e93f80e4720, 8180676731e4, 160339e0dd5c — Bot Mode engine, mostly undocumented); Slack thread-context allowlist tagging (cad0aaaf0d77); all desktop/tui/webapp/docker/mcp/model-routing lines per scope notes.
