# Scenario-debt fresh-text resweep — pass 7 (2026-11-18, priority-run)

Pin: v0.23.1 @ 3b421578588243f920886e6fe79a6faa87ea026e. Question: do the 10
scenario-debt requirements (ledger coverage table, pass 4) gain grounding from
text newer than the pass-3/4 survey — the v0.23.0..v0.23.1 window (2,578
non-merge commits) and the pass-5 corpus re-mine?

## Corpus scanned
- Tier A: `releases.json` v0.23.1 body (the only relnote newer than the
  survey; 2,734 chars). Content: plugin-catalog 2 MiB→16 MiB cap fix (#151860)
  + rollup preamble; explicitly defers curated notes to v0.24.0. No hits on any
  of the 10 debt topics.
- Tier C: all test files added/modified in `git log v0.23.0..v0.23.1`
  (759 files, /tmp list rebuilt via `--diff-filter=AM --name-only -- tests/`),
  grepped per debt topic (coerce/repair, session platform, first-run/onboarding,
  busy/gone/503, provenance/mount).
- Tier B: docs cited by each debt requirement re-opened at the pin.

## Verdicts per requirement (10)
| REQ | Verdict | Evidence |
|---|---|---|
| gateway "Turns reload ... .env" | **CLOSED, 3 scenarios grounded** | tests/gateway/test_session_config_loaders.py::test_a_local_turn_reloads_the_profiles_env_file_and_keeps_its_own_turn_budget (bypass-parametrized ids=['profile','ignore_user_config'], pins reload + bypass exclusion + budget-kept); tests/gateway/test_session_resume_config_refresh.py::test_a_resume_expands_var_references_from_the_profiles_current_env |
| tools "Session-platform-gated toolsets" | **CLOSED, 1 scenario grounded** | tests/tools/test_connectors_catalog.py::test_only_a_desktop_session_carries_the_tool (drops named for cli/tui/telegram/cron/None, kept for desktop). Test predates the survey but the REQ only became this contract at the pass-3 drift rewrite, which was never re-swept for scenarios. |
| tools "Shared argument repair for inline tools" | **CLOSED, 1 scenario grounded** | tests/tools/test_todo_tool_type_coercion.py::TestJsonStringCoercion::test_json_string_is_parsed_into_list dispatches through INLINE_TOOL_EXECUTORS (wrapper `_coerced` → `coerce_tool_args` live at pin). Wording kept to what the test pins. |
| gateway "Multi-tenant gateway isolation" | stays debt | no window test/doc names the isolation trigger+outcome; invariant per ledger |
| gateway "Side tasks resolve the profile's config with built-in defaults" | stays debt | no Tier A/B/C pair in window |
| sessions-state "Busy-vs-gone error taxonomy" | stays debt | no window test asserts the 503-vs-500 mapping; hermes_state_errors.py:30/:67 comments remain the only source (verified live at pin) |
| cli-surface "First-run surfaces reach their own setup" | stays debt | new window tests (test_onboarding_fresh_launch.py et al.) pin onboarding RESTART (unfinished run starts over), not the blank-install→setup-panel contract; no ui-tui vitest for setupRequired/setup.status routing |
| skills-system "External skill mounts carry a provenance tier" | stays debt | no window test/doc adds a user-observable trigger→outcome for a mount |
| cron-background "Board is the hard isolation boundary" | stays debt (permanent, per NEXT-PASS 3) | invariant-only |
| cron-background "Owner recovery refuses to guess" | stays debt (permanent, per NEXT-PASS 3) | invariant-only |

## Drift findings (own findings, verified at pin before correcting)
- **D-08a (statement drift, corrected)**: gateway-messaging REQ "Turns reload
  the routed profile's current .env" claimed reload "on every execution path —
  ... and bypass sessions alike". At the pin, `gateway/run_turn_runner.py:1305-1309`
  gates the reload on `if not policy.ignore_user_config:` with comment
  "A bypass session never reads the profile." (:1307), and the requirement's
  own cited commit 6e7567be260b says the bypass turn NEVER reloads. Statement
  rewritten to exclude bypass sessions; old wording preserved append-only in
  the requirement's Evidence line; pass-2b Known-gaps flag annotated FIXED.
- **D-08b (mechanical anchor relocations, annotated in place)**:
  run_turn_runner.py:1275-1279→:1305-1309; run.py:1580-1586→:1574-1584;
  agent/inline_tool_executors.py:307-315→:346-355 (old lines = raw dict
  region); import cite :17→:18; model_tools.py:902→:897/:914.
  (`tools/arg_coercion.py:21` still true; sessions-state `hermes_state_errors.py`
  :30/:67 cites re-verified true; tools-toolsets `toolsets.py:143/:244/:449`
  anchors re-verified via gate.)

## Fleet delta
166 reqs / 165 VERIFIED unchanged; grounded scenarios 234 → 239; scenario debt
10 → 7 (gateway-messaging 3→2, tools-toolsets 2→0). Gate GREEN; strict
validate 10/10.
