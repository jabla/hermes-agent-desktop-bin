# hermes-agent-desktop-bin

Prebuilt Arch Linux package of [Hermes Agent](https://github.com/NousResearch/hermes-agent) desktop app from Nous Research. Nothing is compiled at install time.

The source package [hermes-agent-desktop](https://aur.archlinux.org/packages/hermes-agent-desktop) builds the same recipe on your machine. The two conflict.

## Install

```bash
yay -S hermes-agent-bin
yay -S hermes-agent-desktop-bin
```

Launcher: `hermes-desktop`. Optional features and browser tools: see [hermes-agent-bin](https://github.com/jabla/hermes-agent-bin#optional-features). Update with your AUR helper, not in the app. After an update, run `hermes gateway restart` and restart the app.

## Electron

The app runs on Arch's `electron44` instead of a bundled Electron. If needed, flags for this app go into `~/.config/hermes-desktop-flags.conf`.

## What differs from upstream

Besides the system Electron:

- `package-managed-runtime.patch`: the updater, the update channel switch and the first-run setup refuse and point to your AUR helper.
- `package-managed-bootstrap.patch`: the runtime installer refuses to run.
- `harden-hud-modifier-monitor.patch`: the X11 HUD helper is built with Arch's `CFLAGS` and `LDFLAGS` (full RELRO).

## Bugs

Packaging problems: open an issue here. Bugs in Hermes itself: [upstream](https://github.com/NousResearch/hermes-agent/issues).

## License

Repository content: [BSD Zero Clause (0BSD)](LICENSE). The packaged app is MIT (Nous Research).
