import { defineStore } from 'pinia'
import {
  createPlanningAgents,
  planningAgentDefinitionMap,
  planningAgentDefinitions,
} from '@/constants/planningAgents'
import { streamTravelPlan } from '@/services/api/planner'
import {
  clearDraftRequest,
  readDraftRequest,
  saveDraftRequest,
} from '@/services/storage/planStorage'
import type {
  Attraction,
  Hotel,
  PlanningAgentId,
  PlanningEventRecord,
  PlanningProgress,
  PlanningAgentState,
  PlanningResultHighlight,
  PlanningState,
  Restaurant,
  TripPlan,
  TripRequest,
  WeatherInfo,
} from '@/types/travel'

const MAX_EVENT_LOG = 24

const STAGE_LABELS = {
  prepare: '主控调度',
  parallel: '天气检查',
  refine: '锚点验真',
  enrich: '周边补全',
  route: '路线体检 / 行程拼装',
  evaluate: '方案审核',
  repair: '定向修复',
  finalize: '最终成稿',
} as const

function createIdleState(): PlanningState {
  return {
    step: 'idle',
    progress: 0,
    messages: [],
    eventLog: [],
    agents: createPlanningAgents(),
    attractions: [],
    hotels: [],
    restaurants: [],
    weather: [],
  }
}

function resolveTransportCounts(data: PlanningState['routes']) {
  return {
    days: data?.daily_plan?.length || 0,
  }
}

function resolveCountSummary(counts: Record<string, number>) {
  const entries = Object.entries(counts).filter(([, value]) => value > 0)
  if (!entries.length) {
    return ''
  }

  return entries
    .map(([key, value]) => {
      switch (key) {
        case 'items':
          return `${value} 项`
        case 'days':
          return `${value} 天`
        case 'attractions':
          return `${value} 景点`
        case 'hotels':
          return `${value} 酒店`
        case 'score':
          return `${value} 分`
        case 'issues':
          return `${value} 问题`
        case 'repairs':
          return `${value} 修复`
        case 'iteration':
          return `第 ${value} 轮`
        case 'targets':
          return `${value} 目标`
        default:
          return `${value} ${key}`
      }
    })
    .join(' · ')
}

function getLastLog(logs: string[]) {
  return logs.length ? logs[logs.length - 1] : undefined
}

function eventRecordId(event: Pick<PlanningEventRecord, 'timestamp'>, sequence: number) {
  return `${event.timestamp || 'event'}-${sequence}`
}

function parseEventRecordSequence(id?: string) {
  const match = String(id || '').match(/-(\d+)$/)
  if (!match) {
    return null
  }

  const sequence = Number(match[1])
  return Number.isFinite(sequence) ? sequence : null
}

function isKnownAgentId(agentId?: string): agentId is PlanningAgentId {
  return Boolean(agentId && planningAgentDefinitionMap[agentId as PlanningAgentId])
}

function normalizePlanningAgents(
  agents?: Partial<Record<string, Partial<PlanningAgentState>>>,
): Record<PlanningAgentId, PlanningAgentState> {
  const currentAgents = createPlanningAgents()
  if (!agents) {
    return currentAgents
  }

  for (const definition of planningAgentDefinitions) {
    const restored = agents[definition.id]
    if (!restored) {
      continue
    }

    currentAgents[definition.id] = {
      ...currentAgents[definition.id],
      status: restored.status || currentAgents[definition.id].status,
      progress: Number(restored.progress || 0),
      logs: Array.isArray(restored.logs) ? restored.logs : [],
      counts: restored.counts || {},
      lastMessage: restored.lastMessage,
      startedAt: restored.startedAt,
      finishedAt: restored.finishedAt,
    }
  }

  return currentAgents
}

function normalizeEventLog(records: PlanningEventRecord[]) {
  const normalized: PlanningEventRecord[] = []
  const seen = new Set<string>()
  let nextSequence = 0

  for (const record of records) {
    if (record.agentId && !isKnownAgentId(record.agentId)) {
      continue
    }

    const parsedSequence = parseEventRecordSequence(record.id)
    if (parsedSequence !== null) {
      nextSequence = Math.max(nextSequence, parsedSequence + 1)
    }

    let id = record.id
    if (!id || seen.has(id)) {
      id = eventRecordId(record, nextSequence)
      nextSequence += 1
    }

    seen.add(id)
    normalized.push({
      ...record,
      id,
    })
  }

  nextSequence = Math.max(nextSequence, normalized.length)

  return {
    eventLog: normalized.slice(-MAX_EVENT_LOG),
    nextSequence,
  }
}

