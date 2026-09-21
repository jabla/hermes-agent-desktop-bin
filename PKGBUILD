# Build PKGBUILD for the prebuilt hermes-agent-desktop-bin package.
# Kept in sync with the AUR source package hermes-agent-desktop
# (https://aur.archlinux.org/packages/hermes-agent-desktop): its patches,
# launcher and regression tests are vendored verbatim, so the prebuilt package
# behaves exactly like a local build of the source package. The scheduled bump
# job warns when that package's sources or dependencies drift from these. The
# packaged app itself is MIT-licensed (Nous Research).
pkgname=hermes-agent-desktop-bin
_pkgname=hermes-desktop          # /usr/bin launcher name (AUR convention, lowercase)
_upstream=Hermes                 # productName + executableName
_pkgver_tag=v2026.9.21
_commit=d337b736aa1e8ebecfab043842d13e4a2d2f48a3
pkgver=0.21.4
pkgrel=1
pkgdesc="Official Hermes Agent desktop app from Nous Research — chat, voice, file browser, and settings UI for the local agent runtime (prebuilt binary, CI-built)"
arch=('x86_64')
url='https://github.com/NousResearch/hermes-agent'
license=('MIT')
depends=(
  'curl' 'electron42' 'git' 'hicolor-icon-theme' 'libnotify' 'libsecret'
  'nodejs>=22.22' 'npm' 'uv' 'xdg-utils'
)
optdepends=(
  'hermes-agent-bin: run the app on the installed Hermes runtime instead of a local install'
  'libayatana-appindicator: tray indicator support'
  'google-chrome: local browser automation (or chromium)'
  'chromium: local browser automation (or google-chrome)'
  'ffmpeg: audio and video processing'
  'ripgrep: fast file content search'
)
makedepends=('python')
provides=('hermes-agent-desktop')
conflicts=('hermes-agent-desktop')
options=('!debug')
source=(
  "hermes-agent-${_pkgver_tag}.tar.gz::${url}/archive/refs/tags/${_pkgver_tag}.tar.gz"
  'system-electron-resources.patch'
  'pin-packaged-runtime.patch'
  'fix-voice-prefs-storage-spy.patch'
  'system-browser.patch'
  'packaged-bootstrap.patch'
  'runtime-policy.patch'
  'hermes-desktop'
  'launcher.test.cjs'
  'launcher-runtime-root.test.cjs'
  'runtime.test.cjs'
  'runtime-policy.test.py'
)
# NOTE: makepkg also validates the local files. The bump automation maintains
# the tarball sum; after editing a local file run
# `python3 scripts/bump-pkgbuild.py --sync-sums`, or the build fails at
# "Validating source files".
sha256sums=('c38cd7639707fe695f94ecd948ee7a9ce7de0c57461e39fb022966d79a692a65'
            'ee465a1aa2ad5789fa5c7b3a89993bbf0e68efddbf27c93109519b72a4cb90f7'
            '5c185a979974f7a9a476b32e5e8ac21dfcd907ed7d0e671cfb294ecf17d021b0'
            '7f8500e475a13466ecba2bb74e73fbbcba8dcb70bcbf4e789faf7a8f27df0cac'
            'fa8933a96e58575e7d4f876a7eb380d6c1723233832b787a46fb158f79df7718'
            '960009893274b567eca91f42ae168661efda18646f2783b75b831e1d71190cb1'
            '9fca70bad0c6db28e9499761a570e8bca83c9666e6bb8ec35401b8aef3424a8d'
            'ac7b80c86ad6e3f2195863e1f2d100f1cce8c98e9b097dc6cf121a636afc7b84'
            'dcb84ac7c5f5a7168d089ba082a8c8c77cf3955abc79775f530aee870a30d5df'
            '8ee5ff76ab7afb5ddeade96ed82bcc7e546e17d9e9539e08931084e03ee79c7f'
            '1a39719fd6b6ac2e773e6f72bd55ef313469734cf72dbe1f9adf7bff0979c873'
            '9be2b77733674bbfdb1a39ddc902ac9f751f49ce7398675c89190eb0cc6759ea')

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
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/system-electron-resources.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/pin-packaged-runtime.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/fix-voice-prefs-storage-spy.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/system-browser.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/packaged-bootstrap.patch"
  patch --batch --fuzz=0 -Np1 -i "${srcdir}/runtime-policy.patch"
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
  # Arch's versioned runtime instead of downloading a second copy.
  local electron_dir='apps/desktop/node_modules/electron'

  # Upstream locks an older Electron major (40.x at the time of writing) than
  # the runtime used here. electron42 is the oldest major that still receives
  # security fixes, so running the app on a newer runtime is deliberate. The
  # opposite direction is not safe: an app written against a newer major may
  # call APIs this runtime lacks, so stop instead of shipping that build.
  local locked_electron system_electron
  locked_electron="$(node -p "require('./${electron_dir}/package.json').version")"
  system_electron="$(< /usr/lib/electron42/version)"
  if (( ${locked_electron%%.*} > ${system_electron%%.*} )); then
    printf 'ERROR: upstream locks Electron %s, newer than the system runtime %s — move the package to a newer electronNN\n' \
      "${locked_electron}" "${system_electron}"
    return 1
  elif (( ${locked_electron%%.*} < ${system_electron%%.*} )); then
    printf 'NOTE: upstream locks Electron %s; the package runs on system Electron %s\n' \
      "${locked_electron}" "${system_electron}"
  fi

  rm -rf "${electron_dir}/dist"
  ln -s /usr/lib/electron42 "${electron_dir}/dist"
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
  local electron_version
  electron_version="$(< /usr/lib/electron42/version)"
  # Keep upstream's package.json and lockfile pins intact for deterministic
  # npm ci. The builder CLI override below selects the system runtime without
  # pretending that the locked npm tooling package was resolved at a new pin.
  npm run build

  # Upstream writes the wall clock into the bundled install stamp. Normalize it
  # to makepkg's reproducible-build epoch before electron-builder consumes it.
  local build_time
  build_time="$(date -u -d "@${SOURCE_DATE_EPOCH}" '+%Y-%m-%dT%H:%M:%S.000Z')"
  sed -i -E \
    "s|(\"builtAt\": \")[^\"]+(\")|\1${build_time}\2|" \
    build/install-stamp.json
  grep -Fq "\"builtAt\": \"${build_time}\"" build/install-stamp.json

  # Upstream's builder wrapper resolves node_modules/electron/dist and passes it
  # as electronDist. prepare() links that directory to Arch's Electron runtime.
  # package() keeps only the app resources, so electron42 remains their owner.
  npm run builder -- --linux dir \
    -c.electronVersion="${electron_version}"
}

