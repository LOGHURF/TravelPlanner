<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { load as loadAmap } from '@amap/amap-jsapi-loader'
import { MapPinned, Route, Timer } from 'lucide-vue-next'
import type { DailyPlan } from '@/types/travel'
import {
  buildActiveRoute,
  clearResolvedRouteMetrics,
  storeResolvedRouteMetrics,
  type DayMapStop,
  getDayTheme,
} from '@/composables/useAmapRoute'
import { formatDistanceKm, formatDuration } from '@/utils/location'

const emit = defineEmits<{
  (e: 'marker-click', stop: DayMapStop): void
  (e: 'select-stop', stop: DayMapStop): void
}>()

const props = withDefaults(
  defineProps<{
    day: DailyPlan
    summary?: string
    immersive?: boolean
  }>(),
  {
    summary: '',
    immersive: false,
  },
)

const containerRef = ref<HTMLDivElement | null>(null)
const renderState = ref<'loading' | 'ready' | 'fallback'>('loading')
const mapInstance = ref<any>(null)
const overlays = ref<any[]>([])
const resolvedMetrics = ref<{ distanceLabel: string; durationLabel: string }>({
  distanceLabel: '',
  durationLabel: '',
})
let renderRequestId = 0

const amapKey = import.meta.env.VITE_AMAP_KEY?.trim()
const securityJsCode = import.meta.env.VITE_AMAP_SECURITY_JS_CODE?.trim()
const theme = computed(() => getDayTheme(props.day.day_index || 1))
const activeRoute = computed(() => buildActiveRoute(props.day))
const displayDistanceLabel = computed(
  () => resolvedMetrics.value.distanceLabel || activeRoute.value?.distanceLabel || '距离待补充',
)
const displayDurationLabel = computed(
  () => resolvedMetrics.value.durationLabel || activeRoute.value?.durationLabel || '',
)

function syncResolvedMetrics(metrics?: { distanceLabel: string; durationLabel: string }) {
  const nextMetrics = metrics || {
    distanceLabel: activeRoute.value?.distanceLabel || '距离待补充',
    durationLabel: activeRoute.value?.durationLabel || '',
  }

  resolvedMetrics.value = nextMetrics
  storeResolvedRouteMetrics(props.day, nextMetrics)
}

function resolveFitViewPadding() {
  const width = containerRef.value?.clientWidth || 0
  const immersive = props.immersive

  if (!immersive) {
    return [72, 88, 72, 120] as [number, number, number, number]
  }

  if (width >= 1440) {
    return [112, 96, 96, 410] as [number, number, number, number]
  }

  if (width >= 1200) {
    return [104, 88, 88, 380] as [number, number, number, number]
  }

  if (width >= 960) {
    return [96, 80, 80, 340] as [number, number, number, number]
  }

  return [60, 72, 180, 72] as [number, number, number, number]
}

function createMarkerContent(stop: NonNullable<typeof activeRoute.value>['stops'][number], isSelected = false) {
  const wrapper = document.createElement('div')
  wrapper.className = `route-marker ${stop.kind} ${isSelected ? 'selected' : ''}`
  wrapper.style.cssText = `
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    cursor: pointer;
  `

  // 根据类型设置颜色
  let bgColor = '#0ea5e9'
  if (stop.kind === 'hotel') bgColor = '#0f766e'
  if (stop.kind === 'meal') bgColor = '#10b981'

  // 圆形标记
  const badge = document.createElement('div')
  badge.className = 'marker-badge'
  badge.textContent = stop.badge
  badge.style.cssText = `
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: ${bgColor};
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    border: 2px solid white;
  `

  // 名称标签
  const name = document.createElement('div')
  name.className = 'marker-name'
  name.textContent = stop.name.slice(0, 8)
  name.style.cssText = `
    background: rgba(255,255,255,0.95);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    color: #1f2937;
    white-space: nowrap;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
  `

  wrapper.appendChild(badge)
  wrapper.appendChild(name)

  // 添加点击事件
  wrapper.addEventListener('click', (e) => {
    e.stopPropagation()
    emit('select-stop', stop)
  })

  return wrapper
}

