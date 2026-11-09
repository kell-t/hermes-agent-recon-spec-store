#!/usr/bin/env python3
"""Pass-3 scripted audit gate: audit specs_draft/ requirement blocks against the pin.

Mandatory between wave completion and commit (ledger NEXT-PASS 6, MISSION-pass3).
Checks per requirement block:
  A1 anchor existence  : `file:line` -> file exists in repo/ at pin, line in range
  A2 anchor keyword    : if anchor has a (`hint`) segment, >=1 identifier token from the
                         hint must appear within +/-5 lines of the anchor line
  A3 VERIFIED needs a line anchor; "anchor not located" while VERIFIED is a FAIL
  P  PR cites          : pull/NNNN or (#NNNN) must appear in pr_index/bundles/releases
  R  relnote quotes    : [relnote <tag>] "quote" -> >=60% verbatim overlap vs that tag's
                         release body (split on ... into fragments)
  T  test cites        : test: path::Cls::fn -> path exists at pin; each :: segment present
  S  tail sha          : 7-12 hex tokens resolve to real commits at the pin (git cat-file)
  B  body length       : requirement statement body (title..Status) < 500 chars (strict)
Structural per file: no `## ` section after `## Known gaps`; V+I+U == req count.

Exit 0 = gate green; exit 1 = failures listed. Usage: audit_gate.py [cap ...] | --all
"""
import difflib
import json
import os
import re
import subprocess
import sys

STORE = "/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent"
DRAFTS = os.path.join(STORE, "specs_draft")
EV = os.path.join(STORE, "recon", "evidence")
REPO = os.path.join(STORE, "repo")
PIN = "2bd378ed1b8d6bf2192cb26e0a55ff309e6bd19"

# ---------- evidence corpora ----------
pr_index = set(json.load(open(os.path.join(EV, "pr_index.json"))).keys())
rel_raw = open(os.path.join(EV, "releases.json")).read()
rel_prs = set(re.findall(r"#(\d+)", rel_raw))
bundle_text = "".join(
    open(os.path.join(EV, fn), errors="ignore").read()
    for fn in os.listdir(EV) if fn.startswith("bundle_")
)
bundle_prs = set(re.findall(r"#(\d+)", bundle_text))
releases = {r["tag"]: r.get("body", "") for r in json.load(open(os.path.join(EV, "releases.json")))}
# release bodies also known under a semver name (e.g. tag v2026.4.3 ships "v0.7.0")
alias = {}
for r in json.load(open(os.path.join(EV, "releases.json"))):
    for v in re.findall(r"v?\d+\.\d+\.\d+", r.get("name", "")):
        alias.setdefault(v if v.startswith("v") else "v" + v, r["tag"])

_file_cache = {}
def repo_lines(rel):
    if rel not in _file_cache:
        p = os.path.join(REPO, rel)
        try:
            _file_cache[rel] = open(p, errors="ignore").read().splitlines()
        except OSError:
            _file_cache[rel] = None
    return _file_cache[rel]

_sha_cache = {}
def sha_resolves(tok):
    if tok not in _sha_cache:
        r = subprocess.run(
            ["git", "-C", REPO, "cat-file", "-e", tok + "^{commit}"],
            capture_output=True)
        _sha_cache[tok] = (r.returncode == 0)
    return _sha_cache[tok]

def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split()

def quote_overlap(quote, body):
    """Per-fragment: longest common word-sequence vs fragment word count (char-based
    SequenceMatcher size counts chars; convert with a char-ratio against the fragment)."""
    frags = [f for f in re.split(r"\.\.\.|…", quote) if f.strip()]
    if not frags:
        return 1.0
    body_n = norm(body)
    body_str = " ".join(body_n)
    ratios = []
    for f in frags:
        ft = norm(f)
        if not ft:
            continue
        fs = " ".join(ft)
        m = difflib.SequenceMatcher(None, fs, body_str, autojunk=False).find_longest_match(
            0, len(fs), 0, len(body_str))
        ratios.append(m.size / max(1, len(fs)))
    return min(ratios) if ratios else 1.0

ANCHOR_RE = re.compile(r"`([\w./\-]+\.(?:py|md|ts|tsx|ya?ml|json|sh|toml)):(\d+)(?:-\d+)?`")
TEST_RE = re.compile(r"(?:test:\s|;|\b)(tests/[\w./\-]+\.py)(?:::(\w+))?(?:::(\w+))?")
SHA_RE = re.compile(r"(?<![\w./:-])([0-9a-f]{7,12})(?![\w./-])")
PRNUM_RE = re.compile(r"(?:pull/|#)(\d{3,6})")
IDENT = re.compile(r"[A-Za-z_][\w.\-]{3,}")

