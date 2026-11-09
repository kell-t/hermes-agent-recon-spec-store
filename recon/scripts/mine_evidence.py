#!/usr/bin/env python3
"""Phase 1 evidence mining. Writes recon/evidence/.

Modes (store_config.pr_ref_mode):
  pr-ref   — mine commits whose subjects end in (#NNNN); produce
             pr_commits.json + pr_index.json (history is an index).
  ref-free — mine the FULL log to commits.json (history is intent
             provenance; evidence = docs + tests + pin code).
Both modes: copy configured normative docs to evidence/docs/ (flattened
names) and inventory tests (Tier-C grounding source).
"""
import json
import os
import re
import subprocess
import collections

import common

cfg = common.load_config()
EV, REPO = common.EV, common.REPO
os.makedirs(EV, exist_ok=True)

out = subprocess.run(["git", "-C", REPO, "log", "--no-merges",
                      "--format=%H|%ad|%s", "--date=short"],
                     capture_output=True, text=True, check=True).stdout
conv = re.compile(r"^(feat|fix|refactor|perf|docs|test|chore|ci|revert"
                  r"|security|style|build)(?:\(([^)]*)\))?(!)?:\s*(.*)$", re.I)
prref = re.compile(r"\(#(\d+)\)\s*$")

rows = []
for line in out.splitlines():
    parts = line.split("|", 2)
    if len(parts) != 3:
        continue
    sha, date, subj = parts
    m = prref.search(subj)
    if cfg["pr_ref_mode"] == "pr-ref" and not m:
        continue
    c = conv.match(subj)
    rows.append({
        "sha": sha[:12], "date": date,
        "pr": (int(m.group(1)) if m else None),
        "subject": subj,
        "type": (c.group(1).lower() if c else "other"),
        "scope": (c.group(2) if c and c.group(2) else ""),
    })

if cfg["pr_ref_mode"] == "pr-ref":
    by_pr = collections.defaultdict(list)
    for r in rows:
        by_pr[r["pr"]].append(r)
    json.dump(rows, open(os.path.join(EV, "pr_commits.json"), "w"), indent=1)
    pr_index = {str(pr): {"date": rs[0]["date"], "shas": [x["sha"] for x in rs],
                          "subject": rs[0]["subject"]} for pr, rs in by_pr.items()}
    json.dump(pr_index, open(os.path.join(EV, "pr_index.json"), "w"), indent=1)
    print("pr_commits:", len(rows), "unique PRs:", len(by_pr))
    dates = sorted(r["date"] for r in rows)
    print("ref window:", dates[0], "..", dates[-1],
          "  <-- if the tail ends before the pin, run mine_tail.py")
    sc = collections.Counter(r["scope"] for r in rows if r["scope"])
    print("top scopes:", sc.most_common(15))
else:
    json.dump(rows, open(os.path.join(EV, "commits.json"), "w"), indent=1)
    print("commits mined:", len(rows), "| window:",
          rows[-1]["date"], "..", rows[0]["date"])

# normative doc corpus
dd = os.path.join(EV, "docs")
os.makedirs(dd, exist_ok=True)
for d in cfg["docs"]:
    src = os.path.join(REPO, d)
    if os.path.exists(src):
        open(os.path.join(dd, d.replace("/", "_")), "w").write(open(src).read())
        print("doc:", d, os.path.getsize(src), "bytes")
    else:
        print("doc MISSING:", d)

# test inventory (Tier-C). Python-ish shapes by default; adapt the regex to
# the source repo's test framework (pytest defs, JS describe/it, go TestXxx).
inv = []
for tf in cfg.get("test_files", []):
    p = os.path.join(REPO, tf)
    if not common.PinTree().exists(tf):
        print("test file MISSING:", tf)
        continue
    lines = open(p, errors="ignore").read().splitlines()
    hits = [(i + 1, l) for i, l in enumerate(lines)
            if re.match(r"\s*(class |def test|    def test|describe\(|func Test)", l)]
    inv.append("%s @ pin (line: decl)" % tf)
    inv += ["%d: %s" % x for x in hits]
    print("tests in", tf, ":", len(hits))
if inv:
    open(os.path.join(EV, "tests_inventory.txt"), "w").write("\n".join(inv) + "\n")
print("done")
