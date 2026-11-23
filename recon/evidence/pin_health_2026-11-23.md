# Pin-health survey — v0.23.1 → v0.23.3 (2026-11-23, priority run)

Trigger (criterion 3): GitHub `releases/latest` = **v0.23.3**, published
2026-11-20T00:34:38Z, non-prerelease — newer than the pin v0.23.1 AND
newer than v0.23.2, which the 2026-11-17 survey had costed. The v0.23.2
survey's headline (0 dead-files, mechanically cheap) does NOT carry over:
the window gained a breaking state-store refactor (see below). Re-pin
remains OWNER-GATED — this file is the readiness survey only; the pin is
unchanged (`3b421578588243f920886e6fe79a6faa87ea026e`).

## Tag resolution (per pin law)

- `refs/tags/v0.23.3` → annotated tag object `2861fe3744f8134b782659438961a4f69ab5d495`
  → commit `caafe5389ae585ef77387a962aee05b1bcf17029` (`GET /git/tags/<obj>`
  object.sha; the cache checkout at tag `v0.23.3` resolves to the same commit).
- Window pin..v0.23.3: **9,829 commits** (local `git rev-list --count`),
  8,430 tree-level changed files. Release notes stored
  `recon/evidence/relnote_v0.23.3.txt`.
- Default branch vs pin (criterion 4): main ahead_by **10,813**
  (compare API, 2026-11-23) — subsumed by the release.

## Method

`recon/scripts/pin_health.py` with a new `PIN_HEALTH_REPO` env override
(ported from the gufo store's copy — the 2026-11-17 run instead checked
the source cache out at the target and restored it afterwards). Survey
checkout via `sync_repo.py --ref v0.23.3 --wt pinhealth-20261123`
(named worktree at `.repo/wt/pinhealth-20261123`, detached at
`caafe538`; pinned `wt/main` untouched; worktree retired after the run).
Verdicts identical dialect to `audit_requirements.py`. Raw output:
`recon/evidence/pin_health_2026-11-23.json`.

## Results — 509 unique anchor cites at v0.23.3 (was 408 at v0.23.2; fleet +17 reqs since the 11-17 survey from passes 9–10)

| Verdict | Count |
|---|---|
| OK | 363 |
| SHIFTED | 113 |
| OOB | 6 |
| HINT-DEAD | 5 (3 survey-tool FPs, 1 known rename, 1 real = old-store removal) |
| DEAD-FILE | 21 |
| MOVED | 1 (already located 2026-11-17) |

Per-cap: sessions-state is the collapse zone — DEAD-FILE 19, OOB 5,
HINT-DEAD 1, SHIFTED 6, OK 3. tools-toolsets carries the other 2
DEAD-FILE + the rename HINT-DEAD + the MOVED. Every other capability is
OK/SHIFTED only (mechanical band).

## HEADLINE — `be3d6affc8` refactor(state)!: remove the old session store

Landed 2026-11-17T19:10+01:00 (inside the v0.23.2→v0.23.3 window, ~370 PRs;
258 files deleted, 164 modified). The legacy root-level `hermes_state_*.py`
store family the **sessions-state** capability was drafted against is gone:
`hermes_state_wal.py`, `hermes_state_schema.py`, `hermes_state_mutation_guards.py`,
`hermes_state_prune_rewrite.py`, `hermes_state_errors.py`, `hermes_state_reconcile.py`,
`hermes_state_readpool.py`, `hermes_state_fts.py`, `hermes_state_repair.py`,
`hermes_state_media.py`, `hermes_state_sessions.py` (+ tools-toolsets'
`hermes_state_identity.py`, `hermes_state_messages.py`) → 21 DEAD-FILE cites.
`hermes_state.py` survives only as a 655-line plugins stand-in
(`:198` `_READ_BUSY_TIMEOUT_S` GONE; `:741`/`:835` OOB);
`hermes_state_common.py` is a 17-line stand-in (`:160/:164/:265` OOB).

Replacement surfaces at v0.23.3 (grepped live in the survey worktree):