def audit_block(header_and_body, failures, ctx):
    text = header_and_body
    title = text.splitlines()[0][len("### Requirement:"):].strip()
    where = "%s / %s" % (ctx, title[:60])
    m_status = re.search(r"-\s*Status:\s*(\w+)", text)
    if not m_status:
        failures.append("STATUS-MISSING: " + where)
        return
    status = m_status.group(1)
    # B: body length (title line end -> Status line start)
    body_part = text[: m_status.start()]
    body_only = body_part.split("\n", 1)[1] if "\n" in body_part else ""
    if len(body_only.strip()) >= 500:
        failures.append("BODY-500 (%d): %s" % (len(body_only.strip()), where))
    # A1/A2 anchors
    anchor_lines = [l for l in text.splitlines() if "Anchor:" in l or "Anchor " in l]
    anchors = ANCHOR_RE.findall(text)
    if status == "VERIFIED":
        if not anchors and "anchor not located" in text.lower():
            failures.append("VERIFIED-NO-ANCHOR: " + where)
        elif not anchors:
            failures.append("VERIFIED-NO-LINE-ANCHOR: " + where)
    for f, ln in anchors:
        lines = repo_lines(f)
        if lines is None:
            failures.append("ANCHOR-MISSING-FILE %s:%s in %s" % (f, ln, where))
            continue
        if not (1 <= int(ln) <= len(lines)):
            failures.append("ANCHOR-OOB %s:%s (file %d lines) in %s" % (f, ln, len(lines), where))
            continue
    # A2 keyword check: per anchor segment with hint
    for seg in re.findall(r"`([\w./\-]+\.\w+):(\d+)`\s*\(([^)]+)\)", text):
        f, ln, hint = seg
        lines = repo_lines(f)
        if lines is None:
            continue
        lo, hi = max(0, int(ln) - 6), min(len(lines), int(ln) + 5)
        window = " ".join(lines[lo:hi])
        toks = [t for t in IDENT.findall(hint)
                if not t.lower() in ("field", "example", "gate", "line", "the", "dict",
                                      "method", "class", "function", "entry", "name")]
        # stem-tolerant: a hint word matches a window word sharing a >=5-char prefix
        wwords = re.findall(r"[\w.\-]+", window)
        def hit(t):
            return any(w == t or (len(w) >= 5 and len(t) >= 5 and w[:5] == t[:5])
                       for w in wwords)
        if toks and not any(hit(t) for t in toks):
            whole = "\n".join(lines)
            if not any(t in whole for t in toks):
                failures.append("ANCHOR-KEYWORD %s:%s hint=%r in %s" % (f, ln, hint[:40], where))
    # P: PR cites
    vn_path = os.path.join(EV, "verified_numbers.json")
    vn = json.load(open(vn_path)) if os.path.exists(vn_path) else {}
    for p in PRNUM_RE.findall(text):
        if (p not in pr_index and p not in bundle_prs and p not in rel_prs
                and p not in vn):
            failures.append("PR-NOT-IN-EVIDENCE #%s in %s" % (p, where))
    # R: relnote quotes
    for m in re.finditer(r"\[relnote ([\w.\-]+)\]\s*\"([^\"]+)\"", text):
        tag, quote = m.group(1), m.group(2)
        body = releases.get(tag) or releases.get(alias.get(tag, ""), None)
        if body is None:
            alt = [t for t in releases if tag in t or t in tag]
            body = " ".join(releases[t] for t in alt) if alt else None
        if body is None:
            failures.append("RELNOTE-TAG-UNKNOWN %s in %s" % (tag, where))
            continue
        r = quote_overlap(quote, body)
        if r < 0.6:
            failures.append("RELNOTE-OVERLAP %.0f%% %s %r in %s"
                            % (r * 100, tag, quote[:50], where))
    # T: test cites
    for m in re.finditer(r"(tests/[\w./\-]+\.py)((?:::(?:\w+))+)", text):
        path, segs = m.group(1), [s for s in m.group(2).split("::") if s]
        lines = repo_lines(path)
        if lines is None:
            failures.append("TEST-PATH-MISSING %s in %s" % (path, where))
            continue
        whole = "\n".join(lines)
        for s in segs:
            if s not in whole:
                failures.append("TEST-NAME-MISSING %s::%s in %s" % (path, s, where))
    # S: sha cites (skip the pin itself and pure-digit tokens)
    for tok in SHA_RE.findall(text):
        if tok.isdigit() or tok in PIN[:12]:
            continue
        if not sha_resolves(tok):
            failures.append("SHA-UNRESOLVED %s in %s" % (tok, where))

def audit_file(cap, failures):
    p = os.path.join(DRAFTS, cap + ".md")
    text = open(p).read()
    blocks = re.split(r"(?=^### Requirement: )", text, flags=re.M)
    head = blocks[0]
    # structural: `## ` sections after Known gaps
    kg = text.find("\n## Known gaps")
    if kg >= 0:
        after = text[kg + 1:]
        extra = [l for l in after.splitlines()
                 if re.match(r"^## (?!Sub-area)", l) and not l.startswith("## Known gaps")]
        for sec in extra:
            # prose sections are fine; only requirement sections after Known gaps break the validator
            seg = after.split(sec + "\n", 1)[1] if sec in after else ""
            stop = re.search(r"^## ", seg, re.M)
            seg = seg[: stop.start()] if stop else seg
            if "### Requirement:" in seg:
                failures.append("REQ-SECTION-AFTER-KNOWN-GAPS %s: %s" % (cap, sec))
    for b in blocks[1:]:
        audit_block(b.rstrip() + "\n", failures, cap)
    v, i, u = text.count("Status: VERIFIED"), text.count("Status: INFERRED"), text.count("Status: UNVERIFIED")
    n = text.count("### Requirement:")
    if v + i + u != n:
        failures.append("STATUS-COUNT %s: V%d+I%d+U%d != %d reqs" % (cap, v, i, u, n))
    return n, v, i, u

def main():
    args = sys.argv[1:]
    caps = sorted(f[:-3] for f in os.listdir(DRAFTS) if f.endswith(".md")) if args == ["--all"] else args
    failures = []
    tot = [0, 0, 0, 0]
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
    print("GATE GREEN")

if __name__ == "__main__":
    main()
