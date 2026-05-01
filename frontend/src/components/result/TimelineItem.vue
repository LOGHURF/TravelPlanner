<script setup lang="ts">
withDefaults(
  defineProps<{
    time: string
    title: string
    caption?: string
    terminal?: boolean
  }>(),
  {
    caption: '',
    terminal: false,
  },
)
</script>

<template>
  <article class="relative grid grid-cols-[72px_1fr] gap-4">
    <div class="pt-1 text-sm font-medium tabular-nums text-slate-500">
      {{ time }}
    </div>

    <div class="relative pb-6" :class="terminal && 'pb-0'">
      <span class="absolute left-[5px] top-1.5 h-3 w-3 rounded-full bg-gradient-to-b from-sky-500 to-emerald-400 shadow-sm shadow-sky-300/60" />
      <span
        v-if="!terminal"
        class="absolute left-[10px] top-5 w-0.5 rounded-full bg-[linear-gradient(180deg,rgba(14,165,233,0.65)_0%,rgba(16,185,129,0.55)_100%)]"
        :style="{ height: 'calc(100% - 12px)' }"
      />

      <div class="ml-8">
        <p class="text-base font-semibold leading-tight text-slate-900">
          {{ title }}
        </p>
        <p v-if="caption" class="mt-1 text-sm leading-relaxed text-slate-500">
          {{ caption }}
        </p>
      </div>
    </div>
  </article>
</template>
