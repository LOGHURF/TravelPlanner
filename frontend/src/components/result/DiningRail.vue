<script setup lang="ts">
import { UtensilsCrossed } from 'lucide-vue-next'
import type { Restaurant } from '@/types/travel'

defineProps<{
  restaurants: Restaurant[]
}>()

const mealLabels: Record<string, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '加餐',
}
</script>

<template>
  <section class="rail atlas-surface">
    <div class="atlas-section-title">
      <div>
        <span>Dining Notes</span>
        <h2>把吃饭点放在当天的路线后面</h2>
      </div>
    </div>

    <div class="dining-grid">
      <article v-for="restaurant in restaurants.slice(0, 6)" :key="`${restaurant.name}-${restaurant.type}`">
        <div class="card-head">
          <strong>{{ restaurant.name }}</strong>
          <span>{{ mealLabels[restaurant.type] || restaurant.type }}</span>
        </div>
        <p>{{ restaurant.description || restaurant.address || '优先推荐离当天路线更顺手的餐饮点。' }}</p>
        <small v-if="restaurant.rating || restaurant.price_per_person">
          <UtensilsCrossed :size="14" />
          <span v-if="restaurant.rating">评分 {{ restaurant.rating.toFixed(1) }}</span>
          <span v-if="restaurant.price_per_person">人均 ¥{{ Math.round(restaurant.price_per_person) }}</span>
        </small>
      </article>
    </div>
  </section>
</template>

<style scoped>
.rail {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.dining-grid {
  display: grid;
  gap: 10px;
}

.dining-grid article {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid rgba(19, 34, 59, 0.1);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.56);
}

.card-head,
.dining-grid small {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-head span,
.dining-grid p,
.dining-grid small {
  color: var(--color-text-secondary);
  font-size: 0.92rem;
}
</style>
