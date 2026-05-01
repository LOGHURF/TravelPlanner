<script setup lang="ts">
/**
 * Progress - 进度条组件
 * 
 * 支持线性进度条和圆形进度条
 * 
 * @example
 * <Progress v-model="percent" />
 * <Progress variant="circular" :size="120" v-model="percent" />
 * <Progress :indeterminate="true" />
 */

import { computed } from 'vue'

type ProgressVariant = 'linear' | 'circular'

interface Props {
  /** 进度值 (0-100) */
  modelValue?: number
  /** 变体类型 */
  variant?: ProgressVariant
  /** 尺寸（圆形时有效） */
  size?: number
  /** 线宽（圆形时有效） */
  strokeWidth?: number
  /** 是否不确定状态 */
  indeterminate?: boolean
  /** 显示百分比文字 */
  showLabel?: boolean
  /** 颜色 */
  color?: string
  /** 轨道颜色 */
  trackColor?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  variant: 'linear',
  size: 120,
  strokeWidth: 8,
  indeterminate: false,
  showLabel: true,
  color: 'var(--color-primary)',
  trackColor: 'var(--color-bg-tertiary)',
})

const normalizedValue = computed(() => {
  const val = Math.min(100, Math.max(0, props.modelValue))
  return Math.round(val)
})

// Circular progress calculations
const radius = computed(() => (props.size - props.strokeWidth) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const strokeDashoffset = computed(() => {
  return circumference.value - (normalizedValue.value / 100) * circumference.value
})

const viewBox = computed(() => `0 0 ${props.size} ${props.size}`)
</script>

<template>
  <!-- Linear Progress -->
  <div
    v-if="variant === 'linear'"
    class="progress-linear"
    :class="{ 'progress-linear--indeterminate': indeterminate }"
  >
    <div class="progress-linear__track">
      <div
        class="progress-linear__fill"
        :style="{
          width: indeterminate ? undefined : `${normalizedValue}%`,
          backgroundColor: color,
        }"
      />
    </div>
    <span v-if="showLabel && !indeterminate" class="progress-linear__label">
      {{ normalizedValue }}%
    </span>
  </div>
  
  <!-- Circular Progress -->
  <div
    v-else
    class="progress-circular"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <svg
      class="progress-circular__svg"
      :viewBox="viewBox"
    >
      <!-- Track -->
      <circle
        class="progress-circular__track"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        :stroke="trackColor"
        fill="none"
      />
      <!-- Progress -->
      <circle
        class="progress-circular__progress"
        :class="{ 'progress-circular__progress--indeterminate': indeterminate }"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        :stroke="color"
        fill="none"
        :stroke-dasharray="indeterminate ? undefined : `${circumference} ${circumference}`"
        :stroke-dashoffset="indeterminate ? undefined : strokeDashoffset"
        :stroke-linecap="'round'"
        :transform="`rotate(-90 ${size / 2} ${size / 2})`"
      />
    </svg>
    <div v-if="showLabel && !indeterminate" class="progress-circular__label">
      <span class="progress-circular__value">{{ normalizedValue }}</span>
      <span class="progress-circular__unit">%</span>
    </div>
  </div>
</template>

<style scoped>
/* Linear Progress */
.progress-linear {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}

.progress-linear__track {
  flex: 1;
  height: 8px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-linear__fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

.progress-linear__label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text-secondary);
  min-width: 40px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* Indeterminate Animation */
.progress-linear--indeterminate .progress-linear__fill {
  width: 40%;
  animation: progress-linear-indeterminate 1.5s ease-in-out infinite;
}

@keyframes progress-linear-indeterminate {
  0% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(50%);
  }
  100% {
    transform: translateX(200%);
  }
}

/* Circular Progress */
.progress-circular {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.progress-circular__svg {
  transform: rotate(-90deg);
}

.progress-circular__track {
  transition: stroke var(--duration-fast);
}

.progress-circular__progress {
  transition: stroke-dashoffset var(--duration-slow) var(--ease-out);
}

.progress-circular__label {
  position: absolute;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.progress-circular__value {
  font-size: 1.5rem;
  font-weight: var(--font-bold);
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

.progress-circular__unit {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

/* Circular Indeterminate Animation */
.progress-circular__progress--indeterminate {
  animation: progress-circular-indeterminate 1.5s ease-in-out infinite;
  stroke-dasharray: 60% 200%;
}

@keyframes progress-circular-indeterminate {
  0% {
    transform: rotate(0deg);
    stroke-dasharray: 1% 200%;
  }
  50% {
    stroke-dasharray: 60% 200%;
  }
  100% {
    transform: rotate(360deg);
    stroke-dasharray: 1% 200%;
  }
}
</style>
