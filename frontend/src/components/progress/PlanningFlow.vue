<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  AlertTriangle,
  Binary,
  Check,
  ChevronDown,
  Circle,
  CloudSun,
  FileText,
  Flag,
  GitBranch,
  Hotel,
  Play,
  Route,
  Search,
  Sparkles,
  UtensilsCrossed,
} from 'lucide-vue-next'
import type { LucideIcon } from 'lucide-vue-next'
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

type VisualNodeId = PlanningAgentId | 'start' | 'finish'

interface FlowNodeConfig {
  id: PlanningAgentId
  label: string
  shortLabel: string
  icon: LucideIcon
}

interface VisualNode {
  id: VisualNodeId
  label: string
  shortLabel: string
  caption: string
  icon: LucideIcon
  x: number
  y: number
  width?: number
  agentId?: PlanningAgentId
}

interface FlowEdge {
  from: VisualNodeId
  to: VisualNodeId
  path: string
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
  icon: LucideIcon
  headerClass: string
  iconClass: string
  bodyClass: string
}

const rootNode: FlowNodeConfig = {
  id: 'orchestrator',
  label: '需求拆解',
  shortLabel: '拆解',
  icon: Binary,
}

const parallelNodes: FlowNodeConfig[] = [
  { id: 'attraction_agent', label: '景点召回', shortLabel: '景点', icon: Search },
  { id: 'hotel_agent', label: '酒店召回', shortLabel: '酒店', icon: Hotel },
  { id: 'weather_agent', label: '天气召回', shortLabel: '天气', icon: CloudSun },
]

const chainNodes: FlowNodeConfig[] = [
  { id: 'reviewer_agent', label: '评审压缩', shortLabel: '评审', icon: Sparkles },
  { id: 'restaurant_agent', label: '餐饮补齐', shortLabel: '餐饮', icon: UtensilsCrossed },
  { id: 'transport_agent', label: '交通动线', shortLabel: '交通', icon: Route },
  { id: 'final_planning', label: '最终成稿', shortLabel: '成稿', icon: FileText },
]

const orderedNodes = [rootNode, ...parallelNodes, ...chainNodes]

const graphNodes: VisualNode[] = [
  {
    id: 'start',
    label: '开始',
    shortLabel: '开始',
    caption: '请求进入',
    icon: Play,
    x: 480,
    y: 70,
    width: 128,
  },
  {
    id: rootNode.id,
    agentId: rootNode.id,
    label: rootNode.label,
    shortLabel: rootNode.shortLabel,
    caption: '提取约束与检索参数',
    icon: rootNode.icon,
    x: 480,
    y: 230,
  },
  {
    id: 'attraction_agent',
    agentId: 'attraction_agent',
    label: '景点召回',
    shortLabel: '景点',
    caption: 'POI 与候选景点',
    icon: Search,
    x: 190,
    y: 470,
  },
  {
    id: 'hotel_agent',
    agentId: 'hotel_agent',
    label: '酒店召回',
    shortLabel: '酒店',
    caption: '住宿候选',
    icon: Hotel,
    x: 480,
    y: 470,
  },
  {
    id: 'weather_agent',
    agentId: 'weather_agent',
    label: '天气召回',
    shortLabel: '天气',
    caption: '日期天气切片',
    icon: CloudSun,
    x: 770,
    y: 470,
  },
  {
    id: 'reviewer_agent',
    agentId: 'reviewer_agent',
    label: '评审压缩',
    shortLabel: '评审',
    caption: '去重、筛选、收敛',
    icon: Sparkles,
    x: 480,
    y: 700,
  },
  {
    id: 'restaurant_agent',
    agentId: 'restaurant_agent',
    label: '餐饮补齐',
    shortLabel: '餐饮',
    caption: '按动线补餐饮',
    icon: UtensilsCrossed,
    x: 480,
    y: 875,
  },
  {
    id: 'transport_agent',
    agentId: 'transport_agent',
    label: '交通动线',
    shortLabel: '交通',
    caption: '计算每日移动',
    icon: Route,
    x: 480,
    y: 1050,
  },
  {
    id: 'final_planning',
    agentId: 'final_planning',
    label: '最终成稿',
    shortLabel: '成稿',
    caption: '合并为完整行程',
    icon: FileText,
    x: 480,
    y: 1225,
  },
  {
    id: 'finish',
    label: '完成',
    shortLabel: '完成',
    caption: '进入结果页',
    icon: Flag,
    x: 480,
    y: 1390,
    width: 128,
  },
]

