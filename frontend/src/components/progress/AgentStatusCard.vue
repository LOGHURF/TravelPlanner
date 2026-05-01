<script setup lang="ts">
import { computed } from 'vue'
import {
  BedDouble,
  Bot,
  Calculator,
  CheckCircle2,
  CloudSun,
  Clock3,
  FileText,
  Loader2,
  Route,
  Search,
  UtensilsCrossed,
  XCircle,
} from 'lucide-vue-next'
import type { PlanningAgentId, PlanningAgentState } from '@/types/travel'

interface Props {
  agent: PlanningAgentState
  isActive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isActive: false,
})

const emit = defineEmits<{
  click: [agentId: PlanningAgentId]
}>()

const iconMap: Partial<Record<PlanningAgentId, typeof Bot>> = {
  orchestrator: Bot,
  attraction_agent: Search,
  restaurant_agent: UtensilsCrossed,
  hotel_agent: BedDouble,
  weather_agent: CloudSun,
  reviewer_agent: Calculator,
  transport_agent: Route,
  final_planning: FileText,
}

const statusConfig = {
  pending: {
    icon: Clock3,
    label: '等待中',
    tone: 'bg-slate-100 text-slate-500',
    ring: 'border-white/35',
    progress: 'bg-slate-300',
  },
  running: {
    icon: Loader2,
    label: '执行中',
    tone: 'bg-sky-100 text-sky-700',
    ring: 'border-sky-200 bg-sky-50/70',
    progress: 'bg-gradient-to-r from-sky-500 to-emerald-400',
  },
  completed: {
    icon: CheckCircle2,
    label: '已完成',
    tone: 'bg-emerald-100 text-emerald-700',
    ring: 'border-emerald-200 bg-emerald-50/70',
    progress: 'bg-gradient-to-r from-emerald-500 to-teal-400',
  },
  error: {
    icon: XCircle,
    label: '异常',
    tone: 'bg-rose-100 text-rose-700',
    ring: 'border-rose-200 bg-rose-50/70',
    progress: 'bg-gradient-to-r from-rose-500 to-orange-400',
  },
} as const

const iconComponent = computed(() => iconMap[props.agent.id] || Bot)
const statusMeta = computed(() => statusConfig[props.agent.status])
const isRunning = computed(() => props.agent.status === 'running')
const visibleLogs = computed(() => props.agent.logs.slice(-3))

function handleClick() {
  emit('click', props.agent.id)
}
</script>

<template>
  <button
    type="button"
    class="glass-surface group relative w-full overflow-hidden rounded-panel border p-4 text-left shadow-glass transition-all duration-300 ease-standard will-change-transform"
    :class="[
      props.isActive
        ? 'border-sky-300 bg-white/84 shadow-glass-hover'
        : `border-white/35 bg-white/68 hover:-translate-y-0.5 hover:border-sky-200 hover:bg-white/80 hover:shadow-glass-hover`,
      statusMeta.ring,
    ]"
    :aria-pressed="props.isActive"
    @click="handleClick"
  >
    <div class="pointer-events-none absolute inset-x-4 bottom-0 h-0.5 rounded-full bg-sky-500/80 opacity-0 transition-all duration-300 ease-spring group-hover:opacity-100" />

    <div class="flex items-start gap-3">
      <div
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-emerald-400 text-white shadow-sm"
      >
        <component :is="iconComponent" :size="18" />
      </div>

      <div class="min-w-0 flex-1 space-y-2">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h4 class="truncate text-base font-semibold text-slate-900">
              {{ props.agent.label }}
            </h4>
            <p class="mt-1 line-clamp-2 text-sm leading-relaxed text-slate-500">
              {{ props.agent.description }}
            </p>
          </div>

          <span class="text-sm font-semibold tabular-nums text-slate-700">
            {{ props.agent.progress }}%
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span
            class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
            :class="statusMeta.tone"
          >
            <component
              :is="statusMeta.icon"
              :size="12"
              :class="isRunning ? 'animate-spin' : ''"
            />
            {{ statusMeta.label }}
          </span>
          <span
            v-if="Object.keys(props.agent.counts || {}).length"
            class="rounded-full bg-white/70 px-2.5 py-1 text-xs uppercase tracking-wider text-slate-500"
          >
            {{ Object.values(props.agent.counts).reduce((sum, value) => sum + value, 0) }} items
          </span>
        </div>

        <div class="h-1.5 overflow-hidden rounded-full bg-slate-200/80">
          <div
            class="h-full rounded-full transition-[width] duration-500 ease-standard"
            :class="statusMeta.progress"
            :style="{ width: `${props.agent.progress}%` }"
          />
        </div>

        <p v-if="props.agent.lastMessage" class="text-sm leading-relaxed text-slate-600">
          {{ props.agent.lastMessage }}
        </p>

        <div v-if="props.isActive && visibleLogs.length" class="grid gap-2 pt-1">
          <p class="text-xs font-medium uppercase tracking-wider text-sky-600">
            Recent Logs
          </p>
          <div class="grid gap-2">
            <div
              v-for="(log, index) in visibleLogs"
              :key="`${props.agent.id}-${index}`"
              class="rounded-2xl border border-white/30 bg-white/62 px-3 py-2 text-sm leading-relaxed text-slate-600"
            >
              {{ log }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </button>
</template>
