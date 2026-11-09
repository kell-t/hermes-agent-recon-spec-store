# Capability: cron-background

Baseline: hermes-agent main @ 2bd378ed (2026-11-05). Evidence window: 2026-02-26 .. 2026-10-27.

## Purpose
Scheduled background jobs: `cron/jobs.py` (job store) and `cron/scheduler.py` (tick loop + `scheduler_*.py` siblings), driven by the `cronjob` tool, the `hermes cron` CLI, and `/cron`. The scheduler's hardening invariants — at-most-once occurrence accounting, inactivity watchdog, headless refusal, per-profile scope binding — each guard a real incident. Kanban (the multi-agent work queue) shares the area guide.

## Primary code locations
- `cron/jobs.py`, `cron/job_definition.py`, `cron/jobs_time.py` — store, definition fields, time math
- `cron/scheduler.py` + `cron/scheduler_*.py` — tick loop, multiplex provider, gateway gate
- `cron/occurrences.py`, `cron/executions.py`, `cron/missed_runs.py` — occurrence accounting
- `cron/AGENTS.md` — the invariants law; long-form `website/docs/developer-guide/cron-internals.md`

## Requirements

### Requirement: Four schedule notations and a defined job schema
Jobs SHALL accept duration (`"30m"`), every-phrase (`"every monday 9am"`), 5-field cron (`"0 9 * * *"`), and ISO one-shot schedules; job definition fields (`skills`, `model`/`provider` overrides, `script`, `context_from`, `workdir`, `timezone`, `grace_minutes`) SHALL stay in `JOB_DEFINITION_FIELDS` or profile distribution strips them.
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Cron
**Anchor**: `cron/job_definition.py:13` (`JOB_DEFINITION_FIELDS = frozenset({`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Jobs SHALL accept duration (`"30m"`), every-phrase (`"every monday 9am"`), 5-field cron (`"0 9 * * *"`), and ISO one-shot schedules;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Pre-run scripts are files, never command lines
A job's `script` SHALL always be a file under `HERMES_HOME/scripts/` — never an inline command line (`script='echo hi'` is refused at creation); its stdout is injected into the prompt, and `no_agent=True` makes the script the whole job.
**Status**: INFERRED
**Evidence**: doc: cron/AGENTS.md § Cron (per-job fields)
**Anchor**: not located (creation-time refusal site not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A job's `script` SHALL always be a file under `HERMES_HOME/scripts/` — never an inline command line (`script='echo hi'` is refused at creation);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Idle-based inactivity watchdog
Cron agent sessions SHALL be hard-interrupted on inactivity (default 600s idle, `HERMES_CRON_TIMEOUT` override, `0` unlimited): the watchdog measures idle time, not wall-clock, so a long-but-active job is never cut and a stalled one cannot monopolize the scheduler; attached scripts are bounded separately by a 3600s script timeout.
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants
**Anchor**: `cron/executions.py:195` (reads `_cron_inactivity_seconds()`), `cron/executions.py:198`


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Cron agent sessions SHALL be hard-interrupted on inactivity (default 600s idle, `HERMES_CRON_TIMEOUT` override, `0` unlimited): the watchdog measures idle time, not wall-clock, so a long-but-active job is never cut and a stalled one cannot monopolize the scheduler;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: At-most-once occurrence accounting
`tick()` SHALL advance `next_run_at` before dispatch and stamp `pending_slot` in the same save; a scan finding the stamp with a dead owner SHALL restore the instant exactly once; the executions ledger's `scheduled_instant` SHALL block a second fire, and skipped past-grace misses SHALL be logged — a slot is never dropped silently.
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants (cites #107485); module `cron/occurrences.py` exists for the restore-once rule
**Anchor**: `cron/occurrences.py` (module present; restore-once logic per doc), `cron/scheduler.py:187` (pre-lock boot fingerprint raise)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `tick()` SHALL advance `next_run_at` before dispatch and stamp `pending_slot` in the same save;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Bounded catch-up window
Missed-run catch-up SHALL use half the period clamped to 120s–2h, overridable per job by `grace_minutes` (`0` meaning never catch up — a real value, never conflated with unset), with 120s grace for missed one-shots.
**Status**: INFERRED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants
**Anchor**: not located (`cron/jobs_time.py` per doc "knobs live in cron/jobs_time.py")


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Missed-run catch-up SHALL use half the period clamped to 120s–2h, overridable per job by `grace_minutes` (`0` meaning never catch up — a real value, never conflated with unset), with 120s grace for missed one-shots.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Pinned timezone owns the whole run-time path
A job's pinned `timezone` SHALL govern every `next_run_at` write site (not just computation); `compute_next_run` resolves job pin before profile zone, `_evaluate_due_job` normalizes stored instants into the job's zone, and timezone-shift repair SHALL be skipped for pinned jobs.
**Status**: INFERRED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants ("one missed site is a burst re-run or a skipped slot")
**Anchor**: not located (`cron/jobs_time.py`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A job's pinned `timezone` SHALL govern every `next_run_at` write site (not just computation);
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Per-home tick lock
A file lock at `<home>/cron/.tick.lock` SHALL keep overlapping processes to one tick at a time for that profile's store, addressed profile-aware (never a `~/.hermes/...` literal).
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants
**Anchor**: `cron/scheduler.py:3` (module docstring states the lock)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A file lock at `<home>/cron/.tick.lock` SHALL keep overlapping processes to one tick at a time for that profile's store, addressed profile-aware (never a `~/.hermes/...` literal).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Headless ticks refuse rather than spawn a gateway
`hermes cron tick` (headless mode) SHALL skip agent jobs when no gateway owns the home — stamping `last_fire_error`, warning once per tick, leaving the due instant untouched — instead of spawning an unmanaged gateway daemon; the in-process ticker and `hermes cron run` are not headless.
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants ("Same policy as approvals")
**Anchor**: `cron/scheduler_gateway_gate.py` (module dedicated to the gate; opened as gate owner per doc)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** `hermes cron tick` (headless mode) SHALL skip agent jobs when no gateway owns the home — stamping `last_fire_error`, warning once per tick, leaving the due instant untouched — instead of spawning an unmanaged gateway daemon;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: One ticker binds each served profile's scope
The multiplex ticker SHALL be one ticker iterating served profiles sequentially under a per-home scope guard (home + secrets + terminal scope), never N threads; everything a tick touches (store open, lock path, failure counters, job env, session-end flush) lives inside the guard, and supervision re-enumerates homes when profile dirs appear or are tombstoned.
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants (documents the historical bug: a store opened before scope entry wrote a secondary profile's run records into the launch profile's jobs.json)
**Anchor**: `cron/scheduler_provider.py:539` (`_start_multiplex`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** The multiplex ticker SHALL be one ticker iterating served profiles sequentially under a per-home scope guard (home + secrets + terminal scope), never N threads;
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: In-flight cron state is (home, job) keyed
Because one process ticks N profile stores, in-flight scheduler state SHALL be keyed by `(home key, job id)` (two profiles may legitimately carry a `daily-brief`), and the parallel job pool SHALL be keyed by home (`cron.max_parallel_jobs` per profile).
**Status**: VERIFIED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants ("Per-profile process assumptions are the bug class")
**Anchor**: `cron/scheduler.py:581` (`def _inflight_key(job_id, home=None) -> tuple`)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Because one process ticks N profile stores, in-flight scheduler state SHALL be keyed by `(home key, job id)` (two profiles may legitimately carry a `daily-brief`), and the parallel job pool SHALL be keyed by home (`cron.max_parallel_jobs` per profile).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Cron ticking is not gated on the multiplex flag
One host gateway SHALL tick every profile's store regardless of `gateway.multiplex_profiles` (that flag gates adapters only).
**Status**: INFERRED
**Evidence**: doc: cron/AGENTS.md § Hardening invariants (names `run.py::_cron_tick_profile_homes`)
**Anchor**: not located (gateway/run.py sibling not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** One host gateway SHALL tick every profile's store regardless of `gateway.multiplex_profiles` (that flag gates adapters only).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Pinned job models never fall back globally
A job with a pinned model/provider SHALL never fall back to the global fallback chain on failure.
**Status**: INFERRED
**Evidence**: [PR #120312](https://github.com/NousResearch/hermes-agent/pull/120312) — "a pinned job never falls back to the global fallback chain"
**Anchor**: `cron/jobs_model_pin.py` (module named for the rule; lines not opened)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A job with a pinned model/provider SHALL never fall back to the global fallback chain on failure.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Lost manual runs are recorded honestly
A manual `hermes cron run` whose worker is lost SHALL be recorded as a lost run, not reported as a restart that never happened.
**Status**: INFERRED
**Evidence**: [PR #128509](https://github.com/NousResearch/hermes-agent/pull/128509) — "record a lost manual run instead of reporting a restart that never happened"
**Anchor**: not located


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** A manual `hermes cron run` whose worker is lost SHALL be recorded as a lost run, not reported as a restart that never happened.
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

### Requirement: Kanban completion requires evidence
Completing a Kanban task SHALL refuse empty result evidence (`complete_task` without evidence is rejected).
**Status**: INFERRED
**Evidence**: [PR #117483](https://github.com/NousResearch/hermes-agent/pull/117483) — "refuse empty complete_task evidence"; [PR #91264](https://github.com/NousResearch/hermes-agent/pull/91264) — judge transport failure / worker failed stops (tests)
**Anchor**: not located (kanban code outside `cron/` proper — `plugins/kanban/` boundary, deferred plugins scope)


#### Scenario: Conformance check (derived)
- **WHEN** the behavior described by this requirement is exercised
- **THEN** Completing a Kanban task SHALL refuse empty result evidence (`complete_task` without evidence is rejected).
- NOTE: SCENARIO-DEBT (derived, pass-4 conformance) — no scenario evidence in pass-3 corpus;
  replace with evidence-backed scenarios on next recon pass.

## Known gaps / open questions
- Wall-clock stale-claim guard for live-but-deadlocked workers (#115692) and dispatch-hold/quota-hold mechanics (`cron/dispatch_hold.py`, `extra_fire.settle`) referenced by doc/bundle, not drafted — pass 2.
- Chronos managed-cron contract (`website/docs/developer-guide/chronos-managed-cron-contract.md`, #97494 403 failover to built-in ticker) not drafted — external service contract, needs a dedicated requirement pass.
- Kanban dispatcher invariants (cron/AGENTS.md second half) not read/drafted; kanban sits at the deferred plugins boundary — ownership decision needed.
- `hermes cron` CLI surface verbs drafted only as part of scheduling entry points.
- PR-ref window ends 2026-10-27 vs pin 2026-11-05.
