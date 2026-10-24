#!/usr/bin/env python3
"""Bump hermes-agent-desktop-bin to the latest upstream release.

Three modes:
  * default (dry run): report what a bump would change, write nothing.
  * --pr: create branch + commit (PKGBUILD, aur/PKGBUILD, aur/.SRCINFO),
    push it and open an auto-merge PR. Never commits to main directly.
  * --sync-sums: only refresh the checksums of the local source files
    (patches, launcher, tests) in PKGBUILD after editing one of them.

Exits 0 without changes when PKGBUILD already tracks the latest upstream tag.
Requires: gh (GH_TOKEN + GH_REPO env), makepkg available for .SRCINFO regen,
vercmp (pacman) for the version order. UPSTREAM_API_TOKEN, when set,
authenticates the GitHub API reads.
Must not run as root: makepkg refuses to run as root, so the container job
runs this script through runuser as an unprivileged user.
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request

REPO = "NousResearch/hermes-agent"
SHA_RE = re.compile(r"^sha256sums=\('([0-9a-f]{64})'", re.M)


def api(path: str):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "hermes-desktop-arch-builder"}
    # Unauthenticated requests share a 60/hour limit per runner IP and fail
    # with "HTTP Error 403: rate limit exceeded" on busy hosted runners.
    token = os.environ.get("UPSTREAM_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(url: str, timeout: int = 600) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def vercmp(a: str, b: str) -> int:
    """pacman's version order, the one users' updates follow (<0, 0, >0)."""
    r = run(["vercmp", a, b])
    if r.returncode != 0:
        sys.exit(f"vercmp {a} {b} failed: {r.stderr.strip()}")
    return int(r.stdout)


def next_pkgrel(version: str, cur_version: str, cur_pkgrel: str) -> int:
    """pkgrel for a new upstream tag that builds `version`.

    A new version starts at 1. A new tag with the same version (upstream
    re-tagged a release) needs pkgrel+1: with pkgrel=1 again, the release tag
    v<pkgver>-1 already exists, the release job skips and the new build never
    reaches the AUR. An older version means the release name was misparsed or
    upstream moved "latest" back; publishing it would downgrade users.
    """
    order = vercmp(version, cur_version)
    if order > 0:
        return 1
    if order < 0:
        sys.exit(f"upstream version {version} is older than PKGBUILD pkgver "
                 f"{cur_version}; refusing to downgrade (check the release name)")
    if not cur_pkgrel.isdigit():
        sys.exit(f"cannot increment non-integer pkgrel {cur_pkgrel!r}")
    return int(cur_pkgrel) + 1


def edit_pkgbuild(path: str, tag: str, version: str, commit: str, checksum: str,
                  pkgrel: int):
    """Edit the GitHub build PKGBUILD (has _pkgver_tag/_commit)."""
    pkg = open(path).read()
    pkg = re.sub(r"(?m)^_pkgver_tag=.*$", f"_pkgver_tag={tag}", pkg)
    pkg = re.sub(r"(?m)^_commit=.*$", f"_commit={commit}", pkg)
    pkg = re.sub(r"(?m)^pkgver=.*$", f"pkgver={version}", pkg)
    pkg = re.sub(r"(?m)^pkgrel=.*$", f"pkgrel={pkgrel}", pkg)
    # The pattern here used to be `sha256sums=\('\('…`, which can never match:
    # the substitution silently did nothing and the build then failed at makepkg
    # with "Validating source files with sha256sums ... FAILED" because the
    # previous release's checksum was still in the PKGBUILD.
    pkg = SHA_RE.sub(f"sha256sums=('{checksum}'", pkg)
    # Fail loudly if any field stopped matching, instead of shipping the old value.
    for field in (f"_pkgver_tag={tag}", f"_commit={commit}", f"pkgver={version}",
                  f"pkgrel={pkgrel}", f"sha256sums=('{checksum}'"):
        if not starts_line(pkg, field):
            sys.exit(f"failed to write {field!r} into {path}")
    open(path, "w").write(pkg)


def starts_line(text: str, prefix: str) -> bool:
    """Whether a line starts with prefix (a plain substring test would also
    accept it inside another assignment, e.g. _commit= in _upstream_commit=)."""
    return re.search(r"(?m)^" + re.escape(prefix), text) is not None


def sync_local_source_sums(path: str) -> list[str]:
    """Refresh the sha256sums entries of LOCAL files in source=() (the patches).

    The bump only maintains the tarball checksum. Editing a patch otherwise
    leaves its sum stale and the build dies much later at "Validating source
    files with sha256sums ... <patch> ... FAILED".
    """
    pkg = open(path).read()
    src = re.search(r"(?ms)^source=\((.*?)^\)", pkg)
    sums = re.search(r"(?ms)^sha256sums=\((.*?)\)[ \t]*$", pkg)
    if not src or not sums:
        sys.exit(f"cannot locate source=/sha256sums= in {path}")
    entries = [e.strip().strip("'\"")
               for e in re.split(r"\s+", src.group(1).strip()) if e.strip()]
    old = re.findall(r"'([0-9a-f]{64})'", sums.group(1))
    if len(entries) != len(old):
        sys.exit(f"{path}: {len(entries)} source entries but {len(old)} checksums")
    base = os.path.dirname(os.path.abspath(path))
    block = sums.group(1)
    changed = []
    for entry, old_sum in zip(entries, old):
        if "://" in entry or "::" in entry:
            continue                     # remote source, handled by the bump
        if not os.path.isfile(os.path.join(base, entry)):
            sys.exit(f"{path}: local source {entry!r} does not exist")
        new_sum = hashlib.sha256(open(os.path.join(base, entry), "rb").read()).hexdigest()
        if new_sum != old_sum:
            # A hash is as long as any other hash, so replacing it in place
            # keeps the PKGBUILD layout (one sum per line, indent) intact.
            block = block.replace(old_sum, new_sum, 1)
            changed.append(f"{entry}: {old_sum[:8]}… -> {new_sum[:8]}…")
    if changed:
        open(path, "w").write(pkg[:sums.start(1)] + block + pkg[sums.end(1):])
    return changed


def edit_aur_pkgbuild(path: str, version: str, pkgrel: int):
    """Edit the AUR wrapper PKGBUILD (no _pkgver_tag/_commit; source URL is
    variable-driven and follows pkgver/pkgrel automatically).

    Deliberately does NOT touch sha256sums: the wrapper's source is the
    release ARTIFACT, whose sha only exists AFTER the CI build. The
    post-release sync job computes the real artifact sha and injects it —
    writing the upstream source-tarball sha here would break `yay -S`
    checksums on the first automated bump."""
    pkg = open(path).read()
    pkg = re.sub(r"(?m)^pkgver=.*$", f"pkgver={version}", pkg)
    pkg = re.sub(r"(?m)^pkgrel=.*$", f"pkgrel={pkgrel}", pkg)
    for field in (f"pkgver={version}", f"pkgrel={pkgrel}"):
        if not starts_line(pkg, field):
            sys.exit(f"failed to write {field!r} into {path}")
    open(path, "w").write(pkg)


def require_non_root():
    """makepkg refuses to run as root — fail before anything is written."""
    if os.geteuid() == 0:
        sys.exit(
            "refusing to run as root: makepkg (used to regenerate aur/.SRCINFO) "
            "will not run as root. Run this script as an unprivileged user — "
            "see the 'bump' job in .github/workflows/build.yml."
        )


def printsrcinfo(pkg_dir: str) -> str:
    require_non_root()
    r = run(["makepkg", "--printsrcinfo"], cwd=pkg_dir)
    if r.returncode != 0:
        print("makepkg --printsrcinfo failed:", r.stderr)
        sys.exit(1)
    return r.stdout


def regen_srcinfo(aur_dir: str):
    srcinfo = printsrcinfo(aur_dir)
    with open(os.path.join(aur_dir, ".SRCINFO"), "w") as f:
        f.write(srcinfo)


ELECTRON_VAR_RE = re.compile(r"""(?m)^_electron=['"]?electron(\d+)\b""")
ARCH_SEARCH = "https://archlinux.org/packages/search/json/?name="


def locked_electron(tarball: bytes) -> str:
    """The Electron version upstream's lockfile installs for apps/desktop,
    the one prepare() compares with the system runtime."""
    with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
        member = next(m for m in tar
                      if m.name.count("/") == 1 and m.name.endswith("/package-lock.json"))
        packages = json.load(tar.extractfile(member))["packages"]
    for path in ("apps/desktop/node_modules/electron", "node_modules/electron"):
        if path in packages:
            return packages[path]["version"]
    raise KeyError("package-lock.json installs no electron")


def electron_lag(tag: str, tarball: bytes) -> list[str]:
    """Report when upstream's desktop app at tag locks a newer Electron major
    than _electron in PKGBUILD. prepare() stops on such a build, this says so
    in the bump PR already. Warns instead of failing.
    """
    try:
        ours = int(ELECTRON_VAR_RE.search(open("PKGBUILD").read()).group(1))
        locked = locked_electron(tarball)
        major = int(locked.split(".")[0])
    except Exception as exc:        # advisory: never blocks the bump
        print(f"::warning::Electron check skipped: {exc!r}")
        return []
    if major <= ours:
        print(f"upstream {tag} locks Electron {locked}, PKGBUILD runs electron{ours}")
        return []
    try:
        # Only the repositories the build container enables, not [*-testing].
        found = [r for r in json.loads(fetch(f"{ARCH_SEARCH}electron{major}", timeout=20))["results"]
                 if r["repo"] in ("core", "extra")]
        arch = (f"Arch ships electron{major} {found[0]['pkgver']}" if found
                else f"Arch has no electron{major} yet")
    except Exception as exc:
        arch = f"Arch package lookup failed: {exc}"
    line = (f"upstream {tag} locks Electron {locked}, newer than electron{ours}: "
            f"prepare() stops on it ({arch}). Move _electron and the aur/PKGBUILD "
            f"dependency to electron{major} (README, Electron)")
    print(f"::warning title=Electron::{line}")
    return [line]


def gh(args: list[str]) -> subprocess.CompletedProcess:
    return run(["gh", *args])


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--pr", action="store_true",
                      help="push bump branch and open auto-merge PR")
    mode.add_argument("--sync-sums", action="store_true",
                      help="refresh the checksums of local source files in PKGBUILD")
    args = ap.parse_args()

    if args.sync_sums:
        changed = sync_local_source_sums("PKGBUILD")
        for line in changed:
            print("source checksum refreshed:", line)
        if not changed:
            print("local source checksums are current")
        return 0

    require_non_root()

    rel = api(f"/repos/{REPO}/releases/latest")
    tag = rel["tag_name"]
    # Up to v0.21.5 upstream tagged by date and named releases "Hermes Agent
    # v0.21.3 (v2026.9.14)"; since v0.21.6 the tag is the version itself and
    # the name reads "Hermes Agent v0.21.6". Take the first vX.Y.Z in the name
    # that is not the date tag, whatever order upstream uses.
    date_tag = re.fullmatch(r"v(\d{4}\.\d+\.\d+(?:\.\d+)?)", tag)
    candidates = [v for v in re.findall(r"\bv(\d+\.\d+\.\d+)\b", rel.get("name") or "")
                  if not (date_tag and date_tag.group(1).startswith(v))]
    if not candidates:
        print(f"cannot parse version from release name: {rel.get('name')!r}")
        return 2
    version = candidates[0]
    if not date_tag and tag != f"v{version}":
        print(f"release name {rel.get('name')!r} does not match its tag {tag}")
        return 2

    pkg = open("PKGBUILD").read()
    cur_tag = re.search(r"(?m)^_pkgver_tag=(.+)$", pkg).group(1)
    if cur_tag == tag:
        print(f"PKGBUILD already at latest tag {tag}, nothing to do")
        return 0
    cur_version = re.search(r"(?m)^pkgver=(.+)$", pkg).group(1)
    cur_pkgrel = re.search(r"(?m)^pkgrel=(.+)$", pkg).group(1)
    pkgrel = next_pkgrel(version, cur_version, cur_pkgrel)
    full_version = version if pkgrel == 1 else f"{version}-{pkgrel}"

    ref = api(f"/repos/{REPO}/git/refs/tags/{tag}")
    obj = ref["object"]
    commit = obj["sha"]
    if obj["type"] == "tag":
        commit = api(f"/repos/{REPO}/git/tags/{commit}")["object"]["sha"]

    tarball = fetch(f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz")
    checksum = hashlib.sha256(tarball).hexdigest()
    print(f"upstream tag={tag} version={version} pkgrel={pkgrel} commit={commit} "
          f"sha256={checksum}")
    electron = electron_lag(tag, tarball)

    if not args.pr:
        print("dry run: no files changed (use --pr to open the bump PR)")
        return 0

    # No PR yet open for this tag?
    existing = gh(["pr", "list", "--state", "open",
                   "--search", f"in:title \"chore: bump to {tag}\"",
                   "--json", "number,url"])
    if existing.returncode == 0 and json.loads(existing.stdout):
        pr = json.loads(existing.stdout)[0]
        # main's ruleset requires branches to be up to date with main, so
        # auto-merge waits forever once main moves. Merging main into the bump
        # branch re-runs the checks and lets auto-merge proceed.
        r = gh(["pr", "update-branch", pr["url"]])
        if r.returncode != 0:
            print(f"PR for {tag} is open but cannot be updated with main "
                  f"({pr['url']}): {r.stderr.strip()}")
            return 1
        print(f"PR for {tag} already open ({pr['url']}): {r.stdout.strip()}")
        return 0

    edit_pkgbuild("PKGBUILD", tag, version, commit, checksum, pkgrel)
    for line in sync_local_source_sums("PKGBUILD"):
        print("source checksum refreshed:", line)
    edit_aur_pkgbuild("aur/PKGBUILD", version, pkgrel)
    regen_srcinfo("aur")

    branch = f"bump/{tag}"
    gh_repo = os.environ["GH_REPO"]
    push_url = f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/{gh_repo}.git"

    # -B (not -b): a previous run may have left the branch behind after
    # failing further down, and re-runs must not die on "branch exists".
    run(["git", "checkout", "-B", branch])
    run(["git", "config", "user.email", "jabla@users.noreply.github.com"])
    run(["git", "config", "user.name", "hermes-agent-desktop-bin CI"])
    run(["git", "add", "PKGBUILD", "aur/PKGBUILD", "aur/.SRCINFO"])
    r = run(["git", "commit", "-m", f"chore: bump to {tag} (v{full_version})"])
    if r.returncode != 0:
        print("commit failed:", r.stderr)
        return 1
    # --force: this branch is owned by the bump job and only ever carries this
    # one bump commit; retries after a partial run must be able to reset it.
    # No -u: it would store the token-bearing push URL in .git/config.
    r = run(["git", "push", "--force", push_url, f"HEAD:{branch}"])
    if r.returncode != 0:
        print("push failed:", r.stderr)
        return 1

    body = (f"Automated bump to upstream [release {tag}]"
            f"(https://github.com/{REPO}/releases/tag/{tag}).\n\n"
            "Build + smoke run as required checks; auto-merge after green.")
    if electron:
        body += "\n\n**Electron** (the build stops until this is done):\n" + "\n".join(
            f"- {line}" for line in electron)
    r = gh(["pr", "create", "--base", "main", "--head", branch,
            "--title", f"chore: bump to {tag} (v{full_version})",
            "--body", body])
    if r.returncode != 0:
        print("pr create failed:", r.stderr)
        return 1
    pr_url = r.stdout.strip().splitlines()[-1]
    print(pr_url)

    r = gh(["pr", "merge", pr_url, "--auto", "--squash"])
    if r.returncode != 0:
        print("auto-merge enable failed:", r.stderr)
        return 1
    print("auto-merge enabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
