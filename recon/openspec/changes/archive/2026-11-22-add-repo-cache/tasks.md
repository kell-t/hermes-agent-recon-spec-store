# Tasks: add-repo-cache

- [x] `tools/scripts/sync_repo.py` (create/fetch/rename-adopt/ref-resolve/gitignore-ensure)
- [x] `common.py` REPO → `<store>/.repo`
- [x] RUNBOOK §1 step 5 (copy kit `openspec/` → `recon/openspec/`) + Phase 0 step 1/2 (`.repo` via sync_repo.py)
- [x] PLAYBOOK Phase 0 step 1 cache wording
- [x] templates/store-README.md snippet → sync_repo.py
- [x] tools/README.md table row + dependency line
- [x] root README.md tree entries (`openspec/`, sync note)
- [x] `openspec validate --all --strict` green at kit root
- [x] recovery law (owner 2026-11-21, simplified 2026-11-22): re-clone = corruption-only, manual, undo-first (rename `.repo` → `.repo-old`, a rolling one-slot undo that REPLACES any previous `.repo-old`, before the fresh clone; store work ignores `.repo-old`; mid-clone failure self-heals on next sync); auth/server errors never trigger it (spec req 4 + design decision 2 + tool docstring)
- [x] source identity law (owner 2026-11-22): `origin` never rewritten silently; `--rebuild --relocate` = owner-directed source move through the `.repo-old` slot; advisory `MOVE_NOTICE` channel (GitHub redirect-table HEAD probe + fetch-stderr notice scan; `RECON_MOVE_PROBE=0` to disable; probe failure silent) — spec "Source identity changes are explicit and owner-directed" + design decision 11
- [ ] post-merge: ARCHIVE with `openspec archive add-repo-cache --yes` on
  main — this CREATES the living specs under `openspec/specs/` from the
  deltas (their `## Purpose` sections are consumed at creation); commit the
  created specs + archived folder (signed) and push; then a follow-up
  one-line commit sets `PIN: kit main @ <archive-commit-sha>` in
  openspec/project.md (kit-side PIN duty). Deltas are deliberately
  NOT pre-applied on the branch (canonical flow, design decision 8). Kit
  `openspec/` re-copied verbatim to each store's `recon/openspec/` at the
  same kit sync; `openspec validate --all --strict` green before and after
- [ ] post-merge fleet adoption (inventory CONFIRMED 2026-11-21 — not a contingency: all three stores carry a legacy `repo/` clone, ~817 MB total: hermes-agent 721 MB @ pin `3b42157858`, gufo 92 MB, tinytuya 4.1 MB). Per store, IN ORDER: (1) run `sync_repo.py <source-url> --ref <pin>` FIRST — it rename-adopts `repo/` → `.repo` on the spot (NEVER re-clone; adopted caches stay non-bare — the tool attaches the named worktree `.repo/wt/<branch>` the same way; verify HEAD survived the rename and no fresh clone appeared); (2) re-copy kit scripts (new `common.py` resolves `.repo` strictly and reads source files via `common.SRC` = the branch worktree — adoption must precede this step or gates lose the clone; after a passing gate the owner MAY reclaim the vestigial root checkout's disk); (3) confirm `.gitignore` carries `.repo/` (script ensures); (4) copy kit `openspec/` → `recon/openspec/`; (5) ledger line with kit version. Start with tinytuya (smallest; proves the path). — spec agent, per store policy

## Verification tests (owner request 2026-11-22 — no requirements changed)
- [x] `tests/` pytest suite at KIT level (outside any spec store): one test
      per scenario across both change-deltas on this branch, tagged with the
      exact requirement/scenario titles (`tests/specmap.py`); the traceability
      meta tests FAIL in both directions when spec and tests drift.
      24 checks — 11 offline, 13 `@network` (real GitHub origins only: local
      transports cannot serve blobless lazy fetches). `tests/requirements.txt`
      for the venv. Suite supersedes the authoring-time dev battery.

## Post-merge: archive moves scenarios — amend test claims (owner, 2026-11-22)
- [ ] After merge, `openspec archive add-repo-cache --yes` relocates this
      delta; the scenarios' authoritative source becomes
      `openspec/specs/<capability>/spec.md`. IMMEDIATELY amend the test
      claims (the stale-claim meta test fails until this lands, naming
      every file): `tests/test_repo_cache.py`
      `CHANGE = "add-repo-cache"` -> `CHANGE = "spec:repo-cache"`;
      `tests/test_kit_spec_propagation.py` -> `CHANGE =
      "spec:kit-spec-propagation"`. Requirement/scenario titles themselves
      are unchanged by archive, so ONLY the source constants flip. Re-run
      `pytest tests` + strict validate green in the same follow-up commit;
      that commit is also where the kit-side PIN line advances (PIN law).
