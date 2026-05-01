<script setup lang="ts">
import { computed } from 'vue'
import { NotebookPen } from 'lucide-vue-next'
import type { TripPlan } from '@/types/travel'

const props = defineProps<{
  plan: TripPlan
  compact?: boolean
}>()

const narrativeParagraphs = computed(() =>
  (props.plan.narrative_plan || props.plan.overall_suggestions || '')
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, props.compact ? 1 : 3),
)

const compactSummary = computed(
  () =>
    narrativeParagraphs.value[0] ||
    props.plan.important_notes?.[0] ||
    props.plan.packing_tips?.[0] ||
    '',
)
</script>

<template>
  <section class="notes atlas-surface" :class="{ compact: props.compact }">
    <template v-if="props.compact">
      <article v-if="compactSummary" class="compact-summary">
        <NotebookPen :size="16" />
        <p>{{ compactSummary }}</p>
      </article>
    </template>

    <template v-else>
      <div v-if="!props.compact" class="atlas-section-title">
        <div>
          <span>Notes Board</span>
          <h2>最后把建议、提醒和行囊提示钉住</h2>
        </div>
      </div>

      <div class="notes-copy">
        <article v-for="paragraph in narrativeParagraphs" :key="paragraph">
          <NotebookPen :size="18" />
          <p>{{ paragraph }}</p>
        </article>
      </div>

      <div v-if="plan.important_notes?.length" class="tag-row">
        <span
          v-for="note in plan.important_notes.slice(0, props.compact ? 3 : 6)"
          :key="note"
        >
          {{ note }}
        </span>
      </div>

      <div v-if="plan.packing_tips?.length" class="packing-box">
        <strong>行李建议</strong>
        <p>
          {{ plan.packing_tips.slice(0, props.compact ? 3 : plan.packing_tips.length).join(' · ') }}
        </p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.notes {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.notes-copy {
  display: grid;
  gap: 10px;
}

.notes-copy article {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(19, 34, 59, 0.1);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.56);
}

.notes-copy p,
.packing-box p {
  color: var(--color-text-secondary);
  font-size: 0.92rem;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-row span {
  padding: 8px 12px;
  border: 1px solid rgba(19, 34, 59, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.52);
  font-size: 0.9rem;
}

.packing-box {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(19, 34, 59, 0.05);
}

.notes.compact {
  padding: 10px 12px;
}

.compact-summary {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: start;
}

.compact-summary p {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 0.86rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
</style>
