<script setup lang="ts">
/**
 * FeatureCards - 产品特色展示
 * 
 * 带滚动动画的版本
 */

import { ref, onMounted } from 'vue'
import { Brain, Map, Sparkles } from 'lucide-vue-next'
import { Card } from '@/components/ui'

const features = [
  {
    icon: Brain,
    title: '智能推荐',
    description: '基于你的偏好和同行人员，AI Agent 为你精准推荐最合适的景点、餐厅和住宿',
    gradient: 'var(--gradient-sky)',
    iconColor: '#007AFF',
  },
  {
    icon: Map,
    title: '实时规划',
    description: '8 个智能 Agent 并行工作，实时协调预算、路线和偏好，生成最优行程',
    gradient: 'var(--gradient-sunset)',
    iconColor: '#FF9500',
  },
  {
    icon: Sparkles,
    title: '个性定制',
    description: '从文化体验到自然风光，从紧凑到宽松，完全按照你的节奏定制旅程',
    gradient: 'var(--gradient-spring)',
    iconColor: '#34C759',
  },
]

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
</script>

<template>
  <section ref="sectionRef" class="features">
    <div class="features__header" :class="{ 'is-visible': isVisible }">
      <h2 class="features__title">为什么选择我们</h2>
      <p class="features__subtitle">
        让 AI 处理繁琐的规划工作，你只需享受旅程
      </p>
    </div>
    
    <div class="features__grid">
      <Card
        v-for="(feature, index) in features"
        :key="feature.title"
        class="feature-card"
        :class="{ 'is-visible': isVisible }"
        hoverable
        padding="lg"
        :style="{ transitionDelay: `${index * 100 + 200}ms` }"
      >
        <div class="feature-card__icon-wrapper" :style="{ background: feature.gradient }">
          <component 
            :is="feature.icon" 
            :size="28" 
            :color="feature.iconColor"
            :stroke-width="1.5"
          />
        </div>
        
        <h3 class="feature-card__title">{{ feature.title }}</h3>
        <p class="feature-card__description">{{ feature.description }}</p>
      </Card>
    </div>
  </section>
</template>

<style scoped>
.features {
  padding: var(--space-20) var(--space-8);
  max-width: var(--max-width-xl);
  margin: 0 auto;
}

.features__header {
  text-align: center;
  margin-bottom: var(--space-14);
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s var(--ease-out);
}

.features__header.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.features__title {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  margin-bottom: var(--space-4);
  letter-spacing: -0.02em;
}

.features__subtitle {
  font-size: var(--text-xl);
  color: var(--color-text-tertiary);
  font-weight: var(--font-normal);
}

.features__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-8);
}

/* Feature Card */
.feature-card {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.6s var(--ease-out);
}

.feature-card.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.feature-card :deep(.card__body) {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.feature-card__icon-wrapper {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-6);
  transition: transform 0.3s var(--ease-spring);
  box-shadow: var(--shadow-md);
}

.feature-card:hover .feature-card__icon-wrapper {
  transform: scale(1.1) rotate(-5deg);
}

.feature-card__title {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  margin-bottom: var(--space-3);
  letter-spacing: -0.01em;
}

.feature-card__description {
  font-size: var(--text-base);
  color: var(--color-text-secondary);
  line-height: 1.7;
}

/* Responsive */
@media (max-width: 1024px) {
  .features__grid {
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-6);
  }
}

@media (max-width: 768px) {
  .features__grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-5);
  }
}

@media (max-width: 640px) {
  .features {
    padding: var(--space-12) var(--space-5);
  }

  .features__title {
    font-size: var(--text-2xl);
  }

  .features__subtitle {
    font-size: var(--text-base);
  }

  .features__grid {
    grid-template-columns: 1fr;
    gap: var(--space-4);
  }
}
</style>
