# hermes-agent-desktop-bin

Prebuilt Arch Linux binary package for the [Hermes Agent desktop app](https://github.com/NousResearch/hermes-agent) (Nous Research).

Builds the upstream source tag once in GitHub Actions (archlinux container) and ships the finished `.pkg.tar.zst` — **nothing is compiled on the installing machine**.

Plan: later submit as AUR package `hermes-agent-desktop-bin` (this repo hosts the build artifacts; AUR PKGBUILD references the versioned GitHub Release asset, vscodium-bin-style).

## Status

Work in progress (private). Current state:

- [x] PKGBUILD tracking upstream tag `v2026.9.7` (Hermes Agent v0.21.1), package name `hermes-agent-desktop-bin` (conflicts with AUR `hermes-agent-desktop`)
- [x] CI build: `makepkg` in `archlinux:latest` container, non-root
- [x] boot smoke test of the built package (xvfb, headless + real desktop on 2nd laptop)
- [ ] package repo / release publishing (next step)

## Layout

- `PKGBUILD` — adapted from [AUR hermes-agent-desktop](https://aur.archlinux.org/packages/hermes-agent-desktop), same electron42 system-runtime patches
- `scripts/bump-pkgbuild.py` — auto-bump to latest upstream release tag (used by the scheduled workflow)
- `.github/workflows/build.yml` — build on `workflow_dispatch`, daily tag check on schedule
