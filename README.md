# hermes-agent-desktop-bin

Prebuilt Arch Linux package for the [Hermes Agent desktop app](https://github.com/NousResearch/hermes-agent) (Nous Research).

The upstream source is built **once** in GitHub Actions (archlinux container). The finished `.pkg.tar.zst` is published as a GitHub Release — **nothing is compiled on the installing machine**.

## Install

From the [AUR](https://aur.archlinux.org/packages/hermes-agent-desktop-bin) (recommended):

```bash
yay -S hermes-agent-desktop-bin
```

Or directly from the [GitHub Releases](https://github.com/jabla/hermes-agent-desktop-bin/releases) of this repo:

```bash
yay -U https://github.com/jabla/hermes-agent-desktop-bin/releases/download/<tag>/hermes-agent-desktop-bin-<ver>-x86_64.pkg.tar.zst
```

The package conflicts with the AUR source package `hermes-agent-desktop` (installing one removes the other). The launcher is `hermes-desktop`, reusing the system `electron42` runtime.

## How updates work (fully automated)

```
upstream release (NousResearch/hermes-agent)
  → daily cron detects new tag
  → bump job opens PR "chore: bump to <tag>" (never commits to main directly)
  → required checks on the PR: build + xvfb boot smoke test
  → auto-merge when green
  → push to main triggers: build → smoke → GitHub Release v<pkgver>-<pkgrel>
  → aur-sync job pushes aur/ (wrapper PKGBUILD) to aur.archlinux.org
  → `yay -Syu` picks up the new version
```

Bump PRs are opened and auto-merged by the automation. Pull requests from
humans are reviewed by the maintainer before merging.

## Repository policies

- `main` is protected by a ruleset: pull requests required, status checks
  `build` + `smoke` mandatory, force-push and branch deletion blocked.
- Least-privilege tokens: `contents: read` by default, elevated only where
  needed (bump, release).
- The AUR secret key is used exclusively by the `aur-sync` job and only runs
  after a green release on main — never on pull requests.

## Layout

- `PKGBUILD` — build recipe (adapted from AUR `hermes-agent-desktop`, keeps its
  system-`electron42` patches). Produces the installable package.
- `aur/PKGBUILD`, `aur/.SRCINFO` — AUR wrapper package (single source of truth;
  references the versioned GitHub Release asset, sha256 pinned). CI validates
  `.SRCINFO` against the PKGBUILD.
- `scripts/bump-pkgbuild.py` — bump automation: detects the latest upstream
  release, updates both PKGBUILDs + `.SRCINFO`, opens the auto-merge PR
  (`--pr`); without `--pr` it is a dry run.
- `.github/workflows/build.yml` — the whole pipeline (bump, build, smoke,
  release, aur-sync).

## License

- Repository content (PKGBUILDs, scripts, docs): [BSD Zero Clause (0BSD)](LICENSE) — do whatever you want, no warranty, no liability.
- The packaged application is MIT-licensed by Nous Research (upstream).
- The AUR `hermes-agent-desktop` PKGBUILD this repo was adapted from is 0BSD (AUR contributors), attribution in the PKGBUILD header.

## Status

- [x] Package: `hermes-agent-desktop-bin`, tracking upstream (currently 0.21.1-1)
- [x] CI build in archlinux container, non-root makepkg
- [x] Boot smoke test (xvfb, headless; verified on a real desktop)
- [x] GitHub Release publishing after green build + smoke
- [x] AUR package live, `yay -Syu`-compatible
- [x] Branch protection + PR-only flow
