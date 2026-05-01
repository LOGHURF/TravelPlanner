import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildPlanHtmlDocument,
  clearDraftRequest,
  downloadPlanAsHtml,
  getPlanRecord,
  readDraftRequest,
  saveDraftRequest,
  savePlanRecord,
} from '@/services/storage/planStorage'
import { createPlanningAgents } from '@/constants/planningAgents'
import type { PlanningState, TripPlan, TripRequest } from '@/types/travel'

const mockRequest: TripRequest = {
  destination: '北京',
  start_date: '2026-03-01',
  end_date: '2026-03-03',
  companions: '朋友',
}

const mockPlan: TripPlan = {
  city: '北京',
  start_date: '2026-03-01',
  end_date: '2026-03-03',
  days: [
    {
      date: '2026-03-01',
      day_index: 1,
      description: '故宫 / 景山',
      attractions: [
        { name: '故宫', address: '景山前街4号', category: '历史古迹', rating: 4.9 },
        { name: '景山公园', address: '景山西街44号', category: '风景名胜', rating: 4.7 },
      ],
      meals: [
        { name: '四季民福', type: 'lunch', meal_type: 'lunch', address: '前门大街', cuisine_type: '京菜' },
      ],
      hotel: {
        name: '王府井酒店',
        address: '王府井大街',
        description: '靠近核心景点',
      },
      route_segments: [
        { from_name: '故宫', to_name: '景山公园', distance: 1.2, duration: 12 },
      ],
      timeline: [
        { time: '09:00', activity: '故宫', type: 'attraction' },
        { time: '13:00', activity: '景山公园', type: 'attraction' },
      ],
      estimated_cost: {
        attractions: 120,
        meals: 180,
        transport: 40,
        hotel: 680,
      },
      weather: {
        date: '2026-03-01',
        day_weather: '晴',
        night_weather: '晴',
        day_temp: 8,
        night_temp: -1,
        wind_direction: '北',
        wind_power: '2级',
      },
    },
  ],
  weather_info: [],
  overall_suggestions: '建议错峰入园。',
  important_notes: ['提前预约热门景点'],
  packing_tips: ['身份证'],
  estimated_total_cost: 1020,
}

const mockPlanningState: PlanningState = {
  step: 'completed',
  progress: 100,
  messages: ['规划已完成'],
  eventLog: [],
  agents: createPlanningAgents(),
  attractions: [],
  hotels: [],
  restaurants: [],
  weather: [],
  itinerary: mockPlan,
}

const STORAGE_KEY = 'travelplanner.plan.records.v2'

describe('planStorage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('stores and retrieves plan record', () => {
    const planId = savePlanRecord(mockPlan, mockRequest, mockPlanningState)
    const record = getPlanRecord(planId)

    expect(record?.plan.city).toBe('北京')
    expect(record?.planningState?.step).toBe('completed')
  })

  it('does not persist a duplicate itinerary inside the planning snapshot', () => {
    const planId = savePlanRecord(mockPlan, mockRequest, mockPlanningState)

    const rawRecords = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
    expect(rawRecords[planId].planningState.itinerary).toBeUndefined()

    const record = getPlanRecord(planId)
    expect(record?.planningState?.itinerary?.city).toBe('北京')
  })

  it('prunes older records instead of failing when localStorage quota is exceeded', () => {
    const oversizedRecords = Object.fromEntries(
      Array.from({ length: 8 }, (_, index) => [
        `old-${index}`,
        {
          id: `old-${index}`,
          plan: {
            ...mockPlan,
            city: `旧行程${index}`,
            narrative_plan: 'x'.repeat(2400),
          },
          request: mockRequest,
          createdAt: new Date(2026, 0, index + 1).toISOString(),
        },
      ]),
    )
    let storageValue = JSON.stringify(oversizedRecords)
    const storageLimit = 12000

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key: string) => {
      return key === STORAGE_KEY ? storageValue : null
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
      if (key === STORAGE_KEY && value.length > storageLimit) {
        throw new DOMException('Quota exceeded', 'QuotaExceededError')
      }
      if (key === STORAGE_KEY) {
        storageValue = value
      }
    })

    const planId = savePlanRecord(mockPlan, mockRequest, mockPlanningState)
    const savedRecords = JSON.parse(storageValue)

    expect(savedRecords[planId]?.plan.city).toBe('北京')
    expect(Object.keys(savedRecords).length).toBeLessThan(9)
    expect(storageValue.length).toBeLessThanOrEqual(storageLimit)
  })

  it('stores and clears draft request', () => {
    saveDraftRequest(mockRequest)
    expect(readDraftRequest()?.destination).toBe('北京')
    clearDraftRequest()
    expect(readDraftRequest()).toBeNull()
  })

  it('builds standalone html document for exported plan', () => {
    const html = buildPlanHtmlDocument(mockPlan)

    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('北京 行程')
    expect(html).toContain('DAY 01')
    expect(html).toContain('故宫')
    expect(html).toContain('故宫 -&gt; 景山公园')
  })

  it('downloads plan as html file', async () => {
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    })

    downloadPlanAsHtml(mockPlan, 'beijing-trip.html')

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    const blob = createObjectURL.mock.calls[0]?.[0] as unknown as Blob
    expect(blob.type).toBe('text/html;charset=utf-8')
    await expect(blob.text()).resolves.toContain('故宫 / 景山')
    expect(click).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
