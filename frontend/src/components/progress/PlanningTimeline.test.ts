import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PlanningTimeline from '@/components/progress/PlanningTimeline.vue'
import { createPlanningAgents } from '@/constants/planningAgents'
import type { PlanningState } from '@/types/travel'

function createState(): PlanningState {
  const agents = createPlanningAgents()
  agents.attraction_agent = {
    ...agents.attraction_agent,
    status: 'running',
    progress: 64,
    lastMessage: '正在筛选景点候选',
    logs: ['景点 Agent已开始处理', '正在筛选景点候选'],
    counts: { items: 3 },
  }
  agents.weather_agent = {
    ...agents.weather_agent,
    status: 'completed',
    progress: 100,
    lastMessage: '已完成当前阶段处理',
    logs: ['天气 Agent已开始处理', '阶段结果已返回：2 天', '已完成当前阶段处理'],
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
        message: '正在筛选景点候选',
        agentId: 'attraction_agent',
        label: '景点 Agent',
        phase: 'parallel',
        status: 'running',
        timestamp: '2026-03-03T10:00:01Z',
      },
      {
        id: 'event-2',
        eventType: 'weather',
        message: '天气结果已更新（2天）',
        label: '天气 Agent',
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
  state.agents.attraction_agent = {
    ...state.agents.attraction_agent,
    status: 'completed',
    progress: 100,
  }
  state.eventLog = [
    {
      id: 'event-3',
      eventType: 'agent_progress',
      message: '正在生成最终行程',
      agentId: 'final_planning',
      label: '成稿 Agent',
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
        currentStageLabel: '并行召回景点、酒店与天气',
      },
    })

    expect(wrapper.text()).toContain('景点')
    expect(wrapper.text()).toContain('正在筛选景点候选')
    expect(wrapper.text()).toContain('64%')
  })

  it('displays completed agent', async () => {
    const wrapper = mount(PlanningTimeline, {
      props: {
        state: createState(),
        currentStageLabel: '并行召回景点、酒店与天气',
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
