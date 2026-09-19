/**
 * scratchpad — notes that outlive the session.
 *
 * A conversation ends and everything the agent worked out goes with it. The
 * next session starts by rediscovering the same facts: which command runs the
 * tests, which module owns the retry logic, which approach was already tried
 * and abandoned.
 *
 * This gives the agent somewhere to write that down. Three tools over one JSON
 * file on disk: remember, recall, forget.
 */

import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { homedir } from 'node:os'

export const name = 'scratchpad'
export const inject = ['tools']

export interface Config {
  /** Where the notes live. `~` expands to the home directory. */
  path: string
  /** Refuse to add a note past this many, so the file cannot grow without bound. */
  maxNotes: number
  /** Longest single note, in characters. */
  maxNoteLength: number
}

export const Config: Schema<Config> = Schema.object({
  path: Schema.string().default('~/.dsh/scratchpad.json'),
  maxNotes: Schema.number().default(200),
  maxNoteLength: Schema.number().default(2000),
})

interface Note {
  key: string
  value: string
  written: string
}

function count(n: number): string {
  return `${n} note${n === 1 ? '' : 's'}`
}

function expandHome(path: string): string {
  return path.startsWith('~') ? resolve(homedir(), path.slice(1).replace(/^[\\/]/, '')) : resolve(path)
}

async function readNotes(file: string): Promise<Note[]> {
  try {
    const raw = await readFile(file, 'utf8')
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Note[]) : []
  } catch {
    // A missing or corrupt file is an empty scratchpad, not an error. Failing
    // the tool here would make every later call fail too.
    return []
  }
}

async function writeNotes(file: string, notes: Note[]): Promise<void> {
  await mkdir(dirname(file), { recursive: true })
  await writeFile(file, `${JSON.stringify(notes, null, 2)}\n`, 'utf8')
}

export function apply(ctx: Context, config: Config) {
  const file = expandHome(config.path)

  ctx.tools.register(defineTool({
    name: 'remember',
    description:
      'Save a fact for future sessions. Use it for things that were expensive ' +
      'to work out and will be true again next time: build commands, where a ' +
      'subsystem lives, an approach that failed and why. Writing the same key ' +
      'again replaces the earlier note.',
    parameters: {
      key: { type: 'string', required: true, description: 'Short identifier, e.g. "test-command".' },
      value: { type: 'string', required: true, description: 'The fact worth keeping.' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      if (args.value.length > config.maxNoteLength) {
        return `Not saved: the note is ${args.value.length} characters, over the ${config.maxNoteLength} limit.`
      }

      const notes = await readNotes(file)
      const existing = notes.findIndex(note => note.key === args.key)

      if (existing < 0 && notes.length >= config.maxNotes) {
        return `Not saved: the scratchpad holds ${config.maxNotes} notes. Forget one first.`
      }

      const note: Note = { key: args.key, value: args.value, written: new Date().toISOString() }
      if (existing >= 0) {
        notes[existing] = note
        await writeNotes(file, notes)
        return `Replaced the note under "${args.key}".`
      }

      notes.push(note)
      await writeNotes(file, notes)
      return `Saved "${args.key}". ${count(notes.length)} on the scratchpad.`
    },
  }))

  ctx.tools.register(defineTool({
    name: 'recall',
    description:
      'Read back saved notes. Without a key it lists everything; with one it ' +
      'returns notes whose key or contents match.',
    parameters: {
      // An optional parameter omits `required` entirely; the schema compiler
      // rejects `required: false`.
      key: { type: 'string', description: 'Filter. Omit to list everything.' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const notes = await readNotes(file)
      if (notes.length === 0) return 'The scratchpad is empty.'

      const needle = args.key?.toLowerCase()
      const matches = needle
        ? notes.filter(n => n.key.toLowerCase().includes(needle) || n.value.toLowerCase().includes(needle))
        : notes

      if (matches.length === 0) return `Nothing on the scratchpad matches "${args.key}".`

      return matches.map(n => `${n.key}: ${n.value}`).join('\n')
    },
  }))

  ctx.tools.register(defineTool({
    name: 'forget',
    description: 'Delete a note by key, for facts that have gone stale.',
    parameters: {
      key: { type: 'string', required: true, description: 'The key to remove.' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const notes = await readNotes(file)
      const remaining = notes.filter(n => n.key !== args.key)

      if (remaining.length === notes.length) return `No note is saved under "${args.key}".`

      await writeNotes(file, remaining)
      const left = remaining.length
      return `Forgot "${args.key}". ${count(left)} ${left === 1 ? 'remains' : 'remain'}.`
    },
  }))

  ctx.logger?.info?.(`scratchpad ready at ${file}`)
}
