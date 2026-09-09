# Security

## Scope

This repository contains packaging automation for the upstream Hermes Agent
desktop app:

- `PKGBUILD` / `aur/PKGBUILD` — recipes, no application code
- `.github/workflows/build.yml` — CI pipeline (bump, build, smoke, release,
  aur-sync)
- `scripts/` — bump automation

The packaged application itself lives at
https://github.com/NousResearch/hermes-agent — report application
vulnerabilities there.

## Supply-chain notes

- Builds run in a fresh `archlinux:latest` container per run; the base image
  is not pinned to a digest (rolling distro).
- GitHub Actions are pinned to commit SHAs (official `actions/*`), kept current by Dependabot (weekly, grouped).
- The `AUR_SSH_KEY` secret is a dedicated, low-scope deploy key used only by
  the `aur-sync` job; it runs exclusively after a green release on `main`,
  never on pull requests.
- `main` is protected: pull requests required, `build` + `smoke` checks
  mandatory, force-push blocked.

## Reporting

To report a security issue in this repository's automation, open a private
vulnerability report via GitHub: *Issues → New issue → Report a security
vulnerability* (or contact the maintainer through the AUR package page).
