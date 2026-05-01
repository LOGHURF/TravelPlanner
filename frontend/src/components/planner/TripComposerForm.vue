<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import {
  MapPin,
  Minus,
  Plus,
  Sparkles,
} from 'lucide-vue-next'
import { Button, Input, Pill } from '@/components/ui'
import DateRangePicker from '@/components/ui/DateRangePicker.vue'
import type { TripRequest } from '@/types/travel'

interface Props {
  initialData?: Partial<TripRequest> | null
  isSubmitting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  initialData: null,
  isSubmitting: false,
})

const emit = defineEmits<{
  submit: [payload: TripRequest]
}>()

const companionOptions = [
  { label: '独自', value: '独自' },
  { label: '情侣', value: '情侣' },
  { label: '朋友', value: '朋友' },
  { label: '家庭', value: '家庭' },
  { label: '老人', value: '老人' },
]

const hotelOptions = [
  { label: '经济型', value: '经济型' },
  { label: '舒适型', value: '舒适型' },
  { label: '高档型', value: '高档型' },
  { label: '豪华型', value: '豪华型' },
]

const paceOptions: Array<{ label: string; value: NonNullable<TripRequest['pace']> }> = [
  { label: '紧凑', value: '紧凑' },
  { label: '适中', value: '适中' },
  { label: '宽松', value: '宽松' },
]

const styleOptions = [
  { label: '文化体验', value: '文化体验' },
  { label: '自然风光', value: '自然风光' },
  { label: '历史古迹', value: '历史古迹' },
  { label: '休闲娱乐', value: '娱乐' },
]

