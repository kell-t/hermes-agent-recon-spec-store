#!/usr/bin/env python3
"""Requirement-level audit gate over specs_draft/ (the fabrication gate).

Run between every wave completion and every commit; run it over EXISTING
drafts as a baseline BEFORE the first wave and triage (see
references/audit-gate-fp-taxonomy.md — the gate WILL false-positive first).

Checks per requirement block:
  A1 anchor file exists at pin, line in range (ranges `f.py:A-B` allowed)
  A2 anchor hint keyword within +/-5 lines (stem-tolerant, stoplisted,
     dotted `Cls.member` -> final segment)
  A3 VERIFIED requires a line anchor ("anchor not located" + VERIFIED = FAIL)
  F  every backticked file-looking path anywhere in the draft must resolve
     at the pin (EXISTENCE-based, not slash-based)
  P  GitHub-number cites: pr-ref stores — must appear in pr_index/bundles/
     releases/verified_numbers; ref-free stores — verified_numbers ONLY
  R  [relnote <ver>] "quote" -> >=60% non-stopword token overlap vs that
     version's body (relnote files and/or releases.json, alias-resolved)
  T  test cites `path::Seg::Seg` -> path exists; every segment greppable
  S  sha tokens (7-12 hex) resolve via git cat-file at the pin
  B  requirement body (title -> first Status line) < 500 chars
Structural per file: no `### Requirement:` inside `## ` sections that follow
`## Known gaps`; VERIFIED+INFERRED+UNVERIFIED == requirement count.

Exit 0 = green. Usage: audit_requirements.py [--all | cap ...]
"""
import json
import os
import re
import sys

import common

cfg = common.load_config()
DRAFTS, EV = common.DRAFTS, common.EV
PIN = cfg["pin_sha"]
pin = common.PinTree()
EXTS = cfg["anchor_extensions"]

# ---------- corpora (optional per store shape) ----------
pr_index = set((common.corpus("pr_index.json") or {}).keys())
bundle_text = "".join(open(os.path.join(EV, fn), errors="ignore").read()
                      for fn in os.listdir(EV) if fn.startswith("bundle_")) \
    if os.path.isdir(EV) else ""
bundle_prs = set(re.findall(r"#(\d+)", bundle_text))
rel_bodies = common.relnote_bodies(cfg)
runtime_artifacts = set(cfg.get("runtime_artifacts", []))
rel_prs = set(re.findall(r"#(\d+)", json.dumps(rel_bodies)))
vn = common.verified_numbers()

ANCHOR_RE = re.compile(r"`([\w./\-]+\.(?:%s)):(\d+)(?:-\d+)?(?:\s*\([^)]*\))?`"
                       % "|".join(map(re.escape, EXTS)))
PATH_RE = re.compile(r"`([\w./\-]+\.(?:%s))(?::\d+(?:-\d+)?)?(?:\s*\([^)]*\))?`"
                     % "|".join(map(re.escape, EXTS)))
TESTSEG_RE = re.compile(r"([\w./\-]+\.(?:%s))((?:::\w+)+)" % "|".join(map(re.escape, EXTS)))
SHA_RE = re.compile(r"(?<![\w./:-])([0-9a-f]{7,12})(?![\w./-])")
PRNUM_RE = re.compile(r"(?:pull/|#)(\d{2,7})")
IDENT = re.compile(r"[A-Za-z_][\w.\-]{3,}")
HINT_STOP = {"field", "example", "gate", "line", "the", "dict", "method",
             "class", "function", "entry", "name", "module", "docstring",
             "comment", "docstrings", "comments", "header", "note"}


