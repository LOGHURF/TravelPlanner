<script setup lang="ts">
/**
 * ScrollReveal - 滚动显示动画组件
 * 
 * 当元素进入视口时触发动画
 */

import { ref, onMounted } from 'vue'

interface Props {
  /** 动画延迟（毫秒） */
  delay?: number
  /** 动画持续时间（毫秒） */
  duration?: number
  /** 移动距离 */
  distance?: string
  /** 动画方向 */
  direction?: 'up' | 'down' | 'left' | 'right'
  /** 阈值（0-1） */
  threshold?: number
  /** 只触发一次 */
  once?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  delay: 0,
  duration: 600,
  distance: '30px',
  direction: 'up',
  threshold: 0.1,
  once: true,
})

const elementRef = ref<HTMLElement | null>(null)
const isVisible = ref(false)
const hasAnimated = ref(false)

const transformMap = {
  up: `translateY(${props.distance})`,
  down: `translateY(-${props.distance})`,
  left: `translateX(${props.distance})`,
  right: `translateX(-${props.distance})`,
}

onMounted(() => {
  if (!elementRef.value) return
  
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            isVisible.value = true
            hasAnimated.value = true
          }, props.delay)
          
          if (props.once) {
            observer.unobserve(entry.target)
          }
        } else if (!props.once) {
          isVisible.value = false
        }
      })
    },
    { threshold: props.threshold }
  )
  
  observer.observe(elementRef.value)
})
</script>

<template>
  <div
    ref="elementRef"
    class="scroll-reveal"
    :class="{ 'is-visible': isVisible }"
  >
    <slot />
  </div>
</template>

<style scoped>
.scroll-reveal {
  opacity: 0;
  transform: v-bind('transformMap[props.direction]');
  transition: v-bind('`all ${props.duration}ms var(--ease-out)`');
}

.scroll-reveal.is-visible {
  opacity: 1;
  transform: translate(0);
}
</style>
