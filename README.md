# hermes-agent-desktop-bin

Prebuilt Arch Linux package for the [Hermes Agent desktop app](https://github.com/NousResearch/hermes-agent) (Nous Research). **Nothing is compiled at install time**: GitHub Actions builds the app once per upstream release — reusing Arch's `electron42` runtime instead of bundling Electron — and publishes the finished `.pkg.tar.zst`; the AUR `-bin` wrapper just downloads and extracts it.

## Install

```bash
yay -S hermes-agent-desktop-bin
```

This replaces the source package `hermes-agent-desktop` (they conflict) and behaves like it: same patches, launcher and runtime dependencies. The launcher points the app at the runtime installed by `hermes-agent` / `hermes-agent-bin` when it is installed, so nothing is installed twice; without one the app keeps the upstream first-run flow (see [Runtime](#runtime)). Either way the app cannot update itself and uses the system `uv` and Node.js — update through your AUR helper. Launcher: `hermes-desktop`.

## How it works

- `PKGBUILD` — the *build* recipe, run in CI (archlinux container, non-root makepkg, including `check()`). Builds the app against the system `electron42` runtime, so the package stays small instead of shipping Electron.
- `*.patch`, `hermes-desktop`, `*.test.cjs`, `runtime-policy.test.py` — vendored from the AUR source package [hermes-agent-desktop](https://aur.archlinux.org/packages/hermes-agent-desktop), verbatim except for `hermes-desktop` (runtime root, see [Runtime](#runtime)) and `launcher-runtime-root.test.cjs`, which covers that change and exists only here.
- `aur/PKGBUILD` — the AUR *wrapper*, source of truth for [hermes-agent-desktop-bin on the AUR](https://aur.archlinux.org/packages/hermes-agent-desktop-bin). Its `source` points at the GitHub Release artifact, stored under a name that differs from the package makepkg writes; `package()` only extracts the payload.
- `scripts/bump-pkgbuild.py` — bump automation, runs every 2 hours: detects a new upstream tag, edits both PKGBUILDs + `.SRCINFO`, opens an auto-merge PR, and reports drift from `hermes-agent-desktop`.
- `scripts/check-metadata.sh` — fails the build when `PKGBUILD` and `aur/PKGBUILD` disagree on version, dependencies, provides or conflicts.
- `.github/workflows/build.yml` — `bump` / `build` / `smoke` / `release` / `aur-sync` pipeline.

## Runtime

The packaged app needs a Hermes Agent runtime to talk to. This package prefers
the one the user already has:

- `hermes-agent-bin` (or `hermes-agent`) installed → the launcher exports
  `HERMES_DESKTOP_HERMES_ROOT=/opt/hermes-agent`, but only when
  `/opt/hermes-agent/venv/bin/python` exists and only when the variable is not
  set already. The app evaluates it before every runtime and policy check, runs
  its backend from `/opt/hermes-agent`, and never starts an install of its own.
  The backend then starts the runtime's venv python directly instead of
  `/usr/bin/hermes`, so the launcher also exports that wrapper's environment
  (`HERMES_DISABLE_LAZY_INSTALLS=1`, `HERMES_LAZY_INSTALL_TARGET` under
  `$XDG_DATA_HOME/hermes-agent/python`): the venv is root-owned, and the
  optional dependencies installed on demand (voice, provider SDKs, …) live in
  the user's durable target, shared by the CLI and the desktop.
- No package runtime → unchanged upstream behaviour: the first-run setup offers
  to install a runtime into `~/.hermes/hermes-agent`.

Without that override the packaged app insists on a policy-patched checkout in
`~/.hermes/hermes-agent`: `packaged-bootstrap.patch` (vendored from the source
package) reports `package-patch-missing` for anything else, and *every*
`bootstrap-needed` backend goes through the first-run setup gate. A machine
that already has a runtime therefore gets a second one (~0.5-1 GB: repository,
venv, python-deps and node-deps stages) plus a click on "Install Hermes
locally" after the update that introduces it.

The hardening itself is untouched: `HERMES_DESKTOP_PACKAGE_MANAGED_RUNTIME=1`
stays exported, so the in-app updater stays disabled ("This Hermes runtime is
managed by the system package. Update hermes-agent-desktop with your package
manager.") and versions keep coming from pacman. The `hermes-agent-bin`
optdepends entry points users at this behaviour.

This is the package's only deliberate divergence from `hermes-agent-desktop`;
`scripts/bump-pkgbuild.py` lists it explicitly so the drift report stays
meaningful, and the CI smoke job covers both paths.

## Maintenance

- **New upstream release**: the scheduled `bump` job checks every 2 hours, moves `PKGBUILD` to the new tag (tag, commit, source checksum), updates `aur/PKGBUILD` and `.SRCINFO`, and opens an auto-merge PR. A new version starts at `pkgrel=1`; a new tag with an unchanged version gets the next `pkgrel` (otherwise its release tag would already exist); an older version aborts the bump. An open bump PR is updated with `main` on every run, because the ruleset only merges up-to-date branches. The job authenticates with the `BUMP_TOKEN` secret — a fine-grained PAT (Contents + Pull requests: read/write) — because the default `GITHUB_TOKEN` produces a bot-authored PR whose checks need manual approval and whose merge never triggers the release pipeline. The job logs the token identity it used and fails if the secret is missing or rejected. The PAT is created without an expiry date, so revocation — not rotation — is the deliberate step: delete it under *Settings → Developer settings → Fine-grained tokens* and `gh secret delete BUMP_TOKEN` here and in `hermes-agent-bin`.
- **Runtime in CI**: `smoke` installs a pinned `hermes-agent-bin` release
  artifact (version + sha256 in the workflow) to boot the app on a real package
  runtime, and fails when the app stops at the first-run setup screen instead
  or when the running backend lacks a variable the runtime's `/usr/bin/hermes`
  exports. Boot decisions are asserted on `~/.hermes/logs/desktop.log`, not on
  stdout, which only carries Electron's output and the install stamp.
  Bump that pin together with the desktop version; the job checks the download
  against the pinned checksum.
- **Pipeline**: `build` → `smoke` → `release` → `aur-sync`. The first two also run on pull requests (merge gate): `build` runs `check()` (typecheck, the upstream tests covering the patched files, the packaging tests, node-pty under `electron42`; upstream's full suite is left to upstream's CI), `smoke` installs the package with its declared dependencies, loads the node-pty addon with `electron42` and boots the app under xvfb until the packaged install stamp is logged. `release` and `aur-sync` only run for `main`; `release` writes notes linking the upstream release and the upstream compare view, and `aur-sync` injects the released artifact's sha256 into `aur/` and pushes to the AUR only while its commit is still `main`'s HEAD. Upstream tag and commit are pinned in `PKGBUILD` (`_pkgver_tag`, `_commit`).
- **Copies of this repository** (forks, a private CI test repository): the scheduled bump and the AUR push only run in `jabla/hermes-agent-desktop-bin`. Elsewhere the bump runs on manual dispatch only and `aur-sync` prints the diff it would push, so pipeline changes can be tested end to end without publishing anything.
- **Packaging-only changes** (patches, launcher, dependencies): bump `pkgrel` in both PKGBUILDs, or the release tag already exists and nothing new is published.
- **Upstream drift in a patch**: if upstream touches the patched sources, `prepare()` stops (`patch --fuzz=0`). Prefer the refreshed files from `hermes-agent-desktop`; the bump job warns ("Drift from hermes-agent-desktop") when its sources, checksums or dependencies differ from `PKGBUILD` — the launcher, its test and the `hermes-agent-bin` optdepends entry are listed as deliberate exceptions in `scripts/bump-pkgbuild.py`. Land the fix *together with* the version bump — a patch written for a release the `PKGBUILD` does not build leaves `main` unbuildable. After editing a local file, run `python3 scripts/bump-pkgbuild.py --sync-sums`.
- **Electron**: upstream locks an older Electron major than `electron42`, the oldest one still receiving security fixes. `prepare()` fails once upstream requires a newer major than the system runtime.
- **AUR wrapper**: only `pkgver`/`pkgrel` are bumped there; its `sha256sums` is the release artifact's, computed after the build by `aur-sync` (a local `makepkg` yields a different hash).
- **AUR key**: keep `AUR_SSH_KEY` as a secret of the `aur` environment, with deployment branches limited to `main` — repository secrets are readable by pull requests from branches of this repository. The same key also publishes `hermes-agent-bin`, and AUR keys can push to every package of the account, so that repository needs the same environment setup.

## License

Repository content: [BSD Zero Clause (0BSD)](LICENSE). The packaged app is MIT (Nous Research).
