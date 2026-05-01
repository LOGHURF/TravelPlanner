<script setup lang="ts">
/**
 * TransitionSlide - 滑动过渡组件
 */

interface Props {
  direction?: 'up' | 'down' | 'left' | 'right'
  distance?: string
  mode?: 'in-out' | 'out-in' | 'default'
}

const props = withDefaults(defineProps<Props>(), {
  direction: 'up',
  distance: '30px',
  mode: 'default',
})

const transformMap = {
  up: `translateY(${props.distance})`,
  down: `translateY(-${props.distance})`,
  left: `translateX(${props.distance})`,
  right: `translateX(-${props.distance})`,
}
</script>

<template>
  <Transition
    name="slide"
    :mode="mode"
  >
    <slot />
  </Transition>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 350ms var(--ease-spring);
}

.slide-enter-from {
  opacity: 0;
  transform: v-bind('transformMap[props.direction]');
}

.slide-leave-to {
  opacity: 0;
  transform: v-bind('transformMap[props.direction]');
}
</style>
