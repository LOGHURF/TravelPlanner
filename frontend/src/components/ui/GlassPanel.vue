<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    hoverable?: boolean
    padding?: 'sm' | 'md' | 'lg'
    glow?: boolean
  }>(),
  {
    hoverable: false,
    padding: 'md',
    glow: false,
  },
)

const hovered = ref(false)

const paddingClass = computed(() => {
  return {
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }[props.padding]
})
</script>

<template>
  <section
    class="glass-surface relative isolate overflow-hidden rounded-panel border border-white/30 text-slate-900 shadow-glass transition-[transform,box-shadow,background-color] duration-300 ease-standard will-change-transform [transform:translateZ(0)]"
    :class="[
      paddingClass,
      props.glow && 'shadow-glow-sky',
      props.hoverable && 'cursor-pointer',
      props.hoverable && hovered && 'scale-[1.02] shadow-glass-hover',
    ]"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
  >
    <div
      class="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.26),rgba(255,255,255,0.06)_36%,rgba(255,255,255,0.12))]"
    />
    <div
      class="pointer-events-none absolute inset-x-4 bottom-0 h-0.5 origin-center rounded-full bg-sky-500 transition-all duration-300 ease-spring"
      :class="props.hoverable && hovered ? 'scale-x-100 opacity-100' : 'scale-x-0 opacity-0'"
    />
    <div class="relative z-10">
      <slot />
    </div>
  </section>
</template>
