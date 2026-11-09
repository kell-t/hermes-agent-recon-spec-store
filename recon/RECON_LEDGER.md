# RECON_LEDGER — hermes-agent

Store: `github/NousResearch/hermes-agent` (id `hermes-agent`). Boot order: PLAYBOOK.md → repo_config.yaml → this file.

## CURRENT STATE (pass 1 complete, 2026-11-08)

- Baseline pin: `main @ 2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19` (tag **v0.23.0**, 2026-11-05). `recon/baseline.txt`.
- Validation: `openspec validate --all --strict --store hermes-agent` → **Totals: 10 passed, 0 failed** (openspec 1.16.1).
- Scenario debt: **130 SCENARIO-DEBT derived scenarios** (every requirement; no evidence-backed scenarios were fabricated — PLAYBOOK lesson 9). Pass-2/3 scenario pass replaces them where release notes / docs give trigger+outcome.
- Scenario-debt note: converter emits `#### Scenario: Conformance check (derived)` blocks marked `SCENARIO-DEBT (derived, pass-4 conformance)`.
- Store registration: store must be registered on the machine (`openspec store register <store-path>`); registrations do not travel with the git repo.

### Coverage table (scripted tally, tally of specs_draft/ + converted openspec/specs/)

| Capability | Reqs | VERIFIED | INFERRED | UNVERIFIED | Scenario debt |
|---|---|---|---|---|---|
| agent-turn-loop | 14 | 10 | 4 | 0 | 14 |
| gateway-messaging | 14 | 7 | 7 | 0 | 14 |
| sessions-state | 13 | 7 | 6 | 0 | 13 |
| tools-toolsets | 12 | 6 | 6 | 0 | 12 |
| profiles-isolation | 13 | 6 | 7 | 0 | 13 |
| cron-background | 14 | 7 | 7 | 0 | 14 |
| skills-system | 13 | 3 | 10 | 0 | 13 |
| config-provider-models | 12 | 6 | 6 | 0 | 12 |
| cli-surface | 11 | 4 | 7 | 0 | 11 |
| delegation-orchestration | 14 | 6 | 8 | 0 | 14 |
| **TOTAL** | **130** | **62 (47.7%)** | **68 (52.3%)** | **0** | **130** |

Audit performed (scripted, pass-4 grade): all `file:line` anchors exist at the pin and line numbers are within file length; every `pull/NNNN` citation matches the mined `pr_commits.json`/bundle/release-note evidence (0 off-evidence cites). Status counts reconcile with headers exactly.

### Evidence inventory (`recon/evidence/`)
- `pr_commits.json` — 5,893 PR-landed commits (of 58,953 no-merge, 62,624 total), window 2026-02-26..2026-10-27; `pr_index.json` (5,601 unique PRs).
- `releases.json` — 47 GitHub releases (all with bodies; 44 stable `vX.Y.Z` tags).
- `clusters.json` + `bundle_*.txt` ×10 — keyword clusters (≤2 buckets/commit), bundles capped 60.
- `repo_meta.json`; API budget spend this pass ≈6 of 5000/hr shared (check `rate_limit` remaining before use).

## Open gap register (pass 1 carry-over)

Cross-cutting:
- G-01 **PR-ref tail hole**: `(#NNNN)` convention ends 2026-10-27; pin is 2026-11-05. Pass 2 must mine the tail with `git log` WITHOUT the ref filter (~9 days, subjects without refs) — PLAYBOOK lesson 3.
- G-02 **UNVERIFIED backlog**: see per-file `## Known gaps` — items recorded there are never presented as spec. Notable: `/compress` parser contract, `--now` deferral implementation site, kanban dispatcher, chronos managed-cron contract, worktree isolation knob, gateway 85%-hygiene threshold constant.
- G-03 **Ownership boundaries undecided** (assign in pass 2): kanban (cron vs plugins-mcp), compression display (sessions-state vs agent-turn-loop), fleet reconciliation (`fleet` keyword false-positive — belongs to deferred update-packaging), plugin×skill and plugin×tool contracts.
- G-04 **Cluster regex noise**: `cli-surface` and `tools-toolsets` bundles carried desktop/telegram false-positives (`\bcli\b`, `\btools?\b` over-match); drafters rejected them, but tighten regexes in repo_config before pass 2.
- G-05 Verification-rate skew by capability: skills-system 23% VERIFIED vs agent-turn-loop 71% — AGENTS.md density differs; pass 2 should anchor-verify skills-system's INFERRED set (authoring-standards test file, curator code).

Deferred buckets (not reconstructed — deliberate): desktop-ui (7,059 scope commits), tui-web, plugins-mcp (2,371), update-packaging (1,063+), memory-system, skins/pets/locales/tests/website/evals.

## Drift register
- D-01 agent/AGENTS.md claims gateway session hygiene at 85%; the constant was not found under `gateway/session*.py` at the pin (doc-vs-code; doc claim kept as requirement per DRAFT_TEMPLATE rule 6).
- D-02 `provider-runtime.md` lists resolver files as primary implementation — matched the tree; no drift found on that page.

## Pass history
| Date | Pass | Pin | Outcome |
|---|---|---|---|
| 2026-11-08 | 1 (solo — fleet delegation blocked: `delegation.oneshot_max_children=0` in one-shot runs; run waves inline) | v0.23.0 @ 2bd378ed | Scope set (10 caps); 130 reqs drafted, converted, strict-valid green; 130 scenario-debt |

Commits: e785176 scaffold → a77b2e9 phase 0/1 → ee3db62 drafts 1-3 → e9a612c drafts 4-7 → 3f2166f drafts 8-10 + conversion (validation green).

## NEXT-PASS instructions (pass 2)
1. Baseline: stay at v0.23.0 @ 2bd378ed until owner re-pins; re-run `python3 /opt/data/profiles/spec/cache/.../tally.py` equivalents from the store (scripts live in the profile scratch — **promote `tally.py`/`mine_evidence.py`/`cluster.py` into `recon/scripts/`** on next commit so they survive).
2. Mine the G-01 tail (no-`(#NNNN)` git log 2026-10-27..pin) into `evidence/tail_commits.json`; merge into relevant bundles; draft deltas for touched caps.
3. Scenario pass: for each capability, add evidence-backed `#### Scenario:` blocks (trigger+outcome from release notes / AGENTS.md / website/docs) ahead of derived ones; converter keeps both — delete the derived block only when a grounded one exists; re-tally debt.
4. Anchor-verify the INFERRED set, priorities: skills-system (G-05), delegation-orchestration, gateway streaming invariants 2/4, `--now` site, 85% hygiene constant.
5. Resolve G-03 ownership decisions in repo_config.yaml (scope section), then move cross-boundary requirements accordingly.
6. Fleet: this store was drafted solo because one-shot delegation budget is 0 — if pass 2 runs interactively (non-one-shot), waves of 3 drafting children per PLAYBOOK Phase 3 are available; give each child the failed-delegation brief pattern in `specs_draft` git history.
7. Converter quirk: `draft_to_spec.py ... ""` emits dirs named `-<cap>`; strip the leading dash (`mv ./-<cap> ./<cap>`) before validating, and re-register the store after machine moves.
8. Keep `openspec validate --all --strict --store hermes-agent` green at every commit.
