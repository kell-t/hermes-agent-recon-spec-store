MISSION — spec reconstruction PASS 3 for NousResearch/hermes-agent (interactive session; delegation enabled)

You are the spec agent. Read in order: recon/PLAYBOOK.md → recon/repo_config.yaml → recon/RECON_LEDGER.md (pass-2 CURRENT STATE + NEXT-PASS section, line ~68). Store: /opt/data/agent-github-spec-store/github/NousResearch/hermes-agent (openspec store id: hermes-agent). Pinned clone: repo/ @ 2bd378ed (v0.23.0). Do NOT re-pin; baseline stays at 2bd378ed until the owner re-pins.

Pass-2 state: 158 reqs / 94 VERIFIED (59.5%) / 64 INFERRED / 23 scenario-debt / 213 grounded scenarios. Validate green 10/10 strict at HEAD.

## Pass-3 objectives (priority order, per the ledger's NEXT-PASS)
1. G-06 ANCHOR-VERIFY the 64-INFERRED mass. Order: cli-surface → tools-toolsets → config-provider-models → profiles-isolation → cron-background (the three 10-INFERRED heaviest first as W1/W2), then sessions-state — its INFERRED set is mostly Tier-B-only: do NOT force anchors there; where no anchor exists at the pin, keep INFERRED and say exactly why in Known gaps. VERIFIED = you OPENED the file at the pin and saw the implementation (file:line). Blanks over guesses; never invent anchors/PR numbers.
2. KANBAN dedicated pass (G-07): mine kanban-scoped commits (reuse recon/scripts/mine_evidence.py + mine_tail.py patterns; scope regex per repo_config kanban/delegation-orchestration + tail items), then read cron/AGENTS.md § Kanban and hermes_cli/kanban*.py at the pin. Expect 5–8 NEW cron-background requirements per the pass-2 ownership decision (kanban→cron-background). Draft per DRAFT_TEMPLATE.md, convert, validate.
3. SCENARIO DEBT: ground remaining 23 debt scenarios ONLY if NEW Tier A/B/C evidence text appears during objectives 1–2; never derive a scenario. Anything still ungroundable stays listed in Known gaps with the reason.
4. D-03/D-04: prepare upstream-report drafts INSIDE the store (recon/upstream-drafts/) if evidence supports them, but post nothing externally — license firewall + coordinator-owned approvals log. Owner approval required first.

## Fleet (delegation is enabled in this session)
MAX 3 concurrent children per wave (server limit, hard). Leaf children DO fabricate at the margin (pass 2: invented test-class segment, wrong release tags) — so:
- Pass every child full context: store path, pin sha 2bd378ed, capability name + its INFERRED requirement list (paste them in), DRAFT_TEMPLATE.md rules (VERIFIED=opened-at-pin; blanks over guesses; anchors file:line at pin; requirement body <500 chars).
- MANDATORY scripted audit gate between each wave's completion and your commit/conversion: anchor existence at pin (file exists + line in range + symbol/keyword present), relnote quote overlap ≥60%, test-name grep, tail-sha resolution against the pin. Use/extend recon/scripts (write audit_gate.py if not present). Fix or downgrade every failed child claim yourself before committing; self-reports are hypotheses, scripted tallies govern.
- Wave plan: W1 = cli-surface + tools-toolsets + config-provider-models anchor-verify. W2 = profiles-isolation + cron-background + sessions-state anchor-verify. W3 = kanban evidence bundle + drafting (1 child) while parent tallies/audits W1–W2. Adjust from the ledger as needed.

## Converter/validator quirks (from pass 2, binding)
(a) draft_to_spec.py ... "" emits `-<cap>` dirs — strip the leading dash. (b) The validator parses requirements ONLY inside the main `## Requirements` section — use `## Sub-area:` (converter flattens it), never a new `## ` section after `## Known gaps`. (c) Requirement body >500 chars fails strict — push detail into anchors/scenarios. (d) Re-register the store after machine moves.
Convert with: python3 /opt/data/agent-github-spec-store/tools/draft_to_spec.py specs_draft openspec/specs ""
Validate with PATH including /opt/data/home/.npm-global/bin: openspec validate --all --strict --store hermes-agent — must stay GREEN at EVERY commit.

## Constraints (unchanged)
- Sole spec writer; only YOUR verified findings change specs; specs model merged reality at the pin; unmerged PRs are not drift.
- Blanks over guesses; scripted tallies govern; never fabricate PR numbers/paths/anchors.
- GitHub read-only via curl -s --netrc; never print token; no pushes.
- License firewall: stay inside your store; do not open other repos' stores.
- git commit the store at each milestone with clear messages.

## Talk to the owner
BOT=$(grep '^TELEGRAM_BOT_TOKEN=' /opt/data/profiles/spec/.env | cut -d= -f2)
curl -s -X POST "https://api.telegram.org/bot$BOT/sendMessage" -d chat_id=402754873 --data-urlencode "text=spec: ..."
Short updates (2-6 lines) at: plan set | each wave done (+audit result) | kanban drafting done | validate checkpoint(s) | final report. One per >=5 min, start every message with "spec: ", no secrets/paths.

## Final report (last message)
Reqs by capability with VERIFIED/INFERRED deltas vs pass 2 (158/94 baseline); VERIFIED % old→new; scenario-debt 23→N; kanban reqs added; D-03/D-04 draft status; validate line; commits; wall-clock; what remains and exactly why (NEXT-PASS accuracy note).
