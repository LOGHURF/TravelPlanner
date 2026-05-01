<script setup lang="ts">
import { computed } from 'vue'
import { VueDatePicker } from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'
import { zhCN } from 'date-fns/locale'
import { CalendarDays, Minus, Plus } from 'lucide-vue-next'

interface Props {
  startDate?: string
  endDate?: string
  minDays?: number
  maxDays?: number
}

type PickerInput = string | number | Date | null | undefined
type PickerRange = string[] | null

const props = withDefaults(defineProps<Props>(), {
  startDate: '',
  endDate: '',
  minDays: 1,
  maxDays: 14,
})

const emit = defineEmits<{
  'update:startDate': [value: string]
  'update:endDate': [value: string]
  change: [{ startDate: string; endDate: string; duration: number }]
}>()

const today = formatDateInput(new Date())
const quickDurations = [2, 3, 5, 7]
const rangeConfig = { partialRange: false, autoSwitchStartEnd: true }
const timeConfig = { enableTimePicker: false }

const selectedRange = computed<PickerRange>({
  get() {
    if (!props.startDate || !props.endDate) {
      return null
    }
    return [props.startDate, props.endDate]
  },
  set(value) {
    if (!Array.isArray(value) || !value[0]) {
      return
    }

    const startDate = toDateInput(value[0])
    const endDate = toDateInput(value[1] || value[0])
    if (startDate && endDate) {
      commitRange(startDate, endDate)
    }
  },
})

const duration = computed(() => {
  if (!props.startDate || !props.endDate) {
    return 0
  }

  const start = parseDateInput(props.startDate)
  const end = parseDateInput(props.endDate)
  if (!start || !end) {
    return 0
  }

  return Math.max(0, inclusiveDays(start, end))
})

const summary = computed(() => {
  if (!props.startDate || !props.endDate || !duration.value) {
    return '选择出行日期'
  }

  return `${formatShortDate(props.startDate)} - ${formatShortDate(props.endDate)}`
})

const dateInputLabel = computed(() => {
  if (!props.startDate || !props.endDate) {
    return '选择出行日期'
  }
  return `${props.startDate} - ${props.endDate}`
})

function parseDateInput(value: string) {
  const parts = value.split('-').map((part) => Number(part))
  if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part))) {
    return null
  }

  const [year, month, day] = parts
  if (!year || !month || !day) {
    return null
  }

  return new Date(year, month - 1, day)
}

function formatDateInput(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function toDateInput(value: PickerInput) {
  if (!value) {
    return ''
  }
  if (value instanceof Date) {
    return formatDateInput(value)
  }
  if (typeof value === 'number') {
    return formatDateInput(new Date(value))
  }
  return value.slice(0, 10)
}

function addDays(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function toUtcDay(date: Date) {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
}

function inclusiveDays(start: Date, end: Date) {
  return Math.floor((toUtcDay(end) - toUtcDay(start)) / 86_400_000) + 1
}

function clampDuration(value: number) {
  return Math.max(props.minDays, Math.min(props.maxDays, Math.round(value)))
}

function commitRange(startDate: string, endDate: string) {
  const start = parseDateInput(startDate)
  const end = parseDateInput(endDate)
  if (!start || !end) {
    return
  }

  const rawDuration = inclusiveDays(start, end)
  const nextDuration = clampDuration(rawDuration)
  const nextEnd = formatDateInput(addDays(start, nextDuration - 1))

  emit('update:startDate', startDate)
  emit('update:endDate', nextEnd)
  emit('change', {
    startDate,
    endDate: nextEnd,
    duration: nextDuration,
  })
}

function setDuration(value: number) {
  const start = parseDateInput(props.startDate) || addDays(new Date(), 1)
  const nextDuration = clampDuration(value)
  commitRange(formatDateInput(start), formatDateInput(addDays(start, nextDuration - 1)))
}

function formatShortDate(value: string) {
  const date = parseDateInput(value)
  if (!date) {
    return value
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

</script>

<template>
  <div class="date-range-picker grid gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
    <div class="flex items-center gap-2 text-sm font-medium text-slate-700">
      <CalendarDays class="h-4 w-4 shrink-0 text-sky-600" />
      <span class="min-w-0 flex-1 truncate">{{ summary }}</span>
      <span v-if="duration" class="tabular-nums text-slate-500">{{ duration }} 天</span>
    </div>

    <VueDatePicker
      v-model="selectedRange"
      model-type="yyyy-MM-dd"
      :range="rangeConfig"
      :min-date="today"
      :auto-apply="true"
      :clearable="false"
      format="yyyy-MM-dd"
      :time-config="timeConfig"
      :locale="zhCN"
      week-start="1"
      placeholder="选择出行日期"
    >
      <template #trigger>
        <button
          type="button"
          class="flex min-h-11 w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-semibold text-slate-950 transition-colors hover:border-sky-300 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
        >
          <CalendarDays class="h-4 w-4 shrink-0 text-slate-400" />
          <span class="min-w-0 flex-1 truncate">{{ dateInputLabel }}</span>
        </button>
      </template>
    </VueDatePicker>

    <div class="grid grid-cols-[40px_1fr_40px] items-center gap-2">
      <button
        type="button"
        class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 transition-colors hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-45"
        :disabled="duration <= props.minDays"
        aria-label="减少天数"
        @click="setDuration((duration || props.minDays) - 1)"
      >
        <Minus class="h-4 w-4" />
      </button>

      <label class="flex h-10 items-center justify-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-600">
        <input
          type="number"
          inputmode="numeric"
          :min="props.minDays"
          :max="props.maxDays"
          :value="duration || props.minDays"
          class="h-full w-10 appearance-none border-0 bg-transparent p-0 text-center text-base font-semibold tabular-nums text-slate-950 [outline:none] ring-0 focus:border-0 focus:[outline:none] focus:ring-0"
          aria-label="行程天数"
          @change="setDuration(Number(($event.target as HTMLInputElement).value || props.minDays))"
        />
        天
      </label>

      <button
        type="button"
        class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 transition-colors hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-45"
        :disabled="duration >= props.maxDays"
        aria-label="增加天数"
        @click="setDuration((duration || props.minDays) + 1)"
      >
        <Plus class="h-4 w-4" />
      </button>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="day in quickDurations"
        :key="day"
        type="button"
        class="h-8 rounded-lg border px-3 text-xs font-medium transition-colors"
        :class="duration === day
          ? 'border-sky-600 bg-sky-600 text-white'
          : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300 hover:text-sky-700'"
        @click="setDuration(day)"
      >
        {{ day }}天
      </button>
    </div>
  </div>
</template>

<style scoped>
.date-range-picker :deep(.dp__main) {
  font-family: inherit;
}

.date-range-picker :deep(.dp__theme_light) {
  --dp-primary-color: #0284c7;
  --dp-primary-text-color: #ffffff;
  --dp-border-color: #e2e8f0;
  --dp-border-color-hover: #7dd3fc;
  --dp-border-radius: 8px;
  --dp-cell-border-radius: 8px;
  --dp-font-size: 0.875rem;
}

.date-range-picker :deep(.dp__input) {
  min-height: 44px;
  border-radius: 8px;
  border-color: #e2e8f0;
  color: #0f172a;
  font-weight: 600;
}

.date-range-picker :deep(.dp__input:focus) {
  border-color: #38bdf8;
  box-shadow: 0 0 0 3px rgb(186 230 253 / 0.8);
}
</style>
