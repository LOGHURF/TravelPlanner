<script setup lang="ts">
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

const iconSizeMap = {
  sm: 14,
  md: 16,
  lg: 18,
}

interface Props {
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  block?: boolean
  type?: 'button' | 'submit' | 'reset'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  block: false,
  type: 'button',
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const isDisabled = computed(() => props.disabled || props.loading)
const iconSize = computed(() => iconSizeMap[props.size])

const sizeClass = computed(() => {
  return {
    sm: 'h-10 px-4 text-sm',
    md: 'h-11 px-5 text-sm',
    lg: 'h-12 px-6 text-base',
  }[props.size]
})

const variantClass = computed(() => {
  switch (props.variant) {
    case 'secondary':
      return 'border border-slate-200 bg-white text-slate-800 shadow-sm hover:border-sky-300 hover:text-slate-950'
    case 'ghost':
      return 'border border-transparent bg-white text-slate-700 shadow-sm hover:border-slate-200 hover:text-slate-950'
    case 'danger':
      return 'bg-gradient-to-r from-rose-500 to-orange-400 text-white shadow-lg shadow-rose-400/30 hover:brightness-110'
    default:
      return 'bg-gradient-to-r from-sky-500 to-emerald-400 text-white shadow-lg shadow-sky-500/30 hover:brightness-110'
  }
})

function handleClick(event: MouseEvent) {
  if (isDisabled.value) {
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    :type="type"
    :disabled="isDisabled"
    class="inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all duration-300 ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white/70 disabled:cursor-not-allowed disabled:opacity-55"
    :class="[
      sizeClass,
      variantClass,
      block && 'w-full',
      !isDisabled && 'will-change-transform hover:scale-[1.02] active:scale-[0.98]',
    ]"
    @click="handleClick"
  >
    <Loader2
      v-if="loading"
      class="animate-spin"
      :size="iconSize"
    />
    <span class="inline-flex min-w-0 items-center justify-center gap-2">
      <slot />
    </span>
  </button>
</template>
