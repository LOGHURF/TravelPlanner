import type { PlanningProgress } from '@/types/travel'

export function parseSSEPayload(chunk: string): PlanningProgress[] {
  return chunk
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim())
    .filter(Boolean)
    .flatMap((payload) => {
      try {
        return [JSON.parse(payload) as PlanningProgress]
      } catch (error) {
        console.error('解析 SSE 数据失败', payload, error)
        return []
      }
    })
}
