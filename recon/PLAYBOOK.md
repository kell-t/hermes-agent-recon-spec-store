# Spec Reconstruction Playbook — Deconstructing Any Git Repo with Agent Fleets

A reusable, evidence-grounded process for reconstructing a specification (OpenSpec-flavored or any requirement format) from a git repository's code, history, and documentation. Designed for autonomous or semi-autonomous agent fleets. Validated on Droid-Deck/DroidDeck (1,946 commits, 738 PR-landed, ~50 min wall-clock, two waves of 4 drafting agents, 89.6% requirement verification rate).

Core principle: **history is evidence, the current tree is ground truth.** Never replay history to build the spec; reconstruct at a checkpoint, verified against HEAD.

## Document family (three layers)

| File | Mutability | Repo-specific? | Holds |
|---|---|---|---|
| `PLAYBOOK.md` (this file) | stable law, grows only repo-agnostic lessons | No | Method, phases, verification rules, reliability lessons |
| `repo_config.yaml` | amended at scope changes | **Yes** | Repo pin info, scope decision, clustering keyword map, normative-doc locations, fleet knobs, loop cadence |
| `RECON_LEDGER.md` | rewritten every pass | **Yes** | Current baseline, coverage table, open/closed gap register, drift register, pass history |
| `DRAFT_TEMPLATE.md` | stable law | No | The drafting rules each drafting agent must read first |
| `specs_draft/` + `evidence/` | growing artifacts | Yes | Produced drafts and raw mined data |

Boot order for any agent: PLAYBOOK → repo_config → LEDGER. Boundary test for any new fact: "would this help a fleet deconstructing a different repo?" — yes → PLAYBOOK, no → config or ledger. A workspace with no prior LEDGER means first pass: create it from the Phase-0 scope decision.

---

## Phase 0 — Scope and pin

1. Clone (blobless: `git clone --filter=blob:none`) at the default branch. Record and freeze the baseline:
   `BASELINE=$(git rev-parse HEAD)` — store in `evidence/baseline.txt` with date and branch.
2. Survey the repo shape: top-level dirs, language mix (`find … | sed 's/.*\.//' | sort | uniq -c`), docs locations, tags/release history, CONTRIBUTING/AGENTS/README files.
3. Count the history: total commits, merge vs squash ratio, whether commit subjects carry PR refs (`(#NNNN)`).
4. Check API budget (e.g. `curl api.github.com/rate_limit`) before any GitHub-API phase; prefer the clone + `git log` over API calls.
5. **Scope decision (mandatory, explicit):** full-project reconstruction is almost always wrong. Pick the capability surface you actually need. Record the chosen scope and the deferred buckets.

## Phase 1 — Mine evidence (cheap, mechanical)

Sources, in priority order:
1. **PR-landed commits:** `git log --no-merges --format=%H|%ad|%s --date=short`, filter for `(#NNNN)$`. Parse conventional-commit type(scope). Save as JSON: `{sha, date, pr, subject, type, scope}`.
2. **Release notes / changelogs:** per-version files are curated intent statements — the highest-signal evidence in the repo. Extract all.
3. **Topic docs:** design docs, dev notes, architecture docs. Read directory listings first; read fully the ones matching your capability scope.
4. **Issue tracker (optional, when available):** carries intent language code never shows. Sample, don't dump.

Store everything under `evidence/` as JSON/text. This phase is scripted, not LLM work.

## Phase 2 — Cluster by capability

First-pass keyword/heuristic clustering of PR-landed commits into capability buckets (regex keyword sets per bucket; cap each commit at ~2 buckets). Output `evidence/clusters.json`, then `evidence/bundle_<cap>.txt` — a bounded (≤60 items) per-capability PR list with dates and subjects, plus pointers to the release notes and topic docs.

Treat clusters as a **starting partition, not truth**: expect ~50% false-positive rates in some buckets; drafters are expected to reject misfiled items.

## Phase 3 — Draft (LLM fleet, one capability per agent)

Rules, enforced by a shared DRAFT_TEMPLATE that every drafting agent must read first:

- **Evidence-first:** every requirement cites at least one real PR number, commit, or doc file. No citation → the requirement does not exist.
- **Verification tiers, assigned honestly:**
  - `VERIFIED` — the agent OPENED the implementing code at the baseline and saw it. Requires an anchor (`file` or `file:line`).
  - `INFERRED` — grounded in docs/PR text, code not confirmed.
  - `UNVERIFIED` — recorded in the gaps section only, never presented as spec.
- **Blanks over guesses.** Never invent PR numbers, paths, or line numbers. Anchor not found → write "anchor not located".
- **WHAT/WHY, not HOW** — except where implementation IS the contract (protocols, file formats, wire limits).
- **RFC-2119 verbs:** SHALL / SHOULD / MAY.
- **Doc-vs-code disagreement:** record the doc claim as the requirement and log the disagreement in a drift register.
- **Density target:** 8–20 requirements per capability. This is a seed, not a finish line.

