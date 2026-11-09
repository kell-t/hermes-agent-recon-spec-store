# RECON_LEDGER — hermes-agent

Store: `github/NousResearch/hermes-agent` (id `hermes-agent`). Boot order: PLAYBOOK.md → repo_config.yaml → this file.

## CURRENT STATE (pass 3 complete, 2026-11-08)

- Baseline pin: `main @ 2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19` (tag **v0.23.0**, 2026-11-05). `recon/baseline.txt`. Unchanged — owner has not re-pinned.
- Validation: `openspec validate --all --strict --store hermes-agent` → **Totals: 10 passed, 0 failed** (openspec 1.16.1), GREEN at every pass-3 commit.
- Fleet: **166 requirements** (pass 2: 158; +9 kanban G-07, −2 dead-at-pin removed → D-05), **156 VERIFIED (94.0%)** (pass 2: 94/59.5%; +64 anchor-verified upgrades), 10 INFERRED, 0 UNVERIFIED-as-spec.
- Scenario debt: **23 → 10** (16 new Tier-B grounded scenarios — verbatim docstring/comment/log-string quotes re-opened by the spec-writer at the pin). Residual: gateway-messaging 3, cron-background 2, tools-toolsets 2, cli-surface 1, sessions-state 1, skills-system 1 (reasons in per-file Known gaps). **234 evidence-backed scenarios.**
- Audit gate (NEW pass 3): `recon/scripts/audit_gate.py` — scripted per-requirement checks: anchor file+line at pin, hint-keyword window (stem + dotted-symbol tolerant), relnote quote overlap ≥60% (release-name version aliases resolved), test path + `::` segment existence, tail-sha `cat-file` resolution, PR/issue cites vs pr_index/bundles/releases/`recon/evidence/verified_numbers.json`, body <500 chars, requirement-section rules. MANDATORY between every wave completion and every commit.
- Store registration: store must be registered on the machine (`openspec store register <store-path>`); registrations do not travel with the git repo.

### Coverage table (scripted tally of specs_draft/, pass 3)

| Capability | Reqs | VERIFIED | INFERRED | Grounded scenarios | Scenario debt |
|---|---|---|---|---|---|
| agent-turn-loop | 17 | 12 | 5 | 29 | 0 |
| gateway-messaging | 17 | 16 | 1 | 28 | 3 |
| sessions-state | 13 | 13 | 0 | 23 | 1 |
| tools-toolsets | 15 | 15 | 0 | 19 | 2 |
| profiles-isolation | 16 | 16 | 0 | 19 | 0 |
| cron-background | 26 | 26 | 0 | 32 | 2 |
| skills-system | 17 | 16 | 1 | 28 | 1 |
| config-provider-models | 14 | 14 | 0 | 18 | 0 |
| cli-surface | 14 | 14 | 0 | 18 | 1 |
| delegation-orchestration | 17 | 14 | 3 | 20 | 0 |
| **TOTAL** | **166** | **156 (94.0%)** | **10** | **234** | **10** |