function createEventRecord(event: PlanningProgress, sequence: number): PlanningEventRecord | null {
  const timestamp = event.timestamp
  const baseRecord = {
    id: eventRecordId({ timestamp }, sequence),
    eventType: event.type,
    timestamp,
    agentId: event.agentId,
    label: event.label,
    phase: event.phase,
    status: event.status,
  } satisfies Omit<PlanningEventRecord, 'message'>

  switch (event.type) {
    case 'progress':
      return event.message
        ? {
            ...baseRecord,
            message: event.message,
          }
        : null
    case 'agent_start':
    case 'agent_progress':
    case 'agent_done':
    case 'agent_error':
      return {
        ...baseRecord,
        message: event.message || event.label || 'Agent 状态更新',
      }
    case 'agent_result':
      return {
        ...baseRecord,
        message: event.message || formatResultEventMessage(event),
      }
    case 'attractions':
    case 'hotels':
    case 'restaurants':
    case 'weather':
    case 'routes':
    case 'itinerary':
      return {
        ...baseRecord,
        message: formatResultEventMessage(event),
      }
    case 'error':
      return {
        ...baseRecord,
        message: event.message || '规划失败，请稍后重试',
      }
    case 'done':
      return {
        ...baseRecord,
        message: event.message || '规划流程结束',
      }
    default:
      return null
  }
}

function appendEventLog(nextState: PlanningState, event: PlanningProgress, sequence: number) {
  const record = createEventRecord(event, sequence)
  if (!record) {
    return sequence
  }

  const previous = nextState.eventLog[nextState.eventLog.length - 1]
  if (previous) {
    if (previous.message === record.message) {
      if (previous.eventType === 'progress' && record.agentId) {
        nextState.eventLog = [...nextState.eventLog.slice(0, -1), record]
        return sequence + 1
      }
      if (previous.agentId && record.eventType === 'progress') {
        return sequence
      }
      if (previous.eventType === record.eventType && previous.agentId === record.agentId) {
        return sequence
      }
    }
  }

  nextState.eventLog = [...nextState.eventLog, record].slice(-MAX_EVENT_LOG)
  return sequence + 1
}

function resolveArrayCount(data: unknown) {
  return Array.isArray(data) ? data.length : 0
}

function formatResultEventMessage(event: PlanningProgress) {
  switch (event.type) {
    case 'agent_result': {
      const countSummary = resolveCountSummary(event.counts || {})
      return countSummary ? `阶段结果已返回：${countSummary}` : '阶段结果已返回'
    }
    case 'attractions':
      return `景点结果已更新（${resolveArrayCount(event.data)}项）`
    case 'hotels':
      return `酒店结果已更新（${resolveArrayCount(event.data)}项）`
    case 'restaurants':
      return `餐饮结果已更新（${resolveArrayCount(event.data)}项）`
    case 'weather':
      return `天气结果已更新（${resolveArrayCount(event.data)}天）`
    case 'routes': {
      const routes = event.data as PlanningState['routes']
      const days = routes?.daily_plan?.length || 0
      return `交通动线已更新（${days}天）`
    }
    case 'itinerary': {
      const itinerary = event.data as TripPlan | undefined
      const days = itinerary?.days.length || 0
      return `最终行程已生成（${days}天）`
    }
    default:
      return event.message || '结果已更新'
  }
}

function assignAgentCounts(
  nextState: PlanningState,
  agentId: PlanningAgentId,
  counts: Record<string, number>,
) {
  const agent = nextState.agents[agentId]
  if (!agent) {
    return
  }

  nextState.agents = {
    ...nextState.agents,
    [agentId]: {
      ...agent,
      counts: {
        ...agent.counts,
        ...counts,
      },
    },
  }
}

function resolveOverallProgress(state: PlanningState): number {
  const totalWeight = planningAgentDefinitions.reduce((total, agent) => total + agent.weight, 0)
  const completedWeight = planningAgentDefinitions.reduce((total, definition) => {
    const agent = state.agents[definition.id]
    const ratio =
      agent.status === 'completed'
        ? 1
        : agent.status === 'error'
          ? Math.max(agent.progress, 12) / 100
          : agent.progress / 100

    return total + definition.weight * ratio
  }, 0)

  return Math.min(100, Math.round((completedWeight / totalWeight) * 100))
}

