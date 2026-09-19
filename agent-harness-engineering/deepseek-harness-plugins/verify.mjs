/**
 * Exercise both plugins against a stand-in context, without booting the harness.
 *
 * Booting the web UI proves the plugins *load*. This proves they *work*: every
 * tool is called, the event listener is fired with both a success and a
 * failure, and the loop warning is driven past its threshold.
 *
 * Run it from a harness checkout, which supplies the TypeScript loader:
 *
 *   cd /path/to/deepseek-harness
 *   node --import tsx/esm /path/to/this/verify.mjs
 */

import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const plugins = new URL('./plugins/', import.meta.url)

const scratchpad = await import(new URL('scratchpad/src/index.ts', plugins).href)
const pulse = await import(new URL('session-pulse/src/index.ts', plugins).href)

console.log('scratchpad exports:', Object.keys(scratchpad).join(', '))
console.log('session-pulse exports:', Object.keys(pulse).join(', '))

// Minimal stand-in for the parts of ctx these plugins touch.
const registered = new Map()
const listeners = new Map()
const ctx = {
  tools: { register: (tool) => registered.set(tool.name, tool) },
  on: (event, fn) => {
    listeners.set(event, fn)
    return () => listeners.delete(event)
  },
  logger: { info: (m) => console.log('  [log]', m), warn: (m) => console.log('  [warn]', m) },
}

const tmpNotes = join(tmpdir(), `dsh-scratchpad-verify-${process.pid}.json`)

console.log('\n--- loading scratchpad ---')
scratchpad.apply(ctx, scratchpad.Config({ path: tmpNotes }))
console.log('tools:', [...registered.keys()].join(', '))

console.log('\n--- exercising scratchpad ---')
console.log(' remember:', await registered.get('remember').execute({
  key: 'test-command', value: 'pnpm vitest run --reporter dot',
}))
console.log(' remember:', await registered.get('remember').execute({
  key: 'build-command', value: 'pnpm build',
}))
console.log(' recall(all):\n  ', (await registered.get('recall').execute({})).replace(/\n/g, '\n   '))
console.log(' recall(test):', await registered.get('recall').execute({ key: 'test' }))
console.log(' remember again (replace):', await registered.get('remember').execute({
  key: 'test-command', value: 'pnpm vitest run',
}))
console.log(' forget:', await registered.get('forget').execute({ key: 'build-command' }))
console.log(' forget missing:', await registered.get('forget').execute({ key: 'nope' }))
console.log(' recall after:', await registered.get('recall').execute({}))

console.log('\n--- loading session-pulse ---')
registered.clear()
pulse.apply(ctx, pulse.Config({ logCalls: false, repeatWarning: 3 }))
console.log('tools:', [...registered.keys()].join(', '))
console.log('listening for:', [...listeners.keys()].join(', '))

console.log('\n--- exercising session-pulse ---')
console.log(' pulse (before any calls):', await registered.get('pulse').execute({}))

const onResult = listeners.get('tools/result')
const ok = { content: [{ type: 'text', text: 'file contents here' }] }
const bad = { content: [{ type: 'text', text: 'Error: no such file' }] }

onResult({ name: 'read_file' }, ok)
onResult({ name: 'read_file' }, ok)
onResult({ name: 'read_file' }, bad)
onResult({ name: 'write_file' }, ok)
onResult({ name: 'pulse' }, ok) // ignored by config

console.log(' pulse (after 4 calls, 1 failure):')
console.log('  ', (await registered.get('pulse').execute({})).replace(/\n/g, '\n   '))

console.log('\n--- repeat warning at threshold 3 ---')
onResult({ name: 'run_bash' }, ok)
onResult({ name: 'run_bash' }, ok)
onResult({ name: 'run_bash' }, ok) // should warn here
