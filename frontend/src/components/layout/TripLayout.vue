<script setup lang="ts">
import { computed, provide, ref, type ComputedRef } from 'vue'
import { useWindowSize } from '@vueuse/core'

const props = withDefaults(
  defineProps<{
    themeColor?: string
    initialPanelWidth?: number
    minPanelWidth?: number
    maxPanelWidth?: number
    sheetTitle?: string
    sheetPreview?: string
  }>(),
  {
    themeColor: '#0EA5E9',
    initialPanelWidth: 380,
    minPanelWidth: 340,
    maxPanelWidth: 440,
    sheetTitle: 'Trip Details',
    sheetPreview: '上滑查看详情',
  },
)

const emit = defineEmits<{
  (e: 'sheet-close'): void
}>()

const { width, height } = useWindowSize()
const isMobile = computed(() => width.value < 768)

const providedTheme: ComputedRef<string> = computed(() => props.themeColor)
provide('themeColor', providedTheme)

const panelWidth = ref(props.initialPanelWidth)

function clampWidth(next: number) {
  return Math.min(props.maxPanelWidth, Math.max(props.minPanelWidth, next))
}

function startResize(event: PointerEvent) {
  const startX = event.clientX
  const startWidth = panelWidth.value
  document.body.style.userSelect = 'none'

  const onMove = (moveEvent: PointerEvent) => {
    panelWidth.value = clampWidth(startWidth + moveEvent.clientX - startX)
  }

  const onUp = () => {
    document.body.style.userSelect = ''
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }

  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const snapPoints = [0.2, 0.6, 0.9] as const
const activeSnap = ref(1)
const dragOffset = ref(0)
const touchStartY = ref<number | null>(null)

const sheetHeight = computed(() => Math.round(height.value * snapPoints[activeSnap.value]))
const sheetStyle = computed(() => ({
  height: `${sheetHeight.value}px`,
  transform: `translateY(${dragOffset.value}px)`,
}))

function onSheetTouchStart(event: TouchEvent) {
  touchStartY.value = event.touches[0]?.clientY ?? null
}

function onSheetTouchMove(event: TouchEvent) {
  if (touchStartY.value === null) {
    return
  }
  const delta = event.touches[0].clientY - touchStartY.value
  dragOffset.value = Math.max(-180, delta)
}

function onSheetTouchEnd() {
  const delta = dragOffset.value

  if (delta > 72) {
    if (activeSnap.value === 0) {
      emit('sheet-close')
    } else {
      activeSnap.value -= 1
    }
  } else if (delta < -72 && activeSnap.value < snapPoints.length - 1) {
    activeSnap.value += 1
  }

  dragOffset.value = 0
  touchStartY.value = null
}
</script>

<template>
  <div class="relative min-h-screen overflow-hidden bg-slate-100 text-slate-900">
    <div class="absolute inset-0 z-0">
      <slot name="map" />
    </div>

    <div
      v-if="!isMobile"
      class="pointer-events-none absolute inset-0 z-20"
      :style="{ '--panel-width': `${panelWidth}px` }"
    >
      <aside class="pointer-events-auto absolute bottom-5 left-5 top-5 w-[min(var(--panel-width),calc(100vw-40px))] min-w-0 overflow-hidden">
        <div class="grid h-full grid-cols-[1fr_10px] gap-2">
          <section
            data-testid="trip-layout-side-panel"
            class="h-full min-h-0 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_18px_45px_rgba(15,23,42,0.18)]"
          >
            <div class="result-panel-scroll h-full overflow-y-auto px-4 py-4">
              <slot name="panel" />
            </div>
          </section>

          <button
            type="button"
            aria-label="调整侧栏宽度"
            class="group relative h-full w-[10px] touch-none"
            @pointerdown.prevent="startResize"
          >
            <span
              class="absolute inset-y-10 left-1/2 w-[2px] -translate-x-1/2 rounded-full bg-slate-300 transition-all duration-200 ease-standard group-hover:w-[4px] group-hover:bg-sky-500"
            />
          </button>
        </div>
      </aside>

      <section class="pointer-events-none absolute inset-0">
        <slot name="over-map" />
      </section>
    </div>

    <div v-else class="pointer-events-none relative z-20 min-h-screen p-4">
      <slot name="over-map" />
    </div>

    <Teleport to="body">
      <slot name="modals" />
    </Teleport>

    <Transition name="slide-up">
      <section
        v-show="isMobile"
        class="fixed inset-x-0 bottom-0 z-30 px-2 pb-[env(safe-area-inset-bottom)]"
      >
        <div
          class="mx-auto flex max-w-xl flex-col overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-[0_-12px_32px_rgba(15,23,42,0.16)] transition-transform duration-300 ease-standard"
          :style="sheetStyle"
        >
          <div
            class="shrink-0 touch-none"
            @touchstart.passive="onSheetTouchStart"
            @touchmove.prevent="onSheetTouchMove"
            @touchend="onSheetTouchEnd"
          >
            <div class="flex items-center justify-center px-4 pt-3">
              <div class="h-1.5 w-14 rounded-full bg-slate-300/80" />
            </div>

            <header class="px-6 pb-4 pt-3">
              <p class="text-xs font-medium uppercase tracking-wider text-sky-600">
                {{ props.sheetPreview }}
              </p>
              <h2 class="mt-1 text-xl font-semibold tracking-tight text-slate-900">
                {{ props.sheetTitle }}
              </h2>
            </header>

            <div class="mx-6 border-t border-slate-200" />
          </div>

          <div
            v-show="true"
            data-testid="trip-layout-mobile-panel-scroll"
            class="min-h-0 flex-1 overscroll-contain overflow-y-auto px-6 pb-8 pt-5"
          >
            <slot name="panel" />
          </div>
        </div>
      </section>
    </Transition>
  </div>
</template>

<style scoped>
.result-panel-scroll {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.result-panel-scroll::-webkit-scrollbar {
  width: 8px;
}

.result-panel-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.result-panel-scroll::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}
</style>
