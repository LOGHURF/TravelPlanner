<script setup lang="ts">
import { computed } from 'vue'

type CardVariant = 'default' | 'outlined' | 'elevated'

interface Props {
  variant?: CardVariant
  hoverable?: boolean
  clickable?: boolean
  disabled?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  hoverable: false,
  clickable: false,
  disabled: false,
  padding: 'md',
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const tagName = computed(() => (props.clickable && !props.disabled ? 'button' : 'div'))

const surfaceClass = computed(() => {
  const paddingMap = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  } as const

  const variantMap = {
    default: 'glass-surface border border-white/35 bg-white/72 shadow-glass',
    outlined: 'border border-slate-200/80 bg-white/58 shadow-sm',
    elevated: 'glass-surface border border-white/45 bg-white/80 shadow-glass-hover',
  } as const

  return [
    'relative overflow-hidden rounded-panel text-slate-900 transition-all duration-300 ease-standard',
    paddingMap[props.padding],
    variantMap[props.variant],
    props.clickable && !props.disabled ? 'cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white/70' : '',
    props.hoverable || props.clickable ? 'will-change-transform hover:-translate-y-0.5 hover:shadow-glass-hover' : '',
    props.disabled ? 'cursor-not-allowed opacity-60' : '',
  ]
})

function handleClick(event: MouseEvent) {
  if (!props.clickable || props.disabled) {
    return
  }
  emit('click', event)
}
</script>

<template>
  <component
    :is="tagName"
    :type="tagName === 'button' ? 'button' : undefined"
    :disabled="tagName === 'button' ? props.disabled : undefined"
    :class="surfaceClass"
    @click="handleClick"
  >
    <div
      v-if="$slots.header"
      class="relative z-10 border-b border-white/35 pb-4"
      :class="props.padding === 'none' ? 'px-6 pt-6' : ''"
    >
      <slot name="header" />
    </div>

    <div
      class="relative z-10"
      :class="[
        $slots.header && props.padding !== 'none' ? 'pt-0' : '',
        $slots.footer && props.padding === 'none' ? 'px-6 py-5' : '',
      ]"
    >
      <slot />
    </div>

    <div
      v-if="$slots.footer"
      class="relative z-10 mt-4 border-t border-white/35 pt-4"
      :class="props.padding === 'none' ? 'px-6 pb-6' : ''"
    >
      <slot name="footer" />
    </div>
  </component>
</template>
