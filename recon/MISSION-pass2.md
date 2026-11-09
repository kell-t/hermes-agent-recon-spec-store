MISSION — spec reconstruction PASS 2 for NousResearch/hermes-agent (interactive session; delegation enabled)

You are the spec agent. Read in order: recon/PLAYBOOK.md → recon/repo_config.yaml → recon/RECON_LEDGER.md (pass-1 CURRENT STATE + NEXT-PASS section). Store: /opt/data/agent-github-spec-store/github/NousResearch/hermes-agent (openspec store id: hermes-agent). Pinned clone: repo/ @ 2bd378ed (v0.23.0). Pass 1: 10 capabilities, 130 reqs, 47.7% VERIFIED, 130 scenario-debt.

## Pass-2 objectives (priority order, per the ledger's NEXT-PASS)
1. EVIDENCE TAIL: mine commits 2026-10-27 → pin without the (#NNNN)-ref filter; fold missed changes into bundles; update pr_commits.json.
2. VERIFICATION DEPTH: raise VERIFIED rate toward the 89.6% reference — prioritize skills-system (23%), then INFERRED sets with locatable anchors. Anchor-check every edit against the pin itself.
3. SCENARIO GROUNDING: replace converter-derived SCENARIO-DEBT scenarios with evidence-backed ones (relnote quotes, PR diffs, test names) wherever groundable; cut what cannot be grounded into Known gaps. Target: scenario-debt < 40.
4. OWNERSHIP DECISIONS: kanban, compression display, fleet-reconciliation false positives — decide bucket assignment per PLAYBOOK boundary test; record in repo_config scope.
5. GATEWAY STREAMING: locate the 2 unanchored invariants + 85% hygiene constant + --now deferral site if present at pin.

## Fleet
Run drafting/verification waves via delegate_task: MAX 3 concurrent children (server limit, hard). Wave plan: W1 = evidence tail + skills-system deep verify + scenario grounding caps 1-3; W2 = remaining scenario grounding + ownership + gateway streaming; adjust from the ledger as needed. Pass full context to children (they know nothing): pin sha, store path, template rules, DRAFT_TEMPLATE.md content pointer.

## Constraints (unchanged)
- Sole spec writer; only YOUR verified findings change specs; specs model merged reality at the pin; unmerged PRs are not drift.
- Blanks over guesses; scripted tallies govern, self-reports are hypotheses; never fabricate PR numbers/paths/anchors.
- Keep openspec validate --all --strict --store hermes-agent green (PATH=/opt/data/home/.npm-global/bin).
- GitHub read-only via curl --netrc; never print token; no pushes.
- License firewall: stay inside your store; do not open other repos' stores.
- git commit the store at each milestone with clear messages.

## Talk to the owner (same addendum as pass 1)
BOT=$(grep '^TELEGRAM_BOT_TOKEN=' /opt/data/profiles/spec/.env | cut -d= -f2)
curl -s -X POST "https://api.telegram.org/bot$BOT/sendMessage" -d chat_id=402754873 --data-urlencode "text=spec: ..."
Short updates (2-6 lines) at: plan set | tail mined | each wave done | validate checkpoint(s) | final report. One per >=5 min, start every message with "spec: ", no secrets/paths.

## Final report (last message)
Reqs by capability with VERIFIED/INFERRED deltas vs pass 1; VERIFIED % old→new; scenario-debt 130→N; ownership decisions made; gaps closed G-xx; validate line; commits; wall-clock; NEXT-PASS accuracy note (what you could not finish and exactly why).
