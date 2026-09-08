#!/usr/bin/env python3
"""Bump PKGBUILD to the latest upstream hermes-agent release tag.

Run from repo root. Exits 0 without changes when PKGBUILD already tracks the
latest tag. When a bump happened and PUSH=1, commits and pushes PKGBUILD.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "NousResearch/hermes-agent"


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


def main() -> int:
    rel = api(f"/repos/{REPO}/releases/latest")
    tag = rel["tag_name"]  # e.g. v2026.9.7
    m = re.search(r"\bv(\d+\.\d+\.\d+)\b", rel.get("name") or "")
    if not m:
        print(f"cannot parse version from release name: {rel.get('name')!r}")
        return 2

    pkg = open("PKGBUILD").read()
    cur_tag = re.search(r"(?m)^_pkgver_tag=(.+)$", pkg).group(1)
    if cur_tag == tag:
        print(f"PKGBUILD already at latest tag {tag}, nothing to do")
        return 0

    # tag is annotated -> dereference to the commit
    ref = api(f"/repos/{REPO}/git/refs/tags/{tag}")
    obj = ref["object"]
    sha = obj["sha"]
    if obj["type"] == "tag":
        sha = api(f"/repos/{REPO}/git/tags/{sha}")["object"]["sha"]

    tarball = f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz"
    checksum = hashlib.sha256(fetch(tarball)).hexdigest()
    print(f"upstream tag={tag} version={m.group(1)} commit={sha} sha256={checksum}")

    pkg = re.sub(r"(?m)^_pkgver_tag=.*$", f"_pkgver_tag={tag}", pkg)
    pkg = re.sub(r"(?m)^_commit=.*$", f"_commit={sha}", pkg)
    pkg = re.sub(r"(?m)^pkgver=.*$", f"pkgver={m.group(1)}", pkg)
    pkg = re.sub(r"(?m)^pkgrel=.*$", "pkgrel=1", pkg)
    pkg = re.sub(r"(?m)^sha256sums=\(\('[0-9a-f]{64}'",
                 f"sha256sums=('{checksum}'", pkg)
    open("PKGBUILD", "w").write(pkg)
    print("PKGBUILD bumped")

    if os.environ.get("PUSH") == "1":
        subprocess.run(["git", "config", "user.email",
                        "builder@users.noreply.github.com"], check=True)
        subprocess.run(["git", "config", "user.name",
                        "hermes-desktop-arch builder"], check=True)
        subprocess.run(["git", "add", "PKGBUILD"], check=True)
        subprocess.run(["git", "commit", "-m",
                        f"chore: bump to {tag} (v{m.group(1)})"], check=True)
        subprocess.run(["git", "push",
                        f"https://x-access-token:{os.environ['GITHUB_TOKEN']}"
                        f"@github.com/{os.environ['GITHUB_REPOSITORY']}.git",
                        f"HEAD:{os.environ['GITHUB_REF_NAME']}"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
