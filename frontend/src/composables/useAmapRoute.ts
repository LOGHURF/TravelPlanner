import { reactive } from 'vue'
import type { DailyPlan, Location, Restaurant, RouteSegment, Attraction, Hotel } from '@/types/travel'
import {
  formatDistanceKm,
  formatDuration,
  haversineKm,
  isLocationAvailable,
} from '@/utils/location'

export interface DayTheme {
  stroke: string
  surface: string
  tint: string
}

export interface DayMapStop {
  id: string
  name: string
  kind: 'hotel' | 'attraction' | 'meal'
  label: string
  badge: string
  location: Location
  sequence: number
  image?: string
  raw?: Attraction | Hotel | Restaurant // 保留原始数据用于调试
}

export interface ActiveRoute {
  segment: RouteSegment | null
  segments: RouteSegment[]
  stops: DayMapStop[]
  routeStops: DayMapStop[]
  path: [number, number][]
  distanceLabel: string
  durationLabel: string
  totalDistance: number | null
  totalDuration: number
}

export interface ResolvedRouteMetrics {
  distanceLabel: string
  durationLabel: string
}

const DAY_THEMES: DayTheme[] = [
  { stroke: '#0ea5e9', surface: 'rgba(14, 165, 233, 0.16)', tint: '#0369a1' },
  { stroke: '#14b8a6', surface: 'rgba(20, 184, 166, 0.16)', tint: '#0f766e' },
  { stroke: '#10b981', surface: 'rgba(16, 185, 129, 0.16)', tint: '#047857' },
  { stroke: '#38bdf8', surface: 'rgba(56, 189, 248, 0.16)', tint: '#0284c7' },
]
const liveRouteMetrics = reactive<Record<string, ResolvedRouteMetrics>>({})

type RouteWithLocations = RouteSegment & {
  from_location: Location
  to_location: Location
}

const mealLabels: Record<string, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '加餐',
}

export function getDayTheme(dayIndex = 1): DayTheme {
  return DAY_THEMES[(dayIndex - 1) % DAY_THEMES.length]
}

export function hasRouteLocations(segment?: RouteSegment | null): segment is RouteWithLocations {
  return isLocationAvailable(segment?.from_location) && isLocationAvailable(segment?.to_location)
}

function normalizeMealType(meal?: Restaurant): string {
  return String(meal?.meal_type || meal?.type || '').trim().toLowerCase()
}

function dedupeStops(stops: Omit<DayMapStop, 'sequence'>[]): DayMapStop[] {
  const deduped = stops.filter((stop, index) => {
    const previous = index > 0 ? stops[index - 1] : null
    return !previous ||
      previous.name !== stop.name ||
      previous.location.lat !== stop.location.lat ||
      previous.location.lng !== stop.location.lng
  })

  return deduped.map((stop, index) => ({
    ...stop,
    sequence: index + 1,
  }))
}

function pushStop(
  target: Omit<DayMapStop, 'sequence'>[],
  payload: {
    name: string
    location?: Location | null
    kind: DayMapStop['kind']
    label: string
    badge: string
    image?: string
  },
) {
  const {
    name,
    location,
    kind,
    label,
    badge,
    image,
  } = payload

  if (!name || !isLocationAvailable(location)) {
    return
  }

  target.push({
    id: `${kind}-${target.length}-${name}`,
    name,
    kind,
    label,
    badge,
    location,
    image,
  })
}

function groupMeals(meals: Restaurant[]) {
  const grouped: Record<string, Restaurant[]> = {
    breakfast: [],
    lunch: [],
    snack: [],
    dinner: [],
  }

  for (const meal of meals) {
    const key = normalizeMealType(meal)
    if (key in grouped) {
      grouped[key].push(meal)
    }
  }

  return grouped
}

function fallbackDistanceFromStops(stops: DayMapStop[]): number | null {
  if (stops.length < 2) {
    return null
  }

  let total = 0
  let hasValue = false
  for (let index = 0; index < stops.length - 1; index += 1) {
    const distance = haversineKm(stops[index].location, stops[index + 1].location)
    if (!distance) {
      continue
    }
    total += distance
    hasValue = true
  }

  return hasValue ? Number(total.toFixed(2)) : null
}

function fallbackDurationFromDistance(distance?: number | null): number {
  if (!distance || distance <= 0) {
    return 0
  }
  return Math.max(8, Math.round((distance / 24) * 60))
}

function buildFallbackSegment(day: DailyPlan): RouteSegment | null {
  const path = buildRouteStops(day)
  if (path.length < 2) {
    return null
  }

  const first = path[0]
  const second = path[1]
  const distance = haversineKm(first.location, second.location)
  if (!distance) {
    return null
  }

  return {
    from_name: first.name,
    to_name: second.name,
    from_location: first.location,
    to_location: second.location,
    mode: 'driving',
    distance,
    duration: fallbackDurationFromDistance(distance),
  }
}

