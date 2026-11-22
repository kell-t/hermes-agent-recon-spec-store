# Change: add-repo-cache

## Why
Per-session recon runs re-clone large source repos (`git clone
--filter=blob:none` each time a fresh view is wanted), wasting bandwidth and
wearing SSDs. The first persistent clone was already tolerated in stores as
`<store>/repo` (git-ignored), but the conventions still told agents to clone
anew, and nothing kept an existing clone up to date.

## What Changes
- New `tools/scripts/sync_repo.py`: creates `<store>/.repo` only when
  absent (blobless clone), otherwise fetches and force-checks-out the
  requested ref; adopts a legacy `<store>/repo` once by renaming it; keeps
  the store `.gitignore` covering `.repo/`; strict ref resolution (pin law).
- `tools/scripts/common.py`: `REPO` now resolves `<store>/.repo`.
- RUNBOOK / PLAYBOOK / store-README / tools-README: the cache convention
  (`sync_repo.py`, `.repo`, "refresh, don't re-clone").
- New kit `openspec/` folder tracking these requirements, propagated to
  every store at `recon/openspec/` (capability `kit-spec-propagation`).
- Recovery law for the cache: re-clone only for locally confirmed
  corruption, manually, and only after a shallow-clone access probe
  succeeds; auth/server errors never justify deleting the cache.

## Impact
- Affected specs: `repo-cache` (new), `kit-spec-propagation` (new).
- Affected stores (post-merge, applied by the spec agent per store):
  one-time `mv repo .repo`, re-copy scripts, add `.repo/` to `.gitignore`,
  drop in `recon/openspec/`, record kit version in ledger.
- No change to evidence semantics, gate rules, or validator dialect.
