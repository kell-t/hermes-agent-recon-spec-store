import json, re, sys
d = json.load(open('/opt/data/agent-github-spec-store/github/NousResearch/hermes-agent/recon/evidence/releases.json'))
pat = sys.argv[1]
rx = re.compile(pat, re.I)
for rel in d:
    body = rel['body']
    lines = body.split('\n')
    for i, ln in enumerate(lines):
        if rx.search(ln):
            print(f"--- {rel['tag']} ---")
            print(ln.strip()[:400])
