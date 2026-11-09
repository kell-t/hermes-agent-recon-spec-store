# Capability Spec Draft Template (OpenSpec-flavored)

You are reconstructing a capability spec for DroidDeck (github.com/Droid-Deck/DroidDeck, GPL-3.0)
from evidence. Output ONE file in this exact shape. Rules at the end are binding.

```markdown
# Capability: <name>

Baseline: DroidDeck main @ <sha you checked> (2026-11-04). Evidence window: 2026-09-19 .. 2026-11-04.

## Summary
<2-4 sentences: what this capability is and where it lives in the code.>

## Primary code locations
- `path/...` — <one-line role>

## Requirements

### Requirement: <short title>
The app SHALL <behavior, testable, present tense>.
- Status: VERIFIED | INFERRED | UNVERIFIED
- Evidence: [PR #NNNN](https://github.com/Droid-Deck/DroidDeck/pull/NNNN) — <what it did>; doc: docs/...
- Anchor: `file:line or file` in current HEAD that implements it (VERIFIED only)

(...repeat; group under `## Sub-areas` if needed)

## Known gaps / open questions
- <behavior seen in issue titles or partial evidence that could NOT be grounded — list explicitly>
```

## Binding rules
1. EVIDENCE FIRST: every requirement must cite at least one real PR number or doc file found in the evidence bundle. No citation → do not write the requirement.
2. VERIFIED means you OPENED the current code at the anchor and saw the implementation. Paste the anchor path. If you did not open it, it is INFERRED (cited from docs/PRs but code unconfirmed) or UNVERIFIED.
3. Blanks over guesses. Never invent PR numbers, file paths, or line numbers. If unknown, write "anchor not located".
4. Requirements describe WHAT/WHY (behavior + intent), not implementation detail, except where implementation IS the contract (e.g. protocol names, file formats).
5. Prefer RFC-2119 verbs: SHALL (hard), SHOULD (strong default), MAY (optional).
6. Where docs and code disagree, record the DOC claim as the requirement and note the disagreement in Known gaps.
7. Density target: 8–20 requirements for your capability. Depth over breadth; this is a reconstruction seed, not the final spec.
8. Read the release notes' "30 seconds" summaries first — they are curated intent statements.
