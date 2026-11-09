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
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Cron (per-job fields) — code: cron/jobs_invariants.py:40 refuses command-line scripts at both create_job and update_job doors
- Anchor: `cron/jobs_invariants.py:40` (`_script_is_command_line`) — `if script and _script_is_command_line(script):` raises `SCRIPT_IS_COMMAND_LINE_ERROR`, the creation-time refusal; `cron/jobs_invariants.py:70` (`def _script_is_command_line`) — a script with whitespace that resolves to no file is a command line (`echo hi`), not a path; `cron/jobs.py:1875` (`_validate_job_mode_invariants`) — create_job runs the shared invariant door (also at jobs.py:2134 for update_job, so no bypass via the update door)

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
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants — code: `_compute_grace_seconds` (cron/jobs.py:947) computes half-period clamped [120s, 7200s]; per-job override floors at 120s
- Anchor: `cron/jobs.py:960` (`return max(_MIN_GRACE_SECONDS, min(int(period_seconds) // 2, _MAX_GRACE_SECONDS))`) — half the period, clamped to the window; `cron/jobs.py:943` (`_MIN_GRACE_SECONDS = 120`) with `cron/jobs.py:944` (`_MAX_GRACE_SECONDS = 7200`) — the 120s–2h clamp bounds; `cron/jobs_time.py:83` (`normalize_grace_minutes`) — "``0`` is a real value (never catch up), so it must never be collapsed into absent"; one-shot 120s grace at `cron/jobs.py:120` (`ONESHOT_GRACE_SECONDS = 120`)

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
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants ("one missed site is a burst re-run or a skipped slot") — code: pin-before-profile resolution at cron/jobs.py:1239 and repair skip at cron/jobs.py:3217 (`zone is None` guard)
- Anchor: `cron/jobs.py:1197` (`must pass`) — compute_next_run docstring: "Every caller that advances a job's ``next_run_at`` must pass it, or a pinned job is computed in the wrong zone and jumps a slot"; `cron/jobs.py:1239` (`zone = job_zone or get_timezone() or base_time.tzinfo`) — job pin resolves before the profile zone (job_zone from `jobs_time.zone_for_job` at jobs.py:1203); `cron/jobs.py:3217` (`if kind == "cron" and not manual_run and zone is None and _repair_timezone_shifted_cron(d)`) — repair skipped for pinned jobs (zone not None); `cron/jobs.py:3198` (`zone = jobs_time.zone_for_job(job)`) normalizes the stored instant into the job's zone in `_evaluate_due_job`

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
- Anchor: `cron/scheduler_gateway_gate.py:1` (module docstring — headless tick refuses, never spawns), `cron/scheduler_gateway_gate.py:29` (`_gateway_unavailable`)

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
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Hardening invariants (names `run.py::_cron_tick_profile_homes`) — code: gateway/run_bootstrap.py starts the ticker over `_cron_tick_profile_homes(runner.config)` with no multiplex_profiles gate
- Anchor: `gateway/run_bootstrap.py:398` (`gateway.multiplex_profiles`) — comment at the tick-set site: "its cron ticker owns EVERY profile's store — `gateway.multiplex_profiles` gates adapters, not cron"; the homes call at run_bootstrap.py:402 is ungated; `gateway/run.py:1654` (`def _cron_tick_profile_homes`) — docstring at run.py:1658: "One host process ticks all of them regardless of ``gateway.multiplex_profiles``. Adapter startup already skips ``active``."

#### Scenario: Ticking ignores the multiplex flag
- **WHEN** `gateway.multiplex_profiles` is off
- **THEN** the one host gateway SHALL still tick every profile's store — that flag gates adapters only
- Source: doc: cron/AGENTS.md § Hardening invariants "That flag gates ADAPTERS"
- Source: doc: cron/AGENTS.md § Hardening invariants "host gateway process ticks EVERY profile's store either way"