export function buildDayStops(day?: DailyPlan): DayMapStop[] {
  if (!day) {
    return []
  }

  const meals = groupMeals(day.meals || [])
  const stops: Omit<DayMapStop, 'sequence'>[] = []

  pushStop(stops, {
    name: day.hotel?.name || '',
    location: day.hotel?.location,
    kind: 'hotel',
    label: '酒店',
    badge: '住',
    image: day.hotel?.image_url,
  })

  const breakfast = meals.breakfast[0]
  pushStop(stops, {
    name: breakfast?.name || '',
    location: breakfast?.location,
    kind: 'meal',
    label: mealLabels.breakfast,
    badge: '早',
    image: breakfast?.photo,
  })

  for (const [index, attraction] of (day.attractions || []).entries()) {
    pushStop(stops, {
      name: attraction.name,
      location: attraction.location,
      kind: 'attraction',
      label: `第 ${index + 1} 景点`,
      badge: String(index + 1),
      image: attraction.image_url || attraction.photo,
    })

    if (index === 0) {
      const lunch = meals.lunch[0]
      pushStop(stops, {
        name: lunch?.name || '',
        location: lunch?.location,
        kind: 'meal',
        label: mealLabels.lunch,
        badge: '午',
        image: lunch?.photo,
      })
    }

    if (index === Math.max(0, (day.attractions || []).length - 1)) {
      const snack = meals.snack[0]
      pushStop(stops, {
        name: snack?.name || '',
        location: snack?.location,
        kind: 'meal',
        label: mealLabels.snack,
        badge: '茶',
        image: snack?.photo,
      })
    }
  }

  if (!(day.attractions || []).length) {
    const lunch = meals.lunch[0]
    pushStop(stops, {
      name: lunch?.name || '',
      location: lunch?.location,
      kind: 'meal',
      label: mealLabels.lunch,
      badge: '午',
      image: lunch?.photo,
    })
  }

  const dinner = meals.dinner[0]
  pushStop(stops, {
    name: dinner?.name || '',
    location: dinner?.location,
    kind: 'meal',
    label: mealLabels.dinner,
    badge: '晚',
    image: dinner?.photo,
  })

  if (stops.length > 1) {
    pushStop(stops, {
      name: day.hotel?.name || '',
      location: day.hotel?.location,
      kind: 'hotel',
      label: '回酒店',
      badge: '住',
      image: day.hotel?.image_url,
    })
  }

  return dedupeStops(stops)
}

export function buildRouteStops(day?: DailyPlan): DayMapStop[] {
  if (!day) {
    return []
  }

  const stops: Omit<DayMapStop, 'sequence'>[] = []
  for (const [index, attraction] of (day.attractions || []).entries()) {
    pushStop(stops, {
      name: attraction.name,
      location: attraction.location,
      kind: 'attraction',
      label: `第 ${index + 1} 景点`,
      badge: String(index + 1),
      image: attraction.image_url || attraction.photo,
    })
  }

  return dedupeStops(stops)
}

function buildPathFromSegments(segments: RouteSegment[]): [number, number][] {
  const path: [number, number][] = []

  for (const segment of segments) {
    if (!hasRouteLocations(segment)) {
      continue
    }

    const start: [number, number] = [segment.from_location.lng, segment.from_location.lat]
    const end: [number, number] = [segment.to_location.lng, segment.to_location.lat]
    const last = path[path.length - 1]

    if (!last || last[0] !== start[0] || last[1] !== start[1]) {
      path.push(start)
    }

    path.push(end)
  }

  return path
}

function buildPathFromStops(stops: DayMapStop[]): [number, number][] {
  return stops.map((stop) => [stop.location.lng, stop.location.lat] as [number, number])
}

function stopSignature(stops: DayMapStop[]) {
  return stops
    .map((stop) => `${stop.kind}:${stop.name}:${stop.location.lat.toFixed(6)},${stop.location.lng.toFixed(6)}`)
    .join('|')
}

export function getDayRouteMetricsKey(day?: DailyPlan) {
  if (!day) {
    return ''
  }

  const stops = buildRouteStops(day)
  return `${day.date || ''}::${day.day_index || 0}::${stopSignature(stops)}`
}

export function readResolvedRouteMetrics(day?: DailyPlan): ResolvedRouteMetrics | null {
  const key = getDayRouteMetricsKey(day)
  return key ? liveRouteMetrics[key] || null : null
}

export function storeResolvedRouteMetrics(day: DailyPlan | undefined, metrics: ResolvedRouteMetrics) {
  const key = getDayRouteMetricsKey(day)
  if (!key) {
    return
  }

  liveRouteMetrics[key] = metrics
}

export function clearResolvedRouteMetrics(day?: DailyPlan) {
  const key = getDayRouteMetricsKey(day)
  if (!key || !liveRouteMetrics[key]) {
    return
  }

  delete liveRouteMetrics[key]
}

export function buildActiveRoute(day?: DailyPlan): ActiveRoute | null {
  if (!day) {
    return null
  }

  const segments = (day.route_segments || []).filter(hasRouteLocations)
  const stops = buildDayStops(day)
  const routeStops = buildRouteStops(day)
  const path = segments.length ? buildPathFromSegments(segments) : buildPathFromStops(routeStops)
  const totalDistanceFromSegments = segments.reduce((sum, segment) => sum + Number(segment.distance || 0), 0)
  const totalDuration = segments.reduce((sum, segment) => sum + Number(segment.duration || 0), 0)
  const totalDistance =
    totalDistanceFromSegments > 0 ? Number(totalDistanceFromSegments.toFixed(2)) : fallbackDistanceFromStops(routeStops)
  const resolvedDuration = totalDuration > 0 ? totalDuration : fallbackDurationFromDistance(totalDistance)
  const segment = segments[0] || buildFallbackSegment(day)

  return {
    segment,
    segments,
    stops,
    routeStops,
    path,
    totalDistance,
    totalDuration: resolvedDuration,
    distanceLabel: formatDistanceKm(totalDistance),
    durationLabel: formatDuration(resolvedDuration),
  }
}