Budget rule (dominant cost control): drafters read their bundle + doc pointers first; whole-repo reads only for anchor verification. Bounded bundles in, anchor-only reads out.

Concurrency rule: cap simultaneous drafting agents (e.g. 4 per node) and run waves, not swarms. Each agent's context is its own; the shared resource is inference throughput and prompt-cache residency.

## Phase 4 — Verify and tally (scripted, adversarial to self-reports)

Never trust drafting agents' self-reported counts. Programmatically:
- Count requirement headers and status grades per file; reconcile against reports; investigate discrepancies.
- Spot-check anchors: do cited files exist at baseline? Do cited line numbers still contain what's claimed?
- Verify PR-number attribution independently: `git log --grep "(#NNNN)"` matching by **message text and diff**, not the number alone. (Validated failure mode: trusted PR numbers with no matching record in the extracted evidence.)

## Phase 5 — Gap register (a first-class deliverable)

Every pass ships an explicit gap register alongside requirements:
- Behaviors seen in evidence but not groundable at HEAD.
- Constants claimed by docs but not found in code.
- Undocumented contracts (teardown ordering, fallback semantics, gating conditions).
- Deferred scope decisions and ownership ambiguities between capabilities (e.g. "HUD-boundary PRs excluded — hud capability should own them").
- Stale/rebased evidence: bundle recency holes (bundles cut from a window miss the newest commits — re-extract rather than reuse).

Rule: "unknown" must never silently become "absent", and never become "assumed".

## Phase 6 — Output package

Ship as a self-contained handoff:
1. `GROUNDWORK.md` — baseline pin (SHA, branch, date), method summary, workspace inventory, cross-cutting findings (evidence reliability, doc/code drift register), consolidated gap register, operating rules, suggested next passes.
2. `specs_draft/<capability>.md` — one file per capability, template-shaped.
3. `evidence/` — raw mined data (commit JSON, clusters, bundles, release notes, baseline SHA) so the next fleet can re-derive everything without re-mining.
4. `DRAFT_TEMPLATE.md` — the drafting law, reusable verbatim by future fleets.
5. Checksums; exclude the clone itself from archives (recipients clone their own).
6. State explicitly whether the package contains sensitive data (it should not).

## Recurring maintenance loop (after the initial pass)

```
re-pin baseline → diff vs previous baseline → extract new PR-landed commits
→ draft deltas for touched capabilities → verify anchors at NEW baseline
→ archive deltas into the living spec (only when code matches)
```

Archive precondition, always both: (a) upstream code at the fresh baseline matches the delta, and (b) anchor verification passed at that baseline. A stale-baseline archive poisons the source of truth.

## Reliability lessons encoded (worth their weight)

1. **PR numbers are hypotheses.** Squash/rebase history produces duplicate and misattributed refs. Match by text and diff.
2. **Docs drift; code rots docs quietly.** Keep a drift register every pass; doc staleness is itself a reportable finding upstream.
3. **Bundle windows have tails.** Anything cut from "recent history" misses the last few days. Re-extract for fresh windows.
4. **Self-reports are hypotheses.** All fleet metrics get scripted counting before publication.
5. **Reverse-engineering captures behavior, not intent.** Where code and docs/issues disagree, the *intent* belongs in the spec and the disagreement gets a drift entry.
6. **Full-project reconstruction is a treadmill; selective, checkpointed reconstruction converges.** Deep where you work, absent elsewhere.
7. **Gaps are deliverables** — a precise unknown is worth more than a confident guess.
8. **Reproducibility survives engine swaps.** With temperature-0 serving guarantees, verification artifacts remain valid across inference-engine changes: re-run verification, not authorship.
9. **Evidence-graded specs drift from spec-tool formats; conversion passes are the bridge.** Reconstruction drafts naturally produce verified invariants (SHALL + anchor), while spec tools like OpenSpec require scenario blocks (WHEN/THEN/AND) per requirement. Don't fabricate scenarios during reconstruction — code evidence shows a behavior exists but rarely documents its trigger contract. Instead run a separate, strictly-grounded scenario-ification pass: add a Scenario only when BOTH trigger and outcome appear in human-written sources (release notes, in-repo docs); leave requirements that lack documented triggers as property-style invariants with an explicit note. Non-normative docs (working logs) may supply substance quotes but should be flagged as such.

## License / legality note

Specs derived from a repo's docs/code inherit that repo's encumbrances. Check the license before publishing a reconstruction; note any clean-room obligations the project itself observes (e.g. license-blocked borrowed code).
