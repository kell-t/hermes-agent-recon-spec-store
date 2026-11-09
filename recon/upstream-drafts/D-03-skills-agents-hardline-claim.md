# Upstream-report draft D-03 — skills/AGENTS.md over-claims test enforcement

STATUS: PARKED (owner ruling 2026-11-08) — tracked as Known gap in the spec; do not file upstream without fresh approval.

Repo: NousResearch/hermes-agent @ pin 2bd378ed (v0.23.0)

## Claim (verified at pin)
`skills/AGENTS.md:24` headlines the authoring standards as
"HARDLINE — enforced by `tests/skills/test_authoring_standards.py`", but at the pin:

- The test file enforces the mechanical subset: `test_required_frontmatter_fields`,
  `test_name_matches_directory`, `test_description_hardline`, `test_related_skills_resolve`,
  `test_no_machine_local_paths`, `test_size_limit`, `test_shell_snippets_paste_safe`.
  Standards 2–3 (native-tool prose rules beyond backtick snippets, and the later prose rules)
  have no blocking assertion.
- The prose-rule companion is `tools/skill_linter.py`, whose own docstring says the linter is
  "the advisory companion" and its findings "never block by themselves" (`LintFinding` rows;
  severity is "advisory metadata for the caller").
- Rule 4 (author credit / human-first authoring) has no mechanical check at all.

Net: the doc's "HARDLINE — enforced by" overstates enforcement for the prose rules. Per the
store's DRAFT_TEMPLATE rule 6 the DOC claim stays the requirement; the disagreement is recorded
in the spec's Known gaps (pass-2 D-03).

## Suggested upstream framing (issue body sketch, NOT filed)
Docs-vs-tests drift in skills/AGENTS.md authoring standards: either extend
`tests/skills/test_authoring_standards.py` to block standards 2–4 (or wire skill_linter severity
into CI), or soften the header to "mechanical subset enforced by test; prose rules lint-advised".
Category: documentation accuracy (§3.2-style ordinary public work, not security).
