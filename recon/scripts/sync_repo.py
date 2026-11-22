#!/usr/bin/env python3
"""sync_repo.py — manage the store's persistent bare source cache at
<store>/.repo.

Spec: openspec/specs/repo-cache/spec.md (kit). The clone is a CACHE: clone
once (bare + blobless), keep it current with fetch. Every checkout of the
source is a NAMED WORKTREE under `<store>/.repo/wt/<branch>`, named after
the branch of this spec-store it serves (git keeps its own admin in
`.repo/worktrees/`; checkouts live in `.repo/wt/`). Never delete-and-
reclone in normal flow; never edit or commit inside the cache or worktrees.

Corruption recovery (spec) keeps ONE rolling undo slot: `sync_repo.py
--rebuild <url>` renames the existing cache to `.repo-old` (replacing any
previous `.repo-old`) BEFORE cloning fresh — a quick "undo button", not
forensics: the cache holds a public repo, so nothing demands preservation.
Work on the spec store ignores `.repo-old`. The tool keeps this policy
stricter than the spec's SHOULD: use it only for locally confirmed
corruption (git fsck); authentication or server errors (401/403, rate
limit, 5xx) are NEVER grounds — the failure is upstream, and normal sync
touches nothing then.

Usage:
  sync_repo.py <source-url> [--ref <tag|sha|branch>] [--wt NAME]
               [--dest DIR] [--rebuild [--relocate]]

--dest defaults to <store>/.repo (store root auto-detected like the other
kit scripts: from this file's location, override env RECON_STORE).
--dest exists for tool development/testing only — store work always uses
the default path (spec: one active clone per store).
--wt defaults to the store repo's current branch (fallback "main").

Behavior:
  - .repo absent, legacy <store>/repo present (same origin URL) -> rename,
    adopt (adopted caches may stay non-bare; worktrees attach the same
    way), continue as refresh.
  - .repo absent -> `git clone --bare --filter=blob:none`; refspec
    rewritten to mirror refs/remotes/origin/* (bare's default mirror maps
    to refs/heads/* and would leave no origin/* refs to resolve).
  - .repo present (bare or non-bare), same origin URL -> fetch --prune
    --tags; resolve ref strictly (refs/tags/, refs/remotes/origin/, bare
    ref/sha); worktree wt/<name>: `worktree add --detach` if absent, else
    `checkout --force --detach` + `clean -fdq` (cache is disposable).
  - .repo present, DIFFERENT origin URL -> refuse (exit 3), BEFORE any
    undo-slot rename: a wrong-URL --rebuild must never consume a healthy
    cache.
  - ref unresolvable after fetch -> exit 2, checkout untouched (pin law:
    never silently fall back to a different ref).
  - Ensures the store root .gitignore ignores `.repo/` and `.repo-old/`.
  - Mid-clone interruption needs no special handling: a clean git clone
    failure removes its directory; a hard-killed partial .git is completed
    by the next run's fetch + forced checkout (verified 2026-11-21).
  - --rebuild replaces the whole directory at --dest, including a husk
    without git metadata (clone killed before init completed), with the
    rename into the `.repo-old` slot.
  - Source identity is explicit: `origin` is never silently rewritten. A
    cache whose origin differs from the requested URL refuses (exit 3),
    refresh or rebuild alike; only a deliberate `--relocate` (valid only
    with --rebuild) bypasses the guard for an owner-instructed upstream
    move, still through the undo slot.
  - Move notices are ADVISORY: after a successful fetch the tool checks
    GitHub's redirect table (HEAD web probe; disable with
    RECON_MOVE_PROBE=0) and scans fetch stderr for GitHub's "This
    repository moved" notice; either hit prints `MOVE_NOTICE=<url>` for
    the agent to surface to the owner. It never rewrites origin, never
    triggers recovery, never changes the exit code; a probe that cannot
    run (offline, rate limit, non-GitHub origin) stays silent.

Prints machine-readable tail lines for ledger capture:
  DEST=<abs worktree path>  CACHE=<abs cache path>  HEAD=<full sha>
  [PREV=<full sha>]
Exit codes: 0 ok | 2 ref not found | 3 remote mismatch | 4 usage/env error
(usage errors exit 4, never argparse's default 2 — 2 belongs to the pin law).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from urllib import error as urlerror
from urllib import request as urlrequest


MOVED_RE = re.compile(
    r"This repository moved\. Please use the new location:\s*"
    r"(?:remote:\s*)?(\S+)")


class ArgParser(argparse.ArgumentParser):
    """Usage errors must not exit 2: 2 is reserved for the pin law."""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(4)


def store_root() -> str:
    try:
        from common import STORE  # kit layout: same directory
        return STORE
    except Exception:
        return os.getcwd()


LAST_STDERR = ""


def git(args, cwd=None, check=True):
    global LAST_STDERR
    r = subprocess.run(["git"] + args, cwd=cwd,
                       capture_output=True, text=True)
    LAST_STDERR = r.stderr or ""
    if check and r.returncode != 0:
        sys.stderr.write(f"git {' '.join(args)} failed: "
                         f"{r.stderr.strip() or r.stdout.strip()}\n")
        raise SystemExit(4)
    return r.stdout.strip()


def github_slug(url):
    """owner/repo for a GitHub URL (https or scp-form ssh); else None."""
    m = re.match(r"(?:https?://github\.com[:/]|git@github\.com:)"
                 r"([^/]+/[^/]+?)(?:\.git)?/?$", (url or ""), re.I)
    return m.group(1) if m else None


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # surface 301s as HTTPError; do not follow


def move_notice(source_url, fetch_stderr=""):
    """ADVISORY ONLY (spec): canonical URL when GitHub's redirect table
    knows the repo moved, else None. Two channels: GitHub's own
    'This repository moved' notice on fetch stderr (historical; silent on
    today's read paths), and a HEAD probe of the web endpoint (301 ->
    canonical). Never raises, never acts — remediation is the owner's via
    --rebuild --relocate. Set RECON_MOVE_PROBE=0 to skip the probe."""
    m = MOVED_RE.search(fetch_stderr or "")
    if m:
        return m.group(1)
    slug = github_slug(source_url)
    if not slug or os.environ.get("RECON_MOVE_PROBE") == "0":
        return None
    try:
        req = urlrequest.Request(f"https://github.com/{slug}",
                                 method="HEAD",
                                 headers={"User-Agent":
                                          "recon-spec-store-kit"})
        urlrequest.build_opener(_NoRedirect).open(req, timeout=10)
    except urlerror.HTTPError as e:
        if e.code in (301, 302, 307, 308):
            new = github_slug(e.headers.get("Location", ""))
            if new and new.lower() != slug.lower():
                return e.headers.get("Location")
    except Exception:
        return None  # offline / rate-limited: the advisory stays silent
    return None


def is_cache(d):
    """Bare or non-bare git repository directory."""
    return (os.path.isdir(os.path.join(d, ".git"))
            or (os.path.isfile(os.path.join(d, "HEAD"))
                and os.path.isdir(os.path.join(d, "objects"))))


def origin_url(dest):
    return git(["-C", dest, "remote", "get-url", "origin"], check=False)


def url_eq(a, b):
    norm = lambda u: (u or "").rstrip("/").removesuffix(".git").lower()
    return norm(a) == norm(b)


def store_branch():
    """Current branch of the spec-store repo (names the default worktree)."""
    b = git(["-C", store_root(), "branch", "--show-current"], check=False)
    return b or "main"


def resolve_ref(dest, ref):
    """Strict resolution: tag -> origin/<ref> -> bare ref (full/abbrev sha).
    origin/ is preferred over a possibly-stale local ref (worktrees detach;
    cache refs are read-only). Returns full sha or None."""
    candidates = [f"refs/tags/{ref}", f"refs/remotes/origin/{ref}", ref]
    for c in candidates:
        r = git(["-C", dest, "rev-parse", "--verify", "--quiet",
                 f"{c}^{{commit}}"], check=False)
        if r:
            return r
    return None


def ensure_gitignore(dest):
    """Keep the cache AND its undo slot out of git: neither the cache dir
    nor `<cache>-old` may ever be committed."""
    parent = os.path.dirname(os.path.abspath(dest))
    name = os.path.basename(os.path.abspath(dest))
    gi = os.path.join(parent, ".gitignore")
    need = [f"{name}/", f"{name}-old/"]
    text = open(gi).read() if os.path.exists(gi) else ""
    have = {l.strip() for l in text.splitlines()}
    missing = [l for l in need if l not in have and f"/{l}" not in have]
    if not missing:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    text += ("\n# Persistent source cache + recovery undo slot"
             " (recon-spec-store-kit cache;\n"
             "# see recon/openspec/specs/repo-cache).\n"
             + "".join(l + "\n" for l in missing))
    with open(gi, "w") as f:
        f.write(text)
    print(f"gitignore: added {missing} to {gi}")


def stash_undo(dest):
    """Rolling ONE-slot undo (owner ruling 2026-11-22): rename the current
    cache to `<dest>-old`, REPLACING any previous slot. The copy is a
    quick undo button for a public-repo cache, not forensics. The one
    destructive step in recovery consumes only the PREVIOUS undo slot,
    never the active cache: a crash between replace and rename loses at
    worst the older undo copy."""
    old = dest + "-old"
    if os.path.isdir(old):
        shutil.rmtree(old)
        print(f"undo slot rolls: replaced previous {old}")
    shutil.move(dest, old)
    print(f"undo slot: {dest} -> {old}")


def main():
    ap = ArgParser(description="manage the store's persistent bare source"
                               " cache (see module docstring)")
    ap.add_argument("url", help="source repo URL")
    ap.add_argument("--ref", default=None,
                    help="tag|sha|branch to check out (strict; detached)")
    ap.add_argument("--wt", default=None,
                    help="worktree name (default: store's current branch)")
    ap.add_argument("--dest", default=None,
                    help="cache dir (default <store>/.repo;"
                         " dev/testing override only)")
    ap.add_argument("--rebuild", action="store_true",
                    help="recovery: rename the existing cache (husks"
                         " included) into the .repo-old undo slot (slot"
                         " rolls), then clone fresh; auth/server errors"
                         " are never grounds")
    ap.add_argument("--relocate", action="store_true",
                    help="with --rebuild only: owner-instructed source"
                         " URL change; deliberately skips the"
                         " origin-mismatch guard")
    args = ap.parse_args()
    if args.relocate and not args.rebuild:
        ap.error("--relocate requires --rebuild")

    dest = args.dest or os.path.join(store_root(), ".repo")
    legacy = os.path.join(os.path.dirname(os.path.abspath(dest))
                          if args.dest else store_root(), "repo")
    wt = os.path.join(dest, "wt", args.wt or store_branch())

    # Wrong-URL --rebuild is refused BEFORE touching anything: recovery
    # may never consume a healthy cache on an upstream/parameter problem.
    # Only the deliberate --relocate (owner-instructed move) skips this.
    if args.rebuild and not args.relocate and is_cache(dest) \
            and not url_eq(origin_url(dest), args.url):
        sys.stderr.write(
            f"{dest} origin '{origin_url(dest)}' != requested "
            f"'{args.url}'; refusing rebuild of a cache that tracks a "
            f"different source.\n")
        raise SystemExit(3)
    if args.rebuild and os.path.isdir(dest):
        stash_undo(dest)
    elif args.rebuild:
        print("--rebuild: nothing at --dest to stash; cloning fresh")

    prev = ""
    if not is_cache(dest):
        if os.path.isdir(os.path.join(legacy, ".git")) and not args.rebuild:
            if not url_eq(origin_url(legacy), args.url):
                sys.stderr.write(
                    f"legacy {legacy} origin '{origin_url(legacy)}' != "
                    f"requested '{args.url}'; refusing to adopt.\n")
                raise SystemExit(3)
            shutil.move(legacy, dest)
            print(f"adopted legacy clone: {legacy} -> {dest}")
        else:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            print(f"cloning (bare, blobless) {args.url} -> {dest}")
            git(["clone", "--bare", "--filter=blob:none", args.url, dest])
            git(["-C", dest, "config", "remote.origin.fetch",
                 "+refs/heads/*:refs/remotes/origin/*"])
    else:
        if not url_eq(origin_url(dest), args.url):
            sys.stderr.write(
                f"{dest} origin '{origin_url(dest)}' != requested "
                f"'{args.url}'; refusing to re-point an existing cache.\n")
            raise SystemExit(3)

    # refresh first (requirement: cache up to date before work; and a fresh
    # ref is usually only known after fetch)
    git(["-C", dest, "fetch", "--prune", "--tags", "origin"])

    # advisory move notice (never acts, never fails the sync)
    notice = move_notice(args.url, LAST_STDERR)
    if notice:
        print(f"MOVE_NOTICE={notice}")
        print("MOVE_ADVISORY: upstream source moved; origin untouched and"
              " no recovery triggered — owner may direct"
              " `--rebuild --relocate <new-url>` (update the recorded"
              " source URL + ledger on doing so).")

    wt_exists = os.path.exists(os.path.join(wt, ".git"))
    if args.ref:
        sha = resolve_ref(dest, args.ref)
        if not sha:
            sys.stderr.write(
                f"ref '{args.ref}' not resolvable in {dest} even after "
                f"fetch; checkout left untouched (pin law).\n")
            raise SystemExit(2)
    elif wt_exists:
        sha = None  # no ref given + worktree exists: leave it where it is
    else:
        sha = resolve_ref(dest, "main") or resolve_ref(dest, "HEAD")
        if not sha:
            sys.stderr.write("no --ref and neither origin HEAD nor "
                             "'main' resolves in the cache.\n")
            raise SystemExit(2)

    if wt_exists:
        prev = git(["-C", wt, "rev-parse", "--verify", "--quiet", "HEAD"],
                   check=False)  # empty on unborn HEAD (aborted state)
        if sha:
            git(["-C", wt, "checkout", "--force", "--detach", sha])
            git(["-C", wt, "clean", "-fdq"], check=False)
        head = sha or prev
    else:
        os.makedirs(os.path.join(dest, "wt"), exist_ok=True)
        git(["-C", dest, "worktree", "add", "--detach", wt, sha])
        head = sha

    ensure_gitignore(dest)
    print(f"DEST={os.path.abspath(wt)} CACHE={os.path.abspath(dest)}"
          f" HEAD={head}" + (f" PREV={prev}" if prev and prev != head else ""))


if __name__ == "__main__":
    main()
