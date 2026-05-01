<script setup lang="ts">
import { computed } from 'vue'
import {
  Cloud,
  CloudRain,
  CloudSun,
  Sun,
  Wind,
} from 'lucide-vue-next'
import type { WeatherInfo } from '@/types/travel'
import { formatShortDate } from '@/utils/date'

interface Props {
  weatherList: WeatherInfo[]
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
})

function getWeatherIcon(weather: string) {
  const text = weather.toLowerCase()
  if (text.includes('雨')) return CloudRain
  if (text.includes('晴')) return Sun
  if (text.includes('云') || text.includes('阴')) return Cloud
  return CloudSun
}

function getTone(weather: string) {
  const text = weather.toLowerCase()
  if (text.includes('雨')) return 'weather-item--rain'
  if (text.includes('晴')) return 'weather-item--sunny'
  if (text.includes('云') || text.includes('阴')) return 'weather-item--cloudy'
  return 'weather-item--mild'
}

const displayList = computed(() => props.weatherList.slice(0, props.compact ? 7 : 5))
</script>

<template>
  <section class="weather-rail" :class="{ 'weather-rail--compact': compact }">
    <header class="weather-rail__header">
      <div>
        <p class="weather-rail__eyebrow">Weather</p>
        <h3>天气概览</h3>
      </div>
    </header>

    <div class="weather-rail__list" :class="{ 'weather-rail__list--compact': compact }">
      <article
        v-for="(item, index) in displayList"
        :key="item.date"
        class="weather-item"
        :class="getTone(item.day_weather)"
      >
        <div class="weather-item__icon">
          <component :is="getWeatherIcon(item.day_weather)" :size="18" />
        </div>

        <div class="weather-item__copy">
          <strong>{{ compact ? `Day ${index + 1}` : formatShortDate(item.date) }}</strong>
          <span>{{ item.day_weather }} · {{ item.night_temp }}°-{{ item.day_temp }}°</span>
        </div>

        <div class="weather-item__meta">
          <span>{{ formatShortDate(item.date) }}</span>
          <small>
            <Wind :size="12" />
            {{ item.wind_direction || '微风' }}
          </small>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.weather-rail {
  display: grid;
  gap: var(--space-4);
}

.weather-rail__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.weather-rail__eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: rgba(255, 255, 255, 0.5);
}

.weather-rail__header h3 {
  color: #ffffff;
}

.weather-rail__list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-3);
}

.weather-rail__list--compact {
  grid-template-columns: 1fr;
}

.weather-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.05);
}

.weather-item__icon {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  color: #ffffff;
}

.weather-item__copy,
.weather-item__meta {
  display: grid;
  gap: 4px;
}

.weather-item__copy strong {
  color: #ffffff;
}

.weather-item__copy span,
.weather-item__meta span,
.weather-item__meta small {
  font-size: var(--text-sm);
  color: rgba(230, 238, 255, 0.68);
}

.weather-item__meta {
  justify-items: end;
}

.weather-item__meta small {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.weather-item--sunny .weather-item__icon {
  background: linear-gradient(135deg, #fbbf24, #f97316);
}

.weather-item--rain .weather-item__icon {
  background: linear-gradient(135deg, #38bdf8, #2563eb);
}

.weather-item--cloudy .weather-item__icon {
  background: linear-gradient(135deg, #94a3b8, #64748b);
}

.weather-item--mild .weather-item__icon {
  background: linear-gradient(135deg, #2dd4bf, #0f766e);
}

.weather-rail--compact .weather-item {
  grid-template-columns: auto minmax(0, 1fr);
}

.weather-rail--compact .weather-item__meta {
  grid-column: 2;
  justify-items: start;
}
</style>