function formatDateInput(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function createDefaults(): TripRequest {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const duration = 3

  return {
    destination: '',
    start_date: formatDateInput(tomorrow),
    end_date: formatDateInput(addDays(tomorrow, duration - 1)),
    duration,
    origin: '',
    num_people: 2,
    companions: '情侣',
    pace: '适中',
    style_preferences: ['文化体验', '自然风光'],
    hotel_level: '舒适型',
    special_requirements: '',
  }
}

const formState = reactive<TripRequest>(createDefaults())

watch(
  () => props.initialData,
  (value) => {
    Object.assign(formState, createDefaults(), value ?? {})
  },
  { immediate: true },
)

const destinationError = computed(() => {
  if (!formState.destination.trim()) {
    return '请输入目的地'
  }
  return ''
})

const isValid = computed(() => !destinationError.value)

function toggleStyle(value: string) {
  const current = formState.style_preferences || []
  if (current.includes(value)) {
    formState.style_preferences = current.filter((item) => item !== value)
    return
  }
  formState.style_preferences = [...current, value]
}

function updatePeople(delta: number) {
  const current = formState.num_people || 1
  formState.num_people = Math.max(1, Math.min(20, current + delta))
}

function choiceButtonClass(active: boolean) {
  return [
    'rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
    active
      ? 'border-sky-600 bg-sky-600 text-white shadow-sm shadow-sky-500/20'
      : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300 hover:text-slate-900',
  ]
}

function handleDateChange({
  startDate,
  endDate,
  duration,
}: {
  startDate: string
  endDate: string
  duration: number
}) {
  formState.start_date = startDate
  formState.end_date = endDate
  formState.duration = duration
}

function handleSubmit() {
  if (!isValid.value) {
    return
  }

  emit('submit', {
    destination: formState.destination.trim(),
    start_date: formState.start_date,
    end_date: formState.end_date,
    duration: formState.duration,
    origin: formState.origin?.trim() || '',
    num_people: formState.num_people || 1,
    companions: formState.companions,
    pace: formState.pace,
    style_preferences: [...(formState.style_preferences || [])],
    hotel_level: formState.hotel_level,
    special_requirements: formState.special_requirements?.trim() || '',
  })
}

defineExpose({
  formState,
  isValid,
  setDestination: (destination: string) => {
    formState.destination = destination
  },
})
</script>

<template>
  <section id="planner-form" class="relative">
    <div class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_18px_50px_rgba(15,23,42,0.12)]">
      <div class="border-b border-slate-200 bg-slate-50 px-4 py-4 md:px-5">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-[0.16em] text-sky-600">
              TravelPlanner
            </p>
            <h1 class="mt-1 text-xl font-semibold tracking-tight text-slate-950 md:text-2xl">
              开始规划行程
            </h1>
          </div>
          <p class="text-sm text-slate-500">
            目的地、日期、偏好一次填完。
          </p>
        </div>
      </div>

      <form class="grid gap-5 px-4 py-5 md:px-5" @submit.prevent="handleSubmit">
        <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div class="grid min-w-0 gap-4">
            <div class="grid gap-4 sm:grid-cols-2">
              <Input
                v-model="formState.destination"
                label="目的地"
                size="md"
                placeholder="例如：杭州 / 成都 / 北京"
                :error="destinationError"
                required
              />

              <Input
                v-model="formState.origin"
                label="出发地（可选）"
                placeholder="例如：上海"
              >
                <template #prefix>
                  <MapPin class="h-4 w-4 shrink-0 text-slate-400" />
                </template>
              </Input>
            </div>

            <div class="grid gap-4 xl:grid-cols-[180px_1fr]">
              <div class="space-y-2">
                <label class="text-sm font-medium text-slate-700">人数</label>
                <div class="grid h-10 grid-cols-[40px_1fr_40px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                  <button
                    type="button"
                    class="flex items-center justify-center text-slate-600 transition-colors hover:bg-slate-50 hover:text-sky-700 disabled:opacity-40"
                    :disabled="(formState.num_people || 1) <= 1"
                    aria-label="减少人数"
                    @click="updatePeople(-1)"
                  >
                    <Minus class="h-4 w-4" />
                  </button>
                  <strong class="flex items-center justify-center border-x border-slate-200 text-sm tabular-nums text-slate-950">
                    {{ formState.num_people || 1 }} 人
                  </strong>
                  <button
                    type="button"
                    class="flex items-center justify-center text-slate-600 transition-colors hover:bg-slate-50 hover:text-sky-700 disabled:opacity-40"
                    :disabled="(formState.num_people || 1) >= 20"
                    aria-label="增加人数"
                    @click="updatePeople(1)"
                  >
                    <Plus class="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div class="space-y-2">
                <label class="text-sm font-medium text-slate-700">旅行节奏</label>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="option in paceOptions"
                    :key="option.value"
                    type="button"
                    :aria-pressed="formState.pace === option.value"
                    :class="choiceButtonClass(formState.pace === option.value)"
                    @click="formState.pace = option.value"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </div>
            </div>

            <div class="grid gap-4 lg:grid-cols-2">
              <div class="space-y-2">
                <label class="text-sm font-medium text-slate-700">同行关系</label>
                <Pill v-model="formState.companions" :options="companionOptions" size="sm" />
              </div>

              <div class="space-y-2">
                <label class="text-sm font-medium text-slate-700">住宿偏好</label>
                <Pill v-model="formState.hotel_level" :options="hotelOptions" size="sm" />
              </div>
            </div>
          </div>

          <div class="min-w-0">
            <label class="mb-2 block text-sm font-medium text-slate-700">出行日期</label>
            <DateRangePicker
              v-model:start-date="formState.start_date"
              v-model:end-date="formState.end_date"
              :min-days="1"
              :max-days="14"
              @change="handleDateChange"
            />
          </div>
        </div>

        <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div class="space-y-3">
            <label class="text-sm font-medium text-slate-700">偏好风格</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in styleOptions"
                :key="option.value"
                type="button"
                :aria-pressed="formState.style_preferences?.includes(option.value)"
                :class="choiceButtonClass(Boolean(formState.style_preferences?.includes(option.value)))"
                @click="toggleStyle(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <div class="space-y-3">
            <label class="text-sm font-medium text-slate-700">补充要求</label>
            <textarea
              v-model="formState.special_requirements"
              class="min-h-24 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm leading-relaxed text-slate-900 [outline:none] transition-colors placeholder:text-slate-400 focus:border-sky-400 focus:[outline:none] focus:ring-2 focus:ring-sky-100"
              placeholder="夜景、拍照、少走路等"
            />
          </div>
        </div>

        <div class="flex justify-end border-t border-slate-100 pt-4">
          <div class="w-full sm:w-auto sm:min-w-52">
            <Button
              type="submit"
              size="lg"
              block
              :loading="props.isSubmitting"
              :disabled="!isValid"
            >
              <Sparkles :size="18" />
              {{ props.isSubmitting ? '正在生成规划...' : '立即开始规划' }}
            </Button>
          </div>
        </div>
      </form>
    </div>
  </section>
</template>
