#!/usr/bin/env python3
"""Pass-2 G-01: mine commits after the (#NNNN)-ref window (author date > 2026-10-27)
WITHOUT the ref filter. Writes evidence/tail_commits.json; appends ref-bearing tail
commits into pr_commits.json/pr_index.json; appends clustered TAIL sections to bundles.
Clustering for the tail is SCOPE-FIRST (conventional-commit scope vs repo_config
included[].scopes), subject regex (G-04 tightened) as fallback, <=2 buckets/commit."""
import json, re, os, subprocess, collections

STORE = "/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent"
REPO = os.path.join(STORE, "repo")
EV = os.path.join(STORE, "recon", "evidence")
TAIL_AFTER = "2026-10-27"

conv = re.compile(r'^(feat|fix|refactor|perf|docs|test|chore|ci|revert|security|style|build)'
                  r'(?:\(([^)]*)\))?(!)?:\s*(.*)$', re.I)
prref = re.compile(r'\(#(\d+)\)\s*$')

out = subprocess.run(["git", "-C", REPO, "log", "--no-merges",
                      "--format=%H|%ad|%s", "--date=short"],
                     capture_output=True, text=True, check=True).stdout
tail = []
seen = set()
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
    tail.append({
        "sha": sha[:12], "date": date, "pr": (int(m.group(1)) if m else None),
        "subject": subj, "type": (c.group(1).lower() if c else "other"),
        "scope": (c.group(2) if c and c.group(2) else ""),
    })
tail.sort(key=lambda r: r["date"], reverse=True)
json.dump(tail, open(os.path.join(EV, "tail_commits.json"), "w"), indent=1)
print("tail commits (author date > %s): %d, with PR ref: %d" %
      (TAIL_AFTER, len(tail), sum(1 for r in tail if r["pr"])))

# merge ref-bearing tail commits into the PR corpus
pc_path = os.path.join(EV, "pr_commits.json")
pcs = json.load(open(pc_path))
known_shas = {r["sha"] for r in pcs}
pi_path = os.path.join(EV, "pr_index.json")
pidx = json.load(open(pi_path))
added = 0
for r in tail:
    if r["pr"] and r["sha"] not in known_shas:
        pcs.append(r); known_shas.add(r["sha"]); added += 1
        pidx.setdefault(str(r["pr"]), {"date": r["date"], "shas": [], "subject": r["subject"], "tail": True})["shas"].append(r["sha"])
json.dump(pcs, open(pc_path, "w"), indent=1)
json.dump(pidx, open(pi_path, "w"), indent=1)
print("appended to pr_commits.json:", added, "| corpus:", len(pcs), "| pr_index:", len(pidx))

# SCOPE-FIRST clustering for the tail
SCOPES = {
 "agent-turn-loop": {"agent", "compression"},
 "gateway-messaging": {"gateway", "telegram", "discord", "slack", "relay", "bot-mode",
                        "whatsapp", "signal", "matrix", "email-platform"},
 "sessions-state": {"state", "sessions"},
 "skills-system": {"skills", "curator"},
 "tools-toolsets": {"tools", "terminal", "browser"},
 "profiles-isolation": {"profiles", "isolation", "multiplex"},
 "cron-background": {"cron", "kanban", "scheduler"},
 "config-provider-models": {"config", "providers", "models", "auth"},
 "cli-surface": {"cli"},
 "delegation-orchestration": {"delegation", "subagent", "fleet"},
}
# G-04 tightened subject fallbacks (pass-1 over-matched \btools?\b and \bcli\b)
SUBJ = {
 "agent-turn-loop": r'compact|compress|prompt[- ]cach|turn[- ]loop|system prompt|cache[- ]break|token[- ]lock|run_agent|message[- ]flow',
 "gateway-messaging": r'gateway|telegram|discord|slack|whatsapp|signal\b|matrix|relay|bot[- ]mode|multiplex|platform adapter|adapter',
 "sessions-state": r'session|state db|hermes_state|history|resume|checkpoint|sqlite',
 "skills-system": r'skill|curator',
 "tools-toolsets": r'toolset|tool registry|check_fn|service-gated|function.call|tool call|tool result|tool_|toolsets',
 "profiles-isolation": r'profile|hermes_home|HERMES_HOME|isolation|multiplex|per-profile|profile scope',
 "cron-background": r'cron|schedul|job\b|kanban|ticker|background run',
 "config-provider-models": r'config|provider|model\b|models|\.env|api key|auth|oauth|anthropic|openai|base url',
 "cli-surface": r'slash command|\brepl\b|subcommand|cli_|hermes_cli|\bcli\b (?=flag|command|output|parser|prompt)',
 "delegation-orchestration": r'delegat|subagent|sub-agent|orchestr|child agent|parallel child',
}
comp = {k: re.compile(v, re.I) for k, v in SUBJ.items()}
tc = collections.defaultdict(list)
for r in tail:
    hits = [k for k, s in SCOPES.items() if r["scope"].lower() in s]
    if not hits:
        hits = [k for k, c in comp.items() if c.search(r["subject"])]
    for k in hits[:2]:
        tc[k].append(r)
json.dump(tc, open(os.path.join(EV, "tail_clusters.json"), "w"), indent=1)
for k, v in sorted(tc.items()):
    path = os.path.join(EV, "bundle_%s.txt" % k)
    body = open(path).read().rstrip("\n") if os.path.exists(path) else "# Bundle: %s\n" % k
    # drop any previous TAIL section (idempotent re-run)
    body = body.split("\n# ==== TAIL")[0]
    lines = ["", "# ==== TAIL APPEND (G-01): %d commits, author date > %s, no-ref included,"
             " scope-first clustering, newest first, capped 40 ====" % (len(v), TAIL_AFTER)]
    for r in v[:40]:
        ref = ("(#%d)" % r["pr"]) if r["pr"] else "(no-ref)"
        lines.append("%s %s [%s] %s" % (r["date"], ref, r["sha"], r["subject"]))
    open(path, "w").write(body + "\n" + "\n".join(lines) + "\n")
    print("bundle_%s TAIL: %d kept of %d" % (k, min(len(v), 40), len(v)))
print("tail uncategorized:", sum(1 for r in tail
      if r["scope"].lower() not in set().union(*SCOPES.values())
      and not any(c.search(r["subject"]) for c in comp.values())))
