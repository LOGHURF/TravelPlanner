import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PlanningFlow from '@/components/progress/PlanningFlow.vue'
import { createPlanningAgents } from '@/constants/planningAgents'
import type { PlanningState } from '@/types/travel'

function createBaseState(): PlanningState {
  return {
    step: 'planning',
    progress: 82,
    messages: [],
    eventLog: [],
    agents: createPlanningAgents(),
    attractions: [],
    hotels: [],
    restaurants: [],
    weather: [],
  }
}

describe('PlanningFlow', () => {
  it('does not infer a parallel weather node as completed from later progress', () => {
    const state = createBaseState()
    state.agents.final_planning = {
      ...state.agents.final_planning,
      status: 'completed',
      progress: 100,
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '生成最终行程',
      },
    })

    expect(wrapper.text()).toMatch(/天气检查\s*等待中/)
  })

  it('does not infer anchor resolver completion from nearby POI data', () => {
    const state = createBaseState()
    state.attractions = [{ name: '西湖', address: '杭州', category: '风景名胜' }]
    state.hotels = [{ name: '杭州酒店', address: '杭州', hotel_level: '舒适型' }]
    state.agents.nearby_poi_agent = {
      ...state.agents.nearby_poi_agent,
      status: 'running',
      progress: 45,
    }
    state.agents.weather_agent = {
      ...state.agents.weather_agent,
      status: 'completed',
      progress: 100,
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '周边补全',
        activeAgentId: 'nearby_poi_agent',
      },
    })

    expect(wrapper.text()).toMatch(/锚点验真\s*等待中/)
  })

  it('renders a stage board without graph connectors or duplicate stage strip', () => {
    const state = createBaseState()
    state.agents.orchestrator = {
      ...state.agents.orchestrator,
      status: 'completed',
      progress: 100,
    }
    state.agents.nearby_poi_agent = {
      ...state.agents.nearby_poi_agent,
      status: 'running',
      progress: 45,
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '周边补全',
        activeAgentId: 'nearby_poi_agent',
      },
    })

    expect(wrapper.find('[data-testid="orchestrator-loop"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="workflow-lines"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="stage-connector"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="repair-loop"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="repair-notice"]').exists()).toBe(true)
    expect(wrapper.find('.stage-strip').exists()).toBe(false)
    expect(wrapper.find('[data-workflow-node="orchestrator"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-worker-node]')).toHaveLength(6)
    expect(wrapper.find('[data-workflow-node="repair_router"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('审核不通过会回到主控生成下一批修复任务')
    expect(wrapper.text()).toContain('输入')
    expect(wrapper.text()).toContain('输出')
  })

  it('renders evaluator status and current repair round', () => {
    const state = createBaseState()
    state.messages = ['第1轮定向修复: route_matrix_agent']
    state.agents.plan_evaluator_agent = {
      ...state.agents.plan_evaluator_agent,
      status: 'completed',
      progress: 100,
      counts: { score: 72, issues: 2, repairs: 1 },
    }
    state.agents.orchestrator = {
      ...state.agents.orchestrator,
      status: 'running',
      progress: 72,
      logs: ['第1轮定向修复: route_matrix_agent'],
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '定向修复',
        activeAgentId: 'orchestrator',
      },
    })

    expect(wrapper.get('[data-workflow-node="plan_evaluator_agent"]').text()).toContain('方案审核')
    expect(wrapper.text()).toContain('第 1 轮修复')
    expect(wrapper.text()).toContain('主控调度')
  })

  it('surfaces max repair exhaustion as an explicit planning risk', () => {
    const state = createBaseState()
    state.messages = ['已达到最大修复轮(3)，方案仍存在审核风险，将带风险说明成稿']

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '生成最终行程',
      },
    })

    expect(wrapper.get('[data-testid="planning-risk"]').text()).toContain('方案仍存在审核风险')
    expect(wrapper.get('[data-testid="planning-risk"]').text()).toContain('最大修复轮')
  })
})
