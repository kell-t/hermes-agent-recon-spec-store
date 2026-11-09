# hermes-agent-recon-spec-store

A **reconnaissance spec store** for [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — a reverse-engineered behavioral model maintained by an autonomous spec agent, built *from* the source at a pinned commit, never merged upstream.

## What this is

An [OpenSpec](https://openspec.dev/) store describing what hermes-agent **does**, capability by capability (agent turn loop, gateway messaging, delegation/orchestration, profiles, sessions/state, skills, tools/toolsets, config/providers, CLI surface, cron/background). Every requirement carries a provenance status:

- `VERIFIED` — an anchor (`file:line` at the pinned commit) or a release-note/PR citation, re-checked at the pin by a scripted audit gate.
- `INFERRED` — supported by evidence not yet anchor-checked; treat as a hypothesis.

The authoritative snapshot (counts, pin, coverage, open gaps, next pass) lives in [`recon/RECON_LEDGER.md`](recon/RECON_LEDGER.md) — everything else in this README is by-design approximate.

## How it is derived

The spec agent clones the upstream repo **blobless at the pinned commit** (kept out of git on purpose — see `.gitignore`), mines releases, PRs, issues and source, drafts requirements with `file:line` evidence, and runs `recon/scripts/audit_gate.py` + `openspec validate --all --strict` before every commit. Nothing is asserted without a citation, and citations are mechanically re-checked against the pin.

Upstream hermes-agent is MIT-licensed; this store is derivative documentation of it, attributed above and per-spec in `recon/`.

## Branches

One branch per upstream **full release** (non-pre), named exactly after the tag — e.g. `v0.23.0` (pin `2bd378e`). `main` is the working trunk. New release branches are based off whichever of {previous release branch, last main-dev pin} yields the smaller reconciliation delta, then walked forward or back to the new release (policy details in the fleet workflow doc).

## How to use

```bash
# validate (needs: npm i -g @fission-ai/openspec)
openspec store register .
openspec validate --all --strict --no-interactive

# get the pinned source alongside, the way the agent does:
git clone --filter=blobless --branch v0.23.0 https://github.com/NousResearch/hermes-agent repo
```

Read order: `recon/RECON_LEDGER.md` (state + gaps) → `openspec/specs/<capability>/spec.md` (requirements) → `recon/evidence/` (citation bundles).

**Status snapshot (rot-prone; the ledger wins):** 166 requirements, 156 VERIFIED (94.0%), 234 evidence-grounded scenarios, at pin v0.23.0.
