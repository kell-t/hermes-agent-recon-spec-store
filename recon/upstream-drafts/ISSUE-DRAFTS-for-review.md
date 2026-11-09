# Issue drafts — hermes-agent docs drift (for owner review)

Prepared 2026-11-08. All claims verified by the spec pass at tag **v0.23.0** (`2bd378e`); line refs are from that tag.
**Re-check vs current main `e0754412` (2026-11-08): D-03 unfixed (header + test file identical to pin). "Default 3" staleness has open fix PRs #125133/#111838/#105997 — excluded here. Kanban "convention" phrasing still present on main; #120013 covers a different angle.**
Overlap check (searched issues incl. closed): D-04's "default 3" staleness is **already reported** — #125131 (tools/AGENTS.md + configuration.md + environment-variables.md) and #125183 (docs site). Do not re-file; it is excluded below. D-03 and cluster items 2–3: no existing issues found (`test_authoring_standards` → 0 hits; `delegation.backend`/`provider` → none).

---

## ISSUE A

**Title:** `skills/AGENTS.md` over-states enforcement: "HARDLINE — enforced by tests" covers only the mechanical subset

**Body:**

### Pre-flight

- [x] Searched existing issues by title, text, and code symbols (`test_authoring_standards`, `skill_linter`, "HARDLINE") — `test_authoring_standards` has zero hits; existing "hardline" issues all concern the command guard, not skill authoring.
- [x] Verified at the v0.23.0 tag (`2bd378e`); line refs are from that tag.

### Description

`skills/AGENTS.md:24` headlines the authoring standards as **"HARDLINE — enforced by `tests/skills/test_authoring_standards.py`"**, but at the tag:

1. The test enforces only the mechanical subset: required frontmatter fields, name↔directory match, description hardline, related-skill resolution, no machine-local paths, size limit, paste-safe shell snippets.
2. The prose rules (native-tool prose, later editorial rules) have **no blocking assertion**; their companion `tools/skill_linter.py` says in its own docstring that it is "the advisory companion" whose findings "never block by themselves".
3. Rule 4 (author credit / human-first authoring) has **no mechanical check at all**.

Net: a contributor reads "HARDLINE — enforced by" and reasonably assumes CI blocks prose-rule violations; it doesn't. Either extend `test_authoring_standards.py` (or wire `skill_linter` severity into CI), or soften the header to e.g. "mechanical subset enforced by tests; prose rules lint-advised."

Category: documentation accuracy.

---

## ISSUE B

**Title:** Delegation docs cluster: `delegation.backend` vs `delegation.provider` naming trap; single-vs-batch wording drift

**Body:**

### Pre-flight

- [x] Searched `delegation.backend`, `delegation.provider`, "backend provider". Related but distinct: #125131 / #125183 (default-value staleness — this is **not** that; filed separately on purpose).
- [x] Verified at the v0.23.0 tag (`2bd378e`).

### Item 1 — naming trap

`delegation.backend` selects the delegation **provider plugin** (routing/lifecycle strategy) while `delegation.provider` pins **credentials** — near-identical keys, different semantics (`tools/AGENTS.md` § Delegation routes). Candidate for an explicit disambiguation note in both `tools/AGENTS.md` and user docs; a wrong-key config fails quietly, not loudly.

### Item 2 — internal wording drift

`tools/AGENTS.md` § Delegation says "Shapes: single (`goal` …) or batch (`tasks: [...])" while adjacent prose elsewhere in the same guide still reads tasks-only. Low severity; one editing pass.

---

## OPTIONAL SIBLING — comment on #110394

kanban docs call completion evidence "a convention", but the refusal behavior is pinned by hard refusal tests (goal-loop stops, #91264-class). Suggest the docs say *enforced* — and note that #110394's premise ("no evidence mechanism… discipline that drifts") could use the correction that a refusal mechanism does exist at the pin.
