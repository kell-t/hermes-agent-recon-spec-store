#!/usr/bin/env python3
"""common.py — shared store-config loading and audit primitives.

Copy into <store>/recon/scripts/ alongside store_config.yaml. All toolkit
scripts import this module; keep cite grammar in sync with
templates/SCENARIO_PASS_TEMPLATE.md (the templates show what children write;
this module defines what the gate accepts — divergence manufactures
wave-wide false positives).
"""
import json
import os
import re
import subprocess

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
STORE = os.environ.get(
    "RECON_STORE",
    os.path.abspath(os.path.join(SCRIPTS_DIR, os.pardir, os.pardir)))
DRAFTS = os.path.join(STORE, "specs_draft")
EV = os.path.join(STORE, "recon", "evidence")
REPO = os.path.join(STORE, "repo")

_DEFAULTS = {
    "pin_sha": "",
    "pr_ref_mode": "pr-ref",          # pr-ref | ref-free
    "capabilities": {},               # cap -> {subject_regex, scopes, code}
    "docs": [],                       # normative docs to copy into evidence/docs
    "test_files": [],                 # for Tier-C inventory
    "release_notes": {"mode": "relnote_files",
                      "source": "recon/evidence/docs/RELEASE.md",
                      "header_regex": r"(?m)^## (v[0-9][^\n]*)$"},
    "anchor_extensions": ["py", "md", "ts", "tsx", "yaml", "yml", "json",
                          "sh", "toml"],
    "runtime_artifacts": [],          # data files behavior writes, never in-repo
    "anchor_hint_check": "strict",    # strict | false (stores graduate to strict;
                                      # YAML parses bare `off` as False)
    "tail_after": None,               # author-date the ref window stops at
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    """Load recon/scripts/store_config.yaml (YAML-lite: json is a subset, so
    we accept either real YAML via PyYAML if installed, or a JSON file named
    .json alongside)."""
    cfg = dict(_DEFAULTS)
    path = os.path.join(SCRIPTS_DIR, "store_config.yaml")
    if os.path.exists(path):
        try:
            import yaml  # type: ignore
            user = yaml.safe_load(open(path)) or {}
            return _deep_merge(cfg, user)
        except ImportError:
            jpath = os.path.join(SCRIPTS_DIR, "store_config.json")
            if os.path.exists(jpath):
                return _deep_merge(cfg, json.load(open(jpath)))
            raise SystemExit(
                "store_config.yaml present but PyYAML is not installed; "
                "pip install pyyaml, or keep a store_config.json twin.")
    else:
        jpath = os.path.join(SCRIPTS_DIR, "store_config.json")
        if os.path.exists(jpath):
            cfg = _deep_merge(cfg, json.load(open(jpath)))
    if not cfg["pin_sha"]:
        raise SystemExit("store_config: pin_sha is required")
    return cfg


def corpus(name, default=None):
    """Load an evidence JSON corpus if present (stores differ in which exist)."""
    p = os.path.join(EV, name)
    return json.load(open(p)) if os.path.exists(p) else default


# ---------- shared audit primitives (validated shapes) ----------

STOP = set((
    "a an the and or but if then that this these those of to in on for with "
    "as at by from is are was were be been being it its into over under not "
    "no nor so than too very can could will would shall may might must do "
    "does did done have has had having you your we our they their he she i "
    "when while before after also more most other some any each per via"
).split())


def tokens(s):
    return [t for t in re.findall(r"[A-Za-z0-9_]{3,}", s.lower())
            if t not in STOP]


def token_overlap(quote, body):
    """Substance-match: fraction of the quote's non-stopword tokens found in
    the body. The gate threshold in practice is 0.6."""
    qt = tokens(quote)
    if not qt:
        return 1.0
    bt = set(tokens(body))
    return sum(1 for t in qt if t in bt) / len(qt)


class PinTree:
    """Read-only view of the source clone at the pin, with caches."""

    def __init__(self, repo=REPO):
        self.repo = repo
        self._files = {}
        self._shas = {}
        self._names = None

    def lines(self, rel):
        if rel not in self._files:
            try:
                with open(os.path.join(self.repo, rel), errors="ignore") as fh:
                    self._files[rel] = fh.read().splitlines()
            except OSError:
                self._files[rel] = None
        return self._files[rel]

    def exists(self, rel):
        return self.lines(rel) is not None

    def sha_resolves(self, tok):
        if tok not in self._shas:
            r = subprocess.run(
                ["git", "-C", self.repo, "cat-file", "-e",
                 tok + "^{commit}"], capture_output=True)
            self._shas[tok] = (r.returncode == 0)
        return self._shas[tok]

    def _name_index(self):
        """basename -> [repo-relative paths] (walk-cached, deterministic)."""
        if self._names is None:
            idx = {}
            for root, dirs, files in os.walk(self.repo):
                dirs[:] = sorted(d for d in dirs if d not in (
                    ".git", "node_modules", "__pycache__", ".venv",
                    "dist", "build"))
                for f in sorted(files):
                    rel = os.path.relpath(os.path.join(root, f), self.repo)
                    idx.setdefault(f, []).append(rel)
            self._names = idx
        return self._names

    def find_suffix(self, rel):
        """All repo paths equal to `rel` or ending with '/' + `rel`
        (drafts sometimes cite partial repo-relative paths)."""
        rel = rel.rstrip("/")
        cands = self._name_index().get(os.path.basename(rel), [])
        return [c for c in cands if c == rel or c.endswith("/" + rel)]

    def resolve_bare_path(self, name):
        """BARE-PATH rule: EXISTENCE-based, not slash-based. A name is fine
        when <repo>/<name> exists, or it occurs (as full or suffix match)
        somewhere in the tree — drafts cite subdir files by basename or
        partial path. Flag only names that resolve nowhere."""
        if self.exists(name):
            return name
        hits = self.find_suffix(name)
        return hits[0] if hits else None


def relnote_bodies(cfg):
    """Release-note corpus, dual-mode: per-version relnote_<ver>.txt files,
    or releases.json (GitHub API). Returns {version-tag: body}, including
    name-carried aliases (tag may be date-based while the release NAME
    carries the semver, e.g. tag v2026.3.30 ships "v0.6.0")."""
    bodies = {}
    for p in os.listdir(EV) if os.path.isdir(EV) else []:
        if p.startswith("relnote_") and p.endswith(".txt"):
            bodies[p[len("relnote_"):-len(".txt")]] = \
                open(os.path.join(EV, p)).read()
    rels = corpus("releases.json")
    if rels:
        by_tag = {r["tag"]: r.get("body", "") for r in rels}
        bodies.update(by_tag)
        for r in rels:
            for v in re.findall(r"v?\d+\.\d+\.\d+", r.get("name", "")):
                key = v if v.startswith("v") else "v" + v
                bodies.setdefault(key, by_tag[r["tag"]])
                bodies.setdefault(r["tag"] + " (" + key + ")", by_tag[r["tag"]])
    return bodies


def verified_numbers():
    """{number: {...}} allowlist of API-verified GitHub numbers
    (issue-or-PR kind verified via GET /repos/<org>/<repo>/issues/NNNN).
    Accepts the canonical verified_numbers.json or a legacy
    verified_prs.json ({number: title} shape)."""
    vn = corpus("verified_numbers.json")
    if vn:
        return vn
    legacy = corpus("verified_prs.json", {})
    return {k: (v if isinstance(v, dict) else
                {"kind": "migrated", "title": str(v)})
            for k, v in legacy.items()}


# ---- Source-line cite parsing -------------------------------------------
# A Source: line is one or more cites joined by ';' (outside quotes and
# backticks). Accepted cite shapes (dialect law: keep templates in sync):
#   [relnote <ver>] "quote" ["quote" ...]
#   doc: <path>[:line] [(annotation)] [§ section [—]] "quote" [/ "quote"...]
#   doc: <path> § section                    (quoteless: section presence)
#   test: <path>::[Class::]method            (bare path::rest continues a
#                                             preceding test: prefix)
#   free prose carrying `file:line` anchors  (anchor existence checked)
def split_cites(line):
    """Split a Source line on ';' outside \"...\" and `...` spans."""
    segs, cur, quote, bt = [], "", False, False
    for ch in line:
        if ch == '"' and not bt:
            quote = not quote
        elif ch == "`" and not quote:
            bt = not bt
        if ch == ";" and not quote and not bt:
            segs.append(cur)
            cur = ""
        else:
            cur += ch
    segs.append(cur)
    return [s.strip() for s in segs if s.strip()]


def _mk_test(path, rest):
    """test: cite -> {kind, path, segs}; '::' or ',' separate segments;
    a trailing ' (' / ' —' annotation (possibly unbalanced) ends the
    path grammar — identifiers never contain whitespace."""
    head = re.split(r"\s+[\(—]", rest.strip(), 1)[0]
    return {"kind": "test", "path": path,
            "segs": [t for t in re.split(r"::|,\s+", head) if t]}


def parse_source(line):
    """-> list of cite dicts: {kind, ...}. Unrecognized segments yield
    {'kind': 'other', 'text': seg} for the caller to flag or tolerate."""
    cites = []
    for seg in split_cites(line):
        m = re.match(r"\[relnote ([^\]]+)\]\s*(.*)$", seg, re.S)
        if m:
            cites.append({"kind": "relnote",
                          "ver": re.sub(r"\s+", " ", m.group(1).strip()),
                          "quotes": re.findall(r'"([^"]+)"', seg)})
            continue
        m = re.match(r"doc:\s+(\S+)\s*(.*)$", seg, re.S)
        if m:
            raw = m.group(1)
            # continuation anchors like ` + :1 (module docstring)` are
            # additional line pointers, not section text
            rest = re.sub(r"\+\s*:\d+(?:-\d+)?(?:\s*\([^)]*\))?", " ",
                          m.group(2))
            path = re.sub(r"[:.,]+$", "", raw)
            lm = re.search(r":(\d+)(?:-(\d+))?$", path)
            path = re.sub(r":\d+(?:-\d+)?$", "", path)
            cites.append({"kind": "doc", "path": path,
                          "lines": (int(lm.group(1)),
                                    int(lm.group(2) or lm.group(1)))
                                   if lm else None,
                          "quotes": re.findall(r'"([^"]+)"', rest),
                          "section": re.sub(r"\([^)]*\)", " ",
                                            rest.split('"')[0]).strip(" —§/")})
            continue
        m = re.match(r"code string:\s*(\S+?):(\d+)", seg)
        if m:
            cites.append({"kind": "code", "path": m.group(1),
                          "line": int(m.group(2)),
                          "quotes": re.findall(r'"([^"]+)"', seg)})
            continue
        m = re.match(r"(?:test:\s*)?([^\s:;]+)::(.*)$", seg)
        if m and ("/" in m.group(1) or "." in m.group(1)):
            # strip quoted prose and (...) annotations first: method/class
            # names never live inside them, and their words must not act
            # as connectors. Remaining grammar: '::' or ',' separate
            # segments; ' and ' joins cites (`X::m and ::m2`, `X::m and Y::m`)
            skel = re.sub(r'"[^"]*"', " ", m.group(2))
            skel = re.sub(r"\([^)]*\)", " ", skel)
            parts = re.split(r"\s+and\s+", skel.strip())
            cites.append(_mk_test(m.group(1), parts[0]))
            for p in parts[1:]:
                pm = re.match(r"([^\s:;]+)::(.+)$", p)
                if pm and ("/" in pm.group(1) or "." in pm.group(1)):
                    cites.append(_mk_test(pm.group(1), pm.group(2)))
                elif p.startswith("::"):
                    cites[-1]["segs"] += [t.strip(" ,;.")
                                         for t in re.split(r"::|,\s+", p)
                                         if t.strip(" ,;.")]
                elif p and ("/" in p or "." in p):
                    cites.append(_mk_test(p, ""))   # existence-only cite
            continue
        if seg.startswith("::") and cites and cites[-1]["kind"] == "test":
            # bare `::method` continues the previous test cite's class
            cites[-1]["segs"] += [x for x in seg.split("::") if x]
            continue
        if seg.startswith('"') and cites and cites[-1]["kind"] in (
                "doc", "relnote"):
            cites[-1]["quotes"] += re.findall(r'"([^"]+)"', seg)
            continue
        anchors = re.findall(r"`([^`\s]+):(\d+)`", seg)
        if anchors:
            cites.append({"kind": "anchor",
                          "anchors": [(f, int(l)) for f, l in anchors]})
            continue
        cites.append({"kind": "other", "text": seg})
    return cites
