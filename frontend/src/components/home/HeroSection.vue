<script setup lang="ts">
/**
 * HeroSection - 首页主视觉区域
 * 
 * 支持标准版和紧凑版两种布局
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { Sparkles } from 'lucide-vue-next'

interface Props {
  /** 后端连接状态 */
  backendReady?: boolean
  /** 紧凑模式（用于并排布局） */
  compact?: boolean
}

withDefaults(defineProps<Props>(), {
  backendReady: false,
  compact: false,
})

// Particle animation
interface Particle {
  x: number
  y: number
  size: number
  speedX: number
  speedY: number
  opacity: number
}

const particles = ref<Particle[]>([])
const particleCount = 20

function initParticles() {
  particles.value = Array.from({ length: particleCount }, () => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 2 + 1,
    speedX: (Math.random() - 0.5) * 0.3,
    speedY: (Math.random() - 0.5) * 0.3,
    opacity: Math.random() * 0.4 + 0.1,
  }))
}

let animationFrame: number

function animateParticles() {
  particles.value = particles.value.map((p) => {
    let newX = p.x + p.speedX
    let newY = p.y + p.speedY
    
    if (newX < 0) newX = 100
    if (newX > 100) newX = 0
    if (newY < 0) newY = 100
    if (newY > 100) newY = 0
    
    return { ...p, x: newX, y: newY }
  })
  
  animationFrame = requestAnimationFrame(animateParticles)
}

onMounted(() => {
  initParticles()
  animateParticles()
})

onUnmounted(() => {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame)
  }
})
</script>

<template>
  <section class="hero" :class="{ 'hero--compact': compact }">
    <!-- Background decoration -->
    <div class="hero__bg">
      <div class="hero__gradient hero__gradient--primary" />
      <div class="hero__gradient hero__gradient--secondary" />
      <div class="hero__grid" />
      <div class="hero__particles">
        <div
          v-for="(particle, index) in particles"
          :key="index"
          class="hero__particle"
          :style="{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            opacity: particle.opacity,
          }"
        />
      </div>
    </div>
    
    <!-- Content -->
    <div class="hero__content">
      <div class="hero__badge">
        <Sparkles :size="14" />
        <span>AI 驱动的旅行规划</span>
      </div>
      
      <h1 class="hero__title">
        <span class="hero__title-line">让 AI 为你规划</span>
        <span class="hero__title-line hero__title-line--highlight">完美旅程</span>
      </h1>
      
      <p class="hero__subtitle">
        输入目的地和时间，智能 Agent 自动为你定制专属行程
      </p>
      
      <!-- Stats -->
      <div class="hero__stats">
        <div class="hero__stat">
          <span class="hero__stat-value">10+</span>
          <span class="hero__stat-label">城市覆盖</span>
        </div>
        <div class="hero__stat-divider" />
        <div class="hero__stat">
          <span class="hero__stat-value">8</span>
          <span class="hero__stat-label">智能 Agent</span>
        </div>
        <div class="hero__stat-divider" />
        <div class="hero__stat">
          <span class="hero__stat-value">3s</span>
          <span class="hero__stat-label">快速规划</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  overflow: hidden;
}

/* Compact mode */
.hero--compact {
  min-height: auto;
  padding: 0;
}

.hero--compact .hero__title {
  font-size: clamp(2rem, 4vw, 3rem);
}

.hero--compact .hero__stats {
  margin-top: var(--space-6);
}

/* Background */
.hero__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
}

.hero__gradient {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}

.hero__gradient--primary {
  width: 500px;
  height: 500px;
  background: linear-gradient(135deg, #007AFF 0%, #5AC8FA 100%);
  top: -150px;
  right: -100px;
  animation: float 8s ease-in-out infinite;
}

.hero__gradient--secondary {
  width: 350px;
  height: 350px;
  background: linear-gradient(135deg, #FF9500 0%, #FFD60A 100%);
  bottom: -100px;
  left: -100px;
  animation: float 10s ease-in-out infinite reverse;
}

.hero__grid {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(0, 122, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 122, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
}

/* Particles */
.hero__particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.hero__particle {
  position: absolute;
  background: var(--color-primary);
  border-radius: 50%;
  pointer-events: none;
}

/* Content */
.hero__content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.hero__badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2_5);
  padding: var(--space-2_5) var(--space-5);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  margin-bottom: var(--space-7);
  letter-spacing: 0.02em;
}

.hero__title {
  font-size: clamp(2.5rem, 6vw, 4rem);
  font-weight: var(--font-bold);
  line-height: 1.15;
  letter-spacing: -0.03em;
  margin-bottom: var(--space-7);
}

.hero__title-line {
  display: block;
  color: var(--color-text-primary);
}

.hero__title-line--highlight {
  background: linear-gradient(135deg, var(--color-primary) 0%, #5AC8FA 50%, #34D399 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero__subtitle {
  font-size: clamp(1.125rem, 2vw, 1.25rem);
  color: var(--color-text-secondary);
  line-height: 1.6;
  max-width: 520px;
  margin: 0 auto var(--space-10);
  font-weight: var(--font-normal);
}

/* Stats */
.hero__stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-10);
  margin-top: var(--space-8);
  padding: var(--space-5) var(--space-8);
  background: var(--color-bg-primary);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-md);
}

.hero__stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1_5);
}

.hero__stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}

.hero__stat-label {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  font-weight: var(--font-medium);
}

.hero__stat-divider {
  width: 1px;
  height: 40px;
  background: var(--color-border-light);
}

/* Animations */
@keyframes float {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(-15px, 15px); }
}

/* Responsive */
@media (max-width: 640px) {
  .hero {
    padding: var(--space-6);
  }

  .hero__stats {
    gap: var(--space-6);
    padding: var(--space-4) var(--space-6);
  }

  .hero__stat-value {
    font-size: var(--text-xl);
  }

  .hero__stat-divider {
    height: 28px;
  }

  .hero__gradient {
    filter: blur(60px);
  }

  .hero__gradient--primary {
    width: 280px;
    height: 280px;
  }

  .hero__gradient--secondary {
    width: 180px;
    height: 180px;
  }
}
</style>
