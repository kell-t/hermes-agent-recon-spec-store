#!/usr/bin/env python3
"""Phase 4 scripted tally: requirement/status counts + scenario counts per
draft file. Children's self-reported numbers are hypotheses; this is the
tally that goes into the ledger's coverage table.
"""
import os
import re

import common

DRAFTS = common.DRAFTS
rows, tot = [], dict(reqs=0, V=0, I=0, U=0, grounded=0, derived=0)
for fn in sorted(os.listdir(DRAFTS)):
    if not fn.endswith(".md"):
        continue
    text = os.path.join(DRAFTS, fn)
    text = open(text).read()
    reqs = text.count("### Requirement:")
    v = text.count("Status: VERIFIED") + text.count("**Status**: VERIFIED")
    i = text.count("Status: INFERRED") + text.count("**Status**: INFERRED")
    u = text.count("Status: UNVERIFIED") + text.count("**Status**: UNVERIFIED")
    scen = len(re.findall(r"(?m)^#### Scenario:", text))
    derived = len(re.findall(r"(?m)SCENARIO-DEBT", text))
    grounded = scen - derived
    rows.append((fn[:-3], reqs, v, i, u, grounded))
    if v + i + u != reqs:
        print("STATUS-COUNT MISMATCH:", fn[:-3], v, i, u, "!=", reqs)
    tot["reqs"] += reqs
    tot["V"] += v
    tot["I"] += i
    tot["U"] += u
    tot["grounded"] += grounded
    tot["derived"] += derived

for cap, reqs, v, i, u, g in rows:
    print("%-28s reqs=%-3d V=%-3d I=%-3d U=%-3d grounded_scen=%-3d"
          % (cap, reqs, v, i, u, g))
pct = (100.0 * tot["V"] / tot["reqs"]) if tot["reqs"] else 0.0
print("TOTAL reqs=%d VERIFIED=%d (%.1f%%) INFERRED=%d UNVERIFIED=%d "
      "grounded_scen=%d derived=%d"
      % (tot["reqs"], tot["V"], pct, tot["I"], tot["U"],
         tot["grounded"], tot["derived"]))
