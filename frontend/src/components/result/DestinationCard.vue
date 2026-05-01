<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue'
import { MapPin, Star } from 'lucide-vue-next'
import GlassPanel from '@/components/ui/GlassPanel.vue'

const props = withDefaults(
  defineProps<{
    title: string
    image: string
    description: string
    location?: string
    price?: number | string
    rating?: number
    badge?: string
    compact?: boolean
  }>(),
  {
    location: '',
    price: '',
    rating: 0,
    badge: 'Recommended',
    compact: false,
  },
)

const injectedTheme = inject<ComputedRef<string> | string>('themeColor', '#0EA5E9')
const themeColor = computed(() =>
  typeof injectedTheme === 'string' ? injectedTheme : injectedTheme.value,
)

const priceLabel = computed(() => {
  if (props.price === '' || props.price === null || props.price === undefined) {
    return ''
  }
  return `¥${props.price}`
})
</script>

<template>
  <GlassPanel
    hoverable
    glow
    padding="sm"
    class="group h-full"
    :style="{ '--local-accent': themeColor }"
  >
    <article
      class="grid gap-4"
      :class="props.compact ? 'min-h-[280px] grid-rows-[190px_auto]' : 'min-h-[360px] grid-rows-[3fr_2fr]'"
    >
      <div class="relative overflow-hidden rounded-2xl">
        <img
          :src="props.image"
          :alt="props.title"
          class="aspect-[4/3] h-full w-full object-cover transition-transform duration-500 ease-standard group-hover:scale-[1.04]"
        >

        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/42 via-transparent to-white/6" />

        <div class="absolute left-4 top-4">
          <span
            class="rounded-full bg-emerald-500 font-semibold text-white shadow-sm"
            :class="props.compact ? 'px-2.5 py-1 text-xs' : 'px-3 py-1 text-sm'"
          >
            {{ priceLabel || '精选' }}
          </span>
        </div>

        <div
          class="absolute right-4 top-4 flex items-center gap-1 rounded-full bg-white/88 font-semibold text-slate-900 shadow-sm"
          :class="props.compact ? 'px-2.5 py-1 text-xs' : 'px-3 py-1 text-sm'"
        >
          <Star class="h-4 w-4 fill-current text-amber-400" />
          <span class="tabular-nums">{{ props.rating.toFixed(1) }}</span>
        </div>

        <div class="absolute bottom-4 left-4 right-4">
          <p class="font-medium uppercase tracking-wider text-white/90" :class="props.compact ? 'text-[11px]' : 'text-xs'">
            {{ props.badge }}
          </p>
        </div>
      </div>

      <div class="flex flex-col justify-between gap-4 px-1 pb-1">
        <div class="space-y-2">
          <h3 class="font-semibold leading-tight text-slate-900" :class="props.compact ? 'text-lg' : 'text-xl'">
            {{ props.title }}
          </h3>
          <p
            class="line-clamp-2 font-normal leading-relaxed text-slate-600"
            :class="props.compact ? 'text-sm' : 'text-base'"
          >
            {{ props.description }}
          </p>
        </div>

        <div class="space-y-3">
          <div class="glass-divider" />
          <div class="flex items-center justify-between gap-4 text-sm text-slate-500">
            <div class="flex min-w-0 items-center gap-2">
              <MapPin class="h-4 w-4 shrink-0 text-sky-600" />
              <span class="truncate">{{ props.location }}</span>
            </div>
            <span class="tabular-nums text-slate-500">{{ priceLabel || 'Custom' }}</span>
          </div>
        </div>
      </div>
    </article>
  </GlassPanel>
</template>
