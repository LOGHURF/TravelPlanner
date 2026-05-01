<script setup lang="ts">
/**
 * AnimatedNumber - 数字动画组件
 * 
 * 数字递增动画效果
 */

import { ref, watch, onMounted, computed } from 'vue'

interface Props {
  /** 目标值 */
  value: number
  /** 动画持续时间（毫秒） */
  duration?: number
  /** 延迟时间（毫秒） */
  delay?: number
  /** 是否自动开始 */
  autoStart?: boolean
  /** 小数位数 */
  decimals?: number
  /** 前缀 */
  prefix?: string
  /** 后缀 */
  suffix?: string
}

const props = withDefaults(defineProps<Props>(), {
  duration: 1000,
  delay: 0,
  autoStart: true,
  decimals: 0,
  prefix: '',
  suffix: '',
})

const displayValue = ref(0)
const isAnimating = ref(false)

let startTime: number | null = null
let rafId: number | null = null

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function animate(currentTime: number) {
  if (!startTime) startTime = currentTime
  const elapsed = currentTime - startTime - props.delay
  
  if (elapsed < 0) {
    rafId = requestAnimationFrame(animate)
    return
  }
  
  const progress = Math.min(elapsed / props.duration, 1)
  const easeProgress = easeOutCubic(progress)
  
  displayValue.value = props.value * easeProgress
  
  if (progress < 1) {
    rafId = requestAnimationFrame(animate)
  } else {
    displayValue.value = props.value
    isAnimating.value = false
  }
}

function start() {
  if (isAnimating.value) return
  isAnimating.value = true
  displayValue.value = 0
  startTime = null
  rafId = requestAnimationFrame(animate)
}

function stop() {
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  isAnimating.value = false
}

// Watch for value changes
watch(() => props.value, () => {
  if (props.autoStart) {
    stop()
    start()
  }
})

onMounted(() => {
  if (props.autoStart) {
    start()
  }
})

// Format the display value
const formattedValue = computed(() => {
  const num = displayValue.value.toFixed(props.decimals)
  return `${props.prefix}${num}${props.suffix}`
})
</script>

<template>
  <span class="animated-number">{{ formattedValue }}</span>
</template>

<style scoped>
.animated-number {
  font-variant-numeric: tabular-nums;
}
</style>
