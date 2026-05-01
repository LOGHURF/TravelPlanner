<script setup lang="ts">
import { computed, ref, useId } from 'vue'

type InputType = 'text' | 'password' | 'email' | 'number' | 'tel' | 'url' | 'search'
type InputSize = 'sm' | 'md' | 'lg'

interface Props {
  type?: InputType
  label?: string
  placeholder?: string
  error?: string
  disabled?: boolean
  required?: boolean
  size?: InputSize
  maxLength?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  label: '',
  placeholder: '',
  error: '',
  disabled: false,
  required: false,
  size: 'md',
  maxLength: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  focus: [event: FocusEvent]
  blur: [event: FocusEvent]
  input: [event: Event]
}>()

const modelValue = defineModel<string>({ default: '' })
const isFocused = ref(false)
const inputId = useId()
const errorId = `${inputId}-error`
const hintId = `${inputId}-hint`

const wrapperClass = computed(() => {
  const sizeMap = {
    sm: 'h-10 px-3 text-sm',
    md: 'h-11 px-3.5 text-sm',
    lg: 'h-12 px-4 text-base',
  } satisfies Record<InputSize, string>

  return [
    'flex min-w-0 items-center gap-2 rounded-lg border bg-white transition-colors duration-200 ease-standard',
    sizeMap[props.size],
    props.disabled
      ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
      : 'border-slate-200 shadow-sm',
    props.error
      ? 'border-rose-300 focus-within:border-rose-400 focus-within:ring-2 focus-within:ring-rose-100'
      : 'focus-within:border-sky-400 focus-within:ring-2 focus-within:ring-sky-100',
    isFocused.value && !props.error ? 'border-sky-400' : '',
  ]
})

function handleFocus(event: FocusEvent) {
  isFocused.value = true
  emit('focus', event)
}

function handleBlur(event: FocusEvent) {
  isFocused.value = false
  emit('blur', event)
}

function handleInput(event: Event) {
  emit('input', event)
}
</script>

<template>
  <div class="grid w-full gap-2">
    <label
      v-if="props.label"
      :for="inputId"
      class="inline-flex items-center gap-1 text-sm font-medium text-slate-700"
    >
      <span>{{ props.label }}</span>
      <span v-if="props.required" class="text-rose-500">*</span>
    </label>

    <div :class="wrapperClass">
      <slot name="prefix" />

      <input
        :id="inputId"
        v-model="modelValue"
        :type="props.type"
        :placeholder="props.placeholder"
        :disabled="props.disabled"
        :maxlength="props.maxLength"
        :aria-invalid="Boolean(props.error)"
        :aria-describedby="props.error ? errorId : ($slots.hint ? hintId : undefined)"
        class="block h-full min-w-0 flex-1 appearance-none border-0 bg-transparent p-0 text-slate-950 [outline:none] ring-0 placeholder:text-slate-400 focus:border-0 focus:[outline:none] focus:ring-0 disabled:cursor-not-allowed"
        @focus="handleFocus"
        @blur="handleBlur"
        @input="handleInput"
      >

      <slot name="suffix" />
    </div>

    <p
      v-if="props.error"
      :id="errorId"
      class="text-sm leading-relaxed text-rose-600"
    >
      {{ props.error }}
    </p>

    <p
      v-else-if="$slots.hint"
      :id="hintId"
      class="text-sm leading-relaxed text-slate-500"
    >
      <slot name="hint" />
    </p>
  </div>
</template>
