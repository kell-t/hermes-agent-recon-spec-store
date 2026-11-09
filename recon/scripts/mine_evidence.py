#!/usr/bin/env python3
"""Phase 1 evidence mining for hermes-agent store. Writes to evidence/."""
import json, re, subprocess, os, collections

STORE = "/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent"
REPO = os.path.join(STORE, "repo")
EV = os.path.join(STORE, "recon", "evidence")
os.makedirs(EV, exist_ok=True)

# 1) PR-landed commits
out = subprocess.run(["git", "-C", REPO, "log", "--no-merges",
                      "--format=%H|%ad|%s", "--date=short"],
                     capture_output=True, text=True, check=True).stdout
rows = []
conv = re.compile(r'^(feat|fix|refactor|perf|docs|test|chore|ci|revert|security|style|build)'
                  r'(?:\(([^)]*)\))?(!)?:\s*(.*)$', re.I)
prref = re.compile(r'\(#(\d+)\)\s*$')
for line in out.splitlines():
    parts = line.split("|", 2)
    if len(parts) != 3:
        continue
    sha, date, subj = parts
    m = prref.search(subj)
    if not m:
        continue
    c = conv.match(subj)
    rows.append({
        "sha": sha[:12], "date": date, "pr": int(m.group(1)),
        "subject": subj, "type": (c.group(1).lower() if c else "other"),
        "scope": (c.group(2) if c and c.group(2) else ""),
    })
# dedupe on pr number keeping all shas? keep commit-level rows; also build pr index
by_pr = collections.defaultdict(list)
for r in rows:
    by_pr[r["pr"]].append(r)
json.dump(rows, open(os.path.join(EV, "pr_commits.json"), "w"), indent=1)
pr_index = {str(pr): {"date": rs[0]["date"], "shas": [r["sha"] for r in rs],
                      "subject": rs[0]["subject"]} for pr, rs in by_pr.items()}
json.dump(pr_index, open(os.path.join(EV, "pr_index.json"), "w"), indent=1)
print("pr_commits:", len(rows), "unique PRs:", len(by_pr))

# date span of PR-landed window
dates = sorted(r["date"] for r in rows)
print("window:", dates[0], "..", dates[-1])

# scope histogram for ledger
sc = collections.Counter(r["scope"] for r in rows if r["scope"])
print("top scopes:", sc.most_common(15))
