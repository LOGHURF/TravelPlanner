<script setup lang="ts">
/**
 * CircularProgress - 圆形进度条
 * 
 * 大圆形进度展示，用于规划页主进度
 */

import { computed } from 'vue'

interface Props {
  /** 进度值 (0-100) */
  modelValue?: number
  /** 尺寸 */
  size?: number
  /** 线宽 */
  strokeWidth?: number
  /** 显示的文字 */
  label?: string
  /** 子文字 */
  sublabel?: string
  /** 是否动画 */
  animated?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  size: 280,
  strokeWidth: 12,
  label: '',
  sublabel: '',
  animated: true,
})

const normalizedValue = computed(() => {
  return Math.min(100, Math.max(0, props.modelValue))
})

const radius = computed(() => (props.size - props.strokeWidth) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const strokeDashoffset = computed(() => {
  return circumference.value - (normalizedValue.value / 100) * circumference.value
})

const viewBox = computed(() => `0 0 ${props.size} ${props.size}`)

const gradientId = computed(() => `progress-gradient-${Math.random().toString(36).substr(2, 9)}`)
</script>

<template>
  <div class="circular-progress" :style="{ width: `${size}px`, height: `${size}px` }">
    <!-- Gradient Definition -->
    <svg width="0" height="0" class="circular-progress__defs">
      <defs>
        <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#007AFF" />
          <stop offset="100%" stop-color="#5AC8FA" />
        </linearGradient>
      </defs>
    </svg>
    
    <!-- Progress Circle -->
    <svg
      class="circular-progress__svg"
      :viewBox="viewBox"
    >
      <!-- Background Track -->
      <circle
        class="circular-progress__track"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        fill="none"
      />
      
      <!-- Progress Arc -->
      <circle
        class="circular-progress__progress"
        :class="{ 'circular-progress__progress--animated': animated }"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        :stroke="`url(#${gradientId})`"
        fill="none"
        :stroke-dasharray="`${circumference} ${circumference}`"
        :stroke-dashoffset="strokeDashoffset"
        :stroke-linecap="'round'"
        :transform="`rotate(-90 ${size / 2} ${size / 2})`"
      />
    </svg>
    
    <!-- Center Content -->
    <div class="circular-progress__content">
      <span class="circular-progress__value">{{ normalizedValue }}</span>
      <span class="circular-progress__unit">%</span>
    </div>
    
    <!-- Labels -->
    <div v-if="label || sublabel" class="circular-progress__labels">
      <p v-if="label" class="circular-progress__label">{{ label }}</p>
      <p v-if="sublabel" class="circular-progress__sublabel">{{ sublabel }}</p>
    </div>
  </div>
</template>

<style scoped>
.circular-progress {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.circular-progress__defs {
  position: absolute;
}

.circular-progress__svg {
  transform: rotate(-90deg);
  width: 100%;
  height: 100%;
}

.circular-progress__track {
  stroke: var(--color-bg-tertiary);
}

.circular-progress__progress {
  transition: stroke-dashoffset var(--duration-slow) var(--ease-out);
}

.circular-progress__content {
  position: absolute;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.circular-progress__value {
  font-size: 4rem;
  font-weight: var(--font-bold);
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.circular-progress__unit {
  font-size: 1.5rem;
  font-weight: var(--font-semibold);
  color: var(--color-text-secondary);
}

.circular-progress__labels {
  position: absolute;
  bottom: 60px;
  text-align: center;
}

.circular-progress__label {
  font-size: var(--text-lg);
  font-weight: var(--font-medium);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.circular-progress__sublabel {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

/* Pulse animation for running state */
@keyframes pulse-ring {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 122, 255, 0.4);
  }
  70% {
    box-shadow: 0 0 0 20px rgba(0, 122, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(0, 122, 255, 0);
  }
}

.circular-progress--running .circular-progress__svg {
  animation: pulse-ring 2s ease-out infinite;
  border-radius: 50%;
}
</style>
