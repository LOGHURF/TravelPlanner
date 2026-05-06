import type { PlanningAgentDefinition, PlanningAgentId, PlanningAgentState } from '@/types/travel'

export const planningAgentDefinitions: PlanningAgentDefinition[] = [
  {
    id: 'orchestrator',
    label: '主控调度',
    phase: 'prepare',
    weight: 8,
    description: '读取当前状态，决定下一批要执行的节点，并接收审核后的修复任务。',
  },
  {
    id: 'strategy_agent',
    label: '策略规划',
    phase: 'prepare',
    weight: 20,
    description: '把用户需求拆成每日片区、必验景点锚点和住宿范围。',
  },
  {
    id: 'weather_agent',
    label: '天气检查',
    phase: 'parallel',
    weight: 10,
    description: '获取出行日期天气，标记雨、热、冷等会影响安排的约束。',
  },
  {
    id: 'anchor_resolver_agent',
    label: '锚点验真',
    phase: 'refine',
    weight: 20,
    description: '用 POI 验证策略里的地点真实存在，并排除公交站等错误类型。',
  },
  {
    id: 'nearby_poi_agent',
    label: '周边补全',
    phase: 'enrich',
    weight: 14,
    description: '围绕已验真的锚点召回酒店、午晚餐和可用周边 POI。',
  },
  {
    id: 'route_matrix_agent',
    label: '路线体检',
    phase: 'route',
    weight: 14,
    description: '计算景点、餐饮、酒店之间的距离，找出不可达和绕路风险。',
  },
  {
    id: 'itinerary_composer_agent',
    label: '行程拼装',
    phase: 'route',
    weight: 14,
    description: '把已验证 POI、餐饮、酒店和路线组合成每日动线。',
  },
  {
    id: 'plan_evaluator_agent',
    label: '方案审核',
    phase: 'evaluate',
    weight: 12,
    description: '检查完整性、偏好匹配、距离和风险；不通过就开修复单。',
  },
  {
    id: 'final_planning',
    label: '最终成稿',
    phase: 'finalize',
    weight: 10,
    description: '审核通过后合并所有阶段结果，输出可展示的最终行程。',
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