const graphEdges: FlowEdge[] = [
  { from: 'start', to: 'orchestrator', path: 'M480 114 C486 138 474 162 480 186' },
  { from: 'orchestrator', to: 'attraction_agent', path: 'M480 274 C380 296 286 344 190 426' },
  { from: 'orchestrator', to: 'hotel_agent', path: 'M480 274 C486 328 474 376 480 426' },
  { from: 'orchestrator', to: 'weather_agent', path: 'M480 274 C580 296 674 344 770 426' },
  { from: 'attraction_agent', to: 'reviewer_agent', path: 'M190 514 C286 596 382 630 480 656' },
  { from: 'hotel_agent', to: 'reviewer_agent', path: 'M480 514 C474 570 486 610 480 656' },
  { from: 'weather_agent', to: 'reviewer_agent', path: 'M770 514 C674 596 578 630 480 656' },
  { from: 'reviewer_agent', to: 'restaurant_agent', path: 'M480 744 C486 774 474 802 480 831' },
  { from: 'restaurant_agent', to: 'transport_agent', path: 'M480 919 C474 950 486 976 480 1006' },
  { from: 'transport_agent', to: 'final_planning', path: 'M480 1094 C486 1124 474 1152 480 1181' },
  { from: 'final_planning', to: 'finish', path: 'M480 1269 C474 1298 486 1320 480 1346' },
]

const expandedResources = ref<Record<string, boolean>>({
  attractions: true,
  hotels: false,
  restaurants: false,
  weather: false,
  routes: false,
})

function isAgentNode(nodeId: VisualNodeId): nodeId is PlanningAgentId {
  return nodeId in props.state.agents
}

function agentState(agentId: PlanningAgentId) {
  return props.state.agents[agentId]
}

function hasStructuredResult(agentId: PlanningAgentId) {
  switch (agentId) {
    case 'orchestrator':
      return props.state.step !== 'idle' || props.state.eventLog.length > 0
    case 'attraction_agent':
      return props.state.attractions.length > 0
    case 'hotel_agent':
      return props.state.hotels.length > 0
    case 'reviewer_agent':
      return props.state.attractions.length > 0 || props.state.hotels.length > 0
    case 'restaurant_agent':
      return props.state.restaurants.length > 0
    case 'transport_agent':
      return Boolean(props.state.routes?.daily_plan?.length)
    case 'weather_agent':
      return props.state.weather.length > 0
    case 'final_planning':
      return Boolean(props.state.itinerary)
    default:
      return false
  }
}

function hasNodeActivity(agentId: PlanningAgentId) {
  const status = agentState(agentId)?.status || 'pending'
  return status === 'running' || status === 'completed' || hasStructuredResult(agentId)
}

function effectiveStatus(agentId: PlanningAgentId): PlanningAgentStatus {
  const rawStatus = agentState(agentId)?.status || 'pending'
  if (rawStatus !== 'pending') {
    return rawStatus
  }

  if (hasStructuredResult(agentId)) {
    return 'completed'
  }

  if (agentId === rootNode.id) {
    return orderedNodes.slice(1).some((node) => hasNodeActivity(node.id)) ? 'completed' : 'pending'
  }

  if (parallelNodes.some((node) => node.id === agentId)) {
    return 'pending'
  }

  const chainIndex = chainNodes.findIndex((node) => node.id === agentId)
  const laterCompleted =
    chainIndex >= 0 && chainNodes.slice(chainIndex + 1).some((node) => hasNodeActivity(node.id))

  return laterCompleted ? 'completed' : 'pending'
}

function visualNodeStatus(nodeId: VisualNodeId): PlanningAgentStatus {
  if (nodeId === 'start') {
    return props.state.step !== 'idle' || props.state.eventLog.length > 0 ? 'completed' : 'pending'
  }

  if (nodeId === 'finish') {
    if (props.state.step === 'error') {
      return 'error'
    }
    return props.state.itinerary ? 'completed' : 'pending'
  }

  return effectiveStatus(nodeId)
}

function effectiveProgress(agentId: PlanningAgentId) {
  const agent = agentState(agentId)
  const status = effectiveStatus(agentId)
  if (!agent) {
    return 0
  }
  if (status === 'completed') {
    return Math.max(100, agent.progress || 0)
  }
  if (status === 'running') {
    return Math.max(12, agent.progress || 0)
  }
  return agent.progress || 0
}

