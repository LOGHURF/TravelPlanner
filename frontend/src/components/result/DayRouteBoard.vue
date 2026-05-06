<script setup lang="ts">
import { computed } from 'vue'
import {
  BedDouble,
  Clock3,
  MapPin,
  MapPinned,
  Route,
  Star,
  UtensilsCrossed,
  Wallet,
} from 'lucide-vue-next'
import type { DailyPlan } from '@/types/travel'
import { formatShortDate } from '@/utils/date'
import {
  getAttractionImage,
  getHotelImage,
  getRestaurantImage,
} from '@/utils/media'

const props = defineProps<{
  day: DailyPlan
}>()

const timelineItems = computed(() => props.day.timeline || [])
const routeSegments = computed(() => props.day.route_segments || [])
const costCards = computed(() => [
  {
    label: '景点',
    value: Math.round(Number(props.day.estimated_cost?.attractions || 0)),
  },
  {
    label: '餐饮',
    value: Math.round(Number(props.day.estimated_cost?.meals || 0)),
  },
  {
    label: '交通',
    value: Math.round(Number(props.day.estimated_cost?.transport || 0)),
  },
  {
    label: '住宿',
    value: Math.round(Number(props.day.estimated_cost?.hotel || 0)),
  },
])

function cardTone(category?: string) {
  const value = String(category || '')
  if (value.includes('历史') || value.includes('文化')) return 'activity-card--violet'
  if (value.includes('自然') || value.includes('风景')) return 'activity-card--green'
  if (value.includes('娱乐') || value.includes('休闲')) return 'activity-card--amber'
  return 'activity-card--blue'
}

function formatMealAnchor(meal: DailyPlan['meals'][number]) {
  const distance = Number(meal.distance_to_anchor_km || 0)
  if (!meal.meal_anchor_name || distance <= 0) {
    return ''
  }
  return `距 ${meal.meal_anchor_name} ${distance.toFixed(1)} km`
}
</script>

<template>
  <section class="day-board">
    <header class="day-board__header">
      <div>
        <p class="day-board__eyebrow">Day {{ day.day_index }}</p>
        <h3>{{ day.description || `第 ${day.day_index} 天行程` }}</h3>
        <p class="day-board__summary">
          {{ formatShortDate(day.date) }}
          <span v-if="day.weather">· {{ day.weather.day_weather }} {{ day.weather.night_temp }}°-{{ day.weather.day_temp }}°</span>
          <span v-if="day.hotel?.name">· 住 {{ day.hotel.name }}</span>
        </p>
      </div>

      <div class="day-board__meta">
        <span v-if="day.transport_mode">{{ day.transport_mode }}</span>
        <span v-if="day.weather_note">{{ day.weather_note }}</span>
      </div>
    </header>

    <div class="day-board__hero-grid">
      <article class="day-board__panel">
        <div class="day-board__panel-head">
          <Clock3 :size="16" />
          <strong>执行时间线</strong>
        </div>

        <div v-if="timelineItems.length" class="timeline-list">
          <article
            v-for="item in timelineItems"
            :key="`${item.time}-${item.activity}`"
            class="timeline-item"
          >
            <div class="timeline-item__time">{{ item.time }}</div>
            <div class="timeline-item__content">
              <strong>{{ item.activity }}</strong>
              <span>{{ item.type }}</span>
            </div>
          </article>
        </div>

        <div v-else class="day-board__empty">当前日程暂无细分时间线。</div>
      </article>

      <article class="day-board__panel">
        <div class="day-board__panel-head">
          <Wallet :size="16" />
          <strong>当日预算</strong>
        </div>

        <div class="cost-grid">
          <article v-for="card in costCards" :key="card.label" class="cost-card">
            <span>{{ card.label }}</span>
            <strong>¥{{ card.value || 0 }}</strong>
          </article>
        </div>
      </article>
    </div>

    <section class="day-board__section">
      <div class="day-board__section-head">
        <div class="day-board__section-title">
          <MapPinned :size="18" />
          <h4>核心景点</h4>
        </div>
        <span>{{ day.attractions.length }} 个</span>
      </div>

      <div class="activity-grid">
        <article
          v-for="spot in day.attractions"
          :key="spot.name"
          class="activity-card"
          :class="cardTone(spot.category)"
        >
          <div class="activity-card__image">
            <img
              v-if="getAttractionImage(spot)"
              :src="getAttractionImage(spot)"
              :alt="spot.name"
            />
            <div v-else class="activity-card__placeholder">
              <MapPin :size="20" />
            </div>
          </div>

          <div class="activity-card__body">
            <div class="activity-card__topline">
              <span>{{ spot.category || '推荐景点' }}</span>
              <small v-if="spot.rating">
                <Star :size="12" fill="currentColor" />
                {{ spot.rating.toFixed(1) }}
              </small>
            </div>
            <strong>{{ spot.name }}</strong>
            <p>{{ spot.description || spot.address || '已纳入今日路线' }}</p>
          </div>
        </article>
      </div>
    </section>

    <div class="day-board__detail-grid">
      <section class="day-board__section">
        <div class="day-board__section-head">
          <div class="day-board__section-title">
            <UtensilsCrossed :size="18" />
            <h4>餐饮安排</h4>
          </div>
          <span>{{ day.meals.length }} 个</span>
        </div>

        <div v-if="day.meals.length" class="detail-list">
          <article v-for="meal in day.meals" :key="meal.name" class="detail-item">
            <div class="detail-item__thumb">
              <img
                v-if="getRestaurantImage(meal)"
                :src="getRestaurantImage(meal)"
                :alt="meal.name"
              />
              <div v-else class="detail-item__fallback">
                <UtensilsCrossed :size="16" />
              </div>
            </div>

            <div class="detail-item__copy">
              <strong>{{ meal.name }}</strong>
              <span>{{ meal.cuisine_type || meal.meal_type || meal.type }}</span>
              <span v-if="formatMealAnchor(meal)">{{ formatMealAnchor(meal) }}</span>
            </div>
          </article>
        </div>

        <div v-else class="day-board__empty">暂无餐饮信息。</div>
      </section>

      <section class="day-board__section">
        <div class="day-board__section-head">
          <div class="day-board__section-title">
            <BedDouble :size="18" />
            <h4>住宿安排</h4>
          </div>
        </div>

        <article v-if="day.hotel" class="hotel-card">
          <div class="hotel-card__thumb">
            <img
              v-if="getHotelImage(day.hotel)"
              :src="getHotelImage(day.hotel)"
              :alt="day.hotel.name"
            />
            <div v-else class="hotel-card__fallback">
              <BedDouble :size="18" />
            </div>
          </div>

          <div class="hotel-card__copy">
            <strong>{{ day.hotel.name }}</strong>
            <span>{{ day.hotel.hotel_level || '住宿推荐' }}</span>
            <p>{{ day.hotel.address || day.accommodation || '已纳入本日行程' }}</p>
          </div>
        </article>

        <div v-else class="day-board__empty">暂无住宿信息。</div>
      </section>
    </div>

    <section class="day-board__section">
      <div class="day-board__section-head">
        <div class="day-board__section-title">
          <Route :size="18" />
          <h4>路线段</h4>
        </div>
        <span>{{ routeSegments.length }} 段</span>
      </div>

      <div v-if="routeSegments.length" class="route-list">
        <article
          v-for="segment in routeSegments"
          :key="`${segment.from_name}-${segment.to_name}`"
          class="route-item"
        >
          <strong>{{ segment.from_name }} → {{ segment.to_name }}</strong>
          <span>
            {{ segment.mode || 'mixed' }}
            <template v-if="segment.distance"> · {{ segment.distance }} km</template>
            <template v-if="segment.duration"> · {{ segment.duration }} 分钟</template>
          </span>
        </article>
      </div>

      <div v-else class="day-board__empty">当前没有额外路径段明细。</div>
    </section>
  </section>
