import { defineStore } from 'pinia'
import {
  getPlanRecord,
  savePlanRecord,
} from '@/services/storage/planStorage'
import type { PlanningState, StoredPlanRecord, TripPlan, TripRequest } from '@/types/travel'

export const usePlanResultStore = defineStore('plan-result', {
  state: () => ({
    activeDayByPlan: {} as Record<string, number>,
  }),
  actions: {
    saveResult(plan: TripPlan, request: TripRequest, planningState?: PlanningState): string {
      return savePlanRecord(plan, request, planningState)
    },
    loadResult(planId: string): StoredPlanRecord | null {
      return getPlanRecord(planId)
    },
    getActiveDay(planId: string): number {
      return this.activeDayByPlan[planId] ?? 0
    },
    setActiveDay(planId: string, index: number): void {
      this.activeDayByPlan[planId] = index
    },
  },
})
