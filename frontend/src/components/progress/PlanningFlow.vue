<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Check, Circle } from 'lucide-vue-next'
import type { Component } from 'vue'
import PlanningLoopGraph from './PlanningLoopGraph.vue'
import PlanningResourcePanel from './PlanningResourcePanel.vue'
import type { PlanningAgentId, PlanningAgentStatus, PlanningState } from '@/types/travel'

interface Props {
  state: PlanningState
  currentStageLabel?: string
  headlineCopy?: string
  activeAgentId?: PlanningAgentId | ''
}

const props = withDefaults(defineProps<Props>(), {
  currentStageLabel: '准备中',
  headlineCopy: '',
  activeAgentId: '',
})

const emit = defineEmits<{
  selectAgent: [agentId: PlanningAgentId]
}>()

const orderedAgentIds: PlanningAgentId[] = [
  'orchestrator',
  'strategy_agent',
  'weather_agent',
  'anchor_resolver_agent',
  'nearby_poi_agent',
  'route_matrix_agent',
  'itinerary_composer_agent',
  'plan_evaluator_agent',
  'final_planning',
]

function agentState(agentId: PlanningAgentId) {
  return props.state.agents[agentId]
}

function hasStructuredResult(agentId: PlanningAgentId) {
  switch (agentId) {
    case 'orchestrator':
      return props.state.step !== 'idle' || props.state.eventLog.length > 0
    case 'strategy_agent':
      return Boolean(agentState(agentId)?.counts?.days)
    case 'anchor_resolver_agent':
      return Boolean(agentState(agentId)?.counts?.items)
    case 'nearby_poi_agent':
      return props.state.attractions.length > 0 || props.state.hotels.length > 0 || props.state.restaurants.length > 0
    case 'route_matrix_agent':
      return Boolean(agentState(agentId)?.counts?.routes || agentState(agentId)?.counts?.issues)
    case 'itinerary_composer_agent':
      return props.state.restaurants.length > 0
    case 'weather_agent':
      return props.state.weather.length > 0
    case 'plan_evaluator_agent':
      return Boolean(agentState(agentId)?.counts?.score)
    case 'final_planning':
      return Boolean(props.state.itinerary)
    default:
      return false
  }
}

function effectiveStatus(agentId: PlanningAgentId): PlanningAgentStatus {
  const rawStatus = agentState(agentId)?.status || 'pending'
  if (rawStatus !== 'pending') {
    return rawStatus
  }
  return hasStructuredResult(agentId) ? 'completed' : 'pending'
}

function effectiveProgress(agentId: PlanningAgentId) {
  const agent = agentState(agentId)
  const status = effectiveStatus(agentId)
  if (!agent) return 0
  if (status === 'completed') return Math.max(100, agent.progress || 0)
  if (status === 'running') return Math.max(12, agent.progress || 0)
  return agent.progress || 0
}

function statusLabel(agentId: PlanningAgentId) {
  switch (effectiveStatus(agentId)) {
    case 'running':
      return '执行中'
    case 'completed':
      return '已完成'
    case 'error':
      return '异常'
    default:
      return '等待中'
  }
}

function nodeIcon(agentId: PlanningAgentId): Component | null {
  const status = effectiveStatus(agentId)
  if (status === 'completed') return Check
  if (status === 'error') return AlertTriangle
  if (status === 'pending') return Circle
  return null
}

function cardClass(agentId: PlanningAgentId) {
  return [
    'agent-card',
    `is-${effectiveStatus(agentId)}`,
    selectedAgentId.value === agentId ? 'is-active' : '',
  ]
}

function countSummary(counts: Record<string, number> = {}) {
  const entries = Object.entries(counts).filter(([, value]) => Number(value) > 0)
  if (!entries.length) return ''
  return entries
    .map(([key, value]) => {
      if (key === 'items') return `${value} 项`
      if (key === 'days') return `${value} 天`
      if (key === 'attractions') return `${value} 景点`
      if (key === 'hotels') return `${value} 酒店`
      if (key === 'score') return `${value} 分`
      if (key === 'issues') return `${value} 问题`
      if (key === 'repairs') return `${value} 修复`
      return `${value} ${key}`
    })
    .join(' · ')
}

