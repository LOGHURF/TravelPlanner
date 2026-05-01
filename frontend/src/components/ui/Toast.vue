<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { AlertCircle, CheckCircle2, Info, X, XCircle } from 'lucide-vue-next'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Props {
  type?: ToastType
  message?: string
  visible?: boolean
  duration?: number
  closable?: boolean
  position?: 'top' | 'bottom' | 'top-right' | 'bottom-right'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  message: '',
  visible: false,
  duration: 3000,
  closable: true,
  position: 'top',
})

const emit = defineEmits<{
  close: []
  'update:visible': [value: boolean]
}>()

const isVisible = ref(props.visible)
let closeTimer: ReturnType<typeof setTimeout> | null = null

const iconMap = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
}

const toneClass = computed(() => {
  return {
    success: 'text-emerald-600',
    error: 'text-rose-600',
    warning: 'text-amber-600',
    info: 'text-sky-600',
  }[props.type]
})

const positionClass = computed(() => {
  return {
    top: 'top-6 left-1/2 -translate-x-1/2',
    bottom: 'bottom-6 left-1/2 -translate-x-1/2',
    'top-right': 'right-6 top-6',
    'bottom-right': 'bottom-6 right-6',
  }[props.position]
})

function clearCloseTimer() {
  if (!closeTimer) {
    return
  }
  clearTimeout(closeTimer)
  closeTimer = null
}

function close() {
  clearCloseTimer()
  isVisible.value = false
  emit('update:visible', false)
  emit('close')
}

function startCloseTimer() {
  clearCloseTimer()
  if (props.duration > 0) {
    closeTimer = setTimeout(() => close(), props.duration)
  }
}

watch(
  () => props.visible,
  (value) => {
    isVisible.value = value
    if (value) {
      startCloseTimer()
    } else {
      clearCloseTimer()
    }
  },
)

onMounted(() => {
  if (isVisible.value) {
    startCloseTimer()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="toast-float">
      <section
        v-if="isVisible"
        class="fixed z-[1200] max-w-sm px-4"
        :class="positionClass"
        @mouseenter="clearCloseTimer"
        @mouseleave="startCloseTimer"
      >
        <div class="glass-surface flex items-start gap-3 rounded-panel border border-white/40 px-4 py-3 shadow-glass">
          <component :is="iconMap[props.type]" class="mt-0.5 h-5 w-5 shrink-0" :class="toneClass" />
          <div class="min-w-0 flex-1">
            <slot>
              <p class="text-sm leading-relaxed text-slate-700">
                {{ props.message }}
              </p>
            </slot>
          </div>
          <button
            v-if="props.closable"
            type="button"
            class="rounded-full p-1 text-slate-400 transition-colors duration-200 hover:bg-white/70 hover:text-slate-700"
            aria-label="关闭提示"
            @click="close"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.toast-float-enter-active,
.toast-float-leave-active {
  transition: all 0.3s var(--ease-standard);
}

.toast-float-enter-from,
.toast-float-leave-to {
  opacity: 0;
  transform: translate3d(0, -12px, 0);
}
</style>
