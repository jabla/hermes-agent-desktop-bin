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
- The `AUR_SSH_KEY` secret is used only by the `aur-sync` job; `release` and
  `aur-sync` run exclusively for `main` (push or manual dispatch on `main`),
  never on pull requests or other branches. The key belongs in the `aur`
  environment with deployment branches limited to `main`: pull requests from
  branches of this repository can read repository-level secrets, environment
  secrets they cannot. AUR keys are not per package: the key can push to every
  package of the AUR account, and `hermes-agent-bin` publishes with the same
  key, so both repositories must protect it the same way.
- The AUR package's patches, launcher and tests are vendored from the AUR
  source package `hermes-agent-desktop` after review; the bump job only
  reports drift from it and never copies files automatically. Deliberate
  divergences (the launcher's runtime root, its test, one optdepends entry) are
  listed in `scripts/bump-pkgbuild.py` and in the README.
- The `smoke` job downloads a pinned release artifact of `hermes-agent-bin`
  (version and sha256 hard-coded in the workflow, verified before install) to
  boot the app against a real package runtime.
- `main` is protected: pull requests required, `build` + `smoke` checks
  mandatory, force-push blocked.

## Reporting

To report a security issue in this repository's automation, open a private
vulnerability report via GitHub: *Issues → New issue → Report a security
vulnerability* (or contact the maintainer through the AUR package page).
