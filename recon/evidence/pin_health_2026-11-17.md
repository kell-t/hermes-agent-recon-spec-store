# Pin-health survey — v0.23.1 → v0.23.2 (2026-11-17, priority run)

Trigger (criterion 3): GitHub `releases/latest` = **v0.23.2**, published
2026-11-16T20:59:18Z, non-prerelease, newer than the pin v0.23.1.
Re-pin remains OWNER-GATED — this file is the readiness survey only;
the pin is unchanged (`3b421578588243f920886e6fe79a6faa87ea026e`).

## Tag resolution (per pin law)

- `refs/tags/v0.23.2` → annotated tag object `28f57ed8e3dba4eceb67dfd3e3abda1a7604452d`
  → commit `ae2a81ccc00e9b7c06301523e5bb09608397149c` (`git/tags` object.sha;
  cross-checked in clone `git rev-parse v0.23.2^{commit}` and release
  `target_commitish` — all three agree).
- Window pin..v0.23.2: **8,154 commits**, 5,211 changed files
  (A 2,627 / M 2,525 / R 36 / D 23). Heaviest trees: tests 1561,
  plugin-catalog 1244, contributors 573, hermes_cli 321, apps 245, tools 224,
  gateway 182, agent 158. Release notes stored `recon/evidence/relnote_v0.23.2.txt`.
- Default branch vs pin (criterion 4): main ahead_by 8,168 — subsumed by the release.

## Method

`recon/scripts/pin_health.py` (new, promoted this run): extracts every
backticked `file:line` anchor cite from `specs_draft/` (same ANCHOR_RE
dialect as `audit_requirements.py`, dedup'd), and classifies each against
the clone working tree checked out at the survey target (restored to the
pin afterwards; clone is draft-read-only, no store content depends on its
HEAD). Verdicts: OK / SHIFTED (hint exists elsewhere in file) / OOB /
MOVED (suffix match) / DEAD-FILE / HINT-DEAD (hint token found nowhere
in file). Raw output: `recon/evidence/pin_health_2026-11-17.json`.

## Results — 408 unique anchor cites at v0.23.2

| Verdict | Count |
|---|---|
| OK | 309 |
| SHIFTED | 96 |
| MOVED | 1 |
| HINT-DEAD | 2 (1 triaged FP, 1 real rename) |
| DEAD-FILE / OOB | 0 |

Per-cap: agent-turn-loop 23OK/6S · cli-surface 30OK/4S/1HD · config-provider-models 26OK/11S ·
cron-background 56OK/13S · delegation-orchestration 24OK/11S · gateway-messaging 25OK/16S ·
profiles-isolation 29OK/13S · sessions-state 27OK/7S · skills-system 48OK/4S · tools-toolsets 21OK/11S/1HD/1M.

**0 dead files, 0 out-of-bounds** — mechanically the re-pin is cheap:
96 line-shifts re-anchorable by nearest-hint (JSON carries
`nearest_hint_line` per record). Two FAIL-LIKE records triaged by hand:

1. `hermes_cli/commands.py:211` (cli-surface) — HINT-DEAD is a SURVEY
   TOOL FP. Cite reads `` `hermes_cli/commands.py:211` (example gate
   `display.tool_progress_command`) ``; the hint token exists as part of
   the dotted name `display.tool_progress_command` on line 211 VERBATIM
   at v0.23.2 (`git grep -n tool_progress_command v0.23.2 -- hermes_cli/`
   → `commands.py:211 gateway_config_gate="display.tool_progress_command"`).
   My per-line matcher keeps dotted names atomic, so `tool_progress_command`
   stem-matched nothing, while the real gate (`audit_requirements.py`)
   falls back to whole-file substring and passes. Treat as OK; no action
   at re-pin.
2. `tools/browser_harness_dirs.py:98-117` (tools-toolsets, socket-budget
   requirement) — REAL symbol death with SURVIVING contract.
   `fit_default_socket_dir` deleted by `f5dc3f632b` "fix(browser): every
   profile gets its own browser-harness daemon dirs, not only served
   ones" (2026-11-12; confirmed in-window: ancestor of v0.23.2, NOT of
   pin; −41/+15 across `tools/browser_harness_dirs.py` + `tools/browser_use_cli.py`).
   Replacement chain at v0.23.2: `socket_dir_budget` :45,
   `fits_socket_budget` :55, `socket_fit_runtime_dir` :129,
   `claim_private_dir` :179, `_LINUX_SOCKET_DIR_BUDGET` :25 — the deep-HOME
   sun_path budget behavior survives under renamed symbols.
   Re-pin action: re-anchor to `tools/browser_harness_dirs.py:129`
   (runtime-dir fit) + :45/:55/:179; read the f5dc3f632b per-profile
   daemon-dir change for possible requirement-text growth (multi-profile
   harness dirs), citing `[commit f5dc3f632b…]`.
3. `utils.py:679-684` (`safe_json_loads`, tools-toolsets) — MOVED,
   destination located: root `utils.py` split into the `utils/` package
   by `a1bbd329ea` "refactor: split utils.py into the utils package"
   (in-window); `def safe_json_loads` now at `utils/files.py:661` at
   v0.23.2 (git grep). Re-pin: re-anchor `utils/files.py:661-...`.
   (The survey's suffix-match guess `plugins/platforms/qqbot/utils.py`
   was wrong — real destination found via `git grep "def safe_json_loads"`.)

## Verdict

Re-pin to v0.23.2 is mechanically cheap: 0 dead anchors, ~96 line-shifts,
1 package-split re-anchor, 1 rename with surviving contract + a possible
behavior add (per-profile browser-harness daemon dirs). Behavioral
re-reads at re-pin should start from `relnote_v0.23.2.txt` and the two
triaged windows above, plus the standard new-window removal sweep
(pin..v0.23.2). OWNER ACTION: approve re-pin to v0.23.2 @
`ae2a81ccc00e9b7c06301523e5bb09608397149c`.
