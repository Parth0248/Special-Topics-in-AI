#!/usr/bin/env node
/**
 * Link this project against a DeepSeek Harness checkout.
 *
 * A plugin imports `@deepseek-ai/cordis` and friends, and Node resolves those
 * from the *plugin's* directory, not the harness's. Installing our own copies
 * would be wrong even if it worked: the harness README is explicit that every
 * plugin must share the installation's single cordis instance, and a second
 * copy means `instanceof` checks against the framework quietly fail.
 *
 * So this symlinks the harness's own packages into ./node_modules rather than
 * installing anything.
 *
 *   node scripts/link-harness.mjs [path-to-harness]
 *
 * Defaults to $DSH_HARNESS_PATH, then to the location used while developing.
 */

import { mkdir, rm, symlink } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const DEFAULT_HARNESS = 'D:/Projects/deepseek-harness/deepseek-harness'
const harness = resolve(
  process.argv[2] ?? process.env.DSH_HARNESS_PATH ?? DEFAULT_HARNESS,
)

// Where each package actually lives inside the harness checkout.
const PACKAGES = {
  '@deepseek-ai/cordis': 'vendor/cordis',
  '@deepseek-ai/schemastery': 'vendor/schemastery',
  '@deepseek-ai/cosmokit': 'vendor/cosmokit',
  '@deepseek-ai/dsh-tools': 'packages/core/tools',
}

if (!existsSync(harness)) {
  console.error(`No harness checkout at ${harness}`)
  console.error('Pass the path as an argument or set DSH_HARNESS_PATH.')
  process.exit(1)
}

const scope = join(projectRoot, 'node_modules', '@deepseek-ai')
await mkdir(scope, { recursive: true })

for (const [pkg, relative] of Object.entries(PACKAGES)) {
  const target = join(harness, relative)
  if (!existsSync(target)) {
    console.error(`  missing in harness: ${relative}`)
    process.exit(1)
  }

  const link = join(projectRoot, 'node_modules', pkg)
  await rm(link, { recursive: true, force: true })
  // 'junction' is the only link type Windows creates without elevation.
  await symlink(target, link, process.platform === 'win32' ? 'junction' : 'dir')
  console.log(`  ${pkg} -> ${relative}`)
}

console.log(`\nLinked against ${harness}`)
console.log('Next: node scripts/setup.mjs')
