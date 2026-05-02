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

function horizontalSpread(path?: string) {
  const numbers = path?.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || []
  const xValues = numbers.filter((_, index) => index % 2 === 0)
  if (!xValues.length) {
    return Number.POSITIVE_INFINITY
  }
  return Math.max(...xValues) - Math.min(...xValues)
}

describe('PlanningFlow', () => {
  it('does not infer a parallel weather node as completed from later chain progress', () => {
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

    expect(wrapper.text()).toMatch(/天气召回\s*等待中/)
  })

  it('does not infer reviewer completion from upstream attraction or hotel data', () => {
    const state = createBaseState()
    state.attractions = [
      {
        name: '西湖',
        address: '杭州',
        category: '风景名胜',
      },
    ]
    state.hotels = [
      {
        name: '杭州酒店',
        address: '杭州',
        hotel_level: '舒适型',
      },
    ]
    state.agents.attraction_agent = {
      ...state.agents.attraction_agent,
      status: 'running',
      progress: 45,
    }
    state.agents.hotel_agent = {
      ...state.agents.hotel_agent,
      status: 'completed',
      progress: 100,
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '并行召回景点、酒店与天气',
        activeAgentId: 'attraction_agent',
      },
    })

    expect(wrapper.text()).toMatch(/评审压缩\s*等待中/)
  })

  it('renders a directional workflow graph with visible branch edges', () => {
    const state = createBaseState()
    state.agents.orchestrator = {
      ...state.agents.orchestrator,
      status: 'completed',
      progress: 100,
    }
    state.agents.attraction_agent = {
      ...state.agents.attraction_agent,
      status: 'running',
      progress: 45,
    }

    const wrapper = mount(PlanningFlow, {
      props: {
        state,
        currentStageLabel: '并行召回景点、酒店与天气',
        activeAgentId: 'attraction_agent',
      },
    })

    expect(wrapper.find('[data-testid="workflow-graph-canvas"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-workflow-node]')).toHaveLength(10)
    expect(wrapper.findAll('[data-workflow-edge]')).toHaveLength(11)
    expect(wrapper.findAll('[data-workflow-edge-underlay]')).toHaveLength(11)
    expect(wrapper.get('[data-workflow-edge="orchestrator-to-attraction_agent"]').classes()).toContain('is-active')
    const activeMarker = wrapper.get('[data-testid="workflow-arrow-active"]')
    expect(activeMarker.attributes('markerWidth')).toBe('24')
    expect(activeMarker.attributes('markerHeight')).toBe('24')
    expect(activeMarker.get('path').attributes('d')).toBe('M3 3L21 12L3 21Z')

    wrapper.findAll('[data-workflow-edge]').forEach((edge) => {
      expect(edge.attributes('d')).toContain('C')
    })
    ;[
      'start-to-orchestrator',
      'reviewer_agent-to-restaurant_agent',
      'restaurant_agent-to-transport_agent',
      'transport_agent-to-final_planning',
      'final_planning-to-finish',
    ].forEach((edgeId) => {
      expect(horizontalSpread(wrapper.get(`[data-workflow-edge="${edgeId}"]`).attributes('d'))).toBeLessThanOrEqual(16)
    })
    expect(wrapper.get('[data-workflow-node="attraction_agent"]').classes()).toContain('is-active')
  })
})
