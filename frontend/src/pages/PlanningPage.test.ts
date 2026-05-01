import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlanningPage from '@/pages/PlanningPage.vue'
import { usePlannerStore } from '@/stores/planner'
import type { TripPlan, TripRequest } from '@/types/travel'

const push = vi.fn()
const replace = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push, replace }),
}))

const request: TripRequest = {
  destination: '北京',
  start_date: '2026-03-10',
  end_date: '2026-03-12',
  duration: 3,
  origin: '上海',
}

const itinerary: TripPlan = {
  city: '北京',
  start_date: '2026-03-10',
  end_date: '2026-03-12',
  total_days: 3,
  days: [],
  weather_info: [],
}

describe('PlanningPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
    replace.mockClear()
  })

  it('routes to the result page when the final itinerary is generated', async () => {
    const store = usePlannerStore()
    store.setRequest(request)
    store.hasStarted = true

    const wrapper = mount(PlanningPage, {
      global: {
        stubs: {
          AppNavBar: true,
          PlanningFlow: true,
          Button: true,
          Toast: true,
        },
      },
    })

    await nextTick()
    store.applyProgress({ type: 'itinerary', data: itinerary })
    await nextTick()
    await nextTick()

    expect(push).toHaveBeenCalledWith({
      name: 'plan-result',
      params: { planId: expect.any(String) },
    })

    wrapper.unmount()
  })

  it('keeps a manual result entry visible when an itinerary exists before the completed flag settles', async () => {
    const store = usePlannerStore()
    store.setRequest(request)
    store.hasStarted = true

    const wrapper = mount(PlanningPage, {
      global: {
        stubs: {
          AppNavBar: {
            template: '<header><slot name="actions" /></header>',
          },
          PlanningFlow: true,
          Button: {
            emits: ['click'],
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          Toast: true,
        },
      },
    })

    await nextTick()
    store.state = {
      ...store.state,
      step: 'planning',
      itinerary,
    }
    await nextTick()
    await nextTick()

    const button = wrapper.get('button')
    expect(button.text()).toContain('查看行程')

    await button.trigger('click')
    expect(push).toHaveBeenLastCalledWith({
      name: 'plan-result',
      params: { planId: expect.any(String) },
    })

    wrapper.unmount()
  })
})
