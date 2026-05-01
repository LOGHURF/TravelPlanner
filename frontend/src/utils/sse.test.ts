import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseSSEPayload } from '@/utils/sse'

describe('parseSSEPayload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('extracts multiple data rows from sse chunk', () => {
    const payload = [
      'data: {"type":"progress","message":"开始规划"}',
      '',
      'data: {"type":"agent_start","agentId":"attraction_agent","label":"景点 Agent","status":"running","progress":12}',
      '',
      'data: {"type":"done"}',
    ].join('\n')

    expect(parseSSEPayload(payload)).toEqual([
      { type: 'progress', message: '开始规划' },
      {
        type: 'agent_start',
        agentId: 'attraction_agent',
        label: '景点 Agent',
        status: 'running',
        progress: 12,
      },
      { type: 'done' },
    ])
  })

  it('ignores malformed rows', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const payload = ['event: message', 'data: not-json', 'data: {"type":"done"}'].join('\n')
    expect(parseSSEPayload(payload)).toEqual([{ type: 'done' }])
  })
})
