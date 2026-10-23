# Build PKGBUILD for the prebuilt hermes-agent-desktop-bin package.
# Kept in sync with the AUR source package hermes-agent-desktop
# (https://aur.archlinux.org/packages/hermes-agent-desktop): its patches,
# launcher and regression tests are vendored verbatim (apart from the Electron
# major, see the README), so the prebuilt package behaves exactly like a local
# build of the source package. The bump job warns when that package's sources
# or dependencies drift from these. The packaged app itself is MIT-licensed
# (Nous Research).
pkgname=hermes-agent-desktop-bin
_pkgname=hermes-desktop          # /usr/bin launcher name (AUR convention, lowercase)
_upstream=Hermes                 # productName + executableName
_pkgver_tag=v0.22.5
_commit=bf0203a794a07aac3ff764972ab9087baa4e4f4e
pkgver=0.22.5
pkgrel=1
pkgdesc="Hermes Agent desktop app from Nous Research — chat, voice, file browser, and settings UI for the local agent runtime (prebuilt binary, CI-built)"
arch=('x86_64')
url='https://github.com/NousResearch/hermes-agent'
license=('MIT')
# The app runs its backend through /usr/bin/hermes from hermes-agent (or
# hermes-agent-bin, which provides it with its version) and never installs a
# runtime of its own. Like hermes-agent-desktop it needs a runtime of at least
# its own version. hermes-agent's own dependencies (ffmpeg, ripgrep, browsers,
# ...) are not repeated here.
depends=(
  'electron44'
  "hermes-agent>=${pkgver}"
  'hicolor-icon-theme'
  'libnotify'
  'libsecret'
  'libx11'
  'libxi'
  'xdg-utils'
)
optdepends=(
  'libayatana-appindicator: tray indicator support'
)
makedepends=('npm')
checkdepends=('nodejs')
provides=('hermes-agent-desktop')
conflicts=('hermes-agent-desktop')
options=('!debug')
source=(
  "hermes-agent-${_pkgver_tag}.tar.gz::${url}/archive/refs/tags/${_pkgver_tag}.tar.gz"
  'package-managed-runtime.patch'
  'package-managed-bootstrap.patch'
  'harden-hud-modifier-monitor.patch'
  'hermes-desktop'
  'launcher.test.cjs'
)
# NOTE: makepkg also validates the local files. The bump automation maintains
# the tarball sum; after editing a local file run
# `python3 scripts/bump-pkgbuild.py --sync-sums`, or the build fails at
# "Validating source files".
sha256sums=('a8f67e5ec14fea681acef6cc7ff1553f002bb6101fd2df22bfdd4b7eecc54eb2'
            '19c1f67e0b24d86d9c61237f9c05a02b66ca34a8467c298a2423d5a39106c0c4'
            '412ad7b2b6bc5149a8d236ad2cb9be54d2ac0ab78dbd3c8e16deb4f4e683713f'
            'cf8b625b00e606b5b135bf5a38a851d8a699c819139e6720eecfa043ba886e9b'
            '6b2e17a0411f23dcafa9a6da7d8cd850573430a45ff1353e0febbbfc84fbea9f'
            '4b80f0d97e93a24f030a75a8b425db1315888a9ddaa7c0077c7e0401ddf58522')

# NOTE: ${srcdir} is empty at the top level of a PKGBUILD — makepkg only sets
# it inside the function scope of prepare()/build()/package(). Computing the
# extracted directory once at the top (as `_srcdir=...`) silently produces a
# root-prefixed path (`/hermes-agent-2026.7.1`) and `cd` fails. Define a helper
# and call it from each function instead.
_extract_dir() {
  echo "${srcdir}/hermes-agent-${_pkgver_tag#v}"
}

_set_npm_env() {
  export npm_config_cache="${srcdir}/npm-cache"
  export npm_config_update_notifier=false
  export npm_config_audit=false
  export npm_config_fund=false
}

