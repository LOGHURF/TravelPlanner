import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PlanningTimeline from '@/components/progress/PlanningTimeline.vue'
import { createPlanningAgents } from '@/constants/planningAgents'
import type { PlanningState } from '@/types/travel'

function createState(): PlanningState {
  const agents = createPlanningAgents()
  agents.nearby_poi_agent = {
    ...agents.nearby_poi_agent,
    status: 'running',
    progress: 64,
    lastMessage: '正在召回周边 POI',
    logs: ['周边补全已开始处理', '正在召回周边 POI'],
    counts: { attractions: 3 },
  }
  agents.weather_agent = {
    ...agents.weather_agent,
    status: 'completed',
    progress: 100,
    lastMessage: '已完成当前阶段处理',
    logs: ['天气检查已开始处理', '阶段结果已返回：2 天', '已完成当前阶段处理'],
    counts: { days: 2 },
  }

  return {
    step: 'planning',
    progress: 42,
    messages: [],
    eventLog: [
      {
        id: 'event-1',
        eventType: 'agent_progress',
        message: '正在召回周边 POI',
        agentId: 'nearby_poi_agent',
        label: '周边补全',
        phase: 'enrich',
        status: 'running',
        timestamp: '2026-03-03T10:00:01Z',
      },
      {
        id: 'event-2',
        eventType: 'weather',
        message: '天气结果已更新（2天）',
        label: '天气检查',
        timestamp: '2026-03-03T10:00:02Z',
      },
    ],
    agents,
    attractions: [],
    hotels: [],
    restaurants: [],
    weather: [],
  }
}

function createCompletedState(): PlanningState {
  const state = createState()
  state.step = 'completed'
  state.progress = 100
  state.agents.nearby_poi_agent = {
    ...state.agents.nearby_poi_agent,
    status: 'completed',
    progress: 100,
  }
  state.eventLog = [
    {
      id: 'event-3',
      eventType: 'agent_progress',
      message: '正在生成最终行程',
      agentId: 'final_planning',
      label: '最终成稿',
      phase: 'finalize',
      status: 'running',
      timestamp: '2026-03-03T10:00:03Z',
    },
    {
      id: 'event-4',
      eventType: 'itinerary',
      message: '最终行程已生成（3天）',
      label: '系统事件',
      timestamp: '2026-03-03T10:00:04Z',
    },
  ]
  state.agents.final_planning = {
    ...state.agents.final_planning,
    status: 'completed',
    progress: 100,
    lastMessage: '已完成当前阶段处理',
  }

  return state
}

describe('PlanningTimeline', () => {
  it('displays running agent info', async () => {
    const wrapper = mount(PlanningTimeline, {
      props: {
        state: createState(),
        currentStageLabel: '周边补全',
      },
    })

    expect(wrapper.text()).toContain('周边补全')
    expect(wrapper.text()).toContain('正在召回周边 POI')
    expect(wrapper.text()).toContain('64%')
  })

  it('displays completed agent', async () => {
    const wrapper = mount(PlanningTimeline, {
      props: {
        state: createState(),
        currentStageLabel: '天气检查',
      },
    })

    // Weather agent should be shown as completed
    expect(wrapper.text()).toContain('天气')
    expect(wrapper.text()).toContain('已完成')
  })

  it('shows completed events after planning completes', () => {
    const state = createCompletedState()
    const wrapper = mount(PlanningTimeline, {
      props: {
        state,
        currentStageLabel: '最终行程已生成',
      },
    })

    expect(wrapper.text()).toContain('最终行程已生成')
    expect(wrapper.text()).toContain('100%')
  })
})
