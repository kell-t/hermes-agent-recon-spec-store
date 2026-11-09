# Capability: cron-background

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27. | Pass 3 (scenario-ification) applied 2026-11-08

## Summary
Scheduled background jobs: `cron/jobs.py` (job store) and `cron/scheduler.py` (tick loop + `scheduler_*.py` siblings), driven by the `cronjob` tool, the `hermes cron` CLI, and `/cron`. The scheduler's hardening invariants — at-most-once occurrence accounting, inactivity watchdog, headless refusal, per-profile scope binding — each guard a real incident. Kanban (the multi-agent work queue) shares the area guide.

## Primary code locations
- `cron/jobs.py`, `cron/job_definition.py`, `cron/jobs_time.py` — store, definition fields, time math
- `cron/scheduler.py` + `cron/scheduler_*.py` — tick loop, multiplex provider, gateway gate
- `cron/occurrences.py`, `cron/executions.py`, `cron/missed_runs.py` — occurrence accounting
- `cron/AGENTS.md` — the invariants law; long-form `website/docs/developer-guide/cron-internals.md`

## Requirements

### Requirement: Four schedule notations and a defined job schema
Jobs SHALL accept duration (`"30m"`), every-phrase (`"every monday 9am"`), 5-field cron (`"0 9 * * *"`), and ISO one-shot schedules; job definition fields (`skills`, `model`/`provider` overrides, `script`, `context_from`, `workdir`, `timezone`, `grace_minutes`) SHALL stay in `JOB_DEFINITION_FIELDS` or profile distribution strips them.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Cron
- Anchor: `cron/job_definition.py:13` (`JOB_DEFINITION_FIELDS = frozenset({`)

#### Scenario: Four notations define a schedule
- **WHEN** a job's schedule is written as a duration (`"30m"`, `"2h"`, `"1d"`), an "every" phrase (`"every 2h"`, `"every monday 9am"`), a 5-field cron expression, or an ISO one-shot instant
- **THEN** the scheduler SHALL accept it as that notation's schedule
- Source: doc: cron/AGENTS.md § Cron "Schedules: duration"
- Source: doc: cron/AGENTS.md § Cron "5-field cron (`"0 9 * * *"`), ISO one-shot"

#### Scenario: Definition fields survive profile distribution
- **WHEN** a profile distribution ships job definitions carrying `timezone`/`grace_minutes`
- **THEN** those fields SHALL stay in `JOB_DEFINITION_FIELDS` — otherwise the distribution strips them
- Source: doc: cron/AGENTS.md § Hardening invariants (timezone bullet) "must stay in `job_definition.JOB_DEFINITION_FIELDS` or a profile"
- Source: doc: cron/AGENTS.md § Hardening invariants (timezone bullet) "distribution strips them"

### Requirement: Pre-run scripts are files, never command lines
A job's `script` SHALL always be a file under `HERMES_HOME/scripts/` — never an inline command line (`script='echo hi'` is refused at creation); its stdout is injected into the prompt, and `no_agent=True` makes the script the whole job.
- Status: INFERRED
- Evidence: doc: cron/AGENTS.md § Cron (per-job fields)
- Anchor: not located (creation-time refusal site not opened)

#### Scenario: An inline command line is refused at creation
- **WHEN** a job is created with `script=\"echo hi\"` (a command line instead of a file)
- **THEN** creation SHALL refuse it — the script is always a file under `HERMES_HOME/scripts/`, never a command line
- Source: doc: cron/AGENTS.md § Cron "never a command line — `script='echo hi'` is refused at creation"