prepare() {
  cd "$(_extract_dir)"
  _set_npm_env
  # --fuzz=0: a hunk whose context drifted must fail loudly instead of being
  # applied at a guessed location (offsets are still accepted).
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/package-managed-runtime.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/package-managed-bootstrap.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/harden-hud-modifier-monitor.patch"
  # Keep desktop metadata aligned with the Agent release, not the separately
  # versioned upstream desktop package.json.
  npm pkg set version=${pkgver} --prefix apps/desktop
  # The source archive has no .git directory. Pin the peeled release commit
  # locally so the bundled install stamp is reproducible and does not require
  # another network lookup during prepare()/build().
  export GITHUB_SHA="${_commit}" GITHUB_REF_NAME="${_pkgver_tag}"
  export ELECTRON_SKIP_BINARY_DOWNLOAD=1
  npm ci --prefer-offline --no-audit --ignore-scripts

  # Keep the locked Electron npm package for its TypeScript declarations and
  # tooling, but make any build helper that resolves `require('electron')` use
  # Arch's versioned runtime instead of downloading a second copy. npm hoists
  # it to the root node_modules since v0.22.5 (apps/desktop/node_modules
  # before), so take the copy apps/desktop resolves.
  local electron_dir
  electron_dir="$(cd apps/desktop && node -p 'path.dirname(require.resolve("electron/package.json"))')"
  # Only the build tree's own copy may be replaced below: without it (say,
  # dev dependencies omitted) Node would resolve some electron further up.
  if [[ "${electron_dir}" != "$(pwd -P)/"* ]]; then
    printf 'ERROR: electron resolves outside the build tree: %s\n' "${electron_dir}"
    return 1
  fi

  # The runtime used here is the major upstream locks (44.x at the time of
  # writing). A newer runtime than upstream's lock is fine: the package ran
  # on electron42 while upstream locked 40.x. The opposite direction is not
  # safe: an app written against a newer major may call APIs this runtime
  # lacks, so stop instead of shipping that build.
  local locked_electron system_electron
  locked_electron="$(node -p 'require(process.argv[1]).version' "${electron_dir}/package.json")"
  system_electron="$(< /usr/lib/electron44/version)"
  if (( ${locked_electron%%.*} > ${system_electron%%.*} )); then
    printf 'ERROR: upstream locks Electron %s, newer than the system runtime %s — move the package to a newer electronNN\n' \
      "${locked_electron}" "${system_electron}"
    return 1
  elif (( ${locked_electron%%.*} < ${system_electron%%.*} )); then
    printf 'NOTE: upstream locks Electron %s; the package runs on system Electron %s\n' \
      "${locked_electron}" "${system_electron}"
  fi

  rm -rf "${electron_dir}/dist"
  ln -s /usr/lib/electron44 "${electron_dir}/dist"
  printf '%s' 'electron' > "${electron_dir}/path.txt"
  test -x "${electron_dir}/dist/electron"

  # Build node-pty's Linux native addon locally. Its npm lifecycle uses
  # node-gyp on Linux. Explicitly export makepkg's build flags because npm
  # otherwise leaves them as unexported shell variables, producing an addon
  # without Arch's full RELRO hardening. --offline prevents any header or
  # binary download.
  export CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
  npm rebuild node-pty --offline
}

build() {
  cd "$(_extract_dir)/apps/desktop"
  _set_npm_env
  export npm_config_offline=true
  # makepkg runs build() in a separate subshell from prepare().
  export GITHUB_SHA="${_commit}" GITHUB_REF_NAME="${_pkgver_tag}"
  # The X11 HUD modifier monitor is compiled with cc during the build; it
  # takes these flags from the environment (harden-hud-modifier-monitor.patch).
  export CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
  # Keep upstream's package.json and lockfile pins intact for deterministic
  # npm ci. electron-builder still prepares a throwaway Electron zip for the
  # packager; package() keeps only the app resources and the launcher runs
  # Arch's electron44.
  npm run build

  # Upstream writes the wall clock into the bundled install stamp. Normalize it
  # to makepkg's reproducible-build epoch before electron-builder consumes it.
  local build_time
  build_time="$(date -u -d "@${SOURCE_DATE_EPOCH}" '+%Y-%m-%dT%H:%M:%S.000Z')"
  sed -i -E \
    "s|(\"builtAt\": \")[^\"]+(\")|\1${build_time}\2|" \
    build/install-stamp.json
  grep -Fq "\"builtAt\": \"${build_time}\"" build/install-stamp.json

  # Upstream's prepared-packaging gate admits `--dir`, not a bare `dir` token,
  # and rejects `-c.electronVersion=...` overrides. Omit --x64: an explicit
  # arch flag stages into build/native-deps-<platform>-<arch>, which
  # productOutput does not allow; the host arch reuses build/native-deps.
  npm run builder -- --linux --dir
}