function buildResultHighlight(
  id: PlanningResultHighlight['id'],
  label: string,
  items: string[],
  summary: string,
  status: PlanningResultHighlight['status'],
): PlanningResultHighlight {
  const count = items.length
  return {
    id,
    label,
    count,
    status,
    summary,
    preview: items.slice(0, 3),
  }
}

function pickAttractionPreview(attractions: Attraction[]) {
  return attractions
    .map((item) => {
      const extras = [item.category, item.visit_duration].filter(Boolean).join(' · ')
      return extras ? `${item.name} · ${extras}` : item.name
    })
    .filter(Boolean)
}

function pickHotelPreview(hotels: Hotel[]) {
  return hotels
    .map((item) => {
      const extras = [
        item.hotel_level,
        item.price_per_night ? `￥${Math.round(item.price_per_night)}/晚` : '',
      ]
        .filter(Boolean)
        .join(' · ')
      return extras ? `${item.name} · ${extras}` : item.name
    })
    .filter(Boolean)
}

function pickRestaurantPreview(restaurants: Restaurant[]) {
  return restaurants
    .map((item) => {
      const extras = [item.cuisine_type, item.price_per_person ? `￥${item.price_per_person}/人` : '']
        .filter(Boolean)
        .join(' · ')
      return extras ? `${item.name} · ${extras}` : item.name
    })
    .filter(Boolean)
}

function pickWeatherPreview(weather: WeatherInfo[]) {
  return weather
    .map((item) => {
      const tempRange =
        item.day_temp || item.night_temp ? `${item.night_temp}~${item.day_temp}°C` : ''
      return [item.date, item.day_weather, tempRange].filter(Boolean).join(' · ')
    })
    .filter(Boolean)
}

