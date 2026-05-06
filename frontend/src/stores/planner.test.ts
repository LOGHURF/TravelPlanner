import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { usePlannerStore } from '@/stores/planner'
import type { TripPlan, TripRequest } from '@/types/travel'

const request: TripRequest = {
  destination: '北京',
  start_date: '2026-03-10',
  end_date: '2026-03-12',
  origin: '上海',
  companions: '朋友',
  pace: '适中',
  hotel_level: '舒适型',
  duration: 3,
}

describe('planner store agent progress', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('tracks agent lifecycle independently', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'agent_start',
      agentId: 'nearby_poi_agent',
      label: '周边补全',
      status: 'running',
      progress: 12,
      message: '周边补全已开始处理',
      timestamp: '2026-03-03T10:00:00Z',
    })
    store.applyProgress({
      type: 'agent_progress',
      agentId: 'nearby_poi_agent',
      label: '周边补全',
      status: 'running',
      progress: 72,
      message: '正在筛选景点候选',
      timestamp: '2026-03-03T10:00:01Z',
    })
    store.applyProgress({
      type: 'agent_result',
      agentId: 'nearby_poi_agent',
      label: '周边补全',
      status: 'running',
      progress: 86,
      counts: { items: 4 },
    })
    store.applyProgress({
      type: 'agent_done',
      agentId: 'nearby_poi_agent',
      label: '周边补全',
      status: 'completed',
      progress: 100,
      message: '已完成当前阶段处理',
      counts: { items: 4 },
      timestamp: '2026-03-03T10:00:02Z',
    })

    const agent = store.state.agents.nearby_poi_agent
    expect(agent.status).toBe('completed')
    expect(agent.progress).toBe(100)
    expect(agent.logs).toContain('正在筛选景点候选')
    expect(agent.counts).toEqual({ items: 4 })
    expect(agent.startedAt).toBe('2026-03-03T10:00:00Z')
    expect(agent.finishedAt).toBe('2026-03-03T10:00:02Z')
    expect(store.state.progress).toBeGreaterThan(0)
  })

  it('derives active agent, stage label, recent events, and result highlights', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'agent_start',
      agentId: 'strategy_agent',
      label: '策略规划',
      phase: 'prepare',
      status: 'running',
      progress: 20,
      message: '开始生成片区策略',
      timestamp: '2026-03-03T10:00:00Z',
    })
    store.applyProgress({
      type: 'agent_start',
      agentId: 'anchor_resolver_agent',
      label: '锚点验真',
      phase: 'refine',
      status: 'running',
      progress: 20,
      message: '开始验证锚点',
      timestamp: '2026-03-03T10:00:01Z',
    })
    store.applyProgress({
      type: 'agent_start',
      agentId: 'weather_agent',
      label: '天气检查',
      phase: 'parallel',
      status: 'running',
      progress: 20,
      message: '开始召回天气切片',
      timestamp: '2026-03-03T10:00:02Z',
    })
    store.applyProgress({
      type: 'attractions',
      data: [{ name: '故宫' }, { name: '景山公园' }],
      timestamp: '2026-03-03T10:00:03Z',
    })
    store.applyProgress({
      type: 'hotels',
      data: [{ name: '王府井酒店' }],
      timestamp: '2026-03-03T10:00:04Z',
    })

    expect(store.activeAgentId).toBe('weather_agent')
    expect(store.currentStageLabel).toBe('天气检查')
    expect(store.recentEvents[0]?.message).toBe('酒店结果已更新（1项）')
    expect(store.recentEvents[1]?.message).toBe('景点结果已更新（2项）')

    const attractionHighlight = store.resultHighlights.find((item) => item.id === 'attractions')
    const hotelHighlight = store.resultHighlights.find((item) => item.id === 'hotels')

    expect(attractionHighlight).toMatchObject({
      status: 'partial',
      count: 2,
      preview: ['故宫', '景山公园'],
    })
    expect(hotelHighlight).toMatchObject({
      status: 'partial',
      count: 1,
      preview: ['王府井酒店'],
    })
  })

  it('deduplicates matching system progress when an agent event with the same message follows', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'progress',
      message: '天气完成:3天',
      timestamp: '2026-03-03T10:00:00Z',
    })
    store.applyProgress({
      type: 'agent_progress',
      agentId: 'weather_agent',
      label: '天气检查',
      phase: 'enrich',
      status: 'running',
      message: '天气完成:3天',
      progress: 72,
      timestamp: '2026-03-03T10:00:01Z',
    })

    expect(store.state.eventLog).toHaveLength(1)
    expect(store.state.eventLog[0]).toMatchObject({
      eventType: 'agent_progress',
      agentId: 'weather_agent',
      message: '天气完成:3天',
    })
  })

  it('marks planning completed when itinerary arrives', () => {
    const store = usePlannerStore()
    store.setRequest(request)
    store.applyProgress({
      type: 'agent_start',
      agentId: 'final_planning',
      status: 'running',
      progress: 12,
    })

    const itinerary: TripPlan = {
      city: '北京',
      start_date: '2026-03-10',
      end_date: '2026-03-12',
      total_days: 3,
      days: [],
      weather_info: [],
      statistics: {
        attraction_count: 0,
      },
    }

    store.applyProgress({
      type: 'itinerary',
      data: itinerary,
    })

    expect(store.state.step).toBe('completed')
    expect(store.state.progress).toBe(100)
    expect(store.state.agents.final_planning.status).toBe('completed')
    expect(store.state.agents.final_planning.progress).toBe(100)
    expect(store.state.agents.final_planning.counts).toEqual({ days: 0, attractions: 0 })
  })

  it('tracks evaluator and orchestrator-driven repair dispatch', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'agent_start',
      agentId: 'plan_evaluator_agent',
      label: '方案审核',
      phase: 'evaluate',
      status: 'running',
      progress: 12,
      message: '开始审核完整方案',
    })
    store.applyProgress({
      type: 'agent_result',
      agentId: 'plan_evaluator_agent',
      label: '方案审核',
      phase: 'evaluate',
      status: 'running',
      progress: 86,
      counts: { score: 72, issues: 2, repairs: 1 },
    })
    store.applyProgress({
      type: 'agent_progress',
      agentId: 'orchestrator',
      label: '主控调度',
      phase: 'prepare',
      status: 'running',
      progress: 72,
      message: '第1轮定向修复: route_matrix_agent',
    })

    expect(store.state.agents.plan_evaluator_agent.counts).toEqual({
      score: 72,
      issues: 2,
      repairs: 1,
    })
    expect(store.currentStageLabel).toBe('定向修复')
    expect(store.activeAgentId).toBe('orchestrator')
  })

  it('does not let a done event hide an earlier stream error', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'agent_start',
      agentId: 'strategy_agent',
      status: 'running',
      progress: 30,
    })
    store.applyProgress({
      type: 'error',
      message: 'LLM 输出不是 JSON',
    })
    store.applyProgress({
      type: 'done',
    })

    expect(store.state.step).toBe('error')
    expect(store.state.progress).toBeLessThan(100)
    expect(store.state.error).toBe('LLM 输出不是 JSON')
  })

  it('restores a saved planning snapshot for replay mode', () => {
    const store = usePlannerStore()
    const itinerary: TripPlan = {
      city: '北京',
      start_date: '2026-03-10',
      end_date: '2026-03-12',
      total_days: 3,
      days: [],
      weather_info: [],
    }

    store.restoreSnapshot(request, {
      step: 'completed',
      progress: 100,
      messages: ['规划已完成'],
      eventLog: [],
      agents: {
        ...store.state.agents,
        final_planning: {
          ...store.state.agents.final_planning,
          status: 'completed',
          progress: 100,
          logs: ['已输出最终行程'],
        },
      },
      attractions: [],
      hotels: [],
      restaurants: [],
      weather: [],
      itinerary,
    })

    expect(store.request?.destination).toBe('北京')
    expect(store.state.itinerary?.city).toBe('北京')
    expect(store.state.step).toBe('completed')
    expect(store.hasStarted).toBe(true)
    expect(store.isStreaming).toBe(false)
  })

  it('migrates legacy snapshots without crashing active stage getters', () => {
    const store = usePlannerStore()

    store.restoreSnapshot(request, {
      step: 'planning',
      progress: 32,
      messages: ['旧流程快照'],
      eventLog: [
        {
          id: 'legacy-1',
          eventType: 'agent_done',
          agentId: 'removed_stage' as never,
          message: '旧阶段完成',
        },
      ],
      agents: {
        removed_stage: {
          id: 'removed_stage',
          label: '旧阶段',
          phase: 'route',
          description: '旧流程',
          status: 'completed',
          progress: 100,
          logs: ['旧日志'],
          counts: {},
        },
      } as never,
      attractions: [],
      hotels: [],
      restaurants: [],
      weather: [],
    })

    expect(store.state.eventLog).toHaveLength(0)
    expect(store.state.agents.strategy_agent).toBeDefined()
    expect(store.activeAgentId).toBe('orchestrator')
    expect(store.currentStageLabel).toBe('主控调度')
  })

  it('surfaces unknown live agent events as explicit contract errors', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    store.applyProgress({
      type: 'agent_start',
      agentId: 'removed_stage' as never,
      status: 'running',
      progress: 12,
    })

    expect(store.state.step).toBe('error')
    expect(store.state.error).toBe('收到未知规划阶段: removed_stage')
  })

  it('keeps event log ids unique after the capped log starts trimming older entries', () => {
    const store = usePlannerStore()
    store.setRequest(request)

    for (let index = 0; index < 32; index += 1) {
      store.applyProgress({
        type: 'progress',
        message: `流式更新 ${index + 1}`,
      })
    }

    const ids = store.state.eventLog.map((record) => record.id)
    expect(store.state.eventLog).toHaveLength(24)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('rebuilds duplicate event ids when restoring a saved snapshot', () => {
    const store = usePlannerStore()

    store.restoreSnapshot(request, {
      step: 'planning',
      progress: 56,
      messages: ['恢复回放态'],
      eventLog: [
        {
          id: 'event-24',
          eventType: 'progress',
          message: '第一条',
        },
        {
          id: 'event-24',
          eventType: 'progress',
          message: '第二条',
        },
      ],
      agents: store.state.agents,
      attractions: [],
      hotels: [],
      restaurants: [],
      weather: [],
    })

    const ids = store.state.eventLog.map((record) => record.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(store.hasStarted).toBe(true)
  })
})
