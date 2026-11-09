#!/usr/bin/env python3
"""Phase 4: scripted tallies + anchor/PR audit of specs_draft/."""
import json, os, re, subprocess

STORE = "/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent"
DRAFTS = os.path.join(STORE, "specs_draft")
EV = os.path.join(STORE, "recon", "evidence")
REPO = os.path.join(STORE, "repo")

pr_index = set(json.load(open(os.path.join(EV, "pr_index.json"))).keys())
rel_text = open(os.path.join(EV, "releases.json")).read()
rel_prs = set(re.findall(r'#(\d+)', rel_text))
bundle_text = ""
for fn in os.listdir(EV):
    if fn.startswith("bundle_"):
        bundle_text += open(os.path.join(EV, fn)).read()
bundle_prs = set(re.findall(r'#(\d+)', bundle_text))

anchor_re = re.compile(r'`?([\w/\-]+\.(?:py|md|ts|yaml|json)):(\d+)`?')
total = {}
for fn in sorted(os.listdir(DRAFTS)):
    if not fn.endswith(".md"):
        continue
    text = open(os.path.join(DRAFTS, fn)).read()
    reqs = text.count("### Requirement:")
    ver = text.count("Status: VERIFIED")
    inf = text.count("Status: INFERRED")
    unv = text.count("Status: UNVERIFIED")
    # anchors with line numbers: verify file exists and line within range
    bad_anchor = []
    for f, ln in anchor_re.findall(text):
        p = os.path.join(REPO, f)
        if not os.path.exists(p):
            bad_anchor.append(f + ":" + ln + " MISSING-FILE")
        else:
            n = sum(1 for _ in open(p, errors="ignore"))
            if int(ln) > n:
                bad_anchor.append(f + ":" + ln + " LINE-OOB(%d)" % n)
    # PR citations
    cited = set(re.findall(r'pull/(\d+)', text))
    uncited = sorted(c for c in cited if c not in pr_index and c not in bundle_prs and c not in rel_prs)
    total[fn[:-3]] = dict(reqs=reqs, VERIFIED=ver, INFERRED=inf, UNVERIFIED=unv,
                          bad_anchor=bad_anchor, prs_offline=uncited)

tots = dict(reqs=0, VERIFIED=0, INFERRED=0, UNVERIFIED=0)
for cap, d in total.items():
    print("%-28s reqs=%-3d V=%-3d I=%-3d U=%-3d" % (cap, d["reqs"], d["VERIFIED"], d["INFERRED"], d["UNVERIFIED"]))
    if d["bad_anchor"]:
        print("   BAD ANCHORS:", d["bad_anchor"])
    if d["prs_offline"]:
        print("   PR-CITES-NOT-IN-EVIDENCE:", d["prs_offline"])
    for k in tots:
        tots[k] += d[k]
print("TOTAL", tots)
# header-count consistency (V+I+U == reqs?)
for cap, d in total.items():
    if d["VERIFIED"] + d["INFERRED"] + d["UNVERIFIED"] != d["reqs"]:
        print("STATUS-COUNT MISMATCH:", cap)
