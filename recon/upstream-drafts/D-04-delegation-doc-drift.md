# Upstream-report draft D-04 — delegation doc/code staleness cluster

STATUS: DRAFT — NOT POSTED. Owner approval required before any external posting.

Repo: NousResearch/hermes-agent @ pin 2bd378ed (v0.23.0)

## Item 1 (verified at pin): tools/AGENTS.md "default 3" is stale
- `tools/AGENTS.md:146` (§ Delegation): "concurrency capped by `delegation.max_concurrent_children`,
  default 3".
- `tools/delegate_tool_config.py:19`: `_DEFAULT_MAX_CONCURRENT_CHILDREN = 10`.
- User docs agree with the code: `website/docs/user-guide/features/delegation.md:45` "Up to 10
  concurrent subagents by default (configurable, no hard ceiling)".
So the area guide's parenthetical is a stale default value; a contributor reading only the area
guide would set wrong expectations for fleet capacity.

## Item 2 (verified at pin): "tasks-only" vs "Shapes: single or batch"
tools/AGENTS.md § Delegation itself says "Shapes: single (`goal` ...) or batch (`tasks: [...]`)"
while adjacent prose elsewhere in the guide still reads tasks-only in places — internal wording
drift (flagged pass 2; low severity).

## Item 3: delegation.backend vs delegation.provider naming trap
`delegation.backend` selects the delegation provider plugin (routing/lifecycle strategy) while
`delegation.provider` pins credentials — near-identical names, different semantics
(`tools/AGENTS.md` § Delegation routes paragraph). Candidate for a docs disambiguation note.

## Item 4: kanban handoff evidence "a convention" vs hard-refusal tests
kanban.md prose calls completion evidence "a convention" while the behavior is pinned by hard
refusal tests (#91264-class goal-loop stops). Docs should say the refusal is enforced (relevant
to the pass-3 kanban requirements drafted into cron-background).

## Item 5: toolset reduction invariant pinned only at resolution-test level
relnote 2026.3.23 records disabled toolsets historically re-enabling (#2268); today the reduction
invariant holds at the toolset-resolution layer (tests) but user docs never state "disabled stays
disabled". Candidate for a user-docs contract line.

## Suggested upstream framing (NOT filed)
One docs-accuracy issue with items 1–2 (concrete stale value + wording), and 3–5 as smaller
disambiguation notes. All five are §3.2 ordinary public work; none security-sensitive.