Pass-3 audit (scripted gate + ~15 spec-writer spot-checks at pin, all child anchors true). Caught and fixed: 2 pass-2 sha transpositions (6b2895cacb86→6b2895cacb85, e20007e4e70c→e20007e4e7c0 — pass-2's own sha audit had missed the rejected-list items); 1 phantom-PR cite (#112647 = ISSUE, pulls/ 404; code comments cite it); 1 closed-unmerged PR cite kept with salvage note (#64611); 5 pass-2 VERIFIEDs with file-only anchors re-anchored file:line by the spec-writer; 2 DEAD pass-2 requirements (D-05); 4 child-cited kanban numbers API-verified (issues #114587 #111306 #115460, PR #99558) and 3 issue-cites relabeled from "PR"; 12 gate false-positives fixed in the gate (range anchors `:A-B`, prose-hint stoplist, dotted `Cls.member` tokens, release-name aliases like v2026.4.3=v0.7.0, prose sections after Known gaps).

## Gap register (pass 3 state)

Closed this pass:
- G-06 **INFERRED mass CLOSED**: 64 → 10 (residual 10 = agent-turn-loop 5, delegation-orchestration 3, gateway-messaging 1, skills-system 1 — non-target residue, unchanged honest statuses). sessions-state's Tier-B-only fear did NOT materialize: all 6 had real implementations at the pin (image replay lives in `agent/image_replay.py` + `agent/turn_context.py:1417`, correcting the draft's guessed location).
- G-07 **Kanban dedicated pass CLOSED**: `recon/evidence/bundle_kanban.txt` (98 PR-window + 23 tail, strict scope=kanban/subject-word; plugin-catalog pins excluded — deferred). 9 NEW cron-background requirements VERIFIED under § Sub-area: Kanban — dispatcher loop + single-writer tick lock (#50331 #41448 #17805); failure_limit breaker + exit-78 sticky first-attempt trip (#114587); board-hard/tenant-soft isolation (#19653); (pid, worker_started_at) liveness fingerprint + hold-not-signal on unverified fingerprint (#99558); notifications via owning-profile adapter, one-WARNING fail-closed (#110919 #115460); scrubbed assignee child env (build_subprocess_env + strip_launch_profile_env); `owned_kanban_task()` ownership gating; path-scoped descendant fence (`kanban_path_is_fenced`, `DELEGATED_CHILD_ENV_MARKER`); owner-recovery refuses-to-guess tail cluster (d4283a9c9cdf post-commit block hook, e62c15e667e4, c777ba429fc8, 89f13590e0e8, b2e0171c29e5; test 25e7f5fc21d8).
- G-08 **Scenario-debt 23 → 10** via 16 new Tier-B scenarios (grounding rule held: only quotes read fresh at the pin during objectives 1–2; nothing derived).
- D-05 **NEW→CLOSED same pass**: two pass-2 requirements were DEAD at the pin — role-based setup toolset grant (#119491; deleted by c3f85bc54f 2026-09-29, setup-profile machinery removed b120ac575d 2026-10-13) rewritten to the surviving session-platform-gated toolsets (`toolsets.py` TOOLSET_SESSION_PLATFORMS, VERIFIED); setup-chat low reasoning effort (#129405, added df150ec10d1e, deleted b120ac575d) removed. **Law: PR-landed evidence must be re-checked for later removal commits at every pin re-verification.**

Open:
- G-02 **UNVERIFIED backlog** (per-file `## Known gaps`, never presented as spec): `/compress` parser contract; chronos managed-cron contract; worktree isolation knob; human-first author credit (→ D-03). Note: the `--now` parse site was FOUND pass 3 (`hermes_cli/skills_hub.py:1646` `invalidate_cache="--now" in args`) and the deferral requirement is now VERIFIED in cli-surface.
- G-08' **Scenario-debt 10**: no Tier A/B/C trigger+outcome text (2 kanban reqs are invariant-only prose; reasons per-file). NOT cut.
- G-09 **plugin×skill and plugin×tool contracts** unassigned (boundary vs deferred plugins-mcp; revisit when that bucket opens).

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
- D-05 pass 3: 2 dead-at-pin requirements found+fixed by the anchor sweep — see Gap register G closed list; the audit-gate law is now in PLAYBOOK-level practice.
- D-04 **OPEN** (pass-2 flags, recorded in per-file Known gaps): `tools/AGENTS.md` § Delegation "default 3" stale vs code `_DEFAULT_MAX_CONCURRENT_CHILDREN = 10` and docs ("Up to 10"); "tasks-only" vs "Shapes: single or batch"; `delegation.backend` (plugin selector) vs `delegation.provider` (credential pin) naming trap; kanban.md calls handoff evidence "a convention" while the hard-refusal requirement rests on #91264 tests that pin goal-loop stops; relnote 2026.3.23 records disabled toolsets historically re-enabling (reduction invariant pinned only at resolution-test level).

## Pass history
| Date | Pass | Pin | Outcome |
|---|---|---|---|
| 2026-11-08 | 1 (solo — fleet delegation blocked in one-shot runs; waves inline) | v0.23.0 @ 2bd378ed | Scope set (10 caps); 130 reqs drafted, converted, strict-valid green; 130 scenario-debt; 47.7% VERIFIED |
| 2026-11-08 | 2 (fleet: 2 waves × 3 children + inline audit gate; owner steering mid-pass) | v0.23.0 @ 2bd378ed | 158 reqs / 59.5% VERIFIED / 23 debt / 213 grounded scenarios; G-01/03(3of4)/04/05 closed; D-01 closed; strict green |
| 2026-11-08 | 3 (fleet: W1 3 + W2 3 + W3 1 children, scripted audit_gate.py between waves; 2 approvals blocked on owner non-response, retried per standing instruction) | v0.23.0 @ 2bd378ed | 166 reqs / 156 VERIFIED (94.0%) / 10 INFERRED / 234 scenarios / 10 debt; G-06/G-07/G-08 closed; D-05 found+fixed; audit_gate.py + verified_numbers.json; D-03/D-04 upstream drafts staged (unposted); strict green at every commit |

Commits — pass 3: aaf6e08 (gate + baseline triage) → afa4123 (W1) → 20764e7 (D-03/D-04 drafts) → 24f9f7b (W2) → 6689081 (W3 kanban + debt sweep) → (ledger + gap lines, this commit).

## NEXT-PASS instructions (pass 4)
1. Baseline: stay at v0.23.0 @ 2bd378ed until owner re-pins. On re-pin: `scripts/mine_evidence.py` (full corpus) then `scripts/mine_tail.py` (window = > newest PR-ref date); re-verify anchors touched by the diff; RE-CHECK removal commits for every PR-cited requirement (D-05 law).
2. Remaining INFERRED 10: agent-turn-loop 5, delegation-orchestration 3, gateway-messaging 1, skills-system 1 — anchor-verify as a small W1; expect most to close (all pass-3 target sets closed).
3. Scenario-debt 10: ground only on fresh Tier A/B/C text; 2 kanban + gateway-messaging 3 are invariant-only — candidates to stay debt permanently; say so in the spec rather than churning.
4. G-09 plugin×skill/plugin×tool contracts: needs the deferred plugins-mcp bucket decision from the owner first.
5. D-03/D-04: drafts staged in `recon/upstream-drafts/` — posting requires owner approval + coordinator approvals log; do not post without both.
6. Fleet: waves of 3 + `scripts/audit_gate.py` between wave completion and commit (mandatory; extend it with new check classes as incidents dictate). Children self-report PR numbers labeled "PR" that are issues — gate's verified_numbers flow works; keep requiring children to hit issues API and label kind.
7. Converter/validator quirks (binding): (a) `draft_to_spec.py ... ""` emits `-<cap>` dirs — merge `./-<cap>/spec.md` into `./<cap>/spec.md` (prefix paths with `./` so leading dashes don't parse as options) and rmdir; (b) requirements ONLY inside the main `## Requirements` region — `## Sub-area:` is fine, new `## ` prose sections after Known gaps are fine but must not contain `### Requirement:`; (c) requirement body >500 chars fails strict; (d) re-register the store after machine moves.
8. Keep `openspec validate --all --strict --store hermes-agent` green at every commit.
