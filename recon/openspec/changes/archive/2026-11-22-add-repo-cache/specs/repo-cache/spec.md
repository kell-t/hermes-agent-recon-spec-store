## Purpose
Give every spec store a single persistent, git-ignored bare source clone (`.repo`) that all recon tooling shares via named worktrees, refreshed by fetch instead of re-cloned per session, so repeated spec work does no redundant download or SSD wear.

## ADDED Requirements


### Requirement: One persistent git-ignored clone at `.repo`
Each store SHALL keep exactly one ACTIVE source clone — the clone used for
all work on the spec store — at `<store>/.repo`, ignored by the store repo's
git; workflows needing the source at the pin SHALL use that clone and SHALL
NOT create duplicate clones, delete-and-reclone (the recovery and relocation
requirements below are the exception), or check the source out to any path
other than that clone's named worktrees, inside or outside the store.

#### Scenario: Cache created on first use
- **WHEN** `<store>/.repo` does not exist
- **THEN** `tools/scripts/sync_repo.py` creates it as a bare blobless clone
  (`git clone --bare --filter=blob:none`) of the store's source URL
- **AND** the script ensures the store root `.gitignore` ignores `.repo/`
  and `.repo-old/`

#### Scenario: Cache reused, never re-cloned
- **WHEN** `<store>/.repo` already exists for the same source URL
- **THEN** `sync_repo.py` refreshes it with `git fetch` and a forced
  detached update of the requested ref's named worktree
- **AND** no clone and no delete occur

### Requirement: Source checkouts are named worktrees under the cache
The cache is cloned bare and carries no root checkout; every checkout of the
source SHALL be a detached linked worktree at
`<store>/.repo/wt/<branch>`, named after the spec-store branch whose pin it
serves. Worktrees share the cache's single object database: each adds
working files, metadata, and at most its tree's unique lazily-fetched
blobs. When a store branch retires, its worktree SHALL be removed with
`git worktree remove` without touching the cache.

#### Scenario: Worktree per store branch
- **WHEN** `sync_repo.py` runs for store branch `<b>` (default: the store
  repo's current branch)
- **THEN** `<store>/.repo/wt/<b>` exists, detached at the resolved ref
- **AND** no second clone exists

#### Scenario: Worktrees share one object database
- **WHEN** a worktree is added under `.repo/wt/`
- **THEN** no history is re-downloaded (commits and trees are shared, and
  blobs already fetched by any worktree are reused)
- **AND** the object store grows only by the blobs unique to the new tree
- **AND** `git worktree remove` reclaims the checked-out files while
  shared objects remain for the other worktrees

### Requirement: Cache refreshed up to date before recon work
Agents SHALL run the sync step at the start of any work that reads the
source repo, so the cache is current before pin checks, anchor re-opens, or
evidence mining; after fetch, the requested ref (tag/sha/branch) SHALL be
resolved strictly — if it still does not resolve, the tool SHALL fail loudly
and leave the checkout untouched (pin law: never silently fall back to a
different ref).

#### Scenario: Ref present after fetch
- **WHEN** `sync_repo.py --ref <tag|sha|branch>` resolves the ref after fetch
- **THEN** the tool creates or force-updates that branch's worktree
  detached at the commit
- **AND** prints the resolved full SHA for the ledger line

#### Scenario: Ref missing after fetch
- **WHEN** the requested ref cannot be resolved locally or on `origin` after
  fetch
- **THEN** the tool exits non-zero with a message naming the ref
- **AND** changes nothing in the checkout

### Requirement: `.repo` treated as disposable cache
The cache and its worktrees SHALL be treated as read-only views for recon
purposes: the sync step may force-discard local modifications, and nothing
outside the store's tooling SHALL depend on local commits or edits inside
them.

#### Scenario: Dirty worktree recovered
- **WHEN** a previous run left a worktree with local modifications
- **THEN** the sync step resets it to the requested ref (force checkout +
  clean of untracked files) rather than failing

### Requirement: Re-cloning only as recovery with a `.repo-old` undo slot
Deleting and re-creating `<store>/.repo` SHOULD be reserved for manual
recovery of a locally confirmed corrupted clone (`git fsck` failure,
unreadable refs, index damage) or owner-directed relocation (below); when
performed, it SHALL first rename the old cache to `<store>/.repo-old` —
replacing any existing `.repo-old` — and only then clone fresh. Work on
the spec store SHALL ignore `.repo-old`. Authentication or server errors
(401/403, rate limits, 5xx, timeouts) SHALL NOT trigger recovery.

#### Scenario: Transient failure preserves the cache
- **WHEN** a sync fails with an authentication, rate-limit, or server error
- **THEN** the existing `.repo` is left in place untouched — recovery is
  not a response to upstream trouble

#### Scenario: Undo slot precedes re-clone
- **WHEN** recovery runs (`sync_repo.py --rebuild` or the manual
  equivalent) on a confirmed-corrupt cache
- **THEN** `.repo` is renamed to `.repo-old` (replacing any existing
  `.repo-old`) and only then is the fresh bare blobless clone created at
  `.repo`
- **AND** if that clone fails, nothing is lost: `.repo-old` still holds
  the previous cache
- **AND** the next ordinary sync run restores the cache, either by
  cloning again from scratch (a cleanly failed clone leaves no directory
  behind, exactly as on first install) or by completing a
  hard-interrupted partial `.git` with its fetch and forced checkout

#### Scenario: Undo slot rolls
- **WHEN** a recovery runs while `.repo-old` already exists
- **THEN** the previous undo copy is deleted as the new one takes its
  place
- **AND** the slot holds only the most recent previous cache
- **AND** no store work ever reads it

### Requirement: Source identity changes are explicit and owner-directed
The cache's recorded `origin` URL is its source identity: tooling SHALL NOT
rewrite it silently, and `--rebuild` SHALL refuse (exit 3) a URL differing
from the recorded origin unless `--relocate` is deliberately passed with it.
Relocation reuses the `.repo-old` undo mechanics of corruption recovery.
Move detection SHALL be advisory only: it SHALL NOT rewrite `origin`,
trigger recovery, or change the sync result.

#### Scenario: Relocation refused without the deliberate flag
- **WHEN** `--rebuild <url>` runs while `<url>` differs from the recorded
  origin and `--relocate` is absent
- **THEN** the tool exits 3 and touches nothing — a typo can never consume
  a healthy cache

#### Scenario: Relocation is owner-directed
- **WHEN** `sync_repo.py --rebuild --relocate <new-url>` runs on the
  owner's instruction
- **THEN** the current cache moves to `.repo-old` (the slot rolls) before
  the fresh clone from `<new-url>`
- **AND** the agent updates the store's recorded source URL and records a
  ledger line

#### Scenario: Move notice is advisory
- **WHEN** post-fetch move detection (GitHub redirect-table probe, or a
  `This repository moved` notice on fetch stderr) resolves the recorded
  slug to a different canonical repository
- **THEN** the tool prints a `MOVE_NOTICE=<canonical-url>` line for the
  agent to surface to the owner
- **AND** nothing changes: `origin` is not rewritten, recovery is not
  triggered, and the sync result is unaffected

#### Scenario: Probe failure is silent
- **WHEN** move detection cannot run (offline, rate-limited, non-GitHub
  origin)
- **THEN** the sync completes normally with neither notice nor error
