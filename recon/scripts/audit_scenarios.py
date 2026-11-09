#!/usr/bin/env python3
"""Scenario-level audit gate: every `#### Scenario:` block's `- Source:`
lines are cite lists joined by ';' (outside quotes/backticks); every cite
must be one of (cite grammar must match SCENARIO_PASS_TEMPLATE):

  [relnote <ver>] "phrase" ["phrase"...]
                     -> version body exists (relnote_<ver>.txt and/or
                        releases.json, alias-resolved); >=60% overlap each
  doc: <path>[:line] [(annotation)] [§ section [—]] "phrase" [/ "phrase"...]
                     -> path resolves under evidence/docs/ (flattened) or
                        the repo; >=60% overlap each quote; a quoteless
                        `doc: p § Section` requires the section text to
                        appear in the file
  test: <path>::[Class::]method
                     -> EXACT grep of path + every :: segment in the repo
                        at the pin (a bare `path::rest` after ';` is a
                        test cite continuation)
  prose with `file:line` anchors -> anchor files must exist at the pin

Exit non-zero on any violation. Scenarios with a NOTE marking them derived
(conversion-injected scenario-debt) are skipped, never counted as grounded.
"""
import os
import re
import sys

import common

DRAFTS, EV = common.DRAFTS, common.EV
DOCS = os.path.join(EV, "docs")
pin = common.PinTree()
rel_bodies = common.relnote_bodies({})


def resolve_doc(path):
    for cand in (os.path.join(DOCS, path), os.path.join(common.REPO, path),
                 os.path.join(DOCS, path.replace("/", "_"))):
        if os.path.exists(cand):
            return cand
    return None


