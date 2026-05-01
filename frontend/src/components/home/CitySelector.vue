<script setup lang="ts">
/**
 * CitySelector - 热门城市快速选择
 * 
 * 带滚动动画的版本
 */

import { ref, onMounted } from 'vue'
import { MapPin } from 'lucide-vue-next'
import { Card } from '@/components/ui'

interface City {
  name: string
  subtitle: string
  image: string
  accent: 'blue' | 'orange' | 'green'
}

interface Props {
  cities?: City[]
}

withDefaults(defineProps<Props>(), {
  cities: () => [
    {
      name: '北京',
      subtitle: '历史文化之旅',
      image: 'https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=400&h=300&fit=crop',
      accent: 'orange',
    },
    {
      name: '成都',
      subtitle: '美食休闲之都',
      image: 'https://images.unsplash.com/photo-1565608087341-34a1f75ddbe7?w=400&h=300&fit=crop',
      accent: 'green',
    },
    {
      name: '杭州',
      subtitle: '西湖江南风情',
      image: 'https://images.unsplash.com/photo-1565378435245-2528d587e524?w=400&h=300&fit=crop',
      accent: 'blue',
    },
  ],
})

const emit = defineEmits<{
  select: [city: string]
}>()

const sectionRef = ref<HTMLElement | null>(null)
const isVisible = ref(false)

onMounted(() => {
  if (!sectionRef.value) return
  
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          isVisible.value = true
          observer.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.2 }
  )
  
  observer.observe(sectionRef.value)
})

function handleSelect(city: City) {
  emit('select', city.name)
}
</script>

<template>
  <section ref="sectionRef" class="city-selector">
    <div class="city-selector__header" :class="{ 'is-visible': isVisible }">
      <h2 class="city-selector__title">热门目的地</h2>
      <p class="city-selector__subtitle">
        选择一个城市，快速开始规划
      </p>
    </div>
    
    <div class="city-selector__grid">
      <Card
        v-for="(city, index) in cities"
        :key="city.name"
        class="city-card"
        :class="[`city-card--${city.accent}`, { 'is-visible': isVisible }]"
        hoverable
        clickable
        padding="none"
        :style="{ transitionDelay: `${index * 100 + 200}ms` }"
        @click="handleSelect(city)"
      >
        <div class="city-card__image-wrapper">
          <img 
            :src="city.image" 
            :alt="city.name"
            class="city-card__image"
            loading="lazy"
          />
          <div class="city-card__overlay" />
        </div>
        
        <div class="city-card__content">
          <div class="city-card__icon">
            <MapPin :size="16" />
          </div>
          <div class="city-card__info">
            <h3 class="city-card__name">{{ city.name }}</h3>
            <p class="city-card__subtitle">{{ city.subtitle }}</p>
          </div>
        </div>
      </Card>
    </div>
  </section>
</template>

<style scoped>
.city-selector {
  padding: var(--space-12) var(--space-8) var(--space-20);
  max-width: var(--max-width-xl);
  margin: 0 auto;
}

.city-selector__header {
  text-align: center;
  margin-bottom: var(--space-10);
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s var(--ease-out);
}

.city-selector__header.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.city-selector__title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  margin-bottom: var(--space-3);
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
}

.city-selector__subtitle {
  font-size: var(--text-lg);
  color: var(--color-text-tertiary);
  font-weight: var(--font-normal);
}

.city-selector__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-8);
}

/* City Card */
.city-card {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s var(--ease-out);
  overflow: hidden;
  cursor: pointer;
  border-radius: var(--radius-xl);
}

.city-card.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.city-card__image-wrapper {
  position: relative;
  height: 240px;
  overflow: hidden;
}

.city-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.8s var(--ease-out);
}

.city-card:hover .city-card__image {
  transform: scale(1.1);
}

.city-card__overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.15) 45%, transparent 100%);
  transition: opacity 0.3s;
}

.city-card:hover .city-card__overlay {
  opacity: 0.9;
}

.city-card__content {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--space-6);
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
}

.city-card__icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.3s var(--ease-spring);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.city-card:hover .city-card__icon {
  transform: scale(1.1);
  background: rgba(255, 255, 255, 0.35);
}

.city-card__name {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: white;
  margin-bottom: var(--space-1);
  transition: transform 0.3s var(--ease-out);
  letter-spacing: -0.01em;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.city-card:hover .city-card__name {
  transform: translateX(6px);
}

.city-card__subtitle {
  font-size: var(--text-base);
  color: rgba(255, 255, 255, 0.85);
  transition: transform 0.3s var(--ease-out);
  font-weight: var(--font-medium);
}

.city-card:hover .city-card__subtitle {
  transform: translateX(6px);
}

/* Accent colors for hover state */
.city-card--blue:hover {
  box-shadow: 0 20px 50px rgba(0, 122, 255, 0.3);
}

.city-card--orange:hover {
  box-shadow: 0 20px 50px rgba(255, 149, 0, 0.3);
}

.city-card--green:hover {
  box-shadow: 0 20px 50px rgba(52, 199, 89, 0.3);
}

/* Responsive */
@media (max-width: 1024px) {
  .city-selector__grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-6);
  }
}

@media (max-width: 640px) {
  .city-selector {
    padding: var(--space-8) var(--space-5) var(--space-12);
  }

  .city-selector__title {
    font-size: var(--text-2xl);
  }

  .city-selector__subtitle {
    font-size: var(--text-base);
  }

  .city-selector__grid {
    grid-template-columns: 1fr;
    gap: var(--space-5);
  }

  .city-card__image-wrapper {
    height: 200px;
  }

  .city-card__content {
    padding: var(--space-5);
  }

  .city-card__name {
    font-size: var(--text-xl);
  }
}
</style>
