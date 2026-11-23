#!/usr/bin/env python3
"""Pin-readiness survey: classify every draft anchor cite against the
WORKING TREE of the source clone (which must be checked out at the survey
target). Same cite dialect as audit_requirements.py (ANCHOR_RE + hint
windows), but instead of pass/fail at the pin it emits per-anchor
verdicts at the target commit so a re-pin can be costed BEFORE approval:

  OK            hint window matches (or no hint and line in bounds)
  SHIFTED       hint exists in the file but not within +/-5 of the cited
                line (nearest hit reported)
  OOB           cited line beyond file end (nearest hint hit reported)
  MOVED         anchor file gone at target but a suffix match exists
  DEAD-FILE     anchor file gone and resolves nowhere
  HINT-DEAD     file exists, hint token found nowhere in it (dead-anchor
                candidate -- needs a human read at re-pin)

Usage: python3 pin_health.py            # prints JSON summary to stdout
Run from the store with the venv python (PyYAML via common.load_config).
"""
import json
import os
import re
import sys

import common

cfg = common.load_config()
DRAFTS = common.DRAFTS
# PIN_HEALTH_REPO: survey an alternate checkout (e.g. a scratch worktree at
# a candidate re-pin target) without disturbing the pinned clone checkout.
# Same override as the gufo store's copy (promoted 2026-11-18).
tree = common.PinTree(os.environ.get("PIN_HEALTH_REPO") or None)
EXTS = cfg["anchor_extensions"]

ANCHOR_RE = re.compile(r"`([\w./\-]+\.(?:%s)):(\d+)(?:-\d+)?(?:\s*\([^)]*\))?`"
                       % "|".join(map(re.escape, EXTS)))
HINT_RE = re.compile(
    r"`([\w./\-]+\.\w+):(\d+)(?:-\d+)?(?:\s*\(([^)]*)\))?`(?:\s*\(([^)]+)\))?")
IDENT = re.compile(r"[A-Za-z_][\w.\-]{3,}")
HINT_STOP = {"field", "example", "gate", "line", "the", "dict", "method",
             "class", "function", "entry", "name", "module", "docstring",
             "comment", "docstrings", "comments", "header", "note"}


def hint_tokens(hint):
    toks = [t for t in IDENT.findall(hint) if t.lower() not in HINT_STOP]
    return [t.split(".")[-1] if "." in t else t for t in toks]


def classify(path, ln, hint):
    lines = tree.lines(path)
    if lines is None:
        alt = tree.find_suffix(path)
        return ("MOVED" if alt else "DEAD-FILE"), None, alt[:3]
    ln = int(ln)
    toks = hint_tokens(hint) if hint else []

    def hit(t, words):
        return any(w == t or (len(w) >= 5 and len(t) >= 5 and w[:5] == t[:5])
                   for w in words)

    if not (1 <= ln <= len(lines)):
        near = None
        if toks:
            for i, l in enumerate(lines, 1):
                wl = re.findall(r"[\w.\-]+", l)
                if any(hit(t, wl) for t in toks):
                    near = i
                    break
        return "OOB", near, None
    if not toks:
        return "OK", None, None
    lo, hi = max(0, ln - 6), min(len(lines), ln + 5)
    wwords = re.findall(r"[\w.\-]+", " ".join(lines[lo:hi]))
    if any(hit(t, wwords) for t in toks):
        return "OK", None, None
    near, whole = None, "\n".join(lines)
    for t in toks:
        if t in whole:
            for i, l in enumerate(lines, 1):
                wl = re.findall(r"[\w.\-]+", l)
                if hit(t, wl):
                    near = i if near is None else min(near, i)
                    break
    if near is None:
        return "HINT-DEAD", None, None
    return "SHIFTED", near, None


def main():
    per_cap, records = {}, []
    for fn in sorted(os.listdir(DRAFTS)):
        if not fn.endswith(".md"):
            continue
        cap = fn[:-3]
        text = open(os.path.join(DRAFTS, fn), errors="ignore").read()
        hints = {(m.group(1), m.group(2)): (m.group(3) or m.group(4) or "")
                 for m in HINT_RE.finditer(text)}
        seen = set()
        for f, ln in ANCHOR_RE.findall(text):
            key = (f, ln)
            if key in seen:
                continue
            seen.add(key)
            verdict, near, alt = classify(f, ln, hints.get(key, ""))
            rec = {"cap": cap, "anchor": "%s:%s" % (f, ln),
                   "verdict": verdict}
            if near is not None:
                rec["nearest_hint_line"] = near
            if alt:
                rec["moved_candidates"] = alt
            records.append(rec)
            per_cap.setdefault(cap, {}).setdefault(verdict, 0)
            per_cap[cap][verdict] += 1
    totals = {}
    for c in per_cap.values():
        for k, v in c.items():
            totals[k] = totals.get(k, 0) + v
    print(json.dumps({"total_anchors": len(records),
                      "totals": totals, "per_cap": per_cap,
                      "non_ok": [r for r in records
                                 if r["verdict"] != "OK"]},
                     indent=1))


if __name__ == "__main__":
    main()
