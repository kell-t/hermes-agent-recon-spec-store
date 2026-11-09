# RECON_LEDGER — hermes-agent

Store: `github/NousResearch/hermes-agent` (id `hermes-agent`). Boot order: PLAYBOOK.md → repo_config.yaml → this file.

## CURRENT STATE (pass 2 complete, 2026-11-08)

- Baseline pin: `main @ 2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19` (tag **v0.23.0**, 2026-11-05). `recon/baseline.txt`. Unchanged — owner has not re-pinned.
- Validation: `openspec validate --all --strict --store hermes-agent` → **Totals: 10 passed, 0 failed** (openspec 1.16.1).
- Scenario debt: **130 → 23** derived SCENARIO-DEBT blocks (target <40 met); **213 evidence-backed scenarios** (Tier A release-note quotes, Tier B in-repo docs, Tier C test names) under requirements in `specs_draft/` and converted specs. Residual debt: config-provider-models 7, profiles-isolation 4, tools-toolsets 4, gateway-messaging 3, cron-background 2, cli-surface 1, sessions-state 1, skills-system 1.
- Fleet: **158 requirements** (pass 1: 130; +28 from tail folds), **94 VERIFIED (59.5%)** (pass 1: 62/47.7%; reference 89.6%), 64 INFERRED, 0 UNVERIFIED-as-spec.
- Store registration: store must be registered on the machine (`openspec store register <store-path>`); registrations do not travel with the git repo.

### Coverage table (scripted tally of specs_draft/, pass 2)

| Capability | Reqs | VERIFIED | INFERRED | Grounded scenarios | Scenario debt |
|---|---|---|---|---|---|
| agent-turn-loop | 17 | 12 | 5 | 29 | 0 |
| gateway-messaging | 17 | 16 | 1 | 28 | 3 |
| sessions-state | 13 | 7 | 6 | 23 | 1 |
| tools-toolsets | 15 | 6 | 9 | 17 | 4 |
| profiles-isolation | 16 | 6 | 10 | 15 | 4 |
| cron-background | 17 | 7 | 10 | 23 | 2 |
| skills-system | 17 | 16 | 1 | 28 | 1 |
| config-provider-models | 15 | 6 | 9 | 12 | 7 |
| cli-surface | 14 | 4 | 10 | 18 | 1 |
| delegation-orchestration | 17 | 14 | 3 | 20 | 0 |
| **TOTAL** | **158** | **94 (59.5%)** | **64** | **213** | **23** |