def audit_block(text, failures, ctx):
    title = text.splitlines()[0][len("### Requirement:"):].strip()
    where = "%s / %s" % (ctx, title[:60])
    m_status = re.search(r"[-*]\s*\*{0,2}Status\*{0,2}:\s*(\w+)", text)
    if not m_status:
        failures.append("STATUS-MISSING: " + where)
        return
    status = m_status.group(1)
    # B: body length (title line end -> Status line start)
    body_part = text[: m_status.start()]
    body_only = body_part.split("\n", 1)[1] if "\n" in body_part else ""
    if len(body_only.strip()) >= 500:
        failures.append("BODY-500 (%d): %s" % (len(body_only.strip()), where))
    # A1/A3 anchors
    anchors = ANCHOR_RE.findall(text)
    if status == "VERIFIED":
        if not anchors:
            tag = "VERIFIED-NO-ANCHOR" if "anchor not located" in text.lower() \
                else "VERIFIED-NO-LINE-ANCHOR"
            failures.append("%s: %s" % (tag, where))
    for f, ln in anchors:
        lines = pin.lines(f)
        if lines is None:
            failures.append("ANCHOR-MISSING-FILE %s:%s in %s" % (f, ln, where))
        elif not (1 <= int(ln) <= len(lines)):
            failures.append("ANCHOR-OOB %s:%s (file %d lines) in %s"
                            % (f, ln, len(lines), where))
    # A2 hint keywords (stem-tolerant); hint inside or outside the backticks
    for m in re.finditer(
            r"`([\w./\-]+\.\w+):(\d+)(?:-\d+)?(?:\s*\(([^)]*)\))?`(?:\s*\(([^)]+)\))?",
            text):
        f, ln = m.group(1), m.group(2)
        hint = m.group(3) or m.group(4) or ""
        if not hint:
            continue
        lines = pin.lines(f)
        if lines is None:
            continue
        lo, hi = max(0, int(ln) - 6), min(len(lines), int(ln) + 5)
        wwords = re.findall(r"[\w.\-]+", " ".join(lines[lo:hi]))
        toks = [t for t in IDENT.findall(hint) if t.lower() not in HINT_STOP]
        toks = [t.split(".")[-1] if "." in t else t for t in toks]

        def hit(t):
            return any(w == t or (len(w) >= 5 and len(t) >= 5 and w[:5] == t[:5])
                       for w in wwords)
        if toks and not any(hit(t) for t in toks):
            whole = "\n".join(lines)
            if not any(t in whole for t in toks):
                if cfg.get("anchor_hint_check", "strict") not in (
                        "off", False):
                    failures.append(
                        "ANCHOR-KEYWORD %s:%s hint=%r in %s"
                        % (f, ln, hint[:40], where))
    # F bare/relative path existence (existence-based, not slash-based);
    # runtime_artifacts = data files the behavior writes (never in-repo);
    # drift-note lines record absent/renamed files ON PURPOSE; names that
    # exist in the flattened evidence/docs corpus are corpus citations
    for line in text.splitlines():
        if re.search(r"\bdrift\b", line, re.I):
            continue
        for p in set(PATH_RE.findall(line)):
            if not pin.exists(p) and pin.resolve_bare_path(p) is None \
                    and os.path.basename(p) not in runtime_artifacts \
                    and not os.path.exists(
                        os.path.join(common.EV, "docs", p)):
                failures.append("PATH-UNRESOLVED `%s` in %s" % (p, where))
    # P GitHub-number cites
    for p in PRNUM_RE.findall(text):
        if cfg["pr_ref_mode"] == "ref-free":
            if p not in vn:
                failures.append("NUMBER-NOT-VERIFIED #%s in %s" % (p, where))
        elif (p not in pr_index and p not in bundle_prs
              and p not in rel_prs and p not in vn):
            failures.append("PR-NOT-IN-EVIDENCE #%s in %s" % (p, where))
    # R relnote quotes
    for m in re.finditer(r"\[relnote ([^\]]+)\]\s*\"([^\"]+)\"", text):
        tag, quote = re.sub(r"\s+", " ", m.group(1).strip()), m.group(2)
        body = rel_bodies.get(tag)
        if body is None:
            alt = [t for t in rel_bodies if tag in t or t in tag]
            body = " ".join(rel_bodies[t] for t in alt) if alt else None
        if body is None:
            failures.append("RELNOTE-TAG-UNKNOWN %s in %s" % (tag, where))
            continue
        ov = common.token_overlap(quote, body)
        if ov < 0.6:
            failures.append("RELNOTE-OVERLAP %.0f%% %s %r in %s"
                            % (ov * 100, tag, quote[:50], where))
    # T test cites (basename/partial path: any candidate file containing
    # every :: segment passes)
    for path, segs in TESTSEG_RE.findall(text):
        cands = [path] if pin.exists(path) else pin.find_suffix(path)
        if not cands:
            failures.append("TEST-PATH-MISSING %s in %s" % (path, where))
            continue
        seg_list = [x for x in segs.split("::") if x]
        whole_list = ["\n".join(pin.lines(c) or []) for c in cands]
        for s in seg_list:
            if not any(s in whole for whole in whole_list):
                failures.append("TEST-NAME-MISSING %s::%s in %s"
                                % (path, s, where))
    # S sha cites (a 7-12 hex run is a commit ref ONLY outside backticks;
    # backticked hex like `0000aa55` is a code constant, not a commit)
    const_spans = [(m.start(), m.end())
                   for m in re.finditer(r"`[^`]+`", text)]
    for m in re.finditer(r"(?<![\w./:-])([0-9a-f]{7,12})(?![\w./-])", text):
        tok = m.group(1)
        if tok.isdigit() or tok in PIN[:12]:
            continue
        if any(a <= m.start() < b for a, b in const_spans):
            continue
        if not pin.sha_resolves(tok):
            failures.append("SHA-UNRESOLVED %s in %s" % (tok, where))


