#!/usr/bin/env python3
"""draft_to_spec.py — convert groundwork `specs_draft/*.md` (OpenSpec-flavored)
into validator-conformant `openspec/specs/<repo>-<cap>/spec.md`.

Workflow adjustments discovered against openspec v1.16.1 validator rules
(read from dist/core/parsers/requirement-text.js + validator.js):
  1. `## Purpose` is a required header; drafts use `## Summary` -> rename.
  2. Requirement body = lines up to the first header. `- Status:` style bullets
     inside it count toward the >500-char limit, but `**Key**:` metadata lines
     are explicitly skipped by the parser -> convert evidence bullets.
  3. `## Sub-area:` h2 sections orphan the `### Requirement:` headers nested
     under them (validator: "Requirement header outside Requirements section")
     -> flatten to bold text lines.
  4. Every requirement MUST have >=1 `#### Scenario:` (ERROR even non-strict).
     Requirements whose pass-3 evidence yielded no scenario get an explicit
     DERIVED scenario restating the requirement, labeled so it is tracked as
     scenario debt in RECON_LEDGER — never presented as evidence-backed.

Deterministic; safe to re-run after each drafting pass.
Usage: draft_to_spec.py <drafts_dir> <specs_out_dir> <repo-prefix>
"""
import re
import sys
import os

DERIVED_MARK = "SCENARIO-DEBT (derived, pass-4 conformance)"


def convert(text: str) -> tuple[str, int]:
    debt = 0
    # 1. Summary -> Purpose
    text = re.sub(r"^## Summary\b.*$", "## Purpose", text, count=1, flags=re.M)
    # 2. flatten h2 sub-area headers nested in Requirements
    text = re.sub(r"^## Sub-area:\s*(.+)$", r"**Sub-area: \1**", text, flags=re.M)

    lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    def bullets_to_metadata(block: list[str]) -> list[str]:
        """Convert `- Status|Evidence|Anchor:` bullets (+ indented continuations)
        into `**Key**:` metadata lines, which the validator excludes from
        requirement text."""
        res: list[str] = []
        k = 0
        while k < len(block):
            m = re.match(r"^- (Status|Evidence|Anchor):\s*(.*)$", block[k])
            if m:
                parts = [m.group(2)]
                j = k + 1
                while j < len(block) and re.match(r"^\s{2,}\S", block[j]):
                    parts.append(block[j].strip())
                    j += 1
                res.append(f"**{m.group(1)}**: " + " ".join(parts))
                k = j
                continue
            res.append(block[k])
            k += 1
        return res

    while i < n:
        line = lines[i]
        # 3. lone evidence bullets outside requirement blocks
        m = re.match(r"^- (Status|Evidence|Anchor):\s*(.*)$", line)
        if m:
            parts = [m.group(2)]
            j = i + 1
            while j < n and re.match(r"^\s{2,}\S", lines[j]):
                parts.append(lines[j].strip())
                j += 1
            out.append(f"**{m.group(1)}**: " + " ".join(parts))
            i = j
            continue
        # 4. requirement block: up to the next header at level <= 3
        if re.match(r"^### Requirement:", line):
            block = [line]
            j = i + 1
            while j < n and not re.match(r"^#{1,3}\s", lines[j]):
                block.append(lines[j])
                j += 1
            block = bullets_to_metadata(block)
            has_scen = any(re.match(r"^#### Scenario:", b) for b in block)
            if not has_scen:
                first = next((b.strip() for b in block[1:] if b.strip() and not b.startswith("**")), "")
                # restate requirement's leading sentence as a derived check
                sent = re.split(r"(?<=[.;])\s", first, maxsplit=1)[0][:300] if first else "the requirement above"
                block += [
                    "",
                    "#### Scenario: Conformance check (derived)",
                    f"- **WHEN** the behavior described by this requirement is exercised",
                    f"- **THEN** {sent}",
                    f"- NOTE: {DERIVED_MARK} — no scenario evidence in pass-3 corpus;",
                    f"  replace with evidence-backed scenarios on next recon pass.",
                    "",
                ]
                debt += 1
            out.extend(block)
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out), debt


def main() -> None:
    drafts_dir, out_root, prefix = sys.argv[1:4]
    total = 0
    for fn in sorted(os.listdir(drafts_dir)):
        if not fn.endswith(".md"):
            continue
        cap = f"{prefix}-{fn[:-3]}" if prefix else fn[:-3]
        src = os.path.join(drafts_dir, fn)
        dst_dir = os.path.join(out_root, cap)
        os.makedirs(dst_dir, exist_ok=True)
        converted, debt = convert(open(src).read())
        open(os.path.join(dst_dir, "spec.md"), "w").write(converted)
        total += debt
        print(f"{cap}: scenario-debt added={debt}")
    print(f"total derived scenarios: {total}")


if __name__ == "__main__":
    main()
