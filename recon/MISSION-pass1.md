MISSION — spec reconstruction pass 1 for NousResearch/hermes-agent

Store: /opt/data/agent-github-spec-store/github/NousResearch/hermes-agent  (OpenSpec store id: hermes-agent, git repo, already scaffolded)
Pinned clone: repo/ at tag v0.23.0 = 2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19 (main, 2026-11-05). recon/baseline.txt written.
Method law: recon/PLAYBOOK.md → recon/DRAFT_TEMPLATE.md → your RECON_LEDGER.md (you create it: no prior ledger = first pass). Read them FIRST, follow them.

## Your deliverables (all inside the store; you are the sole spec writer)
1. recon/repo_config.yaml — the per-repo intel: scope decision (included + deferred buckets with rationale — PLAYBOOK Phase 0/lesson 6: full-project reconstruction is a non-converging treadmill; hermes-agent is large, cap your ambition deliberately), clustering keyword regexes for commit mining, normative doc locations (docs/, AGENTS.md, CHANGELOG if any, GitHub release notes via `curl -s --netrc https://api.github.com/repos/NousResearch/hermes-agent/releases`), fleet knobs.
2. recon/evidence/ — mined evidence: pr_commits.json (git log --no-merges with (#NNNN) refs), release notes, repo_meta.json, per-capability bundles. Prefer git history over API; API budget is 5000/hr SHARED across the whole fleet — spend carefully.
3. specs_draft/<capability>.md — 8-20 requirements each, OpenSpec-flavored per DRAFT_TEMPLATE.md. You may run drafting waves via delegate_task (you are a full Hermes instance). Every requirement: PR/doc citation + status VERIFIED/INFERRED/UNVERIFIED + anchor file:line at the pin. VERIFIED = you opened the file. Blanks over guesses; never invent PR numbers or paths.
4. Conversion + validation: run  python3 /opt/data/agent-github-spec-store/tools/draft_to_spec.py specs_draft openspec/specs ""   (empty prefix — the store folder IS the namespace; capability dirs named after capabilities). Then  openspec validate --all --strict --store hermes-agent  (PATH needs /opt/data/home/.npm-global/bin) must reach 0 errors. Requirements without scenario evidence will get SCENARIO-DEBT derived scenarios from the converter — that is acceptable in pass 1; count and record them.
5. recon/RECON_LEDGER.md — CURRENT STATE, capability coverage table (scripted tallies govern, self-reports are hypotheses), open gap register, pass history incl. the pin.
6. git commit the store at each milestone (scaffold commit exists: 7520356). Commit message per milestone.

## Capability starting points (decide the real scope yourself in Phase 0)
gateway-messaging (platforms incl. telegram/multiplexer), sessions-state, skills-system, tools-toolsets, profiles-isolation, cron-background, delegation-orchestration, config-provider-models, cli-surface, plugins-mcp, desktop-ui... deferred candidates: skins/themes, pets, docs/translations, tests, packaging.

## Rules of engagement
- Work ONLY inside your store path. License firewall: do NOT open or reference the droiddeck store.
- GitHub: read-only PAT via `curl -s --netrc` and plain-https git. Never print the token. NO pushing, no PRs, no writes to GitHub.
- Specs stay private; the repo has no openspec/ folder at the pin.
- Time budget: this is a background run; depth target per PLAYBOOK (154-req scale like the reference pass is the ceiling, not the floor — converging beats exhaustive).
- If you must stop early, commit state and write the RECON_LEDGER with accurate NEXT-PASS instructions (baseline, window, open gaps) so a pass 2 resumes without you.

## Final report format (last message of your run)
Pin + commit shas made; capability table (reqs/VERIFIED/INFERRED/UNVERIFIED per cap); validate summary line; scenario-debt count; top open gaps; wall-clock spent.

## ADDENDUM (owner directive): talk to the user while you build
The user (chat_id 402754873) wants live visibility. You are a headless session, but your bot can message them directly:

  BOT=$(grep '^TELEGRAM_BOT_TOKEN=' /opt/data/profiles/spec/.env | cut -d= -f2)
  curl -s -X POST "https://api.telegram.org/bot$BOT/sendMessage" -d chat_id=402754873 --data-urlencode "text=..."

Rules:
- Send a SHORT update (2-6 lines, no markdown tables) at each of: scope decision made (Phase 0) | evidence mined | each drafting wave completed (name the capabilities) | conversion done + first validate result | validation green | final report (same content as your last message). ~6-10 messages total, no more than one per 5 minutes; batch small events into the next milestone message.
- Every message starts with "spec: " so the user can tell it is you.
- Never include tokens, secrets, or absolute paths the user did not give you; capability names + counts are fine.
- The user may reply to your bot messages — those replies open a DIFFERENT session and will NOT reach you mid-run. Tell them once (in the scope-decision message) to route corrections/questions to the coordinator instead while you run.
- Subagent waves: max 3 concurrent children (server limit).
