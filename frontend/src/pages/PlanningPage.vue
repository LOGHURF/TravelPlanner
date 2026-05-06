<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, RefreshCw } from 'lucide-vue-next'
import AppNavBar from '@/components/layout/AppNavBar.vue'
import PlanningFlow from '@/components/progress/PlanningFlow.vue'
import { Button, Toast } from '@/components/ui'
import { usePlannerStore } from '@/stores/planner'
import { usePlanResultStore } from '@/stores/planResult'
import type { PlanningAgentId } from '@/types/travel'

const route = useRoute()
const router = useRouter()
const plannerStore = usePlannerStore()
const planResultStore = usePlanResultStore()

const redirected = ref(false)
const savedPlanId = ref('')
const showErrorToast = ref(false)
const selectedAgentId = ref<PlanningAgentId | ''>('')

const reviewPlanId = computed(() => String(route.query.review || ''))
const isReviewMode = computed(() => Boolean(reviewPlanId.value))
const tripBrief = computed(() => plannerStore.request)
const currentStageLabel = computed(() => plannerStore.currentStageLabel)
const isCompleted = computed(() => plannerStore.state.step === 'completed')
const hasError = computed(() => plannerStore.state.step === 'error')
const canOpenResult = computed(() =>
  Boolean(plannerStore.itinerary && plannerStore.request && !isReviewMode.value),
)

const tripChips = computed(() =>
  [
    tripBrief.value?.duration ? `${tripBrief.value.duration} 天` : '',
    tripBrief.value?.num_people ? `${tripBrief.value.num_people} 人` : '',
    tripBrief.value?.companions || '',
    tripBrief.value?.pace ? `${tripBrief.value.pace} 节奏` : '',
  ].filter(Boolean),
)

const headlineCopy = computed(() => {
  if (hasError.value) {
    return plannerStore.state.error || '规划出现异常'
  }
  if (isCompleted.value) {
    return 'Orchestrator 已收敛所有 Worker 输出，最终结果已生成。'
  }
  return '主控按批次派发规划节点，方案审核不通过时会回到主控，定向重跑需要修复的节点。'
})

onMounted(async () => {
  if (isReviewMode.value) {
    const reviewRecord = planResultStore.loadResult(reviewPlanId.value)
    if (reviewRecord?.planningState) {
      plannerStore.restoreSnapshot(reviewRecord.request, reviewRecord.planningState)
      return
    }
    await router.replace({ name: 'home' })
    return
  }

  const request = plannerStore.request ?? plannerStore.hydrateDraft()
  if (!request) {
    await router.replace({ name: 'home' })
    return
  }

  if (!plannerStore.hasStarted) {
    await plannerStore.streamPlan()
  }
})

watch(
  () => plannerStore.itinerary,
  (plan) => {
    if (!plan || !plannerStore.request || redirected.value || isReviewMode.value) {
      return
    }
    redirected.value = true
    const planId = ensureSavedPlanId()
    if (!planId) {
      return
    }
    void router.push({ name: 'plan-result', params: { planId } })
  },
  { immediate: true },
)

watch(
  () => hasError.value,
  (value) => {
    if (value) {
      showErrorToast.value = true
    }
  },
)

function ensureSavedPlanId() {
  if (savedPlanId.value) {
    return savedPlanId.value
  }
  if (!plannerStore.itinerary || !plannerStore.request) {
    return ''
  }

  savedPlanId.value = planResultStore.saveResult(
    plannerStore.itinerary,
    plannerStore.request,
    plannerStore.state,
  )
  return savedPlanId.value
}

function goToResult() {
  const planId = ensureSavedPlanId()
  if (!planId) {
    return
  }
  router.push({ name: 'plan-result', params: { planId } })
}

async function retryPlanning() {
  if (!plannerStore.request) {
    return
  }
  showErrorToast.value = false
  plannerStore.setRequest(plannerStore.request)
  redirected.value = false
  savedPlanId.value = ''
  await plannerStore.streamPlan()
}
</script>

<template>
  <main class="min-h-screen">
    <AppNavBar
      :back-to="{ name: 'home' }"
      back-label="返回首页"
      :title="tripBrief?.destination || '规划中'"
      subtitle="Planning Session"
      :chips="tripChips"
    >
      <template #actions>
        <Button
          v-if="canOpenResult"
          size="sm"
          @click="goToResult"
        >
          查看行程
          <ArrowRight :size="16" />
        </Button>
        <Button
          v-else-if="hasError && !isReviewMode"
          variant="secondary"
          size="sm"
          @click="retryPlanning"
        >
          <RefreshCw :size="16" />
          重新规划
        </Button>
      </template>
    </AppNavBar>

    <section class="mx-auto max-w-[1440px] px-4 pb-12 pt-8 md:px-6 lg:px-10 lg:pt-10">
      <div class="grid gap-8">
        <PlanningFlow
          :state="plannerStore.state"
          :current-stage-label="currentStageLabel"
          :headline-copy="headlineCopy"
          :active-agent-id="selectedAgentId || plannerStore.activeAgentId"
          @select-agent="selectedAgentId = $event"
        />
      </div>
    </section>

    <Toast
      v-model:visible="showErrorToast"
      type="error"
      message="规划过程中出现错误，请重试"
      position="top"
      :duration="5000"
    />
  </main>
</template>
