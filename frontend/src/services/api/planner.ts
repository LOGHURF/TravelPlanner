import type { PlanningProgress, TripRequest } from '@/types/travel'
import { parseSSEPayload } from '@/utils/sse'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL

export async function streamTravelPlan(
  request: TripRequest,
  onProgress: (progress: PlanningProgress) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/travel/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`请求失败: ${error}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法读取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const segments = buffer.split('\n\n')
    buffer = segments.pop() ?? ''

    for (const segment of segments) {
      for (const progress of parseSSEPayload(segment)) {
        onProgress(progress)
      }
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    for (const progress of parseSSEPayload(buffer)) {
      onProgress(progress)
    }
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/travel/health`)
    return response.ok
  } catch {
    return false
  }
}
