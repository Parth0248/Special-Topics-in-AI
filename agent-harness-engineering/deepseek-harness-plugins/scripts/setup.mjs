#!/usr/bin/env node
/**
 * Generate cordis.local.yml from the template.
 *
 * The Cordis loader resolves plugin modules by absolute path, which is machine
 * specific and cannot be committed. This writes the real paths once so the
 * patch file stays reproducible on any checkout.
 */

import { readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const template = join(projectRoot, 'cordis.template.yml')
const output = join(projectRoot, 'cordis.local.yml')

// Cordis reads YAML paths with forward slashes on every platform.
const rootForYaml = projectRoot.replace(/\\/g, '/')

const rendered = (await readFile(template, 'utf8')).replaceAll('{{ROOT}}', rootForYaml)
await writeFile(output, rendered, 'utf8')

console.log(`Wrote ${output}`)
console.log('\nBoot the harness with it:\n')
console.log(`  pnpm dsh web --patch "${output.replace(/\\/g, '/')}"\n`)