Audit performed (scripted, pass 2): all `file:line` anchors exist at the pin, line numbers within file length; every `pull/NNNN` cite matches mined evidence; **54 tail-commit sha cites all resolve to real commits at the pin**; 27 relnote quotes overlap their release bodies (one flag hand-verified verbatim — audit regex punctuation artifact, not a fabrication); 84 test cites verified as existing paths + class/function names. Incidents caught by the spec-writer audit gate and fixed (children's self-checks missed them): 1 fabricated test-class segment (`TestBusyPathAuthz` → `TestBusySessionAuthBypass`), 2 relnote tag mislabels (`v0.6.0` → `v2026.3.30 (v0.6.0)`), 2 bare-filename anchors qualified, 4 requirement bodies trimmed under the 500-char strict limit, 13 tail-fold requirement blocks relocated into `## Requirements` (validator rule, see quirks).

### Evidence inventory (`recon/evidence/`)
- `pr_commits.json` — 5,893 PR-landed commits (of 58,953 no-merge, 62,624 total), window 2026-02-26..2026-10-27; `pr_index.json` (5,601 unique PRs).
- `tail_commits.json` + `tail_clusters.json` — **pass 2, G-01 CLOSED**: 2,031 commits with author date > 2026-10-27 at the pin, **0 carry `(#NNNN)` refs (convention ended, tail evidence = sha+subject only)**; clustered scope-first (conventional-commit scope → capability), 701 bucketed, 1,330 uncategorized (deferred-scope areas). Each `bundle_<cap>.txt` carries a `# ==== TAIL APPEND` section (≤40/cap).
- `releases.json` — 47 GitHub releases (all with bodies; 44 stable tags); `clusters.json` + `bundle_*.txt` ×10; `repo_meta.json`.
- API budget spend pass 2: 0 GitHub-API calls (git-log mining only).

## Gap register (pass 2 state)

Closed this pass:
- G-01 **PR-ref tail hole CLOSED**: mined no-filter to `tail_commits.json` (`scripts/mine_tail.py`), TAIL APPEND in all bundles, 28 tail-folded requirements merged.
- G-03 **Ownership CLOSED (3 of 4)** — recorded in repo_config `scope.ownership_decisions`: kanban→cron-background (root AGENTS.md routing table row `cron/, kanban → cron/AGENTS.md`); compression-display→sessions-state (`hermes_state_compaction_display.py` is the SessionDB read-layer contract); fleet-reconciliation excluded-confirmed → deferred update-packaging. (Plugin×skill / plugin×tool contracts remain open → G-09.)
- G-04 **Cluster regex noise CLOSED for the tail**: tail clustering is scope-first with narrowed subject fallbacks (`scripts/mine_tail.py` SCOPES/SUBJ; note in repo_config `clustering`).
- G-05 **skills-system verification CLOSED**: 23% → **94% VERIFIED** (16/17); curator sub-area drafted from skills/AGENTS.md + `agent/curator*.py` at the pin (inactivity trigger, scope invariants, tar.gz+manifest snapshots).

Open:
- G-02 **UNVERIFIED backlog** (per-file `## Known gaps`, never presented as spec): `/compress` parser contract; `--now` *parser* site (deferral rule anchored at `agent/turn_context.py:1207`, `agent/delegation_backends.py:8`; the slash-argument parse site still open); chronos managed-cron contract; worktree isolation knob; human-first author credit (no mechanical check — see D-03).
- G-06 **INFERRED mass (64 reqs)**: cli-surface 10, profiles-isolation 10, cron-background 10, tools-toolsets 9, config-provider-models 9, sessions-state 6 — pass-3 anchor-verify targets.
- G-07 **Tail not fully consumed**: bundles show 40/cap of up to 260 clustered; kanban tail (post-commit block hook, restart-wait, systemd scopes) deferred to a dedicated kanban pass; rooms-delivery tail cluster → gateway-messaging; ~1,330 uncategorized tail commits are deferred-bucket scope — deliberate.
- G-08 **Scenario-debt 23**: no Tier A/B/C trigger+outcome text exists for these; left property-style with per-file notes. NOT cut — deleting grounded requirements to flatter a metric would destroy spec value.
- G-09 **plugin×skill and plugin×tool contracts** unassigned (survives from G-03): boundary sits against deferred plugins-mcp; revisit when that bucket opens.

Deferred buckets (not reconstructed — deliberate): desktop-ui (7,059 scope commits), tui-web, plugins-mcp (2,371), update-packaging (1,063+), memory-system, skins/pets/locales/tests/website/evals.

## Drift register
- D-01 **CLOSED pass 2**: the 85% gateway session-hygiene threshold claimed by `agent/AGENTS.md:83` exists at the pin — `gateway/run_turn_hygiene.py:102` (`threshold_pct=0.85`; :97 "deliberately HIGHER than the agent's compressor (0.50)"). Pass 1 had searched only `gateway/session*.py`. Anchor set in the gateway spec.
- D-02 `provider-runtime.md` matched the tree; no drift (pass 1, unchanged).
- D-03 **OPEN**: `skills/AGENTS.md` calls authoring standards "HARDLINE — enforced by test_authoring_standards.py", but that test enforces only the mechanical subset; prose rules 2–3 exist as advisory lints (`tools/skill_linter.py` — "Findings never block by themselves") and rule 4 (author credit) has no mechanical check. Doc claim kept as requirement per DRAFT_TEMPLATE rule 6. Upstream-report candidate (owner approval required).
- D-04 **OPEN** (pass-2 flags, recorded in per-file Known gaps): `tools/AGENTS.md` § Delegation "default 3" stale vs code `_DEFAULT_MAX_CONCURRENT_CHILDREN = 10` and docs ("Up to 10"); "tasks-only" vs "Shapes: single or batch"; `delegation.backend` (plugin selector) vs `delegation.provider` (credential pin) naming trap; kanban.md calls handoff evidence "a convention" while the hard-refusal requirement rests on #91264 tests that pin goal-loop stops; relnote 2026.3.23 records disabled toolsets historically re-enabling (reduction invariant pinned only at resolution-test level).

## Pass history
| Date | Pass | Pin | Outcome |
|---|---|---|---|
| 2026-11-08 | 1 (solo — fleet delegation blocked in one-shot runs; waves inline) | v0.23.0 @ 2bd378ed | Scope set (10 caps); 130 reqs drafted, converted, strict-valid green; 130 scenario-debt; 47.7% VERIFIED |
| 2026-11-08 | 2 (fleet: 2 waves × 3 children + inline audit gate; owner steering mid-pass) | v0.23.0 @ 2bd378ed | 158 reqs / 59.5% VERIFIED / 23 debt / 213 grounded scenarios; G-01/03(3of4)/04/05 closed; D-01 closed; strict green |

Commits — pass 1: e785176 → a77b2e9 → ee3db62 → e9a612c → 3f2166f → cb0cffa. Pass 2: cf0bf41 (tail mined) → 9887505 (ownership decisions) → (W1: skills deep verify + agent-turn-loop/sessions-state/gateway scenarios) → (W2: remaining-cap scenarios + delegation 8/8 anchor pass + gateway anchor pass incl. D-01 close) → 6753130 (validator gate + strict green) → this ledger.

## NEXT-PASS instructions (pass 3)
1. Baseline: stay at v0.23.0 @ 2bd378ed until owner re-pins. On re-pin: `scripts/mine_evidence.py` (full corpus) then `scripts/mine_tail.py` (window = > newest PR-ref date); re-verify anchors touched by the diff.
2. Anchor-verify the 64-INFERRED mass (G-06): cli-surface → tools-toolsets → config-provider-models → profiles-isolation → cron-background; then sessions-state (its INFERRED set is mostly Tier-B-only).
3. Ground the remaining 23 debt scenarios only if NEW Tier A/B/C text appears; never derive.
4. Kanban dedicated pass (G-07): cron/AGENTS.md § Kanban + `hermes_cli/kanban*.py` + kanban tail items → expect 5–8 new cron-background reqs.
5. D-03/D-04 are upstream-report candidates — owner approval before any external posting (license firewall + coordinator-owned approvals log).
6. Fleet: waves of 3 children work well, but leaf children DO fabricate at the margin (this pass: invented test-class segment, wrong release tags) — the scripted audit gate (anchor existence, relnote quote overlap ≥60%, test-name grep, tail-sha resolution against the pin) is mandatory between wave completion and conversion.
7. Converter/validator quirks: (a) `draft_to_spec.py ... ""` emits `-<cap>` dirs — strip the leading dash; (b) the validator parses requirements ONLY inside the main `## Requirements` section — put new blocks there, use `## Sub-area:` (converter flattens it), never a new `## ` section after `## Known gaps`; (c) requirement body >500 chars fails strict — push detail into anchors/scenarios; (d) re-register the store after machine moves.
8. Keep `openspec validate --all --strict --store hermes-agent` green at every commit.
