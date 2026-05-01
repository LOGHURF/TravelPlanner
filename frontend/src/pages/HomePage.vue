<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Compass } from 'lucide-vue-next'
import TripComposerForm from '@/components/planner/TripComposerForm.vue'
import { checkHealth } from '@/services/api/planner'
import { usePlannerStore } from '@/stores/planner'
import type { TripRequest } from '@/types/travel'

const router = useRouter()
const plannerStore = usePlannerStore()

const backendReady = ref(false)
const initialData = computed(() => plannerStore.hydrateDraft())

onMounted(async () => {
  backendReady.value = await checkHealth()
})

function handleSubmit(payload: TripRequest) {
  plannerStore.setRequest(payload)
  router.push({ name: 'planning' })
}
</script>

<template>
  <main class="relative min-h-screen overflow-hidden bg-[#eef3f2] text-slate-900">
    <div class="map-backdrop pointer-events-none absolute inset-0" aria-hidden="true" />

    <header class="relative z-10 mx-auto max-w-[1120px] px-4 pt-4 md:px-6 lg:px-8">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="inline-flex w-fit items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm">
          <span
            class="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-600 text-white shadow-sm"
          >
            <Compass :size="18" />
          </span>
          <span class="min-w-0">
            <span class="block text-[11px] font-medium uppercase tracking-[0.18em] text-sky-600">
              TravelPlanner
            </span>
            <strong class="block text-sm font-semibold text-slate-900">
              行程规划控制台
            </strong>
          </span>
        </div>

        <span
          class="inline-flex w-fit items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium shadow-sm"
          :class="backendReady
            ? 'border-emerald-200 bg-white text-emerald-700'
            : 'border-amber-200 bg-white text-amber-700'"
        >
          <span class="h-2 w-2 rounded-full bg-current" />
          {{ backendReady ? '后端已连接' : '后端未连接' }}
        </span>
      </div>
    </header>

    <section
      class="relative z-10 mx-auto flex min-h-[calc(100vh-76px)] max-w-[1120px] items-start px-4 pb-8 pt-5 md:px-6 md:pt-7 lg:px-8"
    >
      <TripComposerForm
        class="w-full max-w-[820px]"
        :initial-data="initialData"
        @submit="handleSubmit"
      />
    </section>
  </main>
</template>

<style scoped>
.map-backdrop {
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    linear-gradient(0deg, rgba(148, 163, 184, 0.14) 1px, transparent 1px),
    linear-gradient(135deg, transparent 0 36%, rgba(14, 165, 233, 0.14) 36% 36.6%, transparent 36.6% 100%),
    linear-gradient(42deg, transparent 0 55%, rgba(16, 185, 129, 0.12) 55% 55.6%, transparent 55.6% 100%),
    #eef3f2;
  background-size:
    56px 56px,
    56px 56px,
    100% 100%,
    100% 100%,
    auto;
}
</style>
