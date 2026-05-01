<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ChevronDown,
  Hotel,
  MapPin,
  Route,
  UtensilsCrossed,
  Wind,
} from 'lucide-vue-next'
import AgentStatusCard from './AgentStatusCard.vue'
import type {
  PlanningAgentId,
  PlanningEventRecord,
  PlanningState,
} from '@/types/travel'

interface Props {
  state: PlanningState
  activeAgentId?: PlanningAgentId | ''
  currentStageLabel?: string
  recentEvents?: PlanningEventRecord[]
}

const props = withDefaults(defineProps<Props>(), {
  activeAgentId: '',
  currentStageLabel: '准备中',
  recentEvents: () => [],
})

const emit = defineEmits<{
  selectAgent: [agentId: PlanningAgentId]
}>()

const expandedSections = ref<Record<string, boolean>>({
  attractions: true,
  hotels: false,
  restaurants: false,
  weather: false,
  routes: false,
})

const selectedAgentId = ref<PlanningAgentId | null>(null)

watch(
  () => props.activeAgentId,
  (value) => {
    if (value) {
      selectedAgentId.value = value
    }
  },
  { immediate: true },
)

const agents = computed(() => Object.values(props.state.agents || {}))

const selectedAgent = computed(() => {
  const fallback = (props.activeAgentId || 'orchestrator') as PlanningAgentId
  const agentId = (selectedAgentId.value || fallback) as PlanningAgentId
  return props.state.agents[agentId]
})

const resourceSections = computed(() => [
  {
    key: 'attractions',
    label: '景点',
    icon: MapPin,
    count: props.state.attractions.length,
    items: props.state.attractions.map((item) => ({
      title: item.name,
      meta: item.rating ? `评分 ${item.rating.toFixed(1)}` : item.category || '候选景点',
    })),
  },
  {
    key: 'hotels',
    label: '酒店',
    icon: Hotel,
    count: props.state.hotels.length,
    items: props.state.hotels.map((item) => ({
      title: item.name,
      meta: item.hotel_level || item.address || '住宿候选',
    })),
  },
  {
    key: 'restaurants',
    label: '餐饮',
    icon: UtensilsCrossed,
    count: props.state.restaurants.length,
    items: props.state.restaurants.map((item) => ({
      title: item.name,
      meta: item.cuisine_type || item.type || '餐饮候选',
    })),
  },
  {
    key: 'weather',
    label: '天气',
    icon: Wind,
    count: props.state.weather.length,
    items: props.state.weather.map((item) => ({
      title: item.date,
      meta: `${item.day_weather} ${item.night_temp}°-${item.day_temp}°`,
    })),
  },
  {
    key: 'routes',
    label: '交通',
    icon: Route,
    count: props.state.routes?.daily_plan?.length || 0,
    items: (props.state.routes?.daily_plan || []).map((item, index) => ({
      title: `Day ${item.day_index || index + 1}`,
      meta: item.reason || props.state.routes?.suggested_mode || '动线已生成',
    })),
  },
])

function toggleSection(key: string) {
  expandedSections.value[key] = !expandedSections.value[key]
}

function isExpanded(key: string) {
  return expandedSections.value[key] ?? false
}

function handleSelectAgent(agentId: PlanningAgentId) {
  selectedAgentId.value = agentId
  emit('selectAgent', agentId)
}
</script>