function toLngLatTuple(value: unknown): [number, number] | null {
  if (Array.isArray(value) && value.length >= 2) {
    const [lng, lat] = value
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      return [Number(lng), Number(lat)]
    }
  }

  if (typeof value === 'object' && value !== null) {
    const candidate = value as {
      lng?: unknown
      lat?: unknown
      getLng?: () => number
      getLat?: () => number
    }

    if (Number.isFinite(candidate.lng) && Number.isFinite(candidate.lat)) {
      return [Number(candidate.lng), Number(candidate.lat)]
    }

    if (typeof candidate.getLng === 'function' && typeof candidate.getLat === 'function') {
      const lng = candidate.getLng()
      const lat = candidate.getLat()
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        return [lng, lat]
      }
    }
  }

  return null
}

function dedupePath(path: [number, number][]): [number, number][] {
  return path.filter((point, index) => {
    const previous = index > 0 ? path[index - 1] : null
    return !previous || previous[0] !== point[0] || previous[1] !== point[1]
  })
}

function extractStepPath(steps: unknown): [number, number][] {
  if (!Array.isArray(steps)) {
    return []
  }

  const points: [number, number][] = []
  for (const step of steps) {
    const rawPath = (step as { path?: unknown })?.path
    if (!Array.isArray(rawPath)) {
      continue
    }
    for (const point of rawPath) {
      const tuple = toLngLatTuple(point)
      if (tuple) {
        points.push(tuple)
      }
    }
  }

  return dedupePath(points)
}

function resolveRouteSearchMode(stops: DayMapStop[]) {
  const segmentModes = (activeRoute.value?.segments || [])
    .map((segment) => String(segment.mode || '').trim().toLowerCase())
    .filter(Boolean)
  const transportCopy = `${props.day.transport_mode || ''} ${props.day.transportation || ''}`

  if (segmentModes.length > 0 && segmentModes.every((mode) => mode === 'walking')) {
    return 'walking'
  }

  if (transportCopy.includes('步行')) {
    return 'walking'
  }

  if (stops.length <= 2 && transportCopy.includes('公交')) {
    return 'walking'
  }

  return 'driving'
}

async function searchDrivingRoute(
  AMap: any,
  stops: DayMapStop[],
): Promise<{ path: [number, number][]; distanceLabel: string; durationLabel: string } | null> {
  if (stops.length < 2) {
    return null
  }

  const start = new AMap.LngLat(stops[0].location.lng, stops[0].location.lat)
  const end = new AMap.LngLat(stops[stops.length - 1].location.lng, stops[stops.length - 1].location.lat)
  const waypoints = stops
    .slice(1, -1)
    .map((stop) => new AMap.LngLat(stop.location.lng, stop.location.lat))

  return await new Promise((resolve) => {
    const driving = new AMap.Driving({
      policy: AMap.DrivingPolicy?.LEAST_TIME,
      extensions: 'all',
      ferry: 1,
      hideMarkers: true,
      showTraffic: false,
      autoFitView: false,
    })

    driving.search(start, end, { waypoints }, (status: string, result: any) => {
      driving.clear?.()
      driving.destroy?.()

      if (status !== 'complete' || !result?.routes?.length) {
        resolve(null)
        return
      }

      const route = result.routes[0]
      const path = extractStepPath(route.steps)
      if (path.length < 2) {
        resolve(null)
        return
      }

      const distanceKm = Number(route.distance || 0) / 1000
      const durationMinutes = Math.max(1, Math.round(Number(route.time || 0) / 60))

      resolve({
        path,
        distanceLabel: formatDistanceKm(distanceKm),
        durationLabel: formatDuration(durationMinutes),
      })
    })
  })
}

async function searchWalkingRoute(
  AMap: any,
  stops: DayMapStop[],
): Promise<{ path: [number, number][]; distanceLabel: string; durationLabel: string } | null> {
  if (stops.length < 2) {
    return null
  }

  const walking = new AMap.Walking({
    hideMarkers: true,
    autoFitView: false,
  })

  let totalDistance = 0
  let totalDuration = 0
  const mergedPath: [number, number][] = []

  try {
    for (let index = 0; index < stops.length - 1; index += 1) {
      const start = new AMap.LngLat(stops[index].location.lng, stops[index].location.lat)
      const end = new AMap.LngLat(stops[index + 1].location.lng, stops[index + 1].location.lat)

      const result = await new Promise<any | null>((resolve) => {
        walking.search(start, end, (status: string, payload: any) => {
          if (status !== 'complete' || !payload?.routes?.length) {
            resolve(null)
            return
          }
          resolve(payload.routes[0])
        })
      })

      if (!result) {
        return null
      }

      totalDistance += Number(result.distance || 0)
      totalDuration += Number(result.time || 0)
      mergedPath.push(...extractStepPath(result.steps))
    }
  } finally {
    walking.clear?.()
    walking.destroy?.()
  }

  const path = dedupePath(mergedPath)
  if (path.length < 2) {
    return null
  }

  return {
    path,
    distanceLabel: formatDistanceKm(totalDistance / 1000),
    durationLabel: formatDuration(Math.max(1, Math.round(totalDuration / 60))),
  }
}

