<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  CloudSun,
  Download,
  Hotel,
  MapPin,
  RefreshCw,
  Share2,
  UtensilsCrossed,
  X,
} from 'lucide-vue-next'
import TripLayout from '@/components/layout/TripLayout.vue'
import MapRouteBoard from '@/components/result/MapRouteBoard.vue'
import TimelineItem from '@/components/result/TimelineItem.vue'
import { Button, Toast } from '@/components/ui'
import { downloadPlanAsHtml } from '@/services/storage/planStorage'
import { usePlanResultStore } from '@/stores/planResult'
import type { TimelineItem as DayTimelineItem, Attraction, Restaurant } from '@/types/travel'
import type { DayMapStop } from '@/composables/useAmapRoute'
import { formatShortDate } from '@/utils/date'
import { getHotelImage } from '@/utils/media'

const route = useRoute()
const router = useRouter()
const planResultStore = usePlanResultStore()

const showShareToast = ref(false)
const activeDayIndex = ref(0)
const selectedStop = ref<Attraction | null>(null)

const planId = computed(() => String(route.params.planId || ''))
const record = computed(() => planResultStore.loadResult(planId.value))
const plan = computed(() => record.value?.plan)
const request = computed(() => record.value?.request)

function resolveDestinationColor(seed: string) {
  const palette = ['#0EA5E9', '#06B6D4', '#14B8A6', '#10B981']
  const index = [...seed].reduce((sum, char) => sum + char.charCodeAt(0), 0) % palette.length
  return palette[index]
}

