# hermes-agent-desktop-bin

Prebuilt Arch Linux package for the [Hermes Agent desktop app](https://github.com/NousResearch/hermes-agent) (Nous Research). **Nothing is compiled at install time**: GitHub Actions builds the app once per upstream release — reusing Arch's `electron44` runtime instead of bundling Electron — and publishes the finished `.pkg.tar.zst`; the AUR `-bin` wrapper just downloads and extracts it.

## Install

```bash
yay -S hermes-agent-desktop-bin
```

This replaces the source package `hermes-agent-desktop` (they conflict) and behaves like it: same runtime patches, launcher and dependencies. The app runs on the Hermes runtime of `hermes-agent` or `hermes-agent-bin` (a dependency) and never installs one of its own (see [Runtime](#runtime)). For the prebuilt runtime, install `hermes-agent-bin` first or pick it when your AUR helper asks which package should provide `hermes-agent`; otherwise the helper may build the source package `hermes-agent`. It cannot update itself: update through your AUR helper. Launcher: `hermes-desktop`.

## How it works

- `PKGBUILD` — the *build* recipe, run in CI (archlinux container, non-root makepkg, including `check()`). Builds the app against the system `electron44` runtime, so the package stays small instead of shipping Electron.
- `*.patch`, `hermes-desktop`, `launcher.test.cjs` — vendored verbatim from the AUR source package [hermes-agent-desktop](https://aur.archlinux.org/packages/hermes-agent-desktop), except `harden-hud-modifier-monitor.patch` (see [Runtime](#runtime)).
- `aur/PKGBUILD` — the AUR *wrapper*, source of truth for [hermes-agent-desktop-bin on the AUR](https://aur.archlinux.org/packages/hermes-agent-desktop-bin). Its `source` points at the GitHub Release artifact, stored under a name that differs from the package makepkg writes; `package()` only extracts the payload.
- `scripts/bump-pkgbuild.py` — bump automation, started by hand: detects a new upstream tag, edits both PKGBUILDs + `.SRCINFO`, opens an auto-merge PR, and reports drift from `hermes-agent-desktop` (in the log and the bump PR).
- `scripts/check-metadata.sh` — fails the build when `PKGBUILD` and `aur/PKGBUILD` disagree on version, dependencies, provides or conflicts.
- `.github/workflows/build.yml` — `bump` / `plan` / `build` / `smoke` / `release` / `aur-sync` pipeline.

## Runtime

The app needs a Hermes Agent runtime. `hermes-agent` of at least the app's
version is a dependency, met by the AUR package `hermes-agent` or by
`hermes-agent-bin`, which provides it with its version (since 0.22.2-1).

- The launcher exports `HERMES_DESKTOP_HERMES=/usr/bin/hermes` unless it is
  set already. The app starts its backend through that CLI wrapper, so the
  backend gets the wrapper's environment: lazy installs off, optional
  dependencies in the user's durable target, shared by the CLI and the desktop.
- `HERMES_DESKTOP_PACKAGE_MANAGED_RUNTIME=1` (also from the launcher) makes the
  patched app refuse the in-app updater and the first-run bootstrap
  (`package-managed-runtime.patch`, `package-managed-bootstrap.patch`). It
  never downloads or writes an agent tree, so versions come from pacman.

Up to 0.21.5 the runtime was optional: the launcher pointed the app at
`/opt/hermes-agent` when it existed, otherwise the app installed its own
runtime into `~/.hermes/hermes-agent`. Since 0.22.0 that directory is unused.
It can be removed together with any `hermes` launchers in `~/.local/bin` that
point into it; `~/.hermes` itself holds the configuration and sessions.

Differences from `hermes-agent-desktop` that stay in `PKGBUILD`:

- `check()` runs the upstream tests covering the patched files, not the full
  suite (see the pipeline below).
- `prepare()` stops when upstream locks a newer Electron major than
  `electron44`.
- `package()` stops on an unknown electron-builder resource.
- `check()` stops when the renderer CSS lacks Tailwind's utilities: outside a
  git checkout Tailwind v4 skips the sources a parent `.gitignore` excludes
  (`src/` here). The window would then show unstyled text.
- `harden-hud-modifier-monitor.patch` builds the X11 HUD helper with Arch's
  `CFLAGS`/`LDFLAGS` (full RELRO). `hermes-agent-desktop` dropped it in
  0.22.0-1.
- `electron44` instead of `electron42`: upstream locks Electron 44 since
  v0.22.5, `hermes-agent-desktop` 0.22.4-1 still runs on `electron42`.

## Maintenance

- **New upstream release**: there is no scheduled check; watch the upstream repository's releases (*Watch > Custom > Releases*) and read the release notes first: almost every release needs patch work here, and releases without a desktop app (v0.21.6) are not packaged. `hermes-agent-bin` has to ship the new version first: the app depends on `hermes-agent` of at least its own version. `smoke` pins that release. Then run the workflow by hand with `bump` (`gh workflow run build-package -f bump=true`). The `bump` job moves `PKGBUILD` to the new tag (tag, commit, source checksum), updates `aur/PKGBUILD` and `.SRCINFO`, and opens an auto-merge PR. A new version starts at `pkgrel=1`; a new tag with an unchanged version gets the next `pkgrel` (otherwise its release tag would already exist); an older version aborts the bump. An open bump PR is updated with `main` when the job runs again, because the ruleset only merges up-to-date branches. The job authenticates with the `BUMP_TOKEN` secret — a fine-grained PAT (Contents + Pull requests: read/write) — because the default `GITHUB_TOKEN` produces a bot-authored PR whose checks need manual approval and whose merge never triggers the release pipeline. The job logs the token identity it used and fails if the secret is missing or rejected; its read-only calls to upstream's API use the workflow token, because unauthenticated calls hit the runners' shared rate limit. The PAT is created without an expiry date, so revocation — not rotation — is the deliberate step: delete it under *Settings → Developer settings → Fine-grained tokens* and `gh secret delete BUMP_TOKEN` here and in `hermes-agent-bin`.
- **Runtime in CI**: `hermes-agent` comes from the AUR, so pacman cannot
  install it in CI. `build` installs every other declared dependency and runs
  makepkg with `--nodeps`. `smoke` installs a pinned `hermes-agent-bin` release
  artifact (`RUNTIME_VER` + `RUNTIME_SUM` in the workflow) together with the
  package and boots the app on it. Since 0.22.4 the app attaches to the
  gateway that `hermes gateway ensure` starts. The smoke fails when that
  gateway was not started through `/usr/bin/hermes` or lacks a variable
  `/usr/bin/hermes` exports. It also fails when an API call with a gateway
  ticket does not succeed, when `/usr/bin/hermes --print-runtime-command`
  names no interpreter that can mint tickets (the app's path for a
  group-writable home), when the app stops at the first-run setup, writes
  `~/.hermes/hermes-agent`, its UI never reports the local connection or its
  window is unstyled.
  The smoke container gets a 1 GB `/dev/shm`: with docker's default 64 MB
  Chromium fails to load the UI's assets and the window stays blank.
  Boot decisions are asserted on
  `~/.hermes/logs/desktop.log`, not on stdout, which only carries Electron's
  output and the install stamp. Pin the `hermes-agent-bin` release the AUR
  ships, never one older than the desktop version, so `smoke` boots the
  combination users get; the job checks the download against the pinned
  checksum.
- **Pipeline**: `plan` -> `build` -> `smoke` -> `release` -> `aur-sync`. On a push to `main` whose `pkgver-pkgrel` is already released (CI, scripts, docs, `aur/`), `plan` skips `build`, `smoke` and `release`: the pull request run checked the change. `aur-sync` still publishes `aur/` against the existing release. A new version is built once: on the push of a merged pull request from this repository, `plan` looks up that pull request's last green run (both lookups are retried for up to 45 s: GitHub links the merge commit to its pull request a few seconds late). When that run built the same tree (`build-info`), `release` publishes its package without building again. A fork pull request, an expired artifact (3 days), another tree or a failed lookup builds as before; the release notes link the run that built the package. A manual dispatch on `main` always builds. If `plan` fails, everything builds. `build` and `smoke` also run on pull requests (merge gate): `build` runs `check()` (typecheck, the upstream tests covering the patched files, the launcher test, node-pty under `electron44`; upstream's full suite is left to upstream's CI) and validates `aur/.SRCINFO` and the metadata of both PKGBUILDs. It also builds `aur/PKGBUILD` from the fresh artifact the way AUR users' makepkg does — its payload must match the artifact file for file (paths, modes, links, sha256). A rebuild must still pass the checksum. `smoke` installs the package with its declared dependencies (the pinned `hermes-agent-bin` for `hermes-agent`), loads the node-pty addon with `electron44`, checks that the app reports the package version and boots the app under xvfb on that runtime: the app must still run 15 s after its UI reported the local connection. Its window must be styled: elements with Tailwind's `flex` class must be flex boxes (asked over the DevTools port), which fails for a renderer built without its CSS utilities or a UI that never mounted. `release` and `aur-sync` only run for `main`; `release` writes notes linking the upstream release and the upstream compare view. `aur-sync` injects the released artifact's sha256 into `aur/` and pushes to the AUR only while its commit is still `main`'s HEAD. Upstream tag and commit are pinned in `PKGBUILD` (`_pkgver_tag`, `_commit`).
- **Copies of this repository** (forks, a private CI test repository): the AUR push only runs in `jabla/hermes-agent-desktop-bin`. Elsewhere `aur-sync` prints the diff it would push, so pipeline changes can be tested end to end without publishing anything.
- **Packaging-only changes** (patches, launcher, dependencies): bump `pkgrel` in both PKGBUILDs, or the release tag already exists and nothing new is published.
- **Upstream drift in a patch**: if upstream touches the patched sources, `prepare()` stops (`patch --fuzz=0`). Prefer the refreshed files from `hermes-agent-desktop`; the bump job warns ("Drift from hermes-agent-desktop", also in the bump PR) when its sources, checksums or dependencies differ from `PKGBUILD` — deliberate exceptions are listed in `scripts/bump-pkgbuild.py` (`harden-hud-modifier-monitor.patch` and `electron44` at the moment) — and when its PKGBUILD changes beyond the version fields (build steps, which the `.SRCINFO` comparison cannot see). Review that change in its [AUR history](https://aur.archlinux.org/cgit/aur.git/log/?h=hermes-agent-desktop), port what applies, then set `REFERENCE_PKGBUILD_SHA256` in `scripts/bump-pkgbuild.py` to the value the warning prints. Land the fix *together with* the version bump — a patch written for a release the `PKGBUILD` does not build leaves `main` unbuildable. After editing a local file, run `python3 scripts/bump-pkgbuild.py --sync-sums`.
- **Electron**: the package runs on `electron44`, the major upstream locks since v0.22.5. A newer runtime than upstream's lock is fine. `prepare()` fails once upstream requires a newer major than the system runtime.
- **AUR wrapper**: only `pkgver`/`pkgrel` are bumped there; its `sha256sums` is the release artifact's, computed after the build by `aur-sync` (a local `makepkg` yields a different hash).
- **AUR key**: keep `AUR_SSH_KEY` as a secret of the `aur` environment, with deployment branches limited to `main` — repository secrets are readable by pull requests from branches of this repository. The same key also publishes `hermes-agent-bin`, and AUR keys can push to every package of the account, so that repository needs the same environment setup.

## License

Repository content: [BSD Zero Clause (0BSD)](LICENSE). The packaged app is MIT (Nous Research).
