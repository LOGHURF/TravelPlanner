import { describe, expect, it } from 'vitest'
import type { DailyPlan } from '@/types/travel'
import {
  buildActiveRoute,
  buildDayStops,
  buildRouteStops,
} from '@/composables/useAmapRoute'

const sampleDay: DailyPlan = {
  date: '2026-03-22',
  day_index: 1,
  attractions: [
    {
      name: '断桥',
      address: '西湖景区',
      location: { lat: 30.257, lng: 120.141 },
    },
    {
      name: '灵隐寺',
      address: '灵隐路',
      location: { lat: 30.242, lng: 120.101 },
    },
  ],
  meals: [
    {
      name: '湖滨午餐',
      type: 'lunch',
      meal_type: 'lunch',
      address: '湖滨路',
      location: { lat: 30.258, lng: 120.142 },
    },
    {
      name: '寺前晚餐',
      type: 'dinner',
      meal_type: 'dinner',
      address: '灵隐路',
      location: { lat: 30.241, lng: 120.103 },
    },
  ],
  hotel: {
    name: '西湖酒店',
    address: '湖滨商圈',
    location: { lat: 30.259, lng: 120.145 },
  },
}

describe('useAmapRoute', () => {
  it('separates attraction routing stops from hotel and meal markers', () => {
    const markerStops = buildDayStops(sampleDay)
    const routeStops = buildRouteStops(sampleDay)
    const activeRoute = buildActiveRoute(sampleDay)

    expect(markerStops.map((stop) => stop.kind)).toEqual([
      'hotel',
      'attraction',
      'meal',
      'attraction',
      'meal',
      'hotel',
    ])
    expect(routeStops.map((stop) => stop.name)).toEqual(['断桥', '灵隐寺'])
    expect(activeRoute?.stops.length).toBe(6)
    expect(activeRoute?.routeStops.length).toBe(2)
    expect(activeRoute?.path).toEqual([
      [120.141, 30.257],
      [120.101, 30.242],
    ])
  })
})