function resolveCountSummary(counts: Record<string, number> = {}) {
  const entries = Object.entries(counts).filter(([, value]) => Number(value) > 0)
  if (!entries.length) {
    return ''
  }

  return entries
    .map(([key, value]) => {
      if (key === 'items') return `${value} 项`
      if (key === 'days') return `${value} 天`
      if (key === 'attractions') return `${value} 景点`
      if (key === 'hotels') return `${value} 酒店`
      return `${value} ${key}`
    })
    .join(' · ')
}

function isGenericMessage(message?: string) {
  return ['已完成当前阶段处理', 'Agent 状态更新', '阶段结果已返回'].includes(String(message || '').trim())
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

function visualStatusLabel(nodeId: VisualNodeId) {
  if (!isAgentNode(nodeId)) {
    if (visualNodeStatus(nodeId) === 'completed') {
      return '已完成'
    }
    if (visualNodeStatus(nodeId) === 'error') {
      return '异常'
    }
    return '等待中'
  }
  return statusLabel(nodeId)
}

function statusBadgeClass(agentId: PlanningAgentId) {
  const status = effectiveStatus(agentId)
  return {
    pending: 'bg-slate-100 text-slate-500',
    running: 'bg-sky-100 text-sky-700',
    completed: 'bg-emerald-100 text-emerald-700',
    error: 'bg-rose-100 text-rose-700',
  }[status]
}

function defaultActiveAgentId(): PlanningAgentId {
  const runningNode = orderedNodes.find((node) => effectiveStatus(node.id) === 'running')
  if (runningNode) {
    return runningNode.id
  }

  const completedNode = [...orderedNodes]
    .reverse()
    .find((node) => effectiveStatus(node.id) === 'completed')

  return completedNode?.id || 'orchestrator'
}

const selectedAgentId = computed<PlanningAgentId>(() => {
  const requestedId = props.activeAgentId as PlanningAgentId | ''
  if (requestedId && agentState(requestedId)) {
    return requestedId
  }
  return defaultActiveAgentId()
})

const selectedNode = computed(() => {
  return orderedNodes.find((node) => node.id === selectedAgentId.value) || rootNode
})

const selectedAgent = computed(() => agentState(selectedAgentId.value))

const selectedSummary = computed(() => {
  const agent = selectedAgent.value
  if (!agent) {
    return props.headlineCopy || '等待阶段状态更新。'
  }

  if (agent.lastMessage && !isGenericMessage(agent.lastMessage)) {
    return agent.lastMessage
  }

  if (agent.description) {
    return agent.description
  }

  return props.headlineCopy || '等待阶段状态更新。'
})

const detailChips = computed(() => {
  const agent = selectedAgent.value
  if (!agent) {
    return []
  }

  const chips = [`进度 ${effectiveProgress(selectedAgentId.value)}%`]
  const countSummary = resolveCountSummary(agent.counts || {})
  if (countSummary) {
    chips.push(countSummary)
  }
  return chips
})

const progressValue = computed(() => Math.max(0, Math.min(100, props.state.progress || 0)))

const resourceGroups = computed<ResourceGroup[]>(() => {
  return [
    {
      key: 'attractions',
      label: '景点',
      count: props.state.attractions.length,
      icon: Search,
      headerClass: 'border-sky-200 bg-sky-50 text-sky-900',
      iconClass: 'bg-sky-500 text-white',
      bodyClass: 'bg-sky-50/55',
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
      headerClass: 'border-emerald-200 bg-emerald-50 text-emerald-900',
      iconClass: 'bg-emerald-500 text-white',
      bodyClass: 'bg-emerald-50/55',
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
      headerClass: 'border-amber-200 bg-amber-50 text-amber-900',
      iconClass: 'bg-amber-500 text-white',
      bodyClass: 'bg-amber-50/55',
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
      headerClass: 'border-cyan-200 bg-cyan-50 text-cyan-900',
      iconClass: 'bg-cyan-500 text-white',
      bodyClass: 'bg-cyan-50/55',
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
      headerClass: 'border-slate-300 bg-slate-100 text-slate-900',
      iconClass: 'bg-slate-700 text-white',
      bodyClass: 'bg-slate-100/75',
      items: (props.state.routes?.daily_plan || []).slice(0, 4).map((item, index) => ({
        title: `Day ${item.day_index || index + 1}`,
        meta: item.reason || props.state.routes?.suggested_mode || '已生成交通动线',
      })),
    },
  ].filter((group) => group.count > 0)
})

const resourceTotalCount = computed(() => {
  return resourceGroups.value.reduce((total, group) => total + group.count, 0)
})

const resourceEmptyCopy = computed(() => {
  if (props.state.step === 'idle') {
    return '规划开始后，这里会持续展示已经获取到的资源。'
  }
  return '当前还没有获取到可展示的资源。'
})

function isActiveNode(nodeId: VisualNodeId) {
  return nodeId === selectedAgentId.value
}

function isEdgeActive(edge: FlowEdge) {
  if (edge.to === selectedAgentId.value) {
    return true
  }

  const targetStatus = visualNodeStatus(edge.to)
  const sourceStatus = visualNodeStatus(edge.from)
  return targetStatus === 'running' || (sourceStatus === 'running' && targetStatus !== 'pending')
}

function isEdgeCompleted(edge: FlowEdge) {
  return visualNodeStatus(edge.from) === 'completed' && visualNodeStatus(edge.to) === 'completed'
}

function workflowNodeClass(node: VisualNode) {
  const status = visualNodeStatus(node.id)
  return [
    'workflow-node',
    `is-${status}`,
    isActiveNode(node.id) ? 'is-active' : '',
    !node.agentId ? 'is-system' : '',
  ]
}

function workflowEdgeClass(edge: FlowEdge) {
  return [
    'workflow-edge',
    isEdgeActive(edge) ? 'is-active' : '',
    isEdgeCompleted(edge) ? 'is-completed' : '',
  ]
}

function edgeMarker(edge: FlowEdge) {
  if (isEdgeActive(edge)) {
    return 'url(#workflow-arrow-active)'
  }
  if (isEdgeCompleted(edge)) {
    return 'url(#workflow-arrow-completed)'
  }
  return 'url(#workflow-arrow-pending)'
}

function nodeIcon(nodeId: VisualNodeId) {
  const status = visualNodeStatus(nodeId)
  if (status === 'completed') {
    return Check
  }
  if (status === 'error') {
    return AlertTriangle
  }
  if (!isAgentNode(nodeId) && nodeId !== 'start') {
    return Circle
  }
  return null
}

function nodeStyle(node: VisualNode) {
  return {
    left: `${(node.x / 960) * 100}%`,
    top: `${(node.y / 1460) * 100}%`,
    width: `${node.width || 156}px`,
  }
}

function handleSelect(node: VisualNode) {
  if (!node.agentId) {
    return
  }
  emit('selectAgent', node.agentId)
}

function toggleResourceGroup(key: string) {
  expandedResources.value[key] = !expandedResources.value[key]
}

function isResourceGroupExpanded(key: string) {
  return expandedResources.value[key] ?? false
}
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-7">
    <div class="grid gap-7 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div class="grid gap-5">
        <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
          <div class="space-y-3">
            <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
              Workflow Graph
            </p>
            <h2 class="text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">
              {{ props.currentStageLabel }}
            </h2>
            <p class="max-w-[46rem] text-sm leading-relaxed text-slate-600 md:text-base">
              {{ props.headlineCopy || '点击图上的节点查看当前阶段说明和已返回资源。' }}
            </p>
          </div>

          <div class="space-y-3">
            <div class="h-3 overflow-hidden rounded-full bg-slate-200">
              <div
                class="h-full rounded-full bg-sky-600 transition-[width] duration-500 ease-standard"
                :style="{ width: `${progressValue}%` }"
              />
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="tracking-[0.14em] text-slate-500">OVERALL PROGRESS</span>
              <strong class="font-semibold tabular-nums text-slate-950">{{ progressValue }}%</strong>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 bg-slate-50 p-4 md:p-5">
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
            <div class="flex items-center gap-3">
              <span class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700">
                <GitBranch class="h-4 w-4" />
              </span>
              <div>
                <h3 class="text-base font-semibold text-slate-950">执行拓扑</h3>
                <p class="text-sm text-slate-500">从需求拆解到最终成稿的真实流向</p>
              </div>
            </div>

            <span class="rounded-lg bg-white px-3 py-1 text-sm text-slate-600 ring-1 ring-slate-200">
              当前查看：{{ selectedNode.label }}
            </span>
          </div>

          <div
            data-testid="workflow-graph-canvas"
            class="workflow-graph-canvas mt-5 overflow-x-auto rounded-xl border border-slate-200 bg-white"
          >
            <div class="relative min-h-[1160px] min-w-[860px]">
              <svg
                class="absolute inset-0 h-full w-full"
                viewBox="0 0 960 1460"
                fill="none"
                role="img"
                aria-label="规划工作流拓扑图"
              >
                <defs>
                  <marker
                    id="workflow-arrow-pending"
                    data-testid="workflow-arrow-pending"
                    markerWidth="24"
                    markerHeight="24"
                    refX="19"
                    refY="12"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                  >
                    <path d="M3 3L21 12L3 21Z" fill="#cbd5e1" stroke="#ffffff" stroke-width="3" />
                  </marker>
                  <marker
                    id="workflow-arrow-active"
                    data-testid="workflow-arrow-active"
                    markerWidth="24"
                    markerHeight="24"
                    refX="19"
                    refY="12"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                  >
                    <path d="M3 3L21 12L3 21Z" fill="#2563eb" stroke="#ffffff" stroke-width="3" />
                  </marker>
                  <marker
                    id="workflow-arrow-completed"
                    data-testid="workflow-arrow-completed"
                    markerWidth="24"
                    markerHeight="24"
                    refX="19"
                    refY="12"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                  >
                    <path d="M3 3L21 12L3 21Z" fill="#059669" stroke="#ffffff" stroke-width="3" />
                  </marker>
                </defs>

                <path
                  v-for="edge in graphEdges"
                  :key="`underlay-${edge.from}-${edge.to}`"
                  :d="edge.path"
                  data-workflow-edge-underlay
                  class="workflow-edge-underlay"
                />

                <path
                  v-for="edge in graphEdges"
                  :key="`${edge.from}-${edge.to}`"
                  :d="edge.path"
                  :data-workflow-edge="`${edge.from}-to-${edge.to}`"
                  :class="workflowEdgeClass(edge)"
                  :marker-end="edgeMarker(edge)"
                />
              </svg>

              <button
                v-for="node in graphNodes"
                :key="node.id"
                type="button"
                :data-workflow-node="node.id"
                :aria-pressed="isActiveNode(node.id)"
                :disabled="!node.agentId"
                :class="workflowNodeClass(node)"
                :style="nodeStyle(node)"
                @click="handleSelect(node)"
              >
                <span class="workflow-node-icon">
                  <component
                    :is="nodeIcon(node.id) || node.icon"
                    class="h-5 w-5"
                  />
                </span>
                <span class="workflow-node-copy">
                  <strong>{{ node.label }}</strong>
                  <span>{{ visualStatusLabel(node.id) }}</span>
                </span>
                <span class="workflow-node-caption">{{ node.caption }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <aside class="rounded-xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm md:p-6 xl:sticky xl:top-24 xl:h-fit">
        <div class="space-y-3">
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
            当前阶段
          </p>
          <div class="space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <h3 class="text-2xl font-semibold tracking-tight text-slate-950">
                {{ selectedNode.label }}
              </h3>
              <span
                class="inline-flex rounded-full px-3 py-1 text-sm font-medium"
                :class="statusBadgeClass(selectedAgentId)"
              >
                {{ statusLabel(selectedAgentId) }}
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
              <p class="text-xs font-medium uppercase tracking-[0.18em] text-sky-600">
                Resources
              </p>
              <h4 class="mt-1 text-lg font-semibold text-slate-950">
                已获取的资源
              </h4>
            </div>
            <span class="text-sm tabular-nums text-slate-500">
              {{ resourceTotalCount }}
            </span>
          </div>

          <div v-if="resourceGroups.length" class="grid gap-3">
            <section
              v-for="group in resourceGroups"
              :key="group.key"
              class="overflow-hidden rounded-lg border border-slate-200 bg-white"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 border-b px-4 py-4 text-left transition-colors duration-200 ease-standard"
                :class="group.headerClass"
                :aria-expanded="isResourceGroupExpanded(group.key)"
                @click="toggleResourceGroup(group.key)"
              >
                <span class="flex min-w-0 items-center gap-3">
                  <span
                    class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-sm"
                    :class="group.iconClass"
                  >
                    <component :is="group.icon" :size="18" />
                  </span>
                  <span class="min-w-0">
                    <strong class="block text-sm font-semibold">
                      {{ group.label }}
                    </strong>
                    <span class="block text-xs opacity-80">
                      已获取 {{ group.count }} 条
                    </span>
                  </span>
                </span>

                <ChevronDown
                  :size="18"
                  class="shrink-0 transition-transform duration-300 ease-standard"
                  :class="isResourceGroupExpanded(group.key) ? 'rotate-180' : ''"
                />
              </button>

              <div
                class="grid overflow-hidden transition-all duration-300 ease-standard"
                :class="isResourceGroupExpanded(group.key) ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
              >
                <div class="min-h-0 overflow-hidden">
                  <div class="grid gap-3 px-4 py-4" :class="group.bodyClass">
                    <article
                      v-for="item in group.items"
                      :key="`${group.key}-${item.title}-${item.meta}`"
                      class="rounded-lg border border-slate-200 bg-white px-3 py-3"
                    >
                      <strong class="block text-sm font-semibold text-slate-950">
                        {{ item.title }}
                      </strong>
                      <p class="mt-1 text-sm leading-relaxed text-slate-600">
                        {{ item.meta }}
                      </p>
                    </article>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div
            v-else
            class="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-5 text-sm leading-relaxed text-slate-500"
          >
            {{ resourceEmptyCopy }}
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.workflow-graph-canvas {
  background-image: radial-gradient(circle, #dbe3ee 1px, transparent 1px);
  background-size: 24px 24px;
}

.workflow-edge {
  stroke: #cbd5e1;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 8 11;
  vector-effect: non-scaling-stroke;
}

.workflow-edge-underlay {
  stroke: rgb(255 255 255 / 0.96);
  stroke-width: 9;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

.workflow-edge.is-completed {
  stroke: #059669;
  stroke-dasharray: none;
}

.workflow-edge.is-active {
  stroke: #2563eb;
  stroke-width: 4;
  stroke-dasharray: none;
  filter: drop-shadow(0 7px 10px rgb(37 99 235 / 0.20));
}

.workflow-node {
  position: absolute;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  grid-template-rows: auto auto;
  align-items: center;
  column-gap: 10px;
  row-gap: 4px;
  min-height: 72px;
  padding: 9px 10px;
  border: 1px solid #dbe5f1;
  border-radius: 12px;
  background: #ffffff;
  transform: translate(-50%, -50%);
  color: #475569;
  box-shadow: 0 12px 30px rgb(15 23 42 / 0.08);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    color 180ms ease,
    transform 180ms ease;
}

.workflow-node:disabled {
  cursor: default;
}

.workflow-node:not(:disabled) {
  cursor: pointer;
}

.workflow-node:not(:disabled):hover {
  transform: translate(-50%, -50%) scale(1.03);
}

.workflow-node-icon {
  display: inline-flex;
  grid-row: 1 / span 2;
  height: 36px;
  width: 36px;
  align-items: center;
  justify-content: center;
  border: 2px solid #dbe5f1;
  border-radius: 10px;
  background: #f8fafc;
  color: #64748b;
}

.workflow-node-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
  text-align: left;
}

.workflow-node-copy strong {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.workflow-node-copy span,
.workflow-node-caption {
  font-size: 10px;
  line-height: 1.25;
  color: #64748b;
}

.workflow-node-caption {
  grid-column: 2;
  min-width: 0;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-node.is-running .workflow-node-icon,
.workflow-node.is-active .workflow-node-icon {
  border-color: #60a5fa;
  background: #2563eb;
  color: #ffffff;
  box-shadow:
    0 0 0 3px rgb(37 99 235 / 0.12),
    0 10px 20px rgb(37 99 235 / 0.18);
}

.workflow-node.is-running,
.workflow-node.is-active {
  border-color: #60a5fa;
  box-shadow:
    0 0 0 4px rgb(37 99 235 / 0.10),
    0 16px 36px rgb(37 99 235 / 0.16);
}

.workflow-node.is-completed .workflow-node-icon {
  border-color: #5eead4;
  background: #ecfdf5;
  color: #047857;
}

.workflow-node.is-completed {
  border-color: #99f6e4;
  background: #f0fdfa;
}

.workflow-node.is-error .workflow-node-icon {
  border-color: #fda4af;
  background: #fff1f2;
  color: #be123c;
}

.workflow-node.is-error {
  border-color: #fda4af;
  background: #fff1f2;
}

.workflow-node.is-pending .workflow-node-icon {
  background: #ffffff;
}

.workflow-node.is-active .workflow-node-copy strong,
.workflow-node.is-running .workflow-node-copy strong {
  color: #1d4ed8;
}
</style>
