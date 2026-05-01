<script setup lang="ts">
import { computed } from 'vue'

interface PillOption {
  label: string
  value: string | number
  disabled?: boolean
}

interface Props {
  options?: PillOption[]
  modelValue?: string | number | (string | number)[]
  multiple?: boolean
  clearable?: boolean
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  options: () => [],
  modelValue: undefined,
  multiple: false,
  clearable: false,
  size: 'md',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number | (string | number)[]]
  change: [value: string | number | (string | number)[]]
  click: []
}>()

const groupClass = computed(() => {
  return {
    sm: 'gap-2',
    md: 'gap-2.5',
    lg: 'gap-3',
  }[props.size]
})

function isSelected(value: string | number) {
  if (props.multiple) {
    return Array.isArray(props.modelValue) && props.modelValue.includes(value)
  }
  return props.modelValue === value
}

function pillClass(selected: boolean, disabled = false) {
  const sizeClass = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  }[props.size]

  return [
    'inline-flex items-center justify-center rounded-lg border font-medium transition-colors duration-200 ease-standard',
    sizeClass,
    disabled || props.disabled
      ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400 opacity-55'
      : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300 hover:text-slate-900',
    selected
      ? 'border-sky-600 bg-sky-600 text-white shadow-sm shadow-sky-500/20 hover:border-sky-600 hover:text-white'
      : '',
  ]
}

function handleSelect(option: PillOption) {
  if (option.disabled || props.disabled) {
    return
  }

  if (props.multiple) {
    const current = Array.isArray(props.modelValue) ? [...props.modelValue] : []
    const index = current.indexOf(option.value)

    if (index > -1) {
      current.splice(index, 1)
    } else {
      current.push(option.value)
    }

    emit('update:modelValue', current)
    emit('change', current)
    return
  }

  if (props.clearable && props.modelValue === option.value) {
    emit('update:modelValue', '')
    emit('change', '')
    return
  }

  emit('update:modelValue', option.value)
  emit('change', option.value)
}
</script>

<template>
  <div
    v-if="props.options.length > 0"
    class="flex flex-wrap"
    :class="groupClass"
    role="group"
  >
    <button
      v-for="option in props.options"
      :key="option.value"
      type="button"
      :aria-pressed="isSelected(option.value)"
      :disabled="option.disabled || props.disabled"
      :class="pillClass(isSelected(option.value), option.disabled)"
      @click="handleSelect(option)"
    >
      {{ option.label }}
    </button>
  </div>

  <button
    v-else
    type="button"
    :disabled="props.disabled"
    :class="pillClass(false)"
    @click="$emit('click')"
  >
    <slot />
  </button>
</template>