async function resolveRenderedRoute(
  AMap: any,
  stops: DayMapStop[],
): Promise<{ path: [number, number][]; distanceLabel: string; durationLabel: string }> {
  const fallback = {
    path: activeRoute.value?.path || [],
    distanceLabel: activeRoute.value?.distanceLabel || '距离待补充',
    durationLabel: activeRoute.value?.durationLabel || '',
  }

  if (stops.length < 2) {
    return fallback
  }

  const searchMode = resolveRouteSearchMode(stops)
  const liveRoute =
    searchMode === 'walking'
      ? await searchWalkingRoute(AMap, stops)
      : await searchDrivingRoute(AMap, stops)

  return liveRoute || fallback
}

async function renderMap() {
  console.log('[MapRouteBoard] 开始渲染地图', {
    hasContainer: !!containerRef.value,
    stopsLength: activeRoute.value?.stops?.length,
    routeStopsLength: activeRoute.value?.routeStops?.length,
    stops: activeRoute.value?.stops?.map(s => ({ name: s.name, kind: s.kind, location: s.location })),
    hasAMapKey: !!amapKey,
  })

  if (!containerRef.value || !activeRoute.value?.stops.length) {
    console.warn('[MapRouteBoard] 无法渲染: 缺少容器或 stops 数据')
    syncResolvedMetrics()
    renderState.value = 'fallback'
    return
  }

  if (!amapKey) {
    console.warn('[MapRouteBoard] 无法渲染: 缺少 AMap Key')
    syncResolvedMetrics()
    renderState.value = 'fallback'
    return
  }

  renderState.value = 'loading'
  clearResolvedRouteMetrics(props.day)
  resolvedMetrics.value = { distanceLabel: '', durationLabel: '' }
  const requestId = ++renderRequestId

  try {
    if (securityJsCode) {
      ;(window as any)._AMapSecurityConfig = {
        ...((window as any)._AMapSecurityConfig || {}),
        securityJsCode,
      }
    }

    const AMap = await loadAmap({
      key: amapKey,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar', 'AMap.Driving', 'AMap.Walking'],
    })

    if (!containerRef.value || !activeRoute.value?.stops.length || requestId !== renderRequestId) {
      return
    }

    const routeToRender = await resolveRenderedRoute(AMap, activeRoute.value.routeStops)
    if (requestId !== renderRequestId) {
      return
    }

    syncResolvedMetrics({
      distanceLabel: routeToRender.distanceLabel,
      durationLabel: routeToRender.durationLabel,
    })

    const center = routeToRender.path[0] || [
      activeRoute.value.stops[0].location.lng,
      activeRoute.value.stops[0].location.lat,
    ]

    if (!mapInstance.value) {
      mapInstance.value = new AMap.Map(containerRef.value, {
        viewMode: '2D',
        zoom: 12,
        center,
        resizeEnable: true,
        dragEnable: true,
        zoomEnable: true,
        keyboardEnable: true,
        doubleClickZoom: true,
        mapStyle: 'amap://styles/normal',
      })

      mapInstance.value.addControl(new AMap.Scale())
      mapInstance.value.addControl(new AMap.ToolBar({ position: 'RT' }))
    } else {
      mapInstance.value.setCenter(center)
      mapInstance.value.setZoom(12)
    }

    if (overlays.value.length) {
      mapInstance.value.remove(overlays.value)
      overlays.value = []
    }

    const nextOverlays: any[] = []

    if (routeToRender.path.length >= 2) {
      nextOverlays.push(
        new AMap.Polyline({
          path: routeToRender.path,
          strokeColor: '#ffffff',
          strokeWeight: 12,
          strokeOpacity: 0.84,
          lineJoin: 'round',
          lineCap: 'round',
          zIndex: 15,
        }),
      )
      nextOverlays.push(
        new AMap.Polyline({
          path: routeToRender.path,
          strokeColor: theme.value.stroke,
          strokeWeight: 6,
          strokeOpacity: 0.92,
          lineJoin: 'round',
          lineCap: 'round',
          showDir: true,
          zIndex: 16,
        }),
      )
    }

    console.log('[MapRouteBoard] 开始创建标记', { stopsCount: activeRoute.value.stops.length })

    for (const stop of activeRoute.value.stops) {
      console.log('[MapRouteBoard] 创建标记', { name: stop.name, kind: stop.kind, location: stop.location })
      nextOverlays.push(
        new AMap.Marker({
          position: [stop.location.lng, stop.location.lat],
          title: `${stop.label} ${stop.name}`,
          content: createMarkerContent(stop),
          anchor: 'bottom-center',
          offset: new AMap.Pixel(0, -16),
          zIndex: stop.kind === 'hotel' ? 24 : 20 + stop.sequence,
        }),
      )
    }

    console.log('[MapRouteBoard] 标记创建完成', { overlaysCount: nextOverlays.length })

    overlays.value = nextOverlays
    mapInstance.value.add(nextOverlays)
    mapInstance.value.setFitView(nextOverlays, false, resolveFitViewPadding())
    renderState.value = 'ready'
  } catch (error) {
    console.error('地图加载失败', error)
    syncResolvedMetrics()
    renderState.value = 'fallback'
  }
}

