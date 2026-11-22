# Design: add-repo-cache

## Decisions

1. **Name `.repo`, one clone per store, git-ignored.** A dot-dir keeps the
   cache visually out of the way at store root and signals machine-owned.
   The cache is **bare** (decision 9): it holds no root checkout — all
   working views are named worktrees under it. One clone per store (not a
   cluster-wide shared cache) keeps store repos self-contained and license
   tiering simple: each store's clone is of its own source repo, and per the
   kit's license firewall nothing shared across stores crosses repo
   boundaries implicitly.
2. **Fetch, don't re-clone.** The clone is a cache: `sync_repo.py` clones
   only when absent, otherwise `git fetch --prune --tags` + forced detached
   update of the named worktree + `git clean -fd`. Re-cloning is a recovery
   action for a **corrupted cache only** (`git fsck` failure, unreadable
   refs, index damage), never for authentication or server errors — a
   403/401, rate limit, or 5xx says nothing about the local clone.
   Requirement strength follows that split (owner ruling, 2026-11-21): the
   *policy* is soft (re-cloning **SHOULD** be reserved for recovery), the
   *mechanics* are hard (undo-copy-before-clone, auth-never-triggers:
   **SHALL**).
   Recovery keeps ONE **rolling undo slot** (owner simplification,
   2026-11-22; an earlier design date-stamped forensic quarantines and
   kept them until owner-authorized deletion — withdrawn because the
   cache holds a **public** repo whose preservation is not the store's
   job): rename `.repo` → `.repo-old`, **replacing** any existing
   `.repo-old`, THEN clone fresh into `.repo`. The rename-first ordering
   keeps the destructive step minimal — the only deletion is the
   *previous* undo copy, never the active cache; a crash between replace
   and rename loses at worst the older undo. If the fresh clone fails
   mid-recovery, `.repo-old` still holds the old copy, and the next run
   of `sync_repo.py` restores the cache — verified empirically on
   2026-11-21 with SIGKILL mid-clone: a *cleanly* failed clone leaves no
   directory (git cleans up; next run clones as on first install), and a
   **hard-killed partial `.git`** (objects present, HEAD unborn) is healed
   by the next run's fetch + forced checkout (recovered to a healthy HEAD,
   rc=0). An earlier draft required a shallow-clone access probe; it was
   superseded — the ordering itself makes the probe redundant (nothing is
   consumed or destroyed before access is proven by the clone's own
   success). A staging-dir + swap design was also considered and rejected
   as more moving parts for the same guarantee. Worktree git links stay
   git-native (absolute): after a slot rename the stashed worktrees read
   broken, but the undo path is `mv .repo-old .repo` + ordinary sync, so
   inspectability was judged not worth hand-editing git pointer files
   (decision 10). A wrong-URL `--rebuild` is refused (exit 3) BEFORE the
   slot is touched — recovery may never consume a healthy cache on a
   parameter mistake — and `--rebuild` stashes husk directories (no git
   metadata) that would otherwise block the fresh clone. `.repo-old` is
   gitignored and ignored by all store work (spec scenario "Undo slot
   rolls").
3. **Strict ref resolution (pin law).** After fetch the requested
   tag/sha/branch must resolve (local, then `origin/<ref>`, then
   `refs/tags/<ref>`); otherwise exit non-zero leaving the checkout
   untouched. Silent fallback to another ref would poison pin-anchored
   evidence.
4. **Remote-mismatch guard.** If an existing `.repo`'s `origin` URL differs
   from the requested source URL, the tool refuses (exit 3) rather than
   re-pointing someone's cache — likely a typo or a store mix-up.
5. **Legacy adoption over dual paths.** `common.py` resolves strictly
   `.repo`; the one-time migration is `sync_repo.py` renaming `<store>/repo`
   when `.repo` is absent (same filesystem, instant). No fallback read path:
   two accepted locations would fork conventions across stores. Adopted
   legacy clones stay non-bare; named worktrees attach to them the same way
   (the tool detects bare vs non-bare), and their old root checkout becomes
   vestigial — the owner may reclaim that disk after a passing gate.
6. **Kit openspec copy is read-only in stores.** Requirements change only
   via kit PR; the store copy is re-copied verbatim on kit sync. This keeps
   a single source of truth and an audit-diffable invariant (empty diff
   against the kit tree at the recorded version).
7. **Blobless clone stays the default** (`--filter=blob:none`): history
   mining needs commit/tree metadata, old blobs rarely; it also minimizes
   the SSD footprint this change is protecting.
8. **Canonical change→archive flow (owner-confirmed 2026-11-21).** Living
   specs are NOT pre-applied on the change branch: `changes/` holds the
   delta, and `openspec archive` (post-merge, per team-workflow doctrine —
   "specs/ moves forward only with work that actually shipped") creates or
   updates `openspec/specs/`. A `## Purpose` section in the delta is read
   when the capability is created; without it archive writes a `TBD`
   placeholder that fails strict. Verified chain: change-only strict 1/1 →
   archive → specs created with real Purpose → strict 2/2.
9. **Bare cache + named worktrees (owner ruling, 2026-11-22; measured on
   hermes-agent, which supersedes this decision's first-draft kit-only
   estimate).** Baseline bare blobless clone = 198 MB (objects 184 MB);
   then `main` + the last five releases as worktrees, in order:

   | # | ref | working files | obj-DB step | total step | total vs bare |
   |---|-----|---------------|-------------|------------|---------------|
   | 1 | main | 319 MiB | +106 MiB | +428 MiB | 316% |
   | 2 | v2026.9.7 | 183 MiB | +39 MiB | +223 MiB | 429% |
   | 3 | v2026.9.11 | 189 MiB | +12 MiB | +202 MiB | 531% |
   | 4 | v2026.9.14 | 192 MiB | +14 MiB | +207 MiB | 636% |
   | 5 | v2026.9.21 | 208 MiB | +23 MiB | +233 MiB | 754% |
   | 6 | v2026.9.24 | 210 MiB | +20 MiB | +231 MiB | 870% |

   Mechanism: a blobless clone lazily fetches each tree's blobs at first
   checkout (every pack here carries a `.promisor` marker), so the object
   store DOES grow per new worktree — but only by that tree's **unique**
   blobs: after the first checkout the step falls to a ~12–39 MiB flat
   band between adjacent releases (deduplicated across worktrees;
   saturating, not monotonically shrinking). The first-draft claim "zero
   new pack objects" was wrong for blobless clones and is retracted —
   it held only where blobs were already local. Working files are linear
   and intrinsic (~190–210 MiB per release tree): N concurrent worktrees
   cost N checkout file trees, so TOTAL footprint is ~linear with a slope
   far below N clones — 6 refs shared 398 MB of objects where six clones
   would carry ~1.1 GB. That is why the requirement mandates removing a
   worktree when its store branch retires: total footprint stays bounded
   by the number of CONCURRENT active branches — normally one.
   Sequential-checkout comparison (same host/day, ONE non-bare blobless
   clone moved main → five releases → back to main): the object DB
   followed the SAME curve (291→398 MiB — the lazy-blob union is a
   property of the refs visited, not of the worktree model), while
   working files stayed at ONE tree, so the total held flat at
   514–720 MiB regardless of refs visited, and returning to main after a
   full pass added ZERO bytes (every blob already cached). Worktrees pay
   N × file trees for CONCURRENT views (1724 MiB with six refs live).
   Conclusion: a single-active-branch store has the SAME footprint as
   sequential checkout; the worktree premium is purely concurrency —
   ~+1 file tree per extra branch kept open, bounded by the mandated
   retire-prune.
   Checkouts live only at `<store>/.repo/wt/<branch>`, named after the
   spec-store branch each serves (`--wt` overrides; default is the store
   repo's current branch). `.repo/worktrees/` is git's own admin
   namespace — putting checkouts there collides with it, so they live in
   `.repo/wt/` instead. Consumers read source files through
   `common.SRC` (the current branch's worktree), never through the bare
   cache root.
10. **Relative worktree git links — experimented, REJECTED (2026-11-22).**
    A hybrid form (worktree-side `.git` file rewritten cache-relative,
    admin-side `worktrees/<name>/gitdir` left absolute) was implemented
    and verified on git 2.47.3 — it let a renamed cache keep usable
    worktrees — but was WITHDRAWN the same day on owner review:
    hand-editing git pointer files is an extra failure surface for no
    job the store owns (the cache holds a public repo; recoverability is
    `mv .repo-old .repo` + ordinary sync, not live inspection of a sick
    cache). Two hard findings are kept as evidence in case the idea
    resurfaces: making BOTH sides relative is dangerous — git resolves
    the admin-side file literally, judges a LIVE worktree "prunable",
    and `git worktree prune` then deletes its admin entry, orphaning the
    checkout; and git 2.47.3 offers no supported creation-time relative
    mode — there is no `--relative-paths` flag, and
    `worktree.useRelativePaths` is NOT a real key (git accepts any
    dotted config silently but the binary contains no such code path —
    pointers stayed absolute with it set; never set it globally).

11. **Source identity and move notices (owner ruling, 2026-11-22).**
    The recorded `origin` URL is treated as source identity: never
    rewritten silently; a `--rebuild` URL that differs from it refuses
    (exit 3) unless `--relocate` is deliberately passed alongside — the
    F1 guarantee (a typo can never consume a healthy cache) survives
    because skipping the guard is itself an explicit, rare act. Measured
    justification for a dedicated channel: after a repo move GitHub
    answers git traffic on the OLD slug with 200 + correct content and
    zero signaling (packet-traced), so no passive detection exists on
    the transport; the `This repository moved` stderr notice is
    historical (push-era reports; absent from current read paths) and is
    kept only as a free regex on already-captured stderr. The live
    signal is GitHub's redirect table itself (web HEAD / REST 301 ->
    canonical location), probed once per sync. The notice channel is
    advisory BY CONSTRUCTION: print `MOVE_NOTICE=<url>`, probe failures
    silent, exit codes untouched — provenance decisions belong to the
    owner (`--relocate`), never to inference. Slug-RECLAIM after a move
    is not this channel's job (alias gone, same slug answers 200): the
    strict pin law catches it (tag resolves to a different SHA -> exit
    2, checkout untouched).

## Notes (not requirements)
- Scope note (owner, 2026-11-21): the kit's openspec folder intentionally
  tracks ONLY this change's requirements for now. Formally specifying the
  rest of the kit's behavior (evidence models, gate dialect, license
  tiering) is deferred; those remain governed by RUNBOOK/PLAYBOOK/references
  prose. No requirement is written to enforce that deferral.
- A cluster-wide shared source cache (multiple stores or agents sharing one
  clone via `git worktree`) was considered and deferred: concurrency
  coordination is the hard part, and per-store clones already remove the
  repeated-clone wear this change targets. (Within ONE store, worktrees are
  now the standard working view — decision 9; the deferred idea is sharing
  ACROSS stores/agents.)
- `--dest` and `--wt` are tool-development/testing conveniences; store work
  always uses the defaults (`<store>/.repo`, current branch).

## Migration (per existing store)
`python3 recon/scripts/sync_repo.py <source-url> --ref <pin>` once → renames
legacy `repo/`, refreshes, creates this branch's worktree, prints the pin
SHA; then re-copy kit scripts, ensure `.gitignore` has `.repo/` and
`.repo-old/`, copy kit `openspec/` → `recon/openspec/`, ledger line with kit
version.