export const usePlannerStore = defineStore('planner', {
  state: () => ({
    request: null as TripRequest | null,
    state: createIdleState(),
    isStreaming: false,
    hasStarted: false,
    eventSequence: 0,
  }),
  getters: {
    hasRequest: (store) => Boolean(store.request),
    itinerary: (store) => store.state.itinerary,
    recentEvents: (store) => store.state.eventLog.slice(-8).reverse(),
    activeAgentId: (store): PlanningAgentId => {
      const latestRunningRecord = [...store.state.eventLog]
        .reverse()
        .find((record) => {
          if (!record.agentId) {
            return false
          }
          if (!['agent_start', 'agent_progress'].includes(record.eventType)) {
            return false
          }
          const agent = store.state.agents[record.agentId]
          return Boolean(agent && agent.status === 'running')
        })

      if (latestRunningRecord?.agentId) {
        return latestRunningRecord.agentId
      }

      const latestCompletedRecord = [...store.state.eventLog]
        .reverse()
        .find((record) => record.agentId && isKnownAgentId(record.agentId) && record.eventType === 'agent_done')

      if (latestCompletedRecord?.agentId) {
        return latestCompletedRecord.agentId
      }

      const firstRunningAgent = planningAgentDefinitions.find(
        (definition) => store.state.agents[definition.id].status === 'running',
      )
      return firstRunningAgent?.id || 'orchestrator'
    },
    currentStageLabel(): string {
      if (this.state.step === 'error') {
        return '规划异常'
      }
      if (this.state.step === 'completed') {
        return '最终行程已生成'
      }

      const runningAgents = planningAgentDefinitions.filter(
        (definition) => this.state.agents[definition.id].status === 'running',
      )
      const hasParallelRunning = runningAgents.some((agent) => agent.phase === 'parallel')

      if (hasParallelRunning) {
        return STAGE_LABELS.parallel
      }

      const activeAgent = this.state.agents[this.activeAgentId] || this.state.agents.orchestrator
      if (
        this.activeAgentId === 'orchestrator' &&
        activeAgent.logs.some((line) => line.includes('定向修复'))
      ) {
        return STAGE_LABELS.repair
      }
      return STAGE_LABELS[activeAgent.phase] || '准备开始规划'
    },
    resultHighlights(): PlanningResultHighlight[] {
      const routeDays = this.state.routes?.daily_plan?.length || 0
      const attractionStatus =
        this.state.attractions.length === 0
          ? 'empty'
          : this.state.agents.nearby_poi_agent.status === 'completed'
            ? 'ready'
            : 'partial'
      const hotelStatus =
        this.state.hotels.length === 0
          ? 'empty'
          : this.state.agents.nearby_poi_agent.status === 'completed'
            ? 'ready'
            : 'partial'
      const restaurantStatus =
        this.state.restaurants.length === 0
          ? 'empty'
          : this.state.agents.nearby_poi_agent.status === 'completed'
            ? 'ready'
            : 'partial'
      const weatherStatus =
        this.state.weather.length === 0
          ? 'empty'
          : this.state.agents.weather_agent.status === 'completed'
            ? 'ready'
            : 'partial'
      const routeStatus =
        routeDays === 0
          ? 'empty'
          : this.state.agents.itinerary_composer_agent.status === 'completed'
            ? 'ready'
            : 'partial'

      return [
        buildResultHighlight(
          'attractions',
          '景点',
          pickAttractionPreview(this.state.attractions),
          this.state.attractions.length
            ? `已筛出 ${this.state.attractions.length} 个景点`
            : '等待景点结果返回',
          attractionStatus,
        ),
        buildResultHighlight(
          'hotels',
          '酒店',
          pickHotelPreview(this.state.hotels),
          this.state.hotels.length
            ? `已锁定 ${this.state.hotels.length} 组住宿候选`
            : '等待酒店结果返回',
          hotelStatus,
        ),
        buildResultHighlight(
          'restaurants',
          '餐饮',
          pickRestaurantPreview(this.state.restaurants),
          this.state.restaurants.length
            ? `已补充 ${this.state.restaurants.length} 个餐饮推荐`
            : '等待餐饮结果返回',
          restaurantStatus,
        ),
        buildResultHighlight(
          'weather',
          '天气',
          pickWeatherPreview(this.state.weather),
          this.state.weather.length
            ? `已补充 ${this.state.weather.length} 天气切片`
            : '等待天气结果返回',
          weatherStatus,
        ),
        {
          id: 'routes',
          label: '交通',
          count: routeDays,
          status: routeStatus,
          summary: routeDays ? `已生成 ${routeDays} 天城市动线` : '等待交通结果返回',
          preview: [
            this.state.routes?.suggested_mode ? `推荐 ${this.state.routes.suggested_mode}` : '',
            this.state.routes?.planning_reason || '',
          ].filter(Boolean),
        },
        {
          id: 'itinerary',
          label: '成稿',
          count: this.state.itinerary?.days.length || 0,
          status: this.state.itinerary ? 'ready' : 'empty',
          summary: this.state.itinerary ? '最终行程已生成' : '等待最终行程生成',
          preview: this.state.itinerary
            ? [
                this.state.itinerary.city,
                this.state.itinerary.days[0]?.description || '',
                this.state.itinerary.days[0]?.attractions?.[0]?.name || '',
              ].filter(Boolean)
            : [],
        },
      ]
    },
  },
  actions: {
    hydrateDraft() {
      if (!this.request) {
        this.request = readDraftRequest()
      }
      return this.request
    },
    setRequest(request: TripRequest) {
      this.request = request
      saveDraftRequest(request)
      this.state = {
        ...createIdleState(),
        step: 'planning',
        messages: ['开始规划本次旅程...'],
      }
      this.hasStarted = false
      this.eventSequence = 0
    },
    restoreSnapshot(request: TripRequest, snapshot: PlanningState) {
      const normalized = normalizeEventLog(snapshot.eventLog || [])
      this.request = request
      saveDraftRequest(request)
      this.state = {
        ...createIdleState(),
        ...snapshot,
        agents: normalizePlanningAgents(snapshot.agents),
        eventLog: normalized.eventLog,
      }
      this.isStreaming = false
      this.hasStarted = true
      this.eventSequence = normalized.nextSequence
    },
    resetPlanningState() {
      this.state = createIdleState()
      this.isStreaming = false
      this.hasStarted = false
      this.eventSequence = 0
    },
    clearAll() {
      this.request = null
      this.resetPlanningState()
      clearDraftRequest()
    },
    applyProgress(event: PlanningProgress) {
      const nextState = { ...this.state }
      this.eventSequence = appendEventLog(nextState, event, this.eventSequence)

      switch (event.type) {
        case 'progress':
          if (event.message) {
            nextState.messages = [...nextState.messages, event.message]
          }
          break
        case 'agent_start':
        case 'agent_progress':
        case 'agent_result':
        case 'agent_done':
        case 'agent_error': {
          if (!event.agentId) {
            break
          }

          const currentAgent = nextState.agents[event.agentId]
          if (!currentAgent) {
            nextState.step = 'error'
            nextState.error = `收到未知规划阶段: ${event.agentId}`
            break
          }

          const agentLabel = event.label || currentAgent.label
          const nextLogs = [...currentAgent.logs]

          if (event.message && getLastLog(nextLogs) !== event.message) {
            nextLogs.push(event.message)
          }

          if (event.type === 'agent_result' && event.counts) {
            const countSummary = resolveCountSummary(event.counts)
            const countMessage = countSummary ? `阶段结果已返回：${countSummary}` : ''
            if (countMessage && getLastLog(nextLogs) !== countMessage) {
              nextLogs.push(countMessage)
            }
          }

          let nextStatus = currentAgent.status
          if (event.type === 'agent_start' || event.type === 'agent_progress') {
            nextStatus = 'running'
          } else if (event.type === 'agent_done') {
            nextStatus = 'completed'
          } else if (event.type === 'agent_error') {
            nextStatus = 'error'
          }

          nextState.agents = {
            ...nextState.agents,
            [event.agentId]: {
              ...currentAgent,
              label: agentLabel,
              status: event.status || nextStatus,
              progress:
                event.type === 'agent_done'
                  ? 100
                  : Math.max(currentAgent.progress, event.progress ?? 0),
              logs: nextLogs,
              counts: {
                ...currentAgent.counts,
                ...(event.counts || {}),
              },
              lastMessage: event.message || currentAgent.lastMessage,
              startedAt:
                event.type === 'agent_start'
                  ? event.timestamp || currentAgent.startedAt
                  : currentAgent.startedAt,
              finishedAt:
                event.type === 'agent_done' || event.type === 'agent_error'
                  ? event.timestamp || currentAgent.finishedAt
                  : currentAgent.finishedAt,
            },
          }

          if (event.message) {
            nextState.messages = [...nextState.messages, `${agentLabel}：${event.message}`]
          }

          break
        }
        case 'attractions':
          nextState.attractions = Array.isArray(event.data) ? event.data : []
          assignAgentCounts(nextState, 'nearby_poi_agent', {
            attractions: nextState.attractions.length,
          })
          break
        case 'hotels':
          nextState.hotels = Array.isArray(event.data) ? event.data : []
          assignAgentCounts(nextState, 'nearby_poi_agent', {
            hotels: nextState.hotels.length,
          })
          break
        case 'restaurants':
          nextState.restaurants = Array.isArray(event.data) ? event.data : []
          assignAgentCounts(nextState, 'nearby_poi_agent', {
            restaurants: nextState.restaurants.length,
          })
          break
        case 'weather':
          nextState.weather = Array.isArray(event.data) ? event.data : []
          assignAgentCounts(nextState, 'weather_agent', {
            days: nextState.weather.length,
          })
          break
        case 'routes':
          nextState.routes = (event.data as PlanningState['routes']) || undefined
          assignAgentCounts(nextState, 'itinerary_composer_agent', resolveTransportCounts(nextState.routes))
          break
        case 'itinerary':
          nextState.itinerary = (event.data as TripPlan) || undefined
          nextState.agents = {
            ...nextState.agents,
            final_planning: {
              ...nextState.agents.final_planning,
              status: 'completed',
              progress: 100,
            },
          }
          assignAgentCounts(nextState, 'final_planning', {
            days: nextState.itinerary?.days.length || 0,
            attractions: nextState.itinerary?.statistics?.attraction_count || 0,
          })
          nextState.step = 'completed'
          nextState.progress = 100
          break
        case 'error':
          nextState.step = 'error'
          nextState.error = event.message || '规划失败，请稍后重试'
          break
        case 'done':
          if (nextState.step === 'error') {
            break
          }
          if (nextState.itinerary) {
            nextState.step = 'completed'
            nextState.progress = 100
          }
          break
      }

      if (event.type !== 'itinerary' && event.type !== 'done') {
        nextState.progress = resolveOverallProgress(nextState)
      }

      this.state = nextState
    },
    async streamPlan() {
      if (!this.request || this.isStreaming) {
        return
      }

      this.isStreaming = true
      this.hasStarted = true
      if (this.state.step === 'idle') {
        this.state = {
          ...createIdleState(),
          step: 'planning',
          messages: ['开始规划本次旅程...'],
        }
        this.eventSequence = 0
      }

      try {
        await streamTravelPlan(this.request, (event) => {
          this.applyProgress(event)
        })

        if (!this.state.itinerary) {
          this.state = {
            ...this.state,
            step: 'error',
            error: this.state.error || '本次规划未生成可用结果',
          }
        }
      } catch (error) {
        this.state = {
          ...this.state,
          step: 'error',
          error: error instanceof Error ? error.message : '规划失败',
        }
      } finally {
        this.isStreaming = false
      }
    },
  },
})
