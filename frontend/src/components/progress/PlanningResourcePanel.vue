<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, CloudSun, Hotel, Route, Search, UtensilsCrossed } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { PlanningState } from '@/types/travel'

interface Props {
  state: PlanningState
  selectedNodeLabel: string
  selectedStatusLabel: string
  selectedSummary: string
  detailChips: string[]
}

interface ResourceItem {
  title: string
  meta: string
}

interface ResourceGroup {
  key: string
  label: string
  count: number
  items: ResourceItem[]
  icon: Component
  className: string
}

const props = defineProps<Props>()

const expandedResources = ref<Record<string, boolean>>({
  attractions: true,
  hotels: false,
  restaurants: false,
  weather: false,
  routes: false,
})

const resourceGroups = computed<ResourceGroup[]>(() => {
  return [
    {
      key: 'attractions',
      label: '景点',
      count: props.state.attractions.length,
      icon: Search,
      className: 'tone-sky',
      items: props.state.attractions.slice(0, 4).map((item) => ({
        title: item.name,
        meta: [item.category, item.rating ? `评分 ${item.rating.toFixed(1)}` : '', item.address]
          .filter(Boolean)
          .join(' · '),
      })),
    },
    {
      key: 'hotels',
      label: '酒店',
      count: props.state.hotels.length,
      icon: Hotel,
      className: 'tone-emerald',
      items: props.state.hotels.slice(0, 4).map((item) => ({
        title: item.name,
        meta: [item.hotel_level, item.rating ? `评分 ${item.rating.toFixed(1)}` : '', item.address]
          .filter(Boolean)
          .join(' · '),
      })),
    },
    {
      key: 'restaurants',
      label: '餐饮',
      count: props.state.restaurants.length,
      icon: UtensilsCrossed,
      className: 'tone-amber',
      items: props.state.restaurants.slice(0, 4).map((item) => ({
        title: item.name,
        meta: [item.cuisine_type || item.type, item.estimated_cost ? `¥${item.estimated_cost}` : '']
          .filter(Boolean)
          .join(' · '),
      })),
    },
    {
      key: 'weather',
      label: '天气',
      count: props.state.weather.length,
      icon: CloudSun,
      className: 'tone-cyan',
      items: props.state.weather.slice(0, 4).map((item) => ({
        title: item.date,
        meta: [item.day_weather, `${item.night_temp}°-${item.day_temp}°`, item.wind_direction]
          .filter(Boolean)
          .join(' · '),
      })),
    },
    {
      key: 'routes',
      label: '交通',
      count: props.state.routes?.daily_plan?.length || 0,
      icon: Route,
      className: 'tone-slate',
      items: (props.state.routes?.daily_plan || []).slice(0, 4).map((item, index) => ({
        title: `Day ${item.day_index || index + 1}`,
        meta: item.reason || props.state.routes?.suggested_mode || '已生成交通动线',
      })),
    },
  ].filter((group) => group.count > 0)
})

const resourceTotalCount = computed(() => resourceGroups.value.reduce((total, group) => total + group.count, 0))

function toggleResourceGroup(key: string) {
  expandedResources.value[key] = !expandedResources.value[key]
}
</script>

<template>
  <aside class="rounded-xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm md:p-6 xl:sticky xl:top-24 xl:h-fit">
    <div class="space-y-3">
      <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
        当前阶段
      </p>
      <div class="space-y-2">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h3 class="text-2xl font-semibold tracking-tight text-slate-950">
            {{ selectedNodeLabel }}
          </h3>
          <span class="inline-flex rounded-full bg-white px-3 py-1 text-sm font-medium text-slate-600 ring-1 ring-slate-200">
            {{ selectedStatusLabel }}
          </span>
        </div>
        <p class="text-sm leading-relaxed text-slate-600 md:text-base">
          {{ selectedSummary }}
        </p>
      </div>
    </div>

    <div v-if="detailChips.length" class="mt-5 flex flex-wrap gap-2">
      <span
        v-for="chip in detailChips"
        :key="chip"
        class="rounded-lg bg-white px-3 py-1 text-sm text-slate-600 ring-1 ring-slate-200"
      >
        {{ chip }}
      </span>
    </div>

    <div class="mt-8 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">Resources</p>
          <h4 class="mt-1 text-lg font-semibold text-slate-950">已获取的资源</h4>
        </div>
        <span class="text-sm tabular-nums text-slate-500">{{ resourceTotalCount }}</span>
      </div>

      <div v-if="resourceGroups.length" class="grid gap-3">
        <section
          v-for="group in resourceGroups"
          :key="group.key"
          class="resource-group"
          :class="group.className"
        >
          <button
            type="button"
            class="resource-group__header"
            :aria-expanded="expandedResources[group.key] ?? false"
            @click="toggleResourceGroup(group.key)"
          >
            <span class="resource-group__title">
              <component :is="group.icon" :size="18" />
              <span>
                <strong>{{ group.label }}</strong>
                <small>已获取 {{ group.count }} 条</small>
              </span>
            </span>
            <ChevronDown
              :size="18"
              class="transition-transform duration-300 ease-standard"
              :class="expandedResources[group.key] ? 'rotate-180' : ''"
            />
          </button>

          <div v-if="expandedResources[group.key]" class="grid gap-3 px-4 pb-4">
            <article
              v-for="item in group.items"
              :key="`${group.key}-${item.title}-${item.meta}`"
              class="rounded-lg border border-slate-200 bg-white px-3 py-3"
            >
              <strong class="block text-sm font-semibold text-slate-950">{{ item.title }}</strong>
              <p class="mt-1 text-sm leading-relaxed text-slate-600">{{ item.meta }}</p>
            </article>
          </div>
        </section>
      </div>

      <div
        v-else
        class="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-5 text-sm leading-relaxed text-slate-500"
      >
        规划开始后，这里会持续展示已经获取到的资源。
      </div>
    </div>
  </aside>
</template>

<style scoped>
.resource-group {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
}

.resource-group__header {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  text-align: left;
}

.resource-group__title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.resource-group__title strong,
.resource-group__title small {
  display: block;
}

.resource-group__title strong {
  font-size: 14px;
  font-weight: 700;
}

.resource-group__title small {
  font-size: 12px;
  color: #64748b;
}

.tone-sky .resource-group__header {
  background: #eff6ff;
  color: #0c4a6e;
}

.tone-emerald .resource-group__header {
  background: #ecfdf5;
  color: #064e3b;
}

.tone-amber .resource-group__header {
  background: #fffbeb;
  color: #78350f;
}

.tone-cyan .resource-group__header {
  background: #ecfeff;
  color: #164e63;
}

.tone-slate .resource-group__header {
  background: #f1f5f9;
  color: #0f172a;
}
</style>
