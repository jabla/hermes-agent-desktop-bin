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

## License

Repository content: [BSD Zero Clause (0BSD)](LICENSE). The packaged app is MIT (Nous Research).
