<script setup lang="ts">
import {
  AlertTriangle,
  Binary,
  CloudSun,
  FileCheck2,
  FileText,
  MapPinned,
  Route,
  Search,
  Sparkles,
  UtensilsCrossed,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import type { PlanningAgentId } from '@/types/travel'
import './PlanningLoopGraph.css'

interface AgentCard {
  id: PlanningAgentId
  label: string
  caption: string
  input: string
  output: string
  icon: Component
}

interface StageColumn {
  key: string
  marker: string
  title: string
  description: string
  isWorker?: boolean
  agents: AgentCard[]
}

interface Props {
  repairRound: number
  cardClass: (agentId: PlanningAgentId) => string[]
  statusLabel: (agentId: PlanningAgentId) => string
  nodeIcon: (agentId: PlanningAgentId) => Component | null
}

defineProps<Props>()

const emit = defineEmits<{
  selectAgent: [agentId: PlanningAgentId]
}>()

const orchestrator: AgentCard = {
  id: 'orchestrator',
  label: '主控调度',
  caption: '决定下一步该派谁，审核失败时生成修复批次。',
  input: '用户需求 / 当前状态',
  output: '下一批执行节点',
  icon: Binary,
}

const stages: StageColumn[] = [
  {
    key: 'control',
    marker: '01',
    title: '主控调度',
    description: '读取状态，决定下一批执行节点。',
    agents: [orchestrator],
  },
  {
    key: 'batch-one',
    marker: '02',
    title: '第 1 批：策略与约束',
    description: '先确定旅行骨架、天气约束和真实地点。',
    isWorker: true,
    agents: [
      {
        id: 'strategy_agent',
        label: '策略规划',
        caption: '把需求拆成每日片区、必验锚点和住宿范围。',
        input: '目的地 / 偏好 / 天数',
        output: '每日片区骨架',
        icon: Search,
      },
      {
        id: 'weather_agent',
        label: '天气检查',
        caption: '获取出行日期天气，标记雨热冷等约束。',
        input: '目的地 / 日期',
        output: '天气风险',
        icon: CloudSun,
      },
      {
        id: 'anchor_resolver_agent',
        label: '锚点验真',
        caption: '用 POI 验证策略地点真实存在且类型正确。',
        input: '策略锚点',
        output: '真实 POI',
        icon: MapPinned,
      },
    ],
  },
  {
    key: 'batch-two',
    marker: '03',
    title: '第 2 批：落地与组合',
    description: '补齐可用 POI，检查距离，再拼成每日草案。',
    isWorker: true,
    agents: [
      {
        id: 'nearby_poi_agent',
        label: '周边补全',
        caption: '围绕锚点找酒店、午晚餐和可用周边 POI。',
        input: '真实锚点',
        output: '酒店 / 餐饮',
        icon: UtensilsCrossed,
      },
      {
        id: 'route_matrix_agent',
        label: '路线体检',
        caption: '计算点位间距离，找不可达和绕路风险。',
        input: '景点 / 酒店 / 餐饮',
        output: '路线矩阵',
        icon: Route,
      },
      {
        id: 'itinerary_composer_agent',
        label: '行程拼装',
        caption: '把验证后的点位组合成每天可执行动线。',
        input: 'POI / 路线矩阵',
        output: '每日草案',
        icon: Sparkles,
      },
    ],
  },
  {
    key: 'review',
    marker: '04',
    title: '审核与成稿',
    description: '审核通过就成稿，不通过则交回主控定向修复。',
    agents: [
      {
        id: 'plan_evaluator_agent',
        label: '方案审核',
        caption: '检查完整性、偏好、距离和风险；不通过就开修复单。',
        input: '完整草案',
        output: '通过 / 修复任务',
        icon: AlertTriangle,
      },
      {
        id: 'final_planning',
        label: '最终成稿',
        caption: '审核通过后合并所有结果，生成可展示行程。',
        input: '通过的草案',
        output: '最终行程',
        icon: FileText,
      },
    ],
  },
]

function selectAgent(agentId: PlanningAgentId) {
  emit('selectAgent', agentId)
}
</script>

<template>
  <div data-testid="orchestrator-loop" class="workflow-shell">
    <div class="workflow-shell__header">
      <div>
        <h3>阶段看板</h3>
        <p>按真实职责分组展示规划状态，不用连线表达顺序；当前执行、已完成和异常状态直接落在节点卡片上。</p>
      </div>
      <span>{{ repairRound ? `第 ${repairRound} 轮修复` : '初始规划轮' }}</span>
    </div>

    <div class="stage-board">
      <section
        v-for="stage in stages"
        :key="stage.key"
        class="stage-column"
        :data-stage="stage.key"
      >
        <div class="stage-column__head">
          <span>{{ stage.marker }}</span>
          <div>
            <h4>{{ stage.title }}</h4>
            <p>{{ stage.description }}</p>
          </div>
        </div>

        <div class="stage-column__cards">
          <button
            v-for="agent in stage.agents"
            :key="agent.id"
            type="button"
            :data-workflow-node="agent.id"
            :data-worker-node="stage.isWorker ? agent.id : null"
            :class="cardClass(agent.id)"
            @click="selectAgent(agent.id)"
          >
            <span class="agent-card__icon"><component :is="nodeIcon(agent.id) || agent.icon" /></span>
            <span class="agent-card__copy">
              <strong>{{ agent.label }}</strong>
              <span>{{ statusLabel(agent.id) }}</span>
              <small>{{ agent.caption }}</small>
              <em><b>输入</b>{{ agent.input }}</em>
              <em><b>输出</b>{{ agent.output }}</em>
            </span>
          </button>
        </div>
      </section>
    </div>

    <div data-testid="repair-notice" class="repair-notice">
      <FileCheck2 />
      <div>
        <strong>审核回环</strong>
        <span>审核不通过会回到主控生成下一批修复任务，只重跑需要修复的节点。</span>
      </div>
    </div>
  </div>
</template>
