/**
 * session-pulse — what did the agent actually do?
 *
 * The transcript shows what the agent said. It does not show that read_file was
 * called forty times, that three of those failed, or that one tool accounts for
 * most of the session's wall time. That information exists only as it streams
 * past, and then it is gone.
 *
 * This listens to `tools/result` and keeps a running tally, exposed through a
 * `pulse` tool so the agent can read its own behaviour back.
 *
 * Where `scratchpad` registers tools, this one registers an event listener —
 * the two plugins deliberately use different seams of the framework.
 */

import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'session-pulse'
export const inject = ['tools']

export interface Config {
  /** Print each tool call to the server log as it happens. */
  logCalls: boolean
  /** Warn when one tool is called more than this many times — usually a loop. */
  repeatWarning: number
  /** Ignore these tool names in the tally, so the reporter is not its own subject. */
  ignore: string[]
}

export const Config: Schema<Config> = Schema.object({
  logCalls: Schema.boolean().default(false),
  repeatWarning: Schema.number().default(15),
  ignore: Schema.array(String).default(['pulse']),
})

interface Stat {
  calls: number
  failures: number
  totalMs: number
}

export function apply(ctx: Context, config: Config) {
  const stats = new Map<string, Stat>()
  const started = Date.now()
  let warned = new Set<string>()

  function statFor(tool: string): Stat {
    let stat = stats.get(tool)
    if (!stat) {
      stat = { calls: 0, failures: 0, totalMs: 0 }
      stats.set(tool, stat)
    }
    return stat
  }

  // Registered through ctx.on, so it is removed automatically when the plugin
  // unloads or hot-reloads. No manual teardown.
  ctx.on('tools/result', (exec, result) => {
    const tool = exec?.name
    if (!tool || config.ignore.includes(tool)) return

    const stat = statFor(tool)
    stat.calls += 1

    const text = (result?.content ?? [])
      .map((block: { type: string, text?: string }) => (block.type === 'text' ? block.text ?? '' : ''))
      .join('')

    if (result?.isError || /^error[: ]/i.test(text.trim())) {
      stat.failures += 1
    }

    if (config.logCalls) {
      ctx.logger?.info?.(`[pulse] ${tool} (${stat.calls} calls, ${stat.failures} failed)`)
    }

    if (stat.calls === config.repeatWarning && !warned.has(tool)) {
      warned.add(tool)
      ctx.logger?.warn?.(
        `[pulse] ${tool} has run ${stat.calls} times this session — possible loop.`,
      )
    }
  })

  ctx.tools.register(defineTool({
    name: 'pulse',
    description:
      'Report what this session has actually done: which tools ran, how often, ' +
      'and how many failed. Useful when you suspect you are repeating yourself ' +
      'or want to tell the user where the time went.',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute() {
      if (stats.size === 0) return 'No tools have run yet this session.'

      const minutes = Math.max(1, Math.round((Date.now() - started) / 60000))
      const rows = [...stats.entries()].sort((a, b) => b[1].calls - a[1].calls)
      const totalCalls = rows.reduce((sum, [, s]) => sum + s.calls, 0)
      const totalFailures = rows.reduce((sum, [, s]) => sum + s.failures, 0)

      const lines = rows.map(([tool, stat]) => {
        const failed = stat.failures > 0 ? `, ${stat.failures} failed` : ''
        return `  ${tool}: ${stat.calls} call${stat.calls === 1 ? '' : 's'}${failed}`
      })

      const busiest = rows[0]
      const note =
        busiest && busiest[1].calls >= config.repeatWarning
          ? `\n\n${busiest[0]} has run ${busiest[1].calls} times — worth checking you are not looping.`
          : ''

      return (
        `${totalCalls} tool calls over ~${minutes} minute${minutes === 1 ? '' : 's'}` +
        `, ${totalFailures} failed.\n\n${lines.join('\n')}${note}`
      )
    },
  }))

  ctx.logger?.info?.('session-pulse watching tool activity')
}