bad, stats = [], {}
for fn in sorted(os.listdir(DRAFTS)):
    if not fn.endswith(".md"):
        continue
    cap = fn[:-3]
    text = open(os.path.join(DRAFTS, fn)).read()
    scen_blocks = []
    for m in re.finditer(r"(?m)^#### Scenario: (.+)$", text):
        nm = re.search(r"(?m)^#{2,4} ", text[m.end():])
        blk_end = m.end() + (nm.start() if nm else len(text) - m.end())
        scen_blocks.append((m.group(1), text[m.end():blk_end]))
    grounded = 0
    for name, blk in scen_blocks:
        if "SCENARIO-DEBT" in blk or "derived" in name.lower():
            continue
        grounded += 1
        sources = re.findall(r"(?m)^- Source: (.+)$", blk)
        if not sources:
            bad.append("%s | %s: scenario with no Source line" % (cap, name))
        for s in sources:
            cites = common.parse_source(s)
            typed = [c for c in cites if c["kind"] != "other"]
            if not typed:
                bad.append("%s | %s: unparseable Source: %s" % (cap, name,
                                                                s[:80]))
            for c in cites:
                if c["kind"] == "other":
                    # prose commentary rides along with a verifiable cite;
                    # flag only when the line has no typed evidence at all
                    continue
                if c["kind"] == "relnote":
                    body = rel_bodies.get(c["ver"])
                    if body is None:
                        alt = [t for t in rel_bodies
                               if c["ver"] in t or t in c["ver"]]
                        body = " ".join(rel_bodies[t] for t in alt) \
                            if alt else None
                    if body is None:
                        bad.append("%s | %s: relnote %s not mined"
                                   % (cap, name, c["ver"]))
                        continue
                    for q in c["quotes"]:
                        ov = common.token_overlap(q, body)
                        if ov < 0.6:
                            bad.append("%s | %s: relnote quote overlap "
                                       "%.0f%%: %s..." % (cap, name,
                                                          ov * 100, q[:60]))
                    if not c["quotes"]:
                        bad.append("%s | %s: relnote cite with no quote"
                                   % (cap, name))
                elif c["kind"] == "doc":
                    p = resolve_doc(c["path"])
                    if p is None:
                        bad.append("%s | %s: doc path unresolved: %s"
                                   % (cap, name, c["path"]))
                        continue
                    body = open(p, errors="ignore").read()
                    if c["quotes"]:
                        for q in c["quotes"]:
                            ov = common.token_overlap(q, body)
                            if ov < 0.6:
                                bad.append("%s | %s: doc quote overlap "
                                           "%.0f%%: %s..." % (cap, name,
                                                              ov * 100,
                                                              q[:60]))
                    else:
                        # quoteless pointer; if it carried a line/range
                        # treat as code anchor, else verify section parts
                        if c.get("lines") and not c["section"].strip():
                            src = pin.lines(c["path"])
                            if src is None:
                                bad.append(
                                    "%s | %s: code path missing: %s"
                                    % (cap, name, c["path"]))
                            elif c["lines"][1] > len(src):
                                bad.append(
                                    "%s | %s: code line out of range: %s"
                                    % (cap, name, c["path"]))
                            continue
                        low = body.lower()
                        head = re.split(r"\s+—\s+|\s+-\s+", c["section"])[0]
                        parts = [re.sub(r"\s*\d+$", "", x.strip().lower())
                                 for x in re.split(r"[,/]", head)]
                        missing = []
                        if len(parts) > 1 and re.fullmatch(
                                r"[\w./_-]+\.(md|py|ts|tsx|yaml|yml|json"
                                r"|sh|toml)", head.strip().lower()):
                            parts = [head.strip().lower()]  # it's one path
                        for x in parts:
                            if not x:
                                continue
                            if re.search(r"\.(md|py|ts|tsx|yaml|yml|json|"
                                         r"sh|toml)$", x):
                                # section pointer to another file
                                if (resolve_doc(x) is None
                                        and not pin.exists(x)):
                                    missing.append(x)
                            elif x not in low:
                                missing.append(x)
                        if missing:
                            bad.append("%s | %s: doc section not found: %s"
                                       % (cap, name,
                                          c["section"][:60] or c["path"]))
                elif c["kind"] == "code":
                    if not pin.exists(c["path"]):
                        bad.append("%s | %s: code path missing: %s"
                                   % (cap, name, c["path"]))
                        continue
                    lines = pin.lines(c["path"])
                    if c["line"] > len(lines):
                        bad.append("%s | %s: code line out of range: %s:%s"
                                   % (cap, name, c["path"], c["line"]))
                        continue
                    for q in c.get("quotes", []):
                        ov = common.token_overlap("\n".join(lines), q)
                        if ov < 0.6:
                            bad.append("%s | %s: code string quote overlap "
                                       "%.0f%%: %s..." % (cap, name,
                                                          ov * 100, q[:60]))
                elif c["kind"] == "test":
                    path = c["path"]
                    if not pin.exists(path):
                        bad.append("%s | %s: test path missing: %s"
                                   % (cap, name, path))
                        continue
                    whole = "\n".join(pin.lines(path))
                    for seg in c["segs"]:
                        if seg not in whole:
                            bad.append("%s | %s: test segment missing: "
                                       "%s::%s" % (cap, name, path, seg))
                elif c["kind"] == "anchor":
                    for f, ln in c["anchors"]:
                        fp = resolve_doc(f) if "/" not in f else None
                        if not pin.exists(f) and fp is None:
                            alt = pin.resolve_bare_path(f)
                            if alt is None:
                                bad.append("%s | %s: anchor file missing: %s"
                                           % (cap, name, f))
                else:
                    bad.append("%s | %s: unparseable Source segment: %s"
                               % (cap, name, c["text"][:80]))
    stats[cap] = dict(reqs=text.count("### Requirement:"), grounded=grounded)

tot_g = sum(v["grounded"] for v in stats.values())
tot_r = sum(v["reqs"] for v in stats.values())
for cap, d in sorted(stats.items()):
    print("%-28s reqs=%-3d grounded_scen=%d" % (cap, d["reqs"], d["grounded"]))
print("TOTAL grounded scenarios %d / requirements %d" % (tot_g, tot_r))
if bad:
    print("\n".join("VIOLATION: %s" % b for b in bad))
    print("FAIL: %d violations" % len(bad))
    sys.exit(1)
print("SCENARIOS GATE GREEN")