| Dead at pin | Successor at v0.23.3 |
|---|---|
| `hermes_state_readpool.py` | `persistence/sqlite/_state/readpool.py` |
| `hermes_state_errors.py` | `persistence/sqlite/_state/errors.py` (shared predicates via `storage_errors`) |
| `hermes_state_repair.py` | `persistence/sqlite/_state/repair.py` |
| `hermes_state_mutation_guards.py` | `persistence/sqlite/_state/guard.py` |
| `hermes_state_wal.py` | `sqlite_support.py` (journal-mode policy, WAL fallbacks) |
| `hermes_state_schema.py` / FTS | `persistence/sqlite/_schema.py`, `_schema_ddl.py` (`fts_storage_version`) |
| `hermes_state_sessions.py` / `hermes_state_messages.py` | `persistence/sqlite/conversation/sessions.py`, `.../messages.py` (+ `_store/sessions.py`, `_store/messages.py`, `_store/messages_sql.py`, `_store/session_list.py`) |
| `hermes_state_media.py` | `persistence/sqlite/conversation/_store/media.py` |
| `hermes_state_prune_rewrite.py` | `persistence/sqlite/conversation/_store/prune_rewrite.py` |
| `hermes_state_identity.py` | `persistence/sqlite/conversation/_store/identity.py` |
| `hermes_state_reconcile.py` | `persistence/sqlite/admin/_reconcile.py` |
| onboarding rules (agent) | `session_rules/` |

Commit message adds observable contract changes a re-pin pass must re-read:
stand-in SessionDB close/reopen semantics (re-open with warning unless the
file was replaced or the store is latched corrupt; read-only raises), named
source wins over source list, `persistence=` injection for agents given a
stand-in, plugin context engines get `persistence=` beside deprecated
`session_db=`, backend-import guard now refuses anything outside
`persistence/`.

**Costing: sessions-state (13 reqs) is a behavioral rewrite at re-pin, not a
re-anchor wave. The v0.23.2 survey's "mechanically cheap" verdict is
superseded for v0.23.3.** All other caps stay in the mechanical band.

## Triage of non-OK, non-SHIFTED (each opened live at target)

- HINT-DEAD `hermes_cli/commands.py:211` — **FP** (survey matcher splits the
  dotted hint token and prefix-compares; `gateway_config_gate="display.tool_progress_command"`
  verbatim at :211). Same FP class recorded 2026-11-17; kit gate passes it.
- HINT-DEAD `cron/quota_hold.py:56` — **FP**, same dotted-token class
  (`cur = cur.__cause__ or cur.__context__` verbatim at :56).
- HINT-DEAD `cron/scheduler_liveness.py:76` — **FP**, same class
  (`self._idle_seconds() >= self._every` verbatim at :76).
- HINT-DEAD `tools/browser_harness_dirs.py:98` — **real rename, already
  documented 2026-11-17**: `fit_default_socket_dir` deleted by `f5dc3f632b`;
  surviving chain re-verified at target — `socket_dir_budget` :45,
  `fits_socket_budget` :55, `socket_fit_runtime_dir` :129. Re-anchor at re-pin.
- HINT-DEAD `hermes_state.py:198` — **real**: old-store removal (above).
- OOB `agent/context_compressor.py:5462` — **mechanical**: quoted hint
  verbatim at :5061 (file 5,610→5,209 lines).
- OOB `hermes_state.py:741/:835`, `hermes_state_common.py:160/:164/:265` —
  **real**: old-store removal (stand-ins).
- MOVED `utils.py:679` (`safe_json_loads`) — already located 2026-11-17:
  `utils/files.py:661` at target (grep-verified). The suffix-matcher
  candidate `plugins/platforms/qqbot/utils.py` is a tool artifact — a
  different file; do not re-anchor there.

## Deferred to the re-pin pass (post-approval)

Deep `[PR #NNNN]`/commit-cite ancestry resweep across the 9,829-commit
window (removal-check law — the 11-16 resweep covers the OLD window only);
sessions-state behavioral re-write against `persistence/sqlite/_state/` +
conversation store modules; ~113-anchor mechanical re-anchor wave;
`releases.json` re-mine + corpus re-mine; relnotes v0.23.2 ALREADY staged,
v0.23.3 staged this run.

**OWNER ACTION: approve re-pin to v0.23.3 @ `caafe5389ae5`**
(supersedes the 2026-11-17 v0.23.2 target).