def audit_file(cap, failures):
    text = open(os.path.join(DRAFTS, cap + ".md")).read()
    kg = text.find("\n## Known gaps")
    if kg >= 0:
        after = text[kg + 1:]
        for sec in [l for l in after.splitlines()
                    if re.match(r"^## (?!Sub-area)", l)
                    and not l.startswith("## Known gaps")]:
            seg = after.split(sec + "\n", 1)[1] if sec in after else ""
            stop = re.search(r"^## ", seg, re.M)
            seg = seg[: stop.start()] if stop else seg
            if "### Requirement:" in seg:
                failures.append("REQ-SECTION-AFTER-KNOWN-GAPS %s: %s" % (cap, sec))
    for b in re.split(r"(?=^### Requirement: )", text, flags=re.M)[1:]:
        audit_block(b.rstrip() + "\n", failures, cap)
    n = text.count("### Requirement:")
    v = text.count("Status: VERIFIED") + text.count("**Status**: VERIFIED")
    i = text.count("Status: INFERRED") + text.count("**Status**: INFERRED")
    u = text.count("Status: UNVERIFIED") + text.count("**Status**: UNVERIFIED")
    if v + i + u != n:
        failures.append("STATUS-COUNT %s: V%d+I%d+U%d != %d reqs" % (cap, v, i, u, n))
    return n, v, i, u


def main():
    args = sys.argv[1:]
    caps = (sorted(f[:-3] for f in os.listdir(DRAFTS) if f.endswith(".md"))
            if args in ([], ["--all"]) else args)
    failures, tot = [], [0, 0, 0, 0]
    for cap in caps:
        n, v, i, u = audit_file(cap, failures)
        print("%-28s reqs=%-3d V=%-3d I=%-3d U=%-3d" % (cap, n, v, i, u))
        tot = [a + b for a, b in zip(tot, (n, v, i, u))]
    print("TOTAL reqs=%d V=%d I=%d U=%d" % tuple(tot))
    if failures:
        print("\n=== GATE FAILURES (%d) ===" % len(failures))
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("REQUIREMENTS GATE GREEN")


if __name__ == "__main__":
    main()
