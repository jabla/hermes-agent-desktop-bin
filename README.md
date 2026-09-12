# hermes-agent-desktop-bin

Prebuilt Arch Linux package for the [Hermes Agent desktop app](https://github.com/NousResearch/hermes-agent) (Nous Research). **Nothing is compiled at install time**: GitHub Actions builds the app once per upstream release — reusing Arch's `electron42` runtime instead of bundling Electron — and publishes the finished `.pkg.tar.zst`; the AUR `-bin` wrapper just downloads and extracts it.

## Install

```bash
yay -S hermes-agent-desktop-bin
```

This replaces the source package `hermes-agent-desktop` (they conflict). Launcher: `hermes-desktop`.

## How it works

- `PKGBUILD` — the *build* recipe, run in CI (archlinux container, non-root makepkg). Builds the app against the system `electron42` runtime, so the package stays small instead of shipping Electron.
- `aur/PKGBUILD` — the AUR *wrapper*, source of truth for [hermes-agent-desktop-bin on the AUR](https://aur.archlinux.org/packages/hermes-agent-desktop-bin). Its `source` URL points at the GitHub Release artifact; `package()` only extracts the payload.
- `scripts/bump-pkgbuild.py` — bump automation, runs every 2 hours: detects a new upstream tag, edits both PKGBUILDs + `.SRCINFO`, opens an auto-merge PR.
- `.github/workflows/build.yml` — `bump` / `build` / `smoke` / `release` / `aur-sync` pipeline.

## Maintenance

- **New upstream release**: the scheduled `bump` job checks every 2 hours, moves `PKGBUILD` to the new tag (tag, commit, source checksum), updates `aur/PKGBUILD` and `.SRCINFO`, and opens an auto-merge PR. It authenticates with the `BUMP_TOKEN` secret — a fine-grained PAT (Contents + Pull requests: read/write) — because the default `GITHUB_TOKEN` produces a bot-authored PR whose checks need manual approval and whose merge never triggers the release pipeline. The job logs the token identity it used and fails instead of degrading silently; renew the PAT before it expires.
- **Pipeline**: `build` → `smoke` → `release` → `aur-sync`. The first two also run on pull requests (merge gate); `release` writes notes linking the upstream release and the upstream compare view, and `aur-sync` injects the released artifact's sha256 into `aur/` before pushing to the AUR. Upstream tag and commit are pinned in `PKGBUILD` (`_pkgver_tag`, `_commit`).
- **Upstream drift in a patch**: if upstream touches the patched sources, `prepare()` stops with a `.rej`. Regenerate the hunk against the new tag and land it *together with* the version bump — a patch written for a release the `PKGBUILD` does not build leaves `main` unbuildable. The bump keeps the checksums of the local patch files in sync on its own.
- **AUR wrapper**: only `pkgver`/`pkgrel` are bumped there; its `sha256sums` is the release artifact's, computed after the build by `aur-sync` (a local `makepkg` yields a different hash).

## License

Repository content: [BSD Zero Clause (0BSD)](LICENSE). The packaged app is MIT (Nous Research).