#### Scenario: no_agent makes the script the whole job
- **WHEN** a job sets `no_agent=True`
- **THEN** the script is the whole job — its stdout is delivered verbatim with zero LLM involvement (and for an agent job, the pre-run script's stdout is injected into the prompt)
- Source: doc: cron/AGENTS.md § Cron "makes the script the whole job"
- Source: doc: website/docs/user-guide/features/cron.md § What cron can do now "a script on a schedule, its stdout delivered verbatim, zero LLM involvement"

### Requirement: Idle-based inactivity watchdog
Cron agent sessions SHALL be hard-interrupted on inactivity (default 600s idle, `HERMES_CRON_TIMEOUT` override, `0` unlimited): the watchdog measures idle time, not wall-clock, so a long-but-active job is never cut and a stalled one cannot monopolize the scheduler; attached scripts are bounded separately by a 3600s script timeout.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants
- Anchor: `cron/executions.py:195` (reads `_cron_inactivity_seconds()`), `cron/executions.py:198`

#### Scenario: A stalled session is hard-interrupted
- **WHEN** a cron agent session sits idle past the watchdog limit (default 600s; `HERMES_CRON_TIMEOUT` overrides, `0` = unlimited)
- **THEN** the session SHALL be hard-interrupted so it cannot monopolise the scheduler
- Source: doc: cron/AGENTS.md § Hardening invariants "session is hard-interrupted so it cannot monopolise the scheduler"
- Source: doc: cron/AGENTS.md § Hardening invariants "`HERMES_CRON_TIMEOUT` overrides, `0` = unlimited"

#### Scenario: A long-but-active job is never cut
- **WHEN** a job runs a long time while staying active
- **THEN** it SHALL NOT be timed out — the watchdog measures idle time, not wall-clock, and active tasks run indefinitely
- **AND** attached scripts are bounded separately by the script timeout (3600s)
- Source: doc: cron/AGENTS.md § Hardening invariants "while a long-but-active job"
- Source: doc: cron/AGENTS.md § Hardening invariants "(`_DEFAULT_SCRIPT_TIMEOUT`, 3600s)"
- Source: [relnote 2026.4.8] "Inactivity-based cron timeout** — replaces wall-clock; active tasks run indefinitely"

### Requirement: At-most-once occurrence accounting
`tick()` SHALL advance `next_run_at` before dispatch and stamp `pending_slot` in the same save; a scan finding the stamp with a dead owner SHALL restore the instant exactly once; the executions ledger's `scheduled_instant` SHALL block a second fire, and skipped past-grace misses SHALL be logged — a slot is never dropped silently.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants (cites #107485); module `cron/occurrences.py` exists for the restore-once rule
- Anchor: `cron/occurrences.py` (module present; restore-once logic per doc), `cron/scheduler.py:187` (pre-lock boot fingerprint raise)

#### Scenario: A mid-run crash never double-fires the occurrence
- **WHEN** `tick()` dispatches an occurrence
- **THEN** it advances `next_run_at` BEFORE dispatch and stamps `pending_slot` in the same save (at-most-once across a mid-run crash)
- **AND** a scan that finds the stamp with a dead owner restores the instant ONCE
- Source: doc: cron/AGENTS.md § Hardening invariants "(at-most-once across a mid-run crash) and stamps `pending_slot` in the same save"
- Source: doc: cron/AGENTS.md § Hardening invariants "finds the stamp with a dead owner restores the instant ONCE"

#### Scenario: A slot missed across a restart fires once, and is never dropped silently
- **WHEN** a slot is missed during a restart gap
- **THEN** it SHALL fire once (catch-up), or, when `cron.catch_up_missed: false`, the past-grace miss is skipped with a logged reason
- **AND** a slot is never dropped silently
- Source: [relnote 0.22.0] "a slot missed during a restart fires once"
- Source: doc: cron/AGENTS.md § Hardening invariants "Never drop a slot silently"
- Source: doc: website/docs/user-guide/features/cron.md § Verbs "A recurring job whose slot came due while it was paused keeps that slot due, so the next tick fires one catch-up run"

### Requirement: Bounded catch-up window
Missed-run catch-up SHALL use half the period clamped to 120s–2h, overridable per job by `grace_minutes` (`0` meaning never catch up — a real value, never conflated with unset), with 120s grace for missed one-shots.
- Status: INFERRED
- Evidence: doc: cron/AGENTS.md § Hardening invariants
- Anchor: not located (`cron/jobs_time.py` per doc "knobs live in cron/jobs_time.py")

#### Scenario: Late delivery only inside the computed window
- **WHEN** a cron occurrence is missed and its catch-up window has not lapsed
- **THEN** it is run late only inside a catch-up window of half the job's period, clamped to 2 minutes–2 hours (120s grace for missed one-shots)
- Source: doc: website/docs/user-guide/features/cron.md § Catch-up window "A missed cron occurrence is run late only inside a catch-up window: half the job's period, clamped to 2 minutes–2 hours"
- Source: doc: cron/AGENTS.md § Hardening invariants "120s grace for missed"

#### Scenario: grace_minutes 0 never catches up
- **WHEN** a job sets `--grace-minutes 0`
- **THEN** a missed occurrence is skipped — `0` means never catch up (a real value, never conflated with unset); `--grace-minutes ""` restores the computed window
- **AND** it only applies to cron expressions — `once` and `interval` schedules have no missed wall clock to catch up on
- Source: doc: website/docs/user-guide/features/cron.md § Catch-up window "means never catch up"
- Source: doc: website/docs/user-guide/features/cron.md § Catch-up window "schedules have no missed wall clock to catch up on"

### Requirement: Pinned timezone owns the whole run-time path
A job's pinned `timezone` SHALL govern every `next_run_at` write site (not just computation); `compute_next_run` resolves job pin before profile zone, `_evaluate_due_job` normalizes stored instants into the job's zone, and timezone-shift repair SHALL be skipped for pinned jobs.
- Status: INFERRED
- Evidence: doc: cron/AGENTS.md § Hardening invariants ("one missed site is a burst re-run or a skipped slot")
- Anchor: not located (`cron/jobs_time.py`)

#### Scenario: The pinned zone governs every write, and shift-repair stands down
- **WHEN** a job carries a pinned `timezone`
- **THEN** `compute_next_run` resolves job pin before the profile zone and every `next_run_at` write site must pass the pin — one missed site is a burst re-run or a skipped slot
- **AND** `_evaluate_due_job` normalizes the stored instant into the job's zone and skips `_repair_timezone_shifted_cron` for pinned jobs
- Source: doc: cron/AGENTS.md § Hardening invariants "*job pin → profile zone*, and every `next_run_at` write site must pass the pin"
- Source: doc: cron/AGENTS.md § Hardening invariants "one missed site is a burst"
- Source: doc: cron/AGENTS.md § Hardening invariants "**skips `_repair_timezone_shifted_cron`** for pinned jobs"

### Requirement: Per-home tick lock
A file lock at `<home>/cron/.tick.lock` SHALL keep overlapping processes to one tick at a time for that profile's store, addressed profile-aware (never a `~/.hermes/...` literal).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants
- Anchor: `cron/scheduler.py:3` (module docstring states the lock)

#### Scenario: Overlapping processes tick once per store
- **WHEN** two processes tick at the same time for one profile's store
- **THEN** the per-home file lock at `<home>/cron/.tick.lock` lets only one tick proceed
- **AND** the lock path is resolved profile-aware, never a `~/.hermes/...` literal
- Source: doc: cron/AGENTS.md § Hardening invariants "Per-home tick lock `<home>/cron/.tick.lock` prevents duplicate ticks across processes for"

### Requirement: Headless ticks refuse rather than spawn a gateway
`hermes cron tick` (headless mode) SHALL skip agent jobs when no gateway owns the home — stamping `last_fire_error`, warning once per tick, leaving the due instant untouched — instead of spawning an unmanaged gateway daemon; the in-process ticker and `hermes cron run` are not headless.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants ("Same policy as approvals")
- Anchor: `cron/scheduler_gateway_gate.py` (module dedicated to the gate; opened as gate owner per doc)

#### Scenario: A headless tick refuses instead of spawning a gateway
- **WHEN** `hermes cron tick` runs (system crontab / external scheduler) and discovery says no gateway owns the home
- **THEN** agent jobs SHALL be skipped with a logged reason (`last_fire_error` stamped, one warning per tick) instead of spawning an unmanaged daemon
- **AND** the due instant is untouched — the schedule is not advanced or penalised, and the jobs fire on the next tick after `hermes gateway start`
- Source: doc: cron/AGENTS.md § Hardening invariants "says no gateway owns the home"
- Source: doc: website/docs/user-guide/features/cron.md § Verbs "With no gateway up, agent jobs are skipped with a logged reason"
- Source: doc: website/docs/user-guide/features/cron.md § Verbs "schedule is not advanced or penalised"

#### Scenario: Script-only jobs still run headless
- **WHEN** a bare `hermes cron tick` runs with no gateway up and the job is `no_agent`
- **THEN** the script job still runs from the bare tick (only agent jobs are refused)
- Source: doc: website/docs/user-guide/features/cron.md § Verbs "`no_agent` script jobs still run from a bare tick."

### Requirement: One ticker binds each served profile's scope
The multiplex ticker SHALL be one ticker iterating served profiles sequentially under a per-home scope guard (home + secrets + terminal scope), never N threads; everything a tick touches (store open, lock path, failure counters, job env, session-end flush) lives inside the guard, and supervision re-enumerates homes when profile dirs appear or are tombstoned.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants (documents the historical bug: a store opened before scope entry wrote a secondary profile's run records into the launch profile's jobs.json)
- Anchor: `cron/scheduler_provider.py:539` (`_start_multiplex`)

#### Scenario: One ticker, sequential, fully inside the scope guard
- **WHEN** the multiplex provider starts ticking served profiles
- **THEN** it runs ONE ticker iterating `profiles_to_serve()` sequentially under `_profile_cron_scope(home)` (home + secret scope + terminal scope) — never N threads
- **AND** everything a tick touches lives inside that guard (store open, lock path, failure counters, job env, session-end flush): the guarded incident was a store opened before the scope was entered writing a secondary profile's run records into the launch profile's `jobs.json`
- Source: doc: cron/AGENTS.md § Hardening invariants "sequentially under `_profile_cron_scope(home)` (home + secret scope + terminal scope)"
- Source: doc: cron/AGENTS.md § Hardening invariants "a store opened before the scope was entered"
- Source: [relnote 0.22.0] "A multiplexed gateway runs each profile's jobs with that profile's env and secrets"

#### Scenario: Supervision follows the served-home set
- **WHEN** a profile directory appears or is tombstoned
- **THEN** ticker supervision re-enumerates the served homes (per served home, not per process)
- Source: doc: cron/AGENTS.md § Hardening invariants "re-enumerate when a profile dir appears or is tombstoned"

### Requirement: In-flight cron state is (home, job) keyed
Because one process ticks N profile stores, in-flight scheduler state SHALL be keyed by `(home key, job id)` (two profiles may legitimately carry a `daily-brief`), and the parallel job pool SHALL be keyed by home (`cron.max_parallel_jobs` per profile).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants ("Per-profile process assumptions are the bug class")
- Anchor: `cron/scheduler.py:581` (`def _inflight_key(job_id, home=None) -> tuple`)

#### Scenario: Same job id in two profiles stays separate
- **WHEN** two profiles legitimately carry a job with the same id (e.g. `daily-brief`)
- **THEN** in-flight scheduler state SHALL be keyed `(home key, job id)`
- **AND** the parallel job pool is keyed by home (`cron.max_parallel_jobs` is per profile)
- Source: doc: cron/AGENTS.md § Hardening invariants "keyed by `_inflight_key(job_id)` = `(home key, job id)`"
- Source: doc: cron/AGENTS.md § Hardening invariants "profiles legitimately carry a `daily-brief`"

### Requirement: Cron ticking is not gated on the multiplex flag
One host gateway SHALL tick every profile's store regardless of `gateway.multiplex_profiles` (that flag gates adapters only).
- Status: INFERRED
- Evidence: doc: cron/AGENTS.md § Hardening invariants (names `run.py::_cron_tick_profile_homes`)
- Anchor: not located (gateway/run.py sibling not opened)

#### Scenario: Ticking ignores the multiplex flag
- **WHEN** `gateway.multiplex_profiles` is off
- **THEN** the one host gateway SHALL still tick every profile's store — that flag gates adapters only
- Source: doc: cron/AGENTS.md § Hardening invariants "That flag gates ADAPTERS"
- Source: doc: cron/AGENTS.md § Hardening invariants "host gateway process ticks EVERY profile's store either way"

### Requirement: Pinned job models never fall back globally
A job with a pinned model/provider SHALL never fall back to the global fallback chain on failure.
- Status: INFERRED
- Evidence: [PR #120312](https://github.com/NousResearch/hermes-agent/pull/120312) — "a pinned job never falls back to the global fallback chain"
- Anchor: `cron/jobs_model_pin.py` (module named for the rule; lines not opened)

#### Scenario: A pinned job never borrows the global fallback chain
- **WHEN** a job carries its own `provider`, `model` or `base_url` and its run fails
- **THEN** `_job_fallback_chain()` returns no chain for it, so a pinned job never lands on a global chain entry
- **AND** the same answer feeds the credential-resolution walk, the pre-dispatch key check, and the mid-run ladder
- Source: doc: website/docs/developer-guide/cron-internals.md "**Unpinned jobs only:** `_job_fallback_chain()` returns no chain for a job carrying its own `provider`, `model` or `base_url`"
- Source: doc: website/docs/developer-guide/cron-internals.md "so a pinned job never lands on a global chain entry"

### Requirement: Lost manual runs are recorded honestly
A manual `hermes cron run` whose worker is lost SHALL be recorded as a lost run, not reported as a restart that never happened.
- Status: INFERRED
- Evidence: [PR #128509](https://github.com/NousResearch/hermes-agent/pull/128509) — "record a lost manual run instead of reporting a restart that never happened"
- Anchor: not located

### Requirement: Kanban completion requires evidence
Completing a Kanban task SHALL refuse empty result evidence (`complete_task` without evidence is rejected).
- Status: INFERRED
- Evidence: [PR #117483](https://github.com/NousResearch/hermes-agent/pull/117483) — "refuse empty complete_task evidence"; [PR #91264](https://github.com/NousResearch/hermes-agent/pull/91264) — judge transport failure / worker failed stops (tests)
- Anchor: not located (kanban code outside `cron/` proper — `plugins/kanban/` boundary, deferred plugins scope)

## Known gaps / open questions
- Wall-clock stale-claim guard for live-but-deadlocked workers (#115692) and dispatch-hold/quota-hold mechanics (`cron/dispatch_hold.py`, `extra_fire.settle`) referenced by doc/bundle, not drafted — pass 2.
- Chronos managed-cron contract (`website/docs/developer-guide/chronos-managed-cron-contract.md`, #97494 403 failover to built-in ticker) not drafted — external service contract, needs a dedicated requirement pass.
- Kanban dispatcher invariants (cron/AGENTS.md second half) not read/drafted; kanban sits at the deferred plugins boundary — ownership decision needed.
- `hermes cron` CLI surface verbs drafted only as part of scheduling entry points.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.

## Requirements (tail fold, commits after 2026-10-27)

### Requirement: Scheduled jobs get their actual run time in the prompt
A fired job's prompt SHALL carry the actual fire time; scheduling cadence SHALL stay out of job prompts (the cadence clause is scoped and also applied on update).
- Status: INFERRED
- Evidence: [commit 3166c4a4b149] — give scheduled jobs their actual run time in the prompt; [commit 8a900e67159d] — keep scheduling cadence out of cron job prompts; [commit ce1370430ef8] — scope prompt clause to cadence and cover update
- Anchor: not located (prompt-assembly seam for cron jobs)

#### Scenario: The prompt knows when the job fired
- **WHEN** a scheduled job fires and its prompt is assembled
- **THEN** the prompt carries the fire time
- Source: [relnote 0.23.0] "A manual run no longer consumes a one-shot, and prompts carry the fire time."

### Requirement: Gateway drain holds dispatch; a one-shot due during the hold fires once afterwards
While a gateway drain holds cron dispatch, a one-shot becoming due SHALL NOT be consumed or lost: it fires once when the next gateway ticks; the drain-hold grace extension is capped, never re-fires a claimed one-shot, and a failed write mid-drain does not restart the hold window.
- Status: INFERRED
- Evidence: [commit c7b72e1fe4a7] — a one-shot due while a gateway drain holds dispatch fires once afterwards; [commit b7798657a008] — the drain-hold grace extension is capped and never re-fires a claimed one-shot; [commit b425edd28617] — a failed write mid-drain no longer restarts the hold window
- Anchor: not located (dispatch-hold machinery adjacent to `cron/dispatch_hold.py`, already in Known gaps)

#### Scenario: Due during the drain, fired by the next gateway
- **WHEN** a one-shot becomes due while a gateway drain holds dispatch
- **THEN** it fires once the next gateway ticks (it is neither dropped nor double-fired)
- Source: test: tests/cron/test_oneshot_due_during_drain_hold.py::test_oneshot_due_during_a_drain_fires_once_the_next_gateway_ticks

### Requirement: Per-job catch_up composes with grace_minutes and the global setting
Each job SHALL pick its own missed-run policy: the job's `catch_up` beats the global setting, an explicit `grace_minutes` still skips past it unless the job opts into `catch_up`, and a `catch_up: off` skip books exactly one missed row with the count.
- Status: INFERRED
- Evidence: [commit d4865574e474] — review round 3: Stop settles by its own run, missed counts use the pinned zone, distributions keep catch_up; [commit e9f01737aae3] — how a job's catch_up composes with grace_minutes; [commit bb8c685c8981] — test: an explicit grace_minutes still skips past it unless the job opts into catch_up; [commit 3f435147912f] — a Run-now stopped by cancel reports cancelled, not failed
- Anchor: not located (catch-up policy resolution in jobs_time/store layer)

#### Scenario: Job policy beats the global setting
- **WHEN** a job sets `catch_up` while a global missed-run setting exists
- **THEN** the job's setting wins
- **AND** with catch-up off the skip books one missed row with the count
- Source: test: tests/cron/test_cron_stop_and_missed_policy.py::test_job_catch_up_beats_the_global_setting
- Source: test: tests/cron/test_cron_stop_and_missed_policy.py::test_catch_up_off_skips_and_books_one_missed_row_with_the_count

#### Scenario: Explicit grace still applies once opted into catch_up
- **WHEN** a job has an explicit `grace_minutes` and catches up
- **THEN** occurrences past the explicit grace are still skipped unless the job opts into `catch_up`
- Source: test: tests/cron/test_cron_stop_and_missed_policy.py::test_explicit_grace_skips_past_it_unless_the_job_opts_into_catch_up
- Source: [relnote 0.23.0] "Each job picks its own missed-run policy (`--catch-up on|off`)."

## Scenario-ification notes
- REQ "Lost manual runs are recorded honestly": no doc-grounded trigger; kept as invariant. (#128509 commit-title-only; relnote 2026.9.11's killed-manual-run bullet (#106733) is about not blocking the next run, a different contract.)
- REQ "Kanban completion requires evidence": no doc-grounded trigger for the REFUSAL; kept as invariant. (#117483 commit-title-only; no test named for refusing empty `complete_task` evidence found. The #91264 side of its Evidence IS test-grounded — tests/hermes_cli/test_kanban_goal_mode.py::test_loop_stops_on_judge_transport_failure and ::test_loop_stops_on_worker_failed_flag — but those pin goal-loop stops, not the complete_task evidence gate, so they do not satisfy this requirement's WHEN/THEN.)
- Doc-vs-code surprise (flagged, not fixed): website/docs/user-guide/features/kanban.md § Recommended handoff evidence says the evidence keys are "a convention, not a schema requirement" (line: These keys are a convention, not a schema requirement), while REQ "Kanban completion requires evidence" (from #117483) asserts a hard refusal of empty evidence; kanban.md's `complete_task` boundary prose covers GitHub required-check evidence, not the empty-result refusal.
- Kanban tail commits noted for a dedicated kanban pass (fold cap reached here): d4283a9c9cdf + 25e7f5fc21d8 (dependency block hook post-commit), dbde5a991ae0 / eace3e056e8b (worker vs restart-wait), 3776709d521b (isolate and reap owned Kanban systemd scopes, relnote 0.22.1).
- Tail items rejected (out of capability ownership): plugin-catalog/catalog entries and bumps (3a9c3d46d522, bb719c349235, fb5a2b140371, 083772b37465, 8aaa8af075f8, fef61fbc7fd5, f6e0ffe53529, 40bbdd2e3274, 0f29a7d98917, 3093bc3117d4, d8232c0eb889, ad98ff37f0e5), desktop (9dd1ea34f23e retry schedule, e03222879c39 pin Kanban boards as tabs, e86597e2605e Scheduled-posts pane), rooms/group-chat delivery tail cluster 2e1c0291b881 / fbe94827167a / f7065f26d76f / 32f95b873f52 (gateway-messaging & rooms boundary — noted for that capability), sessions-state (edf1495a314f warm reopen totals), CI (e534ed0b08cc, df128c13bb9d), webhook kanban_task_id guard deea569ef62d (webhooks boundary).
- Tail items folded: 3166c4a4b149 + 8a900e67159d + ce1370430ef8 → "run time in the prompt"; c7b72e1fe4a7 + b7798657a008 + b425edd28617 → "drain hold"; d4865574e474 + e9f01737aae3 + bb8c685c8981 + 3f435147912f → "catch_up composition". f7a018a77cbd DST-adjacent timezone test fix is test-infra, not folded.