### Requirement: Pinned job models never fall back globally
A job with a pinned model/provider SHALL never fall back to the global fallback chain on failure.
- Status: VERIFIED
- Evidence: [PR #120312](https://github.com/NousResearch/hermes-agent/pull/120312) — "a pinned job never falls back to the global fallback chain" — code: `_job_fallback_chain` (cron/scheduler.py:98) feeds the same pinned verdict to resolution, preflight (scheduler_preflight.py:98) and mid-run (scheduler.py:1771)
- Anchor: `cron/scheduler.py:98` (`def _job_fallback_chain`) — docstring: "A pinned job never borrows the global ``fallback_providers`` chain ... at credential resolution AND mid-run"; `cron/scheduler.py:106` (`return scoped_fallback_chain(`) — passes `pinned=_job_route_pinned(job)` so a pinned job gets no chain; `cron/scheduler.py:92` (`def _job_route_pinned`) — any own provider/model/base_url string is an explicit operator pin

#### Scenario: A pinned job never borrows the global fallback chain
- **WHEN** a job carries its own `provider`, `model` or `base_url` and its run fails
- **THEN** `_job_fallback_chain()` returns no chain for it, so a pinned job never lands on a global chain entry
- **AND** the same answer feeds the credential-resolution walk, the pre-dispatch key check, and the mid-run ladder
- Source: doc: website/docs/developer-guide/cron-internals.md "**Unpinned jobs only:** `_job_fallback_chain()` returns no chain for a job carrying its own `provider`, `model` or `base_url`"
- Source: doc: website/docs/developer-guide/cron-internals.md "so a pinned job never lands on a global chain entry"

### Requirement: Lost manual runs are recorded honestly
A manual `hermes cron run` whose worker is lost SHALL be recorded as a lost run, not reported as a restart that never happened.
- Status: VERIFIED
- Evidence: [PR #128509](https://github.com/NousResearch/hermes-agent/pull/128509) — "record a lost manual run instead of reporting a restart that never happened" — code: waiter path calls `terminalize_dead_owner` with `external_worker_exited_reason` cause (cron/scheduler.py:3551-3554, #128509)
- Anchor: `cron/executions.py:565` (`def terminalize_dead_owner`) — docstring: without it "a manual run whose worker dies is filed as 'Scheduler restarted ...' (a restart that never happened)"; records the attempt as `unknown` with an observed cause; `cron/scheduler_worker_failure.py:48` (`def external_worker_exited_reason`) — truthful cause: "Restart-safe cron worker exited with status {returncode} after adopting this execution" (#128509); `cron/scheduler.py:3554` (`if not terminalize_dead_owner(execution_id, reason=reason):`) — the waiter records the lost run instead of reporting a restart

#### Scenario: A dead worker's manual run files an observed cause
- **WHEN** a manual run's restart-safe worker dies and the waiter terminalizes the attempt
- **THEN** it is filed "as `unknown` with a cause this process actually observed" — never "_OWNER_GONE_REASON", "which asserts a scheduler restart"
- Source: doc: cron/executions.py:567 (`terminalize_dead_owner` docstring) — "Record one attempt as ``unknown`` with a cause this process actually observed"
### Requirement: Kanban completion requires evidence
Completing a Kanban task SHALL refuse empty result evidence (`complete_task` without evidence is rejected).
- Status: VERIFIED
- Evidence: [PR #117483](https://github.com/NousResearch/hermes-agent/pull/117483) — "refuse empty complete_task evidence"; [PR #91264](https://github.com/NousResearch/hermes-agent/pull/91264) — judge transport failure / worker failed stops (tests) — code: gate lives in hermes_cli/kanban_db.py (`_gate_empty_completion`, `EmptyCompletionError`), not plugins/kanban; test tests/hermes_cli/test_kanban_empty_completion.py pins it (#117483)
- Anchor: `hermes_cli/kanban_db.py:2808` (`raise EmptyCompletionError(task_id)`) — after an auditable `completion_blocked_empty_result` event, empty/whitespace-only evidence is refused; `hermes_cli/kanban_db.py:2777` (`def _gate_empty_completion`) — "Refuse a completion that would leave the card with no evidence"; requires substantive result/summary/stored text (review approval exempt); `hermes_cli/kanban_db.py:2669` (`_gate_empty_completion(conn, task_id, result=result, summary=summary)`) — called from `complete_task` (def at kanban_db.py:2640)

#### Scenario: An empty completion is refused with an audit event
- **WHEN** `complete_task` would "leave the card with no evidence"
- **THEN** a `completion_blocked_empty_result` audit event is recorded and `EmptyCompletionError` is raised; "Review approvals are exempt: a human vouches for the card"
- Source: doc: hermes_cli/kanban_db.py:2784 (`_gate_empty_completion` docstring) — "Refuse a completion that would leave the card with no evidence."; event at :2802, raise at :2808
## Sub-area: Tail fold (commits after 2026-10-27)

### Requirement: Scheduled jobs get their actual run time in the prompt
A fired job's prompt SHALL carry the actual fire time; scheduling cadence SHALL stay out of job prompts (the cadence clause is scoped and also applied on update).
- Status: VERIFIED
- Evidence: [commit 3166c4a4b149] — give scheduled jobs their actual run time in the prompt; [commit 8a900e67159d] — keep scheduling cadence out of cron job prompts; [commit ce1370430ef8] — scope prompt clause to cadence and cover update — code: `_run_time_line()` (cron/scheduler_prompt.py:293) injected at :357; cadence clause at tools/cronjob_tools.py:1145 covers create and update (commits 3166c4a4b149/8a900e67159d/ce1370430ef8, all ancestors of the pin)
- Anchor: `cron/scheduler_prompt.py:357` (`prompt = _CRON_HINT + _run_time_line() + prompt`) — every fired job's assembled prompt carries the run-time line; `cron/scheduler_prompt.py:301` (`return f"[CURRENT RUN TIME: {safe_strftime(now, '%A, %Y-%m-%d %H:%M %Z').strip()}{zone}]

"`) — the fire-time line in the configured zone (def at :293); `tools/cronjob_tools.py:1145` (`"For create/update: the full self-contained prompt (when it runs goes in 'schedule'`) — cadence clause scoped to create/update, keeping cadence out of job prompts

#### Scenario: The prompt knows when the job fired
- **WHEN** a scheduled job fires and its prompt is assembled
- **THEN** the prompt carries the fire time
- Source: [relnote 0.23.0] "A manual run no longer consumes a one-shot, and prompts carry the fire time."

### Requirement: Gateway drain holds dispatch; a one-shot due during the hold fires once afterwards
While a gateway drain holds cron dispatch, a one-shot becoming due SHALL NOT be consumed or lost: it fires once when the next gateway ticks; the drain-hold grace extension is capped, never re-fires a claimed one-shot, and a failed write mid-drain does not restart the hold window.
- Status: VERIFIED
- Evidence: [commit c7b72e1fe4a7] — a one-shot due while a gateway drain holds dispatch fires once afterwards; [commit b7798657a008] — the drain-hold grace extension is capped and never re-fires a claimed one-shot; [commit b425edd28617] — a failed write mid-drain no longer restarts the hold window — code: dispatch_hold module docstring states the one-shot "fires once when dispatch resumes"; claim guard at cron/missed_runs.py:136-138; tests/cron/test_oneshot_due_during_drain_hold.py present
- Anchor: `cron/dispatch_hold.py:77` (`def grace_starts_at`) — a one-shot due during a hold counts grace from the hold's end; extension only for one-shots due within `MAX_EXTENSION_SECONDS` (dispatch_hold.py:29, 1800.0) of the hold's end, i.e. capped; `cron/dispatch_hold.py:32` (`_hold_since: dict[str, float] = {}`) — comment: "Kept in memory so a failed write mid-drain cannot reset ``since``"; `cron/missed_runs.py:137` (`grace_start = d.next_run_dt.timestamp() if claimed else grace_starts_at(`) — a claimed one-shot already fired once, so it never gets the extension (never re-dispatched)

#### Scenario: Due during the drain, fired by the next gateway
- **WHEN** a one-shot becomes due while a gateway drain holds dispatch
- **THEN** it fires once the next gateway ticks (it is neither dropped nor double-fired)
- Source: test: tests/cron/test_oneshot_due_during_drain_hold.py::test_oneshot_due_during_a_drain_fires_once_the_next_gateway_ticks

### Requirement: Per-job catch_up composes with grace_minutes and the global setting
Each job SHALL pick its own missed-run policy: the job's `catch_up` beats the global setting, an explicit `grace_minutes` still skips past it unless the job opts into `catch_up`, and a `catch_up: off` skip books exactly one missed row with the count.
- Status: VERIFIED
- Evidence: [commit d4865574e474] — review round 3: Stop settles by its own run, missed counts use the pinned zone, distributions keep catch_up; [commit e9f01737aae3] — how a job's catch_up composes with grace_minutes; [commit bb8c685c8981] — test: an explicit grace_minutes still skips past it unless the job opts into catch_up; [commit 3f435147912f] — a Run-now stopped by cancel reports cancelled, not failed — code: `catch_up` in `JOB_DEFINITION_FIELDS` (cron/job_definition.py:18); composition resolved in `job_catches_up` (cron/missed_runs.py:25-41)
- Anchor: `cron/missed_runs.py:25` (`def job_catches_up`) — docstring: "The job's own ``catch_up`` wins; otherwise one-shots skip, and recurring jobs skip past an explicit ``grace_minutes`` or else follow ``cron.catch_up_missed``"; `cron/missed_runs.py:28` (`value = job.get("catch_up")`) — job bool wins outright; explicit grace override → False at :38; global default at :41 (`_cron_config_number("catch_up_missed", True, ...)`) ; `cron/missed_runs.py:104` (`f"skipped, catch-up off; next run {new_next}"`) — the catch_up-off skip books one missed row with the count via `_book_missed(job, missed, first, ...)` (missed_runs.py:103, def at :63)

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

## Sub-area: Kanban (multi-agent work queue)

### Requirement: The dispatcher is a long-lived loop running inside the gateway
The dispatcher SHALL be a long-lived loop (default 60s, `kanban.dispatch_interval_seconds`) that each tick reclaims stale claims, promotes ready tasks, atomically claims, and spawns assigned profiles. It SHALL run inside the gateway by default (`kanban.dispatch_in_gateway: true`), under a per-board single-writer tick lock, and one tick's failure SHALL never stop the next.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Dispatcher bullet); [PR #50331](https://github.com/NousResearch/hermes-agent/pull/50331) — single-writer dispatch lock; [PR #41448](https://github.com/NousResearch/hermes-agent/pull/41448) — machine-global singleton lock; [PR #17805](https://github.com/NousResearch/hermes-agent/pull/17805) — durable board
- Anchor: `gateway/kanban_watchers.py:257` (`_kanban_dispatcher_watcher`) — docstring: "one tick every `dispatch_interval_seconds`... Gated by `kanban.dispatch_in_gateway` (default True)"; the gate is at kanban_watchers.py:231 (`kanban_cfg.get("dispatch_in_gateway", True)`); `gateway/kanban_watchers_dispatcher.py:50` (`dispatch_interval_seconds`) — default 60 with a 1.0s sanity floor at :55; `hermes_cli/kanban_db_dispatch.py:2026` (`_dispatch_tick_lock`) — per-DB-path non-blocking lock; the loser returns `DispatchResult(skipped_locked=True)` and writes nothing (:1995-2001)

#### Scenario: Two dispatchers tick one board
- **WHEN** two dispatchers tick the same `kanban.db` concurrently
- **THEN** "The loser returns an empty `DispatchResult` with `skipped_locked=True` and writes nothing; the lock is keyed on the resolved DB path so unrelated boards tick in parallel"
- Source: doc: hermes_cli/kanban_db_dispatch.py:1995-2001 (`_dispatch_tick` docstring)
### Requirement: Failure breaker stops spin loops; a terminal provider error trips it first attempt
After `kanban.failure_limit` consecutive non-success attempts on a task (default 2) the dispatcher SHALL auto-block it. A worker exit of `KANBAN_TERMINAL_PROVIDER_EXIT_CODE` (78) SHALL force-trip the breaker on that first attempt, sticky — `recompute_ready` must not auto-resume it — because no retry can heal a revoked credential or a gone model (#114587).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (isolation paragraph); [issue #114587](https://github.com/NousResearch/hermes-agent/pull/114587) — first-occurrence park; [issue #111306](https://github.com/NousResearch/hermes-agent/pull/111306) — every reclaim that releases a claim is booked as a failure (`release_stale_claims` docstring, kanban_db.py:2322-2325)
- Anchor: `hermes_cli/kanban_db.py:315` (`KANBAN_TERMINAL_PROVIDER_EXIT_CODE = 78`) — comment: "parks the card blocked on the FIRST occurrence instead of spending `failure_limit` identical spawns. 78 == BSD EX_CONFIG"; `hermes_cli/kanban_db_dispatch.py:37` (`DEFAULT_FAILURE_LIMIT = 2`); `hermes_cli/kanban_db_dispatch.py:1293` (`_record_task_failure(`) — inside `elif dead.terminal_provider:` (:1288) with `force_trip=True`, comment: "recompute_ready must not auto-resume it before the operator fixes the provider"

#### Scenario: A worker exits 78 (credential revoked, model gone)
- **WHEN** a worker exits `KANBAN_TERMINAL_PROVIDER_EXIT_CODE` (78 == EX_CONFIG)
- **THEN** "``force_trip`` blocks now, sticky: ``recompute_ready`` must not auto-resume it before the operator fixes the provider" — "A retry cannot heal a revoked credential or a missing model"
- Source: doc: hermes_cli/kanban_db_dispatch.py:1289-1292 (comment under `elif dead.terminal_provider:`)
### Requirement: Board is the hard isolation boundary; tenant is a soft namespace
A spawned worker's board SHALL be pinned in its environment (`HERMES_KANBAN_DB`, `HERMES_KANBAN_WORKSPACES_ROOT`, `HERMES_KANBAN_BOARD`) to the board the task was claimed from, so workers cannot see other boards; `tenant` SHALL stay a soft namespace within a board (`HERMES_TENANT`), giving workspace-path and memory-key isolation for one fleet serving several businesses.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Isolation paragraph); [PR #19653](https://github.com/NousResearch/hermes-agent/pull/19653) — multi-project boards; [PR #17805](https://github.com/NousResearch/hermes-agent/pull/17805) — durable multi-profile board
- Anchor: `hermes_cli/kanban_db_dispatch.py:2754` (`def _default_spawn`) — docstring: "board pins the child's `HERMES_KANBAN_DB` / `HERMES_KANBAN_BOARD` / workspaces_root to the board the task was claimed from, so workers cannot see other boards"; `hermes_cli/kanban_db_dispatch.py:2847` (`env["HERMES_KANBAN_DB"] = str(_kb.kanban_db_path(board=board))`) — with `HERMES_KANBAN_BOARD` pinned at :2851 as "defense-in-depth pin"; `hermes_cli/kanban_db_dispatch.py:2810` (`env["HERMES_TENANT"] = task.tenant`) — tenant travels as an env namespace, never a store pin

### Requirement: Worker liveness is a (pid, started_at) fingerprint, never bare PID
Reclaim and stale-claim paths SHALL treat a worker as live only when its PID is alive AND matches the start-time fingerprint recorded at spawn (`_worker_alive`); bare PID existence SHALL never license extending a claim or signalling a process. A spawn whose fingerprint could not be captured SHALL be held but never signalled — missing process identity is refusal, not permission (#99558).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (process-identity note — "never bare PID existence, or a recycled PID gets killed on reclaim"); [PR #99558](https://github.com/NousResearch/hermes-agent/pull/99558); [PR #50366](https://github.com/NousResearch/hermes-agent/pull/50366) — reclaim claim-lock-aware
- Anchor: `hermes_cli/kanban_db_dispatch.py:378` (`_worker_alive`) — "True when `pid` is live AND is still the worker we spawned... bare existence is never enough to extend a claim or to signal"; `hermes_cli/kanban_db_dispatch.py:393` (`_pid_recycled`) — fingerprint is `<instantiation epoch>|<start time>` (:364-375), survives no reboot; `hermes_cli/kanban_db_dispatch.py:361` (`UNVERIFIED_WORKER_FINGERPRINT = "unverified"`) — claim held, `_terminate_reclaimed_worker` refuses to signal it

#### Scenario: A reclaim probe meets a live PID with the wrong fingerprint
- **WHEN** a stale-claim reclaim sees the recorded PID alive but the start-time fingerprint no longer matches
- **THEN** `_worker_alive` is False — after a reboot or PID recycle "bare existence is never enough to extend a claim or to signal"
- Source: doc: hermes_cli/kanban_db_dispatch.py:378-380 (`_worker_alive` docstring)
### Requirement: Kanban notifications leave through the owning profile's adapter
Notification subscriptions SHALL carry a `notifier_profile`; a gateway notifier SHALL collect only the subs its served profiles own (`_notify_profile_filter`) and deliver via THAT profile's adapter, never the multiplexer's launch/primary adapter. A fail-closed skip SHALL log once per subscription row at WARNING with the remedy, never a bare `continue` (#110919).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Notifications bullet); [PR #110919](https://github.com/NousResearch/hermes-agent/pull/110919) — anchorless thread subscription warns once instead of vanishing; [issue #115460](https://github.com/NousResearch/hermes-agent/pull/115460)
- Anchor: `hermes_cli/kanban_db_notify.py:144` (`_notify_profile_filter`) — SQL predicate over `notifier_profile`; `list_notify_subs` docstring (:175): "Gateway notifiers pass the profiles they own so they cannot claim another gateway's events"; `gateway/kanban_watchers_notifier.py:162` (`_adapter_for_subscription`) — a profile holding its OWN adapter is a credential boundary "the primary never stands in"; `gateway/kanban_watchers_notifier.py:145` (`_warn_unroutable_sub_once`) — one WARNING naming the re-subscribe remedy

#### Scenario: A routed sub hits a closed credential gate
- **WHEN** a kanban notification subscription's owning profile fails the credential gate at delivery
- **THEN** it is a "permanent dead-end: delivery rewinds every tick with only a DEBUG line. Say so ONCE per row at WARNING" — never a silent `continue` (#115460)
- Source: doc: gateway/kanban_watchers_notifier.py:146-148 (`_warn_unroutable_sub_once` docstring)
### Requirement: Workers get the assignee's profile and board in a scrubbed child env
Dispatch SHALL build the worker's env via `build_subprocess_env` under the assignee's secret scope, pin the assignee's `HERMES_HOME`, and then call `strip_launch_profile_env` — the worker SHALL never inherit the default/launch profile's `.env` settings, `TERMINAL_*` policy, or a previous conversation's routing vars.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Notifications bullet — "scrubbed child env (`build_subprocess_env` + `strip_launch_profile_env`); they never inherit the default profile's `.env`") — code comment kanban_db_dispatch.py:2780-2787 records the incident (a routed home's worker inheriting the dispatcher's own `OPENAI_API_KEY`)
- Anchor: `hermes_cli/kanban_db_dispatch.py:2790` (`env = build_subprocess_env(`) — built inside `_worker_profile_scope(profile_home...)` (:2788) so passthrough resolves B's secrets, not the launch profile's; `hermes_cli/kanban_db_dispatch.py:2808` (`strip_launch_profile_env(env, profile_home)`) — comment: must not hand another profile "the launch profile's .env settings / TERMINAL_* policy"; `hermes_cli/kanban_db_dispatch.py:2798` (`env.pop(key, None)`) — every `session_context._VAR_MAP` routing var dropped ("its worker must never inherit routing mirrored by a previous gateway turn")

#### Scenario: A multiplexer dispatches for another profile
- **WHEN** the dispatcher spawns a worker for a profile other than the launch profile
- **THEN** `strip_launch_profile_env(env, profile_home)` runs — "A multiplexer dispatching for another profile must not hand it the launch profile's .env settings / TERMINAL_* policy — a standalone dispatcher never would."
- Source: doc: hermes_cli/kanban_db_dispatch.py:2806-2808 (comment above `strip_launch_profile_env`)
### Requirement: Kanban guidance and stop nudge gate on ownership, not tool access
Every reader that turns `HERMES_KANBAN_TASK` into worker behaviour (KANBAN_GUIDANCE injection, the stop nudge, shell-hook task stamping) SHALL resolve it through `owned_kanban_task()`, which answers `""` for delegate children and non-dispatcher-owned in-process contexts; tool visibility via a profile's toolset and an inherited env var are NOT ownership.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Prompt injection sites bullet)
- Anchor: `agent/delegation_context.py:96` (`owned_kanban_task`) — docstring: "Tool access is not worker identity... every reader... goes through this one helper"; returns `""` unless `is_dispatcher_owned_worker_context()` (:71); `agent/agent_init.py:1045` (`KANBAN_GUIDANCE if owned_kanban_task() and "kanban_show" in agent.valid_tool_names`) — guidance needs BOTH ownership and tool access; `agent/kanban_stop.py:39` (`return bool(owned_kanban_task())`) — the stop nudge's gate

#### Scenario: A delegate child inherits HERMES_KANBAN_TASK
- **WHEN** a delegate child or cron run beside a worker reads `owned_kanban_task()`
- **THEN** it answers `""` — "Tool access is not worker identity" — so no kanban guidance is injected and the stop nudge stays silent
- Source: doc: agent/delegation_context.py:96-98 (`owned_kanban_task` docstring)
### Requirement: Descendant fence is a path, not a flag
A delegated child's Kanban marker (`DELEGATED_CHILD_ENV_MARKER`) SHALL carry the fenced board ROOT, and `kanban_path_is_fenced` SHALL deny mutations only at the dispatcher-pinned `HERMES_KANBAN_DB` or under that root — so a child working against a scratch `HERMES_HOME` keeps a writable board; a legacy `"1"` marker fences everything.
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (Descendant fence bullet)
- Anchor: `agent/delegation_context.py:144` (`kanban_path_is_fenced`) — pinned-DB equality at :158-160, `target.relative_to(Path(marker)...)` under-root check at :161-165, marker `"1"` fences all at :154; `agent/delegation_context.py:20` (`DELEGATED_CHILD_ENV_MARKER = "HERMES_DELEGATED_CHILD_CONTEXT"`); `agent/delegation_context.py:122` (`scrub_kanban_env`) — strips worker identity but keeps an inherited path-valued marker, docstring: "a child running a repro against a temp `HERMES_HOME` got a silently read-only board there"

#### Scenario: A delegated child runs against a scratch home
- **WHEN** a delegated child touches a Kanban DB other than the dispatcher-pinned one (e.g. a repro against a temp `HERMES_HOME`)
- **THEN** the fence applies only to the pinned DB or the marker's board root — otherwise "a child running a repro against a temp `HERMES_HOME` got a silently read-only board there"
- Source: doc: agent/delegation_context.py:129-131 (`scrub_kanban_env` docstring) — "a child running a repro against a temp ``HERMES_HOME`` got a silently read-only board there"
### Requirement: Owner recovery refuses to guess; a lost worker's exit is booked once
The dispatcher SHALL not authorize another attempt on missing or ambiguous owner receipts
("Missing/ambiguous owner receipts never authorize another attempt"), and SHALL treat missing
evidence as never proof that an attempt is over; a lost worker's clean exit SHALL be booked as a
crash exactly once — not additionally as a protocol violation — while transport loss resumes the
same attempt bounded from the owner's last answer (d4283a9c9cdf post-commit block hook;
e62c15e667e4; 89f13590e0e8).
- Status: VERIFIED
- Evidence: doc: cron/AGENTS.md § Kanban (worker-liveness/reclaim context); tail commits d4283a9c9cdf (dispatch dependency block hook post-commit), e62c15e667e4, c777ba429fc8, 89f13590e0e8, b2e0171c29e5; test commit 25e7f5fc21d8 (post-commit kanban_task_blocked pin)
- Anchor: `hermes_cli/kanban_owner_recovery.py:46` (`owner_reclaim_paused` docstring) — "Missing/ambiguous owner receipts never authorize another attempt"; `hermes_cli/kanban_owner_recovery.py:153` (`owner_attempt_provably_over`) — "Missing evidence is never proof"; `hermes_cli/kanban_worker_client.py:68` (comment) — "The wait is bounded from the owner's last answer"; `hermes_cli/kanban_db.py:3211` (`_fire_task_hook("kanban_task_blocked", ...)`) — fired outside the write transaction

## Known gaps / open questions
- Kanban pass 3 (G-07) residual scenario-debt, kept ungrounded per rule (no Tier A/B/C trigger+outcome text): REQ "Board is the hard isolation boundary" — cron/AGENTS.md states the invariant but no incident/documented trigger exists at the pin; REQ "Owner recovery refuses to guess" — evidence is code docstrings (invariants) + tail commit subjects, no documented scenario pair.
- Wall-clock stale-claim guard for live-but-deadlocked workers (#115692) and dispatch-hold/quota-hold mechanics (`cron/dispatch_hold.py`, `extra_fire.settle`) referenced by doc/bundle, not drafted — pass 2.
- Chronos managed-cron contract (`website/docs/developer-guide/chronos-managed-cron-contract.md`, #97494 403 failover to built-in ticker) not drafted — external service contract, needs a dedicated requirement pass.
- Kanban dispatcher invariants (cron/AGENTS.md second half) not read/drafted; kanban sits at the deferred plugins boundary — ownership decision needed.
- `hermes cron` CLI surface verbs drafted only as part of scheduling entry points.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.

## Scenario-ification notes
- REQ "Lost manual runs are recorded honestly": no doc-grounded trigger; kept as invariant. (#128509 commit-title-only; relnote 2026.9.11's killed-manual-run bullet (#106733) is about not blocking the next run, a different contract.)
- REQ "Kanban completion requires evidence": no doc-grounded trigger for the REFUSAL; kept as invariant. (#117483 commit-title-only; no test named for refusing empty `complete_task` evidence found. The #91264 side of its Evidence IS test-grounded — tests/hermes_cli/test_kanban_goal_mode.py::test_loop_stops_on_judge_transport_failure and ::test_loop_stops_on_worker_failed_flag — but those pin goal-loop stops, not the complete_task evidence gate, so they do not satisfy this requirement's WHEN/THEN.)
- Doc-vs-code surprise (flagged, not fixed): website/docs/user-guide/features/kanban.md § Recommended handoff evidence says the evidence keys are "a convention, not a schema requirement" (line: These keys are a convention, not a schema requirement), while REQ "Kanban completion requires evidence" (from #117483) asserts a hard refusal of empty evidence; kanban.md's `complete_task` boundary prose covers GitHub required-check evidence, not the empty-result refusal.
- Kanban tail commits noted for a dedicated kanban pass (fold cap reached here): d4283a9c9cdf + 25e7f5fc21d8 (dependency block hook post-commit), dbde5a991ae0 / eace3e056e8b (worker vs restart-wait), 3776709d521b (isolate and reap owned Kanban systemd scopes, relnote 0.22.1).
- Tail items rejected (out of capability ownership): plugin-catalog/catalog entries and bumps (3a9c3d46d522, bb719c349235, fb5a2b140371, 083772b37465, 8aaa8af075f8, fef61fbc7fd5, f6e0ffe53529, 40bbdd2e3274, 0f29a7d98917, 3093bc3117d4, d8232c0eb889, ad98ff37f0e5), desktop (9dd1ea34f23e retry schedule, e03222879c39 pin Kanban boards as tabs, e86597e2605e Scheduled-posts pane), rooms/group-chat delivery tail cluster 2e1c0291b881 / fbe94827167a / f7065f26d76f / 32f95b873f52 (gateway-messaging & rooms boundary — noted for that capability), sessions-state (edf1495a314f warm reopen totals), CI (e534ed0b08cc, df128c13bb9d), webhook kanban_task_id guard deea569ef62d (webhooks boundary).
- Tail items folded: 3166c4a4b149 + 8a900e67159d + ce1370430ef8 → "run time in the prompt"; c7b72e1fe4a7 + b7798657a008 + b425edd28617 → "drain hold"; d4865574e474 + e9f01737aae3 + bb8c685c8981 + 3f435147912f → "catch_up composition". f7a018a77cbd DST-adjacent timezone test fix is test-infra, not folded.