check() {
  cd "$(_extract_dir)"
  _set_npm_env
  export npm_config_offline=true
  # Hermes desktop tests expect English timestamps and isolated temporary git
  # repositories; the default Hermes scratch directory sits inside a git repo.
  export LANG=C.UTF-8 LC_ALL=C.UTF-8
  export GIT_CEILING_DIRECTORIES="${TMPDIR:-/tmp}"
  unset HERMES_DESKTOP_PACKAGE_MANAGED_RUNTIME
  node "${srcdir}/launcher.test.cjs"
  npm run typecheck --workspace apps/desktop

  # Upstream's full vitest suite (~1000 files) runs in upstream's CI; here it
  # took ~90% of the build time and exercised upstream code on Arch's system
  # Node, which the app does not run on. Run the tests that cover what the
  # patches change instead: the patched tests and every test importing a
  # patched module. The file list follows the patches automatically; diff -u
  # style headers carry a tab and a timestamp after the path.
  local patched=()
  mapfile -t patched < <(sed -n 's|^+++ b/apps/desktop/\([^\t]*\).*|\1|p' "${srcdir}"/*.patch | sort -u)
  # A misparsed header would select no tests and pass (--passWithNoTests).
  (( ${#patched[@]} > 0 ))
  local file
  for file in "${patched[@]}"; do
    test -f "apps/desktop/${file}"
  done
  (cd apps/desktop && npx vitest related --run --passWithNoTests "${patched[@]}")

  # Tailwind v4 skips sources that a parent directory's .gitignore excludes
  # when the build directory is no git checkout (this repository ignores
  # src/). The renderer then ships without its utility classes: the window
  # shows unstyled text while the app itself boots fine.
  local css=(apps/desktop/release/linux-unpacked/resources/app.asar.unpacked/dist/assets/index-*.css)
  if ! grep -q '\.flex{' "${css[@]}"; then
    printf 'ERROR: the renderer CSS lacks Tailwind utilities (%s) — build from a git checkout or without a parent .gitignore excluding src/\n' \
      "${css[*]##*/}"
    return 1
  fi

  # node-pty is the only native Node addon shipped by Hermes. Load the staged
  # module with the exact Electron runtime used by the installed launcher; its
  # N-API build must not merely load under makepkg's system Node.
  local node_pty_root="${PWD}/apps/desktop/release/linux-unpacked/resources/app.asar.unpacked/dist/node_modules/node-pty"
  test -f "${node_pty_root}/package.json"
  # Bypass Arch's launcher here: it injects the user's electron44 flags, which
  # are valid in Chromium mode but rejected while ELECTRON_RUN_AS_NODE is set.
  env ELECTRON_RUN_AS_NODE=1 NODE_PTY_ROOT="${node_pty_root}" \
    /usr/lib/electron44/electron -e \
    'const pty = require(process.env.NODE_PTY_ROOT); if (typeof pty.spawn !== "function") process.exit(1)'
}

package() {
  cd "$(_extract_dir)"
  local appdir="apps/desktop/release/linux-unpacked"
  local resources="${appdir}/resources"
  if [ ! -d "${appdir}" ]; then
    printf 'ERROR: electron-builder did not produce %s\n' "${appdir}"
    ls -la apps/desktop/release/ 2>/dev/null || true
    return 1
  fi
  if [ ! -f "${resources}/app.asar" ] || \
     [ ! -d "${resources}/app.asar.unpacked" ] || \
     [ ! -f "${resources}/install-stamp.json" ]; then
    printf 'ERROR: electron-builder output is missing required app resources\n'
    find "${resources}" -maxdepth 2 -printf '%M %p\n' 2>/dev/null || true
    return 1
  fi
  # Only the first three resources are installed. The skipped ones are
  # upstream's Windows icon, electron-updater metadata (Hermes ships no
  # electron-updater) and Electron's own default app, which electron44
  # provides. Anything else is a new runtime resource the app would miss on
  # Linux, so stop until it is packaged or deliberately added here.
  local entry
  for entry in "${resources}"/*; do
    case "${entry##*/}" in
      app.asar|app.asar.unpacked|install-stamp.json) ;;
      icon.ico|app-update.yml|default_app.asar) ;;
      *)
        printf 'ERROR: unexpected electron-builder resource %s — install it or allowlist it in package()\n' \
          "${entry##*/}"
        return 1
        ;;
    esac
  done
  # Install dir stays version-independent of pkgname: the launcher and the
  # packaged app reference /usr/lib/hermes-agent-desktop by path. The
  # conflicts=() entry guarantees only one variant (source or -bin) is
  # installed, so a fixed dir cannot collide.
  local libdir="/usr/lib/hermes-agent-desktop"
  install -dm755 "${pkgdir}${libdir}"
  install -Dm644 "${resources}/app.asar" \
    "${pkgdir}${libdir}/app.asar"
  cp -a "${resources}/app.asar.unpacked" \
    "${pkgdir}${libdir}/app.asar.unpacked"
  install -Dm644 "${resources}/install-stamp.json" \
    "${pkgdir}${libdir}/install-stamp.json"
  # The agent runtime comes from the hermes-agent dependency (/usr/bin/hermes).
  # This package must not ship or run an installer that writes an agent tree.
  install -Dm755 "${srcdir}/hermes-desktop" "${pkgdir}/usr/bin/${_pkgname}"
  install -Dm644 /dev/stdin "${pkgdir}/usr/share/applications/${_pkgname}.desktop" <<EOF
[Desktop Entry]
Name=Hermes
GenericName=AI Agent Client
Comment=${pkgdesc}
Exec=/usr/bin/${_pkgname} %U
Terminal=false
Type=Application
Icon=${_upstream,,}
StartupWMClass=${_upstream}
Categories=Development;
Keywords=AI;Agent;Chat;Assistant;
MimeType=x-scheme-handler/hermes;
EOF
  install -Dm644 "apps/desktop/assets/icon.png" \
    "${pkgdir}/usr/share/icons/hicolor/512x512/apps/${_upstream,,}.png"
  install -Dm644 "LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
