#!/usr/bin/env python3
"""Merge release notes, repo meta, build clusters + bundles."""
import json, re, os, subprocess, collections

STORE = "/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent"
EV = os.path.join(STORE, "recon", "evidence")

# releases
rels = json.load(open("/tmp/rel_p1.json"))
slim = [{"tag": r["tag_name"], "name": r.get("name") or "",
         "published_at": (r.get("published_at") or "")[:10],
         "body": r.get("body") or ""} for r in rels]
json.dump(slim, open(os.path.join(EV, "releases.json"), "w"), indent=1)
print("releases:", len(slim), "with body:", sum(1 for r in slim if len(r["body"]) > 200))
stable = [r["tag"] for r in slim if re.match(r'^v\d+\.\d+\.\d+$', r["tag"])]
print("stable tags:", len(stable), stable[:5], "...", stable[-3:] if len(stable) > 5 else "")

# clusters (from repo_config.yaml keyword map — duplicated here deliberately for speed)
KW = {
 "agent-turn-loop": r'compact|compress|prompt[- ]cach|turn[- ]loop|system prompt|cache[- ]break|token[- ]lock|run_agent|message[- ]flow',
 "gateway-messaging": r'gateway|telegram|discord|slack|whatsapp|signal\b|matrix|relay|bot[- ]mode|multiplex|platform adapter|adapter',
 "sessions-state": r'session|state db|hermes_state|history|resume|checkpoint|sqlite',
 "skills-system": r'skill|curator',
 "tools-toolsets": r'\btools?\b|toolset|registry|check_fn|service-gated|function.call|tool call',
 "profiles-isolation": r'profile|hermes_home|HERMES_HOME|isolation|multiplex|per-profile|profile scope',
 "cron-background": r'cron|schedul|job\b|kanban|ticker|background run',
 "config-provider-models": r'config|provider|model\b|models|\.env|api key|auth|oauth|anthropic|openai|base url',
 "cli-surface": r'\bcli\b|slash command|repl|hermes |subcommand|mixin|cli_',
 "delegation-orchestration": r'delegat|subagent|sub-agent|fleet|orchestr|child agent|parallel',
}
rows = json.load(open(os.path.join(EV, "pr_commits.json")))
comp = {k: re.compile(v, re.I) for k, v in KW.items()}
clusters = collections.defaultdict(list)
for r in rows:
    hits = [k for k, c in comp.items() if c.search(r["subject"])]
    for k in hits[:2]:
        clusters[k].append(r)
json.dump({k: v for k, v in clusters.items()}, open(os.path.join(EV, "clusters.json"), "w"), indent=1)
for k, v in sorted(clusters.items()):
    v.sort(key=lambda r: r["date"], reverse=True)
    lines = ["# Bundle: %s — %d PR-landed commits (window %s..%s), newest first, capped at 60" %
             (k, len(v), min(x["date"] for x in v), max(x["date"] for x in v)),
             "# Clusters are a STARTING PARTITION, not truth; reject misfiled items.", ""]
    for r in v[:60]:
        lines.append("%s (#%d) [%s] %s" % (r["date"], r["pr"], r["sha"], r["subject"]))
    open(os.path.join(EV, "bundle_%s.txt" % k.replace("-", "-")), "w").write("\n".join(lines) + "\n")
    print("bundle_%s: %d (%d kept)" % (k, len(v), min(len(v), 60)))
print("uncategorized commits:", sum(1 for r in rows if not any(c.search(r["subject"]) for c in comp.values())))
