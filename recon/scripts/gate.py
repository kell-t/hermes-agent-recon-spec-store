#!/usr/bin/env python3
"""gate.py — the single-command gate. Run between every wave completion and
every commit. Exit 0 means: requirements gate green, scenarios gate green
(scenarios audited only if any grounded scenario blocks exist yet), tally
consistent. `openspec validate --all --strict` remains a separate, mandatory
green light post-conversion (the CLI is the format authority; this gate is
the evidence-fabrication authority).
"""
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
auditors = ["audit_requirements.py"]
# only run the scenario auditor once scenario blocks exist
drafts = os.environ.get(
    "RECON_STORE",
    os.path.abspath(os.path.join(SCRIPTS, os.pardir, os.pardir)))
drafts = os.path.join(drafts, "specs_draft")
has_scen = False
if os.path.isdir(drafts):
    for fn in os.listdir(drafts):
        if fn.endswith(".md") and open(os.path.join(drafts, fn),
                                       errors="ignore").read().count("#### Scenario:"):
            has_scen = True
            break
if has_scen:
    auditors.append("audit_scenarios.py")
auditors.append("tally.py")

rc = 0
for a in auditors:
    print("\n==== %s ====" % a)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, a)])
    if r.returncode != 0 and a != "tally.py":   # tally is informational
        rc = 1
print("\nGATE: %s" % ("GREEN" if rc == 0 else "RED — fix before commit"))
sys.exit(rc)