async function scheduleRenderMap() {
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve())
  })
  await renderMap()
}

watch(
  () => props.day,
  () => {
    void scheduleRenderMap()
  },
  { flush: 'post' },
)

onMounted(() => {
  void scheduleRenderMap()

  // 监听定位事件
  window.addEventListener('locate-to-coordinates', ((event: CustomEvent) => {
    const { lat, lng } = event.detail
    if (mapInstance.value && lat && lng) {
      mapInstance.value.setZoom(16)
      mapInstance.value.setCenter([lng, lat])
    }
  }) as EventListener)
})

onBeforeUnmount(() => {
  if (mapInstance.value) {
    mapInstance.value.destroy()
    mapInstance.value = null
  }
})
</script>

<template>
  <section
    class="relative h-full min-h-[60vh] w-full"
    :style="{ '--map-stroke': theme.stroke, '--map-surface': theme.surface, '--map-tint': theme.tint }"
  >
    <div
      class="absolute inset-0 overflow-hidden"
      :class="props.immersive ? '' : 'rounded-lg border border-slate-200 bg-white shadow-sm'"
    >
      <div ref="containerRef" class="h-full w-full" :class="{ invisible: renderState !== 'ready' }" />

      <div
        v-if="renderState === 'loading'"
        class="absolute inset-0 flex items-center justify-center bg-slate-50 text-sm font-medium text-slate-600"
      >
        正在铺开今日路线...
      </div>

      <div
        v-if="renderState === 'fallback'"
        class="absolute inset-0 flex items-center justify-center bg-slate-50 text-slate-600"
      >
        <div class="flex flex-col items-center gap-3">
          <MapPinned class="h-8 w-8 text-sky-500" />
          <p class="text-sm font-medium">地图暂不可用</p>
        </div>
      </div>
    </div>

    <div class="pointer-events-none absolute left-6 top-6 flex flex-wrap gap-2">
      <div class="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
        <div class="flex items-center gap-2 text-sm font-medium text-slate-800">
          <Route class="h-4 w-4 text-sky-600" />
          <span>Day {{ props.day.day_index }} 路线</span>
        </div>
      </div>

      <div class="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
        <div class="flex items-center gap-2 text-sm tabular-nums text-slate-700">
          <MapPinned class="h-4 w-4 text-emerald-500" />
          <span>{{ displayDistanceLabel }}</span>
        </div>
      </div>

      <div
        v-if="displayDurationLabel"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm"
      >
        <div class="flex items-center gap-2 text-sm tabular-nums text-slate-700">
          <Timer class="h-4 w-4 text-sky-600" />
          <span>{{ displayDurationLabel }}</span>
        </div>
      </div>
    </div>

    <p
      v-if="props.summary"
      class="pointer-events-none absolute bottom-6 left-6 max-w-[340px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 shadow-sm"
    >
      {{ props.summary }}
    </p>
  </section>
</template>

<style scoped>
.route-marker {
  position: relative;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.route-marker:hover {
  transform: scale(1.1);
}

.route-marker-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.marker-badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--marker-accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  border: 2px solid white;
}

.marker-name {
  background: rgba(255,255,255,0.95);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: #1f2937;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
