import type { PlanningAgentDefinition, PlanningAgentId, PlanningAgentState } from '@/types/travel'

export const planningAgentDefinitions: PlanningAgentDefinition[] = [
  {
    id: 'orchestrator',
    label: '需求拆解',
    phase: 'prepare',
    weight: 8,
    description: '整理出目的地、偏好、预算与检索关键词。',
  },
  {
    id: 'attraction_agent',
    label: '景点 Agent',
    phase: 'parallel',
    weight: 20,
    description: '并行召回景点候选，形成路线骨架。',
  },
  {
    id: 'hotel_agent',
    label: '酒店 Agent',
    phase: 'parallel',
    weight: 20,
    description: '补足住宿候选，并与行程重心对齐。',
  },
  {
    id: 'weather_agent',
    label: '天气 Agent',
    phase: 'parallel',
    weight: 10,
    description: '并行召回出行日期内的天气切片和提醒。',
  },
  {
    id: 'reviewer_agent',
    label: '评审 Agent',
    phase: 'refine',
    weight: 14,
    description: '对景点和酒店做筛选，去掉不合适项。',
  },
  {
    id: 'restaurant_agent',
    label: '餐饮 Agent',
    phase: 'enrich',
    weight: 14,
    description: '根据路线与节奏加入餐饮建议。',
  },
  {
    id: 'transport_agent',
    label: '交通 Agent',
    phase: 'route',
    weight: 14,
    description: '拼接城市内移动方式与每日动线。',
  },
  {
    id: 'final_planning',
    label: '成稿 Agent',
    phase: 'finalize',
    weight: 10,
    description: '合并所有阶段结果，输出最终行程。',
  },
]

export const planningAgentDefinitionMap = planningAgentDefinitions.reduce(
  (accumulator, definition) => {
    accumulator[definition.id] = definition
    return accumulator
  },
  {} as Record<PlanningAgentId, PlanningAgentDefinition>,
)

export function createPlanningAgents(): Record<PlanningAgentId, PlanningAgentState> {
  return planningAgentDefinitions.reduce(
    (accumulator, definition) => {
      accumulator[definition.id] = {
        id: definition.id,
        label: definition.label,
        phase: definition.phase,
        description: definition.description,
        status: 'pending',
        progress: 0,
        logs: [],
        counts: {},
      }
      return accumulator
    },
    {} as Record<PlanningAgentId, PlanningAgentState>,
  )
}
