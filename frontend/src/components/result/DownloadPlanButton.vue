<script setup lang="ts">
import { Download } from 'lucide-vue-next'
import { downloadPlanAsHtml } from '@/services/storage/planStorage'
import type { TripPlan } from '@/types/travel'

const props = defineProps<{
  plan: TripPlan
}>()

function handleDownload() {
  const fileName = `${props.plan.city || 'trip-plan'}-${props.plan.start_date || 'plan'}-行程网页.html`
  downloadPlanAsHtml(props.plan, fileName)
}
</script>

<template>
  <button class="atlas-button secondary" type="button" @click="handleDownload">
    <Download :size="18" />
    导出 HTML
  </button>
</template>