check() {
  cd "$(_extract_dir)"
  _set_npm_env
  export npm_config_offline=true
  node "${srcdir}/launcher.test.cjs"
  node "${srcdir}/launcher-runtime-root.test.cjs"
  node "${srcdir}/runtime.test.cjs" "$PWD/scripts/install.sh" "$PWD"
  python -B "${srcdir}/runtime-policy.test.py" "$PWD"
  npm run typecheck --workspace apps/desktop

  # Upstream's full vitest suite (~1000 files) runs in upstream's CI; here it
  # took ~90% of the build time and exercised upstream code on Arch's system
  # Node, which the app does not run on. Run the tests that cover what the
  # patches change instead: the patched tests and every test importing a
  # patched module. The file list follows the patches automatically.
  local patched=()
  mapfile -t patched < <(sed -n 's|^+++ b/apps/desktop/||p' "${srcdir}"/*.patch | sort -u)
  (cd apps/desktop && npx vitest related --run --passWithNoTests "${patched[@]}")

  # node-pty is the only native Node addon shipped by Hermes. Load the staged
  # module with the exact Electron runtime used by the installed launcher; its
  # N-API build must not merely load under makepkg's system Node.
  local node_pty_root="${PWD}/apps/desktop/release/linux-unpacked/resources/app.asar.unpacked/dist/node_modules/node-pty"
  test -f "${node_pty_root}/package.json"
  # Bypass Arch's launcher here: it injects the user's electron42 flags, which
  # are valid in Chromium mode but rejected while ELECTRON_RUN_AS_NODE is set.
  env ELECTRON_RUN_AS_NODE=1 NODE_PTY_ROOT="${node_pty_root}" \
    /usr/lib/electron42/electron -e \
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
  # electron-updater) and Electron's own default app, which electron42
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
  # Bootstrap uses the reviewed installer and patch from this exact package,
  # not an unpatched installer downloaded separately from GitHub.
  install -Dm644 scripts/install.sh "${pkgdir}${libdir}/runtime/install.sh"
  install -Dm644 "${srcdir}/runtime-policy.patch" \
    "${pkgdir}${libdir}/runtime/runtime-policy.patch"
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