function createFallbackImage(title: string, accent: string) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${accent}" stop-opacity="0.95" />
          <stop offset="100%" stop-color="#dff7f4" stop-opacity="1" />
        </linearGradient>
      </defs>
      <rect width="800" height="600" rx="32" fill="url(#g)" />
      <circle cx="632" cy="118" r="72" fill="rgba(255,255,255,0.42)" />
      <path d="M0 418C132 336 222 330 320 372C430 420 532 414 800 284V600H0V418Z" fill="rgba(255,255,255,0.28)" />
      <text x="56" y="468" fill="#0f172a" font-size="42" font-family="Inter, sans-serif" font-weight="600">${title}</text>
      <text x="56" y="520" fill="rgba(15,23,42,0.7)" font-size="22" font-family="Inter, sans-serif">TravelPlanner Curated Stop</text>
    </svg>
  `
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

function formatMealAnchor(meal: Restaurant) {
  const distance = Number(meal.distance_to_anchor_km || 0)
  if (!meal.meal_anchor_name || distance <= 0) {
    return ''
  }
  return `距 ${meal.meal_anchor_name} ${distance.toFixed(1)} km`
}

const destinationColor = computed(() =>
  resolveDestinationColor(plan.value?.city || request.value?.destination || 'travel'),
)

const activeDay = computed(() => {
  if (!plan.value?.days.length) {
    return null
  }
  return plan.value.days[activeDayIndex.value] || plan.value.days[0]
})

const currentTimeline = computed<DayTimelineItem[]>(() => {
  if (activeDay.value?.timeline?.length) {
    return activeDay.value.timeline
  }

  if (!activeDay.value) {
    return []
  }

  const fallback: DayTimelineItem[] = []
  if (activeDay.value.hotel?.name) {
    fallback.push({
      time: '09:00',
      activity: activeDay.value.hotel.name,
      type: 'hotel',
    })
  }

  activeDay.value.attractions.forEach((attraction, index) => {
    fallback.push({
      time: `${10 + index * 2}:30`,
      activity: attraction.name,
      type: 'attraction',
    })
  })

  activeDay.value.meals.slice(0, 2).forEach((meal, index) => {
    fallback.push({
      time: index === 0 ? '12:30' : '18:30',
      activity: meal.name,
      type: 'meal',
    })
  })

  return fallback
})

const dayCards = computed(() =>
  (plan.value?.days || []).map((day, index) => ({
    index,
    label: `Day ${day.day_index}`,
    summary: day.description || `${formatShortDate(day.date)} 行程`,
    meta: [day.weather?.day_weather, `${day.attractions.length} 个景点`].filter(Boolean).join(' · '),
  })),
)

const summaryText = computed(() => {
  if (activeDay.value?.description) {
    return activeDay.value.description
  }
  return plan.value?.overall_suggestions || plan.value?.narrative_plan || `${plan.value?.city || 'Trip'} 行程`
})

const quickFacts = computed(() =>
  [
    plan.value?.total_days || plan.value?.days.length ? `${plan.value?.total_days || plan.value?.days.length} 天` : '',
    request.value?.companions || '',
    request.value?.pace ? `${request.value.pace} 节奏` : '',
    request.value?.hotel_level || '',
  ].filter(Boolean),
)

function handleSelectStop(stop: DayMapStop) {
  // 根据 stop.kind 查找对应的景点/酒店/餐厅
  if (stop.kind === 'attraction') {
    const attraction = activeDay.value?.attractions.find(a => a.name === stop.name)
    if (attraction) {
      selectedStop.value = attraction
    }
  }
}

function locateToAttraction(attraction: Attraction) {
  // 触发地图定位到景点
  if (attraction.location) {
    window.dispatchEvent(new CustomEvent('locate-to-coordinates', {
      detail: { lat: attraction.location.lat, lng: attraction.location.lng, name: attraction.name }
    }))
  }
}

const visibleAttractions = computed(() => activeDay.value?.attractions || [])

watch(
  () => [planId.value, plan.value?.days.length || 0],
  () => {
    const length = plan.value?.days.length || 0
    if (!length) {
      activeDayIndex.value = 0
      return
    }
    const stored = planResultStore.getActiveDay(planId.value)
    activeDayIndex.value = Math.min(Math.max(stored, 0), length - 1)
  },
  { immediate: true },
)

watch(activeDayIndex, (value) => {
  if (planId.value) {
    planResultStore.setActiveDay(planId.value, value)
  }
})

function downloadPlan() {
  if (!plan.value) {
    return
  }
  const filename = `${plan.value.city || 'trip-plan'}-${plan.value.total_days || plan.value.days.length}天-行程网页.html`
  downloadPlanAsHtml(plan.value, filename)
}

async function sharePlan() {
  try {
    await navigator.clipboard.writeText(window.location.href)
    showShareToast.value = true
  } catch (error) {
    console.error('复制链接失败', error)
  }
}

function reviewPlanning() {
  router.push({ name: 'planning', query: { review: planId.value } })
}
</script>

<template>
  <main v-if="plan && activeDay" class="min-h-screen">
    <TripLayout
      :theme-color="destinationColor"
      :initial-panel-width="380"
      :min-panel-width="340"
      :max-panel-width="440"
      :sheet-title="plan.city"
      :sheet-preview="`Day ${activeDay.day_index} · ${activeDay.weather?.day_weather || '行程详情'}`"
    >
      <template #map>
        <MapRouteBoard
          immersive
          class="h-full"
          :day="activeDay"
          @select-stop="handleSelectStop"
        />
      </template>

      <template #panel>
        <div class="space-y-5">
          <header class="sticky top-0 z-10 -mx-4 -mt-4 border-b border-slate-200 bg-white px-4 pb-4 pt-4">
            <div class="flex items-center justify-between gap-3">
              <button
                type="button"
                class="inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:border-sky-300 hover:text-slate-950"
                @click="router.push({ name: 'home' })"
              >
                <ArrowLeft class="h-4 w-4" />
                返回首页
              </button>

              <div class="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  title="回看规划"
                  aria-label="回看规划"
                  class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:border-sky-300 hover:text-sky-700"
                  @click="reviewPlanning"
                >
                  <RefreshCw class="h-4 w-4" />
                </button>
                <button
                  type="button"
                  title="分享"
                  aria-label="分享"
                  class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:border-sky-300 hover:text-sky-700"
                  @click="sharePlan"
                >
                  <Share2 class="h-4 w-4" />
                </button>
                <button
                  type="button"
                  title="导出 HTML"
                  aria-label="导出 HTML"
                  class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-sky-600 text-white shadow-sm transition-colors hover:bg-sky-700"
                  @click="downloadPlan"
                >
                  <Download class="h-4 w-4" />
                </button>
              </div>
            </div>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <span
                v-for="fact in quickFacts"
                :key="fact"
                class="inline-flex h-7 items-center whitespace-nowrap rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-xs font-medium text-slate-600"
              >
                {{ fact }}
              </span>
            </div>
          </header>

          <section class="space-y-2">
            <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
              Travel Overview
            </p>
            <h1 class="text-2xl font-semibold tracking-tight text-slate-950">
              {{ plan.city }}
            </h1>
            <p class="text-sm leading-relaxed text-slate-600">
              {{ summaryText }}
            </p>
          </section>

          <section
            data-testid="active-day-summary"
            class="rounded-lg border border-sky-200 bg-sky-50 px-3.5 py-3.5"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-700">
                  Active Day
                </p>
                <h2 class="mt-1 text-xl font-semibold text-slate-950">
                  Day {{ activeDay.day_index }}
                </h2>
                <p class="mt-1 line-clamp-2 text-sm leading-relaxed text-slate-600">
                  {{ activeDay.description || formatShortDate(activeDay.date) }}
                </p>
              </div>
              <div class="grid shrink-0 gap-1 text-right text-xs text-slate-600">
                <span class="rounded-lg bg-white px-2 py-1 font-medium text-sky-700">
                  {{ activeDay.weather?.day_weather || '天气' }}
                </span>
                <span>{{ activeDay.attractions.length }} 景点</span>
                <span>{{ activeDay.meals.length }} 餐饮</span>
              </div>
            </div>
          </section>

          <section class="space-y-3 border-t border-slate-200 pt-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                  Days
                </p>
                <h2 class="mt-1 text-lg font-semibold text-slate-950">
                  切换日程
                </h2>
              </div>
              <span class="text-xs tabular-nums text-slate-500">
                {{ plan.total_days || plan.days.length }} days
              </span>
            </div>

            <div data-testid="day-switcher" class="grid gap-2">
              <button
                v-for="item in dayCards"
                :key="item.label"
                type="button"
                class="rounded-lg border px-3 py-3 text-left transition-colors"
                :class="item.index === activeDayIndex
                  ? 'border-sky-500 bg-sky-50'
                  : 'border-slate-200 bg-white hover:border-sky-300'"
                @click="activeDayIndex = item.index"
              >
                <div class="flex items-center justify-between gap-3">
                  <strong class="text-sm font-semibold text-slate-950">
                    {{ item.label }}
                  </strong>
                  <span class="truncate text-xs text-sky-700">
                    {{ item.meta }}
                  </span>
                </div>
                <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">
                  {{ item.summary }}
                </p>
              </button>
            </div>
          </section>

          <section class="space-y-3 border-t border-slate-200 pt-4">
            <div>
              <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                Stops
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-950">
                今日景点
              </h2>
            </div>

            <div class="grid gap-2">
              <button
                v-for="attraction in visibleAttractions"
                :key="attraction.name"
                type="button"
                class="rounded-lg border border-slate-200 bg-white px-3 py-3 text-left shadow-sm transition-colors hover:border-sky-300 hover:bg-sky-50"
                @click="locateToAttraction(attraction)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <h3 class="truncate text-base font-semibold text-slate-950">
                      {{ attraction.name }}
                    </h3>
                    <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">
                      {{ attraction.description || attraction.address || '已纳入今日路线。' }}
                    </p>
                  </div>
                  <span
                    v-if="attraction.rating"
                    class="shrink-0 rounded-lg bg-amber-50 px-2 py-1 text-xs font-semibold tabular-nums text-amber-700"
                  >
                    {{ attraction.rating.toFixed(1) }}
                  </span>
                </div>
                <p
                  v-if="attraction.address"
                  class="mt-2 flex min-w-0 items-center gap-1 text-xs text-slate-500"
                >
                  <MapPin class="h-3.5 w-3.5 shrink-0 text-sky-600" />
                  <span class="truncate">{{ attraction.address }}</span>
                </p>
              </button>
            </div>
          </section>

          <section class="space-y-3 border-t border-slate-200 pt-4">
            <div>
              <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                Weather
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-950">
                天气与节奏
              </h2>
            </div>

            <div class="grid gap-2">
              <article
                v-for="weather in plan.weather_info"
                :key="weather.date"
                class="rounded-lg border border-slate-200 bg-white px-3 py-3"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-2">
                    <CloudSun class="h-4 w-4 text-sky-600" />
                    <strong class="text-sm font-semibold text-slate-950">
                      {{ formatShortDate(weather.date) }}
                    </strong>
                  </div>
                  <span class="text-sm tabular-nums text-slate-500">
                    {{ weather.night_temp }}°-{{ weather.day_temp }}°
                  </span>
                </div>
                <p class="mt-1 text-xs leading-relaxed text-slate-600">
                  {{ weather.day_weather }} · {{ weather.wind_direction || '微风' }}
                </p>
              </article>
            </div>
          </section>

          <section class="space-y-3 border-t border-slate-200 pt-4">
            <div>
              <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                Stay & Dining
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-950">
                住宿与用餐
              </h2>
            </div>

            <article
              v-if="activeDay.hotel"
              class="overflow-hidden rounded-lg border border-slate-200 bg-white"
            >
              <div class="grid gap-3 p-3 sm:grid-cols-[72px_1fr]">
                <div class="overflow-hidden rounded-lg bg-slate-200">
                  <img
                    :src="getHotelImage(activeDay.hotel) || createFallbackImage(activeDay.hotel.name, destinationColor)"
                    :alt="activeDay.hotel.name"
                    class="aspect-square h-full w-full object-cover"
                  >
                </div>
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Hotel class="h-4 w-4 text-emerald-500" />
                    <span class="rounded-lg bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                      {{ activeDay.hotel.hotel_level || '精选住宿' }}
                    </span>
                  </div>
                  <h3 class="text-base font-semibold leading-tight text-slate-950">
                    {{ activeDay.hotel.name }}
                  </h3>
                  <p class="line-clamp-2 text-xs leading-relaxed text-slate-600">
                    {{ activeDay.hotel.address || activeDay.accommodation || '已纳入今日路线' }}
                  </p>
                </div>
              </div>
            </article>

            <div class="grid gap-2">
              <article
                v-for="meal in activeDay.meals"
                :key="meal.name"
                class="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3"
              >
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <UtensilsCrossed class="h-4 w-4 text-emerald-500" />
                    <strong class="truncate text-sm font-semibold text-slate-950">
                      {{ meal.name }}
                    </strong>
                  </div>
                  <p class="mt-1 text-xs leading-relaxed text-slate-600">
                    {{ meal.cuisine_type || meal.meal_type || meal.type }}
                  </p>
                  <p
                    v-if="formatMealAnchor(meal)"
                    class="mt-1 text-xs leading-relaxed text-slate-500"
                  >
                    {{ formatMealAnchor(meal) }}
                  </p>
                </div>
                <span class="rounded-lg bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                  {{ meal.estimated_cost ? `¥${meal.estimated_cost}` : '推荐' }}
                </span>
              </article>
            </div>
          </section>

          <section class="space-y-3 border-t border-slate-200 pt-4">
            <div>
              <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                Timeline
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-950">
                今日时间线
              </h2>
            </div>

            <TransitionGroup name="list" tag="div" class="grid gap-0">
              <div
                v-for="(item, index) in currentTimeline"
                :key="`${item.time}-${item.activity}`"
                v-memo="[item.time, item.activity]"
              >
                <TimelineItem
                  :time="item.time"
                  :title="item.activity"
                  :caption="item.type"
                  :terminal="index === currentTimeline.length - 1"
                />
              </div>
            </TransitionGroup>
          </section>

          <section v-if="plan.important_notes?.length" class="space-y-3 border-t border-slate-200 pt-4">
            <div>
              <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                Notes
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-950">
                出行提醒
              </h2>
            </div>

            <div class="grid gap-2">
              <article
                v-for="note in plan.important_notes"
                :key="note"
                class="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm leading-relaxed text-slate-600"
              >
                {{ note }}
              </article>
            </div>
          </section>
        </div>
      </template>

      <template #over-map>
        <div class="pointer-events-none flex h-full flex-col items-end justify-end p-4 md:p-5">
          <Transition name="slide-up">
            <div
              v-if="selectedStop"
              class="pointer-events-auto hidden w-full max-w-[320px] overflow-hidden rounded-lg border border-slate-200 bg-white p-4 shadow-[0_14px_34px_rgba(15,23,42,0.16)] md:block"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                  <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
                    选中地点
                  </p>
                  <h3 class="mt-1 truncate text-lg font-semibold text-slate-950">
                    {{ selectedStop.name }}
                  </h3>
                  <p v-if="selectedStop.description" class="mt-1 line-clamp-2 text-sm text-slate-600">
                    {{ selectedStop.description }}
                  </p>
                  <p v-if="selectedStop.address" class="mt-2 flex items-center gap-1 text-xs text-slate-500">
                    <MapPin class="h-3.5 w-3.5 shrink-0 text-sky-600" />
                    <span class="truncate">{{ selectedStop.address }}</span>
                  </p>
                </div>
                <button
                  type="button"
                  class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                  aria-label="关闭选中地点"
                  @click="selectedStop = null"
                >
                  <X class="h-4 w-4" />
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </template>

      <template #modals>
        <Toast
          v-model:visible="showShareToast"
          type="success"
          message="链接已复制到剪贴板"
          position="top-right"
        />
      </template>
    </TripLayout>
  </main>

  <main
    v-else
    class="grid min-h-screen place-items-center p-6"
  >
    <div class="max-w-lg rounded-lg border border-slate-200 bg-white px-8 py-10 shadow-sm">
      <p class="text-xs font-medium uppercase tracking-wider text-sky-600">
        Missing Plan
      </p>
      <h2 class="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
        未找到对应行程
      </h2>
      <p class="mt-4 text-base leading-relaxed text-slate-600">
        该规划可能已经失效，返回首页重新生成即可。
      </p>
      <div class="mt-8">
        <Button @click="router.push({ name: 'home' })">
          返回首页
        </Button>
      </div>
    </div>
  </main>
</template>
