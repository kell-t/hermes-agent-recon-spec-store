#!/usr/bin/env python3
"""Pass-2 tail mining (pr-ref stores whose ref window stops before the pin).

Mines commits with AUTHOR date > store_config.tail_after WITHOUT the ref
filter (tail commits are cited [commit <12-hex>] — they are real at the pin).
Pitfall encoded: `git log --since=` filters COMMITTER date while %ad prints
AUTHOR date; rebased histories mix the two — so we parse the full log and
filter author-date HERE, not with --since.

Clustering for the tail is SCOPE-FIRST (conventional-commit scope vs the
capability's `scopes` list), subject regex as fallback, <=2 buckets/commit.
Appends an idempotent `# ==== TAIL APPEND` section to each bundle; merges
ref-bearing tail commits into pr_commits.json/pr_index.json.
"""
import collections
import json
import os
import re
import subprocess

import common

cfg = common.load_config()
EV, REPO = common.EV, common.REPO
TAIL_AFTER = cfg.get("tail_after")
if not TAIL_AFTER:
    raise SystemExit("store_config.tail_after is required for tail mining")

conv = re.compile(r"^(feat|fix|refactor|perf|docs|test|chore|ci|revert"
                  r"|security|style|build)(?:\(([^)]*)\))?(!)?:\s*(.*)$", re.I)
prref = re.compile(r"\(#(\d+)\)\s*$")

out = subprocess.run(["git", "-C", REPO, "log", "--no-merges",
                      "--format=%H|%ad|%s", "--date=short"],
                     capture_output=True, text=True, check=True).stdout
tail, seen = [], set()
for line in out.splitlines():
    parts = line.split("|", 2)
    if len(parts) != 3:
        continue
    sha, date, subj = parts
    if date <= TAIL_AFTER or sha in seen:
        continue
    seen.add(sha)
    m = prref.search(subj)
    c = conv.match(subj)
    tail.append({"sha": sha[:12], "date": date,
                 "pr": (int(m.group(1)) if m else None),
                 "subject": subj,
                 "type": (c.group(1).lower() if c else "other"),
                 "scope": (c.group(2) if c and c.group(2) else "")})
tail.sort(key=lambda r: r["date"], reverse=True)
json.dump(tail, open(os.path.join(EV, "tail_commits.json"), "w"), indent=1)
print("tail commits (author date > %s): %d, with PR ref: %d"
      % (TAIL_AFTER, len(tail), sum(1 for r in tail if r["pr"])))

# merge ref-bearing tail commits into the PR corpus
pc_path = os.path.join(EV, "pr_commits.json")
pcs = json.load(open(pc_path))
known = {r["sha"] for r in pcs}
pi_path = os.path.join(EV, "pr_index.json")
pidx = json.load(open(pi_path))
added = 0
for r in tail:
    if r["pr"] and r["sha"] not in known:
        pcs.append(r)
        known.add(r["sha"])
        added += 1
        pidx.setdefault(str(r["pr"]), {"date": r["date"], "shas": [],
                                       "subject": r["subject"], "tail": True}
                       )["shas"].append(r["sha"])
json.dump(pcs, open(pc_path, "w"), indent=1)
json.dump(pidx, open(pi_path, "w"), indent=1)
print("appended to pr_commits.json:", added, "| corpus:", len(pcs))

SCOPES = {k: set(s.lower() for s in c.get("scopes", []))
          for k, c in cfg["capabilities"].items()}
# Optional per-cap `tail_subject_regex` (tightened fallback for the tail);
# falls back to the pass-1 `subject_regex`.
SUBJ = {k: re.compile(c.get("tail_subject_regex") or c["subject_regex"], re.I)
        for k, c in cfg["capabilities"].items()}
tc = collections.defaultdict(list)
for r in tail:
    hits = [k for k, s in SCOPES.items() if r["scope"].lower() in s]
    if not hits:
        hits = [k for k, rx in SUBJ.items() if rx.search(r["subject"])]
    for k in hits[:2]:
        tc[k].append(r)
json.dump(tc, open(os.path.join(EV, "tail_clusters.json"), "w"), indent=1)
for k, v in sorted(tc.items()):
    path = os.path.join(EV, "bundle_%s.txt" % k)
    body = open(path).read().rstrip("\n") if os.path.exists(path) else "# Bundle: %s\n" % k
    body = body.split("\n# ==== TAIL")[0]          # idempotent re-runs
    lines = ["", "# ==== TAIL APPEND: %d commits, author date > %s, no-ref included,"
             " scope-first clustering, newest first, capped 40 ====" % (len(v), TAIL_AFTER)]
    for r in v[:40]:
        ref = ("(#%d)" % r["pr"]) if r["pr"] else "(no-ref)"
        lines.append("%s %s [%s] %s" % (r["date"], ref, r["sha"], r["subject"]))
    open(path, "w").write(body + "\n" + "\n".join(lines) + "\n")
    print("bundle_%s TAIL: %d kept of %d" % (k, min(len(v), 40), len(v)))
