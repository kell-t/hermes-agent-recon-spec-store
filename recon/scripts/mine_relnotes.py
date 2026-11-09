#!/usr/bin/env python3
"""Split the in-tree release doc into per-version evidence/relnote_<ver>.txt
so drafts can cite `[relnote <ver>] "quote"` and audit_scenarios.py can
word-overlap-verify mechanically.

Idempotent: rewrites all relnote_*.txt each run. Header/version shapes come
from store_config.release_notes (header_regex, version_extract).

If the repo publishes via GitHub Releases instead, fetch the API to
evidence/releases.json ({tag, name, published_at, body} list) — the auditors
read both corpora.
"""
import glob
import os
import re

import common

cfg = common.load_config()
rn = cfg["release_notes"]
src = os.path.join(common.STORE, rn["source"])
out_dir = common.EV

text = open(src).read()
for f in glob.glob(os.path.join(out_dir, "relnote_*.txt")):
    os.remove(f)

parts = re.split(rn["header_regex"], text)
vrx = re.compile(rn.get("version_extract", r"^v?\d+\.\d+(\.\d+)?"))
count = 0
for i in range(1, len(parts) - 1, 2):
    header = parts[i].strip()
    body = parts[i + 1].strip()
    m = vrx.match(header.split(" - ")[0].strip())
    if not m:
        print("SKIP weird version header:", header)
        continue
    ver = m.group(0)
    if not ver.startswith("v"):
        ver = "v" + ver
    with open(os.path.join(out_dir, "relnote_%s.txt" % ver), "w") as fh:
        fh.write(header + "\n" + body + "\n")
    count += 1
print("wrote %d relnote files from %s" % (count, src))
