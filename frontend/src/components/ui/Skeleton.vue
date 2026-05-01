<script setup lang="ts">
/**
 * Skeleton - 骨架屏组件
 * 
 * 用于加载状态的占位展示
 * 
 * @example
 * <Skeleton width="200px" height="20px" />
 * <Skeleton circle :size="40" />
 * <Skeleton text :lines="3" />
 */

import { computed } from 'vue'

interface Props {
  /** 宽度 */
  width?: string
  /** 高度 */
  height?: string
  /** 尺寸（圆形时使用） */
  size?: string | number
  /** 是否为圆形 */
  circle?: boolean
  /** 是否为文本模式 */
  text?: boolean
  /** 文本行数 */
  lines?: number
  /** 是否动画 */
  animated?: boolean
  /** 圆角 */
  radius?: string
}

const props = withDefaults(defineProps<Props>(), {
  width: '100%',
  height: '20px',
  size: '',
  circle: false,
  text: false,
  lines: 1,
  animated: true,
  radius: '',
})

const classes = computed(() => [
  'skeleton',
  {
    'skeleton--animated': props.animated,
    'skeleton--circle': props.circle,
  },
])

const style = computed(() => {
  if (props.circle) {
    const s = props.size || props.height
    return {
      width: typeof s === 'number' ? `${s}px` : s,
      height: typeof s === 'number' ? `${s}px` : s,
      borderRadius: '50%',
    }
  }
  
  return {
    width: props.width,
    height: props.height,
    borderRadius: props.radius || 'var(--radius-md)',
  }
})
</script>

<template>
  <!-- Text Mode with multiple lines -->
  <div v-if="text" class="skeleton-text">
    <div
      v-for="i in lines"
      :key="i"
      :class="classes"
      :style="{
        width: i === lines && lines > 1 ? '80%' : '100%',
        height: '1em',
        marginBottom: i < lines ? '0.5em' : 0,
        borderRadius: '4px',
      }"
    />
  </div>
  
  <!-- Single skeleton -->
  <div
    v-else
    :class="classes"
    :style="style"
  />
</template>

<style scoped>
.skeleton {
  background: var(--color-bg-tertiary);
  position: relative;
  overflow: hidden;
}

.skeleton--animated::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.4),
    transparent
  );
  transform: translateX(-100%);
  animation: skeleton-loading 1.5s infinite;
}

@keyframes skeleton-loading {
  100% {
    transform: translateX(100%);
  }
}

.skeleton-text {
  display: flex;
  flex-direction: column;
}
</style>