<template>
  <section class="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
    <div class="grid gap-6">
      <div class="glass-surface rounded-[28px] border border-white/35 p-6 shadow-glass md:p-8">
        <div class="space-y-3">
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
            Current Stage
          </p>
          <h3 class="text-2xl font-light tracking-tight text-slate-900">
            {{ props.currentStageLabel }}
          </h3>
        </div>

        <div
          v-if="selectedAgent"
          class="mt-5 rounded-[24px] border border-sky-200 bg-sky-50/80 p-5"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <strong class="text-lg font-semibold text-slate-900">
              {{ selectedAgent.label }}
            </strong>
            <span class="text-sm font-semibold tabular-nums text-sky-700">
              {{ selectedAgent.progress }}%
            </span>
          </div>
          <p class="mt-3 text-sm leading-relaxed text-slate-600">
            {{ selectedAgent.lastMessage || selectedAgent.description }}
          </p>
        </div>
      </div>

      <div class="glass-surface rounded-[28px] border border-white/35 p-6 shadow-glass md:p-8">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
              Agent Panel
            </p>
            <h3 class="mt-2 text-2xl font-light tracking-tight text-slate-900">
              执行节点
            </h3>
          </div>
          <p class="text-sm leading-relaxed text-slate-500">
            点击任一节点查看最近阶段日志。
          </p>
        </div>

        <div class="mt-6 grid gap-3">
          <AgentStatusCard
            v-for="agent in agents"
            :key="agent.id"
            :agent="agent"
            :is-active="agent.id === (selectedAgentId || props.activeAgentId)"
            @click="handleSelectAgent"
          />
        </div>
      </div>
    </div>

    <div class="grid gap-6">
      <div class="glass-surface rounded-[28px] border border-white/35 p-6 shadow-glass md:p-8">
        <div class="space-y-3">
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
            Resources
          </p>
          <h3 class="text-2xl font-light tracking-tight text-slate-900">
            已找到的资源
          </h3>
        </div>

        <div class="mt-6 grid gap-3">
          <section
            v-for="section in resourceSections"
            v-show="section.count > 0"
            :key="section.key"
            class="rounded-[24px] border border-white/35 bg-white/60"
          >
            <button
              type="button"
              class="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
              :aria-expanded="isExpanded(section.key)"
              @click="toggleSection(section.key)"
            >
              <span class="inline-flex min-w-0 items-center gap-3">
                <span class="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-emerald-400 text-white shadow-sm">
                  <component :is="section.icon" :size="15" />
                </span>
                <span class="min-w-0">
                  <span class="block text-sm font-semibold text-slate-900">
                    {{ section.label }}
                  </span>
                  <span class="block text-xs uppercase tracking-wider text-slate-500">
                    {{ section.count }} items
                  </span>
                </span>
              </span>

              <ChevronDown
                :size="16"
                class="shrink-0 text-slate-400 transition-transform duration-300 ease-standard"
                :class="isExpanded(section.key) ? 'rotate-180' : ''"
              />
            </button>

            <div
              class="grid overflow-hidden transition-all duration-300 ease-standard"
              :class="isExpanded(section.key) ? 'grid-rows-[1fr] px-5 pb-5' : 'grid-rows-[0fr] px-5'"
            >
              <div class="min-h-0 overflow-hidden">
                <div class="grid gap-2">
                  <article
                    v-for="item in section.items"
                    :key="`${section.key}-${item.title}-${item.meta}`"
                    class="rounded-2xl border border-white/30 bg-white/72 px-4 py-3"
                  >
                    <strong class="block text-sm font-semibold text-slate-900">
                      {{ item.title }}
                    </strong>
                    <span class="mt-1 block text-sm leading-relaxed text-slate-500">
                      {{ item.meta }}
                    </span>
                  </article>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div class="glass-surface rounded-[28px] border border-white/35 p-6 shadow-glass md:p-8">
        <div class="space-y-3">
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
            Recent Events
          </p>
          <h3 class="text-2xl font-light tracking-tight text-slate-900">
            流式日志
          </h3>
        </div>

        <div class="mt-6 grid gap-3">
          <article
            v-for="event in props.recentEvents"
            :key="event.id"
            class="rounded-[24px] border border-white/35 bg-white/62 px-5 py-4"
          >
            <strong class="block text-sm font-semibold text-slate-900">
              {{ event.label || event.agentId || event.eventType }}
            </strong>
            <p class="mt-2 text-sm leading-relaxed text-slate-500">
              {{ event.message }}
            </p>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>
