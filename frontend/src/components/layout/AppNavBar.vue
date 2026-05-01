<script setup lang="ts">
import { ChevronLeft, Compass } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

interface Props {
  title?: string
  subtitle?: string
  chips?: string[]
  backTo?: RouteLocationRaw | null
  backLabel?: string
}

withDefaults(defineProps<Props>(), {
  title: '',
  subtitle: '',
  chips: () => [],
  backTo: null,
  backLabel: '返回',
})
</script>

<template>
  <header class="sticky top-0 z-40 px-4 pt-4 md:px-6 lg:px-10">
    <div class="mx-auto max-w-[1440px]">
      <div class="glass-surface relative overflow-hidden rounded-[28px] border border-white/40 px-4 py-4 shadow-glass md:px-6">
        <div
          class="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.22),rgba(255,255,255,0.06)_36%,rgba(255,255,255,0.12))]"
        />

        <div class="relative grid gap-4 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center">
          <div class="flex flex-wrap items-center gap-3">
            <RouterLink
              v-if="backTo"
              :to="backTo"
              class="inline-flex items-center gap-2 rounded-full border border-white/40 bg-white/68 px-4 py-2 text-sm font-medium text-slate-700 transition-all duration-300 ease-standard hover:border-sky-200 hover:bg-white/84 hover:text-slate-900"
            >
              <ChevronLeft :size="16" />
              <span>{{ backLabel }}</span>
            </RouterLink>

            <RouterLink
              to="/"
              class="inline-flex items-center gap-3 rounded-full border border-white/40 bg-white/72 px-4 py-2 text-slate-900 shadow-sm transition-all duration-300 ease-standard hover:border-sky-200 hover:bg-white/88"
            >
              <span
                class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-emerald-400 text-white shadow-lg shadow-sky-500/20"
              >
                <Compass :size="18" />
              </span>

              <span class="min-w-0">
                <span class="block text-[11px] font-medium uppercase tracking-[0.22em] text-sky-600">
                  TravelPlanner
                </span>
                <strong class="block truncate text-sm font-semibold text-slate-900">
                  多 Agent 旅行规划
                </strong>
              </span>
            </RouterLink>
          </div>

          <div
            v-if="title || subtitle || chips.length"
            class="flex min-w-0 flex-col items-start gap-2 text-left lg:items-center lg:text-center"
          >
            <p
              v-if="subtitle"
              class="text-[11px] font-medium uppercase tracking-[0.22em] text-sky-600"
            >
              {{ subtitle }}
            </p>
            <h1
              v-if="title"
              class="font-display text-2xl font-light tracking-tight text-slate-900 md:text-3xl"
            >
              {{ title }}
            </h1>
            <div v-if="chips.length" class="flex flex-wrap gap-2 lg:justify-center">
              <span
                v-for="chip in chips"
                :key="chip"
                class="rounded-full bg-white/68 px-3 py-1 text-xs font-medium uppercase tracking-wider text-slate-600"
              >
                {{ chip }}
              </span>
            </div>
          </div>

          <div class="flex flex-wrap items-center justify-start gap-3 lg:justify-end">
            <slot name="actions" />
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
