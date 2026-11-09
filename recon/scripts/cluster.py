#!/usr/bin/env python3
"""Phase 2: cluster mined commits into capability buckets and write bounded
drafting bundles (evidence/clusters.json + evidence/bundle_<cap>.txt).

pr-ref stores: cluster evidence/pr_commits.json by subject regex (<=2
buckets/commit). ref-free stores: cluster evidence/commits.json the same way,
but bundle headers state that subjects are INTENT ONLY (verify at pin) and
include the capability's code/doc inventory.

Clusters are a STARTING PARTITION, not truth: expect heavy FP rates;
drafters reject misfiled items. Tighten regexes after triaging FPs.
"""
import collections
import json
import os
import re

import common

cfg = common.load_config()
EV = common.EV
CAPS = cfg["capabilities"]

if cfg["pr_ref_mode"] == "pr-ref":
    rows = common.corpus("pr_commits.json")
    if not rows:
        raise SystemExit("run mine_evidence.py first")
else:
    rows = common.corpus("commits.json")
    if not rows:
        raise SystemExit("run mine_evidence.py first")

comp = {k: re.compile(c["subject_regex"], re.I) for k, c in CAPS.items()}
clusters = collections.defaultdict(list)
for r in rows:
    hits = [k for k, rx in comp.items() if rx.search(r["subject"])]
    for k in hits[:2]:
        clusters[k].append(r)
json.dump(clusters, open(os.path.join(EV, "clusters.json"), "w"), indent=1)

for k, v in sorted(clusters.items()):
    v.sort(key=lambda r: r["date"], reverse=True)
    if cfg["pr_ref_mode"] == "pr-ref":
        lines = ["# Bundle: %s — %d PR-landed commits (window %s..%s), newest first, capped at 60"
                 % (k, len(v), min(x["date"] for x in v), max(x["date"] for x in v)),
                 "# Clusters are a STARTING PARTITION, not truth; reject misfiled items.", ""]
        for r in v[:60]:
            lines.append("%s (#%d) [%s] %s" % (r["date"], r["pr"], r["sha"], r["subject"]))
    else:
        lines = ["# Bundle: %s — %d/%d commit-subject hits (full history; refs rare — subject = intent only, verify at pin)"
                 % (k, len(v), len(rows)),
                 "# Primary code/doc inventory:"]
        lines += ["  - " + f for f in CAPS[k].get("code", [])]
        lines.append("")
        for r in v[:60]:
            lines.append("%s [%s] %s" % (r["date"], r["sha"], r["subject"]))
    open(os.path.join(EV, "bundle_%s.txt" % k), "w").write("\n".join(lines) + "\n")
    print("bundle_%s: %d (%d kept)" % (k, len(v), min(len(v), 60)))

uncat = sum(1 for r in rows
            if not any(rx.search(r["subject"]) for rx in comp.values()))
print("uncategorized commits:", uncat, "/", len(rows),
      "(high % = your regex map or scope list needs work)")
