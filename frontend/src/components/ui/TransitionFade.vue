<script setup lang="ts">
/**
 * TransitionFade - 淡入淡出过渡组件
 */

interface Props {
  mode?: 'in-out' | 'out-in' | 'default'
  duration?: number
}

withDefaults(defineProps<Props>(), {
  mode: 'default',
  duration: 300,
})
</script>

<template>
  <Transition
    name="fade"
    :mode="mode"
  >
    <slot />
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 300ms var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
