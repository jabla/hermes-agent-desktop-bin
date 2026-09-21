// Tests for this package's own divergence from hermes-agent-desktop: the
// launcher points the app at the runtime installed by hermes-agent(-bin) when
// one is installed, and leaves the upstream first-run flow alone when there is
// none. The vendored launcher.test.cjs covers the browser detection upstream
// ships; this file covers what this package adds.
//
// Run with: node launcher-runtime-root.test.cjs
// HERMES_LAUNCHER_PATH can point at a launcher under test (defaults to the
// launcher next to this file).
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const { test } = require('node:test')

const launcher = fs.readFileSync(
  process.env.HERMES_LAUNCHER_PATH || path.join(__dirname, 'hermes-desktop'), 'utf8')

const VARS = [
  'HERMES_DESKTOP_IS_PACKAGED',
  'HERMES_DESKTOP_RESOURCES_PATH',
  'HERMES_DESKTOP_PACKAGE_MANAGED_RUNTIME',
  'HERMES_DESKTOP_HERMES_ROOT',
]

function fakeRuntime(dir, { withVenv = true } = {}) {
  fs.mkdirSync(path.join(dir, 'hermes_cli'), { recursive: true })
  fs.writeFileSync(path.join(dir, 'hermes_cli', 'main.py'), '# stub\n')
  if (withVenv) {
    fs.mkdirSync(path.join(dir, 'venv', 'bin'), { recursive: true })
    fs.writeFileSync(path.join(dir, 'venv', 'bin', 'python'), '#!/bin/sh\nexit 0\n', { mode: 0o755 })
  }
}

function tempDir(t, prefix) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix))
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }))
  return dir
}

// Runs the real launcher with only the final process launch replaced, so the
// wrapper is exercised without starting Electron or touching the user's home.
function runLauncher(t, { runtimeRoot, preSetRoot } = {}) {
  const home = tempDir(t, 'hermes-launcher-home-')
  fs.mkdirSync(path.join(home, '.config'))
  const env = { HOME: home, PATH: '/usr/bin:/bin' }
  if (runtimeRoot !== undefined) env.HERMES_DESKTOP_RUNTIME_ROOT = runtimeRoot
  if (preSetRoot !== undefined) env.HERMES_DESKTOP_HERMES_ROOT = preSetRoot
  const printArgs = VARS.map((v) => `"\${${v}:-}"`).join(' ')
  const result = spawnSync('/bin/bash', ['-c', `
    exec() {
      printf '%s\\0' ${printArgs}
    }
    ${launcher}
  `, 'hermes-desktop'], { env, cwd: home, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const parts = result.stdout.split('\0').slice(0, -1)
  assert.equal(parts.length, VARS.length, `launcher printed ${parts.length} of ${VARS.length} variables`)
  return Object.fromEntries(VARS.map((name, index) => [name, parts[index]]))
}

test('a runtime installed by the package is used', (t) => {
  const runtime = tempDir(t, 'hermes-runtime-stub-')
  fakeRuntime(runtime)
  assert.equal(runLauncher(t, { runtimeRoot: runtime }).HERMES_DESKTOP_HERMES_ROOT, runtime)
})

test('a runtime directory without a usable venv is ignored', (t) => {
  const runtime = tempDir(t, 'hermes-runtime-stub-')
  fakeRuntime(runtime, { withVenv: false })
  assert.equal(runLauncher(t, { runtimeRoot: runtime }).HERMES_DESKTOP_HERMES_ROOT, '')
})

test('a missing runtime directory is ignored', (t) => {
  const missing = path.join(tempDir(t, 'hermes-runtime-parent-'), 'hermes-agent')
  assert.equal(runLauncher(t, { runtimeRoot: missing }).HERMES_DESKTOP_HERMES_ROOT, '')
})

test('an explicitly configured runtime root is never overwritten', (t) => {
  const runtime = tempDir(t, 'hermes-runtime-stub-')
  fakeRuntime(runtime)
  const values = runLauncher(t, { runtimeRoot: runtime, preSetRoot: '/home/user/my/checkout' })
  assert.equal(values.HERMES_DESKTOP_HERMES_ROOT, '/home/user/my/checkout')
})

test('the packaged runtime invariants stay exported', (t) => {
  const missing = path.join(tempDir(t, 'hermes-runtime-parent-'), 'hermes-agent')
  const values = runLauncher(t, { runtimeRoot: missing })
  assert.equal(values.HERMES_DESKTOP_IS_PACKAGED, '1')
  assert.equal(values.HERMES_DESKTOP_RESOURCES_PATH, '/usr/lib/hermes-agent-desktop')
  assert.equal(values.HERMES_DESKTOP_PACKAGE_MANAGED_RUNTIME, '1')
})