</template>

<style scoped>
.day-board {
  display: grid;
  gap: var(--space-5);
}

.day-board__header,
.day-board__panel,
.day-board__section {
  padding: 20px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(9, 16, 29, 0.9), rgba(10, 19, 34, 0.96));
}

.day-board__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.day-board__eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.48);
}

.day-board__header h3,
.day-board__section h4 {
  color: #ffffff;
}

.day-board__summary,
.day-board__meta,
.day-board__empty,
.timeline-item__content span,
.detail-item__copy span,
.route-item span,
.hotel-card__copy span,
.hotel-card__copy p,
.activity-card__body p,
.cost-card span {
  color: rgba(230, 238, 255, 0.68);
}

.day-board__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

.day-board__meta span {
  padding: 7px 12px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.05);
  font-size: var(--text-xs);
}

.day-board__hero-grid,
.day-board__detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.day-board__panel {
  display: grid;
  gap: var(--space-4);
}

.day-board__panel-head,
.day-board__section-head,
.day-board__section-title,
.timeline-item,
.detail-item,
.hotel-card,
.route-item {
  display: flex;
  align-items: center;
}

.day-board__panel-head,
.day-board__section-head {
  justify-content: space-between;
}

.day-board__panel-head strong,
.timeline-item__content strong,
.detail-item__copy strong,
.hotel-card__copy strong,
.route-item strong,
.activity-card__body strong,
.cost-card strong {
  color: #ffffff;
}

.timeline-list,
.detail-list,
.route-list {
  display: grid;
  gap: var(--space-3);
}

.timeline-item,
.detail-item,
.hotel-card,
.route-item {
  gap: var(--space-3);
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.timeline-item__time {
  min-width: 60px;
  font-size: var(--text-sm);
  color: #9ce8d3;
}

.timeline-item__content,
.detail-item__copy,
.hotel-card__copy {
  display: grid;
  gap: 4px;
}

.cost-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.cost-card {
  display: grid;
  gap: 4px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.cost-card strong {
  font-size: var(--text-xl);
}

.activity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.activity-card {
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
}

.activity-card__image {
  height: 180px;
}

.activity-card__image img,
.detail-item__thumb img,
.hotel-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.activity-card__placeholder,
.detail-item__fallback,
.hotel-card__fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.activity-card__body {
  display: grid;
  gap: var(--space-3);
  padding: 18px;
}

.activity-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.activity-card__topline span,
.activity-card__topline small {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs);
  color: rgba(230, 238, 255, 0.72);
}

.activity-card--blue {
  box-shadow: inset 0 1px 0 rgba(56, 189, 248, 0.08);
}

.activity-card--green {
  box-shadow: inset 0 1px 0 rgba(52, 211, 153, 0.08);
}

.activity-card--amber {
  box-shadow: inset 0 1px 0 rgba(251, 191, 36, 0.08);
}

.activity-card--violet {
  box-shadow: inset 0 1px 0 rgba(167, 139, 250, 0.08);
}

.detail-item__thumb,
.hotel-card__thumb {
  width: 72px;
  height: 72px;
  overflow: hidden;
  border-radius: 16px;
  flex-shrink: 0;
}

.route-item {
  justify-content: space-between;
  flex-wrap: wrap;
}

@media (max-width: 960px) {
  .day-board__hero-grid,
  .day-board__detail-grid,
  .activity-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .day-board__header {
    flex-direction: column;
  }

  .day-board__meta {
    justify-content: flex-start;
  }
}
</style>