function defaultActiveAgentId(): PlanningAgentId {
  const running = orderedAgentIds.find((agentId) => effectiveStatus(agentId) === 'running')
  if (running) return running
  const completed = [...orderedAgentIds].reverse().find((agentId) => effectiveStatus(agentId) === 'completed')
  return completed || 'orchestrator'
}

function displayLabel(agentId: PlanningAgentId) {
  return agentState(agentId)?.label || agentId
}

const selectedAgentId = computed<PlanningAgentId>(() => {
  const requested = props.activeAgentId as PlanningAgentId | ''
  return requested && agentState(requested) ? requested : defaultActiveAgentId()
})

const selectedAgent = computed(() => agentState(selectedAgentId.value))
const selectedNodeLabel = computed(() => displayLabel(selectedAgentId.value))

const selectedSummary = computed(() => {
  const agent = selectedAgent.value
  if (agent?.lastMessage) return agent.lastMessage
  if (agent?.description) return agent.description
  return props.headlineCopy || '等待阶段状态更新。'
})

const planningRisk = computed(() => {
  const lines = [
    ...props.state.messages,
    ...props.state.eventLog.map((item) => item.message),
  ]
  return (
    lines.find((line) => line.includes('最大修复轮') || line.includes('审核风险')) || ''
  )
})

const detailChips = computed(() => {
  const agent = selectedAgent.value
  if (!agent) return []
  const chips = [`进度 ${effectiveProgress(selectedAgentId.value)}%`]
  const summary = countSummary(agent.counts || {})
  if (summary) chips.push(summary)
  return chips
})

const repairRound = computed(() => {
  const text = [...props.state.messages, ...props.state.eventLog.map((item) => item.message)].join('\n')
  const matches = [...text.matchAll(/第\s*(\d+)\s*轮定向修复/g)]
  return matches.length ? Number(matches[matches.length - 1][1]) : 0
})

const progressValue = computed(() => Math.max(0, Math.min(100, props.state.progress || 0)))

function handleSelect(agentId: PlanningAgentId) {
  emit('selectAgent', agentId)
}
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
    <div class="grid gap-6">
      <div class="grid gap-5">
        <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-end">
          <div class="space-y-3">
            <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
              编排流程
            </p>
            <h2 class="text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">
              {{ props.currentStageLabel }}
            </h2>
            <p class="max-w-[46rem] text-sm leading-relaxed text-slate-600 md:text-base">
              {{ props.headlineCopy || '主控按批次派发任务，审核节点只判断方案是否够好；不通过就回到主控定向重跑对应节点。' }}
            </p>
            <div
              v-if="planningRisk"
              data-testid="planning-risk"
              class="flex max-w-[46rem] items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm leading-relaxed text-amber-900"
            >
              <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
              <div class="min-w-0">
                <strong class="block font-semibold">带风险成稿</strong>
                <span>{{ planningRisk }}</span>
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div class="h-3 overflow-hidden rounded-full bg-slate-200">
              <div
                class="h-full rounded-full bg-sky-600 transition-[width] duration-500 ease-standard"
                :style="{ width: `${progressValue}%` }"
              />
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="tracking-[0.14em] text-slate-500">整体进度</span>
              <strong class="font-semibold tabular-nums text-slate-950">{{ progressValue }}%</strong>
            </div>
          </div>
        </div>

        <PlanningLoopGraph
          :repair-round="repairRound"
          :card-class="cardClass"
          :status-label="statusLabel"
          :node-icon="nodeIcon"
          @select-agent="handleSelect"
        />
      </div>

      <PlanningResourcePanel
        :state="props.state"
        :selected-node-label="selectedNodeLabel"
        :selected-status-label="statusLabel(selectedAgentId)"
        :selected-summary="selectedSummary"
        :detail-chips="detailChips"
      />
    </div>
  </section>
</template>
