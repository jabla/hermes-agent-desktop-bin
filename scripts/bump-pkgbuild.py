#!/usr/bin/env python3
"""Bump hermes-agent-desktop-bin to the latest upstream release.

Three modes:
  * default (dry run): report what a bump would change, write nothing.
  * --pr: create branch + commit (PKGBUILD, aur/PKGBUILD, aur/.SRCINFO),
    push it and open an auto-merge PR. Never commits to main directly.
  * --sync-sums: only refresh the checksums of the local source files
    (patches, launcher, tests) in PKGBUILD after editing one of them.

Every bump run also compares PKGBUILD with the AUR source package
hermes-agent-desktop and reports drift as a warning.

Exits 0 without changes when PKGBUILD already tracks the latest upstream tag.
Requires: gh (GH_TOKEN + GH_REPO env), makepkg available for .SRCINFO regen,
vercmp (pacman) for the version order.
Must not run as root: makepkg refuses to run as root, so the container job
runs this script through runuser as an unprivileged user.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "NousResearch/hermes-agent"
REFERENCE = "hermes-agent-desktop"
REFERENCE_SRCINFO = f"https://aur.archlinux.org/cgit/aur.git/plain/.SRCINFO?h={REFERENCE}"
SHA_RE = re.compile(r"^sha256sums=\('([0-9a-f]{64})'", re.M)


def api(path: str):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "hermes-desktop-arch-builder"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as r:
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
        if field not in pkg:
            sys.exit(f"failed to write {field!r} into {path}")
    open(path, "w").write(pkg)


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
        if field not in pkg:
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


def parse_srcinfo(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition(" = ")
        if sep:
            fields.setdefault(key, []).append(value)
    return fields


def source_sums(info: dict[str, list[str]]) -> dict[str, str]:
    """Map each source file name (before `::`, else the URL basename) to its sum."""
    names = [s.split("::", 1)[0] if "::" in s else s.rsplit("/", 1)[-1]
             for s in info.get("source", [])]
    return dict(zip(names, info.get("sha256sums", [])))


# Divergences from the AUR source package that are deliberate — see README,
# "Runtime". The launcher points the app at the runtime installed by
# hermes-agent(-bin) when one is installed (same filename as the reference,
# deliberately different content), its own test exists only here, and the
# optdepends entry documents the choice. Everything else (patches, other
# sources, checksums, dependencies) must keep matching the reference.
LOCAL_ONLY_SOURCES = {"launcher-runtime-root.test.cjs"}
DIVERGENT_CHECKSUMS = {"hermes-desktop"}
DIVERGENT_OPTDEPENDS = {
    "hermes-agent-bin: run the app on the installed Hermes runtime instead of a local install"
}


def check_reference_drift() -> list[str]:
    """Compare PKGBUILD with the AUR source package it is kept in sync with.

    Warns instead of failing: the reference may simply be one release ahead
    or behind. Source files and runtime dependencies must match at any
    version, checksums only while both build the same pkgver — minus the
    deliberate divergences in DIVERGENT_SOURCES / DIVERGENT_OPTDEPENDS.
    """
    try:
        ref = parse_srcinfo(fetch(REFERENCE_SRCINFO).decode())
    except Exception as exc:        # AUR outages must not block the bump
        print(f"::warning::{REFERENCE} drift check skipped: {exc}")
        return []
    ours = parse_srcinfo(printsrcinfo("."))
    drift = []
    for key in ("depends", "optdepends"):
        here, there = set(ours.get(key, [])), set(ref.get(key, []))
        if key == "optdepends":
            here -= DIVERGENT_OPTDEPENDS
        if here != there:
            drift.append(f"{key}: only here {sorted(here - there)}, "
                         f"only in {REFERENCE} {sorted(there - here)}")
    # Local files only: the upstream tarball's name carries the release tag.
    here = {s for s in ours.get("source", []) if "://" not in s} - LOCAL_ONLY_SOURCES
    there = {s for s in ref.get("source", []) if "://" not in s}
    if here != there:
        drift.append(f"source files: only here {sorted(here - there)}, "
                     f"only in {REFERENCE} {sorted(there - here)}")
    our_sums, ref_sums = source_sums(ours), source_sums(ref)
    our_ver, ref_ver = ours.get("pkgver", ["?"])[0], ref.get("pkgver", ["?"])[0]
    if our_ver == ref_ver:
        for name in sorted(our_sums.keys() & ref_sums.keys()):
            if name in DIVERGENT_CHECKSUMS or name in LOCAL_ONLY_SOURCES:
                continue
            if our_sums[name] != ref_sums[name]:
                drift.append(f"{name}: sha256 {our_sums[name][:12]}… here, "
                             f"{ref_sums[name][:12]}… in {REFERENCE}")
    else:
        print(f"{REFERENCE} is at {ref_ver}, PKGBUILD at {our_ver}: checksums not compared")
    for line in drift:
        print(f"::warning title=Drift from {REFERENCE}::{line}")
    if not drift:
        print(f"PKGBUILD is in sync with {REFERENCE} {ref_ver}")
    return drift


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
    check_reference_drift()

    rel = api(f"/repos/{REPO}/releases/latest")
    tag = rel["tag_name"]
    # Release names read "Hermes Agent v0.21.3 (v2026.9.14)": take the first
    # vX.Y.Z that is not the date tag itself, whatever order upstream uses.
    date_version = tag.lstrip("v")
    candidates = [v for v in re.findall(r"\bv(\d+\.\d+\.\d+)\b", rel.get("name") or "")
                  if not date_version.startswith(v)]
    if not candidates:
        print(f"cannot parse version from release name: {rel.get('name')!r}")
        return 2
    version = candidates[0]

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

    checksum = hashlib.sha256(
        fetch(f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz")
    ).hexdigest()
    print(f"upstream tag={tag} version={version} pkgrel={pkgrel} commit={commit} "
          f"sha256={checksum}")

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

    r = gh(["pr", "create", "--base", "main", "--head", branch,
            "--title", f"chore: bump to {tag} (v{full_version})",
            "--body",
            f"Automated bump to upstream [release {tag}]"
            f"(https://github.com/{REPO}/releases/tag/{tag}).\n\n"
            "Build + smoke run as required checks; auto-merge after green."])
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
